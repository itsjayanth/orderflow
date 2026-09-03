import datetime
import logging
import zoneinfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from appointment_flow.domain.reminders import is_reminder_due
from appointments.adapters.reminder_repository import AppointmentReminderRepository
from conversation.adapters.whatsapp_client import get_whatsapp_sender
from identity.adapters.repository import MerchantRepository
from identity.domain.models import MerchantVertical
from notifications.adapters.whatsapp_channel import WhatsAppNotificationChannel
from orders.adapters.repository import OrderRepository
from orders.domain.state_machine import transition_payment_status
from shared.config import get_settings
from shared.db import SessionFactory
from shared.tenant import TenantContext

logger = logging.getLogger(__name__)

# Only these two offsets (Task 4 of the appointment scheduling plan: "1hr
# and 30min before") map to an actual notification kind/template today --
# see identity/domain/models.py's Merchant.reminder_offsets_minutes and
# notifications/domain/models.py's NOTIFICATION_KINDS docstring. A
# merchant with some other offset configured (no UI sets one today) gets
# no reminder for it -- silently skipped below, not an error, same
# "unrecognized/unconfigured = no-op" convention the rest of this scan
# already follows for a merchant with no reminder template at all.
_REMINDER_KIND_BY_OFFSET_MINUTES = {
    60: "appointment_reminder_60m",
    30: "appointment_reminder_30m",
}


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


async def send_due_appointment_reminders(now_utc: datetime.datetime | None = None) -> None:
    """Appointment-reminder scan (plan Task 4) -- reuses this same
    AsyncIOScheduler rather than introducing Celery/Redis/BullMQ; this app
    has zero queue infrastructure by design and this is a 5-minute table
    scan, not a workload that needs one.

    Nothing is pre-queued: every tick recomputes "what's due" fresh from
    `status == "confirmed"` appointments plus AppointmentReminderRepository's
    idempotency table, so a cancellation or reschedule after a reminder
    became eligible but before it was sent is automatically safe -- the
    next tick simply won't find that appointment (or will find it at its
    new time) rather than needing an explicit cancel-pending-reminder step.

    Unlike the old single-global-template design, this no longer bails
    out early when the global whatsapp_appointment_reminder_template_name
    env var is unset -- a merchant can configure their own per-kind
    template (NotificationTemplate rows for appointment_reminder_60m/30m)
    with no global default set at all, so that decision has to happen per
    merchant/offset, inside notify_appointment_reminder, not once here.

    now_utc is injectable (defaults to the real clock in every production
    call site) so a test can seed an appointment at a fixed offset and
    then simulate "10 minutes later" by calling this again with a later
    now_utc, rather than needing to actually sleep -- same testability
    convention appointment_flow.domain.reminders.is_reminder_due and
    appointment_flow.domain.availability.get_available_slots already use."""
    now_utc = now_utc if now_utc is not None else datetime.datetime.now(datetime.UTC)
    channel = WhatsAppNotificationChannel(get_whatsapp_sender())

    async with SessionFactory() as session:
        merchants = await MerchantRepository(session).list_enabled_for_vertical(
            MerchantVertical.APPOINTMENT
        )

    sent_count = 0
    for merchant in merchants:
        offsets = [
            offset
            for offset in merchant.reminder_offsets_minutes
            if offset in _REMINDER_KIND_BY_OFFSET_MINUTES
        ]
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
                for offset_minutes in offsets:
                    if offset_minutes in already_sent:
                        continue
                    if not is_reminder_due(
                        appointment_date=appointment.appointment_date,
                        start_time=appointment.start_time,
                        timezone=merchant.timezone,
                        offset_minutes=offset_minutes,
                        now_utc=now_utc,
                    ):
                        continue

                    sent = await channel.notify_appointment_reminder(
                        merchant_id=merchant.merchant_id,
                        appointment_id=appointment.appointment_id,
                        kind=_REMINDER_KIND_BY_OFFSET_MINUTES[offset_minutes],
                    )
                    if sent:
                        await reminder_repo.mark_sent(appointment.appointment_id, offset_minutes)
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
