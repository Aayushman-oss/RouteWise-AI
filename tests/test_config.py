"""
RouteWise AI – Tests: Configuration
"""

import os
import pytest


def test_config_defaults_exist():
    """Config module loads without errors and provides defaults."""
    import config
    assert config.WATSONX_MODEL_ID == "ibm/granite-4-h-small"
    assert config.WATSONX_URL.startswith("https://")
    assert config.MAX_NEW_TOKENS == 1200
    assert config.MODEL_TEMPERATURE == 0.3
    assert config.REQUEST_TIMEOUT == 60


def test_validate_config_missing_credentials():
    """validate_config returns not-ready when credentials are missing."""
    import config
    original_key = config.WATSONX_API_KEY
    original_pid = config.WATSONX_PROJECT_ID
    try:
        config.WATSONX_API_KEY = None
        config.WATSONX_PROJECT_ID = None
        status = config.validate_config()
        assert not status.is_ready
        assert not status.api_key_set
        assert not status.project_id_set
        assert "WATSONX_API_KEY" in status.summary
    finally:
        config.WATSONX_API_KEY = original_key
        config.WATSONX_PROJECT_ID = original_pid


def test_get_safe_config_display_no_secrets():
    """get_safe_config_display never returns API key or project ID."""
    import config
    display = config.get_safe_config_display()
    assert "api_key" not in str(display).lower() or display.get("api_key_configured") in (True, False)
    # Ensure actual credential values are not exposed
    key = config.WATSONX_API_KEY or ""
    pid = config.WATSONX_PROJECT_ID or ""
    display_str = str(display)
    if len(key) > 8:
        assert key not in display_str
    if len(pid) > 8:
        assert pid not in display_str


def test_config_status_summary_format():
    import config
    status = config.ConfigStatus(
        api_key_set=False,
        project_id_set=True,
        url_set=True,
        model_id_set=True,
    )
    assert not status.is_ready
    assert "WATSONX_API_KEY" in status.summary
