"""
RouteWise AI – Tests: WatsonxService diagnostics
==================================================
Unit tests for:
  - _classify_sdk_exception()  — maps exception types to diagnostic codes
  - _safe_reason()             — extracts IBM reason attribute safely
  - _extract_ibm_code()        — pulls IBM error IDs from reason strings
  - _safe_status_code()        — reads HTTP status from exception attributes
  - WatsonxError.diag_code     — exception carries diagnostic code
  - ConnectionTestResult.diag_code — result carries diagnostic code
  - test_connection() diagnostic codes via mocked generate()

No live IBM credentials or network connectivity required.
Live integration tests are in tests/test_integration.py (guarded).
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ─── Helpers ────────────────────────────────────────────────────────────────

def _make_exc(cls_name: str, status: int = None, reason: str = None):
    """
    Fabricate an exception whose class __name__ matches cls_name.
    Optionally attach a .response.status_code and/or .reason attribute.

    We create a fresh subclass of Exception with the desired name so that
    type(exc).__name__ == cls_name, which is exactly how _classify_sdk_exception
    dispatches.
    """
    # Build a fresh subclass each call so __name__ is exactly cls_name
    FakeClass = type(cls_name, (Exception,), {})
    exc = FakeClass("stub error")
    if status is not None:
        resp = MagicMock()
        resp.status_code = status
        exc.response = resp
    if reason is not None:
        exc.reason = reason
    return exc


# ─── _classify_sdk_exception ────────────────────────────────────────────────

class TestClassifySDKException:
    """Each IBM SDK exception class name maps to the correct diagnostic code."""

    def _classify(self, exc):
        from services.watsonx_service import _classify_sdk_exception
        code, msg = _classify_sdk_exception(exc)
        return code, msg

    # IBM SDK typed exceptions
    def test_authentication_error(self):
        code, msg = self._classify(_make_exc("AuthenticationError"))
        assert code == "AUTH_FAILED"
        assert "API key" in msg or "authentication" in msg.lower()

    def test_invalid_credentials_error(self):
        code, msg = self._classify(_make_exc("InvalidCredentialsError"))
        assert code == "AUTH_FAILED"
        assert "credential" in msg.lower() or "key" in msg.lower()

    def test_no_wml_credentials_provided(self):
        code, msg = self._classify(_make_exc("NoWMLCredentialsProvided"))
        assert code == "MISSING_CREDENTIALS"

    def test_cannot_set_project_or_space_no_reason(self):
        code, msg = self._classify(_make_exc("CannotSetProjectOrSpace"))
        assert code == "PROJECT_NOT_FOUND"
        assert "project" in msg.lower()

    def test_cannot_set_project_with_ibm_code_in_reason(self):
        exc = _make_exc("CannotSetProjectOrSpace",
                         reason='{"id":"WSCPA404PE","code":404}')
        code, msg = self._classify(exc)
        assert code == "PROJECT_NOT_FOUND"
        assert "WSCPA404PE" in msg

    def test_missing_foundation_model(self):
        code, msg = self._classify(_make_exc("MissingFoundationModel"))
        assert code == "MODEL_NOT_FOUND"
        assert "model" in msg.lower()

    def test_forbidden_action_for_plan(self):
        code, msg = self._classify(_make_exc("ForbiddenActionForPlan"))
        assert code == "PERMISSION_DENIED"
        assert "403" in msg or "plan" in msg.lower() or "permission" in msg.lower()

    def test_exceeded_limit_of_api_calls(self):
        code, msg = self._classify(_make_exc("ExceededLimitOfAPICalls"))
        assert code == "RATE_LIMIT"
        assert "quota" in msg.lower() or "limit" in msg.lower()

    # WMLClientError / ApiRequestFailure via HTTP status
    def test_wml_client_error_401(self):
        code, msg = self._classify(_make_exc("WMLClientError", status=401))
        assert code == "AUTH_FAILED"
        assert "401" in msg

    def test_wml_client_error_403(self):
        code, msg = self._classify(_make_exc("WMLClientError", status=403))
        assert code == "PERMISSION_DENIED"
        assert "403" in msg

    def test_api_request_failure_404(self):
        code, msg = self._classify(_make_exc("ApiRequestFailure", status=404))
        assert code == "PROJECT_NOT_FOUND"
        assert "404" in msg

    def test_api_request_failure_429(self):
        code, msg = self._classify(_make_exc("ApiRequestFailure", status=429))
        assert code == "RATE_LIMIT"
        assert "429" in msg

    def test_api_request_failure_500(self):
        code, msg = self._classify(_make_exc("ApiRequestFailure", status=500))
        assert code == "REGION_OR_ENDPOINT_ERROR"
        assert "500" in msg

    def test_api_request_failure_503(self):
        code, msg = self._classify(_make_exc("ApiRequestFailure", status=503))
        assert code == "REGION_OR_ENDPOINT_ERROR"
        assert "503" in msg

    # Network / timeout exceptions
    def test_connect_timeout(self):
        code, msg = self._classify(_make_exc("ConnectTimeout"))
        assert code == "NETWORK_TIMEOUT"
        assert "timeout" in msg.lower() or "timed out" in msg.lower()

    def test_read_timeout(self):
        code, msg = self._classify(_make_exc("ReadTimeout"))
        assert code == "NETWORK_TIMEOUT"

    def test_connection_error(self):
        code, msg = self._classify(_make_exc("ConnectionError"))
        assert code == "NETWORK_ERROR"

    def test_connect_error(self):
        code, msg = self._classify(_make_exc("ConnectError"))
        assert code == "NETWORK_ERROR"

    def test_ssl_error(self):
        code, msg = self._classify(_make_exc("SSLError"))
        assert code == "NETWORK_ERROR"
        assert "SSL" in msg or "certificate" in msg.lower()

    # Unknown exception falls back to UNKNOWN_ERROR
    def test_unknown_exception_returns_unknown_code(self):
        code, msg = self._classify(_make_exc("SomeFutureSDKException"))
        assert code == "UNKNOWN_ERROR"
        assert "SomeFutureSDKException" in msg

    # Return type contract
    def test_returns_tuple_of_strings(self):
        code, msg = self._classify(_make_exc("AuthenticationError"))
        assert isinstance(code, str)
        assert isinstance(msg, str)
        assert len(msg) > 10

    def test_message_never_contains_apikey_literal(self):
        """Messages must never suggest logging or showing actual key values."""
        from services.watsonx_service import _classify_sdk_exception
        for cls_name in (
            "AuthenticationError", "CannotSetProjectOrSpace",
            "InvalidCredentialsError", "ApiRequestFailure",
        ):
            _, msg = _classify_sdk_exception(_make_exc(cls_name, status=401))
            assert "api_key" not in msg.lower() or "WATSONX_API_KEY" in msg, (
                f"{cls_name}: message should not mention raw key value"
            )


# ─── _safe_reason ────────────────────────────────────────────────────────────

class TestSafeReason:
    def test_none_reason_returns_empty(self):
        from services.watsonx_service import _safe_reason
        exc = Exception("test")
        assert _safe_reason(exc) == ""

    def test_string_reason_returned_safely(self):
        from services.watsonx_service import _safe_reason
        exc = Exception("test")
        exc.reason = '{"id":"WSCPA404PE","code":404}'
        result = _safe_reason(exc)
        assert "WSCPA404PE" in result

    def test_dict_reason_extracts_id(self):
        from services.watsonx_service import _safe_reason
        exc = Exception("test")
        exc.reason = {"id": "SOMEIBMCODE", "code": 404}
        result = _safe_reason(exc)
        assert "SOMEIBMCODE" in result

    def test_long_reason_truncated_to_200(self):
        from services.watsonx_service import _safe_reason
        exc = Exception("test")
        exc.reason = "X" * 500
        result = _safe_reason(exc)
        assert len(result) <= 200


# ─── _extract_ibm_code ───────────────────────────────────────────────────────

class TestExtractIBMCode:
    def test_extracts_code_from_json_id_field(self):
        from services.watsonx_service import _extract_ibm_code
        assert _extract_ibm_code('{"id":"WSCPA404PE","code":404}') == "WSCPA404PE"

    def test_returns_empty_when_no_code(self):
        from services.watsonx_service import _extract_ibm_code
        assert _extract_ibm_code("some plain text error") == ""

    def test_returns_empty_on_empty_string(self):
        from services.watsonx_service import _extract_ibm_code
        assert _extract_ibm_code("") == ""

    def test_extracts_bare_code_pattern(self):
        from services.watsonx_service import _extract_ibm_code
        result = _extract_ibm_code("ERRCODE404 something went wrong")
        assert result != ""  # at minimum finds something


# ─── _safe_status_code ───────────────────────────────────────────────────────

class TestSafeStatusCode:
    def test_returns_none_when_no_response(self):
        from services.watsonx_service import _safe_status_code
        exc = Exception("no response")
        assert _safe_status_code(exc) is None

    def test_returns_status_code_from_response(self):
        from services.watsonx_service import _safe_status_code
        exc = _make_exc("ApiRequestFailure", status=404)
        assert _safe_status_code(exc) == 404

    def test_returns_none_when_status_not_int(self):
        from services.watsonx_service import _safe_status_code
        exc = Exception("test")
        resp = MagicMock()
        resp.status_code = "404"  # string, not int
        exc.response = resp
        assert _safe_status_code(exc) is None


# ─── WatsonxError carries diag_code ─────────────────────────────────────────

class TestWatsonxErrorDiagCode:
    def test_default_diag_code(self):
        from services.watsonx_service import WatsonxError
        err = WatsonxError("something broke")
        assert err.diag_code == "UNKNOWN_ERROR"

    def test_explicit_diag_code(self):
        from services.watsonx_service import WatsonxError
        err = WatsonxError("auth failed", diag_code="AUTH_FAILED")
        assert err.diag_code == "AUTH_FAILED"
        assert str(err) == "auth failed"

    def test_project_not_found_code(self):
        from services.watsonx_service import WatsonxError
        err = WatsonxError("project missing", diag_code="PROJECT_NOT_FOUND")
        assert err.diag_code == "PROJECT_NOT_FOUND"


# ─── ConnectionTestResult carries diag_code ─────────────────────────────────

class TestConnectionTestResultDiagCode:
    def test_success_result(self):
        from services.watsonx_service import ConnectionTestResult
        r = ConnectionTestResult(
            success=True, model_id="ibm/granite-4-h-small",
            message="ok", response_preview="hello", diag_code="OK",
        )
        assert r.success is True
        assert r.diag_code == "OK"

    def test_failure_result_carries_code(self):
        from services.watsonx_service import ConnectionTestResult
        r = ConnectionTestResult(
            success=False, model_id="ibm/granite-4-h-small",
            message="project not found", diag_code="PROJECT_NOT_FOUND",
        )
        assert r.success is False
        assert r.diag_code == "PROJECT_NOT_FOUND"

    def test_default_diag_code_is_empty_string(self):
        from services.watsonx_service import ConnectionTestResult
        r = ConnectionTestResult(
            success=False, model_id="ibm/granite-4-h-small", message="x"
        )
        assert r.diag_code == ""


# ─── test_connection() returns correct diag_code ────────────────────────────

class TestTestConnectionDiagCodes:
    """
    test_connection() should surface the correct diag_code for each failure mode.
    All IBM interactions are fully mocked.
    """

    def _make_svc_with_error(self, exc):
        """Return a WatsonxService whose generate() raises exc."""
        from services.watsonx_service import WatsonxService
        svc = WatsonxService()
        svc._client = MagicMock()
        svc._model = MagicMock()
        svc._model.generate.side_effect = exc
        return svc

    def test_project_not_found_propagates_to_result(self):
        """CannotSetProjectOrSpace → diag_code=PROJECT_NOT_FOUND in result."""
        from services.watsonx_service import WatsonxService, WatsonxError
        svc = WatsonxService()
        # Simulate _ensure_client raising with correct code
        svc.generate = MagicMock(
            side_effect=WatsonxError("project missing", diag_code="PROJECT_NOT_FOUND")
        )
        result = svc.test_connection()
        assert result.success is False
        assert result.diag_code == "PROJECT_NOT_FOUND"
        assert "project" in result.message.lower()

    def test_auth_failed_propagates_to_result(self):
        from services.watsonx_service import WatsonxService, WatsonxError
        svc = WatsonxService()
        svc.generate = MagicMock(
            side_effect=WatsonxError("auth failed", diag_code="AUTH_FAILED")
        )
        result = svc.test_connection()
        assert result.success is False
        assert result.diag_code == "AUTH_FAILED"

    def test_rate_limit_propagates_to_result(self):
        from services.watsonx_service import WatsonxService, WatsonxError
        svc = WatsonxService()
        svc.generate = MagicMock(
            side_effect=WatsonxError("too many requests", diag_code="RATE_LIMIT")
        )
        result = svc.test_connection()
        assert result.success is False
        assert result.diag_code == "RATE_LIMIT"

    def test_model_not_found_propagates_to_result(self):
        from services.watsonx_service import WatsonxService, WatsonxError
        svc = WatsonxService()
        svc.generate = MagicMock(
            side_effect=WatsonxError("model missing", diag_code="MODEL_NOT_FOUND")
        )
        result = svc.test_connection()
        assert result.success is False
        assert result.diag_code == "MODEL_NOT_FOUND"

    def test_missing_credentials_from_config_error(self):
        from services.watsonx_service import WatsonxService, ConfigError
        svc = WatsonxService()
        svc.generate = MagicMock(
            side_effect=ConfigError("WATSONX_API_KEY missing")
        )
        result = svc.test_connection()
        assert result.success is False
        assert result.diag_code == "MISSING_CREDENTIALS"

    def test_success_has_ok_code(self):
        from services.watsonx_service import WatsonxService, GenerationResult
        svc = WatsonxService()
        svc.generate = MagicMock(
            return_value=GenerationResult(
                text="Connection OK", input_tokens=5, output_tokens=3,
                model_id="ibm/granite-4-h-small",
            )
        )
        result = svc.test_connection()
        assert result.success is True
        assert result.diag_code == "OK"
        assert result.response_preview == "Connection OK"

    def test_unexpected_exception_returns_unknown_code(self):
        from services.watsonx_service import WatsonxService
        svc = WatsonxService()
        svc.generate = MagicMock(side_effect=RuntimeError("unexpected"))
        result = svc.test_connection()
        assert result.success is False
        # UNKNOWN_ERROR or a classified code — must not be empty
        assert result.diag_code != ""
        assert result.message != ""
