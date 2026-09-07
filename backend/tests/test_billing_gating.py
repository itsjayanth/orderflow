import datetime
import uuid
from decimal import Decimal

from billing.domain.gating import billing_cycle_window, effective_order_cap, effective_tier
from billing.domain.models import Plan, Subscription
from shared.config import get_settings

NOW = datetime.datetime(2026, 9, 15, 12, 0, 0, tzinfo=datetime.UTC)


def _plan(tier: str = "growth", order_cap: int | None = 750) -> Plan:
    return Plan(
        plan_id=uuid.uuid4(),
        tier=tier,
        billing_interval="monthly",
        display_name=tier.title(),
        price_inr=Decimal("2499.00"),
        order_cap=order_cap,
        whatsapp_flow_enabled=True,
        branding_required=False,
    )


def _subscription(status: str, past_due_since: datetime.datetime | None = None) -> Subscription:
    return Subscription(
        merchant_id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        status=status,
        past_due_since=past_due_since,
    )


# --- effective_tier ----------------------------------------------------------


def test_effective_tier_trialing_gets_real_plan_tier() -> None:
    plan = _plan(tier="growth")
    subscription = _subscription("trialing")

    assert effective_tier(subscription, plan, NOW) == "growth"


def test_effective_tier_active_gets_real_plan_tier() -> None:
    plan = _plan(tier="pro")
    subscription = _subscription("active")

    assert effective_tier(subscription, plan, NOW) == "pro"


def test_effective_tier_past_due_within_grace_gets_real_plan_tier() -> None:
    grace_days = get_settings().billing_past_due_grace_days
    plan = _plan(tier="growth")
    subscription = _subscription(
        "past_due", past_due_since=NOW - datetime.timedelta(days=grace_days - 1)
    )

    assert effective_tier(subscription, plan, NOW) == "growth"


def test_effective_tier_past_due_past_grace_falls_back_to_starter() -> None:
    grace_days = get_settings().billing_past_due_grace_days
    plan = _plan(tier="growth")
    subscription = _subscription(
        "past_due", past_due_since=NOW - datetime.timedelta(days=grace_days + 1)
    )

    assert effective_tier(subscription, plan, NOW) == "starter"


def test_effective_tier_past_due_exactly_at_grace_boundary_still_real_tier() -> None:
    grace_days = get_settings().billing_past_due_grace_days
    plan = _plan(tier="growth")
    subscription = _subscription(
        "past_due", past_due_since=NOW - datetime.timedelta(days=grace_days)
    )

    assert effective_tier(subscription, plan, NOW) == "growth"


def test_effective_tier_expired_falls_back_to_starter() -> None:
    plan = _plan(tier="pro")
    subscription = _subscription("expired")

    assert effective_tier(subscription, plan, NOW) == "starter"


def test_effective_tier_canceled_falls_back_to_starter() -> None:
    plan = _plan(tier="growth")
    subscription = _subscription("canceled")

    assert effective_tier(subscription, plan, NOW) == "starter"


# --- effective_order_cap ------------------------------------------------------


def test_effective_order_cap_looks_up_by_tier() -> None:
    plans_by_tier = {"starter": _plan("starter", 150), "growth": _plan("growth", 750)}

    assert effective_order_cap("starter", plans_by_tier) == 150
    assert effective_order_cap("growth", plans_by_tier) == 750


def test_effective_order_cap_unlimited_is_none() -> None:
    plans_by_tier = {"pro": _plan("pro", None)}

    assert effective_order_cap("pro", plans_by_tier) is None


def test_effective_order_cap_unknown_tier_is_none() -> None:
    assert effective_order_cap("nonexistent", {}) is None


# --- billing_cycle_window ------------------------------------------------------


def test_billing_cycle_window_uses_real_period_when_set() -> None:
    start = datetime.datetime(2026, 9, 1, tzinfo=datetime.UTC)
    end = datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC)
    subscription = _subscription("active")
    subscription.current_period_start = start
    subscription.current_period_end = end

    assert billing_cycle_window(subscription, NOW) == (start, end)


def test_billing_cycle_window_falls_back_to_calendar_month() -> None:
    subscription = _subscription("trialing")

    start, end = billing_cycle_window(subscription, NOW)

    assert start == datetime.datetime(2026, 9, 1, tzinfo=datetime.UTC)
    assert end == datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC)


def test_billing_cycle_window_calendar_month_handles_december() -> None:
    subscription = _subscription("expired")
    december_now = datetime.datetime(2026, 12, 20, tzinfo=datetime.UTC)

    start, end = billing_cycle_window(subscription, december_now)

    assert start == datetime.datetime(2026, 12, 1, tzinfo=datetime.UTC)
    assert end == datetime.datetime(2027, 1, 1, tzinfo=datetime.UTC)
