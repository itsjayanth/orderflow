import datetime
import uuid

from fastapi import APIRouter, HTTPException, status

from appointment_flow.api.schemas import (
    AppointmentFlowBookingRequest,
    AppointmentFlowBookingResponse,
    AppointmentFlowCustomerLookupOut,
    AppointmentFlowInfoOut,
    AppointmentFlowServiceOut,
    AppointmentFlowSlotOut,
)
from appointment_flow.domain.availability import get_available_slots
from appointment_flow.domain.booking import PastDateError, perform_booking, resolve_duration_minutes
from appointments.adapters.repository import SlotConflictError
from appointments.adapters.scheduling_repository import AppointmentServiceRepository
from customers.domain.identity_resolution import resolve_customer_by_whatsapp_id
from identity.adapters.repository import MerchantRepository
from identity.domain.models import Merchant
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from shared.deps import DbSession
from shared.tenant import TenantContext

router = APIRouter(prefix="/api/v1/appointment-flow", tags=["appointment_flow"])


async def _get_bookable_merchant_or_404(session: DbSession, merchant_id: uuid.UUID) -> Merchant:
    merchant = await MerchantRepository(session).get(merchant_id)
    if merchant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant not found")
    if not merchant.appointment_enabled:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Appointment booking is not available for this business"
        )
    return merchant


@router.get("/{merchant_id}/info", response_model=AppointmentFlowInfoOut)
async def get_appointment_flow_info(
    merchant_id: uuid.UUID, session: DbSession
) -> AppointmentFlowInfoOut:
    """Public and unauthenticated -- this is what the customer-facing
    booking webview loads before showing its date/time/details form."""
    merchant = await _get_bookable_merchant_or_404(session, merchant_id)
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
    return AppointmentFlowInfoOut(
        business_name=merchant.business_name,
        merchant_whatsapp_number=waba.display_phone_number if waba else None,
    )


@router.get("/{merchant_id}/services", response_model=list[AppointmentFlowServiceOut])
async def list_appointment_flow_services(
    merchant_id: uuid.UUID, session: DbSession
) -> list[AppointmentFlowServiceOut]:
    """Public and unauthenticated, same security model as get_public_catalog
    (ordering_flow/api/router.py). An empty list is the normal case for a
    merchant who hasn't defined any service types -- the booking webview
    treats that as "skip the service-select step", not an error."""
    merchant = await _get_bookable_merchant_or_404(session, merchant_id)
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    services = await AppointmentServiceRepository(session).list(tenant)
    return [AppointmentFlowServiceOut.model_validate(s) for s in services]


@router.get("/{merchant_id}/availability", response_model=list[AppointmentFlowSlotOut])
async def get_appointment_flow_availability(
    merchant_id: uuid.UUID,
    date: datetime.date,
    session: DbSession,
    service_id: uuid.UUID | None = None,
    staff_id: uuid.UUID | None = None,
) -> list[AppointmentFlowSlotOut]:
    """Public and unauthenticated. Returns the open slots for `date`, sized
    to the given service's duration (or the day's default slot duration
    when no service_id is given) -- see
    appointment_flow.domain.availability.get_available_slots for how
    working hours minus existing bookings becomes this list. An empty list
    means either the merchant hasn't configured hours for that weekday, or
    every slot that day is already taken -- the frontend shows the same
    "nothing available" state either way, it doesn't need to distinguish
    them."""
    merchant = await _get_bookable_merchant_or_404(session, merchant_id)
    tenant = TenantContext(merchant_id=merchant.merchant_id)

    duration_minutes = await resolve_duration_minutes(
        session, tenant, service_id=service_id, appointment_date=date
    )
    slots = await get_available_slots(
        session,
        tenant,
        appointment_date=date,
        service_duration_minutes=duration_minutes,
        staff_id=staff_id,
    )
    return [AppointmentFlowSlotOut(start_time=s.start_time, end_time=s.end_time) for s in slots]


@router.get("/{merchant_id}/customer-lookup", response_model=AppointmentFlowCustomerLookupOut)
async def customer_lookup(
    merchant_id: uuid.UUID, whatsapp_number: str, session: DbSession
) -> AppointmentFlowCustomerLookupOut:
    """Public and unauthenticated, same security model as
    ordering_flow.api.router.customer_lookup -- lets the booking webview
    prefill a returning customer's name and email once it knows their
    WhatsApp number (normally the `wa` query param the CTA link already
    carries, never a number the customer typed in here). 404s for a
    customer that doesn't exist yet, same as the ordering webview's
    version -- the normal new-customer case, not an error."""
    merchant = await _get_bookable_merchant_or_404(session, merchant_id)
    tenant = TenantContext(merchant_id=merchant.merchant_id)

    resolved = await resolve_customer_by_whatsapp_id(session, tenant, whatsapp_number)
    if resolved is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")

    return AppointmentFlowCustomerLookupOut(
        display_name=resolved.customer.display_name,
        email=resolved.customer.email,
    )


@router.post(
    "/{merchant_id}/book",
    response_model=AppointmentFlowBookingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def book_appointment(
    merchant_id: uuid.UUID, body: AppointmentFlowBookingRequest, session: DbSession
) -> AppointmentFlowBookingResponse:
    merchant = await _get_bookable_merchant_or_404(session, merchant_id)
    tenant = TenantContext(merchant_id=merchant.merchant_id)

    try:
        result = await perform_booking(
            session,
            tenant,
            merchant,
            customer_whatsapp_number=body.customer_whatsapp_number,
            customer_display_name=body.customer_display_name,
            name=body.name,
            email=body.email,
            appointment_date=body.appointment_date,
            start_time=body.start_time,
            service_id=body.service_id,
            staff_id=body.staff_id,
            created_via="browser",
            notes=body.notes,
        )
    except PastDateError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Cannot book an appointment in the past"
        ) from exc
    except SlotConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "slot_no_longer_available") from exc

    appointment = result.appointment
    return AppointmentFlowBookingResponse(
        appointment_id=appointment.appointment_id,
        appointment_number=appointment.appointment_number,
        status=appointment.status,
        appointment_date=appointment.appointment_date,
        start_time=appointment.start_time,
        end_time=appointment.end_time,
    )
