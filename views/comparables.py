"""pages/comparables.py — Rent Comparables module."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date
from database.db import execute, fetchall
from utils.formatting import fmt_currency, fmt_pct, fmt_date
from components.theme import COLORS


def render(property_id: int | None, rr_data: dict | None):
    st.markdown("## 📍 Rent Comparables")
    if not property_id:
        st.warning("Select a property to manage comparables.")
        return

    comps = fetchall("SELECT * FROM comparable_properties WHERE property_id=? ORDER BY distance_miles", (property_id,))

    if comps:
        _render_comp_summary(comps, property_id, rr_data)

    with st.expander("➕ Add Comparable Property", expanded=not comps):
        _add_comp_form(property_id)

    if comps:
        st.markdown("---")
        st.markdown("### Add Rent Snapshot to Existing Comp")
        comp_names = {c["id"]: f"{c['comp_name']} ({c['city']}, {c['state']})" for c in comps}
        sel_id = st.selectbox("Select Comparable", options=list(comp_names.keys()),
                               format_func=lambda x: comp_names[x], key="snap_sel")
        if sel_id:
            _add_snapshot_form(sel_id)
            _render_snapshots(sel_id)


def _render_comp_summary(comps: list, property_id: int, rr_data: dict | None):
    st.markdown('<div class="dash-card"><div class="dash-card-title">Comparable Set Summary</div>', unsafe_allow_html=True)

    rows = []
    for c in comps:
        snaps = fetchall(
            "SELECT * FROM comparable_unit_snapshots WHERE comp_property_id=? ORDER BY snapshot_date DESC LIMIT 5",
            (c["id"],)
        )
        avg_rent = None
        if snaps:
            rents = [s["avg_rent"] for s in snaps if s.get("avg_rent")]
            avg_rent = sum(rents) / len(rents) if rents else None

        rows.append({
            "Property":  c["comp_name"],
            "Address":   f"{c.get('city','')}, {c.get('state','')}",
            "Distance":  f"{c.get('distance_miles',0):.1f} mi" if c.get("distance_miles") else "—",
            "Year Built":str(c.get("year_built","—")),
            "Units":     str(c.get("units","—")),
            "Class":     c.get("property_class","—"),
            "Avg Rent":  fmt_currency(avg_rent),
            "Apts URL":  c.get("apts_url",""),
            "Status":    c.get("status","Active"),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Subject vs comp chart
    if rr_data:
        _render_subject_vs_comp_chart(comps, rr_data)

    st.markdown("</div>", unsafe_allow_html=True)


def _render_subject_vs_comp_chart(comps: list, rr_data: dict):
    """Subject average rent vs comp averages."""
    s = rr_data.get("summary", {})
    subject_avg = s.get("avg_inplace_rent", 0)

    comp_avgs = []
    comp_names = []
    for c in comps:
        snaps = fetchall(
            "SELECT avg_rent FROM comparable_unit_snapshots WHERE comp_property_id=? AND avg_rent IS NOT NULL ORDER BY snapshot_date DESC LIMIT 3",
            (c["id"],)
        )
        if snaps:
            avg = sum(s["avg_rent"] for s in snaps) / len(snaps)
            comp_avgs.append(avg)
            comp_names.append(c["comp_name"][:20])

    if not comp_avgs:
        return

    all_names = ["Subject Property"] + comp_names
    all_vals  = [subject_avg] + comp_avgs
    colors    = [COLORS["accent_teal"]] + [COLORS["accent_blue"]] * len(comp_avgs)

    fig = go.Figure(go.Bar(
        x=all_names, y=all_vals, marker_color=colors,
        text=[fmt_currency(v) for v in all_vals],
        textposition="outside",
        textfont=dict(size=11, color=COLORS["text_primary"]),
    ))
    fig.update_layout(
        title="Subject vs Comparable Average Rents",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=280, margin=dict(l=10, r=10, t=40, b=40),
        yaxis=dict(tickprefix="$", tickformat=",.0f", gridcolor=COLORS["border"]),
        xaxis=dict(tickfont=dict(size=10)),
        font=dict(color=COLORS["text_secondary"]),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _add_comp_form(property_id: int):
    col1, col2, col3 = st.columns(3)
    with col1:
        name       = st.text_input("Property Name")
        address    = st.text_input("Address")
        city       = st.text_input("City")
        state      = st.text_input("State", max_chars=2)
        zip_code   = st.text_input("ZIP Code")
    with col2:
        distance   = st.number_input("Distance (miles)", min_value=0.0, step=0.1, format="%.1f")
        year_built = st.number_input("Year Built", min_value=1900, max_value=2030, value=2000)
        units      = st.number_input("Total Units", min_value=0, step=1)
        prop_class = st.selectbox("Property Class", ["A", "A-", "B+", "B", "B-", "C+", "C"])
        asset_type = st.selectbox("Asset Type", ["Garden Style", "Mid-Rise", "High-Rise", "Townhomes", "Mixed"])
    with col3:
        apts_url   = st.text_input("Apartments.com URL")
        prop_url   = st.text_input("Property Website")
        amenities  = st.text_area("Amenities", height=60)
        notes      = st.text_area("Notes", height=60)

    if st.button("💾 Add Comparable", key="save_comp"):
        if not name:
            st.error("Property name is required.")
        else:
            execute("""
                INSERT INTO comparable_properties
                (property_id,comp_name,address,city,state,zip,distance_miles,year_built,
                 units,property_class,asset_type,amenities,apts_url,property_url,notes,
                 created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (property_id, name, address, city, state, zip_code, distance, year_built,
                  units, prop_class, asset_type, amenities, apts_url, prop_url, notes,
                  datetime.now().isoformat(), datetime.now().isoformat()))
            st.success(f"✅ '{name}' added to comp set.")
            st.rerun()


def _add_snapshot_form(comp_id: int):
    with st.expander("Add Rent Snapshot", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            unit_type  = st.text_input("Unit Type", key=f"snap_ut_{comp_id}")
            beds       = st.number_input("Bedrooms",  min_value=0, max_value=6, step=1, key=f"snap_bd_{comp_id}")
            baths      = st.number_input("Bathrooms", min_value=0.0, max_value=4.0, step=0.5, key=f"snap_ba_{comp_id}")
            sqft       = st.number_input("Sq Ft",     min_value=0.0, step=10.0, key=f"snap_sf_{comp_id}")
        with col2:
            min_rent   = st.number_input("Min Rent",  min_value=0.0, step=50.0, key=f"snap_mn_{comp_id}")
            max_rent   = st.number_input("Max Rent",  min_value=0.0, step=50.0, key=f"snap_mx_{comp_id}")
            avg_rent   = st.number_input("Avg Rent",  min_value=0.0, step=50.0, key=f"snap_av_{comp_id}")
            concs      = st.number_input("Concessions ($)", min_value=0.0, step=50.0, key=f"snap_co_{comp_id}")
        with col3:
            snap_date  = st.date_input("Snapshot Date", value=date.today(), key=f"snap_dt_{comp_id}")
            source_tp  = st.selectbox("Data Source", ["Manual", "Apartments.com", "CoStar", "Yardi Matrix", "Other"], key=f"snap_ds_{comp_id}")
            confidence = st.selectbox("Confidence", ["High", "Medium", "Low"], key=f"snap_cf_{comp_id}")
            avail_u    = st.number_input("Available Units", min_value=0, step=1, key=f"snap_au_{comp_id}")

        if st.button("💾 Save Snapshot", key=f"save_snap_{comp_id}"):
            rpsf = (avg_rent / sqft) if (avg_rent and sqft and sqft > 0) else None
            execute("""
                INSERT INTO comparable_unit_snapshots
                (comp_property_id,snapshot_date,unit_type,bedrooms,bathrooms,sq_ft,
                 min_rent,max_rent,avg_rent,concessions,available_units,rent_per_sf,
                 data_source,confidence,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (comp_id, snap_date.isoformat(), unit_type, beds, baths, sqft,
                  min_rent, max_rent, avg_rent, concs, avail_u, rpsf,
                  source_tp, confidence, datetime.now().isoformat()))
            st.success("✅ Rent snapshot saved.")
            st.rerun()


def _render_snapshots(comp_id: int):
    snaps = fetchall(
        "SELECT * FROM comparable_unit_snapshots WHERE comp_property_id=? ORDER BY snapshot_date DESC, unit_type",
        (comp_id,)
    )
    if snaps:
        st.markdown("**Rent History**")
        rows = [{
            "Date":        s.get("snapshot_date",""),
            "Unit Type":   s.get("unit_type",""),
            "Beds":        s.get("bedrooms",""),
            "Baths":       s.get("bathrooms",""),
            "Sq Ft":       s.get("sq_ft",""),
            "Min Rent":    fmt_currency(s.get("min_rent")),
            "Max Rent":    fmt_currency(s.get("max_rent")),
            "Avg Rent":    fmt_currency(s.get("avg_rent")),
            "Concessions": fmt_currency(s.get("concessions")),
            "Rent/SF":     f"${s['rent_per_sf']:.2f}" if s.get("rent_per_sf") else "—",
            "Source":      s.get("data_source",""),
            "Confidence":  s.get("confidence",""),
        } for s in snaps]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
