"""
mcp_server/tools.py
--------------------
The actual implementations behind Sentinel's four capabilities. Both
mcp_server/server.py (exposed over MCP) and agents/crew.py (exposed as
CrewAI tools) call these same functions, so there is exactly one
implementation of each capability — the MCP server is genuinely "the only
entry point" the spec asks for, not a thin duplicate of agent logic.
"""
from __future__ import annotations
import datetime as _dt
from typing import Optional

from data.schema import get_connection
from guardrails.safety import check_command_safety, HIGH_RISK_COMMANDS
from knowledge_base.rag import retrieve as kb_retrieve
from nl2sql.translator import query_database as _nl2sql_query


def get_system_logs(server_id: Optional[str] = None, log_level: Optional[str] = None, limit: int = 50) -> dict:
    """Read-only log fetch, optionally filtered by server and/or level."""
    clauses, params = [], []
    if server_id:
        clauses.append("server_id = ?")
        params.append(server_id)
    if log_level:
        clauses.append("log_level = ?")
        params.append(log_level.upper())
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM logs {where} ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    return {"count": len(rows), "logs": rows}


def execute_system_command(command: str, server_id: str) -> dict:
    """Simulated command execution, gated by the safety guardrails. Never
    actually touches a real host — this is a training/demo environment —
    but it does write the outcome to the `incidents` table so the loop's
    Verify step and the Data Intelligence Agent see a consistent history.
    """
    decision = check_command_safety(command, server_id)
    now = _dt.datetime.utcnow().isoformat(sep=" ", timespec="seconds")

    if not decision.allowed:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO incidents (server_id, opened_at, symptom, remediation, status)
                   VALUES (?, ?, ?, ?, 'ESCALATED')""",
                (server_id, now, f"Blocked high-risk command: {command}", decision.reason),
            )
            conn.commit()
        return {"executed": False, "simulated": True, "reason": decision.reason}

    # Simulate the effect: high-risk commands that ARE allowed "resolve" the
    # load by nudging metrics down; non-risky commands (restarts) always do.
    with get_connection() as conn:
        if command.strip().lower() in {"restart_service"} | HIGH_RISK_COMMANDS:
            conn.execute(
                "UPDATE servers SET cpu_usage_percent = cpu_usage_percent * 0.5, "
                "memory_usage_percent = memory_usage_percent * 0.5 WHERE server_id = ?",
                (server_id,),
            )
        conn.commit()

    return {
        "executed": True,
        "simulated": True,
        "command": command,
        "server_id": server_id,
        "reason": decision.reason,
        "result": "200 OK (simulated)",
    }


def query_knowledge_base(query: str, k: int = 3) -> dict:
    """RAG lookup over the incident-response runbooks."""
    chunks = kb_retrieve(query, k=k)
    return {
        "count": len(chunks),
        "results": [{"source": c.source, "text": c.text, "score": c.score} for c in chunks],
    }


def query_database(nl_query: str) -> dict:
    """NL2SQL over system_telemetry.db, with graceful degradation for
    out-of-scope questions."""
    result = _nl2sql_query(nl_query)
    return {
        "success": result.success,
        "sql": result.sql,
        "rows": result.rows,
        "message": result.message,
    }
