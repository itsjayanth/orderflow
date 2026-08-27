import datetime
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from appointments.adapters.repository import AppointmentRepository
from appointments.domain.events import AppointmentCancelled, AppointmentConfirmed, publish
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from notifications import wiring
from notifications.adapters.repository import NotificationTemplateRepository
from notifications.adapters.whatsapp_channel import WhatsAppNotificationChannel
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
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
        self.cancelled: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def notify_appointment_confirmed(
        self, *, merchant_id: uuid.UUID, appointment_id: uuid.UUID
    ) -> bool:
        self.confirmed.append((merchant_id, appointment_id))
        return True

    async def notify_appointment_cancelled(
        self, *, merchant_id: uuid.UUID, appointment_id: uuid.UUID
    ) -> bool:
        self.cancelled.append((merchant_id, appointment_id))
        return True


async def _seed_appointment(db_session: AsyncSession, *, connect_whatsapp: bool = True):
    merchant = await MerchantRepository(db_session).create(
        business_name="Test Kitchen", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    tenant = TenantContext(merchant_id=merchant.merchant_id)

    if connect_whatsapp:
        await WhatsAppBusinessAccountRepository(db_session).upsert(
            tenant, phone_number_id="PNID1", access_token_encrypted=encrypt("dummy-token")
        )

    customer = await CustomerRepository(db_session).find_or_create(
        tenant, "919876543210", display_name="Asha"
    )
    appointment = await AppointmentRepository(db_session).create(
        tenant,
        customer_id=customer.customer_id,
        name="Asha Rao",
        email="asha@example.com",
        appointment_date=datetime.date(2026, 9, 1),
        appointment_time=datetime.time(18, 0),
    )
    await db_session.commit()
    return tenant, appointment


# --- WhatsAppNotificationChannel: appointment kinds -------------------------


async def test_notify_appointment_confirmed_sends_expected_message(
    db_session: AsyncSession,
) -> None:
    tenant, appointment = await _seed_appointment(db_session)
    sender = FakeSender()
    channel = WhatsAppNotificationChannel(sender)

    result = await channel.notify_appointment_confirmed(
        merchant_id=tenant.merchant_id, appointment_id=appointment.appointment_id
    )

    assert result is True
    assert len(sender.calls) == 1
    assert sender.calls[0]["to"] == "919876543210"
    assert "confirmed" in sender.calls[0]["body"].lower()
    assert "2026-09-01" in sender.calls[0]["body"]
    assert "18:00:00" in sender.calls[0]["body"]


async def test_notify_appointment_cancelled_sends_expected_message(
    db_session: AsyncSession,
) -> None:
    tenant, appointment = await _seed_appointment(db_session)
    sender = FakeSender()
    channel = WhatsAppNotificationChannel(sender)

    result = await channel.notify_appointment_cancelled(
        merchant_id=tenant.merchant_id, appointment_id=appointment.appointment_id
    )

    assert result is True
    assert "cancelled" in sender.calls[0]["body"].lower()


async def test_notify_appointment_returns_false_when_whatsapp_not_connected(
    db_session: AsyncSession,
) -> None:
    tenant, appointment = await _seed_appointment(db_session, connect_whatsapp=False)
    sender = FakeSender()
    channel = WhatsAppNotificationChannel(sender)

    result = await channel.notify_appointment_confirmed(
        merchant_id=tenant.merchant_id, appointment_id=appointment.appointment_id
    )

    assert result is False
    assert sender.calls == []


async def test_notify_appointment_returns_false_for_unknown_appointment(
    db_session: AsyncSession,
) -> None:
    tenant, _ = await _seed_appointment(db_session)
    sender = FakeSender()
    channel = WhatsAppNotificationChannel(sender)

    result = await channel.notify_appointment_confirmed(
        merchant_id=tenant.merchant_id, appointment_id=uuid.uuid4()
    )

    assert result is False
    assert sender.calls == []


# --- template override -----------------------------------------------------


async def test_notify_appointment_confirmed_uses_active_template_when_configured(
    db_session: AsyncSession,
) -> None:
    tenant, appointment = await _seed_appointment(db_session)
    await NotificationTemplateRepository(db_session).upsert(
        tenant,
        "appointment_confirmed",
        template_name="appointment_confirmed_v1",
        language_code="en",
        body="Hi {{customer_name}}, see you on {{appointment_date}} at {{appointment_time}}!",
        is_active=True,
    )
    await db_session.commit()
    sender = FakeSender()
    channel = WhatsAppNotificationChannel(sender)

    await channel.notify_appointment_confirmed(
        merchant_id=tenant.merchant_id, appointment_id=appointment.appointment_id
    )

    assert sender.calls[0]["body"] == "Hi Asha, see you on 2026-09-01 at 18:00:00!"


async def test_notify_appointment_cancelled_falls_back_to_default_when_template_inactive(
    db_session: AsyncSession,
) -> None:
    tenant, appointment = await _seed_appointment(db_session)
    await NotificationTemplateRepository(db_session).upsert(
        tenant,
        "appointment_cancelled",
        template_name="cancel_v1",
        language_code="en",
        body="This should not be sent.",
        is_active=False,
    )
    await db_session.commit()
    sender = FakeSender()
    channel = WhatsAppNotificationChannel(sender)

    await channel.notify_appointment_cancelled(
        merchant_id=tenant.merchant_id, appointment_id=appointment.appointment_id
    )

    assert sender.calls[0]["body"] != "This should not be sent."
    assert "cancelled" in sender.calls[0]["body"].lower()


# --- event wiring ------------------------------------------------------


async def test_appointment_confirmed_event_routes_to_confirmed_notification() -> None:
    real_channel = wiring.get_notification_channel()
    recording = RecordingChannel()
    wiring.set_notification_channel(recording)
    try:
        merchant_id, appointment_id = uuid.uuid4(), uuid.uuid4()
        await publish(AppointmentConfirmed(appointment_id=appointment_id, merchant_id=merchant_id))
    finally:
        wiring.set_notification_channel(real_channel)

    assert recording.confirmed == [(merchant_id, appointment_id)]
    assert recording.cancelled == []


async def test_appointment_cancelled_event_routes_to_cancelled_notification() -> None:
    real_channel = wiring.get_notification_channel()
    recording = RecordingChannel()
    wiring.set_notification_channel(recording)
    try:
        merchant_id, appointment_id = uuid.uuid4(), uuid.uuid4()
        await publish(AppointmentCancelled(appointment_id=appointment_id, merchant_id=merchant_id))
    finally:
        wiring.set_notification_channel(real_channel)

    assert recording.cancelled == [(merchant_id, appointment_id)]
    assert recording.confirmed == []


# --- templates API lists the new kinds --------------------------------


async def test_templates_list_includes_appointment_kinds(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "business_name": "Test Kitchen",
            "owner_name": "Jane Owner",
            "owner_contact": "owner@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert response.status_code == 201, response.text
    tokens = response.json()

    list_response = await client.get(
        "/api/v1/notifications/templates",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert list_response.status_code == 200
    kinds = {t["notification_kind"] for t in list_response.json()}
    assert {"appointment_confirmed", "appointment_cancelled"} <= kinds
