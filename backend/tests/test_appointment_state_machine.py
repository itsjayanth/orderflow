import datetime
import itertools
import uuid

import pytest

from appointments.domain.models import Appointment
from appointments.domain.state_machine import (
    STATUSES,
    TRANSITIONS,
    IllegalTransitionError,
    transition_status,
)


def _appointment(status: str | None = None) -> Appointment:
    return Appointment(
        appointment_id=uuid.uuid4(),
        merchant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        appointment_number=1,
        appointment_date=datetime.date(2026, 9, 1),
        start_time=datetime.time(18, 0),
        end_time=datetime.time(18, 30),
        name="Asha",
        email="asha@example.com",
        status=status,
    )


# --- every legal transition succeeds -----------------------------------

_LEGAL_FROM_NON_NONE = [(f, t) for f, t in TRANSITIONS if f is not None]


@pytest.mark.parametrize(("from_status", "to_status"), sorted(_LEGAL_FROM_NON_NONE, key=str))
def test_legal_transition_succeeds(from_status: str, to_status: str) -> None:
    appointment = _appointment(status=from_status)

    transition_status(appointment, to_status)

    assert appointment.status == to_status


# --- every illegal (from, to) combination raises -------------------------

_ALL_FROM_STATES = {None, *STATUSES}
_ALL_ILLEGAL_COMBOS = [
    (from_status, to_status)
    for from_status, to_status in itertools.product(_ALL_FROM_STATES, STATUSES)
    if (from_status, to_status) not in TRANSITIONS
]


@pytest.mark.parametrize(("from_status", "to_status"), sorted(_ALL_ILLEGAL_COMBOS, key=str))
def test_illegal_transition_raises(from_status: str | None, to_status: str) -> None:
    appointment = _appointment(status=from_status)

    with pytest.raises(IllegalTransitionError):
        transition_status(appointment, to_status)


def test_illegal_transition_does_not_mutate_appointment() -> None:
    appointment = _appointment(status="completed")

    with pytest.raises(IllegalTransitionError):
        transition_status(appointment, "confirmed")

    assert appointment.status == "completed"


# --- side effects ----------------------------------------------------------


def test_confirmed_sets_confirmed_at() -> None:
    appointment = _appointment(status="requested")
    assert appointment.confirmed_at is None

    transition_status(appointment, "confirmed")

    assert appointment.confirmed_at is not None


def test_completed_sets_completed_at() -> None:
    appointment = _appointment(status="confirmed")
    assert appointment.completed_at is None

    transition_status(appointment, "completed")

    assert appointment.completed_at is not None


def test_cancelled_from_requested_sets_cancelled_at() -> None:
    appointment = _appointment(status="requested")

    transition_status(appointment, "cancelled")

    assert appointment.status == "cancelled"
    assert appointment.cancelled_at is not None


def test_cancelled_from_confirmed_sets_cancelled_at() -> None:
    appointment = _appointment(status="confirmed")

    transition_status(appointment, "cancelled")

    assert appointment.status == "cancelled"
    assert appointment.cancelled_at is not None


def test_cannot_cancel_a_completed_appointment() -> None:
    appointment = _appointment(status="completed")

    with pytest.raises(IllegalTransitionError):
        transition_status(appointment, "cancelled")


def test_cannot_transition_out_of_cancelled() -> None:
    appointment = _appointment(status="cancelled")

    for to_status in STATUSES - {"cancelled"}:
        with pytest.raises(IllegalTransitionError):
            transition_status(appointment, to_status)
