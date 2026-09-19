"""
orchestrator/graph.py
-----------------------
The LangGraph circular workflow required by the spec:

    Monitor -> Diagnose -> Remediate -> Verify
                 ^                        |
                 |________ retry _________|   (if Verify fails, retry_count < max_retries)

Verify failing after max_retries routes to END with final_status="ESCALATED"
rather than looping forever.

Each node does two things:
  1. Calls the real Sentinel tool(s) via mcp_server/tools.py — this is the
     part that actually reads logs, retrieves runbooks, executes
     (simulated) remediation, and re-checks metrics. This always runs,
     with or without an LLM configured.
  2. If an LLM is configured, additionally asks the matching CrewAI agent
     (agents/crew.py) to reason over the tool output and produce a short
     natural-language decision/summary, which is folded into agent_logs.
     Without an LLM, a plain rule-based summary is used instead — the
     control flow and the underlying tool calls are identical either way,
     so the graph itself is fully testable offline.
"""
from __future__ import annotations
import os
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from orchestrator.state import SentinelState
from data.schema import get_connection
from mcp_server import tools as impl

ANOMALY_CPU_THRESHOLD = 80.0
ANOMALY_MEM_THRESHOLD = 80.0


def _llm_available() -> bool:
    has_key = bool(
        os.getenv("OPENROUTER_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    )
    return has_key and os.getenv("SENTINEL_FORCE_MOCK") != "1"


def _agent_reasoning(role: str, task_description: str) -> str | None:
    """Best-effort: run a single-task CrewAI crew for `role` and return its
    text output. Returns None (caller falls back to a rule-based summary)
    if no LLM is configured or CrewAI/the LLM call fails for any reason —
    this keeps the graph's control flow resilient to missing credentials."""
    if not _llm_available():
        return None
    try:
        from crewai import Task, Crew, Process
        from agents.crew import (
            build_monitor_agent,
            build_diagnostician_agent,
            build_remediation_agent,
        )

        builders = {
            "monitor": build_monitor_agent,
            "diagnostician": build_diagnostician_agent,
            "remediation": build_remediation_agent,
        }
        agent = builders[role]()
        task = Task(description=task_description, expected_output="A concise summary.", agent=agent)
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
        result = crew.kickoff()
        return str(result)
    except Exception as e:  # pragma: no cover - defensive, keeps demo offline-safe
        return f"[agent reasoning unavailable: {e}]"


# --------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------

def monitor_node(state: SentinelState) -> dict:
    with get_connection() as conn:
        servers = [dict(r) for r in conn.execute("SELECT * FROM servers").fetchall()]

    anomalous = [
        s for s in servers
        if s["cpu_usage_percent"] >= ANOMALY_CPU_THRESHOLD
        or s["memory_usage_percent"] >= ANOMALY_MEM_THRESHOLD
        or s["status"] != "ACTIVE"
    ]

    logs = list(state.get("agent_logs", []))
    if not anomalous:
        logs.append("Monitor: no anomalies detected across monitored servers.")
        return {"anomaly_detected": False, "agent_logs": logs, "final_status": "HEALTHY"}

    target = anomalous[0]
    error_logs = impl.get_system_logs(server_id=target["server_id"], log_level="ERROR", limit=10)
    summary = (
        f"Server {target['server_id']} ({target['hostname']}): CPU={target['cpu_usage_percent']}%, "
        f"MEM={target['memory_usage_percent']}%, status={target['status']}, "
        f"recent ERROR logs={error_logs['count']}."
    )

    reasoning = _agent_reasoning(
        "monitor",
        f"Review this telemetry snapshot and confirm whether it is an anomaly worth "
        f"escalating: {summary}",
    )
    logs.append(f"Monitor: anomaly detected -> {summary}" + (f" | Agent: {reasoning}" if reasoning else ""))

    return {
        "server_id": target["server_id"],
        "anomaly_detected": True,
        "anomaly_summary": summary,
        "agent_logs": logs,
    }


def diagnose_node(state: SentinelState) -> dict:
    logs = list(state["agent_logs"])
    kb = impl.query_knowledge_base(state["anomaly_summary"] or "system anomaly", k=1)

    if kb["count"] == 0:
        root_cause = "No matching runbook found."
        action = "restart_service"  # safe default
    else:
        top = kb["results"][0]
        root_cause = f"Likely per runbook '{top['source']}' (score={top['score']:.2f})."
        # naive extraction of the recommended command from the runbook text
        action = "system_reboot" if "reboot" in top["text"].lower() and "high-risk" not in top["text"].lower() else "restart_service"

    reasoning = _agent_reasoning(
        "diagnostician",
        f"Given anomaly '{state['anomaly_summary']}' and runbook match '{root_cause}', "
        f"recommend a single remediation command.",
    )
    logs.append(f"Diagnostician: {root_cause} Recommended action: {action}." + (f" | Agent: {reasoning}" if reasoning else ""))

    return {"root_cause": root_cause, "recommended_action": action, "agent_logs": logs}


def remediate_node(state: SentinelState) -> dict:
    logs = list(state["agent_logs"])
    command = state["recommended_action"] or "restart_service"
    server_id = state["server_id"]

    result = impl.execute_system_command(command=command, server_id=server_id)

    reasoning = _agent_reasoning(
        "remediation",
        f"Report the outcome of running '{command}' on {server_id}: {result}.",
    )
    logs.append(f"Remediation: ran '{command}' on {server_id} -> {result}." + (f" | Agent: {reasoning}" if reasoning else ""))

    return {"remediation_command": command, "remediation_result": result, "agent_logs": logs}


def verify_node(state: SentinelState) -> dict:
    logs = list(state["agent_logs"])
    server_id = state["server_id"]

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM servers WHERE server_id = ?", (server_id,)).fetchone()

    healthy = row is not None and row["cpu_usage_percent"] < ANOMALY_CPU_THRESHOLD and row["memory_usage_percent"] < ANOMALY_MEM_THRESHOLD

    if healthy:
        logs.append(f"Verify: {server_id} back within normal thresholds. Incident resolved.")
        with get_connection() as conn:
            conn.execute(
                "UPDATE incidents SET status='RESOLVED', closed_at=datetime('now') "
                "WHERE server_id=? AND status='OPEN'",
                (server_id,),
            )
            conn.commit()
        return {"verification_passed": True, "agent_logs": logs, "final_status": "RESOLVED"}

    logs.append(f"Verify: {server_id} still anomalous after remediation.")
    return {"verification_passed": False, "agent_logs": logs}


def route_after_verify(state: SentinelState) -> str:
    if state.get("verification_passed"):
        return "resolved"
    if state["retry_count"] < state["max_retries"]:
        return "retry"
    return "escalate"


def bump_retry_node(state: SentinelState) -> dict:
    logs = list(state["agent_logs"])
    new_count = state["retry_count"] + 1
    logs.append(f"Orchestrator: verification failed, retrying diagnosis (attempt {new_count}/{state['max_retries']}).")
    return {"retry_count": new_count, "agent_logs": logs}


def escalate_node(state: SentinelState) -> dict:
    logs = list(state["agent_logs"])
    logs.append(f"Orchestrator: max retries ({state['max_retries']}) exhausted. Escalating to human operator.")
    with get_connection() as conn:
        conn.execute(
            "UPDATE incidents SET status='ESCALATED' WHERE server_id=? AND status='OPEN'",
            (state["server_id"],),
        )
        conn.commit()
    return {"agent_logs": logs, "final_status": "ESCALATED"}


# --------------------------------------------------------------------------
# Graph assembly
# --------------------------------------------------------------------------

def build_graph():
    builder = StateGraph(SentinelState)

    builder.add_node("monitor", monitor_node)
    builder.add_node("diagnose", diagnose_node)
    builder.add_node("remediate", remediate_node)
    builder.add_node("verify", verify_node)
    builder.add_node("bump_retry", bump_retry_node)
    builder.add_node("escalate", escalate_node)

    builder.add_edge(START, "monitor")

    builder.add_conditional_edges(
        "monitor",
        lambda s: "diagnose" if s["anomaly_detected"] else "end",
        {"diagnose": "diagnose", "end": END},
    )

    builder.add_edge("diagnose", "remediate")
    builder.add_edge("remediate", "verify")

    builder.add_conditional_edges(
        "verify",
        route_after_verify,
        {"resolved": END, "retry": "bump_retry", "escalate": "escalate"},
    )

    builder.add_edge("bump_retry", "diagnose")
    builder.add_edge("escalate", END)

    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


def run_sentinel(thread_id: str = "sentinel-session", max_retries: int = 2) -> SentinelState:
    graph = build_graph()
    initial_state: SentinelState = {
        "server_id": None,
        "anomaly_detected": False,
        "anomaly_summary": None,
        "root_cause": None,
        "recommended_action": None,
        "remediation_command": None,
        "remediation_result": None,
        "verification_passed": None,
        "retry_count": 0,
        "max_retries": max_retries,
        "agent_logs": [],
        "final_status": None,
    }
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(initial_state, config=config)
