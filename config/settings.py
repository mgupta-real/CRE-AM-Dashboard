"""
config/settings.py
Central configuration for the CRE Asset Management Dashboard.
Designed so that moving to Supabase/cloud later requires only env-var changes.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Paths ─────────────────────────────────────────────────────────────────────
DB_PATH      = os.getenv("DB_PATH",        str(BASE_DIR / "data" / "cre_dashboard.db"))
UPLOAD_DIR   = os.getenv("UPLOAD_DIR",     str(BASE_DIR / "data" / "uploads"))
PROCESSED_DIR= os.getenv("PROCESSED_DIR",  str(BASE_DIR / "data" / "processed"))
EXPORT_DIR   = os.getenv("EXPORT_DIR",     str(BASE_DIR / "data" / "exports"))

# ── App ───────────────────────────────────────────────────────────────────────
APP_ENV      = os.getenv("APP_ENV", "development")
APP_NAME     = "CRE Asset Management"
APP_VERSION  = "1.0.0-MVP"

# ── Future Auth (Supabase) ────────────────────────────────────────────────────
SUPABASE_URL        = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY   = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY= os.getenv("SUPABASE_SERVICE_KEY", "")

# ── Ensure dirs exist ─────────────────────────────────────────────────────────
for d in [UPLOAD_DIR, PROCESSED_DIR, EXPORT_DIR]:
    Path(d).mkdir(parents=True, exist_ok=True)
