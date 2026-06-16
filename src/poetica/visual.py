"""Visual worlds for Poetica Playground — simulate IR ops as domain-specific actions."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Frame:
    """A single visual frame in a world simulation."""
    step: int
    op: str
    description: str
    state_ascii: str
    details: Dict[str, Any] = field(default_factory=dict)


class BaseWorld:
    """Base class for visual worlds."""
    name: str = "base"

    def step(self, op: Dict[str, Any]) -> Frame:
        raise NotImplementedError

    def render(self) -> str:
        raise NotImplementedError

    def reset(self):
        raise NotImplementedError


class RobotGridWorld(BaseWorld):
    """A robot moving on a 2D grid."""
    name = "robot_grid"

    def __init__(self, width: int = 5, height: int = 5):
        self.width = width
        self.height = height
        self.reset()

    def reset(self):
        self.x = 0
        self.y = 0
        self.direction = "north"
        self.trail: List[tuple] = [(0, 0)]
        self._step_count = 0
        self._vars: Dict[str, Any] = {}

    def step(self, op: Dict[str, Any]) -> Frame:
        self._step_count += 1
        op_name = op.get("op", "")

        if op_name == "seed":
            return self._do_seed(op)
        elif op_name == "flow":
            return self._do_flow(op)
        elif op_name == "emit":
            return self._do_emit(op)
        elif op_name in ("when", "if", "else_when", "else"):
            return self._do_decision(op)
        elif op_name == "bloom":
            return Frame(
                step=self._step_count, op=op_name,
                description=f"Robot stops: {op.get('value', '')}",
                state_ascii=self.render(),
            )
        else:
            return Frame(
                step=self._step_count, op=op_name,
                description=f"{op_name}: {op}",
                state_ascii=self.render(),
            )

    def _do_seed(self, op: Dict[str, Any]) -> Frame:
        name = op.get("name", "")
        value = op.get("value", "")
        self._vars[name] = value
        if name == "x":
            self.x = int(value) if value.isdigit() else 0
        elif name == "y":
            self.y = int(value) if value.isdigit() else 0
        elif name == "direction":
            self.direction = value.strip('"').strip("'")
        return Frame(
            step=self._step_count, op="seed",
            description=f"Set {name} = {value}",
            state_ascii=self.render(),
            details={"name": name, "value": value},
        )

    def _do_flow(self, op: Dict[str, Any]) -> Frame:
        dest = op.get("dest", "")
        source = op.get("source", "")
        if dest == "y":
            if "+" in source:
                self.y = min(self.y + 1, self.height - 1)
            elif "-" in source:
                self.y = max(self.y - 1, 0)
        elif dest == "x":
            if "+" in source:
                self.x = min(self.x + 1, self.width - 1)
            elif "-" in source:
                self.x = max(self.x - 1, 0)
        elif dest == "direction":
            self.direction = source.strip('"').strip("'")
        self.trail.append((self.x, self.y))
        return Frame(
            step=self._step_count, op="flow",
            description=f"Move: {dest} = {source}  (robot at {self.x},{self.y})",
            state_ascii=self.render(),
        )

    def _do_emit(self, op: Dict[str, Any]) -> Frame:
        value = op.get("value", "")
        label = op.get("label", "")
        msg = f'[{label}] {value}' if label else value
        return Frame(
            step=self._step_count, op="emit",
            description=f"Output: {msg}",
            state_ascii=self.render(),
        )

    def _do_decision(self, op: Dict[str, Any]) -> Frame:
        cond = op.get("condition", "") or f"{op.get('left', '')} == {op.get('right', '')}"
        return Frame(
            step=self._step_count, op=op["op"],
            description=f"Check: {cond}",
            state_ascii=self.render(),
        )

    def render(self) -> str:
        lines = []
        trail_set = set(self.trail)
        for row in range(self.height - 1, -1, -1):
            cells = []
            for col in range(self.width):
                if col == self.x and row == self.y:
                    arrow = {"north": "^", "south": "v", "east": ">", "west": "<"}
                    cells.append(f" {arrow.get(self.direction, '@')} ")
                elif (col, row) in trail_set:
                    cells.append(" . ")
                else:
                    cells.append("   ")
            lines.append("|" + "|".join(cells) + "|")
            lines.append("+" + "+".join(["---"] * self.width) + "+")
        # Add column numbers
        cols = " " + "  ".join(f" {i} " for i in range(self.width))
        lines.append(cols)
        return "\n".join(lines)


class GardenWorld(BaseWorld):
    """A garden where plants grow."""
    name = "garden"

    PLANT_STAGES = {0: ".", 1: "o", 2: "O", 3: "*"}

    def __init__(self, width: int = 6):
        self.width = width
        self.reset()

    def reset(self):
        self.plants: List[Dict[str, Any]] = []
        self._step_count = 0
        self._vars: Dict[str, Any] = {}

    def step(self, op: Dict[str, Any]) -> Frame:
        self._step_count += 1
        op_name = op.get("op", "")

        if op_name == "seed":
            return self._do_seed(op)
        elif op_name == "grow":
            return self._do_grow(op)
        elif op_name == "emit":
            return self._do_emit(op)
        elif op_name == "for":
            return Frame(
                step=self._step_count, op="for",
                description=f"For each {op.get('var', '?')} in {op.get('collection', '?')}:",
                state_ascii=self.render(),
            )
        elif op_name == "pack":
            return Frame(
                step=self._step_count, op="pack",
                description=f"Harvest: pack {op.get('data', '?')} as {op.get('format', '?')}",
                state_ascii=self.render(),
            )
        elif op_name == "bloom":
            # Bloom all plants to max stage
            for p in self.plants:
                p["stage"] = 3
            return Frame(
                step=self._step_count, op="bloom",
                description=f"Garden blooms: {op.get('value', '')}",
                state_ascii=self.render(),
            )
        else:
            return Frame(
                step=self._step_count, op=op_name,
                description=f"{op_name}: {op}",
                state_ascii=self.render(),
            )

    def _do_seed(self, op: Dict[str, Any]) -> Frame:
        name = op.get("name", "")
        value = op.get("value", "")
        self._vars[name] = value
        return Frame(
            step=self._step_count, op="seed",
            description=f"Prepare plot: {name} = {value}",
            state_ascii=self.render(),
        )

    def _do_grow(self, op: Dict[str, Any]) -> Frame:
        plant_name = op.get("source", "").strip('"').strip("'")
        self.plants.append({"name": plant_name, "stage": 1})
        return Frame(
            step=self._step_count, op="grow",
            description=f"Plant: {plant_name}",
            state_ascii=self.render(),
        )

    def _do_emit(self, op: Dict[str, Any]) -> Frame:
        # Water plants — advance stage
        for p in self.plants:
            if p["stage"] < 3:
                p["stage"] = min(p["stage"] + 1, 3)
        value = op.get("value", "")
        label = op.get("label", "")
        msg = f'[{label}] {value}' if label else value
        return Frame(
            step=self._step_count, op="emit",
            description=f"Tend: {msg}",
            state_ascii=self.render(),
        )

    def render(self) -> str:
        if not self.plants:
            return "  [empty garden plot]"
        lines = []
        # Header
        lines.append("  " + "=" * (self.width * 6 + 1))
        # Plant row
        cells = []
        for p in self.plants[:self.width]:
            icon = self.PLANT_STAGES.get(p["stage"], "?")
            cells.append(f"  {icon}  ")
        row = "|" + "|".join(cells) + "|"
        lines.append("  " + row)
        # Labels
        labels = []
        for p in self.plants[:self.width]:
            name = p["name"][:4]
            labels.append(f"{name:^5}")
        lines.append("  |" + "|".join(labels) + "|")
        # Ground
        lines.append("  " + "=" * (self.width * 6 + 1))
        return "\n".join(lines)


class FilesystemWorld(BaseWorld):
    """A simulated filesystem with directories and files."""
    name = "filesystem"

    def __init__(self):
        self.reset()

    def reset(self):
        self.cwd = "/home"
        self.files: List[str] = []
        self._step_count = 0
        self._vars: Dict[str, Any] = {}

    def step(self, op: Dict[str, Any]) -> Frame:
        self._step_count += 1
        op_name = op.get("op", "")

        if op_name == "seed":
            return self._do_seed(op)
        elif op_name == "grow":
            return self._do_grow(op)
        elif op_name == "emit":
            return self._do_emit(op)
        elif op_name == "for":
            return Frame(
                step=self._step_count, op="for",
                description=f"List each {op.get('var', '?')} in {op.get('collection', '?')}:",
                state_ascii=self.render(),
            )
        elif op_name == "flow":
            return self._do_flow(op)
        elif op_name == "bloom":
            return Frame(
                step=self._step_count, op="bloom",
                description=f"Done: {op.get('value', '')}",
                state_ascii=self.render(),
            )
        else:
            return Frame(
                step=self._step_count, op=op_name,
                description=f"{op_name}: {op}",
                state_ascii=self.render(),
            )

    def _do_seed(self, op: Dict[str, Any]) -> Frame:
        name = op.get("name", "")
        value = op.get("value", "")
        self._vars[name] = value
        if name == "path":
            self.cwd = value.strip('"').strip("'")
        elif name == "files":
            # Parse list literal
            inner = value.strip("[]")
            if inner:
                self.files = [f.strip().strip('"').strip("'") for f in inner.split(",")]
        return Frame(
            step=self._step_count, op="seed",
            description=f"Set {name} = {value}",
            state_ascii=self.render(),
        )

    def _do_grow(self, op: Dict[str, Any]) -> Frame:
        filename = op.get("source", "").strip('"').strip("'")
        self.files.append(filename)
        return Frame(
            step=self._step_count, op="grow",
            description=f"Create file: {filename}",
            state_ascii=self.render(),
        )

    def _do_emit(self, op: Dict[str, Any]) -> Frame:
        value = op.get("value", "")
        return Frame(
            step=self._step_count, op="emit",
            description=f"Show: {value}",
            state_ascii=self.render(),
        )

    def _do_flow(self, op: Dict[str, Any]) -> Frame:
        source = op.get("source", "")
        dest = op.get("dest", "")
        return Frame(
            step=self._step_count, op="flow",
            description=f"Move: {source} -> {dest}",
            state_ascii=self.render(),
        )

    def render(self) -> str:
        lines = []
        lines.append(f"  {self.cwd}/")
        if not self.files:
            lines.append("    (empty)")
        else:
            for i, f in enumerate(self.files):
                connector = "+-" if i < len(self.files) - 1 else "\\-"
                lines.append(f"    {connector} {f}")
        return "\n".join(lines)


WORLDS = {
    "robot_grid": RobotGridWorld,
    "garden": GardenWorld,
    "filesystem": FilesystemWorld,
}


def get_world(name: str) -> BaseWorld:
    """Create a world by name."""
    cls = WORLDS.get(name)
    if cls is None:
        raise ValueError(f"Unknown world: {name}. Available: {', '.join(WORLDS.keys())}")
    return cls()


def list_worlds() -> List[str]:
    """List available world names."""
    return list(WORLDS.keys())
