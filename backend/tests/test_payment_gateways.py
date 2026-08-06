import hashlib
import hmac
import json
import uuid
from decimal import Decimal

import pytest

from payments.adapters.dummy_gateway import DummyPaymentGateway
from payments.adapters.gateway_selector import get_payment_gateway, resolve_credentials
from payments.adapters.razorpay_gateway import RazorpayGateway
from payments.domain.gateway import WebhookVerificationError
from payments.domain.models import MerchantPaymentCredentials


def _sign(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _payload(*, event: str, payment_id: str, order_id: str) -> bytes:
    return json.dumps(
        {
            "event": event,
            "payload": {"payment": {"entity": {"id": payment_id, "order_id": order_id}}},
        }
    ).encode("utf-8")


# --- DummyPaymentGateway -----------------------------------------------


def test_dummy_gateway_create_link_does_not_hit_network() -> None:
    gateway = DummyPaymentGateway("some-secret")

    link = gateway.create_link(order_id=uuid.uuid4(), amount=Decimal("349.00"), currency="INR")

    assert link.url.startswith("https://dummy-checkout.orderflow.local/pay/")
    assert link.provider_order_id.startswith("dummy_order_")


def test_dummy_gateway_verifies_correctly_signed_webhook() -> None:
    secret = "test-secret"
    gateway = DummyPaymentGateway(secret)
    payload = _payload(event="payment.captured", payment_id="pay_123", order_id="order_abc")
    signature = _sign(payload, secret)

    result = gateway.verify_webhook(payload=payload, signature=signature)

    assert result.provider_payment_id == "pay_123"
    assert result.provider_order_id == "order_abc"
    assert result.succeeded is True


def test_dummy_gateway_payment_failed_event_not_succeeded() -> None:
    secret = "test-secret"
    gateway = DummyPaymentGateway(secret)
    payload = _payload(event="payment.failed", payment_id="pay_123", order_id="order_abc")
    signature = _sign(payload, secret)

    result = gateway.verify_webhook(payload=payload, signature=signature)

    assert result.succeeded is False


def test_dummy_gateway_rejects_wrong_signature() -> None:
    gateway = DummyPaymentGateway("real-secret")
    payload = _payload(event="payment.captured", payment_id="pay_123", order_id="order_abc")
    wrong_signature = _sign(payload, "wrong-secret")

    with pytest.raises(WebhookVerificationError):
        gateway.verify_webhook(payload=payload, signature=wrong_signature)


def test_dummy_gateway_rejects_tampered_payload() -> None:
    secret = "test-secret"
    gateway = DummyPaymentGateway(secret)
    payload = _payload(event="payment.captured", payment_id="pay_123", order_id="order_abc")
    signature = _sign(payload, secret)
    tampered = _payload(event="payment.captured", payment_id="pay_999", order_id="order_abc")

    with pytest.raises(WebhookVerificationError):
        gateway.verify_webhook(payload=tampered, signature=signature)


# --- RazorpayGateway (verify_webhook is pure HMAC, no network needed) ---


def test_razorpay_gateway_verify_webhook_uses_real_hmac_algorithm() -> None:
    """DummyPaymentGateway and RazorpayGateway must agree byte-for-byte on
    signature verification -- that's what makes swapping to real keys a
    no-op for already-tested webhook logic."""
    secret = "shared-test-secret"
    payload = _payload(event="payment.captured", payment_id="pay_123", order_id="order_abc")
    signature = _sign(payload, secret)

    gateway = RazorpayGateway("rzp_test_fake", secret)
    result = gateway.verify_webhook(payload=payload, signature=signature)

    assert result.provider_payment_id == "pay_123"
    assert result.succeeded is True


def test_razorpay_gateway_rejects_wrong_signature() -> None:
    gateway = RazorpayGateway("rzp_test_fake", "real-secret")
    payload = _payload(event="payment.captured", payment_id="pay_123", order_id="order_abc")

    with pytest.raises(WebhookVerificationError):
        gateway.verify_webhook(payload=payload, signature=_sign(payload, "wrong-secret"))


# --- gateway_selector -----------------------------------------------------


@pytest.mark.parametrize("key_id", ["rzp_test_abc123", "rzp_live_abc123"])
def test_selector_picks_razorpay_for_real_looking_keys(key_id: str) -> None:
    gateway = get_payment_gateway(key_id, "secret")
    assert isinstance(gateway, RazorpayGateway)


@pytest.mark.parametrize("key_id", [None, "", "placeholder", "sk_not_razorpay"])
def test_selector_picks_dummy_for_anything_else(key_id: str | None) -> None:
    gateway = get_payment_gateway(key_id, "secret")
    assert isinstance(gateway, DummyPaymentGateway)


def test_resolve_credentials_defaults_when_no_row() -> None:
    merchant_id = uuid.uuid4()

    key_id, key_secret = resolve_credentials(None, merchant_id)

    assert key_id is None
    assert key_secret == f"dummy-secret-{merchant_id}"


def test_resolve_credentials_decrypts_stored_secret() -> None:
    from shared.encryption import encrypt

    merchant_id = uuid.uuid4()
    credentials = MerchantPaymentCredentials(
        merchant_id=merchant_id,
        razorpay_key_id="rzp_test_abc123",
        razorpay_key_secret_encrypted=encrypt("real-secret"),
    )

    key_id, key_secret = resolve_credentials(credentials, merchant_id)

    assert key_id == "rzp_test_abc123"
    assert key_secret == "real-secret"
