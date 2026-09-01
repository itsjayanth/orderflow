"""Controls whether WhatsApp-driven features (order placing, appointment
booking) run over native in-chat Flows or an interactive CTA-URL button that
links out to the hosted web page for the same action -- selected once,
globally, via the INTERACTION_MODE env var (see shared/config.py). Every
call site that sends a Flow message for one of these features routes
through get_delivery_strategy() instead of branching on waba.whatsapp_flow_id
directly, so mode-switching logic stays in exactly one place
(conversation/domain/handler.py)."""

import logging
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache

from shared.config import get_settings

logger = logging.getLogger(__name__)


class InteractionMode(StrEnum):
    WHATSAPP_FLOW = "WHATSAPP_FLOW"
    BROWSER_LINK = "BROWSER_LINK"


class Feature(StrEnum):
    APPOINTMENT_BOOKING = "APPOINTMENT_BOOKING"
    ORDER_PLACING = "ORDER_PLACING"


_DEFAULT_MODE = InteractionMode.WHATSAPP_FLOW


@dataclass(frozen=True, slots=True)
class FeatureDeliveryConfig:
    """Everything the controller needs to build a BROWSER_LINK reply for a
    feature. web_path is a format string filled with merchant_id -- flow_id
    itself stays out of this map since it's per-merchant data already
    resolved from the WhatsAppBusinessAccount row at each call site
    (waba.whatsapp_flow_id / whatsapp_appointment_flow_id), not a static
    config value. cta_display_text is the button label shown to the
    customer -- reuses the same wording each feature's send_flow call
    already uses as its `cta` string, so the two modes read consistently."""

    web_path: str
    cta_display_text: str


# Add a feature here (plus its own web_path/cta_display_text) to extend this
# to a 3rd feature -- nothing else in this module changes.
def _feature_config() -> dict[Feature, FeatureDeliveryConfig]:
    return {
        Feature.ORDER_PLACING: FeatureDeliveryConfig(
            web_path="/order/{merchant_id}",
            cta_display_text="Order now",
        ),
        Feature.APPOINTMENT_BOOKING: FeatureDeliveryConfig(
            web_path="/book/{merchant_id}",
            cta_display_text="Book now",
        ),
    }


@lru_cache
def _resolved_mode() -> InteractionMode:
    """Reads and validates INTERACTION_MODE once (cached like
    shared.config.get_settings()) -- an invalid or unset value logs a
    warning and falls back to WHATSAPP_FLOW rather than crashing the
    process, since a typo'd env var shouldn't take down inbound WhatsApp
    handling entirely."""
    raw = get_settings().interaction_mode
    try:
        return InteractionMode(raw)
    except ValueError:
        logger.warning(
            "Invalid INTERACTION_MODE=%r -- falling back to %s. Valid values: %s",
            raw,
            _DEFAULT_MODE.value,
            ", ".join(m.value for m in InteractionMode),
        )
        return _DEFAULT_MODE


def get_delivery_strategy(feature: Feature) -> InteractionMode:
    """The single place mode-switching logic lives -- every call site that
    used to check `if waba.whatsapp_flow_id:` directly for one of these two
    features checks this instead."""
    if feature not in _feature_config():
        raise ValueError(f"Unknown feature: {feature!r}")
    return _resolved_mode()


def get_feature_config(feature: Feature) -> FeatureDeliveryConfig:
    return _feature_config()[feature]


def validate_startup_config() -> None:
    """Fail fast at process startup, not at message-send time, if
    BROWSER_LINK mode is selected but frontend_base_url (the domain every
    BROWSER_LINK reply builds its link from) isn't set -- called from
    app.py's module-level startup wiring. A silent failure here would only
    surface days later as "customers stopped getting order links"."""
    if _resolved_mode() != InteractionMode.BROWSER_LINK:
        return
    if not get_settings().frontend_base_url:
        raise RuntimeError(
            "INTERACTION_MODE=BROWSER_LINK requires FRONTEND_BASE_URL to be set -- "
            "every BROWSER_LINK reply links to {FRONTEND_BASE_URL}{web_path}."
        )


def reset_cache_for_tests() -> None:
    """Test-only escape hatch -- _resolved_mode() is cached like
    get_settings(), so a test that changes INTERACTION_MODE needs to clear
    it to see the new value."""
    _resolved_mode.cache_clear()
