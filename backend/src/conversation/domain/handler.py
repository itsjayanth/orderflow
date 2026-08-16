import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import MenuItemRepository
from conversation.adapters.repository import MessageDedupeRepository
from conversation.adapters.whatsapp_client import WhatsAppSender
from conversation.domain.intents import Intent, classify
from conversation.domain.webhook_parser import InboundMessage
from customers.adapters.repository import CustomerRepository
from flows.domain.menu_order import (
    NoItemsSelectedError,
    build_new_delivery_address,
    parse_flow_completion,
    resolve_cart,
)
from identity.adapters.repository import MerchantRepository
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from onboarding.domain.models import WhatsAppBusinessAccount
from ordering_flow.domain.checkout import perform_checkout
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
        return HandledMessage(intent=Intent.GREETING, reply_sent=False, skipped_unknown_number=True)

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

    if message.flow_response is not None:
        reply_sent = await _handle_flow_completion(session, sender, waba, tenant, message)
        return HandledMessage(intent=Intent.FLOW_ORDER_COMPLETED, reply_sent=reply_sent)

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
        if waba.whatsapp_flow_id:
            # Native in-chat ordering (see flows/) -- set once per merchant
            # by scripts/setup_whatsapp_flow.py. Falls back to the webview
            # link below for any merchant who hasn't had that run yet, so
            # PLACE_ORDER never silently does nothing.
            #
            # flow_token carries the customer's own WhatsApp number rather
            # than an opaque id -- flows/api/router.py has no other way to
            # know *who* is filling out the Flow (the encrypted request
            # body doesn't include it), and it's what lets the DETAILS
            # screen prefill a returning customer's saved address.
            sent = await sender.send_flow(
                phone_number_id=message.phone_number_id,
                access_token=access_token,
                to=message.from_phone,
                flow_id=waba.whatsapp_flow_id,
                flow_token=message.from_phone,
                body="Browse the menu and place your order without leaving WhatsApp.",
                cta="Order now",
            )
            if sent:
                return True
            # Flow send failed (e.g. Flow got unpublished) -- fall through
            # to the link rather than leaving the customer with no reply.

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


async def _handle_flow_completion(
    session: AsyncSession,
    sender: WhatsAppSender,
    waba: WhatsAppBusinessAccount,
    tenant: TenantContext,
    message: InboundMessage,
) -> bool:
    """The customer tapped "Place order" on the Flow's terminal PAYMENT
    screen -- WhatsApp delivers the `complete` action's payload here as a
    regular message (interactive.nfm_reply), not to flows/api/router.py's
    data-exchange endpoint (that endpoint only ever sees INIT/data_exchange/
    ping, never the final submission). Reuses the exact same
    perform_checkout the public ordering webview calls, so a Flow order and
    a webview order become indistinguishable the moment they're an Order
    row -- no separate order-creation path to keep in sync."""
    access_token = decrypt(waba.access_token_encrypted) if waba.access_token_encrypted else ""
    assert message.flow_response is not None  # narrows for mypy; caller already checked

    submission = parse_flow_completion(message.flow_response)
    menu_items = await MenuItemRepository(session).list(tenant, include_unavailable=False)

    try:
        cart = resolve_cart(selected_item_ids=submission.selected_item_ids, menu_items=menu_items)
    except NoItemsSelectedError:
        return await sender.send_text(
            phone_number_id=message.phone_number_id,
            access_token=access_token,
            to=message.from_phone,
            body='That order came through empty -- send "menu" to try again.',
        )

    result = await perform_checkout(
        session,
        tenant,
        customer_whatsapp_number=message.from_phone,
        items=cart.checkout_items,
        payment_method="cod" if submission.payment_method == "cod" else "online",
        order_type="delivery" if submission.order_type == "delivery" else "pickup",
        customer_display_name=message.from_name,
        new_delivery_address=build_new_delivery_address(submission),
        whatsapp_conversation_ref=message.whatsapp_message_id,
    )

    if result.payment_link_url is None:
        # COD: perform_checkout already published OrderConfirmedCOD, which
        # notifications/wiring.py turns into the merchant's own configured
        # "order_confirmed" template (or the built-in default) over the
        # same channel every other lifecycle notification uses. Sending our
        # own confirmation text here duplicated it -- the event-driven one
        # is the single source of truth for "order confirmed" wording.
        return True

    # Online payment: perform_checkout deliberately does *not* publish a
    # confirmation event yet (payment isn't captured), so there's nothing
    # else telling the customer how to pay -- this is a distinct "here's
    # your payment link" prompt, not a duplicate. The real "order
    # confirmed" notification fires later via OrderPaid once payment
    # succeeds, through that same shared channel.
    body = (
        f"Order #{result.order.order_number} received!\n\n{cart.summary_text}"
        f"\n\nComplete payment: {result.payment_link_url}"
    )
    return await sender.send_text(
        phone_number_id=message.phone_number_id,
        access_token=access_token,
        to=message.from_phone,
        body=body,
    )
