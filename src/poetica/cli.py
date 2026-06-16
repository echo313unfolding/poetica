"""Poetica CLI — compile poems from the command line.

Usage:
    poetica compile program.poem --type sonnet
    poetica compile program.poem --target python --level 2
    poetica targets
    echo "seed x with 42\nemit x" | poetica compile - --type haiku
"""

import argparse
import json
import sys

from poetica import compile_poem, __version__
from poetica.parser import PoeticaParser
from poetica.compiler import PoeticaCompiler
from poetica.gate import Gate, GateError
from poetica.receipt import Receipt
from poetica.emitters import get_emitter, list_targets
from poetica.cmd import run_cmd
from poetica.intent import IntentError
from poetica.canvas import visualize_poem, visualize_command, to_mermaid, to_json_graph, to_ascii


def cmd_compile(args):
    """Compile a .poem file to target language code."""
    if args.file == '-':
        source = sys.stdin.read()
    else:
        with open(args.file, 'r') as f:
            source = f.read()

    target = args.type or args.target or "python"
    level = args.level

    try:
        code = compile_poem(source, target=target, level=level)
    except GateError as e:
        print(f"Gate REJECT: {e}", file=sys.stderr)
        sys.exit(1)

    if args.receipt:
        parser = PoeticaParser()
        elements = parser.parse(source)
        compiler = PoeticaCompiler()
        ir = compiler.compile(elements, source)
        gate = Gate(level=level, allow_external=(level >= 4))
        decisions = [d.to_dict() for d in gate.check_all(ir)]
        receipt = Receipt(
            source_hash=ir["source_hash"],
            target=target,
            gate_level=level,
            gate_policy=gate.policy_hash,
            decisions=decisions,
            output_hash=Receipt.hash_output(code),
        )
        print(receipt.to_json(), file=sys.stderr)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(code)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(code)


def cmd_targets(args):
    """List available poem types and their target languages."""
    targets = list_targets()
    for poem_type, lang in targets.items():
        print(f"  {poem_type:10s} -> {lang}")


def cmd_nl(args):
    """NL text → gated shell command → dry-run or execute → receipt."""
    try:
        receipt = run_cmd(
            text=args.text,
            level=args.level,
            approve=args.approve,
            yes=args.yes,
        )
    except IntentError as e:
        print(f"Intent error: {e}", file=sys.stderr)
        sys.exit(1)

    print(receipt.to_json())
    if not receipt.approved:
        if receipt.gate_decision == "REJECT":
            sys.exit(1)


def cmd_visualize(args):
    """Visualize a poem as a concept diagram."""
    if args.file == '-':
        source = sys.stdin.read()
    else:
        with open(args.file, 'r') as f:
            source = f.read()

    nodes = visualize_poem(source, level=args.level)

    # Extract program name from source
    name = "program"
    for line in source.split('\n'):
        stripped = line.strip()
        if stripped.startswith("name "):
            name = stripped[5:].strip()
            break

    fmt = args.format
    if fmt == "mermaid":
        print(to_mermaid(nodes, name))
    elif fmt == "json":
        print(to_json_graph(nodes, name))
    elif fmt == "ascii":
        print(to_ascii(nodes, name))


def cmd_explain_command(args):
    """Visualize what a shell command does."""
    nodes = visualize_command(args.command)
    fmt = args.format
    if fmt == "mermaid":
        print(to_mermaid(nodes, args.command))
    elif fmt == "json":
        print(to_json_graph(nodes, args.command))
    elif fmt == "ascii":
        print(to_ascii(nodes, args.command))


def cmd_check(args):
    """Dry-run: parse and gate-check without generating code."""
    if args.file == '-':
        source = sys.stdin.read()
    else:
        with open(args.file, 'r') as f:
            source = f.read()

    parser = PoeticaParser()
    elements = parser.parse(source)
    compiler = PoeticaCompiler()
    ir = compiler.compile(elements, source)

    gate = Gate(level=args.level, allow_external=(args.level >= 4))
    decisions = gate.check_all(ir)

    rejected = [d for d in decisions if d.verdict == "REJECT"]
    if rejected:
        for d in rejected:
            print(f"  REJECT  {d.op:12s}  {d.reason} (needs L{d.level})", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"OK: {len(decisions)} ops, all allowed at L{args.level}")


def main():
    p = argparse.ArgumentParser(
        prog="poetica",
        description="Write what you mean. Compile to what you need.",
    )
    p.add_argument("--version", action="version", version=f"poetica {__version__}")
    sub = p.add_subparsers(dest="command")

    # compile
    comp = sub.add_parser("compile", help="Compile a .poem file to code")
    comp.add_argument("file", help="Path to .poem file (or - for stdin)")
    comp.add_argument("--type", "-t", help="Poem type (sonnet, haiku, ballad, ode, prose, verse)")
    comp.add_argument("--target", help="Target language (python, rust, javascript, go, bash, sql)")
    comp.add_argument("--level", "-l", type=int, default=1, help="Capability level 1-5 (default: 1)")
    comp.add_argument("--output", "-o", help="Output file (default: stdout)")
    comp.add_argument("--receipt", action="store_true", help="Print receipt to stderr")
    comp.set_defaults(func=cmd_compile)

    # targets
    tgt = sub.add_parser("targets", help="List available poem types")
    tgt.set_defaults(func=cmd_targets)

    # check
    chk = sub.add_parser("check", help="Gate-check a poem without compiling")
    chk.add_argument("file", help="Path to .poem file (or - for stdin)")
    chk.add_argument("--level", "-l", type=int, default=1, help="Capability level 1-5 (default: 1)")
    chk.set_defaults(func=cmd_check)

    # visualize
    viz = sub.add_parser("visualize", help="Visualize a poem as a concept diagram")
    viz.add_argument("file", help="Path to .poem file (or - for stdin)")
    viz.add_argument("--format", "-f", choices=["mermaid", "json", "ascii"],
                     default="ascii", help="Output format (default: ascii)")
    viz.add_argument("--level", "-l", type=int, default=5,
                     help="Gate level for annotation (default: 5)")
    viz.set_defaults(func=cmd_visualize)

    # explain-command
    exc = sub.add_parser("explain-command", help="Visualize what a shell command does")
    exc.add_argument("command", help="Shell command to explain (e.g. 'ls -la')")
    exc.add_argument("--format", "-f", choices=["mermaid", "json", "ascii"],
                     default="ascii", help="Output format (default: ascii)")
    exc.set_defaults(func=cmd_explain_command)

    # cmd
    cmd = sub.add_parser("cmd", help="NL to gated shell command")
    cmd.add_argument("text", help="Natural language command")
    cmd.add_argument("--dry-run", action="store_true", default=True,
                     help="Show what would run without executing (default)")
    cmd.add_argument("--approve", action="store_true",
                     help="Actually execute the command")
    cmd.add_argument("--level", "-l", type=int, default=1,
                     help="Gate level 1-5 (default: 1)")
    cmd.add_argument("--yes", "-y", action="store_true",
                     help="Auto-confirm for apt commands")
    cmd.set_defaults(func=cmd_nl)

    args = p.parse_args()
    if not args.command:
        p.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
