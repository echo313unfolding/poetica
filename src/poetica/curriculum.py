"""Poetica Curriculum Mapper — attach school syllabi to the concept graph.

A curriculum pack connects school language (standards, objectives, grade bands)
to Poetica concepts, domain packs, visual worlds, code targets, and assessment
evidence.

Architecture:
  syllabus / standard / unit objective
  → concept node
  → Poetica lesson
  → visual world
  → code target
  → evidence criteria

Curriculum packs can map objectives to existing Poetica/domain concepts.
They cannot bypass gates, create unsafe ops, or silently execute commands.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from poetica.alignment import align_poem, to_lesson, to_json as align_to_json
from poetica.canvas import _OP_CONCEPTS
from poetica.domain import find_domain, load_domain
from poetica.visual import list_worlds


# All known Poetica ops (the concept graph nodes a curriculum can reference)
KNOWN_OPS = set(_OP_CONCEPTS.keys())


@dataclass
class StandardLink:
    """A reference to an external standard (CSTA, NGSS, etc.)."""
    standard_id: str
    source: str = ""       # e.g. "CSTA", "NGSS", "local"
    description: str = ""


@dataclass
class EvidenceItem:
    """One assessment evidence criterion."""
    description: str
    evidence_type: str = "observation"  # observation, modification, debug, transfer


@dataclass
class CurriculumConcept:
    """A concept node in the curriculum graph."""
    concept_id: str
    label: str = ""
    poetica_ops: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class Lesson:
    """A single lesson within a unit."""
    phrase: str
    concept_id: str
    domain: str = ""
    target_languages: List[str] = field(default_factory=lambda: ["python"])
    visual_world: str = ""
    evidence: List[EvidenceItem] = field(default_factory=list)
    notes: str = ""


@dataclass
class Unit:
    """A curriculum unit containing standards, concepts, and lessons."""
    title: str
    standards: List[StandardLink] = field(default_factory=list)
    concepts: List[CurriculumConcept] = field(default_factory=list)
    poetica_ops: List[str] = field(default_factory=list)
    visual_worlds: List[str] = field(default_factory=list)
    lessons: List[Lesson] = field(default_factory=list)
    evidence: List[EvidenceItem] = field(default_factory=list)


@dataclass
class CurriculumPack:
    """A loaded curriculum pack."""
    curriculum: str
    grade_band: str
    subject: str = ""
    description: str = ""
    standard_source: str = ""
    domain: str = ""
    target_languages: List[str] = field(default_factory=lambda: ["python"])
    units: List[Unit] = field(default_factory=list)

    def list_units(self) -> List[str]:
        """Return unit titles."""
        return [u.title for u in self.units]

    def get_unit(self, title: str) -> Optional[Unit]:
        """Find a unit by title."""
        for u in self.units:
            if u.title == title:
                return u
        return None

    def list_concepts(self) -> List[CurriculumConcept]:
        """Return all concepts across all units."""
        concepts = []
        seen = set()
        for unit in self.units:
            for c in unit.concepts:
                if c.concept_id not in seen:
                    concepts.append(c)
                    seen.add(c.concept_id)
        return concepts

    def get_concept(self, concept_id: str) -> Optional[CurriculumConcept]:
        """Find a concept by ID across all units."""
        for unit in self.units:
            for c in unit.concepts:
                if c.concept_id == concept_id:
                    return c
        return None

    def get_lessons_for_concept(self, concept_id: str) -> List[Lesson]:
        """Get all lessons mapped to a concept."""
        lessons = []
        for unit in self.units:
            for lesson in unit.lessons:
                if lesson.concept_id == concept_id:
                    lessons.append(lesson)
        return lessons

    def all_ops(self) -> set:
        """Return all Poetica ops referenced across the curriculum."""
        ops = set()
        for unit in self.units:
            ops.update(unit.poetica_ops)
            for c in unit.concepts:
                ops.update(c.poetica_ops)
        return ops

    def validate(self) -> List[str]:
        """Validate the curriculum pack. Returns list of error messages."""
        errors = []
        if not self.curriculum:
            errors.append("curriculum name is required")
        if not self.grade_band:
            errors.append("grade_band is required")
        if not self.units:
            errors.append("at least one unit is required")

        # Check ops reference known Poetica ops
        for unit in self.units:
            for op in unit.poetica_ops:
                if op not in KNOWN_OPS:
                    errors.append(f"unit '{unit.title}': unknown op '{op}'")
            for c in unit.concepts:
                for op in c.poetica_ops:
                    if op not in KNOWN_OPS:
                        errors.append(
                            f"concept '{c.concept_id}': unknown op '{op}'"
                        )

        # Check visual worlds exist
        available_worlds = set(list_worlds())
        for unit in self.units:
            for w in unit.visual_worlds:
                if w not in available_worlds:
                    errors.append(f"unit '{unit.title}': unknown world '{w}'")

        # Check domain exists if specified
        if self.domain:
            path = find_domain(self.domain)
            if path is None:
                errors.append(f"unknown domain '{self.domain}'")

        return errors


def _parse_standards(raw: list) -> List[StandardLink]:
    """Parse standards from YAML list (strings or dicts)."""
    standards = []
    for item in (raw or []):
        if isinstance(item, str):
            # "CSTA-1B-AP-10" → parse source from prefix
            parts = item.split("-", 1)
            standards.append(StandardLink(
                standard_id=item,
                source=parts[0] if len(parts) > 1 else "",
            ))
        elif isinstance(item, dict):
            standards.append(StandardLink(
                standard_id=item.get("id", ""),
                source=item.get("source", ""),
                description=item.get("description", ""),
            ))
    return standards


def _parse_evidence(raw: list) -> List[EvidenceItem]:
    """Parse evidence items from YAML list (strings or dicts)."""
    items = []
    for item in (raw or []):
        if isinstance(item, str):
            items.append(EvidenceItem(description=item))
        elif isinstance(item, dict):
            items.append(EvidenceItem(
                description=item.get("description", ""),
                evidence_type=item.get("type", "observation"),
            ))
    return items


def _parse_concepts(raw: list) -> List[CurriculumConcept]:
    """Parse concepts from YAML list (strings or dicts)."""
    concepts = []
    for item in (raw or []):
        if isinstance(item, str):
            concepts.append(CurriculumConcept(concept_id=item, label=item))
        elif isinstance(item, dict):
            concepts.append(CurriculumConcept(
                concept_id=item.get("id", ""),
                label=item.get("label", item.get("id", "")),
                poetica_ops=item.get("poetica_ops", []),
                description=item.get("description", ""),
            ))
    return concepts


def _parse_lessons(raw: list) -> List[Lesson]:
    """Parse lessons from YAML list."""
    lessons = []
    for item in (raw or []):
        if not isinstance(item, dict):
            continue
        lessons.append(Lesson(
            phrase=item.get("phrase", ""),
            concept_id=item.get("concept", ""),
            domain=item.get("domain", ""),
            target_languages=item.get("target_languages", ["python"]),
            visual_world=item.get("visual_world", ""),
            evidence=_parse_evidence(item.get("evidence", [])),
            notes=item.get("notes", ""),
        ))
    return lessons


def load_curriculum(path: str) -> CurriculumPack:
    """Load a curriculum pack from a YAML or JSON file."""
    with open(path, 'r') as f:
        raw = f.read()

    if path.endswith('.json'):
        data = json.loads(raw)
    else:
        try:
            import yaml
            data = yaml.safe_load(raw)
        except ImportError:
            data = json.loads(raw)

    units = []
    for u in data.get("units", []):
        units.append(Unit(
            title=u.get("title", ""),
            standards=_parse_standards(u.get("standards", [])),
            concepts=_parse_concepts(u.get("concepts", [])),
            poetica_ops=u.get("poetica_ops", []),
            visual_worlds=u.get("visual_worlds", []),
            lessons=_parse_lessons(u.get("lessons", [])),
            evidence=_parse_evidence(u.get("evidence", [])),
        ))

    return CurriculumPack(
        curriculum=data.get("curriculum", ""),
        grade_band=data.get("grade_band", ""),
        subject=data.get("subject", ""),
        description=data.get("description", ""),
        standard_source=data.get("standard_source", ""),
        domain=data.get("domain", ""),
        target_languages=data.get("target_languages", ["python"]),
        units=units,
    )


def find_curriculum(name: str) -> Optional[str]:
    """Find a built-in curriculum pack by name. Returns path or None."""
    base = os.path.join(os.path.dirname(__file__), '..', '..', 'examples', 'curricula')
    base = os.path.normpath(base)
    for ext in ('.yaml', '.yml', '.json'):
        path = os.path.join(base, name + ext)
        if os.path.exists(path):
            return path
    return None


def list_curricula() -> List[str]:
    """List available built-in curriculum pack names."""
    base = os.path.join(os.path.dirname(__file__), '..', '..', 'examples', 'curricula')
    base = os.path.normpath(base)
    if not os.path.isdir(base):
        return []
    names = []
    for f in sorted(os.listdir(base)):
        if f.endswith(('.yaml', '.yml', '.json')):
            name = os.path.splitext(f)[0]
            if name not in names:
                names.append(name)
    return names


def generate_lesson(lesson: Lesson, domain_name: str = "") -> str:
    """Generate a full alignment lesson from a Lesson object.

    Uses the domain pack if specified, runs through align_poem + to_lesson.
    """
    source = lesson.phrase
    domain = lesson.domain or domain_name

    rewrites = []
    if domain:
        path = find_domain(domain)
        if path:
            pack = load_domain(path)
            source, rewrites = pack.preprocess_with_map(source)

    spans = align_poem(source, target=lesson.target_languages[0], rewrites=rewrites)
    return to_lesson(spans)


def generate_evidence_json(lesson: Lesson, curriculum_name: str = "",
                           concept_id: str = "") -> str:
    """Generate evidence schema JSON for a lesson."""
    data = {
        "curriculum": curriculum_name,
        "concept": concept_id or lesson.concept_id,
        "phrase": lesson.phrase,
        "domain": lesson.domain,
        "target_languages": lesson.target_languages,
        "visual_world": lesson.visual_world,
        "evidence_criteria": [
            {
                "description": e.description,
                "type": e.evidence_type,
                "met": None,  # filled by student/teacher
            }
            for e in lesson.evidence
        ],
    }
    return json.dumps(data, indent=2)


def inspect_curriculum(pack: CurriculumPack) -> str:
    """Render a human-readable summary of a curriculum pack."""
    lines = []
    lines.append(f"Curriculum: {pack.curriculum}")
    lines.append(f"Grade Band: {pack.grade_band}")
    if pack.subject:
        lines.append(f"Subject:    {pack.subject}")
    if pack.standard_source:
        lines.append(f"Standards:  {pack.standard_source}")
    if pack.domain:
        lines.append(f"Domain:     {pack.domain}")
    if pack.description:
        lines.append(f"")
        lines.append(pack.description)
    lines.append("")

    for i, unit in enumerate(pack.units):
        lines.append(f"Unit {i+1}: {unit.title}")

        if unit.standards:
            std_ids = [s.standard_id for s in unit.standards]
            lines.append(f"  Standards: {', '.join(std_ids)}")

        if unit.concepts:
            concept_ids = [c.concept_id for c in unit.concepts]
            lines.append(f"  Concepts:  {', '.join(concept_ids)}")

        if unit.poetica_ops:
            lines.append(f"  Ops:       {', '.join(unit.poetica_ops)}")

        if unit.visual_worlds:
            lines.append(f"  Worlds:    {', '.join(unit.visual_worlds)}")

        if unit.lessons:
            lines.append(f"  Lessons:   {len(unit.lessons)}")
            for j, lesson in enumerate(unit.lessons):
                lines.append(f"    {j+1}. [{lesson.concept_id}] {lesson.phrase}")

        if unit.evidence:
            lines.append(f"  Evidence:  {len(unit.evidence)} criteria")

        lines.append("")

    # Validation
    errors = pack.validate()
    if errors:
        lines.append("Validation errors:")
        for e in errors:
            lines.append(f"  - {e}")
    else:
        lines.append("Validation: OK")

    return "\n".join(lines)


def map_curriculum(pack: CurriculumPack) -> str:
    """Render the concept → ops → domain → world mapping as a table."""
    lines = []
    lines.append(f"Curriculum Map: {pack.curriculum} ({pack.grade_band})")
    lines.append("")

    # Column headers
    header = f"{'Concept':<30} {'Ops':<25} {'Domain':<12} {'World':<15} {'Lessons':>7}"
    lines.append(header)
    lines.append("-" * len(header))

    for unit in pack.units:
        for concept in unit.concepts:
            ops_str = ", ".join(concept.poetica_ops[:4])
            if len(concept.poetica_ops) > 4:
                ops_str += "..."

            domain = pack.domain or ""
            # Find lessons for this concept
            lessons = [l for l in unit.lessons if l.concept_id == concept.concept_id]
            if lessons and lessons[0].domain:
                domain = lessons[0].domain

            worlds = ", ".join(unit.visual_worlds[:2])
            if lessons and lessons[0].visual_world:
                worlds = lessons[0].visual_world

            lines.append(
                f"{concept.concept_id:<30} {ops_str:<25} {domain:<12} "
                f"{worlds:<15} {len(lessons):>7}"
            )

    return "\n".join(lines)
