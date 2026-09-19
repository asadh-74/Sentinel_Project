"""
main.py
-------
Sentinel CLI. Run without any API keys configured — it will use the
offline TF-IDF RAG backend, the pattern-matching NL2SQL fallback, and skip
LLM-based agent narration (control flow and tool execution are identical
either way). Add GROQ_API_KEY or OPENAI_API_KEY to .env for full
LLM-reasoned agent output.

Usage:
    python main.py setup                 # create the incidents table / seed data
    python main.py demo                  # run one full self-healing loop
    python main.py query "<question>"    # ask the Data Intelligence Agent something
    python main.py mcp                   # start the MCP server (stdio)
"""
import sys
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def cmd_setup():
    from data.setup_db import setup
    setup()


def cmd_demo():
    from orchestrator.graph import run_sentinel

    print("=" * 70)
    print("SENTINEL — Autonomous System Health Guardian")
    print("Running one Monitor -> Diagnose -> Remediate -> Verify cycle...")
    print("=" * 70)

    final = run_sentinel(max_retries=2)

    print()
    print(f"FINAL STATUS : {final['final_status']}")
    print(f"SERVER       : {final.get('server_id')}")
    print(f"RETRIES USED : {final['retry_count']} / {final['max_retries']}")
    print()
    print("Agent log trail:")
    for line in final["agent_logs"]:
        print(f"  - {line}")


def cmd_query(nl_query: str):
    from mcp_server.tools import query_database

    result = query_database(nl_query)
    print(f"Question : {nl_query}")
    print(f"SQL      : {result['sql']}")
    print(f"Message  : {result['message']}")
    if result["rows"]:
        print("Rows     :")
        print(json.dumps(result["rows"], indent=2))


def cmd_mcp():
    from mcp_server.server import mcp
    mcp.run(transport="stdio")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command, *rest = sys.argv[1:]

    if command == "setup":
        cmd_setup()
    elif command == "demo":
        cmd_demo()
    elif command == "query":
        if not rest:
            print("Usage: python main.py query \"<your question>\"")
            return
        cmd_query(" ".join(rest))
    elif command == "mcp":
        cmd_mcp()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
