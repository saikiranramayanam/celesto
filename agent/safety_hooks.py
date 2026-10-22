import json
import re
from datetime import datetime, timezone
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOGS_DIR / "commands.jsonl"

# Malicious patterns to block
BLOCKED_PATTERNS = [
    re.compile(r"rm\s+-rf\s+[/~]", re.IGNORECASE),
    re.compile(r"curl.*(\$API_KEY|\$CELESTO_API_KEY|\$LLM_API_KEY|\.env)", re.IGNORECASE),
    re.compile(r"wget.*(\$API_KEY|\$CELESTO_API_KEY|\$LLM_API_KEY|\.env)", re.IGNORECASE),
    re.compile(r"cat\s+.*\.env", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE), # fork bomb
    re.compile(r"mkfs\.", re.IGNORECASE),
    re.compile(r"dd\s+if=/dev/zero", re.IGNORECASE),
]

class CommandBlockedError(Exception):
    """Raised when a command is blocked by Celesto safety hooks."""
    pass

def audit_log_command(sandbox_name: str, command: str, decision: str):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "sandbox_name": sandbox_name,
        "command": command.strip(),
        "decision": decision,
        "execution_target": "celesto_sandbox",
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry

def pre_command_safety_hook(sandbox_name: str, command: str) -> bool:
    """
    Evaluates commands prior to guest execution.
    Logs every attempt to logs/commands.jsonl.
    Blocks destructive attacks or prompt-injected secret exfiltration.
    """
    for pattern in BLOCKED_PATTERNS:
        if pattern.search(command):
            audit_log_command(sandbox_name, command, decision="block")
            raise CommandBlockedError(f"SafetyHook blocked dangerous command: {command}")

    audit_log_command(sandbox_name, command, decision="allow")
    return True
