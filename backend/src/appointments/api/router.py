import datetime
import uuid
from typing import cast

from fastapi import APIRouter, HTTPException, status

from appointments.adapters.repository import (
    AppointmentNotFoundError,
    AppointmentRepository,
    SlotConflictError,
)
from appointments.adapters.scheduling_repository import AppointmentServiceRepository
from appointments.api.schemas import (
    AppointmentOut,
    AppointmentPaymentLinkOut,
    AppointmentRescheduleRequest,
    AppointmentStatus,
    AppointmentStatusUpdate,
    AppointmentUpdate,
    CreatedVia,
    PaymentStatus,
)
from appointments.domain.events import (
    AppointmentCancelled,
    AppointmentCompleted,
    AppointmentConfirmed,
    publish,
)
from appointments.domain.models import Appointment
from appointments.domain.state_machine import IllegalTransitionError
from payments.adapters.gateway_selector import get_payment_gateway, resolve_credentials
from payments.adapters.repository import (
    MerchantPaymentCredentialsRepository,
    PaymentEventRepository,
)
from shared.deps import CurrentTenant, DbSession

router = APIRouter(prefix="/api/v1/appointments", tags=["appointments"])

_EVENT_BY_STATUS = {
    "confirmed": AppointmentConfirmed,
    "completed": AppointmentCompleted,
    "cancelled": AppointmentCancelled,
}


def _to_appointment_out(appointment: Appointment) -> AppointmentOut:
    """Built manually (rather than pure `AppointmentOut.model_validate`)
    because customer_number/customer_whatsapp_number/customer_name are
    flattened from the eager-loaded `appointment.customer` relationship,
    not plain attributes on Appointment itself -- same rationale as
    orders/api/router.py's `_to_order_out`."""
    return AppointmentOut(
        appointment_id=appointment.appointment_id,
        appointment_number=appointment.appointment_number,
        customer_id=appointment.customer_id,
        customer_number=appointment.customer.customer_number,
        customer_whatsapp_number=appointment.customer.whatsapp_number,
        customer_name=appointment.customer.display_name,
        name=appointment.name,
        email=appointment.email,
        appointment_date=appointment.appointment_date,
        start_time=appointment.start_time,
        end_time=appointment.end_time,
        service_id=appointment.service_id,
        staff_id=appointment.staff_id,
        created_via=cast(CreatedVia, appointment.created_via),
        payment_status=cast(PaymentStatus, appointment.payment_status),
        notes=appointment.notes,
        status=cast(AppointmentStatus, appointment.status),
        requested_at=appointment.requested_at,
        confirmed_at=appointment.confirmed_at,
        completed_at=appointment.completed_at,
        cancelled_at=appointment.cancelled_at,
    )


@router.get("", response_model=list[AppointmentOut])
async def list_appointments(
    tenant: CurrentTenant,
    session: DbSession,
    status: str | None = None,
    from_date: datetime.date | None = None,
    to_date: datetime.date | None = None,
    customer_id: uuid.UUID | None = None,
) -> list[AppointmentOut]:
    appointments = await AppointmentRepository(session).list(
        tenant,
        status=status,
        from_date=from_date,
        to_date=to_date,
        customer_id=customer_id,
    )
    return [_to_appointment_out(appointment) for appointment in appointments]


@router.get("/{appointment_id}", response_model=AppointmentOut)
async def get_appointment(
    appointment_id: uuid.UUID, tenant: CurrentTenant, session: DbSession
) -> AppointmentOut:
    appointment = await AppointmentRepository(session).get(tenant, appointment_id)
    if appointment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    return _to_appointment_out(appointment)


@router.patch("/{appointment_id}/status", response_model=AppointmentOut)
async def update_appointment_status(
    appointment_id: uuid.UUID,
    body: AppointmentStatusUpdate,
    tenant: CurrentTenant,
    session: DbSession,
) -> AppointmentOut:
    repo = AppointmentRepository(session)
    try:
        appointment = await repo.transition_status(tenant, appointment_id, body.to_status)
    except AppointmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found") from exc
    except IllegalTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await session.commit()

    event_cls = _EVENT_BY_STATUS.get(body.to_status)
    if event_cls is not None:
        await publish(
            event_cls(appointment_id=appointment.appointment_id, merchant_id=tenant.merchant_id)
        )

    return _to_appointment_out(appointment)


@router.patch("/{appointment_id}", response_model=AppointmentOut)
async def update_appointment(
    appointment_id: uuid.UUID, body: AppointmentUpdate, tenant: CurrentTenant, session: DbSession
) -> AppointmentOut:
    appointment = await AppointmentRepository(session).update_notes(
        tenant, appointment_id, **body.model_dump(exclude_unset=True)
    )
    if appointment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    await session.commit()
    return _to_appointment_out(appointment)


@router.patch("/{appointment_id}/reschedule", response_model=AppointmentOut)
async def reschedule_appointment(
    appointment_id: uuid.UUID,
    body: AppointmentRescheduleRequest,
    tenant: CurrentTenant,
    session: DbSession,
) -> AppointmentOut:
    """Dashboard-only date/time change -- NOT a state-machine transition
    (status is untouched), see AppointmentRepository.reschedule's
    docstring. Preserves the appointment's existing duration (new_end =
    new_start + old duration) rather than taking a duration from the
    request, since this endpoint's job is "move the same booking," not
    "resize it"."""
    existing = await AppointmentRepository(session).get(tenant, appointment_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")

    duration = datetime.datetime.combine(
        datetime.date.min, existing.end_time
    ) - datetime.datetime.combine(datetime.date.min, existing.start_time)
    new_end_time = (
        datetime.datetime.combine(body.appointment_date, body.start_time) + duration
    ).time()

    try:
        appointment = await AppointmentRepository(session).reschedule(
            tenant,
            appointment_id,
            appointment_date=body.appointment_date,
            start_time=body.start_time,
            end_time=new_end_time,
        )
    except SlotConflictError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "slot_no_longer_available") from exc

    if appointment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    await session.commit()
    return _to_appointment_out(appointment)


@router.post(
    "/{appointment_id}/payment-link",
    response_model=AppointmentPaymentLinkOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment_payment_link(
    appointment_id: uuid.UUID, tenant: CurrentTenant, session: DbSession
) -> AppointmentPaymentLinkOut:
    """Placeholder payment-link generation -- Task 5 of the appointment
    scheduling work. Reuses the same provider-agnostic PaymentGateway
    Protocol and gateway_selector Orders already use; DummyPaymentGateway
    handles it until the merchant has real Razorpay credentials on file,
    exactly like Orders today. Amount comes from the appointment's linked
    AppointmentService price -- there's no amount field on Appointment
    itself, and guessing one rather than requiring a priced service would
    silently charge the wrong number."""
    appointment = await AppointmentRepository(session).get(tenant, appointment_id)
    if appointment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")

    service = (
        await AppointmentServiceRepository(session).get(tenant, appointment.service_id)
        if appointment.service_id is not None
        else None
    )
    if service is None or service.price is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "no price configured for this appointment -- set a service price first",
        )

    credentials = await MerchantPaymentCredentialsRepository(session).get(tenant)
    key_id, key_secret = resolve_credentials(credentials, tenant.merchant_id)
    gateway = get_payment_gateway(key_id, key_secret)

    link = gateway.create_link(
        entity_id=appointment.appointment_id, amount=service.price, currency="INR"
    )

    await PaymentEventRepository(session).create(
        appointment_id=appointment.appointment_id,
        provider="razorpay" if key_id else "dummy",
        event_type="link_created",
        provider_order_id=link.provider_order_id,
    )
    appointment.payment_status = "pending"
    await session.commit()

    return AppointmentPaymentLinkOut(url=link.url, provider_order_id=link.provider_order_id)
