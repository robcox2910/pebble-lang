"""Tests for pattern matching: match/case statements."""

import pytest

from pebble.ast_nodes import (
    CapturePattern,
    LiteralPattern,
    MatchStatement,
    OrPattern,
    WildcardPattern,
)
from pebble.bytecode import OpCode
from pebble.errors import ParseError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.tokens import TokenKind
from tests.conftest import (
    analyze,
    compile_opcodes,
    run_source,
)

# -- Named constants ----------------------------------------------------------

LITERAL_INT = 42
LITERAL_FLOAT = 3.14
LITERAL_NEG = -1
CASE_COUNT_TWO = 2
OR_FIRST = 1
OR_SECOND = 2
OR_THIRD = 3


# -- Helpers ------------------------------------------------------------------


def _lex(source: str) -> list[TokenKind]:
    """Lex and return just the token kinds."""
    return [t.kind for t in Lexer(source).tokenize()]


def _parse(source: str) -> list[object]:
    """Lex + parse helper returning the statement list."""
    tokens = Lexer(source).tokenize()
    return list(Parser(tokens).parse().statements)


# =============================================================================
# Lexer
# =============================================================================


class TestMatchLexer:
    """Verify match and case tokenize as keywords."""

    def test_match_keyword_token(self) -> None:
        """Verify 'match' produces a MATCH token."""
        kinds = _lex("match")
        assert TokenKind.MATCH in kinds

    def test_case_keyword_token(self) -> None:
        """Verify 'case' produces a CASE token."""
        kinds = _lex("case")
        assert TokenKind.CASE in kinds

    def test_match_not_identifier(self) -> None:
        """Verify 'match' is not lexed as IDENTIFIER."""
        kinds = _lex("match")
        assert TokenKind.IDENTIFIER not in kinds


# =============================================================================
# Parser
# =============================================================================


class TestMatchParser:
    """Verify parsing of match/case statements."""

    def test_parse_literal_int_pattern(self) -> None:
        """Parse a match with an integer literal pattern."""
        stmts = _parse('match x { case 42 { print("yes") } case _ { print("no") } }')
        assert len(stmts) == 1
        match_stmt = stmts[0]
        assert isinstance(match_stmt, MatchStatement)
        assert len(match_stmt.cases) == CASE_COUNT_TWO
        assert isinstance(match_stmt.cases[0].pattern, LiteralPattern)
        assert match_stmt.cases[0].pattern.value == LITERAL_INT

    def test_parse_literal_string_pattern(self) -> None:
        """Parse a match with a string literal pattern."""
        stmts = _parse('match x { case "hi" { print("hello") } case _ { print("bye") } }')
        case0 = stmts[0]
        assert isinstance(case0, MatchStatement)
        assert isinstance(case0.cases[0].pattern, LiteralPattern)
        assert case0.cases[0].pattern.value == "hi"

    def test_parse_literal_true_pattern(self) -> None:
        """Parse a match with a boolean true pattern."""
        stmts = _parse("match x { case true { print(1) } case _ { print(0) } }")
        case0 = stmts[0]
        assert isinstance(case0, MatchStatement)
        assert isinstance(case0.cases[0].pattern, LiteralPattern)
        assert case0.cases[0].pattern.value is True

    def test_parse_literal_false_pattern(self) -> None:
        """Parse a match with a boolean false pattern."""
        stmts = _parse("match x { case false { print(0) } case _ { print(1) } }")
        case0 = stmts[0]
        assert isinstance(case0, MatchStatement)
        assert isinstance(case0.cases[0].pattern, LiteralPattern)
        assert case0.cases[0].pattern.value is False

    def test_parse_literal_float_pattern(self) -> None:
        """Parse a match with a float literal pattern."""
        stmts = _parse("match x { case 3.14 { print(1) } case _ { print(0) } }")
        case0 = stmts[0]
        assert isinstance(case0, MatchStatement)
        assert isinstance(case0.cases[0].pattern, LiteralPattern)
        assert case0.cases[0].pattern.value == LITERAL_FLOAT

    def test_parse_negative_int_pattern(self) -> None:
        """Parse a match with a negative integer pattern."""
        stmts = _parse("match x { case -1 { print(1) } case _ { print(0) } }")
        case0 = stmts[0]
        assert isinstance(case0, MatchStatement)
        assert isinstance(case0.cases[0].pattern, LiteralPattern)
        assert case0.cases[0].pattern.value == LITERAL_NEG

    def test_parse_wildcard_pattern(self) -> None:
        """Parse a match with a wildcard pattern."""
        stmts = _parse("match x { case _ { print(0) } }")
        case0 = stmts[0]
        assert isinstance(case0, MatchStatement)
        assert isinstance(case0.cases[0].pattern, WildcardPattern)

    def test_parse_capture_pattern(self) -> None:
        """Parse a match with a capture pattern."""
        stmts = _parse("match x { case let y { print(y) } }")
        case0 = stmts[0]
        assert isinstance(case0, MatchStatement)
        assert isinstance(case0.cases[0].pattern, CapturePattern)
        assert case0.cases[0].pattern.name == "y"

    def test_parse_or_pattern(self) -> None:
        """Parse a match with an OR pattern."""
        stmts = _parse("match x { case 1 | 2 | 3 { print(1) } case _ { print(0) } }")
        case0 = stmts[0]
        assert isinstance(case0, MatchStatement)
        pat = case0.cases[0].pattern
        assert isinstance(pat, OrPattern)
        assert len(pat.patterns) == OR_THIRD
        assert pat.patterns[0].value == OR_FIRST
        assert pat.patterns[1].value == OR_SECOND
        assert pat.patterns[2].value == OR_THIRD

    def test_parse_error_missing_open_brace(self) -> None:
        """Error when match body has no opening brace."""
        with pytest.raises(ParseError, match=r"Expected '\{'"):
            _parse("match x case 1 { print(1) } }")

    def test_parse_error_case_let_underscore(self) -> None:
        """Error on 'case let _' — ambiguous pattern."""
        with pytest.raises(ParseError, match="Cannot use '_' as capture"):
            _parse("match x { case let _ { print(0) } }")

    def test_parse_error_unexpected_pattern_token(self) -> None:
        """Error on unexpected token in pattern position."""
        with pytest.raises(ParseError, match="Expected pattern"):
            _parse("match x { case + { print(0) } }")


# =============================================================================
# Analyzer
# =============================================================================


class TestMatchAnalyzer:
    """Verify semantic analysis of match/case statements."""

    def test_exhaustiveness_error(self) -> None:
        """Error when last case is not wildcard or capture."""
        with pytest.raises(SemanticError, match="must end with a wildcard or capture"):
            analyze("let x = 1\nmatch x { case 1 { print(1) } }")

    def test_unreachable_case_after_wildcard(self) -> None:
        """Error when a case follows a wildcard."""
        with pytest.raises(SemanticError, match="Unreachable"):
            analyze("let x = 1\nmatch x { case _ { print(0) } case 1 { print(1) } }")

    def test_unreachable_case_after_capture(self) -> None:
        """Error when a case follows a capture."""
        with pytest.raises(SemanticError, match="Unreachable"):
            analyze("let x = 1\nmatch x { case let y { print(y) } case 1 { print(1) } }")

    def test_empty_match_error(self) -> None:
        """Error on match with zero cases."""
        with pytest.raises(SemanticError, match="at least one case"):
            analyze("let x = 1\nmatch x { }")

    def test_capture_scope_isolation(self) -> None:
        """Capture variable is not visible outside its case body."""
        with pytest.raises(SemanticError, match="Undeclared variable 'y'"):
            analyze("let x = 1\nmatch x { case let y { print(y) } }\nprint(y)")

    def test_capture_binding_valid(self) -> None:
        """Capture variable is usable inside its case body — no error."""
        analyze("let x = 1\nmatch x { case let y { print(y) } }")

    def test_scope_isolation_between_cases(self) -> None:
        """Variables declared in one case are not visible in another."""
        analyze(
            "let x = 1\nmatch x {\n"
            "  case 1 { let a = 10\nprint(a) }\n"
            "  case _ { let a = 20\nprint(a) }\n"
            "}"
        )


# =============================================================================
# Compiler + End-to-end
# =============================================================================


class TestMatchCompiler:
    """Verify compilation and execution of match/case statements."""

    def test_compile_emits_store_and_equal(self) -> None:
        """Compiler emits STORE_NAME for hidden variable and EQUAL for literal test."""
        opcodes = compile_opcodes("let x = 1\nmatch x { case 1 { print(1) } case _ { print(0) } }")
        assert OpCode.STORE_NAME in opcodes
        assert OpCode.EQUAL in opcodes

    def test_match_int_literal(self) -> None:
        """Match an integer literal — execute matching case body."""
        output = run_source("let x = 42\nmatch x { case 42 { print(1) } case _ { print(0) } }")
        assert output.strip() == "1"

    def test_match_string_literal(self) -> None:
        """Match a string literal."""
        output = run_source('let x = "hi"\nmatch x { case "hi" { print(1) } case _ { print(0) } }')
        assert output.strip() == "1"

    def test_match_bool_literal(self) -> None:
        """Match a boolean literal."""
        output = run_source("let x = true\nmatch x { case true { print(1) } case _ { print(0) } }")
        assert output.strip() == "1"

    def test_match_float_literal(self) -> None:
        """Match a float literal."""
        output = run_source("let x = 3.14\nmatch x { case 3.14 { print(1) } case _ { print(0) } }")
        assert output.strip() == "1"

    def test_match_negative_literal(self) -> None:
        """Match a negative integer literal."""
        output = run_source("let x = -1\nmatch x { case -1 { print(1) } case _ { print(0) } }")
        assert output.strip() == "1"

    def test_wildcard_catches_all(self) -> None:
        """Wildcard case catches any unmatched value."""
        output = run_source("let x = 99\nmatch x { case 1 { print(1) } case _ { print(0) } }")
        assert output.strip() == "0"

    def test_capture_binds_value(self) -> None:
        """Capture pattern binds the matched value to a variable."""
        output = run_source("let x = 42\nmatch x { case let y { print(y) } }")
        assert output.strip() == "42"

    def test_or_pattern_matches_any(self) -> None:
        """OR pattern matches any of the listed alternatives."""
        output = run_source(
            "let x = 2\nmatch x { case 1 | 2 | 3 { print(1) } case _ { print(0) } }"
        )
        assert output.strip() == "1"

    def test_or_pattern_no_match(self) -> None:
        """OR pattern falls through when none match."""
        output = run_source(
            "let x = 5\nmatch x { case 1 | 2 | 3 { print(1) } case _ { print(0) } }"
        )
        assert output.strip() == "0"

    def test_first_match_wins(self) -> None:
        """When multiple cases could match, the first one wins."""
        output = run_source(
            "let x = 1\nmatch x {\n"
            "  case 1 { print(1) }\n"
            "  case 1 { print(2) }\n"
            "  case _ { print(0) }\n"
            "}"
        )
        assert output.strip() == "1"

    def test_nested_match(self) -> None:
        """Nested match statements use different hidden variables."""
        output = run_source(
            "let x = 1\nlet y = 2\n"
            "match x {\n"
            "  case 1 {\n"
            "    match y {\n"
            "      case 2 { print(12) }\n"
            "      case _ { print(10) }\n"
            "    }\n"
            "  }\n"
            "  case _ { print(0) }\n"
            "}"
        )
        assert output.strip() == "12"

    def test_match_in_function(self) -> None:
        """Match works correctly inside a function body."""
        output = run_source(
            "fn classify(n) {\n"
            "  match n {\n"
            "    case 0 { return 0 }\n"
            "    case let x { return x }\n"
            "  }\n"
            "}\n"
            "print(classify(0))\n"
            "print(classify(5))\n"
        )
        assert output.strip() == "0\n5"

    def test_match_inside_loop(self) -> None:
        """Match works correctly inside a loop."""
        output = run_source(
            "for i in range(3) {\n"
            "  match i {\n"
            "    case 0 { print(0) }\n"
            "    case 1 { print(1) }\n"
            "    case _ { print(2) }\n"
            "  }\n"
            "}"
        )
        assert output.strip() == "0\n1\n2"

    def test_capture_pattern_used_in_closure(self) -> None:
        """Capture pattern variable is accessible from a nested closure."""
        output = run_source(
            "fn outer(val) {\n"
            "  match val {\n"
            "    case let captured {\n"
            "      fn inner() {\n"
            "        return captured\n"
            "      }\n"
            "      return inner()\n"
            "    }\n"
            "  }\n"
            "}\n"
            "print(outer(42))"
        )
        assert output.strip() == "42"
