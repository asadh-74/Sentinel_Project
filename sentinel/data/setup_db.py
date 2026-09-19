"""
setup_db.py
-----------
The Sentinel spec calls for a `system_telemetry.db` containing `servers`,
`logs`, and `incidents` tables. The provided data pack only ships `servers`
and `logs`, so this script idempotently adds the missing `incidents` table
(used by the Remediation Agent to record what it did, and by the Verify
step of the LangGraph loop to check whether an incident is still open).

Run once:  python data/setup_db.py
Safe to re-run — it only creates the table/columns if they don't exist yet.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "system_telemetry.db"


def setup(db_path: Path = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            incident_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id       TEXT NOT NULL,
            opened_at       TEXT NOT NULL,
            closed_at       TEXT,
            symptom         TEXT NOT NULL,
            root_cause      TEXT,
            remediation     TEXT,
            status          TEXT NOT NULL DEFAULT 'OPEN',   -- OPEN | RESOLVED | ESCALATED
            retry_count     INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (server_id) REFERENCES servers(server_id)
        )
    """)

    # A couple of historical incidents so the Data Intelligence Agent /
    # NL2SQL interface has something realistic to query against.
    cur.execute("SELECT COUNT(*) FROM incidents")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            """INSERT INTO incidents
               (server_id, opened_at, closed_at, symptom, root_cause, remediation, status, retry_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                ("SRV-002", "2026-06-29 09:12:00", "2026-06-29 09:41:00",
                 "High memory usage (92.3%) on db-prod-1",
                 "Unbounded query result caching in the reporting service",
                 "Restarted reporting-cache service; flushed cache",
                 "RESOLVED", 1),
                ("SRV-001", "2026-06-30 02:04:00", None,
                 "Elevated ERROR rate in Auth-Service logs",
                 None, None, "OPEN", 0),
            ],
        )

    conn.commit()

    # Sanity print so this is useful when run standalone.
    for table in ("servers", "logs", "incidents"):
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"{table}: {cur.fetchone()[0]} rows")

    conn.close()


if __name__ == "__main__":
    setup()
