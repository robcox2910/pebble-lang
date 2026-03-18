"""Tests for the ``null`` type (Phase 4 Item 3).

Cover the full pipeline: lexer, parser, analyzer, compiler, and
end-to-end integration via the VM.
"""

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import Assignment, LiteralPattern, MatchStatement, NullLiteral
from pebble.bytecode import CompiledProgram, OpCode
from pebble.compiler import Compiler
from pebble.errors import PebbleRuntimeError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.tokens import TokenKind
from tests.conftest import run_source


def _tokens(source: str) -> list[tuple[TokenKind, str]]:
    """Tokenize *source* and return ``(kind, value)`` pairs (no EOF)."""
    tokens = Lexer(source).tokenize()
    return [(t.kind, t.value) for t in tokens if t.kind != TokenKind.EOF]


def _parse(source: str) -> Assignment:
    """Parse *source* and return the first Assignment statement."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    stmt = program.statements[0]
    assert isinstance(stmt, Assignment)
    return stmt


def _compile_result(source: str) -> CompiledProgram:
    """Compile *source* and return the CompiledProgram."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzer = SemanticAnalyzer()
    analyzed = analyzer.analyze(program)
    return Compiler(
        cell_vars=analyzer.cell_vars,
        free_vars=analyzer.free_vars,
    ).compile(analyzed)


# -- Named constants ----------------------------------------------------------

CONST_POOL_INDEX_ZERO = 0


# -- Cycle 1: Lexer -----------------------------------------------------------


class TestLexerNull:
    """Lexer produces NULL tokens for the ``null`` keyword."""

    def test_null_keyword_token(self) -> None:
        """``null`` is lexed as a single NULL token."""
        result = _tokens("null")
        assert result == [(TokenKind.NULL, "null")]


# -- Cycle 2: Parser ----------------------------------------------------------


class TestParserNull:
    """Parser produces NullLiteral and LiteralPattern(None) nodes."""

    def test_parse_null_literal(self) -> None:
        """``let x = null`` parses the RHS as a NullLiteral."""
        stmt = _parse("let x = null")
        assert isinstance(stmt.value, NullLiteral)

    def test_parse_null_in_equality(self) -> None:
        """``x == null`` parses without error."""
        tokens = Lexer("let x = null\nx == null").tokenize()
        program = Parser(tokens).parse()
        assert len(program.statements) > 1

    def test_parse_null_match_pattern(self) -> None:
        """``case null`` produces a LiteralPattern with value None."""
        source = "match x { case null { print(1) } case _ { print(2) } }"
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        match_stmt = program.statements[0]
        assert isinstance(match_stmt, MatchStatement)
        first_case = match_stmt.cases[0]
        assert isinstance(first_case.pattern, LiteralPattern)
        assert first_case.pattern.value is None


# -- Cycle 3: Analyzer --------------------------------------------------------


class TestAnalyzerNull:
    """Analyzer accepts null-related constructs."""

    def test_null_literal_passes(self) -> None:
        """``let x = null`` passes semantic analysis."""
        tokens = Lexer("let x = null").tokenize()
        program = Parser(tokens).parse()
        SemanticAnalyzer().analyze(program)

    def test_null_type_annotation(self) -> None:
        """``let x: Null = null`` passes semantic analysis."""
        tokens = Lexer("let x: Null = null").tokenize()
        program = Parser(tokens).parse()
        SemanticAnalyzer().analyze(program)

    def test_null_as_default_param(self) -> None:
        """``fn f(x = null)`` passes semantic analysis."""
        tokens = Lexer("fn f(x = null) { return x }").tokenize()
        program = Parser(tokens).parse()
        SemanticAnalyzer().analyze(program)


# -- Cycle 4: Compiler --------------------------------------------------------


class TestCompilerNull:
    """Compiler emits correct bytecode for null."""

    def test_null_emits_load_const_none(self) -> None:
        """``null`` emits LOAD_CONST with None in the constant pool."""
        result = _compile_result("fn f() { return null }")
        fn = result.functions["f"]
        assert None in fn.constants
        load_idx = fn.constants.index(None)
        assert any(i.opcode is OpCode.LOAD_CONST and i.operand == load_idx for i in fn.instructions)

    def test_implicit_return_emits_null(self) -> None:
        """A function without return uses None in the constant pool."""
        result = _compile_result("fn f() { print(1) }")
        fn = result.functions["f"]
        last_load = fn.instructions[-2]
        assert last_load.opcode is OpCode.LOAD_CONST
        assert fn.constants[last_load.operand] is None  # type: ignore[index]


# -- Cycle 5: Integration (end-to-end via VM) ---------------------------------


class TestNullIntegration:
    """End-to-end tests for null behaviour."""

    def test_print_null(self) -> None:
        """``print(null)`` outputs ``null``."""
        assert run_source("print(null)") == "null\n"

    def test_type_of_null(self) -> None:
        """``type(null)`` returns ``"null"``."""
        assert run_source("print(type(null))") == "null\n"

    def test_null_equality(self) -> None:
        """``null == null`` is ``true``."""
        assert run_source("print(null == null)") == "true\n"

    def test_null_not_equal_zero(self) -> None:
        """``null == 0`` is ``false``."""
        assert run_source("print(null == 0)") == "false\n"

    def test_null_not_equal_false(self) -> None:
        """``null == false`` is ``false``."""
        assert run_source("print(null == false)") == "false\n"

    def test_null_not_equal_empty_string(self) -> None:
        """``null == ""`` is ``false``."""
        assert run_source('print(null == "")') == "false\n"

    def test_null_is_falsy(self) -> None:
        """``if null`` takes the else branch."""
        source = 'if null { print("yes") } else { print("no") }'
        assert run_source(source) == "no\n"

    def test_not_null(self) -> None:
        """``not null`` is ``true``."""
        assert run_source("print(not null)") == "true\n"

    def test_null_arithmetic_error(self) -> None:
        """``null + 1`` raises a PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError):
            run_source("print(null + 1)")

    def test_null_comparison_error(self) -> None:
        """``null < 1`` raises a PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError):
            run_source("print(null < 1)")

    def test_implicit_return_is_null(self) -> None:
        """A function without explicit return returns null."""
        assert run_source("fn f() { let x = 1 }\nprint(f())") == "null\n"

    def test_bare_return_is_null(self) -> None:
        """A bare ``return`` produces null."""
        assert run_source("fn f() { return }\nprint(f())") == "null\n"

    def test_null_in_list(self) -> None:
        """Null values in a list print correctly."""
        assert run_source("print([1, null, 3])") == "[1, null, 3]\n"

    def test_null_in_dict(self) -> None:
        """Null values in a dict print correctly."""
        assert run_source('print({"a": null})') == "{a: null}\n"

    def test_null_in_string_interpolation(self) -> None:
        """Null in string interpolation converts to ``"null"``."""
        assert run_source('let x = null\nprint("{x}")') == "null\n"

    def test_null_type_annotation_e2e(self) -> None:
        """``let x: Null = null`` works at runtime."""
        assert run_source("let x: Null = null\nprint(x)") == "null\n"

    def test_null_type_mismatch(self) -> None:
        """``let x: Int = null`` raises a runtime type error."""
        with pytest.raises(SemanticError, match="expected Int, got Null"):
            run_source("let x: Int = null")

    def test_list_push_returns_null(self) -> None:
        """``xs.push(2)`` returns null (not 0)."""
        source = "let xs = [1]\nlet r = xs.push(2)\nprint(r)"
        assert run_source(source) == "null\n"

    def test_null_default_param(self) -> None:
        """``fn f(x = null)`` uses null when called without arguments."""
        source = "fn f(x = null) { return x }\nprint(f())"
        assert run_source(source) == "null\n"

    def test_null_in_match(self) -> None:
        """``case null`` matches a null value."""
        source = (
            "let x = null\n"
            "match x {\n"
            '  case null { print("matched") }\n'
            '  case _ { print("nope") }\n'
            "}"
        )
        assert run_source(source) == "matched\n"

    def test_null_and_short_circuit(self) -> None:
        """``null and 1`` short-circuits to null (falsy)."""
        assert run_source("print(null and 1)") == "null\n"

    def test_null_or_short_circuit(self) -> None:
        """``null or 42`` short-circuits to 42."""
        assert run_source("print(null or 42)") == "42\n"
