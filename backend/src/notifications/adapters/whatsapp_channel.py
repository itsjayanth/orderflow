import uuid

from conversation.adapters.whatsapp_client import WhatsAppSender
from customers.adapters.repository import CustomerRepository
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from orders.adapters.repository import OrderRepository
from shared.db import SessionFactory
from shared.encryption import decrypt
from shared.tenant import TenantContext

_ORDER_CONFIRMED_MESSAGE = "Order confirmed! We'll let you know when it's ready."
_ORDER_READY_MESSAGE = "Your order is ready!"
_ORDER_COMPLETED_MESSAGE = "Your order is complete. Enjoy your meal!"


class WhatsAppNotificationChannel:
    """Each call opens its own session (like shared/scheduler.py's sweep
    job) -- notification handlers run after the triggering request has
    already committed, so there's nothing to share a transaction with."""

    def __init__(self, sender: WhatsAppSender) -> None:
        self._sender = sender

    async def _send(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID, message: str) -> bool:
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

            return await self._sender.send_text(
                phone_number_id=waba.phone_number_id,
                access_token=decrypt(waba.access_token_encrypted),
                to=customer.whatsapp_number,
                body=message,
            )

    async def notify_order_confirmed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return await self._send(
            merchant_id=merchant_id, order_id=order_id, message=_ORDER_CONFIRMED_MESSAGE
        )

    async def notify_order_ready(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return await self._send(
            merchant_id=merchant_id, order_id=order_id, message=_ORDER_READY_MESSAGE
        )

    async def notify_order_completed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return await self._send(
            merchant_id=merchant_id, order_id=order_id, message=_ORDER_COMPLETED_MESSAGE
        )
