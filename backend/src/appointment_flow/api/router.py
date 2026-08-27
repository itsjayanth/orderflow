import uuid

from fastapi import APIRouter, HTTPException, status

from appointment_flow.api.schemas import (
    AppointmentFlowBookingRequest,
    AppointmentFlowBookingResponse,
    AppointmentFlowInfoOut,
)
from appointment_flow.domain.booking import PastDateError, perform_booking
from identity.adapters.repository import MerchantRepository
from identity.domain.models import Merchant
from shared.deps import DbSession
from shared.tenant import TenantContext

router = APIRouter(prefix="/api/v1/appointment-flow", tags=["appointment_flow"])


async def _get_bookable_merchant_or_404(session: DbSession, merchant_id: uuid.UUID) -> Merchant:
    merchant = await MerchantRepository(session).get(merchant_id)
    if merchant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurant not found")
    if not merchant.appointment_booking_enabled:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Appointment booking is not available for this restaurant"
        )
    return merchant


@router.get("/{merchant_id}/info", response_model=AppointmentFlowInfoOut)
async def get_appointment_flow_info(
    merchant_id: uuid.UUID, session: DbSession
) -> AppointmentFlowInfoOut:
    """Public and unauthenticated -- this is what the customer-facing
    booking webview loads before showing its date/time/details form."""
    merchant = await _get_bookable_merchant_or_404(session, merchant_id)
    return AppointmentFlowInfoOut(business_name=merchant.business_name)


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
            customer_whatsapp_number=body.customer_whatsapp_number,
            customer_display_name=body.customer_display_name,
            name=body.name,
            email=body.email,
            appointment_date=body.appointment_date,
            appointment_time=body.appointment_time,
            notes=body.notes,
        )
    except PastDateError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Cannot book an appointment in the past"
        ) from exc

    appointment = result.appointment
    return AppointmentFlowBookingResponse(
        appointment_id=appointment.appointment_id,
        appointment_number=appointment.appointment_number,
        status=appointment.status,
        appointment_date=appointment.appointment_date,
        appointment_time=appointment.appointment_time,
    )
