"""Tests for float literals and float type support."""

import pytest

from pebble.ast_nodes import FloatLiteral
from pebble.builtins import format_value
from pebble.errors import PebbleRuntimeError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.tokens import TokenKind
from tests.conftest import (  # pyright: ignore[reportMissingImports]
    run_source,  # pyright: ignore[reportUnknownVariableType]
)

# -- Named constants ----------------------------------------------------------

FLOAT_3_14 = 3.14
FLOAT_0_5 = 0.5
FLOAT_1_0 = 1.0
FLOAT_42_0 = 42.0


# -- Lexer: float tokens ------------------------------------------------------


class TestFloatLexer:
    """Verify the lexer produces FLOAT tokens for decimal literals."""

    def test_simple_float(self) -> None:
        """Verify ``3.14`` produces a FLOAT token."""
        tokens = Lexer("3.14").tokenize()
        assert tokens[0].kind == TokenKind.FLOAT
        assert tokens[0].value == "3.14"

    def test_zero_point_five(self) -> None:
        """Verify ``0.5`` produces a FLOAT token."""
        tokens = Lexer("0.5").tokenize()
        assert tokens[0].kind == TokenKind.FLOAT
        assert tokens[0].value == "0.5"

    def test_one_point_zero(self) -> None:
        """Verify ``1.0`` produces a FLOAT token."""
        tokens = Lexer("1.0").tokenize()
        assert tokens[0].kind == TokenKind.FLOAT
        assert tokens[0].value == "1.0"

    def test_integer_still_integer(self) -> None:
        """Verify ``42`` still produces an INTEGER token."""
        tokens = Lexer("42").tokenize()
        assert tokens[0].kind == TokenKind.INTEGER

    def test_float_followed_by_dot_method(self) -> None:
        """Verify ``42`` followed by ``.foo`` remains INTEGER + DOT."""
        tokens = Lexer("42.foo").tokenize()
        # 42 is INTEGER, .foo would be DOT + IDENTIFIER
        assert tokens[0].kind == TokenKind.INTEGER
        assert tokens[0].value == "42"

    def test_multiple_digit_float(self) -> None:
        """Verify ``123.456`` produces a FLOAT token."""
        tokens = Lexer("123.456").tokenize()
        assert tokens[0].kind == TokenKind.FLOAT
        assert tokens[0].value == "123.456"


# -- Parser: FloatLiteral node ------------------------------------------------


class TestFloatParser:
    """Verify the parser builds FloatLiteral AST nodes."""

    def test_float_literal_node(self) -> None:
        """Verify ``3.14`` parses to a FloatLiteral with value 3.14."""
        tokens = Lexer("3.14").tokenize()
        node = Parser(tokens).parse_expression()
        assert isinstance(node, FloatLiteral)
        assert node.value == FLOAT_3_14

    def test_float_in_expression(self) -> None:
        """Verify floats parse correctly in expressions."""
        tokens = Lexer("1.0").tokenize()
        node = Parser(tokens).parse_expression()
        assert isinstance(node, FloatLiteral)
        assert node.value == FLOAT_1_0


# -- VM: float execution ------------------------------------------------------


class TestFloatExecution:
    """Verify float values execute correctly through the full pipeline."""

    def test_print_float(self) -> None:
        """Verify ``print(3.14)`` outputs ``3.14``."""
        assert run_source("print(3.14)") == "3.14\n"

    def test_print_one_point_zero(self) -> None:
        """Verify ``print(1.0)`` outputs ``1.0`` (not ``1``)."""
        assert run_source("print(1.0)") == "1.0\n"

    def test_float_in_variable(self) -> None:
        """Verify floats can be stored and retrieved."""
        assert run_source("let x = 0.5\nprint(x)") == "0.5\n"


# -- Builtins: float support ---------------------------------------------------


class TestFloatBuiltins:
    """Verify builtins handle float values."""

    def test_type_of_float(self) -> None:
        """Verify ``type(3.14)`` returns ``"float"``."""
        assert run_source("print(type(3.14))") == "float\n"

    def test_format_value_float(self) -> None:
        """Verify format_value produces correct float strings."""
        assert format_value(FLOAT_3_14) == "3.14"
        assert format_value(FLOAT_1_0) == "1.0"

    def test_str_of_float(self) -> None:
        """Verify ``str(3.14)`` returns ``"3.14"``."""
        assert run_source("print(str(3.14))") == "3.14\n"

    def test_float_in_string_interpolation(self) -> None:
        """Verify floats work in string interpolation."""
        assert run_source('print("pi is {3.14}")') == "pi is 3.14\n"

    def test_float_builtin_from_int(self) -> None:
        """Verify ``float(42)`` returns ``42.0``."""
        assert run_source("print(float(42))") == "42.0\n"

    def test_float_builtin_from_string(self) -> None:
        """Verify ``float("3.14")`` returns ``3.14``."""
        assert run_source('print(float("3.14"))') == "3.14\n"

    def test_float_builtin_from_float(self) -> None:
        """Verify ``float(1.5)`` returns ``1.5`` (identity)."""
        assert run_source("print(float(1.5))") == "1.5\n"

    def test_float_builtin_invalid_string(self) -> None:
        """Verify ``float("abc")`` raises a runtime error."""
        with pytest.raises(PebbleRuntimeError, match="Cannot convert"):
            run_source('float("abc")')

    def test_float_builtin_from_bool_rejected(self) -> None:
        """Verify ``float(true)`` raises a runtime error."""
        with pytest.raises(PebbleRuntimeError, match="Cannot convert"):
            run_source("float(true)")

    def test_int_builtin_truncates_float(self) -> None:
        """Verify ``int(3.7)`` returns ``3`` (truncation)."""
        assert run_source("print(int(3.7))") == "3\n"

    def test_int_builtin_truncates_negative_float(self) -> None:
        """Verify ``int(-2.9)`` returns ``-2`` (truncation toward zero)."""
        assert run_source("print(int(-2.9))") == "-2\n"


# -- Mixed arithmetic ---------------------------------------------------------


class TestMixedArithmetic:
    """Verify mixed int/float arithmetic produces float results."""

    def test_int_plus_float(self) -> None:
        """Verify ``1 + 2.0`` produces ``3.0``."""
        assert run_source("print(1 + 2.0)") == "3.0\n"

    def test_float_plus_int(self) -> None:
        """Verify ``2.0 + 1`` produces ``3.0``."""
        assert run_source("print(2.0 + 1)") == "3.0\n"

    def test_float_plus_float(self) -> None:
        """Verify ``1.5 + 2.5`` produces ``4.0``."""
        assert run_source("print(1.5 + 2.5)") == "4.0\n"

    def test_float_times_int(self) -> None:
        """Verify ``3.0 * 2`` produces ``6.0``."""
        assert run_source("print(3.0 * 2)") == "6.0\n"

    def test_float_minus_int(self) -> None:
        """Verify ``5.5 - 2`` produces ``3.5``."""
        assert run_source("print(5.5 - 2)") == "3.5\n"

    def test_float_modulo(self) -> None:
        """Verify ``7.5 % 2`` produces ``1.5``."""
        assert run_source("print(7.5 % 2)") == "1.5\n"

    def test_negate_float(self) -> None:
        """Verify ``-3.14`` produces ``-3.14``."""
        assert run_source("print(-3.14)") == "-3.14\n"


# -- True division and floor division -----------------------------------------


class TestDivision:
    """Verify ``/`` is true division and ``//`` is floor division."""

    def test_true_division_int_int(self) -> None:
        """Verify ``7 / 2`` produces ``3.5`` (true division)."""
        assert run_source("print(7 / 2)") == "3.5\n"

    def test_true_division_exact(self) -> None:
        """Verify ``6 / 2`` produces ``3.0`` (always float)."""
        assert run_source("print(6 / 2)") == "3.0\n"

    def test_true_division_float_int(self) -> None:
        """Verify ``7.0 / 2`` produces ``3.5``."""
        assert run_source("print(7.0 / 2)") == "3.5\n"

    def test_floor_division_int_int(self) -> None:
        """Verify ``7 // 2`` produces ``3`` (integer result)."""
        assert run_source("print(7 // 2)") == "3\n"

    def test_floor_division_float_int(self) -> None:
        """Verify ``7.0 // 2`` produces ``3.0`` (float result)."""
        assert run_source("print(7.0 // 2)") == "3.0\n"

    def test_floor_division_int_float(self) -> None:
        """Verify ``7 // 2.0`` produces ``3.0`` (float result)."""
        assert run_source("print(7 // 2.0)") == "3.0\n"

    def test_true_division_by_zero(self) -> None:
        """Verify ``1 / 0`` raises a division-by-zero error."""
        with pytest.raises(PebbleRuntimeError, match="Division by zero"):
            run_source("print(1 / 0)")

    def test_floor_division_by_zero(self) -> None:
        """Verify ``1 // 0`` raises a division-by-zero error."""
        with pytest.raises(PebbleRuntimeError, match="Division by zero"):
            run_source("print(1 // 0)")


# -- Comparison: mixed int/float ----------------------------------------------


class TestMixedComparison:
    """Verify comparison operators work with mixed int/float."""

    def test_int_less_than_float(self) -> None:
        """Verify ``3 < 3.5`` produces true."""
        assert run_source("print(3 < 3.5)") == "true\n"

    def test_float_equals_int(self) -> None:
        """Verify ``3.0 == 3`` produces true."""
        assert run_source("print(3.0 == 3)") == "true\n"

    def test_float_greater_than_int(self) -> None:
        """Verify ``3.5 > 3`` produces true."""
        assert run_source("print(3.5 > 3)") == "true\n"

    def test_float_less_equal_int(self) -> None:
        """Verify ``3.0 <= 3`` produces true."""
        assert run_source("print(3.0 <= 3)") == "true\n"

    def test_float_greater_equal_int(self) -> None:
        """Verify ``3.0 >= 3`` produces true."""
        assert run_source("print(3.0 >= 3)") == "true\n"

    def test_float_not_equal_int(self) -> None:
        """Verify ``3.5 != 3`` produces true."""
        assert run_source("print(3.5 != 3)") == "true\n"
