"""Unified error reporting for the Pebble compiler.

Every compiler phase (lexer, parser, semantic analyser, VM) raises a
specialised subclass of :class:`PebbleError`.  The :func:`format_error`
helper produces human-friendly output with the offending source line and
a caret pointing to the exact column.  :class:`ErrorCollector` lets
multiple errors be gathered and reported together.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


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
    source_line = source_lines[line - 1] if line <= len(source_lines) else ""

    caret = " " * (column - 1) + "^"

    return f"{line} | {source_line}\n{caret}\n{message}"


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
