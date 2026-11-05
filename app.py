"""
RouteWise AI – Main Application Entry Point
============================================
Run locally:  streamlit run app.py
Deploy:       Streamlit Community Cloud (add IBM credentials in Secrets)
"""

from __future__ import annotations

import streamlit as st
from datetime import date, timedelta

# ── Page config (must be first Streamlit call) ───────────────────────────────
st.set_page_config(
    page_title="RouteWise AI",
    page_icon="R",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Imports ──────────────────────────────────────────────────────────────────
import config
from components.navigation import render_navigation, set_page
from components.destination_cards import render_destination_cards
from components.itinerary_view import render_itinerary
from components.budget_view import render_budget_chart, render_budget_vs_actual_bar, render_budget_metrics
from components.map_view import render_destination_map, render_route_map
from services.destination_service import get_featured_destinations, get_destination, DESTINATIONS
from utils.validation import (
    validate_location_input, validate_budget, validate_dates, validate_num_travellers,
    sanitize_prompt_input,
)
from utils.security import check_prompt_injection


# ── Global CSS ───────────────────────────────────────────────────────────────
def _inject_global_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        /* Typography & Base */
        html, body, [class*="css"] {
            font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
            color: #1D2D36;
        }
        h1, h2, h3 { font-weight: 700; letter-spacing: -0.3px; }
        h1 { font-size: 2rem !important; }
        h2 { font-size: 1.5rem !important; }
        h3 { font-size: 1.1rem !important; }

        /* Streamlit metric tweak */
        [data-testid="metric-container"] {
            background: #F4F7F8;
            border: 1px solid #E2E8EC;
            border-radius: 10px;
            padding: 0.8rem 0.95rem;
        }

        /* Buttons */
        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.85rem;
        }
        .stButton > button[kind="primary"] {
            background: #142B3B;
            color: #fff;
            border: none;
        }
        .stButton > button[kind="primary"]:hover {
            background: #1E4658;
        }

        /* Expander */
        .streamlit-expanderHeader {
            font-weight: 600;
            font-size: 0.95rem;
            background: #F4F7F8;
        }

        /* Section headers */
        .rw-section-header {
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #647785;
            border-bottom: 1px solid #E2E8EC;
            padding-bottom: 0.3rem;
            margin: 1.2rem 0 0.8rem 0;
        }

        /* Info cards */
        .rw-info-card {
            background: #F4F7F8;
            border: 1px solid #E2E8EC;
            border-radius: 12px;
            padding: 1.1rem 1.25rem;
            margin-bottom: 0.6rem;
        }

        /* Hero section */
        .rw-hero {
            background: linear-gradient(120deg, #142B3B 0%, #24566A 100%);
            color: #fff;
            padding: 2.7rem 2.2rem;
            border-radius: 14px;
            margin-bottom: 2rem;
        }
        .rw-hero h1 { color: #fff !important; font-size: 2.2rem !important; margin-bottom: 0.3rem; }
        .rw-hero p { color: #D5E1E4; font-size: 1rem; margin: 0; }

        /* Status pill */
        .rw-pill-green { background: #d1fae5; color: #065f46; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
        .rw-pill-red { background: #fee2e2; color: #991b1b; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
        .rw-pill-yellow { background: #fef9c3; color: #92400e; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }

        /* Tabs, fields and surfaces */
        [data-baseweb="tab-list"] { gap: 0.35rem; border-bottom: 1px solid #E2E8EC; }
        [data-baseweb="tab"] { color: #647785; font-weight: 600; padding: 0.7rem 1rem; }
        [aria-selected="true"][data-baseweb="tab"] { color: #142B3B !important; }
        [data-baseweb="tab-highlight"] { background: #2D7180 !important; }
        [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
        [data-testid="stDateInput"] input, [data-testid="stSelectbox"] > div { border-radius: 8px; }
        .stAlert { border-radius: 10px; }
        div[data-testid="stExpander"] { border: 1px solid #E2E8EC; border-radius: 10px; overflow: hidden; }

        /* Hide Streamlit default padding on top */
        .main > .block-container { padding-top: 0.65rem !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── Session state helpers ────────────────────────────────────────────────────
def _init_session():
    defaults = {
        "current_page": "Home",
        "planning_result": None,
        "replanning_result": None,
        "approved_replan": False,
        "prefill_destination": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: HOME
# ─────────────────────────────────────────────────────────────────────────────
def page_home():
    st.markdown(
        """
        <div class="rw-hero">
            <h1>RouteWise AI</h1>
            <p>Intelligent Indian Travel Planning · Powered by IBM Granite on watsonx.ai</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Quick-start CTA
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(
            """
            **Plan smarter. Travel better.**

            RouteWise AI brings together destination intelligence, route optimization,
            budget planning and real-time weather insights — all driven by IBM Granite,
            IBM's enterprise foundation model.
            """
        )
        if st.button("Start Planning Your Trip", type="primary", use_container_width=True):
            set_page("Plan Your Trip")
    with col2:
        cfg_status = config.validate_config()
        status_class = "rw-pill-green" if cfg_status.is_ready else "rw-pill-red"
        status_text = "Granite Connected" if cfg_status.is_ready else "Granite: Setup Required"
        st.markdown(f'<span class="{status_class}">{status_text}</span>', unsafe_allow_html=True)
        st.caption("IBM Granite 4H Small")
    with col3:
        st.caption("Built for IBM SkillsBuild")
        st.caption("University Education Internship")

    st.markdown('<div class="rw-section-header">Featured Destinations</div>', unsafe_allow_html=True)

    featured = get_featured_destinations(6)
    render_destination_cards(featured, cols=3)

    # How it works
    st.markdown('<div class="rw-section-header">How RouteWise AI Works</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    steps = [
        ("1", "Share Preferences", "Tell us your destination, dates, budget and interests."),
        ("2", "AI Analysis", "IBM Granite analyzes options across 6 specialized agents."),
        ("3", "Itinerary Generated", "Get a day-by-day plan with activities, costs and maps."),
        ("4", "Smart Adaptation", "Dynamic replanning adapts to weather or plan changes."),
    ]
    for col, (num, title, desc) in zip([c1, c2, c3, c4], steps):
        with col:
            st.markdown(
                f"""
                <div class="rw-info-card" style="text-align:center">
                    <div style="font-size:1.5rem;font-weight:700;color:#142B3B">{num}</div>
                    <div style="font-weight:600;margin:0.3rem 0">{title}</div>
                    <div style="font-size:0.82rem;color:#647785">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: PLAN YOUR TRIP
# ─────────────────────────────────────────────────────────────────────────────
def page_plan_trip():
    st.markdown("## Plan Your Trip")
    st.caption("Fill in your travel details and let IBM Granite generate your personalized itinerary.")

    cfg_status = config.validate_config()
    if not cfg_status.is_ready:
        st.warning(
            "**IBM Granite not configured.** A template itinerary will be generated. "
            "Add your credentials in the Settings page for AI-powered planning.",
            
        )

    with st.form("trip_form"):
        st.markdown('<div class="rw-section-header">Trip Basics</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            origin = st.text_input(
                "Starting Location",
                placeholder="e.g. New Delhi",
                help="City or town you're departing from",
            )
        with c2:
            default_dest = st.session_state.get("prefill_destination", "")
            destination = st.text_input(
                "Destination",
                value=default_dest,
                placeholder="e.g. Jaipur",
                help="Your primary destination in India",
            )

        st.markdown('<div class="rw-section-header">Dates & Travellers</div>', unsafe_allow_html=True)
        c3, c4, c5 = st.columns(3)
        with c3:
            today = date.today()
            start_date = st.date_input("Departure Date", value=today + timedelta(days=7), min_value=today)
        with c4:
            end_date = st.date_input("Return Date", value=today + timedelta(days=12), min_value=today + timedelta(days=1))
        with c5:
            num_travellers = st.number_input("Number of Travellers", min_value=1, max_value=50, value=2)

        st.markdown('<div class="rw-section-header">Budget & Preferences</div>', unsafe_allow_html=True)
        c6, c7 = st.columns(2)
        with c6:
            budget = st.number_input(
                "Total Budget (₹ INR)",
                min_value=500,
                max_value=10_000_000,
                value=30000,
                step=1000,
                help="Total budget for the entire trip including all expenses",
            )
        with c7:
            accommodation = st.selectbox(
                "Accommodation Preference",
                ["budget", "mid-range", "luxury", "homestay"],
                index=1,
            )

        c8, c9 = st.columns(2)
        with c8:
            transport = st.selectbox(
                "Transport Preference",
                ["mixed", "train", "bus", "flight", "car"],
                index=0,
            )
        with c9:
            interests = st.multiselect(
                "Interests & Activities",
                ["history", "culture", "food", "adventure", "nature", "photography",
                 "spirituality", "wildlife", "beaches", "trekking", "art", "shopping"],
                default=["culture", "food"],
            )

        additional_notes = st.text_area(
            "Additional Notes (optional)",
            placeholder="Any specific requirements, accessibility needs, or preferences...",
            max_chars=1000,
            height=80,
        )

        submitted = st.form_submit_button("Generate My Itinerary", type="primary", use_container_width=True)

    if submitted:
        _handle_trip_form_submission(
            origin=origin,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            num_travellers=int(num_travellers),
            budget=float(budget),
            accommodation=accommodation,
            transport=transport,
            interests=interests,
            additional_notes=additional_notes,
        )


def _handle_trip_form_submission(**kwargs):
    """Validate, build request, run orchestrator, store result."""
    from models.travel_request import TravelRequest
    from pydantic import ValidationError

    # Validate inputs
    errors = []
    ok, msg = validate_location_input(kwargs["origin"])
    if not ok: errors.append(f"Origin: {msg}")
    ok, msg = validate_location_input(kwargs["destination"])
    if not ok: errors.append(f"Destination: {msg}")
    ok, msg = validate_budget(kwargs["budget"])
    if not ok: errors.append(f"Budget: {msg}")
    ok, msg = validate_dates(kwargs["start_date"], kwargs["end_date"])
    if not ok: errors.append(f"Dates: {msg}")
    ok, msg = validate_num_travellers(kwargs["num_travellers"])
    if not ok: errors.append(f"Travellers: {msg}")

    if kwargs.get("additional_notes") and check_prompt_injection(kwargs["additional_notes"]):
        errors.append("Additional notes contain disallowed content. Please rephrase.")

    if errors:
        for e in errors:
            st.error(e)
        return

    try:
        request = TravelRequest(
            origin=sanitize_prompt_input(kwargs["origin"]),
            destination=sanitize_prompt_input(kwargs["destination"]),
            start_date=kwargs["start_date"],
            end_date=kwargs["end_date"],
            num_travellers=kwargs["num_travellers"],
            budget_inr=kwargs["budget"],
            accommodation_preference=kwargs["accommodation"],
            transport_preference=kwargs["transport"],
            interests=kwargs["interests"],
            additional_notes=sanitize_prompt_input(kwargs.get("additional_notes") or ""),
        )
    except ValidationError as exc:
        for err in exc.errors():
            st.error(f"{err['loc'][-1]}: {err['msg']}")
        return

    from agents.orchestrator import get_orchestrator
    with st.spinner("IBM Granite is planning your trip across 6 AI agents…"):
        try:
            orchestrator = get_orchestrator()
            result = orchestrator.plan(request)
            st.session_state["planning_result"] = result
            st.session_state["replanning_result"] = None
            st.session_state["approved_replan"] = False
            st.session_state["prefill_destination"] = ""
            st.success(
                f"Itinerary generated in {result.elapsed_seconds}s! "
                + ("(IBM Granite)" if result.granite_used else "(Template – connect Granite for AI planning)")
            )
            st.session_state["current_page"] = "My Itinerary"
            st.rerun()
        except Exception as exc:
            st.error(f"Planning failed: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: MY ITINERARY
# ─────────────────────────────────────────────────────────────────────────────
def page_itinerary():
    st.markdown("## My Itinerary")

    result = st.session_state.get("planning_result")
    if not result or not result.itinerary:
        st.info("No itinerary yet. Go to **Plan Your Trip** to create one.")
        if st.button("Go to Trip Planner →", type="primary"):
            set_page("Plan Your Trip")
        return

    itinerary = result.itinerary

    # Map tab alongside itinerary
    tab1, tab2, tab3 = st.tabs(["Day-by-Day Plan", "Map", "Route Details"])

    with tab1:
        render_itinerary(itinerary)

    with tab2:
        dest = get_destination(itinerary.destination)
        if dest:
            render_destination_map(
                latitude=dest["latitude"],
                longitude=dest["longitude"],
                destination=itinerary.destination,
                attractions=dest.get("highlights"),
            )
        else:
            # Try geocoding
            from services.maps_service import geocode
            coords = geocode(itinerary.destination)
            if coords:
                render_destination_map(coords[0], coords[1], itinerary.destination)
            else:
                st.info("Map coordinates not available for this destination.")

        # Route map
        if result.route_data:
            st.markdown("#### Route Overview")
            from services.maps_service import geocode
            origin_c = geocode(itinerary.origin)
            dest_c = geocode(itinerary.destination)
            render_route_map(origin_c, dest_c, itinerary.origin, itinerary.destination)

    with tab3:
        if result.route_data:
            route = result.route_data.get("route_info", {})
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Distance", f"{route.get('distance_km', 'N/A')} km")
            with col2:
                hrs = route.get("duration_hours", 0)
                st.metric("Travel Time", f"{hrs:.1f} hours")
            with col3:
                rec = result.route_data.get("recommended_transport", "N/A")
                st.metric("Recommended", rec.title())

            if route.get("is_estimated"):
                st.caption("Distance and duration are estimates based on a straight-line calculation.")

            reasoning = result.route_data.get("reasoning")
            if reasoning:
                st.info(f"**Route advice:** {reasoning}")

            tips = result.route_data.get("journey_tips", [])
            if tips:
                st.markdown("**Journey Tips:**")
                for tip in tips:
                    st.markdown(f"- {tip}")

            costs = result.route_data.get("transport_costs_inr", {})
            if costs:
                from utils.calculations import format_inr
                st.markdown("**Transport Cost Comparison** (estimated, all travellers, round-trip):")
                cost_df_data = {"Mode": list(costs.keys()), "Estimated Cost": [format_inr(v) for v in costs.values()]}
                import pandas as pd
                st.dataframe(pd.DataFrame(cost_df_data), use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: BUDGET PLANNER
# ─────────────────────────────────────────────────────────────────────────────
def page_budget():
    st.markdown("## Budget Planner")

    result = st.session_state.get("planning_result")
    if not result or not result.itinerary:
        st.info("Generate an itinerary first to see your budget breakdown.")
        if st.button("Plan a Trip →", type="primary"):
            set_page("Plan Your Trip")
        return

    itinerary = result.itinerary
    budget_data = result.budget_data or {}
    breakdown = itinerary.budget_breakdown

    render_budget_metrics(breakdown, itinerary.total_budget_inr)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        render_budget_chart(breakdown, itinerary.total_budget_inr, "Expense Distribution")
    with col2:
        render_budget_vs_actual_bar(breakdown, itinerary.total_budget_inr)

    # Budget advisory from Granite
    if budget_data:
        st.markdown('<div class="rw-section-header">Budget Advisory</div>', unsafe_allow_html=True)
        assessment = budget_data.get("budget_assessment")
        if assessment:
            st.info(f"{assessment}")

        col1, col2 = st.columns(2)
        with col1:
            tips = budget_data.get("cost_saving_tips", [])
            if tips:
                st.markdown("**Cost-Saving Tips**")
                for tip in tips:
                    st.markdown(f"- {tip}")
        with col2:
            splurge = budget_data.get("splurge_suggestions", [])
            if splurge:
                st.markdown("**Worth the Splurge**")
                for s in splurge:
                    st.markdown(f"- {s}")

        warning = budget_data.get("budget_warning")
        if warning:
            st.warning(f"{warning}")

    st.caption(
        "All figures are estimates based on typical costs for Indian travel. "
        "Actual prices vary by season, availability and personal choices. "
        "Always verify with local sources before booking."
    )


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: SMART REPLANNING
# ─────────────────────────────────────────────────────────────────────────────
def page_replanning():
    st.markdown("## Smart Replanning")
    st.caption("Simulate a disruption and let IBM Granite intelligently revise your itinerary.")

    result = st.session_state.get("planning_result")
    if not result or not result.itinerary:
        st.info("You need an existing itinerary to test replanning.")
        if st.button("Create an Itinerary →", type="primary"):
            set_page("Plan Your Trip")
        return

    itinerary = result.itinerary
    num_days = len(itinerary.days)

    st.markdown(
        f"""
        <div class="rw-info-card">
            <b>Current trip:</b> {itinerary.trip_title}<br>
            <b>Days:</b> {num_days}  ·  
            <b>Destination:</b> {itinerary.destination}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="rw-section-header">Disruption Details</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        disruption_type = st.selectbox(
            "Disruption Type",
            ["weather", "transport", "safety", "personal"],
        )
    with col2:
        affected_day = st.selectbox(
            "Affected Day",
            list(range(1, num_days + 1)),
            format_func=lambda d: f"Day {d} – {itinerary.days[d-1].date_str if d <= len(itinerary.days) else ''}",
        )

    disruption_desc = st.text_area(
        "Describe the Disruption",
        placeholder="e.g. Heavy rainfall forecast for the day – outdoor activities may be unsafe.",
        max_chars=500,
        height=80,
    )

    if not disruption_desc.strip():
        # Pre-fill with example
        examples = {
            "weather": "Heavy rainfall and thunderstorm warning issued for the day.",
            "transport": "Railway strike affecting train services in the region.",
            "safety": "Local curfew declared in the planned area.",
            "personal": "One traveller is unwell and needs a rest day.",
        }
        disruption_desc = examples.get(disruption_type, "")
        st.caption(f"Example: {disruption_desc}")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        generate_btn = st.button("Generate Revised Plan", type="primary", use_container_width=True)

    replan_result = st.session_state.get("replanning_result")

    if generate_btn and disruption_desc.strip():
        if check_prompt_injection(disruption_desc):
            st.error("Disruption description contains disallowed content.")
        else:
            from agents.orchestrator import get_orchestrator
            with st.spinner("IBM Granite is replanning your affected day…"):
                try:
                    orchestrator = get_orchestrator()
                    replan_result = orchestrator.replan(
                        itinerary=itinerary,
                        disruption_type=disruption_type,
                        disruption_description=sanitize_prompt_input(disruption_desc),
                        affected_day=affected_day,
                    )
                    st.session_state["replanning_result"] = replan_result
                    st.session_state["approved_replan"] = False
                    st.success("Revised plan ready! Review the changes below before approving.")
                except Exception as exc:
                    st.error(f"Replanning failed: {exc}")

    # Show comparison
    if replan_result and not st.session_state.get("approved_replan"):
        st.markdown("---")
        st.markdown("### Proposed Changes")

        st.info(f"**Reason:** {replan_result.reason}")
        if replan_result.changes_made:
            st.markdown("**Changes:**")
            for change in replan_result.changes_made:
                st.markdown(f"- {change}")

        col_orig, col_rev = st.columns(2)
        with col_orig:
            st.markdown("**Original Plan – Day " + str(affected_day) + "**")
            orig_day = next((d for d in itinerary.days if d.day_number == affected_day), None)
            if orig_day:
                for a in orig_day.activities:
                    st.markdown(f"- **{a.time}** {a.activity}")
        with col_rev:
            st.markdown("**Revised Plan – Day " + str(affected_day) + "**")
            rev_day = next((d for d in replan_result.revised_itinerary.days if d.day_number == affected_day), None)
            if rev_day:
                for a in rev_day.activities:
                    st.markdown(f"- **{a.time}** {a.activity}")

        st.warning("**Your existing itinerary will be replaced.** This action cannot be undone.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Approve & Apply Changes", type="primary", use_container_width=True):
                result.itinerary = replan_result.revised_itinerary
                st.session_state["planning_result"] = result
                st.session_state["approved_replan"] = True
                st.success("Revised itinerary applied! View it in the My Itinerary page.")
                st.rerun()
        with c2:
            if st.button("Keep Original", use_container_width=True):
                st.session_state["replanning_result"] = None
                st.rerun()

    elif st.session_state.get("approved_replan"):
        st.success("Revised itinerary is active. View it in the My Itinerary page.")
        if st.button("View Updated Itinerary →"):
            set_page("My Itinerary")


# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTIC GUIDANCE HELPER
# ─────────────────────────────────────────────────────────────────────────────

# Diagnostic codes are defined in services/watsonx_service.py; imported here
# as string literals so this helper stays importable even without the SDK.
_DIAG_GUIDANCE: dict[str, tuple[str, str]] = {
    "MISSING_CREDENTIALS": (
        "Credentials not configured",
        "Add `WATSONX_API_KEY` and `WATSONX_PROJECT_ID` to your `.env` file "
        "(local) or to Streamlit Secrets (cloud deployment).",
    ),
    "AUTH_FAILED": (
        "API key authentication failed (401)",
        "Your IBM Cloud API key may be **invalid, expired, or revoked**.\n\n"
        "- Generate a new key at [cloud.ibm.com/iam/apikeys](https://cloud.ibm.com/iam/apikeys)\n"
        "- Ensure you are using an **IBM Cloud API key**, not a Watson Studio token\n"
        "- Update `WATSONX_API_KEY` in `.env` and restart the app",
    ),
    "PERMISSION_DENIED": (
        "Permission denied (403)",
        "Your IBM Cloud account or plan may not have watsonx.ai access.\n\n"
        "- Verify service entitlements at [cloud.ibm.com](https://cloud.ibm.com)\n"
        "- Ensure watsonx.ai is provisioned in your account\n"
        "- Check that your API key has the required IAM roles",
    ),
    "PROJECT_NOT_FOUND": (
        "watsonx.ai project not found (404)",
        "The `WATSONX_PROJECT_ID` in your `.env` does not match any project "
        "in your IBM Cloud account or region.\n\n"
        "- Log in to [dataplatform.cloud.ibm.com](https://dataplatform.cloud.ibm.com)\n"
        "- Open your project → **Manage** → **General** → copy the **Project ID**\n"
        "- Update `WATSONX_PROJECT_ID` in `.env` and restart the app\n"
        "- Ensure the project is in the same region as `WATSONX_URL`",
    ),
    "MODEL_NOT_FOUND": (
        "Model not available",
        f"The model is not available in your watsonx.ai project or region.\n\n"
        "- Check available models at [dataplatform.cloud.ibm.com](https://dataplatform.cloud.ibm.com)\n"
        "- Ensure `WATSONX_MODEL_ID` is set correctly in `.env`\n"
        "- The default is `ibm/granite-4-h-small`",
    ),
    "RATE_LIMIT": (
        "⏳ Rate limit or quota exceeded (429)",
        "You have hit IBM watsonx.ai's API quota or rate limit.\n\n"
        "- Wait a few minutes and try again\n"
        "- Check your usage at [cloud.ibm.com/billing](https://cloud.ibm.com/billing)",
    ),
    "REGION_OR_ENDPOINT_ERROR": (
        "Regional endpoint error (5xx)",
        "IBM watsonx.ai returned a server error. This may indicate:\n\n"
        "- An incorrect regional endpoint in `WATSONX_URL`\n"
        "- A temporary IBM service outage — check [ibm.com/cloud/status](https://www.ibm.com/cloud/status)\n"
        "- Valid regions: `us-south`, `eu-de`, `eu-gb`, `jp-tok`, `au-syd`\n"
        "  Example: `https://us-south.ml.cloud.ibm.com`",
    ),
    "NETWORK_TIMEOUT": (
        "Connection timed out",
        "The request to IBM watsonx.ai timed out.\n\n"
        "- Check your internet connection\n"
        "- Try increasing `REQUEST_TIMEOUT` in `.env` (current default: 60s)\n"
        "- Verify `WATSONX_URL` is reachable from your network",
    ),
    "NETWORK_ERROR": (
        "Network error",
        "Could not reach IBM watsonx.ai.\n\n"
        "- Check your internet connection\n"
        "- Verify `WATSONX_URL` is correct and reachable\n"
        "- If behind a corporate firewall, check proxy settings",
    ),
    "UNKNOWN_ERROR": (
        "Unexpected error",
        "An unexpected error occurred. Check the application logs for the "
        "exception class and diagnostic code. "
        "No credentials or API keys are written to logs.",
    ),
}


def _render_diagnostic_guidance(diag_code: str) -> None:
    """Render an expanded guidance panel for the given diagnostic code."""
    if not diag_code or diag_code == "OK":
        return
    label, guidance = _DIAG_GUIDANCE.get(
        diag_code,
        ("Diagnostic: " + diag_code, "Check application logs for more details."),
    )
    with st.expander(f"Diagnostic: {label}", expanded=True):
        st.markdown(guidance)
        st.caption(f"Diagnostic code: `{diag_code}`")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: SETTINGS
# ─────────────────────────────────────────────────────────────────────────────
def page_settings():
    st.markdown("## Settings")
    st.caption("IBM Granite configuration status and connection diagnostics.")

    cfg = config.get_safe_config_display()
    cfg_status = config.validate_config()

    st.markdown('<div class="rw-section-header">IBM Granite Connection</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        status_icon = "●" if cfg_status.is_ready else "○"
        st.markdown(f"**Status:** {status_icon} {cfg_status.summary}")
        st.markdown(f"**Model ID:** `{cfg['model_id']}`")
        st.markdown(f"**Endpoint:** `{cfg['endpoint_url']}`")
        st.markdown(f"**API Key:** {'Configured' if cfg['api_key_configured'] else 'Not set'}")
        st.markdown(f"**Project ID:** {'Configured' if cfg['project_id_configured'] else 'Not set'}")
    with col2:
        st.markdown(f"**Max Tokens:** `{cfg['max_new_tokens']}`")
        st.markdown(f"**Temperature:** `{cfg['temperature']}`")
        st.markdown(f"**Timeout:** `{cfg['request_timeout']}s`")
        st.markdown(f"**App Version:** `{cfg['app_version']}`")

    st.markdown('<div class="rw-section-header">Connection Test</div>', unsafe_allow_html=True)
    if st.button("Test IBM Granite Connection", type="primary"):
        if not cfg_status.is_ready:
            st.error("Cannot test — credentials not configured. Add them to `.env` or Streamlit secrets.")
        else:
            from services.watsonx_service import get_watsonx_service
            with st.spinner("Testing connection to IBM Granite…"):
                svc = get_watsonx_service()
                # Reset cached client so the test always probes fresh
                svc.reset()
                test_result = svc.test_connection()
            if test_result.success:
                st.success(f"{test_result.message}")
                if test_result.response_preview:
                    st.caption(f"Model response preview: {test_result.response_preview}")
            else:
                st.error(f"{test_result.message}")
                _render_diagnostic_guidance(test_result.diag_code)

    # ── Model Availability ───────────────────────────────────────────────────
    st.markdown('<div class="rw-section-header">Model Availability in Your Region</div>', unsafe_allow_html=True)

    # Derive a short region label from the endpoint URL
    _endpoint_label = config.WATSONX_URL
    _region_map = {
        "us-south": "US South (Dallas)",
        "eu-de": "EU Frankfurt",
        "eu-gb": "EU London",
        "jp-tok": "Tokyo",
        "au-syd": "Sydney",
    }
    _region_display = next(
        (label for key, label in _region_map.items() if key in config.WATSONX_URL),
        config.WATSONX_URL,
    )

    with st.expander(f"Available models at {_region_display}", expanded=False):
        if not cfg_status.is_ready:
            st.info("Configure your IBM credentials above to probe model availability.")
        else:
            if st.button("Check Model Availability", key="btn_model_avail"):
                from services.watsonx_service import get_watsonx_service, WatsonxError, ConfigError
                from services.model_discovery import list_available_models

                with st.spinner("Querying IBM watsonx.ai model catalog…"):
                    svc = get_watsonx_service()
                    svc.reset()
                    # Initialise client so we can pass it to discovery
                    _avail_error = None
                    try:
                        svc._ensure_client()
                        discovery = list_available_models(svc._client)
                    except (WatsonxError, ConfigError) as _exc:
                        discovery = None
                        _avail_error = str(_exc)
                    except Exception as _exc:
                        discovery = None
                        _avail_error = f"Unexpected error ({type(_exc).__name__})"

                if _avail_error:
                    st.error(f"Could not retrieve model list: {_avail_error}")
                elif discovery is None or not discovery.success:
                    st.warning(
                        f"Could not retrieve model list: "
                        f"{getattr(discovery, 'error', 'Unknown error') if discovery else 'No result'}"
                    )
                else:
                    _configured_model = config.WATSONX_MODEL_ID
                    _model_found = discovery.is_model_available(_configured_model)
                    _is_gen = discovery.is_generative_model_available(_configured_model)

                    # Configured model status
                    if _model_found and _is_gen:
                        st.success(f"Configured model `{_configured_model}` is available and supports generation.")
                    elif _model_found and not _is_gen:
                        st.warning(
                            f"Configured model `{_configured_model}` exists in this region "
                            "but does **not** support text generation (it may be an embedding or time-series model)."
                        )
                    else:
                        st.error(
                            f"Configured model `{_configured_model}` is **not available** in this region ({_region_display})."
                        )

                    # Generative Granite models
                    _gen_granite = discovery.generative_granite_models()
                    if _gen_granite:
                        st.markdown("**IBM Granite generative models available in this region:**")
                        for _m in _gen_granite:
                            _tick = "●" if _m.model_id == _configured_model else "○"
                            st.markdown(f"  {_tick} `{_m.model_id}` — {_m.label}")
                    else:
                        st.warning(
                            "No IBM Granite generative models are available in this region.\n\n"
                            "Your IBM Lite plan in this region may only include embedding or "
                            "time-series Granite models. Consider switching to **US South** "
                            "(`https://us-south.ml.cloud.ibm.com`) where Granite generative "
                            "models are typically available."
                        )

                    # Other generative models (non-Granite)
                    _other_gen = [m for m in discovery.generative_models() if not m.is_granite]
                    if _other_gen:
                        with st.expander(f"Other generative models available ({len(_other_gen)})", expanded=False):
                            for _m in _other_gen:
                                st.markdown(f"  • `{_m.model_id}` — {_m.label}")

                    st.caption(
                        f"Total models in catalog: {len(discovery.models)} | "
                        f"Generative: {len(discovery.generative_models())} | "
                        f"Generative Granite: {len(_gen_granite)}"
                    )

    st.markdown('<div class="rw-section-header">How to Configure Credentials</div>', unsafe_allow_html=True)

    with st.expander("Local Development (.env file)"):
        st.code(
            """# .env (never commit to Git)
WATSONX_API_KEY=your_ibm_cloud_api_key
WATSONX_PROJECT_ID=your_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=ibm/granite-4-h-small""",
            language="bash",
        )
        st.markdown(
            "1. Create your IBM Cloud API key at [cloud.ibm.com/iam/apikeys](https://cloud.ibm.com/iam/apikeys)\n"
            "2. Create a watsonx.ai project at [dataplatform.cloud.ibm.com](https://dataplatform.cloud.ibm.com)\n"
            "3. Copy your Project ID from the project settings\n"
            "4. Paste values into `.env` and restart the app"
        )

    with st.expander("Streamlit Community Cloud (Secrets)"):
        st.code(
            """# Settings → Secrets in Streamlit Cloud
WATSONX_API_KEY = "your_ibm_cloud_api_key"
WATSONX_PROJECT_ID = "your_project_id"
WATSONX_URL = "https://us-south.ml.cloud.ibm.com"
WATSONX_MODEL_ID = "ibm/granite-4-h-small" """,
            language="toml",
        )
        st.markdown(
            "Never upload `.env` to GitHub. Use Streamlit Cloud's Secrets panel instead."
        )

    st.markdown('<div class="rw-section-header">About RouteWise AI</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        - **Application:** {config.APP_NAME} v{config.APP_VERSION}
        - **Purpose:** Intelligent Indian travel planning powered by IBM Granite
        - **AI Model:** IBM Granite 4H Small (`{config.WATSONX_MODEL_ID}`)
        - **Architecture:** 6-agent pipeline (Preference → Destination → Route → Budget → Weather → Itinerary)
        - **Project:** IBM SkillsBuild University Education Internship
        - **External APIs:** Open-Meteo (weather), OpenStreetMap Nominatim (geocoding), OSRM (routing)
        """
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ROUTER
# ─────────────────────────────────────────────────────────────────────────────
def main():
    _init_session()
    _inject_global_css()
    current_page = render_navigation()

    if current_page == "Home":
        page_home()
    elif current_page == "Plan Your Trip":
        page_plan_trip()
    elif current_page == "My Itinerary":
        page_itinerary()
    elif current_page == "Budget Planner":
        page_budget()
    elif current_page == "Smart Replanning":
        page_replanning()
    elif current_page == "Settings":
        page_settings()
    else:
        page_home()


if __name__ == "__main__":
    main()
