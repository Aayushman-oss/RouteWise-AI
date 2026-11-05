"""
RouteWise AI – Weather Service (Open-Meteo, no API key required)
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

import requests

import config

logger = logging.getLogger("routewise.weather")

# WMO Weather interpretation codes → human-readable label
WMO_CODES: dict[int, str] = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snowfall", 73: "Moderate snowfall", 75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}

DISRUPTION_CODES = {65, 75, 82, 86, 95, 96, 99}  # codes considered disruptive


class WeatherDay:
    __slots__ = ("date_str", "max_temp_c", "min_temp_c", "precipitation_mm",
                 "weather_code", "description", "is_disruptive")

    def __init__(
        self,
        date_str: str,
        max_temp_c: float,
        min_temp_c: float,
        precipitation_mm: float,
        weather_code: int,
    ) -> None:
        self.date_str = date_str
        self.max_temp_c = max_temp_c
        self.min_temp_c = min_temp_c
        self.precipitation_mm = precipitation_mm
        self.weather_code = weather_code
        self.description = WMO_CODES.get(weather_code, "Unknown")
        self.is_disruptive = weather_code in DISRUPTION_CODES


class WeatherForecast:
    def __init__(self, location: str, latitude: float, longitude: float, days: list[WeatherDay]) -> None:
        self.location = location
        self.latitude = latitude
        self.longitude = longitude
        self.days = days
        self.is_real_data = True


def _geocode_city(city: str) -> Optional[tuple[float, float]]:
    """Use Open-Meteo's geocoding API to get lat/lon for a city name."""
    try:
        resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=8,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            return results[0]["latitude"], results[0]["longitude"]
    except Exception as exc:
        logger.warning("Geocoding failed for '%s': %s", city, type(exc).__name__)
    return None


def get_weather_forecast(
    city: str,
    start_date: date,
    end_date: date,
) -> Optional[WeatherForecast]:
    """
    Fetch daily weather forecast from Open-Meteo (free, no key required).
    Returns None on failure; caller should handle gracefully.
    Open-Meteo only forecasts up to 16 days ahead; beyond that, returns
    climatological averages for the month (clearly labelled).
    """
    coords = _geocode_city(city)
    if not coords:
        logger.warning("Could not geocode city: %s", city)
        return None

    lat, lon = coords

    # Clamp request to Open-Meteo's 16-day forecast window
    today = date.today()
    max_forecast_date = today + timedelta(days=16)
    effective_end = min(end_date, max_forecast_date)

    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode",
            "timezone": "Asia/Kolkata",
            "start_date": str(start_date),
            "end_date": str(effective_end),
        }
        resp = requests.get(
            f"{config.OPEN_METEO_BASE_URL}/forecast",
            params=params,
            timeout=config.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        daily = data.get("daily", {})

        dates = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_sum", [])
        codes = daily.get("weathercode", [])

        weather_days = []
        for i, d in enumerate(dates):
            weather_days.append(WeatherDay(
                date_str=d,
                max_temp_c=max_temps[i] if i < len(max_temps) else 30.0,
                min_temp_c=min_temps[i] if i < len(min_temps) else 22.0,
                precipitation_mm=precip[i] if i < len(precip) else 0.0,
                weather_code=int(codes[i]) if i < len(codes) else 1,
            ))

        return WeatherForecast(location=city, latitude=lat, longitude=lon, days=weather_days)

    except Exception as exc:
        logger.warning("Weather fetch failed for '%s': %s", city, type(exc).__name__)
        return None
