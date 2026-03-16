"""Tests for chained comparisons (Phase 4 Item 4).

Chained comparisons like ``1 < x < 10`` are desugared at parse time into
``(1 < x) and (x < 10)`` using existing ``BinaryOp`` / ``"and"`` nodes.
"""

from pebble.ast_nodes import BinaryOp, Identifier, IntegerLiteral
from pebble.lexer import Lexer
from pebble.parser import Parser
from tests.conftest import (  # pyright: ignore[reportMissingImports]
    run_source,  # pyright: ignore[reportUnknownVariableType]
)

# -- Named constants ----------------------------------------------------------

ONE = 1
TWO = 2
THREE = 3
FIVE = 5
TEN = 10


def _parse_expr(source: str) -> BinaryOp:
    """Lex and parse a single expression, assert it is a BinaryOp."""
    tokens = Lexer(source).tokenize()
    node = Parser(tokens).parse_expression()
    assert isinstance(node, BinaryOp)
    return node


def _run(source: str) -> str:
    """Compile and run *source*, return captured output."""
    return run_source(source)  # type: ignore[no-any-return]


# -- Parser tests: AST structure ----------------------------------------------


class TestChainedComparisonParser:
    """Verify chained comparisons desugar to AND-chains in the AST."""

    def test_two_way_chain(self) -> None:
        """Verify ``1 < x < 10`` desugars to ``(1 < x) and (x < 10)``."""
        node = _parse_expr("1 < x < 10")
        assert node.operator == "and"
        # left arm: 1 < x
        assert isinstance(node.left, BinaryOp)
        assert node.left.operator == "<"
        assert isinstance(node.left.left, IntegerLiteral)
        assert node.left.left.value == ONE
        assert isinstance(node.left.right, Identifier)
        assert node.left.right.name == "x"
        # right arm: x < 10
        assert isinstance(node.right, BinaryOp)
        assert node.right.operator == "<"
        assert isinstance(node.right.left, Identifier)
        assert node.right.left.name == "x"
        assert isinstance(node.right.right, IntegerLiteral)
        assert node.right.right.value == TEN

    def test_three_way_chain(self) -> None:
        """Verify ``1 < a < b < 10`` desugars to ``((1<a) and (a<b)) and (b<10)``."""
        node = _parse_expr("1 < a < b < 10")
        assert node.operator == "and"
        # right arm: b < 10
        assert isinstance(node.right, BinaryOp)
        assert node.right.operator == "<"
        assert isinstance(node.right.left, Identifier)
        assert node.right.left.name == "b"
        assert isinstance(node.right.right, IntegerLiteral)
        assert node.right.right.value == TEN
        # left arm: (1 < a) and (a < b)
        assert isinstance(node.left, BinaryOp)
        assert node.left.operator == "and"
        assert isinstance(node.left.left, BinaryOp)
        assert node.left.left.operator == "<"
        assert isinstance(node.left.right, BinaryOp)
        assert node.left.right.operator == "<"

    def test_mixed_relational(self) -> None:
        """Verify ``1 <= x < 10`` desugars to ``(1 <= x) and (x < 10)``."""
        node = _parse_expr("1 <= x < 10")
        assert node.operator == "and"
        assert isinstance(node.left, BinaryOp)
        assert node.left.operator == "<="
        assert isinstance(node.right, BinaryOp)
        assert node.right.operator == "<"

    def test_chained_equality(self) -> None:
        """Verify ``a == b == c`` desugars to ``(a == b) and (b == c)``."""
        node = _parse_expr("a == b == c")
        assert node.operator == "and"
        assert isinstance(node.left, BinaryOp)
        assert node.left.operator == "=="
        assert isinstance(node.right, BinaryOp)
        assert node.right.operator == "=="

    def test_chained_not_equal(self) -> None:
        """Verify ``a != b != c`` desugars to ``(a != b) and (b != c)``."""
        node = _parse_expr("a != b != c")
        assert node.operator == "and"
        assert isinstance(node.left, BinaryOp)
        assert node.left.operator == "!="
        assert isinstance(node.right, BinaryOp)
        assert node.right.operator == "!="

    def test_single_comparison_unchanged(self) -> None:
        """Verify ``a < b`` produces a plain BinaryOp (no AND wrapping)."""
        node = _parse_expr("a < b")
        assert node.operator == "<"
        assert isinstance(node.left, Identifier)
        assert isinstance(node.right, Identifier)

    def test_chain_with_arithmetic(self) -> None:
        """Verify ``0 < x + 1 < 10`` desugars correctly with arithmetic."""
        node = _parse_expr("0 < x + 1 < 10")
        assert node.operator == "and"
        # left arm checks 0 < (x + 1)
        assert isinstance(node.left, BinaryOp)
        assert node.left.operator == "<"
        assert isinstance(node.left.right, BinaryOp)
        assert node.left.right.operator == "+"
        # right arm checks (x + 1) < 10
        assert isinstance(node.right, BinaryOp)
        assert node.right.operator == "<"
        assert isinstance(node.right.left, BinaryOp)
        assert node.right.left.operator == "+"

    def test_chain_preserves_precedence(self) -> None:
        """Verify ``a + 1 < b < c * 2`` groups arithmetic before comparisons."""
        node = _parse_expr("a + 1 < b < c * 2")
        assert node.operator == "and"
        # left arm checks (a + 1) < b
        assert isinstance(node.left, BinaryOp)
        assert node.left.operator == "<"
        assert isinstance(node.left.left, BinaryOp)
        assert node.left.left.operator == "+"
        # right arm checks b < (c * 2)
        assert isinstance(node.right, BinaryOp)
        assert node.right.operator == "<"
        assert isinstance(node.right.right, BinaryOp)
        assert node.right.right.operator == "*"


# -- Integration tests: end-to-end via run_source ----------------------------


class TestChainedComparisonIntegration:
    """Verify chained comparisons work end-to-end through the full pipeline."""

    def test_range_check_true(self) -> None:
        """Verify ``1 < x < 10`` evaluates true when x is in range."""
        assert _run("let x = 5\nprint(1 < x < 10)") == "true\n"

    def test_range_check_false_low(self) -> None:
        """Verify ``1 < x < 10`` evaluates false when x is below range."""
        assert _run("let x = 0\nprint(1 < x < 10)") == "false\n"

    def test_range_check_false_high(self) -> None:
        """Verify ``1 < x < 10`` evaluates false when x is above range."""
        assert _run("let x = 15\nprint(1 < x < 10)") == "false\n"

    def test_boundary_inclusive(self) -> None:
        """Verify ``1 <= x <= 10`` includes the boundary values."""
        assert _run("let x = 1\nprint(1 <= x <= 10)") == "true\n"

    def test_boundary_exclusive(self) -> None:
        """Verify ``1 < x < 10`` excludes the boundary value."""
        assert _run("let x = 1\nprint(1 < x < 10)") == "false\n"

    def test_descending_chain(self) -> None:
        """Verify ``10 > x > 1`` works as a descending range check."""
        assert _run("let x = 5\nprint(10 > x > 1)") == "true\n"

    def test_triple_chain(self) -> None:
        """Verify three-way chain ``1 < a < b < 10`` works end-to-end."""
        assert _run("let a = 2\nlet b = 5\nprint(1 < a < b < 10)") == "true\n"

    def test_mixed_operators(self) -> None:
        """Verify mixed ``1 <= x < 10`` works end-to-end."""
        assert _run("let x = 5\nprint(1 <= x < 10)") == "true\n"

    def test_equality_chain(self) -> None:
        """Verify ``3 == x == 3`` works as an equality chain."""
        assert _run("let x = 3\nprint(3 == x == 3)") == "true\n"

    def test_chain_in_if(self) -> None:
        """Verify chained comparison works as an if condition."""
        source = 'let x = 50\nif 0 < x < 100 {\n  print("in range")\n}'
        assert _run(source) == "in range\n"

    def test_chain_in_while(self) -> None:
        """Verify chained comparison works as a while condition."""
        source = "let x = 1\nwhile 0 < x < 5 {\n  print(x)\n  x = x + 1\n}\n"
        assert _run(source) == "1\n2\n3\n4\n"

    def test_chain_with_arithmetic(self) -> None:
        """Verify chained comparison with arithmetic subexpressions."""
        assert _run("let x = 5\nprint(0 < x + 1 < 10)") == "true\n"

    def test_chain_short_circuit(self) -> None:
        """Verify short-circuit: false left skips right comparison."""
        assert _run("let x = 0\nprint(1 < x < 10)") == "false\n"

    def test_chain_with_float(self) -> None:
        """Verify chained comparison works with float values."""
        assert _run("let x = 3.5\nprint(1 < x < 10)") == "true\n"

    def test_non_chained_still_works(self) -> None:
        """Verify a single comparison still works unchanged."""
        assert _run("print(3 < 5)") == "true\n"
