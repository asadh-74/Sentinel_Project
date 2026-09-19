"""
agents/tools.py
-----------------
CrewAI-facing wrappers around mcp_server/tools.py. These call the exact
same implementations the MCP server exposes — CrewAI just needs its own
BaseTool wrapper so agents can invoke them.
"""
from typing import Optional, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from mcp_server import tools as impl


class GetLogsArgs(BaseModel):
    server_id: Optional[str] = Field(None, description="e.g. 'SRV-001'; omit for all servers")
    log_level: Optional[str] = Field(None, description="'INFO' | 'WARN' | 'ERROR'")
    limit: int = Field(50, description="Max rows to return")


class GetSystemLogsTool(BaseTool):
    name: str = "get_system_logs"
    description: str = "Fetch recent telemetry logs, optionally filtered by server_id and/or log_level."
    args_schema: Type[BaseModel] = GetLogsArgs

    def _run(self, server_id: Optional[str] = None, log_level: Optional[str] = None, limit: int = 50) -> dict:
        return impl.get_system_logs(server_id=server_id, log_level=log_level, limit=limit)


class ExecuteCommandArgs(BaseModel):
    command: str = Field(..., description="e.g. 'restart_service' or 'system_reboot'")
    server_id: str = Field(..., description="Target server, e.g. 'SRV-002'")


class ExecuteSystemCommandTool(BaseTool):
    name: str = "execute_system_command"
    description: str = (
        "Execute a remediation command against a server (simulated). "
        "High-risk commands are automatically blocked during critical DB load."
    )
    args_schema: Type[BaseModel] = ExecuteCommandArgs

    def _run(self, command: str, server_id: str) -> dict:
        return impl.execute_system_command(command=command, server_id=server_id)


class KnowledgeBaseArgs(BaseModel):
    query: str = Field(..., description="Symptom description, e.g. 'high memory on db host'")
    k: int = Field(3, description="Number of runbook chunks to return")


class QueryKnowledgeBaseTool(BaseTool):
    name: str = "query_knowledge_base"
    description: str = "Search incident-response runbooks for likely root causes and remediations."
    args_schema: Type[BaseModel] = KnowledgeBaseArgs

    def _run(self, query: str, k: int = 3) -> dict:
        return impl.query_knowledge_base(query=query, k=k)


class QueryDatabaseArgs(BaseModel):
    nl_query: str = Field(..., description="A natural-language question about servers, logs, or incidents")


class QueryDatabaseTool(BaseTool):
    name: str = "query_database"
    description: str = (
        "Ask a natural-language question about infrastructure health; it is translated "
        "to SQL and run against system_telemetry.db. Out-of-scope questions are declined gracefully."
    )
    args_schema: Type[BaseModel] = QueryDatabaseArgs

    def _run(self, nl_query: str) -> dict:
        return impl.query_database(nl_query=nl_query)
