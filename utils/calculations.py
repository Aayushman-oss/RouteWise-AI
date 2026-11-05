"""
RouteWise AI – Budget and Travel Calculations
"""

from __future__ import annotations

from typing import Dict, Optional
from models.itinerary import BudgetBreakdown


# ─── Accommodation cost benchmarks (INR per night per room) ─────────────────

ACCOMMODATION_COSTS: Dict[str, Dict[str, float]] = {
    "budget": {"metro": 800, "tier2": 600, "hill": 700, "beach": 750},
    "mid-range": {"metro": 2500, "tier2": 1800, "hill": 2200, "beach": 2800},
    "luxury": {"metro": 8000, "tier2": 5000, "hill": 7000, "beach": 9000},
    "homestay": {"metro": 1200, "tier2": 900, "hill": 1100, "beach": 1000},
}

# Approximate per-person per-day food cost (INR)
FOOD_COSTS: Dict[str, float] = {
    "budget": 400,
    "mid-range": 900,
    "luxury": 2500,
    "homestay": 500,
}

# Intercity transport cost per km per person (INR) for rough estimates
TRANSPORT_COST_PER_KM: Dict[str, float] = {
    "train": 0.8,
    "bus": 0.6,
    "flight": 5.5,
    "car": 2.5,
    "mixed": 1.5,
}


def estimate_accommodation_cost(
    accommodation_type: str,
    destination_type: str,
    num_nights: int,
    num_travellers: int,
) -> float:
    """Estimate total accommodation cost in INR."""
    acc_type = accommodation_type.lower() if accommodation_type.lower() in ACCOMMODATION_COSTS else "mid-range"
    dest_type = destination_type.lower() if destination_type.lower() in list(ACCOMMODATION_COSTS["mid-range"].keys()) else "tier2"
    cost_per_room_night = ACCOMMODATION_COSTS[acc_type][dest_type]
    rooms_needed = max(1, (num_travellers + 1) // 2)
    return cost_per_room_night * num_nights * rooms_needed


def estimate_food_cost(
    accommodation_type: str,
    num_days: int,
    num_travellers: int,
) -> float:
    """Estimate total food cost in INR."""
    acc_type = accommodation_type.lower() if accommodation_type.lower() in FOOD_COSTS else "mid-range"
    daily_per_person = FOOD_COSTS[acc_type]
    return daily_per_person * num_days * num_travellers


def estimate_transport_cost(
    distance_km: float,
    transport_type: str,
    num_travellers: int,
) -> float:
    """Estimate round-trip transport cost in INR."""
    t = transport_type.lower() if transport_type.lower() in TRANSPORT_COST_PER_KM else "mixed"
    cost_per_person = distance_km * TRANSPORT_COST_PER_KM[t] * 2  # round trip
    return cost_per_person * num_travellers


class BudgetValidationResult:
    """Carries a BudgetBreakdown together with validation metadata."""

    __slots__ = ("breakdown", "budget_exceeded_by_inr", "was_scaled", "nights_used", "warning")

    def __init__(
        self,
        breakdown: BudgetBreakdown,
        budget_exceeded_by_inr: float,
        was_scaled: bool,
        nights_used: int,
        warning: Optional[str],
    ) -> None:
        self.breakdown = breakdown
        self.budget_exceeded_by_inr = budget_exceeded_by_inr
        self.was_scaled = was_scaled
        self.nights_used = nights_used
        self.warning = warning


def build_budget_breakdown(
    total_budget_inr: float,
    accommodation_type: str,
    destination_type: str,
    num_days: int,
    num_travellers: int,
    transport_type: str,
    distance_km: float = 500.0,
) -> BudgetBreakdown:
    """
    Build a deterministic budget breakdown.

    Rules enforced by Python (Granite is not involved here):
    - num_nights is max(0, num_days - 1) — safe for 1-day trips.
    - Fixed costs (transport + accommodation + food) are calculated first.
    - Activities is allocated from *remaining capacity*, not a fixed % of total.
    - Miscellaneous is 5% of total budget, floored at zero.
    - Estimated costs are never artificially scaled down to conceal an overrun.
    - If fixed costs exceed the budget, the returned breakdown preserves those
      estimates and validation must flag the overrun.
    """
    # Guard: a 1-day trip has 0 accommodation nights; 0-day trips not valid but
    # clamp rather than raising so the agent never crashes on bad input.
    nights = max(0, num_days - 1)

    accommodation = estimate_accommodation_cost(
        accommodation_type, destination_type, nights, num_travellers
    )
    food = estimate_food_cost(accommodation_type, num_days, num_travellers)
    transport = estimate_transport_cost(distance_km, transport_type, num_travellers)

    # Fixed costs first — activities get only what remains.
    misc = total_budget_inr * 0.05
    fixed_used = accommodation + food + transport + misc
    remaining_for_activities = max(0.0, total_budget_inr - fixed_used)
    # Activities capped to remaining capacity (up to 10% of total budget).
    activities = min(remaining_for_activities, total_budget_inr * 0.10)

    # Never scale down real estimated fixed costs to make a plan appear
    # affordable. Preserve estimates and let validation report an overrun.
    total_estimated = accommodation + food + transport + activities + misc
    was_scaled = False

    return BudgetBreakdown(
        transportation_inr=round(transport, 2),
        accommodation_inr=round(accommodation, 2),
        food_inr=round(food, 2),
        activities_inr=round(activities, 2),
        miscellaneous_inr=round(misc, 2),
    )


def validate_budget_breakdown(
    breakdown: BudgetBreakdown,
    total_budget_inr: float,
) -> Optional[str]:
    """
    Post-construction check: return a warning string if the breakdown total
    exceeds the user's budget, or None when it is within bounds.

    Use this after build_budget_breakdown() to surface a flag to the UI.
    """
    excess = breakdown.total_inr - total_budget_inr
    if excess > 0.01:  # 1 paisa tolerance for floating-point
        return (
            f"Estimated cost {format_inr(breakdown.total_inr)} exceeds your budget "
            f"of {format_inr(total_budget_inr)} by {format_inr(excess)}."
        )
    return None


def percentage_of(part: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100, 1)


def format_inr(amount: float) -> str:
    """Format a float as Indian Rupees using Indian lakh/crore grouping.

    Examples:
        1000       → ₹1,000
        10000      → ₹10,000
        100000     → ₹1,00,000
        10000000   → ₹1,00,00,000
    """
    amount = round(amount)
    if amount < 0:
        return f"-{format_inr(-amount)}"
    s = str(int(amount))
    # First group: last 3 digits
    if len(s) <= 3:
        return f"₹{s}"
    result = s[-3:]
    s = s[:-3]
    # Subsequent groups: 2 digits each (Indian system)
    while s:
        result = s[-2:] + "," + result
        s = s[:-2]
    return "₹" + result
