import uuid
from dataclasses import dataclass
from typing import Protocol

from billing.domain.models import Plan


@dataclass(frozen=True, slots=True)
class SubscriptionCheckout:
    provider_subscription_id: str
    checkout_url: str


class BillingWebhookVerificationError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class VerifiedBillingEvent:
    """The result of successfully verifying a platform-billing webhook
    payload's signature -- callers can trust these fields came from the
    provider, not from anything a client claims. `event_type` is the raw
    Razorpay event name (e.g. "subscription.activated"); mapping it onto a
    Subscription.status transition is the router's job, not the gateway's."""

    provider_subscription_id: str
    provider_payment_id: str | None
    event_type: str
    raw_payload: bytes


class BillingGateway(Protocol):
    """The platform-billing counterpart to payments/domain/gateway.py's
    PaymentGateway -- same port shape, different money flow (platform ->
    merchant subscription fees, not customer -> merchant order payments).
    Unlike PaymentGateway, there's exactly one platform Razorpay account,
    not per-merchant credentials -- see
    billing/adapters/gateway_selector.py."""

    def create_subscription(
        self, *, plan: Plan, merchant_id: uuid.UUID
    ) -> SubscriptionCheckout: ...

    def verify_webhook(self, *, payload: bytes, signature: str) -> VerifiedBillingEvent: ...
