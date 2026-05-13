"""
pages/rent_roll.py
Rent Roll Dashboard — powered by parsed rent roll data.
"""
import streamlit as st
import pandas as pd
import numpy as np
from components.theme import kpi_card, COLORS
from components.charts import (
    occupancy_donut, unit_mix_bar, rent_comparison_bar,
    lease_expiration_chart, expiry_buckets_bar, rent_per_sf_bar,
    delinquency_by_unit_type, ar_aging_buckets,
    lease_tradeout_chart, leased_vs_occupied_by_unit_type,
)
from utils.formatting import fmt_currency, fmt_pct, fmt_date, fmt_number


BUCKET_ORDER = ["0–3 Months", "3–6 Months", "6–12 Months", "1–2 Years", "2–3 Years", "3+ Years", "Unknown", "Expired"]


def render(rr_data: dict | None,
           box_score_data: dict | None = None,
           ar_data: dict | None = None,
           lto_data: dict | None = None):
    if rr_data is None:
        _render_empty_state()
        return
    if rr_data.get("errors"):
        for e in rr_data["errors"]:
            st.error(f"⚠ {e}")
        return

    s    = rr_data["summary"]
    mix  = rr_data.get("unit_mix", {})
    exps = rr_data.get("lease_expirations", {})
    buck = rr_data.get("expiry_buckets", {})
    units= rr_data.get("units", [])

    total  = s["total_units"]
    occ_u  = s["occupied_units"]
    vac_u  = s["vacant_units"]
    not_u  = s["notice_units"]
    mod_u  = s.get("model_admin_units", 0)
    occ_p  = s["physical_occ"]
    avg_ip = s["avg_inplace_rent"]
    avg_mkt= s["avg_market_rent"]
    ltl    = s["loss_to_lease"]
    ltl_p  = s["loss_to_lease_pct"]
    ann    = s["annual_sched_rent"]

    # ── KPI Row ────────────────────────────────────────────────────────────
    # Contextual second-line info ("delta" slot) is computed from currently
    # available data — historical comparisons activate when prior rent rolls
    # are uploaded.
    vac_pct = (vac_u / total) if total else None
    gap_per_unit = (avg_mkt - avg_ip) if (avg_mkt and avg_ip) else None
    ann_per_unit = (ann / total) if total and ann else None
    notice_vac_pct = ((not_u + vac_u) / total) if total else None
    occ_target_gap = (occ_p - 0.92) * 100 if occ_p is not None else None

    cols = st.columns(8)
    kpis = [
        ("Total Units", fmt_number(total), "🏢",
         f"Vacant: {fmt_number(vac_u)} • Notice: {fmt_number(not_u)}", None),
        ("Occupied", fmt_number(occ_u), "✅",
         f"of {fmt_number(total)} units", True),
        ("Physical Occ.", fmt_pct(occ_p), "📊",
         (f"Target: 92% • {'▲' if occ_target_gap >= 0 else '▼'} "
          f"{abs(occ_target_gap):.1f} pp" if occ_target_gap is not None else ""),
         (occ_p is not None and occ_p >= 0.92)),
        ("Avg In-Place", fmt_currency(avg_ip), "💰",
         (f"Market: {fmt_currency(avg_mkt)}" if avg_mkt else ""), None),
        ("Avg Market Rent", fmt_currency(avg_mkt), "🎯",
         (f"Gap: {fmt_currency(gap_per_unit)}" if gap_per_unit else ""), None),
        ("Loss-to-Lease", fmt_currency(ltl), "📉",
         (f"{fmt_pct(ltl_p)} of GPR" if ltl_p is not None else ""),
         (ltl is not None and ltl < 0)),
        ("Notice / Vacant", fmt_number(not_u + vac_u), "⚠",
         (f"{fmt_pct(notice_vac_pct)} of portfolio" if notice_vac_pct is not None else ""),
         (False if (notice_vac_pct is not None and notice_vac_pct > 0.08) else None)),
        ("Annual Sched. Rent", fmt_currency(ann), "📆",
         (f"≈ {fmt_currency(ann_per_unit)} / unit / yr" if ann_per_unit else ""),
         None),
    ]
    for col, (label, value, icon, delta, pos) in zip(cols, kpis):
        with col:
            st.markdown(
                kpi_card(label, value, delta=delta, delta_positive=pos, icon=icon),
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: 4 charts ────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown('<div class="dash-card"><div class="dash-card-title">1. Occupancy Status Mix</div>', unsafe_allow_html=True)
        st.plotly_chart(
            occupancy_donut(occ_u, vac_u, not_u, mod_u, total),
            use_container_width=True, config={"displayModeBar": False},
        )
        st.markdown(f'<p style="color:{COLORS["text_secondary"]};font-size:11px;text-align:center;">Physical Occupancy: <b style="color:{COLORS["text_primary"]}">{occ_p*100:.1f}%</b></p>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="dash-card"><div class="dash-card-title">2. Unit Mix by Unit Type</div>', unsafe_allow_html=True)
        if mix:
            uts = list(mix.keys())
            cnts = [mix[ut]["count"] for ut in uts]
            st.plotly_chart(
                unit_mix_bar(uts, cnts),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("No unit type data.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c3:
        st.markdown('<div class="dash-card"><div class="dash-card-title">3. In-Place vs Market Rent</div>', unsafe_allow_html=True)
        if mix:
            uts = list(mix.keys())
            inplace = [mix[ut]["avg_inplace"] for ut in uts]
            market  = [mix[ut]["avg_market"]  for ut in uts]
            st.plotly_chart(
                rent_comparison_bar(uts, inplace, market),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("No unit type data.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c4:
        st.markdown('<div class="dash-card"><div class="dash-card-title">4. Lease Expirations (Next 12 Mo.)</div>', unsafe_allow_html=True)
        if exps:
            from datetime import date
            # Show last 6 months + all future — gives full picture
            all_months = {}
            for k, v in sorted(exps.items()):
                try:
                    yr, mo = int(k[:4]), int(k[5:])
                    d = date(yr, mo, 1)
                    label = d.strftime("%b '%y")
                    all_months[label] = v
                except Exception:
                    pass
            if all_months:
                st.plotly_chart(
                    lease_expiration_chart(list(all_months.keys()), list(all_months.values())),
                    use_container_width=True, config={"displayModeBar": False},
                )
            else:
                st.info("No expiration data available.")
        else:
            st.info("No expiration data.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Row 2: 3 charts + watchlist ─────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown('<div class="dash-card"><div class="dash-card-title">5. Lease Expiry Buckets</div>', unsafe_allow_html=True)
        if buck:
            ordered_b = [b for b in BUCKET_ORDER if b in buck]
            ordered_v = [buck[b] for b in ordered_b]
            st.plotly_chart(
                expiry_buckets_bar(ordered_b, ordered_v),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("No bucket data.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="dash-card"><div class="dash-card-title">6. Avg Rent per SF by Unit Type</div>', unsafe_allow_html=True)
        if mix:
            uts   = list(mix.keys())
            rpsfs = [mix[ut].get("avg_rent_sf", 0) for ut in uts]
            st.plotly_chart(
                rent_per_sf_bar(uts, rpsfs),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("No data.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c3:
        st.markdown('<div class="dash-card"><div class="dash-card-title">7. Delinquency by Unit Type</div>', unsafe_allow_html=True)
        delinq_data = _build_delinquency_by_unit_type(ar_data, units)
        if delinq_data:
            utypes, totals, plus30 = delinq_data
            st.plotly_chart(
                delinquency_by_unit_type(utypes, totals, plus30, height=320),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.markdown(
                '<p style="color:#8BA3C7;font-size:12px;margin-top:16px;">'
                'Delinquency data not available.<br>'
                'Upload a <b>Resident Aged Receivables</b> PDF in the Upload Center '
                'to populate this chart.</p>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with c4:
        st.markdown('<div class="dash-card"><div class="dash-card-title">8. Lease Trade-Out by Lease Type</div>', unsafe_allow_html=True)
        if lto_data and lto_data.get("summary"):
            summary = lto_data["summary"]
            ltypes  = [s["lease_type"] for s in summary]
            priors  = [s["prior_lease_rent"]   or 0 for s in summary]
            currs   = [s["current_lease_rent"] or 0 for s in summary]
            chg_pct = [s["lease_rent_change_pct"] for s in summary]
            st.plotly_chart(
                lease_tradeout_chart(ltypes, priors, currs, chg_pct, height=320),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.markdown(
                '<p style="color:#8BA3C7;font-size:12px;margin-top:16px;">'
                'Prior-lease data not available.<br>'
                'Upload a <b>Lease Trade-Out</b> Excel file in the Upload Center '
                'to populate this chart.</p>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Upside & Vacancy Risk Watchlist ────────────────────────────────────
    st.markdown('<div class="dash-card"><div class="dash-card-title">9. Upside & Vacancy Risk Watchlist</div>', unsafe_allow_html=True)
    _render_watchlist(units)
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Box Score section (only if data uploaded) ──────────────────────────
    if box_score_data:
        _render_box_score_section(box_score_data)

    # ── Aged Receivables detail (only if data uploaded) ────────────────────
    if ar_data:
        _render_ar_section(ar_data)

    # ── Lease Trade-Out detail (only if data uploaded) ─────────────────────
    if lto_data:
        _render_lto_section(lto_data)

    # ── Full Rent Roll Table ───────────────────────────────────────────────
    st.markdown('<div class="dash-card"><div class="dash-card-title">Rent Roll Detail Table</div>', unsafe_allow_html=True)
    _render_rent_roll_table(units)
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Analyst Notes (rules-based narrative) ──────────────────────────────
    from services.insights_rules import load_config, evaluate_rent_roll, sort_findings
    from components.narrative import render_narrative
    config = load_config()
    findings = sort_findings(evaluate_rent_roll(
        rr_data, box_score_data, ar_data, lto_data, config
    ))
    render_narrative(
        findings,
        title="Analyst Notes — Rent Roll & Operations",
        empty_message="Once a rent roll is uploaded, operational flags appear here. "
                      "Upload a Box Score, Aged Receivables, or Lease Trade-Out file to enrich the analysis.",
    )


def _render_watchlist(units: list):
    """Show top upside / vacant units."""
    watchlist = []
    for u in units:
        if u["status"] in ("Vacant", "Notice") or (u.get("delta_amt") and u["delta_amt"] > 100):
            watchlist.append({
                "Unit":        u["unit_no"],
                "Type":        u["unit_type"],
                "Status":      u["status"],
                "In-Place Rent": fmt_currency(u.get("effective_rent")),
                "Market Rent": fmt_currency(u.get("market_rent")),
                "Upside $":    fmt_currency(u.get("delta_amt")),
                "Upside %":    fmt_pct(u.get("delta_pct")),
            })

    watchlist.sort(key=lambda x: float(x["Upside $"].replace("$", "").replace(",", "").replace("—", "0") or 0), reverse=True)

    if watchlist:
        df = pd.DataFrame(watchlist[:20])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No units flagged for watchlist at this time.")


def _render_rent_roll_table(units: list):
    if not units:
        st.info("No unit data.")
        return

    rows = []
    for u in units:
        status = u["status"]
        status_icon = "🟢" if status == "Occupied" else ("🔴" if status == "Vacant" else "🟡")
        rows.append({
            "Unit":           u["unit_no"],
            "Type":           u["unit_type"],
            "Status":         f"{status_icon} {status}",
            "Lease End":      fmt_date(u.get("lease_end")),
            "In-Place Rent":  fmt_currency(u.get("effective_rent")),
            "Market Rent":    fmt_currency(u.get("market_rent")),
            "Delta $":        fmt_currency(u.get("delta_amt")),
            "Delta %":        fmt_pct(u.get("delta_pct")),
            "Sq Ft":          fmt_number(u.get("unit_size_sf")),
            "Rent/SF":        f"${u['rent_per_sf']:.2f}" if u.get("rent_per_sf") else "—",
            "Move-In":        fmt_date(u.get("move_in_date")),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True, height=500)
    st.markdown(f'<p style="color:#8BA3C7;font-size:11px;margin-top:4px;">Showing {len(rows)} units</p>', unsafe_allow_html=True)


def _render_empty_state():
    st.markdown("""
    <div class="dash-card" style="text-align:center; padding:60px 20px;">
        <div style="font-size:48px; margin-bottom:16px;">🏠</div>
        <h3 style="color:#F0F4FF; margin-bottom:8px;">No Rent Roll Uploaded</h3>
        <p style="color:#8BA3C7;">Upload a standardized rent roll file in the Upload Center.</p>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────
# Helpers for operational data sections
# ─────────────────────────────────────────────────────────────────────────
def _build_delinquency_by_unit_type(ar_data: dict | None, units: list) -> tuple | None:
    """
    Join Aged Receivables data to Rent Roll on Bldg-Unit, then aggregate by
    unit type. Returns (unit_types, total_balances, plus30_balances) or None.
    """
    if not ar_data or not ar_data.get("items"):
        return None

    # Build unit_no → unit_type lookup from rent roll
    # The rent roll's "unit_no" is the right-hand part of Aged Receivables' bldg_unit
    # (e.g., AR "1-0102" → RR unit_no "0102" or "1-0102" depending on dataset).
    unit_type_by_no: dict[str, str] = {}
    for u in units:
        uno = (u.get("unit_no") or "").strip()
        if uno:
            unit_type_by_no[uno] = u.get("unit_type") or "Unknown"
            # Also store the second-component variant (after dash) for tolerant matching
            if "-" in uno:
                unit_type_by_no[uno.split("-", 1)[1]] = u.get("unit_type") or "Unknown"

    # Aggregate balances by unit type
    totals_by_type: dict[str, float] = {}
    plus30_by_type: dict[str, float] = {}
    matched = 0
    for item in ar_data["items"]:
        bldg_unit = (item.get("bldg_unit") or "").strip()
        if not bldg_unit or bldg_unit == "COLLECTIONS":
            continue
        utype = (
            unit_type_by_no.get(bldg_unit)
            or unit_type_by_no.get(bldg_unit.split("-", 1)[1] if "-" in bldg_unit else bldg_unit)
            or "Unknown"
        )
        if utype != "Unknown":
            matched += 1
        bal = item.get("balance") or 0
        plus30 = (item.get("d_31_60") or 0) + (item.get("d_61_90") or 0) + (item.get("d_90_plus") or 0)
        # Only include positive balances (debt) in the totals
        if bal > 0:
            totals_by_type[utype] = totals_by_type.get(utype, 0) + bal
        if plus30 > 0:
            plus30_by_type[utype] = plus30_by_type.get(utype, 0) + plus30

    if not totals_by_type:
        return None

    # Sort by total balance descending
    utypes = sorted(totals_by_type.keys(), key=lambda k: totals_by_type[k], reverse=True)
    totals = [totals_by_type[k] for k in utypes]
    plus30 = [plus30_by_type.get(k, 0) for k in utypes]
    return utypes, totals, plus30


def _render_box_score_section(bd: dict):
    """Render Box Score availability + property pulse + make-ready snapshot."""
    st.markdown(
        f'<div class="dash-card"><div class="dash-card-title">'
        f'📦 Box Score — {bd.get("period", "")}</div>',
        unsafe_allow_html=True,
    )

    # KPI strip: pulse highlights
    pt = bd.get("property_pulse_total") or {}
    at = bd.get("availability_total") or {}
    if pt or at:
        cols = st.columns(6)
        kpis = [
            ("Move-Ins",   fmt_number(pt.get("move_ins", 0)),     "📥"),
            ("Move-Outs",  fmt_number(pt.get("move_outs", 0)),    "📤"),
            ("Net Change", _fmt_net(pt),                          "📊"),
            ("Notices",    fmt_number(pt.get("notices", 0)),      "⚠"),
            ("Renewals",   fmt_number(pt.get("renewal_offers_completed", 0)), "🔄"),
            ("Exposure",   fmt_pct(at.get("exposure")),           "🎯"),
        ]
        for col, (label, val, icon) in zip(cols, kpis):
            with col:
                st.markdown(
                    kpi_card(label, val, icon=icon),
                    unsafe_allow_html=True,
                )

    # Availability chart + Property Pulse table side-by-side
    c1, c2 = st.columns([1.2, 1])
    with c1:
        avail = bd.get("availability") or []
        if avail:
            utypes = [a["unit_type"] for a in avail]
            occ = [(a.get("occupied_no_notice") or 0) for a in avail]
            noti= [(a.get("notice") or 0) for a in avail]
            vac = [(a.get("vacant") or 0) for a in avail]
            st.markdown(
                '<p style="color:#8BA3C7;font-size:12px;margin-bottom:6px;">'
                'Leased vs Occupied by Unit Type</p>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(
                leased_vs_occupied_by_unit_type(utypes, occ, noti, vac, height=300),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("No availability data parsed.")

    with c2:
        pulse = bd.get("property_pulse") or []
        if pulse:
            df = pd.DataFrame([{
                "Unit Type":  p["unit_type"],
                "Move-Ins":   int(p.get("move_ins")   or 0),
                "Move-Outs":  int(p.get("move_outs")  or 0),
                "Notices":    int(p.get("notices")    or 0),
                "Skips":      int(p.get("skips")      or 0),
                "Evictions":  int(p.get("evictions")  or 0),
                "Leased":     int(p.get("leased")     or 0),
            } for p in pulse])
            st.markdown(
                '<p style="color:#8BA3C7;font-size:12px;margin-bottom:6px;">'
                'Property Pulse (this period)</p>',
                unsafe_allow_html=True,
            )
            st.dataframe(df, use_container_width=True, hide_index=True)

    # Make-ready strip
    mr = bd.get("make_ready") or []
    if mr:
        st.markdown(
            '<p style="color:#8BA3C7;font-size:12px;margin-top:8px;margin-bottom:6px;">'
            'Make Ready Status</p>',
            unsafe_allow_html=True,
        )
        df = pd.DataFrame([{
            "Status":           m["status"],
            "Vacant Rented":    int(m.get("vacant_rented")   or 0),
            "Vacant Unrented":  int(m.get("vacant_unrented") or 0),
            "Total":            int(m.get("total")           or 0),
            "% of Vacant":      fmt_pct(m.get("pct")),
        } for m in mr])
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("</div>", unsafe_allow_html=True)


def _fmt_net(pulse_total: dict) -> str:
    mi = pulse_total.get("move_ins") or 0
    mo = pulse_total.get("move_outs") or 0
    net = mi - mo
    return f"{'+' if net >= 0 else ''}{int(net)}"


def _render_ar_section(ar: dict):
    """Render Aged Receivables totals + aging bucket chart + delinquent residents table."""
    t = ar.get("totals", {}) or {}

    st.markdown(
        f'<div class="dash-card"><div class="dash-card-title">'
        f'💵 Aged Receivables — {ar.get("period", "")}</div>',
        unsafe_allow_html=True,
    )

    # KPI strip: aging totals
    cols = st.columns(6)
    kpis = [
        ("Delinquent",    fmt_number(t.get("delinquent_count", 0)),    "🔴"),
        ("Total Owed",    fmt_currency(t.get("delinquent_balance")),   "💰"),
        ("0–30 Days",     fmt_currency(t.get("d_0_30")),               "🟢"),
        ("31–60 Days",    fmt_currency(t.get("d_31_60")),              "🟡"),
        ("61–90 Days",    fmt_currency(t.get("d_61_90")),              "🟠"),
        ("90+ Days",      fmt_currency(t.get("d_90_plus")),            "🔴"),
    ]
    for col, (label, val, icon) in zip(cols, kpis):
        with col:
            st.markdown(
                kpi_card(label, val, icon=icon),
                unsafe_allow_html=True,
            )

    # Aging bucket horizontal bar + delinquent residents table
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.markdown(
            '<p style="color:#8BA3C7;font-size:12px;margin-top:12px;margin-bottom:6px;">'
            'Aging Bucket Distribution</p>',
            unsafe_allow_html=True,
        )
        labels = ["0–30 Days", "31–60 Days", "61–90 Days", "90+ Days"]
        values = [
            max(0, t.get("d_0_30")   or 0),
            max(0, t.get("d_31_60")  or 0),
            max(0, t.get("d_61_90")  or 0),
            max(0, t.get("d_90_plus") or 0),
        ]
        if sum(values) > 0:
            st.plotly_chart(
                ar_aging_buckets(labels, values, height=220),
                use_container_width=True, config={"displayModeBar": False},
            )
        else:
            st.info("No outstanding balances in aging buckets.")

    with c2:
        st.markdown(
            '<p style="color:#8BA3C7;font-size:12px;margin-top:12px;margin-bottom:6px;">'
            'Top Delinquent Residents</p>',
            unsafe_allow_html=True,
        )
        delinquent = [
            it for it in ar.get("items", [])
            if (it.get("balance") or 0) > 0 and it.get("bldg_unit") != "COLLECTIONS"
        ]
        delinquent.sort(key=lambda x: x.get("balance") or 0, reverse=True)
        if delinquent:
            df = pd.DataFrame([{
                "Unit":         it["bldg_unit"],
                "Resident":     it.get("resident", ""),
                "Status":       it.get("lease_status", ""),
                "0–30":         fmt_currency(it.get("d_0_30"))   if it.get("d_0_30")   else "—",
                "31–60":        fmt_currency(it.get("d_31_60"))  if it.get("d_31_60")  else "—",
                "61–90":        fmt_currency(it.get("d_61_90"))  if it.get("d_61_90")  else "—",
                "90+":          fmt_currency(it.get("d_90_plus")) if it.get("d_90_plus") else "—",
                "Balance":      fmt_currency(it.get("balance")),
            } for it in delinquent[:15]])
            st.dataframe(df, use_container_width=True, hide_index=True, height=320)
        else:
            st.info("No delinquent residents found.")

    st.markdown("</div>", unsafe_allow_html=True)


def _render_lto_section(lto: dict):
    """Render Lease Trade-Out summary KPIs + detail table."""
    summary = lto.get("summary", []) or []
    total = lto.get("total", {}) or {}

    st.markdown(
        f'<div class="dash-card"><div class="dash-card-title">'
        f'📈 Lease Trade-Out — {lto.get("period", "")}</div>',
        unsafe_allow_html=True,
    )

    # KPI strip
    cols = st.columns(5)
    kpis = [
        ("Total Leases",
         fmt_number(total.get("leases", 0)),
         "📝"),
        ("Avg Rent Change",
         (f"{'+' if (total.get('lease_rent_change_dollar') or 0) >= 0 else ''}"
          f"{fmt_currency(total.get('lease_rent_change_dollar'))}"),
         "💵"),
        ("Avg % Change",
         (f"{(total.get('lease_rent_change_pct') or 0)*100:+.2f}%"
          if total.get('lease_rent_change_pct') is not None else "—"),
         "📊"),
        ("Renewals",
         fmt_number(next((s["leases"] for s in summary if s["lease_type"].lower() == "renewal"), 0)),
         "🔁"),
        ("New Apps",
         fmt_number(next((s["leases"] for s in summary if s["lease_type"].lower() == "application"), 0)),
         "✍"),
    ]
    for col, (label, val, icon) in zip(cols, kpis):
        with col:
            st.markdown(
                kpi_card(label, val, icon=icon),
                unsafe_allow_html=True,
            )

    # Summary table + Detail table
    if summary:
        st.markdown(
            '<p style="color:#8BA3C7;font-size:12px;margin-top:12px;margin-bottom:6px;">'
            'Summary by Lease Type</p>',
            unsafe_allow_html=True,
        )
        df = pd.DataFrame([{
            "Lease Type":      s["lease_type"],
            "Leases":          int(s.get("leases") or 0),
            "Avg SQFT":        fmt_number(s.get("avg_sqft"), 0),
            "Days Vacant":     fmt_number(s.get("avg_days_vacant"), 1),
            "Prior Rent":      fmt_currency(s.get("prior_lease_rent")),
            "Current Rent":    fmt_currency(s.get("current_lease_rent")),
            "Δ $":             fmt_currency(s.get("lease_rent_change_dollar")),
            "Δ %":             fmt_pct(s.get("lease_rent_change_pct")),
        } for s in summary])
        st.dataframe(df, use_container_width=True, hide_index=True)

    detail = lto.get("detail", []) or []
    if detail:
        st.markdown(
            '<p style="color:#8BA3C7;font-size:12px;margin-top:12px;margin-bottom:6px;">'
            'Per-Unit Detail</p>',
            unsafe_allow_html=True,
        )
        df = pd.DataFrame([{
            "Unit":       d.get("bldg_unit") or "",
            "Type":       d.get("unit_type") or "",
            "Lease Type": d.get("current_lease_type") or "",
            "Resident":   d.get("current_resident") or "",
            "Prior Rent": fmt_currency(d.get("prior_lease_rent")),
            "New Rent":   fmt_currency(d.get("current_lease_rent")),
            "Δ $":        fmt_currency(d.get("lease_rent_change_dollar")),
            "Δ %":        fmt_pct(d.get("lease_rent_change_pct")),
            "Days Vac":   fmt_number(d.get("days_vacant"), 0),
        } for d in detail])
        st.dataframe(df, use_container_width=True, hide_index=True, height=320)

    st.markdown("</div>", unsafe_allow_html=True)
