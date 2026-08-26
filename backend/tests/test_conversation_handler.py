import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import ItemRepository
from conversation.adapters.whatsapp_client import WhatsAppSender
from conversation.domain.handler import handle_inbound_message
from conversation.domain.intents import Intent
from conversation.domain.webhook_parser import InboundMessage
from customers.adapters.repository import AddressRepository, CustomerRepository
from identity.adapters.repository import MerchantRepository
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from ordering_flow.domain.checkout import CheckoutItem, perform_checkout
from orders.adapters.repository import OrderRepository
from shared.encryption import encrypt
from shared.tenant import TenantContext


class FakeSender(WhatsAppSender):
    def __init__(self, *, flow_send_succeeds: bool = True) -> None:
        self.text_calls: list[dict] = []
        self.button_calls: list[dict] = []
        self.flow_calls: list[dict] = []
        self._flow_send_succeeds = flow_send_succeeds

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


class NoopNotificationChannel:
    async def notify_order_confirmed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return True

    async def notify_order_preparing(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return True

    async def notify_order_ready(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return True

    async def notify_order_completed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        return True


class RecordingNotificationChannel:
    """Records every notify_* call instead of swallowing or actually
    sending it -- lets a test assert exactly one confirmation fired
    (proving the fix for the double-message bug: perform_checkout's
    OrderConfirmedCOD publish is the *only* thing that should confirm a
    COD order, not also an explicit sender.send_text from the handler)."""

    def __init__(self) -> None:
        self.confirmed_calls: list[uuid.UUID] = []

    async def notify_order_confirmed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        self.confirmed_calls.append(order_id)
        return True

    async def notify_order_preparing(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
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
    assert "Test Kitchen" in sender.button_calls[0]["body"]
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
