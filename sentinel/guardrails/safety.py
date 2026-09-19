"""
guardrails/safety.py
---------------------
Production resilience for the Remediation Agent.

Spec requirement: "Remediation Agent must prevent 'high-risk' commands
(e.g., system_reboot) during critical database load."

This module is intentionally standalone (no LLM, no agent framework) so it
can be unit-tested in isolation and is trivially auditable — this is the
one piece of the system a reviewer should be able to read in 30 seconds
and trust.
"""
from dataclasses import dataclass
from data.schema import get_connection

# Commands that can cause an outage or data loss if fired at the wrong time.
HIGH_RISK_COMMANDS = {
    "system_reboot",
    "shutdown",
    "restart_database",
    "drop_table",
    "kill_all_connections",
    "force_failover",
}

# A server is under "critical database load" if either metric crosses this.
CRITICAL_LOAD_THRESHOLD = 85.0

# Only servers that actually run a database service are subject to the
# database-load check; a reboot of a stateless web node isn't gated by it.
DB_SERVICE_HINTS = ("db-", "database", "sql", "postgres", "mysql")


@dataclass
class SafetyDecision:
    allowed: bool
    reason: str


def _server_row(conn, server_id: str):
    return conn.execute(
        "SELECT * FROM servers WHERE server_id = ?", (server_id,)
    ).fetchone()


def _looks_like_db_server(hostname: str) -> bool:
    hostname = (hostname or "").lower()
    return any(hint in hostname for hint in DB_SERVICE_HINTS)


def is_critical_db_load(server_id: str) -> bool:
    """True if the named server is a DB host currently over the critical
    CPU/memory threshold."""
    with get_connection() as conn:
        row = _server_row(conn, server_id)
        if row is None:
            return False
        if not _looks_like_db_server(row["hostname"]):
            return False
        return (
            row["cpu_usage_percent"] >= CRITICAL_LOAD_THRESHOLD
            or row["memory_usage_percent"] >= CRITICAL_LOAD_THRESHOLD
        )


def check_command_safety(command: str, server_id: str) -> SafetyDecision:
    """The single gate every remediation command must pass through before
    execute_system_command is allowed to run it for real."""
    normalized = command.strip().lower()

    if normalized not in HIGH_RISK_COMMANDS:
        return SafetyDecision(allowed=True, reason="Command is not on the high-risk list.")

    if is_critical_db_load(server_id):
        return SafetyDecision(
            allowed=False,
            reason=(
                f"BLOCKED: '{command}' is a high-risk command and {server_id} is "
                f"currently under critical database load (>= {CRITICAL_LOAD_THRESHOLD}% "
                "CPU/memory). Escalating to a human operator instead of executing."
            ),
        )

    return SafetyDecision(
        allowed=True,
        reason=f"'{command}' is high-risk but {server_id} is not under critical DB load. Proceeding.",
    )
