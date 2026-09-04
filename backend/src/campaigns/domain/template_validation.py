import re

from campaigns.domain.models import TEMPLATE_CATEGORIES, TEMPLATE_HEADER_TYPES

# Meta's documented per-component length caps for a message template.
_HEADER_TEXT_MAX_LENGTH = 60
_BODY_MAX_LENGTH = 1024
_FOOTER_MAX_LENGTH = 60

_VARIABLE_RE = re.compile(r"\{\{(\d+)\}\}")


class InvalidTemplateError(Exception):
    """Raised by validate_template(); the API layer maps this to a 422."""


def normalize_template_name(name: str) -> str:
    """Meta requires a template name to be lowercase snake_case -- this is
    applied at save time so a merchant typing "Order Promo" doesn't get a
    confusing rejection from Meta over formatting alone."""
    normalized = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not normalized:
        raise InvalidTemplateError("Template name must contain at least one letter or digit.")
    return normalized


def count_body_variables(body_text: str) -> int:
    """{{1}}, {{2}}, ... must be sequential with no gaps, starting at 1 --
    Meta rejects a template whose declared example params don't exactly
    match the variables actually used in the body. Raises on a gap/
    duplicate/out-of-order number (e.g. {{1}} {{3}}, or {{2}} {{2}})
    rather than silently guessing what the merchant meant."""
    numbers = sorted(int(match) for match in _VARIABLE_RE.findall(body_text))
    expected = list(range(1, len(numbers) + 1))
    if numbers != expected:
        raise InvalidTemplateError(
            f"Body variables must be sequential starting at {{{{1}}}} with no gaps or "
            f"duplicates -- found {numbers or 'none'}."
        )
    return len(numbers)


def validate_template(
    *,
    category: str,
    header_type: str,
    header_text: str | None,
    body_text: str,
    footer_text: str | None,
) -> int:
    """Pure validation, no I/O -- returns the body's variable count (so the
    caller doesn't need to call count_body_variables separately) or raises
    InvalidTemplateError. Doesn't validate header_media_handle/buttons --
    those are adapter-layer concerns (an image upload result, a URL
    shape), not something knowable from this data alone."""
    if category not in TEMPLATE_CATEGORIES:
        raise InvalidTemplateError(
            f"category must be one of {TEMPLATE_CATEGORIES}, got {category!r}."
        )
    if header_type not in TEMPLATE_HEADER_TYPES:
        raise InvalidTemplateError(
            f"header_type must be one of {TEMPLATE_HEADER_TYPES}, got {header_type!r}."
        )
    if header_type == "TEXT" and not header_text:
        raise InvalidTemplateError("header_text is required when header_type is TEXT.")
    if header_type != "TEXT" and header_text:
        raise InvalidTemplateError("header_text is only valid when header_type is TEXT.")
    if header_text is not None and len(header_text) > _HEADER_TEXT_MAX_LENGTH:
        raise InvalidTemplateError(
            f"header_text must be at most {_HEADER_TEXT_MAX_LENGTH} characters."
        )
    if not body_text.strip():
        raise InvalidTemplateError("body_text is required.")
    if len(body_text) > _BODY_MAX_LENGTH:
        raise InvalidTemplateError(f"body_text must be at most {_BODY_MAX_LENGTH} characters.")
    if footer_text is not None and len(footer_text) > _FOOTER_MAX_LENGTH:
        raise InvalidTemplateError(
            f"footer_text must be at most {_FOOTER_MAX_LENGTH} characters."
        )

    return count_body_variables(body_text)
