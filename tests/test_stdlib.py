"""Tests for the standard library built-in functions (Phase 13).

Cover the builtins module, analyzer registration, and VM execution of
str(), int(), type(), push(), and pop().
"""

from io import StringIO

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.builtins import BUILTIN_ARITIES, BUILTINS, format_value
from pebble.compiler import Compiler
from pebble.errors import PebbleRuntimeError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.vm import VirtualMachine

# -- Named constants ----------------------------------------------------------

RUNTIME_BUILTIN_COUNT = 6
TOTAL_BUILTIN_COUNT = 8


# -- Helpers ------------------------------------------------------------------


def _run_source(source: str) -> str:
    """Compile and run *source*, returning captured output."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzed = SemanticAnalyzer().analyze(program)
    compiled = Compiler().compile(analyzed)
    buf = StringIO()
    VirtualMachine(output=buf).run(compiled)
    return buf.getvalue()


# -- Cycle 1: Builtins module + str() ----------------------------------------


class TestBuiltinsModule:
    """Verify the builtins registry structure."""

    def test_runtime_builtin_count(self) -> None:
        """There are 6 runtime builtins."""
        assert len(BUILTINS) == RUNTIME_BUILTIN_COUNT

    def test_total_builtin_arities(self) -> None:
        """BUILTIN_ARITIES includes all 8 builtins."""
        assert len(BUILTIN_ARITIES) == TOTAL_BUILTIN_COUNT

    def test_all_runtime_builtins_in_arities(self) -> None:
        """Every runtime builtin appears in BUILTIN_ARITIES."""
        for name in BUILTINS:
            assert name in BUILTIN_ARITIES


class TestFormatValue:
    """Verify the format_value helper."""

    def test_format_int(self) -> None:
        """format_value(42) returns '42'."""
        assert format_value(42) == "42"

    def test_format_str(self) -> None:
        """format_value('hello') returns 'hello'."""
        assert format_value("hello") == "hello"

    def test_format_bool_true(self) -> None:
        """format_value(True) returns 'true'."""
        assert format_value(True) == "true"  # noqa: FBT003

    def test_format_bool_false(self) -> None:
        """format_value(False) returns 'false'."""
        assert format_value(False) == "false"  # noqa: FBT003

    def test_format_list(self) -> None:
        """format_value([1, 2, 3]) returns '[1, 2, 3]'."""
        assert format_value([1, 2, 3]) == "[1, 2, 3]"


class TestStrBuiltin:
    """Verify str() conversion."""

    def test_str_of_int(self) -> None:
        """str(42) returns '42'."""
        assert _run_source("print(str(42))") == "42\n"

    def test_str_of_bool_true(self) -> None:
        """str(true) returns 'true'."""
        assert _run_source("print(str(true))") == "true\n"

    def test_str_of_bool_false(self) -> None:
        """str(false) returns 'false'."""
        assert _run_source("print(str(false))") == "false\n"

    def test_str_of_string(self) -> None:
        """str('hello') returns 'hello'."""
        assert _run_source('print(str("hello"))') == "hello\n"

    def test_str_of_list(self) -> None:
        """str([1, 2]) returns '[1, 2]'."""
        assert _run_source("print(str([1, 2]))") == "[1, 2]\n"


# -- Cycle 2: int() + type() -------------------------------------------------


class TestIntBuiltin:
    """Verify int() conversion."""

    def test_int_of_string(self) -> None:
        """int('42') returns 42."""
        assert _run_source('print(int("42"))') == "42\n"

    def test_int_of_negative_string(self) -> None:
        """int('-7') returns -7."""
        assert _run_source('print(int("-7"))') == "-7\n"

    def test_int_of_int(self) -> None:
        """int(42) returns 42 (identity)."""
        assert _run_source("print(int(42))") == "42\n"

    def test_int_of_non_numeric_string(self) -> None:
        """int('hello') raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="Cannot convert"):
            _run_source('int("hello")')

    def test_int_of_bool(self) -> None:
        """int(true) raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="Cannot convert"):
            _run_source("int(true)")


class TestTypeBuiltin:
    """Verify type() introspection."""

    def test_type_of_int(self) -> None:
        """type(42) returns 'int'."""
        assert _run_source("print(type(42))") == "int\n"

    def test_type_of_str(self) -> None:
        """type('hello') returns 'str'."""
        assert _run_source('print(type("hello"))') == "str\n"

    def test_type_of_bool(self) -> None:
        """type(true) returns 'bool'."""
        assert _run_source("print(type(true))") == "bool\n"

    def test_type_of_list(self) -> None:
        """type([]) returns 'list'."""
        assert _run_source("print(type([]))") == "list\n"


# -- Cycle 3: push() + pop() -------------------------------------------------


class TestPushBuiltin:
    """Verify push() list mutation."""

    def test_push_appends_element(self) -> None:
        """push(xs, 4) appends 4 to the list."""
        source = "let xs = [1, 2, 3]\npush(xs, 4)\nprint(xs)"
        assert _run_source(source) == "[1, 2, 3, 4]\n"

    def test_push_returns_list(self) -> None:
        """push() returns the mutated list."""
        source = "let xs = [1]\nprint(push(xs, 2))"
        assert _run_source(source) == "[1, 2]\n"

    def test_push_to_empty_list(self) -> None:
        """push([], 1) works on empty lists."""
        source = "let xs = []\npush(xs, 1)\nprint(xs)"
        assert _run_source(source) == "[1]\n"

    def test_push_non_list_error(self) -> None:
        """push() on a non-list raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="requires a list"):
            _run_source('push("hello", 1)')


class TestPopBuiltin:
    """Verify pop() list mutation."""

    def test_pop_removes_last(self) -> None:
        """pop(xs) removes and returns the last element."""
        source = "let xs = [1, 2, 3]\nlet last = pop(xs)\nprint(last)\nprint(xs)"
        assert _run_source(source) == "3\n[1, 2]\n"

    def test_pop_empty_list_error(self) -> None:
        """pop([]) raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="empty list"):
            _run_source("let xs = []\npop(xs)")

    def test_pop_non_list_error(self) -> None:
        """pop() on a non-list raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="requires a list"):
            _run_source('pop("hello")')


# -- Cycle 4: Analyzer registration -------------------------------------------


class TestAnalyzerBuiltins:
    """Verify the analyzer recognizes all builtins."""

    def test_push_arity_check(self) -> None:
        """push() with wrong arity raises SemanticError."""
        with pytest.raises(SemanticError, match="expects 2"):
            _run_source("push([1])")

    def test_pop_arity_check(self) -> None:
        """pop() with wrong arity raises SemanticError."""
        with pytest.raises(SemanticError, match="expects 1"):
            _run_source("pop([1], 2)")

    def test_undeclared_function_still_caught(self) -> None:
        """Calling an unknown function still raises SemanticError."""
        with pytest.raises(SemanticError, match="Undeclared function"):
            _run_source("foo()")

    def test_existing_builtins_still_work(self) -> None:
        """print, range, and len still work after refactor."""
        source = """\
let xs = [1, 2, 3]
for i in range(len(xs)) {
    print(xs[i])
}"""
        assert _run_source(source) == "1\n2\n3\n"


# -- Cycle 5: Integration ----------------------------------------------------


class TestStdlibIntegration:
    """End-to-end tests combining stdlib with other features."""

    def test_build_list_with_push(self) -> None:
        """Build a list dynamically using push in a loop."""
        source = """\
let xs = []
for i in range(3) {
    push(xs, i * 10)
}
print(xs)"""
        assert _run_source(source) == "[0, 10, 20]\n"

    def test_type_check_in_condition(self) -> None:
        """Use type() in an if condition."""
        source = """\
let x = 42
if type(x) == "int" {
    print("it is an integer")
}"""
        assert _run_source(source) == "it is an integer\n"

    def test_str_in_interpolation(self) -> None:
        """Use str() inside string interpolation."""
        source = 'let x = 42\nprint("value: {str(x)}")'
        assert _run_source(source) == "value: 42\n"

    def test_int_round_trip(self) -> None:
        """Convert int to str to int."""
        source = """\
let x = 42
let s = str(x)
let y = int(s)
print(y)"""
        assert _run_source(source) == "42\n"

    def test_stack_with_push_pop(self) -> None:
        """Use push/pop to implement a simple stack."""
        source = """\
let stack = []
push(stack, 1)
push(stack, 2)
push(stack, 3)
let top = pop(stack)
print("popped: {top}, remaining: {len(stack)}")"""
        assert _run_source(source) == "popped: 3, remaining: 2\n"
