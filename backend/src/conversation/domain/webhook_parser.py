from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class InboundMessage:
    phone_number_id: str
    whatsapp_message_id: str
    from_phone: str
    from_name: str | None
    text: str | None
    button_id: str | None


def parse_inbound_messages(payload: dict[str, Any]) -> list[InboundMessage]:
    """Parses a WhatsApp Cloud API webhook payload's `entry[].changes[].value`
    into InboundMessage records. Only `messages` events carry something to
    act on -- status callbacks (sent/delivered/read) and other webhook
    field types are silently skipped, not errors."""
    messages: list[InboundMessage] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            if phone_number_id is None:
                continue

            contacts = value.get("contacts", [])
            name_by_wa_id = {c.get("wa_id"): c.get("profile", {}).get("name") for c in contacts}

            for raw_message in value.get("messages", []):
                message_id = raw_message.get("id")
                from_phone = raw_message.get("from")
                if message_id is None or from_phone is None:
                    continue

                text: str | None = None
                button_id: str | None = None
                message_type = raw_message.get("type")
                if message_type == "text":
                    text = raw_message.get("text", {}).get("body")
                elif message_type == "interactive":
                    interactive = raw_message.get("interactive", {})
                    if interactive.get("type") == "button_reply":
                        button_id = interactive.get("button_reply", {}).get("id")

                messages.append(
                    InboundMessage(
                        phone_number_id=phone_number_id,
                        whatsapp_message_id=message_id,
                        from_phone=from_phone,
                        from_name=name_by_wa_id.get(from_phone),
                        text=text,
                        button_id=button_id,
                    )
                )

    return messages
