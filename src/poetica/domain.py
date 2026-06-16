"""Domain packs — subject-specific surface languages for Poetica.

A domain pack rewrites domain phrases into canonical Poetica before the parser
sees them. The compiler, gate, and emitters stay unchanged.

Architecture:
  domain source → pre-process (term sub + phrase rewrite) → canonical Poetica
  → parser → compiler → gate → emitter

Domain packs can change: terms, phrases, visuals, examples.
Domain packs cannot change: ops, gate levels, compiler behavior, safety rules.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DomainPack:
    """A loaded domain pack."""
    name: str
    domain: str
    description: str = ""
    terms: Dict[str, Dict[str, str]] = field(default_factory=dict)
    phrases: Dict[str, Dict[str, str]] = field(default_factory=dict)
    visuals: Dict[str, str] = field(default_factory=dict)

    # Compiled phrase patterns (built from phrases dict)
    _phrase_rules: List[tuple] = field(default_factory=list, repr=False)

    def __post_init__(self):
        self._compile_phrases()

    def _compile_phrases(self):
        """Convert phrase patterns with {placeholders} into regex rules."""
        self._phrase_rules = []
        for pattern_str, info in self.phrases.items():
            canonical = info.get("pattern", "")
            if not canonical:
                continue
            # Convert {placeholder} to named regex groups
            regex_str = pattern_str
            placeholders = re.findall(r'\{(\w+)\}', pattern_str)
            for ph in placeholders:
                regex_str = regex_str.replace(f'{{{ph}}}', f'(?P<{ph}>.+?)')
            # Anchor
            regex_str = '^' + regex_str + '$'
            try:
                compiled = re.compile(regex_str)
                self._phrase_rules.append((compiled, canonical, placeholders, info))
            except re.error:
                pass  # Skip invalid patterns

    def preprocess(self, source: str) -> str:
        """Rewrite domain source into canonical Poetica."""
        lines = []
        for line in source.split('\n'):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                lines.append(line)
                continue
            indent = line[:len(line) - len(line.lstrip())]
            rewritten = self._rewrite_line(stripped)
            lines.append(indent + rewritten)
        return '\n'.join(lines)

    def _rewrite_line(self, line: str) -> str:
        """Rewrite a single line: term substitution then phrase matching."""
        # Term substitution
        result = self._substitute_terms(line)
        # Phrase rewriting
        result = self._rewrite_phrase(result)
        return result

    def _substitute_terms(self, line: str) -> str:
        """Replace domain terms with their canonical forms."""
        result = line
        # Sort by length descending so longer terms match first
        sorted_terms = sorted(self.terms.items(), key=lambda x: len(x[0]), reverse=True)
        for term, info in sorted_terms:
            maps_to = info.get("maps_to", term.replace(".", "_"))
            result = result.replace(term, maps_to)
        return result

    def _rewrite_phrase(self, line: str) -> str:
        """Try to match a domain phrase and rewrite to canonical Poetica."""
        for regex, canonical, placeholders, info in self._phrase_rules:
            m = regex.match(line)
            if m:
                result = canonical
                for ph in placeholders:
                    result = result.replace(f'{{{ph}}}', m.group(ph))
                return result
        return line

    def get_visual(self, op_name: str) -> Optional[str]:
        """Get domain-specific visual description for an op, if defined."""
        return self.visuals.get(op_name)


def load_domain(path: str) -> DomainPack:
    """Load a domain pack from a YAML or JSON file."""
    with open(path, 'r') as f:
        raw = f.read()

    if path.endswith('.json'):
        data = json.loads(raw)
    else:
        # Try YAML, fall back to JSON
        try:
            import yaml
            data = yaml.safe_load(raw)
        except ImportError:
            data = json.loads(raw)

    return DomainPack(
        name=data.get("name", ""),
        domain=data.get("domain", ""),
        description=data.get("description", ""),
        terms=data.get("terms", {}),
        phrases=data.get("phrases", {}),
        visuals=data.get("visuals", {}),
    )


def find_domain(name: str) -> Optional[str]:
    """Find a built-in domain pack by name. Returns path or None."""
    # Check built-in domains directory
    base = os.path.join(os.path.dirname(__file__), '..', '..', 'examples', 'domains')
    base = os.path.normpath(base)
    for ext in ('.yaml', '.yml', '.json'):
        path = os.path.join(base, name + ext)
        if os.path.exists(path):
            return path
    return None


def list_domains() -> List[str]:
    """List available built-in domain pack names."""
    base = os.path.join(os.path.dirname(__file__), '..', '..', 'examples', 'domains')
    base = os.path.normpath(base)
    if not os.path.isdir(base):
        return []
    domains = []
    for f in sorted(os.listdir(base)):
        if f.endswith(('.yaml', '.yml', '.json')):
            name = os.path.splitext(f)[0]
            if name not in domains:
                domains.append(name)
    return domains
