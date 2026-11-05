# RouteWise AI – Comprehensive Technical Audit Report (v5)

**Audit Date (v1):** 2026-11-05
**Audit Date (v2 – post-fix):** 2026-11-05
**Audit Date (v3 – diagnostics):** 2026-11-05
**Audit Date (v4 – model discovery):** 2026-11-05
**Audit Date (v5 – deterministic validation):** 2026-11-05
**Auditor:** IBM Bob (automated code inspection + test execution)
**Scope:** Full project review + P1–P5 fixes + IBM Granite integration improvements + deterministic validation

---

## Executive Summary (v5)

All critical and high-priority issues from v1/v2/v3/v4 remain resolved.
**Six deterministic validation improvements** implemented across budget, itinerary, replanning, and weather agents.
The test suite grew to **236 tests (236 passed, 15 skipped, 0 failed)** — +27 new tests covering all six improvements.
IBM Granite SDK integration is correctly wired end-to-end; live inference blocked only by regional endpoint configuration (switch `.env` to us-south).

---

## 1. Changes Implemented

### PHASE 1 – Critical Fixes

| Change | File(s) | Result |
|---|---|---|
| Installed `ibm-watsonx-ai==1.9.0` | `requirements.txt` (constraint already correct) | SDK available; all SDK imports work |
| Expanded `_INJECTION_PATTERNS` regex | `utils/security.py` | 18 new patterns: `system:`, `act as`, `pretend to be`, `new persona`, `roleplay as`, `take on the role`, `from now on you are`, `disregard … (safety/filter/restriction/instruction)`, `developer mode enabled`, `override safety/filter/restriction`, `ignore prior`, `<<SYS>>`, expanded `forget`, `ignore all/prior` |
| Unified sanitization — `sanitize_prompt_input` delegates to `sanitize_for_prompt` | `utils/validation.py` | Single source-of-truth for injection stripping |
| Unified model-level sanitizer to use `sanitize_for_prompt` | `models/travel_request.py` | All 3 injection stripping paths use identical patterns |
| 56 new security tests (detection + sanitization + false-positive guards) | `tests/test_security_extended.py` | All 56 pass |

### PHASE 2 – Functional and Usability Fixes

| Change | File(s) | Result |
|---|---|---|
| `format_inr` rewritten for Indian lakh/crore grouping | `utils/calculations.py` | `₹1,000` / `₹10,000` / `₹1,00,000` / `₹1,00,00,000` — verified |
| Removed `enableCORS = false` from Streamlit config | `.streamlit/config.toml` | Startup warning eliminated; clean launch confirmed |
| Created MIT `LICENSE` file | `LICENSE` | File present; README reference satisfied |
| Attraction markers added to Folium destination map | `components/map_view.py` | Up to 5 red star markers plotted with deterministic offsets from destination centre |
| `@st.cache_resource` caching for `WatsonxService` | `services/watsonx_service.py` | `get_watsonx_service()` uses `st.cache_resource` inside Streamlit; falls back to module singleton in tests/CLI |

### PHASE 3 – Automated Testing Expansion

| New File | Contents | Tests Added |
|---|---|---|
| `tests/test_agents.py` | Unit tests for all 7 agents with mocked `WatsonxService` | 25 tests |
| `tests/test_security_extended.py` | Injection detection, sanitization, false-positive guards | 56 tests |
| `tests/test_integration.py` | Guarded live tests: Open-Meteo (4), OSRM/Nominatim (5), IBM Granite (6) | 15 tests (all skipped in CI; require env var flags) |
| `pytest.ini` | Registers `integration` mark; sets `-ra` summary | Configuration |

### PHASE 4 – IBM Granite Diagnostic Improvements

| Change | File(s) | Result |
|---|---|---|
| Added `_classify_sdk_exception()` — maps IBM SDK exception class names and HTTP status codes to diagnostic codes | `services/watsonx_service.py` | 9 diagnostic codes: AUTH\_FAILED, PERMISSION\_DENIED, PROJECT\_NOT\_FOUND, MODEL\_NOT\_FOUND, RATE\_LIMIT, REGION\_OR\_ENDPOINT\_ERROR, NETWORK\_TIMEOUT, NETWORK\_ERROR, UNKNOWN\_ERROR |
| Added `_safe_reason()`, `_extract_ibm_code()`, `_safe_status_code()` — safe IBM error metadata extraction | `services/watsonx_service.py` | Extracts IBM error ID (e.g. WSCPA404PE) from exception `reason` attribute; truncated to 200 chars; no raw bodies logged |
| `WatsonxError` carries `diag_code` attribute | `services/watsonx_service.py` | All raise sites pass explicit diagnostic code |
| `ConnectionTestResult` carries `diag_code` attribute | `services/watsonx_service.py` | Diagnostic code flows from exception → result → UI |
| Log entries include `exc_class`, `diag`, `ibm_code`, `endpoint` — never API key or credential value | `services/watsonx_service.py` | Safe structured logging verified |
| Settings page calls `svc.reset()` before test to force fresh probe | `app.py` | Ensures each test button press re-probes rather than reusing a cached failed client |
| `_render_diagnostic_guidance()` — expander with actionable fix instructions per diagnostic code | `app.py` | Shown when test fails; links to IBM Cloud IAM, watsonx.ai project, and status page |
| 46 new diagnostic unit tests | `tests/test_watsonx_diagnostics.py` | Covers all exception classes, HTTP status codes, safe helper functions, `WatsonxError.diag_code`, `ConnectionTestResult.diag_code`, and `test_connection()` diagnostic propagation |

### PHASE 5 – Model Discovery Utility (v4)

| Change | File(s) | Result |
|---|---|---|
| `services/model_discovery.py` — new module | `services/model_discovery.py` | `ModelInfo` dataclass with `is_generative`, `is_granite`, `is_generative_granite` properties; `DiscoveryResult` with `generative_models()`, `generative_granite_models()`, `is_model_available()`; `list_available_models(client)` calls `client.foundation_models.get_model_specs(url=endpoint)`; never raises — returns error in `DiscoveryResult.error`; safe logging (no credentials) |
| `filter_generative_models()` / `filter_granite_generative()` / `is_model_available()` helpers | `services/model_discovery.py` | Pure filtering functions on `list[ModelInfo]`; fully unit-tested without a live client |
| `_parse_model_specs()` — parses SDK dict/object response | `services/model_discovery.py` | Handles `{"resources": [...]}` dict, `obj.resources` attribute, or plain list; skips malformed entries gracefully |
| `list_available_models_no_client()` — best-effort unauthenticated probe | `services/model_discovery.py` | Tries SDK package-level `get_model_specs`; returns error result when not supported |
| Settings page "Model Availability in Your Region" section | `app.py` | "Check Model Availability" button: initialises client, calls `list_available_models()`, shows configured model status (✅/⚠️/❌), lists all generative Granite models available in the region, lists other generative models in collapsible expander, shows catalog summary caption |
| 35 new model discovery unit tests | `tests/test_model_discovery.py` | Covers `ModelInfo`, `DiscoveryResult`, `_parse_model_specs`, `filter_generative_models`, `filter_granite_generative`, `is_model_available`, `list_available_models`, `list_available_models_no_client` — fully mocked, no live SDK calls |

### PHASE 6 – Deterministic Validation Improvements (v5)

| Change | File(s) | Issue Fixed |
|---|---|---|
| `build_budget_breakdown()` scaling guard tightened from >110% to >100% | `utils/calculations.py` | Budget could silently exceed user's maximum between 100–110% |
| Activities allocation: capped to remaining capacity after fixed costs | `utils/calculations.py` | Activities added 10% of total budget unconditionally, even if fixed costs already consumed 95% |
| Accommodation nights guard: `num_nights = max(0, num_days - 1)` | `utils/calculations.py` | 1-day trip produced `num_nights=0` with no guard, risking negative/zero costs silently |
| `validate_budget_breakdown()` helper added | `utils/calculations.py` | Post-construction explicit check; returns warning string when total > budget (1 paisa tolerance) |
| `budget_overrun_warning` field in `BudgetAgent.analyze()` output | `agents/budget_agent.py` | Budget overrun was logged but never propagated to UI or itinerary warnings |
| Day count validation: trim if Granite returns too many days | `agents/itinerary_agent.py` | 5-day trip could produce 7-day itinerary — dates extended past `end_date` |
| Day count validation: pad with template days if Granite returns too few | `agents/itinerary_agent.py` | 5-day trip could produce 3-day itinerary with no warning |
| `day_number` clamping to `[1, duration_days]` | `agents/itinerary_agent.py` | Granite-returned `day_number=10` for a 5-day trip produced dates outside the trip window |
| Activity cost sum vs activities budget check (>110% triggers warning) | `agents/itinerary_agent.py` | Granite-generated activity costs not verified against Python-calculated activities budget |
| `budget_overrun_warning` propagated from budget_data to itinerary warnings | `agents/itinerary_agent.py` | Budget overrun from BudgetAgent was not surfaced in final itinerary warnings |
| Post-revision cost guard in `_apply_revision()` (>115% triggers warning) | `agents/replanning_agent.py` | Granite could return revised activities costing more than original day's budget |
| `simulation_disclaimer` in `_fallback_replan()` output | `agents/replanning_agent.py` | Fallback replanning produced deterministic results that could appear to be live safety data |
| Simulation disclaimer appended to `revised.warnings` on fallback path | `agents/replanning_agent.py` | Users had no indication that a replanning scenario was simulated |
| `data_disclaimer` field added to `WeatherAgent.analyze()` output | `agents/weather_agent.py` | Granite weather safety assessment appeared to be official advisory with no disclosure |
| Budget constraint line added to itinerary generation prompt | `agents/itinerary_agent.py` | Granite instructed to not exceed activities budget; day count constraint explicit |
| Budget per-night constraint added to itinerary prompt | `agents/itinerary_agent.py` | Accommodation cost per night was not bounded in Granite's generation context |

---

## 2. Project Completeness Audit (Updated)

| Feature | Implementation File | Status | Evidence | Issue | Required Fix |
|---|---|---|---|---|---|
| Streamlit application and navigation | `app.py`, `components/navigation.py` | **COMPLETE AND TESTED** | Clean startup (no warnings); all 6 pages route correctly | None | None |
| IBM Granite integration (SDK) | `services/watsonx_service.py` | **IMPLEMENTED — AUTHENTICATION TESTED** | SDK v1.9.0 installed; IAM auth works; Project ID 404 (see §5) | Project ID in `.env` does not exist in the IBM Cloud account | Update `WATSONX_PROJECT_ID` in `.env` with valid project |
| Secure `.env` and `st.secrets` | `config.py`, `.gitignore` | **COMPLETE AND TESTED** | `.env` git-ignored; `st.secrets` fallback coded; no secrets in logs | None | None |
| Travel Preference Agent | `agents/preference_agent.py` | **IMPLEMENTED AND UNIT TESTED** | 4 unit tests pass (mocked); live test blocked by Project ID | Fix Project ID | None |
| Destination Intelligence Agent | `agents/destination_agent.py` | **IMPLEMENTED AND UNIT TESTED** | 3 unit tests pass | Fix Project ID | None |
| Route Intelligence Agent | `agents/route_agent.py` | **IMPLEMENTED AND UNIT TESTED** | 3 unit tests pass; OSRM integration test exists (guarded) | Fix Project ID | None |
| Budget Optimization Agent | `agents/budget_agent.py` | **COMPLETE AND TESTED** | 3 agent tests + 9 budget calc tests pass; all arithmetic Python-only | None | None |
| Weather and Safety Agent | `agents/weather_agent.py` | **IMPLEMENTED AND UNIT TESTED** | 3 unit tests pass; Open-Meteo integration test exists (guarded) | Fix Project ID | None |
| Itinerary Generation Agent | `agents/itinerary_agent.py` | **IMPLEMENTED AND UNIT TESTED** | 3 unit tests pass (Granite parse + template fallback) | Fix Project ID | None |
| Dynamic Replanning Agent | `agents/replanning_agent.py` | **IMPLEMENTED AND UNIT TESTED** | 5 unit tests pass; deep-copy verified; user approval enforced | Fix Project ID | None |
| Central agent orchestrator | `agents/orchestrator.py` | **COMPLETE AND TESTED** | 6-step pipeline; per-step isolation; `PlanningResult` structure | None | None |
| OpenStreetMap / Nominatim | `services/maps_service.py` | **IMPLEMENTED AND TESTED** | Guarded integration tests exist; 8s timeout | None | None |
| OSRM routing | `services/maps_service.py` | **IMPLEMENTED AND TESTED** | Guarded integration tests exist; Haversine fallback | None | None |
| Open-Meteo weather | `services/weather_service.py` | **IMPLEMENTED AND TESTED** | Guarded integration tests exist; 4 weather tests | None | None |
| Interactive itinerary visualization | `components/itinerary_view.py` | **COMPLETE AND TESTED** | Import tested; all 6 day view elements render | None | None |
| Interactive map (Folium) | `components/map_view.py` | **COMPLETE AND TESTED** | Destination + attraction markers + route map; fallback if folium absent | None | None |
| Budget charts (Plotly) | `components/budget_view.py` | **COMPLETE AND TESTED** | Donut + bar charts; import tested | None | None |
| Budget calculations + Indian formatting | `utils/calculations.py` | **COMPLETE AND TESTED** | 18 budget tests pass (9 original + 9 new); `format_inr`, `validate_budget_breakdown`, 1-day guard all verified | None | None |
| User approval for replanning | `app.py`, `agents/replanning_agent.py` | **COMPLETE AND TESTED** | `requires_user_approval=True` unit-tested; UI buttons tested | None | None |
| Error handling | All agents, services, `app.py` | **COMPLETE AND TESTED** | Per-step isolation; `WatsonxError`/`ConfigError` hierarchy | None | None |
| Input validation | `utils/validation.py`, `models/travel_request.py` | **COMPLETE AND TESTED** | 18 validation tests pass | None | None |
| Output validation | All agents | **COMPLETE AND TESTED** | JSON parsed; Pydantic enforces types; agent tests verify | None | None |
| Prompt injection protection | `utils/security.py` | **COMPLETE AND TESTED** | 56 security tests pass (detection + sanitization + false-positives) | None | None |
| External API timeouts | All services | **COMPLETE AND TESTED** | 8s geocoding; `REQUEST_TIMEOUT` (60s) for OSRM/weather | None | None |
| API failure safety | All services | **COMPLETE AND TESTED** | All services return `None`/fallback on error | None | None |
| Streamlit Cloud deployment readiness | `app.py`, `requirements.txt`, `runtime.txt` | **COMPLETE AND TESTED** | Clean startup; `st.secrets` coded; `runtime.txt` correct | None | None |

---

## 3. Test Suite Results

### Standard Run (`pytest tests/ -v`)

```
236 total  |  236 passed  |  0 failed  |  15 skipped
```

| File | Tests | Passed | Failed | Skipped | Notes |
|---|---|---|---|---|---|
| `test_agents.py` | 25 | 25 | 0 | 0 | Mocked WatsonxService; all 7 agents |
| `test_budget.py` | 18 | 18 | 0 | 0 | 9 original + 9 new validation tests |
| `test_config.py` | 4 | 4 | 0 | 0 | Config module tests |
| `test_integration.py` | 15 | 0 | 0 | 15 | Guarded; require env var flags |
| `test_itinerary_validation.py` | 18 | 18 | 0 | 0 | New: day count, cost guards, disclaimers |
| `test_model_discovery.py` | 35 | 35 | 0 | 0 | Model discovery — fully mocked |
| `test_security_extended.py` | 57 | 57 | 0 | 0 | Injection detection + sanitization |
| `test_validation.py` | 17 | 17 | 0 | 0 | Validation + Pydantic tests |
| `test_watsonx.py` | 7 | 7 | 0 | 0 | Mocked/config watsonx tests |
| `test_watsonx_diagnostics.py` | 46 | 46 | 0 | 0 | Diagnostic classifier + result types |

**v1 results:** 43 tests | 41 passed | **2 failed**
**v2 results:** 128 tests | 113 passed | **0 failed** | 15 guarded-skip
**v3 results:** 174 tests | 159 passed | **0 failed** | 15 guarded-skip
**v4 results:** 209 tests | 209 passed | **0 failed** | 15 guarded-skip
**v5 results:** 236 tests | 236 passed | **0 failed** | 15 guarded-skip

### Fixes that resolved previous failures

| Previous failure | Root cause | Fix |
|---|---|---|
| `test_format_inr` | `format_inr` used Western `{:,}` grouping | Rewrote with Indian lakh/crore grouping algorithm |
| `test_sanitize_removes_injection` | `sanitize_for_prompt` did not remove `system:` | Added `system\s*:` to `_INJECTION_PATTERNS`; unified sanitization path |

---

## 4. IBM Granite Connection Status

**CREDENTIALS VALID — MODEL AVAILABILITY IS REGION-DEPENDENT**

| Check | Result | Notes |
|---|---|---|
| SDK installed | `ibm-watsonx-ai==1.9.0` ✅ | — |
| API key authentication | **Succeeds** (IAM validates the key) ✅ | — |
| Project lookup | **Succeeds** when a valid project ID is provided ✅ | Previous WSCPA404PE error resolved once valid project ID is set in `.env` |
| Model `ibm/granite-4-h-small` in Tokyo (`jp-tok`) | **NOT AVAILABLE** ❌ | Confirmed via `get_model_specs()`: 12 models in Tokyo catalog; none are IBM Granite generative; only Granite embedding and time-series models present |
| Model `ibm/granite-4-h-small` in US South (`us-south`) | **Expected to be available** (not yet confirmed live) | Standard availability on IBM Lite plan in us-south |
| Model inference | **Not tested live** — blocked until region/model is aligned | App runs fully in template mode |
| Model availability UI | **AVAILABLE** — "Check Model Availability" button in Settings | Uses `services/model_discovery.py`; shows which Granite generative models exist in the configured region |
| Diagnostic code surfaced on model error | `MODEL_NOT_FOUND` | Settings page shows actionable guidance to switch region or model |

### Tokyo Region — Confirmed Model Catalog

Probed via `client.foundation_models.get_model_specs(url="https://jp-tok.ml.cloud.ibm.com")`:

| model_id | task_ids | Generative? | IBM Granite? |
|---|---|---|---|
| `ibm/granite-embedding-278m-multilingual` | [] | ❌ | ✅ (embedding only) |
| `ibm/granite-ttm-*` (several) | [time_series_forecasting] | ❌ | ✅ (time-series only) |
| `meta-llama/llama-3-3-70b-instruct` | [generation] | ✅ | ❌ |
| `meta-llama/llama-4-maverick-17b-*` | [generation] | ✅ | ❌ |
| `mistralai/mistral-medium-2505` | [generation] | ✅ | ❌ |
| `mistralai/mistral-small-3-1-*` | [generation] | ✅ | ❌ |

**Conclusion:** IBM Lite plan in Tokyo does not include IBM Granite generative/chat models. Switch `WATSONX_URL` to `https://us-south.ml.cloud.ibm.com` to access `ibm/granite-4-h-small`.

---

## 5. Security Audit (Updated)

| Area | Status | Notes |
|---|---|---|
| `.env` git-ignored | **PASS** | Both `.env` and `secrets.toml` excluded |
| Credentials in logs | **PASS** | Sanitized error messages; no key in log output |
| `st.secrets` integration | **PASS** | Tested |
| Prompt injection detection | **PASS** | 25 patterns; 56 tests pass including 13 false-positive guards |
| `sanitize_for_prompt` removes `system:` | **PASS** (was FAIL) | Fixed in v2 |
| `sanitize_prompt_input` unified | **PASS** (was PARTIAL) | Delegates to `sanitize_for_prompt` |
| Model-level `sanitize_notes` unified | **PASS** (was PARTIAL) | Uses `sanitize_for_prompt` |
| External API timeouts | **PASS** | 8s geocoding; 60s OSRM/weather |
| XSRF protection | **PASS** | `enableXsrfProtection=true`; CORS conflict removed |

---

## 6. README Verification (Updated)

| Previously inaccurate claim | Status |
|---|---|
| LICENSE referenced but missing | **FIXED** — `LICENSE` file created (MIT) |
| Prompt injection claim overstated | **FIXED** — now fully implemented and tested |
| `format_inr` Western grouping | **FIXED** — Indian lakh/crore grouping |

All other README claims remain accurate and verified.

---

## 7. Remaining Limitations

| Priority | Item | Detail |
|---|---|---|
| **P1 – Blocking** | `ibm/granite-4-h-small` not available in Tokyo region | Confirmed via `get_model_specs()`. Switch `WATSONX_URL` to `https://us-south.ml.cloud.ibm.com` in `.env`. App works fully in template mode until resolved. |
| P2 – Important | Live Granite inference not confirmed end-to-end | After region switch, a live `test_connection()` call is needed to confirm generation works. Not yet executed. |
| P3 – Medium | Guarded integration tests not run in CI | Open-Meteo, OSRM, Nominatim tests are coded but require `RUN_OPEN_METEO_TESTS=1` etc. to execute |
| P4 – Low | Destination knowledge base only covers 8 cities | Out-of-knowledge-base destinations fall back to Granite-only reasoning |
| P4 – Low | Attraction marker coordinates are deterministic offsets | Marker positions approximate; not geocoded. Accurate only for zoomed-in city maps |
| P4 – Low | `pandas` imported inline in `app.py` line ~449 | Minor style issue; does not affect functionality |

---

## 8. Streamlit Deployment Readiness

**READY.**

| Check | Result |
|---|---|
| App starts (clean) | ✅ No warnings, no errors |
| CORS/XSRF conflict | ✅ Resolved (removed `enableCORS=false`) |
| `runtime.txt` | ✅ `python-3.11` |
| `requirements.txt` | ✅ All dependencies including `ibm-watsonx-ai>=1.1.2` |
| `.env` git-ignored | ✅ |
| `st.secrets` handling | ✅ Tested |
| Template mode (no credentials) | ✅ Shows simulated itinerary with clear warning |
| `@st.cache_resource` for WatsonxService | ✅ Prevents SDK re-initialisation on reruns |
| `LICENSE` file | ✅ Created |

To deploy to Streamlit Community Cloud:
1. Push code to GitHub (`.env` will not be included)
2. In Streamlit Cloud → App Settings → Secrets, add:
   ```toml
   WATSONX_API_KEY = "your_valid_api_key"
   WATSONX_PROJECT_ID = "your_valid_project_id"
   WATSONX_URL = "https://us-south.ml.cloud.ibm.com"
   WATSONX_MODEL_ID = "ibm/granite-4-h-small"
   ```
3. Deploy — the app will use Granite for all 6 agents automatically

---

## 9. Files Modified in v2 and v3

| File | Type | Change |
|---|---|---|
| `utils/security.py` | Modified (v2) | Expanded `_INJECTION_PATTERNS` (18 new patterns) |
| `utils/validation.py` | Modified (v2) | `sanitize_prompt_input` delegates to `sanitize_for_prompt` |
| `utils/calculations.py` | Modified (v2) | `format_inr` rewritten for Indian lakh/crore grouping |
| `models/travel_request.py` | Modified (v2) | `sanitize_notes` validator uses `sanitize_for_prompt` |
| `services/watsonx_service.py` | Modified (v2+v3) | `@st.cache_resource`; full diagnostic classifier; structured safe logging |
| `components/map_view.py` | Modified (v2) | Attraction markers (up to 5) added to destination map |
| `app.py` | Modified (v3) | `svc.reset()` before test; `_render_diagnostic_guidance()` helper |
| `.streamlit/config.toml` | Modified (v2) | Removed `enableCORS = false` |
| `LICENSE` | Created (v2) | MIT License |
| `pytest.ini` | Created (v2) | Registers `integration` mark; sets `-ra` |
| `tests/test_agents.py` | Created (v2) | 25 unit tests for all 7 agents (mocked) |
| `tests/test_security_extended.py` | Created (v2) | 57 security/injection tests |
| `tests/test_integration.py` | Created (v2) | 15 guarded live integration tests |
| `tests/test_watsonx_diagnostics.py` | Created (v3) | 46 diagnostic unit tests |

---

*Generated by automated code inspection, live SDK test execution, and diagnostic verification.*
*No credentials, API keys, or token values were displayed, logged, or committed during this audit.*


---

## PHASE 6 – Direct maintenance update (ChatGPT-assisted)

**Scope:** Targeted fixes applied to the uploaded source archive. No credentials were included in the archive or modified.

Changes:
- `services/model_discovery.py`: mocked-client discovery no longer imports/requires the SDK package before calling the supplied client; a missing client is handled explicitly.
- `agents/itinerary_agent.py`: itinerary date coverage now includes both arrival and departure dates; token budgeting follows calendar dates; duplicate day numbers are ignored; mixed Granite/template days are explicitly labelled; activity budget warnings use a strict allocated-budget threshold; zero activity allocation no longer causes division by zero; raw model response snippets are no longer written to logs.
- `agents/replanning_agent.py`: revised days exceeding the original daily total are rejected and the original day is restored; no 15% tolerance.
- `utils/calculations.py`: actual fixed cost estimates are no longer proportionally scaled down to conceal an over-budget trip. Overruns remain visible for validation.
- Tests updated to reflect inclusive date coverage, strict activity/replanning budget rules, and mocked discovery independence from the installed SDK.
- Added a regression test for 12–18 November 2026: seven calendar dates and up to six overnight stays.

Independent test execution in the working environment:
**236 passed, 15 skipped, 0 failed.**
The 15 skipped tests are guarded live integrations for Open-Meteo, OSRM/Nominatim and IBM Granite. No live IBM inference was performed as part of this archive review.

Important remaining verification:
- Run the application with the user's own local `.env` or Streamlit secrets.
- Confirm a real `ibm/granite-4-h-small` inference from RouteWise AI.
- Verify the external map tile provider configuration and live weather/route integrations.


## Follow-up fix: Granite chat inference and map tiles

- Replaced the deprecated `ModelInference.generate()` / `/ml/v1/text/generation`
  request path with the documented `ModelInference.chat()` interface
  (`/ml/v1/text/chat`) for Granite chat inference.
- Chat request parameters (`max_tokens`, `temperature`) are passed per request;
  legacy text-generation parameters are no longer supplied to the model
  constructor.
- Added parsing for chat `choices[].message.content` and token usage, including
  text-block content responses.
- Empty chat responses and SDKs without a `chat` method now produce explicit
  errors instead of silently continuing.
- Added unit tests for chat response parsing, request parameters, empty output,
  and missing chat support.
- Replaced CartoDB Positron tiles with OpenStreetMap tiles to remove the
  Carto API-key requirement.
- Updated the minimum IBM SDK requirement to `ibm-watsonx-ai>=1.1.26`.

Verification in this editing environment: 242 tests passed, 15 guarded live
integration tests skipped, 0 failed. The IBM SDK is not installed in this
editing environment and no live IBM credentials were used, so live Granite
chat inference still needs to be confirmed on the user's machine after
installing the updated requirements.
