import datetime
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from appointments.adapters.repository import AppointmentRepository
from appointments.adapters.scheduling_repository import MerchantAvailabilityRepository
from shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class Slot:
    start_time: datetime.time
    end_time: datetime.time


def _minutes(value: datetime.time) -> int:
    return value.hour * 60 + value.minute


def _time_from_minutes(value: int) -> datetime.time:
    return datetime.time(hour=value // 60, minute=value % 60)


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and a_end > b_start


async def get_available_slots(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    appointment_date: datetime.date,
    service_duration_minutes: int,
    staff_id: uuid.UUID | None = None,
) -> list[Slot]:
    """Candidate slots at the day's configured slot_duration_minutes
    cadence, across the merchant's working-hours window for that weekday,
    minus already-booked ranges (padded by buffer_minutes on each side).

    No MerchantAvailability row for this weekday => the merchant hasn't
    configured hours for that day => empty list, not "assume always open".
    This deliberately doesn't consult AppointmentService.duration_minutes
    itself -- the caller resolves the effective duration (service-specific
    or the day's own slot_duration_minutes default) and passes it in, so
    this function has one job: turn a duration + working hours + existing
    bookings into a slot list."""
    availability = await MerchantAvailabilityRepository(session).get_for_day(
        tenant, day_of_week=appointment_date.weekday(), staff_id=staff_id
    )
    if availability is None:
        return []

    window_start = _minutes(availability.start_time)
    window_end = _minutes(availability.end_time)
    cadence = availability.slot_duration_minutes
    buffer_minutes = availability.buffer_minutes

    booked_ranges = await AppointmentRepository(session).list_booked_ranges(
        tenant, appointment_date=appointment_date, staff_id=staff_id
    )
    # Pad every booked range by the buffer on both sides so a slot can't be
    # offered right up against an existing appointment with no breathing
    # room between them.
    padded_ranges = [
        (_minutes(start) - buffer_minutes, _minutes(end) + buffer_minutes)
        for start, end in booked_ranges
    ]

    slots: list[Slot] = []
    candidate_start = window_start
    while candidate_start + service_duration_minutes <= window_end:
        candidate_end = candidate_start + service_duration_minutes
        if not any(
            _overlaps(candidate_start, candidate_end, busy_start, busy_end)
            for busy_start, busy_end in padded_ranges
        ):
            slots.append(
                Slot(
                    start_time=_time_from_minutes(candidate_start),
                    end_time=_time_from_minutes(candidate_end),
                )
            )
        candidate_start += cadence

    return slots
