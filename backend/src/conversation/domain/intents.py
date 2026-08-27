from enum import StrEnum


class Intent(StrEnum):
    PLACE_ORDER = "place_order"
    TRACK_ORDER = "track_order"
    BOOK_APPOINTMENT = "book_appointment"
    TALK_TO_RESTAURANT = "talk_to_restaurant"
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


# Order matters: checked top to bottom, first match wins. TRACK_ORDER and
# TALK_TO_RESTAURANT are checked before PLACE_ORDER specifically because
# "order" is a broad word that shows up inside phrases like "track my
# order" -- the narrower intents have to get first look.
_TEXT_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    Intent.TRACK_ORDER: ("track", "status", "where is my order"),
    Intent.TALK_TO_RESTAURANT: ("talk", "human", "help", "staff", "call"),
    Intent.BOOK_APPOINTMENT: (
        "book appointment",
        "appointment",
        "booking",
        "book a slot",
        "book a table",
    ),
    Intent.PLACE_ORDER: ("order", "menu", "hungry"),
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
