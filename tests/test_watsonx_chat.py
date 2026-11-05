"""Tests for IBM watsonx.ai chat inference response handling."""

from unittest.mock import MagicMock

import pytest

from services.watsonx_service import WatsonxService, WatsonxError


def test_extract_chat_response_from_dict():
    response = {
        "choices": [{"message": {"role": "assistant", "content": '{"ok": true}'}}],
        "usage": {"prompt_tokens": 25, "completion_tokens": 8},
    }
    text, input_tokens, output_tokens = WatsonxService._extract_chat_response(response)
    assert text == '{"ok": true}'
    assert input_tokens == 25
    assert output_tokens == 8


def test_extract_chat_response_from_content_blocks():
    response = {
        "choices": [{"message": {"content": [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "India"},
        ]}}],
        "usage": {"prompt_tokens": 4, "completion_tokens": 2},
    }
    text, _, _ = WatsonxService._extract_chat_response(response)
    assert text == "Hello\\nIndia"


def test_generate_uses_chat_not_deprecated_generate(monkeypatch):
    import config

    monkeypatch.setattr(config, "WATSONX_API_KEY", "test-key")
    monkeypatch.setattr(config, "WATSONX_PROJECT_ID", "test-project")
    service = WatsonxService()
    model = MagicMock()
    model.chat.return_value = {
        "choices": [{"message": {"content": '{"result": "ok"}'}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 6},
    }
    service._client = MagicMock()
    service._model = model

    result = service.generate("Return JSON", max_tokens=128, temperature=0.2)

    model.chat.assert_called_once()
    model.generate.assert_not_called()
    assert result.text == '{"result": "ok"}'
    assert result.output_tokens == 6
    args = model.chat.call_args.kwargs
    assert args["params"]["max_tokens"] == 128
    assert args["params"]["temperature"] == 0.2
    assert args["messages"][0]["role"] == "user"


def test_generate_fails_clearly_if_chat_method_missing(monkeypatch):
    import config

    monkeypatch.setattr(config, "WATSONX_API_KEY", "test-key")
    monkeypatch.setattr(config, "WATSONX_PROJECT_ID", "test-project")
    service = WatsonxService()
    service._client = MagicMock()
    service._model = object()

    with pytest.raises(WatsonxError, match="does not expose the chat inference method"):
        service.generate("Hello", max_tokens=20)


def test_generate_rejects_empty_chat_response(monkeypatch):
    import config

    monkeypatch.setattr(config, "WATSONX_API_KEY", "test-key")
    monkeypatch.setattr(config, "WATSONX_PROJECT_ID", "test-project")
    service = WatsonxService()
    model = MagicMock()
    model.chat.return_value = {"choices": [{"message": {"content": ""}}], "usage": {}}
    service._client = MagicMock()
    service._model = model

    with pytest.raises(WatsonxError, match="empty chat response"):
        service.generate("Hello", max_tokens=20)
