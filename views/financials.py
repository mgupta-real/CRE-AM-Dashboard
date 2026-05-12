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
        ("NOI Margin", fmt_pct(margin) if margin else "—", "📊", None),
        ("Occupancy", fmt_pct(occ) if occ else "—", "🏠",
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
        periods  = ["T12", "T6", "T3", "Current"]
        noi_vals = [s.get("noi_t12"), s.get("noi_t6"), s.get("noi_t3"), s.get("noi_t1")]
        marg_vals = [
            (s["noi_t12"] / s["total_revenue_t12"]) if s.get("noi_t12") and s.get("total_revenue_t12") else None,
            (s["noi_t6"]  / s["total_revenue_t6"])  if s.get("noi_t6")  and s.get("total_revenue_t6")  else None,
            (s["noi_t3"]  / s["total_revenue_t3"])  if s.get("noi_t3")  and s.get("total_revenue_t3")  else None,
            (s["noi_t1"]  / s["total_revenue_t1"])  if s.get("noi_t1")  and s.get("total_revenue_t1")  else None,
        ]

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
    """
    Render a clean T12 financial statement with the key rollup rows only.
    Structure mirrors a standard multifamily operating statement.
    """
    # Build a lookup: line_item name (lower) -> first matching line item dict
    lkp = {}
    for li in t12_data.get("line_items", []):
        key = li.get("line_item", "").strip().lower()
        if key and key not in lkp:
            lkp[key] = li

    def row(label, key, indent=0, bold=False, separator=False):
        li = lkp.get(key.lower())
        prefix = "    " * indent
        return {
            "_bold": bold,
            "_sep":  separator,
            "Line Item":   prefix + label,
            "T12":         fmt_currency(li["t12"]) if li and li.get("t12") is not None else "—",
            "T6":          fmt_currency(li["t6"])  if li and li.get("t6")  is not None else "—",
            "T3":          fmt_currency(li["t3"])  if li and li.get("t3")  is not None else "—",
            "Current Mo.": fmt_currency(li["t1"])  if li and li.get("t1")  is not None else "—",
        }

    rows = [
        # ── REVENUE ──────────────────────────────────────────────────────
        row("REVENUE",                              "",                          bold=True),
        row("  Gross Potential Rent",               "gross potential rent",      indent=1),
        row("  Loss to Lease",                      "gain / loss to lease",      indent=1),
        row("  Concessions",                        "concessions",               indent=1),
        row("  Vacancy Loss",                       "vacancy loss",              indent=1),
        row("  Non-Revenue Units",                  "non revenue units",         indent=1),
        row("  Bad Debt",                           "bad debt",                  indent=1),
        row("  Net Rental Income",                  "net rental income",         indent=1, bold=True),
        row("  Other Income",                       "other income ops",          indent=1),
        row("TOTAL REVENUE",                        "total revenue",             bold=True),
        # ── EXPENSES ─────────────────────────────────────────────────────
        row("OPERATING EXPENSES",                   "",                          bold=True),
        row("  Payroll",                            "payroll",                   indent=1),
        row("  Repairs & Maintenance",              "repairs & maintenance",     indent=1),
        row("  Turnover",                           "turnover expenses",         indent=1),
        row("  Contract Services",                  "contract services",         indent=1),
        row("  Utilities",                          "utilities",                 indent=1),
        row("  Landscaping",                        "landscape maintenance contract", indent=1),
        row("  Marketing",                          "marketing",                 indent=1),
        row("  Administrative",                     "administrative",            indent=1),
        row("  Management Fees",                    "management fee",            indent=1),
        row("  Controllable Expenses",              "controllable",              indent=1, bold=True),
        row("  Real Estate Taxes",                  "real estate taxes",         indent=1),
        row("  Insurance",                          "insurance",                 indent=1),
        row("  Non-Controllable Expenses",          "non controllable",          indent=1, bold=True),
        row("TOTAL OPERATING EXPENSES",             "operating expenses",        bold=True),
        # ── NOI ───────────────────────────────────────────────────────────
        row("NET OPERATING INCOME",                 "net operating income",      bold=True),
    ]

    # Drop the empty header rows (no key match expected) but keep separators
    display_rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    df = pd.DataFrame(display_rows)

    # Apply styling
    def style_row(row_s):
        orig = rows[row_s.name]
        if orig["_bold"] or row_s["Line Item"].strip() in (
            "NET OPERATING INCOME", "TOTAL REVENUE", "TOTAL OPERATING EXPENSES"
        ):
            return ["font-weight:700; color:#F0F4FF; background-color:#0D1A2F"] * len(row_s)
        if row_s["Line Item"].strip() in ("REVENUE", "OPERATING EXPENSES"):
            return ["font-weight:600; color:#00C2FF; background-color:#0A1525; letter-spacing:.05em"] * len(row_s)
        return ["color:#C8D8F0"] * len(row_s)

    styled = df.style.apply(style_row, axis=1).set_properties(**{
        "font-size": "13px",
        "padding": "6px 12px",
    })

    st.dataframe(styled, use_container_width=True, hide_index=True, height=700)
