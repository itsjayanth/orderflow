import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


class AppointmentFlowInfoOut(BaseModel):
    business_name: str
    # Null until the merchant has connected WhatsApp (onboarding) -- the
    # dialable display phone number, not Meta's opaque phone_number_id, so
    # the booking webview's confirmation screen can send the customer back
    # to the chat once the appointment is booked. Stored verbatim as Meta
    # reports it ("+91 90000 00000"), so callers normalise it themselves.
    merchant_whatsapp_number: str | None = None


class AppointmentFlowServiceOut(BaseModel):
    service_id: uuid.UUID
    name: str
    duration_minutes: int
    price: Decimal | None

    model_config = {"from_attributes": True}


class AppointmentFlowSlotOut(BaseModel):
    start_time: datetime.time
    end_time: datetime.time


class AppointmentFlowBookingRequest(BaseModel):
    customer_whatsapp_number: str
    customer_display_name: str | None = None
    name: str
    email: EmailStr
    appointment_date: datetime.date
    start_time: datetime.time
    service_id: uuid.UUID | None = None
    staff_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)


class AppointmentFlowBookingResponse(BaseModel):
    appointment_id: uuid.UUID
    appointment_number: int
    status: str
    appointment_date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
