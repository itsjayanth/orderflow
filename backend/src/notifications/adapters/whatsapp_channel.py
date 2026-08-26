import uuid

from conversation.adapters.whatsapp_client import WhatsAppSender
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from notifications.adapters.repository import NotificationTemplateRepository
from notifications.domain.models import DEFAULT_MESSAGES
from notifications.domain.rendering import render_template
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from orders.adapters.repository import OrderRepository
from shared.db import SessionFactory
from shared.encryption import decrypt
from shared.tenant import TenantContext


class WhatsAppNotificationChannel:
    """Each call opens its own session (like shared/scheduler.py's sweep
    job) -- notification handlers run after the triggering request has
    already committed, so there's nothing to share a transaction with."""

    def __init__(self, sender: WhatsAppSender) -> None:
        self._sender = sender

    async def _send(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID, kind: str) -> bool:
        tenant = TenantContext(merchant_id=merchant_id)
        async with SessionFactory() as session:
            waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
            if waba is None or waba.phone_number_id is None or waba.access_token_encrypted is None:
                return False

            order = await OrderRepository(session).get(tenant, order_id)
            if order is None:
                return False

            customer = await CustomerRepository(session).get(tenant, order.customer_id)
            if customer is None:
                return False

            merchant = await MerchantRepository(session).get(tenant.merchant_id)

            items = "\n".join(
                f"{item.quantity}x {item.name_snapshot} - {order.currency} {item.line_total}"
                for item in order.items
            )
            context = {
                "business_name": merchant.business_name if merchant else "",
                "customer_name": customer.display_name or "",
                "order_id": str(order.order_id),
                "order_number": f"{order.order_number:04d}",
                "total": str(order.total),
                "currency": order.currency,
                "items": items,
            }
            template = await NotificationTemplateRepository(session).get(tenant, kind)
            template_body = (
                template.body
                if template is not None and template.is_active
                else DEFAULT_MESSAGES[kind]
            )
            message = render_template(template_body, context)

            return await self._sender.send_text(
                phone_number_id=waba.phone_number_id,
                access_token=decrypt(waba.access_token_encrypted),
                to=customer.whatsapp_number,
                body=message,
            )

    async def notify_order_confirmed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return await self._send(merchant_id=merchant_id, order_id=order_id, kind="order_confirmed")

    async def notify_order_processing(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return await self._send(merchant_id=merchant_id, order_id=order_id, kind="order_processing")

    async def notify_order_ready(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return await self._send(merchant_id=merchant_id, order_id=order_id, kind="order_ready")

    async def notify_order_completed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return await self._send(merchant_id=merchant_id, order_id=order_id, kind="order_completed")
