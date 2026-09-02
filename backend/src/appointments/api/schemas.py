import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, Field

AppointmentStatus = Literal["requested", "confirmed", "completed", "cancelled"]
PaymentStatus = Literal["not_required", "pending", "paid", "failed"]
CreatedVia = Literal["flow", "browser", "dashboard"]


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
