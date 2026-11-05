"""
RouteWise AI – Map View Component
Uses Folium for interactive maps embedded in Streamlit.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Optional, Tuple

import streamlit as st

logger = logging.getLogger("routewise.map_view")


def render_destination_map(
    latitude: float,
    longitude: float,
    destination: str,
    attractions: Optional[List[str]] = None,
    zoom: int = 11,
):
    """
    Render an interactive Folium map centred on the destination.
    Plots the destination pin and up to 5 attraction markers.
    Gracefully handles missing folium/streamlit-folium.
    """
    try:
        import folium
        from streamlit_folium import st_folium

        m = folium.Map(
            location=[latitude, longitude],
            zoom_start=zoom,
            tiles="OpenStreetMap",
        )

        # Main destination marker
        folium.Marker(
            location=[latitude, longitude],
            popup=folium.Popup(f"<b>{destination}</b>", max_width=200),
            tooltip=destination,
            icon=folium.Icon(color="darkblue", icon="map-marker", prefix="fa"),
        ).add_to(m)

        # Attraction markers – spread around centre (no live geocoding needed)
        if attractions:
            # Small deterministic offsets so pins don't all stack on the same spot
            offsets = [
                (0.012, 0.015), (-0.010, 0.018), (0.018, -0.012),
                (-0.015, -0.010), (0.008, -0.020),
            ]
            for i, attraction in enumerate(attractions[:5]):
                dlat, dlon = offsets[i % len(offsets)]
                folium.Marker(
                    location=[latitude + dlat, longitude + dlon],
                    popup=folium.Popup(attraction, max_width=180),
                    tooltip=attraction,
                    icon=folium.Icon(color="red", icon="star", prefix="fa"),
                ).add_to(m)

        st_folium(m, width="100%", height=400, returned_objects=[])

    except ImportError:
        st.info(
            f"Map for **{destination}** — install `folium` and `streamlit-folium` for interactive maps.\n\n"
            f"Coordinates: {latitude:.4f}°N, {longitude:.4f}°E"
        )
    except Exception as exc:
        logger.warning("Map rendering failed: %s", exc)
        st.caption(f"Map unavailable. Coordinates: {latitude:.4f}°N, {longitude:.4f}°E")


def render_route_map(
    origin_coords: Optional[Tuple[float, float]],
    dest_coords: Optional[Tuple[float, float]],
    origin_name: str,
    dest_name: str,
):
    """Render a route map between two points."""
    if not origin_coords or not dest_coords:
        st.info("Route map unavailable – location coordinates not found.")
        return

    try:
        import folium
        from streamlit_folium import st_folium

        mid_lat = (origin_coords[0] + dest_coords[0]) / 2
        mid_lon = (origin_coords[1] + dest_coords[1]) / 2

        m = folium.Map(location=[mid_lat, mid_lon], zoom_start=6, tiles="OpenStreetMap")

        folium.Marker(
            origin_coords,
            popup=origin_name,
            tooltip=f"Origin: {origin_name}",
            icon=folium.Icon(color="green", icon="home", prefix="fa"),
        ).add_to(m)

        folium.Marker(
            dest_coords,
            popup=dest_name,
            tooltip=f"Destination: {dest_name}",
            icon=folium.Icon(color="red", icon="flag", prefix="fa"),
        ).add_to(m)

        folium.PolyLine(
            [origin_coords, dest_coords],
            color="#1a1a2e",
            weight=2.5,
            opacity=0.7,
            dash_array="6 4",
        ).add_to(m)

        st_folium(m, width="100%", height=380, returned_objects=[])

    except ImportError:
        st.info(f"Route: **{origin_name}** → **{dest_name}**\n\nInstall `folium` and `streamlit-folium` for an interactive map.")
    except Exception as exc:
        logger.warning("Route map failed: %s", exc)
        st.caption("Route map unavailable.")
