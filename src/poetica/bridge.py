"""Poetica bridge — compile, run, test, build, deploy through operation tokens.

Extends the lowering layer to cover the full lifecycle:
    compose (Poetica) → compile (emitter) → run/test/build/deploy (bridge)

Every action: operation token → gate check → argv list → receipt.
AI or human composes tokens. Deterministic lowering handles syntax.
The gate handles safety. The receipt handles proof.

Bridge operation tokens (all L4 unless noted):

  run.python         python3 <file>                    L4
  run.rust            cargo run                         L4
  run.node            node <file>                       L4
  run.bash            bash <file>                       L4
  run.go              go run <file>                     L4

  test.python         python3 -m pytest <path>          L4
  test.rust            cargo test                       L4
  test.node            npm test                         L4

  build.rust           cargo build [--release]          L4
  build.node           npm run build                    L4
  build.python         python3 -m build                 L4
  build.go             go build                         L4
  build.c              gcc <file> -o <out>              L4
  build.make           make [target]                    L4

  vcs.status           git status                       L1
  vcs.diff             git diff                         L1
  vcs.log              git log --oneline -N             L1
  vcs.add              git add <files>                  L4
  vcs.commit           git commit -m <msg>              L4

  pipe.jq              <input> | jq <filter>            L2
  pipe.grep            grep <pattern> <file>            L2
  pipe.wc              wc -l <file>                     L1
  pipe.sort            sort <file>                      L1
  pipe.head            head -n N <file>                 L1

  fs.read              cat <file>                       L1
  fs.list              ls -la [path]                    L1
  fs.find              find <path> -name <pattern>      L2
  fs.mkdir             mkdir -p <path>                  L4
  fs.write             tee <file>                       L4
  fs.remove            rm <file>                        L4

  package.install      pip install / cargo add / npm i  L4
  package.list         pip list / cargo tree / npm ls   L1

  deploy.docker_build  docker build -t <tag> .          L4
  deploy.docker_run    docker run <image>               L4
  deploy.scp           scp <src> <dst>                  L4

No shell=True. No string interpolation. User/AI input never enters
argv directly — it goes through validation first.
"""

import hashlib
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class BridgeOp:
    """A single bridge operation — what to run and at what gate level."""
    token: str           # e.g. "run.python", "test.rust"
    argv: List[str]      # command as argv list
    level: int           # minimum gate level required
    description: str     # human-readable summary
    params: Dict[str, Any] = field(default_factory=dict)
    cwd: Optional[str] = None
    stdin_data: Optional[str] = None


@dataclass
class BridgeReceipt:
    """Receipt for a bridge operation."""
    schema: str = "poetica.bridge.receipt.v1"
    operation_token: str = ""
    argv: List[str] = field(default_factory=list)
    gate_level: int = 1
    gate_decision: str = ""
    approved: bool = False
    executed: bool = False
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    stdout_hash: str = ""
    stderr_hash: str = ""
    timestamp: str = ""
    duration_ms: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if not self.executed:
            for k in ("exit_code", "stdout", "stderr", "stdout_hash",
                       "stderr_hash", "duration_ms"):
                d.pop(k, None)
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ── Validation helpers ──────────────────────────────────────────────

_SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_\-./][a-zA-Z0-9_\-./]*$')
_SAFE_PACKAGE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._\-]*$')
_SAFE_GIT_MSG = re.compile(r'^[^\x00-\x1f]*$')  # no control chars
_SAFE_JQ_FILTER = re.compile(r'^[a-zA-Z0-9_.\[\]|,\s\-"\'{}:@?/]+$')
_SAFE_GREP_PATTERN = re.compile(r'^.{1,200}$')  # just length-bounded


def _validate_path(path: str, label: str = "path") -> str:
    """Validate a file path — no shell metacharacters, no traversal tricks."""
    if not path:
        raise BridgeError(f"Empty {label}")
    if not _SAFE_FILENAME.match(path):
        raise BridgeError(f"Unsafe {label}: {path!r}")
    # Block obvious traversal
    resolved = str(Path(path).resolve())
    if ".." in path.split("/"):
        raise BridgeError(f"Path traversal in {label}: {path!r}")
    return path


def _validate_package(name: str) -> str:
    if not _SAFE_PACKAGE.match(name):
        raise BridgeError(f"Invalid package name: {name!r}")
    return name


def _validate_git_message(msg: str) -> str:
    if not msg or not _SAFE_GIT_MSG.match(msg):
        raise BridgeError(f"Invalid git message")
    if len(msg) > 500:
        raise BridgeError(f"Git message too long ({len(msg)} > 500)")
    return msg


class BridgeError(Exception):
    pass


# ── Operation registry ──────────────────────────────────────────────

def _op_run_python(params: Dict) -> BridgeOp:
    f = _validate_path(params.get("file", ""), "file")
    return BridgeOp(
        token="run.python", argv=["python3", f], level=4,
        description=f"Run Python: {f}")

def _op_run_rust(params: Dict) -> BridgeOp:
    argv = ["cargo", "run"]
    if params.get("release"):
        argv.append("--release")
    return BridgeOp(
        token="run.rust", argv=argv, level=4,
        description="Run Rust project (cargo run)")

def _op_run_node(params: Dict) -> BridgeOp:
    f = _validate_path(params.get("file", ""), "file")
    return BridgeOp(
        token="run.node", argv=["node", f], level=4,
        description=f"Run Node.js: {f}")

def _op_run_bash(params: Dict) -> BridgeOp:
    f = _validate_path(params.get("file", ""), "file")
    return BridgeOp(
        token="run.bash", argv=["bash", f], level=4,
        description=f"Run Bash script: {f}")

def _op_run_go(params: Dict) -> BridgeOp:
    f = _validate_path(params.get("file", ""), "file")
    return BridgeOp(
        token="run.go", argv=["go", "run", f], level=4,
        description=f"Run Go: {f}")

# ── Test ──

def _op_test_python(params: Dict) -> BridgeOp:
    argv = ["python3", "-m", "pytest"]
    path = params.get("path", "")
    if path:
        argv.append(_validate_path(path, "test path"))
    if params.get("verbose"):
        argv.append("-v")
    return BridgeOp(
        token="test.python", argv=argv, level=4,
        description="Run Python tests (pytest)")

def _op_test_rust(params: Dict) -> BridgeOp:
    return BridgeOp(
        token="test.rust", argv=["cargo", "test"], level=4,
        description="Run Rust tests (cargo test)")

def _op_test_node(params: Dict) -> BridgeOp:
    return BridgeOp(
        token="test.node", argv=["npm", "test"], level=4,
        description="Run Node.js tests (npm test)")

# ── Build ──

def _op_build_rust(params: Dict) -> BridgeOp:
    argv = ["cargo", "build"]
    if params.get("release"):
        argv.append("--release")
    return BridgeOp(
        token="build.rust", argv=argv, level=4,
        description="Build Rust project")

def _op_build_node(params: Dict) -> BridgeOp:
    return BridgeOp(
        token="build.node", argv=["npm", "run", "build"], level=4,
        description="Build Node.js project")

def _op_build_python(params: Dict) -> BridgeOp:
    return BridgeOp(
        token="build.python", argv=["python3", "-m", "build"], level=4,
        description="Build Python package")

def _op_build_go(params: Dict) -> BridgeOp:
    argv = ["go", "build"]
    out = params.get("output")
    if out:
        argv.extend(["-o", _validate_path(out, "output")])
    return BridgeOp(
        token="build.go", argv=argv, level=4,
        description="Build Go project")

def _op_build_c(params: Dict) -> BridgeOp:
    f = _validate_path(params.get("file", ""), "file")
    out = _validate_path(params.get("output", "a.out"), "output")
    return BridgeOp(
        token="build.c", argv=["gcc", f, "-o", out], level=4,
        description=f"Compile C: {f} → {out}")

def _op_build_make(params: Dict) -> BridgeOp:
    argv = ["make"]
    target = params.get("target")
    if target:
        if not re.match(r'^[a-zA-Z0-9_\-]+$', target):
            raise BridgeError(f"Invalid make target: {target!r}")
        argv.append(target)
    return BridgeOp(
        token="build.make", argv=argv, level=4,
        description=f"Run make{' ' + target if target else ''}")

# ── Version control ──

def _op_vcs_status(params: Dict) -> BridgeOp:
    return BridgeOp(
        token="vcs.status", argv=["git", "status"], level=1,
        description="Git status")

def _op_vcs_diff(params: Dict) -> BridgeOp:
    argv = ["git", "diff"]
    if params.get("staged"):
        argv.append("--staged")
    return BridgeOp(
        token="vcs.diff", argv=argv, level=1,
        description="Git diff")

def _op_vcs_log(params: Dict) -> BridgeOp:
    n = min(int(params.get("count", 10)), 100)
    return BridgeOp(
        token="vcs.log", argv=["git", "log", "--oneline", f"-{n}"], level=1,
        description=f"Git log (last {n})")

def _op_vcs_add(params: Dict) -> BridgeOp:
    files = params.get("files", [])
    if isinstance(files, str):
        files = [files]
    validated = [_validate_path(f, "file") for f in files]
    if not validated:
        raise BridgeError("No files to add")
    return BridgeOp(
        token="vcs.add", argv=["git", "add"] + validated, level=4,
        description=f"Git add {len(validated)} file(s)")

def _op_vcs_commit(params: Dict) -> BridgeOp:
    msg = _validate_git_message(params.get("message", ""))
    return BridgeOp(
        token="vcs.commit", argv=["git", "commit", "-m", msg], level=4,
        description="Git commit")

# ── Pipe / filter ──

def _op_pipe_jq(params: Dict) -> BridgeOp:
    f = params.get("filter", ".")
    if not _SAFE_JQ_FILTER.match(f):
        raise BridgeError(f"Unsafe jq filter: {f!r}")
    inp = params.get("file")
    if inp:
        argv = ["jq", f, _validate_path(inp, "file")]
    else:
        argv = ["jq", f]
    return BridgeOp(
        token="pipe.jq", argv=argv, level=2,
        description=f"jq {f}",
        stdin_data=params.get("stdin"))

def _op_pipe_grep(params: Dict) -> BridgeOp:
    pattern = params.get("pattern", "")
    if not _SAFE_GREP_PATTERN.match(pattern):
        raise BridgeError(f"Unsafe grep pattern")
    f = _validate_path(params.get("file", ""), "file")
    return BridgeOp(
        token="pipe.grep", argv=["grep", pattern, f], level=2,
        description=f"grep {pattern!r} in {f}")

def _op_pipe_wc(params: Dict) -> BridgeOp:
    f = _validate_path(params.get("file", ""), "file")
    return BridgeOp(
        token="pipe.wc", argv=["wc", "-l", f], level=1,
        description=f"Count lines in {f}")

def _op_pipe_sort(params: Dict) -> BridgeOp:
    f = _validate_path(params.get("file", ""), "file")
    return BridgeOp(
        token="pipe.sort", argv=["sort", f], level=1,
        description=f"Sort {f}")

def _op_pipe_head(params: Dict) -> BridgeOp:
    f = _validate_path(params.get("file", ""), "file")
    n = min(int(params.get("count", 10)), 1000)
    return BridgeOp(
        token="pipe.head", argv=["head", f"-n{n}", f], level=1,
        description=f"First {n} lines of {f}")

# ── Filesystem ──

def _op_fs_read(params: Dict) -> BridgeOp:
    f = _validate_path(params.get("file", ""), "file")
    return BridgeOp(
        token="fs.read", argv=["cat", f], level=1,
        description=f"Read {f}")

def _op_fs_list(params: Dict) -> BridgeOp:
    path = params.get("path", ".")
    if path != ".":
        _validate_path(path, "path")
    return BridgeOp(
        token="fs.list", argv=["ls", "-la", path], level=1,
        description=f"List {path}")

def _op_fs_find(params: Dict) -> BridgeOp:
    path = _validate_path(params.get("path", "."), "path")
    pattern = params.get("pattern", "*")
    if not re.match(r'^[a-zA-Z0-9_\-.*?]+$', pattern):
        raise BridgeError(f"Unsafe find pattern: {pattern!r}")
    return BridgeOp(
        token="fs.find", argv=["find", path, "-name", pattern], level=2,
        description=f"Find {pattern} in {path}")

def _op_fs_mkdir(params: Dict) -> BridgeOp:
    path = _validate_path(params.get("path", ""), "path")
    return BridgeOp(
        token="fs.mkdir", argv=["mkdir", "-p", path], level=4,
        description=f"Create directory {path}")

def _op_fs_write(params: Dict) -> BridgeOp:
    f = _validate_path(params.get("file", ""), "file")
    content = params.get("content", "")
    return BridgeOp(
        token="fs.write", argv=["tee", f], level=4,
        description=f"Write to {f}",
        stdin_data=content)

def _op_fs_remove(params: Dict) -> BridgeOp:
    f = _validate_path(params.get("file", ""), "file")
    # Never allow rm -rf, only single files
    return BridgeOp(
        token="fs.remove", argv=["rm", f], level=4,
        description=f"Remove {f}")

# ── Package management ──

def _op_package_install(params: Dict) -> BridgeOp:
    pkg = _validate_package(params.get("package", ""))
    manager = params.get("manager", "pip")
    if manager == "pip":
        return BridgeOp(
            token="package.install", argv=["pip3", "install", pkg], level=4,
            description=f"pip install {pkg}")
    elif manager == "cargo":
        return BridgeOp(
            token="package.install", argv=["cargo", "add", pkg], level=4,
            description=f"cargo add {pkg}")
    elif manager == "npm":
        return BridgeOp(
            token="package.install", argv=["npm", "install", pkg], level=4,
            description=f"npm install {pkg}")
    else:
        raise BridgeError(f"Unknown package manager: {manager}")

def _op_package_list(params: Dict) -> BridgeOp:
    manager = params.get("manager", "pip")
    if manager == "pip":
        return BridgeOp(
            token="package.list", argv=["pip3", "list"], level=1,
            description="pip list")
    elif manager == "cargo":
        return BridgeOp(
            token="package.list", argv=["cargo", "tree", "--depth", "1"], level=1,
            description="cargo tree")
    elif manager == "npm":
        return BridgeOp(
            token="package.list", argv=["npm", "ls", "--depth=0"], level=1,
            description="npm ls")
    else:
        raise BridgeError(f"Unknown package manager: {manager}")

# ── Deploy ──

def _op_deploy_docker_build(params: Dict) -> BridgeOp:
    tag = params.get("tag", "app")
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._\-/:]*$', tag):
        raise BridgeError(f"Invalid docker tag: {tag!r}")
    return BridgeOp(
        token="deploy.docker_build",
        argv=["docker", "build", "-t", tag, "."], level=4,
        description=f"Docker build: {tag}")

def _op_deploy_docker_run(params: Dict) -> BridgeOp:
    image = params.get("image", "")
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._\-/:]*$', image):
        raise BridgeError(f"Invalid docker image: {image!r}")
    return BridgeOp(
        token="deploy.docker_run",
        argv=["docker", "run", "--rm", image], level=4,
        description=f"Docker run: {image}")

def _op_deploy_scp(params: Dict) -> BridgeOp:
    src = _validate_path(params.get("source", ""), "source")
    dst = params.get("destination", "")
    if not dst or not re.match(r'^[a-zA-Z0-9@._\-:/]+$', dst):
        raise BridgeError(f"Invalid scp destination: {dst!r}")
    return BridgeOp(
        token="deploy.scp", argv=["scp", src, dst], level=4,
        description=f"SCP {src} → {dst}")


# ── Registry ──

_BRIDGE_OPS: Dict[str, callable] = {
    "run.python": _op_run_python,
    "run.rust": _op_run_rust,
    "run.node": _op_run_node,
    "run.bash": _op_run_bash,
    "run.go": _op_run_go,

    "test.python": _op_test_python,
    "test.rust": _op_test_rust,
    "test.node": _op_test_node,

    "build.rust": _op_build_rust,
    "build.node": _op_build_node,
    "build.python": _op_build_python,
    "build.go": _op_build_go,
    "build.c": _op_build_c,
    "build.make": _op_build_make,

    "vcs.status": _op_vcs_status,
    "vcs.diff": _op_vcs_diff,
    "vcs.log": _op_vcs_log,
    "vcs.add": _op_vcs_add,
    "vcs.commit": _op_vcs_commit,

    "pipe.jq": _op_pipe_jq,
    "pipe.grep": _op_pipe_grep,
    "pipe.wc": _op_pipe_wc,
    "pipe.sort": _op_pipe_sort,
    "pipe.head": _op_pipe_head,

    "fs.read": _op_fs_read,
    "fs.list": _op_fs_list,
    "fs.find": _op_fs_find,
    "fs.mkdir": _op_fs_mkdir,
    "fs.write": _op_fs_write,
    "fs.remove": _op_fs_remove,

    "package.install": _op_package_install,
    "package.list": _op_package_list,

    "deploy.docker_build": _op_deploy_docker_build,
    "deploy.docker_run": _op_deploy_docker_run,
    "deploy.scp": _op_deploy_scp,
}


def list_bridge_ops() -> Dict[str, int]:
    """Return {token: min_level} for all registered bridge operations."""
    result = {}
    for token, builder in _BRIDGE_OPS.items():
        # Build with empty params to get the level (some will fail — catch)
        try:
            op = builder({})
            result[token] = op.level
        except (BridgeError, Exception):
            # Infer from token family
            if token.startswith(("fs.read", "fs.list", "vcs.status",
                                 "vcs.diff", "vcs.log", "pipe.wc",
                                 "pipe.sort", "pipe.head", "package.list")):
                result[token] = 1
            elif token.startswith(("pipe.jq", "pipe.grep", "fs.find")):
                result[token] = 2
            else:
                result[token] = 4
    return result


def resolve(token: str, params: Dict[str, Any] = None) -> BridgeOp:
    """Resolve an operation token to a BridgeOp (validated, not executed).

    Args:
        token: Operation token (e.g. "run.python", "vcs.status").
        params: Parameters for the operation.

    Returns:
        BridgeOp with validated argv.

    Raises:
        BridgeError: If token is unknown or params are invalid.
    """
    builder = _BRIDGE_OPS.get(token)
    if builder is None:
        raise BridgeError(f"Unknown bridge operation: {token!r}")
    return builder(params or {})


def execute(token: str, params: Dict[str, Any] = None,
            level: int = 1, approve: bool = False,
            timeout: int = 60, capture: bool = True) -> BridgeReceipt:
    """Resolve, gate-check, and optionally execute a bridge operation.

    Args:
        token: Operation token.
        params: Parameters for the operation.
        level: Current gate level (1-5).
        approve: If True, actually execute. If False, dry-run only.
        timeout: Execution timeout in seconds.
        capture: If True, capture stdout/stderr.

    Returns:
        BridgeReceipt with full audit trail.
    """
    import time

    try:
        op = resolve(token, params)
    except BridgeError as e:
        return BridgeReceipt(
            operation_token=token,
            gate_level=level,
            gate_decision=f"ERROR: {e}",
            approved=False,
            executed=False,
        )

    # Gate check
    if op.level > level:
        return BridgeReceipt(
            operation_token=op.token,
            argv=op.argv,
            gate_level=level,
            gate_decision=f"REJECT: requires L{op.level}, have L{level}",
            approved=False,
            executed=False,
        )

    # Dry-run
    if not approve:
        return BridgeReceipt(
            operation_token=op.token,
            argv=op.argv,
            gate_level=level,
            gate_decision="ALLOW",
            approved=False,
            executed=False,
        )

    # Execute
    t0 = time.time()
    try:
        result = subprocess.run(
            op.argv,
            capture_output=capture,
            timeout=timeout,
            cwd=op.cwd,
            input=op.stdin_data.encode() if op.stdin_data else None,
        )
        duration_ms = (time.time() - t0) * 1000

        stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
        stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""

        return BridgeReceipt(
            operation_token=op.token,
            argv=op.argv,
            gate_level=level,
            gate_decision="ALLOW",
            approved=True,
            executed=True,
            exit_code=result.returncode,
            stdout=stdout,
            stderr=stderr,
            stdout_hash=hashlib.sha256(result.stdout or b"").hexdigest(),
            stderr_hash=hashlib.sha256(result.stderr or b"").hexdigest(),
            duration_ms=round(duration_ms, 2),
        )
    except subprocess.TimeoutExpired:
        return BridgeReceipt(
            operation_token=op.token,
            argv=op.argv,
            gate_level=level,
            gate_decision="ALLOW",
            approved=True,
            executed=True,
            exit_code=-1,
            stderr=f"Timeout after {timeout}s",
            duration_ms=(time.time() - t0) * 1000,
        )
    except FileNotFoundError:
        return BridgeReceipt(
            operation_token=op.token,
            argv=op.argv,
            gate_level=level,
            gate_decision="ALLOW",
            approved=True,
            executed=True,
            exit_code=-1,
            stderr=f"Command not found: {op.argv[0]}",
        )


# ── Compile-and-run convenience ─────────────────────────────────────

_TARGET_TO_RUNNER = {
    "python": "run.python",
    "rust": "run.rust",
    "javascript": "run.node",
    "go": "run.go",
    "bash": "run.bash",
}

_TARGET_TO_EXT = {
    "python": ".py",
    "rust": ".rs",
    "javascript": ".js",
    "go": ".go",
    "bash": ".sh",
    "sql": ".sql",
}


def compile_and_run(source: str, target: str = "python",
                    level: int = 4, approve: bool = False,
                    domain_pack=None) -> Dict[str, Any]:
    """Full pipeline: Poetica source → compile → write temp file → run.

    Returns dict with compile_result, bridge_receipt, and lowering_result.
    Does NOT execute unless approve=True.
    """
    from poetica import compile_poem
    from poetica.lower import lower_source

    # Compile
    try:
        code = compile_poem(source, target=target, level=level)
    except Exception as e:
        return {"error": f"Compile failed: {e}", "stage": "compile"}

    # Lower (for the operation token audit trail)
    lowering = lower_source(source, level=level, domain_pack=domain_pack)

    # Write to temp file
    ext = _TARGET_TO_EXT.get(target, ".txt")
    program_name = lowering.program
    tmp_path = f"/tmp/poetica_{program_name}{ext}"

    runner_token = _TARGET_TO_RUNNER.get(target)
    if runner_token is None:
        return {
            "compiled_code": code,
            "lowering": lowering.to_dict(),
            "note": f"No runner for target '{target}' — compile-only",
        }

    # Write the compiled code
    with open(tmp_path, "w") as f:
        f.write(code)

    # Resolve + gate-check + optionally execute
    receipt = execute(runner_token, {"file": tmp_path},
                      level=level, approve=approve)

    return {
        "compiled_code": code,
        "compiled_file": tmp_path,
        "lowering": lowering.to_dict(),
        "bridge_receipt": receipt.to_dict(),
    }
