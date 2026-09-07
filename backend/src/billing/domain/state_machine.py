import datetime

from billing.domain.models import Subscription

SubscriptionStatus = str

SUBSCRIPTION_STATUSES: frozenset[SubscriptionStatus] = frozenset(
    {"trialing", "active", "past_due", "canceled", "expired"}
)

# `None` on the left is the pre-creation "start" state, same convention as
# orders/domain/state_machine.py's PAYMENT_TRANSITIONS -- a Subscription
# row never exists with status unset.
#
# `expired -> active` and `canceled -> active` are deliberately legal, not
# terminal dead ends: a merchant whose trial lapsed or who cancelled can
# always come back and subscribe again later (billing/domain/gating.py's
# "never lock out a live restaurant" philosophy extends to "never lock out
# a former customer" too).
SUBSCRIPTION_TRANSITIONS: frozenset[tuple[SubscriptionStatus | None, SubscriptionStatus]] = (
    frozenset(
        {
            (None, "trialing"),
            ("trialing", "active"),  # subscribe / mandate confirmed before trial ends
            ("trialing", "expired"),  # trial sweep, no active subscription yet
            ("active", "past_due"),  # payment.failed / subscription.pending
            ("past_due", "active"),  # recovered charge
            ("past_due", "canceled"),  # grace period exceeded, or provider halted retries
            ("active", "canceled"),  # user-initiated, effective at period end
            ("expired", "active"),  # subscribes after trial lapse
            ("canceled", "active"),  # re-subscribes later
        }
    )
)


class IllegalTransitionError(Exception):
    def __init__(
        self, machine: str, from_status: str | None, to_status: str
    ) -> None:
        super().__init__(f"illegal {machine} transition: {from_status!r} -> {to_status!r}")
        self.machine = machine
        self.from_status = from_status
        self.to_status = to_status


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def transition_subscription_status(
    subscription: Subscription, to_status: SubscriptionStatus
) -> Subscription:
    """Validates and applies a Subscription.status transition per
    SUBSCRIPTION_TRANSITIONS, including side effects. Checks before
    mutating -- an illegal call leaves the entity completely untouched,
    same convention as orders/domain/state_machine.py's transition
    functions."""
    from_status = subscription.status
    if (from_status, to_status) not in SUBSCRIPTION_TRANSITIONS:
        raise IllegalTransitionError("subscription", from_status, to_status)

    subscription.status = to_status

    if to_status == "past_due":
        subscription.past_due_since = _now()

    if to_status == "active":
        # Entering (or re-entering) active means whatever put the
        # subscription in trouble before is resolved -- clear the grace-
        # period clock and any pending cancel-at-period-end flag from a
        # prior cycle.
        subscription.past_due_since = None
        subscription.cancel_at_period_end = False

    if to_status in ("canceled", "expired"):
        subscription.past_due_since = None

    return subscription
