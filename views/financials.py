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
    Render T12 operating statement. Uses multiple fallback keys per row so
    it works regardless of minor naming differences across T12 templates.
    """
    line_items = t12_data.get("line_items", [])

    # Build line-item lookup (by line_item name). Keep the entry with most data
    # if duplicate names appear. Match is case-insensitive on the trimmed name.
    lkp = {}
    for li in line_items:
        key = (li.get("line_item") or "").strip().lower()
        if not key:
            continue
        existing = lkp.get(key)
        if existing is None:
            lkp[key] = li
        elif li.get("t12") is not None and existing.get("t12") is None:
            lkp[key] = li

    # Build a category index: category name (lower) -> list of non-subtotal line items
    # under it. Subtotal rows are excluded so we don't double-count when summing.
    cat_index: dict[str, list[dict]] = {}
    for li in line_items:
        cat = (li.get("category") or "").strip().lower()
        if not cat:
            continue
        if li.get("is_subtotal"):
            continue
        cat_index.setdefault(cat, []).append(li)

    COLS = ("t12", "t6", "t3", "t1")

    def find_li(*names):
        """Exact match on line_item, then substring fallback. Returns the dict or None."""
        # 1) Exact (case-insensitive) with t12 present
        for n in names:
            li = lkp.get(n.strip().lower())
            if li is not None and li.get("t12") is not None:
                return li
        # 2) Substring fallback — prefer shortest matching name
        for n in names:
            needle = n.strip().lower()
            if not needle:
                continue
            best = None
            for name_lc, li in lkp.items():
                if needle in name_lc and li.get("t12") is not None:
                    if best is None or len(name_lc) < len(best[0]):
                        best = (name_lc, li)
            if best is not None:
                return best[1]
        # 3) Exact match even if t12 is None
        for n in names:
            li = lkp.get(n.strip().lower())
            if li is not None:
                return li
        return None

    def values_from_line_item(*names):
        """Return {col: value} for the first matching line item, or None values."""
        li = find_li(*names)
        if li is None:
            return {c: None for c in COLS}
        return {c: li.get(c) for c in COLS}

    def values_sum_line_items(*names):
        """Sum across multiple specific line-item names (subtotals)."""
        out = {c: None for c in COLS}
        for n in names:
            li = find_li(n)
            if li is None:
                continue
            for c in COLS:
                v = li.get(c)
                if v is not None:
                    out[c] = (out[c] or 0) + v
        return out

    def values_sum_categories(*cats):
        """Sum all non-subtotal line items belonging to the given categories."""
        out = {c: None for c in COLS}
        for cat in cats:
            for li in cat_index.get(cat.strip().lower(), []):
                for c in COLS:
                    v = li.get(c)
                    if v is not None:
                        out[c] = (out[c] or 0) + v
        return out

    def row(label, vals=None, indent=0, bold=False):
        """Build a row from a values dict. If vals is None, all columns show '—'."""
        vals = vals or {c: None for c in COLS}
        pad = "\u00a0" * (6 * indent)
        return {
            "_bold":       bold,
            "Line Item":   pad + label,
            "T12":         fmt_currency(vals.get("t12")) if vals.get("t12") is not None else "—",
            "T6":          fmt_currency(vals.get("t6"))  if vals.get("t6")  is not None else "—",
            "T3":          fmt_currency(vals.get("t3"))  if vals.get("t3")  is not None else "—",
            "Current Mo.": fmt_currency(vals.get("t1"))  if vals.get("t1")  is not None else "—",
        }

    # Shortcuts for the three lookup strategies
    LI  = values_from_line_item     # match a single line-item name
    SL  = values_sum_line_items     # sum specific line-item names
    SC  = values_sum_categories     # sum all non-subtotal items in given categories

    rows = [
        # ── REVENUE ─────────────────────────────────────────────────────────
        row("REVENUE", bold=True),
        row("  Gross Potential Rent",
            LI("gross potential rent", "residential income"),
            indent=1),
        row("  Loss to Lease",
            LI("market loss to lease", "gain / loss to lease", "gain loss to lease", "loss to lease"),
            indent=1),
        row("  Concessions",
            LI("less rent concessions", "concessions"),
            indent=1),
        row("  Vacancy Loss",
            LI("less loss to vacancies", "vacancy loss"),
            indent=1),
        row("  Non-Revenue Units",
            LI("non revenue units", "employee concessions"),
            indent=1),
        row("  Bad Debt",
            SC("Less: Bad Debt") if cat_index.get("less: bad debt")
            else LI("bad debt"),
            indent=1),
        row("  Net Rental Income",
            LI("total net rental income", "net rental income"),
            indent=1, bold=True),
        row("  Other Income",
            SL("total ancillary prop income",
               "total accrued ancil prop income",
               "total other prop income")
            if any(find_li(n) for n in ("total ancillary prop income",
                                        "total other prop income"))
            else LI("other income ops", "other income other", "other income"),
            indent=1),
        row("TOTAL REVENUE",
            LI("total revenue", "total income"),
            bold=True),
        # ── OPERATING EXPENSES ──────────────────────────────────────────────
        row("OPERATING EXPENSES", bold=True),
        row("  Payroll",
            LI("total payroll expense", "payroll"),
            indent=1),
        row("  Repairs & Maintenance",
            LI("total repair and maint expenses", "total repair & maint expenses",
               "repairs & maintenance", "repairs and maintenance"),
            indent=1),
        row("  Turnover",
            SC("Turnover") if cat_index.get("turnover")
            else LI("turnover expenses", "turnover"),
            indent=1),
        row("  Contract Services",
            SC("Contract Services") if cat_index.get("contract services")
            else LI("contract services"),
            indent=1),
        row("  Utilities",
            LI("total utility expense", "utilities"),
            indent=1),
        row("  Landscaping",
            SC("Landscaping") if cat_index.get("landscaping")
            else LI("landscape maintenance contract", "landscaping"),
            indent=1),
        row("  Marketing",
            LI("total advertising promo", "advertising & promotion", "marketing"),
            indent=1),
        row("  Administrative",
            LI("total administrative", "administrative"),
            indent=1),
        row("  Management Fees",
            LI("total professional fees", "management fees", "management fee",
               "external management fee expense"),
            indent=1),
        row("  Controllable Expenses",
            LI("total property level expenses", "total controllable expenses",
               "controllable"),
            indent=1, bold=True),
        row("  Real Estate Taxes",
            LI("total re tax", "total real estate taxes", "real estate taxes"),
            indent=1),
        row("  Insurance",
            LI("total insurance expense", "insurance"),
            indent=1),
        row("  Non-Controllable Expenses",
            LI("total noncontrollable expenses", "total non-controllable expenses",
               "non controllable", "non-controllable"),
            indent=1, bold=True),
        row("TOTAL OPERATING EXPENSES",
            LI("total operating expenses", "operating expenses"),
            bold=True),
        # ── NOI ──────────────────────────────────────────────────────────────
        row("NET OPERATING INCOME",
            LI("net operating income/(loss)", "net operating income", "noi"),
            bold=True),
    ]

    # Render as HTML table — avoids Streamlit Styler stripping values
    html = """
    <style>
    .fin-table{width:100%;border-collapse:collapse;font-family:Inter,sans-serif;font-size:13px;}
    .fin-table th{background:#0A1525;color:#8BA3C7;font-size:11px;text-transform:uppercase;
                  letter-spacing:.06em;padding:8px 14px;text-align:left;border-bottom:2px solid #1E2D4A;}
    .fin-table th:not(:first-child){text-align:right;}
    .fin-table td{padding:8px 14px;border-bottom:1px solid #1A2540;}
    .fin-table td:not(:first-child){text-align:right;font-variant-numeric:tabular-nums;font-family:'SF Mono',monospace;}
    .row-section {background:#0A1525!important;color:#00C2FF!important;font-weight:700;
                  text-transform:uppercase;letter-spacing:.07em;font-size:11px;}
    .row-total   {background:#0D1A2F!important;color:#F0F4FF!important;font-weight:700;}
    .row-subtotal{background:#101C35!important;color:#D0E4FF!important;font-weight:600;}
    .row-normal  {background:#111827;color:#C8D8F0;}
    .row-normal:nth-child(even){background:#0F1B30;}
    </style>
    <table class="fin-table">
    <thead><tr>
      <th style="width:38%">Line Item</th>
      <th style="width:16%">T12</th>
      <th style="width:16%">T6</th>
      <th style="width:15%">T3</th>
      <th style="width:15%">Current Mo.</th>
    </tr></thead><tbody>"""

    for r in rows:
        label = r["Line Item"]
        stripped = label.strip()
        if stripped in ("REVENUE", "OPERATING EXPENSES"):
            css = "row-section"
        elif stripped in ("TOTAL REVENUE","TOTAL OPERATING EXPENSES","NET OPERATING INCOME"):
            css = "row-total"
        elif r["_bold"]:
            css = "row-subtotal"
        else:
            css = "row-normal"
        html += f"""<tr class="{css}">
          <td>{label}</td><td>{r["T12"]}</td><td>{r["T6"]}</td>
          <td>{r["T3"]}</td><td>{r["Current Mo."]}</td></tr>"""

    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)
