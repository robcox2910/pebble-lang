"""Unified error reporting for the Pebble compiler.

Every compiler phase (lexer, parser, semantic analyser, VM) raises a
specialised subclass of :class:`PebbleError`.  The :func:`format_error`
helper produces human-friendly output with the offending source line and
a caret pointing to the exact column.  :class:`ErrorCollector` lets
multiple errors be gathered and reported together.
"""

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class TraceEntry:
    """One frame in a Pebble traceback.

    Attributes:
        function_name: The function (or ``<main>``) where execution was.
        line: 1-based source line of the call site.
        column: 1-based source column of the call site.

    """

    function_name: str
    line: int
    column: int


class PebbleError(Exception):
    """Base class for all Pebble compiler and runtime errors.

    Attributes:
        message: Human-readable description of the error.
        line: 1-based line number where the error occurred.
        column: 1-based column number where the error occurred.

    """

    def __init__(self, message: str, *, line: int, column: int) -> None:
        """Create a PebbleError with location information."""
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"{message} at line {line}, column {column}")


class LexerError(PebbleError):
    """Raise when the lexer encounters invalid input."""


class ParseError(PebbleError):
    """Raise when the parser encounters a syntax error."""


class SemanticError(PebbleError):
    """Raise when the semantic analyser detects a logic error."""


class PebbleRuntimeError(PebbleError):
    """Raise when the virtual machine encounters an execution error."""

    def __init__(
        self,
        message: str,
        *,
        line: int,
        column: int,
        traceback: list[TraceEntry] | None = None,
    ) -> None:
        """Create a runtime error with optional traceback."""
        self.traceback: list[TraceEntry] = traceback if traceback is not None else []
        super().__init__(message, line=line, column=column)


class PebbleImportError(PebbleError):
    """Raise when an import fails (file not found, circular, name missing)."""


# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------


def format_error(source: str, *, line: int, column: int, message: str) -> str:
    """Format an error with the offending source line and a caret underline.

    Args:
        source: The full source text.
        line: 1-based line where the error occurred.
        column: 1-based column where the error occurred.
        message: Human-readable description of the error.

    Returns:
        A multi-line string showing the line number, source line, caret, and
        message.

    """
    source_lines = source.split("\n") if source else []
    if line < 1 or line > len(source_lines):
        return message
    source_line = source_lines[line - 1]

    prefix = f"{line} | "
    caret = " " * (len(prefix) + max(column, 1) - 1) + "^"

    return f"{prefix}{source_line}\n{caret}\n{message}"


def format_traceback(error: PebbleRuntimeError) -> str:
    """Format a runtime error with its traceback in Python-style.

    If the error has a non-empty traceback, produce::

        Traceback (most recent call last):
          line 8, in <main>
          line 4, in outer
        Error: Division by zero at line 2, column 5

    If the traceback is empty but the error has a valid line, return::

        Error: <message> at line <L>, column <C>

    If line is 0, return just ``Error: <message>``.
    """
    error_line = (
        f"Error: {error.message} at line {error.line}, column {error.column}"
        if error.line > 0
        else f"Error: {error.message}"
    )
    if not error.traceback:
        return error_line
    lines = [
        "Traceback (most recent call last):",
        *[f"  line {entry.line}, in {entry.function_name}" for entry in error.traceback],
        error_line,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Error collector
# ---------------------------------------------------------------------------


class ErrorCollector:
    """Accumulate multiple errors for batch reporting."""

    def __init__(self) -> None:
        """Create an empty error collector."""
        self._errors: list[PebbleError] = []

    # -- Mutation -------------------------------------------------------------

    def add(self, error: PebbleError) -> None:
        """Add an error to the collector."""
        self._errors.append(error)

    def clear(self) -> None:
        """Remove all collected errors."""
        self._errors.clear()

    # -- Query ----------------------------------------------------------------

    @property
    def has_errors(self) -> bool:
        """Return True if at least one error has been collected."""
        return len(self._errors) > 0

    @property
    def errors(self) -> list[PebbleError]:
        """Return a copy of the collected errors."""
        return list(self._errors)

    def format_all(self, source: str) -> str:
        """Format every collected error against *source*.

        Each error is separated by a blank line.
        """
        parts = [
            format_error(source, line=e.line, column=e.column, message=e.message)
            for e in self._errors
        ]
        return "\n\n".join(parts)

    # -- Dunder protocols -----------------------------------------------------

    def __len__(self) -> int:
        """Return the number of collected errors."""
        return len(self._errors)

    def __iter__(self) -> Iterator[PebbleError]:
        """Iterate over collected errors in insertion order."""
        return iter(list(self._errors))
