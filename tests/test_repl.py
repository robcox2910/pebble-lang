"""Tests for the interactive REPL (Phase 16).

Verify that the REPL evaluates input, persists state across lines,
recovers from errors, and handles multi-line input.
"""

from io import StringIO
from unittest.mock import patch

import pytest

from pebble.errors import PebbleRuntimeError, SemanticError
from pebble.repl import Repl, read_input

# -- Named constants ----------------------------------------------------------

EXIT_SUCCESS = 0
VALUE_42 = 42
VALUE_7 = 7


# -- Cycle 1: Basic evaluation -----------------------------------------------


class TestReplBasic:
    """Verify basic REPL evaluation."""

    def test_simple_print(self) -> None:
        """REPL evaluates print and captures output."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("print(42)")
        assert buf.getvalue() == "42\n"

    def test_arithmetic_expression(self) -> None:
        """REPL evaluates expressions inside print."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("print(1 + 2)")
        assert buf.getvalue() == "3\n"

    def test_empty_input_is_ignored(self) -> None:
        """Empty or whitespace-only input does nothing."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("")
        r.eval_line("   ")
        assert buf.getvalue() == ""


# -- Cycle 2: Persistent variables -------------------------------------------


class TestReplPersistentVariables:
    """Verify variables persist across REPL inputs."""

    def test_variable_persists(self) -> None:
        """Variable declared in one input is available in the next."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("let x = 10")
        r.eval_line("print(x)")
        assert buf.getvalue() == "10\n"

    def test_variable_reassignment(self) -> None:
        """Variable can be reassigned in a later input."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("let x = 1")
        r.eval_line("x = 42")
        r.eval_line("print(x)")
        assert buf.getvalue() == "42\n"

    def test_multiple_variables(self) -> None:
        """Multiple variables persist independently."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("let a = 10")
        r.eval_line("let b = 20")
        r.eval_line("print(a + b)")
        assert buf.getvalue() == "30\n"


# -- Cycle 3: Persistent functions -------------------------------------------


class TestReplPersistentFunctions:
    """Verify functions persist across REPL inputs."""

    def test_function_persists(self) -> None:
        """Function defined in one input is callable in the next."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("fn add(a, b) { return a + b }")
        r.eval_line("print(add(3, 4))")
        assert buf.getvalue() == "7\n"

    def test_function_uses_variable(self) -> None:
        """Function and variables from different inputs work together."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("fn double(n) { return n * 2 }")
        r.eval_line("let x = 21")
        r.eval_line("print(double(x))")
        assert buf.getvalue() == "42\n"


# -- Cycle 4: Multi-line input -----------------------------------------------


class TestReplMultiLine:
    """Verify multi-line input handling."""

    def test_if_block(self) -> None:
        """Multi-line if block is read as a single input."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("let x = 10\nif x > 5 {\n    print(x)\n}")
        assert buf.getvalue() == "10\n"

    def test_function_block(self) -> None:
        """Multi-line function definition works."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("fn greet(name) {\n    print(name)\n}")
        r.eval_line('greet("Alice")')
        assert buf.getvalue() == "Alice\n"

    def test_read_input_single_line(self) -> None:
        """read_input returns a single line when no braces."""
        with patch("builtins.input", return_value="print(42)"):
            result = read_input("pebble> ")
        assert result == "print(42)"

    def test_read_input_multi_line(self) -> None:
        """read_input reads continuation lines for unbalanced braces."""
        responses = iter(["if true {", "    print(1)", "}"])
        with patch("builtins.input", side_effect=responses):
            result = read_input("pebble> ")
        assert result == "if true {\n    print(1)\n}"

    def test_read_input_eof(self) -> None:
        """read_input returns None on EOF."""
        with patch("builtins.input", side_effect=EOFError):
            result = read_input("pebble> ")
        assert result is None


# -- Cycle 5: Error recovery -------------------------------------------------


class TestReplErrorRecovery:
    """Verify the REPL recovers from errors."""

    def test_syntax_error_recovers(self) -> None:
        """Syntax error doesn't corrupt REPL state."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("let x = 10")
        with pytest.raises(Exception):  # noqa: B017, PT011
            r.eval_line("let = oops")
        r.eval_line("print(x)")
        assert buf.getvalue() == "10\n"

    def test_runtime_error_recovers(self) -> None:
        """Runtime error preserves previous state."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("let x = 10")
        with pytest.raises(PebbleRuntimeError):
            r.eval_line("let y = 1 / 0")
        r.eval_line("print(x)")
        assert buf.getvalue() == "10\n"

    def test_undeclared_variable_error(self) -> None:
        """Using undeclared variable gives semantic error."""
        buf = StringIO()
        r = Repl(output=buf)
        with pytest.raises(SemanticError, match="Undeclared"):
            r.eval_line("print(nope)")


# -- Cycle 6: Integration ----------------------------------------------------


class TestReplIntegration:
    """End-to-end REPL scenarios."""

    def test_full_session(self) -> None:
        """Simulate a full REPL session with variables, functions, and loops."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("fn add(a, b) { return a + b }")
        r.eval_line("let x = add(10, 20)")
        r.eval_line("print(x)")
        r.eval_line("for i in range(3) {\n    print(i)\n}")
        assert buf.getvalue() == "30\n0\n1\n2\n"

    def test_builtin_functions_work(self) -> None:
        """Built-in functions work in REPL context."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("print(len([1, 2, 3]))")
        r.eval_line("print(type(42))")
        assert buf.getvalue() == "3\nint\n"

    def test_string_interpolation_works(self) -> None:
        """String interpolation works in REPL context."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line('let name = "World"')
        r.eval_line('print("Hello {name}")')
        assert buf.getvalue() == "Hello World\n"

    def test_closures_work(self) -> None:
        """Closures work across REPL inputs."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line(
            "fn make_counter() {\n"
            "    let count = 0\n"
            "    fn inc() {\n"
            "        count = count + 1\n"
            "        return count\n"
            "    }\n"
            "    return inc\n"
            "}"
        )
        r.eval_line("let c = make_counter()")
        r.eval_line("print(c())")
        r.eval_line("print(c())")
        assert buf.getvalue() == "1\n2\n"
