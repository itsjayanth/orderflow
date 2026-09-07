import hashlib
import hmac
import json
import uuid

from billing.domain.gateway import (
    BillingWebhookVerificationError,
    SubscriptionCheckout,
    VerifiedBillingEvent,
)
from billing.domain.models import Plan


class DummyBillingGateway:
    """Stands in for RazorpayBillingGateway until a real platform Razorpay
    account exists (Settings holds no platform_razorpay_key_id, or an
    obvious placeholder). `create_subscription` fabricates a local
    subscription id/checkout URL instead of calling Razorpay's Subscriptions
    API. `verify_webhook` still does the exact same HMAC-SHA256(body,
    secret) verification Razorpay's real webhooks use -- against the
    dedicated platform billing webhook secret, not a key_secret -- so
    signature logic is fully exercised now and doesn't need to change when
    real keys arrive. Mirrors payments/adapters/dummy_gateway.py's
    real-HMAC-fake-network pattern exactly."""

    def __init__(self, webhook_secret: str) -> None:
        self._webhook_secret = webhook_secret

    def create_subscription(self, *, plan: Plan, merchant_id: uuid.UUID) -> SubscriptionCheckout:
        provider_subscription_id = f"dummy_sub_{uuid.uuid4().hex[:16]}"
        return SubscriptionCheckout(
            provider_subscription_id=provider_subscription_id,
            checkout_url=(
                f"https://dummy-billing.orderflow.local/activate/{provider_subscription_id}"
            ),
        )

    def verify_webhook(self, *, payload: bytes, signature: str) -> VerifiedBillingEvent:
        expected = hmac.new(
            key=self._webhook_secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise BillingWebhookVerificationError("dummy billing webhook signature mismatch")

        data = json.loads(payload)
        subscription_entity = data["payload"]["subscription"]["entity"]
        # Not every subscription event carries a payment entity (e.g.
        # subscription.activated on a zero-amount trial-to-paid transition)
        # -- provider_payment_id is optional, unlike payments/'s
        # VerifiedPaymentEvent where a payment entity is always present.
        payment_entity = data.get("payload", {}).get("payment", {}).get("entity")
        return VerifiedBillingEvent(
            provider_subscription_id=subscription_entity["id"],
            provider_payment_id=payment_entity["id"] if payment_entity else None,
            event_type=data["event"],
            raw_payload=payload,
        )
