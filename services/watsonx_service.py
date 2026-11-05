"""
RouteWise AI – IBM watsonx.ai Service
=======================================
Handles authentication, inference via the ibm-watsonx-ai SDK, connection
testing with rich diagnostic classification, and safe error handling.

SECURITY: API keys, IAM tokens, credential objects and raw response bodies
that may contain sensitive headers are NEVER logged or surfaced to the UI.
Only safe IBM error codes and sanitized human-readable messages are exposed.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

import config

logger = logging.getLogger("routewise.watsonx")

# ─── Token cache (module-level singleton) ───────────────────────────────────

_token_cache: dict[str, Any] = {
    "token": None,
    "expiry": 0.0,
}

_TOKEN_REFRESH_BUFFER_SECS = 300  # refresh 5 min before actual expiry


# ─── SDK import (graceful fallback) ─────────────────────────────────────────

def _get_sdk():
    """Return the ibm_watsonx_ai module or raise ImportError with guidance."""
    try:
        from ibm_watsonx_ai import APIClient, Credentials  # type: ignore
        return APIClient, Credentials
    except ImportError as exc:
        raise ImportError(
            "ibm-watsonx-ai SDK is not installed. "
            "Run: pip install ibm-watsonx-ai"
        ) from exc


# ─── Diagnostic classifier ───────────────────────────────────────────────────

# Maps IBM SDK exception class names (and HTTP status codes) to structured
# DiagnosticInfo.  We match by class name string rather than by import to
# keep this module importable even when the SDK is absent.

_DIAG_NO_SDK = "SDK_NOT_INSTALLED"
_DIAG_MISSING_CONFIG = "MISSING_CREDENTIALS"
_DIAG_AUTH_FAILED = "AUTH_FAILED"
_DIAG_FORBIDDEN = "PERMISSION_DENIED"
_DIAG_PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
_DIAG_MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
_DIAG_RATE_LIMIT = "RATE_LIMIT"
_DIAG_REGION_ENDPOINT = "REGION_OR_ENDPOINT_ERROR"
_DIAG_TIMEOUT = "NETWORK_TIMEOUT"
_DIAG_NETWORK = "NETWORK_ERROR"
_DIAG_UNKNOWN = "UNKNOWN_ERROR"


def _classify_sdk_exception(exc: Exception) -> tuple[str, str]:
    """
    Classify an IBM SDK (or network) exception into a (diag_code, user_message) pair.

    Rules:
    - Only the exception *class name*, safe IBM error codes, and HTTP status
      codes are examined — never the raw exception message text (which may
      contain credential fragments).
    - Returns a diagnostic code constant and a safe, actionable user message.
    """
    cls_name = type(exc).__name__

    # ── IBM SDK typed exceptions ─────────────────────────────────────────────
    if cls_name == "AuthenticationError":
        return (
            _DIAG_AUTH_FAILED,
            "IBM IAM authentication failed (401). "
            "Your API key may be invalid, expired, or revoked. "
            "Generate a new key at cloud.ibm.com/iam/apikeys.",
        )

    if cls_name == "InvalidCredentialsError":
        return (
            _DIAG_AUTH_FAILED,
            "IBM credentials were rejected. "
            "Check that WATSONX_API_KEY is a valid IBM Cloud API key (not a Watson Studio token).",
        )

    if cls_name == "NoWMLCredentialsProvided":
        return (
            _DIAG_MISSING_CONFIG,
            "No IBM watsonx.ai credentials were provided to the SDK. "
            "Ensure WATSONX_API_KEY and WATSONX_PROJECT_ID are set.",
        )

    if cls_name == "CannotSetProjectOrSpace":
        # Extract IBM error id from the 'reason' attribute if available — safe to log
        reason_str = _safe_reason(exc)
        ibm_code = _extract_ibm_code(reason_str)
        code_hint = f" (IBM code: {ibm_code})" if ibm_code else ""
        return (
            _DIAG_PROJECT_NOT_FOUND,
            f"The watsonx.ai project was not found (404{code_hint}). "
            "Verify that WATSONX_PROJECT_ID is correct and that the project exists in your "
            "IBM Cloud account and region. "
            "Find it at dataplatform.cloud.ibm.com → your project → Manage → General.",
        )

    if cls_name == "MissingFoundationModel":
        return (
            _DIAG_MODEL_NOT_FOUND,
            f"Model '{config.WATSONX_MODEL_ID}' is not available in your watsonx.ai project or region. "
            "Verify the model ID and ensure it is enabled for your account. "
            "Check available models at dataplatform.cloud.ibm.com.",
        )

    if cls_name == "ForbiddenActionForPlan":
        return (
            _DIAG_FORBIDDEN,
            "Your IBM Cloud plan does not permit this action (403). "
            "Upgrade your watsonx.ai plan or check service entitlements at cloud.ibm.com.",
        )

    if cls_name == "ExceededLimitOfAPICalls":
        return (
            _DIAG_RATE_LIMIT,
            "IBM watsonx.ai API quota or rate limit exceeded. "
            "Wait a few minutes before retrying, or check your usage at cloud.ibm.com.",
        )

    if cls_name in ("WMLClientError", "ApiRequestFailure"):
        # Inspect HTTP status code where available without logging body content
        status = _safe_status_code(exc)
        return _classify_by_status(status, exc)

    # ── Network / timeout errors ─────────────────────────────────────────────
    if cls_name in ("ConnectTimeout", "ReadTimeout", "Timeout",
                    "TimeoutError", "asyncio.TimeoutError"):
        return (
            _DIAG_TIMEOUT,
            f"Connection to IBM watsonx.ai timed out ({config.REQUEST_TIMEOUT}s). "
            "Check your internet connection or increase REQUEST_TIMEOUT in .env.",
        )

    if cls_name in ("ConnectionError", "ConnectError", "NetworkError",
                    "OSError", "gaierror"):
        return (
            _DIAG_NETWORK,
            "Could not reach IBM watsonx.ai. "
            f"Verify your internet connection and that the endpoint "
            f"'{config.WATSONX_URL}' is reachable.",
        )

    # ── SSL ──────────────────────────────────────────────────────────────────
    if "SSL" in cls_name or "ssl" in cls_name.lower():
        return (
            _DIAG_NETWORK,
            "SSL/TLS error connecting to IBM watsonx.ai. "
            "Ensure your system certificates (certifi) are up to date.",
        )

    # ── Fall-through: use HTTP status if present ─────────────────────────────
    status = _safe_status_code(exc)
    if status:
        return _classify_by_status(status, exc)

    return (
        _DIAG_UNKNOWN,
        f"An unexpected IBM watsonx.ai error occurred ({cls_name}). "
        "Check application logs for details.",
    )


def _classify_by_status(status: Optional[int], exc: Exception) -> tuple[str, str]:
    """Map HTTP status code to a diagnostic pair."""
    cls_name = type(exc).__name__
    if status == 401:
        return (
            _DIAG_AUTH_FAILED,
            "IBM authentication returned 401 Unauthorized. "
            "Your API key may be invalid, expired, or from the wrong IBM Cloud account.",
        )
    if status == 403:
        return (
            _DIAG_FORBIDDEN,
            "IBM watsonx.ai returned 403 Forbidden. "
            "Your account may lack the required permissions or service entitlement.",
        )
    if status == 404:
        return (
            _DIAG_PROJECT_NOT_FOUND,
            "IBM watsonx.ai returned 404 Not Found. "
            "The project ID, model ID, or endpoint URL may be incorrect. "
            "Verify all three values in your .env file.",
        )
    if status == 429:
        return (
            _DIAG_RATE_LIMIT,
            "IBM watsonx.ai rate limit reached (429 Too Many Requests). "
            "Wait a few minutes before retrying.",
        )
    if status and status >= 500:
        return (
            _DIAG_REGION_ENDPOINT,
            f"IBM watsonx.ai returned a server error ({status}). "
            "This may be a temporary service issue or an incorrect regional endpoint. "
            f"Current endpoint: {config.WATSONX_URL}",
        )
    return (
        _DIAG_UNKNOWN,
        f"IBM watsonx.ai request failed ({cls_name}"
        + (f", HTTP {status}" if status else "")
        + "). Check application logs.",
    )


def _safe_reason(exc: Exception) -> str:
    """Extract the IBM error 'reason' attribute safely — never exposes secrets."""
    reason = getattr(exc, "reason", None)
    if reason is None:
        return ""
    # reason can be a string JSON blob or a dict; keep it short and safe
    try:
        if isinstance(reason, dict):
            return str(reason.get("id", "") or reason.get("code", ""))
        s = str(reason)
        # Only return first 200 chars to avoid leaking large bodies
        return s[:200]
    except Exception:
        return ""


def _extract_ibm_code(reason_str: str) -> str:
    """Pull the IBM error id (e.g. WSCPA404PE) from a reason string, if present."""
    import re
    match = re.search(r'"id"\s*:\s*"([A-Z0-9]+)"', reason_str)
    if match:
        return match.group(1)
    # Fallback: look for a bare code at the start
    match = re.search(r'\b([A-Z]{4,}[0-9]{3,}[A-Z]{0,4})\b', reason_str)
    if match:
        return match.group(1)
    return ""


def _safe_status_code(exc: Exception) -> Optional[int]:
    """Extract HTTP status code from exception attributes without logging body."""
    # ibm_watsonx_ai ApiRequestFailure stores a response object
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code
    return None


# ─── WatsonxService ─────────────────────────────────────────────────────────

class WatsonxService:
    """
    Thread-safe wrapper around the ibm-watsonx-ai SDK.
    Instantiated once and cached on the Streamlit session via get_watsonx_service().
    """

    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._model: Optional[Any] = None
        self._last_init_error: Optional[str] = None

    # ── Initialisation ──────────────────────────────────────────────────────

    def _ensure_client(self) -> None:
        """
        Lazily initialise the API client.
        Raises ConfigError for missing credentials.
        Raises WatsonxError (with a diagnostic code) for SDK / network failures.
        Never logs or exposes API keys or token values.
        """
        if self._client is not None:
            return

        cfg = config.validate_config()
        if not cfg.is_ready:
            raise ConfigError(cfg.summary)

        try:
            APIClient, Credentials = _get_sdk()
            creds = Credentials(
                url=config.WATSONX_URL,
                api_key=config.WATSONX_API_KEY,
            )
            self._client = APIClient(credentials=creds, project_id=config.WATSONX_PROJECT_ID)
            logger.info("IBM watsonx.ai client initialised (endpoint: %s)", config.WATSONX_URL)
        except ImportError as exc:
            raise ConfigError(str(exc)) from exc
        except Exception as exc:
            diag_code, user_msg = _classify_sdk_exception(exc)
            # Log only: exception class, diagnostic code, IBM error code if present
            reason_str = _safe_reason(exc)
            ibm_code = _extract_ibm_code(reason_str)
            logger.error(
                "IBM watsonx.ai client init failed. "
                "exc_class=%s diag=%s ibm_code=%s endpoint=%s",
                type(exc).__name__, diag_code, ibm_code or "n/a", config.WATSONX_URL,
            )
            raise WatsonxError(user_msg, diag_code=diag_code) from exc

    def _get_model(self) -> Any:
        """Return cached ModelInference instance."""
        if self._model is not None:
            return self._model

        self._ensure_client()
        try:
            from ibm_watsonx_ai.foundation_models import ModelInference  # type: ignore
        except ImportError as exc:
            raise ConfigError("ibm-watsonx-ai SDK not available.") from exc

        try:
            # Keep generation parameters on each chat request. Passing legacy
            # text-generation parameters into the constructor can cause them to
            # leak into or conflict with chat inference.
            self._model = ModelInference(
                model_id=config.WATSONX_MODEL_ID,
                api_client=self._client,
                project_id=config.WATSONX_PROJECT_ID,
            )
            logger.info("ModelInference ready (model: %s)", config.WATSONX_MODEL_ID)
        except Exception as exc:
            diag_code, user_msg = _classify_sdk_exception(exc)
            logger.error(
                "ModelInference init failed. exc_class=%s diag=%s model=%s",
                type(exc).__name__, diag_code, config.WATSONX_MODEL_ID,
            )
            raise WatsonxError(user_msg, diag_code=diag_code) from exc

        return self._model

    # ── Public API ───────────────────────────────────────────────────────────

    @staticmethod
    def _extract_chat_response(response: Any) -> tuple[str, int, int]:
        """Extract assistant text and token usage from watsonx chat responses."""
        text = ""
        input_tokens = 0
        output_tokens = 0

        def content_to_text(content: Any) -> str:
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        value = item.get("text")
                        if value:
                            parts.append(str(value))
                return "\\n".join(parts)
            if isinstance(content, dict):
                return str(content.get("text", ""))
            return ""

        if isinstance(response, dict):
            choices = response.get("choices") or []
            if choices:
                choice = choices[0] or {}
                message = choice.get("message", {}) if isinstance(choice, dict) else {}
                text = content_to_text(message.get("content", "")) if isinstance(message, dict) else ""
            usage = response.get("usage") or {}
            if isinstance(usage, dict):
                input_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
                output_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
        else:
            choices = getattr(response, "choices", None) or []
            if choices:
                choice = choices[0]
                message = getattr(choice, "message", None)
                content = getattr(message, "content", "") if message is not None else ""
                text = content_to_text(content)
            usage = getattr(response, "usage", None)
            if usage is not None:
                input_tokens = int(getattr(usage, "prompt_tokens", getattr(usage, "input_tokens", 0)) or 0)
                output_tokens = int(getattr(usage, "completion_tokens", getattr(usage, "output_tokens", 0)) or 0)

        return text.strip(), input_tokens, output_tokens

    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> GenerationResult:
        """
        Generate a response through the supported watsonx chat API.

        Granite 4H Small is a chat/instruct model. Use ModelInference.chat()
        (the /ml/v1/text/chat endpoint) rather than the deprecated text
        generation endpoint. This also prevents generation-only parameters
        from accidentally overriding the model's configured defaults.
        """
        if len(prompt) > config.MAX_PROMPT_CHARS * 3:
            raise ValueError(
                f"Prompt exceeds maximum allowed size ({config.MAX_PROMPT_CHARS * 3} chars)."
            )

        model = self._get_model()
        chat_method = getattr(model, "chat", None)
        if not callable(chat_method):
            raise WatsonxError(
                "The installed ibm-watsonx-ai SDK does not expose the chat inference method. "
                "Upgrade it with: pip install --upgrade ibm-watsonx-ai",
                diag_code=_DIAG_NO_SDK,
            )

        resolved_max_tokens = max_tokens if max_tokens is not None else config.MAX_NEW_TOKENS
        resolved_temperature = temperature if temperature is not None else config.MODEL_TEMPERATURE
        params = {
            "max_tokens": int(resolved_max_tokens),
            "temperature": float(resolved_temperature),
        }
        messages = [{"role": "user", "content": prompt}]

        for attempt in range(1, 4):
            try:
                response = chat_method(messages=messages, params=params)
                text, input_tokens, output_tokens = self._extract_chat_response(response)

                logger.info(
                    "Granite chat generation: input_tokens=%d output_tokens=%d",
                    input_tokens, output_tokens,
                )

                if not text:
                    raise WatsonxError(
                        "IBM Granite returned an empty chat response. "
                        "Check the model's generation parameters and retry.",
                        diag_code=_DIAG_UNKNOWN,
                    )

                return GenerationResult(
                    text=text,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model_id=config.WATSONX_MODEL_ID,
                )

            except WatsonxError:
                raise
            except Exception as exc:
                diag_code, user_msg = _classify_sdk_exception(exc)
                if diag_code == _DIAG_RATE_LIMIT and attempt < 3:
                    wait = 2 ** attempt
                    logger.warning(
                        "Rate limit / transient error (attempt %d/3); retrying in %ds. exc_class=%s",
                        attempt, wait, type(exc).__name__,
                    )
                    time.sleep(wait)
                    continue
                logger.error(
                    "IBM Granite chat inference failed (attempt %d). exc_class=%s diag=%s",
                    attempt, type(exc).__name__, diag_code,
                )
                raise WatsonxError(user_msg, diag_code=diag_code) from exc

        raise WatsonxError(
            "IBM Granite chat inference failed after 3 attempts. Check credentials, endpoint and rate limits.",
            diag_code=_DIAG_UNKNOWN,
        )

    def test_connection(self) -> ConnectionTestResult:
        """
        Send a minimal probe request to verify end-to-end connectivity.

        Stages tested:
          1. Config check (credentials present)
          2. Client init (IAM auth + project lookup)
          3. ModelInference init (model availability)
          4. Generate call (live inference)

        Returns a ConnectionTestResult with a diagnostic code and
        an actionable user message.  Never raises exceptions.
        """
        try:
            result = self.generate("Say: Connection OK", max_tokens=10)
            return ConnectionTestResult(
                success=True,
                model_id=config.WATSONX_MODEL_ID,
                message="Connected successfully to IBM Granite.",
                response_preview=result.text[:80],
                diag_code="OK",
            )
        except ConfigError as exc:
            return ConnectionTestResult(
                success=False,
                model_id=config.WATSONX_MODEL_ID,
                message=str(exc),
                diag_code=_DIAG_MISSING_CONFIG,
            )
        except WatsonxError as exc:
            return ConnectionTestResult(
                success=False,
                model_id=config.WATSONX_MODEL_ID,
                message=str(exc),
                diag_code=exc.diag_code,
            )
        except Exception as exc:
            diag_code, user_msg = _classify_sdk_exception(exc)
            logger.error(
                "Unexpected error in test_connection. exc_class=%s diag=%s",
                type(exc).__name__, diag_code,
            )
            return ConnectionTestResult(
                success=False,
                model_id=config.WATSONX_MODEL_ID,
                message=user_msg,
                diag_code=diag_code,
            )

    def reset(self) -> None:
        """Force re-initialisation on next call (e.g., after credentials change)."""
        self._client = None
        self._model = None


# ─── Result types ────────────────────────────────────────────────────────────

class GenerationResult:
    __slots__ = ("text", "input_tokens", "output_tokens", "model_id")

    def __init__(self, text: str, input_tokens: int, output_tokens: int, model_id: str) -> None:
        self.text = text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model_id = model_id

    def __repr__(self) -> str:  # pragma: no cover
        return f"<GenerationResult tokens={self.output_tokens} model={self.model_id}>"


class ConnectionTestResult:
    __slots__ = ("success", "model_id", "message", "response_preview", "diag_code")

    def __init__(
        self,
        success: bool,
        model_id: str,
        message: str,
        response_preview: str = "",
        diag_code: str = "",
    ) -> None:
        self.success = success
        self.model_id = model_id
        self.message = message
        self.response_preview = response_preview
        self.diag_code = diag_code


# ─── Exceptions ──────────────────────────────────────────────────────────────

class WatsonxError(Exception):
    """Raised for IBM watsonx.ai inference or connectivity errors."""

    def __init__(self, message: str, diag_code: str = _DIAG_UNKNOWN) -> None:
        super().__init__(message)
        self.diag_code = diag_code


class ConfigError(Exception):
    """Raised when required configuration is missing."""


# ─── Streamlit-cached singleton ──────────────────────────────────────────────

# st.cache_resource keeps a single WatsonxService instance alive across
# Streamlit reruns without re-initialising the SDK client on every page load.
# Falls back to a module-level singleton when running outside Streamlit
# (e.g., pytest, CLI scripts).

_service_instance: Optional[WatsonxService] = None


def _make_service() -> WatsonxService:
    """Factory – always creates a fresh instance."""
    return WatsonxService()


def get_watsonx_service() -> WatsonxService:
    """
    Return a cached WatsonxService singleton.

    Inside a Streamlit session the instance is cached with
    @st.cache_resource so the SDK client is initialised only once per
    deployment.  Outside Streamlit (tests, CLI) a plain module-level
    singleton is used instead.
    """
    try:
        import streamlit as st

        # Wrap factory in cache_resource at call time so the decorator is
        # applied exactly once.  Streamlit raises no error if called outside
        # a session context – it just returns the uncached value.
        cached_factory = st.cache_resource(_make_service)
        return cached_factory()
    except Exception:
        # Outside Streamlit or st.cache_resource not available
        global _service_instance
        if _service_instance is None:
            _service_instance = WatsonxService()
        return _service_instance
