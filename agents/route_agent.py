"""
RouteWise AI – Route Intelligence Agent
Evaluates transportation options using OSRM + Granite reasoning.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from models.travel_request import TravelRequest
from services.watsonx_service import WatsonxService
from services.maps_service import get_route_info
from utils.calculations import estimate_transport_cost

logger = logging.getLogger("routewise.agent.route")

TRANSPORT_OPTIONS = {
    "train": {"speed_kmh": 70, "comfort": "high", "note": "Rajdhani/Shatabdi recommended for long routes"},
    "bus": {"speed_kmh": 45, "comfort": "medium", "note": "State buses available; AC options for comfort"},
    "flight": {"speed_kmh": 600, "comfort": "high", "note": "Best for distances > 600 km"},
    "car": {"speed_kmh": 55, "comfort": "high", "note": "Best for destinations not on rail/air routes"},
    "mixed": {"speed_kmh": 60, "comfort": "medium", "note": "Combination based on route availability"},
}

SYSTEM_CONTEXT = """You are a route planning expert for Indian travel.
Given origin, destination, distance, and traveller preferences, recommend the best transport option.
Return a JSON object with:
- recommended_transport: the single best transport type
- reasoning: 2-sentence explanation
- alternatives: list of up to 2 alternative transport options with pros/cons
- journey_tips: list of 2 practical booking/journey tips
- estimated_journey_hours: realistic door-to-door time estimate

Respond ONLY with valid JSON. No markdown, no extra text."""


class RouteAgent:
    def __init__(self, watsonx: WatsonxService) -> None:
        self.watsonx = watsonx

    def analyze(self, request: TravelRequest) -> Dict[str, Any]:
        route = get_route_info(request.origin, request.destination)

        # Deterministic transport cost calculation
        transport_costs = {
            t: estimate_transport_cost(route.distance_km, t, request.num_travellers)
            for t in TRANSPORT_OPTIONS
        }

        prompt = self._build_prompt(request, route, transport_costs)

        try:
            result = self.watsonx.generate(prompt, max_tokens=400)
            parsed = self._parse_json(result.text)
            if parsed:
                parsed["route_info"] = {
                    "distance_km": route.distance_km,
                    "duration_hours": route.duration_hours,
                    "is_estimated": route.is_estimated,
                }
                parsed["transport_costs_inr"] = transport_costs
                logger.info("RouteAgent: Granite analysis complete.")
                return parsed
        except Exception as exc:
            logger.warning("RouteAgent: Granite unavailable (%s), using fallback.", type(exc).__name__)

        return self._fallback(request, route, transport_costs)

    def _build_prompt(self, request: TravelRequest, route: Any, costs: Dict) -> str:
        pref = request.transport_preference
        dist = route.distance_km
        costs_str = "\n".join(f"  {t}: ₹{c:,.0f}" for t, c in costs.items())
        return (
            f"{SYSTEM_CONTEXT}\n\n"
            f"Origin: {request.origin}\n"
            f"Destination: {request.destination}\n"
            f"Distance: {dist:.0f} km\n"
            f"Travellers: {request.num_travellers}\n"
            f"Budget: ₹{request.budget_inr:,.0f}\n"
            f"Preferred transport: {pref}\n"
            f"Estimated costs per option:\n{costs_str}\n\n"
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

    def _fallback(self, request: TravelRequest, route: Any, costs: Dict) -> Dict[str, Any]:
        dist = route.distance_km
        if dist > 600:
            rec = "flight"
        elif dist > 150:
            rec = "train"
        else:
            rec = "car"

        return {
            "recommended_transport": rec,
            "reasoning": f"For a {dist:.0f} km journey, {rec} offers the best balance of speed and cost.",
            "alternatives": [{"type": "train", "pros": "Comfortable, scenic", "cons": "Slower"}] if rec != "train" else [],
            "journey_tips": ["Book tickets at least 2 weeks in advance.", "Check for seasonal demand surges."],
            "estimated_journey_hours": route.duration_hours,
            "route_info": {"distance_km": dist, "duration_hours": route.duration_hours, "is_estimated": route.is_estimated},
            "transport_costs_inr": costs,
        }
