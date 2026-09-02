import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PaymentLink:
    url: str
    provider_order_id: str


class WebhookVerificationError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class VerifiedPaymentEvent:
    """The result of successfully verifying a webhook payload's signature --
    callers can trust these fields came from the provider, not from
    whatever the client claims."""

    provider_payment_id: str
    provider_order_id: str
    succeeded: bool


class PaymentGateway(Protocol):
    """The port ARCHITECTURE.md Section 4 calls for -- swapping providers
    (or, right now, swapping in a dummy implementation while waiting on
    real Razorpay credentials) is an adapter change, not a domain change.

    entity_id is opaque to the gateway -- just something to embed in the
    checkout URL/reference so a later webhook can be traced back to
    whatever domain object paid for it (an Order today, an Appointment as
    of the payment-link-placeholder work). The gateway itself has no
    concept of "order" vs "appointment"."""

    def create_link(
        self, *, entity_id: uuid.UUID, amount: Decimal, currency: str
    ) -> PaymentLink: ...

    def verify_webhook(self, *, payload: bytes, signature: str) -> VerifiedPaymentEvent: ...
