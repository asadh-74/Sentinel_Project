"""
mcp_server/server.py
---------------------
Sentinel's MCP Server — per the spec, THE ONLY entry point agents use to
touch logs, execute commands, query the knowledge base, or query the SQL
database. Agents never import data/schema.py, guardrails/safety.py, etc.
directly in a real deployment; they go through this server's tools.

Run:
    python -m mcp_server.server            # stdio transport (for MCP clients)

Requires the `mcp` package: pip install mcp
"""
from mcp.server.fastmcp import FastMCP

from mcp_server import tools as impl

mcp = FastMCP("sentinel")


@mcp.tool()
def get_system_logs(server_id: str | None = None, log_level: str | None = None, limit: int = 50) -> dict:
    """Fetch recent system logs, optionally filtered by server_id
    (e.g. 'SRV-002') and/or log_level ('INFO'|'WARN'|'ERROR')."""
    return impl.get_system_logs(server_id=server_id, log_level=log_level, limit=limit)


@mcp.tool()
def execute_system_command(command: str, server_id: str) -> dict:
    """Execute a remediation command against a server (READ-ONLY / SIMULATED
    in this environment). High-risk commands (e.g. 'system_reboot') are
    automatically blocked if the target is under critical database load —
    the call will report executed=False with a reason instead of raising."""
    return impl.execute_system_command(command=command, server_id=server_id)


@mcp.tool()
def query_knowledge_base(query: str, k: int = 3) -> dict:
    """Semantic search over the incident-response runbook knowledge base.
    Returns the top-k most relevant runbook sections for a symptom
    description (e.g. 'high memory usage on database host')."""
    return impl.query_knowledge_base(query=query, k=k)


@mcp.tool()
def query_database(nl_query: str) -> dict:
    """Translate a natural-language question about infrastructure health
    into SQL and run it against system_telemetry.db. Gracefully reports
    when a question is outside the schema's scope instead of guessing."""
    return impl.query_database(nl_query=nl_query)


if __name__ == "__main__":
    mcp.run(transport="stdio")
