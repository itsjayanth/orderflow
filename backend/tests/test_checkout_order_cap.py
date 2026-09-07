"""Order-cap soft-block enforcement in perform_checkout() (Phase 17,
PLAN.md open question 5: soft-block, never reject). An order always
succeeds regardless of billing state -- these tests assert the order is
created either way, and that a BillingEvent(event_type="order_cap_exceeded")
row is written only once the merchant's effective tier is at/over its
order cap for the current billing cycle."""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from billing.adapters.repository import PlanRepository, SubscriptionRepository
from billing.domain.models import BillingEvent
from billing.domain.state_machine import transition_subscription_status
from catalog.adapters.repository import ItemRepository
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from ordering_flow.domain.checkout import CheckoutItem, perform_checkout
from orders.adapters.repository import OrderItemInput, OrderRepository
from shared.tenant import TenantContext


async def _make_tenant(db_session: AsyncSession) -> TenantContext:
    merchant = await MerchantRepository(db_session).create(
        business_name="Checkout Cap Business", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    return TenantContext(merchant_id=merchant.merchant_id)


async def _make_item(db_session: AsyncSession, tenant: TenantContext):
    return await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )


async def _billing_events(db_session: AsyncSession, tenant: TenantContext) -> list[BillingEvent]:
    result = await db_session.execute(
        select(BillingEvent).where(
            BillingEvent.merchant_id == tenant.merchant_id,
            BillingEvent.event_type == "order_cap_exceeded",
        )
    )
    return list(result.scalars().all())


async def _seed_starter_subscription_with_cap(
    db_session: AsyncSession, tenant: TenantContext, *, cap: int
) -> None:
    """Mutates the seeded Starter (monthly) Plan's order_cap for this test
    only -- each test gets a fresh schema (autouse _reset_db fixture), so
    this doesn't leak between tests. Subscription is set to "active" on
    that Starter plan (real tier = starter either way)."""
    plan = await PlanRepository(db_session).get_by_tier_and_interval("starter", "monthly")
    assert plan is not None
    plan.order_cap = cap
    subscription = await SubscriptionRepository(db_session).create(
        tenant, plan_id=plan.plan_id, status="trialing", trial_ends_at=None
    )
    transition_subscription_status(subscription, "active")
    await db_session.commit()


async def _seed_order_this_cycle(
    db_session: AsyncSession, tenant: TenantContext, item, *, payment_method: str
) -> None:
    """Seeds one already-placed order (counted by count_since against
    perform_checkout's *next* call) so a low cap can be reached without
    seeding hundreds of orders."""
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543299")
    payment_status = "cod_pending" if payment_method == "cod" else "paid"
    await OrderRepository(db_session).create(
        tenant,
        customer_id=customer.customer_id,
        order_type="pickup",
        payment_method=payment_method,
        payment_status=payment_status,
        fulfillment_status="new",
        items=[
            OrderItemInput(
                item_id=item.item_id,
                name_snapshot=item.name,
                price_snapshot=item.price,
                quantity=1,
            )
        ],
    )
    await db_session.commit()


async def test_checkout_below_cap_creates_no_billing_event(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    item = await _make_item(db_session, tenant)
    await db_session.commit()
    # Growth trial default cap is 750 -- one order is nowhere near it.

    result = await perform_checkout(
        db_session,
        tenant,
        customer_whatsapp_number="+919876543210",
        items=[CheckoutItem(item_id=item.item_id, quantity=1)],
        payment_method="online",
        customer_display_name="Asha",
    )

    assert result.order is not None
    assert await _billing_events(db_session, tenant) == []


async def test_checkout_no_subscription_row_does_not_crash_and_proceeds_uncapped(
    db_session: AsyncSession,
) -> None:
    """A merchant with no Subscription row at all (shouldn't happen
    post-registration-wiring, but defensively) proceeds uncapped -- fail
    open, not closed, on a missing billing record."""
    tenant = await _make_tenant(db_session)
    item = await _make_item(db_session, tenant)
    await db_session.commit()

    result = await perform_checkout(
        db_session,
        tenant,
        customer_whatsapp_number="+919876543210",
        items=[CheckoutItem(item_id=item.item_id, quantity=1)],
        payment_method="cod",
        customer_display_name="Asha",
    )

    assert result.order is not None
    assert await _billing_events(db_session, tenant) == []


async def test_checkout_online_at_cap_soft_blocks_but_order_still_succeeds(
    db_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(db_session)
    item = await _make_item(db_session, tenant)
    await db_session.commit()
    await _seed_starter_subscription_with_cap(db_session, tenant, cap=1)
    await _seed_order_this_cycle(db_session, tenant, item, payment_method="online")

    result = await perform_checkout(
        db_session,
        tenant,
        customer_whatsapp_number="+919876543210",
        items=[CheckoutItem(item_id=item.item_id, quantity=1)],
        payment_method="online",
        customer_display_name="Asha",
    )

    assert result.order is not None
    assert result.payment_link_url is not None
    events = await _billing_events(db_session, tenant)
    assert len(events) == 1
    assert events[0].provider == "dummy"
    assert '"used": 1' in (events[0].raw_payload or "")
    assert '"cap": 1' in (events[0].raw_payload or "")
    assert '"tier": "starter"' in (events[0].raw_payload or "")


async def test_checkout_cod_at_cap_soft_blocks_but_order_still_succeeds(
    db_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(db_session)
    item = await _make_item(db_session, tenant)
    await db_session.commit()
    await _seed_starter_subscription_with_cap(db_session, tenant, cap=1)
    await _seed_order_this_cycle(db_session, tenant, item, payment_method="cod")

    result = await perform_checkout(
        db_session,
        tenant,
        customer_whatsapp_number="+919876543210",
        items=[CheckoutItem(item_id=item.item_id, quantity=1)],
        payment_method="cod",
        customer_display_name="Asha",
    )

    assert result.order is not None
    events = await _billing_events(db_session, tenant)
    assert len(events) == 1
    assert events[0].event_type == "order_cap_exceeded"


async def test_checkout_first_order_under_cap_creates_no_event(db_session: AsyncSession) -> None:
    """cap=1 with zero prior orders this cycle (used=0) stays under cap --
    only the *next* order (once used already reaches the cap) triggers the
    audit event."""
    tenant = await _make_tenant(db_session)
    item = await _make_item(db_session, tenant)
    await db_session.commit()
    await _seed_starter_subscription_with_cap(db_session, tenant, cap=1)

    result = await perform_checkout(
        db_session,
        tenant,
        customer_whatsapp_number="+919876543210",
        items=[CheckoutItem(item_id=item.item_id, quantity=1)],
        payment_method="cod",
        customer_display_name="Asha",
    )

    assert result.order is not None
    assert await _billing_events(db_session, tenant) == []
