"""
RouteWise AI – Destination Cards Component
"""

from __future__ import annotations

import streamlit as st
from typing import List, Dict


def render_destination_cards(destinations: List[Dict], cols: int = 3):
    """Render destination cards in a grid layout."""
    st.markdown(
        """
        <style>
        .dest-card {
            border: 1px solid #E2E8EC;
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 0.5rem;
            background: #fff;
        }
        .dest-name {font-size: 1.05rem; font-weight: 700; color: #142B3B; margin-bottom: 0.15rem;}
        .dest-region {font-size: 0.75rem; color: #647785; text-transform: uppercase; letter-spacing: 0.5px;}
        .dest-desc {font-size: 0.85rem; color: #40545F; margin: 0.4rem 0;}
        .dest-tag {
            display: inline-block;
            background: #F4F7F8;
            border: 1px solid #E2E8EC;
            color: #40545F;
            font-size: 0.7rem;
            padding: 1px 7px;
            border-radius: 20px;
            margin: 2px 2px 0 0;
        }
        .dest-budget {font-size: 0.78rem; color: #647785; margin-top: 0.5rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    rows = [destinations[i:i+cols] for i in range(0, len(destinations), cols)]
    for row in rows:
        grid = st.columns(len(row))
        for i, dest in enumerate(row):
            with grid[i]:
                tags_html = "".join(f'<span class="dest-tag">{t}</span>' for t in dest.get("tags", [])[:4])
                best = ", ".join(dest.get("best_months", [])[:4])
                st.markdown(
                    f"""
                    <div class="dest-card">
                        <div class="dest-name">{dest['name']}</div>
                        <div class="dest-region">{dest.get('region', '')} · {dest.get('type', '').title()}</div>
                        <div class="dest-desc">{dest.get('description', '')}</div>
                        <div>{tags_html}</div>
                        <div class="dest-budget">Best months: {best or 'Year-round'}</div>
                        <div class="dest-budget">Avg ₹{dest.get('avg_budget_per_day_inr', 2000):,}/day</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Plan Trip →", key=f"plan_{dest['name']}", use_container_width=True):
                    st.session_state["prefill_destination"] = dest["city"]
                    st.session_state["current_page"] = "Plan Your Trip"
                    st.rerun()
