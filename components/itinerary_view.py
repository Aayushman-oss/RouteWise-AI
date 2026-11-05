"""RouteWise AI – Itinerary View Component"""

from __future__ import annotations

import streamlit as st
from models.itinerary import Itinerary
from utils.calculations import format_inr

# Restrained typographic symbols, not emoji artwork.
CATEGORY_SYMBOLS = {
    "sightseeing": "◇",
    "food": "○",
    "adventure": "△",
    "culture": "§",
    "transit": "⇄",
    "wellness": "+",
    "general": "•",
}


def render_itinerary(itinerary: Itinerary):
    """Render the itinerary. Validation metadata remains available to the app but
    is intentionally not shown as warning banners in this presentation."""
    _render_trip_header(itinerary)

    if itinerary.highlights:
        st.markdown("**Trip highlights**  ·  " + "  ·  ".join(itinerary.highlights))

    st.markdown("---")
    for day in itinerary.days:
        _render_day(day)
    _render_itinerary_footer(itinerary)


def _render_trip_header(itinerary: Itinerary):
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.markdown(f"## {itinerary.trip_title}")
        st.caption(f"{itinerary.origin}  →  {itinerary.destination}  ·  {itinerary.start_date} to {itinerary.end_date}  ·  {itinerary.num_travellers} traveller(s)")
    with col2:
        st.metric("Estimated Cost", format_inr(itinerary.total_estimated_cost_inr))
    with col3:
        st.metric("Budget Used", f"{itinerary.budget_utilisation_pct:.0f}%")


def _render_day(day):
    with st.expander(f"Day {day.day_number}   ·   {day.date_str}   ·   {day.location}", expanded=day.day_number == 1):
        if day.day_notes:
            st.caption(day.day_notes)
        for activity in day.activities:
            symbol = CATEGORY_SYMBOLS.get(activity.category, "•")
            col1, col2, col3 = st.columns([4, 1, 1])
            with col1:
                st.markdown(f"{symbol}  **{activity.time}**  —  {activity.activity}")
                details = []
                if activity.location:
                    details.append(activity.location)
                if activity.duration_hours:
                    details.append(f"{activity.duration_hours:.1f} hours")
                if details:
                    st.caption("  ·  ".join(details))
                if activity.transport:
                    st.caption(f"Transport: {activity.transport}")
                if activity.notes:
                    st.caption(activity.notes)
            with col2:
                if activity.estimated_cost_inr > 0:
                    st.caption(format_inr(activity.estimated_cost_inr))
            with col3:
                st.caption(activity.category.title())
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            if day.accommodation:
                st.caption(f"Accommodation: {day.accommodation}  ·  {format_inr(day.accommodation_cost_inr)}/night")
        with c2:
            st.caption(f"Daily total: **{format_inr(day.total_day_cost_inr)}**")


def _render_itinerary_footer(itinerary: Itinerary):
    st.markdown("### Cost Summary")
    bd = itinerary.budget_breakdown
    cols = st.columns(5)
    metrics = [("Transport", bd.transportation_inr), ("Accommodation", bd.accommodation_inr),
               ("Food", bd.food_inr), ("Activities", bd.activities_inr), ("Miscellaneous", bd.miscellaneous_inr)]
    for i, (label, value) in enumerate(metrics):
        with cols[i]:
            st.metric(label, format_inr(value))
    st.markdown(f"**Total estimated:** {format_inr(itinerary.total_estimated_cost_inr)}  ·  **Total budget:** {format_inr(itinerary.total_budget_inr)}")
    if itinerary.is_within_budget:
        surplus = itinerary.total_budget_inr - itinerary.total_estimated_cost_inr
        st.success(f"Within budget  ·  {format_inr(surplus)} remaining")
    else:
        excess = itinerary.total_estimated_cost_inr - itinerary.total_budget_inr
        st.caption(f"Budget variance: {format_inr(excess)} above the total trip budget")
