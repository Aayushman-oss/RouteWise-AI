"""
RouteWise AI – Navigation Component
"""

import streamlit as st
import config

NAV_PAGES = [
    ("⌂", "Home"),
    ("⌖", "Plan Your Trip"),
    ("▤", "My Itinerary"),
    ("₹", "Budget Planner"),
    ("↻", "Smart Replanning"),
    ("S", "Settings"),
]


def render_navigation() -> str:
    """Render the top navigation bar and return the selected page name."""
    # Custom CSS for nav
    st.markdown(
        """
        <style>
        /* ── Global resets ── */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .block-container {padding-top: 1.2rem; max-width: 1180px;}

        /* ── Top brand bar ── */
        .rw-brand {
            display: flex;
            align-items: center;
            gap: 0.6rem;
            padding: 0.4rem 0 0.8rem 0;
            border-bottom: 1px solid #E2E8EC;
            margin-bottom: 1rem;
        }
        .rw-brand-name {
            font-size: 1.45rem;
            font-weight: 700;
            color: #142B3B;
            letter-spacing: -0.5px;
        }
        .rw-brand-tag {
            font-size: 0.75rem;
            color: #647785;
            margin-top: 2px;
        }
        .rw-badge {
            background: #142B3B;
            color: #fff;
            font-size: 0.65rem;
            padding: 2px 7px;
            border-radius: 6px;
            font-weight: 600;
            letter-spacing: 0.7px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Brand bar
    st.markdown(
        f"""
        <div class="rw-brand">
            <div>
                <div class="rw-brand-name">RouteWise AI</div>
                <div class="rw-brand-tag">IBM Granite · Indian Travel Intelligence</div>
            </div>
            <span class="rw-badge">BETA</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Page selector via columns
    cols = st.columns(len(NAV_PAGES))
    selected_page = st.session_state.get("current_page", "Home")

    for i, (icon, name) in enumerate(NAV_PAGES):
        with cols[i]:
            is_active = selected_page == name
            btn_style = "primary" if is_active else "secondary"
            if st.button(f"{icon}   {name}", key=f"nav_{name}", use_container_width=True, type=btn_style):
                st.session_state["current_page"] = name
                st.rerun()

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    return st.session_state.get("current_page", "Home")


def set_page(name: str):
    """Programmatically navigate to a page."""
    st.session_state["current_page"] = name
    st.rerun()
