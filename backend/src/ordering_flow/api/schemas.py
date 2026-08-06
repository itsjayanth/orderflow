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
    payment_status: str
    fulfillment_status: str | None
    total: str
    payment_link_url: str | None
