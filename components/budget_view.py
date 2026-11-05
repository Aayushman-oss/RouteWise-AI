"""
RouteWise AI – Budget View Component
Uses Plotly for interactive budget visualizations.
"""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from models.itinerary import BudgetBreakdown
from utils.calculations import format_inr


def render_budget_chart(
    breakdown: BudgetBreakdown,
    total_budget_inr: float,
    title: str = "Budget Breakdown",
):
    """Render a donut chart of budget categories."""
    labels = ["Transport", "Accommodation", "Food", "Activities", "Miscellaneous"]
    values = [
        breakdown.transportation_inr,
        breakdown.accommodation_inr,
        breakdown.food_inr,
        breakdown.activities_inr,
        breakdown.miscellaneous_inr,
    ]
    colors = ["#142B3B", "#24566A", "#4F8490", "#91B2B8", "#D5E1E4"]

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker_colors=colors,
        textinfo="label+percent",
        hovertemplate="%{label}: ₹%{value:,.0f}<extra></extra>",
    )])

    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#1f2328")),
        showlegend=True,
        legend=dict(orientation="v", x=1.05, y=0.5),
        margin=dict(l=20, r=20, t=40, b=20),
        height=320,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="system-ui, sans-serif", color="#374151"),
        annotations=[{
            "text": f"<b>{format_inr(breakdown.total_inr)}</b>",
            "x": 0.5, "y": 0.5,
            "font_size": 14,
            "showarrow": False,
        }],
    )
    st.plotly_chart(fig, use_container_width=True)


def render_budget_vs_actual_bar(breakdown: BudgetBreakdown, total_budget_inr: float):
    """Render a horizontal bar comparing estimated vs budget."""
    categories = ["Transport", "Accommodation", "Food", "Activities", "Misc"]
    estimated = [
        breakdown.transportation_inr,
        breakdown.accommodation_inr,
        breakdown.food_inr,
        breakdown.activities_inr,
        breakdown.miscellaneous_inr,
    ]

    # Allocate budget proportionally
    total_est = sum(estimated)
    if total_est > 0:
        budgeted = [total_budget_inr * (e / total_est) for e in estimated]
    else:
        budgeted = [total_budget_inr / len(categories)] * len(categories)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Estimated",
        y=categories,
        x=estimated,
        orientation="h",
        marker_color="#142B3B",
    ))
    fig.add_trace(go.Bar(
        name="Allocated",
        y=categories,
        x=budgeted,
        orientation="h",
        marker_color="#D5E1E4",
    ))
    fig.update_layout(
        barmode="overlay",
        title="Estimated vs Allocated Budget per Category",
        xaxis_title="Amount (₹)",
        height=280,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f7f8fa",
        font=dict(family="system-ui, sans-serif", color="#374151"),
        legend=dict(orientation="h", x=0, y=1.1),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_budget_metrics(breakdown: BudgetBreakdown, total_budget_inr: float):
    """Render budget metrics in a 2×3 grid."""
    util = min((breakdown.total_inr / total_budget_inr * 100), 999) if total_budget_inr > 0 else 0
    surplus = total_budget_inr - breakdown.total_inr

    st.markdown("#### Expense Breakdown")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Transportation", format_inr(breakdown.transportation_inr))
        st.metric("Food", format_inr(breakdown.food_inr))
    with c2:
        st.metric("Accommodation", format_inr(breakdown.accommodation_inr))
        st.metric("Activities", format_inr(breakdown.activities_inr))
    with c3:
        st.metric("Miscellaneous", format_inr(breakdown.miscellaneous_inr))
        st.metric("Budget Used", f"{util:.1f}%")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Estimated", format_inr(breakdown.total_inr))
    with col2:
        delta_color = "normal" if surplus >= 0 else "inverse"
        st.metric(
            "Budget Surplus / Deficit",
            format_inr(abs(surplus)),
            delta="Surplus" if surplus >= 0 else "Deficit",
            delta_color=delta_color,
        )
