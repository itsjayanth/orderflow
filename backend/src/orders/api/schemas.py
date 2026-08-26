import datetime
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from customers.api.schemas import AddressOut

FulfillmentStatus = Literal["new", "preparing", "ready", "completed", "cancelled"]


class OrderItemOut(BaseModel):
    order_item_id: uuid.UUID
    item_id: uuid.UUID
    name_snapshot: str
    price_snapshot: Decimal
    quantity: int
    line_total: Decimal

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    order_id: uuid.UUID
    order_number: int
    customer_id: uuid.UUID
    customer_number: int
    customer_name: str | None
    customer_whatsapp_number: str
    order_type: str
    payment_method: str
    payment_status: str
    fulfillment_status: str | None
    contact_phone: str | None
    notes: str | None
    subtotal: Decimal
    total: Decimal
    currency: str
    placed_at: datetime.datetime
    paid_at: datetime.datetime | None
    ready_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    items: list[OrderItemOut]

    model_config = {"from_attributes": True}


class OrderDetailOut(OrderOut):
    """The single-order GET's response -- adds the one field (delivery
    address) that needs an extra join/eager-load and so isn't worth
    fetching for every row of the list endpoint. `order_type` on the base
    OrderOut already tells the caller whether to expect this to be
    non-null ("delivery" vs "pickup")."""

    delivery_address: AddressOut | None


class FulfillmentStatusUpdate(BaseModel):
    to_status: FulfillmentStatus


class OrderUpdate(BaseModel):
    contact_phone: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=2000)


class OrderSummaryOut(BaseModel):
    total_orders: int
    revenue_generated: Decimal
    amount_collected: Decimal
    cod_orders: int
    new_orders: int
    preparing_orders: int
    ready_orders: int
    completed_orders: int
    cancelled_orders: int
