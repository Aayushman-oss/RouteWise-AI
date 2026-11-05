"""
RouteWise AI – Pydantic Data Models: TravelRequest
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import config


class TravelRequest(BaseModel):
    """Validated travel planning request from the user."""

    origin: str = Field(..., min_length=2, max_length=100, description="Departure city or location")
    destination: str = Field(..., min_length=2, max_length=100, description="Destination city or region")
    start_date: date = Field(..., description="Travel start date")
    end_date: date = Field(..., description="Travel end date")
    num_travellers: int = Field(..., ge=1, le=50, description="Number of travellers")
    budget_inr: float = Field(..., ge=config.MIN_BUDGET_INR, le=config.MAX_BUDGET_INR, description="Total budget in INR")
    accommodation_preference: str = Field(
        default="mid-range",
        description="budget / mid-range / luxury / homestay",
    )
    transport_preference: str = Field(
        default="mixed",
        description="train / bus / flight / car / mixed",
    )
    interests: List[str] = Field(
        default_factory=list,
        description="E.g. ['history', 'food', 'adventure', 'nature']",
    )
    additional_notes: Optional[str] = Field(
        default=None,
        max_length=config.MAX_PROMPT_CHARS,
        description="Free-text additional preferences",
    )

    @field_validator("origin", "destination", mode="before")
    @classmethod
    def sanitize_location(cls, v: str) -> str:
        # Strip and limit characters to safe printable set
        import re
        v = str(v).strip()
        v = re.sub(r"[^\w\s\-,.]", "", v)
        return v[:100]

    @field_validator("additional_notes", mode="before")
    @classmethod
    def sanitize_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        from utils.security import sanitize_for_prompt
        return sanitize_for_prompt(str(v).strip(), max_len=config.MAX_PROMPT_CHARS)

    @model_validator(mode="after")
    def validate_dates(self) -> "TravelRequest":
        today = date.today()
        if self.start_date < today:
            raise ValueError("Start date cannot be in the past.")
        if self.end_date <= self.start_date:
            raise ValueError("End date must be after start date.")
        if (self.end_date - self.start_date).days > 90:
            raise ValueError("Trip duration cannot exceed 90 days.")
        return self

    @property
    def duration_days(self) -> int:
        return (self.end_date - self.start_date).days

    @property
    def budget_per_day_inr(self) -> float:
        return self.budget_inr / max(self.duration_days, 1)

    @property
    def budget_per_person_inr(self) -> float:
        return self.budget_inr / max(self.num_travellers, 1)

    def to_prompt_context(self) -> str:
        """Return a sanitized string summary safe for embedding in prompts."""
        interests_str = ", ".join(self.interests) if self.interests else "general sightseeing"
        return (
            f"Origin: {self.origin}\n"
            f"Destination: {self.destination}\n"
            f"Travel dates: {self.start_date} to {self.end_date} ({self.duration_days} days)\n"
            f"Travellers: {self.num_travellers}\n"
            f"Total budget: ₹{self.budget_inr:,.0f} (₹{self.budget_per_day_inr:,.0f}/day)\n"
            f"Accommodation: {self.accommodation_preference}\n"
            f"Transport: {self.transport_preference}\n"
            f"Interests: {interests_str}\n"
        )
