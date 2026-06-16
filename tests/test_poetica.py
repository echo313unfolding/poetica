"""Tests for the poetica standalone package."""

import json
import os
import subprocess
import sys
import textwrap
import pytest
from poetica import compile_poem, __version__
from poetica.parser import PoeticaParser, Element
from poetica.compiler import PoeticaCompiler
from poetica.gate import Gate, GateError, GateLevel
from poetica.receipt import Receipt
from poetica.emitters import get_emitter, list_targets
from poetica.intent import Intent, IntentError, parse_intent
from poetica.cmd import CmdReceipt, run_cmd
from poetica.canvas import (
    visualize_poem, visualize_command, to_mermaid, to_json_graph, to_ascii,
    VisualNode,
)
from poetica.visual import (
    RobotGridWorld, GardenWorld, FilesystemWorld,
    get_world, list_worlds, Frame,
)
from poetica.playground import play_poem, render_playback
from poetica.alignment import (
    align_poem, to_table, to_annotated, to_lesson, to_json as align_to_json,
    AlignmentSpan,
)
from poetica.domain import (
    DomainPack, load_domain, find_domain, list_domains,
)
from poetica.curriculum import (
    CurriculumPack, Unit, Lesson, CurriculumConcept, StandardLink, EvidenceItem,
    load_curriculum, find_curriculum, list_curricula,
    inspect_curriculum, map_curriculum, generate_lesson, generate_evidence_json,
    KNOWN_OPS,
)
from poetica.syllabus import (
    extract_syllabus, inspect_syllabus, draft_curriculum_yaml,
    match_concepts, suggest_domain, suggest_visual_worlds, ExtractedUnit,
)


# --- Parser ---

class TestParser:
    def setup_method(self):
        self.parser = PoeticaParser()

    def test_seed(self):
        elements = self.parser.parse("seed x with 42")
        assert len(elements) == 1
        assert elements[0].kind == "seed"
        assert elements[0].label == "x"
        assert elements[0].target == "42"

    def test_seed_expression(self):
        elements = self.parser.parse("seed total with total + x")
        assert elements[0].target == "total + x"

    def test_seed_list(self):
        elements = self.parser.parse("seed items with [1, 2, 3]")
        assert elements[0].target == "[1, 2, 3]"

    def test_seed_call(self):
        elements = self.parser.parse("seed nums with range(1, 16)")
        assert elements[0].target == "range(1, 16)"

    def test_grow(self):
        elements = self.parser.parse("grow plants with \"tomato\"")
        assert elements[0].kind == "grow"
        assert elements[0].label == "plants"
        assert elements[0].target == '"tomato"'

    def test_emit(self):
        elements = self.parser.parse("emit hello")
        assert elements[0].kind == "emit"
        assert elements[0].target == "hello"

    def test_emit_labeled(self):
        elements = self.parser.parse('emit "status" readings')
        assert elements[0].kind == "emit"
        assert elements[0].label == "status"
        assert elements[0].target == "readings"

    def test_pack(self):
        elements = self.parser.parse("pack data as json")
        assert elements[0].kind == "pack"
        assert elements[0].label == "data"
        assert elements[0].target == "json"

    def test_lift(self):
        elements = self.parser.parse("lift artifact to registry")
        assert elements[0].kind == "lift"

    def test_use_with_params(self):
        elements = self.parser.parse("use healthcheck(url: api, timeout: 30)")
        assert elements[0].kind == "use"
        assert elements[0].label == "healthcheck"
        assert elements[0].params == {"url": "api", "timeout": "30"}

    def test_use_no_params(self):
        elements = self.parser.parse("use cleanup")
        assert elements[0].kind == "use"
        assert elements[0].label == "cleanup"

    def test_when(self):
        elements = self.parser.parse("when ready:")
        assert elements[0].kind == "when"
        assert elements[0].label == "ready"

    def test_when_in(self):
        elements = self.parser.parse("when item in collection:")
        assert elements[0].kind == "when_in"

    def test_if_echoes(self):
        elements = self.parser.parse("if status echoes active")
        assert elements[0].kind == "if"
        assert elements[0].label == "status"
        assert elements[0].target == "active"

    def test_else_when(self):
        elements = self.parser.parse("else when x > 0:")
        assert elements[0].kind == "else_when"
        assert elements[0].label == "x > 0"

    def test_else(self):
        elements = self.parser.parse("else:")
        assert elements[0].kind == "else"

    def test_flow(self):
        elements = self.parser.parse("flow input to output")
        assert elements[0].kind == "flow"

    def test_bloom(self):
        elements = self.parser.parse("bloom result")
        assert elements[0].kind == "bloom"

    def test_remember(self):
        elements = self.parser.parse("remember key: value")
        assert elements[0].kind == "remember"

    def test_learn(self):
        elements = self.parser.parse('learn pattern "anomaly"')
        assert elements[0].kind == "learn"

    def test_for_each(self):
        elements = self.parser.parse("for each item in items:")
        assert elements[0].kind == "for"
        assert elements[0].label == "item"
        assert elements[0].target == "items"

    def test_name(self):
        elements = self.parser.parse("name my_program")
        assert elements[0].kind == "name"

    def test_comments_skipped(self):
        elements = self.parser.parse("# comment\nseed x with 1")
        assert len(elements) == 1

    def test_blank_lines_skipped(self):
        elements = self.parser.parse("\n\nseed x with 1\n\n")
        assert len(elements) == 1

    def test_indent_tracking(self):
        source = "when x > 0:\n    emit x\n    emit y"
        elements = self.parser.parse(source)
        assert elements[0].indent == 0
        assert elements[1].indent == 1
        assert elements[2].indent == 1


# --- Compiler ---

class TestCompiler:
    def setup_method(self):
        self.parser = PoeticaParser()
        self.compiler = PoeticaCompiler()

    def test_basic_ir(self):
        elements = self.parser.parse("name test\nseed x with 42\nemit x")
        ir = self.compiler.compile(elements, "name test\nseed x with 42\nemit x")
        assert ir["version"] == "poetica-ir-v1"
        assert ir["name"] == "test"
        assert len(ir["ops"]) == 2

    def test_else_when_in_ir(self):
        source = "when x > 0:\n    emit x\nelse when x < 0:\n    emit y\nelse:\n    emit z"
        elements = self.parser.parse(source)
        ir = self.compiler.compile(elements, source)
        ops = [op["op"] for op in ir["ops"]]
        assert ops == ["when", "emit", "else_when", "emit", "else", "emit"]


# --- Gate ---

class TestGate:
    def test_l1_allows_pure(self):
        gate = Gate(level=1)
        ir = {"ops": [
            {"op": "seed", "name": "x", "value": "1"},
            {"op": "emit", "value": "x"},
            {"op": "bloom", "value": "done"},
        ]}
        decisions = gate.check(ir)
        assert all(d.verdict == "ALLOW" for d in decisions)

    def test_l1_rejects_logic(self):
        gate = Gate(level=1)
        ir = {"ops": [{"op": "when", "condition": "ready"}]}
        with pytest.raises(GateError) as exc_info:
            gate.check(ir)
        assert exc_info.value.decision.reason == "LEVEL-EXCEEDED"

    def test_l2_allows_logic(self):
        gate = Gate(level=2)
        ir = {"ops": [
            {"op": "when", "condition": "ready"},
            {"op": "if", "left": "a", "right": "b"},
            {"op": "for", "var": "i", "collection": "items"},
            {"op": "else_when", "condition": "x > 0"},
            {"op": "else"},
        ]}
        decisions = gate.check(ir)
        assert all(d.verdict == "ALLOW" for d in decisions)

    def test_l2_rejects_transform(self):
        gate = Gate(level=2)
        ir = {"ops": [{"op": "grow", "name": "y", "source": "x"}]}
        with pytest.raises(GateError):
            gate.check(ir)

    def test_l3_allows_transform(self):
        gate = Gate(level=3)
        ir = {"ops": [
            {"op": "grow", "name": "y", "source": "x"},
            {"op": "pack", "data": "y", "format": "json"},
        ]}
        decisions = gate.check(ir)
        assert all(d.verdict == "ALLOW" for d in decisions)

    def test_l3_rejects_external(self):
        gate = Gate(level=3)
        ir = {"ops": [{"op": "lift", "name": "x", "dest": "remote"}]}
        with pytest.raises(GateError) as exc_info:
            gate.check(ir)
        assert exc_info.value.decision.reason == "EXTERNAL-DENIED"

    def test_l4_requires_allow_external(self):
        gate = Gate(level=4, allow_external=False)
        ir = {"ops": [{"op": "use", "tool": "curl", "params": {}}]}
        with pytest.raises(GateError) as exc_info:
            gate.check(ir)
        assert exc_info.value.decision.reason == "EXTERNAL-DENIED"

    def test_l4_with_external(self):
        gate = Gate(level=4, allow_external=True)
        ir = {"ops": [
            {"op": "lift", "name": "x", "dest": "remote"},
            {"op": "use", "tool": "curl", "params": {}},
        ]}
        decisions = gate.check(ir)
        assert all(d.verdict == "ALLOW" for d in decisions)

    def test_unknown_op_rejected(self):
        gate = Gate(level=3)
        ir = {"ops": [{"op": "explode"}]}
        with pytest.raises(GateError) as exc_info:
            gate.check(ir)
        assert exc_info.value.decision.reason == "UNKNOWN-OP"

    def test_check_all_no_raise(self):
        gate = Gate(level=1)
        ir = {"ops": [
            {"op": "seed", "name": "x", "value": "1"},
            {"op": "grow", "name": "y", "source": "x"},
        ]}
        decisions = gate.check_all(ir)
        assert decisions[0].verdict == "ALLOW"
        assert decisions[1].verdict == "REJECT"

    def test_invalid_level(self):
        with pytest.raises(ValueError):
            Gate(level=0)

    def test_l5_allows_unknown(self):
        gate = Gate(level=5, allow_external=True)
        ir = {"ops": [{"op": "custom_thing"}]}
        decisions = gate.check(ir)
        assert decisions[0].verdict == "ALLOW"


# --- Emitters: block structure ---

class TestBlockStructure:
    """Test that when/if/for blocks open and close properly."""

    def _compile(self, source):
        parser = PoeticaParser()
        compiler = PoeticaCompiler()
        elements = parser.parse(source)
        return compiler.compile(elements, source)

    def test_python_when_block(self):
        source = "name test\nseed x with 5\nwhen x > 3:\n    emit x\nemit \"done\""
        code = compile_poem(source, target="python", level=2)
        assert "if x > 3:" in code
        # body should be more indented than the if
        lines = code.split("\n")
        if_line = next(l for l in lines if "if x > 3" in l)
        emit_line = next(l for l in lines if "print(x)" in l)
        assert len(emit_line) - len(emit_line.lstrip()) > len(if_line) - len(if_line.lstrip())

    def test_js_when_closes(self):
        source = "name test\nseed x with 5\nwhen x > 3:\n    emit x\nemit \"done\""
        code = compile_poem(source, target="javascript", level=2)
        assert "if (x > 3) {" in code
        assert code.count("}") >= 2  # block close + function close

    def test_python_if_elif_else(self):
        source = textwrap.dedent("""\
            name test
            seed x with 1
            if x echoes 1
                emit "one"
            else when x == 2:
                emit "two"
            else:
                emit "other"
        """)
        code = compile_poem(source, target="python", level=2)
        assert "if x == 1:" in code
        assert "elif x == 2:" in code
        assert "else:" in code

    def test_js_if_elif_else(self):
        source = textwrap.dedent("""\
            name test
            seed x with 1
            if x echoes 1
                emit "one"
            else when x == 2:
                emit "two"
            else:
                emit "other"
        """)
        code = compile_poem(source, target="javascript", level=2)
        assert "} else if" in code
        assert "} else {" in code

    def test_bash_when_fi(self):
        source = "name test\nseed x with 5\nwhen x > 3:\n    emit x"
        code = compile_poem(source, target="bash", level=2)
        assert "if [[" in code
        assert "fi" in code

    def test_bash_for_done(self):
        source = "name test\nseed items with a b c\nfor each x in items:\n    emit x"
        code = compile_poem(source, target="bash", level=2)
        assert "for x in" in code
        assert "done" in code

    def test_python_for_block(self):
        source = "name test\nseed items with [1, 2]\nfor each x in items:\n    emit x\nemit \"done\""
        code = compile_poem(source, target="python", level=2)
        assert "for x in items:" in code
        # "done" print should be at function-body indent, not loop indent
        lines = code.split("\n")
        for_line = next(l for l in lines if "for x in" in l)
        done_line = next(l for l in lines if 'print("done")' in l)
        assert len(done_line) - len(done_line.lstrip()) == len(for_line) - len(for_line.lstrip())

    def test_nested_blocks_rust(self):
        source = textwrap.dedent("""\
            name test
            seed x with 5
            when x > 0:
                when x > 3:
                    emit "big"
                emit "positive"
        """)
        code = compile_poem(source, target="rust", level=2)
        # Should have two closing braces for the two ifs, plus function + main
        assert code.count("}") >= 4


# --- Emitters: real operations ---

class TestRealOperations:
    def test_python_grow_appends(self):
        code = compile_poem('name t\nseed items with []\ngrow items with "x"', target="python", level=3)
        assert "items.append(" in code

    def test_python_pack_json(self):
        code = compile_poem("name t\nseed data with [1]\npack data as json", target="python", level=3)
        assert "import json" in code
        assert "json.dumps(data)" in code

    def test_python_lift_writes_file(self):
        code = compile_poem('name t\nseed x with "hi"\nlift x to "out.txt"', target="python", level=4)
        assert "import pathlib" in code
        assert "pathlib.Path" in code
        assert "write_text" in code

    def test_python_remember_state(self):
        code = compile_poem('name t\nremember key: "val"', target="python")
        assert '_state = {}' in code
        assert '_state["key"]' in code

    def test_python_use_with_import(self):
        code = compile_poem('name t\nuse os.makedirs(path: "build")', target="python", level=4)
        assert "import os" in code
        assert "os.makedirs(" in code

    def test_js_grow_pushes(self):
        code = compile_poem('name t\nseed a with []\ngrow a with "x"', target="javascript", level=3)
        assert ".push(" in code

    def test_js_pack_json(self):
        code = compile_poem("name t\nseed d with []\npack d as json", target="javascript", level=3)
        assert "JSON.stringify" in code

    def test_go_grow_appends(self):
        code = compile_poem('name t\nseed a with []\ngrow a with "x"', target="go", level=3)
        assert "append(" in code

    def test_rust_grow_pushes(self):
        code = compile_poem('name t\nseed a with []\ngrow a with "x"', target="rust", level=3)
        assert ".push(" in code

    def test_bash_grow_array(self):
        code = compile_poem('name t\nseed a with ()\ngrow a with "x"', target="bash", level=3)
        assert "+=(" in code


# --- Emitter aliases ---

class TestEmitterAliases:
    def test_sonnet_is_python(self):
        ir = {"name": "t", "ops": [{"op": "seed", "name": "x", "value": "1", "indent": 0}]}
        assert get_emitter("sonnet").emit(ir) == get_emitter("python").emit(ir)

    def test_haiku_is_rust(self):
        ir = {"name": "t", "ops": [{"op": "seed", "name": "x", "value": "1", "indent": 0}]}
        assert get_emitter("haiku").emit(ir) == get_emitter("rust").emit(ir)

    def test_ballad_is_javascript(self):
        ir = {"name": "t", "ops": [{"op": "seed", "name": "x", "value": "1", "indent": 0}]}
        assert get_emitter("ballad").emit(ir) == get_emitter("javascript").emit(ir)

    def test_ode_is_go(self):
        ir = {"name": "t", "ops": [{"op": "seed", "name": "x", "value": "1", "indent": 0}]}
        assert get_emitter("ode").emit(ir) == get_emitter("go").emit(ir)

    def test_prose_is_bash(self):
        ir = {"name": "t", "ops": [{"op": "seed", "name": "x", "value": "1", "indent": 0}]}
        assert get_emitter("prose").emit(ir) == get_emitter("bash").emit(ir)

    def test_verse_is_sql(self):
        ir = {"name": "t", "ops": [{"op": "seed", "name": "x", "value": "1", "indent": 0}]}
        assert get_emitter("verse").emit(ir) == get_emitter("sql").emit(ir)

    def test_unknown_target_raises(self):
        with pytest.raises(ValueError):
            get_emitter("cobol")

    def test_list_targets(self):
        targets = list_targets()
        assert len(targets) == 6


# --- compile_poem top-level ---

class TestCompilePoem:
    def test_basic(self):
        code = compile_poem("name test\nseed x with 42\nemit x")
        assert "x = 42" in code
        assert "print" in code

    def test_all_targets(self):
        source = "name test\nseed x with 42\nemit x"
        for target in ["python", "javascript", "rust", "go", "bash", "sql"]:
            code = compile_poem(source, target=target)
            assert len(code) > 0

    def test_gate_blocks(self):
        with pytest.raises(GateError):
            compile_poem("lift data to remote", level=1)

    def test_version(self):
        assert __version__ == "0.1.0"

    def test_expressions_pass_through(self):
        code = compile_poem("name t\nseed x with 5 + 3", target="python")
        assert "x = 5 + 3" in code

    def test_list_literal_pass_through(self):
        code = compile_poem("name t\nseed x with [1, 2, 3]", target="python")
        assert "x = [1, 2, 3]" in code

    def test_function_call_pass_through(self):
        code = compile_poem("name t\nseed x with range(10)", target="python")
        assert "x = range(10)" in code


# --- Receipt ---

class TestReceipt:
    def test_receipt_creation(self):
        r = Receipt(
            source_hash="abc123", target="python", gate_level=1, gate_policy="pol",
            decisions=[{"op": "seed", "verdict": "ALLOW", "reason": "OK", "level": 1}],
            output_hash="def456",
        )
        d = r.to_dict()
        assert d["schema"] == "poetica.receipt.v1"
        assert d["all_allowed"] is True

    def test_hash_output(self):
        h = Receipt.hash_output("hello")
        assert len(h) == 64


# --- End-to-end execution ---

class TestExecution:
    """Test that generated Python actually runs."""

    def _read_example(self, name):
        import pathlib
        path = pathlib.Path(__file__).parent.parent / "examples" / name
        return path.read_text()

    def _run_python(self, code):
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=5,
        )
        return result

    def test_hello_runs(self):
        source = self._read_example("hello.poem")
        code = compile_poem(source, target="python", level=1)
        result = self._run_python(code)
        assert result.returncode == 0
        assert "hello world" in result.stdout
        assert "[count] 3" in result.stdout

    def test_counter_runs(self):
        source = self._read_example("counter.poem")
        code = compile_poem(source, target="python", level=2)
        result = self._run_python(code)
        assert result.returncode == 0
        assert "[total] 15" in result.stdout

    def test_fizzbuzz_runs(self):
        source = self._read_example("fizzbuzz.poem")
        code = compile_poem(source, target="python", level=2)
        result = self._run_python(code)
        assert result.returncode == 0
        assert "FizzBuzz" in result.stdout
        assert "Fizz" in result.stdout
        assert "Buzz" in result.stdout

    def test_garden_runs(self):
        source = self._read_example("garden.poem")
        code = compile_poem(source, target="python", level=3)
        result = self._run_python(code)
        assert result.returncode == 0
        assert "tomato" in result.stdout
        assert "[" in result.stdout  # json output

    def test_hello_all_targets_compile(self):
        source = self._read_example("hello.poem")
        for target in ["sonnet", "haiku", "ballad", "ode", "prose", "verse"]:
            code = compile_poem(source, target=target, level=1)
            assert len(code) > 10

    def test_garden_blocked_at_l1(self):
        source = self._read_example("garden.poem")
        with pytest.raises(GateError):
            compile_poem(source, target="python", level=1)

    def test_pipeline_blocked_at_l3(self):
        source = self._read_example("pipeline.poem")
        with pytest.raises(GateError):
            compile_poem(source, target="python", level=3)

    def test_deploy_all_targets(self):
        source = self._read_example("deploy.poem")
        for target in ["sonnet", "haiku", "ballad", "ode", "prose", "verse"]:
            code = compile_poem(source, target=target, level=4)
            assert len(code) > 10


# --- Intent parser ---

class TestIntent:
    def test_apt_update(self):
        intent = parse_intent("apt update")
        assert intent.op == "package.update_index"
        assert intent.argv == ["sudo", "apt", "update"]
        assert intent.level == 4

    def test_update_package_index(self):
        intent = parse_intent("update package index")
        assert intent.op == "package.update_index"

    def test_refresh_packages(self):
        intent = parse_intent("refresh packages")
        assert intent.op == "package.update_index"

    def test_apt_upgrade(self):
        intent = parse_intent("apt upgrade")
        assert intent.op == "package.upgrade"
        assert "-y" not in intent.argv

    def test_apt_upgrade_yes(self):
        intent = parse_intent("apt upgrade", yes=True)
        assert intent.op == "package.upgrade"
        assert "-y" in intent.argv

    def test_install_package(self):
        intent = parse_intent("install curl")
        assert intent.op == "package.install"
        assert intent.argv == ["sudo", "apt", "install", "curl"]
        assert intent.params["package"] == "curl"

    def test_install_with_yes(self):
        intent = parse_intent("install curl", yes=True)
        assert intent.argv == ["sudo", "apt", "install", "-y", "curl"]

    def test_install_invalid_package(self):
        with pytest.raises(IntentError):
            parse_intent("install ; rm -rf /")

    def test_install_empty_package(self):
        with pytest.raises(IntentError):
            parse_intent("install ")

    def test_ls(self):
        intent = parse_intent("ls")
        assert intent.op == "fs.list"
        assert intent.argv == ["ls", "-la"]
        assert intent.level == 1

    def test_list_files(self):
        intent = parse_intent("list files")
        assert intent.op == "fs.list"

    def test_pwd(self):
        intent = parse_intent("pwd")
        assert intent.op == "fs.pwd"
        assert intent.argv == ["pwd"]
        assert intent.level == 1

    def test_where_am_i(self):
        intent = parse_intent("where am i")
        assert intent.op == "fs.pwd"

    def test_unknown_intent(self):
        with pytest.raises(IntentError):
            parse_intent("hack the planet")

    def test_empty_input(self):
        with pytest.raises(IntentError):
            parse_intent("")

    def test_case_insensitive(self):
        intent = parse_intent("APT UPDATE")
        assert intent.op == "package.update_index"


# --- Cmd pipeline ---

class TestCmd:
    def test_dry_run_does_not_execute(self):
        receipt = run_cmd("ls", level=1, approve=False)
        assert receipt.executed is False
        assert receipt.approved is False
        assert receipt.gate_decision == "ALLOW"
        assert receipt.emitted_command == ["ls", "-la"]

    def test_apt_update_requires_l4(self):
        receipt = run_cmd("apt update", level=1)
        assert receipt.gate_decision == "REJECT"
        assert receipt.approved is False
        assert receipt.executed is False

    def test_apt_update_allowed_at_l4(self):
        receipt = run_cmd("apt update", level=4)
        assert receipt.gate_decision == "ALLOW"
        assert receipt.approved is False  # dry-run default

    def test_ls_allowed_at_l1(self):
        receipt = run_cmd("ls", level=1)
        assert receipt.gate_decision == "ALLOW"
        assert receipt.parsed_intent == "fs.list"

    def test_pwd_allowed_at_l1(self):
        receipt = run_cmd("pwd", level=1)
        assert receipt.gate_decision == "ALLOW"
        assert receipt.emitted_command == ["pwd"]

    def test_approve_executes_safe_command(self):
        receipt = run_cmd("pwd", level=1, approve=True)
        assert receipt.executed is True
        assert receipt.approved is True
        assert receipt.exit_code == 0
        assert len(receipt.stdout_hash) == 64
        assert len(receipt.stderr_hash) == 64

    def test_approve_ls_executes(self):
        receipt = run_cmd("ls", level=1, approve=True)
        assert receipt.executed is True
        assert receipt.exit_code == 0

    def test_receipt_to_json(self):
        receipt = run_cmd("pwd", level=1)
        j = json.loads(receipt.to_json())
        assert j["schema"] == "poetica.cmd.receipt.v1"
        assert j["original_text"] == "pwd"
        assert j["parsed_intent"] == "fs.pwd"
        assert j["emitted_command"] == ["pwd"]
        assert j["gate_decision"] == "ALLOW"
        assert j["approved"] is False
        assert j["executed"] is False
        assert "timestamp" in j

    def test_receipt_executed_has_hashes(self):
        receipt = run_cmd("pwd", level=1, approve=True)
        j = json.loads(receipt.to_json())
        assert "exit_code" in j
        assert "stdout_hash" in j
        assert "stderr_hash" in j

    def test_receipt_dry_run_no_hashes(self):
        receipt = run_cmd("pwd", level=1, approve=False)
        j = json.loads(receipt.to_json())
        assert "exit_code" not in j
        assert "stdout_hash" not in j

    def test_upgrade_yes_flag(self):
        receipt = run_cmd("apt upgrade", level=4, yes=True)
        assert "-y" in receipt.emitted_command

    def test_upgrade_no_yes_flag(self):
        receipt = run_cmd("apt upgrade", level=4, yes=False)
        assert "-y" not in receipt.emitted_command

    def test_install_no_package_rejects(self):
        with pytest.raises(IntentError):
            run_cmd("install ", level=4)

    def test_unknown_intent_raises(self):
        with pytest.raises(IntentError):
            run_cmd("do something weird", level=1)


# --- Echo Canvas ---

class TestCanvas:
    def _read_example(self, name):
        import pathlib
        path = pathlib.Path(__file__).parent.parent / "examples" / name
        return path.read_text()

    def test_fizzbuzz_has_loop_and_decisions(self):
        source = self._read_example("fizzbuzz.poem")
        nodes = visualize_poem(source)
        ops = [n.ir_op for n in nodes]
        assert "for" in ops
        assert "if" in ops or "else_when" in ops
        assert "emit" in ops
        concepts = [n.concept for n in nodes]
        assert "loop" in concepts
        assert "decision" in concepts
        assert "output" in concepts

    def test_hello_has_seed_and_emit(self):
        source = self._read_example("hello.poem")
        nodes = visualize_poem(source)
        ops = [n.ir_op for n in nodes]
        assert "seed" in ops
        assert "emit" in ops
        concepts = [n.concept for n in nodes]
        assert "variable" in concepts
        assert "output" in concepts

    def test_garden_has_grow_and_pack(self):
        source = self._read_example("garden.poem")
        nodes = visualize_poem(source)
        ops = [n.ir_op for n in nodes]
        assert "grow" in ops
        assert "pack" in ops

    def test_pipeline_has_lift(self):
        source = self._read_example("pipeline.poem")
        nodes = visualize_poem(source)
        ops = [n.ir_op for n in nodes]
        assert "lift" in ops
        # lift requires L4
        lift_nodes = [n for n in nodes if n.ir_op == "lift"]
        assert lift_nodes[0].gate_level == 4

    def test_command_ls_visual(self):
        nodes = visualize_command("ls -la")
        assert len(nodes) == 1
        assert nodes[0].concept == "folder_list"
        assert nodes[0].explanation == "List files in a directory"

    def test_command_pwd_visual(self):
        nodes = visualize_command("pwd")
        assert len(nodes) == 1
        assert nodes[0].concept == "location"

    def test_command_apt_update_visual(self):
        nodes = visualize_command("apt update")
        assert len(nodes) == 1
        assert nodes[0].concept == "package_refresh"
        assert nodes[0].gate_level == 4

    def test_command_unknown_fallback(self):
        nodes = visualize_command("docker ps")
        assert len(nodes) == 1
        assert nodes[0].concept == "command"

    def test_json_graph_validates(self):
        source = self._read_example("hello.poem")
        nodes = visualize_poem(source)
        output = to_json_graph(nodes, "greeter")
        graph = json.loads(output)
        assert graph["name"] == "greeter"
        assert len(graph["nodes"]) > 0
        assert len(graph["edges"]) > 0
        # Each node has required fields
        for node in graph["nodes"]:
            assert "id" in node
            assert "source_line" in node
            assert "source_text" in node
            assert "ir_op" in node
            assert "concept" in node
            assert "explanation" in node
            assert "gate_level" in node

    def test_mermaid_contains_flowchart(self):
        source = self._read_example("hello.poem")
        nodes = visualize_poem(source)
        output = to_mermaid(nodes, "greeter")
        assert "flowchart TD" in output
        assert "start" in output
        assert "finish" in output

    def test_mermaid_fizzbuzz_has_decision(self):
        source = self._read_example("fizzbuzz.poem")
        nodes = visualize_poem(source)
        output = to_mermaid(nodes, "fizzbuzz")
        assert "flowchart TD" in output
        # Decisions use {curly brace} syntax in mermaid
        assert "{" in output

    def test_ascii_output_readable(self):
        source = self._read_example("hello.poem")
        nodes = visualize_poem(source)
        output = to_ascii(nodes, "greeter")
        assert "START: greeter" in output
        assert "END" in output
        assert "[=]" in output  # seed icon

    def test_node_has_source_line(self):
        source = self._read_example("hello.poem")
        nodes = visualize_poem(source)
        for node in nodes:
            assert node.source_line > 0

    def test_node_to_dict(self):
        node = VisualNode(
            id="n0", source_line=1, source_text="seed x with 42",
            ir_op="seed", concept="variable", explanation="Create a named value",
            shape="box", icon="[=]", gate_level=1, details={"name": "x"},
        )
        d = node.to_dict()
        assert d["id"] == "n0"
        assert d["ir_op"] == "seed"
        assert d["gate_level"] == 1

    def test_empty_poem(self):
        nodes = visualize_poem("# just a comment\n")
        assert nodes == []

    def test_empty_command(self):
        nodes = visualize_command("")
        assert nodes == []


# --- Visual Worlds ---

class TestVisualWorlds:
    def test_list_worlds(self):
        worlds = list_worlds()
        assert "robot_grid" in worlds
        assert "garden" in worlds
        assert "filesystem" in worlds

    def test_get_world(self):
        w = get_world("robot_grid")
        assert isinstance(w, RobotGridWorld)

    def test_get_world_unknown_raises(self):
        with pytest.raises(ValueError):
            get_world("moon_base")

    def test_robot_seed_sets_position(self):
        w = RobotGridWorld()
        frame = w.step({"op": "seed", "name": "x", "value": "2"})
        assert w.x == 2
        assert frame.op == "seed"
        assert "x" in frame.description

    def test_robot_flow_moves(self):
        w = RobotGridWorld()
        w.step({"op": "seed", "name": "x", "value": "0"})
        frame = w.step({"op": "flow", "source": "x + 1", "dest": "x"})
        assert w.x == 1
        assert frame.op == "flow"

    def test_robot_flow_clamps(self):
        w = RobotGridWorld(width=3, height=3)
        w.x = 2
        w.step({"op": "flow", "source": "x + 1", "dest": "x"})
        assert w.x == 2  # clamped at width-1

    def test_robot_render_has_arrow(self):
        w = RobotGridWorld(width=3, height=3)
        output = w.render()
        assert "^" in output  # default direction is north

    def test_robot_direction(self):
        w = RobotGridWorld()
        w.step({"op": "seed", "name": "direction", "value": '"east"'})
        assert w.direction == "east"
        output = w.render()
        assert ">" in output

    def test_robot_trail(self):
        w = RobotGridWorld()
        w.step({"op": "flow", "source": "x + 1", "dest": "x"})
        assert (0, 0) in w.trail
        assert (1, 0) in w.trail

    def test_garden_grow_adds_plant(self):
        w = GardenWorld()
        w.step({"op": "grow", "name": "garden", "source": '"tomato"'})
        assert len(w.plants) == 1
        assert w.plants[0]["name"] == "tomato"

    def test_garden_emit_waters(self):
        w = GardenWorld()
        w.step({"op": "grow", "name": "garden", "source": '"rose"'})
        assert w.plants[0]["stage"] == 1
        w.step({"op": "emit", "value": "rose"})
        assert w.plants[0]["stage"] == 2

    def test_garden_bloom_maxes(self):
        w = GardenWorld()
        w.step({"op": "grow", "name": "garden", "source": '"lily"'})
        w.step({"op": "bloom", "value": "done"})
        assert w.plants[0]["stage"] == 3

    def test_garden_render_shows_plants(self):
        w = GardenWorld()
        w.step({"op": "grow", "name": "garden", "source": '"basil"'})
        output = w.render()
        assert "basi" in output  # truncated to 4 chars
        assert "o" in output  # stage 1 icon

    def test_garden_empty_render(self):
        w = GardenWorld()
        output = w.render()
        assert "empty" in output

    def test_filesystem_seed_path(self):
        w = FilesystemWorld()
        w.step({"op": "seed", "name": "path", "value": '"/tmp"'})
        assert w.cwd == "/tmp"

    def test_filesystem_seed_files(self):
        w = FilesystemWorld()
        w.step({"op": "seed", "name": "files", "value": '["a.txt", "b.md"]'})
        assert len(w.files) == 2
        assert "a.txt" in w.files

    def test_filesystem_grow_adds_file(self):
        w = FilesystemWorld()
        w.step({"op": "grow", "name": "files", "source": '"new.py"'})
        assert "new.py" in w.files

    def test_filesystem_render_tree(self):
        w = FilesystemWorld()
        w.step({"op": "seed", "name": "files", "value": '["x.py", "y.rs"]'})
        output = w.render()
        assert "x.py" in output
        assert "y.rs" in output
        assert "/home/" in output

    def test_filesystem_empty_render(self):
        w = FilesystemWorld()
        output = w.render()
        assert "empty" in output


# --- Playground ---

class TestPlayground:
    def _read_example(self, name):
        import pathlib
        path = pathlib.Path(__file__).parent.parent / "examples" / name
        return path.read_text()

    def test_play_robot_produces_frames(self):
        source = self._read_example("robot.poem")
        frames = play_poem(source, "robot_grid")
        assert len(frames) > 0
        assert all(isinstance(f, Frame) for f in frames)

    def test_play_garden_produces_frames(self):
        source = self._read_example("garden_visual.poem")
        frames = play_poem(source, "garden")
        assert len(frames) > 0
        # Should have grow frames
        grow_frames = [f for f in frames if f.op == "grow"]
        assert len(grow_frames) == 3  # sunflower, tomato, basil

    def test_play_filesystem_produces_frames(self):
        source = self._read_example("filesystem_visual.poem")
        frames = play_poem(source, "filesystem")
        assert len(frames) > 0

    def test_render_playback_has_structure(self):
        source = self._read_example("hello.poem")
        frames = play_poem(source, "robot_grid")
        output = render_playback(frames, "hello")
        assert "PLAY: hello" in output
        assert "END" in output
        assert "Step 1" in output

    def test_play_hello_in_all_worlds(self):
        source = self._read_example("hello.poem")
        for world in list_worlds():
            frames = play_poem(source, world)
            assert len(frames) > 0

    def test_play_unknown_world_raises(self):
        with pytest.raises(ValueError):
            play_poem("seed x with 1", "atlantis")

    def test_each_frame_has_state(self):
        source = self._read_example("robot.poem")
        frames = play_poem(source, "robot_grid")
        for frame in frames:
            assert frame.state_ascii  # non-empty
            assert frame.description  # non-empty
            assert frame.step > 0


# --- Alignment Map ---

class TestAlignment:
    def _read_example(self, name):
        import pathlib
        path = pathlib.Path(__file__).parent.parent / "examples" / name
        return path.read_text()

    def test_hello_alignment_python(self):
        source = self._read_example("hello.poem")
        spans = align_poem(source, target="python")
        assert len(spans) > 0
        # First span should be seed
        assert spans[0].ir_op == "seed"
        assert spans[0].concept == "variable"
        assert "=" in spans[0].target_text
        assert spans[0].visual_role == "declare"

    def test_alignment_has_all_fields(self):
        source = "name test\nseed x with 42\nemit x"
        spans = align_poem(source, target="python")
        for span in spans:
            assert span.source_line > 0
            assert span.source_text
            assert span.ir_op
            assert span.concept
            assert span.target == "python"
            assert span.target_text
            assert span.visual_role
            assert span.explanation
            assert span.gate_level >= 0

    def test_alignment_target_matches_emitter(self):
        source = "name test\nseed x with 42\nemit x"
        spans = align_poem(source, target="python")
        seed_span = spans[0]
        assert seed_span.target_text == 'x = 42'
        emit_span = spans[1]
        assert "print" in emit_span.target_text

    def test_alignment_javascript_target(self):
        source = "name test\nseed x with 42\nemit x"
        spans = align_poem(source, target="javascript")
        assert spans[0].target == "javascript"
        assert "let" in spans[0].target_text or "const" in spans[0].target_text or "var" in spans[0].target_text

    def test_alignment_roles(self):
        source = self._read_example("fizzbuzz.poem")
        spans = align_poem(source, target="python")
        roles = {s.visual_role for s in spans}
        assert "declare" in roles
        assert "control" in roles
        assert "output" in roles

    def test_alignment_gate_levels(self):
        source = self._read_example("garden.poem")
        spans = align_poem(source, target="python")
        # grow and pack are L3
        grow_spans = [s for s in spans if s.ir_op == "grow"]
        assert grow_spans[0].gate_level == 3
        pack_spans = [s for s in spans if s.ir_op == "pack"]
        assert pack_spans[0].gate_level == 3

    def test_table_output(self):
        source = "name test\nseed x with 42\nemit x"
        spans = align_poem(source, target="python")
        output = to_table(spans)
        assert "Line" in output
        assert "Source" in output
        assert "Concept" in output
        assert "Target" in output
        assert "Role" in output
        assert "seed x with 42" in output

    def test_annotated_output(self):
        source = "name test\nseed x with 42\nemit x"
        spans = align_poem(source, target="python")
        output = to_annotated(spans)
        assert "seed x with 42" in output
        assert "[variable]" in output
        assert "x = 42" in output

    def test_json_output(self):
        source = "name test\nseed x with 42\nemit x"
        spans = align_poem(source, target="python")
        output = align_to_json(spans)
        data = json.loads(output)
        assert len(data) == 2
        assert data[0]["ir_op"] == "seed"
        assert data[0]["source_text"] == "seed x with 42"
        assert data[0]["target_text"] == "x = 42"

    def test_empty_source(self):
        spans = align_poem("# comment only")
        assert spans == []

    def test_table_empty(self):
        output = to_table([])
        assert "no operations" in output

    def test_all_targets(self):
        source = "name test\nseed x with 42\nemit x"
        for target in ["python", "javascript", "rust", "go", "bash", "sql"]:
            spans = align_poem(source, target=target)
            assert len(spans) == 2
            assert spans[0].target == target

    def test_visual_layer_seed(self):
        source = "name test\nseed x with 42"
        spans = align_poem(source, target="python")
        assert spans[0].visual
        assert "x" in spans[0].visual
        assert "42" in spans[0].visual
        assert "box" in spans[0].visual.lower()

    def test_visual_layer_emit(self):
        source = "name test\nemit hello"
        spans = align_poem(source, target="python")
        assert "screen" in spans[0].visual.lower()

    def test_visual_layer_when(self):
        source = "name test\nwhen ready:"
        spans = align_poem(source, target="python")
        assert "fork" in spans[0].visual.lower()

    def test_visual_layer_for(self):
        source = "name test\nfor each item in items:"
        spans = align_poem(source, target="python")
        assert "loop" in spans[0].visual.lower()
        assert "item" in spans[0].visual

    def test_visual_layer_flow(self):
        source = "name test\nflow input to output"
        spans = align_poem(source, target="python")
        assert "moves" in spans[0].visual.lower() or "flow" in spans[0].visual.lower()

    def test_visual_layer_grow(self):
        source = "name test\ngrow items with \"x\""
        spans = align_poem(source, target="python")
        assert "collection" in spans[0].visual.lower()

    def test_lesson_output(self):
        source = "name test\nseed x with 42\nemit x"
        spans = align_poem(source, target="python")
        output = to_lesson(spans)
        assert "Visual:" in output
        assert "Phrase:" in output
        assert "Concept:" in output
        assert "Code:" in output
        # Visual layer content
        assert "box" in output.lower()
        # Phrase layer
        assert "seed x with 42" in output
        # Concept layer
        assert "variable" in output
        # Code layer
        assert "x = 42" in output

    def test_lesson_empty(self):
        output = to_lesson([])
        assert "no operations" in output

    def test_lesson_four_layers_per_op(self):
        source = "name test\nseed x with 42"
        spans = align_poem(source, target="python")
        output = to_lesson(spans)
        assert output.count("Visual:") == 1
        assert output.count("Phrase:") == 1
        assert output.count("Concept:") == 1
        assert output.count("Code:") == 1

    def test_json_includes_visual(self):
        source = "name test\nseed x with 42"
        spans = align_poem(source, target="python")
        output = align_to_json(spans)
        data = json.loads(output)
        assert "visual" in data[0]
        assert "box" in data[0]["visual"].lower()


# --- Domain Packs ---

class TestDomainPacks:
    def _read_example(self, name):
        import pathlib
        path = pathlib.Path(__file__).parent.parent / "examples" / name
        return path.read_text()

    def test_list_domains(self):
        domains = list_domains()
        assert "microbiology" in domains
        assert "robotics" in domains
        assert "finance" in domains

    def test_find_domain(self):
        path = find_domain("microbiology")
        assert path is not None
        assert path.endswith(".yaml")

    def test_find_domain_missing(self):
        path = find_domain("underwater_basket_weaving")
        assert path is None

    def test_load_microbiology(self):
        path = find_domain("microbiology")
        pack = load_domain(path)
        assert pack.domain == "microbiology"
        assert pack.name == "Microbiology Lab Pack"
        assert "culture.growth" in pack.terms
        assert len(pack.phrases) > 0

    def test_term_substitution(self):
        pack = DomainPack(
            name="test", domain="test",
            terms={
                "culture.growth": {"maps_to": "culture_growth"},
                "control.baseline": {"maps_to": "control_baseline"},
            },
        )
        result = pack.preprocess("seed culture.growth with 0.85")
        assert result == "seed culture_growth with 0.85"

    def test_term_substitution_in_condition(self):
        pack = DomainPack(
            name="test", domain="test",
            terms={
                "culture.growth": {"maps_to": "culture_growth"},
                "control.baseline": {"maps_to": "control_baseline"},
            },
        )
        result = pack.preprocess("when culture.growth > control.baseline:")
        assert result == "when culture_growth > control_baseline:"

    def test_phrase_rewriting(self):
        pack = DomainPack(
            name="test", domain="test",
            phrases={
                "flag {x} as {label}": {
                    "pattern": 'remember {x}: {label}',
                },
            },
        )
        result = pack.preprocess('flag sample as "positive"')
        assert result == 'remember sample: "positive"'

    def test_phrase_export(self):
        pack = DomainPack(
            name="test", domain="test",
            phrases={
                "export {data} as {fmt}": {
                    "pattern": "pack {data} as {fmt}",
                },
            },
        )
        result = pack.preprocess("export results as json")
        assert result == "pack results as json"

    def test_term_and_phrase_combined(self):
        pack = DomainPack(
            name="test", domain="test",
            terms={
                "sample.status": {"maps_to": "sample_status"},
            },
            phrases={
                "mark {x} as {label}": {
                    "pattern": 'remember {x}: {label}',
                },
            },
        )
        result = pack.preprocess('mark sample.status as "positive"')
        assert result == 'remember sample_status: "positive"'

    def test_preserves_comments(self):
        pack = DomainPack(name="test", domain="test",
                          terms={"x.y": {"maps_to": "x_y"}})
        result = pack.preprocess("# this is a comment\nseed x.y with 1")
        assert "# this is a comment" in result

    def test_preserves_indentation(self):
        pack = DomainPack(name="test", domain="test",
                          terms={"x.y": {"maps_to": "x_y"}})
        result = pack.preprocess("when ready:\n    seed x.y with 1")
        lines = result.split("\n")
        assert lines[1] == "    seed x_y with 1"

    def test_preserves_blank_lines(self):
        pack = DomainPack(name="test", domain="test",
                          terms={"x.y": {"maps_to": "x_y"}})
        result = pack.preprocess("seed x.y with 1\n\nemit x_y")
        assert "\n\n" in result

    def test_microbiology_assay_compiles(self):
        """Full pipeline: domain poem → preprocess → compile."""
        path = find_domain("microbiology")
        pack = load_domain(path)
        source = self._read_example("assay.poem")
        canonical = pack.preprocess(source)
        # After preprocessing, domain terms should be underscored
        assert "culture_growth" in canonical
        assert "control_baseline" in canonical
        # Should compile to Python
        code = compile_poem(canonical, target="python", level=4)
        assert "culture_growth" in code
        assert "print" in code

    def test_robotics_sensor_compiles(self):
        path = find_domain("robotics")
        pack = load_domain(path)
        source = self._read_example("sensor.poem")
        canonical = pack.preprocess(source)
        assert "sensor_distance" in canonical
        assert "motor_speed" in canonical
        code = compile_poem(canonical, target="python", level=2)
        assert "sensor_distance" in code

    def test_domain_visual_override(self):
        pack = DomainPack(
            name="test", domain="test",
            visuals={"seed": "A test tube labeled '{name}' is prepared with {value}"},
        )
        visual = pack.get_visual("seed")
        assert visual is not None
        assert "test tube" in visual

    def test_domain_visual_none_for_missing(self):
        pack = DomainPack(name="test", domain="test")
        assert pack.get_visual("seed") is None

    def test_no_domain_passthrough(self):
        """Without a domain pack, source passes through unchanged."""
        source = "seed culture.growth with 0.85"
        parser = PoeticaParser()
        elements = parser.parse(source)
        # Parser sees culture.growth as the label (matches [^\s]+)
        assert elements[0].label == "culture.growth"

    def test_microbiology_alignment_lesson(self):
        path = find_domain("microbiology")
        pack = load_domain(path)
        source = self._read_example("assay.poem")
        canonical = pack.preprocess(source)
        spans = align_poem(canonical, target="python")
        output = to_lesson(spans)
        assert "Visual:" in output
        assert "Phrase:" in output
        assert "Code:" in output

    def test_robotics_stop_motor_phrase(self):
        path = find_domain("robotics")
        pack = load_domain(path)
        result = pack.preprocess("stop motor")
        assert "seed motor_speed with 0" in result

    def test_finance_flag_risk(self):
        path = find_domain("finance")
        pack = load_domain(path)
        result = pack.preprocess("flag project risk")
        assert 'remember project: "at_risk"' in result

    # --- Domain Provenance Tests ---

    def test_preprocess_with_map_returns_rewrites(self):
        pack = DomainPack(
            name="test", domain="test_domain",
            terms={
                "sensor.distance": {
                    "maps_to": "sensor_distance",
                    "concept": "distance sensor reading",
                    "visual": "a distance gauge",
                },
            },
        )
        canonical, rewrites = pack.preprocess_with_map("seed sensor.distance with 25")
        assert canonical == "seed sensor_distance with 25"
        assert len(rewrites) == 1
        rw = rewrites[0]
        assert rw.original_text == "seed sensor.distance with 25"
        assert rw.canonical_text == "seed sensor_distance with 25"
        assert rw.domain == "test_domain"
        assert rw.rewrite_type == "term"
        assert rw.domain_concept == "distance sensor reading"

    def test_preprocess_with_map_phrase_rewrite(self):
        pack = DomainPack(
            name="test", domain="robotics",
            terms={"motor.speed": {"maps_to": "motor_speed"}},
            phrases={
                "stop motor": {
                    "pattern": "seed motor.speed with 0",
                    "concept": "emergency stop",
                    "visual": "the motor halts immediately",
                },
            },
        )
        canonical, rewrites = pack.preprocess_with_map("stop motor")
        assert "motor_speed" in canonical
        assert len(rewrites) == 1
        rw = rewrites[0]
        assert rw.original_text == "stop motor"
        assert rw.rewrite_type == "phrase"
        assert rw.domain_concept == "emergency stop"
        assert rw.domain_visual == "the motor halts immediately"

    def test_preprocess_with_map_no_rewrite(self):
        pack = DomainPack(name="test", domain="test")
        canonical, rewrites = pack.preprocess_with_map("seed x with 1")
        assert canonical == "seed x with 1"
        assert len(rewrites) == 0

    def test_preprocess_with_map_skips_comments(self):
        pack = DomainPack(
            name="test", domain="test",
            terms={"x.y": {"maps_to": "x_y"}},
        )
        canonical, rewrites = pack.preprocess_with_map("# comment\nseed x.y with 1")
        assert "# comment" in canonical
        # Only the seed line generates a rewrite, not the comment
        assert len(rewrites) == 1

    def test_alignment_domain_provenance_fields(self):
        """align_poem with rewrites populates domain fields on AlignmentSpan."""
        pack = DomainPack(
            name="test", domain="robotics",
            terms={
                "sensor.distance": {
                    "maps_to": "sensor_distance",
                    "concept": "distance reading",
                    "visual": "distance gauge reads",
                },
            },
        )
        source = "name test\nseed sensor.distance with 25\nemit sensor.distance"
        canonical, rewrites = pack.preprocess_with_map(source)
        spans = align_poem(canonical, target="python", rewrites=rewrites)
        # Find the seed span
        seed_spans = [s for s in spans if s.ir_op == "seed"]
        assert len(seed_spans) >= 1
        seed = seed_spans[0]
        assert seed.domain_original == "seed sensor.distance with 25"
        assert seed.domain_concept == "distance reading"

    def test_lesson_5_layer_with_domain(self):
        """to_lesson shows 5 layers (Original/Canonical/Concept/Code/Visual) for domain ops."""
        pack = DomainPack(
            name="test", domain="robotics",
            terms={
                "motor.speed": {"maps_to": "motor_speed"},
            },
            phrases={
                "stop motor": {
                    "pattern": "seed motor.speed with 0",
                    "concept": "emergency stop",
                    "visual": "the motor halts immediately",
                },
            },
        )
        source = "name test\nstop motor"
        canonical, rewrites = pack.preprocess_with_map(source)
        spans = align_poem(canonical, target="python", rewrites=rewrites)
        output = to_lesson(spans)
        assert "Original:" in output
        assert "Canonical:" in output
        assert "stop motor" in output
        assert "motor_speed" in output

    def test_lesson_4_layer_without_domain(self):
        """to_lesson shows standard 4 layers for non-domain ops."""
        spans = align_poem("name test\nseed x with 1", target="python")
        output = to_lesson(spans)
        assert "Visual:" in output
        assert "Phrase:" in output
        assert "Concept:" in output
        assert "Code:" in output
        assert "Original:" not in output

    def test_annotated_shows_domain_original(self):
        """to_annotated shows domain original phrase when available."""
        pack = DomainPack(
            name="test", domain="robotics",
            terms={
                "motor.speed": {"maps_to": "motor_speed"},
            },
            phrases={
                "stop motor": {
                    "pattern": "seed motor.speed with 0",
                    "concept": "emergency stop",
                    "visual": "motor halts",
                },
            },
        )
        source = "name test\nstop motor"
        canonical, rewrites = pack.preprocess_with_map(source)
        spans = align_poem(canonical, target="python", rewrites=rewrites)
        output = to_annotated(spans)
        assert "stop motor" in output
        assert "[domain: emergency stop]" in output

    def test_json_includes_domain_provenance(self):
        """to_json includes domain fields when present."""
        import json as _json
        pack = DomainPack(
            name="test", domain="robotics",
            terms={
                "sensor.distance": {
                    "maps_to": "sensor_distance",
                    "concept": "distance reading",
                    "visual": "gauge reads value",
                },
            },
        )
        source = "name test\nseed sensor.distance with 25"
        canonical, rewrites = pack.preprocess_with_map(source)
        spans = align_poem(canonical, target="python", rewrites=rewrites)
        output = align_to_json(spans)
        data = _json.loads(output)
        domain_entries = [e for e in data if "domain_original" in e]
        assert len(domain_entries) >= 1
        assert domain_entries[0]["domain_concept"] == "distance reading"

    def test_json_no_domain_fields_without_provenance(self):
        """to_json omits domain fields when no domain provenance."""
        import json as _json
        spans = align_poem("name test\nseed x with 1", target="python")
        output = align_to_json(spans)
        data = _json.loads(output)
        for entry in data:
            assert "domain_original" not in entry


# --- Curriculum Mapper ---

class TestCurriculum:
    def _read_curriculum(self, name):
        import pathlib
        path = pathlib.Path(__file__).parent.parent / "examples" / "curricula" / name
        return str(path)

    def test_list_curricula(self):
        names = list_curricula()
        assert "grade5_robotics" in names
        assert "k8_stem_progression" in names

    def test_find_curriculum(self):
        path = find_curriculum("grade5_robotics")
        assert path is not None
        assert path.endswith(".yaml")

    def test_find_curriculum_missing(self):
        path = find_curriculum("nonexistent_curriculum")
        assert path is None

    def test_load_grade5_robotics(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        assert pack.curriculum == "grade5_robotics_intro"
        assert pack.grade_band == "3-5"
        assert pack.domain == "robotics"
        assert len(pack.units) >= 3

    def test_load_k8_progression(self):
        path = find_curriculum("k8_stem_progression")
        pack = load_curriculum(path)
        assert pack.curriculum == "k8_stem_progression"
        assert pack.grade_band == "K-8"
        assert len(pack.units) >= 5

    def test_unit_listing(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        titles = pack.list_units()
        assert "Inputs and Outputs" in titles
        assert "Conditions and Actions" in titles

    def test_get_unit(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        unit = pack.get_unit("Inputs and Outputs")
        assert unit is not None
        assert unit.title == "Inputs and Outputs"

    def test_get_unit_missing(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        assert pack.get_unit("Nonexistent Unit") is None

    def test_unit_standards(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        unit = pack.get_unit("Conditions and Actions")
        assert len(unit.standards) >= 1
        std_ids = [s.standard_id for s in unit.standards]
        assert any("CSTA" in s for s in std_ids)

    def test_unit_concepts(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        unit = pack.get_unit("Conditions and Actions")
        concept_ids = [c.concept_id for c in unit.concepts]
        assert "input_condition_action" in concept_ids

    def test_concept_has_ops(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        concept = pack.get_concept("input_condition_action")
        assert concept is not None
        assert "seed" in concept.poetica_ops
        assert "when" in concept.poetica_ops

    def test_get_concept_missing(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        assert pack.get_concept("nonexistent") is None

    def test_list_all_concepts(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        concepts = pack.list_concepts()
        ids = [c.concept_id for c in concepts]
        assert "input_output" in ids
        assert "input_condition_action" in ids

    def test_lessons_for_concept(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        lessons = pack.get_lessons_for_concept("input_condition_action")
        assert len(lessons) >= 1
        assert lessons[0].domain == "robotics"

    def test_lessons_for_concept_missing(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        lessons = pack.get_lessons_for_concept("nonexistent")
        assert len(lessons) == 0

    def test_lesson_has_evidence(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        lessons = pack.get_lessons_for_concept("input_condition_action")
        assert len(lessons) >= 1
        assert len(lessons[0].evidence) >= 1
        assert "threshold" in lessons[0].evidence[1].description.lower() or \
               "modify" in lessons[0].evidence[1].description.lower()

    def test_lesson_has_visual_world(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        lessons = pack.get_lessons_for_concept("input_condition_action")
        assert lessons[0].visual_world == "robot_grid"

    def test_lesson_target_languages(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        lessons = pack.get_lessons_for_concept("input_condition_action")
        assert "python" in lessons[0].target_languages

    def test_all_ops_known(self):
        """All Poetica ops in curricula must be known ops."""
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        all_ops = pack.all_ops()
        for op in all_ops:
            assert op in KNOWN_OPS, f"Unknown op: {op}"

    def test_validate_grade5(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        errors = pack.validate()
        assert len(errors) == 0, f"Validation errors: {errors}"

    def test_validate_k8(self):
        path = find_curriculum("k8_stem_progression")
        pack = load_curriculum(path)
        errors = pack.validate()
        assert len(errors) == 0, f"Validation errors: {errors}"

    def test_validate_missing_name(self):
        pack = CurriculumPack(curriculum="", grade_band="3-5",
                              units=[Unit(title="test")])
        errors = pack.validate()
        assert any("curriculum name" in e for e in errors)

    def test_validate_missing_grade(self):
        pack = CurriculumPack(curriculum="test", grade_band="",
                              units=[Unit(title="test")])
        errors = pack.validate()
        assert any("grade_band" in e for e in errors)

    def test_validate_no_units(self):
        pack = CurriculumPack(curriculum="test", grade_band="3-5")
        errors = pack.validate()
        assert any("unit" in e for e in errors)

    def test_validate_unknown_op(self):
        pack = CurriculumPack(
            curriculum="test", grade_band="3-5",
            units=[Unit(title="test", poetica_ops=["seed", "teleport"])],
        )
        errors = pack.validate()
        assert any("teleport" in e for e in errors)

    def test_validate_unknown_world(self):
        pack = CurriculumPack(
            curriculum="test", grade_band="3-5",
            units=[Unit(title="test", visual_worlds=["robot_grid", "mars_colony"])],
        )
        errors = pack.validate()
        assert any("mars_colony" in e for e in errors)

    def test_validate_unknown_domain(self):
        pack = CurriculumPack(
            curriculum="test", grade_band="3-5", domain="alchemy",
            units=[Unit(title="test")],
        )
        errors = pack.validate()
        assert any("alchemy" in e for e in errors)

    def test_inspect_output(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        output = inspect_curriculum(pack)
        assert "grade5_robotics_intro" in output
        assert "3-5" in output
        assert "robotics" in output
        assert "Inputs and Outputs" in output
        assert "Validation: OK" in output

    def test_map_output(self):
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        output = map_curriculum(pack)
        assert "input_condition_action" in output
        assert "robotics" in output

    def test_generate_lesson(self):
        lesson = Lesson(
            phrase="name test\nseed x with 42\nemit x",
            concept_id="variable",
            target_languages=["python"],
        )
        output = generate_lesson(lesson)
        assert "Visual:" in output
        assert "Phrase:" in output
        assert "Code:" in output

    def test_generate_lesson_with_domain(self):
        lesson = Lesson(
            phrase="name test\nseed sensor.distance with 25\nemit sensor.distance",
            concept_id="input_output",
            domain="robotics",
            target_languages=["python"],
        )
        output = generate_lesson(lesson, domain_name="robotics")
        # Should have domain provenance (Original/Canonical) for rewritten lines
        assert "sensor_distance" in output

    def test_generate_evidence_json(self):
        import json as _json
        lesson = Lesson(
            phrase="name test\nseed x with 1",
            concept_id="variable",
            evidence=[
                EvidenceItem(description="student can explain the variable"),
                EvidenceItem(description="student can change the value", evidence_type="modification"),
            ],
        )
        output = generate_evidence_json(lesson, curriculum_name="test_cur", concept_id="variable")
        data = _json.loads(output)
        assert data["curriculum"] == "test_cur"
        assert data["concept"] == "variable"
        assert len(data["evidence_criteria"]) == 2
        assert data["evidence_criteria"][0]["met"] is None
        assert data["evidence_criteria"][1]["type"] == "modification"

    def test_curriculum_from_grade5_lesson_generates(self):
        """Full pipeline: load curriculum → get lesson → generate output."""
        path = find_curriculum("grade5_robotics")
        pack = load_curriculum(path)
        lessons = pack.get_lessons_for_concept("input_condition_action")
        assert len(lessons) >= 1
        output = generate_lesson(lessons[0], domain_name=pack.domain)
        # Should produce alignment lesson with code
        assert len(output) > 0
        # Should contain Python code
        assert "Code:" in output or "Canonical:" in output

    def test_existing_tests_unbroken(self):
        """Canary: existing compile still works after curriculum additions."""
        code = compile_poem("name test\nseed x with 1\nemit x", target="python")
        assert "x = 1" in code
        assert "print" in code


# --- Syllabus Import ---

class TestSyllabus:
    def _read_syllabus(self):
        import pathlib
        path = pathlib.Path(__file__).parent.parent / "examples" / "syllabi" / "grade5_robotics_syllabus.txt"
        return path.read_text()

    def test_extract_title(self):
        text = self._read_syllabus()
        extraction = extract_syllabus(text)
        assert "Robotics" in extraction.title or "Grade 5" in extraction.title

    def test_extract_grade_band(self):
        text = self._read_syllabus()
        extraction = extract_syllabus(text)
        assert extraction.grade_band == "5"

    def test_extract_subject(self):
        text = self._read_syllabus()
        extraction = extract_syllabus(text)
        assert extraction.subject == "Robotics"

    def test_extract_standards(self):
        text = self._read_syllabus()
        extraction = extract_syllabus(text)
        assert len(extraction.standards_refs) >= 2
        refs_str = " ".join(extraction.standards_refs)
        assert "CSTA" in refs_str
        assert "NGSS" in refs_str

    def test_extract_units(self):
        text = self._read_syllabus()
        extraction = extract_syllabus(text)
        assert len(extraction.units) >= 4
        titles = [u.title for u in extraction.units]
        assert "Inputs and Outputs" in titles
        assert "Conditions and Decisions" in titles

    def test_extract_objectives(self):
        text = self._read_syllabus()
        extraction = extract_syllabus(text)
        unit1 = extraction.units[0]
        assert len(unit1.objectives) >= 2
        assert any("input" in obj.lower() for obj in unit1.objectives)

    def test_extract_vocabulary(self):
        text = self._read_syllabus()
        extraction = extract_syllabus(text)
        unit1 = extraction.units[0]
        assert len(unit1.vocabulary) >= 3
        assert "input" in unit1.vocabulary or "sensor" in unit1.vocabulary

    def test_match_sensor_trigger_to_concept(self):
        """'sensors can trigger actions' maps to input_condition_action."""
        unit = ExtractedUnit(
            title="Test",
            raw_text="",
            objectives=[
                "Students will understand that sensors can trigger actions in a robot.",
            ],
        )
        matches = match_concepts(unit)
        concept_ids = [m.concept_id for m in matches]
        assert "input_condition_action" in concept_ids

    def test_match_store_values_to_variable(self):
        """'store and change values' maps to variable_state."""
        unit = ExtractedUnit(
            title="Test",
            raw_text="",
            objectives=[
                "Students will store and change values using variables.",
            ],
        )
        matches = match_concepts(unit)
        concept_ids = [m.concept_id for m in matches]
        assert "variable_state" in concept_ids

    def test_match_condition_to_decision(self):
        unit = ExtractedUnit(
            title="Test",
            raw_text="",
            objectives=[
                "Students will use conditions to make decisions in code.",
            ],
        )
        matches = match_concepts(unit)
        concept_ids = [m.concept_id for m in matches]
        assert "decision" in concept_ids

    def test_match_loop_to_loop_collection(self):
        unit = ExtractedUnit(
            title="Test",
            raw_text="",
            objectives=[
                "Students will repeat actions using loops.",
                "Students will iterate over collections of data.",
            ],
        )
        matches = match_concepts(unit)
        concept_ids = [m.concept_id for m in matches]
        assert "loop_collection" in concept_ids

    def test_match_debug_to_debugging(self):
        unit = ExtractedUnit(
            title="Test",
            raw_text="",
            objectives=[
                "Students will debug programs by finding misplaced instructions.",
            ],
        )
        matches = match_concepts(unit)
        concept_ids = [m.concept_id for m in matches]
        assert "debugging" in concept_ids

    def test_match_confidence_is_bounded(self):
        unit = ExtractedUnit(
            title="Test",
            raw_text="",
            objectives=[
                "Students will understand that sensors can trigger actions in a robot.",
            ],
        )
        matches = match_concepts(unit)
        for m in matches:
            assert 0.0 <= m.confidence <= 1.0

    def test_suggest_domain_robotics(self):
        text = "This course covers robots, sensors, and motors."
        assert suggest_domain(text) == "robotics"

    def test_suggest_domain_empty(self):
        text = "This course covers philosophy."
        assert suggest_domain(text) == ""

    def test_suggest_visual_worlds(self):
        matches = match_concepts(ExtractedUnit(
            title="Test",
            raw_text="",
            objectives=["Students will understand that sensors can trigger actions."],
        ))
        worlds = suggest_visual_worlds(matches)
        assert "robot_grid" in worlds

    def test_inspect_syllabus(self):
        text = self._read_syllabus()
        output = inspect_syllabus(text)
        assert "Robotics" in output
        assert "Unit" in output
        assert "Objectives" in output

    def test_draft_yaml_output(self):
        text = self._read_syllabus()
        extraction = extract_syllabus(text)
        yaml_str = draft_curriculum_yaml(extraction, subject="Robotics", grade_band="5")
        assert "curriculum:" in yaml_str
        assert "grade_band:" in yaml_str
        assert "units:" in yaml_str
        assert "needs_teacher_review: true" in yaml_str

    def test_draft_yaml_has_concepts(self):
        text = self._read_syllabus()
        extraction = extract_syllabus(text)
        yaml_str = draft_curriculum_yaml(extraction)
        assert "input_condition_action" in yaml_str or "decision" in yaml_str

    def test_draft_yaml_suggests_domain(self):
        text = self._read_syllabus()
        extraction = extract_syllabus(text)
        yaml_str = draft_curriculum_yaml(extraction)
        assert "domain: robotics" in yaml_str

    def test_draft_yaml_loadable(self):
        """Generated YAML can be loaded by load_curriculum()."""
        import tempfile
        text = self._read_syllabus()
        extraction = extract_syllabus(text)
        yaml_str = draft_curriculum_yaml(extraction, subject="Robotics", grade_band="5")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_str)
            tmp_path = f.name

        try:
            pack = load_curriculum(tmp_path)
            assert pack.curriculum != ""
            assert pack.grade_band == "5"
            assert len(pack.units) >= 4
        finally:
            os.unlink(tmp_path)

    def test_draft_yaml_validate_reports_review(self):
        """Generated YAML should validate (or report clear review warnings)."""
        import tempfile
        text = self._read_syllabus()
        extraction = extract_syllabus(text)
        yaml_str = draft_curriculum_yaml(extraction, subject="Robotics", grade_band="5")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_str)
            tmp_path = f.name

        try:
            pack = load_curriculum(tmp_path)
            errors = pack.validate()
            # Should not have fatal errors (unknown ops, missing name, etc.)
            fatal = [e for e in errors if "unknown op" in e or "name is required" in e]
            assert len(fatal) == 0, f"Fatal validation errors: {fatal}"
        finally:
            os.unlink(tmp_path)

    def test_full_pipeline_syllabus_to_lesson(self):
        """Full pipeline: syllabus → extract → draft → load → get lesson → generate."""
        import tempfile
        text = self._read_syllabus()
        extraction = extract_syllabus(text)
        yaml_str = draft_curriculum_yaml(extraction, subject="Robotics", grade_band="5")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_str)
            tmp_path = f.name

        try:
            pack = load_curriculum(tmp_path)
            # Should have concepts we can generate lessons for
            all_concepts = pack.list_concepts()
            assert len(all_concepts) > 0
        finally:
            os.unlink(tmp_path)


# --- Grade 5 Robotics Demo ---

class TestGrade5RoboticsDemo:
    """Tests for the Grade 5 Robotics full curriculum demo."""

    def _demo_path(self, name):
        import pathlib
        return str(pathlib.Path(__file__).parent.parent / "demos" / "grade5_robotics" / name)

    def test_run_demo_exits_zero(self):
        """run_demo.sh completes without errors."""
        import pathlib
        demo_dir = pathlib.Path(__file__).parent.parent
        result = subprocess.run(
            ["bash", self._demo_path("run_demo.sh")],
            cwd=str(demo_dir),
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, f"Demo failed:\n{result.stderr}\n{result.stdout[-500:]}"

    def test_generated_curriculum_loads(self):
        """generated_curriculum.yaml loads with load_curriculum()."""
        pack = load_curriculum(self._demo_path("generated_curriculum.yaml"))
        assert pack.curriculum != ""
        assert pack.grade_band == "5"
        assert len(pack.units) >= 4

    def test_generated_curriculum_validates(self):
        """generated_curriculum.yaml has no fatal validation errors."""
        pack = load_curriculum(self._demo_path("generated_curriculum.yaml"))
        errors = pack.validate()
        fatal = [e for e in errors if "unknown op" in e or "name is required" in e]
        assert len(fatal) == 0, f"Fatal errors: {fatal}"

    def test_lesson_output_has_layers(self):
        """Lesson file includes Original, Canonical, Concept, Code, Visual."""
        import pathlib
        text = pathlib.Path(self._demo_path("lesson_input_condition_action.txt")).read_text()
        assert "Original:" in text
        assert "Canonical:" in text
        assert "Concept:" in text
        assert "Code:" in text
        assert "Visual:" in text

    def test_lesson_has_domain_terms(self):
        """Lesson file shows domain language (stop motor, sensor.distance)."""
        import pathlib
        text = pathlib.Path(self._demo_path("lesson_input_condition_action.txt")).read_text()
        assert "stop motor" in text
        assert "sensor.distance" in text or "sensor_distance" in text

    def test_evidence_json_valid(self):
        """evidence JSON has curriculum, concept, evidence_criteria."""
        import pathlib
        data = json.loads(pathlib.Path(
            self._demo_path("evidence_input_condition_action.json")
        ).read_text())
        assert "curriculum" in data
        assert "concept" in data
        assert "evidence_criteria" in data
        assert len(data["evidence_criteria"]) >= 2
        for crit in data["evidence_criteria"]:
            assert "description" in crit
            assert "met" in crit

    def test_evidence_criteria_are_observable(self):
        """Evidence criteria are specific and observable, not letter grades."""
        import pathlib
        data = json.loads(pathlib.Path(
            self._demo_path("evidence_input_condition_action.json")
        ).read_text())
        descriptions = [c["description"] for c in data["evidence_criteria"]]
        # Should have actionable criteria, not vague grades
        assert any("explain" in d for d in descriptions)
        assert any("modify" in d or "threshold" in d for d in descriptions)

    def test_visual_has_grid(self):
        """Visual output shows robot_grid with ASCII grid."""
        import pathlib
        text = pathlib.Path(self._demo_path("visual_robot_grid.txt")).read_text()
        assert "+---+" in text
        assert "^" in text  # robot arrow
        assert "Step 1" in text

    def test_demo_transcript_has_full_pipeline(self):
        """Transcript contains all pipeline steps."""
        import pathlib
        text = pathlib.Path(self._demo_path("demo_transcript.txt")).read_text()
        assert "STEP 1" in text
        assert "STEP 2" in text
        assert "STEP 3" in text
        assert "STEP 4" in text
        assert "STEP 5" in text
        assert "STEP 6" in text
        assert "STEP 7" in text

    def test_demo_transcript_has_lesson(self):
        """Transcript includes alignment lesson with domain provenance."""
        import pathlib
        text = pathlib.Path(self._demo_path("demo_transcript.txt")).read_text()
        assert "Original:" in text
        assert "Canonical:" in text
        assert "motor_speed" in text

    def test_obstacle_poem_compiles_with_domain(self):
        """obstacle_stop.poem compiles to Python through robotics domain."""
        import pathlib
        from poetica.domain import find_domain, load_domain
        source = pathlib.Path(self._demo_path("obstacle_stop.poem")).read_text()
        path = find_domain("robotics")
        pack = load_domain(path)
        canonical = pack.preprocess(source)
        code = compile_poem(canonical, target="python", level=2)
        assert "sensor_distance" in code
        assert "motor_speed" in code
        assert "print" in code
