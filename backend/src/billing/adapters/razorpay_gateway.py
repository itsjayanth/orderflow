import json
import uuid

import razorpay
from razorpay.errors import SignatureVerificationError

from billing.domain.gateway import (
    BillingWebhookVerificationError,
    SubscriptionCheckout,
    VerifiedBillingEvent,
)
from billing.domain.models import Plan

# Razorpay requires a finite total_count of billing cycles per
# subscription -- there's no "run forever" option. 1200 monthly (or
# annual) cycles is effectively unbounded for a restaurant's lifetime
# (100 years); change-plan/cancel are handled as separate API calls
# (edit/cancel), not by ever letting this run out.
_TOTAL_COUNT = 1200


class RazorpayBillingGateway:
    """Real Razorpay Subscriptions integration via the official SDK.
    Selected by `get_billing_gateway` (adapters/gateway_selector.py) only
    when the platform key_id has a genuine Razorpay prefix -- otherwise
    DummyBillingGateway handles it. Unlike payments/adapters/
    razorpay_gateway.py, there's exactly one platform account (no
    per-merchant key_id/key_secret), and webhook verification uses a
    dedicated webhook secret, never the account's key_secret -- the real
    Razorpay pattern for Subscriptions/webhooks in general."""

    def __init__(self, key_id: str, key_secret: str, webhook_secret: str) -> None:
        self._client = razorpay.Client(auth=(key_id, key_secret))
        self._webhook_secret = webhook_secret

    def create_subscription(self, *, plan: Plan, merchant_id: uuid.UUID) -> SubscriptionCheckout:
        response = self._client.subscription.create(
            {
                "plan_id": plan.razorpay_plan_id,
                "customer_notify": 1,
                "quantity": 1,
                "total_count": _TOTAL_COUNT,
                "notes": {"merchant_id": str(merchant_id)},
            }
        )
        return SubscriptionCheckout(
            provider_subscription_id=response["id"],
            checkout_url=response["short_url"],
        )

    def verify_webhook(self, *, payload: bytes, signature: str) -> VerifiedBillingEvent:
        body = payload.decode("utf-8")
        try:
            self._client.utility.verify_webhook_signature(body, signature, self._webhook_secret)
        except SignatureVerificationError as exc:
            raise BillingWebhookVerificationError(str(exc)) from exc

        data = json.loads(body)
        subscription_entity = data["payload"]["subscription"]["entity"]
        payment_entity = data.get("payload", {}).get("payment", {}).get("entity")
        return VerifiedBillingEvent(
            provider_subscription_id=subscription_entity["id"],
            provider_payment_id=payment_entity["id"] if payment_entity else None,
            event_type=data["event"],
            raw_payload=payload,
        )
