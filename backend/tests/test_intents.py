import pytest

from conversation.domain.intents import Intent, classify


@pytest.mark.parametrize(
    "button_id",
    ["place_order", "track_order", "book_appointment", "track_appointment", "faq_menu"],
)
def test_button_reply_maps_directly_to_intent(button_id: str) -> None:
    assert classify(text=None, button_id=button_id) == Intent(button_id)


def test_unknown_button_id_falls_back_to_greeting() -> None:
    assert classify(text=None, button_id="not_a_real_button") == Intent.GREETING


@pytest.mark.parametrize(
    "text",
    ["I want to order", "menu please", "want to buy something"],
)
def test_place_order_keywords(text: str) -> None:
    assert classify(text=text, button_id=None) == Intent.PLACE_ORDER


@pytest.mark.parametrize("text", ["track my order", "what's the status", "Where is my order?"])
def test_track_order_keywords(text: str) -> None:
    assert classify(text=text, button_id=None) == Intent.TRACK_ORDER


@pytest.mark.parametrize(
    "text",
    ["book appointment", "I'd like to make an appointment", "booking please", "book a slot"],
)
def test_book_appointment_keywords(text: str) -> None:
    assert classify(text=text, button_id=None) == Intent.BOOK_APPOINTMENT


@pytest.mark.parametrize(
    "text",
    [
        "what's my appointment status",
        "my appointment",
        "track appointment",
        "show my recent appointment",
    ],
)
def test_track_appointment_keywords(text: str) -> None:
    assert classify(text=text, button_id=None) == Intent.TRACK_APPOINTMENT


def test_track_appointment_beats_book_appointments_broad_keyword() -> None:
    # "appointment status" contains BOOK_APPOINTMENT's broad "appointment"
    # keyword -- TRACK_APPOINTMENT must be checked first, same rationale as
    # TRACK_ORDER vs. PLACE_ORDER below.
    assert classify(text="appointment status please", button_id=None) == Intent.TRACK_APPOINTMENT


@pytest.mark.parametrize("text", ["hi", "hello", "asdkfjhaskdjf", ""])
def test_unrecognized_text_falls_back_to_greeting(text: str) -> None:
    assert classify(text=text, button_id=None) == Intent.GREETING


def test_no_text_and_no_button_falls_back_to_greeting() -> None:
    assert classify(text=None, button_id=None) == Intent.GREETING


def test_button_reply_takes_priority_over_text() -> None:
    assert classify(text="hi", button_id="track_order") == Intent.TRACK_ORDER
