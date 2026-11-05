"""
RouteWise AI – Model Discovery Utility
=======================================
Queries the IBM watsonx.ai SDK for models available in the configured region
and classifies them by task capability.

Design principles:
- Never raises exceptions to callers — always returns empty results on failure
- Takes an already-initialised APIClient as a parameter (no credential handling here)
- Safe to call without live credentials (returns empty list with an error string)
- No logging of credential values or raw response bodies
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import config

logger = logging.getLogger("routewise.model_discovery")


# ─── Data types ──────────────────────────────────────────────────────────────

@dataclass
class ModelInfo:
    """Structured representation of a single watsonx.ai model."""
    model_id: str
    label: str = ""
    task_ids: list[str] = field(default_factory=list)

    @property
    def is_generative(self) -> bool:
        """True when the model supports text generation or Q&A."""
        return any(
            t in ("generation", "question_answering", "text_generation",
                  "chat", "conversational")
            for t in self.task_ids
        )

    @property
    def is_granite(self) -> bool:
        """True when the model ID belongs to the IBM Granite family."""
        return self.model_id.lower().startswith("ibm/granite-")

    @property
    def is_generative_granite(self) -> bool:
        return self.is_granite and self.is_generative


@dataclass
class DiscoveryResult:
    """Result container returned by list_available_models()."""
    models: list[ModelInfo] = field(default_factory=list)
    error: str = ""        # non-empty when the probe failed
    endpoint: str = ""     # WATSONX_URL used for the probe

    @property
    def success(self) -> bool:
        return not self.error

    def generative_models(self) -> list[ModelInfo]:
        return [m for m in self.models if m.is_generative]

    def generative_granite_models(self) -> list[ModelInfo]:
        return [m for m in self.models if m.is_generative_granite]

    def is_model_available(self, model_id: str) -> bool:
        return any(m.model_id == model_id for m in self.models)

    def is_generative_model_available(self, model_id: str) -> bool:
        return any(m.model_id == model_id and m.is_generative for m in self.models)


# ─── Public helpers (stateless, accept pre-built objects) ─────────────────────

def list_available_models(client: Any) -> DiscoveryResult:
    """
    Query the IBM watsonx.ai SDK for all models available at the configured
    endpoint.

    Parameters
    ----------
    client : ibm_watsonx_ai.APIClient
        An already-initialised APIClient instance (not created here — caller
        is responsible for auth).

    Returns
    -------
    DiscoveryResult
        Always returns a DiscoveryResult; never raises.
    """
    endpoint = config.WATSONX_URL

    # The caller supplies an already-authenticated client. Do not require the
    # SDK package merely to exercise this function with a mocked client.
    if client is None:
        return DiscoveryResult(
            error="An authenticated watsonx.ai client is required.",
            endpoint=endpoint,
        )

    try:
        raw = client.foundation_models.get_model_specs(url=endpoint)
    except Exception as exc:
        cls_name = type(exc).__name__
        logger.warning(
            "model_discovery: get_model_specs failed. exc_class=%s endpoint=%s",
            cls_name, endpoint,
        )
        return DiscoveryResult(
            error=f"Could not retrieve model list ({cls_name}).",
            endpoint=endpoint,
        )

    models = _parse_model_specs(raw)
    logger.info(
        "model_discovery: found %d total models (%d generative, %d generative Granite) at %s",
        len(models),
        sum(1 for m in models if m.is_generative),
        sum(1 for m in models if m.is_generative_granite),
        endpoint,
    )
    return DiscoveryResult(models=models, endpoint=endpoint)


def list_available_models_no_client(url: Optional[str] = None) -> DiscoveryResult:
    """
    Attempt to retrieve model specs using a URL-only (unauthenticated) call.

    Some watsonx.ai SDK versions support passing just a URL to get_model_specs
    without a project/auth context.  Falls back to an error result gracefully.

    Parameters
    ----------
    url : str, optional
        Endpoint URL.  Defaults to config.WATSONX_URL.
    """
    endpoint = url or config.WATSONX_URL

    try:
        from ibm_watsonx_ai import APIClient  # type: ignore
        from ibm_watsonx_ai import Credentials  # type: ignore
    except ImportError:
        return DiscoveryResult(
            error="ibm-watsonx-ai SDK is not installed.",
            endpoint=endpoint,
        )

    try:
        # Some SDK versions allow get_model_specs at module/package level
        from ibm_watsonx_ai.foundation_models.utils.enums import ModelTypes  # noqa: F401
    except ImportError:
        pass

    try:
        # Try the static/class-level approach first (no auth needed in some SDK builds)
        import ibm_watsonx_ai as watsonx_pkg
        get_specs_fn = getattr(watsonx_pkg, "get_model_specs", None)
        if get_specs_fn is None:
            # Try via foundation_models module
            from ibm_watsonx_ai import foundation_models as fm_mod
            get_specs_fn = getattr(fm_mod, "get_model_specs", None)

        if get_specs_fn is not None:
            raw = get_specs_fn(url=endpoint)
            models = _parse_model_specs(raw)
            return DiscoveryResult(models=models, endpoint=endpoint)
    except Exception as exc:
        logger.debug("model_discovery no-client probe failed: %s", type(exc).__name__)

    return DiscoveryResult(
        error="Model list requires an authenticated client. Use list_available_models(client) instead.",
        endpoint=endpoint,
    )


# ─── Convenience wrappers (accept raw list/dict returned by caller) ───────────

def filter_generative_models(models: list[ModelInfo]) -> list[ModelInfo]:
    """Return only models whose task_ids include a generative capability."""
    return [m for m in models if m.is_generative]


def filter_granite_generative(models: list[ModelInfo]) -> list[ModelInfo]:
    """Return only IBM Granite models that support text generation."""
    return [m for m in models if m.is_generative_granite]


def is_model_available(model_id: str, models: list[ModelInfo]) -> bool:
    """True when model_id appears in the provided model list."""
    return any(m.model_id == model_id for m in models)


# ─── Internal parsers ─────────────────────────────────────────────────────────

def _parse_model_specs(raw: Any) -> list[ModelInfo]:
    """
    Parse the raw response from get_model_specs() into a list of ModelInfo.

    The SDK may return a dict with a 'resources' key or an object with a
    .resources attribute.  Each resource may be a dict or an object.
    """
    resources: list[Any] = []

    if isinstance(raw, dict):
        resources = raw.get("resources", [])
    elif hasattr(raw, "resources"):
        resources = raw.resources or []
    elif isinstance(raw, list):
        resources = raw

    result: list[ModelInfo] = []
    for item in resources:
        try:
            if isinstance(item, dict):
                model_id = item.get("model_id", "")
                label = item.get("label", model_id)
                task_ids: list[str] = []
                tasks = item.get("task_ids", []) or []
                if isinstance(tasks, list):
                    task_ids = [str(t) for t in tasks]
            else:
                model_id = str(getattr(item, "model_id", ""))
                label = str(getattr(item, "label", model_id))
                raw_tasks = getattr(item, "task_ids", []) or []
                task_ids = [str(t) for t in raw_tasks]

            if not model_id:
                continue

            result.append(ModelInfo(
                model_id=model_id,
                label=label,
                task_ids=task_ids,
            ))
        except Exception as exc:
            logger.debug("model_discovery: skipping malformed resource entry (%s)", type(exc).__name__)
            continue

    return result
