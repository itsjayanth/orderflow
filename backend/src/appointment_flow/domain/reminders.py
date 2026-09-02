import datetime
import zoneinfo


def is_reminder_due(
    *,
    appointment_date: datetime.date,
    start_time: datetime.time,
    timezone: str,
    offset_hours: int,
    now_utc: datetime.datetime,
) -> bool:
    """True once `now_utc` has crossed into the `offset_hours`-before
    window and the appointment itself hasn't already started -- a
    threshold check, not a tight window, since shared/scheduler.py's scan
    runs every 5 minutes and relies on AppointmentReminderRepository's
    idempotency table (not a narrow time window) to avoid duplicate sends:
    the first tick after crossing the threshold sends it, every later tick
    sees it already recorded and skips.

    appointment_date/start_time are naive (no tzinfo) on the Appointment
    row -- interpreted here in the merchant's own local time (`timezone`,
    Merchant.timezone) before comparing against `now_utc`, same rationale
    as appointment_flow.domain.booking's _merchant_today."""
    tz = zoneinfo.ZoneInfo(timezone)
    local_dt = datetime.datetime.combine(appointment_date, start_time, tzinfo=tz)
    appointment_utc = local_dt.astimezone(datetime.UTC)
    threshold_utc = appointment_utc - datetime.timedelta(hours=offset_hours)
    return threshold_utc <= now_utc <= appointment_utc
