import datetime
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from appointments.adapters.repository import AppointmentRepository
from appointments.domain.models import Appointment
from customers.adapters.repository import CustomerRepository
from shared.tenant import TenantContext


class PastDateError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class BookingResult:
    appointment: Appointment


async def perform_booking(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    customer_whatsapp_number: str,
    customer_display_name: str | None,
    name: str,
    email: str,
    appointment_date: datetime.date,
    appointment_time: datetime.time,
    notes: str | None = None,
    whatsapp_conversation_ref: str | None = None,
) -> BookingResult:
    """The one place booking-form -> Appointment happens -- called by the
    public appointment-flow webview (appointment_flow/api/router.py),
    mirroring ordering_flow.domain.checkout.perform_checkout's role for
    product orders. Deliberately does not publish any event: only the
    `confirmed`/`cancelled` transitions (set later from the dashboard)
    trigger a WhatsApp notification per the product spec -- a fresh
    "requested" booking is silent on WhatsApp by design (the booking page
    itself shows the on-screen confirmation)."""
    if appointment_date < datetime.datetime.now(datetime.UTC).date():
        raise PastDateError(appointment_date)

    customer = await CustomerRepository(session).find_or_create(
        tenant, customer_whatsapp_number, display_name=customer_display_name
    )

    appointment = await AppointmentRepository(session).create(
        tenant,
        customer_id=customer.customer_id,
        name=name,
        email=email,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        notes=notes,
        whatsapp_conversation_ref=whatsapp_conversation_ref,
    )
    await session.commit()
    return BookingResult(appointment=appointment)
