import datetime
import uuid
import zoneinfo
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


def is_slot_elapsed(
    *,
    appointment_date: datetime.date,
    start_time: datetime.time,
    timezone: str,
    now_utc: datetime.datetime | None = None,
) -> bool:
    """True once `start_time` on `appointment_date` (interpreted in the
    merchant's own local `timezone`) is at or before "now". Evaluated at
    request time only, same as every other read in this app (no
    server-side push) -- see appointment_flow/domain/booking.py's
    _merchant_today for why local time, not naive UTC, is what the
    comparison must use: a merchant near UTC midnight would otherwise have
    a valid slot wrongly hidden (or an already-passed one wrongly shown).
    Shared by get_available_slots (Task 1: hide elapsed slots from the
    list) and perform_booking (defense in depth: reject a submission for
    an elapsed slot even if the caller's own slot list was stale -- same
    "backend re-validates, never trusts a cached frontend list" principle
    Task 3 applies to availability-window changes)."""
    tz = zoneinfo.ZoneInfo(timezone)
    now = now_utc if now_utc is not None else datetime.datetime.now(datetime.UTC)
    slot_start_utc = datetime.datetime.combine(appointment_date, start_time, tzinfo=tz).astimezone(
        datetime.UTC
    )
    return slot_start_utc <= now


async def get_available_slots(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    appointment_date: datetime.date,
    service_duration_minutes: int,
    timezone: str,
    staff_id: uuid.UUID | None = None,
    now_utc: datetime.datetime | None = None,
) -> list[Slot]:
    """Candidate slots at the day's configured slot_duration_minutes
    cadence, across the merchant's working-hours window for that weekday,
    minus already-booked ranges (padded by buffer_minutes on each side)
    and minus any slot that's already elapsed (Task 1) -- evaluated fresh
    against "now" on every call, so a slot disappears from the list the
    moment its start_time passes without needing any client-side timer;
    the frontend's own short refetchInterval on this query is what makes
    that show up on screen for a page left open (see
    frontend/src/features/booking/useAvailableSlots.ts).

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

    # Injectable for tests (mirrors appointment_flow.domain.reminders.
    # is_reminder_due's own now_utc param) -- defaults to the real clock in
    # every production call site.
    now_utc = now_utc if now_utc is not None else datetime.datetime.now(datetime.UTC)
    slots: list[Slot] = []
    candidate_start = window_start
    while candidate_start + service_duration_minutes <= window_end:
        candidate_end = candidate_start + service_duration_minutes
        candidate_start_time = _time_from_minutes(candidate_start)
        if not any(
            _overlaps(candidate_start, candidate_end, busy_start, busy_end)
            for busy_start, busy_end in padded_ranges
        ) and not is_slot_elapsed(
            appointment_date=appointment_date,
            start_time=candidate_start_time,
            timezone=timezone,
            now_utc=now_utc,
        ):
            slots.append(
                Slot(
                    start_time=candidate_start_time,
                    end_time=_time_from_minutes(candidate_end),
                )
            )
        candidate_start += cadence

    return slots
