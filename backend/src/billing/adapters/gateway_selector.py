from billing.adapters.dummy_gateway import DummyBillingGateway
from billing.adapters.razorpay_gateway import RazorpayBillingGateway
from billing.domain.gateway import BillingGateway

# Same prefixes payments/adapters/gateway_selector.py checks -- Razorpay's
# own key_id format, not something specific to Subscriptions.
REAL_KEY_PREFIXES = ("rzp_test_", "rzp_live_")


def get_billing_gateway(
    key_id: str | None, key_secret: str, webhook_secret: str
) -> BillingGateway:
    """Picks the real Razorpay adapter only for a genuinely-formatted
    platform key id; everything else (unset, empty, or an obvious
    placeholder) falls back to the dummy gateway. There's no per-merchant
    credential row here (unlike payments/) -- the caller resolves
    key_id/key_secret/webhook_secret straight from Settings (shared/
    config.py's platform_razorpay_key_id/_key_secret/_webhook_secret)."""
    if key_id is not None and key_id.startswith(REAL_KEY_PREFIXES):
        return RazorpayBillingGateway(key_id, key_secret, webhook_secret)
    return DummyBillingGateway(webhook_secret)
