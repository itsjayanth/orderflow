import datetime

from orders.domain.models import Order

PaymentStatus = str
FulfillmentStatus = str

PAYMENT_STATUSES: frozenset[PaymentStatus] = frozenset(
    {"awaiting_payment", "paid", "payment_failed", "cancelled", "cod_pending", "cod_collected"}
)
FULFILLMENT_STATUSES: frozenset[FulfillmentStatus] = frozenset(
    {"new", "preparing", "ready", "completed", "cancelled"}
)

# ARCHITECTURE.md Section 7a. `None` on the left is the pre-order-creation
# "start" state -- an Order row never exists with payment_status unset, so
# these two rows are really "what payment_status is Order created with."
PAYMENT_TRANSITIONS: frozenset[tuple[PaymentStatus | None, PaymentStatus]] = frozenset(
    {
        (None, "awaiting_payment"),
        ("awaiting_payment", "paid"),
        ("awaiting_payment", "payment_failed"),
        ("payment_failed", "awaiting_payment"),
        ("awaiting_payment", "cancelled"),
        (None, "cod_pending"),
        ("cod_pending", "cod_collected"),
    }
)

# ARCHITECTURE.md Section 7b. `new -> preparing -> ready -> completed`, plus
# `* -> cancelled` from any non-terminal state.
FULFILLMENT_TRANSITIONS: frozenset[tuple[FulfillmentStatus, FulfillmentStatus]] = frozenset(
    {
        ("new", "preparing"),
        ("preparing", "ready"),
        ("ready", "completed"),
        ("new", "cancelled"),
        ("preparing", "cancelled"),
        ("ready", "cancelled"),
    }
)

# payment_status values that gate fulfillment_status into "new" the moment
# they're reached (Section 7b's "Gate" -- the one place the two machines
# interact).
_FULFILLMENT_GATING_PAYMENT_STATUSES = frozenset({"paid", "cod_pending"})


class IllegalTransitionError(Exception):
    def __init__(self, machine: str, from_status: str | None, to_status: str) -> None:
        super().__init__(f"illegal {machine} transition: {from_status!r} -> {to_status!r}")
        self.machine = machine
        self.from_status = from_status
        self.to_status = to_status


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def transition_payment_status(order: Order, to_status: PaymentStatus) -> Order:
    """Validates and applies a payment_status transition per Section 7a,
    including its side effects: paid_at, and the fulfillment_status gate
    (Section 7b) and the cancellation mirror (7a's "terminal, mirrored onto
    fulfillment_status" note)."""
    from_status = order.payment_status
    if (from_status, to_status) not in PAYMENT_TRANSITIONS:
        raise IllegalTransitionError("payment", from_status, to_status)

    order.payment_status = to_status

    if to_status == "paid":
        order.paid_at = _now()

    if to_status in _FULFILLMENT_GATING_PAYMENT_STATUSES and order.fulfillment_status is None:
        order.fulfillment_status = "new"

    if to_status == "cancelled":
        order.fulfillment_status = "cancelled"

    return order


def transition_fulfillment_status(order: Order, to_status: FulfillmentStatus) -> Order:
    """Validates and applies a fulfillment_status transition per Section 7b,
    including its side effects (ready_at/completed_at). Raises if the order
    hasn't been gated into the fulfillment workflow yet (fulfillment_status
    is still None) or if the transition isn't in FULFILLMENT_TRANSITIONS."""
    from_status = order.fulfillment_status
    if from_status is None or (from_status, to_status) not in FULFILLMENT_TRANSITIONS:
        raise IllegalTransitionError("fulfillment", from_status, to_status)

    order.fulfillment_status = to_status

    if to_status == "ready":
        order.ready_at = _now()
    if to_status == "completed":
        order.completed_at = _now()

    return order
