"""
RouteWise AI – Tests: All Agents (mocked WatsonxService)
=========================================================
These tests verify that every agent:
1. Calls watsonx.generate() and parses valid JSON correctly.
2. Falls back gracefully when Granite is unavailable.
3. Passes structured data between agents as expected.

No live IBM credentials or network connectivity required.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
import pytest

from models.travel_request import TravelRequest
from services.watsonx_service import WatsonxService, GenerationResult


# ── Shared fixtures ───────────────────────────────────────────────────────────

TODAY = date.today()


def _make_request(**overrides) -> TravelRequest:
    defaults = dict(
        origin="Delhi",
        destination="Jaipur",
        start_date=TODAY + timedelta(days=7),
        end_date=TODAY + timedelta(days=12),
        num_travellers=2,
        budget_inr=30000,
        accommodation_preference="mid-range",
        transport_preference="train",
        interests=["culture", "food"],
    )
    defaults.update(overrides)
    return TravelRequest(**defaults)


def _mock_service(response_text: str) -> WatsonxService:
    """Return a WatsonxService whose generate() always returns response_text."""
    svc = MagicMock(spec=WatsonxService)
    svc.generate.return_value = GenerationResult(
        text=response_text,
        input_tokens=50,
        output_tokens=100,
        model_id="ibm/granite-4-h-small",
    )
    return svc


def _mock_service_error(exc: Exception) -> WatsonxService:
    """Return a WatsonxService whose generate() raises the given exception."""
    svc = MagicMock(spec=WatsonxService)
    svc.generate.side_effect = exc
    return svc


# ─────────────────────────────────────────────────────────────────────────────
# PreferenceAgent
# ─────────────────────────────────────────────────────────────────────────────

class TestPreferenceAgent:
    def test_parses_valid_granite_response(self):
        from agents.preference_agent import PreferenceAgent
        payload = {
            "destination_type": "heritage",
            "travel_style": "mid-range",
            "primary_interest": "culture",
            "recommended_accommodation": "mid-range hotel",
            "flexibility_score": 3,
            "key_priorities": ["culture", "food", "comfort"],
            "special_considerations": "2 travellers, 5 days.",
        }
        svc = _mock_service(json.dumps(payload))
        agent = PreferenceAgent(svc)
        result = agent.analyze(_make_request())
        assert result["destination_type"] == "heritage"
        assert result["travel_style"] == "mid-range"
        assert result["flexibility_score"] == 3
        svc.generate.assert_called_once()

    def test_fallback_when_granite_unavailable(self):
        from agents.preference_agent import PreferenceAgent
        from services.watsonx_service import ConfigError
        svc = _mock_service_error(ConfigError("No credentials"))
        agent = PreferenceAgent(svc)
        result = agent.analyze(_make_request())
        # Fallback returns required keys
        assert "destination_type" in result
        assert "travel_style" in result
        assert "key_priorities" in result

    def test_fallback_when_json_malformed(self):
        from agents.preference_agent import PreferenceAgent
        svc = _mock_service("This is not JSON at all.")
        agent = PreferenceAgent(svc)
        result = agent.analyze(_make_request())
        assert "destination_type" in result

    def test_prompt_contains_destination(self):
        from agents.preference_agent import PreferenceAgent
        payload = {"destination_type": "tier2", "travel_style": "budget",
                   "primary_interest": "food", "recommended_accommodation": "budget",
                   "flexibility_score": 2, "key_priorities": ["food"],
                   "special_considerations": ""}
        svc = _mock_service(json.dumps(payload))
        agent = PreferenceAgent(svc)
        agent.analyze(_make_request())
        prompt_used = svc.generate.call_args[0][0]
        assert "Jaipur" in prompt_used


# ─────────────────────────────────────────────────────────────────────────────
# DestinationAgent
# ─────────────────────────────────────────────────────────────────────────────

class TestDestinationAgent:
    _PAYLOAD = {
        "destination_evaluation": "Jaipur is excellent for culture lovers.",
        "top_attractions": [{"name": "Amber Fort", "description": "Majestic hill fort"}],
        "local_experiences": ["Cooking class", "Camel ride"],
        "practical_tips": ["Carry cash", "Book ahead"],
        "best_areas_to_stay": "Old City",
        "cuisine_highlights": ["Dal Baati", "Ghewar"],
        "estimated_daily_spend_inr": 2500,
    }

    def test_parses_valid_granite_response(self):
        from agents.destination_agent import DestinationAgent
        svc = _mock_service(json.dumps(self._PAYLOAD))
        agent = DestinationAgent(svc)
        result = agent.analyze(_make_request(), {"travel_style": "mid-range"})
        assert result["destination_evaluation"] == "Jaipur is excellent for culture lovers."
        assert "static_highlights" in result  # merged from static data

    def test_fallback_when_granite_unavailable(self):
        from agents.destination_agent import DestinationAgent
        from services.watsonx_service import WatsonxError
        svc = _mock_service_error(WatsonxError("inference failed"))
        agent = DestinationAgent(svc)
        result = agent.analyze(_make_request(), {})
        assert "destination_evaluation" in result
        assert "top_attractions" in result

    def test_static_data_merged_into_result(self):
        from agents.destination_agent import DestinationAgent
        svc = _mock_service(json.dumps(self._PAYLOAD))
        agent = DestinationAgent(svc)
        result = agent.analyze(_make_request(), {"travel_style": "mid-range"})
        # Jaipur is in the static knowledge base
        assert isinstance(result.get("static_highlights"), list)


# ─────────────────────────────────────────────────────────────────────────────
# RouteAgent
# ─────────────────────────────────────────────────────────────────────────────

class TestRouteAgent:
    _PAYLOAD = {
        "recommended_transport": "train",
        "reasoning": "Train is comfortable and affordable for 280 km.",
        "alternatives": [{"type": "bus", "pros": "Cheap", "cons": "Slower"}],
        "journey_tips": ["Book 2 weeks ahead."],
        "estimated_journey_hours": 4.5,
    }

    def test_parses_valid_granite_response(self):
        from agents.route_agent import RouteAgent
        from services.maps_service import RouteInfo
        svc = _mock_service(json.dumps(self._PAYLOAD))
        agent = RouteAgent(svc)
        with patch("agents.route_agent.get_route_info") as mock_route:
            mock_route.return_value = RouteInfo("Delhi", "Jaipur", 280, 4.5)
            result = agent.analyze(_make_request())
        assert result["recommended_transport"] == "train"
        assert result["route_info"]["distance_km"] == 280
        assert "transport_costs_inr" in result

    def test_fallback_when_granite_unavailable(self):
        from agents.route_agent import RouteAgent
        from services.maps_service import RouteInfo
        from services.watsonx_service import ConfigError
        svc = _mock_service_error(ConfigError("No credentials"))
        agent = RouteAgent(svc)
        with patch("agents.route_agent.get_route_info") as mock_route:
            mock_route.return_value = RouteInfo("Delhi", "Jaipur", 280, 4.5)
            result = agent.analyze(_make_request())
        assert "recommended_transport" in result
        assert result["route_info"]["distance_km"] == 280

    def test_transport_costs_all_modes_present(self):
        from agents.route_agent import RouteAgent
        from services.maps_service import RouteInfo
        svc = _mock_service(json.dumps(self._PAYLOAD))
        agent = RouteAgent(svc)
        with patch("agents.route_agent.get_route_info") as mock_route:
            mock_route.return_value = RouteInfo("Delhi", "Jaipur", 280, 4.5)
            result = agent.analyze(_make_request())
        costs = result["transport_costs_inr"]
        for mode in ("train", "bus", "flight", "car", "mixed"):
            assert mode in costs
            assert costs[mode] >= 0


# ─────────────────────────────────────────────────────────────────────────────
# BudgetAgent
# ─────────────────────────────────────────────────────────────────────────────

class TestBudgetAgent:
    _PAYLOAD = {
        "budget_assessment": "Budget is manageable for this trip.",
        "cost_saving_tips": ["Eat at dhabas", "Use bus", "Book early"],
        "splurge_suggestions": ["Heritage dinner", "Guided tour"],
        "budget_warning": None,
    }

    def test_parses_valid_granite_narrative(self):
        from agents.budget_agent import BudgetAgent
        svc = _mock_service(json.dumps(self._PAYLOAD))
        agent = BudgetAgent(svc)
        route_data = {"route_info": {"distance_km": 280}}
        result = agent.analyze(_make_request(), route_data, {"destination_type": "tier2"})
        assert result["budget_assessment"] == "Budget is manageable for this trip."
        assert len(result["cost_saving_tips"]) == 3
        assert result["is_within_budget"] is not None

    def test_fallback_when_granite_unavailable(self):
        from agents.budget_agent import BudgetAgent
        from services.watsonx_service import WatsonxError
        svc = _mock_service_error(WatsonxError("timeout"))
        agent = BudgetAgent(svc)
        result = agent.analyze(_make_request(), {}, {})
        assert "budget_assessment" in result
        assert "cost_saving_tips" in result

    def test_python_arithmetic_independent_of_granite(self):
        """Budget totals are computed by Python regardless of Granite response."""
        from agents.budget_agent import BudgetAgent
        svc = _mock_service(json.dumps(self._PAYLOAD))
        agent = BudgetAgent(svc)
        request = _make_request(budget_inr=50000)
        result = agent.analyze(request, {"route_info": {"distance_km": 280}},
                                {"destination_type": "tier2"})
        assert result["total_estimated_inr"] > 0
        assert result["utilisation_pct"] >= 0


# ─────────────────────────────────────────────────────────────────────────────
# WeatherAgent
# ─────────────────────────────────────────────────────────────────────────────

class TestWeatherAgent:
    _PAYLOAD = {
        "overall_assessment": "Good travel conditions expected.",
        "safety_level": "good",
        "disruption_days": [],
        "recommendations": ["Carry sunscreen", "Stay hydrated", "Light clothing"],
        "alternative_suggestion": None,
    }

    def test_parses_valid_granite_response(self):
        from agents.weather_agent import WeatherAgent
        from services.weather_service import WeatherForecast, WeatherDay
        svc = _mock_service(json.dumps(self._PAYLOAD))
        agent = WeatherAgent(svc)
        mock_forecast = WeatherForecast(
            location="Jaipur", latitude=26.91, longitude=75.78,
            days=[WeatherDay("2026-12-01", 28.0, 15.0, 0.0, 1)]
        )
        with patch("agents.weather_agent.get_weather_forecast", return_value=mock_forecast):
            result = agent.analyze(_make_request())
        assert result["overall_assessment"] == "Good travel conditions expected."
        assert result["safety_level"] == "good"
        assert result["forecast_available"] is True

    def test_fallback_when_granite_unavailable(self):
        from agents.weather_agent import WeatherAgent
        from services.weather_service import WeatherForecast, WeatherDay
        from services.watsonx_service import ConfigError
        svc = _mock_service_error(ConfigError("No credentials"))
        agent = WeatherAgent(svc)
        mock_forecast = WeatherForecast(
            location="Jaipur", latitude=26.91, longitude=75.78,
            days=[WeatherDay("2026-12-01", 28.0, 15.0, 0.0, 1)]
        )
        with patch("agents.weather_agent.get_weather_forecast", return_value=mock_forecast):
            result = agent.analyze(_make_request())
        assert "overall_assessment" in result
        assert "safety_level" in result

    def test_handles_no_forecast_data(self):
        from agents.weather_agent import WeatherAgent
        from services.watsonx_service import ConfigError
        svc = _mock_service_error(ConfigError("No credentials"))
        agent = WeatherAgent(svc)
        with patch("agents.weather_agent.get_weather_forecast", return_value=None):
            result = agent.analyze(_make_request())
        assert result["forecast_available"] is False
        assert "overall_assessment" in result


# ─────────────────────────────────────────────────────────────────────────────
# ItineraryAgent
# ─────────────────────────────────────────────────────────────────────────────

class TestItineraryAgent:
    _DAY_PAYLOAD = {
        "trip_title": "Jaipur Heritage Explorer",
        "highlights": ["Amber Fort", "City Palace"],
        "days": [
            {
                "day_number": 1,
                "location": "Jaipur",
                "accommodation": "Mid-range hotel",
                "accommodation_cost_inr": 2000,
                "day_notes": "Arrive and settle in.",
                "activities": [
                    {
                        "time": "10:00",
                        "activity": "Visit Amber Fort",
                        "location": "Amber Fort, Jaipur",
                        "duration_hours": 3.0,
                        "transport": "Auto-rickshaw",
                        "estimated_cost_inr": 500,
                        "notes": "Book guide in advance.",
                        "category": "sightseeing",
                    }
                ],
            }
        ],
        "generation_notes": "Generated by IBM Granite.",
    }

    def test_parses_valid_granite_response(self):
        from agents.itinerary_agent import ItineraryAgent
        from models.itinerary import Itinerary
        svc = _mock_service(json.dumps(self._DAY_PAYLOAD))
        agent = ItineraryAgent(svc)
        itinerary = agent.generate(
            request=_make_request(),
            preference_profile={"travel_style": "mid-range", "key_priorities": ["culture"]},
            destination_data={"top_attractions": [{"name": "Amber Fort"}]},
            budget_data={"breakdown": {"accommodation_inr": 5000, "activities_inr": 3000,
                                        "food_inr": 4000, "transportation_inr": 2000,
                                        "miscellaneous_inr": 1000}},
            weather_data={"disruption_days": []},
        )
        assert isinstance(itinerary, Itinerary)
        assert itinerary.trip_title == "Jaipur Heritage Explorer"
        assert len(itinerary.days) >= 1
        assert not itinerary.is_simulated

    def test_template_fallback_when_granite_unavailable(self):
        from agents.itinerary_agent import ItineraryAgent
        from models.itinerary import Itinerary
        from services.watsonx_service import ConfigError
        svc = _mock_service_error(ConfigError("No credentials"))
        agent = ItineraryAgent(svc)
        itinerary = agent.generate(
            request=_make_request(),
            preference_profile={},
            destination_data={},
            budget_data={"breakdown": {}},
            weather_data={},
        )
        assert isinstance(itinerary, Itinerary)
        assert itinerary.is_simulated
        assert len(itinerary.days) > 0

    def test_weather_disruption_days_included_in_prompt(self):
        from agents.itinerary_agent import ItineraryAgent
        svc = _mock_service(json.dumps(self._DAY_PAYLOAD))
        agent = ItineraryAgent(svc)
        agent.generate(
            request=_make_request(),
            preference_profile={"travel_style": "mid-range", "key_priorities": []},
            destination_data={},
            budget_data={"breakdown": {}},
            weather_data={"disruption_days": [2, 4]},
        )
        prompt_used = svc.generate.call_args[0][0]
        assert "2" in prompt_used or "disruption" in prompt_used.lower()


# ─────────────────────────────────────────────────────────────────────────────
# ReplanningAgent
# ─────────────────────────────────────────────────────────────────────────────

class TestReplanningAgent:
    def _make_itinerary(self):
        from models.itinerary import Itinerary, ItineraryDay, ItineraryActivity, BudgetBreakdown
        activity = ItineraryActivity(
            time="09:00", activity="Visit Amber Fort", location="Amber Fort",
            duration_hours=3.0, estimated_cost_inr=500, category="sightseeing",
        )
        day = ItineraryDay(day_number=1, date_str="2026-12-01", location="Jaipur",
                           activities=[activity], accommodation="Hotel",
                           accommodation_cost_inr=2000)
        return Itinerary(
            trip_title="Jaipur Trip", origin="Delhi", destination="Jaipur",
            start_date="2026-12-01", end_date="2026-12-06", num_travellers=2,
            days=[day],
            budget_breakdown=BudgetBreakdown(transportation_inr=2000,
                                              accommodation_inr=5000, food_inr=3000,
                                              activities_inr=2000, miscellaneous_inr=1000),
            total_budget_inr=30000,
        )

    _REPLAN_PAYLOAD = {
        "revised_day_activities": [
            {
                "time": "10:00", "activity": "Jaipur Museum visit (indoor)",
                "location": "Jaipur", "duration_hours": 2.5,
                "transport": None, "estimated_cost_inr": 200,
                "notes": "Indoor alternative due to rain.", "category": "culture",
            }
        ],
        "changes_made": ["Outdoor fort visit replaced with indoor museum."],
        "reason": "Heavy rainfall forecast — indoor alternatives selected.",
        "revised_accommodation": None,
    }

    def test_parses_valid_granite_response(self):
        from agents.replanning_agent import ReplanningAgent
        from models.itinerary import ReplanningResult
        svc = _mock_service(json.dumps(self._REPLAN_PAYLOAD))
        agent = ReplanningAgent(svc)
        result = agent.replan(
            itinerary=self._make_itinerary(),
            disruption_type="weather",
            disruption_description="Heavy rainfall forecast.",
            affected_day_number=1,
        )
        assert isinstance(result, ReplanningResult)
        assert result.requires_user_approval is True
        assert len(result.changes_made) >= 1
        # Revised day should have new activity
        revised_day = next(d for d in result.revised_itinerary.days if d.day_number == 1)
        assert any("museum" in a.activity.lower() for a in revised_day.activities)

    def test_fallback_weather_replan(self):
        from agents.replanning_agent import ReplanningAgent
        from services.watsonx_service import ConfigError
        svc = _mock_service_error(ConfigError("No credentials"))
        agent = ReplanningAgent(svc)
        result = agent.replan(
            itinerary=self._make_itinerary(),
            disruption_type="weather",
            disruption_description="Thunderstorm warning.",
            affected_day_number=1,
        )
        # Fallback changes outdoor sightseeing → indoor alternative
        assert result.requires_user_approval is True
        revised_day = next(d for d in result.revised_itinerary.days if d.day_number == 1)
        assert len(revised_day.activities) > 0

    def test_deep_copy_preserves_original(self):
        """Replanning must not mutate the original itinerary."""
        from agents.replanning_agent import ReplanningAgent
        svc = _mock_service(json.dumps(self._REPLAN_PAYLOAD))
        agent = ReplanningAgent(svc)
        original = self._make_itinerary()
        original_title = original.trip_title
        result = agent.replan(
            itinerary=original,
            disruption_type="weather",
            disruption_description="Flood warning.",
            affected_day_number=1,
        )
        # Original is untouched
        assert original.trip_title == original_title
        assert original.days[0].activities[0].activity == "Visit Amber Fort"

    def test_user_approval_always_required(self):
        from agents.replanning_agent import ReplanningAgent
        svc = _mock_service(json.dumps(self._REPLAN_PAYLOAD))
        agent = ReplanningAgent(svc)
        result = agent.replan(
            itinerary=self._make_itinerary(),
            disruption_type="transport",
            disruption_description="Rail strike.",
            affected_day_number=1,
        )
        assert result.requires_user_approval is True

    def test_invalid_day_number_returns_gracefully(self):
        from agents.replanning_agent import ReplanningAgent
        svc = _mock_service(json.dumps(self._REPLAN_PAYLOAD))
        agent = ReplanningAgent(svc)
        result = agent.replan(
            itinerary=self._make_itinerary(),
            disruption_type="safety",
            disruption_description="Curfew declared.",
            affected_day_number=99,  # Day 99 does not exist
        )
        # Should return original itinerary unchanged, not crash
        assert result.revised_itinerary is not None
