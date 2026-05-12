"""
database/seed_data.py
Seeds the SQLite database with a demo client and property so the app
is immediately usable without manual setup.
"""
from datetime import datetime
from database.db import execute, fetchone


def seed_demo_data():
    """Insert demo client and property if they don't exist."""
    now = datetime.now().isoformat()

    # --- Demo Client ---
    existing_client = fetchone("SELECT id FROM clients WHERE name = ?", ("Phoenix RE Partners",))
    if not existing_client:
        client_id = execute(
            "INSERT INTO clients (name, created_at, updated_at) VALUES (?,?,?)",
            ("Phoenix RE Partners", now, now),
        )
    else:
        client_id = existing_client["id"]

    # --- Demo Property ---
    existing_prop = fetchone("SELECT id FROM properties WHERE name = ?", ("Phoenix Commons",))
    if not existing_prop:
        execute(
            """INSERT INTO properties
               (client_id, name, address, city, state, zip, property_type,
                year_built, total_units, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                client_id,
                "Phoenix Commons",
                "1234 W Camelback Rd",
                "Phoenix",
                "AZ",
                "85013",
                "Multifamily",
                1998,
                439,
                now,
                now,
            ),
        )

    print("✅ Demo seed data inserted (or already present).")


if __name__ == "__main__":
    from database.db import init_db
    init_db()
    seed_demo_data()
