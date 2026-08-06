import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import MenuItemRepository
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from orders.adapters.repository import OrderItemInput, OrderNotFoundError, OrderRepository
from orders.domain.models import OrderStatusEvent
from orders.domain.state_machine import IllegalTransitionError
from shared.tenant import TenantContext


async def _make_tenant(
    db_session: AsyncSession, business_name: str = "Test Kitchen"
) -> TenantContext:
    merchant = await MerchantRepository(db_session).create(
        business_name=business_name, owner_contact=f"{uuid.uuid4()}@example.com"
    )
    return TenantContext(merchant_id=merchant.merchant_id)


async def _register(client: AsyncClient, owner_contact: str = "owner@example.com") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "business_name": "Test Kitchen",
            "owner_name": "Jane Owner",
            "owner_contact": owner_contact,
            "password": "correct-horse-battery-staple",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _tenant_for(client: AsyncClient, tokens: dict) -> TenantContext:
    me = await client.get("/api/v1/auth/me", headers=_auth_headers(tokens))
    assert me.status_code == 200
    return TenantContext(merchant_id=uuid.UUID(me.json()["merchant"]["merchant_id"]))


async def _seed_order(
    db_session: AsyncSession,
    tenant: TenantContext,
    *,
    payment_status: str = "paid",
    fulfillment_status: str | None = "new",
):
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    menu_item = await MenuItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    order = await OrderRepository(db_session).create(
        tenant,
        customer_id=customer.customer_id,
        order_type="pickup",
        payment_method="online",
        payment_status=payment_status,
        fulfillment_status=fulfillment_status,
        items=[
            OrderItemInput(
                menu_item_id=menu_item.menu_item_id,
                name_snapshot=menu_item.name,
                price_snapshot=menu_item.price,
                quantity=2,
            )
        ],
    )
    await db_session.commit()
    return order


# --- OrderRepository.create + snapshotting ----------------------------------


async def test_create_snapshots_items_and_computes_total(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    order = await _seed_order(db_session, tenant)

    assert len(order.items) == 1
    assert order.items[0].name_snapshot == "Butter Chicken"
    assert order.items[0].line_total == Decimal("698.00")
    assert order.subtotal == Decimal("698.00")
    assert order.total == Decimal("698.00")


# --- repository-level "defense in depth" transition test --------------------


async def test_repository_rejects_illegal_transition(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    order = await _seed_order(db_session, tenant, fulfillment_status="new")
    repo = OrderRepository(db_session)

    with pytest.raises(IllegalTransitionError):
        await repo.transition_fulfillment_status(
            tenant, order.order_id, "completed", changed_by="staff-1"
        )


async def test_repository_transition_writes_status_event(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    order = await _seed_order(db_session, tenant, fulfillment_status="new")
    repo = OrderRepository(db_session)

    await repo.transition_fulfillment_status(
        tenant, order.order_id, "preparing", changed_by="staff-1"
    )

    result = await db_session.execute(
        select(OrderStatusEvent).where(OrderStatusEvent.order_id == order.order_id)
    )
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].from_status == "new"
    assert events[0].to_status == "preparing"
    assert events[0].changed_by == "staff-1"


async def test_repository_transition_nonexistent_order_raises(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    repo = OrderRepository(db_session)

    with pytest.raises(OrderNotFoundError):
        await repo.transition_fulfillment_status(
            tenant, uuid.uuid4(), "preparing", changed_by="staff-1"
        )


# --- API endpoints ------------------------------------------------------


async def test_list_orders_empty(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.get("/api/v1/orders", headers=_auth_headers(tokens))

    assert response.status_code == 200
    assert response.json() == []


async def test_list_orders_returns_seeded_order(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    order = await _seed_order(db_session, tenant)

    response = await client.get("/api/v1/orders", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["order_id"] == str(order.order_id)
    assert body[0]["fulfillment_status"] == "new"


async def test_list_orders_filtered_by_fulfillment_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _seed_order(db_session, tenant, fulfillment_status="new")
    await _seed_order(db_session, tenant, fulfillment_status="preparing")

    response = await client.get(
        "/api/v1/orders", params={"fulfillment_status": "preparing"}, headers=_auth_headers(tokens)
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["fulfillment_status"] == "preparing"


async def test_get_order_detail_includes_items(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    order = await _seed_order(db_session, tenant)

    response = await client.get(f"/api/v1/orders/{order.order_id}", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["name_snapshot"] == "Butter Chicken"


async def test_get_order_not_found(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.get(f"/api/v1/orders/{uuid.uuid4()}", headers=_auth_headers(tokens))

    assert response.status_code == 404


async def test_update_fulfillment_status_happy_path(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    order = await _seed_order(db_session, tenant, fulfillment_status="new")

    response = await client.patch(
        f"/api/v1/orders/{order.order_id}/fulfillment-status",
        json={"to_status": "preparing"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    assert response.json()["fulfillment_status"] == "preparing"


async def test_update_fulfillment_status_sets_ready_at(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    order = await _seed_order(db_session, tenant, fulfillment_status="preparing")

    response = await client.patch(
        f"/api/v1/orders/{order.order_id}/fulfillment-status",
        json={"to_status": "ready"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    assert response.json()["ready_at"] is not None


async def test_update_fulfillment_status_illegal_transition_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    order = await _seed_order(db_session, tenant, fulfillment_status="new")

    response = await client.patch(
        f"/api/v1/orders/{order.order_id}/fulfillment-status",
        json={"to_status": "completed"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 409


async def test_update_fulfillment_status_invalid_value_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    order = await _seed_order(db_session, tenant, fulfillment_status="new")

    response = await client.patch(
        f"/api/v1/orders/{order.order_id}/fulfillment-status",
        json={"to_status": "not-a-real-status"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 422


async def test_orders_isolated_between_merchants(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    tenant_a = await _tenant_for(client, tokens_a)
    tokens_b = await _register(client, owner_contact="owner-b@example.com")
    order_a = await _seed_order(db_session, tenant_a)

    list_response = await client.get("/api/v1/orders", headers=_auth_headers(tokens_b))
    assert list_response.status_code == 200
    assert list_response.json() == []

    detail_response = await client.get(
        f"/api/v1/orders/{order_a.order_id}", headers=_auth_headers(tokens_b)
    )
    assert detail_response.status_code == 404

    update_response = await client.patch(
        f"/api/v1/orders/{order_a.order_id}/fulfillment-status",
        json={"to_status": "preparing"},
        headers=_auth_headers(tokens_b),
    )
    assert update_response.status_code == 404
