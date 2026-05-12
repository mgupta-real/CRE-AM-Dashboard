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
