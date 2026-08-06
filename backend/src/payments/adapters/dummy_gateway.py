import hashlib
import hmac
import json
import uuid
from decimal import Decimal

from payments.domain.gateway import PaymentLink, VerifiedPaymentEvent, WebhookVerificationError


class DummyPaymentGateway:
    """Stands in for RazorpayGateway when the merchant hasn't configured
    real Razorpay credentials yet (Settings holds a placeholder key_id, or
    none at all). `create_link` fabricates a local checkout URL instead of
    calling Razorpay's API. `verify_webhook` still does the exact same
    HMAC-SHA256(body, secret) verification Razorpay's real webhooks use --
    security-critical logic is fully exercised now, against whatever
    secret is on file, dummy or real, and doesn't need to change when real
    keys arrive."""

    def __init__(self, key_secret: str) -> None:
        self._key_secret = key_secret

    def create_link(self, *, order_id: uuid.UUID, amount: Decimal, currency: str) -> PaymentLink:
        provider_order_id = f"dummy_order_{uuid.uuid4().hex[:16]}"
        return PaymentLink(
            url=f"https://dummy-checkout.orderflow.local/pay/{provider_order_id}"
            f"?order_id={order_id}&amount={amount}&currency={currency}",
            provider_order_id=provider_order_id,
        )

    def verify_webhook(self, *, payload: bytes, signature: str) -> VerifiedPaymentEvent:
        expected = hmac.new(
            key=self._key_secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise WebhookVerificationError("dummy webhook signature mismatch")

        data = json.loads(payload)
        entity = data["payload"]["payment"]["entity"]
        return VerifiedPaymentEvent(
            provider_payment_id=entity["id"],
            provider_order_id=entity["order_id"],
            succeeded=data["event"] == "payment.captured",
        )
