"""
Single source of truth for the telemetry DB's schema and connection.
NL2SQL, the MCP tools, and the agents all import from here so the
schema description given to the LLM never drifts from the real DB.
"""
import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "system_telemetry.db"

SCHEMA_DESCRIPTION = """
You are querying a SQLite database called system_telemetry.db with exactly
three tables. Do not assume any other tables or columns exist.

TABLE servers
  server_id             TEXT PRIMARY KEY   -- e.g. 'SRV-001'
  hostname              TEXT               -- e.g. 'web-prod-1'
  region                TEXT               -- e.g. 'US-East'
  status                TEXT               -- 'ACTIVE' | 'DEGRADED' | 'OFFLINE'
  cpu_usage_percent     REAL               -- 0-100
  memory_usage_percent  REAL               -- 0-100

TABLE logs
  log_id                INTEGER PRIMARY KEY
  server_id             TEXT               -- FK -> servers.server_id
  timestamp             TEXT               -- ISO-ish datetime string
  log_level             TEXT               -- 'INFO' | 'WARN' | 'ERROR'
  message               TEXT
  service_name          TEXT               -- e.g. 'Auth-Service'

TABLE incidents
  incident_id           INTEGER PRIMARY KEY
  server_id             TEXT               -- FK -> servers.server_id
  opened_at             TEXT
  closed_at             TEXT               -- NULL while open
  symptom               TEXT
  root_cause            TEXT               -- NULL until diagnosed
  remediation           TEXT               -- NULL until remediated
  status                TEXT               -- 'OPEN' | 'RESOLVED' | 'ESCALATED'
  retry_count           INTEGER
"""

# Vocabulary used by the offline/graceful-degradation scope check in nl2sql.
SCHEMA_VOCABULARY = {
    "server", "servers", "hostname", "region", "status", "cpu", "memory",
    "usage", "active", "degraded", "offline", "log", "logs", "timestamp",
    "level", "error", "warn", "info", "message", "service", "incident",
    "incidents", "root", "cause", "remediation", "resolved", "escalated",
    "open", "closed", "retry",
}


@contextmanager
def get_connection(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
