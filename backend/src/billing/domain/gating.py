import calendar
import datetime

from billing.domain.models import Plan, Subscription
from shared.config import get_settings


def effective_tier(subscription: Subscription, plan: Plan, now: datetime.datetime) -> str:
    """The tier to use for feature-gating purposes right now -- NOT the same as
    subscription.plan.tier, which is the merchant's *actual/intended* plan.
    A merchant whose trial or paid subscription has lapsed keeps using the
    product at Starter limits rather than being cut off entirely (never lock
    out a live restaurant) -- so gating always falls back to "starter",
    never to "no access". Only `trialing` and `active` (and, deliberately,
    `past_due` within its grace window -- see shared/config.py's
    billing_past_due_grace_days -- since Razorpay's own retry cadence hasn't
    been exhausted yet) get the merchant's real plan tier.
    """
    if subscription.status in ("trialing", "active"):
        return plan.tier

    if subscription.status == "past_due" and subscription.past_due_since is not None:
        grace = datetime.timedelta(days=get_settings().billing_past_due_grace_days)
        if now - subscription.past_due_since <= grace:
            return plan.tier

    # past_due past grace, expired, canceled -- or a past_due row with no
    # past_due_since somehow set (shouldn't happen, but fail toward
    # Starter, never toward the merchant's real -- possibly paid-tier --
    # limits).
    return "starter"


def effective_order_cap(tier: str, plans_by_tier: dict[str, Plan]) -> int | None:
    """None = unlimited. Looks up the given tier's own order_cap among the
    (monthly or annual, doesn't matter -- the cap is per-tier, not
    per-interval) Plan rows the caller has indexed by tier."""
    plan = plans_by_tier.get(tier)
    return plan.order_cap if plan is not None else None


def _calendar_month_window(now: datetime.datetime) -> tuple[datetime.datetime, datetime.datetime]:
    start = now.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=datetime.UTC
    )
    days_in_month = calendar.monthrange(start.year, start.month)[1]
    end = start + datetime.timedelta(days=days_in_month)
    return start, end


def billing_cycle_window(
    subscription: Subscription, now: datetime.datetime
) -> tuple[datetime.datetime, datetime.datetime]:
    """Returns (current_period_start, current_period_end). Uses the real
    Razorpay-provided billing period when both are set on the
    Subscription (populated from the subscription.charged webhook
    payload); otherwise falls back to a calendar-month window
    [first of current month, first of next month) -- the state a
    trialing or lapsed-to-Starter subscription is always in, since there's
    no real billing period to anchor to yet."""
    if (
        subscription.current_period_start is not None
        and subscription.current_period_end is not None
    ):
        return subscription.current_period_start, subscription.current_period_end
    return _calendar_month_window(now)
