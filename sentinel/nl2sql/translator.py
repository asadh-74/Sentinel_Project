"""
nl2sql/translator.py
---------------------
Backs the Data Intelligence Agent / query_database() MCP tool.

Design:
  1. Scope check — reject (gracefully) anything that clearly has nothing
     to do with the schema, e.g. "What is the CEO's favorite color?".
     This runs BEFORE any SQL is generated so we never hallucinate a
     query for an unanswerable question.
  2. Translate — ask the LLM for a single read-only SQL statement, given
     the exact schema. If no LLM is configured, fall back to a small
     deterministic pattern-matcher covering common questions so the demo
     still works offline.
  3. Execute safely — only SELECT is ever allowed to run. Anything else
     (even if the LLM produces it) is rejected before touching the DB.
"""
from __future__ import annotations
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from data.schema import SCHEMA_DESCRIPTION, SCHEMA_VOCABULARY, get_connection
from llm.client import chat, get_chat_model

FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|attach|pragma|create)\b", re.IGNORECASE
)


@dataclass
class QueryResult:
    success: bool
    sql: str | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    message: str = ""


def _in_scope(nl_query: str) -> bool:
    words = set(re.findall(r"[a-zA-Z']+", nl_query.lower()))
    return len(words & SCHEMA_VOCABULARY) > 0


def _extract_sql(llm_output: str) -> str:
    """LLMs love wrapping SQL in markdown fences — strip that off."""
    text = llm_output.strip()
    fence = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    # If the model added prose, keep only the first statement-looking line block.
    if ";" in text:
        text = text.split(";")[0] + ";"
    return text.strip()


def _llm_translate(nl_query: str) -> str | None:
    if get_chat_model() is None:
        return None
    system = (
        "You translate natural-language questions into a single read-only "
        "SQLite SELECT statement. Only use the schema given. If the question "
        "cannot be answered with this schema, reply with exactly: NOT_APPLICABLE"
    )
    prompt = f"{SCHEMA_DESCRIPTION}\n\nQuestion: {nl_query}\n\nSQL:"
    output = chat(prompt, system=system)
    if "NOT_APPLICABLE" in output.upper():
        return None
    return _extract_sql(output)


# --- Offline fallback: a small, honest set of patterns. Anything that
# doesn't match falls through to the graceful-degradation path rather
# than guessing. ---------------------------------------------------------
_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bhow many\b.*\bactive\b.*\bserver", re.I),
     "SELECT COUNT(*) AS active_servers FROM servers WHERE status = 'ACTIVE';"),
    (re.compile(r"\bhow many\b.*\bserver", re.I),
     "SELECT COUNT(*) AS total_servers FROM servers;"),
    (re.compile(r"\bhigh cpu\b|\bcpu\b.*\b(over|above|>)\s*(\d+)", re.I),
     "SELECT server_id, hostname, cpu_usage_percent FROM servers WHERE cpu_usage_percent > 80 ORDER BY cpu_usage_percent DESC;"),
    (re.compile(r"\bhigh memory\b|\bmemory\b.*\b(over|above|>)\s*(\d+)", re.I),
     "SELECT server_id, hostname, memory_usage_percent FROM servers WHERE memory_usage_percent > 80 ORDER BY memory_usage_percent DESC;"),
    (re.compile(r"\berror\b.*\blog", re.I),
     "SELECT log_id, server_id, timestamp, service_name, message FROM logs WHERE log_level = 'ERROR' ORDER BY timestamp DESC LIMIT 20;"),
    (re.compile(r"\bopen\b.*\bincident", re.I),
     "SELECT incident_id, server_id, opened_at, symptom, status FROM incidents WHERE status = 'OPEN';"),
    (re.compile(r"\bincident", re.I),
     "SELECT incident_id, server_id, opened_at, closed_at, symptom, status FROM incidents ORDER BY opened_at DESC;"),
    (re.compile(r"\bregion\b", re.I),
     "SELECT region, COUNT(*) AS server_count FROM servers GROUP BY region;"),
    (re.compile(r"\bstatus\b.*\bserver|\bserver\b.*\bstatus", re.I),
     "SELECT server_id, hostname, status FROM servers;"),
    (re.compile(r"\ball server", re.I),
     "SELECT * FROM servers;"),
]


def _pattern_translate(nl_query: str) -> str | None:
    for pattern, sql in _PATTERNS:
        if pattern.search(nl_query):
            return sql
    return None


def translate(nl_query: str) -> str | None:
    sql = _llm_translate(nl_query)
    if sql:
        return sql
    return _pattern_translate(nl_query)


def _execute(sql: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]


def query_database(nl_query: str) -> QueryResult:
    """The full pipeline: scope check -> translate -> safety check -> execute.

    Never raises on a bad/out-of-scope question — always returns a
    QueryResult the caller can present to the user directly.
    """
    if not _in_scope(nl_query):
        return QueryResult(
            success=False,
            message=(
                "That's outside what I can answer from the telemetry database. "
                "I can only answer questions about servers (status, CPU/memory, "
                "region), logs, and incidents. Try rephrasing around one of those."
            ),
        )

    sql = translate(nl_query)
    if not sql:
        return QueryResult(
            success=False,
            message=(
                "I understood this relates to the telemetry schema, but couldn't "
                "confidently translate it into a safe SQL query. Could you be more "
                "specific (e.g. name a server_id, log level, or status)?"
            ),
        )

    if FORBIDDEN_SQL.search(sql) or not sql.strip().lower().startswith("select"):
        return QueryResult(
            success=False,
            sql=sql,
            message="Refused: only read-only SELECT queries are permitted.",
        )

    try:
        rows = _execute(sql)
    except sqlite3.Error as e:
        return QueryResult(success=False, sql=sql, message=f"SQL execution error: {e}")

    return QueryResult(success=True, sql=sql, rows=rows, message=f"{len(rows)} row(s) returned.")
