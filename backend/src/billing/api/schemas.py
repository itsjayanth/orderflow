import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel


class PlanOut(BaseModel):
    plan_id: uuid.UUID
    tier: str
    billing_interval: str
    display_name: str
    price_inr: Decimal
    order_cap: int | None
    whatsapp_flow_enabled: bool
    branding_required: bool
    # razorpay_plan_id is deliberately NOT exposed -- internal provider
    # detail, not something the pricing page or dashboard needs.


class SubscriptionOut(BaseModel):
    merchant_id: uuid.UUID
    plan: PlanOut
    status: str
    trial_ends_at: datetime.datetime | None
    current_period_start: datetime.datetime | None
    current_period_end: datetime.datetime | None
    past_due_since: datetime.datetime | None
    cancel_at_period_end: bool
    orders_used_this_cycle: int
    order_cap: int | None


class SubscribeRequest(BaseModel):
    plan_id: uuid.UUID


class ChangePlanRequest(BaseModel):
    plan_id: uuid.UUID


class SubscriptionCheckoutOut(BaseModel):
    provider_subscription_id: str
    checkout_url: str
