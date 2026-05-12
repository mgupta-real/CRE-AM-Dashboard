"""
pages/financials.py
Financial Dashboard — powered by T12 parsed data.
Renders KPI cards, charts, tables, and variance watchlist.
"""
import streamlit as st
import pandas as pd
import numpy as np
from components.theme import inject_css, kpi_card, COLORS
from components.charts import (
    revenue_expense_noi_trend, noi_margin_trend, t_period_comparison,
    revenue_mix_donut, expense_mix_donut, noi_bridge,
)
from utils.formatting import fmt_currency, fmt_pct, fmt_month_label, fmt_number


def render(t12_data: dict | None, rr_data: dict | None, budget_data: dict | None = None):
    if t12_data is None:
        _render_empty_state()
        return

    if t12_data.get("errors"):
        for e in t12_data["errors"]:
            st.error(f"⚠ {e}")
        return

    s = t12_data.get("summary", {})
    rev   = s.get("total_revenue_t12")
    exp   = s.get("total_expenses_t12")
    noi   = s.get("noi_t12")
    margin= s.get("noi_margin_t12")
    occ   = rr_data["summary"]["physical_occ"] if rr_data else None

    # ── KPI Row ────────────────────────────────────────────────────────────
    cols = st.columns(6)
    kpis = [
        ("Total Revenue (T12)", fmt_currency(rev, 0), "📈", None),
        ("Total Expenses (T12)", fmt_currency(exp, 0), "💸", None),
        ("Net Operating Income", fmt_currency(noi, 0), "🏦", None),
        ("NOI Margin", fmt_pct(margin * 100 if margin else None), "📊", None),
        ("Occupancy", fmt_pct(occ * 100 if occ else None) if occ else "—", "🏠",
         True if occ and occ >= 0.92 else (False if occ else None)),
        ("Budget Variance", "Upload Budget →" if not budget_data else fmt_currency(0), "📋", None),
    ]
    for col, (label, value, icon, pos) in zip(cols, kpis):
        with col:
            st.markdown(kpi_card(label, value, icon=icon), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Trend + Rev Mix ─────────────────────────────────────────────
    c1, c2 = st.columns([2, 1])

    with c1:
        st.markdown('<div class="dash-card"><div class="dash-card-title">Revenue, Expenses & NOI Trend</div>', unsafe_allow_html=True)
        md = t12_data.get("monthly_totals", {})
        mrevs = md.get("revenue", [])
        mexps = md.get("expenses", [])
        mnois = md.get("noi", [])
        mdates = t12_data.get("month_dates", [])
        labels = [fmt_month_label(d) for d in mdates]
        if mrevs and any(v != 0 for v in mrevs):
            st.plotly_chart(
                revenue_expense_noi_trend(labels, mrevs, mexps, mnois),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("Monthly data not available.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="dash-card"><div class="dash-card-title">Revenue Mix (T12)</div>', unsafe_allow_html=True)
        rev_mix = t12_data.get("revenue_mix", {})
        if rev_mix:
            total_rev_mix = sum(rev_mix.values())
            st.plotly_chart(
                revenue_mix_donut(
                    list(rev_mix.keys()), list(rev_mix.values()),
                    "Total Revenue", fmt_currency(total_rev_mix),
                ),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("Revenue mix data not available.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Row 2: Expense Mix + T-Period + NOI Margin + NOI Bridge ───────────
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown('<div class="dash-card"><div class="dash-card-title">Expense Mix (T12)</div>', unsafe_allow_html=True)
        exp_mix = t12_data.get("expense_mix", {})
        if exp_mix:
            total_exp_mix = sum(exp_mix.values())
            st.plotly_chart(
                expense_mix_donut(
                    list(exp_mix.keys()), list(exp_mix.values()),
                    "Total Expenses", fmt_currency(total_exp_mix),
                    height=280,
                ),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("No expense data.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="dash-card"><div class="dash-card-title">T12 / T6 / T3 / Current</div>', unsafe_allow_html=True)
        periods = ["T12", "T6", "T3", "Current"]
        noi_vals = [
            s.get("noi_t12"), s.get("noi_t6"), s.get("noi_t3"), s.get("noi_t1")
        ]
        marg_vals = []
        for p_rev, p_exp in [
            (s.get("total_revenue_t12"), s.get("total_expenses_t12")),
            (s.get("total_revenue_t6"),  s.get("total_expenses_t6")),
            (s.get("total_revenue_t3"),  s.get("total_expenses_t3")),
            (s.get("total_revenue_t1"),  s.get("total_expenses_t1")),
        ]:
            if p_rev and p_rev != 0 and s.get("noi_t12"):
                noi_p = None
                if p_rev and p_exp:
                    noi_p_val = p_rev - p_exp
                    marg_vals.append(noi_p_val / p_rev)
                else:
                    marg_vals.append(None)
            else:
                marg_vals.append(None)

        st.plotly_chart(
            t_period_comparison(periods, noi_vals, marg_vals, height=280),
            use_container_width=True, config={"displayModeBar": False},
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with c3:
        st.markdown('<div class="dash-card"><div class="dash-card-title">NOI Margin Trend</div>', unsafe_allow_html=True)
        if mrevs and mnois and any(r != 0 for r in mrevs):
            margins = [n / r if r and r != 0 else None for n, r in zip(mnois, mrevs)]
            st.plotly_chart(
                noi_margin_trend(labels, margins, height=280),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("Monthly data not available.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c4:
        st.markdown('<div class="dash-card"><div class="dash-card-title">NOI Bridge (T12)</div>', unsafe_allow_html=True)
        if rev and exp and noi:
            from components.charts import noi_bridge
            st.plotly_chart(
                noi_bridge(rev, exp, noi, height=280),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("NOI bridge data not available.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 3: Budget Variance Watchlist ───────────────────────────────────
    if budget_data:
        st.markdown('<div class="dash-card"><div class="dash-card-title">Budget Variance Watchlist</div>', unsafe_allow_html=True)
        _render_budget_table(budget_data)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Row 4: Financial Statement Table ──────────────────────────────────
    st.markdown('<div class="dash-card"><div class="dash-card-title">Financial Statement (T12)</div>', unsafe_allow_html=True)
    _render_financial_statement(t12_data, budget_data)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_empty_state():
    st.markdown("""
    <div class="dash-card" style="text-align:center; padding:60px 20px;">
        <div style="font-size:48px; margin-bottom:16px;">📊</div>
        <h3 style="color:#F0F4FF; margin-bottom:8px;">No T12 Data Uploaded</h3>
        <p style="color:#8BA3C7;">Upload a T12 file in the Upload Center to see the Financial Dashboard.</p>
    </div>
    """, unsafe_allow_html=True)


def _render_budget_table(budget_data: dict):
    rows = budget_data.get("line_items", [])
    if not rows:
        st.info("No budget line items available.")
        return
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_financial_statement(t12_data: dict, budget_data: dict | None):
    """Build the financial statement table from T12 line items."""
    line_items = t12_data.get("line_items", [])

    # Filter to meaningful summary items (subtotals and key rollups)
    KEY_ITEMS = {
        "gross potential rents", "total effective income",
        "less: vacancy loss", "less: loss to lease", "less: concessions",
        "less: bad debt", "net rental income", "other income ops",
        "total revenue", "total income",
        "payroll", "utilities", "repairs & maintenance", "contract services",
        "marketing", "administrative", "management fee",
        "real estate taxes", "insurance", "operating expenses",
        "net operating income",
    }

    rows = []
    for li in line_items:
        item = li.get("line_item", "").strip()
        if item.lower() not in KEY_ITEMS:
            continue
        rows.append({
            "Line Item":   item,
            "T12":         fmt_currency(li.get("t12")),
            "T6":          fmt_currency(li.get("t6")),
            "T3":          fmt_currency(li.get("t3")),
            "Current Mo.": fmt_currency(li.get("t1")),
        })

    if not rows:
        # Fallback: show all non-subtotal items
        for li in line_items[:40]:
            rows.append({
                "Line Item":   li.get("line_item", ""),
                "T12":         fmt_currency(li.get("t12")),
                "T6":          fmt_currency(li.get("t6")),
                "T3":          fmt_currency(li.get("t3")),
                "Current Mo.": fmt_currency(li.get("t1")),
            })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True, height=420)
    else:
        st.info("No financial statement data available.")
