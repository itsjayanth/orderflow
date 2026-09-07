"""Regression coverage for PLAN.md item 2 ("Checkout transaction
ordering"): perform_checkout's online-payment branch must commit the
Order row *before* calling out to the payment gateway, not after. If the
gateway call raises (or the process dies before a later commit), the
order must still be durably persisted in `awaiting_payment` -- never a
phantom order rolled back underneath a live payment link, and never an
order silently lost."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import ItemRepository
from identity.adapters.repository import MerchantRepository
from ordering_flow.domain.checkout import CheckoutItem, perform_checkout
from orders.adapters.repository import OrderRepository
from shared.tenant import TenantContext


class _ExplodingGateway:
    def create_link(self, *, entity_id: uuid.UUID, amount: Decimal, currency: str):
        raise RuntimeError("razorpay is down")


async def _make_tenant(db_session: AsyncSession) -> TenantContext:
    merchant = await MerchantRepository(db_session).create(
        business_name="Transaction Ordering Business", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    return TenantContext(merchant_id=merchant.merchant_id)


async def _make_item(db_session: AsyncSession, tenant: TenantContext):
    return await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )


async def test_online_checkout_order_survives_gateway_failure(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The core regression: gateway.create_link() raising after the order
    is created must NOT roll back the order -- it was already committed."""
    tenant = await _make_tenant(db_session)
    item = await _make_item(db_session, tenant)
    await db_session.commit()

    monkeypatch.setattr(
        "ordering_flow.domain.checkout.get_payment_gateway",
        lambda key_id, key_secret: _ExplodingGateway(),
    )

    with pytest.raises(RuntimeError, match="razorpay is down"):
        await perform_checkout(
            db_session,
            tenant,
            customer_whatsapp_number="+919876543210",
            items=[CheckoutItem(item_id=item.item_id, quantity=1)],
            payment_method="online",
            customer_display_name="Asha",
        )

    orders = await OrderRepository(db_session).list(tenant)
    assert len(orders) == 1
    assert orders[0].payment_status == "awaiting_payment"
    assert orders[0].fulfillment_status is None


async def test_online_checkout_endpoint_returns_5xx_and_persists_order_on_gateway_failure(
    client, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same failure, exercised through the public checkout endpoint --
    the router has no try/except around perform_checkout for anything but
    ItemNotFoundError, so this must surface as an unhandled exception
    (FastAPI's default 500), not a silently-dropped order."""
    tokens_response = await client.post(
        "/api/v1/auth/register",
        json={
            "business_name": "Endpoint Ordering Business",
            "owner_name": "Jane Owner",
            "owner_contact": f"{uuid.uuid4()}@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert tokens_response.status_code == 201, tokens_response.text
    tokens = tokens_response.json()
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    tenant = TenantContext(merchant_id=uuid.UUID(me.json()["merchant"]["merchant_id"]))

    item = await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    await db_session.commit()

    monkeypatch.setattr(
        "ordering_flow.domain.checkout.get_payment_gateway",
        lambda key_id, key_secret: _ExplodingGateway(),
    )

    with pytest.raises(RuntimeError, match="razorpay is down"):
        await client.post(
            f"/api/v1/ordering-flow/{tenant.merchant_id}/checkout",
            json={
                "customer_whatsapp_number": "+919876543210",
                "customer_display_name": "Asha",
                "items": [{"item_id": str(item.item_id), "quantity": 1}],
                "payment_method": "online",
            },
        )

    orders = await OrderRepository(db_session).list(tenant)
    assert len(orders) == 1
    assert orders[0].payment_status == "awaiting_payment"
