import uuid
from typing import Literal

from pydantic import BaseModel


class PaymentSettingsOut(BaseModel):
    razorpay_key_id: str | None
    razorpay_key_secret_set: bool
    using_real_gateway: bool


class PaymentSettingsUpdate(BaseModel):
    razorpay_key_id: str
    razorpay_key_secret: str


class TestCheckoutItem(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int


class TestCheckoutRequest(BaseModel):
    # Identifies the customer by phone number (find-or-create), the same
    # way Phase 6's real WhatsApp ordering flow will -- not by an existing
    # customer_id, since there's deliberately no way to create a customer
    # from the dashboard otherwise (customers/api/router.py is read-only).
    customer_whatsapp_number: str
    customer_display_name: str | None = None
    items: list[TestCheckoutItem]
    order_type: Literal["pickup", "delivery"] = "pickup"
    payment_method: Literal["online", "cod"] = "online"
    delivery_address_id: uuid.UUID | None = None


class TestCheckoutResponse(BaseModel):
    order_id: uuid.UUID
    payment_status: str
    fulfillment_status: str | None
    total: str
    payment_link_url: str | None
