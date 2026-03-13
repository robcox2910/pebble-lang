"""Tests for the Pebble lexer."""

import pytest

from pebble.lexer import Lexer, LexerError
from pebble.tokens import TokenKind

# -- Helpers ------------------------------------------------------------------


def _kinds(source: str) -> list[TokenKind]:
    """Return just the token kinds for *source* (excluding EOF)."""
    tokens = Lexer(source).tokenize()
    return [t.kind for t in tokens if t.kind != TokenKind.EOF]


def _kind_value_pairs(source: str) -> list[tuple[TokenKind, str]]:
    """Return (kind, value) pairs for *source* (excluding EOF)."""
    tokens = Lexer(source).tokenize()
    return [(t.kind, t.value) for t in tokens if t.kind != TokenKind.EOF]


# -- Named constants ----------------------------------------------------------

FIRST_LINE = 1
SECOND_LINE = 2
THIRD_LINE = 3
FIRST_COLUMN = 1
SECOND_COLUMN = 2
THIRD_COLUMN = 3
FOURTH_COLUMN = 4
FIFTH_COLUMN = 5
SIXTH_COLUMN = 6
SEVENTH_COLUMN = 7
EIGHTH_COLUMN = 8
NINTH_COLUMN = 9


class TestLexerIntegers:
    """Verify tokenization of integer literals."""

    def test_single_digit(self) -> None:
        """Verify a single digit is tokenized as INTEGER."""
        assert _kind_value_pairs("5") == [(TokenKind.INTEGER, "5")]

    def test_multi_digit(self) -> None:
        """Verify a multi-digit number is tokenized as INTEGER."""
        assert _kind_value_pairs("42") == [(TokenKind.INTEGER, "42")]

    def test_zero(self) -> None:
        """Verify zero is tokenized as INTEGER."""
        assert _kind_value_pairs("0") == [(TokenKind.INTEGER, "0")]

    def test_large_number(self) -> None:
        """Verify a large number is tokenized as INTEGER."""
        assert _kind_value_pairs("123456") == [(TokenKind.INTEGER, "123456")]


class TestLexerStrings:
    """Verify tokenization of string literals."""

    def test_simple_string(self) -> None:
        """Verify a simple double-quoted string is tokenized."""
        assert _kind_value_pairs('"hello"') == [(TokenKind.STRING, "hello")]

    def test_empty_string(self) -> None:
        """Verify an empty string is tokenized."""
        assert _kind_value_pairs('""') == [(TokenKind.STRING, "")]

    def test_string_with_spaces(self) -> None:
        """Verify a string with spaces preserves its content."""
        assert _kind_value_pairs('"hello world"') == [(TokenKind.STRING, "hello world")]

    def test_string_with_digits(self) -> None:
        """Verify a string containing digits is tokenized as STRING."""
        assert _kind_value_pairs('"abc123"') == [(TokenKind.STRING, "abc123")]

    def test_string_with_newline(self) -> None:
        """Verify a string spanning multiple lines preserves the newline."""
        assert _kind_value_pairs('"line1\nline2"') == [(TokenKind.STRING, "line1\nline2")]

    def test_unterminated_string_raises(self) -> None:
        """Verify an unterminated string raises LexerError."""
        with pytest.raises(LexerError, match="Unterminated string"):
            Lexer('"hello').tokenize()

    def test_unterminated_string_at_eof(self) -> None:
        """Verify an unterminated string at EOF raises LexerError."""
        with pytest.raises(LexerError, match="Unterminated string"):
            Lexer('"').tokenize()


class TestLexerIdentifiersAndKeywords:
    """Verify tokenization of identifiers and keyword recognition."""

    def test_simple_identifier(self) -> None:
        """Verify a simple name is tokenized as IDENTIFIER."""
        assert _kind_value_pairs("foo") == [(TokenKind.IDENTIFIER, "foo")]

    def test_identifier_with_underscore(self) -> None:
        """Verify underscored names are tokenized as IDENTIFIER."""
        assert _kind_value_pairs("my_var") == [(TokenKind.IDENTIFIER, "my_var")]

    def test_identifier_starting_with_underscore(self) -> None:
        """Verify names starting with underscore are IDENTIFIER."""
        assert _kind_value_pairs("_private") == [(TokenKind.IDENTIFIER, "_private")]

    def test_identifier_with_digits(self) -> None:
        """Verify names containing digits are IDENTIFIER."""
        assert _kind_value_pairs("x1") == [(TokenKind.IDENTIFIER, "x1")]

    def test_keyword_let(self) -> None:
        """Verify 'let' is tokenized as LET keyword."""
        assert _kinds("let") == [TokenKind.LET]

    def test_keyword_if(self) -> None:
        """Verify 'if' is tokenized as IF keyword."""
        assert _kinds("if") == [TokenKind.IF]

    def test_keyword_else(self) -> None:
        """Verify 'else' is tokenized as ELSE keyword."""
        assert _kinds("else") == [TokenKind.ELSE]

    def test_keyword_while(self) -> None:
        """Verify 'while' is tokenized as WHILE keyword."""
        assert _kinds("while") == [TokenKind.WHILE]

    def test_keyword_for(self) -> None:
        """Verify 'for' is tokenized as FOR keyword."""
        assert _kinds("for") == [TokenKind.FOR]

    def test_keyword_in(self) -> None:
        """Verify 'in' is tokenized as IN keyword."""
        assert _kinds("in") == [TokenKind.IN]

    def test_keyword_fn(self) -> None:
        """Verify 'fn' is tokenized as FN keyword."""
        assert _kinds("fn") == [TokenKind.FN]

    def test_keyword_return(self) -> None:
        """Verify 'return' is tokenized as RETURN keyword."""
        assert _kinds("return") == [TokenKind.RETURN]

    def test_keyword_true(self) -> None:
        """Verify 'true' is tokenized as TRUE keyword."""
        assert _kinds("true") == [TokenKind.TRUE]

    def test_keyword_false(self) -> None:
        """Verify 'false' is tokenized as FALSE keyword."""
        assert _kinds("false") == [TokenKind.FALSE]

    def test_keyword_and(self) -> None:
        """Verify 'and' is tokenized as AND keyword."""
        assert _kinds("and") == [TokenKind.AND]

    def test_keyword_or(self) -> None:
        """Verify 'or' is tokenized as OR keyword."""
        assert _kinds("or") == [TokenKind.OR]

    def test_keyword_not(self) -> None:
        """Verify 'not' is tokenized as NOT keyword."""
        assert _kinds("not") == [TokenKind.NOT]

    def test_keyword_break(self) -> None:
        """Verify 'break' is tokenized as BREAK keyword."""
        assert _kinds("break") == [TokenKind.BREAK]

    def test_keyword_continue(self) -> None:
        """Verify 'continue' is tokenized as CONTINUE keyword."""
        assert _kinds("continue") == [TokenKind.CONTINUE]

    def test_break_cannot_be_identifier(self) -> None:
        """Verify 'break' is reserved and tokenizes as BREAK, not IDENTIFIER."""
        tokens = Lexer("break").tokenize()
        assert tokens[0].kind == TokenKind.BREAK

    def test_continue_cannot_be_identifier(self) -> None:
        """Verify 'continue' is reserved and tokenizes as CONTINUE, not IDENTIFIER."""
        tokens = Lexer("continue").tokenize()
        assert tokens[0].kind == TokenKind.CONTINUE

    def test_keyword_prefix_is_identifier(self) -> None:
        """Verify a word starting with a keyword is still an IDENTIFIER."""
        assert _kinds("letter") == [TokenKind.IDENTIFIER]

    def test_keyword_suffix_is_identifier(self) -> None:
        """Verify a word ending with a keyword is still an IDENTIFIER."""
        assert _kinds("notify") == [TokenKind.IDENTIFIER]


class TestLexerOperators:
    """Verify tokenization of operators."""

    def test_plus(self) -> None:
        """Verify '+' is tokenized as PLUS."""
        assert _kind_value_pairs("+") == [(TokenKind.PLUS, "+")]

    def test_minus(self) -> None:
        """Verify '-' is tokenized as MINUS."""
        assert _kind_value_pairs("-") == [(TokenKind.MINUS, "-")]

    def test_star(self) -> None:
        """Verify '*' is tokenized as STAR."""
        assert _kind_value_pairs("*") == [(TokenKind.STAR, "*")]

    def test_slash(self) -> None:
        """Verify '/' is tokenized as SLASH."""
        assert _kind_value_pairs("/") == [(TokenKind.SLASH, "/")]

    def test_percent(self) -> None:
        """Verify '%' is tokenized as PERCENT."""
        assert _kind_value_pairs("%") == [(TokenKind.PERCENT, "%")]


class TestLexerComparisons:
    """Verify tokenization of comparison operators."""

    def test_equal_equal(self) -> None:
        """Verify '==' is tokenized as EQUAL_EQUAL."""
        assert _kind_value_pairs("==") == [(TokenKind.EQUAL_EQUAL, "==")]

    def test_bang_equal(self) -> None:
        """Verify '!=' is tokenized as BANG_EQUAL."""
        assert _kind_value_pairs("!=") == [(TokenKind.BANG_EQUAL, "!=")]

    def test_less(self) -> None:
        """Verify '<' is tokenized as LESS."""
        assert _kind_value_pairs("<") == [(TokenKind.LESS, "<")]

    def test_less_equal(self) -> None:
        """Verify '<=' is tokenized as LESS_EQUAL."""
        assert _kind_value_pairs("<=") == [(TokenKind.LESS_EQUAL, "<=")]

    def test_greater(self) -> None:
        """Verify '>' is tokenized as GREATER."""
        assert _kind_value_pairs(">") == [(TokenKind.GREATER, ">")]

    def test_greater_equal(self) -> None:
        """Verify '>=' is tokenized as GREATER_EQUAL."""
        assert _kind_value_pairs(">=") == [(TokenKind.GREATER_EQUAL, ">=")]

    def test_single_equal(self) -> None:
        """Verify '=' is tokenized as EQUAL (assignment, not comparison)."""
        assert _kind_value_pairs("=") == [(TokenKind.EQUAL, "=")]


class TestLexerDelimiters:
    """Verify tokenization of delimiters."""

    def test_left_paren(self) -> None:
        """Verify '(' is tokenized as LEFT_PAREN."""
        assert _kind_value_pairs("(") == [(TokenKind.LEFT_PAREN, "(")]

    def test_right_paren(self) -> None:
        """Verify ')' is tokenized as RIGHT_PAREN."""
        assert _kind_value_pairs(")") == [(TokenKind.RIGHT_PAREN, ")")]

    def test_left_brace(self) -> None:
        """Verify '{' is tokenized as LEFT_BRACE."""
        assert _kind_value_pairs("{") == [(TokenKind.LEFT_BRACE, "{")]

    def test_right_brace(self) -> None:
        """Verify '}' is tokenized as RIGHT_BRACE."""
        assert _kind_value_pairs("}") == [(TokenKind.RIGHT_BRACE, "}")]

    def test_comma(self) -> None:
        """Verify ',' is tokenized as COMMA."""
        assert _kind_value_pairs(",") == [(TokenKind.COMMA, ",")]


class TestLexerWhitespaceAndNewlines:
    """Verify whitespace and newline handling."""

    def test_spaces_are_skipped(self) -> None:
        """Verify spaces between tokens are ignored."""
        assert _kinds("1 + 2") == [TokenKind.INTEGER, TokenKind.PLUS, TokenKind.INTEGER]

    def test_tabs_are_skipped(self) -> None:
        """Verify tabs are ignored."""
        assert _kinds("1\t+\t2") == [TokenKind.INTEGER, TokenKind.PLUS, TokenKind.INTEGER]

    def test_newline_produces_token(self) -> None:
        """Verify a newline produces a NEWLINE token."""
        assert _kinds("1\n2") == [
            TokenKind.INTEGER,
            TokenKind.NEWLINE,
            TokenKind.INTEGER,
        ]

    def test_multiple_newlines_collapse(self) -> None:
        """Verify consecutive newlines produce a single NEWLINE token."""
        assert _kinds("1\n\n\n2") == [
            TokenKind.INTEGER,
            TokenKind.NEWLINE,
            TokenKind.INTEGER,
        ]

    def test_trailing_newlines_are_ignored(self) -> None:
        """Verify trailing newlines don't produce extra tokens."""
        assert _kinds("1\n") == [TokenKind.INTEGER, TokenKind.NEWLINE]

    def test_leading_newlines_are_ignored(self) -> None:
        """Verify leading newlines are skipped."""
        assert _kinds("\n\n1") == [TokenKind.INTEGER]

    def test_empty_source(self) -> None:
        """Verify empty source produces only EOF."""
        tokens = Lexer("").tokenize()
        assert len(tokens) == FIRST_LINE
        assert tokens[0].kind == TokenKind.EOF


class TestLexerComments:
    """Verify comment handling."""

    def test_comment_skips_rest_of_line(self) -> None:
        """Verify a # comment ignores everything until end of line."""
        assert _kinds("# this is a comment") == []

    def test_comment_after_code(self) -> None:
        """Verify a comment after code doesn't affect the code tokens."""
        assert _kinds("42 # the answer") == [TokenKind.INTEGER]

    def test_code_after_comment_line(self) -> None:
        """Verify code on the next line after a comment is tokenized."""
        assert _kinds("# comment\n42") == [TokenKind.INTEGER]

    def test_comment_between_code_lines(self) -> None:
        """Verify a comment between code lines preserves the newline."""
        assert _kinds("1\n# comment\n2") == [
            TokenKind.INTEGER,
            TokenKind.NEWLINE,
            TokenKind.INTEGER,
        ]


class TestLexerSourceLocations:
    """Verify line/column tracking."""

    def test_first_token_location(self) -> None:
        """Verify the first token starts at line 1, column 1."""
        tokens = Lexer("42").tokenize()
        assert tokens[0].location.line == FIRST_LINE
        assert tokens[0].location.column == FIRST_COLUMN

    def test_second_token_column(self) -> None:
        """Verify the second token has the correct column."""
        tokens = Lexer("1 + 2").tokenize()
        plus_token = tokens[1]
        assert plus_token.kind == TokenKind.PLUS
        assert plus_token.location.column == THIRD_COLUMN

    def test_third_token_column(self) -> None:
        """Verify the third token has the correct column."""
        tokens = Lexer("1 + 2").tokenize()
        two_token = tokens[2]
        assert two_token.kind == TokenKind.INTEGER
        assert two_token.location.column == FIFTH_COLUMN

    def test_second_line_location(self) -> None:
        """Verify tokens on the second line have line=2, column=1."""
        tokens = Lexer("1\n2").tokenize()
        # tokens: INTEGER(1), NEWLINE, INTEGER(2), EOF
        two_token = tokens[2]
        assert two_token.kind == TokenKind.INTEGER
        assert two_token.location.line == SECOND_LINE
        assert two_token.location.column == FIRST_COLUMN

    def test_eof_location(self) -> None:
        """Verify the EOF token has the correct location."""
        tokens = Lexer("ab").tokenize()
        eof = tokens[-1]
        assert eof.kind == TokenKind.EOF
        assert eof.location.line == FIRST_LINE
        assert eof.location.column == THIRD_COLUMN

    def test_string_token_location(self) -> None:
        """Verify string token location points to the opening quote."""
        tokens = Lexer('"hi"').tokenize()
        assert tokens[0].location.line == FIRST_LINE
        assert tokens[0].location.column == FIRST_COLUMN

    def test_keyword_location_after_spaces(self) -> None:
        """Verify a keyword after spaces has the correct column."""
        tokens = Lexer("   let").tokenize()
        assert tokens[0].kind == TokenKind.LET
        assert tokens[0].location.column == FOURTH_COLUMN


class TestLexerErrors:
    """Verify error handling for invalid input."""

    def test_unexpected_character_raises(self) -> None:
        """Verify an unexpected character raises LexerError."""
        with pytest.raises(LexerError, match="Unexpected character"):
            Lexer("@").tokenize()

    def test_lone_bang_raises(self) -> None:
        """Verify a lone '!' (not followed by '=') raises LexerError."""
        with pytest.raises(LexerError, match="Unexpected character"):
            Lexer("!").tokenize()

    def test_error_includes_line_and_column(self) -> None:
        """Verify the LexerError includes the location of the bad character."""
        with pytest.raises(LexerError) as exc_info:
            Lexer("let x = @").tokenize()
        error = exc_info.value
        assert error.line == FIRST_LINE
        assert error.column == NINTH_COLUMN

    def test_unterminated_string_location(self) -> None:
        """Verify unterminated string error includes the opening quote location."""
        with pytest.raises(LexerError) as exc_info:
            Lexer('"hello').tokenize()
        error = exc_info.value
        assert error.line == FIRST_LINE
        assert error.column == FIRST_COLUMN


class TestLexerEof:
    """Verify EOF token behaviour."""

    def test_always_ends_with_eof(self) -> None:
        """Verify the token list always ends with an EOF token."""
        tokens = Lexer("42").tokenize()
        assert tokens[-1].kind == TokenKind.EOF

    def test_empty_source_has_eof(self) -> None:
        """Verify empty source produces exactly one EOF token."""
        tokens = Lexer("").tokenize()
        assert len(tokens) == FIRST_LINE
        assert tokens[0].kind == TokenKind.EOF


class TestLexerEdgeCases:
    """Verify edge-case inputs are handled correctly."""

    def test_leading_zero_integer(self) -> None:
        """Verify '007' is tokenized as a single INTEGER."""
        assert _kind_value_pairs("007") == [(TokenKind.INTEGER, "007")]

    def test_triple_equals_splits_correctly(self) -> None:
        """Verify '===' is tokenized as EQUAL_EQUAL + EQUAL."""
        assert _kind_value_pairs("===") == [
            (TokenKind.EQUAL_EQUAL, "=="),
            (TokenKind.EQUAL, "="),
        ]

    def test_bang_equal_equal_splits_correctly(self) -> None:
        """Verify '!==' is tokenized as BANG_EQUAL + EQUAL."""
        assert _kind_value_pairs("!==") == [
            (TokenKind.BANG_EQUAL, "!="),
            (TokenKind.EQUAL, "="),
        ]

    def test_less_equal_equal_splits_correctly(self) -> None:
        """Verify '<==' is tokenized as LESS_EQUAL + EQUAL."""
        assert _kind_value_pairs("<==") == [
            (TokenKind.LESS_EQUAL, "<="),
            (TokenKind.EQUAL, "="),
        ]

    def test_greater_equal_equal_splits_correctly(self) -> None:
        """Verify '>==' is tokenized as GREATER_EQUAL + EQUAL."""
        assert _kind_value_pairs(">==") == [
            (TokenKind.GREATER_EQUAL, ">="),
            (TokenKind.EQUAL, "="),
        ]

    def test_windows_line_endings(self) -> None:
        r"""Verify '\r\n' line endings are handled correctly."""
        assert _kinds("1\r\n2") == [
            TokenKind.INTEGER,
            TokenKind.NEWLINE,
            TokenKind.INTEGER,
        ]

    def test_keywords_are_case_sensitive(self) -> None:
        """Verify uppercase variants of keywords are identifiers."""
        assert _kinds("Let") == [TokenKind.IDENTIFIER]
        assert _kinds("IF") == [TokenKind.IDENTIFIER]
        assert _kinds("While") == [TokenKind.IDENTIFIER]

    def test_comment_with_special_characters(self) -> None:
        """Verify comments with special characters are skipped."""
        assert _kinds("42 # @#$%^&*()") == [TokenKind.INTEGER]

    def test_comment_at_eof_without_newline(self) -> None:
        """Verify a comment at EOF without trailing newline works."""
        assert _kinds("42 # end") == [TokenKind.INTEGER]


class TestLexerCompoundExpressions:
    """Verify tokenization of realistic multi-token expressions."""

    def test_let_declaration(self) -> None:
        """Verify 'let x = 42' tokenizes with correct kinds and values."""
        assert _kind_value_pairs("let x = 42") == [
            (TokenKind.LET, "let"),
            (TokenKind.IDENTIFIER, "x"),
            (TokenKind.EQUAL, "="),
            (TokenKind.INTEGER, "42"),
        ]

    def test_arithmetic_expression(self) -> None:
        """Verify '1 + 2 * 3' tokenizes correctly."""
        assert _kinds("1 + 2 * 3") == [
            TokenKind.INTEGER,
            TokenKind.PLUS,
            TokenKind.INTEGER,
            TokenKind.STAR,
            TokenKind.INTEGER,
        ]

    def test_function_call(self) -> None:
        """Verify 'print(x)' tokenizes correctly."""
        assert _kinds("print(x)") == [
            TokenKind.IDENTIFIER,
            TokenKind.LEFT_PAREN,
            TokenKind.IDENTIFIER,
            TokenKind.RIGHT_PAREN,
        ]

    def test_comparison_expression(self) -> None:
        """Verify 'x >= 10' tokenizes correctly."""
        assert _kinds("x >= 10") == [
            TokenKind.IDENTIFIER,
            TokenKind.GREATER_EQUAL,
            TokenKind.INTEGER,
        ]

    def test_if_block(self) -> None:
        """Verify a multi-line if block tokenizes correctly."""
        source = "if x > 0 {\n    print(x)\n}"
        assert _kinds(source) == [
            TokenKind.IF,
            TokenKind.IDENTIFIER,
            TokenKind.GREATER,
            TokenKind.INTEGER,
            TokenKind.LEFT_BRACE,
            TokenKind.NEWLINE,
            TokenKind.IDENTIFIER,
            TokenKind.LEFT_PAREN,
            TokenKind.IDENTIFIER,
            TokenKind.RIGHT_PAREN,
            TokenKind.NEWLINE,
            TokenKind.RIGHT_BRACE,
        ]

    def test_function_definition(self) -> None:
        """Verify 'fn add(a, b) {' tokenizes correctly."""
        assert _kinds("fn add(a, b) {") == [
            TokenKind.FN,
            TokenKind.IDENTIFIER,
            TokenKind.LEFT_PAREN,
            TokenKind.IDENTIFIER,
            TokenKind.COMMA,
            TokenKind.IDENTIFIER,
            TokenKind.RIGHT_PAREN,
            TokenKind.LEFT_BRACE,
        ]

    def test_logical_expression(self) -> None:
        """Verify 'x > 0 and not done' tokenizes correctly."""
        assert _kinds("x > 0 and not done") == [
            TokenKind.IDENTIFIER,
            TokenKind.GREATER,
            TokenKind.INTEGER,
            TokenKind.AND,
            TokenKind.NOT,
            TokenKind.IDENTIFIER,
        ]

    def test_string_in_expression(self) -> None:
        """Verify 'let msg = "hi"' tokenizes correctly."""
        assert _kinds('let msg = "hi"') == [
            TokenKind.LET,
            TokenKind.IDENTIFIER,
            TokenKind.EQUAL,
            TokenKind.STRING,
        ]

    def test_multiline_program(self) -> None:
        """Verify a multi-line program tokenizes correctly."""
        source = "let x = 1\nlet y = 2\nprint(x + y)"
        assert _kinds(source) == [
            TokenKind.LET,
            TokenKind.IDENTIFIER,
            TokenKind.EQUAL,
            TokenKind.INTEGER,
            TokenKind.NEWLINE,
            TokenKind.LET,
            TokenKind.IDENTIFIER,
            TokenKind.EQUAL,
            TokenKind.INTEGER,
            TokenKind.NEWLINE,
            TokenKind.IDENTIFIER,
            TokenKind.LEFT_PAREN,
            TokenKind.IDENTIFIER,
            TokenKind.PLUS,
            TokenKind.IDENTIFIER,
            TokenKind.RIGHT_PAREN,
        ]
