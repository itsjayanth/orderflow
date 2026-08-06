from fastapi import APIRouter, HTTPException, status

from catalog.adapters.repository import MenuItemRepository
from customers.adapters.repository import CustomerRepository
from orders.adapters.repository import OrderItemInput, OrderRepository
from orders.domain.events import OrderConfirmedCOD, publish
from payments.adapters.gateway_selector import (
    REAL_KEY_PREFIXES,
    get_payment_gateway,
    resolve_credentials,
)
from payments.adapters.repository import (
    MerchantPaymentCredentialsRepository,
    PaymentEventRepository,
)
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
    the payment/fulfillment loop is exercisable end-to-end before the
    WhatsApp Conversation Handler exists."""
    customer = await CustomerRepository(session).find_or_create(
        tenant, body.customer_whatsapp_number, display_name=body.customer_display_name
    )

    menu_repo = MenuItemRepository(session)
    item_inputs: list[OrderItemInput] = []
    for line in body.items:
        menu_item = await menu_repo.get(tenant, line.menu_item_id)
        if menu_item is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Menu item {line.menu_item_id} not found"
            )
        item_inputs.append(
            OrderItemInput(
                menu_item_id=menu_item.menu_item_id,
                name_snapshot=menu_item.name,
                price_snapshot=menu_item.price,
                quantity=line.quantity,
            )
        )

    order_repo = OrderRepository(session)
    payment_event_repo = PaymentEventRepository(session)

    if body.payment_method == "cod":
        order = await order_repo.create(
            tenant,
            customer_id=customer.customer_id,
            order_type=body.order_type,
            payment_method="cod",
            payment_status="cod_pending",
            fulfillment_status="new",
            delivery_address_id=body.delivery_address_id,
            items=item_inputs,
        )
        await payment_event_repo.create(
            order_id=order.order_id, provider="cod", event_type="cod_selected"
        )
        await session.commit()
        publish(OrderConfirmedCOD(order_id=order.order_id, merchant_id=tenant.merchant_id))
        return TestCheckoutResponse(
            order_id=order.order_id,
            payment_status=order.payment_status,
            fulfillment_status=order.fulfillment_status,
            total=str(order.total),
            payment_link_url=None,
        )

    order = await order_repo.create(
        tenant,
        customer_id=customer.customer_id,
        order_type=body.order_type,
        payment_method="online",
        payment_status="awaiting_payment",
        delivery_address_id=body.delivery_address_id,
        items=item_inputs,
    )

    credentials = await MerchantPaymentCredentialsRepository(session).get(tenant)
    key_id, key_secret = resolve_credentials(credentials, tenant.merchant_id)
    gateway = get_payment_gateway(key_id, key_secret)
    link = gateway.create_link(order_id=order.order_id, amount=order.total, currency=order.currency)

    await payment_event_repo.create(
        order_id=order.order_id,
        provider="razorpay" if _is_real_key(key_id) else "dummy",
        event_type="link_created",
        provider_order_id=link.provider_order_id,
    )
    await session.commit()

    return TestCheckoutResponse(
        order_id=order.order_id,
        payment_status=order.payment_status,
        fulfillment_status=order.fulfillment_status,
        total=str(order.total),
        payment_link_url=link.url,
    )
