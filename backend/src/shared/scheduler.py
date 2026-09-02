import datetime
import logging
import zoneinfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from appointment_flow.domain.reminders import is_reminder_due
from appointments.adapters.reminder_repository import AppointmentReminderRepository
from conversation.adapters.whatsapp_client import get_whatsapp_sender
from identity.adapters.repository import MerchantRepository
from notifications.adapters.whatsapp_channel import WhatsAppNotificationChannel
from orders.adapters.repository import OrderRepository
from orders.domain.state_machine import transition_payment_status
from shared.config import get_settings
from shared.db import SessionFactory
from shared.tenant import TenantContext

logger = logging.getLogger(__name__)


async def sweep_abandoned_orders() -> None:
    """Timeout sweep from ARCHITECTURE.md Section 7a/Section 10 -- orders
    stuck in awaiting_payment past the threshold (no webhook, no retry)
    are cancelled so they don't sit in limbo forever."""
    settings = get_settings()
    threshold = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
        minutes=settings.abandoned_order_timeout_minutes
    )

    async with SessionFactory() as session:
        repo = OrderRepository(session)
        stale_orders = await repo.list_stale_awaiting_payment(threshold)
        for order in stale_orders:
            transition_payment_status(order, "cancelled")
        if stale_orders:
            await session.commit()
            logger.info("Cancelled %d abandoned order(s)", len(stale_orders))


async def send_due_appointment_reminders() -> None:
    """Appointment-reminder scan (plan Task 4) -- reuses this same
    AsyncIOScheduler rather than introducing Celery/Redis/BullMQ; this app
    has zero queue infrastructure by design and this is a 5-minute table
    scan, not a workload that needs one.

    Nothing is pre-queued: every tick recomputes "what's due" fresh from
    `status == "confirmed"` appointments plus AppointmentReminderRepository's
    idempotency table, so a cancellation or reschedule after a reminder
    became eligible but before it was sent is automatically safe -- the
    next tick simply won't find that appointment (or will find it at its
    new time) rather than needing an explicit cancel-pending-reminder step."""
    settings = get_settings()
    if not settings.whatsapp_appointment_reminder_template_name:
        # No approved template configured -- every send would just fail at
        # Meta, so skip the scan entirely rather than log a failure per
        # confirmed appointment every 5 minutes.
        return

    now_utc = datetime.datetime.now(datetime.UTC)
    channel = WhatsAppNotificationChannel(get_whatsapp_sender())

    async with SessionFactory() as session:
        merchants = await MerchantRepository(session).list_appointment_booking_enabled()

    sent_count = 0
    for merchant in merchants:
        offsets = merchant.reminder_offsets_hours
        if not offsets:
            continue

        tenant = TenantContext(merchant_id=merchant.merchant_id)
        merchant_today = datetime.datetime.now(zoneinfo.ZoneInfo(merchant.timezone)).date()

        async with SessionFactory() as session:
            reminder_repo = AppointmentReminderRepository(session)
            appointments = await reminder_repo.list_confirmed_upcoming(
                tenant, on_or_after=merchant_today
            )

            for appointment in appointments:
                already_sent = await reminder_repo.sent_offsets(appointment.appointment_id)
                for offset_hours in offsets:
                    if offset_hours in already_sent:
                        continue
                    if not is_reminder_due(
                        appointment_date=appointment.appointment_date,
                        start_time=appointment.start_time,
                        timezone=merchant.timezone,
                        offset_hours=offset_hours,
                        now_utc=now_utc,
                    ):
                        continue

                    sent = await channel.notify_appointment_reminder(
                        merchant_id=merchant.merchant_id,
                        appointment_id=appointment.appointment_id,
                    )
                    if sent:
                        await reminder_repo.mark_sent(appointment.appointment_id, offset_hours)
                        await session.commit()
                        sent_count += 1
                    # A failed send leaves no AppointmentReminder row, so
                    # the next 5-minute tick retries it -- no separate
                    # retry/backoff bookkeeping needed.

    if sent_count:
        logger.info("Sent %d appointment reminder(s)", sent_count)


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(sweep_abandoned_orders, "interval", minutes=5, id="sweep_abandoned_orders")
    scheduler.add_job(
        send_due_appointment_reminders, "interval", minutes=5, id="appointment_reminders"
    )
    return scheduler
