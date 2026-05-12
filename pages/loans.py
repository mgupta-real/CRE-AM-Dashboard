"""pages/loans.py — Loan management page."""
import streamlit as st
import pandas as pd
from datetime import datetime, date
from database.db import execute, fetchall, fetchone
from utils.formatting import fmt_currency, fmt_pct, fmt_date, fmt_number
from components.theme import kpi_card


def render(property_id: int | None):
    st.markdown("## 🏦 Loan Summary")
    if not property_id:
        st.warning("Select a property to manage loans.")
        return

    loans = fetchall("SELECT * FROM loans WHERE property_id=? ORDER BY id", (property_id,))
    noi_t12 = _get_noi(property_id)

    # ── KPI Row ───────────────────────────────────────────────────────────
    if loans:
        total_balance = sum((l.get("current_balance") or 0) for l in loans)
        total_ds = sum((l.get("monthly_debt_svc") or 0) for l in loans) * 12
        dscr = (noi_t12 / total_ds) if (noi_t12 and total_ds and total_ds > 0) else None

        cols = st.columns(5)
        with cols[0]: st.markdown(kpi_card("Total Loan Balance", fmt_currency(total_balance), icon="🏛"), unsafe_allow_html=True)
        with cols[1]: st.markdown(kpi_card("Annual Debt Service", fmt_currency(total_ds), icon="💳"), unsafe_allow_html=True)
        with cols[2]: st.markdown(kpi_card("DSCR", f"{dscr:.2f}x" if dscr else "—", icon="📊",
                                           delta="Healthy" if dscr and dscr >= 1.25 else ("Below 1.25x" if dscr else "")),
                                  unsafe_allow_html=True)
        nearest_mat = _nearest_maturity(loans)
        with cols[3]: st.markdown(kpi_card("Nearest Maturity", nearest_mat or "—", icon="📅"), unsafe_allow_html=True)
        with cols[4]: st.markdown(kpi_card("NOI T12", fmt_currency(noi_t12), icon="📈"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

    # ── Loan cards ────────────────────────────────────────────────────────
    if loans:
        st.markdown("### Existing Loans")
        for loan in loans:
            _render_loan_card(loan, noi_t12)
            st.markdown("---")

    # ── Add new loan ──────────────────────────────────────────────────────
    with st.expander("➕ Add / Edit Loan", expanded=not loans):
        _add_loan_form(property_id)


def _render_loan_card(loan: dict, noi_t12):
    bal  = loan.get("current_balance")
    rate = loan.get("interest_rate")
    mat  = loan.get("maturity_date")
    ds   = loan.get("monthly_debt_svc")
    ann_ds = (ds or 0) * 12

    dscr = (noi_t12 / ann_ds) if (noi_t12 and ann_ds and ann_ds > 0) else None

    days_to_mat = None
    if mat:
        try:
            from dateutil import parser as dp
            mat_dt = dp.parse(str(mat)).date()
            days_to_mat = (mat_dt - date.today()).days
        except Exception:
            pass

    mat_color = "#FF4560" if days_to_mat and days_to_mat < 180 else ("#FFB020" if days_to_mat and days_to_mat < 365 else "#00C48C")

    st.markdown(f"""
    <div class="dash-card">
        <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:12px;">
            <div>
                <h4 style="color:#F0F4FF;margin:0;">{loan.get('lender','[Lender]')} — {loan.get('loan_type','Senior')}</h4>
                <p style="color:#8BA3C7;font-size:12px;margin:4px 0 0 0;">{loan.get('rate_type','')} | {loan.get('amortization_type','')} | Originated: {fmt_date(loan.get('origination_date'))}</p>
            </div>
            <div style="text-align:right;">
                <p style="color:{mat_color};font-size:13px;font-weight:600;margin:0;">Maturity: {fmt_date(mat)}</p>
                {"" if not days_to_mat else f'<p style="color:{mat_color};font-size:11px;margin:2px 0 0 0;">{days_to_mat} days remaining</p>'}
            </div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;">
            <div><p style="color:#8BA3C7;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin:0">Current Balance</p><p style="color:#F0F4FF;font-size:18px;font-weight:700;margin:0">{fmt_currency(bal)}</p></div>
            <div><p style="color:#8BA3C7;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin:0">Interest Rate</p><p style="color:#F0F4FF;font-size:18px;font-weight:700;margin:0">{fmt_pct(rate*100 if rate else None)}</p></div>
            <div><p style="color:#8BA3C7;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin:0">Annual Debt Svc</p><p style="color:#F0F4FF;font-size:18px;font-weight:700;margin:0">{fmt_currency(ann_ds)}</p></div>
            <div><p style="color:#8BA3C7;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin:0">DSCR</p><p style="color:{'#00C48C' if dscr and dscr>=1.25 else '#FF4560' if dscr else '#F0F4FF'};font-size:18px;font-weight:700;margin:0">{f"{dscr:.2f}x" if dscr else "—"}</p></div>
            <div><p style="color:#8BA3C7;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin:0">Extensions</p><p style="color:#F0F4FF;font-size:14px;font-weight:600;margin:0">{loan.get('extension_options','—')}</p></div>
        </div>
        {"" if not loan.get('notes') else f'<p style="color:#8BA3C7;font-size:12px;margin:12px 0 0 0;border-top:1px solid #1E2D4A;padding-top:10px;">{loan["notes"]}</p>'}
    </div>
    """, unsafe_allow_html=True)


def _add_loan_form(property_id: int):
    col1, col2, col3 = st.columns(3)
    with col1:
        lender    = st.text_input("Lender Name")
        loan_type = st.selectbox("Loan Type", ["Senior", "Mezzanine", "Preferred Equity", "Bridge", "Construction"])
        orig_bal  = st.number_input("Original Balance ($)", min_value=0.0, step=100000.0, format="%.0f")
        curr_bal  = st.number_input("Current Balance ($)",  min_value=0.0, step=100000.0, format="%.0f")
    with col2:
        rate      = st.number_input("Interest Rate (%)", min_value=0.0, max_value=30.0, step=0.125, format="%.3f")
        rate_type = st.selectbox("Rate Type", ["Fixed", "Floating"])
        index_tp  = st.selectbox("Index", ["N/A (Fixed)", "SOFR", "Prime", "LIBOR"])
        spread    = st.number_input("Spread (bps over index)", min_value=0.0, step=25.0, format="%.0f") if rate_type == "Floating" else 0
    with col3:
        orig_date = st.date_input("Origination Date", value=date.today())
        mat_date  = st.date_input("Maturity Date",    value=date.today())
        amort_tp  = st.selectbox("Amortization", ["IO", "30-Year Amort", "25-Year Amort", "20-Year Amort"])
        monthly_ds = st.number_input("Monthly Debt Service ($)", min_value=0.0, step=1000.0, format="%.0f")

    col4, col5 = st.columns(2)
    with col4:
        extensions = st.text_input("Extension Options (e.g. '2 x 1-year')")
    with col5:
        notes = st.text_area("Notes", height=80)

    if st.button("💾 Save Loan", key="save_loan"):
        if not lender:
            st.error("Lender name is required.")
        else:
            execute("""
                INSERT INTO loans
                (property_id,lender,loan_type,original_balance,current_balance,
                 interest_rate,rate_type,index_type,spread,origination_date,maturity_date,
                 extension_options,amortization_type,monthly_debt_svc,notes,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (property_id, lender, loan_type, orig_bal, curr_bal,
                  rate / 100, rate_type, index_tp, spread,
                  orig_date.isoformat(), mat_date.isoformat(),
                  extensions, amort_tp, monthly_ds, notes,
                  datetime.now().isoformat(), datetime.now().isoformat()))
            st.success("✅ Loan saved!")
            st.rerun()


def _get_noi(property_id) -> float | None:
    return st.session_state.get("t12_data", {}).get("summary", {}).get("noi_t12")


def _nearest_maturity(loans: list) -> str | None:
    dates = []
    for l in loans:
        if l.get("maturity_date"):
            try:
                from dateutil import parser as dp
                dates.append(dp.parse(str(l["maturity_date"])).date())
            except Exception:
                pass
    if not dates:
        return None
    return min(dates).strftime("%m/%d/%Y")
