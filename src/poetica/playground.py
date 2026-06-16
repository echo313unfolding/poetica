"""Poetica Playground — run poems in visual worlds, step by step."""

from typing import List, Optional

from poetica.parser import PoeticaParser
from poetica.compiler import PoeticaCompiler
from poetica.visual import BaseWorld, Frame, get_world


def play_poem(source: str, world_name: str) -> List[Frame]:
    """Parse a poem, run it through a visual world, return frames."""
    parser = PoeticaParser()
    compiler = PoeticaCompiler()
    elements = parser.parse(source)
    ir = compiler.compile(elements, source)

    world = get_world(world_name)
    frames = []
    for op in ir["ops"]:
        frame = world.step(op)
        frames.append(frame)
    return frames


def render_playback(frames: List[Frame], name: str = "program") -> str:
    """Render frames as a step-by-step ASCII playback."""
    lines = []
    width = 60

    lines.append(f"{'=' * width}")
    lines.append(f"  PLAY: {name}")
    lines.append(f"{'=' * width}")

    for frame in frames:
        lines.append("")
        lines.append(f"  Step {frame.step}: [{frame.op}] {frame.description}")
        lines.append(f"  {'-' * (width - 4)}")
        for state_line in frame.state_ascii.split("\n"):
            lines.append(f"  {state_line}")

    lines.append("")
    lines.append(f"{'=' * width}")
    lines.append(f"  END ({len(frames)} steps)")
    lines.append(f"{'=' * width}")

    return "\n".join(lines)
