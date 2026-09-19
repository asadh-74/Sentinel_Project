"""
orchestrator/state.py
-----------------------
The state threaded through every node of the LangGraph circular workflow:
Monitor -> Diagnose -> Remediate -> Verify -> (retry to Diagnose | END).
"""
from typing import List, Optional
from typing_extensions import TypedDict


class SentinelState(TypedDict):
    # Set by Monitor
    server_id: Optional[str]
    anomaly_detected: bool
    anomaly_summary: Optional[str]

    # Set by Diagnose
    root_cause: Optional[str]
    recommended_action: Optional[str]

    # Set by Remediate
    remediation_command: Optional[str]
    remediation_result: Optional[dict]

    # Set by Verify
    verification_passed: Optional[bool]

    # Loop control
    retry_count: int
    max_retries: int

    # Audit trail — every node appends a line here
    agent_logs: List[str]

    # Final human-readable status
    final_status: Optional[str]
