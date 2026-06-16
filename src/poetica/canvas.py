"""Echo Canvas — visual concept output for Poetica programs and commands.

IR ops → annotated visual nodes → Mermaid / JSON / ASCII output.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from poetica.parser import PoeticaParser
from poetica.compiler import PoeticaCompiler
from poetica.gate import Gate, _LEVEL_OPS


# --- Concept map: op → visual metadata ---

_OP_CONCEPTS = {
    "seed":      {"shape": "box",      "concept": "variable",     "icon": "[=]",  "explanation": "Create a named value"},
    "emit":      {"shape": "speaker",  "concept": "output",       "icon": ">>",   "explanation": "Send a value to the screen"},
    "when":      {"shape": "diamond",  "concept": "decision",     "icon": "<?>",  "explanation": "Check a condition, then act"},
    "if":        {"shape": "diamond",  "concept": "decision",     "icon": "<?>",  "explanation": "Compare two values"},
    "else_when": {"shape": "diamond",  "concept": "decision",     "icon": "<?>",  "explanation": "Another condition to check"},
    "else":      {"shape": "diamond",  "concept": "fallback",     "icon": "<*>",  "explanation": "If nothing else matched, do this"},
    "for":       {"shape": "loop",     "concept": "loop",         "icon": "(o)",  "explanation": "Repeat for each item in a collection"},
    "grow":      {"shape": "build",    "concept": "transform",    "icon": "[+]",  "explanation": "Add to a collection"},
    "pack":      {"shape": "container","concept": "serialize",    "icon": "[{}]", "explanation": "Pack data into a format"},
    "lift":      {"shape": "arrow_out","concept": "external",     "icon": "-->",  "explanation": "Send data to an external system"},
    "use":       {"shape": "arrow_out","concept": "external",     "icon": "-->",  "explanation": "Call an external tool"},
    "flow":      {"shape": "arrow",    "concept": "assignment",   "icon": "->",   "explanation": "Move a value from one place to another"},
    "bloom":     {"shape": "speaker",  "concept": "return",       "icon": "(*)",  "explanation": "Signal completion"},
    "remember":  {"shape": "box",      "concept": "state",        "icon": "[M]",  "explanation": "Store a value for later"},
    "learn":     {"shape": "box",      "concept": "pattern",      "icon": "[~]",  "explanation": "Remember a pattern to recognize"},
    "when_in":   {"shape": "loop",     "concept": "membership",   "icon": "(in)", "explanation": "Check if something is in a collection"},
}

_CMD_CONCEPTS = {
    "fs.list":              {"shape": "folder",  "concept": "folder_list",    "icon": "[D]",  "explanation": "List files in a directory"},
    "fs.pwd":               {"shape": "folder",  "concept": "location",       "icon": "[@]",  "explanation": "Show current directory"},
    "package.update_index": {"shape": "database","concept": "package_refresh","icon": "[db]", "explanation": "Refresh the package database"},
    "package.upgrade":      {"shape": "database","concept": "package_upgrade","icon": "[^^]", "explanation": "Upgrade installed packages"},
    "package.install":      {"shape": "database","concept": "package_install","icon": "[+p]", "explanation": "Install a new package"},
}


def _required_level(op_name: str) -> int:
    for lvl in range(1, 6):
        if op_name in _LEVEL_OPS.get(lvl, set()):
            return lvl
    return 0


@dataclass
class VisualNode:
    """A single visual element in the concept graph."""
    id: str
    source_line: int
    source_text: str
    ir_op: str
    concept: str
    explanation: str
    shape: str
    icon: str
    gate_level: int
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_line": self.source_line,
            "source_text": self.source_text,
            "ir_op": self.ir_op,
            "concept": self.concept,
            "explanation": self.explanation,
            "shape": self.shape,
            "icon": self.icon,
            "gate_level": self.gate_level,
            "details": self.details,
        }


def visualize_poem(source: str, level: int = 5) -> List[VisualNode]:
    """Parse a poem source and produce visual nodes."""
    parser = PoeticaParser()
    compiler = PoeticaCompiler()
    elements = parser.parse(source)
    ir = compiler.compile(elements, source)

    # Build line map: element index → source line number
    line_map = []
    line_num = 0
    for raw_line in source.split('\n'):
        line_num += 1
        stripped = raw_line.strip()
        if stripped and not stripped.startswith('#'):
            line_map.append((line_num, raw_line.strip()))

    # Skip the 'name' element — it's consumed by compiler but not an op
    name_offset = 1 if elements and elements[0].kind == 'name' else 0

    nodes = []
    for i, op in enumerate(ir["ops"]):
        op_name = op.get("op", "")
        meta = _OP_CONCEPTS.get(op_name, {
            "shape": "box", "concept": op_name, "icon": "[?]",
            "explanation": f"Operation: {op_name}",
        })

        src_idx = i + name_offset
        if src_idx < len(line_map):
            src_line, src_text = line_map[src_idx]
        else:
            src_line, src_text = 0, ""

        details = {k: v for k, v in op.items() if k not in ("op", "indent")}

        nodes.append(VisualNode(
            id=f"n{i}",
            source_line=src_line,
            source_text=src_text,
            ir_op=op_name,
            concept=meta["concept"],
            explanation=meta["explanation"],
            shape=meta["shape"],
            icon=meta["icon"],
            gate_level=_required_level(op_name),
            details=details,
        ))

    return nodes


def visualize_command(command_text: str) -> List[VisualNode]:
    """Produce visual nodes for a shell command string (like 'ls -la')."""
    from poetica.intent import parse_intent, IntentError

    # Try to map the raw command to an intent
    # For raw commands like "ls -la", try the base command
    parts = command_text.strip().split()
    if not parts:
        return []

    base_cmd = parts[0]
    # Map common commands to intent ops
    cmd_map = {
        "ls": "fs.list",
        "pwd": "fs.pwd",
        "apt": _apt_subcommand(parts),
    }

    intent_op = cmd_map.get(base_cmd, None)
    if intent_op is None:
        # Fallback: generic command node
        return [VisualNode(
            id="n0",
            source_line=1,
            source_text=command_text,
            ir_op="cmd",
            concept="command",
            explanation=f"Run: {command_text}",
            shape="box",
            icon="[$]",
            gate_level=1,
            details={"argv": parts},
        )]

    meta = _CMD_CONCEPTS.get(intent_op, {
        "shape": "box", "concept": intent_op, "icon": "[$]",
        "explanation": f"Command: {intent_op}",
    })

    level = 4 if intent_op.startswith("package.") else 1

    return [VisualNode(
        id="n0",
        source_line=1,
        source_text=command_text,
        ir_op=intent_op,
        concept=meta["concept"],
        explanation=meta["explanation"],
        shape=meta["shape"],
        icon=meta["icon"],
        gate_level=level,
        details={"argv": parts},
    )]


def _apt_subcommand(parts: List[str]) -> str:
    if len(parts) >= 2:
        sub = parts[1]
        if sub == "update":
            return "package.update_index"
        if sub == "upgrade":
            return "package.upgrade"
        if sub == "install":
            return "package.install"
    return "package.update_index"


# --- Output formatters ---

def to_mermaid(nodes: List[VisualNode], name: str = "program") -> str:
    """Render visual nodes as a Mermaid flowchart."""
    lines = ["flowchart TD"]

    if not nodes:
        lines.append("    empty[No operations]")
        return "\n".join(lines)

    # Start node
    lines.append(f"    start([Start: {name}])")

    prev_id = "start"
    # Track block nesting for decision edges
    block_stack = []  # stack of decision node ids
    after_decision = False  # True if prev node was a decision (when/if)

    for node in nodes:
        nid = node.id
        label = _mermaid_escape(node.source_text or node.ir_op)

        if node.shape == "diamond":
            lines.append(f"    {nid}{{{{{label}}}}}")
        elif node.shape == "loop":
            lines.append(f"    {nid}(({label}))")
        elif node.shape in ("arrow_out", "arrow"):
            lines.append(f"    {nid}[/{label}/]")
        elif node.shape == "speaker":
            lines.append(f"    {nid}[>{label}]")
        else:
            lines.append(f"    {nid}[{label}]")

        # Edge from previous
        if node.ir_op in ("else_when", "else"):
            # Branch from the last decision
            if block_stack:
                dec_id = block_stack[-1]
                lines.append(f"    {dec_id} -- no --> {nid}")
                block_stack[-1] = nid
            else:
                lines.append(f"    {prev_id} --> {nid}")
            after_decision = node.ir_op != "else"
        elif node.ir_op in ("when", "if"):
            lines.append(f"    {prev_id} --> {nid}")
            block_stack.append(nid)
            after_decision = True
            prev_id = nid
            continue
        else:
            if after_decision and block_stack:
                # First node after a decision — this is the "yes" branch
                lines.append(f"    {block_stack[-1]} -- yes --> {nid}")
            else:
                lines.append(f"    {prev_id} --> {nid}")
            after_decision = False

        prev_id = nid

    # End node
    lines.append(f"    finish([End])")
    lines.append(f"    {prev_id} --> finish")

    # Gate level annotations as comments
    gated = [n for n in nodes if n.gate_level >= 3]
    if gated:
        lines.append("")
        for n in gated:
            lines.append(f"    %% {n.id}: requires L{n.gate_level} ({n.concept})")

    return "\n".join(lines)


def _mermaid_escape(text: str) -> str:
    """Escape characters that break Mermaid syntax."""
    return text.replace('"', "'").replace("[", "(").replace("]", ")")


def to_json_graph(nodes: List[VisualNode], name: str = "program") -> str:
    """Render visual nodes as a JSON graph."""
    graph = {
        "name": name,
        "nodes": [n.to_dict() for n in nodes],
        "edges": [],
    }

    for i in range(len(nodes)):
        if i == 0:
            graph["edges"].append({"from": "start", "to": nodes[i].id})
        if i > 0:
            graph["edges"].append({"from": nodes[i - 1].id, "to": nodes[i].id})
        if i == len(nodes) - 1:
            graph["edges"].append({"from": nodes[i].id, "to": "end"})

    return json.dumps(graph, indent=2)


def to_ascii(nodes: List[VisualNode], name: str = "program") -> str:
    """Render visual nodes as an ASCII diagram."""
    lines = []
    width = 50

    lines.append(f"  {'=' * width}")
    lines.append(f"  | {'START: ' + name:^{width - 4}} |")
    lines.append(f"  {'=' * width}")

    for node in nodes:
        lines.append(f"  {'|':^{width}}")
        lines.append(f"  {'v':^{width}}")

        icon = node.icon
        op_label = node.source_text or node.ir_op

        if node.shape == "diamond":
            # Decision node
            inner = f" {icon} {op_label} "
            pad = max(0, width - 4 - len(inner))
            lines.append(f"  /{inner}{'.' * pad}\\")
            lines.append(f"  \\{'.' * (len(inner) + pad)}/")
        elif node.shape == "loop":
            inner = f" {icon} {op_label} "
            lines.append(f"  ({inner:-^{width - 4}})")
        elif node.shape in ("arrow_out", "arrow"):
            inner = f" {icon} {op_label} "
            lines.append(f"  --{inner:-^{width - 6}}-->")
        else:
            inner = f" {icon} {op_label} "
            lines.append(f"  [{inner:-^{width - 4}}]")

        # Explanation + gate level
        expl = f"  L{node.gate_level} | {node.explanation}"
        lines.append(f"  {expl}")

    lines.append(f"  {'|':^{width}}")
    lines.append(f"  {'v':^{width}}")
    lines.append(f"  {'=' * width}")
    lines.append(f"  | {'END':^{width - 4}} |")
    lines.append(f"  {'=' * width}")

    return "\n".join(lines)
