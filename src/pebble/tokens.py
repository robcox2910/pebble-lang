"""Token types, source locations, and keyword mapping for the Pebble language.

This module defines the building blocks of lexical analysis:

- ``TokenKind`` — every category of token the lexer can produce
- ``SourceLocation`` — a line/column position in source code
- ``Token`` — a classified piece of source text with its location
- ``KEYWORDS`` — a mapping from keyword strings to their token kinds
"""

from dataclasses import dataclass
from enum import StrEnum


class TokenKind(StrEnum):
    """Every category of token the Pebble lexer can produce."""

    # -- Literals -------------------------------------------------------------
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    STRING = "STRING"
    STRING_START = "STRING_START"
    STRING_MIDDLE = "STRING_MIDDLE"
    STRING_END = "STRING_END"
    IDENTIFIER = "IDENTIFIER"

    # -- Keywords -------------------------------------------------------------
    CONST = "CONST"
    LET = "LET"
    IF = "IF"
    ELSE = "ELSE"
    WHILE = "WHILE"
    FOR = "FOR"
    IN = "IN"
    FN = "FN"
    RETURN = "RETURN"
    BREAK = "BREAK"
    CONTINUE = "CONTINUE"
    TRY = "TRY"
    CATCH = "CATCH"
    FINALLY = "FINALLY"
    THROW = "THROW"
    MATCH = "MATCH"
    CASE = "CASE"
    TRUE = "TRUE"
    FALSE = "FALSE"

    # -- Operators ------------------------------------------------------------
    PLUS = "PLUS"
    MINUS = "MINUS"
    STAR = "STAR"
    STAR_STAR = "STAR_STAR"
    SLASH = "SLASH"
    SLASH_SLASH = "SLASH_SLASH"
    PERCENT = "PERCENT"

    # -- Bitwise --------------------------------------------------------------
    AMPERSAND = "AMPERSAND"
    PIPE = "PIPE"
    CARET = "CARET"
    TILDE = "TILDE"
    LESS_LESS = "LESS_LESS"
    GREATER_GREATER = "GREATER_GREATER"

    # -- Comparison -----------------------------------------------------------
    EQUAL_EQUAL = "EQUAL_EQUAL"
    BANG_EQUAL = "BANG_EQUAL"
    LESS = "LESS"
    LESS_EQUAL = "LESS_EQUAL"
    GREATER = "GREATER"
    GREATER_EQUAL = "GREATER_EQUAL"

    # -- Logical --------------------------------------------------------------
    AND = "AND"
    OR = "OR"
    NOT = "NOT"

    # -- Delimiters -----------------------------------------------------------
    LEFT_PAREN = "LEFT_PAREN"
    RIGHT_PAREN = "RIGHT_PAREN"
    LEFT_BRACE = "LEFT_BRACE"
    RIGHT_BRACE = "RIGHT_BRACE"
    LEFT_BRACKET = "LEFT_BRACKET"
    RIGHT_BRACKET = "RIGHT_BRACKET"
    COMMA = "COMMA"
    COLON = "COLON"
    DOT = "DOT"
    EQUAL = "EQUAL"

    # -- Special --------------------------------------------------------------
    NEWLINE = "NEWLINE"
    EOF = "EOF"


@dataclass(frozen=True)
class SourceLocation:
    """A line/column position in source code.

    Both ``line`` and ``column`` are 1-based to match how editors display
    positions.
    """

    line: int
    column: int


@dataclass(frozen=True)
class Token:
    """A classified piece of source text with its location.

    Attributes:
        kind: The category of this token.
        value: The raw text that produced this token.
        location: Where the token starts in the source.

    """

    kind: TokenKind
    value: str
    location: SourceLocation


KEYWORDS: dict[str, TokenKind] = {
    "const": TokenKind.CONST,
    "let": TokenKind.LET,
    "if": TokenKind.IF,
    "else": TokenKind.ELSE,
    "while": TokenKind.WHILE,
    "for": TokenKind.FOR,
    "in": TokenKind.IN,
    "fn": TokenKind.FN,
    "return": TokenKind.RETURN,
    "break": TokenKind.BREAK,
    "continue": TokenKind.CONTINUE,
    "try": TokenKind.TRY,
    "catch": TokenKind.CATCH,
    "finally": TokenKind.FINALLY,
    "throw": TokenKind.THROW,
    "match": TokenKind.MATCH,
    "case": TokenKind.CASE,
    "true": TokenKind.TRUE,
    "false": TokenKind.FALSE,
    "and": TokenKind.AND,
    "or": TokenKind.OR,
    "not": TokenKind.NOT,
}
