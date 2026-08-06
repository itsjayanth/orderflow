import re

# Deliberately a plain regex substitution, not a real template engine (no
# eval, no attribute access, no loops/conditionals) -- merchant-authored
# template bodies are untrusted input. Unknown/misspelled `{{var}}` tokens
# are left exactly as typed rather than silently dropped, so a merchant
# previewing/testing a template notices the mistake instead of shipping a
# message with a blank gap in it.
_VARIABLE_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")

# The variables every notification kind's context may include -- not every
# kind populates every variable (e.g. a template for "order_confirmed" using
# {{ready_at}} would just render literally, since that key isn't in context
# yet at confirmation time).
TEMPLATE_VARIABLES = ("business_name", "customer_name", "order_id", "total", "currency")


def render_template(body: str, context: dict[str, str]) -> str:
    def _substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        return context.get(key, match.group(0))

    return _VARIABLE_PATTERN.sub(_substitute, body)
