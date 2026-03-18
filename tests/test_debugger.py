"""Tests for the Pebble bytecode debugger."""

from io import StringIO

from pebble.builtins import Value
from pebble.bytecode import CodeObject, Instruction
from pebble.cli import _parse_args
from pebble.debugger import _ALIASES, DebuggerCommand
from pebble.vm import DebugAction, Frame, VirtualMachine
from tests.conftest import compile_source, debug_run_source

_EXPECTED_ALIAS_COUNT = 9
_MIN_PROMPT_COUNT = 2


# ---------------------------------------------------------------------------
# Cycle 1 — DebugAction + DebugHook in VM
# ---------------------------------------------------------------------------


class _SpyHook:
    """Spy that records every on_instruction call."""

    def __init__(self, *, quit_after: int = 0) -> None:
        """Create a spy hook that optionally quits after *quit_after* calls."""
        self.calls: list[Instruction] = []
        self.quit_after = quit_after

    def on_instruction(
        self,
        instruction: Instruction,
        ip: int,  # noqa: ARG002
        code: CodeObject,  # noqa: ARG002
        stack: list[Value],  # noqa: ARG002
        frames: list[Frame],  # noqa: ARG002
    ) -> DebugAction:
        """Record the instruction and optionally quit."""
        self.calls.append(instruction)
        if self.quit_after and len(self.calls) >= self.quit_after:
            return DebugAction.QUIT
        return DebugAction.CONTINUE


class TestDebugHookVM:
    """Verify DebugHook integration in the VM execution loop."""

    def test_hook_called_for_every_opcode(self) -> None:
        """Spy hook receives one call per instruction (including HALT)."""
        source = "let x = 1\nlet y = 2\nprint(x + y)"
        compiled = compile_source(source)
        spy = _SpyHook()
        buf = StringIO()
        vm = VirtualMachine(output=buf)
        vm.run(compiled, debug_hook=spy)
        # The hook fires for every instruction including HALT
        assert len(spy.calls) == len(compiled.main.instructions)

    def test_quit_aborts_execution(self) -> None:
        """Returning QUIT from the hook stops the VM before completion."""
        source = "print(1)\nprint(2)\nprint(3)"
        compiled = compile_source(source)
        spy = _SpyHook(quit_after=1)
        buf = StringIO()
        vm = VirtualMachine(output=buf)
        vm.run(compiled, debug_hook=spy)
        # VM was told to quit after first instruction — no output printed
        assert buf.getvalue() == ""

    def test_no_hook_runs_normally(self) -> None:
        """Without a debug hook, execution is unaffected."""
        source = "print(42)"
        compiled = compile_source(source)
        buf = StringIO()
        vm = VirtualMachine(output=buf)
        vm.run(compiled)
        assert buf.getvalue() == "42\n"

    def test_hook_on_run_repl(self) -> None:
        """Debug hook also works through run_repl()."""
        source = "let x = 10"
        compiled = compile_source(source)
        spy = _SpyHook()
        vm = VirtualMachine()
        vm.run_repl(compiled, {}, debug_hook=spy)
        assert len(spy.calls) > 0


# ---------------------------------------------------------------------------
# Cycle 2 — Command parsing
# ---------------------------------------------------------------------------


class TestCommandParsing:
    """Verify command name and alias parsing."""

    def test_full_command_names(self) -> None:
        """Each full command name is recognized."""
        for cmd in DebuggerCommand:
            commands = f"{cmd.value}\nquit\n"
            dbg_out, _ = debug_run_source("print(1)", commands)
            assert "(pdb)" in dbg_out

    def test_aliases(self) -> None:
        """Each alias maps to the correct command."""
        assert len(_ALIASES) == _EXPECTED_ALIAS_COUNT
        assert _ALIASES["s"] is DebuggerCommand.STEP
        assert _ALIASES["n"] is DebuggerCommand.ISTEP
        assert _ALIASES["c"] is DebuggerCommand.CONTINUE
        assert _ALIASES["b"] is DebuggerCommand.BREAK
        assert _ALIASES["p"] is DebuggerCommand.PRINT
        assert _ALIASES["bt"] is DebuggerCommand.BACKTRACE
        assert _ALIASES["l"] is DebuggerCommand.LIST
        assert _ALIASES["h"] is DebuggerCommand.HELP
        assert _ALIASES["q"] is DebuggerCommand.QUIT

    def test_command_with_arg(self) -> None:
        """Commands that take arguments parse them correctly."""
        commands = "break 2\nquit\n"
        dbg_out, _ = debug_run_source("let x = 1\nprint(x)", commands)
        assert "Breakpoint set at line 2" in dbg_out

    def test_eof_returns_quit(self) -> None:
        """EOF on input stream aborts execution."""
        # Empty input = immediate EOF
        _, prog_out = debug_run_source("print(1)\nprint(2)", "")
        # Program should not have run to completion
        assert prog_out == ""

    def test_unknown_command_reprompts(self) -> None:
        """An unrecognized command prints an error and re-prompts."""
        commands = "foobar\nquit\n"
        dbg_out, _ = debug_run_source("print(1)", commands)
        assert "Unknown command: foobar" in dbg_out

    def test_blank_lines_ignored(self) -> None:
        """Blank lines are skipped without error."""
        commands = "\n\nquit\n"
        dbg_out, _ = debug_run_source("print(1)", commands)
        # Should see multiple prompts for blank lines + quit
        assert dbg_out.count("(pdb)") >= _MIN_PROMPT_COUNT


# ---------------------------------------------------------------------------
# Cycle 3 — Source-line stepping
# ---------------------------------------------------------------------------


class TestSourceLineStepping:
    """Verify source-line stepping pauses once per line change."""

    def test_three_lines_three_stops(self) -> None:
        """Three-line program pauses 3 times with step commands."""
        source = "let x = 1\nlet y = 2\nprint(x + y)"
        commands = "s\ns\ns\nq\n"
        dbg_out, prog_out = debug_run_source(source, commands)
        # The debugger shows source lines — we expect lines 1, 2, 3
        assert "1: let x = 1" in dbg_out
        assert "2: let y = 2" in dbg_out
        assert "3: print(x + y)" in dbg_out
        # Program ran to completion
        assert prog_out == "3\n"

    def test_multi_instruction_line_pauses_once(self) -> None:
        """Single-line expression with multiple opcodes pauses once."""
        source = "print(1 + 2 + 3)"
        # First stop at line 1, step should go to HALT (end)
        commands = "s\nq\n"
        dbg_out, prog_out = debug_run_source(source, commands)
        # Only one source line shown
        line_count = dbg_out.count("1: print(1 + 2 + 3)")
        assert line_count == 1
        assert prog_out == "6\n"


# ---------------------------------------------------------------------------
# Cycle 4 — Instruction stepping
# ---------------------------------------------------------------------------


class TestInstructionStepping:
    """Verify instruction-level stepping pauses on every opcode."""

    def test_istep_every_opcode(self) -> None:
        """Istep pauses on every instruction, showing opcode names."""
        source = "let x = 1\nlet y = 2"
        # First stop is source-line (default). Switch to istep, then step.
        commands = "n\nn\nn\nn\nn\nn\nn\nn\nn\nq\n"
        dbg_out, _ = debug_run_source(source, commands)
        # After switching to istep mode, opcodes are shown
        assert "STORE_NAME" in dbg_out
        assert "LOAD_CONST" in dbg_out

    def test_istep_shows_operands(self) -> None:
        """Instruction stepping shows operand values."""
        source = "let x = 42"
        commands = "n\nn\nn\nn\nq\n"
        dbg_out, _ = debug_run_source(source, commands)
        # STORE_NAME x should show operand
        assert "STORE_NAME x" in dbg_out


# ---------------------------------------------------------------------------
# Cycle 5 — Breakpoints
# ---------------------------------------------------------------------------


class TestBreakpoints:
    """Verify breakpoint setting, hitting, and clearing."""

    def test_break_and_continue(self) -> None:
        """Setting a breakpoint and continuing stops at the right line."""
        source = "let x = 1\nlet y = 2\nprint(x + y)"
        commands = "break 3\ncontinue\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        # First stop is line 1 (initial step), then continue to line 3
        assert "Breakpoint set at line 3" in dbg_out
        assert "3: print(x + y)" in dbg_out

    def test_clear_breakpoint(self) -> None:
        """Clearing a breakpoint prevents future stops there."""
        source = "let x = 1\nlet y = 2\nprint(x + y)"
        commands = "break 3\nclear 3\ncontinue\n"
        dbg_out, prog_out = debug_run_source(source, commands)
        assert "Breakpoint at line 3 cleared" in dbg_out
        # Program runs to completion since breakpoint was cleared
        assert prog_out == "3\n"

    def test_invalid_break_line(self) -> None:
        """Setting a breakpoint on an out-of-range line shows a warning."""
        source = "print(1)"
        commands = "break 99\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "out of range" in dbg_out

    def test_break_no_arg_lists_breakpoints(self) -> None:
        """Break with no argument lists current breakpoints."""
        source = "let x = 1\nlet y = 2\nprint(x + y)"
        commands = "break 2\nbreak 3\nbreak\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "Breakpoints: [2, 3]" in dbg_out

    def test_break_no_breakpoints_message(self) -> None:
        """Break with no argument and no breakpoints shows a message."""
        source = "print(1)"
        commands = "break\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "No breakpoints set" in dbg_out

    def test_clear_nonexistent(self) -> None:
        """Clearing a line without a breakpoint shows a message."""
        source = "print(1)"
        commands = "clear 5\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "No breakpoint at line 5" in dbg_out

    def test_break_invalid_arg(self) -> None:
        """Non-numeric breakpoint argument shows an error."""
        source = "print(1)"
        commands = "break abc\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "Invalid line number: abc" in dbg_out

    def test_clear_no_arg(self) -> None:
        """Clear with no argument shows usage."""
        source = "print(1)"
        commands = "clear\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "Usage: clear <line>" in dbg_out

    def test_clear_invalid_arg(self) -> None:
        """Non-numeric clear argument shows an error."""
        source = "print(1)"
        commands = "clear abc\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "Invalid line number: abc" in dbg_out


# ---------------------------------------------------------------------------
# Cycle 6 — Variable inspection
# ---------------------------------------------------------------------------


class TestVariableInspection:
    """Verify print and locals commands."""

    def test_print_variable(self) -> None:
        """Print <var> shows the variable's value."""
        source = "let x = 42\nprint(x)"
        commands = "s\nprint x\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "x = 42" in dbg_out

    def test_print_undefined_variable(self) -> None:
        """Print <var> for an undefined variable shows an error."""
        source = "let x = 1"
        commands = "print y\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "Undefined variable: y" in dbg_out

    def test_print_no_arg(self) -> None:
        """Print with no argument shows usage."""
        source = "print(1)"
        commands = "print\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "Usage: print <variable>" in dbg_out

    def test_locals_shows_all(self) -> None:
        """Locals shows all variables in the current frame."""
        source = "let x = 1\nlet y = 2\nprint(x)"
        commands = "s\ns\nlocals\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "x = 1" in dbg_out
        assert "y = 2" in dbg_out

    def test_closure_cells_visible(self) -> None:
        """Closure cells appear in locals with (cell) marker."""
        source = (
            "fn make() {\n"
            "  let x = 10\n"
            "  fn inner() { print(x) }\n"
            "  return inner\n"
            "}\n"
            "let f = make()\n"
            "f()"
        )
        # Step into make, past let x = 10, then check locals
        commands = "s\ns\ns\nlocals\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "(cell)" in dbg_out


# ---------------------------------------------------------------------------
# Cycle 7 — Stack inspection
# ---------------------------------------------------------------------------


class TestStackInspection:
    """Verify stack command."""

    def test_stack_shows_values(self) -> None:
        """Stack shows operand stack with TOS first."""
        source = "let x = 1 + 2"
        # Step with istep to get values on the stack
        commands = "n\nn\nstack\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "TOS" in dbg_out

    def test_stack_empty(self) -> None:
        """Stack on empty stack shows message."""
        source = "let x = 1"
        commands = "stack\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "Stack is empty" in dbg_out


# ---------------------------------------------------------------------------
# Cycle 8 — Backtrace
# ---------------------------------------------------------------------------


class TestBacktrace:
    """Verify backtrace command."""

    def test_backtrace_main(self) -> None:
        """Backtrace in main shows <main>."""
        source = "print(1)"
        commands = "bt\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "<main>" in dbg_out

    def test_backtrace_in_function(self) -> None:
        """Backtrace inside a function shows both the function and <main>."""
        source = "fn greet() {\n  print(1)\n}\ngreet()"
        # Step into greet, then backtrace
        commands = "s\ns\nbt\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "greet" in dbg_out
        assert "<main>" in dbg_out


# ---------------------------------------------------------------------------
# Cycle 9 — Source listing
# ---------------------------------------------------------------------------


class TestSourceListing:
    """Verify list command."""

    def test_list_shows_surrounding_lines(self) -> None:
        """Listing shows source around current line with --> marker."""
        source = "let a = 1\nlet b = 2\nlet c = 3\nlet d = 4\nprint(a + b + c + d)"
        commands = "s\ns\nlist\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "-->" in dbg_out

    def test_list_at_line_one(self) -> None:
        """Listing at line 1 does not crash."""
        source = "print(1)"
        commands = "list\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "-->" in dbg_out


# ---------------------------------------------------------------------------
# Cycle 10 — Help and quit
# ---------------------------------------------------------------------------


class TestHelpAndQuit:
    """Verify help and quit commands."""

    def test_help_lists_commands(self) -> None:
        """Help shows all available commands."""
        source = "print(1)"
        commands = "help\nquit\n"
        dbg_out, _ = debug_run_source(source, commands)
        assert "step" in dbg_out
        assert "istep" in dbg_out
        assert "continue" in dbg_out
        assert "break" in dbg_out
        assert "print" in dbg_out
        assert "locals" in dbg_out
        assert "stack" in dbg_out
        assert "backtrace" in dbg_out
        assert "list" in dbg_out
        assert "quit" in dbg_out

    def test_quit_aborts(self) -> None:
        """Quit stops execution without running the program."""
        source = "print(1)\nprint(2)\nprint(3)"
        commands = "quit\n"
        _, prog_out = debug_run_source(source, commands)
        assert prog_out == ""


# ---------------------------------------------------------------------------
# Cycle 11 — CLI integration
# ---------------------------------------------------------------------------


class TestCLI:
    """Verify argparse integration in cli.py."""

    def test_debug_flag_parsed(self) -> None:
        """The --debug flag sets debug=True in parsed args."""
        args = _parse_args(["--debug", "file.pbl"])
        assert args.debug is True
        assert args.file == "file.pbl"

    def test_no_debug_flag(self) -> None:
        """Without --debug, debug defaults to False."""
        args = _parse_args(["file.pbl"])
        assert args.debug is False

    def test_no_args_file_is_none(self) -> None:
        """No arguments means file is None (REPL mode)."""
        args = _parse_args([])
        assert args.file is None
        assert args.debug is False
