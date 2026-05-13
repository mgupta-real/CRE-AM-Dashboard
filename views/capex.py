"""pages/capex.py — CapEx tracking page."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date
from database.db import execute, fetchall
from utils.formatting import fmt_currency, fmt_pct, fmt_date, fmt_number
from components.theme import kpi_card, COLORS
from components.charts import capex_by_category


def render(property_id: int | None):
    st.markdown("## 🔧 CapEx Tracker")
    if not property_id:
        st.warning("Select a property to manage CapEx.")
        return

    projects = fetchall("SELECT * FROM capex_projects WHERE property_id=? ORDER BY start_date DESC", (property_id,))

    # ── KPI Row ───────────────────────────────────────────────────────────
    if projects:
        total_budget = sum((p.get("budget") or 0) for p in projects)
        total_actual = sum((p.get("actual_spent") or 0) for p in projects)
        remaining    = total_budget - total_actual
        pct_spent    = (total_actual / total_budget * 100) if total_budget > 0 else 0
        over_budget  = sum(1 for p in projects if (p.get("actual_spent") or 0) > (p.get("budget") or 0))

        cols = st.columns(5)
        kpis = [
            ("Total Budget",   fmt_currency(total_budget), "📋", None),
            ("Actual Spent",   fmt_currency(total_actual), "💸", None),
            ("Remaining",      fmt_currency(remaining),    "💰", remaining >= 0),
            ("% Spent",        fmt_pct(pct_spent),         "📊", None),
            ("Over-Budget",    str(over_budget),           "⚠",  False if over_budget > 0 else None),
        ]
        for col, (label, value, icon, pos) in zip(cols, kpis):
            with col:
                st.markdown(kpi_card(label, value, icon=icon), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # ── Capex by Category ──────────────────────────────────────────────
        cat_data: dict[str, dict] = {}
        for p in projects:
            cat = p.get("category") or "Uncategorized"
            if cat not in cat_data:
                cat_data[cat] = {"budget": 0, "actual": 0}
            cat_data[cat]["budget"] += (p.get("budget") or 0)
            cat_data[cat]["actual"] += (p.get("actual_spent") or 0)

        if cat_data:
            st.markdown('<div class="dash-card"><div class="dash-card-title">CapEx by Category</div>', unsafe_allow_html=True)
            st.plotly_chart(
                capex_by_category(
                    list(cat_data.keys()),
                    [cat_data[c]["budget"] for c in cat_data],
                    [cat_data[c]["actual"] for c in cat_data],
                ),
                use_container_width=True, config={"displayModeBar": False},
            )
            st.markdown("</div>", unsafe_allow_html=True)

        # ── Project Table ──────────────────────────────────────────────────
        st.markdown('<div class="dash-card"><div class="dash-card-title">CapEx Projects</div>', unsafe_allow_html=True)
        rows = []
        for p in projects:
            budget = p.get("budget") or 0
            actual = p.get("actual_spent") or 0
            rem    = budget - actual
            pct    = (actual / budget * 100) if budget > 0 else 0
            over   = actual > budget
            rows.append({
                "Project":        p.get("project_name", ""),
                "Category":       p.get("category", ""),
                "Status":         p.get("status", ""),
                "Budget":         fmt_currency(budget),
                "Actual":         fmt_currency(actual),
                "Remaining":      fmt_currency(rem),
                "% Spent":        fmt_pct(pct),
                "Over Budget":    "⚠ YES" if over else "—",
                "Vendor":         p.get("vendor", ""),
                "Start":          fmt_date(p.get("start_date")),
                "Est. Completion":fmt_date(p.get("expected_end")),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    else:
        st.info("No CapEx projects yet. Add one below.")

    # ── Add project form ──────────────────────────────────────────────────
    with st.expander("➕ Add CapEx Project", expanded=not projects):
        _add_capex_form(property_id)


def _add_capex_form(property_id: int):
    col1, col2, col3 = st.columns(3)
    with col1:
        name     = st.text_input("Project Name")
        category = st.selectbox("Category", [
            "Interior Renovation", "Exterior", "Roof", "HVAC", "Plumbing",
            "Electrical", "Common Areas", "Amenities", "Parking", "Technology", "Other"
        ])
        budget   = st.number_input("Budget ($)", min_value=0.0, step=1000.0, format="%.0f")
        actual   = st.number_input("Actual Spent ($)", min_value=0.0, step=100.0, format="%.0f")
    with col2:
        status   = st.selectbox("Status", ["Planned", "In Progress", "Complete", "On Hold", "Over Budget"])
        vendor   = st.text_input("Vendor / Contractor")
        start    = st.date_input("Start Date", value=date.today())
        end_exp  = st.date_input("Expected Completion", value=date.today())
    with col3:
        notes    = st.text_area("Notes", height=120)

    if st.button("💾 Save CapEx Project", key="save_capex"):
        if not name:
            st.error("Project name is required.")
        else:
            execute("""
                INSERT INTO capex_projects
                (property_id,project_name,category,budget,actual_spent,start_date,
                 expected_end,status,vendor,notes,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (property_id, name, category, budget, actual,
                  start.isoformat(), end_exp.isoformat(), status, vendor, notes,
                  datetime.now().isoformat(), datetime.now().isoformat()))
            st.success("✅ CapEx project saved!")
            st.rerun()
