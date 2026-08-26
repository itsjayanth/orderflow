import datetime
import uuid

from pydantic import BaseModel, EmailStr, Field


class AppointmentFlowInfoOut(BaseModel):
    business_name: str


class AppointmentFlowBookingRequest(BaseModel):
    customer_whatsapp_number: str
    customer_display_name: str | None = None
    name: str
    email: EmailStr
    appointment_date: datetime.date
    appointment_time: datetime.time
    notes: str | None = Field(default=None, max_length=1000)


class AppointmentFlowBookingResponse(BaseModel):
    appointment_id: uuid.UUID
    appointment_number: int
    status: str
    appointment_date: datetime.date
    appointment_time: datetime.time
