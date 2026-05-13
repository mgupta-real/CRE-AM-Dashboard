"""pages/documents.py — Document repository page."""
import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
from database.db import execute, fetchall
from config.settings import UPLOAD_DIR
from utils.formatting import fmt_date


DOC_TYPES = ["T12", "Rent Roll", "Budget", "Loan Document", "CapEx Report",
             "Appraisal", "OM", "Insurance", "Tax Bill", "Property Report", "Other"]

TYPE_ICONS = {
    "T12": "📊", "Rent Roll": "🏠", "Budget": "📋", "Loan Document": "🏦",
    "CapEx Report": "🔧", "Appraisal": "📐", "OM": "📄", "Insurance": "🛡",
    "Tax Bill": "🏛", "Property Report": "📝", "Other": "📁",
}


def render(client_id: int | None, property_id: int | None):
    st.markdown("## 📁 Document Repository")

    if not property_id:
        st.warning("Select a property to manage documents.")
        return

    docs = fetchall(
        "SELECT * FROM documents WHERE property_id=? AND deleted_at IS NULL ORDER BY upload_date DESC",
        (property_id,)
    )

    # ── Upload section ─────────────────────────────────────────────────────
    with st.expander("📤 Upload New Document", expanded=not docs):
        _upload_form(client_id, property_id)

    # ── Filter bar ─────────────────────────────────────────────────────────
    if docs:
        col1, col2 = st.columns([1, 3])
        with col1:
            filter_type = st.selectbox("Filter by Type", ["All"] + DOC_TYPES)

        filtered = docs if filter_type == "All" else [d for d in docs if d.get("doc_type") == filter_type]

        # ── Document cards ─────────────────────────────────────────────────
        if filtered:
            st.markdown(f"<p style='color:#8BA3C7;font-size:13px;'>{len(filtered)} document(s)</p>", unsafe_allow_html=True)

            # Group by type
            by_type: dict[str, list] = {}
            for d in filtered:
                t = d.get("doc_type") or "Other"
                by_type.setdefault(t, []).append(d)

            for dtype, ddocs in by_type.items():
                icon = TYPE_ICONS.get(dtype, "📁")
                st.markdown(f"### {icon} {dtype}")
                rows = [{
                    "Name":     d.get("display_name",""),
                    "Period":   d.get("reporting_period","—"),
                    "Uploaded": fmt_date(d.get("upload_date")),
                    "Version":  f"v{d.get('version',1)}",
                    "Notes":    d.get("notes",""),
                    "Path":     d.get("stored_path",""),
                } for d in ddocs]
                df = pd.DataFrame(rows)
                st.dataframe(
                    df[["Name","Period","Uploaded","Version","Notes"]],
                    use_container_width=True, hide_index=True,
                )
        else:
            st.info("No documents match the selected filter.")
    else:
        st.info("No documents uploaded yet. Use the form above to upload.")


def _upload_form(client_id, property_id):
    col1, col2 = st.columns(2)
    with col1:
        doc_type    = st.selectbox("Document Type", DOC_TYPES)
        display_name= st.text_input("Display Name (optional)")
        period      = st.text_input("Reporting Period (e.g. Q1 2025)")
    with col2:
        version     = st.number_input("Version", min_value=1, value=1, step=1)
        notes       = st.text_area("Notes", height=80)

    uploaded = st.file_uploader("Choose File", type=["pdf","xlsx","xls","docx","csv","png","jpg"])
    if uploaded and st.button("📤 Upload", key="doc_up_btn"):
        save_path = Path(UPLOAD_DIR) / f"doc_{property_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded.name}"
        save_path.write_bytes(uploaded.read())
        dname = display_name or uploaded.name
        execute("""
            INSERT INTO documents
            (client_id,property_id,doc_type,display_name,stored_path,
             file_size_bytes,reporting_period,notes,version,upload_date)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (client_id, property_id, doc_type, dname, str(save_path),
              save_path.stat().st_size, period, notes, version,
              datetime.now().isoformat()))
        st.success(f"✅ '{dname}' uploaded.")
        st.rerun()
