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


@pytest.mark.parametrize("text", ["stop", "STOP", " Stop ", "unsubscribe", "Unsubscribe"])
def test_opt_out_keywords_exact_match(text: str) -> None:
    assert classify(text=text, button_id=None) == Intent.OPT_OUT


@pytest.mark.parametrize("text", ["start", "START", " Start ", "subscribe", "Subscribe"])
def test_opt_in_keywords_exact_match(text: str) -> None:
    assert classify(text=text, button_id=None) == Intent.OPT_IN


@pytest.mark.parametrize(
    "text",
    [
        "please stop shipping it late",
        "what's the status",
        "when do you start delivering",
        "I want to subscribe to your newsletter please",
    ],
)
def test_opt_keywords_do_not_match_as_substrings(text: str) -> None:
    # Unlike every other entry in _TEXT_KEYWORDS (substring match), STOP/
    # START/UNSUBSCRIBE/SUBSCRIBE only fire on an exact, stripped match --
    # a substring match would misfire on ordinary customer text like this.
    result = classify(text=text, button_id=None)
    assert result not in (Intent.OPT_OUT, Intent.OPT_IN)
