import itertools
import uuid

import pytest

from billing.domain.models import Subscription
from billing.domain.state_machine import (
    SUBSCRIPTION_STATUSES,
    SUBSCRIPTION_TRANSITIONS,
    IllegalTransitionError,
    transition_subscription_status,
)


def _subscription(
    status: str | None = None, past_due_since=None, cancel_at_period_end: bool = False
) -> Subscription:
    return Subscription(
        merchant_id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        status=status,
        past_due_since=past_due_since,
        cancel_at_period_end=cancel_at_period_end,
    )


# --- every legal transition succeeds ----------------------------------------


@pytest.mark.parametrize(("from_status", "to_status"), sorted(SUBSCRIPTION_TRANSITIONS, key=str))
def test_legal_transition_succeeds(from_status: str | None, to_status: str) -> None:
    subscription = _subscription(status=from_status)

    transition_subscription_status(subscription, to_status)

    assert subscription.status == to_status


# --- every illegal (from, to) combination raises ----------------------------

_ALL_FROM_STATES = {None, *SUBSCRIPTION_STATUSES}
_ALL_ILLEGAL_COMBOS = [
    (from_status, to_status)
    for from_status, to_status in itertools.product(_ALL_FROM_STATES, SUBSCRIPTION_STATUSES)
    if (from_status, to_status) not in SUBSCRIPTION_TRANSITIONS
]


@pytest.mark.parametrize(("from_status", "to_status"), sorted(_ALL_ILLEGAL_COMBOS, key=str))
def test_illegal_transition_raises(from_status: str | None, to_status: str) -> None:
    subscription = _subscription(status=from_status)

    with pytest.raises(IllegalTransitionError):
        transition_subscription_status(subscription, to_status)


def test_illegal_transition_does_not_mutate_subscription() -> None:
    subscription = _subscription(status="trialing")

    with pytest.raises(IllegalTransitionError):
        transition_subscription_status(subscription, "canceled")

    assert subscription.status == "trialing"


# --- side effects ------------------------------------------------------------


def test_entering_past_due_sets_past_due_since() -> None:
    subscription = _subscription(status="active")
    assert subscription.past_due_since is None

    transition_subscription_status(subscription, "past_due")

    assert subscription.past_due_since is not None


def test_entering_active_clears_past_due_since_and_cancel_flag() -> None:
    import datetime

    subscription = _subscription(
        status="past_due",
        past_due_since=datetime.datetime.now(datetime.UTC),
        cancel_at_period_end=True,
    )

    transition_subscription_status(subscription, "active")

    assert subscription.past_due_since is None
    assert subscription.cancel_at_period_end is False


def test_entering_canceled_clears_past_due_since() -> None:
    import datetime

    subscription = _subscription(
        status="past_due", past_due_since=datetime.datetime.now(datetime.UTC)
    )

    transition_subscription_status(subscription, "canceled")

    assert subscription.past_due_since is None


def test_entering_expired_clears_past_due_since() -> None:
    # Not reachable via a real past_due_since in practice (expired only
    # comes from trialing), but the side effect is harmless/defensive.
    subscription = _subscription(status="trialing")

    transition_subscription_status(subscription, "expired")

    assert subscription.past_due_since is None


# --- expired/canceled are not fully terminal --------------------------------


def test_expired_can_transition_back_to_active() -> None:
    """A merchant whose trial lapsed can still subscribe later -- expired
    isn't a dead end."""
    subscription = _subscription(status="expired")

    transition_subscription_status(subscription, "active")

    assert subscription.status == "active"


def test_canceled_can_transition_back_to_active() -> None:
    """A merchant who cancelled can re-subscribe later -- canceled isn't a
    dead end either."""
    subscription = _subscription(status="canceled")

    transition_subscription_status(subscription, "active")

    assert subscription.status == "active"


def test_cannot_transition_out_of_active_except_to_past_due_or_canceled() -> None:
    subscription = _subscription(status="active")

    for to_status in SUBSCRIPTION_STATUSES - {"past_due", "canceled"}:
        with pytest.raises(IllegalTransitionError):
            transition_subscription_status(subscription, to_status)
