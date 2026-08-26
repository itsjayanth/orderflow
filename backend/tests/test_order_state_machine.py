import itertools
import uuid

import pytest

from orders.domain.models import Order
from orders.domain.state_machine import (
    FULFILLMENT_STATUSES,
    FULFILLMENT_TRANSITIONS,
    PAYMENT_STATUSES,
    PAYMENT_TRANSITIONS,
    IllegalTransitionError,
    transition_fulfillment_status,
    transition_payment_status,
)


def _order(payment_status: str | None = None, fulfillment_status: str | None = None) -> Order:
    return Order(
        order_id=uuid.uuid4(),
        merchant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        order_type="pickup",
        payment_method="online",
        payment_status=payment_status,
        fulfillment_status=fulfillment_status,
        subtotal=0,
        total=0,
    )


# --- payment_status: every legal transition succeeds ------------------------


@pytest.mark.parametrize(("from_status", "to_status"), sorted(PAYMENT_TRANSITIONS, key=str))
def test_legal_payment_transition_succeeds(from_status: str | None, to_status: str) -> None:
    order = _order(payment_status=from_status)

    transition_payment_status(order, to_status)

    assert order.payment_status == to_status


# --- payment_status: every illegal (from, to) combination raises ------------

_ALL_PAYMENT_FROM_STATES = {None, *PAYMENT_STATUSES}
_ALL_ILLEGAL_PAYMENT_COMBOS = [
    (from_status, to_status)
    for from_status, to_status in itertools.product(_ALL_PAYMENT_FROM_STATES, PAYMENT_STATUSES)
    if (from_status, to_status) not in PAYMENT_TRANSITIONS
]


@pytest.mark.parametrize(("from_status", "to_status"), sorted(_ALL_ILLEGAL_PAYMENT_COMBOS, key=str))
def test_illegal_payment_transition_raises(from_status: str | None, to_status: str) -> None:
    order = _order(payment_status=from_status)

    with pytest.raises(IllegalTransitionError):
        transition_payment_status(order, to_status)


def test_illegal_payment_transition_does_not_mutate_order() -> None:
    order = _order(payment_status="paid")

    with pytest.raises(IllegalTransitionError):
        transition_payment_status(order, "cod_pending")

    assert order.payment_status == "paid"


# --- payment_status side effects --------------------------------------------


def test_paid_sets_paid_at() -> None:
    order = _order(payment_status="awaiting_payment")
    assert order.paid_at is None

    transition_payment_status(order, "paid")

    assert order.paid_at is not None


def test_paid_gates_fulfillment_status_to_new() -> None:
    order = _order(payment_status="awaiting_payment")
    assert order.fulfillment_status is None

    transition_payment_status(order, "paid")

    assert order.fulfillment_status == "new"


def test_cod_pending_gates_fulfillment_status_to_new() -> None:
    order = _order(payment_status=None)

    transition_payment_status(order, "cod_pending")

    assert order.fulfillment_status == "new"


def test_payment_cancelled_mirrors_onto_fulfillment_status() -> None:
    order = _order(payment_status="awaiting_payment")

    transition_payment_status(order, "cancelled")

    assert order.fulfillment_status == "cancelled"


def test_cod_collected_does_not_reset_fulfillment_status() -> None:
    order = _order(payment_status="cod_pending", fulfillment_status="processing")

    transition_payment_status(order, "cod_collected")

    assert order.fulfillment_status == "processing"


# --- fulfillment_status: every legal transition succeeds --------------------


@pytest.mark.parametrize(("from_status", "to_status"), sorted(FULFILLMENT_TRANSITIONS, key=str))
def test_legal_fulfillment_transition_succeeds(from_status: str, to_status: str) -> None:
    order = _order(payment_status="paid", fulfillment_status=from_status)

    transition_fulfillment_status(order, to_status)

    assert order.fulfillment_status == to_status


# --- fulfillment_status: every illegal (from, to) combination raises --------

_ALL_FULFILLMENT_FROM_STATES = {None, *FULFILLMENT_STATUSES}
_ALL_ILLEGAL_FULFILLMENT_COMBOS = [
    (from_status, to_status)
    for from_status, to_status in itertools.product(
        _ALL_FULFILLMENT_FROM_STATES, FULFILLMENT_STATUSES
    )
    if from_status is None or (from_status, to_status) not in FULFILLMENT_TRANSITIONS
]


@pytest.mark.parametrize(
    ("from_status", "to_status"), sorted(_ALL_ILLEGAL_FULFILLMENT_COMBOS, key=str)
)
def test_illegal_fulfillment_transition_raises(from_status: str | None, to_status: str) -> None:
    order = _order(payment_status="paid", fulfillment_status=from_status)

    with pytest.raises(IllegalTransitionError):
        transition_fulfillment_status(order, to_status)


def test_fulfillment_transition_before_gate_raises() -> None:
    """An order whose payment hasn't reached paid/cod_pending yet has no
    fulfillment_status -- staff can't advance kitchen state on an order
    that isn't paid for or committed to COD."""
    order = _order(payment_status="awaiting_payment", fulfillment_status=None)

    with pytest.raises(IllegalTransitionError):
        transition_fulfillment_status(order, "processing")


def test_illegal_fulfillment_transition_does_not_mutate_order() -> None:
    order = _order(payment_status="paid", fulfillment_status="new")

    with pytest.raises(IllegalTransitionError):
        transition_fulfillment_status(order, "completed")

    assert order.fulfillment_status == "new"


# --- fulfillment_status side effects ----------------------------------------


def test_ready_sets_ready_at() -> None:
    order = _order(payment_status="paid", fulfillment_status="processing")
    assert order.ready_at is None

    transition_fulfillment_status(order, "ready")

    assert order.ready_at is not None


def test_completed_sets_completed_at() -> None:
    order = _order(payment_status="paid", fulfillment_status="ready")
    assert order.completed_at is None

    transition_fulfillment_status(order, "completed")

    assert order.completed_at is not None


def test_cancelled_from_any_non_terminal_state() -> None:
    for from_status in ("new", "processing", "ready"):
        order = _order(payment_status="paid", fulfillment_status=from_status)
        transition_fulfillment_status(order, "cancelled")
        assert order.fulfillment_status == "cancelled"


def test_cannot_cancel_a_completed_order() -> None:
    order = _order(payment_status="paid", fulfillment_status="completed")

    with pytest.raises(IllegalTransitionError):
        transition_fulfillment_status(order, "cancelled")


def test_cannot_transition_out_of_cancelled() -> None:
    order = _order(payment_status="paid", fulfillment_status="cancelled")

    for to_status in FULFILLMENT_STATUSES - {"cancelled"}:
        with pytest.raises(IllegalTransitionError):
            transition_fulfillment_status(order, to_status)
