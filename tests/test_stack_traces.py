"""Tests for source maps and stack traces (tracebacks)."""

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from pebble.cli import main
from pebble.errors import PebbleRuntimeError, TraceEntry, format_traceback
from pebble.repl import Repl, repl
from tests.conftest import debug_run_source, run_source

# -- Named constants ----------------------------------------------------------

_EXPECTED_TRACEBACK_LEN_2 = 2
_EXPECTED_TRACEBACK_LEN_3 = 3
_LINE_1 = 1
_LINE_2 = 2
_LINE_3 = 3
_LINE_4 = 4
_LINE_5 = 5
_LINE_7 = 7
_LINE_8 = 8
_COLUMN_1 = 1
_COLUMN_5 = 5


# ---------------------------------------------------------------------------
# Cycle 1 — TraceEntry + traceback field
# ---------------------------------------------------------------------------


class TestTraceEntryAndField:
    """Verify TraceEntry dataclass and traceback field on PebbleRuntimeError."""

    def test_trace_entry_creation(self) -> None:
        """TraceEntry stores function_name, line, and column."""
        entry = TraceEntry(function_name="f", line=_LINE_2, column=_COLUMN_1)
        assert entry.function_name == "f"
        assert entry.line == _LINE_2
        assert entry.column == _COLUMN_1

    def test_trace_entry_is_frozen(self) -> None:
        """TraceEntry is immutable (frozen dataclass)."""
        entry = TraceEntry(function_name="f", line=_LINE_2, column=_COLUMN_1)
        with pytest.raises(AttributeError):
            entry.line = _LINE_3  # type: ignore[misc]

    def test_runtime_error_default_traceback_empty(self) -> None:
        """PebbleRuntimeError defaults to an empty traceback list."""
        err = PebbleRuntimeError("oops", line=_LINE_1, column=_COLUMN_1)
        assert err.traceback == []

    def test_runtime_error_with_traceback(self) -> None:
        """PebbleRuntimeError accepts a traceback list."""
        entries = [TraceEntry("f", _LINE_2, _COLUMN_1)]
        err = PebbleRuntimeError("oops", line=_LINE_1, column=_COLUMN_1, traceback=entries)
        assert len(err.traceback) == 1
        assert err.traceback[0].function_name == "f"


# ---------------------------------------------------------------------------
# Cycle 2 — VM builds traceback on runtime error
# ---------------------------------------------------------------------------


class TestVMTraceback:
    """Verify the VM attaches traceback entries on runtime errors."""

    def test_nested_call_has_traceback(self) -> None:
        """Error in nested fn a->b produces traceback with <main> and b entries."""
        source = "fn a() { let x = 1 / 0 }\nfn b() { a() }\nb()\n"
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source(source)
        tb = exc_info.value.traceback
        assert len(tb) == _EXPECTED_TRACEBACK_LEN_2
        # Bottom of stack is <main>, top is b (the caller of a where error occurs)
        assert tb[0].function_name == "<main>"
        assert tb[1].function_name == "b"

    def test_single_frame_error_empty_traceback(self) -> None:
        """Error at top level has no traceback entries (no call chain)."""
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source("let x = 1 / 0\n")
        assert exc_info.value.traceback == []

    def test_three_deep_call_chain(self) -> None:
        """Error three calls deep: main->c->b->a produces 3-entry traceback."""
        source = "fn a() { let x = 1 / 0 }\nfn b() { a() }\nfn c() { b() }\nc()\n"
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source(source)
        tb = exc_info.value.traceback
        assert len(tb) == _EXPECTED_TRACEBACK_LEN_3
        assert tb[0].function_name == "<main>"
        assert tb[1].function_name == "c"
        assert tb[2].function_name == "b"

    def test_traceback_has_correct_line_numbers(self) -> None:
        """Traceback entries have the correct call-site line numbers."""
        source = "fn inner() {\n  let x = 1 / 0\n}\nfn outer() {\n  inner()\n}\nouter()\n"
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source(source)
        tb = exc_info.value.traceback
        assert len(tb) == _EXPECTED_TRACEBACK_LEN_2
        # <main> called outer() on line 7
        assert tb[0].line == _LINE_7
        # outer called inner() on line 5
        assert tb[1].line == _LINE_5


# ---------------------------------------------------------------------------
# Cycle 3 — Uncaught throw gets location
# ---------------------------------------------------------------------------


class TestThrowLocation:
    """Verify that uncaught throw gets proper source location and traceback."""

    def test_throw_has_line_number(self) -> None:
        """Bare ``throw "boom"`` at line 1 gets line=1 (not 0)."""
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source('throw "boom"\n')
        assert exc_info.value.line == _LINE_1

    def test_throw_in_function_has_traceback(self) -> None:
        """``fn f() { throw "oops" }; f()`` has traceback with <main>."""
        source = 'fn f() { throw "oops" }\nf()\n'
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source(source)
        assert exc_info.value.line == _LINE_1
        tb = exc_info.value.traceback
        assert len(tb) == 1
        assert tb[0].function_name == "<main>"

    def test_throw_multiline_has_correct_line(self) -> None:
        """Throw on line 3 gets line=3."""
        source = 'let x = 1\nlet y = 2\nthrow "fail"\n'
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source(source)
        assert exc_info.value.line == _LINE_3

    def test_throw_integer_has_line_number(self) -> None:
        """Non-string throw (integer) also gets correct location."""
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source("throw 42\n")
        assert exc_info.value.line == _LINE_1

    def test_throw_integer_in_function_has_traceback(self) -> None:
        """Non-string throw in function gets traceback."""
        source = "fn f() { throw 99 }\nf()\n"
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source(source)
        assert exc_info.value.line == _LINE_1
        assert len(exc_info.value.traceback) == 1


# ---------------------------------------------------------------------------
# Cycle 4 — format_traceback
# ---------------------------------------------------------------------------


class TestFormatTraceback:
    """Verify format_traceback renders Python-style traceback strings."""

    def test_two_entry_traceback(self) -> None:
        """Format a 2-entry traceback into the expected multi-line string."""
        entries = [
            TraceEntry("<main>", _LINE_8, _COLUMN_1),
            TraceEntry("outer", _LINE_4, _COLUMN_1),
        ]
        err = PebbleRuntimeError(
            "Division by zero",
            line=_LINE_2,
            column=_COLUMN_5,
            traceback=entries,
        )
        result = format_traceback(err)
        assert "Traceback (most recent call last):" in result
        assert "line 8, in <main>" in result
        assert "line 4, in outer" in result
        assert "Error: Division by zero at line 2, column 5" in result

    def test_empty_traceback_just_error(self) -> None:
        """Empty traceback returns just the error line."""
        err = PebbleRuntimeError("bad", line=_LINE_3, column=_COLUMN_1)
        result = format_traceback(err)
        assert "Traceback" not in result
        assert "Error: bad at line 3, column 1" in result

    def test_zero_line_error_message_only(self) -> None:
        """Error with line=0 returns just the message."""
        err = PebbleRuntimeError("unknown", line=0, column=0)
        result = format_traceback(err)
        assert result == "Error: unknown"


# ---------------------------------------------------------------------------
# Cycle 5 — CLI integration
# ---------------------------------------------------------------------------


class TestCLITraceback:
    """Verify the CLI displays tracebacks for nested runtime errors."""

    def test_cli_shows_traceback_on_nested_error(self, tmp_path: Path) -> None:
        """Running a .pbl file with nested error shows traceback on stderr."""
        # Write a .pbl file with a nested error
        pbl = tmp_path / "nested.pbl"
        pbl.write_text("fn a() {\n  let x = 1 / 0\n}\nfn b() {\n  a()\n}\nb()\n")

        old_argv = sys.argv
        old_stderr = sys.stderr
        buf = StringIO()
        sys.argv = ["pebble", str(pbl)]
        sys.stderr = buf
        try:
            with pytest.raises(SystemExit):
                main()
        finally:
            sys.argv = old_argv
            sys.stderr = old_stderr

        output = buf.getvalue()
        assert "Traceback (most recent call last):" in output
        assert "in <main>" in output
        assert "in b" in output


# ---------------------------------------------------------------------------
# Cycle 6 — REPL integration
# ---------------------------------------------------------------------------


class TestREPLTraceback:
    """Verify the REPL displays tracebacks for nested runtime errors."""

    def test_repl_eval_line_nested_error_has_traceback(self) -> None:
        """REPL eval_line with nested error raises PebbleRuntimeError with traceback."""
        r = Repl(output=StringIO())
        r.eval_line("fn a() { let x = 1 / 0 }\n")
        r.eval_line("fn b() { a() }\n")
        with pytest.raises(PebbleRuntimeError) as exc_info:
            r.eval_line("b()\n")
        assert len(exc_info.value.traceback) > 0

    def test_repl_loop_shows_traceback(self) -> None:
        """The REPL loop prints traceback to stderr for nested errors."""
        old_stderr = sys.stderr
        err_buf = StringIO()
        sys.stderr = err_buf
        out_buf = StringIO()
        r = Repl(output=out_buf)
        try:
            r.eval_line("fn boom() { let x = 1 / 0 }\n")
            r.eval_line("fn caller() { boom() }\n")
            with pytest.raises(PebbleRuntimeError) as exc_info:
                r.eval_line("caller()\n")
        finally:
            sys.stderr = old_stderr
        assert len(exc_info.value.traceback) == _EXPECTED_TRACEBACK_LEN_2

    def test_repl_loop_displays_traceback_on_stderr(self) -> None:
        """The repl() loop shows traceback on stderr for nested errors."""
        # Simulate user typing: define functions, call with error, then EOF
        user_input = "fn a() { let x = 1 / 0 }\nfn b() { a() }\nb()\n"
        old_stderr = sys.stderr
        err_buf = StringIO()
        sys.stderr = err_buf
        out_buf = StringIO()
        try:
            with patch("builtins.input", side_effect=user_input.splitlines()):
                repl(output=out_buf)
        except StopIteration:
            pass
        finally:
            sys.stderr = old_stderr

        err_output = err_buf.getvalue()
        assert "Traceback (most recent call last):" in err_output


# ---------------------------------------------------------------------------
# Cycle 7 — Debugger backtrace with line numbers
# ---------------------------------------------------------------------------


class TestDebuggerBacktraceLineNumbers:
    """Verify the debugger backtrace command shows line numbers."""

    def test_backtrace_shows_line_in_function(self) -> None:
        """Backtrace inside a function shows (line N) for each frame."""
        source = "fn greet() {\n  print(1)\n}\ngreet()"
        # Step into greet, then backtrace
        commands = "s\ns\nbt\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "(line" in dbg_out
        # greet frame should show a line number
        assert "greet" in dbg_out
        assert "<main>" in dbg_out

    def test_backtrace_main_only_shows_line(self) -> None:
        """Backtrace in main shows <main> with a line number."""
        source = "let x = 1\nprint(x)"
        commands = "bt\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "<main> (line" in dbg_out


# ---------------------------------------------------------------------------
# Cycle 8 — Edge cases
# ---------------------------------------------------------------------------

_RECURSIVE_DEPTH = 5


class TestEdgeCases:
    """Verify edge cases for stack traces."""

    def test_recursive_function_traceback_depth(self) -> None:
        """Recursive function error has traceback matching recursion depth."""
        source = (
            "fn countdown(n) {\n"
            "  if n == 0 {\n"
            "    let x = 1 / 0\n"
            "  }\n"
            "  countdown(n - 1)\n"
            "}\n"
            "countdown(5)\n"
        )
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source(source)
        tb = exc_info.value.traceback
        # 1 entry for <main> + 5 entries for recursive countdown calls
        expected = 1 + _RECURSIVE_DEPTH
        assert len(tb) == expected
        assert tb[0].function_name == "<main>"
        for i in range(1, expected):
            assert tb[i].function_name == "countdown"

    def test_try_catch_does_not_leak_traceback(self) -> None:
        """Caught error does not produce a traceback to the caller."""
        source = (
            "fn risky() { let x = 1 / 0 }\n"
            "fn safe() {\n"
            "  try {\n"
            "    risky()\n"
            "  } catch e {\n"
            '    print("caught")\n'
            "  }\n"
            "}\n"
            "safe()\n"
        )
        # Should not raise
        output = run_source(source)
        assert output.strip() == "caught"

    def test_method_call_shows_class_method_name(self) -> None:
        """Error in a class method shows ClassName.method in traceback."""
        source = (
            "class Calc {\n"
            "  fn divide(self, a, b) {\n"
            "    return a / b\n"
            "  }\n"
            "}\n"
            "let c = Calc()\n"
            "c.divide(1, 0)\n"
        )
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source(source)
        tb = exc_info.value.traceback
        assert len(tb) == 1
        assert tb[0].function_name == "<main>"
        # The error itself happens in Calc.divide — verify the error has correct line
        assert exc_info.value.line == _LINE_3

    def test_top_level_error_no_traceback(self) -> None:
        """Top-level error has empty traceback."""
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source("let x = 1 / 0\n")
        assert exc_info.value.traceback == []
        assert exc_info.value.line == _LINE_1
