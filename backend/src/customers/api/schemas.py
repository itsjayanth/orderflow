import datetime
import uuid

from pydantic import BaseModel


class CustomerOut(BaseModel):
    customer_id: uuid.UUID
    whatsapp_number: str
    display_name: str | None
    first_seen_at: datetime.datetime
    last_order_at: datetime.datetime | None

    model_config = {"from_attributes": True}


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
