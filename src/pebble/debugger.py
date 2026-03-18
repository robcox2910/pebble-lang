"""Interactive bytecode debugger for the Pebble language.

Attach to the VM execution loop via the :class:`DebugHook` protocol.
The debugger lets learners step through source lines or individual
bytecode instructions, set breakpoints, and inspect variables, the
operand stack, and the call stack.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TextIO

from pebble.builtins import Value, format_value
from pebble.bytecode import CodeObject, Instruction
from pebble.vm import DebugAction, Frame


class DebuggerCommand(StrEnum):
    """Every command the debugger understands."""

    STEP = "step"
    ISTEP = "istep"
    CONTINUE = "continue"
    BREAK = "break"
    CLEAR = "clear"
    PRINT = "print"
    STACK = "stack"
    BACKTRACE = "backtrace"
    LOCALS = "locals"
    LIST = "list"
    HELP = "help"
    QUIT = "quit"


_ALIASES: dict[str, DebuggerCommand] = {
    "s": DebuggerCommand.STEP,
    "n": DebuggerCommand.ISTEP,
    "c": DebuggerCommand.CONTINUE,
    "b": DebuggerCommand.BREAK,
    "p": DebuggerCommand.PRINT,
    "bt": DebuggerCommand.BACKTRACE,
    "l": DebuggerCommand.LIST,
    "h": DebuggerCommand.HELP,
    "q": DebuggerCommand.QUIT,
}

_CONTEXT_LINES = 3


@dataclass
class Debugger:
    """Interactive debugger implementing the :class:`DebugHook` protocol.

    Attributes:
        source: The original source text (for display).
        output: Stream where debugger output is written.
        input_stream: Stream where debugger commands are read from.

    """

    source: str
    output: TextIO
    input_stream: TextIO
    _breakpoints: set[int] = field(default_factory=lambda: set[int]())
    _stepping: bool = field(default=True)
    _istep_mode: bool = field(default=False)
    _last_line: int = field(default=0)

    # -- DebugHook protocol ---------------------------------------------------

    def on_instruction(
        self,
        instruction: Instruction,
        ip: int,  # noqa: ARG002
        code: CodeObject,  # noqa: ARG002
        stack: list[Value],
        frames: list[Frame],
    ) -> DebugAction:
        """Pause when a step/breakpoint triggers; prompt for commands."""
        if not self._should_stop(instruction):
            return DebugAction.CONTINUE

        self._show_location(instruction)
        return self._command_loop(instruction, stack, frames)

    # -- Stopping logic -------------------------------------------------------

    def _should_stop(self, instruction: Instruction) -> bool:
        """Return True if the debugger should pause before *instruction*."""
        line = instruction.location.line if instruction.location else 0

        # Instruction-level stepping — always stop
        if self._stepping and self._istep_mode:
            self._last_line = line
            return True

        # Source-line stepping — stop when line changes
        if self._stepping and line != self._last_line:
            self._last_line = line
            return True

        # Breakpoint hit
        if line in self._breakpoints and line != self._last_line:
            self._last_line = line
            return True

        return False

    # -- Display helpers ------------------------------------------------------

    def _show_location(self, instruction: Instruction) -> None:
        """Print the current source line and instruction."""
        line = instruction.location.line if instruction.location else 0
        lines = self.source.splitlines()
        if 0 < line <= len(lines):
            self.output.write(f"  {line}: {lines[line - 1]}\n")
        if self._istep_mode:
            operand = f" {instruction.operand}" if instruction.operand is not None else ""
            self.output.write(f"       {instruction.opcode}{operand}\n")

    # -- Command loop ---------------------------------------------------------

    def _command_loop(
        self,
        instruction: Instruction,
        stack: list[Value],
        frames: list[Frame],
    ) -> DebugAction:
        """Read and dispatch commands until one resumes execution."""
        while True:
            result = self._read_command()
            if result is None:
                return DebugAction.QUIT

            cmd, arg = result

            # Execution commands — return an action
            action = self._dispatch_execution(cmd)
            if action is not None:
                return action

            # Inspection commands — stay in loop
            self._dispatch_inspection(cmd, arg, instruction, stack, frames)

    def _dispatch_execution(self, cmd: DebuggerCommand) -> DebugAction | None:
        """Handle commands that resume or quit execution.

        Return a :class:`DebugAction` if the command resumes execution,
        or ``None`` if it should be handled as an inspection command.
        """
        match cmd:
            case DebuggerCommand.STEP:
                self._stepping = True
                self._istep_mode = False
                return DebugAction.CONTINUE
            case DebuggerCommand.ISTEP:
                self._stepping = True
                self._istep_mode = True
                return DebugAction.CONTINUE
            case DebuggerCommand.CONTINUE:
                self._stepping = False
                return DebugAction.CONTINUE
            case DebuggerCommand.QUIT:
                return DebugAction.QUIT
            case _:
                return None

    def _dispatch_inspection(
        self,
        cmd: DebuggerCommand,
        arg: str,
        instruction: Instruction,
        stack: list[Value],
        frames: list[Frame],
    ) -> None:
        """Handle commands that inspect state without resuming execution."""
        match cmd:
            case DebuggerCommand.BREAK:
                self._cmd_break(arg)
            case DebuggerCommand.CLEAR:
                self._cmd_clear(arg)
            case DebuggerCommand.PRINT:
                self._cmd_print(arg, frames)
            case DebuggerCommand.LOCALS:
                self._cmd_locals(frames)
            case DebuggerCommand.STACK:
                self._cmd_stack(stack)
            case DebuggerCommand.BACKTRACE:
                self._cmd_backtrace(frames)
            case DebuggerCommand.LIST:
                self._cmd_list(instruction)
            case DebuggerCommand.HELP:
                self._cmd_help()
            case _:  # pragma: no cover
                pass

    def _read_command(self) -> tuple[DebuggerCommand, str] | None:
        """Read one command from the input stream.

        Return ``(command, arg)`` or ``None`` on EOF.
        """
        while True:
            self.output.write("(pdb) ")
            line = self.input_stream.readline()
            if not line:
                return None
            raw = line.strip()
            if not raw:
                continue
            parts = raw.split(maxsplit=1)
            word = parts[0]
            arg = parts[1] if len(parts) > 1 else ""

            # Resolve alias
            if word in _ALIASES:
                return _ALIASES[word], arg

            # Resolve full name
            try:
                return DebuggerCommand(word), arg
            except ValueError:
                self.output.write(f"Unknown command: {word}\n")

    # -- Command handlers -----------------------------------------------------

    def _cmd_break(self, arg: str) -> None:
        """Set a breakpoint at the given line number."""
        if not arg:
            if self._breakpoints:
                lines = sorted(self._breakpoints)
                self.output.write(f"Breakpoints: {lines}\n")
            else:
                self.output.write("No breakpoints set.\n")
            return
        try:
            line_no = int(arg)
        except ValueError:
            self.output.write(f"Invalid line number: {arg}\n")
            return
        total_lines = len(self.source.splitlines())
        if line_no < 1 or line_no > total_lines:
            self.output.write(f"Line {line_no} out of range (1-{total_lines}).\n")
            return
        self._breakpoints.add(line_no)
        self.output.write(f"Breakpoint set at line {line_no}.\n")

    def _cmd_clear(self, arg: str) -> None:
        """Remove a breakpoint at the given line number."""
        if not arg:
            self.output.write("Usage: clear <line>\n")
            return
        try:
            line_no = int(arg)
        except ValueError:
            self.output.write(f"Invalid line number: {arg}\n")
            return
        if line_no in self._breakpoints:
            self._breakpoints.discard(line_no)
            self.output.write(f"Breakpoint at line {line_no} cleared.\n")
        else:
            self.output.write(f"No breakpoint at line {line_no}.\n")

    def _cmd_print(self, arg: str, frames: list[Frame]) -> None:
        """Print the value of a variable."""
        if not arg:
            self.output.write("Usage: print <variable>\n")
            return
        value = self._lookup_variable(arg, frames)
        if value is _SENTINEL:
            self.output.write(f"Undefined variable: {arg}\n")
            return
        self.output.write(f"{arg} = {format_value(value)}\n")

    def _cmd_locals(self, frames: list[Frame]) -> None:
        """Print all local variables and closure cells."""
        if not frames:
            self.output.write("No active frame.\n")
            return
        frame = frames[-1]
        if not frame.variables and not frame.cells:
            self.output.write("No locals.\n")
            return
        for name, value in sorted(frame.variables.items()):
            self.output.write(f"  {name} = {format_value(value)}\n")
        for name, cell in sorted(frame.cells.items()):
            self.output.write(f"  {name} = {format_value(cell.value)} (cell)\n")

    def _cmd_stack(self, stack: list[Value]) -> None:
        """Print the operand stack (TOS first)."""
        if not stack:
            self.output.write("Stack is empty.\n")
            return
        for i, value in enumerate(reversed(stack)):
            label = "TOS" if i == 0 else f"  {i}"
            self.output.write(f"  {label}: {format_value(value)}\n")

    def _cmd_backtrace(self, frames: list[Frame]) -> None:
        """Print the call stack with line numbers."""
        if not frames:
            self.output.write("No active frames.\n")
            return
        for i, frame in enumerate(reversed(frames)):
            marker = ">" if i == 0 else " "
            line = 0
            if frame.ip > 0:
                instr = frame.code.instructions[frame.ip - 1]
                if instr.location:
                    line = instr.location.line
            line_info = f" (line {line})" if line > 0 else ""
            self.output.write(f"  {marker} {frame.code.name}{line_info}\n")

    def _cmd_list(self, instruction: Instruction) -> None:
        """Show source lines around the current location."""
        line = instruction.location.line if instruction.location else 0
        lines = self.source.splitlines()
        start = max(0, line - 1 - _CONTEXT_LINES)
        end = min(len(lines), line + _CONTEXT_LINES)
        for i in range(start, end):
            marker = "-->" if i + 1 == line else "   "
            self.output.write(f"  {marker} {i + 1}: {lines[i]}\n")

    def _cmd_help(self) -> None:
        """Print a command reference."""
        self.output.write(
            "Commands:\n"
            "  step    (s)  - Step to next source line\n"
            "  istep   (n)  - Step to next bytecode instruction\n"
            "  continue(c)  - Run to next breakpoint\n"
            "  break   (b)  - Set breakpoint: break <line>\n"
            "  clear        - Remove breakpoint: clear <line>\n"
            "  print   (p)  - Print variable: print <name>\n"
            "  locals       - Show all local variables\n"
            "  stack        - Show operand stack\n"
            "  backtrace(bt)- Show call stack\n"
            "  list    (l)  - Show source around current line\n"
            "  help    (h)  - Show this help\n"
            "  quit    (q)  - Abort execution\n"
        )

    # -- Variable lookup ------------------------------------------------------

    def _lookup_variable(self, name: str, frames: list[Frame]) -> Value:
        """Look up *name* in the current frame's locals and cells.

        Return the sentinel if not found.
        """
        if not frames:
            return _SENTINEL
        frame = frames[-1]
        if name in frame.variables:
            return frame.variables[name]
        if name in frame.cells:
            return frame.cells[name].value
        return _SENTINEL


# Sentinel for "variable not found" — distinct from any Pebble value.
_SENTINEL: Value = object()  # type: ignore[assignment]
