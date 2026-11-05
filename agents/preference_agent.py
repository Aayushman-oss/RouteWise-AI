"""
RouteWise AI – Travel Preference Agent
Interprets and enriches user travel preferences using IBM Granite.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from models.travel_request import TravelRequest
from services.watsonx_service import WatsonxService
from utils.security import sanitize_for_prompt

logger = logging.getLogger("routewise.agent.preference")

SYSTEM_CONTEXT = """You are a travel preferences analyst for an Indian travel platform.
Given user travel requirements, return a JSON object with these keys:
- destination_type: one of [metro, tier2, hill, beach, heritage, adventure, spiritual]
- travel_style: one of [budget, mid-range, luxury]
- primary_interest: the single most relevant interest from the user's list
- recommended_accommodation: specific accommodation recommendation
- flexibility_score: 1-5 (5 = very flexible itinerary)
- key_priorities: list of 3 most important things for this trip
- special_considerations: any notes about traveller count, budget constraints, or accessibility

Respond ONLY with valid JSON. No markdown, no extra text."""


class PreferenceAgent:
    def __init__(self, watsonx: WatsonxService) -> None:
        self.watsonx = watsonx

    def analyze(self, request: TravelRequest) -> Dict[str, Any]:
        """
        Analyze travel request with Granite and return enriched preference profile.
        Falls back to deterministic inference if Granite is unavailable.
        """
        prompt = self._build_prompt(request)
        try:
            result = self.watsonx.generate(prompt, max_tokens=300)
            parsed = self._parse_json_response(result.text)
            if parsed:
                logger.info("PreferenceAgent: Granite analysis complete.")
                return parsed
        except Exception as exc:
            logger.warning("PreferenceAgent: Granite unavailable (%s), using fallback.", type(exc).__name__)

        return self._fallback_analysis(request)

    def _build_prompt(self, request: TravelRequest) -> str:
        interests = sanitize_for_prompt(", ".join(request.interests)) if request.interests else "general sightseeing"
        notes = sanitize_for_prompt(request.additional_notes or "")
        return (
            f"{SYSTEM_CONTEXT}\n\n"
            f"Travel request:\n"
            f"{request.to_prompt_context()}"
            f"Additional notes: {notes}\n\n"
            f"Return JSON:"
        )

    def _parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            # Find JSON block in response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    def _fallback_analysis(self, request: TravelRequest) -> Dict[str, Any]:
        """Deterministic fallback when Granite is unavailable."""
        from services.destination_service import get_destination
        dest = get_destination(request.destination)
        dest_type = dest["destination_type"] if dest else "tier2"

        budget_per_person_day = request.budget_per_day_inr / max(request.num_travellers, 1)
        if budget_per_person_day < 1500:
            style = "budget"
        elif budget_per_person_day < 5000:
            style = "mid-range"
        else:
            style = "luxury"

        return {
            "destination_type": dest_type,
            "travel_style": style,
            "primary_interest": request.interests[0] if request.interests else "sightseeing",
            "recommended_accommodation": request.accommodation_preference,
            "flexibility_score": 3,
            "key_priorities": request.interests[:3] if request.interests else ["comfort", "safety", "value"],
            "special_considerations": f"{request.num_travellers} traveller(s), {request.duration_days} days.",
        }
