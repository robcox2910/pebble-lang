"""Tests for the Pebble parser — statement parsing.

Covers ``let`` declarations, reassignments, ``print()``, ``if/else``,
``while``, block parsing, and the ``Program`` root node.
"""

import pytest

from pebble.ast_nodes import (
    Assignment,
    BinaryOp,
    BooleanLiteral,
    IfStatement,
    IntegerLiteral,
    PrintStatement,
    Program,
    Reassignment,
    Statement,
    StringLiteral,
    WhileLoop,
)
from pebble.errors import ParseError
from pebble.lexer import Lexer
from pebble.parser import Parser

# -- Named constants ----------------------------------------------------------

ANSWER = 42
TEN = 10
FIVE = 5
THREE = 3
TWO = 2
ONE = 1
ZERO = 0


def _parse(source: str) -> Program:
    """Lex and parse *source* into a Program AST."""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def _stmts(source: str) -> list[Statement]:
    """Return the top-level statements from *source*."""
    return _parse(source).statements


# -- Let declarations --------------------------------------------------------


class TestLetDeclaration:
    """Verify parsing of ``let`` variable declarations."""

    def test_let_integer(self) -> None:
        """Verify 'let x = 42' parses to Assignment."""
        stmts = _stmts("let x = 42")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, Assignment)
        assert stmt.name == "x"
        assert isinstance(stmt.value, IntegerLiteral)
        assert stmt.value.value == ANSWER

    def test_let_string(self) -> None:
        """Verify 'let msg = "hello"' parses to Assignment."""
        stmts = _stmts('let msg = "hello"')
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, Assignment)
        assert stmt.name == "msg"
        assert isinstance(stmt.value, StringLiteral)

    def test_let_expression(self) -> None:
        """Verify 'let sum = 1 + 2' parses to Assignment with BinaryOp value."""
        stmts = _stmts("let sum = 1 + 2")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, Assignment)
        assert isinstance(stmt.value, BinaryOp)
        assert stmt.value.operator == "+"

    def test_let_missing_name_raises(self) -> None:
        """Verify 'let = 5' raises ParseError."""
        with pytest.raises(ParseError, match="Expected variable name"):
            _parse("let = 5")

    def test_let_missing_equals_raises(self) -> None:
        """Verify 'let x 5' raises ParseError."""
        with pytest.raises(ParseError, match="Expected '='"):
            _parse("let x 5")


# -- Reassignment ------------------------------------------------------------


class TestReassignment:
    """Verify parsing of variable reassignment."""

    def test_reassign_integer(self) -> None:
        """Verify 'x = 10' parses to Reassignment."""
        stmts = _stmts("x = 10")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, Reassignment)
        assert stmt.name == "x"
        assert isinstance(stmt.value, IntegerLiteral)
        assert stmt.value.value == TEN

    def test_reassign_expression(self) -> None:
        """Verify 'x = x + 1' parses to Reassignment with BinaryOp."""
        stmts = _stmts("x = x + 1")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, Reassignment)
        assert isinstance(stmt.value, BinaryOp)


# -- Print statement ----------------------------------------------------------


class TestPrintStatement:
    """Verify parsing of ``print()`` statements."""

    def test_print_integer(self) -> None:
        """Verify 'print(42)' parses to PrintStatement."""
        stmts = _stmts("print(42)")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, PrintStatement)
        assert isinstance(stmt.expression, IntegerLiteral)
        assert stmt.expression.value == ANSWER

    def test_print_string(self) -> None:
        """Verify 'print("hello")' parses to PrintStatement."""
        stmts = _stmts('print("hello")')
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, PrintStatement)
        assert isinstance(stmt.expression, StringLiteral)

    def test_print_expression(self) -> None:
        """Verify 'print(1 + 2)' parses to PrintStatement with BinaryOp."""
        stmts = _stmts("print(1 + 2)")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, PrintStatement)
        assert isinstance(stmt.expression, BinaryOp)

    def test_print_missing_paren_raises(self) -> None:
        """Verify 'print 42' raises ParseError."""
        with pytest.raises(ParseError, match="Expected '\\('"):
            _parse("print 42")

    def test_print_missing_close_paren_raises(self) -> None:
        """Verify 'print(42' raises ParseError."""
        with pytest.raises(ParseError, match="Expected '\\)'"):
            _parse("print(42")


# -- If statement -------------------------------------------------------------


class TestIfStatement:
    """Verify parsing of ``if/else`` statements."""

    def test_if_without_else(self) -> None:
        """Verify 'if true { print(1) }' parses to IfStatement."""
        stmts = _stmts("if true {\n    print(1)\n}")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, IfStatement)
        assert isinstance(stmt.condition, BooleanLiteral)
        assert stmt.condition.value is True
        assert len(stmt.body) == ONE
        assert isinstance(stmt.body[0], PrintStatement)
        assert stmt.else_body is None

    def test_if_with_else(self) -> None:
        """Verify 'if cond { ... } else { ... }' parses with else_body."""
        source = "if x > 0 {\n    print(x)\n} else {\n    print(0)\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, IfStatement)
        assert stmt.else_body is not None
        assert len(stmt.else_body) == ONE

    def test_if_empty_body(self) -> None:
        """Verify 'if true { }' parses with empty body."""
        stmts = _stmts("if true {\n}")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, IfStatement)
        assert stmt.body == []

    def test_if_missing_brace_raises(self) -> None:
        """Verify missing '{' after condition raises ParseError."""
        with pytest.raises(ParseError, match="Expected '\\{'"):
            _parse("if true print(1)")

    def test_if_missing_closing_brace_raises(self) -> None:
        """Verify missing '}' raises ParseError."""
        with pytest.raises(ParseError, match="Expected '\\}'"):
            _parse("if true {\n    print(1)")


# -- While loop ---------------------------------------------------------------


class TestWhileLoop:
    """Verify parsing of ``while`` loops."""

    def test_while_loop(self) -> None:
        """Verify 'while x < 10 { ... }' parses to WhileLoop."""
        source = "while x < 10 {\n    x = x + 1\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, WhileLoop)
        assert isinstance(stmt.condition, BinaryOp)
        assert stmt.condition.operator == "<"
        assert len(stmt.body) == ONE

    def test_while_empty_body(self) -> None:
        """Verify 'while true { }' parses with empty body."""
        stmts = _stmts("while true {\n}")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, WhileLoop)
        assert stmt.body == []

    def test_while_missing_brace_raises(self) -> None:
        """Verify missing '{' after while condition raises ParseError."""
        with pytest.raises(ParseError, match="Expected '\\{'"):
            _parse("while true print(1)")


# -- Multiple statements ------------------------------------------------------


class TestMultipleStatements:
    """Verify parsing of multiple statements separated by newlines."""

    def test_two_statements(self) -> None:
        """Verify two newline-separated statements parse correctly."""
        stmts = _stmts("let x = 1\nprint(x)")
        assert len(stmts) == TWO
        assert isinstance(stmts[0], Assignment)
        assert isinstance(stmts[1], PrintStatement)

    def test_three_statements(self) -> None:
        """Verify three statements parse correctly."""
        stmts = _stmts("let x = 1\nlet y = 2\nprint(x)")
        assert len(stmts) == THREE

    def test_empty_program(self) -> None:
        """Verify empty source parses to Program with no statements."""
        program = _parse("")
        assert isinstance(program, Program)
        assert program.statements == []

    def test_blank_lines_between_statements(self) -> None:
        """Verify blank lines between statements are tolerated."""
        stmts = _stmts("let x = 1\n\n\nprint(x)")
        assert len(stmts) == TWO


# -- Expression statements ---------------------------------------------------


class TestExpressionStatements:
    """Verify that bare expressions are parsed as statements.

    A bare identifier or function call on its own line should be accepted.
    """

    def test_bare_identifier_as_statement(self) -> None:
        """Verify a bare identifier is treated as a statement."""
        stmts = _stmts("x")
        assert len(stmts) == ONE

    def test_bare_expression_as_statement(self) -> None:
        """Verify a bare expression (e.g. function call) is a statement."""
        stmts = _stmts("1 + 2")
        assert len(stmts) == ONE
