"""
RouteWise AI – Dynamic Replanning Agent
The core innovation: intelligently replans affected itinerary days
when weather, transport or safety conditions change.
Always requires explicit user approval before applying changes.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional

from models.itinerary import Itinerary, ItineraryDay, ItineraryActivity, ReplanningResult
from services.watsonx_service import WatsonxService

logger = logging.getLogger("routewise.agent.replanning")

SYSTEM_CONTEXT = """You are a dynamic travel replanning specialist.
A disruption has occurred during a trip in India. Suggest revised activities for the affected day.
Return a JSON object with:
{
  "revised_day_activities": [
    {
      "time": "09:00",
      "activity": "string",
      "location": "string",
      "duration_hours": 2.0,
      "transport": "string or null",
      "estimated_cost_inr": 0,
      "notes": "string",
      "category": "string"
    }
  ],
  "changes_made": ["string"],
  "reason": "string",
  "revised_accommodation": null
}

Rules:
- Replace weather-sensitive outdoor activities with suitable indoor or covered alternatives
- Keep costs within original day's budget
- Maintain the overall spirit of the trip
- Provide clear reasoning for each change

Respond ONLY with valid JSON. No markdown, no extra text."""


class ReplanningAgent:
    def __init__(self, watsonx: WatsonxService) -> None:
        self.watsonx = watsonx

    def replan(
        self,
        itinerary: Itinerary,
        disruption_type: str,
        disruption_description: str,
        affected_day_number: int,
    ) -> ReplanningResult:
        affected_day = next(
            (d for d in itinerary.days if d.day_number == affected_day_number), None
        )
        if not affected_day:
            return ReplanningResult(
                revised_itinerary=itinerary,
                changes_made=[],
                reason="Affected day not found in itinerary.",
                requires_user_approval=True,
            )

        prompt = self._build_prompt(itinerary, affected_day, disruption_type, disruption_description)

        revised_day_data: Optional[Dict] = None
        try:
            result = self.watsonx.generate(prompt, max_tokens=600)
            revised_day_data = self._parse_json(result.text)
            if revised_day_data:
                logger.info("ReplanningAgent: Granite revision complete.")
        except Exception as exc:
            logger.warning("ReplanningAgent: Granite unavailable (%s), fallback.", type(exc).__name__)

        is_fallback = False
        if not revised_day_data:
            revised_day_data = self._fallback_replan(affected_day, disruption_type)
            is_fallback = True

        revised_itinerary = self._apply_revision(
            itinerary, affected_day_number, revised_day_data, affected_day, is_fallback
        )

        return ReplanningResult(
            revised_itinerary=revised_itinerary,
            changes_made=revised_day_data.get("changes_made", ["Activities revised for disruption."]),
            reason=revised_day_data.get("reason", f"Replanned due to: {disruption_description}"),
            requires_user_approval=True,
        )

    def _build_prompt(self, itinerary: Itinerary, day: ItineraryDay, d_type: str, d_desc: str) -> str:
        orig_activities = "\n".join(
            f"  {a.time} – {a.activity} at {a.location} ({a.duration_hours}h, ₹{a.estimated_cost_inr:.0f})"
            for a in day.activities
        )
        return (
            f"{SYSTEM_CONTEXT}\n\n"
            f"Trip: {itinerary.trip_title}\n"
            f"Destination: {itinerary.destination}\n"
            f"Affected: Day {day.day_number} ({day.date_str}) in {day.location}\n"
            f"Disruption type: {d_type}\n"
            f"Disruption: {d_desc}\n"
            f"Original activities:\n{orig_activities}\n"
            f"Day budget: ₹{day.total_day_cost_inr:,.0f}\n\n"
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

    def _fallback_replan(self, day: ItineraryDay, disruption_type: str) -> Dict:
        """Deterministic fallback revision when Granite unavailable."""
        revised = []
        for a in day.activities:
            if a.category in ("sightseeing", "adventure") and disruption_type == "weather":
                revised.append({
                    "time": a.time,
                    "activity": f"Indoor alternative: {a.activity} museum or exhibition",
                    "location": day.location,
                    "duration_hours": a.duration_hours,
                    "transport": a.transport,
                    "estimated_cost_inr": a.estimated_cost_inr,
                    "notes": "Rescheduled indoors due to weather disruption.",
                    "category": "culture",
                })
            else:
                revised.append({
                    "time": a.time,
                    "activity": a.activity,
                    "location": day.location,
                    "duration_hours": a.duration_hours,
                    "transport": a.transport,
                    "estimated_cost_inr": a.estimated_cost_inr,
                    "notes": a.notes,
                    "category": a.category,
                })

        return {
            "revised_day_activities": revised,
            "changes_made": ["Outdoor activities replaced with indoor alternatives."],
            "reason": f"Day {day.day_number} replanned due to {disruption_type} disruption.",
            "revised_accommodation": None,
            # Step 5: simulation disclaimer on fallback path
            "simulation_disclaimer": (
                "This replanning scenario was generated by a deterministic fallback "
                "(IBM Granite was unavailable). Disruption conditions are simulated. "
                "Verify actual weather, transport, and safety conditions before travelling."
            ),
        }

    def _apply_revision(
        self,
        original: Itinerary,
        day_number: int,
        revision_data: Dict,
        original_day: Optional[ItineraryDay] = None,
        is_fallback: bool = False,
    ) -> Itinerary:
        # Deep copy to avoid mutating original
        import copy
        revised = copy.deepcopy(original)

        # Record original day cost for the post-revision cost guard
        original_day_cost = original_day.total_day_cost_inr if original_day else 0.0

        for day in revised.days:
            if day.day_number == day_number:
                new_activities = []
                for a_raw in revision_data.get("revised_day_activities", []):
                    try:
                        new_activities.append(ItineraryActivity(
                            time=str(a_raw.get("time", "09:00")),
                            activity=str(a_raw.get("activity", "Activity"))[:200],
                            location=str(a_raw.get("location", day.location))[:100],
                            duration_hours=float(a_raw.get("duration_hours", 1.5)),
                            transport=a_raw.get("transport"),
                            estimated_cost_inr=float(a_raw.get("estimated_cost_inr", 0)),
                            notes=a_raw.get("notes"),
                            category=a_raw.get("category", "sightseeing"),
                        ))
                    except Exception:
                        continue
                if new_activities:
                    day.activities = new_activities
                if revision_data.get("revised_accommodation"):
                    day.accommodation = revision_data["revised_accommodation"]

                # Strict post-revision guard: preserve the original day when
                # revised costs exceed its original total (no 15% tolerance).
                new_day_cost = day.total_day_cost_inr
                if new_day_cost > original_day_cost + 0.01:
                    overspend = new_day_cost - original_day_cost
                    logger.warning(
                        "ReplanningAgent: Revised Day %d exceeds original daily budget by ₹%.0f.",
                        day_number, overspend,
                    )
                    # Reject the over-budget revision; do not mutate the user's plan.
                    day.activities = deepcopy(original_day.activities)
                    day.accommodation = original_day.accommodation
                    day.accommodation_cost_inr = original_day.accommodation_cost_inr
                    revised.warnings.append(
                        f"Proposed revision for Day {day_number} was rejected because "
                        f"it exceeded the original daily budget by ₹{overspend:,.0f}. "
                        "The original day's activities were retained."
                    )

        revised.warnings.append(f"Day {day_number} has been dynamically revised.")

        # Simulation disclaimer (fallback path only)
        if is_fallback:
            disclaimer = revision_data.get("simulation_disclaimer", "")
            if disclaimer:
                revised.warnings.append(f"{disclaimer}")

        return revised
