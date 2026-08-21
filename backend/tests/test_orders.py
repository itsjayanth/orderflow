import datetime
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import MenuItemRepository
from customers.adapters.repository import AddressRepository, CustomerRepository
from identity.adapters.repository import MerchantRepository
from orders.adapters.repository import OrderItemInput, OrderNotFoundError, OrderRepository
from orders.domain.models import OrderStatusEvent
from orders.domain.state_machine import IllegalTransitionError
from payments.domain.models import PaymentEvent
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
    payment_method: str = "online",
    customer_whatsapp_number: str = "+919876543210",
    customer_display_name: str | None = None,
    placed_at: datetime.datetime | None = None,
    order_type: str = "pickup",
    delivery_address_id: uuid.UUID | None = None,
):
    customer = await CustomerRepository(db_session).find_or_create(
        tenant, customer_whatsapp_number, display_name=customer_display_name
    )
    menu_item = await MenuItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    order = await OrderRepository(db_session).create(
        tenant,
        customer_id=customer.customer_id,
        order_type=order_type,
        payment_method=payment_method,
        payment_status=payment_status,
        fulfillment_status=fulfillment_status,
        delivery_address_id=delivery_address_id,
        items=[
            OrderItemInput(
                menu_item_id=menu_item.menu_item_id,
                name_snapshot=menu_item.name,
                price_snapshot=menu_item.price,
                quantity=2,
            )
        ],
    )
    if placed_at is not None:
        order.placed_at = placed_at
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


async def test_order_numbers_increment_sequentially_per_merchant(
    db_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(db_session)
    first = await _seed_order(db_session, tenant)
    second = await _seed_order(db_session, tenant)
    third = await _seed_order(db_session, tenant)

    assert [first.order_number, second.order_number, third.order_number] == [1, 2, 3]


async def test_order_numbers_isolated_per_merchant(db_session: AsyncSession) -> None:
    tenant_a = await _make_tenant(db_session, business_name="Kitchen A")
    tenant_b = await _make_tenant(db_session, business_name="Kitchen B")

    order_a1 = await _seed_order(db_session, tenant_a)
    order_b1 = await _seed_order(db_session, tenant_b)
    order_a2 = await _seed_order(db_session, tenant_a)

    assert order_a1.order_number == 1
    assert order_b1.order_number == 1
    assert order_a2.order_number == 2


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
    order = await _seed_order(db_session, tenant, customer_display_name="Asha Rao")

    response = await client.get("/api/v1/orders", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["order_id"] == str(order.order_id)
    assert body[0]["order_number"] == order.order_number
    assert body[0]["fulfillment_status"] == "new"
    assert body[0]["customer_name"] == "Asha Rao"
    assert body[0]["customer_whatsapp_number"] == "+919876543210"
    assert body[0]["customer_number"] == 1


async def test_list_orders_customer_name_null_when_no_display_name_set(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _seed_order(db_session, tenant, customer_display_name=None)

    response = await client.get("/api/v1/orders", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["customer_name"] is None
    assert body[0]["customer_whatsapp_number"] == "+919876543210"


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
    order = await _seed_order(db_session, tenant, customer_display_name="Asha Rao")

    response = await client.get(f"/api/v1/orders/{order.order_id}", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["name_snapshot"] == "Butter Chicken"
    assert body["customer_name"] == "Asha Rao"
    assert body["customer_whatsapp_number"] == "+919876543210"


async def test_get_order_detail_customer_name_null_when_no_display_name_set(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    order = await _seed_order(db_session, tenant, customer_display_name=None)

    response = await client.get(f"/api/v1/orders/{order.order_id}", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert body["customer_name"] is None
    assert body["customer_whatsapp_number"] == "+919876543210"


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


# --- Dashboard edit: contact_phone --------------------------------------


async def test_update_order_contact_phone(client: AsyncClient, db_session: AsyncSession) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    order = await _seed_order(db_session, tenant)

    response = await client.patch(
        f"/api/v1/orders/{order.order_id}",
        json={"contact_phone": "+919876500000"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    assert response.json()["contact_phone"] == "+919876500000"


async def test_update_order_not_found(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.patch(
        f"/api/v1/orders/{uuid.uuid4()}",
        json={"contact_phone": "+919876500000"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 404


async def test_update_order_notes(client: AsyncClient, db_session: AsyncSession) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    order = await _seed_order(db_session, tenant)

    response = await client.patch(
        f"/api/v1/orders/{order.order_id}",
        json={"notes": "No onion, call before delivering"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    assert response.json()["notes"] == "No onion, call before delivering"


async def test_update_order_notes_and_contact_phone_independently(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Sending only one field must not clobber the other (exclude_unset
    semantics, same as CustomerRepository.update / MenuItemRepository.update)."""
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    order = await _seed_order(db_session, tenant)

    await client.patch(
        f"/api/v1/orders/{order.order_id}",
        json={"contact_phone": "+919876500000"},
        headers=_auth_headers(tokens),
    )
    response = await client.patch(
        f"/api/v1/orders/{order.order_id}",
        json={"notes": "Extra spicy"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["notes"] == "Extra spicy"
    assert body["contact_phone"] == "+919876500000"


# --- Order detail: delivery address embed ---------------------------------


async def test_get_order_detail_includes_delivery_address_for_delivery_order(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    address = await AddressRepository(db_session).create(
        tenant,
        customer.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
        is_default=True,
    )
    await db_session.commit()
    order = await _seed_order(
        db_session, tenant, order_type="delivery", delivery_address_id=address.address_id
    )

    response = await client.get(f"/api/v1/orders/{order.order_id}", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert body["delivery_address"] is not None
    assert body["delivery_address"]["line1"] == "12 MG Road"
    assert body["delivery_address"]["city"] == "Bengaluru"


async def test_get_order_detail_delivery_address_null_for_pickup_order(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    order = await _seed_order(db_session, tenant, order_type="pickup")

    response = await client.get(f"/api/v1/orders/{order.order_id}", headers=_auth_headers(tokens))

    assert response.status_code == 200
    assert response.json()["delivery_address"] is None


# --- List filtering by customer_id ----------------------------------------


async def test_list_orders_filtered_by_customer_id(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    matching = await _seed_order(db_session, tenant, customer_whatsapp_number="+919876543210")
    await _seed_order(db_session, tenant, customer_whatsapp_number="+919876543211")

    response = await client.get(
        "/api/v1/orders",
        params={"customer_id": str(matching.customer_id)},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["order_id"] == str(matching.order_id)


# --- Dashboard action: collect COD payment -------------------------------


async def test_collect_cod_payment_happy_path(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    order = await _seed_order(
        db_session,
        tenant,
        payment_status="cod_pending",
        fulfillment_status="new",
        payment_method="cod",
    )

    response = await client.post(
        f"/api/v1/orders/{order.order_id}/collect-cod-payment", headers=_auth_headers(tokens)
    )

    assert response.status_code == 200
    assert response.json()["payment_status"] == "cod_collected"


async def test_collect_cod_payment_records_payment_event(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    order = await _seed_order(
        db_session,
        tenant,
        payment_status="cod_pending",
        fulfillment_status="new",
        payment_method="cod",
    )

    await client.post(
        f"/api/v1/orders/{order.order_id}/collect-cod-payment", headers=_auth_headers(tokens)
    )

    result = await db_session.execute(
        select(PaymentEvent).where(PaymentEvent.order_id == order.order_id)
    )
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].event_type == "cod_collected"
    assert events[0].provider == "cod"


async def test_collect_cod_payment_rejects_already_paid_order(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    order = await _seed_order(
        db_session,
        tenant,
        payment_status="paid",
        fulfillment_status="new",
        payment_method="online",
    )

    response = await client.post(
        f"/api/v1/orders/{order.order_id}/collect-cod-payment", headers=_auth_headers(tokens)
    )

    assert response.status_code == 409


async def test_collect_cod_payment_not_found(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.post(
        f"/api/v1/orders/{uuid.uuid4()}/collect-cod-payment", headers=_auth_headers(tokens)
    )

    assert response.status_code == 404


# --- Dashboard summary --------------------------------------------------


async def test_get_summary_aggregates_across_orders(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    # Each seeded order is 2x Butter Chicken @ 349.00 = 698.00.
    await _seed_order(
        db_session, tenant, payment_status="paid", fulfillment_status="new", payment_method="online"
    )
    await _seed_order(
        db_session,
        tenant,
        payment_status="cod_collected",
        fulfillment_status="completed",
        payment_method="cod",
    )
    await _seed_order(
        db_session,
        tenant,
        payment_status="cod_pending",
        fulfillment_status="preparing",
        payment_method="cod",
    )
    await _seed_order(
        db_session, tenant, payment_status="cancelled", fulfillment_status="cancelled"
    )

    response = await client.get("/api/v1/orders/summary", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert body["total_orders"] == 4
    # Generated excludes the cancelled order: 3 * 698.00 = 2094.00.
    assert body["revenue_generated"] == "2094.00"
    # Collected is narrower still -- only paid + cod_collected: 2 * 698.00.
    assert body["amount_collected"] == "1396.00"
    assert body["cod_orders"] == 2
    assert body["new_orders"] == 1
    assert body["preparing_orders"] == 1
    assert body["ready_orders"] == 0
    assert body["completed_orders"] == 1
    assert body["cancelled_orders"] == 1


async def test_get_summary_isolated_between_merchants(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens_a = await _register(client, owner_contact="summary-a@example.com")
    tenant_a = await _tenant_for(client, tokens_a)
    tokens_b = await _register(client, owner_contact="summary-b@example.com")
    await _seed_order(db_session, tenant_a)

    response = await client.get("/api/v1/orders/summary", headers=_auth_headers(tokens_b))

    assert response.status_code == 200
    body = response.json()
    assert body["total_orders"] == 0
    assert Decimal(body["revenue_generated"]) == 0


# --- Date-range filtering -------------------------------------------------


async def test_list_orders_filtered_by_date_range(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _seed_order(
        db_session, tenant, placed_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    )
    in_range = await _seed_order(
        db_session, tenant, placed_at=datetime.datetime(2026, 1, 15, tzinfo=datetime.UTC)
    )
    await _seed_order(
        db_session, tenant, placed_at=datetime.datetime(2026, 2, 1, tzinfo=datetime.UTC)
    )

    response = await client.get(
        "/api/v1/orders",
        params={"from_date": "2026-01-10", "to_date": "2026-01-20"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["order_id"] == str(in_range.order_id)


async def test_list_orders_date_range_is_inclusive_of_to_date(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    # 23:59 on the to_date boundary should still be included -- the filter
    # covers the whole calendar day, not just midnight.
    await _seed_order(
        db_session, tenant, placed_at=datetime.datetime(2026, 1, 20, 23, 59, tzinfo=datetime.UTC)
    )

    response = await client.get(
        "/api/v1/orders",
        params={"from_date": "2026-01-20", "to_date": "2026-01-20"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_list_orders_date_range_excluding_all_orders_returns_empty(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _seed_order(
        db_session, tenant, placed_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    )

    response = await client.get(
        "/api/v1/orders",
        params={"from_date": "2026-06-01", "to_date": "2026-06-30"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    assert response.json() == []


async def test_list_orders_combines_date_range_with_fulfillment_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _seed_order(
        db_session,
        tenant,
        fulfillment_status="new",
        placed_at=datetime.datetime(2026, 1, 15, tzinfo=datetime.UTC),
    )
    matching = await _seed_order(
        db_session,
        tenant,
        fulfillment_status="preparing",
        placed_at=datetime.datetime(2026, 1, 15, tzinfo=datetime.UTC),
    )
    await _seed_order(
        db_session,
        tenant,
        fulfillment_status="preparing",
        placed_at=datetime.datetime(2026, 3, 1, tzinfo=datetime.UTC),
    )

    response = await client.get(
        "/api/v1/orders",
        params={
            "fulfillment_status": "preparing",
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
        },
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["order_id"] == str(matching.order_id)


async def test_get_summary_filtered_by_date_range(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    # Each seeded order is 2x Butter Chicken @ 349.00 = 698.00.
    await _seed_order(
        db_session, tenant, placed_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    )
    await _seed_order(
        db_session, tenant, placed_at=datetime.datetime(2026, 1, 15, tzinfo=datetime.UTC)
    )
    await _seed_order(
        db_session, tenant, placed_at=datetime.datetime(2026, 2, 1, tzinfo=datetime.UTC)
    )

    response = await client.get(
        "/api/v1/orders/summary",
        params={"from_date": "2026-01-01", "to_date": "2026-01-31"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_orders"] == 2
    assert body["revenue_generated"] == "1396.00"


async def test_get_summary_date_range_excluding_all_orders_returns_zeroes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _seed_order(
        db_session, tenant, placed_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    )

    response = await client.get(
        "/api/v1/orders/summary",
        params={"from_date": "2026-06-01", "to_date": "2026-06-30"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_orders"] == 0
    assert Decimal(body["revenue_generated"]) == 0


async def test_get_summary_without_date_params_matches_all_time_behavior(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Omitting from_date/to_date must behave exactly as before this
    feature -- the all-time aggregate, unfiltered."""
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _seed_order(
        db_session, tenant, placed_at=datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC)
    )
    await _seed_order(
        db_session, tenant, placed_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    )

    response = await client.get("/api/v1/orders/summary", headers=_auth_headers(tokens))

    assert response.status_code == 200
    assert response.json()["total_orders"] == 2
