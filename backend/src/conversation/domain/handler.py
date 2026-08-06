import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from conversation.adapters.repository import MessageDedupeRepository
from conversation.adapters.whatsapp_client import WhatsAppSender
from conversation.domain.intents import Intent, classify
from conversation.domain.webhook_parser import InboundMessage
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from onboarding.domain.models import WhatsAppBusinessAccount
from orders.adapters.repository import OrderRepository
from orders.domain.models import Order
from shared.config import get_settings
from shared.encryption import decrypt
from shared.tenant import TenantContext

_INTENT_MENU_BUTTONS = [
    (Intent.PLACE_ORDER.value, "Place order"),
    (Intent.TRACK_ORDER.value, "Track order"),
    (Intent.TALK_TO_RESTAURANT.value, "Talk to restaurant"),
]


@dataclass(frozen=True, slots=True)
class HandledMessage:
    """What the handler did, for tests to assert on without re-parsing
    whatever the (best-effort, possibly-failed) WhatsApp send did."""

    intent: Intent
    reply_sent: bool
    skipped_duplicate: bool = False
    skipped_unknown_number: bool = False
    skipped_not_live: bool = False


async def handle_inbound_message(
    session: AsyncSession, sender: WhatsAppSender, message: InboundMessage
) -> HandledMessage:
    waba = await WhatsAppBusinessAccountRepository(session).get_by_phone_number_id(
        message.phone_number_id
    )
    if waba is None:
        # No merchant has connected this phone_number_id -- nothing to do.
        return HandledMessage(
            intent=Intent.GREETING, reply_sent=False, skipped_unknown_number=True
        )

    tenant = TenantContext(merchant_id=waba.merchant_id)

    # ARCHITECTURE.md Section 5: `live` is "the gate the Conversation Handler
    # checks before treating inbound chats as order-capable" -- a merchant
    # mid-onboarding (or one whose account got deactivated) can still have a
    # connected WhatsAppBusinessAccount row without being ready for traffic.
    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    if merchant is None or merchant.onboarding_status != "live":
        return HandledMessage(intent=Intent.GREETING, reply_sent=False, skipped_not_live=True)

    dedupe_repo = MessageDedupeRepository(session)
    newly_recorded = await dedupe_repo.mark_processed(
        message.whatsapp_message_id, tenant.merchant_id
    )
    if not newly_recorded:
        await session.commit()
        return HandledMessage(intent=Intent.GREETING, reply_sent=False, skipped_duplicate=True)

    customer = await CustomerRepository(session).find_or_create(
        tenant, message.from_phone, display_name=message.from_name
    )
    await session.commit()

    intent = classify(text=message.text, button_id=message.button_id)
    reply_sent = await _reply_for_intent(
        session, sender, waba, tenant, message, intent, customer.customer_id
    )

    return HandledMessage(intent=intent, reply_sent=reply_sent)


async def _reply_for_intent(
    session: AsyncSession,
    sender: WhatsAppSender,
    waba: WhatsAppBusinessAccount,
    tenant: TenantContext,
    message: InboundMessage,
    intent: Intent,
    customer_id: uuid.UUID,
) -> bool:
    access_token = decrypt(waba.access_token_encrypted) if waba.access_token_encrypted else ""

    if intent == Intent.PLACE_ORDER:
        order_link = f"{get_settings().frontend_base_url}/order/{tenant.merchant_id}"
        return await sender.send_text(
            phone_number_id=message.phone_number_id,
            access_token=access_token,
            to=message.from_phone,
            body=f"Browse the menu and place your order here: {order_link}",
        )

    if intent == Intent.TRACK_ORDER:
        recent_orders = await OrderRepository(session).list_for_customer(
            tenant, customer_id, limit=1
        )
        return await sender.send_text(
            phone_number_id=message.phone_number_id,
            access_token=access_token,
            to=message.from_phone,
            body=_track_order_reply(recent_orders),
        )

    if intent == Intent.TALK_TO_RESTAURANT:
        return await sender.send_text(
            phone_number_id=message.phone_number_id,
            access_token=access_token,
            to=message.from_phone,
            body="A team member from the restaurant will reach out to you shortly.",
        )

    return await sender.send_buttons(
        phone_number_id=message.phone_number_id,
        access_token=access_token,
        to=message.from_phone,
        body="Welcome! What would you like to do?",
        buttons=_INTENT_MENU_BUTTONS,
    )


def _track_order_reply(recent_orders: list[Order]) -> str:
    if not recent_orders:
        return "You don't have any orders with us yet."
    latest = recent_orders[0]
    status = latest.fulfillment_status or latest.payment_status
    return f"Your most recent order is currently: {status}"
