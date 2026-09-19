# Sentinel — The Autonomous System Health Guardian (v2.0)

An intelligent monitoring agent system for a cloud-native platform. Sentinel
watches server telemetry, diagnoses anomalies against a runbook knowledge
base, remediates them (safely, with guardrails), verifies the fix, and
retries or escalates as needed — while also acting as a natural-language
interface onto the platform's operational database.

## Architecture

```
diagrams/sentinel_workflow.png   — full agent hierarchy + LangGraph state diagram
```

- **4 CrewAI agents** (`agents/crew.py`): Monitor, Diagnostician, Remediation,
  Data Intelligence — each with exactly the tools its role needs.
- **1 MCP server** (`mcp_server/server.py`): the *only* entry point into logs,
  command execution, the knowledge base, and the SQL database. Both CrewAI
  and any other MCP client hit the same four tools:
  `get_system_logs`, `execute_system_command`, `query_knowledge_base`,
  `query_database`.
- **1 LangGraph orchestrator** (`orchestrator/graph.py`): the circular
  self-healing loop — `Monitor → Diagnose → Remediate → Verify`, looping
  back to Diagnose on a failed verification (up to `max_retries`), then
  escalating to a human.
- **NL2SQL** (`nl2sql/translator.py`): LLM-based translation with a
  graceful-degradation scope check, so out-of-schema questions ("What's the
  CEO's favorite color?") are declined instead of hallucinated.
- **RAG knowledge base** (`knowledge_base/`): incident runbooks retrieved via
  TF-IDF offline by default, or FAISS + real embeddings once an API key is
  configured.
- **Safety guardrails** (`guardrails/safety.py`): blocks high-risk commands
  (e.g. `system_reboot`) against any server under critical database load.

## Why it runs with zero API keys

Every piece that can be meaningfully tested without an LLM — the guardrails,
NL2SQL scope-checking and SQL execution, RAG retrieval, the LangGraph state
machine and its retry/escalate routing — has a fully offline path. Add an
LLM key and the same graph nodes additionally ask the matching CrewAI agent
to narrate/reason over the same tool output; the control flow doesn't change.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # optional: add GROQ_API_KEY or OPENAI_API_KEY
python main.py setup        # creates the incidents table + seed data
```

## Usage

```bash
# Run one full Monitor -> Diagnose -> Remediate -> Verify cycle
python main.py demo

# Ask the Data Intelligence Agent a question
python main.py query "are there any servers with high memory usage?"
python main.py query "what is the CEO's favorite color?"   # graceful decline

# Start the MCP server (stdio transport) for an external MCP client
python main.py mcp
```

## Project layout

```
sentinel/
├── data/
│   ├── system_telemetry.db     # provided data pack (+ incidents table added by setup_db.py)
│   ├── setup_db.py
│   └── schema.py                # single source of truth for the DB schema
├── knowledge_base/
│   ├── docs/                    # incident-response runbooks (markdown)
│   └── rag.py                   # TF-IDF (offline) / FAISS (LLM) retriever
├── nl2sql/
│   └── translator.py            # scope check -> LLM/pattern translate -> safe execute
├── guardrails/
│   └── safety.py                # high-risk command / critical-load gate
├── llm/
│   └── client.py                # Groq/OpenAI-compatible client with offline mock
├── mcp_server/
│   ├── tools.py                 # the 4 tool implementations (single source of truth)
│   └── server.py                # FastMCP server exposing them
├── agents/
│   ├── tools.py                 # CrewAI BaseTool wrappers around mcp_server/tools.py
│   └── crew.py                  # the 4 CrewAI agents + a standalone NL2SQL crew
├── orchestrator/
│   ├── state.py                 # LangGraph state schema
│   └── graph.py                 # the circular self-healing workflow
├── diagrams/
│   └── sentinel_workflow.png    # visual workflow deliverable
├── reports/                      # post-mortem report lives here (see project root)
├── main.py                       # CLI
├── requirements.txt
└── .env.example
```

## Deliverables checklist (per spec)

- [x] Multi-Agent System — 4 CrewAI agents (`agents/crew.py`)
- [x] NL2SQL interface with graceful degradation (`nl2sql/translator.py`)
- [x] LangGraph circular workflow with retry loop (`orchestrator/graph.py`)
- [x] MCP server as sole entry point, 4 tools (`mcp_server/server.py`)
- [x] Safety guardrails against high-risk commands under critical load (`guardrails/safety.py`)
- [x] Visual workflow diagram (`diagrams/sentinel_workflow.png`)
- [x] Post-Mortem Report simulating an outage (`Sentinel_PostMortem_Report.docx`)
- [ ] LangSmith tracing screenshot — requires a live LangSmith project + API
      key tied to a real account, which this environment doesn't have. Set
      `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` in `.env` and every
      `python main.py query "..."` / `demo` run will show up in your
      LangSmith dashboard for the screenshot.
