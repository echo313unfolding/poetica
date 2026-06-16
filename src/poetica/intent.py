"""Deterministic NL intent mapper for poetica cmd.

NL text → intent IR → gate check → argv list.

No LLM. No eval. No shell interpolation.
User text never enters the command directly.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Intent:
    """Parsed intent from natural language."""
    op: str                    # e.g. "package.update_index", "fs.list"
    argv: List[str]            # command as argv list, never a raw string
    level: int                 # gate level required
    description: str           # human-readable summary
    params: dict = field(default_factory=dict)


class IntentError(Exception):
    """Raised when NL text cannot be mapped to an intent."""
    pass


# Each rule: (compiled_regex, handler_name)
# Order matters — first match wins.
_RULES: List[Tuple[re.Pattern, str]] = []


def _rule(pattern: str):
    """Decorator to register an intent rule."""
    compiled = re.compile(pattern, re.IGNORECASE)
    def decorator(fn):
        _RULES.append((compiled, fn))
        return fn
    return decorator


@_rule(r'^(?:update\s+package\s+index|refresh\s+packages?|apt\s+update)$')
def _intent_apt_update(m: re.Match, yes: bool = False) -> Intent:
    return Intent(
        op="package.update_index",
        argv=["sudo", "apt", "update"],
        level=4,
        description="Update package index",
    )


@_rule(r'^(?:upgrade\s+packages?|apt\s+upgrade)$')
def _intent_apt_upgrade(m: re.Match, yes: bool = False) -> Intent:
    argv = ["sudo", "apt", "upgrade"]
    if yes:
        argv.append("-y")
    return Intent(
        op="package.upgrade",
        argv=argv,
        level=4,
        description="Upgrade installed packages",
        params={"auto_yes": yes},
    )


@_rule(r'^install\s+(.+)$')
def _intent_apt_install(m: re.Match, yes: bool = False) -> Intent:
    package = m.group(1).strip()
    if not package or not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9.+\-]+$', package):
        raise IntentError(f"Invalid package name: {package!r}")
    argv = ["sudo", "apt", "install", package]
    if yes:
        argv.insert(3, "-y")
    return Intent(
        op="package.install",
        argv=argv,
        level=4,
        description=f"Install package: {package}",
        params={"package": package, "auto_yes": yes},
    )


@_rule(r'^(?:list\s+files?|show\s+files?|ls)$')
def _intent_ls(m: re.Match, yes: bool = False) -> Intent:
    return Intent(
        op="fs.list",
        argv=["ls", "-la"],
        level=1,
        description="List files in current directory",
    )


@_rule(r'^(?:show\s+current\s+directory|pwd|where\s+am\s+i)$')
def _intent_pwd(m: re.Match, yes: bool = False) -> Intent:
    return Intent(
        op="fs.pwd",
        argv=["pwd"],
        level=1,
        description="Show current working directory",
    )


def parse_intent(text: str, yes: bool = False) -> Intent:
    """Map natural language text to an Intent.

    Args:
        text: Natural language command.
        yes: Whether --yes was passed (auto-confirm for apt).

    Returns:
        Intent with op, argv, level, description.

    Raises:
        IntentError: If no intent matches.
    """
    cleaned = text.strip()
    if not cleaned:
        raise IntentError("Empty input")

    for pattern, handler in _RULES:
        m = pattern.match(cleaned)
        if m:
            return handler(m, yes=yes)

    raise IntentError(f"Unknown intent: {cleaned!r}")
