from conversation.adapters.whatsapp_client import _list_row


def test_short_title_is_unchanged_with_no_description() -> None:
    row = _list_row("opt_1", "Short title")
    assert row == {"id": "opt_1", "title": "Short title"}
    assert "description" not in row


def test_title_of_exactly_24_chars_is_unchanged() -> None:
    title = "x" * 24
    row = _list_row("opt_1", title)
    assert row == {"id": "opt_1", "title": title}
    assert "description" not in row


def test_title_over_24_chars_is_truncated_with_description() -> None:
    title = "Do you accept card payments at delivery?"
    row = _list_row("faq_1", title)
    assert len(row["title"]) == 24
    assert row["title"].endswith("…")
    assert row["description"] == title[:72]


def test_very_long_title_description_capped_at_72_chars() -> None:
    title = "x" * 200
    row = _list_row("faq_2", title)
    assert len(row["title"]) == 24
    assert row["title"].endswith("…")
    assert len(row["description"]) == 72
    assert row["description"] == title[:72]
