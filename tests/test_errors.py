"""Tests for the Pebble error reporting system."""

import pytest

from pebble.errors import (
    ErrorCollector,
    LexerError,
    ParseError,
    PebbleError,
    PebbleRuntimeError,
    SemanticError,
    format_error,
)

# -- Named constants ----------------------------------------------------------

FIRST_LINE = 1
SECOND_LINE = 2
THIRD_LINE = 3
FIRST_COLUMN = 1
FIFTH_COLUMN = 5
NINTH_COLUMN = 9
ZERO_ERRORS = 0
ONE_ERROR = 1
TWO_ERRORS = 2
THREE_ERRORS = 3


class TestPebbleError:
    """Verify the PebbleError base class."""

    def test_is_exception(self) -> None:
        """Verify PebbleError is an Exception subclass."""
        assert issubclass(PebbleError, Exception)

    def test_stores_message(self) -> None:
        """Verify PebbleError stores the error message."""
        err = PebbleError("something broke", line=FIRST_LINE, column=FIRST_COLUMN)
        assert err.message == "something broke"

    def test_stores_line(self) -> None:
        """Verify PebbleError stores the line number."""
        err = PebbleError("oops", line=SECOND_LINE, column=FIRST_COLUMN)
        assert err.line == SECOND_LINE

    def test_stores_column(self) -> None:
        """Verify PebbleError stores the column number."""
        err = PebbleError("oops", line=FIRST_LINE, column=FIFTH_COLUMN)
        assert err.column == FIFTH_COLUMN

    def test_str_includes_location(self) -> None:
        """Verify str(PebbleError) includes line and column."""
        err = PebbleError("bad thing", line=THIRD_LINE, column=FIFTH_COLUMN)
        text = str(err)
        assert "bad thing" in text
        assert "line 3" in text
        assert "column 5" in text


class TestErrorSubclasses:
    """Verify the specialized error subclasses."""

    def test_lexer_error_is_pebble_error(self) -> None:
        """Verify LexerError is a PebbleError subclass."""
        assert issubclass(LexerError, PebbleError)

    def test_parse_error_is_pebble_error(self) -> None:
        """Verify ParseError is a PebbleError subclass."""
        assert issubclass(ParseError, PebbleError)

    def test_semantic_error_is_pebble_error(self) -> None:
        """Verify SemanticError is a PebbleError subclass."""
        assert issubclass(SemanticError, PebbleError)

    def test_runtime_error_is_pebble_error(self) -> None:
        """Verify PebbleRuntimeError is a PebbleError subclass."""
        assert issubclass(PebbleRuntimeError, PebbleError)

    def test_lexer_error_attributes(self) -> None:
        """Verify LexerError carries message, line, and column."""
        err = LexerError("unterminated string", line=FIRST_LINE, column=FIFTH_COLUMN)
        assert err.message == "unterminated string"
        assert err.line == FIRST_LINE
        assert err.column == FIFTH_COLUMN

    def test_parse_error_attributes(self) -> None:
        """Verify ParseError carries message, line, and column."""
        err = ParseError("expected ')'", line=SECOND_LINE, column=NINTH_COLUMN)
        assert err.message == "expected ')'"
        assert err.line == SECOND_LINE
        assert err.column == NINTH_COLUMN

    def test_semantic_error_attributes(self) -> None:
        """Verify SemanticError carries message, line, and column."""
        err = SemanticError("undeclared variable 'x'", line=THIRD_LINE, column=FIRST_COLUMN)
        assert err.message == "undeclared variable 'x'"
        assert err.line == THIRD_LINE

    def test_runtime_error_attributes(self) -> None:
        """Verify PebbleRuntimeError carries message, line, and column."""
        err = PebbleRuntimeError("division by zero", line=FIRST_LINE, column=FIRST_COLUMN)
        assert err.message == "division by zero"

    def test_all_subclasses_are_catchable_as_pebble_error(self) -> None:
        """Verify all subclasses can be caught as PebbleError."""
        errors: list[PebbleError] = [
            LexerError("a", line=FIRST_LINE, column=FIRST_COLUMN),
            ParseError("b", line=FIRST_LINE, column=FIRST_COLUMN),
            SemanticError("c", line=FIRST_LINE, column=FIRST_COLUMN),
            PebbleRuntimeError("d", line=FIRST_LINE, column=FIRST_COLUMN),
        ]
        for err in errors:
            with pytest.raises(PebbleError):
                raise err


class TestFormatError:
    """Verify the format_error() function that shows source with caret."""

    def test_single_line_source(self) -> None:
        """Verify format_error points to the right column on a single line."""
        source = "let x = @"
        result = format_error(source, line=FIRST_LINE, column=NINTH_COLUMN, message="bad char")
        # Should contain the source line, a caret line, and the message
        assert "let x = @" in result
        assert "^" in result
        assert "bad char" in result

    def test_caret_position(self) -> None:
        """Verify the caret accounts for the line-number prefix."""
        source = "let x = @"
        result = format_error(source, line=FIRST_LINE, column=NINTH_COLUMN, message="bad")
        lines = result.split("\n")
        # Find the caret line
        caret_line = next(ln for ln in lines if "^" in ln)
        caret_col = caret_line.index("^")
        # Prefix is "1 | " (4 chars), then column 9 → 0-based offset 8
        prefix_len = len(f"{FIRST_LINE} | ")
        expected_col = prefix_len + NINTH_COLUMN - 1
        assert caret_col == expected_col

    def test_multiline_source_points_to_correct_line(self) -> None:
        """Verify format_error shows the correct line in multi-line source."""
        source = "let x = 1\nlet y = @\nlet z = 3"
        result = format_error(source, line=SECOND_LINE, column=NINTH_COLUMN, message="oops")
        assert "let y = @" in result
        # Should NOT show the other lines
        assert "let x = 1" not in result
        assert "let z = 3" not in result

    def test_includes_line_number(self) -> None:
        """Verify format_error includes the line number in output."""
        source = "hello\nworld"
        result = format_error(source, line=SECOND_LINE, column=FIRST_COLUMN, message="err")
        assert "2" in result

    def test_empty_source_does_not_crash(self) -> None:
        """Verify format_error handles empty source gracefully."""
        result = format_error("", line=FIRST_LINE, column=FIRST_COLUMN, message="eof")
        assert "eof" in result

    def test_column_one_caret(self) -> None:
        """Verify caret at column 1 aligns under the first character."""
        source = "x"
        result = format_error(source, line=FIRST_LINE, column=FIRST_COLUMN, message="bad")
        lines = result.split("\n")
        caret_line = next(ln for ln in lines if "^" in ln)
        prefix_len = len(f"{FIRST_LINE} | ")
        assert caret_line.index("^") == prefix_len


class TestErrorCollector:
    """Verify the ErrorCollector that accumulates multiple errors."""

    def test_starts_empty(self) -> None:
        """Verify a new ErrorCollector has no errors."""
        collector = ErrorCollector()
        assert len(collector) == ZERO_ERRORS

    def test_has_errors_false_when_empty(self) -> None:
        """Verify has_errors is False when no errors have been added."""
        collector = ErrorCollector()
        assert not collector.has_errors

    def test_add_error(self) -> None:
        """Verify an error can be added to the collector."""
        collector = ErrorCollector()
        collector.add(LexerError("oops", line=FIRST_LINE, column=FIRST_COLUMN))
        assert len(collector) == ONE_ERROR

    def test_has_errors_true_after_add(self) -> None:
        """Verify has_errors is True after adding an error."""
        collector = ErrorCollector()
        collector.add(ParseError("bad", line=FIRST_LINE, column=FIRST_COLUMN))
        assert collector.has_errors

    def test_multiple_errors(self) -> None:
        """Verify multiple errors can be collected."""
        collector = ErrorCollector()
        collector.add(LexerError("a", line=FIRST_LINE, column=FIRST_COLUMN))
        collector.add(ParseError("b", line=SECOND_LINE, column=FIRST_COLUMN))
        collector.add(SemanticError("c", line=THIRD_LINE, column=FIRST_COLUMN))
        assert len(collector) == THREE_ERRORS

    def test_errors_property_returns_list(self) -> None:
        """Verify the errors property returns a list of PebbleError."""
        collector = ErrorCollector()
        err = LexerError("oops", line=FIRST_LINE, column=FIRST_COLUMN)
        collector.add(err)
        assert collector.errors == [err]

    def test_errors_property_is_copy(self) -> None:
        """Verify the errors property returns a copy, not the internal list."""
        collector = ErrorCollector()
        collector.add(LexerError("a", line=FIRST_LINE, column=FIRST_COLUMN))
        errors = collector.errors
        errors.clear()
        assert len(collector) == ONE_ERROR

    def test_iterate_over_collector(self) -> None:
        """Verify the collector is iterable."""
        collector = ErrorCollector()
        err1 = LexerError("a", line=FIRST_LINE, column=FIRST_COLUMN)
        err2 = ParseError("b", line=SECOND_LINE, column=FIRST_COLUMN)
        collector.add(err1)
        collector.add(err2)
        assert list(collector) == [err1, err2]

    def test_format_all_with_source(self) -> None:
        """Verify format_all produces formatted output for each error."""
        collector = ErrorCollector()
        collector.add(LexerError("bad char", line=FIRST_LINE, column=FIFTH_COLUMN))
        collector.add(ParseError("expected )", line=SECOND_LINE, column=FIRST_COLUMN))
        source = "let @= 5\n(unclosed"
        result = collector.format_all(source)
        assert "bad char" in result
        assert "expected )" in result

    def test_clear_removes_all_errors(self) -> None:
        """Verify clear() empties the collector."""
        collector = ErrorCollector()
        collector.add(LexerError("a", line=FIRST_LINE, column=FIRST_COLUMN))
        collector.add(ParseError("b", line=SECOND_LINE, column=FIRST_COLUMN))
        collector.clear()
        assert len(collector) == ZERO_ERRORS
        assert not collector.has_errors
