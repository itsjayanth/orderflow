import uuid

from payments.adapters.dummy_gateway import DummyPaymentGateway
from payments.adapters.razorpay_gateway import RazorpayGateway
from payments.domain.gateway import PaymentGateway
from payments.domain.models import MerchantPaymentCredentials
from shared.config import get_settings
from shared.encryption import decrypt

REAL_KEY_PREFIXES = ("rzp_test_", "rzp_live_")


def resolve_credentials(
    credentials: MerchantPaymentCredentials | None, merchant_id: uuid.UUID
) -> tuple[str | None, str]:
    """key_id is None (dummy gateway) unless real credentials are on file.
    key_secret always resolves to *something* so DummyPaymentGateway's HMAC
    verification has a stable secret to check webhook signatures against
    even before a merchant has visited Settings -- sourced from
    Settings.payments_dummy_gateway_secret (a placeholder, unguessable from
    merchant_id or any other public value), never derived from the merchant
    itself."""
    key_id = credentials.razorpay_key_id if credentials else None
    key_secret = (
        decrypt(credentials.razorpay_key_secret_encrypted)
        if credentials and credentials.razorpay_key_secret_encrypted
        else get_settings().payments_dummy_gateway_secret
    )
    return key_id, key_secret


def get_payment_gateway(key_id: str | None, key_secret: str) -> PaymentGateway:
    """Picks the real Razorpay adapter only for a genuinely-formatted key
    id; everything else (empty, unset, or an obvious placeholder) falls
    back to the dummy gateway. Entering real test-mode keys in Settings is
    the only thing that flips this over -- no redeploy or code change."""
    if key_id is not None and key_id.startswith(REAL_KEY_PREFIXES):
        return RazorpayGateway(key_id, key_secret)
    return DummyPaymentGateway(key_secret)
