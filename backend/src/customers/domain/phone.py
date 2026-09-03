import re

# E.164 (excluding the leading "+") is 7-15 digits -- used as a sanity
# bound on the digit-only id below, not a full E.164 validator.
_MIN_DIGITS = 7
_MAX_DIGITS = 15


def normalize_whatsapp_id(raw: object) -> str | None:
    """Normalizes a WhatsApp id/phone number to this codebase's canonical
    identity key: E.164 digits with no "+", spaces, or punctuation (e.g.
    "+91 98765-43210" -> "919876543210"). This is deliberately the same
    shape Meta's webhook already reports inbound senders in (see
    conversation/domain/webhook_parser.py) -- a native Flow's flow_token
    and every WhatsApp-inbound customer.whatsapp_number are only ever this
    shape, so a literal "+"-prefixed E.164 string would silently stop
    matching them. Returns None for anything that isn't a string, or whose
    digit count falls outside E.164's 7-15 digit range, so a malformed/
    missing id always reads as "no identity available" rather than a
    lookup that raises or matches the wrong customer.

    Used both when *storing* a whatsapp_number (CustomerRepository.
    find_or_create/create) and when *looking one up*
    (identity_resolution.resolve_customer_by_whatsapp_id,
    CustomerRepository.get_by_whatsapp_number) -- normalizing only one
    side would let e.g. a webview checkout's client-supplied
    "+919876543210" and a native Flow's "919876543210" for the exact same
    person silently create two different Customer rows instead of
    resolving to one, defeating this feature's idempotency requirement."""
    if not isinstance(raw, str):
        return None
    digits = re.sub(r"\D", "", raw)
    if not (_MIN_DIGITS <= len(digits) <= _MAX_DIGITS):
        return None
    return digits
