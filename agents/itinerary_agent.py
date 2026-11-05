"""
RouteWise AI – Itinerary Generation Agent
Uses IBM Granite to generate a structured day-by-day itinerary,
then validates and enriches with Python calculations.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from models.travel_request import TravelRequest
from models.itinerary import Itinerary, ItineraryDay, ItineraryActivity, BudgetBreakdown
from services.watsonx_service import WatsonxService
from utils.calculations import format_inr

logger = logging.getLogger("routewise.agent.itinerary")

SYSTEM_CONTEXT = """You are an expert Indian travel itinerary planner.
Create a detailed day-by-day itinerary. Return a JSON object with this exact structure:
{
  "trip_title": "string",
  "highlights": ["string"],
  "days": [
    {
      "day_number": 1,
      "location": "string",
      "accommodation": "string",
      "accommodation_cost_inr": 0,
      "day_notes": "string",
      "activities": [
        {
          "time": "09:00",
          "activity": "string",
          "location": "string",
          "duration_hours": 2.0,
          "transport": "string or null",
          "estimated_cost_inr": 0,
          "notes": "string or null",
          "category": "sightseeing"
        }
      ]
    }
  ],
  "generation_notes": "string"
}

Rules:
- Include 3-5 activities per day
- Costs must be realistic in INR
- The total of all estimated_cost_inr values across ALL days MUST NOT exceed the stated activities budget. If activities would exceed this limit, reduce individual costs proportionally.
- Accommodation cost per night must not exceed the stated accommodation budget divided by the number of nights.
- You MUST generate exactly the number of days specified in the travel details. No more, no fewer.
- day_number values must be sequential integers starting from 1.
- Focus on Indian destinations with culturally accurate recommendations
- category must be one of: sightseeing, food, adventure, culture, transit, wellness

Respond ONLY with valid JSON. No markdown, no extra text."""


# Tokens needed grow with trip length. Budget ~400 tokens/day for activities
# plus ~200 for header/footer. 6-day trip ≈ 2600 tokens; cap at 4096 (model max).
_TOKENS_PER_DAY = 400
_TOKENS_OVERHEAD = 400
_MAX_ITINERARY_TOKENS = 4096


class ItineraryAgent:
    def __init__(self, watsonx: WatsonxService) -> None:
        self.watsonx = watsonx

    def generate(
        self,
        request: TravelRequest,
        preference_profile: Dict[str, Any],
        destination_data: Dict[str, Any],
        budget_data: Dict[str, Any],
        weather_data: Dict[str, Any],
    ) -> Itinerary:
        prompt = self._build_prompt(request, preference_profile, destination_data, budget_data, weather_data)

        raw_itinerary: Optional[Dict] = None
        is_simulated = False
        granite_failure_reason: Optional[str] = None

        # Scale token budget to trip duration so long trips don't get truncated.
        calendar_days = (request.end_date - request.start_date).days + 1
        token_budget = min(
            _TOKENS_OVERHEAD + calendar_days * _TOKENS_PER_DAY,
            _MAX_ITINERARY_TOKENS,
        )

        try:
            result = self.watsonx.generate(prompt, max_tokens=token_budget)
            raw_itinerary = self._parse_json(result.text)
            if raw_itinerary:
                logger.info(
                    "ItineraryAgent: Granite itinerary generated (%d output tokens).",
                    result.output_tokens,
                )
            else:
                # Attempt to repair truncated JSON before giving up
                raw_itinerary = self._repair_truncated_json(result.text)
                if raw_itinerary:
                    logger.info("ItineraryAgent: Truncated Granite JSON repaired successfully.")
                else:
                    granite_failure_reason = (
                        f"IBM Granite returned a response ({result.output_tokens} tokens) "
                        "that could not be parsed as valid JSON. "
                        "The response may have been truncated or malformed."
                    )
                    logger.warning(
                        "ItineraryAgent: Could not parse Granite JSON (%d tokens), using template. "
                        "Response content omitted from logs for privacy.",
                        result.output_tokens,
                    )
        except Exception as exc:
            granite_failure_reason = f"IBM Granite inference failed ({type(exc).__name__}). Check the safe diagnostic details in Settings."
            logger.warning(
                "ItineraryAgent: Granite failed (%s), using template.", type(exc).__name__
            )

        if not raw_itinerary:
            raw_itinerary = self._template_itinerary(request, destination_data)
            is_simulated = True

        return self._build_itinerary_model(
            request, raw_itinerary, budget_data, is_simulated, granite_failure_reason
        )

    def _build_prompt(self, request: TravelRequest, profile: Dict, dest: Dict, budget: Dict, weather: Dict) -> str:
        disruption_days = weather.get("disruption_days", [])
        weather_note = f"Note: Days {disruption_days} may have disruptive weather – plan indoor alternatives." if disruption_days else ""
        budget_bd = budget.get("breakdown", {})
        activities_budget = budget_bd.get("activities_inr", 0)
        accommodation_budget = budget_bd.get("accommodation_inr", 0)
        nights = max(1, request.duration_days - 1)
        accommodation_per_night = accommodation_budget / nights if nights > 0 else accommodation_budget

        return (
            f"{SYSTEM_CONTEXT}\n\n"
            f"Travel details:\n{request.to_prompt_context()}\n"
            f"Travel style: {profile.get('travel_style', 'mid-range')}\n"
            f"Key priorities: {', '.join(profile.get('key_priorities', []))}\n"
            f"Top attractions: {', '.join([a['name'] if isinstance(a, dict) else str(a) for a in dest.get('top_attractions', [])[:5]])}\n"
            f"Calendar dates to represent (inclusive): {(request.end_date - request.start_date).days + 1}\n"
            f"Overnight stays: {max(0, (request.end_date - request.start_date).days)}\n"
            f"Include arrival and departure dates; the final date is a departure day.\n"
            f"Budget for accommodation: {format_inr(accommodation_budget)} total ({format_inr(accommodation_per_night)}/night)\n"
            f"Budget for activities (ALL days combined): {format_inr(activities_budget)} — do not exceed this total\n"
            f"Budget for food: {format_inr(budget_bd.get('food_inr', 0))}\n"
            f"{weather_note}\n\n"
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

    def _repair_truncated_json(self, text: str) -> Optional[Dict]:
        """
        Attempt to recover a usable itinerary dict from a truncated Granite response.

        Strategy:
        1. Find the opening brace.
        2. Extract as many complete day objects as possible by finding complete
           JSON objects for each "day_number" block.
        3. Construct a minimal valid dict with whatever days could be parsed.
        """
        try:
            start = text.find("{")
            if start < 0:
                return None

            # Try progressively trimming the tail to find the largest parseable prefix
            candidate = text[start:]

            # Quick check: if we can add a few closing brackets and parse, do so
            for suffix in ["]}}", "]}", "}"]:
                try:
                    return json.loads(candidate + suffix)
                except Exception:
                    pass

            # Extract individual day objects via regex-free block scan
            day_objects: list = []
            search_text = candidate
            while True:
                day_start = search_text.find('"day_number"')
                if day_start < 0:
                    break
                # Walk backwards to find the opening { of this day object
                obj_start = search_text.rfind("{", 0, day_start)
                if obj_start < 0:
                    break
                # Walk forward to find a matching closing }
                depth = 0
                i = obj_start
                obj_end = -1
                while i < len(search_text):
                    if search_text[i] == "{":
                        depth += 1
                    elif search_text[i] == "}":
                        depth -= 1
                        if depth == 0:
                            obj_end = i + 1
                            break
                    i += 1
                if obj_end < 0:
                    break
                try:
                    day_obj = json.loads(search_text[obj_start:obj_end])
                    day_objects.append(day_obj)
                except Exception:
                    pass
                search_text = search_text[obj_end:]

            if day_objects:
                logger.info(
                    "ItineraryAgent._repair_truncated_json: recovered %d day(s) from truncated response.",
                    len(day_objects),
                )
                return {
                    "trip_title": "",
                    "highlights": [],
                    "days": day_objects,
                    "generation_notes": "Partially recovered from truncated Granite response.",
                }
        except Exception as exc:
            logger.debug("ItineraryAgent._repair_truncated_json: failed (%s)", type(exc).__name__)
        return None

    def _build_itinerary_model(
        self,
        request: TravelRequest,
        raw: Dict,
        budget_data: Dict,
        is_simulated: bool,
        granite_failure_reason: Optional[str] = None,
    ) -> Itinerary:
        days_raw = raw.get("days", [])
        days: List[ItineraryDay] = []
        # Include both arrival and departure dates. Overnight stays are the
        # date difference; calendar itinerary entries are difference + 1.
        expected_days = max(1, (request.end_date - request.start_date).days + 1)

        for d_raw in days_raw:
            activities: List[ItineraryActivity] = []
            for a_raw in d_raw.get("activities", []):
                try:
                    activities.append(ItineraryActivity(
                        time=str(a_raw.get("time", "09:00")),
                        activity=str(a_raw.get("activity", "Activity"))[:200],
                        location=str(a_raw.get("location", request.destination))[:100],
                        duration_hours=float(a_raw.get("duration_hours", 1.5)),
                        transport=a_raw.get("transport"),
                        estimated_cost_inr=float(a_raw.get("estimated_cost_inr", 0)),
                        notes=a_raw.get("notes"),
                        category=a_raw.get("category", "sightseeing"),
                    ))
                except Exception:
                    continue

            # Clamp day_number to valid range [1, expected_days]
            raw_day_num = int(d_raw.get("day_number", len(days) + 1))
            day_num = max(1, min(raw_day_num, expected_days))
            if any(existing.day_number == day_num for existing in days):
                logger.warning("ItineraryAgent: Duplicate day_number=%s ignored.", day_num)
                continue
            day_date = request.start_date + timedelta(days=day_num - 1)

            try:
                days.append(ItineraryDay(
                    day_number=day_num,
                    date_str=str(day_date),
                    location=str(d_raw.get("location", request.destination))[:100],
                    activities=activities,
                    accommodation=d_raw.get("accommodation"),
                    accommodation_cost_inr=float(d_raw.get("accommodation_cost_inr", 0)),
                    day_notes=d_raw.get("day_notes"),
                ))
            except Exception:
                continue

        # ── Day count validation ────────────────────────────────────────────
        # If parsing produced no valid days, generate template days
        warnings_for_mixed = False
        if not days:
            days = self._generate_template_days(request, budget_data)
            is_simulated = True
        else:
            # Trim extra days if Granite generated too many
            if len(days) > expected_days:
                logger.warning(
                    "ItineraryAgent: Granite returned %d days for a %d-day trip — trimming.",
                    len(days), expected_days,
                )
                days = days[:expected_days]
            # Pad missing days if Granite generated too few
            elif len(days) < expected_days:
                logger.warning(
                    "ItineraryAgent: Granite returned %d days for a %d-day trip — padding with template days.",
                    len(days), expected_days,
                )
                existing_day_nums = {d.day_number for d in days}
                template_raw = self._template_itinerary(request, {})
                for t_raw in template_raw.get("days", []):
                    t_day_num = t_raw.get("day_number", 1)
                    if t_day_num not in existing_day_nums and len(days) < expected_days:
                        t_activities = [
                            ItineraryActivity(**a) for a in t_raw.get("activities", [])
                        ]
                        t_date = request.start_date + timedelta(days=t_day_num - 1)
                        days.append(ItineraryDay(
                            day_number=t_day_num,
                            date_str=str(t_date),
                            location=t_raw.get("location", request.destination),
                            activities=t_activities,
                            accommodation=t_raw.get("accommodation"),
                            accommodation_cost_inr=float(t_raw.get("accommodation_cost_inr", 0)),
                            day_notes="⚠️ Template day (Granite did not generate this day).",
                        ))
                days.sort(key=lambda d: d.day_number)
                if any((d.day_notes or "").startswith("⚠️ Template day") for d in days):
                    warnings_for_mixed = True
                else:
                    warnings_for_mixed = False
            else:
                warnings_for_mixed = False

        bd = budget_data.get("breakdown", {})
        breakdown = BudgetBreakdown(
            transportation_inr=float(bd.get("transportation_inr", 0)),
            accommodation_inr=float(bd.get("accommodation_inr", 0)),
            food_inr=float(bd.get("food_inr", 0)),
            activities_inr=float(bd.get("activities_inr", 0)),
            miscellaneous_inr=float(bd.get("miscellaneous_inr", 0)),
        )

        # ── Activity cost validation ────────────────────────────────────────
        # Sum per-activity costs from Granite output and compare to budget.
        activities_budget = float(bd.get("activities_inr", 0))
        total_activity_cost = sum(
            a.estimated_cost_inr
            for day in days
            for a in day.activities
        )

        warnings: List[str] = []
        if warnings_for_mixed:
            warnings.append(
                "⚠️ Mixed itinerary: some days were supplied by the deterministic template "
                "because Granite did not generate all requested days."
            )
        if is_simulated:
            if granite_failure_reason:
                warnings.append(
                    f"⚠️ Template itinerary shown — IBM Granite did not generate a plan. "
                    f"Reason: {granite_failure_reason}"
                )
            else:
                warnings.append(
                    "⚠️ Template itinerary shown — IBM Granite was not available. "
                    "Configure your credentials in Settings for an AI-generated plan."
                )
        if not budget_data.get("is_within_budget", True):
            warnings.append("⚠️ Estimated cost may exceed your budget. Review and adjust.")
        if activities_budget > 0 and total_activity_cost > activities_budget + 0.01:
            logger.warning(
                "ItineraryAgent: Activity costs %.0f exceed activities budget %.0f by %.0f%%.",
                total_activity_cost, activities_budget,
                (total_activity_cost / activities_budget - 1) * 100,
            )
            from utils.calculations import format_inr as _fmt
            warnings.append(
                f"⚠️ Total activity costs ({_fmt(total_activity_cost)}) exceed the "
                f"activities budget ({_fmt(activities_budget)}). "
                "The itinerary is over its allocated activities budget and must be revised."
            )
        # Budget overrun warning from BudgetAgent
        if budget_data.get("budget_overrun_warning"):
            warnings.append(f"⚠️ {budget_data['budget_overrun_warning']}")

        return Itinerary(
            trip_title=raw.get("trip_title", f"{request.destination} Explorer"),
            origin=request.origin,
            destination=request.destination,
            start_date=str(request.start_date),
            end_date=str(request.end_date),
            num_travellers=request.num_travellers,
            days=days,
            budget_breakdown=breakdown,
            total_budget_inr=request.budget_inr,
            highlights=raw.get("highlights", [])[:6],
            warnings=warnings,
            is_simulated=is_simulated,
            generation_notes=raw.get("generation_notes"),
        )

    def _template_itinerary(self, request: TravelRequest, dest: Dict) -> Dict:
        """
        Deterministic template used when Granite is unavailable.

        Duration semantics:
        - request.duration_days = (end_date - start_date).days  (e.g. 6 for 12→18 Nov).
        - The itinerary covers ALL calendar dates from start_date to end_date INCLUSIVE,
          which is duration_days + 1 entries.
        - Days 1 .. duration_days are full activity days with overnight stays.
        - The final entry (day duration_days + 1, the end_date) is a departure day —
          checkout, brief morning, transit home. It has no accommodation cost.

        Attraction rotation: use modulo cycling without cross-boundary wrapping to
        prevent duplicate attractions appearing on consecutive days.
        """
        from services.destination_service import get_destination
        dest_data = get_destination(request.destination)
        default_attractions = [
            "Local Sightseeing", "City Market", "Cultural Centre",
            "Heritage Site", "Viewpoint",
        ]
        attractions = (
            dest_data.get("highlights", default_attractions)
            if dest_data
            else default_attractions
        )
        if not attractions:
            attractions = default_attractions
        n = len(attractions)

        # Calculate per-activity cost scaled to the actual activities budget so
        # template totals never exceed what the budget agent allocated.
        bd = dest.get("_budget_breakdown", {}) if isinstance(dest, dict) else {}
        activities_budget = float(bd.get("activities_inr", 0)) if bd else 0.0

        # calendar_days = duration_days + 1 to include end_date as departure day
        calendar_days = request.duration_days + 1

        # Base costs for 4 activities per day (sightseeing x2, food x2)
        # Scale only against full activity days (duration_days), not the departure day.
        BASE_ACTIVITY_COSTS = [300, 400, 200, 600]  # total per day = 1500
        BASE_DAILY_TOTAL = sum(BASE_ACTIVITY_COSTS)
        total_base_activity_cost = BASE_DAILY_TOTAL * request.duration_days

        # Scale factor: if activities_budget is set and base would exceed it, scale down
        scale = 1.0
        if activities_budget > 0 and total_base_activity_cost > activities_budget:
            scale = activities_budget / total_base_activity_cost

        scaled_costs = [round(c * scale) for c in BASE_ACTIVITY_COSTS]

        days = []
        for d in range(calendar_days):
            day_date = request.start_date + timedelta(days=d)
            day_num = d + 1
            is_last_day = (day_num == calendar_days)

            # Cycle through attractions without cross-boundary wrapping
            # Use two distinct attractions per day, offset so adjacent days differ
            primary_idx = (d * 2) % n
            secondary_idx = (d * 2 + 1) % n
            primary = attractions[primary_idx]
            secondary = attractions[secondary_idx]

            if is_last_day:
                # Final day: departure morning, minimal activities
                activities = [
                    {
                        "time": "08:00",
                        "activity": "Breakfast and hotel checkout",
                        "location": request.destination,
                        "duration_hours": 1.0,
                        "estimated_cost_inr": scaled_costs[1],
                        "category": "food",
                    },
                    {
                        "time": "09:30",
                        "activity": f"Last look at {primary}",
                        "location": request.destination,
                        "duration_hours": 1.5,
                        "estimated_cost_inr": scaled_costs[0],
                        "category": "sightseeing",
                    },
                    {
                        "time": "12:00",
                        "activity": f"Depart {request.destination} → {request.origin}",
                        "location": request.destination,
                        "duration_hours": 1.0,
                        "estimated_cost_inr": 0,
                        "category": "transit",
                    },
                ]
                acc_cost = 0.0  # No overnight stay on departure day
                day_notes = f"Departure day — return to {request.origin}."
            else:
                activities = [
                    {
                        "time": "09:00",
                        "activity": f"Visit {primary}",
                        "location": request.destination,
                        "duration_hours": 2.5,
                        "estimated_cost_inr": scaled_costs[0],
                        "category": "sightseeing",
                    },
                    {
                        "time": "12:30",
                        "activity": "Lunch at local restaurant",
                        "location": request.destination,
                        "duration_hours": 1.0,
                        "estimated_cost_inr": scaled_costs[1],
                        "category": "food",
                    },
                    {
                        "time": "14:30",
                        "activity": f"Explore {secondary}",
                        "location": request.destination,
                        "duration_hours": 3.0,
                        "estimated_cost_inr": scaled_costs[2],
                        "category": "sightseeing",
                    },
                    {
                        "time": "19:00",
                        "activity": "Dinner at recommended restaurant",
                        "location": request.destination,
                        "duration_hours": 1.5,
                        "estimated_cost_inr": scaled_costs[3],
                        "category": "food",
                    },
                ]
                acc_cost = 1800.0 if request.accommodation_preference == "mid-range" else 800.0
                day_notes = "Template itinerary — connect IBM Granite for a personalized plan."

            days.append({
                "day_number": day_num,
                "date_str": str(day_date),
                "location": request.destination,
                "accommodation": (
                    f"{request.accommodation_preference.title()} hotel"
                    if not is_last_day else None
                ),
                "accommodation_cost_inr": acc_cost,
                "day_notes": day_notes,
                "activities": activities,
            })

        return {
            "trip_title": f"{request.destination} — {request.duration_days}-Day Explorer",
            "highlights": attractions[:5],
            "days": days,
            "generation_notes": (
                "Template itinerary. IBM Granite connection required for a personalized plan."
            ),
        }

    def _generate_template_days(self, request: TravelRequest, budget_data: Dict) -> List[ItineraryDay]:
        # Pass budget breakdown into template so activity costs are scaled correctly
        dest_with_budget = {"_budget_breakdown": budget_data.get("breakdown", {})}
        raw = self._template_itinerary(request, dest_with_budget)
        days = []
        for d_raw in raw.get("days", []):
            activities = [ItineraryActivity(**a) for a in d_raw.get("activities", [])]
            day_num = d_raw.get("day_number", 1)
            day_date = request.start_date + timedelta(days=day_num - 1)
            days.append(ItineraryDay(
                day_number=day_num,
                date_str=str(day_date),
                location=d_raw.get("location", request.destination),
                activities=activities,
                accommodation=d_raw.get("accommodation"),
                accommodation_cost_inr=float(d_raw.get("accommodation_cost_inr", 0)),
                day_notes=d_raw.get("day_notes"),
            ))
        return days
