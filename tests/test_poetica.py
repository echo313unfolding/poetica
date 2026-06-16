"""Tests for the poetica standalone package."""

import json
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
