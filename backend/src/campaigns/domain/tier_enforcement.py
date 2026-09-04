from onboarding.domain.models import WhatsAppBusinessAccount


def remaining_quota_today(waba: WhatsAppBusinessAccount, sent_today_count: int) -> int:
    """Pure function -- `sent_today_count` comes from
    CampaignRecipientRepository.count_sent_today(), a query counting
    status == "sent" rows with sent_at inside the merchant's current
    local calendar day (Merchant.timezone, the same per-merchant
    timezone field shared/scheduler.py's send_due_appointment_reminders
    already uses, rather than assuming UTC midnight -- an approximation
    of Meta's actual daily-window semantics, since Meta doesn't publicly
    document whether its own reset is calendar-day-in-some-timezone or a
    rolling 24h window)."""
    return max(0, waba.messaging_tier_daily_limit - sent_today_count)
