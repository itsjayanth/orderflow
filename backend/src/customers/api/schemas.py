import datetime
import uuid

from pydantic import BaseModel, Field


class CustomerOut(BaseModel):
    customer_id: uuid.UUID
    customer_number: int
    whatsapp_number: str
    display_name: str | None
    default_contact_phone: str | None
    email: str | None
    first_seen_at: datetime.datetime
    last_order_at: datetime.datetime | None
    is_active: bool
    # Read-only: only the customer's own STOP/START WhatsApp message can
    # change this (conversation/domain/handler.py) -- no staff-facing write
    # path exists on purpose, see CustomerUpdate below.
    marketing_opt_out: bool
    marketing_opt_out_at: datetime.datetime | None

    model_config = {"from_attributes": True}


class CustomerCreate(BaseModel):
    whatsapp_number: str = Field(min_length=1, max_length=32)
    display_name: str | None = Field(default=None, max_length=255)
    default_contact_phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)


class CustomerUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    default_contact_phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class AddressOut(BaseModel):
    address_id: uuid.UUID
    label: str
    line1: str
    line2: str | None
    landmark: str | None
    city: str
    pincode: str
    geo_lat: float | None
    geo_long: float | None
    is_default: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class CustomerWithAddressesOut(CustomerOut):
    addresses: list[AddressOut]
