"""Echo Alignment Map — phrase-level micro-pattern source maps.

Maps each Poetica source construct to its IR op, target code, concept, and visual role.

Design principle: NO NAKED SYNTAX.
Every syntax token appears with four layers:
  1. Visual   — what you'd SEE happening (spatial/physical)
  2. Phrase   — the Poetica source (human-readable)
  3. Concept  — the formal CS concept name
  4. Target   — the actual code syntax
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from poetica.parser import PoeticaParser
from poetica.compiler import PoeticaCompiler
from poetica.emitters import get_emitter
from poetica.canvas import _OP_CONCEPTS, _required_level


# Visual descriptions: what you'd SEE happening — spatial/physical meaning
# These are templates with {placeholders} filled from op fields.
_OP_VISUALS = {
    "seed":      "A box labeled '{name}' appears and gets filled with {value}",
    "emit":      "The value {value} leaves the program and appears on screen",
    "when":      "A fork in the road — the program checks: {condition}",
    "if":        "Two things are compared side by side: {left} vs {right}",
    "else_when": "Another fork — checked only if the first path wasn't taken: {condition}",
    "else":      "The default path — taken when nothing else matched",
    "for":       "A loop — the program visits each {var} in {collection} one by one",
    "grow":      "The collection {name} gets a new item added: {source}",
    "pack":      "The data {data} gets wrapped up into {format} format",
    "lift":      "The data {name} leaves the program and goes to {dest}",
    "use":       "An external tool '{tool}' is called to do work",
    "flow":      "A value moves: {source} flows into {dest}",
    "bloom":     "The program signals it is done: {value}",
    "remember":  "A value is stored for later: {key} = {value}",
    "learn":     "A pattern is memorized for recognition: {pattern}",
    "when_in":   "Check if {subject} is inside {container}",
}


def _format_visual(op_name: str, op: dict) -> str:
    """Fill visual template with op fields."""
    template = _OP_VISUALS.get(op_name, "Operation: {op}")
    try:
        return template.format(**op)
    except KeyError:
        return template


# Visual roles: what function does this construct serve in the program?
_CONCEPT_ROLES = {
    "variable":    "declare",
    "output":      "output",
    "decision":    "control",
    "fallback":    "control",
    "loop":        "control",
    "membership":  "control",
    "transform":   "transform",
    "serialize":   "transform",
    "external":    "external",
    "assignment":  "declare",
    "return":      "output",
    "state":       "state",
    "pattern":     "state",
}


@dataclass
class AlignmentSpan:
    """One source construct aligned to its target code.

    Four layers (no naked syntax):
      visual      — what you'd SEE happening
      source_text — the Poetica phrase
      concept     — the formal CS concept
      target_text — the code syntax
    """
    source_line: int
    source_start: int
    source_end: int
    source_text: str
    ir_op: str
    concept: str
    target: str
    target_text: str
    visual_role: str
    explanation: str
    gate_level: int
    visual: str = ""
    # Domain provenance (filled when --domain is used)
    domain_original: str = ""   # original phrase before rewrite
    domain_concept: str = ""    # domain-specific concept name
    domain_visual: str = ""     # domain-specific visual description


def align_poem(source: str, target: str = "python",
               rewrites: list = None) -> List[AlignmentSpan]:
    """Produce alignment spans mapping source phrases to target code.

    Args:
        source: Canonical Poetica source (after domain preprocessing).
        target: Target language name.
        rewrites: Optional list of DomainRewrite provenance records from
                  DomainPack.preprocess_with_map().
    """
    parser = PoeticaParser()
    compiler = PoeticaCompiler()
    elements = parser.parse(source)
    ir = compiler.compile(elements, source)

    emitter = get_emitter(target)

    # Build source line map (same as canvas.py)
    line_map = []
    line_num = 0
    for raw_line in source.split('\n'):
        line_num += 1
        stripped = raw_line.strip()
        if stripped and not stripped.startswith('#'):
            line_map.append((line_num, raw_line.strip(), raw_line))

    # Index rewrites by line number for fast lookup
    rewrite_by_line = {}
    if rewrites:
        for rw in rewrites:
            rewrite_by_line[rw.line_num] = rw

    # Name offset — name element is consumed by compiler
    name_offset = 1 if elements and elements[0].kind == 'name' else 0

    spans = []
    for i, op in enumerate(ir["ops"]):
        op_name = op.get("op", "")

        # Source location
        src_idx = i + name_offset
        if src_idx < len(line_map):
            src_line, src_text, raw_line = line_map[src_idx]
            # Character offsets within the original line
            stripped = raw_line.lstrip()
            src_start = len(raw_line) - len(stripped)
            src_end = src_start + len(stripped)
        else:
            src_line, src_text, src_start, src_end = 0, "", 0, 0

        # Concept metadata
        meta = _OP_CONCEPTS.get(op_name, {
            "concept": op_name,
            "explanation": f"Operation: {op_name}",
        })
        concept = meta["concept"]
        explanation = meta["explanation"]
        gate_level = _required_level(op_name)

        # Target code
        target_code = emitter._emit_op(op)
        if isinstance(target_code, list):
            target_text = "\n".join(target_code)
        elif target_code is None:
            target_text = ""
        else:
            target_text = target_code

        # Visual role
        visual_role = _CONCEPT_ROLES.get(concept, "other")

        # Visual description — what you'd SEE happening
        visual = _format_visual(op_name, op)

        # Domain provenance
        domain_original = ""
        domain_concept = ""
        domain_visual = ""
        rw = rewrite_by_line.get(src_line)
        if rw:
            domain_original = rw.original_text
            domain_concept = rw.domain_concept
            domain_visual = rw.domain_visual

        spans.append(AlignmentSpan(
            source_line=src_line,
            source_start=src_start,
            source_end=src_end,
            source_text=src_text,
            ir_op=op_name,
            concept=concept,
            target=target,
            target_text=target_text,
            visual_role=visual_role,
            explanation=explanation,
            gate_level=gate_level,
            visual=visual,
            domain_original=domain_original,
            domain_concept=domain_concept,
            domain_visual=domain_visual,
        ))

    return spans


def to_table(spans: List[AlignmentSpan]) -> str:
    """Render alignment spans as an aligned ASCII table."""
    if not spans:
        return "(no operations)"

    # Column widths
    w_line = 4
    w_source = max(len(s.source_text) for s in spans)
    w_source = max(w_source, 6)
    w_concept = max(len(s.concept) for s in spans)
    w_concept = max(w_concept, 7)
    w_target = max(len(s.target_text.split('\n')[0]) for s in spans)
    w_target = max(w_target, 6)
    w_role = max(len(s.visual_role) for s in spans)
    w_role = max(w_role, 4)

    lines = []
    header = (f"{'Line':>{w_line}} | {'Source':<{w_source}} | "
              f"{'Concept':<{w_concept}} | {'Target':<{w_target}} | "
              f"{'Role':<{w_role}}")
    lines.append(header)
    sep = (f"{'-' * w_line}-+-{'-' * w_source}-+-"
           f"{'-' * w_concept}-+-{'-' * w_target}-+-"
           f"{'-' * w_role}")
    lines.append(sep)

    for span in spans:
        target_first = span.target_text.split('\n')[0]
        line = (f"{span.source_line:>{w_line}} | {span.source_text:<{w_source}} | "
                f"{span.concept:<{w_concept}} | {target_first:<{w_target}} | "
                f"{span.visual_role:<{w_role}}")
        lines.append(line)

    return "\n".join(lines)


def to_annotated(spans: List[AlignmentSpan]) -> str:
    """Render alignment spans as annotated source."""
    if not spans:
        return "(no operations)"

    lines = []
    for span in spans:
        if span.domain_original:
            lines.append(f"{span.domain_original}  [domain: {span.domain_concept}]")
            lines.append(f"  => {span.source_text}")
        else:
            lines.append(span.source_text)
        target_first = span.target_text.split('\n')[0]
        lines.append(f"  -> [{span.concept}] {target_first}    "
                      f'"{span.explanation}" (L{span.gate_level})')
    return "\n".join(lines)


def to_lesson(spans: List[AlignmentSpan]) -> str:
    """Render alignment spans as layered lessons. No naked syntax.

    Without domain (4 layers):
      Visual:  what you'd SEE
      Phrase:  the Poetica source
      Concept: the formal name
      Code:    the target syntax

    With domain provenance (5 layers):
      Original: the domain phrase (what the learner wrote)
      Canonical: the Poetica phrase (what it became)
      Concept:  the domain concept (field-specific name)
      Code:     the target syntax
      Visual:   what you'd SEE (domain-specific when available)
    """
    if not spans:
        return "(no operations)"

    lines = []
    for i, span in enumerate(spans):
        if i > 0:
            lines.append("")
        target_first = span.target_text.split('\n')[0]
        if span.domain_original:
            # 5-layer domain lesson
            visual = span.domain_visual or span.visual
            concept = span.domain_concept or span.concept
            lines.append(f"  Original:  {span.domain_original}")
            lines.append(f"  Canonical: {span.source_text}")
            lines.append(f"  Concept:   {concept}")
            lines.append(f"  Code:      {target_first}")
            lines.append(f"  Visual:    {visual}")
        else:
            # Standard 4-layer lesson
            lines.append(f"  Visual:  {span.visual}")
            lines.append(f"  Phrase:  {span.source_text}")
            lines.append(f"  Concept: {span.concept} ({span.explanation})")
            lines.append(f"  Code:    {target_first}")

    return "\n".join(lines)


def to_json(spans: List[AlignmentSpan]) -> str:
    """Render alignment spans as JSON."""
    import json
    data = []
    for span in spans:
        entry = {
            "source_line": span.source_line,
            "source_start": span.source_start,
            "source_end": span.source_end,
            "source_text": span.source_text,
            "ir_op": span.ir_op,
            "concept": span.concept,
            "target": span.target,
            "target_text": span.target_text,
            "visual_role": span.visual_role,
            "visual": span.visual,
            "explanation": span.explanation,
            "gate_level": span.gate_level,
        }
        if span.domain_original:
            entry["domain_original"] = span.domain_original
            entry["domain_concept"] = span.domain_concept
            entry["domain_visual"] = span.domain_visual
        data.append(entry)
    return json.dumps(data, indent=2)
