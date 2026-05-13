# 🏢 CRE Asset Management Dashboard

A production-grade Streamlit dashboard for Commercial Real Estate / Multifamily asset management. Built for analysts and institutional investors who need real-time financial and operational visibility across their portfolio.

---

## ✨ Features

| Module | Description |
|---|---|
| **Financials** | T12 trend analysis, NOI bridge, revenue/expense mix, financial statement table |
| **Rent Roll** | Occupancy, unit mix, lease expirations, loss-to-lease watchlist |
| **CapEx** | Budget vs actual, project tracking, by-category charts |
| **Loans** | Maturity countdown, DSCR, debt yield, LTV |
| **Comparables** | Rent comp set, subject vs market analysis, historical snapshots |
| **Documents** | Centralized document repository with version tracking |
| **Upload Center** | T12 and rent roll upload, parsing, validation (Analyst view) |
| **Insights Engine** | Rules-based AM observations triggered by real metrics |
| **Excel Export** | Professional multi-sheet export with all dashboard data |

---

## 🚀 Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/your-org/cre-asset-management-dashboard.git
cd cre-asset-management-dashboard
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# or
.venv\Scripts\activate      # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env if needed (defaults work for local dev)
```

### 5. Initialize the database and seed demo data

```bash
python -m database.seed_data
```

### 6. Run the app

```bash
streamlit run app.py
```

Open your browser to **http://localhost:8501**

---

## 📁 Project Structure

```
cre-asset-management-dashboard/
│
├── app.py                    # Entry point + sidebar + page routing
├── requirements.txt
├── README.md
├── .env.example
│
├── config/
│   └── settings.py           # Env vars, paths, constants
│
├── data/
│   ├── uploads/              # Raw uploaded files
│   ├── processed/            # Parsed outputs (JSON)
│   └── exports/              # Excel exports
│
├── database/
│   ├── db.py                 # SQLite connection + helpers
│   ├── schema.sql            # Full schema (auth-ready)
│   └── seed_data.py          # Demo data seeder
│
├── pages/
│   ├── portfolio_overview.py
│   ├── financials.py
│   ├── rent_roll.py
│   ├── capex.py
│   ├── loans.py
│   ├── comparables.py
│   ├── documents.py
│   └── upload_center.py
│
├── services/
│   ├── t12_parser.py         # T12 Excel parser (exact format)
│   ├── rent_roll_parser.py   # Rent roll Excel parser (exact format)
│   ├── insights_engine.py    # Rules-based AM insights
│   └── excel_exporter.py     # Multi-sheet Excel export
│
├── components/
│   ├── theme.py              # Dark navy/blue CSS + KPI card helpers
│   └── charts.py             # Plotly chart factory functions
│
└── utils/
    └── formatting.py         # Currency, percent, date formatters
```

---

## 📊 Input File Formats

### T12 File (Excel)
- Sheet name: `T12`
- Row 4: `T12 As Of Date:` in column C, date value in column D
- Row 8: Header row — `Category`, `T12 Line-Item Name`, 12 monthly date columns, `T12`, `T6`, `T3`, `T1`
- Rows 9+: Line items (revenue, vacancy, expenses, NOI)

### Rent Roll File (Excel)
- Sheet name: `Standardized Rent Roll`
- Columns: `Unit No`, `Unit Size (SF)`, `Market Rent (Monthly)`, `Effective Rent (Monthly)`, `Move In Date`, `Lease Start Date`, `Lease End Date`, `Move Out Date`, `Tenant Name`, `Unit Type`
- Vacant units: Tenant Name = `VACANT`

---

## 🔐 Adding Login Later (Supabase)

The app is architected for seamless auth addition:

1. **Install Supabase client**: `pip install supabase`
2. **Set env vars**: `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `.env`
3. **Replace `database/db.py`**: Swap SQLite connection factory for Supabase client
4. **Wrap pages**: Check `st.session_state['user']` at the top of each page
5. **Add RLS**: All tables have `client_id` and `property_id` — enable Row Level Security on Supabase to restrict access by user

All tables already have:
- `client_id` foreign key
- `property_id` foreign key
- `created_by` / `updated_by` (user ID placeholders)
- `created_at` / `updated_at` timestamps
- `deleted_at` for soft deletes

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit + custom CSS |
| Charts | Plotly (dark theme) |
| Data | Pandas, NumPy |
| Excel | OpenPyXL (read) + XlsxWriter (write) |
| Database | SQLite (MVP) → Supabase PostgreSQL (production) |
| File storage | Local filesystem → Supabase Storage |

---

## 📝 Notes

- No external paid APIs required for MVP
- No login required for MVP — just open and use
- Parser built against Phoenix Commons T12 and Rent Roll formats
- If budget file is missing, dashboard shows clean placeholders
- All charts use Plotly dark theme consistent with the navy/blue design

---

## 📦 Deployment

For production deployment, consider:
- **Streamlit Community Cloud** (free tier): Push to GitHub, deploy at share.streamlit.io
- **Heroku / Railway / Render**: Add `Procfile` with `web: streamlit run app.py --server.port=$PORT`
- **Docker**: Containerize with `python:3.11-slim`, install requirements, expose port 8501
