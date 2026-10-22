import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
from agent.celesto_client import CelestoSandbox

class RecoveryManager:
    """
    Manages recovery strategies when an agent encounters mid-task failures
    (specifically step 7 of 10 in workflow execution).
    Supports 'rollback' (to pre-step checkpoint snapshot), 'resume', and 'fresh'.
    """
    def __init__(self, policy: str = "rollback", trace_path: str = "reports/failure_trace.jsonl"):
        self.policy = policy
        self.trace_path = Path(trace_path)
        self.trace_events: List[Dict[str, Any]] = []

    def record_event(self, event_type: str, details: Dict[str, Any]):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            **details,
        }
        self.trace_events.append(entry)
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.trace_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def execute_workflow_with_recovery(self, sandbox: CelestoSandbox):
        """
        Executes a 10-step agent workflow where Step 7 deliberately triggers a failure
        to demonstrate recovery policy handling and trace logging.
        """
        self.record_event("workflow_started", {"total_steps": 10, "sandbox_name": sandbox.name})

        # Steps 1 to 6
        for step in range(1, 7):
            sandbox.run(f"echo 'Executing step {step}'")
            self.record_event("step_completed", {"step": step})

        # Checkpoint state prior to risky step
        snapshot_id = sandbox.snapshot("checkpoint-step-6")
        self.record_event("snapshot_created", {"snapshot_id": snapshot_id, "step": 6})

        # Step 7 fails
        self.record_event("step_failed", {
            "step": 7,
            "error": "DependencyConflictError: incompatible binary package detected during test suite execution",
        })

        # Apply recovery policy
        if self.policy == "rollback":
            sandbox.restore(snapshot_id)
            self.record_event("policy_applied", {
                "policy": "rollback",
                "target_snapshot": snapshot_id,
                "action": "Restored guest filesystem and RAM to clean pre-step-6 state",
            })
            # Re-execute with adjusted strategy
            sandbox.run("echo 'Re-executing step 7 with pinned dependencies'")
            self.record_event("step_completed", {"step": 7, "recovered": True})
        elif self.policy == "resume":
            self.record_event("policy_applied", {
                "policy": "resume",
                "action": "Retrying step 7 without state reset",
            })
            sandbox.run("echo 'Resuming step 7'")
            self.record_event("step_completed", {"step": 7, "recovered": True})
        elif self.policy == "fresh":
            self.record_event("policy_applied", {
                "policy": "fresh",
                "action": "Deleting current sandbox and starting completely fresh instance",
            })
            sandbox.delete()
            self.record_event("fresh_sandbox_started", {"action": "Rebuilding from ground zero"})

        # Steps 8 to 10
        for step in range(8, 11):
            sandbox.run(f"echo 'Executing step {step}'")
            self.record_event("step_completed", {"step": step})

        self.record_event("workflow_completed", {"status": "success", "steps_executed": 10})
