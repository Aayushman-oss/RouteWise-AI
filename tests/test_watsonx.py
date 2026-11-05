"""
RouteWise AI – Tests: WatsonxService (without live IBM credentials)
Tests configuration validation, error handling and mocking behavior.
"""

import pytest
from unittest.mock import MagicMock, patch


def test_watsonx_service_raises_config_error_when_no_credentials():
    """WatsonxService raises ConfigError when credentials are missing."""
    import config
    from services.watsonx_service import WatsonxService, ConfigError

    original_key = config.WATSONX_API_KEY
    original_pid = config.WATSONX_PROJECT_ID
    try:
        config.WATSONX_API_KEY = None
        config.WATSONX_PROJECT_ID = None
        svc = WatsonxService()
        with pytest.raises(ConfigError):
            svc._ensure_client()
    finally:
        config.WATSONX_API_KEY = original_key
        config.WATSONX_PROJECT_ID = original_pid


def test_test_connection_returns_failure_without_credentials():
    """test_connection returns ConnectionTestResult(success=False) when not configured."""
    import config
    from services.watsonx_service import WatsonxService

    original_key = config.WATSONX_API_KEY
    original_pid = config.WATSONX_PROJECT_ID
    try:
        config.WATSONX_API_KEY = None
        config.WATSONX_PROJECT_ID = None
        svc = WatsonxService()
        result = svc.test_connection()
        assert not result.success
        assert "Missing" in result.message or "credentials" in result.message.lower() or "Configured" not in result.message
    finally:
        config.WATSONX_API_KEY = original_key
        config.WATSONX_PROJECT_ID = original_pid


def test_generation_result_attributes():
    from services.watsonx_service import GenerationResult
    r = GenerationResult(text="Hello India", input_tokens=10, output_tokens=5, model_id="ibm/granite-4-h-small")
    assert r.text == "Hello India"
    assert r.input_tokens == 10
    assert r.output_tokens == 5


def test_watsonx_error_is_exception():
    from services.watsonx_service import WatsonxError
    with pytest.raises(WatsonxError):
        raise WatsonxError("Test error")


def test_config_error_is_exception():
    from services.watsonx_service import ConfigError
    with pytest.raises(ConfigError):
        raise ConfigError("Config missing")


def test_get_watsonx_service_singleton():
    """get_watsonx_service returns the same instance on repeated calls."""
    from services import watsonx_service
    # Reset singleton for clean test
    watsonx_service._service_instance = None
    svc1 = watsonx_service.get_watsonx_service()
    svc2 = watsonx_service.get_watsonx_service()
    assert svc1 is svc2


def test_prompt_too_large_raises_value_error():
    """generate() raises ValueError for oversized prompts."""
    import config
    from services.watsonx_service import WatsonxService, ConfigError

    original_key = config.WATSONX_API_KEY
    original_pid = config.WATSONX_PROJECT_ID
    try:
        # Give fake credentials so we get past config check
        config.WATSONX_API_KEY = "fakekey1234"
        config.WATSONX_PROJECT_ID = "fake-project-id"
        svc = WatsonxService()
        # Manually set a mock client so _ensure_client passes
        svc._client = MagicMock()
        svc._model = MagicMock()

        huge_prompt = "A" * (config.MAX_PROMPT_CHARS * 4)
        with pytest.raises(ValueError, match="maximum allowed size"):
            svc.generate(huge_prompt)
    finally:
        config.WATSONX_API_KEY = original_key
        config.WATSONX_PROJECT_ID = original_pid
        from services import watsonx_service
        watsonx_service._service_instance = None
