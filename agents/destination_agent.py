"""
RouteWise AI – Destination Intelligence Agent
Evaluates destination suitability using IBM Granite and structured data.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from models.travel_request import TravelRequest
from services.watsonx_service import WatsonxService
from services.destination_service import get_destination, DESTINATIONS
from utils.security import sanitize_for_prompt

logger = logging.getLogger("routewise.agent.destination")

SYSTEM_CONTEXT = """You are an expert Indian travel destination consultant.
Given the user's travel request and destination data, provide:
- destination_evaluation: brief assessment of the destination for these travellers
- top_attractions: list of 5 must-visit places with one-line descriptions
- local_experiences: list of 3 authentic local experiences
- practical_tips: list of 3 practical travel tips
- best_areas_to_stay: recommended area/neighbourhood to stay
- cuisine_highlights: list of 3 local dishes to try
- estimated_daily_spend_inr: realistic per-person per-day estimate in INR

Respond ONLY with valid JSON. No markdown, no extra text."""


class DestinationAgent:
    def __init__(self, watsonx: WatsonxService) -> None:
        self.watsonx = watsonx

    def analyze(self, request: TravelRequest, preference_profile: Dict[str, Any]) -> Dict[str, Any]:
        dest_data = get_destination(request.destination)
        prompt = self._build_prompt(request, dest_data, preference_profile)

        try:
            result = self.watsonx.generate(prompt, max_tokens=600)
            parsed = self._parse_json(result.text)
            if parsed:
                # Merge with static data
                if dest_data:
                    parsed["static_highlights"] = dest_data.get("highlights", [])
                    parsed["best_months"] = dest_data.get("best_months", [])
                    parsed["destination_type"] = dest_data.get("type", "general")
                logger.info("DestinationAgent: Granite analysis complete.")
                return parsed
        except Exception as exc:
            logger.warning("DestinationAgent: Granite unavailable (%s), using fallback.", type(exc).__name__)

        return self._fallback(request, dest_data)

    def _build_prompt(self, request: TravelRequest, dest_data: Optional[Dict], profile: Dict) -> str:
        dest_context = ""
        if dest_data:
            dest_context = (
                f"Destination data:\n"
                f"- Type: {dest_data.get('type', 'general')}\n"
                f"- Region: {dest_data.get('region', 'India')}\n"
                f"- Known highlights: {', '.join(dest_data.get('highlights', []))}\n"
                f"- Best travel months: {', '.join(dest_data.get('best_months', []))}\n"
            )

        return (
            f"{SYSTEM_CONTEXT}\n\n"
            f"Travel request:\n{request.to_prompt_context()}\n"
            f"Travel style: {profile.get('travel_style', 'mid-range')}\n"
            f"Primary interest: {profile.get('primary_interest', 'sightseeing')}\n"
            f"{dest_context}\n"
            f"Return JSON:"
        )

    def _parse_json(self, text: str) -> Optional[Dict]:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    def _fallback(self, request: TravelRequest, dest_data: Optional[Dict]) -> Dict[str, Any]:
        highlights = dest_data.get("highlights", ["Historical sites", "Local markets", "Cultural centres"]) if dest_data else []
        return {
            "destination_evaluation": f"{request.destination} is a great destination for {', '.join(request.interests[:2]) if request.interests else 'sightseeing'}.",
            "top_attractions": [{"name": h, "description": "Notable attraction"} for h in highlights[:5]],
            "local_experiences": ["Local cuisine tasting", "Cultural walking tour", "Sunset viewpoint visit"],
            "practical_tips": ["Carry cash for local markets", "Book accommodation in advance", "Hire a local guide"],
            "best_areas_to_stay": "City centre",
            "cuisine_highlights": ["Local thali", "Street food", "Regional sweets"],
            "estimated_daily_spend_inr": dest_data.get("avg_budget_per_day_inr", 2000) if dest_data else 2000,
            "static_highlights": highlights,
            "best_months": dest_data.get("best_months", []) if dest_data else [],
            "destination_type": dest_data.get("type", "general") if dest_data else "general",
        }
