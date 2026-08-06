from enum import StrEnum


class Intent(StrEnum):
    PLACE_ORDER = "place_order"
    TRACK_ORDER = "track_order"
    TALK_TO_RESTAURANT = "talk_to_restaurant"
    GREETING = "greeting"


# Order matters: checked top to bottom, first match wins. TRACK_ORDER and
# TALK_TO_RESTAURANT are checked before PLACE_ORDER specifically because
# "order" is a broad word that shows up inside phrases like "track my
# order" -- the narrower intents have to get first look.
_TEXT_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    Intent.TRACK_ORDER: ("track", "status", "where is my order"),
    Intent.TALK_TO_RESTAURANT: ("talk", "human", "help", "staff", "call"),
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
