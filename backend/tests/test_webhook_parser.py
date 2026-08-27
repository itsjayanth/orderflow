import json

from conversation.domain.webhook_parser import parse_inbound_messages


def _envelope(*, value: dict) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "WABA_ID", "changes": [{"value": value, "field": "messages"}]}],
    }


def test_parses_text_message() -> None:
    payload = _envelope(
        value={
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "911234567890", "phone_number_id": "PNID1"},
            "contacts": [{"profile": {"name": "Asha"}, "wa_id": "919876543210"}],
            "messages": [
                {
                    "from": "919876543210",
                    "id": "wamid.ABC123",
                    "timestamp": "1700000000",
                    "type": "text",
                    "text": {"body": "hi"},
                }
            ],
        }
    )

    messages = parse_inbound_messages(payload)

    assert len(messages) == 1
    message = messages[0]
    assert message.phone_number_id == "PNID1"
    assert message.whatsapp_message_id == "wamid.ABC123"
    assert message.from_phone == "919876543210"
    assert message.from_name == "Asha"
    assert message.text == "hi"
    assert message.button_id is None


def test_parses_interactive_button_reply() -> None:
    payload = _envelope(
        value={
            "metadata": {"phone_number_id": "PNID1"},
            "messages": [
                {
                    "from": "919876543210",
                    "id": "wamid.BTN1",
                    "type": "interactive",
                    "interactive": {
                        "type": "button_reply",
                        "button_reply": {"id": "place_order", "title": "Place order"},
                    },
                }
            ],
        }
    )

    messages = parse_inbound_messages(payload)

    assert len(messages) == 1
    assert messages[0].button_id == "place_order"
    assert messages[0].text is None


def test_parses_interactive_list_reply() -> None:
    payload = _envelope(
        value={
            "metadata": {"phone_number_id": "PNID1"},
            "messages": [
                {
                    "from": "919876543210",
                    "id": "wamid.LIST1",
                    "type": "interactive",
                    "interactive": {
                        "type": "list_reply",
                        "list_reply": {"id": "faq_menu", "title": "Where are you located?"},
                    },
                }
            ],
        }
    )

    messages = parse_inbound_messages(payload)

    assert len(messages) == 1
    assert messages[0].button_id == "faq_menu"
    assert messages[0].text is None


def test_skips_status_callbacks() -> None:
    """Delivery/read status webhooks carry a `statuses` key, not
    `messages` -- nothing to act on."""
    payload = _envelope(
        value={
            "metadata": {"phone_number_id": "PNID1"},
            "statuses": [{"id": "wamid.ABC123", "status": "delivered"}],
        }
    )

    messages = parse_inbound_messages(payload)

    assert messages == []


def test_handles_multiple_entries_and_messages() -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_1",
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "PNID1"},
                            "messages": [
                                {"from": "111", "id": "m1", "type": "text", "text": {"body": "a"}}
                            ],
                        }
                    }
                ],
            },
            {
                "id": "WABA_2",
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "PNID2"},
                            "messages": [
                                {"from": "222", "id": "m2", "type": "text", "text": {"body": "b"}}
                            ],
                        }
                    }
                ],
            },
        ],
    }

    messages = parse_inbound_messages(payload)

    assert {m.whatsapp_message_id for m in messages} == {"m1", "m2"}


def test_ignores_malformed_entries_without_phone_number_id() -> None:
    payload = _envelope(value={"messages": [{"from": "111", "id": "m1", "type": "text"}]})

    messages = parse_inbound_messages(payload)

    assert messages == []


def test_parses_flow_completion_reply() -> None:
    completion_payload = {
        "selected_items": ["abc-123"],
        "order_type": "pickup",
        "payment_method": "cod",
    }
    payload = _envelope(
        value={
            "metadata": {"phone_number_id": "PNID1"},
            "messages": [
                {
                    "from": "919876543210",
                    "id": "wamid.FLOW1",
                    "type": "interactive",
                    "interactive": {
                        "type": "nfm_reply",
                        "nfm_reply": {
                            "name": "flow",
                            "body": "Sent",
                            "response_json": json.dumps(completion_payload),
                        },
                    },
                }
            ],
        }
    )

    messages = parse_inbound_messages(payload)

    assert len(messages) == 1
    assert messages[0].flow_response == completion_payload
    assert messages[0].text is None
    assert messages[0].button_id is None


def test_flow_completion_with_unparseable_response_json_is_not_a_hard_failure() -> None:
    payload = _envelope(
        value={
            "metadata": {"phone_number_id": "PNID1"},
            "messages": [
                {
                    "from": "919876543210",
                    "id": "wamid.FLOW2",
                    "type": "interactive",
                    "interactive": {
                        "type": "nfm_reply",
                        "nfm_reply": {"name": "flow", "body": "Sent", "response_json": "{not json"},
                    },
                }
            ],
        }
    )

    messages = parse_inbound_messages(payload)

    assert len(messages) == 1
    assert messages[0].flow_response is None
