"""
Unit tests for services/model_discovery.py
===========================================
All tests are pure unit tests — no IBM SDK calls, no network requests.
The SDK and APIClient are mocked where needed.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from services.model_discovery import (
    ModelInfo,
    DiscoveryResult,
    _parse_model_specs,
    filter_generative_models,
    filter_granite_generative,
    is_model_available,
    list_available_models,
    list_available_models_no_client,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

SAMPLE_RESOURCES_DICT = [
    {"model_id": "ibm/granite-4-h-small",      "label": "Granite 4H Small",      "task_ids": ["generation"]},
    {"model_id": "ibm/granite-13b-instruct-v2", "label": "Granite 13B Instruct",  "task_ids": ["generation", "question_answering"]},
    {"model_id": "ibm/granite-embedding-278m-multilingual", "label": "Granite Embedding", "task_ids": []},
    {"model_id": "meta-llama/llama-3-3-70b-instruct", "label": "Llama 3.3 70B", "task_ids": ["generation", "chat"]},
    {"model_id": "mistralai/mistral-medium-2505", "label": "Mistral Medium",      "task_ids": ["generation"]},
    {"model_id": "ibm/granite-ttm-512-96-r2",   "label": "Granite TTM",           "task_ids": ["time_series_forecasting"]},
]

SAMPLE_MODELS = _parse_model_specs({"resources": SAMPLE_RESOURCES_DICT})


# ─── ModelInfo ────────────────────────────────────────────────────────────────

class TestModelInfo:
    def test_is_generative_with_generation_task(self):
        m = ModelInfo("ibm/granite-4-h-small", task_ids=["generation"])
        assert m.is_generative is True

    def test_is_generative_with_question_answering(self):
        m = ModelInfo("some/model", task_ids=["question_answering"])
        assert m.is_generative is True

    def test_is_generative_with_chat_task(self):
        m = ModelInfo("some/model", task_ids=["chat"])
        assert m.is_generative is True

    def test_is_not_generative_empty_tasks(self):
        m = ModelInfo("ibm/granite-embedding-278m-multilingual", task_ids=[])
        assert m.is_generative is False

    def test_is_not_generative_time_series(self):
        m = ModelInfo("ibm/granite-ttm-512-96-r2", task_ids=["time_series_forecasting"])
        assert m.is_generative is False

    def test_is_granite_true(self):
        m = ModelInfo("ibm/granite-4-h-small")
        assert m.is_granite is True

    def test_is_granite_false_for_llama(self):
        m = ModelInfo("meta-llama/llama-3-3-70b-instruct")
        assert m.is_granite is False

    def test_is_granite_case_insensitive(self):
        m = ModelInfo("IBM/Granite-4-h-small")
        assert m.is_granite is True

    def test_is_generative_granite_both_conditions(self):
        m = ModelInfo("ibm/granite-4-h-small", task_ids=["generation"])
        assert m.is_generative_granite is True

    def test_is_not_generative_granite_embedding(self):
        m = ModelInfo("ibm/granite-embedding-278m-multilingual", task_ids=[])
        assert m.is_generative_granite is False

    def test_is_not_generative_granite_llama(self):
        m = ModelInfo("meta-llama/llama-3-3-70b-instruct", task_ids=["generation"])
        assert m.is_generative_granite is False


# ─── DiscoveryResult ──────────────────────────────────────────────────────────

class TestDiscoveryResult:
    def test_success_when_no_error(self):
        dr = DiscoveryResult(models=SAMPLE_MODELS)
        assert dr.success is True

    def test_not_success_when_error(self):
        dr = DiscoveryResult(error="Something failed")
        assert dr.success is False

    def test_generative_models_filters_correctly(self):
        dr = DiscoveryResult(models=SAMPLE_MODELS)
        gen = dr.generative_models()
        ids = [m.model_id for m in gen]
        assert "ibm/granite-4-h-small" in ids
        assert "meta-llama/llama-3-3-70b-instruct" in ids
        assert "ibm/granite-embedding-278m-multilingual" not in ids
        assert "ibm/granite-ttm-512-96-r2" not in ids

    def test_generative_granite_models(self):
        dr = DiscoveryResult(models=SAMPLE_MODELS)
        gg = dr.generative_granite_models()
        ids = [m.model_id for m in gg]
        assert "ibm/granite-4-h-small" in ids
        assert "ibm/granite-13b-instruct-v2" in ids
        assert "meta-llama/llama-3-3-70b-instruct" not in ids
        assert "ibm/granite-embedding-278m-multilingual" not in ids

    def test_is_model_available_true(self):
        dr = DiscoveryResult(models=SAMPLE_MODELS)
        assert dr.is_model_available("ibm/granite-4-h-small") is True

    def test_is_model_available_false(self):
        dr = DiscoveryResult(models=SAMPLE_MODELS)
        assert dr.is_model_available("ibm/non-existent-model") is False

    def test_is_generative_model_available_true(self):
        dr = DiscoveryResult(models=SAMPLE_MODELS)
        assert dr.is_generative_model_available("ibm/granite-4-h-small") is True

    def test_is_generative_model_available_false_for_embedding(self):
        dr = DiscoveryResult(models=SAMPLE_MODELS)
        assert dr.is_generative_model_available("ibm/granite-embedding-278m-multilingual") is False

    def test_empty_result_is_successful(self):
        dr = DiscoveryResult(models=[])
        assert dr.success is True
        assert dr.generative_models() == []


# ─── _parse_model_specs ───────────────────────────────────────────────────────

class TestParseModelSpecs:
    def test_parses_dict_with_resources_key(self):
        raw = {"total_count": 2, "resources": SAMPLE_RESOURCES_DICT[:2]}
        result = _parse_model_specs(raw)
        assert len(result) == 2
        assert result[0].model_id == "ibm/granite-4-h-small"

    def test_parses_plain_list(self):
        result = _parse_model_specs(SAMPLE_RESOURCES_DICT)
        assert len(result) == len(SAMPLE_RESOURCES_DICT)

    def test_parses_object_with_resources_attr(self):
        mock_raw = MagicMock()
        mock_raw.resources = SAMPLE_RESOURCES_DICT[:3]
        result = _parse_model_specs(mock_raw)
        assert len(result) == 3

    def test_skips_entries_without_model_id(self):
        raw = {"resources": [{"label": "No ID here", "task_ids": []}]}
        result = _parse_model_specs(raw)
        assert result == []

    def test_handles_empty_resources(self):
        result = _parse_model_specs({"resources": []})
        assert result == []

    def test_handles_none_task_ids(self):
        raw = {"resources": [{"model_id": "some/model", "label": "X", "task_ids": None}]}
        result = _parse_model_specs(raw)
        assert len(result) == 1
        assert result[0].task_ids == []

    def test_handles_object_based_resource(self):
        item = MagicMock()
        item.model_id = "ibm/granite-4-h-small"
        item.label = "Granite"
        item.task_ids = ["generation"]
        result = _parse_model_specs([item])
        assert len(result) == 1
        assert result[0].model_id == "ibm/granite-4-h-small"
        assert result[0].is_generative is True

    def test_handles_unexpected_raw_type_gracefully(self):
        result = _parse_model_specs(None)
        assert result == []

    def test_label_defaults_to_model_id_when_missing(self):
        raw = {"resources": [{"model_id": "some/model"}]}
        result = _parse_model_specs(raw)
        assert result[0].label == "some/model"


# ─── filter_generative_models ────────────────────────────────────────────────

class TestFilterGenerativeModels:
    def test_filters_out_non_generative(self):
        result = filter_generative_models(SAMPLE_MODELS)
        for m in result:
            assert m.is_generative

    def test_keeps_llama_and_granite_gen(self):
        result = filter_generative_models(SAMPLE_MODELS)
        ids = [m.model_id for m in result]
        assert "meta-llama/llama-3-3-70b-instruct" in ids
        assert "ibm/granite-4-h-small" in ids

    def test_excludes_embedding_model(self):
        result = filter_generative_models(SAMPLE_MODELS)
        ids = [m.model_id for m in result]
        assert "ibm/granite-embedding-278m-multilingual" not in ids

    def test_empty_list_returns_empty(self):
        assert filter_generative_models([]) == []


# ─── filter_granite_generative ───────────────────────────────────────────────

class TestFilterGraniteGenerative:
    def test_returns_only_generative_granite(self):
        result = filter_granite_generative(SAMPLE_MODELS)
        for m in result:
            assert m.is_granite
            assert m.is_generative

    def test_excludes_llama(self):
        result = filter_granite_generative(SAMPLE_MODELS)
        ids = [m.model_id for m in result]
        assert "meta-llama/llama-3-3-70b-instruct" not in ids

    def test_excludes_granite_embedding(self):
        result = filter_granite_generative(SAMPLE_MODELS)
        ids = [m.model_id for m in result]
        assert "ibm/granite-embedding-278m-multilingual" not in ids

    def test_includes_generative_granite_models(self):
        result = filter_granite_generative(SAMPLE_MODELS)
        ids = [m.model_id for m in result]
        assert "ibm/granite-4-h-small" in ids
        assert "ibm/granite-13b-instruct-v2" in ids

    def test_empty_list_returns_empty(self):
        assert filter_granite_generative([]) == []


# ─── is_model_available ──────────────────────────────────────────────────────

class TestIsModelAvailable:
    def test_returns_true_for_present_model(self):
        assert is_model_available("ibm/granite-4-h-small", SAMPLE_MODELS) is True

    def test_returns_false_for_absent_model(self):
        assert is_model_available("ibm/phantom-model", SAMPLE_MODELS) is False

    def test_case_sensitive_match(self):
        assert is_model_available("IBM/GRANITE-4-H-SMALL", SAMPLE_MODELS) is False

    def test_empty_model_list(self):
        assert is_model_available("ibm/granite-4-h-small", []) is False


# ─── list_available_models ───────────────────────────────────────────────────

class TestListAvailableModels:
    def test_returns_discovery_result_on_success(self):
        mock_client = MagicMock()
        mock_client.foundation_models.get_model_specs.return_value = {
            "resources": SAMPLE_RESOURCES_DICT
        }
        result = list_available_models(mock_client)
        assert result.success is True
        assert len(result.models) == len(SAMPLE_RESOURCES_DICT)

    def test_passes_url_from_config(self):
        mock_client = MagicMock()
        mock_client.foundation_models.get_model_specs.return_value = {"resources": []}
        with patch("services.model_discovery.config") as mock_cfg:
            mock_cfg.WATSONX_URL = "https://us-south.ml.cloud.ibm.com"
            list_available_models(mock_client)
        mock_client.foundation_models.get_model_specs.assert_called_once_with(
            url="https://us-south.ml.cloud.ibm.com"
        )

    def test_returns_error_result_on_sdk_exception(self):
        mock_client = MagicMock()
        mock_client.foundation_models.get_model_specs.side_effect = RuntimeError("network error")
        result = list_available_models(mock_client)
        assert result.success is False
        assert "RuntimeError" in result.error

    def test_mocked_client_works_without_sdk_import(self):
        mock_client = MagicMock()
        mock_client.foundation_models.get_model_specs.return_value = {
            "resources": [{"model_id": "ibm/granite-4-h-small", "task_ids": ["generation"]}]
        }
        with patch.dict("sys.modules", {"ibm_watsonx_ai": None}):
            result = list_available_models(mock_client)
        assert result.success is True
        assert result.is_generative_model_available("ibm/granite-4-h-small")

    def test_generative_granite_count_from_sample(self):
        mock_client = MagicMock()
        mock_client.foundation_models.get_model_specs.return_value = {
            "resources": SAMPLE_RESOURCES_DICT
        }
        result = list_available_models(mock_client)
        gg = result.generative_granite_models()
        # ibm/granite-4-h-small and ibm/granite-13b-instruct-v2
        assert len(gg) == 2


# ─── list_available_models_no_client ─────────────────────────────────────────

class TestListAvailableModelsNoClient:
    def test_returns_discovery_result(self):
        result = list_available_models_no_client(url="https://us-south.ml.cloud.ibm.com")
        # Either succeeds or fails gracefully — must never raise
        assert isinstance(result, DiscoveryResult)

    def test_returns_error_when_sdk_not_installed(self):
        with patch.dict("sys.modules", {"ibm_watsonx_ai": None}):
            result = list_available_models_no_client()
        assert result.success is False

    def test_never_raises(self):
        # Should never propagate any exception regardless of SDK state
        try:
            result = list_available_models_no_client(url="https://invalid.example.com")
            assert isinstance(result, DiscoveryResult)
        except Exception as exc:
            pytest.fail(f"list_available_models_no_client raised unexpectedly: {exc}")
