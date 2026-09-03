import datetime
import uuid
import zoneinfo
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from appointment_flow.domain.availability import is_slot_elapsed
from appointments.adapters.repository import AppointmentRepository, SlotConflictError
from appointments.adapters.scheduling_repository import (
    AppointmentServiceRepository,
    MerchantAvailabilityRepository,
)
from appointments.domain.events import AppointmentRequested, publish
from appointments.domain.models import Appointment
from customers.adapters.repository import CustomerRepository
from identity.domain.models import Merchant
from shared.tenant import TenantContext

_DEFAULT_DURATION_MINUTES = 30


class PastDateError(Exception):
    """Raised for a date that's already gone, or -- same underlying "this
    can't be booked, it's already in the past" case -- a same-day
    start_time that's already elapsed (Task 1's is_slot_elapsed). Kept as
    one exception type rather than two: every caller (the browser
    booking webview, the WhatsApp Flow completion handler) already treats
    this as a single "pick a different time" outcome, so splitting it
    would only add call sites to keep in sync for no behavioral gain."""


@dataclass(frozen=True, slots=True)
class BookingResult:
    appointment: Appointment


def _merchant_today(merchant: Merchant) -> datetime.date:
    """ "Today" in the merchant's own local time, not UTC -- a merchant near
    UTC midnight would otherwise have a valid same-day slot wrongly
    rejected (or a genuinely past slot wrongly accepted), which is exactly
    the timezone bug this replaces (the old check compared against
    datetime.now(UTC).date() unconditionally)."""
    tz = zoneinfo.ZoneInfo(merchant.timezone)
    return datetime.datetime.now(tz).date()


async def resolve_duration_minutes(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    service_id: uuid.UUID | None,
    appointment_date: datetime.date,
) -> int:
    """service_id given -> that service's own duration. Otherwise, the
    day's configured slot_duration_minutes (so a booking's length matches
    whatever granularity the merchant set their calendar to). Falls back to
    a flat 30 minutes only when neither is configured -- a merchant with no
    services and no availability rows set up yet still gets a bookable
    appointment rather than a hard failure."""
    if service_id is not None:
        service = await AppointmentServiceRepository(session).get(tenant, service_id)
        if service is not None:
            return service.duration_minutes

    availability = await MerchantAvailabilityRepository(session).get_for_day(
        tenant, day_of_week=appointment_date.weekday()
    )
    if availability is not None:
        return availability.slot_duration_minutes

    return _DEFAULT_DURATION_MINUTES


async def perform_booking(
    session: AsyncSession,
    tenant: TenantContext,
    merchant: Merchant,
    *,
    customer_whatsapp_number: str,
    customer_display_name: str | None,
    name: str,
    email: str,
    appointment_date: datetime.date,
    start_time: datetime.time,
    service_id: uuid.UUID | None = None,
    staff_id: uuid.UUID | None = None,
    created_via: str = "browser",
    notes: str | None = None,
    whatsapp_conversation_ref: str | None = None,
) -> BookingResult:
    """The one place booking-form -> Appointment happens -- called by the
    public appointment-flow webview (appointment_flow/api/router.py) and
    the WhatsApp Flow completion handler
    (conversation/domain/handler.py's _handle_appointment_flow_completion),
    mirroring ordering_flow.domain.checkout.perform_checkout's role for
    product orders. Publishes AppointmentRequested on success --
    notifications/wiring.py turns that into the merchant's own configured
    "appointment_requested" template (or the built-in default) over the
    same channel every other lifecycle notification uses, matching how
    perform_checkout already does this for OrderConfirmedCOD/OrderPaid.
    Being the single creation path for both the browser flow and the
    native WhatsApp Flow means this is the only place that needs to fire
    it -- the Flow-completion handler used to also hand-roll its own
    "requested" text send, which would now double-send, so it no longer
    does (see handler.py).

    Takes `merchant` (not just `tenant`) because the past-date check needs
    Merchant.timezone -- the caller already has the row loaded (both call
    sites fetch it for other reasons first), so this doesn't add an extra
    query.

    Raises SlotConflictError (propagated, not caught here) if the resolved
    [start_time, end_time) range is no longer free, OR (Task 3) no longer
    fits inside the merchant's *current* working-hours window for that
    weekday -- re-checked live against MerchantAvailability here rather
    than trusted from whatever slot list the caller (browser page or
    WhatsApp Flow) had on screen, so a merchant shortening their hours
    mid-session can never be bypassed by a stale slot pick. The API layer
    turns either case into the same 409."""
    if appointment_date < _merchant_today(merchant):
        raise PastDateError(appointment_date)
    if appointment_date == _merchant_today(merchant) and is_slot_elapsed(
        appointment_date=appointment_date, start_time=start_time, timezone=merchant.timezone
    ):
        raise PastDateError(appointment_date)

    duration_minutes = await resolve_duration_minutes(
        session, tenant, service_id=service_id, appointment_date=appointment_date
    )
    end_time = (
        datetime.datetime.combine(appointment_date, start_time)
        + datetime.timedelta(minutes=duration_minutes)
    ).time()

    # Only enforced when the merchant has actually configured hours for
    # this weekday -- a merchant with no MerchantAvailability rows at all
    # stays fully permissive here, matching resolve_duration_minutes's own
    # "unconfigured = still bookable" fallback just above, rather than
    # this becoming the first booking-time check to demand availability
    # rows exist. Once hours ARE configured, re-check live rather than
    # trust the caller's slot pick (Task 3) -- catches exactly the "hours
    # just got shortened out from under a stale slot list" case.
    availability = await MerchantAvailabilityRepository(session).get_for_day(
        tenant, day_of_week=appointment_date.weekday(), staff_id=staff_id
    )
    if availability is not None and not (
        availability.start_time <= start_time and end_time <= availability.end_time
    ):
        raise SlotConflictError(
            f"{start_time}-{end_time} on {appointment_date} is outside current working hours"
        )

    customer_repo = CustomerRepository(session)
    customer = await customer_repo.find_or_create(
        tenant, customer_whatsapp_number, display_name=customer_display_name
    )
    # find_or_create only sets name on first creation -- persist a
    # returning customer's corrected name/email as their new defaults too,
    # mirroring perform_checkout's own update_contact_details call for the
    # order flow. Deliberately after find_or_create (a brand-new customer
    # already got `name` as display_name there) but before the write below
    # -- if AppointmentRepository.create raises SlotConflictError, this
    # profile update is rolled back right alongside it.
    await customer_repo.update_profile_from_appointment(customer, display_name=name, email=email)

    try:
        appointment = await AppointmentRepository(session).create(
            tenant,
            customer_id=customer.customer_id,
            name=name,
            email=email,
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            service_id=service_id,
            staff_id=staff_id,
            created_via=created_via,
            notes=notes,
            whatsapp_conversation_ref=whatsapp_conversation_ref,
        )
    except SlotConflictError:
        await session.rollback()
        raise

    await session.commit()
    await publish(
        AppointmentRequested(
            appointment_id=appointment.appointment_id, merchant_id=tenant.merchant_id
        )
    )
    return BookingResult(appointment=appointment)
