import json
import uuid
from decimal import Decimal

import razorpay
from razorpay.errors import SignatureVerificationError

from payments.domain.gateway import PaymentLink, VerifiedPaymentEvent, WebhookVerificationError


class RazorpayGateway:
    """Real Razorpay integration via the official SDK. Selected by
    `get_payment_gateway` (adapters/gateway_selector.py) only when the
    merchant's key_id has a genuine Razorpay prefix -- otherwise
    DummyPaymentGateway handles it, so this class is exercised end-to-end
    the moment real test-mode keys are entered in Settings, with no code
    change required."""

    def __init__(self, key_id: str, key_secret: str) -> None:
        self._client = razorpay.Client(auth=(key_id, key_secret))
        self._key_secret = key_secret

    def create_link(self, *, order_id: uuid.UUID, amount: Decimal, currency: str) -> PaymentLink:
        response = self._client.payment_link.create(
            {
                "amount": int(amount * 100),  # paise
                "currency": currency,
                "reference_id": str(order_id),
                "notes": {"order_id": str(order_id)},
            }
        )
        return PaymentLink(url=response["short_url"], provider_order_id=response["id"])

    def verify_webhook(self, *, payload: bytes, signature: str) -> VerifiedPaymentEvent:
        body = payload.decode("utf-8")
        try:
            self._client.utility.verify_webhook_signature(body, signature, self._key_secret)
        except SignatureVerificationError as exc:
            raise WebhookVerificationError(str(exc)) from exc

        data = json.loads(body)
        entity = data["payload"]["payment"]["entity"]
        return VerifiedPaymentEvent(
            provider_payment_id=entity["id"],
            provider_order_id=entity["order_id"],
            succeeded=data["event"] == "payment.captured",
        )
