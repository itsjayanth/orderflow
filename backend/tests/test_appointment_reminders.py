import datetime

from appointment_flow.domain.reminders import is_reminder_due

_TZ = "Asia/Kolkata"  # UTC+5:30


def test_not_due_before_the_offset_window() -> None:
    # Appointment at 18:00 IST, offset 60m -- more than 60 minutes away.
    now_utc = datetime.datetime(2026, 9, 3, 10, 0, tzinfo=datetime.UTC)
    assert not is_reminder_due(
        appointment_date=datetime.date(2026, 9, 3),
        start_time=datetime.time(18, 0),
        timezone=_TZ,
        offset_minutes=60,
        now_utc=now_utc,
    )


def test_due_exactly_at_the_offset_threshold() -> None:
    # Appointment 2026-09-03 18:00 IST == 2026-09-03 12:30 UTC.
    # 60 minutes before that is 2026-09-03 11:30 UTC.
    appointment_utc = datetime.datetime(2026, 9, 3, 12, 30, tzinfo=datetime.UTC)
    threshold = appointment_utc - datetime.timedelta(minutes=60)
    assert is_reminder_due(
        appointment_date=datetime.date(2026, 9, 3),
        start_time=datetime.time(18, 0),
        timezone=_TZ,
        offset_minutes=60,
        now_utc=threshold,
    )


def test_not_due_after_the_appointment_has_already_started() -> None:
    appointment_utc = datetime.datetime(2026, 9, 3, 12, 30, tzinfo=datetime.UTC)
    after = appointment_utc + datetime.timedelta(minutes=1)
    assert not is_reminder_due(
        appointment_date=datetime.date(2026, 9, 3),
        start_time=datetime.time(18, 0),
        timezone=_TZ,
        offset_minutes=60,
        now_utc=after,
    )


def test_due_partway_through_the_window() -> None:
    appointment_utc = datetime.datetime(2026, 9, 3, 12, 30, tzinfo=datetime.UTC)
    mid_window = appointment_utc - datetime.timedelta(minutes=45)
    assert is_reminder_due(
        appointment_date=datetime.date(2026, 9, 3),
        start_time=datetime.time(18, 0),
        timezone=_TZ,
        offset_minutes=60,
        now_utc=mid_window,
    )


def test_30_minute_offset_not_due_at_the_60_minute_threshold() -> None:
    """The two offsets are independent windows -- 60 minutes out is inside
    the 60m reminder's window but not yet inside the 30m one's."""
    appointment_utc = datetime.datetime(2026, 9, 3, 12, 30, tzinfo=datetime.UTC)
    sixty_minutes_out = appointment_utc - datetime.timedelta(minutes=60)
    assert not is_reminder_due(
        appointment_date=datetime.date(2026, 9, 3),
        start_time=datetime.time(18, 0),
        timezone=_TZ,
        offset_minutes=30,
        now_utc=sixty_minutes_out,
    )


def test_30_minute_offset_due_at_the_30_minute_threshold() -> None:
    appointment_utc = datetime.datetime(2026, 9, 3, 12, 30, tzinfo=datetime.UTC)
    thirty_minutes_out = appointment_utc - datetime.timedelta(minutes=30)
    assert is_reminder_due(
        appointment_date=datetime.date(2026, 9, 3),
        start_time=datetime.time(18, 0),
        timezone=_TZ,
        offset_minutes=30,
        now_utc=thirty_minutes_out,
    )
