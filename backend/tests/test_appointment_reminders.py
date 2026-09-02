import datetime

from appointment_flow.domain.reminders import is_reminder_due

_TZ = "Asia/Kolkata"  # UTC+5:30


def test_not_due_before_the_offset_window() -> None:
    # Appointment at 18:00 IST, offset 24h -- more than 24h away.
    now_utc = datetime.datetime(2026, 9, 1, 10, 0, tzinfo=datetime.UTC)
    assert not is_reminder_due(
        appointment_date=datetime.date(2026, 9, 3),
        start_time=datetime.time(18, 0),
        timezone=_TZ,
        offset_hours=24,
        now_utc=now_utc,
    )


def test_due_exactly_at_the_offset_threshold() -> None:
    # Appointment 2026-09-03 18:00 IST == 2026-09-03 12:30 UTC.
    # 24h before that is 2026-09-02 12:30 UTC.
    appointment_utc = datetime.datetime(2026, 9, 3, 12, 30, tzinfo=datetime.UTC)
    threshold = appointment_utc - datetime.timedelta(hours=24)
    assert is_reminder_due(
        appointment_date=datetime.date(2026, 9, 3),
        start_time=datetime.time(18, 0),
        timezone=_TZ,
        offset_hours=24,
        now_utc=threshold,
    )


def test_not_due_after_the_appointment_has_already_started() -> None:
    appointment_utc = datetime.datetime(2026, 9, 3, 12, 30, tzinfo=datetime.UTC)
    after = appointment_utc + datetime.timedelta(minutes=1)
    assert not is_reminder_due(
        appointment_date=datetime.date(2026, 9, 3),
        start_time=datetime.time(18, 0),
        timezone=_TZ,
        offset_hours=24,
        now_utc=after,
    )


def test_due_partway_through_the_window() -> None:
    appointment_utc = datetime.datetime(2026, 9, 3, 12, 30, tzinfo=datetime.UTC)
    mid_window = appointment_utc - datetime.timedelta(hours=1)
    assert is_reminder_due(
        appointment_date=datetime.date(2026, 9, 3),
        start_time=datetime.time(18, 0),
        timezone=_TZ,
        offset_hours=24,
        now_utc=mid_window,
    )
