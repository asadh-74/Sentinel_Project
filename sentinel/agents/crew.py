"""
agents/crew.py
----------------
Defines Sentinel's four specialized CrewAI agents. These agents are used
two ways:

  1. Standalone, via `data_intelligence_crew()` — a normal CrewAI Crew you
     can `.kickoff()` for ad-hoc natural-language questions.
  2. As reasoning units inside the LangGraph loop (see orchestrator/graph.py)
     — each graph node builds a single-task Crew for its agent and runs it,
     so CrewAI owns "how a role thinks" while LangGraph owns "what happens
     next" (the circular Monitor -> Diagnose -> Remediate -> Verify control
     flow, including retries).

All four agents only reach the outside world through the Sentinel tool
wrappers in agents/tools.py, which in turn call the exact same functions
the MCP server exposes.
"""
from crewai import Agent, Task, Crew, Process

from agents.tools import (
    GetSystemLogsTool,
    ExecuteSystemCommandTool,
    QueryKnowledgeBaseTool,
    QueryDatabaseTool,
)

get_logs_tool = GetSystemLogsTool()
execute_command_tool = ExecuteSystemCommandTool()
query_kb_tool = QueryKnowledgeBaseTool()
query_db_tool = QueryDatabaseTool()


def build_monitor_agent() -> Agent:
    return Agent(
        role="Monitor Agent",
        goal=(
            "Continuously parse system logs and telemetry to detect anomalies "
            "(elevated ERROR rates, CPU/memory over 80%, degraded server status) "
            "and produce a precise, factual anomaly summary."
        ),
        backstory=(
            "A vigilant SRE-in-software-form. You never speculate about causes — "
            "that's the Diagnostician's job. You only report what the data shows: "
            "which server, which metric, which threshold was crossed."
        ),
        tools=[get_logs_tool],
        verbose=True,
        allow_delegation=False,
    )


def build_diagnostician_agent() -> Agent:
    return Agent(
        role="Diagnostician Agent",
        goal=(
            "Given an anomaly summary, consult the incident-response knowledge "
            "base (RAG) to determine the most likely root cause and the "
            "recommended remediation."
        ),
        backstory=(
            "A seasoned troubleshooter who has read every runbook cover to "
            "cover. You ground every diagnosis in a retrieved runbook passage "
            "rather than guessing, and you say so explicitly when evidence is thin."
        ),
        tools=[query_kb_tool, get_logs_tool],
        verbose=True,
        allow_delegation=False,
    )


def build_remediation_agent() -> Agent:
    return Agent(
        role="Remediation Agent",
        goal=(
            "Execute the recommended remediation safely, respecting all safety "
            "guardrails, then hand off for verification."
        ),
        backstory=(
            "Disciplined and risk-averse. You would rather escalate to a human "
            "than run a high-risk command against a server under critical load. "
            "You always report exactly what you ran and what the tool told you."
        ),
        tools=[execute_command_tool],
        verbose=True,
        allow_delegation=False,
    )


def build_data_intelligence_agent() -> Agent:
    return Agent(
        role="Data Intelligence Agent",
        goal=(
            "Answer natural-language questions from administrators about "
            "infrastructure health by querying system_telemetry.db, and "
            "decline gracefully when a question is outside that scope."
        ),
        backstory=(
            "The platform's SQL-fluent analyst. You never invent numbers — "
            "every answer is backed by a real query result, and you say so "
            "plainly when a question can't be answered from this database."
        ),
        tools=[query_db_tool],
        verbose=True,
        allow_delegation=False,
    )


def data_intelligence_crew(nl_query: str) -> Crew:
    """A minimal single-agent Crew for ad-hoc NL2SQL questions."""
    agent = build_data_intelligence_agent()
    task = Task(
        description=(
            f"Answer this administrator question using the query_database tool: "
            f"'{nl_query}'. Report the SQL you ran and summarize the results in "
            f"plain English. If it's out of scope, say so clearly."
        ),
        expected_output="A short, plain-English answer citing the SQL used (or a graceful decline).",
        agent=agent,
    )
    return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
