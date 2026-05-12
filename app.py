"""
app.py — CRE Asset Management Dashboard
Entry point. Run with: streamlit run app.py
"""
import streamlit as st
from datetime import datetime

# ── Page config (must be FIRST Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="CRE Asset Management",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Bootstrap ─────────────────────────────────────────────────────────────────
from database.db import init_db, fetchall, fetchone, execute
init_db()

from components.theme import inject_css
inject_css()

# ── Session state defaults ────────────────────────────────────────────────────
_DEFAULTS = {
    "t12_data":          None,
    "rr_data":           None,
    "t12_property_id":   None,
    "rr_property_id":    None,
    "view_mode":         "Analyst/Admin",
    "active_page":       "Overview",
    "selected_client":   None,
    "selected_property": None,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS  — defined FIRST so they can be called anywhere below
# ═══════════════════════════════════════════════════════════════════════════════

def _render_page_header(title: str, icon: str = "", client_id=None, property_id=None):
    prop   = fetchone("SELECT * FROM properties WHERE id=?", (property_id,)) if property_id else None
    client = fetchone("SELECT * FROM clients WHERE id=?",   (client_id,))   if client_id   else None

    prop_label   = prop["name"]   if prop   else "No Property Selected"
    client_label = client["name"] if client else "No Client"
    view_badge   = "👤 Client View" if st.session_state["view_mode"] == "Client View" else "🔧 Analyst View"

    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
                border-bottom:1px solid #1E2D4A;padding-bottom:14px;margin-bottom:20px;">
        <div>
            <h2 style="color:#F0F4FF;margin:0;font-size:22px;">{icon} {title}</h2>
            <p style="color:#8BA3C7;font-size:12px;margin:4px 0 0 0;">
                {client_label} &nbsp;›&nbsp; {prop_label}
            </p>
        </div>
        <div style="text-align:right;">
            <span style="background:#162035;border:1px solid #1E2D4A;border-radius:6px;
                         padding:4px 12px;font-size:11px;color:#8BA3C7;">{view_badge}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_insights_panel(t12_data, rr_data, property_id):
    if not (t12_data or rr_data):
        return

    from services.insights_engine import generate_insights
    loans = fetchall("SELECT * FROM loans WHERE property_id=?",          (property_id,)) if property_id else []
    capex = fetchall("SELECT * FROM capex_projects WHERE property_id=?", (property_id,)) if property_id else []
    comps = fetchall("SELECT * FROM comparable_properties WHERE property_id=?", (property_id,)) if property_id else []

    insights = generate_insights(t12_data, rr_data, loans or None, capex or None, comps or None)

    if insights:
        st.markdown("---")
        st.markdown("### 💡 Asset Management Insights")
        sev_icons = {"alert": "🔴", "warning": "🟡", "info": "🔵"}
        for ins in insights:
            sev    = ins.get("severity", "info")
            icon   = sev_icons.get(sev, "🔵")
            metric = (
                f"**{ins.get('metric_label')}:** {ins.get('metric_value')}"
                if ins.get("metric_label") else ""
            )
            st.markdown(f"""
            <div class="dash-card insight-{sev}" style="margin-bottom:8px;padding:12px 16px;">
                <div style="display:flex;justify-content:space-between;align-items:start;">
                    <p style="margin:0;color:#F0F4FF;font-size:13px;">{icon} {ins.get('message','')}</p>
                    <span style="color:#8BA3C7;font-size:11px;white-space:nowrap;margin-left:12px;">{metric}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)


def _trigger_export(client_id, property_id):
    from services.excel_exporter import generate_excel
    from services.insights_engine import generate_insights

    prop   = fetchone("SELECT * FROM properties WHERE id=?", (property_id,)) if property_id else None
    client = fetchone("SELECT * FROM clients WHERE id=?",   (client_id,))   if client_id   else None
    loans  = fetchall("SELECT * FROM loans WHERE property_id=?",          (property_id,)) if property_id else []
    capex  = fetchall("SELECT * FROM capex_projects WHERE property_id=?", (property_id,)) if property_id else []
    comps  = fetchall("SELECT * FROM comparable_properties WHERE property_id=?", (property_id,)) if property_id else []

    insights = generate_insights(
        st.session_state.get("t12_data"),
        st.session_state.get("rr_data"),
        loans or None, capex or None, comps or None,
    )

    excel_bytes = generate_excel(
        t12_data      = st.session_state.get("t12_data"),
        rr_data       = st.session_state.get("rr_data"),
        loans         = loans,
        capex         = capex,
        comps         = comps,
        insights      = insights,
        property_name = prop["name"]   if prop   else "Property",
        client_name   = client["name"] if client else "Client",
    )

    fname = (
        f"CRE_Dashboard_{prop['name'] if prop else 'Export'}"
        f"_{datetime.now().strftime('%Y%m%d')}.xlsx"
    )
    st.sidebar.download_button(
        label="⬇ Download Excel",
        data=excel_bytes,
        file_name=fname,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dl_btn",
    )
    st.sidebar.success("Export ready — click Download ↑")


def _render_settings():
    st.markdown("## ⚙ Settings")
    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    st.markdown("### App Info")
    st.markdown("""
    | Setting | Value |
    |---|---|
    | App Version | 1.0.0-MVP |
    | Database | SQLite (local) |
    | Auth | Not enabled (MVP) |
    """)
    st.markdown("### Adding Login / Auth Later")
    st.info("""
    **To add Supabase Auth:**
    1. Install the `supabase` Python client
    2. Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `.env`
    3. Replace `database/db.py` connection factory with the Supabase client
    4. Wrap all pages with `st.session_state['user']` checks
    5. Enable Row Level Security on Supabase tables using `client_id` and `property_id` foreign keys
    """)
    st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    # ── Logo ──────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="padding:12px 0 20px 0;border-bottom:1px solid #1E2D4A;margin-bottom:20px;">
        <p class="nav-logo">🏢 CRE <span>Asset Mgmt</span></p>
        <p style="color:#4A6080;font-size:10px;margin:2px 0 0 0;letter-spacing:.08em;">DASHBOARD v1.0</p>
    </div>
    """, unsafe_allow_html=True)

    # ── View mode toggle ──────────────────────────────────────────────────
    view_mode = st.radio(
        "View Mode",
        ["Analyst/Admin", "Client View"],
        index=0 if st.session_state["view_mode"] == "Analyst/Admin" else 1,
        key="vm_radio",
        horizontal=True,
    )
    st.session_state["view_mode"] = view_mode

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Client selector ───────────────────────────────────────────────────
    st.markdown(
        '<p style="color:#8BA3C7;font-size:11px;text-transform:uppercase;'
        'letter-spacing:.08em;margin-bottom:4px;">CLIENT</p>',
        unsafe_allow_html=True,
    )
    clients      = fetchall("SELECT * FROM clients WHERE deleted_at IS NULL ORDER BY name")
    client_names = [c["name"] for c in clients]
    client_ids   = [c["id"]   for c in clients]

    with st.expander("+ New Client", expanded=not clients):
        new_client = st.text_input("Client Name", key="new_client_name")
        if st.button("Create Client", key="btn_new_client"):
            if new_client.strip():
                cid = execute(
                    "INSERT INTO clients (name, created_at, updated_at) VALUES (?,?,?)",
                    (new_client.strip(), datetime.now().isoformat(), datetime.now().isoformat()),
                )
                st.session_state["selected_client"] = cid
                st.rerun()
            else:
                st.error("Enter a client name.")

    if clients:
        sel_client_idx = 0
        if st.session_state["selected_client"] in client_ids:
            sel_client_idx = client_ids.index(st.session_state["selected_client"])
        sel_client_name = st.selectbox("Select Client", client_names, index=sel_client_idx, key="client_sb")
        st.session_state["selected_client"] = client_ids[client_names.index(sel_client_name)]
    else:
        st.session_state["selected_client"] = None

    client_id = st.session_state["selected_client"]

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Property selector ─────────────────────────────────────────────────
    st.markdown(
        '<p style="color:#8BA3C7;font-size:11px;text-transform:uppercase;'
        'letter-spacing:.08em;margin-bottom:4px;">PROPERTY</p>',
        unsafe_allow_html=True,
    )

    properties = []
    if client_id:
        properties = fetchall(
            "SELECT * FROM properties WHERE client_id=? AND deleted_at IS NULL ORDER BY name",
            (client_id,),
        )

    prop_names = [p["name"] for p in properties]
    prop_ids   = [p["id"]   for p in properties]

    with st.expander("+ New Property", expanded=not properties):
        new_prop_name  = st.text_input("Property Name",   key="new_prop_name")
        new_prop_addr  = st.text_input("Address",          key="new_prop_addr")
        new_prop_city  = st.text_input("City",             key="new_prop_city")
        new_prop_state = st.text_input("State (2-letter)", key="new_prop_state", max_chars=2)
        new_prop_units = st.number_input("Total Units", min_value=0, step=1, key="new_prop_units")
        new_prop_type  = st.selectbox(
            "Property Type",
            ["Multifamily", "Mixed Use", "Student Housing", "Senior Housing", "BTR"],
            key="new_prop_type",
        )
        new_prop_class = st.selectbox("Asset Class", ["A", "B", "C", "D"], key="new_prop_class")
        if st.button("Create Property", key="btn_new_prop"):
            if new_prop_name.strip() and client_id:
                pid = execute(
                    """INSERT INTO properties
                       (client_id,name,address,city,state,total_units,property_type,asset_class,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        client_id, new_prop_name.strip(), new_prop_addr, new_prop_city,
                        new_prop_state.upper(), new_prop_units, new_prop_type, new_prop_class,
                        datetime.now().isoformat(), datetime.now().isoformat(),
                    ),
                )
                st.session_state["selected_property"] = pid
                st.rerun()
            else:
                st.error("Property name and a selected client are required.")

    if properties:
        sel_prop_idx = 0
        if st.session_state["selected_property"] in prop_ids:
            sel_prop_idx = prop_ids.index(st.session_state["selected_property"])
        sel_prop_name = st.selectbox("Select Property", prop_names, index=sel_prop_idx, key="prop_sb")
        st.session_state["selected_property"] = prop_ids[prop_names.index(sel_prop_name)]
    else:
        st.session_state["selected_property"] = None

    property_id = st.session_state["selected_property"]

    # Selected property info card
    if property_id:
        prop_info = fetchone("SELECT * FROM properties WHERE id=?", (property_id,))
        if prop_info:
            st.markdown(f"""
            <div style="background:#0D1526;border:1px solid #1E2D4A;border-radius:8px;
                        padding:10px;margin-top:8px;">
                <p style="color:#F0F4FF;font-size:12px;font-weight:600;margin:0;">{prop_info['name']}</p>
                <p style="color:#8BA3C7;font-size:11px;margin:3px 0 0 0;">
                    {prop_info.get('city','')}, {prop_info.get('state','')}
                </p>
                <p style="color:#8BA3C7;font-size:11px;margin:2px 0 0 0;">
                    {prop_info.get('total_units', 0)} units | Class {prop_info.get('asset_class','—')}
                </p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Navigation ────────────────────────────────────────────────────────
    st.markdown(
        '<p style="color:#8BA3C7;font-size:11px;text-transform:uppercase;'
        'letter-spacing:.08em;margin-bottom:8px;">NAVIGATION</p>',
        unsafe_allow_html=True,
    )

    if view_mode == "Analyst/Admin":
        nav_pages = [
            ("🏢", "Overview"),
            ("📊", "Financials"),
            ("🏠", "Rent Roll"),
            ("🔧", "CapEx"),
            ("🏦", "Loans"),
            ("📍", "Comparables"),
            ("📁", "Documents"),
            ("📤", "Upload Center"),
            ("⚙",  "Settings"),
        ]
    else:
        nav_pages = [
            ("🏢", "Overview"),
            ("📊", "Financials"),
            ("🏠", "Rent Roll"),
            ("🔧", "CapEx"),
            ("🏦", "Loans"),
            ("📍", "Comparables"),
            ("📁", "Documents"),
        ]

    for icon, page in nav_pages:
        if st.button(f"{icon}  {page}", key=f"nav_{page}", use_container_width=True):
            st.session_state["active_page"] = page
            st.rerun()

    # ── Export button ─────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📥 Export to Excel", use_container_width=True, key="export_btn"):
        _trigger_export(client_id, property_id)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT — route to the active page
# ═══════════════════════════════════════════════════════════════════════════════
active   = st.session_state["active_page"]
t12_data = st.session_state.get("t12_data")
rr_data  = st.session_state.get("rr_data")

# Clear data if the property has changed since last upload
if t12_data and st.session_state.get("t12_property_id") != property_id:
    t12_data = None
if rr_data and st.session_state.get("rr_property_id") != property_id:
    rr_data = None

if active == "Overview":
    _render_page_header("Portfolio Overview", "🏢", client_id, property_id)
    from views.portfolio_overview import render as render_portfolio
    render_portfolio(client_id)
    _render_insights_panel(t12_data, rr_data, property_id)

elif active == "Financials":
    _render_page_header("Financial Dashboard", "📊", client_id, property_id)
    from views.financials import render as render_fin
    render_fin(t12_data, rr_data)

elif active == "Rent Roll":
    _render_page_header("Rent Roll Dashboard", "🏠", client_id, property_id)
    from views.rent_roll import render as render_rr
    render_rr(rr_data)

elif active == "CapEx":
    _render_page_header("CapEx Tracker", "🔧", client_id, property_id)
    from views.capex import render as render_capex
    render_capex(property_id)

elif active == "Loans":
    _render_page_header("Loan Summary", "🏦", client_id, property_id)
    from views.loans import render as render_loans
    render_loans(property_id)

elif active == "Comparables":
    _render_page_header("Rent Comparables", "📍", client_id, property_id)
    from views.comparables import render as render_comps
    render_comps(property_id, rr_data)

elif active == "Documents":
    _render_page_header("Document Repository", "📁", client_id, property_id)
    from views.documents import render as render_docs
    render_docs(client_id, property_id)

elif active == "Upload Center":
    if st.session_state["view_mode"] != "Analyst/Admin":
        st.warning("Upload Center is only available in Analyst/Admin view.")
    else:
        _render_page_header("Upload Center", "📤", client_id, property_id)
        from views.upload_center import render as render_upload
        render_upload(client_id, property_id)

elif active == "Settings":
    _render_settings()
