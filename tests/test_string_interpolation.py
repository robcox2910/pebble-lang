"""Tests for string interpolation (Phase 11).

Cover lexer tokenization, parser AST construction, analyzer validation,
compiler bytecode generation, and VM execution of interpolated strings.
"""

import pytest

from pebble.ast_nodes import BinaryOp, Expression, Identifier, StringInterpolation, StringLiteral
from pebble.bytecode import OpCode
from pebble.errors import LexerError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.tokens import TokenKind
from tests.conftest import (
    compile_instructions,
    run_source,
)

# -- Named constants ----------------------------------------------------------

ONE = 1
TWO = 2
THREE = 3
FOUR = 4
FIVE = 5


# -- Helpers ------------------------------------------------------------------


def _kinds(source: str) -> list[TokenKind]:
    """Return just the token kinds for *source* (excluding EOF)."""
    tokens = Lexer(source).tokenize()
    return [t.kind for t in tokens if t.kind != TokenKind.EOF]


def _kind_value_pairs(source: str) -> list[tuple[TokenKind, str]]:
    """Return (kind, value) pairs for *source* (excluding EOF)."""
    tokens = Lexer(source).tokenize()
    return [(t.kind, t.value) for t in tokens if t.kind != TokenKind.EOF]


def _parse_expr(source: str) -> Expression:
    """Lex and parse a single expression from *source*."""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse_expression()


# -- Cycle 1: Lexer tokenization ---------------------------------------------


class TestLexerStringInterpolation:
    """Verify the lexer splits interpolated strings into token sequences."""

    def test_simple_interpolation(self) -> None:
        """``"hello {name}"`` produces STRING_START, IDENTIFIER, STRING_END."""
        pairs = _kind_value_pairs('"hello {name}"')
        assert pairs == [
            (TokenKind.STRING_START, "hello "),
            (TokenKind.IDENTIFIER, "name"),
            (TokenKind.STRING_END, ""),
        ]

    def test_plain_string_unchanged(self) -> None:
        """A string without ``{`` still produces a single STRING token."""
        pairs = _kind_value_pairs('"plain"')
        assert pairs == [(TokenKind.STRING, "plain")]

    def test_text_before_and_after(self) -> None:
        """``"hello {x} world"`` has text in START and END segments."""
        pairs = _kind_value_pairs('"hello {x} world"')
        assert pairs == [
            (TokenKind.STRING_START, "hello "),
            (TokenKind.IDENTIFIER, "x"),
            (TokenKind.STRING_END, " world"),
        ]

    def test_multiple_interpolations(self) -> None:
        """``"{a} and {b}"`` produces START, expr, MIDDLE, expr, END."""
        pairs = _kind_value_pairs('"{a} and {b}"')
        assert pairs == [
            (TokenKind.STRING_START, ""),
            (TokenKind.IDENTIFIER, "a"),
            (TokenKind.STRING_MIDDLE, " and "),
            (TokenKind.IDENTIFIER, "b"),
            (TokenKind.STRING_END, ""),
        ]

    def test_expression_in_interpolation(self) -> None:
        """``"sum is {1 + 2}"`` lexes the expression tokens inside braces."""
        kinds = _kinds('"sum is {1 + 2}"')
        assert kinds == [
            TokenKind.STRING_START,
            TokenKind.INTEGER,
            TokenKind.PLUS,
            TokenKind.INTEGER,
            TokenKind.STRING_END,
        ]

    def test_escaped_brace(self) -> None:
        r"""``"use \{braces\}"`` treats ``\{`` as a literal brace."""
        pairs = _kind_value_pairs(r'"use \{braces}"')
        assert pairs == [(TokenKind.STRING, "use {braces}")]

    def test_escaped_brace_with_interpolation(self) -> None:
        r"""``"\{x} = {x}"`` — escaped brace before real interpolation."""
        pairs = _kind_value_pairs(r'"\{x} = {x}"')
        assert pairs == [
            (TokenKind.STRING_START, "{x} = "),
            (TokenKind.IDENTIFIER, "x"),
            (TokenKind.STRING_END, ""),
        ]

    def test_empty_string_no_interpolation(self) -> None:
        """An empty string still produces a plain STRING token."""
        pairs = _kind_value_pairs('""')
        assert pairs == [(TokenKind.STRING, "")]

    def test_unterminated_interpolation_raises(self) -> None:
        """Unterminated ``{`` inside a string raises LexerError."""
        with pytest.raises(LexerError, match="Unterminated interpolation"):
            Lexer('"hello {name').tokenize()

    def test_three_interpolations(self) -> None:
        """Three interpolation expressions use START, MIDDLE, MIDDLE, END."""
        pairs = _kind_value_pairs('"{a}{b}{c}"')
        assert pairs == [
            (TokenKind.STRING_START, ""),
            (TokenKind.IDENTIFIER, "a"),
            (TokenKind.STRING_MIDDLE, ""),
            (TokenKind.IDENTIFIER, "b"),
            (TokenKind.STRING_MIDDLE, ""),
            (TokenKind.IDENTIFIER, "c"),
            (TokenKind.STRING_END, ""),
        ]


# -- Cycle 2: Parser + AST ---------------------------------------------------


class TestParserStringInterpolation:
    """Verify the parser builds StringInterpolation AST nodes."""

    def test_simple_interpolation_ast(self) -> None:
        """``"hello {name}"`` parses to StringInterpolation with 2 parts."""
        node = _parse_expr('"hello {name}"')
        assert isinstance(node, StringInterpolation)
        assert len(node.parts) == TWO
        assert isinstance(node.parts[0], StringLiteral)
        assert node.parts[0].value == "hello "
        assert isinstance(node.parts[1], Identifier)
        assert node.parts[1].name == "name"

    def test_text_after_interpolation(self) -> None:
        """``"{x} end"`` has identifier then string literal."""
        node = _parse_expr('"{x} end"')
        assert isinstance(node, StringInterpolation)
        assert len(node.parts) == TWO
        assert isinstance(node.parts[0], Identifier)
        assert isinstance(node.parts[1], StringLiteral)
        assert node.parts[1].value == " end"

    def test_multiple_interpolation_parts(self) -> None:
        """``"{a} and {b}"`` parses to 3 parts."""
        node = _parse_expr('"{a} and {b}"')
        assert isinstance(node, StringInterpolation)
        assert len(node.parts) == THREE
        assert isinstance(node.parts[0], Identifier)
        assert isinstance(node.parts[1], StringLiteral)
        assert node.parts[1].value == " and "
        assert isinstance(node.parts[2], Identifier)

    def test_expression_inside_interpolation(self) -> None:
        """``"result: {1 + 2}"`` parses expression inside braces."""
        node = _parse_expr('"result: {1 + 2}"')
        assert isinstance(node, StringInterpolation)
        assert len(node.parts) == TWO
        assert isinstance(node.parts[0], StringLiteral)
        assert isinstance(node.parts[1], BinaryOp)


# -- Cycle 3: Compiler + VM --------------------------------------------------


class TestCompilerStringInterpolation:
    """Verify the compiler emits BUILD_STRING for interpolated strings."""

    def test_build_string_emitted(self) -> None:
        """``print("hello {name}")`` emits BUILD_STRING with correct count."""
        source = 'let name = "world"\nprint("hello {name}")'
        ins = compile_instructions(source)
        build_string_ops = [i for i in ins if i.opcode is OpCode.BUILD_STRING]
        assert len(build_string_ops) == ONE
        assert build_string_ops[0].operand == TWO


class TestVMStringInterpolation:
    """Verify the VM executes string interpolation end-to-end."""

    def test_simple_interpolation(self) -> None:
        """``"hello {name}"`` with name = "world" → "hello world"."""
        source = 'let name = "world"\nprint("hello {name}")'
        assert run_source(source) == "hello world\n"

    def test_integer_interpolation(self) -> None:
        """Integers are converted to strings during interpolation."""
        source = 'let x = 42\nprint("x is {x}")'
        assert run_source(source) == "x is 42\n"

    def test_expression_interpolation(self) -> None:
        """Expressions inside ``{…}`` are evaluated and stringified."""
        source = 'print("sum is {1 + 2}")'
        assert run_source(source) == "sum is 3\n"

    def test_boolean_interpolation(self) -> None:
        """Booleans format as ``true``/``false`` in interpolation."""
        source = 'print("flag is {true}")'
        assert run_source(source) == "flag is true\n"

    def test_multiple_interpolations(self) -> None:
        """Multiple expressions in one string are all evaluated."""
        source = 'let a = 1\nlet b = 2\nprint("{a} + {b} = {a + b}")'
        assert run_source(source) == "1 + 2 = 3\n"

    def test_empty_segments(self) -> None:
        """Interpolation with no surrounding text works."""
        source = 'let x = "hello"\nprint("{x}")'
        assert run_source(source) == "hello\n"

    def test_escaped_brace(self) -> None:
        r"""``\{`` produces a literal brace in the output."""
        source = r'print("value: \{42}")'
        assert run_source(source) == "value: {42}\n"

    def test_adjacent_interpolations(self) -> None:
        """Two adjacent interpolations without text between them."""
        source = 'let a = "hello"\nlet b = "world"\nprint("{a}{b}")'
        assert run_source(source) == "helloworld\n"

    def test_function_call_in_interpolation(self) -> None:
        """A function call works inside interpolation braces."""
        source = 'fn double(n) { return n * 2 }\nprint("result: {double(5)}")'
        assert run_source(source) == "result: 10\n"
