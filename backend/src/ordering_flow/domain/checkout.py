import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import MenuItemRepository
from customers.adapters.repository import CustomerRepository
from orders.adapters.repository import OrderItemInput, OrderRepository
from orders.domain.events import OrderConfirmedCOD, publish
from orders.domain.models import Order
from payments.adapters.gateway_selector import (
    REAL_KEY_PREFIXES,
    get_payment_gateway,
    resolve_credentials,
)
from payments.adapters.repository import (
    MerchantPaymentCredentialsRepository,
    PaymentEventRepository,
)
from shared.tenant import TenantContext


class MenuItemNotFoundError(Exception):
    def __init__(self, menu_item_id: uuid.UUID) -> None:
        super().__init__(f"Menu item {menu_item_id} not found")
        self.menu_item_id = menu_item_id


@dataclass(frozen=True, slots=True)
class CheckoutItem:
    menu_item_id: uuid.UUID
    quantity: int


@dataclass(frozen=True, slots=True)
class CheckoutResult:
    order: Order
    payment_link_url: str | None


async def perform_checkout(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    customer_whatsapp_number: str,
    items: list[CheckoutItem],
    payment_method: Literal["online", "cod"],
    order_type: Literal["pickup", "delivery"] = "pickup",
    customer_display_name: str | None = None,
    delivery_address_id: uuid.UUID | None = None,
    whatsapp_conversation_ref: str | None = None,
) -> CheckoutResult:
    """The one place cart -> Order (+ payment link, if online) happens --
    called by both the dashboard's test-checkout shortcut (Phase 5) and
    the customer-facing ordering webview (Phase 6). Neither caller
    duplicates this branching; ARCHITECTURE.md Section 3 calls this
    Ordering Flow UI's job specifically: calls Catalog/Customer/Order/
    Payment Service, doesn't decide validity beyond what's here.
    """
    customer = await CustomerRepository(session).find_or_create(
        tenant, customer_whatsapp_number, display_name=customer_display_name
    )

    menu_repo = MenuItemRepository(session)
    item_inputs: list[OrderItemInput] = []
    for line in items:
        menu_item = await menu_repo.get(tenant, line.menu_item_id)
        if menu_item is None:
            raise MenuItemNotFoundError(line.menu_item_id)
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

    if payment_method == "cod":
        order = await order_repo.create(
            tenant,
            customer_id=customer.customer_id,
            order_type=order_type,
            payment_method="cod",
            payment_status="cod_pending",
            fulfillment_status="new",
            delivery_address_id=delivery_address_id,
            whatsapp_conversation_ref=whatsapp_conversation_ref,
            items=item_inputs,
        )
        await payment_event_repo.create(
            order_id=order.order_id, provider="cod", event_type="cod_selected"
        )
        await session.commit()
        publish(OrderConfirmedCOD(order_id=order.order_id, merchant_id=tenant.merchant_id))
        return CheckoutResult(order=order, payment_link_url=None)

    order = await order_repo.create(
        tenant,
        customer_id=customer.customer_id,
        order_type=order_type,
        payment_method="online",
        payment_status="awaiting_payment",
        delivery_address_id=delivery_address_id,
        whatsapp_conversation_ref=whatsapp_conversation_ref,
        items=item_inputs,
    )

    credentials = await MerchantPaymentCredentialsRepository(session).get(tenant)
    key_id, key_secret = resolve_credentials(credentials, tenant.merchant_id)
    gateway = get_payment_gateway(key_id, key_secret)
    link = gateway.create_link(order_id=order.order_id, amount=order.total, currency=order.currency)

    is_real = key_id is not None and key_id.startswith(REAL_KEY_PREFIXES)
    await payment_event_repo.create(
        order_id=order.order_id,
        provider="razorpay" if is_real else "dummy",
        event_type="link_created",
        provider_order_id=link.provider_order_id,
    )
    await session.commit()

    return CheckoutResult(order=order, payment_link_url=link.url)
