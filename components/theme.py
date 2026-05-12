"""
components/theme.py
Dark navy/blue institutional CRE dashboard theme for Streamlit.
"""

# ── Color palette ────────────────────────────────────────────────────────────
COLORS = {
    "bg_primary":    "#0A0E1A",
    "bg_secondary":  "#0D1526",
    "bg_card":       "#111827",
    "bg_card_hover": "#1A2540",
    "border":        "#1E2D4A",
    "accent_blue":   "#1E6FEB",
    "accent_cyan":   "#00C2FF",
    "accent_teal":   "#0ADFB4",
    "text_primary":  "#F0F4FF",
    "text_secondary":"#8BA3C7",
    "text_muted":    "#4A6080",
    "green":         "#00C48C",
    "red":           "#FF4560",
    "yellow":        "#FFB020",
    "orange":        "#FF8042",
    "purple":        "#7B5EA7",
    "chart1":        "#1E6FEB",
    "chart2":        "#00C2FF",
    "chart3":        "#0ADFB4",
    "chart4":        "#FFB020",
    "chart5":        "#FF8042",
    "chart6":        "#7B5EA7",
    "chart7":        "#FF4560",
}

PLOTLY_TEMPLATE = "plotly_dark"

CHART_COLORS = [
    COLORS["chart1"], COLORS["chart2"], COLORS["chart3"],
    COLORS["chart4"], COLORS["chart5"], COLORS["chart6"], COLORS["chart7"],
]


def inject_css():
    """Inject custom CSS into the Streamlit app."""
    import streamlit as st
    st.markdown(f"""
    <style>
    /* ── Root & body ──────────────────────────────────────── */
    :root {{
        --bg-primary:    {COLORS['bg_primary']};
        --bg-secondary:  {COLORS['bg_secondary']};
        --bg-card:       {COLORS['bg_card']};
        --border:        {COLORS['border']};
        --accent-blue:   {COLORS['accent_blue']};
        --accent-cyan:   {COLORS['accent_cyan']};
        --accent-teal:   {COLORS['accent_teal']};
        --text-primary:  {COLORS['text_primary']};
        --text-secondary:{COLORS['text_secondary']};
        --green:         {COLORS['green']};
        --red:           {COLORS['red']};
        --yellow:        {COLORS['yellow']};
    }}

    .stApp {{
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
    }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background-color: {COLORS['bg_secondary']} !important;
        border-right: 1px solid var(--border);
    }}
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stRadio label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span {{
        color: var(--text-secondary) !important;
    }}

    /* Main content */
    .main .block-container {{
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }}

    /* ── KPI cards ────────────────────────────────────────── */
    .kpi-card {{
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 16px 20px;
        position: relative;
        overflow: hidden;
        transition: border-color 0.2s;
    }}
    .kpi-card:hover {{ border-color: var(--accent-blue); }}
    .kpi-card::before {{
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan));
    }}
    .kpi-label {{
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-secondary);
        margin: 0 0 4px 0;
    }}
    .kpi-value {{
        font-size: 28px;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1.1;
        margin: 0 0 6px 0;
    }}
    .kpi-delta {{
        font-size: 12px;
        font-weight: 500;
    }}
    .kpi-delta.positive {{ color: var(--green); }}
    .kpi-delta.negative {{ color: var(--red); }}
    .kpi-delta.neutral  {{ color: var(--text-secondary); }}
    .kpi-icon {{
        position: absolute;
        top: 16px; right: 16px;
        font-size: 24px;
        opacity: 0.25;
    }}

    /* ── Dashboard section cards ──────────────────────────── */
    .dash-card {{
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    }}
    .dash-card-title {{
        font-size: 13px;
        font-weight: 700;
        color: var(--text-secondary);
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 16px;
        padding-bottom: 10px;
        border-bottom: 1px solid var(--border);
    }}

    /* ── Tabs ────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {{
        background: var(--bg-secondary);
        border-radius: 8px;
        border: 1px solid var(--border);
        gap: 2px;
        padding: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background: transparent;
        border: none;
        border-radius: 6px;
        color: var(--text-secondary);
        font-weight: 600;
        font-size: 13px;
        padding: 8px 20px;
    }}
    .stTabs [aria-selected="true"] {{
        background: var(--accent-blue) !important;
        color: white !important;
    }}

    /* ── Selectboxes & inputs ─────────────────────────────── */
    .stSelectbox > div > div {{
        background: var(--bg-card) !important;
        border-color: var(--border) !important;
        color: var(--text-primary) !important;
    }}
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input {{
        background: var(--bg-card) !important;
        border-color: var(--border) !important;
        color: var(--text-primary) !important;
    }}
    .stTextArea textarea {{
        background: var(--bg-card) !important;
        border-color: var(--border) !important;
        color: var(--text-primary) !important;
    }}

    /* ── Buttons ──────────────────────────────────────────── */
    .stButton > button {{
        background: var(--accent-blue);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        transition: opacity 0.2s;
    }}
    .stButton > button:hover {{ opacity: 0.85; }}
    .stDownloadButton > button {{
        background: linear-gradient(135deg, var(--accent-blue), var(--accent-cyan));
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }}

    /* ── Tables ───────────────────────────────────────────── */
    .stDataFrame {{ border-radius: 8px; overflow: hidden; }}
    .stDataFrame thead th {{
        background: #162035 !important;
        color: var(--text-secondary) !important;
        font-size: 11px !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    .stDataFrame tbody td {{
        background: var(--bg-card) !important;
        color: var(--text-primary) !important;
        font-size: 13px !important;
    }}
    .stDataFrame tbody tr:hover td {{ background: var(--bg-card-hover) !important; }}

    /* ── Metrics ──────────────────────────────────────────── */
    [data-testid="metric-container"] {{
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 14px 16px;
    }}
    [data-testid="metric-container"] label {{
        color: var(--text-secondary) !important;
        font-size: 11px !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }}
    [data-testid="metric-container"] [data-testid="metric-value"] {{
        color: var(--text-primary) !important;
        font-size: 26px !important;
        font-weight: 700;
    }}

    /* ── Expanders ────────────────────────────────────────── */
    .streamlit-expanderHeader {{
        background: var(--bg-card) !important;
        color: var(--text-primary) !important;
        border-radius: 8px;
    }}

    /* ── Alerts / info boxes ──────────────────────────────── */
    .stAlert {{
        background: var(--bg-card);
        border-radius: 8px;
        border-left: 4px solid var(--accent-blue);
    }}

    /* ── Dividers ──────────────────────────────────────────── */
    hr {{ border-color: var(--border) !important; }}

    /* ── Section headers ───────────────────────────────────── */
    h1, h2, h3, h4 {{ color: var(--text-primary) !important; }}

    /* ── Upload widget ──────────────────────────────────────── */
    [data-testid="stFileUploader"] {{
        background: var(--bg-card);
        border: 2px dashed var(--border);
        border-radius: 10px;
        padding: 8px;
    }}
    [data-testid="stFileUploader"]:hover {{
        border-color: var(--accent-blue);
    }}

    /* ── Watchlist status colors ─────────────────────────── */
    .status-occupied {{ color: {COLORS['green']}; font-weight: 600; }}
    .status-vacant   {{ color: {COLORS['red']};   font-weight: 600; }}
    .status-notice   {{ color: {COLORS['yellow']}; font-weight: 600; }}

    /* ── Insight badges ────────────────────────────────────── */
    .insight-info    {{ border-left: 3px solid {COLORS['accent_blue']}; }}
    .insight-warning {{ border-left: 3px solid {COLORS['yellow']}; }}
    .insight-alert   {{ border-left: 3px solid {COLORS['red']}; }}

    /* ── Logo/nav area ─────────────────────────────────────── */
    .nav-logo {{
        font-size: 18px;
        font-weight: 800;
        color: var(--accent-cyan);
        letter-spacing: 0.03em;
    }}
    .nav-logo span {{ color: var(--text-secondary); font-weight: 400; }}

    /* Scrollbar */
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: var(--bg-primary); }}
    ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}
    </style>
    """, unsafe_allow_html=True)


def kpi_card(label: str, value: str, delta: str = "", delta_positive: bool | None = None,
             icon: str = "", bg_color: str = "") -> str:
    """Return HTML for a KPI card."""
    delta_class = ""
    if delta:
        if delta_positive is True:
            delta_class = "positive"
        elif delta_positive is False:
            delta_class = "negative"
        else:
            delta_class = "neutral"

    style = f'style="background:{bg_color}"' if bg_color else ""
    return f"""
    <div class="kpi-card" {style}>
        <div class="kpi-icon">{icon}</div>
        <p class="kpi-label">{label}</p>
        <p class="kpi-value">{value}</p>
        {"" if not delta else f'<p class="kpi-delta {delta_class}">{delta}</p>'}
    </div>
    """


def section_card_open(title: str = "") -> str:
    title_html = f'<div class="dash-card-title">{title}</div>' if title else ""
    return f'<div class="dash-card">{title_html}'


def section_card_close() -> str:
    return "</div>"
