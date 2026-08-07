import datetime
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

FulfillmentStatus = Literal["new", "preparing", "ready", "completed", "cancelled"]


class OrderItemOut(BaseModel):
    order_item_id: uuid.UUID
    menu_item_id: uuid.UUID
    name_snapshot: str
    price_snapshot: Decimal
    quantity: int
    line_total: Decimal

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    order_id: uuid.UUID
    customer_id: uuid.UUID
    order_type: str
    payment_method: str
    payment_status: str
    fulfillment_status: str | None
    subtotal: Decimal
    total: Decimal
    currency: str
    placed_at: datetime.datetime
    paid_at: datetime.datetime | None
    ready_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    items: list[OrderItemOut]

    model_config = {"from_attributes": True}


class FulfillmentStatusUpdate(BaseModel):
    to_status: FulfillmentStatus


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
