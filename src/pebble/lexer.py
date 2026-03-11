"""Single-pass lexer for the Pebble language.

The lexer reads source text character by character and produces a list of
:class:`~pebble.tokens.Token` objects ready for the parser.
"""

from pebble.errors import LexerError
from pebble.tokens import KEYWORDS, SourceLocation, Token, TokenKind

__all__ = ["Lexer", "LexerError"]


# -- Single-character token mapping -------------------------------------------

_SINGLE_CHARS: dict[str, TokenKind] = {
    "+": TokenKind.PLUS,
    "-": TokenKind.MINUS,
    "*": TokenKind.STAR,
    "/": TokenKind.SLASH,
    "%": TokenKind.PERCENT,
    "(": TokenKind.LEFT_PAREN,
    ")": TokenKind.RIGHT_PAREN,
    "{": TokenKind.LEFT_BRACE,
    "}": TokenKind.RIGHT_BRACE,
    ",": TokenKind.COMMA,
}


class Lexer:
    """Single-pass scanner that converts source text into tokens.

    Usage::

        tokens = Lexer("let x = 42").tokenize()
    """

    def __init__(self, source: str) -> None:
        """Create a lexer for the given source text."""
        self._source = source
        self._pos = 0
        self._line = 1
        self._column = 1
        self._tokens: list[Token] = []

    # -- Public API -----------------------------------------------------------

    def tokenize(self) -> list[Token]:
        """Tokenize the entire source and return the token list.

        The list always ends with an ``EOF`` token.

        Raises:
            LexerError: If the source contains unterminated strings or
                unexpected characters.

        """
        while not self._at_end():
            self._scan_token()

        self._emit(TokenKind.EOF, "")
        return self._tokens

    # -- Scanning dispatch ----------------------------------------------------

    def _scan_token(self) -> None:
        """Scan the next token from the current position."""
        ch = self._peek()

        if ch == "\n":
            self._scan_newline()
        elif ch in " \t\r":
            self._advance()
        elif ch == "#":
            self._skip_comment()
        elif ch == '"':
            self._scan_string()
        elif ch.isdigit():
            self._scan_integer()
        elif ch.isalpha() or ch == "_":
            self._scan_identifier_or_keyword()
        elif ch in _SINGLE_CHARS:
            self._scan_single_char()
        elif ch == "=":
            self._scan_equal()
        elif ch == "!":
            self._scan_bang()
        elif ch == "<":
            self._scan_less()
        elif ch == ">":
            self._scan_greater()
        else:
            msg = f"Unexpected character '{ch}'"
            raise LexerError(msg, line=self._line, column=self._column)

    # -- Individual scanners --------------------------------------------------

    def _scan_newline(self) -> None:
        """Scan one or more consecutive newlines into a single NEWLINE token."""
        # Skip leading newlines at the very start (no tokens yet).
        if not self._tokens:
            while not self._at_end() and self._peek() == "\n":
                self._advance_newline()
            return

        # Skip if the last token is already a NEWLINE (collapse duplicates).
        if self._tokens[-1].kind == TokenKind.NEWLINE:
            self._advance_newline()
            return

        self._emit(TokenKind.NEWLINE, "\n")
        self._advance_newline()

        # Consume any additional consecutive newlines.
        while not self._at_end() and self._peek() == "\n":
            self._advance_newline()

    def _scan_string(self) -> None:
        """Scan a double-quoted string literal."""
        start_line = self._line
        start_col = self._column
        self._advance()  # skip opening quote

        value_chars: list[str] = []
        while not self._at_end() and self._peek() != '"':
            if self._peek() == "\n":
                value_chars.append("\n")
                self._advance_newline()
            else:
                value_chars.append(self._peek())
                self._advance()

        if self._at_end():
            msg = "Unterminated string"
            raise LexerError(msg, line=start_line, column=start_col)

        self._advance()  # skip closing quote
        value = "".join(value_chars)
        self._tokens.append(
            Token(
                kind=TokenKind.STRING,
                value=value,
                location=SourceLocation(line=start_line, column=start_col),
            )
        )

    def _scan_integer(self) -> None:
        """Scan an integer literal (sequence of digits)."""
        start_col = self._column
        digits: list[str] = []
        while not self._at_end() and self._peek().isdigit():
            digits.append(self._peek())
            self._advance()
        value = "".join(digits)
        self._tokens.append(
            Token(
                kind=TokenKind.INTEGER,
                value=value,
                location=SourceLocation(line=self._line, column=start_col),
            )
        )

    def _scan_identifier_or_keyword(self) -> None:
        """Scan an identifier or keyword."""
        start_col = self._column
        chars: list[str] = []
        while not self._at_end() and (self._peek().isalnum() or self._peek() == "_"):
            chars.append(self._peek())
            self._advance()
        value = "".join(chars)
        kind = KEYWORDS.get(value, TokenKind.IDENTIFIER)
        self._tokens.append(
            Token(
                kind=kind,
                value=value,
                location=SourceLocation(line=self._line, column=start_col),
            )
        )

    def _scan_single_char(self) -> None:
        """Scan a single-character token from the dispatch table."""
        ch = self._peek()
        kind = _SINGLE_CHARS[ch]
        self._emit(kind, ch)
        self._advance()

    def _scan_equal(self) -> None:
        """Scan '=' or '=='."""
        start_col = self._column
        self._advance()
        if not self._at_end() and self._peek() == "=":
            self._advance()
            self._tokens.append(
                Token(
                    kind=TokenKind.EQUAL_EQUAL,
                    value="==",
                    location=SourceLocation(line=self._line, column=start_col),
                )
            )
        else:
            self._tokens.append(
                Token(
                    kind=TokenKind.EQUAL,
                    value="=",
                    location=SourceLocation(line=self._line, column=start_col),
                )
            )

    def _scan_bang(self) -> None:
        """Scan '!=' or raise on lone '!'."""
        start_col = self._column
        self._advance()
        if not self._at_end() and self._peek() == "=":
            self._advance()
            self._tokens.append(
                Token(
                    kind=TokenKind.BANG_EQUAL,
                    value="!=",
                    location=SourceLocation(line=self._line, column=start_col),
                )
            )
        else:
            msg = "Unexpected character '!'"
            raise LexerError(msg, line=self._line, column=start_col)

    def _scan_less(self) -> None:
        """Scan '<' or '<='."""
        start_col = self._column
        self._advance()
        if not self._at_end() and self._peek() == "=":
            self._advance()
            self._tokens.append(
                Token(
                    kind=TokenKind.LESS_EQUAL,
                    value="<=",
                    location=SourceLocation(line=self._line, column=start_col),
                )
            )
        else:
            self._tokens.append(
                Token(
                    kind=TokenKind.LESS,
                    value="<",
                    location=SourceLocation(line=self._line, column=start_col),
                )
            )

    def _scan_greater(self) -> None:
        """Scan '>' or '>='."""
        start_col = self._column
        self._advance()
        if not self._at_end() and self._peek() == "=":
            self._advance()
            self._tokens.append(
                Token(
                    kind=TokenKind.GREATER_EQUAL,
                    value=">=",
                    location=SourceLocation(line=self._line, column=start_col),
                )
            )
        else:
            self._tokens.append(
                Token(
                    kind=TokenKind.GREATER,
                    value=">",
                    location=SourceLocation(line=self._line, column=start_col),
                )
            )

    # -- Comment handling -----------------------------------------------------

    def _skip_comment(self) -> None:
        """Skip a ``#`` comment until end of line."""
        while not self._at_end() and self._peek() != "\n":
            self._advance()

    # -- Character helpers ----------------------------------------------------

    def _peek(self) -> str:
        """Return the current character without advancing."""
        return self._source[self._pos]

    def _advance(self) -> None:
        """Advance the position by one character (not a newline)."""
        self._pos += 1
        self._column += 1

    def _advance_newline(self) -> None:
        """Advance past a newline character, updating line/column."""
        self._pos += 1
        self._line += 1
        self._column = 1

    def _at_end(self) -> bool:
        """Return True if all characters have been consumed."""
        return self._pos >= len(self._source)

    def _emit(self, kind: TokenKind, value: str) -> None:
        """Append a token at the current location."""
        self._tokens.append(
            Token(kind=kind, value=value, location=SourceLocation(self._line, self._column))
        )
