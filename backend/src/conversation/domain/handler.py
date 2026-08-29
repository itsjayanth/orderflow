import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from appointment_flow.domain.booking import PastDateError, perform_booking
from catalog.adapters.repository import ItemRepository
from conversation.adapters.repository import MessageDedupeRepository
from conversation.adapters.whatsapp_client import WhatsAppSender
from conversation.domain.intents import Intent, classify
from conversation.domain.webhook_parser import InboundMessage
from customers.adapters.repository import AddressRepository, CustomerRepository
from faq.adapters.repository import FAQItemRepository
from faq.domain.models import FAQItem
from flows.domain.appointment_booking import (
    InvalidAppointmentSubmissionError,
    parse_appointment_flow_completion,
)
from flows.domain.order_builder import (
    NoItemsSelectedError,
    build_new_delivery_address,
    parse_flow_completion,
    resolve_cart,
    resolve_contact_phone,
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

# WhatsApp interactive list messages cap out at 10 rows -- the greeting
# menu, the "browse every FAQ" menu, and the "did you mean" disambiguation
# list all stay under it.
_LIST_MESSAGE_MAX_ROWS = 10
_FAQ_DISAMBIGUATION_MAX_ROWS = 3


async def _menu_options(
    session: AsyncSession, tenant: TenantContext, appointment_booking_enabled: bool
) -> list[tuple[str, str]]:
    """WhatsApp's interactive "button" message type is capped at 3 buttons
    by Meta -- appointment booking (opt-in) or having at least one active
    FAQ (also effectively opt-in -- a merchant who's never added one sees
    nothing new), when present, is what pushes the menu past 3 options,
    which is why the final "show the menu" branch below switches to
    send_list once len(options) > 3. Both stay additive: a merchant using
    neither sees the exact 3-button menu from before either feature
    existed."""
    options = [(Intent.PLACE_ORDER.value, "Place order"), (Intent.TRACK_ORDER.value, "Track order")]
    if appointment_booking_enabled:
        options.append((Intent.BOOK_APPOINTMENT.value, "Book appointment"))
    options.append((Intent.TALK_TO_RESTAURANT.value, "Talk to us"))

    faqs = await FAQItemRepository(session).list(tenant, include_inactive=False)
    if faqs:
        # Folding each FAQ in as its own row -- rather than a single "FAQs"
        # row that opens a *second* list message -- means answering a
        # question is one tap (open the menu, tap the question) instead of
        # two (open the menu, tap "FAQs", open another list, tap the
        # question). _faq_item_for_button below already resolves any row id
        # that's a FAQItem uuid before classify() ever sees it, so tapping
        # one of these rows needs no other wiring. Only falls back to the
        # old single "FAQs" row (leading to _send_faq_menu's own list) once
        # there are more active FAQs than remaining row slots -- WhatsApp
        # list messages cap out at 10 rows total, shared with the fixed
        # options above.
        remaining_rows = _LIST_MESSAGE_MAX_ROWS - len(options)
        if len(faqs) <= remaining_rows:
            options.extend((str(item.faq_item_id), item.question_text) for item in faqs)
        else:
            options.append((Intent.FAQ_MENU.value, "FAQs"))
    return options


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
        # The two Flows' `complete` payloads never share key names by
        # design (see flows/assets/order_flow.json vs
        # flows/assets/appointment_flow.json's Footer payloads) --
        # appointment_date only ever appears on a completed appointment
        # booking, so it's a safe, cheap way to tell which Flow this
        # submission came from without carrying an explicit flow-type
        # marker through the payload.
        if "appointment_date" in message.flow_response:
            appointment_reply_sent = await _handle_appointment_flow_completion(
                session, sender, waba, tenant, message
            )
            return HandledMessage(
                intent=Intent.FLOW_APPOINTMENT_COMPLETED, reply_sent=appointment_reply_sent
            )
        reply_sent = await _handle_flow_completion(session, sender, waba, tenant, message)
        return HandledMessage(intent=Intent.FLOW_ORDER_COMPLETED, reply_sent=reply_sent)

    # A tap on a FAQ list-message row (either the full FAQ_MENU listing or
    # the "did you mean" disambiguation list below) comes back as a
    # button_id, but it's a FAQItem's id, not one of the fixed intent
    # button ids classify() knows about -- resolve it here, before
    # classify(), so it doesn't just fall through to the greeting menu.
    faq_item = await _faq_item_for_button(session, tenant, message.button_id)
    if faq_item is not None:
        reply_sent = await sender.send_text(
            phone_number_id=message.phone_number_id,
            access_token=_access_token(waba),
            to=message.from_phone,
            body=faq_item.answer_text,
        )
        return HandledMessage(intent=Intent.FAQ, reply_sent=reply_sent)

    intent = classify(text=message.text, button_id=message.button_id)

    if intent == Intent.FAQ_MENU:
        reply_sent = await _send_faq_menu(session, sender, waba, tenant, message)
        return HandledMessage(intent=intent, reply_sent=reply_sent)

    # classify() falls back to GREETING both for unrecognized free text and
    # for "no text at all" -- only the former is worth checking against the
    # merchant's FAQs, so this stays narrower than `intent == GREETING`
    # alone (excludes button taps too, since those already had their shot
    # at a specific intent above).
    if intent == Intent.GREETING and message.button_id is None and (message.text or "").strip():
        faq_reply_sent = await _try_faq_text_match(session, sender, waba, tenant, message)
        if faq_reply_sent is not None:
            return HandledMessage(intent=Intent.FAQ, reply_sent=faq_reply_sent)

    reply_sent = await _reply_for_intent(
        session,
        sender,
        waba,
        tenant,
        message,
        intent,
        customer.customer_id,
        merchant.business_name,
        merchant.appointment_booking_enabled,
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
    business_name: str,
    appointment_booking_enabled: bool,
) -> bool:
    access_token = _access_token(waba)

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

    if intent == Intent.BOOK_APPOINTMENT and appointment_booking_enabled:
        if waba.whatsapp_appointment_flow_id:
            # Native in-chat appointment booking (see flows/) -- same
            # dual-path pattern as PLACE_ORDER above: falls back to the
            # webview link below for any merchant who hasn't had the
            # appointment Flow set up yet, or if the send itself fails, so
            # BOOK_APPOINTMENT never silently does nothing.
            sent = await sender.send_flow(
                phone_number_id=message.phone_number_id,
                access_token=access_token,
                to=message.from_phone,
                flow_id=waba.whatsapp_appointment_flow_id,
                flow_token=message.from_phone,
                body="Book your appointment without leaving WhatsApp.",
                cta="Book now",
            )
            if sent:
                return True
            # Flow send failed -- fall through to the link, same rationale
            # as PLACE_ORDER above.

        booking_link = f"{get_settings().frontend_base_url}/book/{tenant.merchant_id}"
        return await sender.send_text(
            phone_number_id=message.phone_number_id,
            access_token=access_token,
            to=message.from_phone,
            body=f"Book your appointment here: {booking_link}",
        )

    if intent == Intent.TALK_TO_RESTAURANT:
        return await sender.send_text(
            phone_number_id=message.phone_number_id,
            access_token=access_token,
            to=message.from_phone,
            body="A team member will reach out to you shortly.",
        )

    # Reaches here for Intent.GREETING, plus Intent.BOOK_APPOINTMENT when
    # the merchant hasn't enabled the feature -- a customer typing "book
    # appointment" for a merchant that never turned it on just sees the
    # normal menu, same as any other unrecognized/unavailable request.
    options = await _menu_options(session, tenant, appointment_booking_enabled)
    body = f"Hi! Welcome to {business_name}. What would you like to do?"
    if len(options) > 3:
        return await sender.send_list(
            phone_number_id=message.phone_number_id,
            access_token=access_token,
            to=message.from_phone,
            body=body,
            button_label="Menu",
            options=options,
        )
    return await sender.send_buttons(
        phone_number_id=message.phone_number_id,
        access_token=access_token,
        to=message.from_phone,
        body=body,
        buttons=options,
    )


def _track_order_reply(recent_orders: list[Order]) -> str:
    if not recent_orders:
        return "You don't have any orders with us yet."
    latest = recent_orders[0]
    status = latest.fulfillment_status or latest.payment_status
    return f"Your most recent order is currently: {status}"


def _access_token(waba: WhatsAppBusinessAccount) -> str:
    return decrypt(waba.access_token_encrypted) if waba.access_token_encrypted else ""


async def _faq_item_for_button(
    session: AsyncSession, tenant: TenantContext, button_id: str | None
) -> FAQItem | None:
    """A FAQ list-message row's id is a FAQItem's own uuid, not one of the
    fixed intent button ids -- an unparseable or unknown id here just means
    "this button tap wasn't a FAQ row", not an error, so both cases return
    None and let the caller fall through to normal intent classification."""
    if button_id is None:
        return None
    try:
        faq_item_id = uuid.UUID(button_id)
    except ValueError:
        return None
    faq_item = await FAQItemRepository(session).get(tenant, faq_item_id)
    if faq_item is None or not faq_item.is_active:
        return None
    return faq_item


async def _send_faq_menu(
    session: AsyncSession,
    sender: WhatsAppSender,
    waba: WhatsAppBusinessAccount,
    tenant: TenantContext,
    message: InboundMessage,
) -> bool:
    items = await FAQItemRepository(session).list(tenant, include_inactive=False)
    access_token = _access_token(waba)
    if not items:
        return await sender.send_text(
            phone_number_id=message.phone_number_id,
            access_token=access_token,
            to=message.from_phone,
            body="No FAQs have been added yet.",
        )
    options = [
        (str(item.faq_item_id), item.question_text) for item in items[:_LIST_MESSAGE_MAX_ROWS]
    ]
    return await sender.send_list(
        phone_number_id=message.phone_number_id,
        access_token=access_token,
        to=message.from_phone,
        body="Here are some frequently asked questions:",
        button_label="View FAQs",
        options=options,
    )


async def _try_faq_text_match(
    session: AsyncSession,
    sender: WhatsAppSender,
    waba: WhatsAppBusinessAccount,
    tenant: TenantContext,
    message: InboundMessage,
) -> bool | None:
    """Returns None (never sent anything) when nothing matched, so the
    caller can fall through to the existing greeting/intent-menu reply
    exactly as it did before this feature existed."""
    assert message.text is not None  # caller already checked
    matches = await FAQItemRepository(session).match(tenant, message.text)
    if not matches:
        return None

    access_token = _access_token(waba)
    if len(matches) == 1:
        return await sender.send_text(
            phone_number_id=message.phone_number_id,
            access_token=access_token,
            to=message.from_phone,
            body=matches[0].answer_text,
        )

    options = [
        (str(item.faq_item_id), item.question_text)
        for item in matches[:_FAQ_DISAMBIGUATION_MAX_ROWS]
    ]
    return await sender.send_list(
        phone_number_id=message.phone_number_id,
        access_token=access_token,
        to=message.from_phone,
        body="Did you mean one of these?",
        button_label="Choose one",
        options=options,
    )


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
    access_token = _access_token(waba)
    assert message.flow_response is not None  # narrows for mypy; caller already checked

    submission = parse_flow_completion(message.flow_response)
    items = await ItemRepository(session).list(tenant, include_unavailable=False)

    try:
        cart = resolve_cart(selected_item_ids=submission.selected_item_ids, items=items)
    except NoItemsSelectedError:
        return await sender.send_text(
            phone_number_id=message.phone_number_id,
            access_token=access_token,
            to=message.from_phone,
            body='That order came through empty -- send "menu" to try again.',
        )

    delivery_address_id: uuid.UUID | None = None
    new_delivery_address = None
    if submission.order_type == "delivery" and submission.address_choice == "same":
        # Customer confirmed reusing their saved address ("Deliver to
        # {address}? Yes") -- reuse the existing Address row as-is via
        # delivery_address_id rather than recreating it through
        # new_delivery_address. Falls back to treating this as a new
        # address if, for whatever reason, there's no saved address to
        # reuse (e.g. it was deleted between the Flow rendering and
        # submission) -- the Flow JSON only ever offers "same" when
        # has_saved_address was true, so this is a defensive fallback, not
        # the expected path.
        existing_customer = await CustomerRepository(session).get_by_whatsapp_number(
            tenant, message.from_phone
        )
        saved_address = None
        if existing_customer is not None:
            saved_address = await AddressRepository(session).get_primary_for_customer(
                tenant, existing_customer.customer_id
            )
        if saved_address is not None:
            delivery_address_id = saved_address.address_id
        else:
            new_delivery_address = build_new_delivery_address(submission)
    else:
        new_delivery_address = build_new_delivery_address(submission)

    result = await perform_checkout(
        session,
        tenant,
        customer_whatsapp_number=message.from_phone,
        items=cart.checkout_items,
        payment_method="cod" if submission.payment_method == "cod" else "online",
        order_type="delivery" if submission.order_type == "delivery" else "pickup",
        customer_display_name=submission.customer_name or message.from_name,
        delivery_address_id=delivery_address_id,
        new_delivery_address=new_delivery_address,
        whatsapp_conversation_ref=message.whatsapp_message_id,
        contact_phone=resolve_contact_phone(submission),
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


async def _handle_appointment_flow_completion(
    session: AsyncSession,
    sender: WhatsAppSender,
    waba: WhatsAppBusinessAccount,
    tenant: TenantContext,
    message: InboundMessage,
) -> bool:
    """The customer tapped "Request appointment" on the appointment Flow's
    single terminal BOOKING screen -- delivered here the same way a
    completed order Flow is (interactive.nfm_reply), never to
    flows/api/router.py's appointment-data-exchange endpoint. Reuses the
    exact same perform_booking the public booking webview calls, so a
    Flow-submitted booking and a web-submitted one become indistinguishable
    the moment they're an Appointment row -- no separate booking-creation
    path to keep in sync."""
    access_token = _access_token(waba)
    assert message.flow_response is not None  # narrows for mypy; caller already checked

    try:
        submission = parse_appointment_flow_completion(message.flow_response)
    except InvalidAppointmentSubmissionError:
        return await sender.send_text(
            phone_number_id=message.phone_number_id,
            access_token=access_token,
            to=message.from_phone,
            body='That booking didn\'t go through -- send "book appointment" to try again.',
        )

    try:
        result = await perform_booking(
            session,
            tenant,
            customer_whatsapp_number=message.from_phone,
            customer_display_name=submission.customer_name or message.from_name,
            name=submission.customer_name or message.from_name or "",
            email=submission.customer_email or "",
            appointment_date=submission.appointment_date,
            appointment_time=submission.appointment_time,
            notes=submission.notes,
            whatsapp_conversation_ref=message.whatsapp_message_id,
        )
    except PastDateError:
        return await sender.send_text(
            phone_number_id=message.phone_number_id,
            access_token=access_token,
            to=message.from_phone,
            body='That date has already passed -- send "book appointment" to pick a new one.',
        )

    # No confirmation event is published here -- matches perform_booking's
    # existing, deliberate "silent on requested" design (only the
    # confirmed/cancelled transitions, set later from the dashboard,
    # notify the customer over WhatsApp per the product spec).
    appointment = result.appointment
    body = (
        f"Appointment #{appointment.appointment_number:04d} requested for "
        f"{appointment.appointment_date.strftime('%a, %d %b')} at "
        f"{appointment.appointment_time.strftime('%I:%M %p').lstrip('0')}!\n\n"
        "We'll message you here once it's confirmed."
    )
    return await sender.send_text(
        phone_number_id=message.phone_number_id,
        access_token=access_token,
        to=message.from_phone,
        body=body,
    )
