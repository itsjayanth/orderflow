import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import MenuItemRepository
from conversation.adapters.whatsapp_client import WhatsAppSender
from conversation.domain.handler import handle_inbound_message
from conversation.domain.intents import Intent
from conversation.domain.webhook_parser import InboundMessage
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from ordering_flow.domain.checkout import CheckoutItem, perform_checkout
from shared.encryption import encrypt
from shared.tenant import TenantContext


class FakeSender(WhatsAppSender):
    def __init__(self) -> None:
        self.text_calls: list[dict] = []
        self.button_calls: list[dict] = []

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


class NoopNotificationChannel:
    async def notify_order_confirmed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return True

    async def notify_order_ready(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return True

    async def notify_order_completed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return True


async def _seed_connected_merchant(db_session: AsyncSession, phone_number_id: str = "PNID1"):
    merchant = await MerchantRepository(db_session).create(
        business_name="Test Kitchen", owner_contact=f"{uuid.uuid4()}@example.com"
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
    button_ids = {b[0] for b in sender.button_calls[0]["buttons"]}
    assert button_ids == {"place_order", "track_order", "talk_to_restaurant"}


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


async def test_talk_to_restaurant_sends_fixed_message(db_session: AsyncSession) -> None:
    await _seed_connected_merchant(db_session)
    sender = FakeSender()
    message = _inbound(button_id="talk_to_restaurant")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.TALK_TO_RESTAURANT
    assert "reach out" in sender.text_calls[0]["body"]


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
    menu_item = await MenuItemRepository(db_session).create(
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
            items=[CheckoutItem(menu_item_id=menu_item.menu_item_id, quantity=1)],
            payment_method="cod",
        )
    finally:
        wiring.set_notification_channel(real_channel)

    sender = FakeSender()
    message = _inbound(from_phone="919876543210", button_id="track_order")

    result = await handle_inbound_message(db_session, sender, message)

    assert result.intent == Intent.TRACK_ORDER
    assert "new" in sender.text_calls[0]["body"]
