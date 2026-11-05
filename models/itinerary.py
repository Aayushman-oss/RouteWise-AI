"""
RouteWise AI – Itinerary Data Model
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class ItineraryActivity(BaseModel):
    time: str = Field(..., description="Suggested time, e.g. '09:00'")
    activity: str
    location: str
    duration_hours: float = Field(..., ge=0.25, le=12.0)
    transport: Optional[str] = None
    estimated_cost_inr: float = Field(default=0.0, ge=0.0)
    notes: Optional[str] = None
    category: str = Field(default="general", description="sightseeing / food / adventure / culture / transit")


class ItineraryDay(BaseModel):
    day_number: int = Field(..., ge=1)
    date_str: str
    location: str
    activities: List[ItineraryActivity] = Field(default_factory=list)
    accommodation: Optional[str] = None
    accommodation_cost_inr: float = Field(default=0.0, ge=0.0)
    day_notes: Optional[str] = None

    @property
    def total_activity_cost_inr(self) -> float:
        return sum(a.estimated_cost_inr for a in self.activities)

    @property
    def total_day_cost_inr(self) -> float:
        return self.total_activity_cost_inr + self.accommodation_cost_inr


class BudgetBreakdown(BaseModel):
    transportation_inr: float = Field(default=0.0, ge=0.0)
    accommodation_inr: float = Field(default=0.0, ge=0.0)
    food_inr: float = Field(default=0.0, ge=0.0)
    activities_inr: float = Field(default=0.0, ge=0.0)
    miscellaneous_inr: float = Field(default=0.0, ge=0.0)

    @property
    def total_inr(self) -> float:
        return (
            self.transportation_inr
            + self.accommodation_inr
            + self.food_inr
            + self.activities_inr
            + self.miscellaneous_inr
        )


class Itinerary(BaseModel):
    trip_title: str
    origin: str
    destination: str
    start_date: str
    end_date: str
    num_travellers: int
    days: List[ItineraryDay] = Field(default_factory=list)
    budget_breakdown: BudgetBreakdown = Field(default_factory=BudgetBreakdown)
    total_budget_inr: float = Field(default=0.0)
    highlights: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    is_simulated: bool = Field(default=True, description="True when data is estimated/demo")
    generation_notes: Optional[str] = None

    @property
    def total_estimated_cost_inr(self) -> float:
        return self.budget_breakdown.total_inr

    @property
    def budget_utilisation_pct(self) -> float:
        if self.total_budget_inr <= 0:
            return 0.0
        return min((self.total_estimated_cost_inr / self.total_budget_inr) * 100, 999.0)

    @property
    def is_within_budget(self) -> bool:
        return self.total_estimated_cost_inr <= self.total_budget_inr


class ReplanningRequest(BaseModel):
    disruption_type: str = Field(..., description="weather / transport / safety / personal")
    disruption_description: str = Field(..., max_length=500)
    affected_day: int = Field(..., ge=1)
    original_itinerary: Itinerary


class ReplanningResult(BaseModel):
    revised_itinerary: Itinerary
    changes_made: List[str] = Field(default_factory=list)
    reason: str
    requires_user_approval: bool = True
    approved: bool = False
