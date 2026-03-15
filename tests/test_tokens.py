"""Tests for the token types, source location, and keyword mapping."""

import dataclasses

import pytest

from pebble.tokens import KEYWORDS, SourceLocation, Token, TokenKind

# -- Named constants for magic-value checks ----------------------------------

FIRST_LINE = 1
FIRST_COLUMN = 1
SECOND_LINE = 2
FIFTH_COLUMN = 5
KEYWORD_COUNT = 23
TOTAL_TOKEN_KINDS = 61


class TestTokenKind:
    """Verify the TokenKind enum has all expected members."""

    def test_total_token_count(self) -> None:
        """Verify the total number of token kinds."""
        assert len(TokenKind) == TOTAL_TOKEN_KINDS

    # -- Literals -------------------------------------------------------------

    def test_integer_literal(self) -> None:
        """Verify INTEGER token kind exists."""
        assert TokenKind.INTEGER == "INTEGER"

    def test_string_literal(self) -> None:
        """Verify STRING token kind exists."""
        assert TokenKind.STRING == "STRING"

    def test_identifier(self) -> None:
        """Verify IDENTIFIER token kind exists."""
        assert TokenKind.IDENTIFIER == "IDENTIFIER"

    # -- Keywords -------------------------------------------------------------

    def test_keyword_const(self) -> None:
        """Verify CONST keyword token kind exists."""
        assert TokenKind.CONST == "CONST"

    def test_keyword_let(self) -> None:
        """Verify LET keyword token kind exists."""
        assert TokenKind.LET == "LET"

    def test_keyword_if(self) -> None:
        """Verify IF keyword token kind exists."""
        assert TokenKind.IF == "IF"

    def test_keyword_else(self) -> None:
        """Verify ELSE keyword token kind exists."""
        assert TokenKind.ELSE == "ELSE"

    def test_keyword_while(self) -> None:
        """Verify WHILE keyword token kind exists."""
        assert TokenKind.WHILE == "WHILE"

    def test_keyword_for(self) -> None:
        """Verify FOR keyword token kind exists."""
        assert TokenKind.FOR == "FOR"

    def test_keyword_in(self) -> None:
        """Verify IN keyword token kind exists."""
        assert TokenKind.IN == "IN"

    def test_keyword_fn(self) -> None:
        """Verify FN keyword token kind exists."""
        assert TokenKind.FN == "FN"

    def test_keyword_return(self) -> None:
        """Verify RETURN keyword token kind exists."""
        assert TokenKind.RETURN == "RETURN"

    def test_keyword_true(self) -> None:
        """Verify TRUE keyword token kind exists."""
        assert TokenKind.TRUE == "TRUE"

    def test_keyword_break(self) -> None:
        """Verify BREAK keyword token kind exists."""
        assert TokenKind.BREAK == "BREAK"

    def test_keyword_continue(self) -> None:
        """Verify CONTINUE keyword token kind exists."""
        assert TokenKind.CONTINUE == "CONTINUE"

    def test_keyword_try(self) -> None:
        """Verify TRY keyword token kind exists."""
        assert TokenKind.TRY == "TRY"

    def test_keyword_catch(self) -> None:
        """Verify CATCH keyword token kind exists."""
        assert TokenKind.CATCH == "CATCH"

    def test_keyword_finally(self) -> None:
        """Verify FINALLY keyword token kind exists."""
        assert TokenKind.FINALLY == "FINALLY"

    def test_keyword_throw(self) -> None:
        """Verify THROW keyword token kind exists."""
        assert TokenKind.THROW == "THROW"

    def test_keyword_match(self) -> None:
        """Verify MATCH keyword token kind exists."""
        assert TokenKind.MATCH == "MATCH"

    def test_keyword_case(self) -> None:
        """Verify CASE keyword token kind exists."""
        assert TokenKind.CASE == "CASE"

    def test_keyword_false(self) -> None:
        """Verify FALSE keyword token kind exists."""
        assert TokenKind.FALSE == "FALSE"

    # -- Operators ------------------------------------------------------------

    def test_operator_plus(self) -> None:
        """Verify PLUS token kind exists."""
        assert TokenKind.PLUS == "PLUS"

    def test_operator_minus(self) -> None:
        """Verify MINUS token kind exists."""
        assert TokenKind.MINUS == "MINUS"

    def test_operator_star(self) -> None:
        """Verify STAR token kind exists."""
        assert TokenKind.STAR == "STAR"

    def test_operator_slash(self) -> None:
        """Verify SLASH token kind exists."""
        assert TokenKind.SLASH == "SLASH"

    def test_operator_percent(self) -> None:
        """Verify PERCENT token kind exists."""
        assert TokenKind.PERCENT == "PERCENT"

    # -- Comparison -----------------------------------------------------------

    def test_equal_equal(self) -> None:
        """Verify EQUAL_EQUAL token kind exists."""
        assert TokenKind.EQUAL_EQUAL == "EQUAL_EQUAL"

    def test_bang_equal(self) -> None:
        """Verify BANG_EQUAL token kind exists."""
        assert TokenKind.BANG_EQUAL == "BANG_EQUAL"

    def test_less(self) -> None:
        """Verify LESS token kind exists."""
        assert TokenKind.LESS == "LESS"

    def test_less_equal(self) -> None:
        """Verify LESS_EQUAL token kind exists."""
        assert TokenKind.LESS_EQUAL == "LESS_EQUAL"

    def test_greater(self) -> None:
        """Verify GREATER token kind exists."""
        assert TokenKind.GREATER == "GREATER"

    def test_greater_equal(self) -> None:
        """Verify GREATER_EQUAL token kind exists."""
        assert TokenKind.GREATER_EQUAL == "GREATER_EQUAL"

    # -- Logical --------------------------------------------------------------

    def test_and(self) -> None:
        """Verify AND token kind exists."""
        assert TokenKind.AND == "AND"

    def test_or(self) -> None:
        """Verify OR token kind exists."""
        assert TokenKind.OR == "OR"

    def test_not(self) -> None:
        """Verify NOT token kind exists."""
        assert TokenKind.NOT == "NOT"

    # -- Delimiters -----------------------------------------------------------

    def test_left_paren(self) -> None:
        """Verify LEFT_PAREN token kind exists."""
        assert TokenKind.LEFT_PAREN == "LEFT_PAREN"

    def test_right_paren(self) -> None:
        """Verify RIGHT_PAREN token kind exists."""
        assert TokenKind.RIGHT_PAREN == "RIGHT_PAREN"

    def test_left_brace(self) -> None:
        """Verify LEFT_BRACE token kind exists."""
        assert TokenKind.LEFT_BRACE == "LEFT_BRACE"

    def test_right_brace(self) -> None:
        """Verify RIGHT_BRACE token kind exists."""
        assert TokenKind.RIGHT_BRACE == "RIGHT_BRACE"

    def test_comma(self) -> None:
        """Verify COMMA token kind exists."""
        assert TokenKind.COMMA == "COMMA"

    def test_equal(self) -> None:
        """Verify EQUAL token kind exists."""
        assert TokenKind.EQUAL == "EQUAL"

    # -- Special --------------------------------------------------------------

    def test_newline(self) -> None:
        """Verify NEWLINE token kind exists."""
        assert TokenKind.NEWLINE == "NEWLINE"

    def test_eof(self) -> None:
        """Verify EOF token kind exists."""
        assert TokenKind.EOF == "EOF"

    # -- StrEnum behaviour ----------------------------------------------------

    def test_token_kind_is_string(self) -> None:
        """Verify TokenKind members are strings (StrEnum)."""
        assert isinstance(TokenKind.PLUS, str)

    def test_token_kind_string_value(self) -> None:
        """Verify TokenKind string value matches member name."""
        assert str(TokenKind.PLUS) == "PLUS"


class TestSourceLocation:
    """Verify the SourceLocation frozen dataclass."""

    def test_create_location(self) -> None:
        """Verify a SourceLocation can be created with line and column."""
        loc = SourceLocation(line=FIRST_LINE, column=FIRST_COLUMN)
        assert loc.line == FIRST_LINE
        assert loc.column == FIRST_COLUMN

    def test_location_is_frozen(self) -> None:
        """Verify SourceLocation is immutable."""
        loc = SourceLocation(line=FIRST_LINE, column=FIRST_COLUMN)
        with pytest.raises(dataclasses.FrozenInstanceError):
            loc.line = SECOND_LINE  # type: ignore[misc]

    def test_location_equality(self) -> None:
        """Verify two SourceLocations with the same values are equal."""
        loc1 = SourceLocation(line=FIRST_LINE, column=FIFTH_COLUMN)
        loc2 = SourceLocation(line=FIRST_LINE, column=FIFTH_COLUMN)
        assert loc1 == loc2

    def test_location_repr(self) -> None:
        """Verify SourceLocation has a readable repr."""
        loc = SourceLocation(line=SECOND_LINE, column=FIFTH_COLUMN)
        assert "line=2" in repr(loc)
        assert "column=5" in repr(loc)


class TestToken:
    """Verify the Token frozen dataclass."""

    def test_create_token(self) -> None:
        """Verify a Token can be created with kind, value, and location."""
        loc = SourceLocation(line=FIRST_LINE, column=FIRST_COLUMN)
        token = Token(kind=TokenKind.INTEGER, value="42", location=loc)
        assert token.kind == TokenKind.INTEGER
        assert token.value == "42"
        assert token.location == loc

    def test_token_is_frozen(self) -> None:
        """Verify Token is immutable."""
        loc = SourceLocation(line=FIRST_LINE, column=FIRST_COLUMN)
        token = Token(kind=TokenKind.PLUS, value="+", location=loc)
        with pytest.raises(dataclasses.FrozenInstanceError):
            token.kind = TokenKind.MINUS  # type: ignore[misc]

    def test_token_equality(self) -> None:
        """Verify two Tokens with the same values are equal."""
        loc = SourceLocation(line=FIRST_LINE, column=FIRST_COLUMN)
        t1 = Token(kind=TokenKind.LET, value="let", location=loc)
        t2 = Token(kind=TokenKind.LET, value="let", location=loc)
        assert t1 == t2

    def test_token_inequality_different_kind(self) -> None:
        """Verify Tokens with different kinds are not equal."""
        loc = SourceLocation(line=FIRST_LINE, column=FIRST_COLUMN)
        t1 = Token(kind=TokenKind.PLUS, value="+", location=loc)
        t2 = Token(kind=TokenKind.MINUS, value="-", location=loc)
        assert t1 != t2

    def test_eof_token(self) -> None:
        """Verify an EOF token can be created with empty value."""
        loc = SourceLocation(line=FIRST_LINE, column=FIRST_COLUMN)
        token = Token(kind=TokenKind.EOF, value="", location=loc)
        assert token.kind == TokenKind.EOF
        assert token.value == ""

    def test_string_token_preserves_value(self) -> None:
        """Verify string token preserves its literal value."""
        loc = SourceLocation(line=FIRST_LINE, column=FIRST_COLUMN)
        token = Token(kind=TokenKind.STRING, value="hello world", location=loc)
        assert token.value == "hello world"


class TestKeywords:
    """Verify the KEYWORDS mapping dict."""

    def test_keywords_count(self) -> None:
        """Verify the number of keywords in the mapping."""
        assert len(KEYWORDS) == KEYWORD_COUNT

    def test_const_keyword(self) -> None:
        """Verify 'const' maps to TokenKind.CONST."""
        assert KEYWORDS["const"] == TokenKind.CONST

    def test_let_keyword(self) -> None:
        """Verify 'let' maps to TokenKind.LET."""
        assert KEYWORDS["let"] == TokenKind.LET

    def test_if_keyword(self) -> None:
        """Verify 'if' maps to TokenKind.IF."""
        assert KEYWORDS["if"] == TokenKind.IF

    def test_else_keyword(self) -> None:
        """Verify 'else' maps to TokenKind.ELSE."""
        assert KEYWORDS["else"] == TokenKind.ELSE

    def test_while_keyword(self) -> None:
        """Verify 'while' maps to TokenKind.WHILE."""
        assert KEYWORDS["while"] == TokenKind.WHILE

    def test_for_keyword(self) -> None:
        """Verify 'for' maps to TokenKind.FOR."""
        assert KEYWORDS["for"] == TokenKind.FOR

    def test_in_keyword(self) -> None:
        """Verify 'in' maps to TokenKind.IN."""
        assert KEYWORDS["in"] == TokenKind.IN

    def test_fn_keyword(self) -> None:
        """Verify 'fn' maps to TokenKind.FN."""
        assert KEYWORDS["fn"] == TokenKind.FN

    def test_return_keyword(self) -> None:
        """Verify 'return' maps to TokenKind.RETURN."""
        assert KEYWORDS["return"] == TokenKind.RETURN

    def test_true_keyword(self) -> None:
        """Verify 'true' maps to TokenKind.TRUE."""
        assert KEYWORDS["true"] == TokenKind.TRUE

    def test_false_keyword(self) -> None:
        """Verify 'false' maps to TokenKind.FALSE."""
        assert KEYWORDS["false"] == TokenKind.FALSE

    def test_and_keyword(self) -> None:
        """Verify 'and' maps to TokenKind.AND."""
        assert KEYWORDS["and"] == TokenKind.AND

    def test_or_keyword(self) -> None:
        """Verify 'or' maps to TokenKind.OR."""
        assert KEYWORDS["or"] == TokenKind.OR

    def test_not_keyword(self) -> None:
        """Verify 'not' maps to TokenKind.NOT."""
        assert KEYWORDS["not"] == TokenKind.NOT

    def test_break_keyword(self) -> None:
        """Verify 'break' maps to TokenKind.BREAK."""
        assert KEYWORDS["break"] == TokenKind.BREAK

    def test_continue_keyword(self) -> None:
        """Verify 'continue' maps to TokenKind.CONTINUE."""
        assert KEYWORDS["continue"] == TokenKind.CONTINUE

    def test_try_keyword(self) -> None:
        """Verify 'try' maps to TokenKind.TRY."""
        assert KEYWORDS["try"] == TokenKind.TRY

    def test_catch_keyword(self) -> None:
        """Verify 'catch' maps to TokenKind.CATCH."""
        assert KEYWORDS["catch"] == TokenKind.CATCH

    def test_finally_keyword(self) -> None:
        """Verify 'finally' maps to TokenKind.FINALLY."""
        assert KEYWORDS["finally"] == TokenKind.FINALLY

    def test_throw_keyword(self) -> None:
        """Verify 'throw' maps to TokenKind.THROW."""
        assert KEYWORDS["throw"] == TokenKind.THROW

    def test_match_keyword(self) -> None:
        """Verify 'match' maps to TokenKind.MATCH."""
        assert KEYWORDS["match"] == TokenKind.MATCH

    def test_case_keyword(self) -> None:
        """Verify 'case' maps to TokenKind.CASE."""
        assert KEYWORDS["case"] == TokenKind.CASE

    def test_non_keyword_returns_none(self) -> None:
        """Verify a non-keyword string is not in the mapping."""
        assert "hello" not in KEYWORDS

    def test_keywords_are_all_lowercase(self) -> None:
        """Verify all keyword keys are lowercase."""
        assert all(k == k.lower() for k in KEYWORDS)
