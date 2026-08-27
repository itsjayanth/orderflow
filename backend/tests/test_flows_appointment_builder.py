import datetime

import pytest

from flows.domain.appointment_booking import (
    InvalidAppointmentSubmissionError,
    build_booking_screen_data,
    parse_appointment_flow_completion,
)


def test_build_booking_screen_data_returns_14_future_dates_starting_tomorrow() -> None:
    data = build_booking_screen_data(business_name="Varkey's")

    assert data["business_name"] == "Varkey's"
    assert len(data["date_options"]) == 14

    today = datetime.datetime.now(datetime.UTC).date()
    ids = [option["id"] for option in data["date_options"]]
    assert today.isoformat() not in ids  # today excluded -- book-ahead only
    assert (today + datetime.timedelta(days=1)).isoformat() == ids[0]
    assert (today + datetime.timedelta(days=14)).isoformat() == ids[-1]
    for option in data["date_options"]:
        assert set(option.keys()) == {"id", "title"}


def test_build_booking_screen_data_returns_30_minute_slots_9am_to_730pm() -> None:
    data = build_booking_screen_data(business_name="Varkey's")

    ids = [option["id"] for option in data["time_options"]]
    assert ids[0] == "09:00"
    assert ids[-1] == "19:30"
    assert len(ids) == 22  # 09:00 .. 19:30 inclusive, every 30 minutes
    assert all(len(option_id) == 5 and option_id[2] == ":" for option_id in ids)
    for option in data["time_options"]:
        assert set(option.keys()) == {"id", "title"}


def test_build_booking_screen_data_time_titles_are_12_hour_no_leading_zero() -> None:
    data = build_booking_screen_data(business_name="Varkey's")

    titles = {option["id"]: option["title"] for option in data["time_options"]}
    assert titles["09:00"] == "9:00 AM"
    assert titles["13:00"] == "1:00 PM"
    assert titles["19:30"] == "7:30 PM"


def test_parse_appointment_flow_completion_parses_valid_payload() -> None:
    submission = parse_appointment_flow_completion(
        {
            "appointment_date": "2026-09-10",
            "appointment_time": "14:30",
            "customer_name": "Asha",
            "customer_email": "asha@example.com",
            "notes": "Window seat please",
        }
    )

    assert submission.appointment_date == datetime.date(2026, 9, 10)
    assert submission.appointment_time == datetime.time(14, 30)
    assert submission.customer_name == "Asha"
    assert submission.customer_email == "asha@example.com"
    assert submission.notes == "Window seat please"


def test_parse_appointment_flow_completion_blank_optional_fields_collapse_to_none() -> None:
    submission = parse_appointment_flow_completion(
        {
            "appointment_date": "2026-09-10",
            "appointment_time": "09:00",
            "customer_name": "  ",
            "customer_email": "",
            "notes": None,
        }
    )

    assert submission.customer_name is None
    assert submission.customer_email is None
    assert submission.notes is None


def test_parse_appointment_flow_completion_raises_on_missing_date() -> None:
    with pytest.raises(InvalidAppointmentSubmissionError):
        parse_appointment_flow_completion({"appointment_time": "09:00"})


def test_parse_appointment_flow_completion_raises_on_missing_time() -> None:
    with pytest.raises(InvalidAppointmentSubmissionError):
        parse_appointment_flow_completion({"appointment_date": "2026-09-10"})


def test_parse_appointment_flow_completion_raises_on_unparseable_date() -> None:
    with pytest.raises(InvalidAppointmentSubmissionError):
        parse_appointment_flow_completion(
            {"appointment_date": "not-a-date", "appointment_time": "09:00"}
        )


def test_parse_appointment_flow_completion_raises_on_unparseable_time() -> None:
    with pytest.raises(InvalidAppointmentSubmissionError):
        parse_appointment_flow_completion(
            {"appointment_date": "2026-09-10", "appointment_time": "not-a-time"}
        )
