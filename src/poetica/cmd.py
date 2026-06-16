"""Poetica cmd — NL to gated shell commands.

NL text → intent IR → gate → argv → dry-run or execute → receipt.
"""

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from poetica.gate import Gate, GateError, GateDecision
from poetica.intent import Intent, IntentError, parse_intent


@dataclass
class CmdReceipt:
    """Receipt for a cmd operation."""
    original_text: str
    parsed_intent: str
    emitted_command: List[str]
    gate_level: int
    gate_decision: str
    approved: bool
    executed: bool
    exit_code: Optional[int] = None
    stdout_hash: str = ""
    stderr_hash: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        d = {
            "schema": "poetica.cmd.receipt.v1",
            "original_text": self.original_text,
            "parsed_intent": self.parsed_intent,
            "emitted_command": self.emitted_command,
            "gate_level": self.gate_level,
            "gate_decision": self.gate_decision,
            "approved": self.approved,
            "executed": self.executed,
            "timestamp": self.timestamp,
        }
        if self.executed:
            d["exit_code"] = self.exit_code
            d["stdout_hash"] = self.stdout_hash
            d["stderr_hash"] = self.stderr_hash
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def run_cmd(text: str, level: int = 1, approve: bool = False,
            yes: bool = False) -> CmdReceipt:
    """Full pipeline: NL text → intent → gate → execute/dry-run → receipt.

    Args:
        text: Natural language command.
        level: Gate level (1-5).
        approve: If True, execute the command. If False, dry-run only.
        yes: If True, add -y to apt commands.

    Returns:
        CmdReceipt with full audit trail.
    """
    # Parse intent
    intent = parse_intent(text, yes=yes)

    # Gate check — build a synthetic IR op for the gate
    gate = Gate(level=level, allow_external=(level >= 4))
    # Map intent ops to gate ops: package.* and fs.* → use (L4) or emit (L1)
    gate_op = "use" if intent.level >= 4 else "emit"
    op_spec = {"op": gate_op, "tool": intent.op}
    decision = gate._check_op(op_spec)

    if decision.verdict == "REJECT":
        return CmdReceipt(
            original_text=text,
            parsed_intent=intent.op,
            emitted_command=intent.argv,
            gate_level=intent.level,
            gate_decision="REJECT",
            approved=False,
            executed=False,
        )

    # Dry-run: gate passed but not approved
    if not approve:
        return CmdReceipt(
            original_text=text,
            parsed_intent=intent.op,
            emitted_command=intent.argv,
            gate_level=intent.level,
            gate_decision="ALLOW",
            approved=False,
            executed=False,
        )

    # Execute — argv list only, never shell=True
    result = subprocess.run(
        intent.argv,
        capture_output=True,
        timeout=60,
    )

    return CmdReceipt(
        original_text=text,
        parsed_intent=intent.op,
        emitted_command=intent.argv,
        gate_level=intent.level,
        gate_decision="ALLOW",
        approved=True,
        executed=True,
        exit_code=result.returncode,
        stdout_hash=hashlib.sha256(result.stdout).hexdigest(),
        stderr_hash=hashlib.sha256(result.stderr).hexdigest(),
    )
