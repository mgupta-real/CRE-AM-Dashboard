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
         "Upload Budget →" if not budget_data else fmt_currency(_budget_variance(budget_data)),
         "📋", "", None),
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

    # ── Expanded Financial Statement Table ────────────────────────────────
    st.markdown(
        '<div class="dash-card"><div class="dash-card-title">'
        'Financial Statement (T12)</div>',
        unsafe_allow_html=True,
    )
    _render_financial_statement(t12_data, budget_data)
    st.markdown(
        '<p style="color:#8BA3C7;font-size:11px;margin-top:6px;">'
        'All values in USD. Budget / Prior-Year columns populate when a budget '
        'or prior-period T12 is uploaded.</p>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


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
    """
    if not budget_data:
        return None
    monthly = budget_data.get("monthly_revenue") or budget_data.get("monthly_totals", {}).get("revenue")
    if monthly and len(monthly) == len(mdates):
        return list(monthly)
    annual = budget_data.get("annual_revenue") or budget_data.get("total_revenue")
    if annual and mdates:
        per_month = annual / 12
        return [per_month] * len(mdates)
    return None


def _budget_variance(budget_data: dict | None):
    """Total revenue variance (Actual T12 − Budget Annual). Returns 0 if missing."""
    if not budget_data:
        return 0
    return budget_data.get("variance_total", 0) or 0


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
# Expanded Financial Statement Table
#
# Columns: Line Item | T12 | T6 | T3 | Current Mo. | YTD | Budget (YTD)
#        | Variance (YTD) | Variance % (YTD) | Prior T12 | YoY %
#
# Budget / Prior-T12 / YoY render "—" when source data is absent.
# ──────────────────────────────────────────────────────────────────────────────
def _render_financial_statement(t12_data: dict, budget_data: dict | None):
    line_items = t12_data.get("line_items", [])
    mdates = t12_data.get("month_dates", []) or []

    # Determine YTD month indices (current calendar year of as-of date)
    ytd_indices = []
    if mdates:
        last = mdates[-1]
        last_year = getattr(last, "year", None)
        if last_year is not None:
            ytd_indices = [i for i, d in enumerate(mdates)
                           if getattr(d, "year", None) == last_year]

    # ── Lookups ──────────────────────────────────────────────────────────
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

    cat_index: dict[str, list[dict]] = {}
    for li in line_items:
        cat = (li.get("category") or "").strip().lower()
        if not cat or li.get("is_subtotal"):
            continue
        cat_index.setdefault(cat, []).append(li)

    def find_li(*names):
        for n in names:
            li = lkp.get(n.strip().lower())
            if li is not None and li.get("t12") is not None:
                return li
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
        for n in names:
            li = lkp.get(n.strip().lower())
            if li is not None:
                return li
        return None

    # ── Strategies that produce {t12,t6,t3,t1,ytd} dicts ─────────────────
    def _ytd_from_monthly(monthly: list | None):
        if not monthly or not ytd_indices:
            return None
        vals = [monthly[i] for i in ytd_indices if i < len(monthly) and monthly[i] is not None]
        if not vals:
            return None
        return sum(vals)

    def vals_from_line_item(*names):
        li = find_li(*names)
        if li is None:
            return {"t12": None, "t6": None, "t3": None, "t1": None, "ytd": None}
        return {
            "t12": li.get("t12"),
            "t6":  li.get("t6"),
            "t3":  li.get("t3"),
            "t1":  li.get("t1"),
            "ytd": _ytd_from_monthly(li.get("monthly")),
        }

    def vals_sum_line_items(*names):
        out = {"t12": None, "t6": None, "t3": None, "t1": None, "ytd": None}
        for n in names:
            li = find_li(n)
            if li is None:
                continue
            for c in ("t12", "t6", "t3", "t1"):
                v = li.get(c)
                if v is not None:
                    out[c] = (out[c] or 0) + v
            ytd_v = _ytd_from_monthly(li.get("monthly"))
            if ytd_v is not None:
                out["ytd"] = (out["ytd"] or 0) + ytd_v
        return out

    def vals_sum_categories(*cats):
        out = {"t12": None, "t6": None, "t3": None, "t1": None, "ytd": None}
        for cat in cats:
            for li in cat_index.get(cat.strip().lower(), []):
                for c in ("t12", "t6", "t3", "t1"):
                    v = li.get(c)
                    if v is not None:
                        out[c] = (out[c] or 0) + v
                ytd_v = _ytd_from_monthly(li.get("monthly"))
                if ytd_v is not None:
                    out["ytd"] = (out["ytd"] or 0) + ytd_v
        return out

    # Budget lookup (per-line; budget_data is optional)
    budget_lkp = {}
    if budget_data and isinstance(budget_data.get("line_items"), list):
        for bi in budget_data["line_items"]:
            key = (bi.get("Line Item") or bi.get("line_item") or "").strip().lower()
            if key:
                budget_lkp[key] = bi

    def _budget_ytd(label: str):
        bi = budget_lkp.get(label.strip().lower())
        if not bi:
            return None
        return bi.get("ytd_budget") or bi.get("budget_ytd") or bi.get("YTD Budget")

    # Prior-T12 lookup (when historical data is available — currently absent)
    prior_lkp = {}
    prior_data = t12_data.get("prior_t12") or {}
    if isinstance(prior_data.get("line_items"), list):
        for pi in prior_data["line_items"]:
            key = (pi.get("line_item") or "").strip().lower()
            if key:
                prior_lkp[key] = pi

    def _prior_t12(label: str, alt_keys: list | None = None):
        candidates = [label, *(alt_keys or [])]
        for k in candidates:
            pi = prior_lkp.get(k.strip().lower())
            if pi and pi.get("t12") is not None:
                return pi["t12"]
        return None

    # ── Row builder ──────────────────────────────────────────────────────
    def row(label, vals=None, *, indent=0, bold=False, budget_label=None,
            prior_keys=None):
        vals = vals or {"t12": None, "t6": None, "t3": None, "t1": None, "ytd": None}
        pad = "\u00a0" * (6 * indent)
        budget_ytd = _budget_ytd(budget_label) if budget_label else None
        prior = _prior_t12(prior_keys[0], prior_keys[1:]) if prior_keys else None

        variance_ytd = (
            vals["ytd"] - budget_ytd
            if (vals["ytd"] is not None and budget_ytd is not None)
            else None
        )
        variance_pct = (
            (variance_ytd / abs(budget_ytd))
            if (variance_ytd is not None and budget_ytd not in (None, 0))
            else None
        )
        yoy = (
            (vals["t12"] - prior) / abs(prior)
            if (vals["t12"] is not None and prior not in (None, 0))
            else None
        )

        return {
            "_bold":  bold,
            "_label": pad + label,
            "t12":     vals["t12"],
            "t6":      vals["t6"],
            "t3":      vals["t3"],
            "t1":      vals["t1"],
            "ytd":     vals["ytd"],
            "bud_ytd": budget_ytd,
            "var_ytd": variance_ytd,
            "var_pct": variance_pct,
            "prior":   prior,
            "yoy":     yoy,
        }

    LI = vals_from_line_item
    SL = vals_sum_line_items
    SC = vals_sum_categories

    # The labels match what the parser stores in `line_item` for typical
    # multifamily T12 exports (e.g. "GROSS POTENTIAL RENT", "TOTAL REVENUE").
    # `prior_keys` and `budget_label` are also provided so that, when those
    # data sources are eventually wired in, the columns light up automatically.
    rows_data = [
        # ── REVENUE ─────────────────────────────────────────────────────
        row("REVENUE", bold=True),
        row("  Gross Potential Rent",
            LI("gross potential rent", "residential income"),
            indent=1,
            budget_label="Gross Potential Rent",
            prior_keys=["gross potential rent"]),
        row("  Loss to Lease",
            LI("market loss to lease", "gain / loss to lease",
               "gain loss to lease", "loss to lease"),
            indent=1,
            budget_label="Loss to Lease",
            prior_keys=["market loss to lease", "loss to lease"]),
        row("  Concessions",
            LI("less rent concessions", "concessions"),
            indent=1,
            budget_label="Concessions",
            prior_keys=["less rent concessions", "concessions"]),
        row("  Vacancy Loss",
            LI("less loss to vacancies", "vacancy loss"),
            indent=1,
            budget_label="Vacancy Loss",
            prior_keys=["less loss to vacancies", "vacancy loss"]),
        row("  Non-Revenue Units",
            LI("non revenue units", "employee concessions"),
            indent=1,
            budget_label="Non-Revenue Units"),
        row("  Bad Debt",
            (SC("Less: Bad Debt") if cat_index.get("less: bad debt")
             else LI("bad debt")),
            indent=1,
            budget_label="Bad Debt",
            prior_keys=["bad debt"]),
        row("  Net Rental Income",
            LI("total net rental income", "net rental income"),
            indent=1, bold=True,
            budget_label="Net Rental Income",
            prior_keys=["total net rental income", "net rental income"]),
        row("  Other Income",
            (SL("total ancillary prop income",
                "total accrued ancil prop income",
                "total other prop income")
             if any(find_li(n) for n in ("total ancillary prop income",
                                         "total other prop income"))
             else LI("other income ops", "other income other", "other income")),
            indent=1,
            budget_label="Other Income"),
        row("TOTAL REVENUE",
            LI("total revenue", "total income"),
            bold=True,
            budget_label="Total Revenue",
            prior_keys=["total revenue", "total income"]),

        # ── OPERATING EXPENSES ──────────────────────────────────────────
        row("OPERATING EXPENSES", bold=True),
        row("  Payroll",
            LI("total payroll expense", "payroll"),
            indent=1,
            budget_label="Payroll",
            prior_keys=["total payroll expense", "payroll"]),
        row("  Repairs & Maintenance",
            LI("total repair and maint expenses", "total repair & maint expenses",
               "repairs & maintenance", "repairs and maintenance"),
            indent=1,
            budget_label="Repairs & Maintenance",
            prior_keys=["total repair and maint expenses"]),
        row("  Turnover",
            (SC("Turnover") if cat_index.get("turnover")
             else LI("turnover expenses", "turnover")),
            indent=1,
            budget_label="Turnover"),
        row("  Contract Services",
            (SC("Contract Services") if cat_index.get("contract services")
             else LI("contract services")),
            indent=1,
            budget_label="Contract Services"),
        row("  Utilities",
            LI("total utility expense", "utilities"),
            indent=1,
            budget_label="Utilities",
            prior_keys=["total utility expense"]),
        row("  Landscaping",
            (SC("Landscaping") if cat_index.get("landscaping")
             else LI("landscape maintenance contract", "landscaping")),
            indent=1,
            budget_label="Landscaping"),
        row("  Marketing",
            LI("total advertising promo", "advertising & promotion", "marketing"),
            indent=1,
            budget_label="Marketing"),
        row("  Administrative",
            LI("total administrative", "administrative"),
            indent=1,
            budget_label="Administrative"),
        row("  Management Fees",
            LI("total professional fees", "management fees", "management fee",
               "external management fee expense"),
            indent=1,
            budget_label="Management Fees"),
        row("  Controllable Expenses",
            LI("total property level expenses", "total controllable expenses",
               "controllable"),
            indent=1, bold=True,
            budget_label="Controllable Expenses"),
        row("  Real Estate Taxes",
            LI("total re tax", "total real estate taxes", "real estate taxes"),
            indent=1,
            budget_label="Real Estate Taxes"),
        row("  Insurance",
            LI("total insurance expense", "insurance"),
            indent=1,
            budget_label="Insurance"),
        row("  Non-Controllable Expenses",
            LI("total noncontrollable expenses", "total non-controllable expenses",
               "non controllable", "non-controllable"),
            indent=1, bold=True,
            budget_label="Non-Controllable Expenses"),
        row("TOTAL OPERATING EXPENSES",
            LI("total operating expenses", "operating expenses"),
            bold=True,
            budget_label="Total Operating Expenses",
            prior_keys=["total operating expenses"]),

        # ── NOI ──────────────────────────────────────────────────────────
        row("NET OPERATING INCOME",
            LI("net operating income/(loss)", "net operating income", "noi"),
            bold=True,
            budget_label="Net Operating Income",
            prior_keys=["net operating income/(loss)", "net operating income"]),
    ]

    _render_statement_html(rows_data)


def _render_statement_html(rows_data: list):
    """
    Render the financial statement as an HTML table with color-coded
    Variance / YoY cells, matching the reference design.
    """
    css = """
    <style>
    .fin-tbl-wrap { overflow-x:auto; }
    .fin-tbl { width:100%; min-width:1100px; border-collapse:collapse;
               font-family:Inter,sans-serif; font-size:12.5px; }
    .fin-tbl th { background:#0A1525; color:#8BA3C7; font-size:10.5px;
                  text-transform:uppercase; letter-spacing:.06em;
                  padding:9px 10px; text-align:right;
                  border-bottom:1px solid #1E2D4A; white-space:nowrap; }
    .fin-tbl th:first-child { text-align:left; }
    .fin-tbl td { padding:7px 10px; border-bottom:1px solid #1A2540;
                  white-space:nowrap; }
    .fin-tbl td:not(:first-child) { text-align:right;
                                    font-variant-numeric:tabular-nums;
                                    font-family:'SF Mono',monospace; }
    .row-header   { background:#0A1525 !important; color:#00C2FF !important;
                    font-weight:700; text-transform:uppercase;
                    letter-spacing:.06em; font-size:11.5px; }
    .row-total    { background:#0D1A2F !important; color:#F0F4FF !important;
                    font-weight:700; font-size:13px; }
    .row-subtotal { background:#0D1A2F !important; color:#E0ECFF !important;
                    font-weight:600; }
    .row-normal   { color:#C8D8F0; }
    .row-normal:nth-child(even) { background:#0F1B30; }
    .pos { color:#00C48C; }
    .neg { color:#FF4560; }
    .muted { color:#4A6080; }
    </style>
    """

    head = """
    <div class="fin-tbl-wrap"><table class="fin-tbl">
    <thead><tr>
      <th style="width:22%">Line Item</th>
      <th>T12</th>
      <th>T6</th>
      <th>T3</th>
      <th>Current Mo.</th>
      <th>YTD</th>
      <th>Budget (YTD)</th>
      <th>Variance (YTD)</th>
      <th>Variance %</th>
      <th>Prior T12</th>
      <th>YoY %</th>
    </tr></thead><tbody>
    """

    body_parts = []
    for r in rows_data:
        label = r["_label"]
        stripped = label.strip()
        if stripped in ("REVENUE", "OPERATING EXPENSES"):
            css_cls = "row-header"
        elif stripped in ("TOTAL REVENUE", "TOTAL OPERATING EXPENSES",
                          "NET OPERATING INCOME"):
            css_cls = "row-total"
        elif r["_bold"]:
            css_cls = "row-subtotal"
        else:
            css_cls = "row-normal"

        # Format primary numeric columns
        def _fmtv(v):
            return fmt_currency(v) if v is not None else "—"

        var_cell = _fmtv(r["var_ytd"])
        var_cls = ""
        if r["var_ytd"] is not None:
            var_cls = "pos" if r["var_ytd"] >= 0 else "neg"

        var_pct_cell = fmt_pct(r["var_pct"]) if r["var_pct"] is not None else "—"
        var_pct_cls = ""
        if r["var_pct"] is not None:
            var_pct_cls = "pos" if r["var_pct"] >= 0 else "neg"

        yoy_cell = fmt_pct(r["yoy"]) if r["yoy"] is not None else "—"
        yoy_cls = ""
        if r["yoy"] is not None:
            yoy_cls = "pos" if r["yoy"] >= 0 else "neg"

        # Section header rows have no values — show em-dashes everywhere except label
        if css_cls == "row-header":
            body_parts.append(f"""<tr class="{css_cls}">
              <td>{label}</td>
              <td class="muted">—</td><td class="muted">—</td>
              <td class="muted">—</td><td class="muted">—</td>
              <td class="muted">—</td><td class="muted">—</td>
              <td class="muted">—</td><td class="muted">—</td>
              <td class="muted">—</td><td class="muted">—</td>
            </tr>""")
            continue

        body_parts.append(f"""<tr class="{css_cls}">
          <td>{label}</td>
          <td>{_fmtv(r['t12'])}</td>
          <td>{_fmtv(r['t6'])}</td>
          <td>{_fmtv(r['t3'])}</td>
          <td>{_fmtv(r['t1'])}</td>
          <td>{_fmtv(r['ytd'])}</td>
          <td>{_fmtv(r['bud_ytd'])}</td>
          <td class="{var_cls}">{var_cell}</td>
          <td class="{var_pct_cls}">{var_pct_cell}</td>
          <td>{_fmtv(r['prior'])}</td>
          <td class="{yoy_cls}">{yoy_cell}</td>
        </tr>""")

    foot = "</tbody></table></div>"
    st.markdown(css + head + "".join(body_parts) + foot, unsafe_allow_html=True)
