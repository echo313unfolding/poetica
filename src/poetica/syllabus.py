"""Poetica Syllabus Import — extract objectives from teacher syllabi.

Converts plaintext syllabi into draft CurriculumPack YAML that maps
objectives to Poetica concepts, domain packs, visual worlds, and evidence.

This is a draft generator, not an authority. Output includes confidence
scores and marks inferred mappings as needing teacher review.

Architecture:
  syllabus text → extract units/objectives → match concept patterns
  → suggest ops/domain/worlds → emit draft YAML

Safety:
  - Does not claim standards alignment is official.
  - Does not silently invent compliance.
  - Marks inferred mappings as inferred.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from poetica.curriculum import (
    CurriculumPack, Unit, Lesson, CurriculumConcept, StandardLink,
    EvidenceItem, KNOWN_OPS, load_curriculum,
)
from poetica.domain import list_domains
from poetica.visual import list_worlds


# --- Concept patterns: keyword clusters → concept ID + ops ---

@dataclass
class ConceptPattern:
    """A pattern that maps objective keywords to a Poetica concept."""
    concept_id: str
    label: str
    keywords: List[str]
    poetica_ops: List[str]
    evidence_templates: List[str]
    visual_worlds: List[str] = field(default_factory=lambda: ["robot_grid"])


_CONCEPT_PATTERNS = [
    ConceptPattern(
        concept_id="input_output",
        label="Input and Output",
        keywords=["input", "output", "sensor reading", "display", "print",
                  "emit", "read sensor", "show"],
        poetica_ops=["seed", "emit"],
        evidence_templates=[
            "student can identify the input value",
            "student can identify the output",
            "student can change the input and predict the output",
        ],
    ),
    ConceptPattern(
        concept_id="input_condition_action",
        label="Input → Condition → Action",
        keywords=["sensor trigger", "condition trigger", "sensor action",
                  "trigger action", "detect", "obstacle", "respond"],
        poetica_ops=["seed", "when", "emit", "flow"],
        evidence_templates=[
            "student can explain input → condition → action",
            "student can modify the threshold",
            "student can debug a wrong comparison",
        ],
    ),
    ConceptPattern(
        concept_id="decision",
        label="Making Decisions",
        keywords=["condition", "decision", "if else", "if/else",
                  "comparison", "threshold", "choose", "branch"],
        poetica_ops=["seed", "when", "emit"],
        evidence_templates=[
            "student can trace which path runs",
            "student can change the condition and predict the new output",
        ],
    ),
    ConceptPattern(
        concept_id="variable_state",
        label="Variables and State",
        keywords=["variable", "store value", "change value", "state",
                  "assignment", "container", "named value", "trace value"],
        poetica_ops=["seed", "flow", "emit"],
        evidence_templates=[
            "student can name what the variable holds",
            "student can trace how a value changes through the program",
            "student can explain initial vs current state",
        ],
    ),
    ConceptPattern(
        concept_id="sequence",
        label="Sequence and Order",
        keywords=["sequence", "order", "top to bottom", "step by step",
                  "instruction order", "execute in order"],
        poetica_ops=["seed", "emit", "flow"],
        evidence_templates=[
            "student can predict output order",
            "student can explain what happens if lines are reordered",
        ],
    ),
    ConceptPattern(
        concept_id="loop_collection",
        label="Loops and Collections",
        keywords=["loop", "repeat", "for each", "iterate", "collection",
                  "repetition", "patrol", "waypoint", "visit each"],
        poetica_ops=["seed", "for", "emit", "grow"],
        evidence_templates=[
            "student can predict how many times the loop runs",
            "student can add items and predict the result",
        ],
        visual_worlds=["robot_grid", "garden"],
    ),
    ConceptPattern(
        concept_id="data_transform",
        label="Data and Transform",
        keywords=["data", "transform", "collect", "pack", "format",
                  "process", "analyze", "convert"],
        poetica_ops=["seed", "grow", "pack", "emit"],
        evidence_templates=[
            "student can explain what the collection contains at each step",
            "student can modify the data and predict the output",
        ],
        visual_worlds=["filesystem"],
    ),
    ConceptPattern(
        concept_id="debugging",
        label="Debugging",
        keywords=["debug", "fix", "error", "mistake", "misplaced",
                  "wrong", "find bug", "trace"],
        poetica_ops=["seed", "when", "emit", "bloom"],
        evidence_templates=[
            "student can identify the bug",
            "student can explain why the output is wrong",
            "student can fix the error",
        ],
    ),
    ConceptPattern(
        concept_id="external_io",
        label="External Input/Output",
        keywords=["file", "network", "api", "web", "download",
                  "upload", "external", "send data", "receive"],
        poetica_ops=["seed", "lift", "use", "emit"],
        evidence_templates=[
            "student can explain where data goes",
            "student can identify external systems",
        ],
    ),
]


@dataclass
class ExtractedUnit:
    """A unit extracted from syllabus text."""
    title: str
    raw_text: str
    objectives: List[str] = field(default_factory=list)
    vocabulary: List[str] = field(default_factory=list)
    standards_refs: List[str] = field(default_factory=list)


@dataclass
class ConceptMatch:
    """A concept matched to an objective."""
    concept_id: str
    label: str
    poetica_ops: List[str]
    matched_keywords: List[str]
    confidence: float  # 0.0 to 1.0
    source_objective: str
    evidence_templates: List[str]
    visual_worlds: List[str]


@dataclass
class SyllabusExtraction:
    """Complete extraction from a syllabus."""
    title: str
    grade_band: str
    subject: str
    standards_refs: List[str]
    units: List[ExtractedUnit]
    needs_teacher_review: bool = True


# --- Standards pattern ---
_STANDARDS_RE = re.compile(
    r'(CSTA[-\s][\w.-]+|NGSS[-\s][\w.-]+|ISTE[-\s][\w.-]+)',
    re.IGNORECASE,
)


def extract_syllabus(text: str) -> SyllabusExtraction:
    """Extract structure from plaintext syllabus."""
    lines = text.split('\n')

    title = _extract_title(lines)
    grade_band = _extract_grade_band(text)
    subject = _extract_subject(text)
    standards_refs = _extract_standards(text)
    units = _extract_units(lines)

    return SyllabusExtraction(
        title=title,
        grade_band=grade_band,
        subject=subject,
        standards_refs=standards_refs,
        units=units,
    )


def _extract_title(lines: list) -> str:
    """Extract course title from first non-empty line."""
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            return stripped
    return "Untitled Course"


def _extract_grade_band(text: str) -> str:
    """Extract grade band from text."""
    # Look for "Grade X" or "Grades X-Y" or "K-8" etc.
    m = re.search(r'[Gg]rades?\s+(\d+[-–]\d+|\d+|K[-–]\d+)', text)
    if m:
        return m.group(1).replace('–', '-')
    # Look for grade in title line
    m = re.search(r'[Gg]rade\s+(\d+)', text)
    if m:
        return m.group(1)
    return ""


def _extract_subject(text: str) -> str:
    """Extract subject from text."""
    text_lower = text.lower()
    subjects = [
        ("robotics", "Robotics"),
        ("computing", "Computing"),
        ("computer science", "Computer Science"),
        ("engineering", "Engineering"),
        ("stem", "STEM"),
        ("science", "Science"),
        ("technology", "Technology"),
        ("math", "Mathematics"),
    ]
    for keyword, label in subjects:
        if keyword in text_lower:
            return label
    return ""


def _extract_standards(text: str) -> List[str]:
    """Extract standards references."""
    return _STANDARDS_RE.findall(text)


def _extract_units(lines: list) -> List[ExtractedUnit]:
    """Extract units from syllabus lines."""
    units = []
    current_unit = None
    current_section = None  # "objectives", "vocabulary", None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect unit header: "Unit N: Title" or "Unit N — Title"
        unit_match = re.match(
            r'[Uu]nit\s+\d+\s*[:—–-]\s*(.+)', stripped
        )
        if unit_match:
            if current_unit:
                units.append(current_unit)
            current_unit = ExtractedUnit(
                title=unit_match.group(1).strip(),
                raw_text="",
            )
            current_section = None
            continue

        if current_unit is None:
            # Look for standards in preamble
            continue

        # Accumulate raw text
        current_unit.raw_text += stripped + "\n"

        # Detect sections within a unit
        if re.match(r'[Oo]bjectives?\s*:', stripped):
            current_section = "objectives"
            continue
        elif re.match(r'[Vv]ocabulary\s*:', stripped):
            current_section = "vocabulary"
            # Check for inline vocabulary: "Vocabulary: word1, word2, ..."
            inline = re.sub(r'^[Vv]ocabulary\s*:\s*', '', stripped)
            if inline:
                words = [w.strip() for w in inline.split(',')]
                current_unit.vocabulary.extend(w for w in words if w)
            continue
        elif re.match(r'[Aa]ctivit(y|ies)\s*:', stripped):
            current_section = "activities"
            continue
        elif re.match(r'[Aa]ssessment\s*:', stripped):
            current_section = "assessment"
            continue
        elif re.match(r'[Ss]tandards?\s*:', stripped):
            current_section = "standards"
            continue

        # Parse content based on current section
        if current_section == "objectives":
            # Strip bullet markers
            obj = re.sub(r'^[-•*]\s*', '', stripped)
            if obj and not obj.endswith(':'):
                current_unit.objectives.append(obj)

        elif current_section == "vocabulary":
            # Vocabulary is usually comma-separated on one line
            words = [w.strip() for w in stripped.split(',')]
            current_unit.vocabulary.extend(w for w in words if w)

        elif current_section == "standards":
            refs = _STANDARDS_RE.findall(stripped)
            current_unit.standards_refs.extend(refs)

    if current_unit:
        units.append(current_unit)

    return units


def match_concepts(unit: ExtractedUnit) -> List[ConceptMatch]:
    """Match unit objectives to Poetica concepts."""
    matches = []
    seen_concepts = set()

    for obj in unit.objectives:
        obj_lower = obj.lower()
        best_match = None
        best_score = 0.0
        best_keywords = []

        for pattern in _CONCEPT_PATTERNS:
            matched = []
            for kw in pattern.keywords:
                if kw.lower() in obj_lower:
                    matched.append(kw)

            if not matched:
                continue

            # Score: proportion of keywords matched, with length bonus
            score = len(matched) / len(pattern.keywords)
            # Bonus for longer keyword matches
            total_chars = sum(len(kw) for kw in matched)
            score += min(total_chars / 50.0, 0.3)
            score = min(score, 1.0)

            if score > best_score:
                best_score = score
                best_match = pattern
                best_keywords = matched

        if best_match and best_match.concept_id not in seen_concepts:
            seen_concepts.add(best_match.concept_id)
            matches.append(ConceptMatch(
                concept_id=best_match.concept_id,
                label=best_match.label,
                poetica_ops=best_match.poetica_ops,
                matched_keywords=best_keywords,
                confidence=round(best_score, 2),
                source_objective=obj,
                evidence_templates=best_match.evidence_templates,
                visual_worlds=best_match.visual_worlds,
            ))

    return matches


def suggest_domain(text: str) -> str:
    """Suggest a domain pack based on syllabus content."""
    text_lower = text.lower()
    available = list_domains()

    domain_keywords = {
        "robotics": ["robot", "sensor", "motor", "actuator", "obstacle"],
        "microbiology": ["biology", "cell", "culture", "assay", "microscope",
                        "organism", "bacteria"],
        "finance": ["finance", "budget", "money", "cost", "profit", "margin",
                    "investment", "portfolio"],
    }

    best_domain = ""
    best_count = 0
    for domain, keywords in domain_keywords.items():
        if domain not in available:
            continue
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > best_count:
            best_count = count
            best_domain = domain

    return best_domain


def suggest_visual_worlds(concepts: List[ConceptMatch]) -> List[str]:
    """Suggest visual worlds based on matched concepts."""
    worlds = set()
    available = set(list_worlds())
    for cm in concepts:
        for w in cm.visual_worlds:
            if w in available:
                worlds.add(w)
    if not worlds:
        worlds.add("robot_grid")
    return sorted(worlds)


def draft_curriculum_yaml(extraction: SyllabusExtraction,
                          subject: str = "",
                          grade_band: str = "",
                          domain: str = "") -> str:
    """Generate draft curriculum YAML from extraction.

    Returns YAML string ready for teacher review.
    """
    subject = subject or extraction.subject
    grade_band = grade_band or extraction.grade_band
    full_text = "\n".join(u.raw_text for u in extraction.units)
    domain = domain or suggest_domain(full_text)

    lines = []
    lines.append(f"# DRAFT — generated from syllabus, needs teacher review")
    lines.append(f"# Source: {extraction.title}")
    lines.append(f"")
    name = re.sub(r'[^a-z0-9_]', '_', extraction.title.lower())
    name = re.sub(r'_+', '_', name).strip('_')
    lines.append(f"curriculum: {name}")
    lines.append(f"grade_band: \"{grade_band}\"")
    if subject:
        lines.append(f"subject: {subject}")
    if extraction.standards_refs:
        # Deduplicate and get source
        sources = set()
        for ref in extraction.standards_refs:
            parts = ref.split('-', 1)
            if parts:
                sources.add(parts[0].upper().strip())
        lines.append(f"standard_source: {'/'.join(sorted(sources))}")
    if domain:
        lines.append(f"domain: {domain}")
    lines.append(f"target_languages:")
    lines.append(f"  - python")
    lines.append(f"")
    lines.append(f"units:")

    for unit in extraction.units:
        concepts = match_concepts(unit)
        worlds = suggest_visual_worlds(concepts)

        lines.append(f"  - title: \"{unit.title}\"")

        # Standards
        all_stds = unit.standards_refs or [
            s for s in extraction.standards_refs
        ]
        if all_stds:
            lines.append(f"    standards:")
            seen = set()
            for std in all_stds:
                if std not in seen:
                    lines.append(f"      - {std}")
                    seen.add(std)

        # Concepts
        if concepts:
            lines.append(f"    concepts:")
            for cm in concepts:
                lines.append(f"      - id: {cm.concept_id}")
                lines.append(f"        label: {cm.label}")
                if cm.poetica_ops:
                    ops_str = ", ".join(cm.poetica_ops)
                    lines.append(f"        poetica_ops: [{ops_str}]")
                lines.append(f"        # confidence: {cm.confidence}"
                             f"  matched: {', '.join(cm.matched_keywords)}")
                lines.append(f"        # source: \"{cm.source_objective}\"")

        # Ops (union of concept ops)
        all_ops = set()
        for cm in concepts:
            all_ops.update(cm.poetica_ops)
        if all_ops:
            ops_str = ", ".join(sorted(all_ops))
            lines.append(f"    poetica_ops: [{ops_str}]")

        # Visual worlds
        if worlds:
            lines.append(f"    visual_worlds:")
            for w in worlds:
                lines.append(f"      - {w}")

        # Lessons (one per concept)
        if concepts:
            lines.append(f"    lessons:")
            for cm in concepts:
                lines.append(f"      - concept: {cm.concept_id}")
                lines.append(f"        phrase: |")
                lines.append(f"          # TODO: write Poetica phrase for"
                             f" {cm.concept_id}")
                lines.append(f"          name {name}_{cm.concept_id}")
                # Generate a minimal phrase hint
                if "seed" in cm.poetica_ops:
                    lines.append(f"          seed x with 1")
                if "when" in cm.poetica_ops:
                    lines.append(f"          when x > 0:")
                    lines.append(f"              emit \"yes\"")
                elif "emit" in cm.poetica_ops:
                    lines.append(f"          emit x")
                if domain:
                    lines.append(f"        domain: {domain}")
                lines.append(f"        target_languages: [python]")
                if worlds:
                    lines.append(f"        visual_world: {worlds[0]}")
                if cm.evidence_templates:
                    lines.append(f"        evidence:")
                    for ev in cm.evidence_templates:
                        lines.append(f"          - {ev}")

        # Unit-level evidence from objectives
        if unit.objectives:
            lines.append(f"    evidence:")
            for obj in unit.objectives:
                lines.append(f"      - \"{obj}\"")

        lines.append(f"")

    lines.append(f"# needs_teacher_review: true")
    lines.append(f"# Generated mappings are inferred from keyword matching.")
    lines.append(f"# Teacher should verify standards alignment, phrase content,")
    lines.append(f"# and evidence criteria before classroom use.")

    return "\n".join(lines)


def inspect_syllabus(text: str) -> str:
    """Inspect a syllabus and show what was extracted."""
    extraction = extract_syllabus(text)

    lines = []
    lines.append(f"Title:      {extraction.title}")
    lines.append(f"Grade Band: {extraction.grade_band or '(not detected)'}")
    lines.append(f"Subject:    {extraction.subject or '(not detected)'}")

    if extraction.standards_refs:
        lines.append(f"Standards:  {', '.join(extraction.standards_refs)}")
    else:
        lines.append(f"Standards:  (none detected)")

    domain = suggest_domain(text)
    if domain:
        lines.append(f"Suggested domain: {domain}")

    lines.append(f"")
    lines.append(f"Units: {len(extraction.units)}")

    for i, unit in enumerate(extraction.units):
        lines.append(f"")
        lines.append(f"  Unit {i+1}: {unit.title}")
        lines.append(f"  Objectives: {len(unit.objectives)}")
        for obj in unit.objectives:
            lines.append(f"    - {obj}")

        if unit.vocabulary:
            lines.append(f"  Vocabulary: {', '.join(unit.vocabulary)}")

        # Show concept matches
        concepts = match_concepts(unit)
        if concepts:
            lines.append(f"  Concept matches:")
            for cm in concepts:
                lines.append(f"    [{cm.confidence:.0%}] {cm.concept_id}"
                             f" (ops: {', '.join(cm.poetica_ops)})")
                lines.append(f"         matched: {', '.join(cm.matched_keywords)}")
                lines.append(f"         from: \"{cm.source_objective}\"")

    return "\n".join(lines)
