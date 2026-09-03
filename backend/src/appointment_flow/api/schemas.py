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


class AppointmentFlowCustomerLookupOut(BaseModel):
    """Returned by GET /{merchant_id}/customer-lookup for a returning
    customer so the booking webview can prefill name + email without
    asking again -- mirrors ordering_flow's OrderingFlowCustomerLookupOut.
    Deliberately carries no phone/whatsapp field: identity itself is never
    round-tripped back to the client through this endpoint, only the
    profile data that goes with it, since the appointment flow has no
    "confirm your number" or "use a different number" step for a client
    value to feed into in the first place."""

    display_name: str | None
    # None both for a customer who's genuinely never given an email (e.g.
    # they've only ever ordered food, never booked before) and for a
    # brand-new customer -- either way the webview just shows an empty,
    # fillable email field, not an error state.
    email: str | None


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
