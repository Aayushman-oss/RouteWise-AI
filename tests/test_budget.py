"""
RouteWise AI – Tests: Budget Calculations
"""

import pytest
from utils.calculations import (
    estimate_accommodation_cost,
    estimate_food_cost,
    estimate_transport_cost,
    build_budget_breakdown,
    validate_budget_breakdown,
    format_inr,
    percentage_of,
)
from models.itinerary import BudgetBreakdown


def test_accommodation_mid_range_tier2():
    cost = estimate_accommodation_cost("mid-range", "tier2", num_nights=3, num_travellers=2)
    # 2 travellers → 1 room, 1800/night × 3 nights
    assert cost == pytest.approx(1800 * 3, rel=0.01)


def test_accommodation_rooms_for_large_group():
    cost_2 = estimate_accommodation_cost("mid-range", "tier2", 3, 2)
    cost_4 = estimate_accommodation_cost("mid-range", "tier2", 3, 4)
    # 4 travellers need 2 rooms
    assert cost_4 == pytest.approx(cost_2 * 2, rel=0.01)


def test_food_cost_scales_with_travellers():
    cost_1 = estimate_food_cost("mid-range", 5, 1)
    cost_3 = estimate_food_cost("mid-range", 5, 3)
    assert cost_3 == pytest.approx(cost_1 * 3, rel=0.01)


def test_transport_cost_round_trip():
    cost = estimate_transport_cost(500.0, "train", 2)
    # 500 km × 0.8 ₹/km × 2 (round trip) × 2 travellers = 1600
    assert cost == pytest.approx(1600.0, rel=0.01)


def test_budget_breakdown_within_budget():
    bd = build_budget_breakdown(
        total_budget_inr=50000,
        accommodation_type="mid-range",
        destination_type="tier2",
        num_days=5,
        num_travellers=2,
        transport_type="train",
        distance_km=500,
    )
    assert isinstance(bd, BudgetBreakdown)
    assert bd.total_inr <= 50000 * 1.1  # allow 10% tolerance
    assert bd.transportation_inr >= 0
    assert bd.accommodation_inr >= 0
    assert bd.food_inr >= 0


def test_budget_breakdown_tight_budget_reports_actual_overrun():
    bd = build_budget_breakdown(
        total_budget_inr=5000,  # very tight
        accommodation_type="budget",
        destination_type="tier2",
        num_days=3,
        num_travellers=1,
        transport_type="bus",
        distance_km=200,
    )
    # Preserve estimated costs and surface the overrun rather than scaling costs down.
    assert bd.total_inr <= 5000
    assert validate_budget_breakdown(bd, 5000) is None


def test_format_inr():
    assert format_inr(1000) == "₹1,000"
    assert format_inr(100000) == "₹1,00,000"


def test_percentage_of():
    assert percentage_of(500, 1000) == 50.0
    assert percentage_of(0, 1000) == 0.0
    assert percentage_of(500, 0) == 0.0


def test_budget_breakdown_fields_non_negative():
    bd = BudgetBreakdown(
        transportation_inr=1000,
        accommodation_inr=2000,
        food_inr=1500,
        activities_inr=500,
        miscellaneous_inr=300,
    )
    assert bd.total_inr == pytest.approx(5300, rel=0.01)


# ─── New: deterministic validation improvements ───────────────────────────────

def test_budget_breakdown_preserves_real_costs_and_flags_overrun():
    """Actual fixed estimates are not scaled down to conceal an over-budget trip."""
    for budget in [5000, 15000, 50000, 200000]:
        bd = build_budget_breakdown(
            total_budget_inr=budget,
            accommodation_type="mid-range",
            destination_type="tier2",
            num_days=5,
            num_travellers=2,
            transport_type="train",
            distance_km=500,
        )
        warning = validate_budget_breakdown(bd, budget)
        if bd.total_inr > budget + 0.01:
            assert warning is not None
        else:
            assert warning is None


def test_budget_breakdown_activities_capped_to_remaining():
    """Activities must not exceed what remains after fixed costs, even on a tight budget."""
    bd = build_budget_breakdown(
        total_budget_inr=8000,
        accommodation_type="luxury",
        destination_type="metro",
        num_days=3,
        num_travellers=2,
        transport_type="flight",
        distance_km=1000,
    )
    fixed = bd.accommodation_inr + bd.food_inr + bd.transportation_inr + bd.miscellaneous_inr
    # Activities get no allocation when fixed costs already exceed the budget.
    assert bd.activities_inr == 0
    assert validate_budget_breakdown(bd, 8000) is not None


def test_budget_breakdown_single_day_trip_no_crash():
    """A 1-day trip produces 0 accommodation nights — must not crash or return negative."""
    bd = build_budget_breakdown(
        total_budget_inr=10000,
        accommodation_type="mid-range",
        destination_type="tier2",
        num_days=1,
        num_travellers=1,
        transport_type="train",
        distance_km=200,
    )
    assert bd.accommodation_inr >= 0
    assert bd.total_inr <= 10000 + 0.01


def test_budget_breakdown_single_day_zero_nights():
    """Accommodation cost for 1-day trip must be 0 (num_nights = max(0, 1-1) = 0)."""
    bd = build_budget_breakdown(
        total_budget_inr=10000,
        accommodation_type="mid-range",
        destination_type="tier2",
        num_days=1,
        num_travellers=1,
        transport_type="train",
        distance_km=200,
    )
    assert bd.accommodation_inr == 0.0


def test_validate_budget_breakdown_no_warning_within_budget():
    """validate_budget_breakdown returns None when total <= budget."""
    bd = BudgetBreakdown(
        transportation_inr=1000,
        accommodation_inr=2000,
        food_inr=1000,
        activities_inr=500,
        miscellaneous_inr=200,
    )
    assert validate_budget_breakdown(bd, 10000) is None


def test_validate_budget_breakdown_warning_when_over():
    """validate_budget_breakdown returns a warning string when total > budget."""
    bd = BudgetBreakdown(
        transportation_inr=5000,
        accommodation_inr=5000,
        food_inr=3000,
        activities_inr=2000,
        miscellaneous_inr=1000,
    )  # total = 16000
    warning = validate_budget_breakdown(bd, 15000)
    assert warning is not None
    assert "exceeds" in warning.lower()
    assert "₹" in warning


def test_validate_budget_breakdown_floating_point_tolerance():
    """Tiny floating-point differences (< 1 paisa) should not trigger a warning."""
    bd = BudgetBreakdown(
        transportation_inr=1000.004,
        accommodation_inr=0,
        food_inr=0,
        activities_inr=0,
        miscellaneous_inr=0,
    )
    # total = 1000.004, budget = 1000 → excess = 0.004 < 0.01 threshold
    assert validate_budget_breakdown(bd, 1000) is None
