from enum import StrEnum


class Intent(StrEnum):
    PLACE_ORDER = "place_order"
    TRACK_ORDER = "track_order"
    BOOK_APPOINTMENT = "book_appointment"
    # MULTI_VERTICAL_PLAN.md Phase M4: the appointment vertical's analogue
    # of TRACK_ORDER, pointed at Appointment instead of Order -- same
    # lookup-by-phone-number pattern, see handler.py's TRACK_ORDER branch.
    TRACK_APPOINTMENT = "track_appointment"
    GREETING = "greeting"
    # Button-driven, like the other menu intents above -- classify() maps
    # the "FAQs" button's id straight to this via the generic button_id
    # lookup below, no keyword list needed.
    FAQ_MENU = "faq_menu"
    # Reported on HandledMessage when a reply was resolved to a specific
    # stored FAQItem (either a confident keyword match on free text, or a
    # tap on a FAQ list-message row) -- never returned by classify() itself,
    # since that requires a tenant-scoped DB lookup classify() deliberately
    # doesn't do (see handler.py).
    FAQ = "faq"
    # Reported on HandledMessage when an inbound message is a completed
    # WhatsApp Flow submission (InboundMessage.flow_response is set) --
    # never returned by classify(), which only sees text/button messages.
    FLOW_ORDER_COMPLETED = "flow_order_completed"
    # Reported on HandledMessage when an inbound message is a completed
    # WhatsApp appointment-booking Flow submission (InboundMessage.flow_response
    # is set, and carries an appointment_date key) -- never returned by
    # classify(), same reason as FLOW_ORDER_COMPLETED above.
    FLOW_APPOINTMENT_COMPLETED = "flow_appointment_completed"


# Order matters: checked top to bottom, first match wins. TRACK_APPOINTMENT is
# checked before TRACK_ORDER (its "status" keyword would otherwise swallow
# "appointment status"), which in turn is checked before PLACE_ORDER, and
# TRACK_APPOINTMENT before BOOK_APPOINTMENT (whose "appointment" keyword is
# broad) -- same "narrower intents get first look" rule this table already
# followed for TRACK_ORDER vs. PLACE_ORDER. classify() itself doesn't know
# the merchant's vertical (see handler.py for that gate); this table just
# has to not misfire between the two verticals' own intents.
_TEXT_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    Intent.TRACK_APPOINTMENT: (
        "appointment status",
        "my appointment",
        "track appointment",
        "recent appointment",
        "appointment history",
    ),
    Intent.TRACK_ORDER: ("track", "status", "where is my order"),
    Intent.BOOK_APPOINTMENT: (
        "book appointment",
        "appointment",
        "booking",
        "book a slot",
    ),
    Intent.PLACE_ORDER: ("order", "menu", "buy"),
}


def classify(*, text: str | None, button_id: str | None) -> Intent:
    """Structured/guided intent detection, not free-text AI chatbot parsing
    (explicitly out of scope per docs/project-brief.txt) -- a WhatsApp
    interactive-button reply always wins when present; free text falls
    back to keyword matching, and anything unrecognized (including "hi")
    shows the greeting/intent menu rather than guessing."""
    if button_id is not None:
        try:
            return Intent(button_id)
        except ValueError:
            return Intent.GREETING

    if text is None:
        return Intent.GREETING

    lowered = text.strip().lower()
    for intent, keywords in _TEXT_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return intent

    return Intent.GREETING
