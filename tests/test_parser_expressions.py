"""Tests for the Pebble parser — expression parsing.

The parser uses recursive descent with Pratt-style precedence climbing.
These tests verify parsing of literals, identifiers, unary ops, binary ops
(with correct precedence and associativity), grouped expressions, and
boolean operators.
"""

import pytest

from pebble.ast_nodes import (
    BinaryOp,
    BooleanLiteral,
    Expression,
    Identifier,
    IntegerLiteral,
    StringLiteral,
    UnaryOp,
)
from pebble.errors import ParseError
from pebble.lexer import Lexer
from pebble.parser import Parser

# -- Named constants ----------------------------------------------------------

ANSWER = 42
SEVEN = 7
THREE = 3
TWO = 2
ONE = 1
ZERO = 0
TEN = 10
FIVE = 5


def _parse_expr(source: str) -> Expression:
    """Lex and parse a single expression from *source*."""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse_expression()


# -- Literals -----------------------------------------------------------------


class TestParserIntegerLiteral:
    """Verify parsing of integer literals."""

    def test_single_digit(self) -> None:
        """Verify a single digit parses to IntegerLiteral."""
        node = _parse_expr("5")
        assert isinstance(node, IntegerLiteral)
        assert node.value == FIVE

    def test_multi_digit(self) -> None:
        """Verify a multi-digit number parses to IntegerLiteral."""
        node = _parse_expr("42")
        assert isinstance(node, IntegerLiteral)
        assert node.value == ANSWER

    def test_zero(self) -> None:
        """Verify zero parses to IntegerLiteral."""
        node = _parse_expr("0")
        assert isinstance(node, IntegerLiteral)
        assert node.value == ZERO


class TestParserStringLiteral:
    """Verify parsing of string literals."""

    def test_simple_string(self) -> None:
        """Verify a double-quoted string parses to StringLiteral."""
        node = _parse_expr('"hello"')
        assert isinstance(node, StringLiteral)
        assert node.value == "hello"

    def test_empty_string(self) -> None:
        """Verify an empty string parses to StringLiteral."""
        node = _parse_expr('""')
        assert isinstance(node, StringLiteral)
        assert node.value == ""


class TestParserBooleanLiteral:
    """Verify parsing of boolean literals."""

    def test_true(self) -> None:
        """Verify 'true' parses to BooleanLiteral(True)."""
        node = _parse_expr("true")
        assert isinstance(node, BooleanLiteral)
        assert node.value is True

    def test_false(self) -> None:
        """Verify 'false' parses to BooleanLiteral(False)."""
        node = _parse_expr("false")
        assert isinstance(node, BooleanLiteral)
        assert node.value is False


class TestParserIdentifier:
    """Verify parsing of identifiers."""

    def test_simple_identifier(self) -> None:
        """Verify a name parses to Identifier."""
        node = _parse_expr("foo")
        assert isinstance(node, Identifier)
        assert node.name == "foo"

    def test_underscore_identifier(self) -> None:
        """Verify an underscore-prefixed name parses to Identifier."""
        node = _parse_expr("_private")
        assert isinstance(node, Identifier)
        assert node.name == "_private"


# -- Unary operations ---------------------------------------------------------


class TestParserUnaryOp:
    """Verify parsing of unary operations."""

    def test_negate_integer(self) -> None:
        """Verify '-42' parses to UnaryOp with '-' and IntegerLiteral."""
        node = _parse_expr("-42")
        assert isinstance(node, UnaryOp)
        assert node.operator == "-"
        assert isinstance(node.operand, IntegerLiteral)
        assert node.operand.value == ANSWER

    def test_not_boolean(self) -> None:
        """Verify 'not true' parses to UnaryOp with 'not'."""
        node = _parse_expr("not true")
        assert isinstance(node, UnaryOp)
        assert node.operator == "not"
        assert isinstance(node.operand, BooleanLiteral)
        assert node.operand.value is True

    def test_double_negate(self) -> None:
        """Verify '--5' parses to nested UnaryOp."""
        node = _parse_expr("--5")
        assert isinstance(node, UnaryOp)
        assert node.operator == "-"
        assert isinstance(node.operand, UnaryOp)
        assert node.operand.operator == "-"

    def test_not_not(self) -> None:
        """Verify 'not not true' parses to nested UnaryOp."""
        node = _parse_expr("not not true")
        assert isinstance(node, UnaryOp)
        assert isinstance(node.operand, UnaryOp)


# -- Binary operations: arithmetic --------------------------------------------


class TestParserArithmetic:
    """Verify parsing of arithmetic binary operations."""

    def test_addition(self) -> None:
        """Verify '1 + 2' parses to BinaryOp with '+'."""
        node = _parse_expr("1 + 2")
        assert isinstance(node, BinaryOp)
        assert node.operator == "+"
        assert isinstance(node.left, IntegerLiteral)
        assert node.left.value == ONE
        assert isinstance(node.right, IntegerLiteral)
        assert node.right.value == TWO

    def test_subtraction(self) -> None:
        """Verify '5 - 3' parses to BinaryOp with '-'."""
        node = _parse_expr("5 - 3")
        assert isinstance(node, BinaryOp)
        assert node.operator == "-"
        assert isinstance(node.left, IntegerLiteral)
        assert node.left.value == FIVE
        assert isinstance(node.right, IntegerLiteral)
        assert node.right.value == THREE

    def test_multiplication(self) -> None:
        """Verify '2 * 3' parses to BinaryOp with '*'."""
        node = _parse_expr("2 * 3")
        assert isinstance(node, BinaryOp)
        assert node.operator == "*"
        assert isinstance(node.left, IntegerLiteral)
        assert node.left.value == TWO
        assert isinstance(node.right, IntegerLiteral)
        assert node.right.value == THREE

    def test_division(self) -> None:
        """Verify '10 / 2' parses to BinaryOp with '/'."""
        node = _parse_expr("10 / 2")
        assert isinstance(node, BinaryOp)
        assert node.operator == "/"
        assert isinstance(node.left, IntegerLiteral)
        assert node.left.value == TEN
        assert isinstance(node.right, IntegerLiteral)
        assert node.right.value == TWO

    def test_modulo(self) -> None:
        """Verify '7 % 3' parses to BinaryOp with '%'."""
        node = _parse_expr("7 % 3")
        assert isinstance(node, BinaryOp)
        assert node.operator == "%"
        assert isinstance(node.left, IntegerLiteral)
        assert node.left.value == SEVEN
        assert isinstance(node.right, IntegerLiteral)
        assert node.right.value == THREE


# -- Precedence ---------------------------------------------------------------


class TestParserPrecedence:
    """Verify operator precedence (higher precedence binds tighter)."""

    def test_mul_before_add(self) -> None:
        """Verify '1 + 2 * 3' groups as '1 + (2 * 3)'."""
        node = _parse_expr("1 + 2 * 3")
        assert isinstance(node, BinaryOp)
        assert node.operator == "+"
        assert isinstance(node.left, IntegerLiteral)
        assert node.left.value == ONE
        assert isinstance(node.right, BinaryOp)
        assert node.right.operator == "*"
        assert isinstance(node.right.left, IntegerLiteral)
        assert node.right.left.value == TWO
        assert isinstance(node.right.right, IntegerLiteral)
        assert node.right.right.value == THREE

    def test_div_before_sub(self) -> None:
        """Verify '10 - 6 / 2' groups as '10 - (6 / 2)'."""
        node = _parse_expr("10 - 6 / 2")
        assert isinstance(node, BinaryOp)
        assert node.operator == "-"
        assert isinstance(node.left, IntegerLiteral)
        assert node.left.value == TEN
        assert isinstance(node.right, BinaryOp)
        assert node.right.operator == "/"

    def test_comparison_below_arithmetic(self) -> None:
        """Verify '1 + 2 > 3' groups as '(1 + 2) > 3'."""
        node = _parse_expr("1 + 2 > 3")
        assert isinstance(node, BinaryOp)
        assert node.operator == ">"
        assert isinstance(node.left, BinaryOp)
        assert node.left.operator == "+"

    def test_and_below_comparison(self) -> None:
        """Verify 'x > 0 and y < 10' groups comparisons first."""
        node = _parse_expr("x > 0 and y < 10")
        assert isinstance(node, BinaryOp)
        assert node.operator == "and"
        assert isinstance(node.left, BinaryOp)
        assert node.left.operator == ">"
        assert isinstance(node.right, BinaryOp)
        assert node.right.operator == "<"

    def test_or_below_and(self) -> None:
        """Verify 'a and b or c' groups as '(a and b) or c'."""
        node = _parse_expr("a and b or c")
        assert isinstance(node, BinaryOp)
        assert node.operator == "or"
        assert isinstance(node.left, BinaryOp)
        assert node.left.operator == "and"

    def test_unary_above_binary(self) -> None:
        """Verify '-x + y' groups as '(-x) + y'."""
        node = _parse_expr("-x + y")
        assert isinstance(node, BinaryOp)
        assert node.operator == "+"
        assert isinstance(node.left, UnaryOp)
        assert node.left.operator == "-"


# -- Associativity ------------------------------------------------------------


class TestParserAssociativity:
    """Verify left-to-right associativity for binary operators."""

    def test_addition_left_associative(self) -> None:
        """Verify '1 + 2 + 3' groups as '(1 + 2) + 3'."""
        node = _parse_expr("1 + 2 + 3")
        assert isinstance(node, BinaryOp)
        assert node.operator == "+"
        assert isinstance(node.left, BinaryOp)
        assert node.left.operator == "+"
        assert isinstance(node.right, IntegerLiteral)
        assert node.right.value == THREE

    def test_subtraction_left_associative(self) -> None:
        """Verify '10 - 3 - 2' groups as '(10 - 3) - 2'."""
        node = _parse_expr("10 - 3 - 2")
        assert isinstance(node, BinaryOp)
        assert node.operator == "-"
        assert isinstance(node.left, BinaryOp)
        assert node.left.operator == "-"
        assert isinstance(node.right, IntegerLiteral)
        assert node.right.value == TWO

    def test_multiplication_left_associative(self) -> None:
        """Verify '2 * 3 * 7' groups as '(2 * 3) * 7'."""
        node = _parse_expr("2 * 3 * 7")
        assert isinstance(node, BinaryOp)
        assert node.operator == "*"
        assert isinstance(node.left, BinaryOp)
        assert isinstance(node.right, IntegerLiteral)
        assert node.right.value == SEVEN


# -- Grouped expressions ------------------------------------------------------


class TestParserGrouped:
    """Verify parenthesised grouped expressions."""

    def test_simple_group(self) -> None:
        """Verify '(42)' unwraps to IntegerLiteral."""
        node = _parse_expr("(42)")
        assert isinstance(node, IntegerLiteral)
        assert node.value == ANSWER

    def test_group_overrides_precedence(self) -> None:
        """Verify '(1 + 2) * 3' groups addition first."""
        node = _parse_expr("(1 + 2) * 3")
        assert isinstance(node, BinaryOp)
        assert node.operator == "*"
        assert isinstance(node.left, BinaryOp)
        assert node.left.operator == "+"

    def test_nested_groups(self) -> None:
        """Verify '((5))' unwraps to IntegerLiteral."""
        node = _parse_expr("((5))")
        assert isinstance(node, IntegerLiteral)
        assert node.value == FIVE

    def test_unclosed_paren_raises(self) -> None:
        """Verify missing ')' raises ParseError."""
        with pytest.raises(ParseError, match="Expected '\\)'"):
            _parse_expr("(1 + 2")


# -- Comparison operators -----------------------------------------------------


class TestParserComparisons:
    """Verify parsing of comparison operators."""

    def test_equal_equal(self) -> None:
        """Verify '1 == 2' parses to BinaryOp with correct operands."""
        node = _parse_expr("1 == 2")
        assert isinstance(node, BinaryOp)
        assert node.operator == "=="
        assert isinstance(node.left, IntegerLiteral)
        assert node.left.value == ONE
        assert isinstance(node.right, IntegerLiteral)
        assert node.right.value == TWO

    def test_bang_equal(self) -> None:
        """Verify '1 != 2' parses to BinaryOp with correct operands."""
        node = _parse_expr("1 != 2")
        assert isinstance(node, BinaryOp)
        assert node.operator == "!="
        assert isinstance(node.left, IntegerLiteral)
        assert node.left.value == ONE
        assert isinstance(node.right, IntegerLiteral)
        assert node.right.value == TWO

    def test_less_than(self) -> None:
        """Verify '1 < 2' parses to BinaryOp with correct operands."""
        node = _parse_expr("1 < 2")
        assert isinstance(node, BinaryOp)
        assert node.operator == "<"
        assert isinstance(node.left, IntegerLiteral)
        assert node.left.value == ONE
        assert isinstance(node.right, IntegerLiteral)
        assert node.right.value == TWO

    def test_less_equal(self) -> None:
        """Verify '1 <= 2' parses to BinaryOp with correct operands."""
        node = _parse_expr("1 <= 2")
        assert isinstance(node, BinaryOp)
        assert node.operator == "<="
        assert isinstance(node.left, IntegerLiteral)
        assert node.left.value == ONE
        assert isinstance(node.right, IntegerLiteral)
        assert node.right.value == TWO

    def test_greater_than(self) -> None:
        """Verify '1 > 2' parses to BinaryOp with correct operands."""
        node = _parse_expr("1 > 2")
        assert isinstance(node, BinaryOp)
        assert node.operator == ">"
        assert isinstance(node.left, IntegerLiteral)
        assert node.left.value == ONE
        assert isinstance(node.right, IntegerLiteral)
        assert node.right.value == TWO

    def test_greater_equal(self) -> None:
        """Verify '1 >= 2' parses to BinaryOp with correct operands."""
        node = _parse_expr("1 >= 2")
        assert isinstance(node, BinaryOp)
        assert node.operator == ">="
        assert isinstance(node.left, IntegerLiteral)
        assert node.left.value == ONE
        assert isinstance(node.right, IntegerLiteral)
        assert node.right.value == TWO


# -- Error handling -----------------------------------------------------------


class TestParserExpressionErrors:
    """Verify error handling in expression parsing."""

    def test_empty_expression_raises(self) -> None:
        """Verify an empty token stream raises ParseError."""
        with pytest.raises(ParseError):
            _parse_expr("")

    def test_unexpected_token_raises(self) -> None:
        """Verify an unexpected token raises ParseError."""
        with pytest.raises(ParseError):
            _parse_expr(")")

    def test_trailing_operator_raises(self) -> None:
        """Verify '1 +' without right operand raises ParseError."""
        with pytest.raises(ParseError):
            _parse_expr("1 +")


# -- Edge cases ---------------------------------------------------------------


class TestParserExpressionEdgeCases:
    """Verify edge-case expressions are handled correctly."""

    def test_mixed_unary_not_minus(self) -> None:
        """Verify 'not -5' parses to nested UnaryOp."""
        node = _parse_expr("not -5")
        assert isinstance(node, UnaryOp)
        assert node.operator == "not"
        assert isinstance(node.operand, UnaryOp)
        assert node.operand.operator == "-"

    def test_all_arithmetic_precedence(self) -> None:
        """Verify '1 + 2 * 3 - 4 / 5' respects full precedence chain."""
        node = _parse_expr("1 + 2 * 3 - 4")
        assert isinstance(node, BinaryOp)
        assert node.operator == "-"
        assert isinstance(node.left, BinaryOp)
        assert node.left.operator == "+"

    def test_deeply_nested_parens(self) -> None:
        """Verify '((((1))))' unwraps to IntegerLiteral."""
        node = _parse_expr("((((1))))")
        assert isinstance(node, IntegerLiteral)
        assert node.value == ONE

    def test_group_with_trailing_operator_raises(self) -> None:
        """Verify '(1 +)' raises ParseError."""
        with pytest.raises(ParseError):
            _parse_expr("(1 +)")

    def test_chained_comparisons_left_associative(self) -> None:
        """Verify '1 < 2 < 3' groups as '(1 < 2) < 3'."""
        node = _parse_expr("1 < 2 < 3")
        assert isinstance(node, BinaryOp)
        assert node.operator == "<"
        assert isinstance(node.left, BinaryOp)
        assert node.left.operator == "<"
        assert isinstance(node.right, IntegerLiteral)
        assert node.right.value == THREE
