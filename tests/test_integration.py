"""
RouteWise AI – Guarded Integration Tests
=========================================
These tests make LIVE network calls to external APIs and IBM Granite.

They are SKIPPED automatically unless the explicit marker environment variables
are set.  Normal CI and pytest runs will never trigger them.

To run a specific group:
    # Open-Meteo (no credentials needed):
    RUN_OPEN_METEO_TESTS=1 pytest tests/test_integration.py::TestOpenMeteoIntegration -v

    # OSRM + Nominatim (no credentials needed):
    RUN_OSRM_TESTS=1 pytest tests/test_integration.py::TestOSRMIntegration -v

    # IBM Granite (requires valid .env credentials):
    RUN_GRANITE_TESTS=1 pytest tests/test_integration.py::TestGraniteIntegration -v

    # All live tests at once (requires credentials for Granite):
    RUN_OPEN_METEO_TESTS=1 RUN_OSRM_TESTS=1 RUN_GRANITE_TESTS=1 pytest tests/test_integration.py -v

IMPORTANT: Never run Granite tests in automated CI without injected secrets.
"""

from __future__ import annotations

import os
import pytest
from datetime import date, timedelta

# ── Guard decorators ──────────────────────────────────────────────────────────

_skip_open_meteo = pytest.mark.skipif(
    not os.environ.get("RUN_OPEN_METEO_TESTS"),
    reason="Open-Meteo integration tests skipped (set RUN_OPEN_METEO_TESTS=1 to run)",
)

_skip_osrm = pytest.mark.skipif(
    not os.environ.get("RUN_OSRM_TESTS"),
    reason="OSRM/Nominatim integration tests skipped (set RUN_OSRM_TESTS=1 to run)",
)

_skip_granite = pytest.mark.skipif(
    not os.environ.get("RUN_GRANITE_TESTS"),
    reason="IBM Granite integration tests skipped (set RUN_GRANITE_TESTS=1 to run)",
)


# ─────────────────────────────────────────────────────────────────────────────
# Open-Meteo Integration
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestOpenMeteoIntegration:
    @_skip_open_meteo
    def test_geocode_returns_coords_for_jaipur(self):
        from services.weather_service import _geocode_city
        result = _geocode_city("Jaipur")
        assert result is not None, "Geocode returned None for Jaipur"
        lat, lon = result
        # Jaipur is ~26.9°N, 75.8°E
        assert 25.0 < lat < 28.0, f"Lat out of range: {lat}"
        assert 74.0 < lon < 77.0, f"Lon out of range: {lon}"

    @_skip_open_meteo
    def test_forecast_returns_weather_days(self):
        from services.weather_service import get_weather_forecast, WeatherForecast
        today = date.today()
        forecast = get_weather_forecast("Jaipur", today, today + timedelta(days=3))
        assert forecast is not None, "get_weather_forecast returned None"
        assert isinstance(forecast, WeatherForecast)
        assert len(forecast.days) >= 1
        day = forecast.days[0]
        # Sanity: temperature in plausible India range
        assert -10 < day.max_temp_c < 55, f"Implausible max_temp_c: {day.max_temp_c}"
        assert isinstance(day.description, str)
        assert isinstance(day.is_disruptive, bool)

    @_skip_open_meteo
    def test_forecast_city_not_found_returns_none(self):
        from services.weather_service import get_weather_forecast
        today = date.today()
        result = get_weather_forecast("ZZZNOTACITYZZZ12345", today, today + timedelta(days=2))
        assert result is None, "Expected None for unknown city"

    @_skip_open_meteo
    def test_forecast_for_multiple_indian_cities(self):
        from services.weather_service import get_weather_forecast
        today = date.today()
        for city in ("Delhi", "Mumbai", "Goa", "Shimla"):
            result = get_weather_forecast(city, today, today + timedelta(days=2))
            assert result is not None, f"No forecast for {city}"
            assert len(result.days) >= 1, f"No days for {city}"


# ─────────────────────────────────────────────────────────────────────────────
# OSRM + Nominatim Integration
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestOSRMIntegration:
    @_skip_osrm
    def test_geocode_delhi(self):
        from services.maps_service import geocode
        result = geocode("Delhi")
        assert result is not None, "geocode returned None for Delhi"
        lat, lon = result
        assert 28.0 < lat < 29.5, f"Delhi lat out of range: {lat}"
        assert 76.5 < lon < 78.0, f"Delhi lon out of range: {lon}"

    @_skip_osrm
    def test_geocode_jaipur(self):
        from services.maps_service import geocode
        result = geocode("Jaipur")
        assert result is not None
        lat, lon = result
        assert 25.0 < lat < 28.0

    @_skip_osrm
    def test_get_route_info_delhi_jaipur(self):
        from services.maps_service import get_route_info, RouteInfo
        route = get_route_info("Delhi", "Jaipur")
        assert isinstance(route, RouteInfo)
        # Delhi–Jaipur is ~270–300 km by road
        assert 200 < route.distance_km < 400, f"Distance out of range: {route.distance_km}"
        assert route.duration_hours > 0
        # Check whether OSRM succeeded (not estimated)
        # We accept either: OSRM success OR Haversine fallback (both are valid)
        assert isinstance(route.is_estimated, bool)

    @_skip_osrm
    def test_get_route_info_unknown_city_falls_back(self):
        from services.maps_service import get_route_info
        route = get_route_info("ZZZUNKNOWNZZZ", "Jaipur")
        # Should not raise; returns fallback estimate
        assert route.distance_km > 0
        assert route.is_estimated is True

    @_skip_osrm
    def test_haversine_fallback_reasonable(self):
        from services.maps_service import _haversine_km
        # Delhi to Jaipur straight-line ~240 km
        dist = _haversine_km((28.6139, 77.2090), (26.9124, 75.7873))
        assert 200 < dist < 280, f"Haversine distance out of range: {dist}"


# ─────────────────────────────────────────────────────────────────────────────
# IBM Granite Integration
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestGraniteIntegration:
    """
    Live tests against IBM watsonx.ai.
    Requires valid WATSONX_API_KEY and WATSONX_PROJECT_ID in .env.
    Never prints or logs credentials.
    """

    @_skip_granite
    def test_config_is_ready(self):
        import config
        status = config.validate_config()
        assert status.is_ready, (
            f"IBM config not ready: {status.summary!r}. "
            "Ensure WATSONX_API_KEY and WATSONX_PROJECT_ID are set."
        )

    @_skip_granite
    def test_connection_test_succeeds(self):
        from services.watsonx_service import WatsonxService
        svc = WatsonxService()
        result = svc.test_connection()
        assert result.success, f"Connection test failed: {result.message}"
        # Sanity: some response text
        assert isinstance(result.response_preview, str)

    @_skip_granite
    def test_generate_returns_non_empty_text(self):
        from services.watsonx_service import WatsonxService, GenerationResult
        svc = WatsonxService()
        result = svc.generate("Say the word: hello", max_tokens=10)
        assert isinstance(result, GenerationResult)
        assert len(result.text) > 0, "Granite returned empty text"
        assert result.output_tokens > 0
        assert result.model_id is not None

    @_skip_granite
    def test_token_usage_reported(self):
        from services.watsonx_service import WatsonxService
        svc = WatsonxService()
        result = svc.generate("What is the capital of India?", max_tokens=20)
        assert result.input_tokens >= 0
        assert result.output_tokens > 0

    @_skip_granite
    def test_preference_agent_live(self):
        """End-to-end: PreferenceAgent makes a real Granite call and returns a valid profile."""
        from agents.preference_agent import PreferenceAgent
        from services.watsonx_service import WatsonxService
        today = date.today()
        from models.travel_request import TravelRequest
        request = TravelRequest(
            origin="Delhi",
            destination="Jaipur",
            start_date=today + timedelta(days=7),
            end_date=today + timedelta(days=12),
            num_travellers=2,
            budget_inr=30000,
            interests=["culture", "food"],
        )
        svc = WatsonxService()
        agent = PreferenceAgent(svc)
        profile = agent.analyze(request)
        # Must have all required keys
        for key in ("destination_type", "travel_style", "primary_interest",
                    "key_priorities", "flexibility_score"):
            assert key in profile, f"Missing key in profile: {key}"

    @_skip_granite
    def test_oversized_prompt_rejected(self):
        """generate() raises ValueError for prompts exceeding the size limit."""
        import config
        from services.watsonx_service import WatsonxService
        svc = WatsonxService()
        huge_prompt = "A" * (config.MAX_PROMPT_CHARS * 4)
        with pytest.raises(ValueError, match="maximum allowed size"):
            svc.generate(huge_prompt)
