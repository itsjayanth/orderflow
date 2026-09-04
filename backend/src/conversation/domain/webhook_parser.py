import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InboundMessage:
    phone_number_id: str
    whatsapp_message_id: str
    from_phone: str
    from_name: str | None
    text: str | None
    button_id: str | None
    # Set when this message is a completed WhatsApp Flow submission
    # (interactive.type == "nfm_reply") -- the Flow's final `complete`
    # action payload, already JSON-decoded. handler.py dispatches on this
    # directly rather than through classify()'s text/button intent
    # matching, since a Flow completion isn't really a conversational
    # intent, it's structured data.
    flow_response: dict[str, Any] | None = None


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
                flow_response: dict[str, Any] | None = None
                message_type = raw_message.get("type")
                if message_type == "text":
                    text = raw_message.get("text", {}).get("body")
                elif message_type == "interactive":
                    interactive = raw_message.get("interactive", {})
                    interactive_type = interactive.get("type")
                    if interactive_type == "button_reply":
                        button_id = interactive.get("button_reply", {}).get("id")
                    elif interactive_type == "list_reply":
                        # A tap on an interactive *list* message's row comes
                        # back shaped differently from a button tap, but
                        # means the same thing to handler.py -- "the id of
                        # whichever option the user picked" -- so it's folded
                        # into the same button_id field rather than adding a
                        # separate one only FAQ list messages would ever set.
                        button_id = interactive.get("list_reply", {}).get("id")
                    elif interactive_type == "nfm_reply":
                        response_json = interactive.get("nfm_reply", {}).get("response_json")
                        if response_json:
                            try:
                                flow_response = json.loads(response_json)
                            except (TypeError, ValueError):
                                logger.warning(
                                    "Flow completion had unparseable response_json: %r",
                                    response_json,
                                )

                messages.append(
                    InboundMessage(
                        phone_number_id=phone_number_id,
                        whatsapp_message_id=message_id,
                        from_phone=from_phone,
                        from_name=name_by_wa_id.get(from_phone),
                        text=text,
                        button_id=button_id,
                        flow_response=flow_response,
                    )
                )

    return messages


@dataclass(frozen=True, slots=True)
class TemplateStatusUpdate:
    meta_template_id: str
    status: str
    reason: str | None = None


# Meta's own event names -> MessageTemplate.meta_approval_status's values
# (campaigns/domain/models.py's TEMPLATE_APPROVAL_STATUSES) -- Meta's
# webhook uses uppercase event names distinct from this codebase's
# lowercase status column. An event not in this table (e.g. IN_APPEAL,
# which Meta also sends but this codebase has no dedicated status for) is
# silently skipped, same "unrecognized field/event = nothing to act on,
# not an error" convention parse_inbound_messages already follows.
_APPROVAL_STATUS_BY_META_EVENT: dict[str, str] = {
    "APPROVED": "approved",
    "REJECTED": "rejected",
    "PENDING": "pending",
    "PAUSED": "paused",
    "DISABLED": "disabled",
}


def parse_template_status_updates(payload: dict[str, Any]) -> list[TemplateStatusUpdate]:
    """Parses a WhatsApp Cloud API webhook payload's `entry[].changes[]`
    where `field == "message_template_status_update"` into
    TemplateStatusUpdate records -- mirrors parse_inbound_messages' own
    "walk entry/changes, skip anything not shaped like what I'm looking
    for" structure, just keyed off `field` instead of the presence of a
    `messages` list. Meta multiplexes multiple event types onto the same
    subscribed webhook URL/payload, so a real inbound payload can carry
    both message and template-status changes interleaved -- this and
    parse_inbound_messages are both run against the same raw payload by
    conversation/api/router.py's receive_webhook, not routed separately."""
    updates: list[TemplateStatusUpdate] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "message_template_status_update":
                continue
            value = change.get("value", {})
            meta_template_id = value.get("message_template_id")
            event = value.get("event")
            if meta_template_id is None or event is None:
                continue
            status = _APPROVAL_STATUS_BY_META_EVENT.get(str(event).upper())
            if status is None:
                continue

            updates.append(
                TemplateStatusUpdate(
                    meta_template_id=str(meta_template_id),
                    status=status,
                    reason=value.get("reason"),
                )
            )

    return updates
