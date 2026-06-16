# Poetica MCP Agent Demo

Proof that an AI agent can use Poetica as an MCP tool server — not just call the CLI.

## What This Proves

```
Claude did not write Python directly.
Claude wrote/used Poetica.
Poetica compiled/lowered it.
The gate checked it.
The bridge showed what would execute.
The receipt/transcript proves it.
```

## Setup

```bash
# Register the Poetica MCP server (user scope — available from any directory)
claude mcp add --scope user poetica /path/to/poetica_mcp_wrapper.sh
```

## MCP Tools

| Tool | Description | Default |
|------|-------------|---------|
| `poetica_compile` | Poem → target language code | — |
| `poetica_lower` | Poem → operation tokens (auditable JSON) | format=json |
| `poetica_bridge` | Execute bridge ops (run/test/build/vcs/fs/pipe/deploy) | dry-run |
| `poetica_run` | Full pipeline: compile → lower → bridge | dry-run |
| `poetica_ops` | List all 50 operation tokens | — |
| `poetica_check` | Gate-check a poem without compiling | — |
| `poetica_targets` | List supported targets + poem-type aliases | — |

## Gate Levels

| Level | Capabilities | Example Tokens |
|-------|-------------|---------------|
| L1 | Read-only | fs.read, vcs.status, pipe.wc |
| L2 | + Search/filter | fs.find, pipe.grep, pipe.jq |
| L3 | + Transform | transform.serialize, transform.append |
| L4 | + Execute/write | run.python, build.rust, vcs.commit |
| L5 | + System | (reserved) |

An AI agent starts at L1 and earns higher levels through trust.

## Safety

- **Dry-run by default** — bridge and run tools show what WOULD execute without doing it
- **Gate enforcement** — L1 agent cannot call L4 operations
- **No shell=True** — all commands go through validation, never string interpolation
- **Receipted** — every action produces a timestamped, hashed receipt

## Transcript

See [transcript.txt](transcript.txt) for the full live demo output.

## Architecture

```
AI Agent
  ↓ MCP tool call
Poetica MCP Server (stdio transport)
  ↓ routes to handler
  ├── poetica_compile → PoeticaParser → PoeticaCompiler → Gate → Emitter → code
  ├── poetica_lower   → lower_source() → operation tokens (JSON)
  ├── poetica_bridge  → resolve() → gate check → dry-run or execute → receipt
  ├── poetica_run     → compile_and_run() → full pipeline
  ├── poetica_ops     → _OP_TOKEN_MAP + list_bridge_ops()
  ├── poetica_check   → Gate.check() → PASS/FAIL
  └── poetica_targets → list_targets() → poem-type aliases
```
