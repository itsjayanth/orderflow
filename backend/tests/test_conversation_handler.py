import datetime
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from appointments.adapters.repository import AppointmentRepository
from appointments.adapters.scheduling_repository import AppointmentServiceRepository
from catalog.adapters.repository import ItemRepository
from conversation.adapters.whatsapp_client import WhatsAppSender
from conversation.domain.handler import handle_inbound_message
from conversation.domain.intents import Intent
from conversation.domain.webhook_parser import InboundMessage
from customers.adapters.repository import AddressRepository, CustomerRepository
from faq.adapters.repository import FAQItemRepository
from identity.adapters.repository import MerchantRepository, WebsiteLinkClickRepository
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from ordering_flow.domain.checkout import CheckoutItem, perform_checkout
from orders.adapters.repository import OrderRepository
from shared.config import get_settings
from shared.encryption import encrypt
from shared.interaction_mode import reset_cache_for_tests
from shared.tenant import TenantContext


class FakeSender(WhatsAppSender):
    def __init__(
        self, *, flow_send_succeeds: bool = True, cta_url_send_succeeds: bool = True
    ) -> None:
        self.text_calls: list[dict] = []
        self.button_calls: list[dict] = []
        self.flow_calls: list[dict] = []
        self.list_calls: list[dict] = []
        self.cta_url_calls: list[dict] = []
        self._flow_send_succeeds = flow_send_succeeds
        self._cta_url_send_succeeds = cta_url_send_succeeds

    async def send_text(
        self, *, phone_number_id: str, access_token: str, to: str, body: str
    ) -> bool:
        self.text_calls.append({"to": to, "body": body})
        return True

    async def send_buttons(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        body: str,
        buttons: list[tuple[str, str]],
    ) -> bool:
        self.button_calls.append({"to": to, "body": body, "buttons": buttons})
        return True

    async def send_test_message(
        self, *, phone_number_id: str, access_token: str, to: str
    ) -> tuple[bool, str]:
        return True, "ok"

    async def send_flow(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        flow_id: str,
        flow_token: str,
        body: str,
        cta: str,
    ) -> bool:
        self.flow_calls.append(
            {"to": to, "flow_id": flow_id, "flow_token": flow_token, "body": body}
        )
        return self._flow_send_succeeds

    async def send_list(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        body: str,
        button_label: str,
        options: list[tuple[str, str]],
    ) -> bool:
        self.list_calls.append(
            {"to": to, "body": body, "button_label": button_label, "options": options}
        )
        return True

    async def send_cta_url_button(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        body: str,
        display_text: str,
        url: str,
    ) -> bool:
        self.cta_url_calls.append(
            {
                "to": to,
                "body": body,
                "display_text": display_text,
                "url": url,
            }
        )
        return self._cta_url_send_succeeds


class NoopNotificationChannel:
    async def notify_order_confirmed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return True

    async def notify_order_processing(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return True

    async def notify_order_ready(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return True

    async def notify_order_completed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return True

    async def notify_appointment_requested(
        self, *, merchant_id: uuid.UUID, appointment_id: uuid.UUID
    ) -> bool:
        return True

    async def notify_appointment_confirmed(
        self, *, merchant_id: uuid.UUID, appointment_id: uuid.UUID
    ) -> bool:
        return True

    async def notify_appointment_cancelled(
        self, *, merchant_id: uuid.UUID, appointment_id: uuid.UUID
    ) -> bool:
        return True


class RecordingNotificationChannel:
    """Records every notify_* call instead of swallowing or actually
    sending it -- lets a test assert exactly one confirmation fired
    (proving the fix for the double-message bug: perform_checkout's
    OrderConfirmedCOD publish is the *only* thing that should confirm a
    COD order, not also an explicit sender.send_text from the handler;
    same story for perform_booking's AppointmentRequested publish vs. the
    appointment Flow-completion handler's old hand-rolled send)."""

    def __init__(self) -> None:
        self.confirmed_calls: list[uuid.UUID] = []
        self.requested_calls: list[uuid.UUID] = []

    async def notify_order_confirmed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        self.confirmed_calls.append(order_id)
        return True

    async def notify_order_processing(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return True

    async def notify_order_ready(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return True

    async def notify_order_completed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return True

    async def notify_appointment_requested(
        self, *, merchant_id: uuid.UUID, appointment_id: uuid.UUID
    ) -> bool:
        self.requested_calls.append(appointment_id)
        return True

    async def notify_appointment_confirmed(
        self, *, merchant_id: uuid.UUID, appointment_id: uuid.UUID
    ) -> bool:
        return True

    async def notify_appointment_cancelled(
        self, *, merchant_id: uuid.UUID, appointment_id: uuid.UUID
    ) -> bool:
        return True


async def _seed_connected_merchant(
    db_session: AsyncSession,
    phone_number_id: str = "PNID1",
    vertical: str = "restaurant",
    *,
    seed_readiness: bool = True,
):
    """`vertical` is "restaurant", "appointment", or "both" -- maps onto the
    two independent enabled flags (VERTICAL_TOGGLE_PLAN.md). `seed_readiness`
    (default True) also creates a minimal available Item/active
    AppointmentService for whichever vertical(s) are enabled, since
    PLACE_ORDER/BOOK_APPOINTMENT are now gated on readiness as well as the
    enabled flag, not just enabled alone -- pass seed_readiness=False for
    tests specifically exercising the "enabled but not ready" empty-flow
    guard."""
    merchant = await MerchantRepository(db_session).create(
        business_name="Test Business", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    await WhatsAppBusinessAccountRepository(db_session).upsert(
        tenant, phone_number_id=phone_number_id, access_token_encrypted=encrypt("dummy-token")
    )
    # These tests exercise the conversation handler itself, not onboarding
    # progression (that's test_onboarding_flow.py) -- jump the merchant
    # straight to "live" so the handler's onboarding-status guard doesn't
    # reject every inbound message here.
    merchant.onboarding_status = "live"
    merchant.restaurant_enabled = vertical in ("restaurant", "both")
    merchant.appointment_enabled = vertical in ("appointment", "both")
    await db_session.commit()

    if seed_readiness:
        if merchant.restaurant_enabled:
            await ItemRepository(db_session).create(
                tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
            )
        if merchant.appointment_enabled:
            await AppointmentServiceRepository(db_session).create(
                tenant, name="Haircut", duration_minutes=30, price=None
            )
        await db_session.commit()

    return merchant, tenant


def _inbound(
    *, phone_number_id: str = "PNID1", from_phone: str = "919876543210", **kwargs
) -> InboundMessage:
    defaults = {
        "phone_number_id": phone_number_id,
        "whatsapp_message_id": f"wamid.{uuid.uuid4().hex}",
        "from_phone": from_phone,
        "from_name": "Asha",
        "text": None,
        "button_id": None,
    }
    defaults.update(kwargs)
    return InboundMessage(**defaults)


async def test_unknown_phone_number_id_is_skipped(db_session: AsyncSession) -> None:
    sender = FakeSender()
    message = _inbound(phone_number_id="NOT_CONNECTED", text="hi")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.skipped_unknown_number is True
    assert result.reply_sent is False
    assert sender.text_calls == []
    assert sender.button_calls == []


async def test_greeting_sends_intent_menu(db_session: AsyncSession) -> None:
    await _seed_connected_merchant(db_session)
    sender = FakeSender()
    message = _inbound(text="hi")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.GREETING
    assert result.reply_sent is True
    assert len(sender.button_calls) == 1
    assert "Test Business" in sender.button_calls[0]["body"]
    button_ids = {b[0] for b in sender.button_calls[0]["buttons"]}
    assert button_ids == {"place_order", "track_order"}


async def test_greeting_sends_appointment_menu_for_appointment_vertical(
    db_session: AsyncSession,
) -> None:
    """An appointment-only merchant never sees "Place order", and "Talk to
    us" is gone for every vertical."""
    await _seed_connected_merchant(db_session, vertical="appointment")
    sender = FakeSender()
    message = _inbound(text="hi")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.reply_sent is True
    assert len(sender.button_calls) == 1
    assert sender.list_calls == []
    button_ids = {b[0] for b in sender.button_calls[0]["buttons"]}
    assert button_ids == {"book_appointment", "track_appointment"}


async def test_greeting_sends_all_four_options_when_both_verticals_enabled(
    db_session: AsyncSession,
) -> None:
    """VERTICAL_TOGGLE_PLAN.md: additive, not exclusive -- a merchant with
    both verticals enabled (and ready) sees all four options. That's more
    than Meta's 3-button cap, so this tips over into a send_list call
    instead of send_buttons."""
    await _seed_connected_merchant(db_session, vertical="both")
    sender = FakeSender()
    message = _inbound(text="hi")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.reply_sent is True
    assert sender.button_calls == []
    assert len(sender.list_calls) == 1
    option_ids = {o[0] for o in sender.list_calls[0]["options"]}
    assert option_ids == {"place_order", "track_order", "book_appointment", "track_appointment"}


async def test_greeting_omits_enabled_but_not_ready_vertical(db_session: AsyncSession) -> None:
    """The "don't show an empty flow" guard (VERTICAL_TOGGLE_PLAN.md): a
    merchant with appointment_enabled=True but zero active services doesn't
    offer "Book appointment" at all -- same as if it weren't enabled.
    restaurant_enabled=True with an available item still shows PLACE_ORDER,
    proving this is per-vertical, not an all-or-nothing guard."""
    _, tenant = await _seed_connected_merchant(db_session, vertical="both", seed_readiness=False)
    await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    sender = FakeSender()
    message = _inbound(text="hi")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.reply_sent is True
    assert len(sender.button_calls) == 1
    button_ids = {b[0] for b in sender.button_calls[0]["buttons"]}
    assert button_ids == {"place_order", "track_order"}


async def test_greeting_sends_menu_including_faqs_when_merchant_has_an_active_faq(
    db_session: AsyncSession,
) -> None:
    """FAQs are additive and only appear once the merchant has actually set
    something up -- a merchant with zero FAQItems sees the exact 2-button
    menu (previous test), unaffected by this feature ever having been
    built. Now that "Talk to us" is gone, a vertical's 2 base options plus
    FAQs is only 3 total -- still within Meta's 3-button cap, so this stays
    a button message rather than tipping over into a list."""
    _, tenant = await _seed_connected_merchant(db_session)
    await FAQItemRepository(db_session).create(
        tenant,
        question_text="Where are you located?",
        answer_text="12 MG Road.",
        keywords=["where"],
    )
    await db_session.commit()
    sender = FakeSender()
    message = _inbound(text="hi")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.reply_sent is True
    assert sender.list_calls == []
    assert len(sender.button_calls) == 1
    button_ids = {b[0] for b in sender.button_calls[0]["buttons"]}
    assert button_ids == {"place_order", "track_order", "faq_menu"}


async def test_book_appointment_sends_booking_link_for_appointment_vertical(
    db_session: AsyncSession,
) -> None:
    merchant, _ = await _seed_connected_merchant(db_session, vertical="appointment")
    sender = FakeSender()
    message = _inbound(button_id="book_appointment")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.BOOK_APPOINTMENT
    assert len(sender.text_calls) == 1
    assert f"/book/{merchant.merchant_id}" in sender.text_calls[0]["body"]


async def test_book_appointment_falls_back_to_menu_for_restaurant_vertical(
    db_session: AsyncSession,
) -> None:
    """A restaurant-vertical customer typing "book appointment" just sees
    the normal 2-button menu, same as any other unrecognized/unavailable
    request -- BOOK_APPOINTMENT never fires for the wrong vertical."""
    await _seed_connected_merchant(db_session)
    sender = FakeSender()
    message = _inbound(button_id="book_appointment")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.BOOK_APPOINTMENT
    assert sender.text_calls == []
    assert len(sender.button_calls) == 1
    button_ids = {b[0] for b in sender.button_calls[0]["buttons"]}
    assert button_ids == {"place_order", "track_order"}


async def test_place_order_falls_back_to_menu_for_appointment_vertical(
    db_session: AsyncSession,
) -> None:
    """The mirror image of the test above -- PLACE_ORDER never fires for an
    appointment-vertical merchant."""
    await _seed_connected_merchant(db_session, vertical="appointment")
    sender = FakeSender()
    message = _inbound(button_id="place_order")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.PLACE_ORDER
    assert sender.text_calls == []
    assert len(sender.button_calls) == 1
    button_ids = {b[0] for b in sender.button_calls[0]["buttons"]}
    assert button_ids == {"book_appointment", "track_appointment"}


async def test_greeting_creates_customer_record(db_session: AsyncSession) -> None:
    _, tenant = await _seed_connected_merchant(db_session)
    sender = FakeSender()
    message = _inbound(from_phone="919876543210", from_name="Asha", text="hi")

    await handle_inbound_message(db_session, sender, message)

    customer = await CustomerRepository(db_session).find_or_create(tenant, "919876543210")
    assert customer.display_name == "Asha"


async def test_duplicate_message_is_not_reprocessed(db_session: AsyncSession) -> None:
    await _seed_connected_merchant(db_session)
    sender = FakeSender()
    message = _inbound(text="hi")

    first = await handle_inbound_message(db_session, sender, message)
    second = await handle_inbound_message(db_session, sender, message)

    assert first.skipped_duplicate is False
    assert second.skipped_duplicate is True
    assert second.reply_sent is False
    # Only the first call actually sent anything.
    assert len(sender.button_calls) == 1


async def test_place_order_sends_ordering_link(db_session: AsyncSession) -> None:
    merchant, _ = await _seed_connected_merchant(db_session)
    sender = FakeSender()
    message = _inbound(button_id="place_order")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.PLACE_ORDER
    assert len(sender.text_calls) == 1
    assert f"/order/{merchant.merchant_id}" in sender.text_calls[0]["body"]


async def test_place_order_sends_flow_when_flow_configured(db_session: AsyncSession) -> None:
    _, tenant = await _seed_connected_merchant(db_session)
    await WhatsAppBusinessAccountRepository(db_session).set_flow_credentials(
        tenant, flow_id="FLOW_123", private_key_encrypted=encrypt("dummy-pem")
    )
    await db_session.commit()
    sender = FakeSender()
    message = _inbound(button_id="place_order")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.PLACE_ORDER
    assert result.reply_sent is True
    assert len(sender.flow_calls) == 1
    assert sender.flow_calls[0]["flow_id"] == "FLOW_123"
    assert sender.text_calls == []


async def test_place_order_falls_back_to_link_when_flow_send_fails(
    db_session: AsyncSession,
) -> None:
    merchant, tenant = await _seed_connected_merchant(db_session)
    await WhatsAppBusinessAccountRepository(db_session).set_flow_credentials(
        tenant, flow_id="FLOW_123", private_key_encrypted=encrypt("dummy-pem")
    )
    await db_session.commit()
    sender = FakeSender(flow_send_succeeds=False)
    message = _inbound(button_id="place_order")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.reply_sent is True
    assert len(sender.flow_calls) == 1
    assert len(sender.text_calls) == 1
    assert f"/order/{merchant.merchant_id}" in sender.text_calls[0]["body"]


async def test_place_order_uses_browser_link_when_interaction_mode_is_browser_link(
    db_session: AsyncSession,
) -> None:
    """BROWSER_LINK mode overrides a configured Flow entirely -- no Flow
    send happens even though the WABA has whatsapp_flow_id set, matching
    the acceptance criterion that BROWSER_LINK mode never triggers a Flow."""
    merchant, tenant = await _seed_connected_merchant(db_session)
    await WhatsAppBusinessAccountRepository(db_session).set_flow_credentials(
        tenant, flow_id="FLOW_123", private_key_encrypted=encrypt("dummy-pem")
    )
    await db_session.commit()
    settings = get_settings()
    settings.interaction_mode = "BROWSER_LINK"
    reset_cache_for_tests()
    try:
        sender = FakeSender()
        message = _inbound(button_id="place_order")

        result = await handle_inbound_message(db_session, sender, message)
    finally:
        settings.interaction_mode = "WHATSAPP_FLOW"
        reset_cache_for_tests()

    assert result.intent == Intent.PLACE_ORDER
    assert result.reply_sent is True
    assert sender.flow_calls == []
    assert len(sender.cta_url_calls) == 1
    assert sender.cta_url_calls[0]["display_text"] == "Order now"
    assert f"order/{merchant.merchant_id}" in sender.cta_url_calls[0]["url"]
    assert "?wa=" in sender.cta_url_calls[0]["url"]


async def test_track_order_with_no_orders(db_session: AsyncSession) -> None:
    await _seed_connected_merchant(db_session)
    sender = FakeSender()
    message = _inbound(button_id="track_order")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.TRACK_ORDER
    assert "don't have any orders" in sender.text_calls[0]["body"]


async def test_track_order_with_existing_order_shows_status(db_session: AsyncSession) -> None:
    from notifications import wiring

    merchant, tenant = await _seed_connected_merchant(db_session)
    item = await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )

    # perform_checkout publishes OrderConfirmedCOD, which the real
    # notification channel would otherwise try to send over the (dummy,
    # non-functional) WhatsApp credentials seeded above -- swap in a no-op
    # so this test doesn't make a real network call to Meta.
    real_channel = wiring.get_notification_channel()
    wiring.set_notification_channel(NoopNotificationChannel())
    try:
        await perform_checkout(
            db_session,
            tenant,
            customer_whatsapp_number="919876543210",
            items=[CheckoutItem(item_id=item.item_id, quantity=1)],
            payment_method="cod",
        )
    finally:
        wiring.set_notification_channel(real_channel)

    sender = FakeSender()
    message = _inbound(from_phone="919876543210", button_id="track_order")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.TRACK_ORDER
    assert "new" in sender.text_calls[0]["body"]


async def test_track_appointment_with_no_appointments(db_session: AsyncSession) -> None:
    await _seed_connected_merchant(db_session, vertical="appointment")
    sender = FakeSender()
    message = _inbound(button_id="track_appointment")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.TRACK_APPOINTMENT
    assert "don't have any appointments" in sender.text_calls[0]["body"]


async def test_track_appointment_with_existing_appointment_shows_status(
    db_session: AsyncSession,
) -> None:
    _, tenant = await _seed_connected_merchant(db_session, vertical="appointment")
    customer = await CustomerRepository(db_session).find_or_create(tenant, "919876543210")
    await AppointmentRepository(db_session).create(
        tenant,
        customer_id=customer.customer_id,
        name="Asha",
        email="asha@example.com",
        appointment_date=datetime.date(2026, 9, 10),
        start_time=datetime.time(14, 30),
        end_time=datetime.time(15, 0),
    )
    await db_session.commit()

    sender = FakeSender()
    message = _inbound(from_phone="919876543210", button_id="track_appointment")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.TRACK_APPOINTMENT
    assert "requested" in sender.text_calls[0]["body"]
    assert "2026-09-10" in sender.text_calls[0]["body"]


async def test_track_appointment_falls_back_to_menu_for_restaurant_vertical(
    db_session: AsyncSession,
) -> None:
    await _seed_connected_merchant(db_session)
    sender = FakeSender()
    message = _inbound(button_id="track_appointment")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.TRACK_APPOINTMENT
    assert sender.text_calls == []
    assert len(sender.button_calls) == 1
    button_ids = {b[0] for b in sender.button_calls[0]["buttons"]}
    assert button_ids == {"place_order", "track_order"}


async def test_flow_completion_creates_cod_order(db_session: AsyncSession) -> None:
    from notifications import wiring

    _, tenant = await _seed_connected_merchant(db_session)
    item = await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    sender = FakeSender()
    message = _inbound(
        from_phone="919876543210",
        flow_response={
            "selected_items": [str(item.item_id)],
            "order_type": "pickup",
            "payment_method": "cod",
        },
    )

    real_channel = wiring.get_notification_channel()
    recorder = RecordingNotificationChannel()
    wiring.set_notification_channel(recorder)
    try:
        result = await handle_inbound_message(db_session, sender, message)
    finally:
        wiring.set_notification_channel(real_channel)

    assert result.intent == Intent.FLOW_ORDER_COMPLETED
    assert result.reply_sent is True
    # The order-confirmed notification fires exactly once, via
    # perform_checkout's OrderConfirmedCOD event -- not also as an explicit
    # sender.send_text from the handler (that was the double-message bug).
    assert len(recorder.confirmed_calls) == 1
    assert sender.text_calls == []

    orders = await OrderRepository(db_session).list_for_customer(
        tenant,
        (await CustomerRepository(db_session).find_or_create(tenant, "919876543210")).customer_id,
    )
    assert len(orders) == 1
    assert orders[0].payment_method == "cod"
    assert recorder.confirmed_calls == [orders[0].order_id]


async def test_flow_completion_online_payment_includes_payment_link(
    db_session: AsyncSession,
) -> None:
    from notifications import wiring

    _, tenant = await _seed_connected_merchant(db_session)
    item = await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    sender = FakeSender()
    message = _inbound(
        from_phone="919876543210",
        flow_response={
            "selected_items": [str(item.item_id)],
            "order_type": "pickup",
            "payment_method": "online",
        },
    )

    real_channel = wiring.get_notification_channel()
    recorder = RecordingNotificationChannel()
    wiring.set_notification_channel(recorder)
    try:
        result = await handle_inbound_message(db_session, sender, message)
    finally:
        wiring.set_notification_channel(real_channel)

    assert result.reply_sent is True
    assert len(sender.text_calls) == 1
    assert "Complete payment" in sender.text_calls[0]["body"]
    # Unlike COD, no confirmation event fires yet -- perform_checkout
    # doesn't publish one for online orders until payment is actually
    # captured (OrderPaid, elsewhere), so the payment-link text above is
    # the only message, not a duplicate of anything.
    assert recorder.confirmed_calls == []


async def test_flow_completion_with_empty_cart_sends_error_and_creates_no_order(
    db_session: AsyncSession,
) -> None:
    _, tenant = await _seed_connected_merchant(db_session)
    sender = FakeSender()
    message = _inbound(
        from_phone="919876543210",
        flow_response={"selected_items": [], "order_type": "pickup", "payment_method": "cod"},
    )

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.FLOW_ORDER_COMPLETED
    assert "empty" in sender.text_calls[0]["body"].lower()

    orders = await OrderRepository(db_session).list_for_customer(
        tenant,
        (await CustomerRepository(db_session).find_or_create(tenant, "919876543210")).customer_id,
    )
    assert orders == []


async def test_flow_completion_stores_name_and_alternate_contact_phone(
    db_session: AsyncSession,
) -> None:
    from notifications import wiring

    _, tenant = await _seed_connected_merchant(db_session)
    item = await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    sender = FakeSender()
    message = _inbound(
        from_phone="919876543210",
        from_name="WhatsApp Profile Name",
        flow_response={
            "selected_items": [str(item.item_id)],
            "order_type": "pickup",
            "payment_method": "cod",
            "customer_name": "Ravi Kumar",
            "contact_choice": "different",
            "contact_phone": "919999999999",
        },
    )

    real_channel = wiring.get_notification_channel()
    wiring.set_notification_channel(RecordingNotificationChannel())
    try:
        result = await handle_inbound_message(db_session, sender, message)
    finally:
        wiring.set_notification_channel(real_channel)

    assert result.intent == Intent.FLOW_ORDER_COMPLETED

    customer = await CustomerRepository(db_session).find_or_create(tenant, "919876543210")
    # The name typed into the Flow wins over the WhatsApp profile name.
    assert customer.display_name == "Ravi Kumar"
    # Remembered for next time (update_contact_details), not just used for
    # this order.
    assert customer.default_contact_phone == "919999999999"

    orders = await OrderRepository(db_session).list_for_customer(tenant, customer.customer_id)
    assert len(orders) == 1
    assert orders[0].contact_phone == "919999999999"


async def test_flow_completion_delivery_address_choice_same_reuses_saved_address(
    db_session: AsyncSession,
) -> None:
    from notifications import wiring

    _, tenant = await _seed_connected_merchant(db_session)
    item = await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    customer = await CustomerRepository(db_session).find_or_create(tenant, "919876543210")
    address_repo = AddressRepository(db_session)
    saved_address = await address_repo.create(
        tenant,
        customer_id=customer.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
        is_default=True,
    )
    await db_session.commit()

    sender = FakeSender()
    message = _inbound(
        from_phone="919876543210",
        flow_response={
            "selected_items": [str(item.item_id)],
            "order_type": "delivery",
            "payment_method": "cod",
            "customer_name": "Ravi Kumar",
            "contact_choice": "same",
            "address_choice": "same",
        },
    )

    real_channel = wiring.get_notification_channel()
    wiring.set_notification_channel(RecordingNotificationChannel())
    try:
        result = await handle_inbound_message(db_session, sender, message)
    finally:
        wiring.set_notification_channel(real_channel)

    assert result.intent == Intent.FLOW_ORDER_COMPLETED

    orders = await OrderRepository(db_session).list_for_customer(tenant, customer.customer_id)
    assert len(orders) == 1
    # Reused the existing Address row rather than creating a fresh one.
    assert orders[0].delivery_address_id == saved_address.address_id
    # "Use my WhatsApp number" -- no alternate number saved.
    assert orders[0].contact_phone == "919876543210"

    addresses = await address_repo.list_for_customer(tenant, customer.customer_id)
    assert len(addresses) == 1


async def test_flow_completion_delivery_address_choice_new_creates_fresh_address(
    db_session: AsyncSession,
) -> None:
    from notifications import wiring

    _, tenant = await _seed_connected_merchant(db_session)
    item = await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    customer = await CustomerRepository(db_session).find_or_create(tenant, "919876543210")
    address_repo = AddressRepository(db_session)
    await address_repo.create(
        tenant,
        customer_id=customer.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
        is_default=True,
    )
    await db_session.commit()

    sender = FakeSender()
    message = _inbound(
        from_phone="919876543210",
        flow_response={
            "selected_items": [str(item.item_id)],
            "order_type": "delivery",
            "payment_method": "cod",
            "address_choice": "new",
            "address_line1": "45 Residency Road",
            "address_city": "Bengaluru",
            "address_pincode": "560025",
        },
    )

    real_channel = wiring.get_notification_channel()
    wiring.set_notification_channel(RecordingNotificationChannel())
    try:
        result = await handle_inbound_message(db_session, sender, message)
    finally:
        wiring.set_notification_channel(real_channel)

    assert result.intent == Intent.FLOW_ORDER_COMPLETED

    orders = await OrderRepository(db_session).list_for_customer(tenant, customer.customer_id)
    assert len(orders) == 1

    addresses = await address_repo.list_for_customer(tenant, customer.customer_id)
    # The original saved address plus a fresh one for this order.
    assert len(addresses) == 2
    assert orders[0].delivery_address_id in {a.address_id for a in addresses}
    new_address = next(a for a in addresses if a.line1 == "45 Residency Road")
    assert orders[0].delivery_address_id == new_address.address_id


# --- FAQ ---


async def test_unrecognized_text_with_strong_faq_match_sends_answer(
    db_session: AsyncSession,
) -> None:
    _, tenant = await _seed_connected_merchant(db_session)
    await FAQItemRepository(db_session).create(
        tenant,
        question_text="Where are you located?",
        answer_text="We're at 12 MG Road, Bengaluru.",
        keywords=["location", "address", "where"],
    )
    await db_session.commit()

    sender = FakeSender()
    message = _inbound(text="hey what's your location")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.FAQ
    assert result.reply_sent is True
    assert sender.text_calls == [
        {"to": message.from_phone, "body": "We're at 12 MG Road, Bengaluru."}
    ]
    # Not the greeting/intent menu -- a FAQ answer was sent instead.
    assert sender.button_calls == []


async def test_unrecognized_text_with_no_faq_match_falls_back_to_greeting_menu(
    db_session: AsyncSession,
) -> None:
    """Unrecognized free text with zero FAQ matches still falls through to
    the existing greeting/intent-menu behavior, unchanged -- the FAQ
    feature must never make an unmatched message go unanswered."""
    _, tenant = await _seed_connected_merchant(db_session)
    await FAQItemRepository(db_session).create(
        tenant,
        question_text="Where are you located?",
        answer_text="We're at 12 MG Road, Bengaluru.",
        keywords=["location", "address", "where"],
    )
    await db_session.commit()

    sender = FakeSender()
    message = _inbound(text="asdkfjhaskdjf")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.GREETING
    assert result.reply_sent is True
    assert sender.text_calls == []
    # The merchant has an active FAQ (just not one matching this text), so
    # the greeting menu itself includes the "FAQs" option -- still the
    # existing greeting/intent-menu behavior, not a FAQ answer. 3 options
    # total stays within Meta's button cap (see the test above).
    assert sender.list_calls == []
    assert len(sender.button_calls) == 1
    button_ids = {b[0] for b in sender.button_calls[0]["buttons"]}
    assert button_ids == {"place_order", "track_order", "faq_menu"}


async def test_unrecognized_text_with_close_matches_sends_disambiguation_list(
    db_session: AsyncSession,
) -> None:
    _, tenant = await _seed_connected_merchant(db_session)
    faq_repo = FAQItemRepository(db_session)
    delivery = await faq_repo.create(
        tenant,
        question_text="Do you deliver?",
        answer_text="Yes, we deliver within 5km.",
        keywords=["deliver", "delivery", "area"],
    )
    timing = await faq_repo.create(
        tenant,
        question_text="What are your delivery timings?",
        answer_text="We deliver 11am-11pm.",
        keywords=["deliver", "delivery", "timings"],
    )
    await db_session.commit()

    sender = FakeSender()
    message = _inbound(text="what's your delivery area and timings")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.FAQ
    assert result.reply_sent is True
    assert sender.text_calls == []
    assert len(sender.list_calls) == 1
    row_ids = {row[0] for row in sender.list_calls[0]["options"]}
    assert row_ids == {str(delivery.faq_item_id), str(timing.faq_item_id)}


async def test_faq_menu_button_sends_list_of_active_faqs(db_session: AsyncSession) -> None:
    _, tenant = await _seed_connected_merchant(db_session)
    faq_repo = FAQItemRepository(db_session)
    active = await faq_repo.create(
        tenant,
        question_text="Where are you located?",
        answer_text="12 MG Road.",
        keywords=["where"],
    )
    inactive = await faq_repo.create(
        tenant, question_text="Old question?", answer_text="Old answer.", keywords=["old"]
    )
    await faq_repo.update(tenant, inactive.faq_item_id, is_active=False)
    await db_session.commit()

    sender = FakeSender()
    message = _inbound(button_id="faq_menu")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.FAQ_MENU
    assert result.reply_sent is True
    assert len(sender.list_calls) == 1
    row_ids = {row[0] for row in sender.list_calls[0]["options"]}
    assert row_ids == {str(active.faq_item_id)}


async def test_faq_menu_with_no_active_faqs_sends_text_instead_of_empty_list(
    db_session: AsyncSession,
) -> None:
    await _seed_connected_merchant(db_session)
    sender = FakeSender()
    message = _inbound(button_id="faq_menu")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.FAQ_MENU
    assert sender.list_calls == []
    assert "No FAQs" in sender.text_calls[0]["body"]


async def test_tapping_faq_list_row_returns_stored_answer(db_session: AsyncSession) -> None:
    _, tenant = await _seed_connected_merchant(db_session)
    faq_item = await FAQItemRepository(db_session).create(
        tenant,
        question_text="Where are you located?",
        answer_text="We're at 12 MG Road, Bengaluru.",
        keywords=["where"],
    )
    await db_session.commit()

    sender = FakeSender()
    message = _inbound(button_id=str(faq_item.faq_item_id))

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.FAQ
    assert result.reply_sent is True
    assert sender.text_calls == [
        {"to": message.from_phone, "body": "We're at 12 MG Road, Bengaluru."}
    ]


async def test_book_appointment_sends_flow_when_flow_configured(db_session: AsyncSession) -> None:
    merchant, tenant = await _seed_connected_merchant(db_session, vertical="appointment")
    await WhatsAppBusinessAccountRepository(db_session).set_appointment_flow_credentials(
        tenant, flow_id="APPT_FLOW_1", private_key_encrypted=encrypt("dummy-pem")
    )
    await db_session.commit()
    sender = FakeSender()
    message = _inbound(button_id="book_appointment")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.BOOK_APPOINTMENT
    assert result.reply_sent is True
    assert len(sender.flow_calls) == 1
    assert sender.flow_calls[0]["flow_id"] == "APPT_FLOW_1"
    assert sender.text_calls == []


async def test_book_appointment_falls_back_to_link_when_flow_send_fails(
    db_session: AsyncSession,
) -> None:
    merchant, tenant = await _seed_connected_merchant(db_session, vertical="appointment")
    await WhatsAppBusinessAccountRepository(db_session).set_appointment_flow_credentials(
        tenant, flow_id="APPT_FLOW_1", private_key_encrypted=encrypt("dummy-pem")
    )
    await db_session.commit()
    sender = FakeSender(flow_send_succeeds=False)
    message = _inbound(button_id="book_appointment")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.reply_sent is True
    assert len(sender.flow_calls) == 1
    assert len(sender.text_calls) == 1
    assert f"/book/{merchant.merchant_id}" in sender.text_calls[0]["body"]


async def test_book_appointment_uses_browser_link_when_interaction_mode_is_browser_link(
    db_session: AsyncSession,
) -> None:
    """Same override as PLACE_ORDER's browser-link test above, but for
    appointment booking -- a configured Flow is still ignored entirely."""
    merchant, tenant = await _seed_connected_merchant(db_session, vertical="appointment")
    await WhatsAppBusinessAccountRepository(db_session).set_appointment_flow_credentials(
        tenant, flow_id="APPT_FLOW_1", private_key_encrypted=encrypt("dummy-pem")
    )
    await db_session.commit()
    settings = get_settings()
    settings.interaction_mode = "BROWSER_LINK"
    reset_cache_for_tests()
    try:
        sender = FakeSender()
        message = _inbound(button_id="book_appointment")

        result = await handle_inbound_message(db_session, sender, message)
    finally:
        settings.interaction_mode = "WHATSAPP_FLOW"
        reset_cache_for_tests()

    assert result.intent == Intent.BOOK_APPOINTMENT
    assert result.reply_sent is True
    assert sender.flow_calls == []
    assert len(sender.cta_url_calls) == 1
    assert sender.cta_url_calls[0]["display_text"] == "Book now"
    assert f"book/{merchant.merchant_id}" in sender.cta_url_calls[0]["url"]
    assert "?wa=" in sender.cta_url_calls[0]["url"]


async def test_appointment_flow_completion_creates_appointment_not_order(
    db_session: AsyncSession,
) -> None:
    """Also proves the fix for the appointment-Flow double-message bug:
    perform_booking's AppointmentRequested publish is the *only* thing
    that should send a "request received" WhatsApp message here, not also
    an explicit sender.send_text from the handler -- see handler.py's
    _handle_appointment_flow_completion, which used to hand-roll this
    itself. Mirrors test_order_flow_completion_with_selected_items_still_
    creates_order_not_appointment's pattern for the analogous Order case."""
    from notifications import wiring

    merchant, tenant = await _seed_connected_merchant(db_session, vertical="appointment")
    sender = FakeSender()
    message = _inbound(
        from_phone="919876543210",
        flow_response={
            "appointment_date": "2026-09-10",
            "appointment_time": "14:30",
            "customer_name": "Asha",
            "customer_email": "asha@example.com",
            "notes": "Window seat please",
        },
    )

    recorder = RecordingNotificationChannel()
    real_channel = wiring.get_notification_channel()
    wiring.set_notification_channel(recorder)
    try:
        result = await handle_inbound_message(db_session, sender, message)
    finally:
        wiring.set_notification_channel(real_channel)

    assert result.intent == Intent.FLOW_APPOINTMENT_COMPLETED
    assert result.reply_sent is True
    assert sender.text_calls == []
    assert len(recorder.requested_calls) == 1

    customer = await CustomerRepository(db_session).find_or_create(tenant, "919876543210")
    appointments = await AppointmentRepository(db_session).list(
        tenant, customer_id=customer.customer_id
    )
    assert len(appointments) == 1
    assert appointments[0].name == "Asha"
    assert appointments[0].email == "asha@example.com"
    assert appointments[0].notes == "Window seat please"

    orders = await OrderRepository(db_session).list_for_customer(tenant, customer.customer_id)
    assert orders == []


async def test_appointment_flow_completion_past_date_sends_error_and_creates_no_appointment(
    db_session: AsyncSession,
) -> None:
    _, tenant = await _seed_connected_merchant(db_session)
    sender = FakeSender()
    message = _inbound(
        from_phone="919876543210",
        flow_response={
            "appointment_date": "2020-01-01",
            "appointment_time": "09:00",
            "customer_name": "Asha",
            "customer_email": "asha@example.com",
        },
    )

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.FLOW_APPOINTMENT_COMPLETED
    assert "already passed" in sender.text_calls[0]["body"]

    customer = await CustomerRepository(db_session).find_or_create(tenant, "919876543210")
    appointments = await AppointmentRepository(db_session).list(
        tenant, customer_id=customer.customer_id
    )
    assert appointments == []


async def test_appointment_flow_completion_malformed_payload_sends_error(
    db_session: AsyncSession,
) -> None:
    _, tenant = await _seed_connected_merchant(db_session)
    sender = FakeSender()
    message = _inbound(
        from_phone="919876543210",
        flow_response={"appointment_date": "not-a-date", "appointment_time": "09:00"},
    )

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.FLOW_APPOINTMENT_COMPLETED
    assert "didn't go through" in sender.text_calls[0]["body"]

    customer = await CustomerRepository(db_session).find_or_create(tenant, "919876543210")
    appointments = await AppointmentRepository(db_session).list(
        tenant, customer_id=customer.customer_id
    )
    assert appointments == []


async def test_greeting_includes_visit_website_when_website_url_set(
    db_session: AsyncSession,
) -> None:
    merchant, _ = await _seed_connected_merchant(db_session)
    await MerchantRepository(db_session).update_website_url(
        merchant.merchant_id, "https://example.com"
    )
    await db_session.commit()
    sender = FakeSender()
    message = _inbound(text="hi")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.reply_sent is True
    assert len(sender.button_calls) == 1
    button_ids = {b[0] for b in sender.button_calls[0]["buttons"]}
    assert button_ids == {"place_order", "track_order", "visit_website"}


async def test_greeting_omits_visit_website_when_website_url_unset(
    db_session: AsyncSession,
) -> None:
    await _seed_connected_merchant(db_session)
    sender = FakeSender()
    message = _inbound(text="hi")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.reply_sent is True
    assert len(sender.button_calls) == 1
    button_ids = {b[0] for b in sender.button_calls[0]["buttons"]}
    assert button_ids == {"place_order", "track_order"}


async def test_visit_website_sends_cta_button_and_records_click(
    db_session: AsyncSession,
) -> None:
    merchant, _ = await _seed_connected_merchant(db_session)
    await MerchantRepository(db_session).update_website_url(
        merchant.merchant_id, "https://example.com"
    )
    await db_session.commit()
    sender = FakeSender()
    message = _inbound(button_id="visit_website")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.VISIT_WEBSITE
    assert result.reply_sent is True
    assert len(sender.cta_url_calls) == 1
    assert sender.cta_url_calls[0]["url"] == "https://example.com"
    assert sender.text_calls == []
    assert sender.button_calls == []

    since = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=5)
    count = await WebsiteLinkClickRepository(db_session).count_since(merchant.merchant_id, since)
    assert count == 1


async def test_visit_website_falls_back_to_menu_when_website_url_unset(
    db_session: AsyncSession,
) -> None:
    """The re-check inside _reply_for_intent's VISIT_WEBSITE branch guards
    against the link having been cleared between the menu being sent and
    the customer tapping it -- even though classify() maps the button id
    straight to Intent.VISIT_WEBSITE, an unset website_url falls through to
    the normal greeting menu instead of sending a broken CTA button."""
    await _seed_connected_merchant(db_session)
    sender = FakeSender()
    message = _inbound(button_id="visit_website")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.VISIT_WEBSITE
    assert sender.cta_url_calls == []
    assert len(sender.button_calls) == 1
    button_ids = {b[0] for b in sender.button_calls[0]["buttons"]}
    assert button_ids == {"place_order", "track_order"}


async def test_order_flow_completion_with_selected_items_still_creates_order_not_appointment(
    db_session: AsyncSession,
) -> None:
    from notifications import wiring

    _, tenant = await _seed_connected_merchant(db_session)
    item = await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    sender = FakeSender()
    message = _inbound(
        from_phone="919876543210",
        flow_response={
            "selected_items": [str(item.item_id)],
            "order_type": "pickup",
            "payment_method": "cod",
        },
    )

    real_channel = wiring.get_notification_channel()
    wiring.set_notification_channel(RecordingNotificationChannel())
    try:
        result = await handle_inbound_message(db_session, sender, message)
    finally:
        wiring.set_notification_channel(real_channel)

    assert result.intent == Intent.FLOW_ORDER_COMPLETED

    customer = await CustomerRepository(db_session).find_or_create(tenant, "919876543210")
    orders = await OrderRepository(db_session).list_for_customer(tenant, customer.customer_id)
    assert len(orders) == 1

    appointments = await AppointmentRepository(db_session).list(
        tenant, customer_id=customer.customer_id
    )
    assert appointments == []
