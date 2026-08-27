import datetime
from dataclasses import dataclass
from typing import Any

# Fixed 30-minute slots, 09:00 through 19:30 inclusive -- there is no
# per-merchant operating-hours/closed-day concept yet (v1 scope per
# docs/project-brief.txt is explicitly "no staff calendars"), so every
# merchant sees the exact same uniform slot list regardless of when they
# actually open or close. This is a deliberate v1 simplification, not a
# gap being silently papered over -- a merchant who only opens evenings
# still sees a 9 AM slot on the Flow.
_SLOT_START_MINUTES = 9 * 60
_SLOT_END_MINUTES = 19 * 60 + 30
_SLOT_STEP_MINUTES = 30

# How many days ahead the DATE dropdown offers -- starting tomorrow, not
# today, since this is a "book ahead" tool, not a same-day walk-in one.
_DAYS_AHEAD = 14


def build_booking_screen_data(*, business_name: str) -> dict[str, Any]:
    """The BOOKING screen's `data` on Flow INIT -- a fixed, merchant-agnostic
    set of date/time options, plus the merchant's display name for the
    screen heading. Represented as Dropdown `data-source` arrays of
    {id, title} objects (same shape RadioButtonsGroup/CheckboxGroup use
    elsewhere in this app for categories/items) rather than a native date
    or time picker component -- see flows/assets/appointment_flow.json's
    header comment for why."""
    today = datetime.datetime.now(datetime.UTC).date()
    date_options = []
    for offset in range(1, _DAYS_AHEAD + 1):
        day = today + datetime.timedelta(days=offset)
        date_options.append({"id": day.isoformat(), "title": day.strftime("%a, %d %b")})

    time_options = []
    for minutes in range(_SLOT_START_MINUTES, _SLOT_END_MINUTES + 1, _SLOT_STEP_MINUTES):
        slot = datetime.time(hour=minutes // 60, minute=minutes % 60)
        time_options.append({"id": slot.strftime("%H:%M"), "title": _format_12h(slot)})

    return {
        "business_name": business_name,
        "date_options": date_options,
        "time_options": time_options,
    }


def _format_12h(value: datetime.time) -> str:
    # strftime("%I:%M %p") pads the hour with a leading zero (e.g.
    # "09:00 AM") -- strip it for the "9:00 AM" look the product ask wants,
    # same convention conversation/domain/handler.py's appointment
    # confirmation text already uses for appointment_time.
    return value.strftime("%I:%M %p").lstrip("0")


class InvalidAppointmentSubmissionError(Exception):
    """The Dropdowns' `required: true` should block an empty/missing date
    or time client-side already -- this is a defensive fallback for the
    data reaching the server malformed some other way (a stale/replayed
    request), not the primary way bad submissions get caught. Mirrors
    order_builder.py's NoItemsSelectedError rationale."""


@dataclass(frozen=True, slots=True)
class FlowAppointmentSubmission:
    appointment_date: datetime.date
    appointment_time: datetime.time
    customer_name: str | None
    customer_email: str | None
    notes: str | None


def parse_appointment_flow_completion(payload: dict[str, Any]) -> FlowAppointmentSubmission:
    """Parses the `complete` action's payload, delivered by WhatsApp as a
    regular inbound message (interactive.nfm_reply.response_json) once the
    customer finishes the Flow -- see webhook_parser.py."""
    raw_date = payload.get("appointment_date")
    raw_time = payload.get("appointment_time")

    try:
        appointment_date = datetime.date.fromisoformat(str(raw_date))
    except (TypeError, ValueError) as exc:
        raise InvalidAppointmentSubmissionError(f"invalid appointment_date: {raw_date!r}") from exc

    try:
        hour_str, minute_str = str(raw_time).split(":")
        appointment_time = datetime.time(hour=int(hour_str), minute=int(minute_str))
    except (TypeError, ValueError) as exc:
        raise InvalidAppointmentSubmissionError(f"invalid appointment_time: {raw_time!r}") from exc

    return FlowAppointmentSubmission(
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        customer_name=(payload.get("customer_name") or "").strip() or None,
        customer_email=(payload.get("customer_email") or "").strip() or None,
        notes=(payload.get("notes") or "").strip() or None,
    )
