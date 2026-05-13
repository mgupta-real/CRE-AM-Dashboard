"""pages/portfolio_overview.py — Portfolio-level overview page."""
import streamlit as st
import pandas as pd
from database.db import fetchall
from utils.formatting import fmt_currency, fmt_pct, fmt_number
from components.theme import kpi_card, COLORS


def render(client_id: int | None):
    st.markdown("## 🏢 Portfolio Overview")

    if not client_id:
        _empty_state()
        return

    properties = fetchall("SELECT * FROM properties WHERE client_id=? AND deleted_at IS NULL", (client_id,))

    if not properties:
        st.info("No properties found for this client. Add a property in the sidebar.")
        return

    # ── Summary row ────────────────────────────────────────────────────────
    total_units = sum((p.get("total_units") or 0) for p in properties)
    cols = st.columns(4)
    with cols[0]: st.markdown(kpi_card("Total Properties", str(len(properties)), icon="🏢"), unsafe_allow_html=True)
    with cols[1]: st.markdown(kpi_card("Total Units",      fmt_number(total_units), icon="🏠"), unsafe_allow_html=True)
    with cols[2]: st.markdown(kpi_card("T12 NOI",          _get_portfolio_noi(), icon="📈"), unsafe_allow_html=True)
    with cols[3]: st.markdown(kpi_card("Avg Occupancy",    _get_portfolio_occ(), icon="📊"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Property cards ─────────────────────────────────────────────────────
    st.markdown("### Properties")
    for prop in properties:
        _render_property_card(prop)


def _render_property_card(prop: dict):
    noi  = _get_noi_for_property(prop["id"])
    occ  = _get_occ_for_property(prop["id"])
    loans = fetchall("SELECT * FROM loans WHERE property_id=?", (prop["id"],))
    loan_bal = sum((l.get("current_balance") or 0) for l in loans)

    st.markdown(f"""
    <div class="dash-card" style="margin-bottom:12px;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
                <h4 style="color:#F0F4FF;margin:0 0 4px 0;">{prop.get('name','[Property]')}</h4>
                <p style="color:#8BA3C7;font-size:12px;margin:0;">{prop.get('address','')}, {prop.get('city','')}, {prop.get('state','')}</p>
            </div>
            <div style="text-align:right;">
                <p style="color:#8BA3C7;font-size:11px;margin:0;">{prop.get('property_type','Multifamily')} | Built {prop.get('year_built','—')}</p>
                <p style="color:#8BA3C7;font-size:11px;margin:0;">{prop.get('total_units','—')} units | Class {prop.get('asset_class','—')}</p>
            </div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:14px;padding-top:14px;border-top:1px solid #1E2D4A;">
            <div>
                <p style="color:#8BA3C7;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin:0">T12 NOI</p>
                <p style="color:#F0F4FF;font-size:16px;font-weight:700;margin:4px 0 0 0">{fmt_currency(noi)}</p>
            </div>
            <div>
                <p style="color:#8BA3C7;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin:0">Occupancy</p>
                <p style="color:{'#00C48C' if occ and occ>=0.92 else '#FF4560' if occ else '#F0F4FF'};font-size:16px;font-weight:700;margin:4px 0 0 0">{fmt_pct(occ*100) if occ else '—'}</p>
            </div>
            <div>
                <p style="color:#8BA3C7;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin:0">Loan Balance</p>
                <p style="color:#F0F4FF;font-size:16px;font-weight:700;margin:4px 0 0 0">{fmt_currency(loan_bal) if loan_bal else '—'}</p>
            </div>
            <div>
                <p style="color:#8BA3C7;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin:0">Units</p>
                <p style="color:#F0F4FF;font-size:16px;font-weight:700;margin:4px 0 0 0">{prop.get('total_units','—')}</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _get_noi_for_property(property_id: int) -> float | None:
    if st.session_state.get("t12_property_id") == property_id:
        return st.session_state.get("t12_data", {}).get("summary", {}).get("noi_t12")
    return None


def _get_occ_for_property(property_id: int) -> float | None:
    if st.session_state.get("rr_property_id") == property_id:
        return st.session_state.get("rr_data", {}).get("summary", {}).get("physical_occ")
    return None


def _get_portfolio_noi() -> str:
    noi = st.session_state.get("t12_data", {}).get("summary", {}).get("noi_t12")
    return fmt_currency(noi) if noi else "—"


def _get_portfolio_occ() -> str:
    occ = st.session_state.get("rr_data", {}).get("summary", {}).get("physical_occ")
    return fmt_pct(occ) if occ else "—"


def _empty_state():
    st.markdown("""
    <div class="dash-card" style="text-align:center;padding:60px 20px;">
        <div style="font-size:48px;margin-bottom:16px;">🏢</div>
        <h3 style="color:#F0F4FF;margin-bottom:8px;">No Client Selected</h3>
        <p style="color:#8BA3C7;">Select or create a client in the sidebar to get started.</p>
    </div>
    """, unsafe_allow_html=True)
