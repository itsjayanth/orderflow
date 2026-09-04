import datetime
import logging
import zoneinfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from appointment_flow.domain.reminders import is_reminder_due
from appointments.adapters.reminder_repository import AppointmentReminderRepository
from campaigns.adapters.repository import CampaignRecipientRepository, CampaignRepository
from campaigns.domain.send_orchestrator import send_campaign_batch
from campaigns.domain.tier_enforcement import remaining_quota_today
from conversation.adapters.whatsapp_client import get_whatsapp_sender
from identity.adapters.repository import MerchantRepository
from identity.domain.models import MerchantVertical
from notifications.adapters.whatsapp_channel import WhatsAppNotificationChannel
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from orders.adapters.repository import OrderRepository
from orders.domain.state_machine import transition_payment_status
from shared.config import get_settings
from shared.db import SessionFactory
from shared.tenant import TenantContext

logger = logging.getLogger(__name__)

# The two offsets (Task 4 of the appointment scheduling plan: "1hr and
# 30min before") that get their own customizable notification kind/
# template -- see identity/domain/models.py's
# Merchant.reminder_offsets_minutes and notifications/domain/models.py's
# NOTIFICATION_KINDS docstring. A merchant can configure any other offset
# too (Settings' Appointment reminders editor); those still get a
# reminder sent, just via the one shared default template
# (whatsapp_appointment_reminder_template_name) rather than a bespoke
# per-offset one -- see notify_appointment_reminder's `kind=None` case.
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
        offsets = merchant.reminder_offsets_minutes
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
                        # None for any offset besides the two named ones --
                        # notify_appointment_reminder falls back to the
                        # shared default template in that case rather than
                        # skipping the send outright.
                        kind=_REMINDER_KIND_BY_OFFSET_MINUTES.get(offset_minutes),
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


async def send_due_campaigns(now_utc: datetime.datetime | None = None) -> None:
    """Broadcast-campaign send sweep (Phase 14) -- mirrors
    sweep_abandoned_orders' shape exactly: query due work, act, commit,
    log a count. "Due" (CampaignRepository.list_due) covers both a
    scheduled campaign whose time has arrived (or is send-now) and a
    campaign still mid-send from a prior tick/day, so overflow from a
    tier-capped previous run resumes automatically -- there's no separate
    "day 2 resume" bookkeeping, the query is always "whatever's still due".

    now_utc is injectable, same testability convention as
    send_due_appointment_reminders above -- a test seeds a small tier cap,
    calls this once, then calls it again with a later now_utc to simulate
    the next day without sleeping."""
    now_utc = now_utc if now_utc is not None else datetime.datetime.now(datetime.UTC)
    sender = get_whatsapp_sender()

    async with SessionFactory() as session:
        due_campaigns = await CampaignRepository(session).list_due(now_utc)

    sent_count = 0
    for due_campaign in due_campaigns:
        tenant = TenantContext(merchant_id=due_campaign.merchant_id)
        async with SessionFactory() as session:
            merchant = await MerchantRepository(session).get(tenant.merchant_id)
            waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
            if (
                merchant is None
                or waba is None
                or not waba.phone_number_id
                or not waba.access_token_encrypted
            ):
                continue

            campaign_repo = CampaignRepository(session)
            campaign = await campaign_repo.get(tenant, due_campaign.campaign_id)
            if campaign is None:
                continue
            if campaign.status == "scheduled":
                await campaign_repo.set_status(campaign, "sending")
                await session.commit()

            # Merchant-local calendar day, not UTC midnight -- same
            # per-merchant timezone convention send_due_appointment_reminders
            # above already uses. An approximation of Meta's actual daily-
            # tier-reset window (not fully documented publicly), per
            # campaigns/domain/tier_enforcement.py's docstring. Derived from
            # the injectable now_utc (not the real clock) so a test can
            # simulate a day boundary via a later now_utc, same as
            # is_reminder_due's now_utc parameter above.
            merchant_now = now_utc.astimezone(zoneinfo.ZoneInfo(merchant.timezone))
            day_start = merchant_now.replace(
                hour=0, minute=0, second=0, microsecond=0
            ).astimezone(datetime.UTC)
            day_end = day_start + datetime.timedelta(days=1)

            recipient_repo = CampaignRecipientRepository(session)
            sent_today = await recipient_repo.count_sent_today(
                tenant, day_start=day_start, day_end=day_end
            )
            quota_remaining = remaining_quota_today(waba, sent_today)

            sent_count += await send_campaign_batch(
                session, tenant, campaign, waba, sender, quota_remaining
            )

            if not await recipient_repo.has_pending(campaign.campaign_id):
                await campaign_repo.set_status(campaign, "completed", completed=True)
                await session.commit()

    if sent_count:
        logger.info("Sent %d campaign message(s)", sent_count)


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(sweep_abandoned_orders, "interval", minutes=5, id="sweep_abandoned_orders")
    scheduler.add_job(
        send_due_appointment_reminders, "interval", minutes=5, id="appointment_reminders"
    )
    scheduler.add_job(send_due_campaigns, "interval", minutes=5, id="send_due_campaigns")
    return scheduler
