import datetime

from appointments.domain.models import Appointment

AppointmentStatus = str

STATUSES: frozenset[AppointmentStatus] = frozenset(
    {"requested", "confirmed", "completed", "cancelled"}
)

# `None` on the left is the pre-appointment-creation "start" state -- an
# Appointment row never exists with status unset, so that row is really
# "what status Appointment is created with" (see
# appointments/adapters/repository.py's `create`, which constructs the row
# directly with status="requested" rather than routing the initial write
# through transition_status -- same convention orders/adapters/repository.py's
# `create` uses for payment_status).
TRANSITIONS: frozenset[tuple[AppointmentStatus | None, AppointmentStatus]] = frozenset(
    {
        (None, "requested"),
        ("requested", "confirmed"),
        ("requested", "cancelled"),
        ("confirmed", "completed"),
        ("confirmed", "cancelled"),
    }
)


class IllegalTransitionError(Exception):
    def __init__(self, from_status: str | None, to_status: str) -> None:
        super().__init__(f"illegal appointment transition: {from_status!r} -> {to_status!r}")
        self.from_status = from_status
        self.to_status = to_status


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def transition_status(appointment: Appointment, to_status: AppointmentStatus) -> Appointment:
    """Validates and applies a status transition, including its side
    effects: confirmed_at/completed_at/cancelled_at. Staff-driven only --
    no fully-automated path ever calls this (see product spec: appointment
    status changes always come from the dashboard)."""
    from_status = appointment.status
    if (from_status, to_status) not in TRANSITIONS:
        raise IllegalTransitionError(from_status, to_status)

    appointment.status = to_status

    if to_status == "confirmed":
        appointment.confirmed_at = _now()
    if to_status == "completed":
        appointment.completed_at = _now()
    if to_status == "cancelled":
        appointment.cancelled_at = _now()

    return appointment
