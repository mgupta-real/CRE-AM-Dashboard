-- CRE Asset Management Dashboard — Schema
-- SQLite MVP; migratable to Supabase PostgreSQL

-- ── Future auth (placeholder) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    UNIQUE,
    name          TEXT,
    role          TEXT    DEFAULT 'viewer',   -- admin | analyst | client_viewer
    is_active     INTEGER DEFAULT 1,
    created_at    TEXT    DEFAULT (datetime('now')),
    updated_at    TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS clients (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    short_code    TEXT    UNIQUE,
    contact_email TEXT,
    contact_phone TEXT,
    notes         TEXT,
    created_at    TEXT    DEFAULT (datetime('now')),
    updated_at    TEXT    DEFAULT (datetime('now')),
    created_by    INTEGER REFERENCES users(id),
    deleted_at    TEXT
);

CREATE TABLE IF NOT EXISTS properties (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL REFERENCES clients(id),
    name            TEXT    NOT NULL,
    address         TEXT,
    city            TEXT,
    state           TEXT,
    zip             TEXT,
    total_units     INTEGER,
    year_built      INTEGER,
    property_type   TEXT    DEFAULT 'Multifamily',
    asset_class     TEXT,
    notes           TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now')),
    created_by      INTEGER REFERENCES users(id),
    deleted_at      TEXT
);

-- ── File uploads ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS uploaded_files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER REFERENCES clients(id),
    property_id     INTEGER REFERENCES properties(id),
    file_type       TEXT,   -- t12 | rent_roll | budget | loan_doc | capex | other
    original_name   TEXT,
    stored_path     TEXT,
    file_size_bytes INTEGER,
    upload_date     TEXT    DEFAULT (datetime('now')),
    reporting_period TEXT,
    as_of_date      TEXT,
    uploaded_by     INTEGER REFERENCES users(id),
    notes           TEXT,
    version         INTEGER DEFAULT 1,
    is_active       INTEGER DEFAULT 1
);

-- ── T12 / Financial data ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS financial_uploads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id     INTEGER NOT NULL REFERENCES properties(id),
    uploaded_file_id INTEGER REFERENCES uploaded_files(id),
    as_of_date      TEXT,
    t12_start_date  TEXT,
    t12_end_date    TEXT,
    total_units     INTEGER,
    created_at      TEXT    DEFAULT (datetime('now')),
    created_by      INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS financial_line_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    financial_upload_id INTEGER NOT NULL REFERENCES financial_uploads(id),
    category        TEXT,
    line_item       TEXT,
    sort_order      INTEGER DEFAULT 0,
    -- Monthly actuals (col names = ISO month end YYYY-MM)
    m1  REAL, m2  REAL, m3  REAL, m4  REAL,
    m5  REAL, m6  REAL, m7  REAL, m8  REAL,
    m9  REAL, m10 REAL, m11 REAL, m12 REAL,
    month_labels    TEXT,   -- JSON array of 12 "YYYY-MM-DD" strings
    t12_value       REAL,
    t6_value        REAL,
    t3_value        REAL,
    t1_value        REAL,
    confidence_score REAL,
    created_at      TEXT    DEFAULT (datetime('now'))
);

-- ── Rent Roll ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rent_roll_uploads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id     INTEGER NOT NULL REFERENCES properties(id),
    uploaded_file_id INTEGER REFERENCES uploaded_files(id),
    as_of_date      TEXT,
    total_units     INTEGER,
    occupied_units  INTEGER,
    vacant_units    INTEGER,
    notice_units    INTEGER,
    physical_occ    REAL,
    avg_inplace_rent REAL,
    avg_market_rent REAL,
    loss_to_lease   REAL,
    annual_sched_rent REAL,
    created_at      TEXT    DEFAULT (datetime('now')),
    created_by      INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS rent_roll_units (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rent_roll_id    INTEGER NOT NULL REFERENCES rent_roll_uploads(id),
    unit_no         TEXT,
    unit_type       TEXT,
    unit_size_sf    REAL,
    status          TEXT,   -- Occupied | Vacant | Notice | Model | Admin
    tenant_name     TEXT,
    market_rent     REAL,
    effective_rent  REAL,
    move_in_date    TEXT,
    lease_start     TEXT,
    lease_end       TEXT,
    move_out_date   TEXT,
    rent_per_sf     REAL,
    delta_amt       REAL,
    delta_pct       REAL,
    created_at      TEXT    DEFAULT (datetime('now'))
);

-- ── Loans ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS loans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id     INTEGER NOT NULL REFERENCES properties(id),
    lender          TEXT,
    loan_type       TEXT,   -- Senior | Mezz | Preferred Equity
    original_balance REAL,
    current_balance REAL,
    interest_rate   REAL,
    rate_type       TEXT,   -- Fixed | Floating
    index_type      TEXT,   -- SOFR | Prime | Fixed
    spread          REAL,
    origination_date TEXT,
    maturity_date   TEXT,
    extension_options TEXT,
    amortization_type TEXT, -- IO | Amortizing
    amort_years     INTEGER,
    monthly_debt_svc REAL,
    notes           TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now')),
    created_by      INTEGER REFERENCES users(id)
);

-- ── Capex ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS capex_projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id     INTEGER NOT NULL REFERENCES properties(id),
    project_name    TEXT,
    category        TEXT,
    budget          REAL,
    actual_spent    REAL    DEFAULT 0,
    start_date      TEXT,
    expected_end    TEXT,
    actual_end      TEXT,
    status          TEXT    DEFAULT 'Planned', -- Planned|In Progress|Complete|On Hold|Over Budget
    vendor          TEXT,
    notes           TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now')),
    created_by      INTEGER REFERENCES users(id)
);

-- ── Comparable properties ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS comparable_properties (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id     INTEGER NOT NULL REFERENCES properties(id),  -- subject property
    comp_name       TEXT,
    address         TEXT,
    city            TEXT,
    state           TEXT,
    zip             TEXT,
    distance_miles  REAL,
    year_built      INTEGER,
    units           INTEGER,
    property_class  TEXT,
    asset_type      TEXT,
    amenities       TEXT,
    apts_url        TEXT,
    property_url    TEXT,
    notes           TEXT,
    status          TEXT    DEFAULT 'Active',
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now')),
    created_by      INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS comparable_unit_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    comp_property_id INTEGER NOT NULL REFERENCES comparable_properties(id),
    snapshot_date   TEXT,
    unit_type       TEXT,
    bedrooms        INTEGER,
    bathrooms       REAL,
    sq_ft           REAL,
    min_rent        REAL,
    max_rent        REAL,
    avg_rent        REAL,
    effective_rent  REAL,
    asking_rent     REAL,
    concessions     REAL    DEFAULT 0,
    available_units INTEGER,
    rent_per_sf     REAL,
    source_url      TEXT,
    data_source     TEXT,   -- Manual | Apartments.com | CoStar | etc.
    confidence      TEXT    DEFAULT 'Medium',
    reviewed_date   TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    created_by      INTEGER REFERENCES users(id)
);

-- ── Documents ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER REFERENCES clients(id),
    property_id     INTEGER REFERENCES properties(id),
    doc_type        TEXT,   -- T12|RentRoll|Budget|Loan|Capex|Report|Insurance|Tax|Appraisal|OM|Other
    display_name    TEXT,
    stored_path     TEXT,
    file_size_bytes INTEGER,
    upload_date     TEXT    DEFAULT (datetime('now')),
    reporting_period TEXT,
    notes           TEXT,
    version         INTEGER DEFAULT 1,
    uploaded_by     INTEGER REFERENCES users(id),
    deleted_at      TEXT
);

-- ── Insights ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS insights (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id     INTEGER REFERENCES properties(id),
    insight_type    TEXT,
    severity        TEXT    DEFAULT 'info',  -- info | warning | alert
    message         TEXT,
    metric_value    REAL,
    metric_label    TEXT,
    generated_at    TEXT    DEFAULT (datetime('now'))
);

-- ── Export / audit logs ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS export_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id     INTEGER REFERENCES properties(id),
    export_type     TEXT,
    file_path       TEXT,
    exported_at     TEXT    DEFAULT (datetime('now')),
    exported_by     INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name      TEXT,
    record_id       INTEGER,
    action          TEXT,   -- INSERT | UPDATE | DELETE
    old_values      TEXT,   -- JSON
    new_values      TEXT,   -- JSON
    performed_by    INTEGER REFERENCES users(id),
    performed_at    TEXT    DEFAULT (datetime('now'))
);
