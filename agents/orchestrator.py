"""
RouteWise AI – Agent Orchestrator
===================================
Central coordinator that receives a validated TravelRequest,
runs each specialist agent in order, and returns a structured PlanningResult.
All agents share the same WatsonxService singleton.
Python performs all deterministic calculations.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from models.travel_request import TravelRequest
from models.itinerary import Itinerary, ReplanningResult
from services.watsonx_service import get_watsonx_service
from agents.preference_agent import PreferenceAgent
from agents.destination_agent import DestinationAgent
from agents.route_agent import RouteAgent
from agents.budget_agent import BudgetAgent
from agents.weather_agent import WeatherAgent
from agents.itinerary_agent import ItineraryAgent
from agents.replanning_agent import ReplanningAgent

logger = logging.getLogger("routewise.orchestrator")


@dataclass
class PlanningResult:
    itinerary: Optional[Itinerary] = None
    preference_profile: Dict[str, Any] = field(default_factory=dict)
    destination_data: Dict[str, Any] = field(default_factory=dict)
    route_data: Dict[str, Any] = field(default_factory=dict)
    budget_data: Dict[str, Any] = field(default_factory=dict)
    weather_data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    granite_used: bool = False


class TravelOrchestrator:
    """
    Coordinates the full multi-agent travel planning pipeline.
    """

    def __init__(self) -> None:
        self._svc = get_watsonx_service()
        self._preference = PreferenceAgent(self._svc)
        self._destination = DestinationAgent(self._svc)
        self._route = RouteAgent(self._svc)
        self._budget = BudgetAgent(self._svc)
        self._weather = WeatherAgent(self._svc)
        self._itinerary = ItineraryAgent(self._svc)
        self._replanning = ReplanningAgent(self._svc)

    def plan(self, request: TravelRequest) -> PlanningResult:
        """
        Execute the full planning pipeline:
        1. Preference analysis (Granite)
        2. Destination intelligence (Granite)
        3. Route evaluation (OSRM + Granite)
        4. Budget calculation (Python) + narrative (Granite)
        5. Weather assessment (Open-Meteo + Granite)
        6. Itinerary generation (Granite + Python validation)
        """
        start = time.time()
        result = PlanningResult()

        logger.info("Orchestrator: Starting planning for %s → %s", request.origin, request.destination)

        # ── Step 1: Preferences ────────────────────────────────────────────
        try:
            result.preference_profile = self._preference.analyze(request)
            logger.info("Step 1/6: Preferences ✓")
        except Exception as exc:
            msg = "Preference analysis failed."
            logger.error(msg + " %s", exc)
            result.errors.append(msg)
            result.preference_profile = {}

        # ── Step 2: Destination Intelligence ──────────────────────────────
        try:
            result.destination_data = self._destination.analyze(request, result.preference_profile)
            logger.info("Step 2/6: Destination ✓")
        except Exception as exc:
            logger.error("Destination analysis failed. %s", exc)
            result.destination_data = {}

        # ── Step 3: Route Intelligence ─────────────────────────────────────
        try:
            result.route_data = self._route.analyze(request)
            logger.info("Step 3/6: Route ✓")
        except Exception as exc:
            logger.error("Route analysis failed. %s", exc)
            result.route_data = {}

        # ── Step 4: Budget Optimization ───────────────────────────────────
        try:
            result.budget_data = self._budget.analyze(request, result.route_data, result.preference_profile)
            logger.info("Step 4/6: Budget ✓")
        except Exception as exc:
            logger.error("Budget analysis failed. %s", exc)
            result.budget_data = {}

        # ── Step 5: Weather & Safety ──────────────────────────────────────
        try:
            result.weather_data = self._weather.analyze(request)
            logger.info("Step 5/6: Weather ✓")
        except Exception as exc:
            logger.error("Weather analysis failed. %s", exc)
            result.weather_data = {}

        # ── Step 6: Itinerary Generation ──────────────────────────────────
        try:
            result.itinerary = self._itinerary.generate(
                request=request,
                preference_profile=result.preference_profile,
                destination_data=result.destination_data,
                budget_data=result.budget_data,
                weather_data=result.weather_data,
            )
            logger.info("Step 6/6: Itinerary ✓")
        except Exception as exc:
            logger.error("Itinerary generation failed. %s", exc)
            result.errors.append("Itinerary generation failed – partial results may be shown.")

        # ── Granite usage flag ────────────────────────────────────────────
        result.granite_used = not (result.itinerary and result.itinerary.is_simulated)

        result.elapsed_seconds = round(time.time() - start, 2)
        logger.info(
            "Orchestrator: Planning complete in %.1fs (Granite used: %s)",
            result.elapsed_seconds,
            result.granite_used,
        )
        return result

    def replan(
        self,
        itinerary: Itinerary,
        disruption_type: str,
        disruption_description: str,
        affected_day: int,
    ) -> ReplanningResult:
        """Run the Dynamic Replanning Agent."""
        logger.info(
            "Orchestrator: Replanning day %d (%s: %s)",
            affected_day, disruption_type, disruption_description[:50],
        )
        return self._replanning.replan(
            itinerary=itinerary,
            disruption_type=disruption_type,
            disruption_description=disruption_description,
            affected_day_number=affected_day,
        )


# Module-level singleton
_orchestrator_instance: Optional[TravelOrchestrator] = None


def get_orchestrator() -> TravelOrchestrator:
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = TravelOrchestrator()
    return _orchestrator_instance
