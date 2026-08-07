import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class PublicMenuItemOut(BaseModel):
    menu_item_id: uuid.UUID
    category: str
    name: str
    price: Decimal

    model_config = {"from_attributes": True}


class PublicMenuOut(BaseModel):
    business_name: str
    items: list[PublicMenuItemOut]
    # Null until the merchant has connected WhatsApp (onboarding) -- lets
    # the webview link back to the chat (e.g. after checkout) since a
    # website can't programmatically return the customer to WhatsApp itself.
    merchant_whatsapp_number: str | None = None


class OrderingFlowCheckoutItem(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int


class OrderingFlowCheckoutRequest(BaseModel):
    customer_whatsapp_number: str
    customer_display_name: str | None = None
    items: list[OrderingFlowCheckoutItem]
    payment_method: Literal["online", "cod"] = "online"
    order_type: Literal["pickup", "delivery"] = "pickup"


class OrderingFlowCheckoutResponse(BaseModel):
    order_id: uuid.UUID
    order_number: int
    payment_status: str
    fulfillment_status: str | None
    total: str
    payment_link_url: str | None
