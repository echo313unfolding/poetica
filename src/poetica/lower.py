"""Poetica lowering layer — bridge Poetica IR to KRISPER IR.

Lowers high-level Poetica operation tokens (seed, emit, grow, bloom, etc.)
to KRISPER executable operations (print, compress, digest, etc.).

This is NOT an LLM tokenizer. These are compiler operation tokens:
canonical symbolic operations that an AI or human can safely compose,
which deterministic lowering then maps to runtime operations.

Stack:
    domain phrase → Poetica phrase → Poetica IR → operation tokens
    → KRISPER IR → MorphSAT gate → execution receipt

Safety:
    - No execution by default
    - Gate levels are preserved
    - Unsupported ops are recorded, not dropped
    - Both Poetica gate and KRISPER gate decisions are tracked
    - Output is auditable JSON
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from poetica.parser import PoeticaParser
from poetica.compiler import PoeticaCompiler
from poetica.gate import Gate, GateError


# ── Operation token categories ──────────────────────────────────────

# Maps Poetica ops to canonical operation token families
_OP_TOKEN_MAP = {
    # L1: Pure
    "seed":     "binding.assign",
    "emit":     "output.print",
    "flow":     "binding.assign",
    "bloom":    "output.return",
    "remember": "binding.persist",

    # L2: + Logic
    "when":     "control.if",
    "when_in":  "control.if_in",
    "if":       "control.if_eq",
    "else_when": "control.elif",
    "else":     "control.else",
    "for":      "control.for",

    # L3: + Transform
    "pack":     "transform.serialize",
    "grow":     "transform.append",
    "learn":    "transform.pattern",

    # L4: + External
    "lift":     "external.write",
    "use":      "external.tool",
}

# Poetica ops that have a direct KRISPER op mapping
_KRISPER_MAP = {
    "emit":     "print",
    "pack":     "write_json",   # pack as json → write_json
    "remember": "digest",       # persist → hash-based storage
}

# Poetica ops that lower to KRISPER variable bindings (not direct ops)
_BINDING_OPS = {"seed", "flow"}

# Control flow ops — KRISPER has no control flow, so these become metadata
_CONTROL_OPS = {"when", "when_in", "if", "else_when", "else", "for"}

# Ops that require KRISPER IO permission
_IO_REQUIRING = {"lift", "use", "pack"}


@dataclass
class OperationToken:
    """A single lowered operation token."""
    poetica_op: str
    operation_token: str
    krisper_op: Optional[str]
    inputs: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    level: int = 1
    status: str = "lowered"  # lowered | binding | control_metadata | unsupported
    indent: int = 0
    domain_provenance: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d["domain_provenance"] is None:
            del d["domain_provenance"]
        return d


@dataclass
class LoweringResult:
    """Complete result of lowering Poetica IR to operation tokens."""
    schema: str = "poetica.lower.v1"
    source_ir: str = "poetica-ir-v1"
    target_ir: str = "krisper-ir"
    program: str = "main"
    source_hash: str = ""
    gate_level: int = 1
    ops: List[OperationToken] = field(default_factory=list)
    unsupported: List[Dict[str, Any]] = field(default_factory=list)
    bindings: Dict[str, Any] = field(default_factory=dict)
    receipts: Dict[str, Any] = field(default_factory=lambda: {
        "poetica_gate": None,
        "krisper_gate": None,
    })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "source_ir": self.source_ir,
            "target_ir": self.target_ir,
            "program": self.program,
            "source_hash": self.source_hash,
            "gate_level": self.gate_level,
            "ops": [op.to_dict() for op in self.ops],
            "unsupported": self.unsupported,
            "bindings": self.bindings,
            "receipts": self.receipts,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_krisper_ir(self) -> Dict[str, Any]:
        """Generate KRISPER-compatible IR from lowered ops.

        Only includes ops that have a valid krisper_op mapping.
        Control flow and bindings are excluded (KRISPER doesn't support them).
        """
        plan = []
        out_counter = 0

        # Pre-populate variables from bindings
        for name, value in self.bindings.items():
            # Bindings become implicit — KRISPER resolves via variables dict
            pass

        for op in self.ops:
            if op.status != "lowered" or op.krisper_op is None:
                continue

            out_counter += 1
            krisper_op = {
                "op": op.krisper_op,
                "in": op.inputs,
                "out": f"result_{out_counter}",
            }
            if op.params:
                krisper_op["params"] = op.params
            plan.append(krisper_op)

        source_hash = self.source_hash or ""
        return {
            "version": "0.2",
            "metadata": {
                "source_hash": source_hash,
                "lowered_from": "poetica-ir-v1",
                "program": self.program,
                "gate_level": self.gate_level,
            },
            "plan": plan,
        }


def _op_level(op_name: str) -> int:
    """Return the minimum gate level for a Poetica op."""
    if op_name in ("seed", "emit", "flow", "bloom", "remember"):
        return 1
    if op_name in ("when", "when_in", "if", "else_when", "else", "for"):
        return 2
    if op_name in ("pack", "grow", "learn"):
        return 3
    if op_name in ("lift", "use"):
        return 4
    return 5


def lower(ir: Dict[str, Any], level: int = 1,
          domain_rewrites: Optional[List] = None) -> LoweringResult:
    """Lower Poetica IR to operation tokens.

    Args:
        ir: Poetica IR dict (from PoeticaCompiler.compile()).
        level: Gate level (1-5). Operations above this level are unsupported.
        domain_rewrites: Optional list of DomainRewrite records for provenance.

    Returns:
        LoweringResult with lowered ops, bindings, and unsupported list.
    """
    result = LoweringResult(
        program=ir.get("name") or "main",
        source_hash=ir.get("source_hash", ""),
        gate_level=level,
    )

    # Build domain provenance lookup by line content
    domain_lookup = {}
    if domain_rewrites:
        for rw in domain_rewrites:
            domain_lookup[rw.canonical_text.strip()] = {
                "original": rw.original_text,
                "canonical": rw.canonical_text,
                "domain": rw.domain,
                "concept": rw.domain_concept,
                "visual": rw.domain_visual,
                "rewrite_type": rw.rewrite_type,
            }

    # Run Poetica gate check
    try:
        gate = Gate(level=level, allow_external=(level >= 4))
        gate.check(ir)
        result.receipts["poetica_gate"] = "PASS"
    except GateError as e:
        result.receipts["poetica_gate"] = f"FAIL: {e}"

    # Lower each op
    for op in ir.get("ops", []):
        op_name = op.get("op", "")
        op_lvl = _op_level(op_name)
        token_name = _OP_TOKEN_MAP.get(op_name)

        if token_name is None:
            result.unsupported.append({
                "op": op_name,
                "reason": "unknown_op",
                "original": op,
            })
            continue

        # Check gate level
        if op_lvl > level:
            result.unsupported.append({
                "op": op_name,
                "operation_token": token_name,
                "reason": f"requires_level_{op_lvl}",
                "gate_level": level,
                "original": op,
            })
            continue

        # Find domain provenance for this op
        provenance = _find_provenance(op, domain_lookup)

        # Lower based on op type
        if op_name in _BINDING_OPS:
            token = _lower_binding(op, token_name, op_lvl, provenance)
            # Track the binding value
            if op_name == "seed":
                result.bindings[op["name"]] = op.get("value", "")
            elif op_name == "flow":
                result.bindings[op["dest"]] = op.get("source", "")
            result.ops.append(token)

        elif op_name in _CONTROL_OPS:
            token = _lower_control(op, token_name, op_lvl, provenance)
            result.ops.append(token)

        elif op_name == "emit":
            token = _lower_emit(op, token_name, op_lvl, result.bindings, provenance)
            result.ops.append(token)

        elif op_name == "bloom":
            token = _lower_bloom(op, token_name, op_lvl, result.bindings, provenance)
            result.ops.append(token)

        elif op_name == "remember":
            token = _lower_remember(op, token_name, op_lvl, provenance)
            result.ops.append(token)

        elif op_name == "pack":
            token = _lower_pack(op, token_name, op_lvl, provenance)
            result.ops.append(token)

        elif op_name == "grow":
            token = _lower_grow(op, token_name, op_lvl, provenance)
            result.ops.append(token)

        elif op_name == "learn":
            token = _lower_learn(op, token_name, op_lvl, provenance)
            result.ops.append(token)

        elif op_name == "lift":
            token = _lower_lift(op, token_name, op_lvl, provenance)
            result.ops.append(token)

        elif op_name == "use":
            token = _lower_use(op, token_name, op_lvl, provenance)
            result.ops.append(token)

        else:
            result.unsupported.append({
                "op": op_name,
                "operation_token": token_name,
                "reason": "no_lowering_handler",
                "original": op,
            })

    return result


def _find_provenance(op: Dict, domain_lookup: Dict) -> Optional[Dict[str, str]]:
    """Try to find domain provenance for a Poetica op."""
    if not domain_lookup:
        return None
    # Reconstruct the canonical line from the op to match against rewrites
    op_name = op.get("op", "")
    candidates = []
    if op_name == "seed":
        candidates.append(f"seed {op.get('name', '')} with {op.get('value', '')}")
    elif op_name == "emit":
        if op.get("label"):
            candidates.append(f'emit "{op["label"]}" {op.get("value", "")}')
        candidates.append(f"emit {op.get('value', '')}")
    elif op_name == "when":
        candidates.append(f"when {op.get('condition', '')}:")
    elif op_name == "flow":
        candidates.append(f"flow {op.get('source', '')} to {op.get('dest', '')}")
    elif op_name == "bloom":
        candidates.append(f"bloom {op.get('value', '')}")

    for c in candidates:
        if c.strip() in domain_lookup:
            return domain_lookup[c.strip()]
    return None


# ── Lowering handlers ───────────────────────────────────────────────

def _lower_binding(op: Dict, token: str, level: int,
                   provenance: Optional[Dict]) -> OperationToken:
    op_name = op["op"]
    if op_name == "seed":
        return OperationToken(
            poetica_op="seed",
            operation_token=token,
            krisper_op=None,  # KRISPER has no seed — it's a binding
            inputs={"name": op["name"], "value": op.get("value", "")},
            level=level,
            status="binding",
            indent=op.get("indent", 0),
            domain_provenance=provenance,
        )
    else:  # flow
        return OperationToken(
            poetica_op="flow",
            operation_token=token,
            krisper_op=None,
            inputs={"source": op.get("source", ""), "dest": op.get("dest", "")},
            level=level,
            status="binding",
            indent=op.get("indent", 0),
            domain_provenance=provenance,
        )


def _lower_emit(op: Dict, token: str, level: int,
                bindings: Dict, provenance: Optional[Dict]) -> OperationToken:
    value = op.get("value", "")
    # Resolve binding if value is a known variable name
    resolved = bindings.get(value, value)
    stripped = resolved.strip('"')
    message = f"utf8:{resolved}" if not resolved.startswith('"') else f"utf8:{stripped}"

    inputs = {"message": message}
    if op.get("label"):
        inputs["label"] = op["label"]

    return OperationToken(
        poetica_op="emit",
        operation_token=token,
        krisper_op="print",
        inputs=inputs,
        level=level,
        status="lowered",
        indent=op.get("indent", 0),
        domain_provenance=provenance,
    )


def _lower_bloom(op: Dict, token: str, level: int,
                 bindings: Dict, provenance: Optional[Dict]) -> OperationToken:
    value = op.get("value", "")
    resolved = bindings.get(value, value)
    return OperationToken(
        poetica_op="bloom",
        operation_token=token,
        krisper_op=None,  # KRISPER has no return — metadata only
        inputs={"value": resolved},
        level=level,
        status="lowered",
        indent=op.get("indent", 0),
        domain_provenance=provenance,
    )


def _lower_remember(op: Dict, token: str, level: int,
                    provenance: Optional[Dict]) -> OperationToken:
    return OperationToken(
        poetica_op="remember",
        operation_token=token,
        krisper_op="digest",
        inputs={"data": f"utf8:{op.get('key', '')}={op.get('value', '')}"},
        level=level,
        status="lowered",
        indent=op.get("indent", 0),
        domain_provenance=provenance,
    )


def _lower_control(op: Dict, token: str, level: int,
                   provenance: Optional[Dict]) -> OperationToken:
    op_name = op["op"]
    inputs = {}
    if op_name == "when":
        inputs["condition"] = op.get("condition", "")
    elif op_name == "when_in":
        inputs["subject"] = op.get("subject", "")
        inputs["container"] = op.get("container", "")
    elif op_name == "if":
        inputs["left"] = op.get("left", "")
        inputs["right"] = op.get("right", "")
    elif op_name == "else_when":
        inputs["condition"] = op.get("condition", "")
    elif op_name == "for":
        inputs["var"] = op.get("var", "")
        inputs["collection"] = op.get("collection", "")

    return OperationToken(
        poetica_op=op_name,
        operation_token=token,
        krisper_op=None,  # KRISPER has no control flow
        inputs=inputs,
        level=level,
        status="control_metadata",
        indent=op.get("indent", 0),
        domain_provenance=provenance,
    )


def _lower_pack(op: Dict, token: str, level: int,
                provenance: Optional[Dict]) -> OperationToken:
    fmt = op.get("format", "json")
    krisper_op = "write_json" if fmt == "json" else None
    status = "lowered" if krisper_op else "unsupported"
    return OperationToken(
        poetica_op="pack",
        operation_token=token,
        krisper_op=krisper_op,
        inputs={"data": op.get("data", "")},
        params={"format": fmt},
        level=level,
        status=status,
        indent=op.get("indent", 0),
        domain_provenance=provenance,
    )


def _lower_grow(op: Dict, token: str, level: int,
                provenance: Optional[Dict]) -> OperationToken:
    return OperationToken(
        poetica_op="grow",
        operation_token=token,
        krisper_op=None,  # KRISPER has no append/grow
        inputs={"name": op.get("name", ""), "source": op.get("source", "")},
        level=level,
        status="lowered",
        indent=op.get("indent", 0),
        domain_provenance=provenance,
    )


def _lower_learn(op: Dict, token: str, level: int,
                 provenance: Optional[Dict]) -> OperationToken:
    return OperationToken(
        poetica_op="learn",
        operation_token=token,
        krisper_op=None,  # KRISPER has no pattern learning
        inputs={"pattern": op.get("pattern", "")},
        level=level,
        status="lowered",
        indent=op.get("indent", 0),
        domain_provenance=provenance,
    )


def _lower_lift(op: Dict, token: str, level: int,
                provenance: Optional[Dict]) -> OperationToken:
    return OperationToken(
        poetica_op="lift",
        operation_token=token,
        krisper_op=None,  # KRISPER has read_text but no write_file
        inputs={"name": op.get("name", ""), "dest": op.get("dest", "")},
        level=level,
        status="lowered",
        indent=op.get("indent", 0),
        domain_provenance=provenance,
    )


def _lower_use(op: Dict, token: str, level: int,
               provenance: Optional[Dict]) -> OperationToken:
    return OperationToken(
        poetica_op="use",
        operation_token=token,
        krisper_op=None,  # KRISPER tool dispatch TBD
        inputs={"tool": op.get("tool", "")},
        params=op.get("params", {}),
        level=level,
        status="lowered",
        indent=op.get("indent", 0),
        domain_provenance=provenance,
    )


# ── Convenience: source text → lowered result ──────────────────────

def lower_source(source: str, level: int = 1,
                 domain_pack=None) -> LoweringResult:
    """Lower Poetica source text to operation tokens.

    Convenience function that runs the full pipeline:
    source → (domain rewrite) → parse → compile → gate → lower.

    Args:
        source: Poetica source text.
        level: Gate level (1-5).
        domain_pack: Optional DomainPack for domain preprocessing.

    Returns:
        LoweringResult.
    """
    domain_rewrites = None

    if domain_pack is not None:
        source, domain_rewrites = domain_pack.preprocess_with_map(source)

    parser = PoeticaParser()
    elements = parser.parse(source)

    compiler = PoeticaCompiler()
    ir = compiler.compile(elements, source)

    return lower(ir, level=level, domain_rewrites=domain_rewrites)
