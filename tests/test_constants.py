"""Tests for the ``const`` keyword — immutable variable declarations."""

import pytest

from pebble.ast_nodes import BinaryOp, ConstAssignment, IntegerLiteral, Program, Statement
from pebble.errors import ParseError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from tests.conftest import (
    analyze,
    run_source,
)

# -- Helpers ------------------------------------------------------------------


def _parse(source: str) -> Program:
    """Lex and parse *source* into a Program AST."""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def _stmts(source: str) -> list[Statement]:
    """Return top-level statements from *source*."""
    return _parse(source).statements


# -- Named constants ----------------------------------------------------------

ANSWER = 42
ONE = 1
TWO = 2
THREE = 3
FIVE = 5


# -- Parser tests -------------------------------------------------------------


class TestConstParser:
    """Verify the parser produces ConstAssignment nodes."""

    def test_const_integer(self) -> None:
        """Parse ``const x = 42`` into a ConstAssignment node."""
        stmts = _stmts("const x = 42")
        assert len(stmts) == ONE
        node = stmts[0]
        assert isinstance(node, ConstAssignment)
        assert node.name == "x"
        assert isinstance(node.value, IntegerLiteral)
        assert node.value.value == ANSWER

    def test_const_with_expression(self) -> None:
        """Parse ``const x = 1 + 2`` into a ConstAssignment with BinaryOp value."""
        stmts = _stmts("const x = 1 + 2")
        assert len(stmts) == ONE
        node = stmts[0]
        assert isinstance(node, ConstAssignment)
        assert isinstance(node.value, BinaryOp)

    def test_const_missing_name(self) -> None:
        """Report an error when the variable name is missing."""
        with pytest.raises(ParseError, match="Expected variable name after 'const'"):
            _stmts("const = 42")

    def test_const_missing_equals(self) -> None:
        """Report an error when the ``=`` is missing."""
        with pytest.raises(ParseError, match="Expected '=' after variable name"):
            _stmts("const x 42")

    def test_const_location(self) -> None:
        """Verify the ConstAssignment location points to the ``const`` token."""
        stmts = _stmts("const x = 42")
        node = stmts[0]
        assert isinstance(node, ConstAssignment)
        assert node.location.line == ONE
        assert node.location.column == ONE


# -- Analyzer tests -----------------------------------------------------------


class TestConstAnalyzer:
    """Verify the analyzer enforces const immutability."""

    def test_const_visible_in_scope(self) -> None:
        """A const variable can be read after declaration."""
        analyze("const x = 5\nprint(x)")

    def test_reassign_const_raises(self) -> None:
        """Reassigning a const variable raises a SemanticError."""
        with pytest.raises(SemanticError, match="Cannot reassign constant 'x'"):
            analyze("const x = 1\nx = 2")

    def test_duplicate_const_raises(self) -> None:
        """Redeclaring a const in the same scope raises a SemanticError."""
        with pytest.raises(SemanticError, match="already declared"):
            analyze("const x = 1\nconst x = 2")

    def test_let_reassignment_still_works(self) -> None:
        """Regular ``let`` variables can still be reassigned (regression)."""
        analyze("let x = 1\nx = 2")

    def test_const_shadows_outer_let(self) -> None:
        """A const in an inner scope can shadow an outer let."""
        analyze("let x = 1\nif true {\n    const x = 2\n    print(x)\n}")

    def test_const_inside_function(self) -> None:
        """A const can be declared inside a function body."""
        analyze("fn f() {\n    const x = 42\n    print(x)\n}")

    def test_const_used_in_expression(self) -> None:
        """A const variable can be used in expressions."""
        analyze("const x = 3\nprint(x + 2)")


# -- VM integration tests -----------------------------------------------------

TWENTY_ONE = 21
NINETY_NINE = 99


class TestConstVM:
    """Verify const declarations work end-to-end through the VM."""

    def test_const_prints_value(self) -> None:
        """A const variable holds and prints its value."""
        output = run_source("const x = 42\nprint(x)")
        assert output == "42\n"

    def test_const_with_expression_value(self) -> None:
        """A const initialised with an expression evaluates correctly."""
        output = run_source("const x = 3 * 7\nprint(x)")
        assert output == f"{TWENTY_ONE}\n"

    def test_const_list_index_assignment(self) -> None:
        """Index assignment on a const list is allowed (binding is const, not value)."""
        source = "const xs = [1, 2, 3]\nxs[0] = 99\nprint(xs[0])"
        output = run_source(source)
        assert output == f"{NINETY_NINE}\n"

    def test_const_in_loop_body(self) -> None:
        """A const inside a loop body is fresh each iteration."""
        source = "for i in range(3) {\n    const x = i * 2\n    print(x)\n}"
        output = run_source(source)
        assert output == "0\n2\n4\n"
