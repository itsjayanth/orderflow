import datetime
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

import shared.scheduler as scheduler_module
from appointments.adapters.repository import AppointmentRepository
from catalog.adapters.repository import ItemRepository
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from orders.adapters.repository import OrderItemInput, OrderRepository
from shared.config import get_settings
from shared.encryption import encrypt
from shared.scheduler import send_due_appointment_reminders, sweep_abandoned_orders
from shared.tenant import TenantContext


async def _make_tenant(db_session: AsyncSession) -> TenantContext:
    merchant = await MerchantRepository(db_session).create(
        business_name="Sweep Business", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    return TenantContext(merchant_id=merchant.merchant_id)


async def test_sweep_cancels_abandoned_orders_but_not_recent_ones(
    db_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(db_session)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    item = await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    order_repo = OrderRepository(db_session)

    def _items() -> list[OrderItemInput]:
        return [
            OrderItemInput(
                item_id=item.item_id,
                name_snapshot=item.name,
                price_snapshot=item.price,
                quantity=1,
            )
        ]

    stale_order = await order_repo.create(
        tenant,
        customer_id=customer.customer_id,
        order_type="pickup",
        payment_method="online",
        payment_status="awaiting_payment",
        items=_items(),
    )
    recent_order = await order_repo.create(
        tenant,
        customer_id=customer.customer_id,
        order_type="pickup",
        payment_method="online",
        payment_status="awaiting_payment",
        items=_items(),
    )
    # Backdate only the stale order's placed_at directly (bypassing the
    # domain layer, which has no reason to ever set this after creation).
    stale_order.placed_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=2)
    await db_session.commit()

    await sweep_abandoned_orders()

    await db_session.refresh(stale_order)
    await db_session.refresh(recent_order)
    assert stale_order.payment_status == "cancelled"
    assert stale_order.fulfillment_status == "cancelled"
    assert recent_order.payment_status == "awaiting_payment"


class FakeReminderSender:
    """Only implements what WhatsAppNotificationChannel.notify_appointment_reminder
    actually calls -- send_due_appointment_reminders only ever reaches
    send_template_message, never any other WhatsAppSender method."""

    def __init__(self, *, succeed: bool = True) -> None:
        self.succeed = succeed
        self.calls: list[dict] = []

    async def send_template_message(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        template_name: str,
        language_code: str,
        body_params: list[str],
    ) -> bool:
        self.calls.append(
            {
                "to": to,
                "template_name": template_name,
                "language_code": language_code,
                "body_params": body_params,
            }
        )
        return self.succeed


async def _seed_confirmed_appointment(
    db_session: AsyncSession, *, appointment_date: datetime.date, start_time: datetime.time
):
    merchant = await MerchantRepository(db_session).create(
        business_name="Reminder Business", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    await MerchantRepository(db_session).set_vertical_flags(
        merchant.merchant_id, restaurant_enabled=False, appointment_enabled=True
    )
    tenant = TenantContext(merchant_id=merchant.merchant_id)
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
        appointment_date=appointment_date,
        start_time=start_time,
        end_time=(
            datetime.datetime.combine(appointment_date, start_time) + datetime.timedelta(minutes=30)
        ).time(),
    )
    await AppointmentRepository(db_session).transition_status(
        tenant, appointment.appointment_id, "confirmed", changed_by="staff-1"
    )
    await db_session.commit()
    return merchant, appointment


async def test_reminder_scan_noops_when_no_template_configured(
    db_session: AsyncSession, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "whatsapp_appointment_reminder_template_name", None)
    fake = FakeReminderSender()
    monkeypatch.setattr(scheduler_module, "get_whatsapp_sender", lambda: fake)

    await send_due_appointment_reminders()

    assert fake.calls == []


async def test_reminder_scan_sends_60m_reminder_not_30m_at_45_minutes_out(
    db_session: AsyncSession, monkeypatch
) -> None:
    """Task 4's exact spec: seeded 45 minutes out, the 60-minute reminder
    is due (45 <= 60) but the 30-minute one isn't yet (45 > 30)."""
    settings = get_settings()
    monkeypatch.setattr(
        settings, "whatsapp_appointment_reminder_template_name", "appointment_reminder"
    )
    fake = FakeReminderSender()
    monkeypatch.setattr(scheduler_module, "get_whatsapp_sender", lambda: fake)

    now_utc = datetime.datetime.now(datetime.UTC)
    appointment_utc = now_utc + datetime.timedelta(minutes=45)
    local_ist = appointment_utc + datetime.timedelta(hours=5, minutes=30)
    merchant, appointment = await _seed_confirmed_appointment(
        db_session, appointment_date=local_ist.date(), start_time=local_ist.time()
    )

    await send_due_appointment_reminders(now_utc)

    assert len(fake.calls) == 1
    assert fake.calls[0]["to"] == "919876543210"
    assert fake.calls[0]["template_name"] == "appointment_reminder"

    # A second scan at the same instant must not re-send the 60m
    # reminder -- the AppointmentReminderRepository row from the first
    # send makes this offset ineligible now.
    await send_due_appointment_reminders(now_utc)
    assert len(fake.calls) == 1

    # Advance to 20 minutes out: now inside the 30-minute window. The
    # 30m reminder fires; the 60m one does not re-fire.
    await send_due_appointment_reminders(appointment_utc - datetime.timedelta(minutes=20))
    assert len(fake.calls) == 2


async def test_reminder_scan_skips_cancelled_appointments(
    db_session: AsyncSession, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(
        settings, "whatsapp_appointment_reminder_template_name", "appointment_reminder"
    )
    fake = FakeReminderSender()
    monkeypatch.setattr(scheduler_module, "get_whatsapp_sender", lambda: fake)

    now_utc = datetime.datetime.now(datetime.UTC)
    # +5:30 (IST offset) + 45 minutes so this is squarely inside the
    # 60-minute reminder window, same as the "not sent" scenario above.
    local_ist = now_utc + datetime.timedelta(hours=6, minutes=15)
    merchant, appointment = await _seed_confirmed_appointment(
        db_session, appointment_date=local_ist.date(), start_time=local_ist.time()
    )
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    await AppointmentRepository(db_session).transition_status(
        tenant, appointment.appointment_id, "cancelled", changed_by="staff-1"
    )
    await db_session.commit()

    await send_due_appointment_reminders(now_utc)

    assert fake.calls == []
