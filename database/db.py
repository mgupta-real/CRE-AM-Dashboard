"""
database/db.py
SQLite connection + schema bootstrap.
Designed so the same interface works with Supabase PostgreSQL later —
swap the connection factory, keep the rest.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from config.settings import DB_PATH


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they do not exist."""
    conn = get_connection()
    schema = Path(__file__).parent / "schema.sql"
    conn.executescript(schema.read_text())
    conn.commit()
    conn.close()


# ── Generic helpers ───────────────────────────────────────────────────────────

def fetchall(sql: str, params=()) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetchone(sql: str, params=()) -> dict | None:
    conn = get_connection()
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return dict(row) if row else None


def execute(sql: str, params=()) -> int:
    """Execute a write statement and return lastrowid."""
    conn = get_connection()
    cur = conn.execute(sql, params)
    conn.commit()
    rowid = cur.lastrowid
    conn.close()
    return rowid


def executemany(sql: str, params_list: list):
    conn = get_connection()
    conn.executemany(sql, params_list)
    conn.commit()
    conn.close()
