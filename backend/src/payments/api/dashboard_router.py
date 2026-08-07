from fastapi import APIRouter, HTTPException, status

from ordering_flow.domain.checkout import CheckoutItem, MenuItemNotFoundError, perform_checkout
from payments.adapters.gateway_selector import REAL_KEY_PREFIXES
from payments.adapters.repository import MerchantPaymentCredentialsRepository
from payments.api.schemas import (
    PaymentSettingsOut,
    PaymentSettingsUpdate,
    TestCheckoutRequest,
    TestCheckoutResponse,
)
from shared.deps import CurrentTenant, DbSession
from shared.encryption import encrypt

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


def _is_real_key(key_id: str | None) -> bool:
    return bool(key_id and key_id.startswith(REAL_KEY_PREFIXES))


@router.get("/settings", response_model=PaymentSettingsOut)
async def get_payment_settings(tenant: CurrentTenant, session: DbSession) -> PaymentSettingsOut:
    credentials = await MerchantPaymentCredentialsRepository(session).get(tenant)
    key_id = credentials.razorpay_key_id if credentials else None
    return PaymentSettingsOut(
        razorpay_key_id=key_id,
        razorpay_key_secret_set=bool(credentials and credentials.razorpay_key_secret_encrypted),
        using_real_gateway=_is_real_key(key_id),
    )


@router.put("/settings", response_model=PaymentSettingsOut)
async def update_payment_settings(
    body: PaymentSettingsUpdate, tenant: CurrentTenant, session: DbSession
) -> PaymentSettingsOut:
    credentials = await MerchantPaymentCredentialsRepository(session).upsert(
        tenant,
        razorpay_key_id=body.razorpay_key_id,
        razorpay_key_secret_encrypted=encrypt(body.razorpay_key_secret),
    )
    await session.commit()
    return PaymentSettingsOut(
        razorpay_key_id=credentials.razorpay_key_id,
        razorpay_key_secret_set=True,
        using_real_gateway=_is_real_key(credentials.razorpay_key_id),
    )


@router.post(
    "/test-checkout", response_model=TestCheckoutResponse, status_code=status.HTTP_201_CREATED
)
async def test_checkout(
    body: TestCheckoutRequest, tenant: CurrentTenant, session: DbSession
) -> TestCheckoutResponse:
    """Dashboard-only stand-in for Phase 6's real WhatsApp ordering flow --
    lets staff create a test order (with a real payment link, or COD) so
    the payment/fulfillment loop is exercisable end-to-end. Phase 6 added
    the real customer-facing equivalent (ordering_flow/api/router.py); both
    go through the same ordering_flow.domain.checkout.perform_checkout."""
    try:
        result = await perform_checkout(
            session,
            tenant,
            customer_whatsapp_number=body.customer_whatsapp_number,
            customer_display_name=body.customer_display_name,
            items=[
                CheckoutItem(menu_item_id=line.menu_item_id, quantity=line.quantity)
                for line in body.items
            ],
            payment_method=body.payment_method,
            order_type=body.order_type,
            delivery_address_id=body.delivery_address_id,
        )
    except MenuItemNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    return TestCheckoutResponse(
        order_id=result.order.order_id,
        order_number=result.order.order_number,
        payment_status=result.order.payment_status,
        fulfillment_status=result.order.fulfillment_status,
        total=str(result.order.total),
        payment_link_url=result.payment_link_url,
    )
