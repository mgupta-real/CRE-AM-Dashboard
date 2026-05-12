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
)
from utils.formatting import fmt_currency, fmt_pct, fmt_date, fmt_number


BUCKET_ORDER = ["0–3 Months", "3–6 Months", "6–12 Months", "1–2 Years", "2–3 Years", "3+ Years", "Unknown", "Expired"]


def render(rr_data: dict | None):
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
    cols = st.columns(8)
    kpis = [
        ("Total Units",     fmt_number(total),          "🏢", None),
        ("Occupied",        fmt_number(occ_u),          "✅", True),
        ("Physical Occ.",   fmt_pct(occ_p * 100),       "📊", occ_p >= 0.92),
        ("Avg In-Place",    fmt_currency(avg_ip),        "💰", None),
        ("Avg Market Rent", fmt_currency(avg_mkt),       "🎯", None),
        ("Loss-to-Lease",   fmt_currency(ltl),           "📉", ltl < 0),
        ("Notice/Vacant",   fmt_number(not_u + vac_u),  "⚠",  False if (not_u+vac_u)/total > 0.08 else None),
        ("Annual Sched. Rent", fmt_currency(ann),        "📆", None),
    ]
    for col, (label, value, icon, pos) in zip(cols, kpis):
        with col:
            st.markdown(kpi_card(label, value, icon=icon), unsafe_allow_html=True)

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
            today = date.today()
            next12 = {}
            for k, v in exps.items():
                try:
                    yr, mo = int(k[:4]), int(k[5:])
                    d = date(yr, mo, 1)
                    delta = (d - today).days
                    if 0 <= delta <= 365:
                        import calendar
                        label = d.strftime("%b '%y")
                        next12[label] = v
                except Exception:
                    pass
            if next12:
                st.plotly_chart(
                    lease_expiration_chart(list(next12.keys()), list(next12.values())),
                    use_container_width=True, config={"displayModeBar": False},
                )
            else:
                st.info("No upcoming expirations in next 12 months.")
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
        st.markdown('<p style="color:#8BA3C7;font-size:12px;margin-top:16px;">Delinquency data not available in current upload.<br>Upload a rent roll with balance columns to enable this chart.</p>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with c4:
        st.markdown('<div class="dash-card"><div class="dash-card-title">8. Rent Trade-Out Trend</div>', unsafe_allow_html=True)
        st.markdown('<p style="color:#8BA3C7;font-size:12px;margin-top:16px;">Prior-lease data not available.<br>This chart requires historical rent roll uploads.</p>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Upside & Vacancy Risk Watchlist ────────────────────────────────────
    st.markdown('<div class="dash-card"><div class="dash-card-title">9. Upside & Vacancy Risk Watchlist</div>', unsafe_allow_html=True)
    _render_watchlist(units)
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Full Rent Roll Table ───────────────────────────────────────────────
    st.markdown('<div class="dash-card"><div class="dash-card-title">Rent Roll Detail Table</div>', unsafe_allow_html=True)
    _render_rent_roll_table(units)
    st.markdown("</div>", unsafe_allow_html=True)


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
