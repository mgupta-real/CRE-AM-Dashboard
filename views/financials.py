"""
views/financials.py
Financial Dashboard — powered by T12 parsed data.

Renders:
  - KPI cards with momentum deltas (T3 annualised vs T12)
  - Period toggle (MTD / YTD / T12) on the Revenue/Expenses/NOI trend
  - Actual vs Budget monthly chart
  - Revenue Mix + Expense Mix donuts
  - T12/T6/T3/Current NOI comparison
  - NOI Margin Trend, NOI Bridge
  - Budget Variance Watchlist (when budget uploaded)
  - Expanded Financial Statement (T12/T6/T3/Current/YTD/Budget/Variance/Prior/YoY)
"""
from datetime import datetime, date
import streamlit as st
import pandas as pd

from components.theme import kpi_card, COLORS
from components.charts import (
    revenue_expense_noi_trend, noi_margin_trend, t_period_comparison,
    revenue_mix_donut, expense_mix_donut, noi_bridge,
    actual_vs_budget_bar,
)
from utils.formatting import fmt_currency, fmt_pct, fmt_month_label


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────────
def render(t12_data: dict | None, rr_data: dict | None, budget_data: dict | None = None):
    if t12_data is None:
        _render_empty_state()
        return
    if t12_data.get("errors"):
        for e in t12_data["errors"]:
            st.error(f"⚠ {e}")
        return

    s = t12_data.get("summary", {})
    md = t12_data.get("monthly_totals", {})
    mrevs = md.get("revenue", []) or []
    mexps = md.get("expenses", []) or []
    mnois = md.get("noi", []) or []
    mdates = t12_data.get("month_dates", []) or []
    labels = [fmt_month_label(d) for d in mdates]

    rev_t12 = s.get("total_revenue_t12")
    exp_t12 = s.get("total_expenses_t12")
    noi_t12 = s.get("noi_t12")
    margin  = s.get("noi_margin_t12")
    occ     = rr_data["summary"]["physical_occ"] if rr_data else None

    # Deltas: T3 annualised vs T12 (current pace vs trailing-12 baseline)
    rev_delta_pct = _delta_pct(s.get("total_revenue_t3"), rev_t12, ann=4)
    exp_delta_pct = _delta_pct(s.get("total_expenses_t3"), exp_t12, ann=4)
    noi_delta_pct = _delta_pct(s.get("noi_t3"), noi_t12, ann=4)
    noi_margin_t3 = (
        s["noi_t3"] / s["total_revenue_t3"]
        if s.get("noi_t3") is not None and s.get("total_revenue_t3") not in (None, 0)
        else None
    )
    margin_delta_pp = (
        (noi_margin_t3 - margin) * 100
        if (noi_margin_t3 is not None and margin is not None)
        else None
    )

    # ── KPI Row ────────────────────────────────────────────────────────────
    cols = st.columns(6)
    kpis = [
        ("Total Revenue (T12)",  fmt_currency(rev_t12, 0), "📈",
         _delta_text(rev_delta_pct), _delta_positive(rev_delta_pct)),
        ("Total Expenses (T12)", fmt_currency(exp_t12, 0), "💸",
         _delta_text(exp_delta_pct),
         # For expenses, *down* is positive
         (None if exp_delta_pct is None else (exp_delta_pct < 0))),
        ("Net Operating Income", fmt_currency(noi_t12, 0), "🏦",
         _delta_text(noi_delta_pct), _delta_positive(noi_delta_pct)),
        ("NOI Margin", fmt_pct(margin) if margin is not None else "—", "📊",
         (f"{'▲' if margin_delta_pp > 0 else '▼'} {abs(margin_delta_pp):.1f} pp"
          if margin_delta_pp is not None else ""),
         (None if margin_delta_pp is None else margin_delta_pp > 0)),
        ("Occupancy", fmt_pct(occ) if occ is not None else "—", "🏠",
         "", (True if occ is not None and occ >= 0.92 else
              (False if occ is not None else None))),
        ("Budget Variance",
         (_format_budget_variance(_budget_variance(budget_data, rev_t12))
          if budget_data else "Upload Budget →"),
         "📋", "", _budget_variance_positive(budget_data, rev_t12)),
    ]
    for col, (label, value, icon, delta, pos) in zip(cols, kpis):
        with col:
            st.markdown(
                kpi_card(label, value, delta=delta, delta_positive=pos, icon=icon),
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Trend (with toggle) + Actual vs Budget + Revenue Mix ────────
    c1, c2, c3 = st.columns([1.4, 1.4, 1.0])

    # Trend chart with MTD/YTD/T12 period toggle
    with c1:
        st.markdown(
            '<div class="dash-card"><div class="dash-card-title">'
            'Revenue, Expenses & NOI Trend'
            '</div>',
            unsafe_allow_html=True,
        )
        period = st.radio(
            "period_select",
            ["MTD", "YTD", "T12"],
            index=2,
            horizontal=True,
            label_visibility="collapsed",
            key="fin_period_toggle",
        )
        # Slice the monthly arrays based on the selected period
        s_labels, s_revs, s_exps, s_nois = _slice_period(
            labels, mrevs, mexps, mnois, mdates, period
        )
        if s_revs and any(v not in (None, 0) for v in s_revs):
            st.plotly_chart(
                revenue_expense_noi_trend(s_labels, s_revs, s_exps, s_nois, height=300),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("Monthly data not available for this period.")
        st.markdown("</div>", unsafe_allow_html=True)

    # Actual vs Budget — uses MTD-style monthly view (always show trailing 12)
    with c2:
        st.markdown(
            '<div class="dash-card"><div class="dash-card-title">'
            'Actual vs Budget (Monthly Revenue)'
            '</div>',
            unsafe_allow_html=True,
        )
        budgets_monthly = _budget_monthly(budget_data, mdates)
        if mrevs and any(v not in (None, 0) for v in mrevs):
            st.plotly_chart(
                actual_vs_budget_bar(labels, mrevs, budgets_monthly, height=340),
                use_container_width=True, config={"displayModeBar": False},
            )
            if not budgets_monthly:
                st.markdown(
                    f'<p style="color:{COLORS["text_muted"]};font-size:11px;'
                    f'margin-top:-8px;text-align:center;">'
                    'Upload a budget file to overlay the budget line.</p>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("Monthly revenue data not available.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c3:
        st.markdown(
            '<div class="dash-card"><div class="dash-card-title">Revenue Mix (T12)</div>',
            unsafe_allow_html=True,
        )
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
        st.markdown(
            '<div class="dash-card"><div class="dash-card-title">Expense Mix (T12)</div>',
            unsafe_allow_html=True,
        )
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
        st.markdown(
            '<div class="dash-card"><div class="dash-card-title">T12 / T6 / T3 / Current</div>',
            unsafe_allow_html=True,
        )
        periods   = ["T12", "T6", "T3", "Current"]
        noi_vals  = [s.get("noi_t12"), s.get("noi_t6"), s.get("noi_t3"), s.get("noi_t1")]
        marg_vals = [
            (s["noi_t12"] / s["total_revenue_t12"]) if s.get("noi_t12") is not None and s.get("total_revenue_t12") else None,
            (s["noi_t6"]  / s["total_revenue_t6"])  if s.get("noi_t6")  is not None and s.get("total_revenue_t6")  else None,
            (s["noi_t3"]  / s["total_revenue_t3"])  if s.get("noi_t3")  is not None and s.get("total_revenue_t3")  else None,
            (s["noi_t1"]  / s["total_revenue_t1"])  if s.get("noi_t1")  is not None and s.get("total_revenue_t1")  else None,
        ]
        st.plotly_chart(
            t_period_comparison(periods, noi_vals, marg_vals, height=280),
            use_container_width=True, config={"displayModeBar": False},
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with c3:
        st.markdown(
            '<div class="dash-card"><div class="dash-card-title">NOI Margin Trend</div>',
            unsafe_allow_html=True,
        )
        if mrevs and mnois and any(r not in (None, 0) for r in mrevs):
            margins_m = [
                (n / r) if (r and r != 0 and n is not None) else None
                for n, r in zip(mnois, mrevs)
            ]
            st.plotly_chart(
                noi_margin_trend(labels, margins_m, height=280),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("Monthly data not available.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c4:
        st.markdown(
            '<div class="dash-card"><div class="dash-card-title">NOI Bridge (T12)</div>',
            unsafe_allow_html=True,
        )
        if rev_t12 and exp_t12 and noi_t12 is not None:
            st.plotly_chart(
                noi_bridge(rev_t12, exp_t12, noi_t12, height=280),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("NOI bridge data not available.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Budget Variance Watchlist (only if budget uploaded) ────────────────
    if budget_data:
        st.markdown(
            '<div class="dash-card"><div class="dash-card-title">'
            'Budget Variance Watchlist</div>',
            unsafe_allow_html=True,
        )
        _render_budget_watchlist(budget_data)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── T12 vs Budget Comparison ──────────────────────────────────────────
    # If no budget loaded, show an upload prompt; if loaded, render the full
    # comparison suite (waterfall, by-category bars, monthly trend, top
    # variances).
    _render_t12_vs_budget_section(t12_data, budget_data)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers — period slicing, deltas, budget interpolation
# ──────────────────────────────────────────────────────────────────────────────
def _slice_period(labels, revs, exps, nois, mdates, period: str):
    """Return (labels, revs, exps, nois) sliced for MTD / YTD / T12."""
    if not labels or not revs:
        return labels, revs, exps, nois
    if period == "T12":
        return labels, revs, exps, nois
    if period == "MTD":
        # Just the most recent month
        return labels[-1:], revs[-1:], exps[-1:], nois[-1:]
    if period == "YTD":
        # Months in the current calendar year (relative to the latest month date)
        if not mdates:
            return labels, revs, exps, nois
        last = mdates[-1]
        year = getattr(last, "year", None)
        if year is None:
            return labels, revs, exps, nois
        idxs = [i for i, d in enumerate(mdates) if getattr(d, "year", None) == year]
        if not idxs:
            return labels, revs, exps, nois
        return ([labels[i] for i in idxs],
                [revs[i]   for i in idxs],
                [exps[i]   for i in idxs],
                [nois[i]   for i in idxs])
    return labels, revs, exps, nois


def _delta_pct(short_period_val, t12_val, ann: int):
    """
    Return percent difference between a short period annualised and T12.
    ann=4 means the short period is T3 (×4 to annualise).
    """
    if short_period_val is None or t12_val is None or t12_val == 0:
        return None
    annualised = short_period_val * ann
    return (annualised - t12_val) / abs(t12_val)


def _delta_text(delta_pct):
    if delta_pct is None:
        return ""
    arrow = "▲" if delta_pct > 0 else ("▼" if delta_pct < 0 else "—")
    return f"vs Prior T12  {arrow} {abs(delta_pct) * 100:.1f}%"


def _delta_positive(delta_pct):
    """Generic 'higher is better' classifier — caller flips for expenses."""
    if delta_pct is None:
        return None
    return delta_pct > 0


def _budget_monthly(budget_data: dict | None, mdates: list) -> list | None:
    """
    Build a list aligned to mdates with the monthly budgeted revenue.
    Returns None if budget data is missing or doesn't include monthly revenue.

    Alignment strategy:
      1) If the budget covers the same months as the T12 (date match), align by date.
      2) Else if the budget is a complete 12-month set, align by calendar month
         (Jan budget against any Jan T12 month, regardless of year).
      3) Else fall back to even-split of annual budget across all T12 months.
    """
    if not budget_data:
        return None

    monthly = (budget_data.get("monthly_revenue")
               or budget_data.get("monthly_totals", {}).get("revenue"))
    bmonths = budget_data.get("month_dates") or []

    # Strategy 1: exact date alignment (best when budget covers the T12 window)
    if monthly and bmonths and mdates:
        bmap = {(d.year, d.month): v for d, v in zip(bmonths, monthly) if d is not None}
        aligned = [bmap.get((d.year, d.month)) for d in mdates if d is not None]
        # If at least half the months matched, use this alignment
        if sum(1 for v in aligned if v is not None) >= max(1, len(mdates) // 2):
            return aligned

    # Strategy 2: calendar-month alignment (year-agnostic, useful when budget
    # is for a different calendar year than the T12)
    if monthly and bmonths and mdates and len(monthly) == 12:
        by_month = {d.month: v for d, v in zip(bmonths, monthly) if d is not None}
        if len(by_month) == 12:
            return [by_month.get(d.month) for d in mdates if d is not None]

    # Strategy 3: even split of annual budget
    annual = (budget_data.get("annual_revenue")
              or budget_data.get("summary", {}).get("total_revenue_t12"))
    if annual and mdates:
        per_month = annual / 12
        return [per_month] * len(mdates)

    return None


def _budget_variance(budget_data: dict | None, actual_t12: float | None = None):
    """
    Total revenue variance (Actual T12 − Budget Annual Revenue).
    Positive = outperforming budget, negative = below budget.
    """
    if not budget_data:
        return None
    annual_budget = (
        budget_data.get("annual_revenue")
        or budget_data.get("summary", {}).get("total_revenue_t12")
    )
    if annual_budget is None:
        return None
    if actual_t12 is None:
        return -annual_budget   # treat as full variance vs zero actual
    return actual_t12 - annual_budget


def _format_budget_variance(v):
    if v is None:
        return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{fmt_currency(v)}"


def _budget_variance_positive(budget_data: dict | None, actual_t12: float | None):
    v = _budget_variance(budget_data, actual_t12)
    if v is None:
        return None
    return v >= 0


# ──────────────────────────────────────────────────────────────────────────────
# Empty / placeholder states
# ──────────────────────────────────────────────────────────────────────────────
def _render_empty_state():
    st.markdown("""
    <div class="dash-card" style="text-align:center; padding:60px 20px;">
        <div style="font-size:48px; margin-bottom:16px;">📊</div>
        <h3 style="color:#F0F4FF; margin-bottom:8px;">No T12 Data Uploaded</h3>
        <p style="color:#8BA3C7;">Upload a T12 file in the Upload Center to see the Financial Dashboard.</p>
    </div>
    """, unsafe_allow_html=True)


def _render_budget_watchlist(budget_data: dict):
    rows = budget_data.get("line_items", [])
    if not rows:
        st.info("No budget line items available.")
        return
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────────────────────────────────────
# T12 vs Budget Comparison Section
#
# Renders when both t12_data and budget_data are present. Falls back to a
# clear "Upload Budget" empty-state when budget is missing.
#
# Strategy: aggregate line_items by *category* (which is the same in T12 and
# Budget standardized templates), then compute variance per category. This
# works regardless of how granular the underlying line_items are.
# ──────────────────────────────────────────────────────────────────────────────
def _category_totals(data: dict, n_months: int = 12) -> dict:
    """
    Aggregate line_items by category. Skips subtotal rows so we don't
    double-count. Returns:
        {category: {t12, t6, t3, t1, monthly[12], kind: 'revenue'|'expense'|'?'}}
    """
    out = {}
    months_in_data = len(data.get("month_dates") or []) or n_months
    for li in (data.get("line_items") or []):
        if li.get("is_subtotal"):
            continue
        cat = (li.get("category") or "").strip()
        if not cat:
            continue
        entry = out.setdefault(cat, {
            "t12":     0.0, "t6": 0.0, "t3": 0.0, "t1": 0.0,
            "monthly": [0.0] * months_in_data,
            "rev_votes": 0, "exp_votes": 0,
        })
        for k in ("t12", "t6", "t3", "t1"):
            v = li.get(k)
            if v is not None:
                entry[k] += v
        for i, mv in enumerate(li.get("monthly") or []):
            if i < months_in_data and mv is not None:
                entry["monthly"][i] += mv
        # Track classification by majority vote of constituent items
        if li.get("is_revenue"):
            entry["rev_votes"] += 1
        if li.get("is_expense"):
            entry["exp_votes"] += 1

    # Decide kind by majority vote; the category name itself also breaks ties
    REV_HINTS = ("income", "rent", "fee", "revenue", "rubs", "pet", "parking",
                 "laundry", "concession", "bad debt", "vacancy", "loss to lease",
                 "month-to-month")
    EXP_HINTS = ("expense", "cost", "tax", "insurance", "utilit", "repair",
                 "maintenance", "personnel", "payroll", "administrative",
                 "advertising", "marketing", "management fee", "landscap",
                 "contract", "turnover")
    for cat, e in out.items():
        cl = cat.lower()
        if e["rev_votes"] > e["exp_votes"]:
            e["kind"] = "revenue"
        elif e["exp_votes"] > e["rev_votes"]:
            e["kind"] = "expense"
        else:
            if any(h in cl for h in EXP_HINTS):
                e["kind"] = "expense"
            elif any(h in cl for h in REV_HINTS):
                e["kind"] = "revenue"
            else:
                e["kind"] = "?"
    return out


def _render_t12_vs_budget_section(t12_data: dict, budget_data: dict | None):
    """
    Renders the comparison block at the bottom of the Financials tab. If no
    budget is loaded, shows a placeholder card prompting the user to upload.
    """
    if not budget_data:
        st.markdown(
            '<div class="dash-card" style="text-align:center;padding:40px 20px;">'
            '<div style="font-size:38px;margin-bottom:12px;">📋</div>'
            '<h3 style="color:#F0F4FF;margin-bottom:6px;">'
            'T12 vs Budget Comparison</h3>'
            '<p style="color:#8BA3C7;margin:0;">Upload a Budget file in the '
            'Upload Center to unlock variance analysis: waterfall, '
            'category-level grouped bars, monthly trend, and top variances.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # ── Step 1: Aggregate by category for both T12 and Budget ────────────
    actual_cats = _category_totals(t12_data)
    budget_cats = _category_totals(budget_data)

    t12_summary    = t12_data.get("summary", {})
    budget_summary = budget_data.get("summary", {})

    actual_rev = t12_summary.get("total_revenue_t12")  or 0
    actual_exp = t12_summary.get("total_expenses_t12") or 0
    actual_noi = t12_summary.get("noi_t12")            or 0
    budget_rev = budget_summary.get("total_revenue_t12")  or 0
    budget_exp = budget_summary.get("total_expenses_t12") or 0
    budget_noi = budget_summary.get("noi_t12")            or 0

    # ── Step 2: KPI strip — six comparison metrics ────────────────────────
    st.markdown(
        '<div class="dash-card-title" style="margin-bottom:8px;font-size:14px;">'
        '📊 T12 Actual vs Budget</div>',
        unsafe_allow_html=True,
    )

    def _var_pct(actual, budget):
        if not budget:
            return None
        return (actual - budget) / abs(budget)

    rev_var   = actual_rev - budget_rev
    exp_var   = actual_exp - budget_exp
    noi_var   = actual_noi - budget_noi
    rev_var_p = _var_pct(actual_rev, budget_rev)
    exp_var_p = _var_pct(actual_exp, budget_exp)
    noi_var_p = _var_pct(actual_noi, budget_noi)

    def _arrow(v): return "▲" if v >= 0 else "▼"
    def _signed(v): return f"+{fmt_currency(v)}" if v >= 0 else fmt_currency(v)

    cols = st.columns(6)
    kpis = [
        ("Revenue (Actual)",  fmt_currency(actual_rev), "📈",
         f"Budget: {fmt_currency(budget_rev)}", None),
        ("Revenue Variance",  _signed(rev_var), "Δ",
         (f"{_arrow(rev_var)} {abs(rev_var_p)*100:.1f}%" if rev_var_p is not None else ""),
         rev_var >= 0),
        ("Expenses (Actual)", fmt_currency(actual_exp), "💸",
         f"Budget: {fmt_currency(budget_exp)}", None),
        ("Expense Variance",  _signed(exp_var), "Δ",
         (f"{_arrow(exp_var)} {abs(exp_var_p)*100:.1f}%" if exp_var_p is not None else ""),
         # For expenses, *under-spending* (negative variance) is favorable
         exp_var <= 0),
        ("NOI (Actual)",      fmt_currency(actual_noi), "🏦",
         f"Budget: {fmt_currency(budget_noi)}", None),
        ("NOI Variance",      _signed(noi_var), "Δ",
         (f"{_arrow(noi_var)} {abs(noi_var_p)*100:.1f}%" if noi_var_p is not None else ""),
         noi_var >= 0),
    ]
    for col, (label, value, icon, delta, pos) in zip(cols, kpis):
        with col:
            st.markdown(
                kpi_card(label, value, delta=delta, delta_positive=pos, icon=icon),
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 3: Variance Waterfall + Monthly Trend ─────────────────────────
    c1, c2 = st.columns([1.2, 1])

    with c1:
        st.markdown(
            '<div class="dash-card"><div class="dash-card-title">'
            'Variance Waterfall — Budget NOI → Actual NOI</div>',
            unsafe_allow_html=True,
        )
        # Build the waterfall items by category-level variance
        favorable, unfavorable = _build_waterfall_items(actual_cats, budget_cats)
        try:
            from components.charts import variance_waterfall
            st.plotly_chart(
                variance_waterfall(budget_noi, favorable, unfavorable, actual_noi, height=400),
                use_container_width=True, config={"displayModeBar": False},
            )
        except ImportError:
            st.info("Waterfall chart unavailable.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown(
            '<div class="dash-card"><div class="dash-card-title">'
            'Monthly Trend — Actual vs Budget (Revenue)</div>',
            unsafe_allow_html=True,
        )
        from components.charts import monthly_actual_vs_budget
        # Align by calendar month
        labels, actuals_m, budgets_m = _align_monthly(
            t12_data.get("month_dates"),
            t12_data.get("monthly_totals", {}).get("revenue"),
            budget_data.get("month_dates"),
            budget_data.get("monthly_totals", {}).get("revenue"),
        )
        if actuals_m and any(v is not None for v in actuals_m):
            st.plotly_chart(
                monthly_actual_vs_budget(labels, actuals_m, budgets_m, "Revenue", height=400),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("Monthly revenue data not available.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Step 4: By-Category Comparison + Monthly NOI Trend ────────────────
    c1, c2 = st.columns([1.4, 1])

    with c1:
        st.markdown(
            '<div class="dash-card"><div class="dash-card-title">'
            'By-Category: Actual vs Budget (T12)</div>',
            unsafe_allow_html=True,
        )
        from components.charts import budget_vs_actual_categories
        # Pick the union of categories across T12 and Budget; sort by |variance|
        all_cats = set(actual_cats) | set(budget_cats)
        rows = []
        for c in all_cats:
            a = actual_cats.get(c, {}).get("t12", 0) or 0
            b = budget_cats.get(c, {}).get("t12", 0) or 0
            kind = (actual_cats.get(c) or budget_cats.get(c) or {}).get("kind", "?")
            rows.append((c, a, b, kind))
        # Filter to only categories with meaningful values
        rows = [r for r in rows if abs(r[1]) > 100 or abs(r[2]) > 100]
        # Sort by absolute T12 actual (largest first)
        rows.sort(key=lambda x: abs(x[1]) + abs(x[2]), reverse=True)
        # Show top 15
        rows = rows[:15]
        if rows:
            cats   = [r[0] for r in rows]
            acts   = [r[1] for r in rows]
            buds   = [r[2] for r in rows]
            st.plotly_chart(
                budget_vs_actual_categories(cats, acts, buds, height=520),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("No comparable categories found.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown(
            '<div class="dash-card"><div class="dash-card-title">'
            'Monthly Trend — Actual vs Budget (NOI)</div>',
            unsafe_allow_html=True,
        )
        labels, actuals_m, budgets_m = _align_monthly(
            t12_data.get("month_dates"),
            t12_data.get("monthly_totals", {}).get("noi"),
            budget_data.get("month_dates"),
            budget_data.get("monthly_totals", {}).get("noi"),
        )
        if actuals_m and any(v is not None for v in actuals_m):
            st.plotly_chart(
                monthly_actual_vs_budget(labels, actuals_m, budgets_m, "NOI", height=520),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("Monthly NOI data not available.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Step 5: Top Variances (two ranked lists) ──────────────────────────
    st.markdown(
        '<div class="dash-card"><div class="dash-card-title">'
        'Top Variances by Category</div>',
        unsafe_allow_html=True,
    )
    _render_top_variances(actual_cats, budget_cats)
    st.markdown("</div>", unsafe_allow_html=True)


def _build_waterfall_items(actual_cats: dict, budget_cats: dict):
    """
    Compute favorable / unfavorable variance contributions to NOI.
    Returns (favorable, unfavorable) lists of (label, magnitude) tuples,
    sorted by magnitude descending (largest first).
    """
    favorable: list[tuple[str, float]] = []
    unfavorable: list[tuple[str, float]] = []

    all_cats = set(actual_cats) | set(budget_cats)
    for c in all_cats:
        a = actual_cats.get(c, {}).get("t12", 0) or 0
        b = budget_cats.get(c, {}).get("t12", 0) or 0
        kind = (actual_cats.get(c) or budget_cats.get(c) or {}).get("kind", "?")
        diff = a - b
        if abs(diff) < 500:   # Skip noise — only show meaningful variances
            continue
        # For revenue: positive diff = favorable (over-performing)
        # For expense: negative diff = favorable (under-spending)
        if kind == "revenue":
            (favorable if diff > 0 else unfavorable).append((c, abs(diff)))
        elif kind == "expense":
            # Expense contribution to NOI is INVERSE: spending less is favorable.
            # diff < 0 means actual < budget = under-spend = favorable for NOI.
            (favorable if diff < 0 else unfavorable).append((c, abs(diff)))
        else:
            # Unknown kind — treat as neutral; bucket by sign
            (favorable if diff > 0 else unfavorable).append((c, abs(diff)))

    # Sort by magnitude and cap at top 5 each to keep waterfall readable
    favorable.sort(key=lambda x: -x[1])
    unfavorable.sort(key=lambda x: -x[1])
    return favorable[:5], unfavorable[:5]


def _align_monthly(t12_dates: list, t12_vals: list,
                   budget_dates: list, budget_vals: list):
    """
    Align two monthly series by calendar month. Returns
    (labels, actual_values, budget_values) where lists are co-indexed.

    If month_dates differ, we use the T12's months as the time axis and look up
    the budget value with the same (year, month) key (or fall back to month-only
    when budget covers a different year — useful for prospective budgets).
    """
    if not t12_dates or not t12_vals:
        return [], [], []
    labels = [fmt_month_label(d) for d in t12_dates]

    actuals = list(t12_vals)
    if not budget_dates or not budget_vals:
        return labels, actuals, [None] * len(actuals)

    # Try exact (year, month) match first
    bmap_full  = {(d.year, d.month): v for d, v in zip(budget_dates, budget_vals) if d}
    bmap_month = {d.month: v for d, v in zip(budget_dates, budget_vals) if d}
    aligned_full = [bmap_full.get((d.year, d.month)) for d in t12_dates if d]
    if sum(1 for v in aligned_full if v is not None) >= max(1, len(t12_dates) // 2):
        return labels, actuals, aligned_full
    # Fall back to calendar-month alignment (year-agnostic) for cross-year budgets
    aligned_month = [bmap_month.get(d.month) for d in t12_dates if d]
    return labels, actuals, aligned_month


def _render_top_variances(actual_cats: dict, budget_cats: dict):
    """Two-column ranked tables: largest favorable and largest unfavorable."""
    all_cats = set(actual_cats) | set(budget_cats)
    rows = []
    for c in all_cats:
        a = actual_cats.get(c, {}).get("t12", 0) or 0
        b = budget_cats.get(c, {}).get("t12", 0) or 0
        kind = (actual_cats.get(c) or budget_cats.get(c) or {}).get("kind", "?")
        diff = a - b
        if abs(diff) < 100:
            continue
        # NOI-impact-positive flag
        if kind == "revenue":
            noi_favorable = diff > 0
        elif kind == "expense":
            noi_favorable = diff < 0
        else:
            noi_favorable = diff > 0
        rows.append({
            "category":      c,
            "actual":        a,
            "budget":        b,
            "variance":      diff,
            "variance_pct":  (diff / abs(b)) if b else None,
            "kind":          kind,
            "noi_favorable": noi_favorable,
        })

    favorable   = sorted([r for r in rows if r["noi_favorable"]],     key=lambda r: -abs(r["variance"]))[:5]
    unfavorable = sorted([r for r in rows if not r["noi_favorable"]], key=lambda r: -abs(r["variance"]))[:5]

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            '<p style="color:#00C48C;font-weight:600;font-size:13px;margin-bottom:6px;">'
            '✓ Top 5 Favorable (NOI ↑)</p>',
            unsafe_allow_html=True,
        )
        if favorable:
            df = pd.DataFrame([{
                "Category":    r["category"],
                "Actual":      fmt_currency(r["actual"]),
                "Budget":      fmt_currency(r["budget"]),
                "Variance":    ("+" if r["variance"] >= 0 else "") + fmt_currency(r["variance"]),
                "Variance %":  fmt_pct(r["variance_pct"]) if r["variance_pct"] is not None else "—",
            } for r in favorable])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No favorable variances above $100.")

    with c2:
        st.markdown(
            '<p style="color:#FF4560;font-weight:600;font-size:13px;margin-bottom:6px;">'
            '✗ Top 5 Unfavorable (NOI ↓)</p>',
            unsafe_allow_html=True,
        )
        if unfavorable:
            df = pd.DataFrame([{
                "Category":    r["category"],
                "Actual":      fmt_currency(r["actual"]),
                "Budget":      fmt_currency(r["budget"]),
                "Variance":    ("+" if r["variance"] >= 0 else "") + fmt_currency(r["variance"]),
                "Variance %":  fmt_pct(r["variance_pct"]) if r["variance_pct"] is not None else "—",
            } for r in unfavorable])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No unfavorable variances above $100.")
