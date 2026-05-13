"""
pages/upload_center.py
Upload Center — allows uploading T12 and Rent Roll files,
parses them, and stores results in session state and SQLite.
"""
import streamlit as st
import shutil
import json
from pathlib import Path
from datetime import datetime
from config.settings import UPLOAD_DIR
from services.t12_parser import parse_t12
from services.rent_roll_parser import parse_rent_roll
from services.budget_parser import parse_budget
from services.box_score_parser import parse_box_score
from services.aged_receivables_parser import parse_aged_receivables
from services.lease_tradeout_parser import parse_lease_tradeout
from database.db import execute, fetchall


def render(client_id: int | None, property_id: int | None):
    st.markdown("## 📤 Upload Center")
    st.markdown('<p style="color:#8BA3C7;margin-top:-8px;">Upload property financial and operational files for parsing and analysis.</p>', unsafe_allow_html=True)

    if not client_id or not property_id:
        st.warning("⚠ Please select a Client and Property in the sidebar before uploading files.")
        return

    # ── T12 Upload ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 T12 Financial File")
    col1, col2 = st.columns([2, 1])
    with col1:
        t12_file = st.file_uploader(
            "Upload T12 Excel (.xlsx)",
            type=["xlsx", "xls"],
            key="t12_upload",
        )
    with col2:
        st.markdown("""
        <div class="dash-card" style="margin-top:4px;">
        <p style="color:#8BA3C7;font-size:12px;margin:0;">
        <b style="color:#F0F4FF;">Expected format:</b><br>
        • Sheet named "T12"<br>
        • T12 As Of Date row<br>
        • Category & Line Item columns<br>
        • Monthly columns (up to 12)<br>
        • T12/T6/T3/T1 summary columns
        </p>
        </div>
        """, unsafe_allow_html=True)

    if t12_file:
        if st.button("🔄 Parse & Load T12", key="btn_t12"):
            _process_t12(t12_file, client_id, property_id)

    # Show last upload info
    if st.session_state.get("t12_data"):
        s = st.session_state["t12_data"].get("summary", {})
        as_of = st.session_state["t12_data"].get("as_of_date")
        st.success(f"✅ T12 loaded | As of: {as_of.strftime('%b %d, %Y') if as_of else '—'} | NOI: {_fmt(s.get('noi_t12'))}")

    # ── Rent Roll Upload ───────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🏠 Rent Roll File")
    col1, col2 = st.columns([2, 1])
    with col1:
        rr_file = st.file_uploader(
            "Upload Standardized Rent Roll (.xlsx)",
            type=["xlsx", "xls"],
            key="rr_upload",
        )
    with col2:
        st.markdown("""
        <div class="dash-card" style="margin-top:4px;">
        <p style="color:#8BA3C7;font-size:12px;margin:0;">
        <b style="color:#F0F4FF;">Expected format:</b><br>
        • Sheet: "Standardized Rent Roll"<br>
        • Unit No, Unit Type, Sq Ft<br>
        • Market Rent, Effective Rent<br>
        • Lease Start, Lease End dates<br>
        • Tenant Name (VACANT for empties)
        </p>
        </div>
        """, unsafe_allow_html=True)

    if rr_file:
        if st.button("🔄 Parse & Load Rent Roll", key="btn_rr"):
            _process_rent_roll(rr_file, client_id, property_id)

    if st.session_state.get("rr_data"):
        s = st.session_state["rr_data"].get("summary", {})
        as_of = st.session_state["rr_data"].get("as_of_date")
        st.success(
            f"✅ Rent Roll loaded | {s.get('total_units',0)} units | "
            f"Occ: {s.get('physical_occ',0)*100:.1f}% | "
            f"As of: {as_of.strftime('%b %d, %Y') if as_of else '—'}"
        )

    # ── Budget Upload ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 💰 Annual Budget File")
    col1, col2 = st.columns([2, 1])
    with col1:
        budget_file = st.file_uploader(
            "Upload Budget Template (.xlsx)",
            type=["xlsx", "xls"],
            key="budget_upload",
        )
    with col2:
        st.markdown("""
        <div class="dash-card" style="margin-top:4px;">
        <p style="color:#8BA3C7;font-size:12px;margin:0;">
        <b style="color:#F0F4FF;">Expected format:</b><br>
        • Sheet named "Budget"<br>
        • "Budget As Of Date" + "Property Units"<br>
        • Category & Line Item columns<br>
        • 12 monthly columns + Annual Budget<br>
        • Download <b>Budget_Template.xlsx</b> and fill in.
        </p>
        </div>
        """, unsafe_allow_html=True)

    if budget_file:
        if st.button("🔄 Parse & Load Budget", key="btn_budget"):
            _process_budget(budget_file, client_id, property_id)

    if st.session_state.get("budget_data"):
        bs = st.session_state["budget_data"].get("summary", {})
        as_of = st.session_state["budget_data"].get("as_of_date")
        st.success(
            f"✅ Budget loaded | Annual Revenue: {_fmt(bs.get('total_revenue_t12'))} | "
            f"NOI: {_fmt(bs.get('noi_t12'))} | "
            f"Year start: {as_of.strftime('%b %Y') if as_of else '—'}"
        )

    # ── Box Score Upload ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📦 Box Score (Monthly Leasing Snapshot)")
    col1, col2 = st.columns([2, 1])
    with col1:
        box_file = st.file_uploader(
            "Upload Box Score PDF",
            type=["pdf"],
            key="boxscore_upload",
        )
    with col2:
        st.markdown("""
        <div class="dash-card" style="margin-top:4px;">
        <p style="color:#8BA3C7;font-size:12px;margin:0;">
        <b style="color:#F0F4FF;">Yardi Box Score 4.0</b><br>
        Tables parsed:<br>
        • Availability (by Unit Type)<br>
        • Property Pulse<br>
        • Make Ready Status
        </p>
        </div>
        """, unsafe_allow_html=True)

    if box_file and st.button("🔄 Parse & Load Box Score", key="btn_box"):
        _process_operational(box_file, parse_box_score, "box_score",
                             "Box Score", client_id, property_id)

    if st.session_state.get("box_score_data"):
        bd = st.session_state["box_score_data"]
        t = bd.get("availability_total")
        if t:
            st.success(
                f"✅ Box Score loaded | {t['units']:.0f} units | "
                f"Occ: {(t['occupied_pct'] or 0)*100:.1f}% | "
                f"Period: {bd.get('period', '—')}"
            )

    # ── Aged Receivables Upload ───────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 💵 Resident Aged Receivables")
    col1, col2 = st.columns([2, 1])
    with col1:
        ar_file = st.file_uploader(
            "Upload Aged Receivables PDF",
            type=["pdf"],
            key="ar_upload",
        )
    with col2:
        st.markdown("""
        <div class="dash-card" style="margin-top:4px;">
        <p style="color:#8BA3C7;font-size:12px;margin:0;">
        <b style="color:#F0F4FF;">Yardi A/R Aging 3.5</b><br>
        Parses per-unit balances by:<br>
        • 0-30 / 31-60 / 61-90 / 90+ days<br>
        • Lease status & pre-payments<br>
        Powers the Delinquency chart.
        </p>
        </div>
        """, unsafe_allow_html=True)

    if ar_file and st.button("🔄 Parse & Load Aged Receivables", key="btn_ar"):
        _process_operational(ar_file, parse_aged_receivables, "ar_data",
                             "Aged Receivables", client_id, property_id)

    if st.session_state.get("ar_data"):
        ar = st.session_state["ar_data"]
        t = ar.get("totals", {})
        st.success(
            f"✅ Aged Receivables loaded | "
            f"Delinquent: {t.get('delinquent_count', 0)} residents owing "
            f"{_fmt(t.get('delinquent_balance'))} | "
            f"Period: {ar.get('period', '—')}"
        )

    # ── Lease Trade-Out Upload ────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📈 Lease Trade-Out")
    col1, col2 = st.columns([2, 1])
    with col1:
        lto_file = st.file_uploader(
            "Upload Lease Trade-Out Excel (.xlsx)",
            type=["xlsx", "xls"],
            key="lto_upload",
        )
    with col2:
        st.markdown("""
        <div class="dash-card" style="margin-top:4px;">
        <p style="color:#8BA3C7;font-size:12px;margin:0;">
        <b style="color:#F0F4FF;">Yardi Lease Trade-out 2.2</b><br>
        Captures prior vs current rent:<br>
        • Summary by lease type<br>
        • Per-unit detail<br>
        Powers the Lease Trade-Out chart.
        </p>
        </div>
        """, unsafe_allow_html=True)

    if lto_file and st.button("🔄 Parse & Load Lease Trade-Out", key="btn_lto"):
        _process_operational(lto_file, parse_lease_tradeout, "lto_data",
                             "Lease Trade-Out", client_id, property_id)

    if st.session_state.get("lto_data"):
        lto = st.session_state["lto_data"]
        t = lto.get("total", {}) or {}
        chg_d = t.get("lease_rent_change_dollar")
        chg_p = t.get("lease_rent_change_pct")
        chg_text = (
            f"Avg rent Δ: {_fmt(chg_d)} ({chg_p*100:+.1f}%)"
            if chg_d is not None and chg_p is not None else "—"
        )
        st.success(
            f"✅ Lease Trade-Out loaded | {t.get('leases', 0):.0f} leases | "
            f"{chg_text} | Period: {lto.get('period', '—')}"
        )

    # ── Document Upload ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📁 Other Documents")
    doc_type = st.selectbox("Document Type", [
        "Budget", "Loan Document", "Appraisal", "OM", "Insurance",
        "Tax Bill", "Capex Report", "Property Report", "Other"
    ], key="doc_type_sel")
    doc_file = st.file_uploader("Upload Document", type=["pdf", "xlsx", "xls", "docx", "csv"], key="doc_upload")
    doc_notes = st.text_input("Notes (optional)", key="doc_notes")
    if doc_file and st.button("📤 Upload Document", key="btn_doc"):
        _save_document(doc_file, doc_type, doc_notes, client_id, property_id)

    # ── File History ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📋 Upload History")
    history = fetchall(
        "SELECT * FROM uploaded_files WHERE property_id=? ORDER BY upload_date DESC LIMIT 20",
        (property_id,)
    )
    if history:
        import pandas as pd
        df = pd.DataFrame(history)[["file_type","original_name","upload_date","as_of_date","notes"]]
        df.columns = ["Type","File Name","Upload Date","As-Of Date","Notes"]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No files uploaded yet for this property.")


def _process_t12(uploaded_file, client_id, property_id):
    with st.spinner("Parsing T12..."):
        save_path = Path(UPLOAD_DIR) / f"t12_{property_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
        save_path.write_bytes(uploaded_file.read())

        result = parse_t12(str(save_path))

        if result.get("errors"):
            for e in result["errors"]:
                st.error(f"Parse error: {e}")
            return

        if result.get("warnings"):
            for w in result["warnings"]:
                st.warning(f"⚠ {w}")

        st.session_state["t12_data"] = result
        st.session_state["t12_property_id"] = property_id

        # Save to DB
        as_of = result.get("as_of_date")
        file_id = execute(
            "INSERT INTO uploaded_files (client_id,property_id,file_type,original_name,stored_path,upload_date,as_of_date) VALUES (?,?,?,?,?,?,?)",
            (client_id, property_id, "t12", uploaded_file.name, str(save_path),
             datetime.now().isoformat(),
             as_of.isoformat() if as_of else None)
        )
        st.success(f"✅ T12 parsed successfully! {len(result.get('line_items', []))} line items loaded.")
        st.rerun()


def _process_budget(uploaded_file, client_id, property_id):
    with st.spinner("Parsing Budget..."):
        save_path = Path(UPLOAD_DIR) / f"budget_{property_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
        save_path.write_bytes(uploaded_file.read())

        result = parse_budget(str(save_path))

        if result.get("errors"):
            for e in result["errors"]:
                st.error(f"Parse error: {e}")
            return

        if result.get("warnings"):
            for w in result["warnings"]:
                st.warning(f"⚠ {w}")

        st.session_state["budget_data"] = result
        st.session_state["budget_property_id"] = property_id

        as_of = result.get("as_of_date")
        execute(
            "INSERT INTO uploaded_files (client_id,property_id,file_type,original_name,stored_path,upload_date,as_of_date) VALUES (?,?,?,?,?,?,?)",
            (client_id, property_id, "budget", uploaded_file.name, str(save_path),
             datetime.now().isoformat(),
             as_of.isoformat() if as_of else None)
        )
        bs = result.get("summary", {})
        st.success(
            f"✅ Budget parsed! {len(result.get('line_items', []))} line items | "
            f"Annual Revenue: {_fmt(bs.get('total_revenue_t12'))} | "
            f"NOI: {_fmt(bs.get('noi_t12'))}"
        )
        st.rerun()


def _process_rent_roll(uploaded_file, client_id, property_id):
    with st.spinner("Parsing Rent Roll..."):
        save_path = Path(UPLOAD_DIR) / f"rr_{property_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
        save_path.write_bytes(uploaded_file.read())

        result = parse_rent_roll(str(save_path))

        if result.get("errors"):
            for e in result["errors"]:
                st.error(f"Parse error: {e}")
            return

        if result.get("warnings"):
            for w in result["warnings"]:
                st.warning(f"⚠ {w}")

        st.session_state["rr_data"] = result
        st.session_state["rr_property_id"] = property_id

        s = result.get("summary", {})
        as_of = result.get("as_of_date")
        file_id = execute(
            "INSERT INTO uploaded_files (client_id,property_id,file_type,original_name,stored_path,upload_date,as_of_date) VALUES (?,?,?,?,?,?,?)",
            (client_id, property_id, "rent_roll", uploaded_file.name, str(save_path),
             datetime.now().isoformat(),
             as_of.isoformat() if as_of else None)
        )
        st.success(f"✅ Rent Roll parsed! {s.get('total_units',0)} units | {s.get('physical_occ',0)*100:.1f}% occupied.")
        st.rerun()


def _process_operational(uploaded_file, parser_fn, session_key: str,
                         file_kind: str, client_id, property_id):
    """
    Generic processor for operational reports (Box Score, Aged Receivables,
    Lease Trade-Out). Saves file → parses → stores in session_state[session_key]
    → records upload in the database.
    """
    with st.spinner(f"Parsing {file_kind}..."):
        save_path = (
            Path(UPLOAD_DIR) /
            f"{session_key}_{property_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
        )
        save_path.write_bytes(uploaded_file.read())

        try:
            result = parser_fn(str(save_path))
        except Exception as e:
            st.error(f"Parse error: {e}")
            return

        if result.get("errors"):
            for e in result["errors"]:
                st.error(f"Parse error: {e}")
            return

        for w in result.get("warnings", []):
            st.warning(f"⚠ {w}")

        st.session_state[session_key] = result
        st.session_state[f"{session_key}_property_id"] = property_id

        # Save audit row
        try:
            execute(
                "INSERT INTO uploaded_files (client_id,property_id,file_type,original_name,stored_path,upload_date,as_of_date) VALUES (?,?,?,?,?,?,?)",
                (
                    client_id, property_id, session_key,
                    uploaded_file.name, str(save_path),
                    datetime.now().isoformat(),
                    None,
                )
            )
        except Exception:
            # Non-fatal — DB write can fail in dev environments
            pass

        st.success(f"✅ {file_kind} parsed!")
        st.rerun()


def _save_document(uploaded_file, doc_type, notes, client_id, property_id):
    save_path = Path(UPLOAD_DIR) / f"doc_{property_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
    save_path.write_bytes(uploaded_file.read())
    execute(
        "INSERT INTO documents (client_id,property_id,doc_type,display_name,stored_path,notes,upload_date) VALUES (?,?,?,?,?,?,?)",
        (client_id, property_id, doc_type, uploaded_file.name, str(save_path), notes, datetime.now().isoformat())
    )
    st.success(f"✅ Document '{uploaded_file.name}' uploaded.")


def _fmt(v) -> str:
    if v is None:
        return "—"
    return f"${float(v):,.0f}"
