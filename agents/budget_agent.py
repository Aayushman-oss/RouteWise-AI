"""
RouteWise AI – Budget Optimization Agent
All arithmetic is done in Python; Granite provides narrative reasoning.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from models.travel_request import TravelRequest
from models.itinerary import BudgetBreakdown
from services.watsonx_service import WatsonxService
from utils.calculations import build_budget_breakdown, validate_budget_breakdown, format_inr

logger = logging.getLogger("routewise.agent.budget")

SYSTEM_CONTEXT = """You are a travel budget advisor for India.
Given a budget breakdown, provide:
- budget_assessment: one-sentence assessment (is it realistic?)
- cost_saving_tips: list of 3 specific money-saving tips for this trip
- splurge_suggestions: list of 2 things worth spending a bit more on
- budget_warning: null or a brief warning if the budget is very tight

Respond ONLY with valid JSON. No markdown, no extra text."""


class BudgetAgent:
    def __init__(self, watsonx: WatsonxService) -> None:
        self.watsonx = watsonx

    def analyze(
        self,
        request: TravelRequest,
        route_data: Dict[str, Any],
        preference_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        # Python handles all math
        distance_km = route_data.get("route_info", {}).get("distance_km", 500.0)
        dest_type = preference_profile.get("destination_type", "tier2")

        breakdown = build_budget_breakdown(
            total_budget_inr=request.budget_inr,
            accommodation_type=request.accommodation_preference,
            destination_type=dest_type,
            num_days=request.duration_days,
            num_travellers=request.num_travellers,
            transport_type=request.transport_preference,
            distance_km=distance_km,
        )

        # Deterministic validation: check if breakdown exceeds budget (should
        # not happen after the fix to build_budget_breakdown, but kept as a
        # safety net in case upstream values shift).
        budget_overrun_warning = validate_budget_breakdown(breakdown, request.budget_inr)
        if budget_overrun_warning:
            logger.warning("BudgetAgent: %s", budget_overrun_warning)

        is_tight = breakdown.total_inr > request.budget_inr * 0.95
        budget_surplus = request.budget_inr - breakdown.total_inr

        # Granite for narrative advisory
        prompt = self._build_prompt(request, breakdown, is_tight)
        granite_advice: Dict[str, Any] = {}
        try:
            result = self.watsonx.generate(prompt, max_tokens=300)
            parsed = self._parse_json(result.text)
            if parsed:
                granite_advice = parsed
                logger.info("BudgetAgent: Granite narrative complete.")
        except Exception as exc:
            logger.warning("BudgetAgent: Granite unavailable (%s), using fallback.", type(exc).__name__)
            granite_advice = self._fallback_advice(request, breakdown, is_tight)

        return {
            "breakdown": breakdown.model_dump(),
            "total_estimated_inr": breakdown.total_inr,
            "budget_surplus_inr": budget_surplus,
            "is_within_budget": breakdown.total_inr <= request.budget_inr,
            "is_tight": is_tight,
            "utilisation_pct": round((breakdown.total_inr / request.budget_inr) * 100, 1),
            "budget_overrun_warning": budget_overrun_warning,
            **granite_advice,
        }

    def _build_prompt(self, request: TravelRequest, breakdown: BudgetBreakdown, is_tight: bool) -> str:
        return (
            f"{SYSTEM_CONTEXT}\n\n"
            f"Destination: {request.destination}\n"
            f"Duration: {request.duration_days} days, {request.num_travellers} traveller(s)\n"
            f"Total budget: {format_inr(request.budget_inr)}\n"
            f"Breakdown:\n"
            f"  Transport: {format_inr(breakdown.transportation_inr)}\n"
            f"  Accommodation: {format_inr(breakdown.accommodation_inr)}\n"
            f"  Food: {format_inr(breakdown.food_inr)}\n"
            f"  Activities: {format_inr(breakdown.activities_inr)}\n"
            f"  Miscellaneous: {format_inr(breakdown.miscellaneous_inr)}\n"
            f"  TOTAL: {format_inr(breakdown.total_inr)}\n"
            f"Budget tight: {'Yes' if is_tight else 'No'}\n\n"
            f"Return JSON:"
        )

    def _parse_json(self, text: str) -> Optional[Dict]:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception:
            pass
        return None

    def _fallback_advice(self, request: TravelRequest, breakdown: BudgetBreakdown, is_tight: bool) -> Dict:
        tips = [
            "Travel by sleeper class train for long distances.",
            "Eat at local dhabas for authentic and affordable meals.",
            "Book accommodation 4-6 weeks in advance for better rates.",
        ]
        splurge = ["One guided heritage tour", "A quality seafood dinner"]
        warning = "Budget is very tight – consider reducing trip duration." if is_tight else None
        return {
            "budget_assessment": f"Your budget of {format_inr(request.budget_inr)} is {'tight but' if is_tight else ''} manageable for this trip.",
            "cost_saving_tips": tips,
            "splurge_suggestions": splurge,
            "budget_warning": warning,
        }
