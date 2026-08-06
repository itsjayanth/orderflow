import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import MenuItemRepository
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from notifications import wiring
from notifications.adapters.whatsapp_channel import WhatsAppNotificationChannel
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from orders.adapters.repository import OrderItemInput, OrderRepository
from orders.domain.events import (
    OrderCompleted,
    OrderConfirmedCOD,
    OrderPaid,
    OrderReady,
    publish,
)
from shared.encryption import encrypt
from shared.tenant import TenantContext


class FakeSender:
    def __init__(self, *, succeed: bool = True) -> None:
        self.succeed = succeed
        self.calls: list[dict] = []

    async def send_text(
        self, *, phone_number_id: str, access_token: str, to: str, body: str
    ) -> bool:
        self.calls.append(
            {
                "phone_number_id": phone_number_id,
                "access_token": access_token,
                "to": to,
                "body": body,
            }
        )
        return self.succeed

    async def send_buttons(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        body: str,
        buttons: list[tuple[str, str]],
    ) -> bool:
        raise NotImplementedError


class RecordingChannel:
    def __init__(self) -> None:
        self.confirmed: list[tuple[uuid.UUID, uuid.UUID]] = []
        self.ready: list[tuple[uuid.UUID, uuid.UUID]] = []
        self.completed: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def notify_order_confirmed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        self.confirmed.append((merchant_id, order_id))
        return True

    async def notify_order_ready(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        self.ready.append((merchant_id, order_id))
        return True

    async def notify_order_completed(self, *, merchant_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        self.completed.append((merchant_id, order_id))
        return True


async def _seed_order(db_session: AsyncSession, *, connect_whatsapp: bool = True):
    merchant = await MerchantRepository(db_session).create(
        business_name="Test Kitchen", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    tenant = TenantContext(merchant_id=merchant.merchant_id)

    if connect_whatsapp:
        await WhatsAppBusinessAccountRepository(db_session).upsert(
            tenant, phone_number_id="PNID1", access_token_encrypted=encrypt("dummy-token")
        )

    customer = await CustomerRepository(db_session).find_or_create(tenant, "919876543210")
    menu_item = await MenuItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    order = await OrderRepository(db_session).create(
        tenant,
        customer_id=customer.customer_id,
        order_type="pickup",
        payment_method="cod",
        payment_status="pending",
        fulfillment_status="new",
        items=[
            OrderItemInput(
                menu_item_id=menu_item.menu_item_id,
                name_snapshot=menu_item.name,
                price_snapshot=menu_item.price,
                quantity=1,
            )
        ],
    )
    await db_session.commit()
    return tenant, order


async def test_notify_order_confirmed_sends_expected_message(db_session: AsyncSession) -> None:
    tenant, order = await _seed_order(db_session)
    sender = FakeSender()
    channel = WhatsAppNotificationChannel(sender)

    result = await channel.notify_order_confirmed(
        merchant_id=tenant.merchant_id, order_id=order.order_id
    )

    assert result is True
    assert len(sender.calls) == 1
    assert sender.calls[0]["to"] == "919876543210"
    assert sender.calls[0]["phone_number_id"] == "PNID1"
    assert sender.calls[0]["access_token"] == "dummy-token"
    assert "confirmed" in sender.calls[0]["body"].lower()


async def test_notify_order_ready_sends_expected_message(db_session: AsyncSession) -> None:
    tenant, order = await _seed_order(db_session)
    sender = FakeSender()
    channel = WhatsAppNotificationChannel(sender)

    await channel.notify_order_ready(merchant_id=tenant.merchant_id, order_id=order.order_id)

    assert "ready" in sender.calls[0]["body"].lower()


async def test_notify_order_completed_sends_expected_message(db_session: AsyncSession) -> None:
    tenant, order = await _seed_order(db_session)
    sender = FakeSender()
    channel = WhatsAppNotificationChannel(sender)

    await channel.notify_order_completed(merchant_id=tenant.merchant_id, order_id=order.order_id)

    assert "complete" in sender.calls[0]["body"].lower()


async def test_notify_returns_false_when_whatsapp_not_connected(db_session: AsyncSession) -> None:
    tenant, order = await _seed_order(db_session, connect_whatsapp=False)
    sender = FakeSender()
    channel = WhatsAppNotificationChannel(sender)

    result = await channel.notify_order_confirmed(
        merchant_id=tenant.merchant_id, order_id=order.order_id
    )

    assert result is False
    assert sender.calls == []


async def test_notify_returns_false_for_unknown_order(db_session: AsyncSession) -> None:
    tenant, _ = await _seed_order(db_session)
    sender = FakeSender()
    channel = WhatsAppNotificationChannel(sender)

    result = await channel.notify_order_confirmed(
        merchant_id=tenant.merchant_id, order_id=uuid.uuid4()
    )

    assert result is False
    assert sender.calls == []


async def test_notify_propagates_sender_failure(db_session: AsyncSession) -> None:
    tenant, order = await _seed_order(db_session)
    sender = FakeSender(succeed=False)
    channel = WhatsAppNotificationChannel(sender)

    result = await channel.notify_order_confirmed(
        merchant_id=tenant.merchant_id, order_id=order.order_id
    )

    assert result is False
    assert len(sender.calls) == 1


async def test_register_notification_handlers_is_idempotent() -> None:
    # register_notification_handlers already ran once at app import time
    # (app.py, module level). Calling it again here must not double-subscribe,
    # or a single published event would fire the recording channel twice.
    wiring.register_notification_handlers()
    wiring.register_notification_handlers()

    real_channel = wiring.get_notification_channel()
    recording = RecordingChannel()
    wiring.set_notification_channel(recording)
    try:
        await publish(OrderPaid(order_id=uuid.uuid4(), merchant_id=uuid.uuid4()))
    finally:
        wiring.set_notification_channel(real_channel)

    assert len(recording.confirmed) == 1


async def test_order_paid_and_confirmed_cod_both_route_to_confirmed_notification() -> None:
    real_channel = wiring.get_notification_channel()
    recording = RecordingChannel()
    wiring.set_notification_channel(recording)
    try:
        merchant_id, order_id = uuid.uuid4(), uuid.uuid4()
        await publish(OrderPaid(order_id=order_id, merchant_id=merchant_id))
        await publish(OrderConfirmedCOD(order_id=order_id, merchant_id=merchant_id))
    finally:
        wiring.set_notification_channel(real_channel)

    assert recording.confirmed == [(merchant_id, order_id), (merchant_id, order_id)]


async def test_order_ready_routes_to_ready_notification() -> None:
    real_channel = wiring.get_notification_channel()
    recording = RecordingChannel()
    wiring.set_notification_channel(recording)
    try:
        merchant_id, order_id = uuid.uuid4(), uuid.uuid4()
        await publish(OrderReady(order_id=order_id, merchant_id=merchant_id))
    finally:
        wiring.set_notification_channel(real_channel)

    assert recording.ready == [(merchant_id, order_id)]
    assert recording.confirmed == []
    assert recording.completed == []


async def test_order_completed_routes_to_completed_notification() -> None:
    real_channel = wiring.get_notification_channel()
    recording = RecordingChannel()
    wiring.set_notification_channel(recording)
    try:
        merchant_id, order_id = uuid.uuid4(), uuid.uuid4()
        await publish(OrderCompleted(order_id=order_id, merchant_id=merchant_id))
    finally:
        wiring.set_notification_channel(real_channel)

    assert recording.completed == [(merchant_id, order_id)]
    assert recording.confirmed == []
    assert recording.ready == []
