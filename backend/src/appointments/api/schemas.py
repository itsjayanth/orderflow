import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, Field

AppointmentStatus = Literal["requested", "confirmed", "completed", "cancelled"]


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
    appointment_time: datetime.time
    notes: str | None
    status: AppointmentStatus
    requested_at: datetime.datetime
    confirmed_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    cancelled_at: datetime.datetime | None

    model_config = {"from_attributes": True}


class AppointmentStatusUpdate(BaseModel):
    to_status: Literal["confirmed", "completed", "cancelled"]


class AppointmentUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)
