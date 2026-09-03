import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    business_name: str
    owner_name: str
    owner_contact: EmailStr
    password: str


class LoginRequest(BaseModel):
    email_or_phone: str
    password: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MerchantOut(BaseModel):
    merchant_id: uuid.UUID
    business_name: str
    onboarding_status: str
    restaurant_enabled: bool
    appointment_enabled: bool

    model_config = {"from_attributes": True}


class StaffUserOut(BaseModel):
    staff_user_id: uuid.UUID
    name: str
    email_or_phone: str
    role: str
    last_login_at: datetime.datetime | None

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    staff_user: StaffUserOut
    merchant: MerchantOut


class AppointmentAvailabilityWindow(BaseModel):
    """One weekday's working-hours window. day_of_week follows Python's
    date.weekday(): 0=Monday .. 6=Sunday."""

    day_of_week: int = Field(ge=0, le=6)
    start_time: datetime.time
    end_time: datetime.time
    slot_duration_minutes: int = Field(default=30, gt=0)
    buffer_minutes: int = Field(default=0, ge=0)

    model_config = {"from_attributes": True}


def _positive_offsets(value: list[int]) -> list[int]:
    if any(hours <= 0 for hours in value):
        raise ValueError("reminder_offsets_hours must all be positive")
    return value


class AppointmentAvailabilitySettingsOut(BaseModel):
    timezone: str
    windows: list[AppointmentAvailabilityWindow]
    # Hours-before-appointment offsets the reminder scan sends a WhatsApp
    # reminder at (shared/scheduler.py). Empty list = reminders off.
    reminder_offsets_hours: list[int] = Field(default_factory=lambda: [24])

    _validate_offsets = field_validator("reminder_offsets_hours")(_positive_offsets)


class AppointmentAvailabilitySettingsUpdate(BaseModel):
    timezone: str
    windows: list[AppointmentAvailabilityWindow]
    reminder_offsets_hours: list[int] = Field(default_factory=lambda: [24])

    _validate_offsets = field_validator("reminder_offsets_hours")(_positive_offsets)


class AppointmentServiceOut(BaseModel):
    service_id: uuid.UUID
    name: str
    duration_minutes: int
    price: Decimal | None
    is_active: bool

    model_config = {"from_attributes": True}


class AppointmentServiceCreateRequest(BaseModel):
    name: str
    duration_minutes: int = Field(gt=0)
    price: Decimal | None = None


class AppointmentServiceUpdateRequest(BaseModel):
    name: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    price: Decimal | None = None
    is_active: bool | None = None
