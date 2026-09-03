import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, Field

AppointmentStatus = Literal["requested", "confirmed", "completed", "cancelled"]
PaymentStatus = Literal["not_required", "pending", "paid", "failed"]
CreatedVia = Literal["flow", "browser", "dashboard"]
AppointmentEventType = Literal[
    "requested", "confirmed", "completed", "cancelled", "rescheduled", "reminder_sent"
]


class AppointmentStatusEventOut(BaseModel):
    """One row of the Task 5 history timeline -- see
    appointments/domain/models.py's AppointmentStatusEvent for what each
    field means per event_type. Fields irrelevant to a given event_type
    are simply null (e.g. offset_minutes only on "reminder_sent")."""

    event_type: AppointmentEventType
    from_status: AppointmentStatus | None
    to_status: AppointmentStatus | None
    from_appointment_date: datetime.date | None
    from_start_time: datetime.time | None
    to_appointment_date: datetime.date | None
    to_start_time: datetime.time | None
    offset_minutes: int | None
    changed_by: str
    changed_at: datetime.datetime

    model_config = {"from_attributes": True}


class AppointmentOut(BaseModel):
    appointment_id: uuid.UUID
    appointment_number: int
    customer_id: uuid.UUID
    customer_number: int
    customer_whatsapp_number: str
    customer_name: str | None
    name: str
    email: str
    appointment_date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
    service_id: uuid.UUID | None
    staff_id: uuid.UUID | None
    created_via: CreatedVia
    payment_status: PaymentStatus
    notes: str | None
    status: AppointmentStatus
    requested_at: datetime.datetime
    confirmed_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    cancelled_at: datetime.datetime | None
    # Chronological (see Appointment.status_events' order_by) -- the
    # dashboard's history dropdown (Task 5) renders this directly, no
    # separate per-event endpoint. Only populated on GET /{appointment_id}
    # (see _to_appointment_out's docstring) -- list_appointments doesn't
    # eager-load it, since the appointments list view doesn't need it.
    status_events: list[AppointmentStatusEventOut] = []

    model_config = {"from_attributes": True}


class AppointmentStatusUpdate(BaseModel):
    to_status: Literal["confirmed", "completed", "cancelled"]


class AppointmentPaymentLinkOut(BaseModel):
    url: str
    provider_order_id: str


class AppointmentUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class AppointmentRescheduleRequest(BaseModel):
    appointment_date: datetime.date
    start_time: datetime.time
