"""
RouteWise AI – Maps Service (OpenStreetMap Nominatim + OSRM)
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import requests
import config

logger = logging.getLogger("routewise.maps")

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
HEADERS = {"User-Agent": "RouteWiseAI/1.0 (IBM internship project)"}


class RouteInfo:
    __slots__ = ("origin", "destination", "distance_km", "duration_hours", "is_estimated")

    def __init__(
        self,
        origin: str,
        destination: str,
        distance_km: float,
        duration_hours: float,
        is_estimated: bool = False,
    ) -> None:
        self.origin = origin
        self.destination = destination
        self.distance_km = distance_km
        self.duration_hours = duration_hours
        self.is_estimated = is_estimated


def geocode(place: str) -> Optional[Tuple[float, float]]:
    """Return (lat, lon) for a place name using Nominatim."""
    try:
        resp = requests.get(
            f"{NOMINATIM_BASE}/search",
            params={"q": place + ", India", "format": "json", "limit": 1},
            headers=HEADERS,
            timeout=8,
        )
        resp.raise_for_status()
        results = resp.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as exc:
        logger.warning("Geocoding failed for '%s': %s", place, type(exc).__name__)
    return None


def get_route_info(origin: str, destination: str) -> RouteInfo:
    """
    Get driving route distance and duration using OSRM.
    Falls back to straight-line Haversine estimate on failure.
    """
    origin_coords = geocode(origin)
    dest_coords = geocode(destination)

    if origin_coords and dest_coords:
        try:
            url = (
                f"{config.OSRM_BASE_URL}/route/v1/driving/"
                f"{origin_coords[1]},{origin_coords[0]};"
                f"{dest_coords[1]},{dest_coords[0]}"
            )
            resp = requests.get(
                url,
                params={"overview": "false"},
                timeout=config.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                distance_km = route["distance"] / 1000.0
                duration_hours = route["duration"] / 3600.0
                return RouteInfo(
                    origin=origin,
                    destination=destination,
                    distance_km=round(distance_km, 1),
                    duration_hours=round(duration_hours, 2),
                )
        except Exception as exc:
            logger.warning("OSRM route failed: %s", type(exc).__name__)

    # Fallback: Haversine estimate
    if origin_coords and dest_coords:
        dist = _haversine_km(origin_coords, dest_coords)
        return RouteInfo(
            origin=origin,
            destination=destination,
            distance_km=round(dist, 1),
            duration_hours=round(dist / 60, 2),  # ~60 km/h average
            is_estimated=True,
        )

    # Ultimate fallback: generic estimate
    return RouteInfo(
        origin=origin,
        destination=destination,
        distance_km=500.0,
        duration_hours=8.0,
        is_estimated=True,
    )


def _haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Compute great-circle distance in km between two (lat, lon) pairs."""
    import math
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    ah = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(ah))
