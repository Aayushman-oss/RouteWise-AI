"""
RouteWise AI – Tests: Itinerary and Replanning Deterministic Validation
=======================================================================
Tests for the post-generation validation logic added in Steps 2, 3, 4, 5, 6:
- Day count trimming / padding
- day_number clamping to [1, duration_days]
- Activity cost sum vs activities budget
- Replanning cost guard
- Weather and replanning disclaimers
All tests are pure unit tests — no IBM SDK calls, no network requests.
"""

from __future__ import annotations

import copy
from datetime import date, timedelta
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from models.itinerary import (
    BudgetBreakdown,
    Itinerary,
    ItineraryActivity,
    ItineraryDay,
    ReplanningResult,
)
from models.travel_request import TravelRequest
from agents.itinerary_agent import ItineraryAgent
from agents.replanning_agent import ReplanningAgent
from agents.weather_agent import WeatherAgent


# ─── Shared fixtures ─────────────────────────────────────────────────────────

def _make_request(duration_days: int = 5, budget: float = 50000) -> TravelRequest:
    today = date.today()
    return TravelRequest(
        origin="Mumbai",
        destination="Goa",
        start_date=today + timedelta(days=7),
        end_date=today + timedelta(days=7 + duration_days),
        num_travellers=2,
        budget_inr=budget,
        accommodation_preference="mid-range",
        transport_preference="train",
    )


def _make_budget_data(
    activities_inr: float = 5000,
    accommodation_inr: float = 10000,
    is_within_budget: bool = True,
) -> Dict[str, Any]:
    return {
        "breakdown": {
            "transportation_inr": 3200,
            "accommodation_inr": accommodation_inr,
            "food_inr": 9000,
            "activities_inr": activities_inr,
            "miscellaneous_inr": 2500,
        },
        "is_within_budget": is_within_budget,
        "budget_overrun_warning": None,
    }


def _make_activity(cost: float = 500.0, category: str = "sightseeing") -> ItineraryActivity:
    return ItineraryActivity(
        time="09:00",
        activity="Visit fort",
        location="Goa",
        duration_hours=2.0,
        estimated_cost_inr=cost,
        category=category,
    )


def _make_day(day_number: int, activity_cost: float = 500.0, acc_cost: float = 1500.0) -> ItineraryDay:
    today = date.today() + timedelta(days=7)
    return ItineraryDay(
        day_number=day_number,
        date_str=str(today + timedelta(days=day_number - 1)),
        location="Goa",
        activities=[_make_activity(cost=activity_cost)],
        accommodation="Mid-range hotel",
        accommodation_cost_inr=acc_cost,
    )


def _make_itinerary(num_days: int = 3) -> Itinerary:
    days = [_make_day(i + 1) for i in range(num_days)]
    return Itinerary(
        trip_title="Test Trip",
        origin="Mumbai",
        destination="Goa",
        start_date=str(date.today() + timedelta(days=7)),
        end_date=str(date.today() + timedelta(days=7 + num_days)),
        num_travellers=2,
        days=days,
        budget_breakdown=BudgetBreakdown(
            transportation_inr=3200,
            accommodation_inr=4500,
            food_inr=9000,
            activities_inr=1500,
            miscellaneous_inr=500,
        ),
        total_budget_inr=20000,
        is_simulated=False,
    )


# ─── ItineraryAgent: day count trimming ──────────────────────────────────────

class TestItineraryDayCountValidation:

    def _agent(self) -> ItineraryAgent:
        mock_svc = MagicMock()
        mock_svc.generate.side_effect = Exception("Granite unavailable")
        return ItineraryAgent(mock_svc)

    def test_template_covers_all_calendar_dates_inclusive(self):
        """Fallback template must produce exactly duration_days days."""
        agent = self._agent()
        request = _make_request(duration_days=4)
        budget_data = _make_budget_data()
        result = agent.generate(request, {}, {}, budget_data, {})
        assert len(result.days) == 5

    def test_trim_excess_days_from_raw(self):
        """If raw['days'] has more entries than duration_days, trim to duration_days."""
        agent = self._agent()
        request = _make_request(duration_days=3)
        # Build a raw dict with 5 days
        raw_days = [
            {"day_number": i + 1, "location": "Goa", "accommodation": "Hotel",
             "accommodation_cost_inr": 1500, "day_notes": None,
             "activities": [{"time": "09:00", "activity": f"Act {i+1}", "location": "Goa",
                             "duration_hours": 2.0, "estimated_cost_inr": 200, "category": "sightseeing"}]}
            for i in range(5)
        ]
        result = agent._build_itinerary_model(request, {"days": raw_days, "trip_title": "T", "highlights": []}, _make_budget_data(), False)
        assert len(result.days) == 4

    def test_pad_missing_days_from_raw(self):
        """If raw['days'] has fewer entries than duration_days, pad to duration_days."""
        agent = self._agent()
        request = _make_request(duration_days=4)
        # Build a raw dict with only 2 days
        raw_days = [
            {"day_number": i + 1, "location": "Goa", "accommodation": "Hotel",
             "accommodation_cost_inr": 1500, "day_notes": None,
             "activities": [{"time": "09:00", "activity": f"Act {i+1}", "location": "Goa",
                             "duration_hours": 2.0, "estimated_cost_inr": 200, "category": "sightseeing"}]}
            for i in range(2)
        ]
        result = agent._build_itinerary_model(request, {"days": raw_days, "trip_title": "T", "highlights": []}, _make_budget_data(), False)
        assert len(result.days) == 5

    def test_padded_days_sorted_by_day_number(self):
        """After padding, days must be sorted by day_number."""
        agent = self._agent()
        request = _make_request(duration_days=4)
        raw_days = [
            {"day_number": 1, "location": "Goa", "accommodation": "Hotel",
             "accommodation_cost_inr": 0, "day_notes": None,
             "activities": [{"time": "09:00", "activity": "Act", "location": "Goa",
                             "duration_hours": 1.0, "estimated_cost_inr": 0, "category": "sightseeing"}]},
        ]
        result = agent._build_itinerary_model(request, {"days": raw_days, "trip_title": "T", "highlights": []}, _make_budget_data(), False)
        assert len(result.days) == 5
        day_nums = [d.day_number for d in result.days]
        assert day_nums == sorted(day_nums)


# ─── ItineraryAgent: day_number clamping ─────────────────────────────────────

class TestDayNumberClamping:

    def test_day_number_above_duration_clamped(self):
        """day_number > duration_days must be clamped to duration_days."""
        agent = ItineraryAgent(MagicMock())
        request = _make_request(duration_days=3)
        # Day with day_number=10 for a 3-day trip
        raw_days = [
            {"day_number": 10, "location": "Goa", "accommodation": "Hotel",
             "accommodation_cost_inr": 0, "day_notes": None,
             "activities": [{"time": "09:00", "activity": "Act", "location": "Goa",
                             "duration_hours": 1.0, "estimated_cost_inr": 0, "category": "sightseeing"}]},
        ]
        result = agent._build_itinerary_model(
            request, {"days": raw_days, "trip_title": "T", "highlights": []}, _make_budget_data(), False
        )
        # The clamped day should have day_number <= 3
        for day in result.days:
            assert day.day_number <= 4

    def test_day_number_zero_clamped_to_one(self):
        """day_number=0 must be clamped to 1."""
        agent = ItineraryAgent(MagicMock())
        request = _make_request(duration_days=3)
        raw_days = [
            {"day_number": 0, "location": "Goa", "accommodation": "Hotel",
             "accommodation_cost_inr": 0, "day_notes": None,
             "activities": [{"time": "09:00", "activity": "Act", "location": "Goa",
                             "duration_hours": 1.0, "estimated_cost_inr": 0, "category": "sightseeing"}]},
        ]
        result = agent._build_itinerary_model(
            request, {"days": raw_days, "trip_title": "T", "highlights": []}, _make_budget_data(), False
        )
        for day in result.days:
            assert day.day_number >= 1


# ─── ItineraryAgent: activity cost guard ─────────────────────────────────────

class TestActivityCostGuard:

    def test_no_warning_when_activities_within_budget(self):
        """No activity cost warning when total is within 110% of budget."""
        agent = ItineraryAgent(MagicMock())
        request = _make_request(duration_days=2, budget=50000)
        # Each day has one activity costing 500 = total 1000, budget 5000
        raw_days = [
            {"day_number": i + 1, "location": "Goa", "accommodation": "Hotel",
             "accommodation_cost_inr": 1500, "day_notes": None,
             "activities": [{"time": "09:00", "activity": "Act", "location": "Goa",
                             "duration_hours": 2.0, "estimated_cost_inr": 500, "category": "sightseeing"}]}
            for i in range(2)
        ]
        result = agent._build_itinerary_model(
            request, {"days": raw_days, "trip_title": "T", "highlights": []},
            _make_budget_data(activities_inr=5000), False,
        )
        # No activity cost warning in warnings
        activity_cost_warnings = [w for w in result.warnings if "activity costs" in w.lower()]
        assert activity_cost_warnings == []

    def test_warning_when_activities_exceed_110_pct(self):
        """Activity cost warning emitted when total exceeds 110% of activities budget."""
        agent = ItineraryAgent(MagicMock())
        request = _make_request(duration_days=2, budget=50000)
        # Activities cost 7000 total, budget 5000 → 140% → should warn
        raw_days = [
            {"day_number": i + 1, "location": "Goa", "accommodation": "Hotel",
             "accommodation_cost_inr": 0, "day_notes": None,
             "activities": [{"time": "09:00", "activity": "Act", "location": "Goa",
                             "duration_hours": 2.0, "estimated_cost_inr": 3500, "category": "sightseeing"}]}
            for i in range(2)
        ]
        result = agent._build_itinerary_model(
            request, {"days": raw_days, "trip_title": "T", "highlights": []},
            _make_budget_data(activities_inr=5000), False,
        )
        activity_cost_warnings = [w for w in result.warnings if "activity costs" in w.lower()]
        assert len(activity_cost_warnings) == 1
        assert "₹" in activity_cost_warnings[0]

    def test_flags_any_activity_cost_over_allocated_budget(self):
        """Any amount above the allocated activities budget must trigger a warning."""
        agent = ItineraryAgent(MagicMock())
        request = _make_request(duration_days=1, budget=50000)
        # 1 day, 1 activity costing 5500 exceeds the 5000 allocation → warn
        raw_days = [
            {"day_number": 1, "location": "Goa", "accommodation": "Hotel",
             "accommodation_cost_inr": 0, "day_notes": None,
             "activities": [{"time": "09:00", "activity": "Act", "location": "Goa",
                             "duration_hours": 2.0, "estimated_cost_inr": 5500, "category": "sightseeing"}]}
        ]
        result = agent._build_itinerary_model(
            request, {"days": raw_days, "trip_title": "T", "highlights": []},
            _make_budget_data(activities_inr=5000), False,
        )
        activity_cost_warnings = [w for w in result.warnings if "activity costs" in w.lower()]
        assert len(activity_cost_warnings) == 1

    def test_budget_overrun_warning_propagated(self):
        """budget_overrun_warning from BudgetAgent is propagated to itinerary warnings."""
        agent = ItineraryAgent(MagicMock())
        request = _make_request(duration_days=2, budget=50000)
        raw_days = [
            {"day_number": 1, "location": "Goa", "accommodation": "Hotel",
             "accommodation_cost_inr": 0, "day_notes": None,
             "activities": [{"time": "09:00", "activity": "Act", "location": "Goa",
                             "duration_hours": 2.0, "estimated_cost_inr": 100, "category": "sightseeing"}]},
        ]
        budget_data = _make_budget_data()
        budget_data["budget_overrun_warning"] = "Estimated cost ₹51,000 exceeds your budget of ₹50,000 by ₹1,000."
        result = agent._build_itinerary_model(
            request, {"days": raw_days, "trip_title": "T", "highlights": []}, budget_data, False
        )
        overrun_warnings = [w for w in result.warnings if "51,000" in w or "exceeds" in w.lower()]
        assert len(overrun_warnings) >= 1


# ─── ReplanningAgent: cost guard ─────────────────────────────────────────────

class TestReplanningCostGuard:

    def test_no_warning_when_revised_cost_within_115_pct(self):
        """No cost warning when revised day total <= 115% of original."""
        agent = ReplanningAgent(MagicMock())
        itinerary = _make_itinerary(num_days=3)
        original_day = itinerary.days[0]   # day_number=1, activity 500 + acc 1500 = 2000
        # Revised: activity cost 700 + acc 1500 = 2200 (110% of 2000) → no warning
        revision_data = {
            "revised_day_activities": [
                {"time": "09:00", "activity": "Indoor museum", "location": "Goa",
                 "duration_hours": 2.0, "estimated_cost_inr": 700, "category": "culture"}
            ],
            "changes_made": ["Moved indoors."],
            "reason": "Weather disruption.",
            "revised_accommodation": None,
        }
        result = agent._apply_revision(itinerary, 1, revision_data, original_day, False)
        cost_warnings = [w for w in result.warnings if "more than the original" in w]
        assert cost_warnings == []

    def test_warning_when_revised_cost_exceeds_115_pct(self):
        """Cost warning emitted when revised day total > 115% of original."""
        agent = ReplanningAgent(MagicMock())
        itinerary = _make_itinerary(num_days=3)
        original_day = itinerary.days[0]   # total_day_cost_inr = 500 + 1500 = 2000
        # Revised: activity cost 5000 → new total = 5000 + 1500 = 6500 → 325% of original
        revision_data = {
            "revised_day_activities": [
                {"time": "09:00", "activity": "Luxury spa", "location": "Goa",
                 "duration_hours": 4.0, "estimated_cost_inr": 5000, "category": "wellness"}
            ],
            "changes_made": ["Added luxury alternative."],
            "reason": "Weather.",
            "revised_accommodation": None,
        }
        result = agent._apply_revision(itinerary, 1, revision_data, original_day, False)
        cost_warnings = [w for w in result.warnings if "revision" in w.lower() and "rejected" in w.lower()]
        assert len(cost_warnings) == 1
        assert "₹" in cost_warnings[0]

    def test_no_false_positive_when_original_cost_is_zero(self):
        """When original day cost is 0, the cost guard must not trigger."""
        agent = ReplanningAgent(MagicMock())
        itinerary = _make_itinerary(num_days=3)
        # Create a day with zero costs
        zero_day = ItineraryDay(
            day_number=1,
            date_str=str(date.today() + timedelta(days=8)),
            location="Goa",
            activities=[],
            accommodation_cost_inr=0.0,
        )
        revision_data = {
            "revised_day_activities": [
                {"time": "09:00", "activity": "Anything", "location": "Goa",
                 "duration_hours": 1.0, "estimated_cost_inr": 10000, "category": "sightseeing"}
            ],
            "changes_made": [],
            "reason": "Test.",
            "revised_accommodation": None,
        }
        result = agent._apply_revision(itinerary, 1, revision_data, zero_day, False)
        cost_warnings = [w for w in result.warnings if "more than the original" in w]
        assert cost_warnings == []


# ─── ReplanningAgent: simulation disclaimer ──────────────────────────────────

class TestReplanningSimulationDisclaimer:

    def test_fallback_includes_simulation_disclaimer(self):
        """When is_fallback=True, the simulation disclaimer must appear in warnings."""
        agent = ReplanningAgent(MagicMock())
        itinerary = _make_itinerary(num_days=3)
        original_day = itinerary.days[0]
        revision_data = agent._fallback_replan(original_day, "weather")
        result = agent._apply_revision(itinerary, 1, revision_data, original_day, is_fallback=True)
        disclaimer_warnings = [w for w in result.warnings if "simulated" in w.lower()]
        assert len(disclaimer_warnings) >= 1

    def test_no_disclaimer_when_granite_used(self):
        """When is_fallback=False (Granite path), no simulation disclaimer in warnings."""
        agent = ReplanningAgent(MagicMock())
        itinerary = _make_itinerary(num_days=3)
        original_day = itinerary.days[0]
        revision_data = {
            "revised_day_activities": [
                {"time": "09:00", "activity": "Museum", "location": "Goa",
                 "duration_hours": 2.0, "estimated_cost_inr": 300, "category": "culture"}
            ],
            "changes_made": ["Replaced outdoor activity."],
            "reason": "Heavy rain forecast.",
            "revised_accommodation": None,
        }
        result = agent._apply_revision(itinerary, 1, revision_data, original_day, is_fallback=False)
        disclaimer_warnings = [w for w in result.warnings if "simulated" in w.lower()]
        assert disclaimer_warnings == []

    def test_fallback_replan_dict_contains_disclaimer_key(self):
        """_fallback_replan() must include 'simulation_disclaimer' key."""
        agent = ReplanningAgent(MagicMock())
        day = _make_day(1)
        result = agent._fallback_replan(day, "weather")
        assert "simulation_disclaimer" in result
        assert len(result["simulation_disclaimer"]) > 20

    def test_requires_user_approval_always_true(self):
        """ReplanningResult.requires_user_approval must always be True."""
        mock_svc = MagicMock()
        mock_svc.generate.side_effect = Exception("Granite unavailable")
        agent = ReplanningAgent(mock_svc)
        itinerary = _make_itinerary(num_days=3)
        result = agent.replan(itinerary, "weather", "Heavy rainfall", 1)
        assert result.requires_user_approval is True


# ─── WeatherAgent: data disclaimer ───────────────────────────────────────────

class TestWeatherDisclaimer:

    def test_data_disclaimer_in_weather_output(self):
        """WeatherAgent.analyze() must include 'data_disclaimer' in the return dict."""
        mock_svc = MagicMock()
        mock_svc.generate.side_effect = Exception("Granite unavailable")
        agent = WeatherAgent(mock_svc)
        request = _make_request(duration_days=3)

        with patch("agents.weather_agent.get_weather_forecast", return_value=None):
            result = agent.analyze(request)

        assert "data_disclaimer" in result
        disclaimer = result["data_disclaimer"]
        assert "Open-Meteo" in disclaimer
        assert "AI-generated" in disclaimer
        assert "not an official" in disclaimer

    def test_data_disclaimer_present_when_forecast_unavailable(self):
        """Disclaimer appears even when forecast data is unavailable."""
        mock_svc = MagicMock()
        mock_svc.generate.side_effect = Exception("unavailable")
        agent = WeatherAgent(mock_svc)
        request = _make_request(duration_days=3)

        with patch("agents.weather_agent.get_weather_forecast", return_value=None):
            result = agent.analyze(request)

        assert "data_disclaimer" in result

    def test_data_source_field_present(self):
        """data_source field must always be present in WeatherAgent output."""
        mock_svc = MagicMock()
        mock_svc.generate.side_effect = Exception("unavailable")
        agent = WeatherAgent(mock_svc)
        request = _make_request()

        with patch("agents.weather_agent.get_weather_forecast", return_value=None):
            result = agent.analyze(request)

        assert "data_source" in result
        assert result["data_source"] == "No data"


def test_jaipur_november_12_to_18_covers_seven_calendar_dates():
    """12–18 Nov inclusive is seven itinerary dates and six overnight stays."""
    agent = ItineraryAgent(MagicMock())
    request = _make_request(duration_days=6)
    # Explicitly pin the regression dates rather than relying on helper defaults.
    from datetime import date
    request.start_date = date(2026, 11, 12)
    request.end_date = date(2026, 11, 18)
    result = agent.generate(request, {}, {}, _make_budget_data(), {})
    assert len(result.days) == 7
    assert result.days[0].date_str == "2026-11-12"
    assert result.days[-1].date_str == "2026-11-18"
    assert sum(1 for day in result.days if day.accommodation) <= 6
