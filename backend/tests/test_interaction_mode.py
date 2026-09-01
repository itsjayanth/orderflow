import logging

import pytest

from shared.config import get_settings
from shared.interaction_mode import (
    Feature,
    InteractionMode,
    get_delivery_strategy,
    get_feature_config,
    reset_cache_for_tests,
    validate_startup_config,
)


@pytest.fixture(autouse=True)
def _restore_settings() -> None:
    """_resolved_mode() is cached like get_settings() itself -- every test
    below mutates the shared Settings singleton, so both the mutation and
    the cache have to be cleaned up after each test regardless of pass/fail,
    or state leaks into the next test (and into test_conversation_handler.py
    if it runs afterwards in the same session)."""
    settings = get_settings()
    original_mode = settings.interaction_mode
    original_frontend_base_url = settings.frontend_base_url
    yield
    settings.interaction_mode = original_mode
    settings.frontend_base_url = original_frontend_base_url
    reset_cache_for_tests()


def test_valid_whatsapp_flow_mode_resolves() -> None:
    get_settings().interaction_mode = "WHATSAPP_FLOW"
    reset_cache_for_tests()

    assert get_delivery_strategy(Feature.ORDER_PLACING) == InteractionMode.WHATSAPP_FLOW


def test_valid_browser_link_mode_resolves() -> None:
    get_settings().interaction_mode = "BROWSER_LINK"
    reset_cache_for_tests()

    assert get_delivery_strategy(Feature.ORDER_PLACING) == InteractionMode.BROWSER_LINK


def test_missing_mode_falls_back_to_default_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    get_settings().interaction_mode = ""
    reset_cache_for_tests()

    with caplog.at_level(logging.WARNING):
        strategy = get_delivery_strategy(Feature.APPOINTMENT_BOOKING)

    assert strategy == InteractionMode.WHATSAPP_FLOW
    assert any("Invalid INTERACTION_MODE" in record.message for record in caplog.records)


def test_invalid_mode_falls_back_to_default_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    get_settings().interaction_mode = "NOT_A_REAL_MODE"
    reset_cache_for_tests()

    with caplog.at_level(logging.WARNING):
        strategy = get_delivery_strategy(Feature.ORDER_PLACING)

    assert strategy == InteractionMode.WHATSAPP_FLOW
    assert any("Invalid INTERACTION_MODE" in record.message for record in caplog.records)


def test_both_features_return_the_same_resolved_mode() -> None:
    get_settings().interaction_mode = "BROWSER_LINK"
    reset_cache_for_tests()

    assert (
        get_delivery_strategy(Feature.ORDER_PLACING)
        == get_delivery_strategy(Feature.APPOINTMENT_BOOKING)
        == InteractionMode.BROWSER_LINK
    )


def test_validate_startup_config_is_noop_in_whatsapp_flow_mode() -> None:
    settings = get_settings()
    settings.interaction_mode = "WHATSAPP_FLOW"
    settings.frontend_base_url = ""
    reset_cache_for_tests()

    validate_startup_config()  # must not raise -- frontend_base_url is irrelevant in this mode


def test_validate_startup_config_raises_when_frontend_base_url_missing() -> None:
    settings = get_settings()
    settings.interaction_mode = "BROWSER_LINK"
    settings.frontend_base_url = ""
    reset_cache_for_tests()

    with pytest.raises(RuntimeError, match="BROWSER_LINK"):
        validate_startup_config()


def test_validate_startup_config_passes_when_frontend_base_url_set() -> None:
    settings = get_settings()
    settings.interaction_mode = "BROWSER_LINK"
    settings.frontend_base_url = "https://example.com"
    reset_cache_for_tests()

    validate_startup_config()  # must not raise


def test_feature_config_carries_each_feature_own_web_path_and_cta_text() -> None:
    order_config = get_feature_config(Feature.ORDER_PLACING)
    appointment_config = get_feature_config(Feature.APPOINTMENT_BOOKING)

    assert order_config.web_path != appointment_config.web_path
    assert order_config.cta_display_text != appointment_config.cta_display_text
    assert "{merchant_id}" in order_config.web_path
    assert "{merchant_id}" in appointment_config.web_path
