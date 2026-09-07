import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from billing.adapters.repository import PlanRepository, SubscriptionRepository
from identity.adapters.repository import MerchantRepository
from shared.scheduler import sweep_billing_subscriptions
from shared.tenant import TenantContext


async def _make_tenant(db_session: AsyncSession) -> TenantContext:
    merchant = await MerchantRepository(db_session).create(
        business_name="Sweep Billing Business", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    return TenantContext(merchant_id=merchant.merchant_id)


async def test_sweep_expires_lapsed_trials_but_not_active_ones(db_session: AsyncSession) -> None:
    now = datetime.datetime.now(datetime.UTC)
    growth_plan = await PlanRepository(db_session).get_by_tier_and_interval("growth", "monthly")
    assert growth_plan is not None

    lapsed_tenant = await _make_tenant(db_session)
    lapsed = await SubscriptionRepository(db_session).create(
        lapsed_tenant,
        plan_id=growth_plan.plan_id,
        status="trialing",
        trial_ends_at=now - datetime.timedelta(days=1),
    )

    fresh_tenant = await _make_tenant(db_session)
    fresh = await SubscriptionRepository(db_session).create(
        fresh_tenant,
        plan_id=growth_plan.plan_id,
        status="trialing",
        trial_ends_at=now + datetime.timedelta(days=10),
    )
    await db_session.commit()

    await sweep_billing_subscriptions(now)

    await db_session.refresh(lapsed)
    await db_session.refresh(fresh)
    assert lapsed.status == "expired"
    assert fresh.status == "trialing"


async def test_sweep_does_not_re_expire_already_active_subscription(
    db_session: AsyncSession,
) -> None:
    """A subscription whose webhook already fired (status == "active") is
    never touched by the trial sweep, even if trial_ends_at has passed --
    the query itself filters on status == "trialing"."""
    now = datetime.datetime.now(datetime.UTC)
    growth_plan = await PlanRepository(db_session).get_by_tier_and_interval("growth", "monthly")
    assert growth_plan is not None

    tenant = await _make_tenant(db_session)
    subscription_repo = SubscriptionRepository(db_session)
    subscription = await subscription_repo.create(
        tenant,
        plan_id=growth_plan.plan_id,
        status="trialing",
        trial_ends_at=now - datetime.timedelta(days=1),
    )
    from billing.domain.state_machine import transition_subscription_status

    transition_subscription_status(subscription, "active")
    await db_session.commit()

    await sweep_billing_subscriptions(now)

    await db_session.refresh(subscription)
    assert subscription.status == "active"


async def test_sweep_cancels_past_due_subscriptions_exceeding_grace(
    db_session: AsyncSession,
) -> None:
    from shared.config import get_settings

    grace_days = get_settings().billing_past_due_grace_days
    now = datetime.datetime.now(datetime.UTC)
    growth_plan = await PlanRepository(db_session).get_by_tier_and_interval("growth", "monthly")
    assert growth_plan is not None

    lapsed_tenant = await _make_tenant(db_session)
    lapsed = await SubscriptionRepository(db_session).create(
        lapsed_tenant, plan_id=growth_plan.plan_id, status="trialing", trial_ends_at=None
    )
    from billing.domain.state_machine import transition_subscription_status

    transition_subscription_status(lapsed, "active")
    transition_subscription_status(lapsed, "past_due")
    lapsed.past_due_since = now - datetime.timedelta(days=grace_days + 1)

    within_grace_tenant = await _make_tenant(db_session)
    within_grace = await SubscriptionRepository(db_session).create(
        within_grace_tenant, plan_id=growth_plan.plan_id, status="trialing", trial_ends_at=None
    )
    transition_subscription_status(within_grace, "active")
    transition_subscription_status(within_grace, "past_due")
    within_grace.past_due_since = now - datetime.timedelta(days=grace_days - 1)

    await db_session.commit()

    await sweep_billing_subscriptions(now)

    await db_session.refresh(lapsed)
    await db_session.refresh(within_grace)
    assert lapsed.status == "canceled"
    assert within_grace.status == "past_due"


async def test_sweep_advances_over_simulated_time_without_sleeping(
    db_session: AsyncSession,
) -> None:
    """now_utc is injectable -- simulate "10 days later" by calling the
    sweep again with a later now_utc, same convention as
    send_due_appointment_reminders/send_due_campaigns."""
    now = datetime.datetime.now(datetime.UTC)
    growth_plan = await PlanRepository(db_session).get_by_tier_and_interval("growth", "monthly")
    assert growth_plan is not None

    tenant = await _make_tenant(db_session)
    subscription = await SubscriptionRepository(db_session).create(
        tenant,
        plan_id=growth_plan.plan_id,
        status="trialing",
        trial_ends_at=now + datetime.timedelta(days=5),
    )
    await db_session.commit()

    await sweep_billing_subscriptions(now)
    await db_session.refresh(subscription)
    assert subscription.status == "trialing"

    await sweep_billing_subscriptions(now + datetime.timedelta(days=10))
    await db_session.refresh(subscription)
    assert subscription.status == "expired"
