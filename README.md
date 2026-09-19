# Sentinel

Sentinel is an AI-driven orchestration and telemetry analysis system designed for automated IT operations and incident response. It leverages large language models (LLMs), retrieval-augmented generation (RAG), and multi-agent workflows to monitor system health, diagnose issues, and generate automated post-mortem reports.

## Architecture & Features

* **Agentic Orchestrator (`sentinel/orchestrator/`)**: Manages the state and execution graph of the system workflows.
* **Multi-Agent Crew (`sentinel/agents/`)**: Specialized AI agents equipped with custom tools for system diagnosis.
* **Knowledge Base & RAG (`sentinel/knowledge_base/`)**: Automated retrieval system containing documentation for diagnosing high CPU usage, high memory usage, disk/network issues, and authentication service errors.
* **Natural Language to SQL (`sentinel/nl2sql/`)**: Translates natural language queries into SQL to interact with the system telemetry database.
* **MCP Server (`sentinel/mcp_server/`)**: Exposes system tools and context via the Model Context Protocol (MCP).
* **Safety Guardrails (`sentinel/guardrails/`)**: Built-in safety and validation layers to ensure secure agent operations.
* **Automated Reporting (`sentinel/reports/`)**: Generates structured `.docx` post-mortem reports after incident resolution.

## Setup

1. **Environment Variables:** Copy `.env.example` to `.env` and configure your LLM API keys and database credentials.
2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
