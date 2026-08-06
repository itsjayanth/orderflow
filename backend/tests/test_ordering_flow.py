import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import MenuItemRepository
from shared.tenant import TenantContext


async def _register(client: AsyncClient, owner_contact: str = "owner@example.com") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "business_name": "Public Kitchen",
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


async def test_public_menu_requires_no_auth(client: AsyncClient, db_session: AsyncSession) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await MenuItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    await db_session.commit()

    response = await client.get(f"/api/v1/ordering-flow/{tenant.merchant_id}/menu")

    assert response.status_code == 200
    body = response.json()
    assert body["business_name"] == "Public Kitchen"
    assert len(body["items"]) == 1
    assert body["items"][0]["name"] == "Butter Chicken"


async def test_public_menu_excludes_unavailable_items(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    menu_repo = MenuItemRepository(db_session)
    available = await menu_repo.create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    unavailable = await menu_repo.create(
        tenant, category="Mains", name="Sold Out Dish", price=Decimal("199.00")
    )
    await menu_repo.update(tenant, unavailable.menu_item_id, is_available=False)
    await db_session.commit()

    response = await client.get(f"/api/v1/ordering-flow/{tenant.merchant_id}/menu")

    names = {item["name"] for item in response.json()["items"]}
    assert names == {"Butter Chicken"}
    assert available.menu_item_id  # sanity: fixture actually created


async def test_public_menu_unknown_merchant_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/ordering-flow/{uuid.uuid4()}/menu")

    assert response.status_code == 404


async def test_public_checkout_online_creates_order_with_link(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    menu_item = await MenuItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/ordering-flow/{tenant.merchant_id}/checkout",
        json={
            "customer_whatsapp_number": "+919876543210",
            "customer_display_name": "Asha",
            "items": [{"menu_item_id": str(menu_item.menu_item_id), "quantity": 1}],
            "payment_method": "online",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["payment_status"] == "awaiting_payment"
    assert body["payment_link_url"].startswith("https://dummy-checkout.orderflow.local/pay/")

    # Shows up on the merchant's dashboard immediately, no separate wiring.
    orders_response = await client.get("/api/v1/orders", headers=_auth_headers(tokens))
    assert len(orders_response.json()) == 1


async def test_public_checkout_cod_gates_straight_to_new(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    menu_item = await MenuItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/ordering-flow/{tenant.merchant_id}/checkout",
        json={
            "customer_whatsapp_number": "+919876543210",
            "items": [{"menu_item_id": str(menu_item.menu_item_id), "quantity": 1}],
            "payment_method": "cod",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["payment_status"] == "cod_pending"
    assert body["fulfillment_status"] == "new"


async def test_public_checkout_unknown_menu_item_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/ordering-flow/{tenant.merchant_id}/checkout",
        json={
            "customer_whatsapp_number": "+919876543210",
            "items": [{"menu_item_id": str(uuid.uuid4()), "quantity": 1}],
        },
    )

    assert response.status_code == 404


async def test_public_checkout_unknown_merchant_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/ordering-flow/{uuid.uuid4()}/checkout",
        json={"customer_whatsapp_number": "+919876543210", "items": []},
    )

    assert response.status_code == 404


async def test_public_checkout_isolated_between_merchants(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    tenant_a = await _tenant_for(client, tokens_a)
    tokens_b = await _register(client, owner_contact="owner-b@example.com")
    tenant_b = await _tenant_for(client, tokens_b)
    menu_item_b = await MenuItemRepository(db_session).create(
        tenant_b, category="Mains", name="Only At B", price=Decimal("100.00")
    )
    await db_session.commit()

    # Ordering from A's public menu page but referencing B's item id 404s.
    response = await client.post(
        f"/api/v1/ordering-flow/{tenant_a.merchant_id}/checkout",
        json={
            "customer_whatsapp_number": "+919876543210",
            "items": [{"menu_item_id": str(menu_item_b.menu_item_id), "quantity": 1}],
        },
    )

    assert response.status_code == 404
