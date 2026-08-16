import json
import uuid
from decimal import Decimal

import razorpay
from razorpay.errors import BadRequestError, SignatureVerificationError

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
        self._key_id = key_id
        self._key_secret = key_secret

    def create_link(self, *, order_id: uuid.UUID, amount: Decimal, currency: str) -> PaymentLink:
        payload = {
            "amount": int(amount * 100),  # paise
            "currency": currency,
            "reference_id": str(order_id),
            "notes": {"order_id": str(order_id)},
        }

        # UPI Payment Links skip Razorpay's full checkout page (card/netbanking/
        # UPI method picker) and go straight to "choose a UPI app" -- the
        # closest this integration gets to a native app-switch feel for the
        # payment step. Razorpay only supports this in Live Mode (rzp_live_
        # keys); requesting it against a Test Mode key raises BadRequestError,
        # so Test Mode transparently falls back to a standard link below.
        if self._key_id.startswith("rzp_live_"):
            try:
                response = self._client.payment_link.create({**payload, "upi_link": True})
                return PaymentLink(url=response["short_url"], provider_order_id=response["id"])
            except BadRequestError:
                pass

        response = self._client.payment_link.create(payload)
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
