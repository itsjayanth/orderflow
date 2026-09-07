import hashlib
import hmac
import json
import uuid
from decimal import Decimal

import pytest

from billing.adapters.dummy_gateway import DummyBillingGateway
from billing.adapters.gateway_selector import get_billing_gateway
from billing.adapters.razorpay_gateway import RazorpayBillingGateway
from billing.domain.gateway import BillingWebhookVerificationError
from billing.domain.models import Plan


def _plan(razorpay_plan_id: str | None = "plan_abc123") -> Plan:
    return Plan(
        plan_id=uuid.uuid4(),
        tier="growth",
        billing_interval="monthly",
        display_name="Growth",
        price_inr=Decimal("2499.00"),
        order_cap=750,
        whatsapp_flow_enabled=True,
        branding_required=False,
        razorpay_plan_id=razorpay_plan_id,
    )


def _sign(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _payload(*, event: str, subscription_id: str, payment_id: str | None = None) -> bytes:
    body = {
        "event": event,
        "payload": {"subscription": {"entity": {"id": subscription_id}}},
    }
    if payment_id is not None:
        body["payload"]["payment"] = {"entity": {"id": payment_id}}
    return json.dumps(body).encode("utf-8")


# --- DummyBillingGateway -----------------------------------------------


def test_dummy_gateway_create_subscription_does_not_hit_network() -> None:
    gateway = DummyBillingGateway("some-secret")

    checkout = gateway.create_subscription(plan=_plan(), merchant_id=uuid.uuid4())

    assert checkout.provider_subscription_id.startswith("dummy_sub_")
    assert checkout.checkout_url.startswith(
        "https://dummy-billing.orderflow.local/activate/"
    )
    assert checkout.provider_subscription_id in checkout.checkout_url


def test_dummy_gateway_verifies_correctly_signed_webhook_with_payment() -> None:
    secret = "test-secret"
    gateway = DummyBillingGateway(secret)
    payload = _payload(event="subscription.charged", subscription_id="sub_1", payment_id="pay_1")
    signature = _sign(payload, secret)

    result = gateway.verify_webhook(payload=payload, signature=signature)

    assert result.provider_subscription_id == "sub_1"
    assert result.provider_payment_id == "pay_1"
    assert result.event_type == "subscription.charged"


def test_dummy_gateway_verifies_webhook_with_no_payment_entity() -> None:
    """Not every subscription event carries a payment (e.g. activation on
    a zero-amount transition) -- provider_payment_id is optional."""
    secret = "test-secret"
    gateway = DummyBillingGateway(secret)
    payload = _payload(event="subscription.activated", subscription_id="sub_2")
    signature = _sign(payload, secret)

    result = gateway.verify_webhook(payload=payload, signature=signature)

    assert result.provider_subscription_id == "sub_2"
    assert result.provider_payment_id is None


def test_dummy_gateway_rejects_wrong_signature() -> None:
    gateway = DummyBillingGateway("real-secret")
    payload = _payload(event="subscription.activated", subscription_id="sub_1")
    wrong_signature = _sign(payload, "wrong-secret")

    with pytest.raises(BillingWebhookVerificationError):
        gateway.verify_webhook(payload=payload, signature=wrong_signature)


def test_dummy_gateway_rejects_tampered_payload() -> None:
    secret = "test-secret"
    gateway = DummyBillingGateway(secret)
    payload = _payload(event="subscription.activated", subscription_id="sub_1")
    signature = _sign(payload, secret)
    tampered = _payload(event="subscription.activated", subscription_id="sub_999")

    with pytest.raises(BillingWebhookVerificationError):
        gateway.verify_webhook(payload=tampered, signature=signature)


# --- RazorpayBillingGateway (verify_webhook is pure HMAC, no network) ---


def test_razorpay_gateway_verify_webhook_uses_real_hmac_algorithm() -> None:
    """DummyBillingGateway and RazorpayBillingGateway must agree
    byte-for-byte on signature verification -- that's what makes swapping
    to real platform keys a no-op for already-tested webhook logic."""
    secret = "shared-test-secret"
    payload = _payload(event="subscription.charged", subscription_id="sub_1", payment_id="pay_1")
    signature = _sign(payload, secret)

    gateway = RazorpayBillingGateway("rzp_test_fake", "fake-key-secret", secret)
    result = gateway.verify_webhook(payload=payload, signature=signature)

    assert result.provider_subscription_id == "sub_1"
    assert result.event_type == "subscription.charged"


def test_razorpay_gateway_rejects_wrong_signature() -> None:
    gateway = RazorpayBillingGateway("rzp_test_fake", "fake-key-secret", "real-webhook-secret")
    payload = _payload(event="subscription.activated", subscription_id="sub_1")

    with pytest.raises(BillingWebhookVerificationError):
        gateway.verify_webhook(payload=payload, signature=_sign(payload, "wrong-secret"))


def test_razorpay_gateway_create_subscription_calls_sdk_with_plan_id() -> None:
    from unittest.mock import MagicMock

    gateway = RazorpayBillingGateway("rzp_test_fake", "secret", "webhook-secret")
    gateway._client.subscription = MagicMock()
    gateway._client.subscription.create.return_value = {
        "id": "sub_created1",
        "short_url": "https://rzp.io/sub1",
    }

    checkout = gateway.create_subscription(plan=_plan("plan_abc123"), merchant_id=uuid.uuid4())

    assert checkout.provider_subscription_id == "sub_created1"
    assert checkout.checkout_url == "https://rzp.io/sub1"
    call_kwargs = gateway._client.subscription.create.call_args[0][0]
    assert call_kwargs["plan_id"] == "plan_abc123"


# --- gateway_selector -----------------------------------------------------


@pytest.mark.parametrize("key_id", ["rzp_test_abc123", "rzp_live_abc123"])
def test_selector_picks_razorpay_for_real_looking_keys(key_id: str) -> None:
    gateway = get_billing_gateway(key_id, "secret", "webhook-secret")
    assert isinstance(gateway, RazorpayBillingGateway)


@pytest.mark.parametrize("key_id", [None, "", "placeholder", "sk_not_razorpay"])
def test_selector_picks_dummy_for_anything_else(key_id: str | None) -> None:
    gateway = get_billing_gateway(key_id, "secret", "webhook-secret")
    assert isinstance(gateway, DummyBillingGateway)
