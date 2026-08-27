import datetime
import uuid
from typing import cast

from fastapi import APIRouter, HTTPException, status

from appointments.adapters.repository import AppointmentNotFoundError, AppointmentRepository
from appointments.api.schemas import (
    AppointmentOut,
    AppointmentStatus,
    AppointmentStatusUpdate,
    AppointmentUpdate,
)
from appointments.domain.events import (
    AppointmentCancelled,
    AppointmentCompleted,
    AppointmentConfirmed,
    publish,
)
from appointments.domain.models import Appointment
from appointments.domain.state_machine import IllegalTransitionError
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
        appointment_time=appointment.appointment_time,
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
