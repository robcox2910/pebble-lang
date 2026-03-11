"""Recursive-descent parser with Pratt-style precedence climbing.

The parser consumes a list of :class:`~pebble.tokens.Token` objects produced
by the lexer and builds an :class:`~pebble.ast_nodes.Program` AST.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Never

if TYPE_CHECKING:
    from collections.abc import Callable

from pebble.ast_nodes import (
    Assignment,
    BinaryOp,
    BooleanLiteral,
    Expression,
    Identifier,
    IfStatement,
    IntegerLiteral,
    PrintStatement,
    Program,
    Reassignment,
    Statement,
    StringLiteral,
    UnaryOp,
    WhileLoop,
)
from pebble.errors import ParseError
from pebble.tokens import Token, TokenKind

# ---------------------------------------------------------------------------
# Precedence levels (higher number = tighter binding)
# ---------------------------------------------------------------------------

_PREFIX_PRECEDENCE = 7  # unary -, not

_INFIX_PRECEDENCE: dict[TokenKind, int] = {
    # Logical
    TokenKind.OR: 1,
    TokenKind.AND: 2,
    # Comparison
    TokenKind.EQUAL_EQUAL: 3,
    TokenKind.BANG_EQUAL: 3,
    TokenKind.LESS: 4,
    TokenKind.LESS_EQUAL: 4,
    TokenKind.GREATER: 4,
    TokenKind.GREATER_EQUAL: 4,
    # Arithmetic
    TokenKind.PLUS: 5,
    TokenKind.MINUS: 5,
    TokenKind.STAR: 6,
    TokenKind.SLASH: 6,
    TokenKind.PERCENT: 6,
}

_OPERATOR_TEXT: dict[TokenKind, str] = {
    TokenKind.PLUS: "+",
    TokenKind.MINUS: "-",
    TokenKind.STAR: "*",
    TokenKind.SLASH: "/",
    TokenKind.PERCENT: "%",
    TokenKind.EQUAL_EQUAL: "==",
    TokenKind.BANG_EQUAL: "!=",
    TokenKind.LESS: "<",
    TokenKind.LESS_EQUAL: "<=",
    TokenKind.GREATER: ">",
    TokenKind.GREATER_EQUAL: ">=",
    TokenKind.AND: "and",
    TokenKind.OR: "or",
}


class Parser:
    r"""Recursive-descent parser that builds an AST from a token list.

    Usage::

        tokens = Lexer("let x = 42\nprint(x)").tokenize()
        program = Parser(tokens).parse()
    """

    def __init__(self, tokens: list[Token]) -> None:
        """Create a parser for the given token list."""
        self._tokens = tokens
        self._pos = 0

    # -- Public API -----------------------------------------------------------

    def parse(self) -> Program:
        """Parse the full token stream into a Program AST."""
        self._skip_newlines()
        statements: list[Statement] = []
        while not self._at_end():
            statements.append(self._parse_statement())
            self._skip_newlines()
        return Program(statements=statements)

    def parse_expression(self) -> Expression:
        """Parse and return a single expression."""
        return self._parse_precedence(min_precedence=0)

    # -- Statement parsing ----------------------------------------------------

    def _parse_statement(self) -> Statement:
        """Parse a single statement."""
        kind = self._peek().kind

        if kind == TokenKind.LET:
            return self._parse_let()
        if kind == TokenKind.IF:
            return self._parse_if()
        if kind == TokenKind.WHILE:
            return self._parse_while()

        # Check for print(expr) — 'print' is an identifier, not a keyword
        if kind == TokenKind.IDENTIFIER and self._peek().value == "print":
            return self._parse_print()

        # Check for reassignment: identifier followed by '='
        if kind == TokenKind.IDENTIFIER and self._peek_next_kind() == TokenKind.EQUAL:
            return self._parse_reassignment()

        # Fall through to expression statement
        return self._parse_expression_statement()

    def _parse_let(self) -> Assignment:
        """Parse a ``let name = expr`` declaration."""
        let_token = self._advance()  # consume 'let'
        name_token = self._expect(TokenKind.IDENTIFIER, "Expected variable name after 'let'")
        self._expect(TokenKind.EQUAL, "Expected '=' after variable name")
        value = self.parse_expression()
        self._consume_newline()
        return Assignment(name=name_token.value, value=value, location=let_token.location)

    def _parse_reassignment(self) -> Reassignment:
        """Parse a ``name = expr`` reassignment."""
        name_token = self._advance()  # consume identifier
        self._advance()  # consume '='
        value = self.parse_expression()
        self._consume_newline()
        return Reassignment(name=name_token.value, value=value, location=name_token.location)

    def _parse_print(self) -> PrintStatement:
        """Parse a ``print(expr)`` statement."""
        print_token = self._advance()  # consume 'print'
        self._expect(TokenKind.LEFT_PAREN, "Expected '(' after 'print'")
        expr = self.parse_expression()
        self._expect(TokenKind.RIGHT_PAREN, "Expected ')' after print argument")
        self._consume_newline()
        return PrintStatement(expression=expr, location=print_token.location)

    def _parse_if(self) -> IfStatement:
        """Parse an ``if cond { body } [else { body }]`` statement."""
        if_token = self._advance()  # consume 'if'
        condition = self.parse_expression()
        body = self._parse_block()

        else_body: list[Statement] | None = None
        if not self._at_end() and self._peek().kind == TokenKind.ELSE:
            self._advance()  # consume 'else'
            else_body = self._parse_block()

        return IfStatement(
            condition=condition,
            body=body,
            else_body=else_body,
            location=if_token.location,
        )

    def _parse_while(self) -> WhileLoop:
        """Parse a ``while cond { body }`` loop."""
        while_token = self._advance()  # consume 'while'
        condition = self.parse_expression()
        body = self._parse_block()
        return WhileLoop(condition=condition, body=body, location=while_token.location)

    def _parse_block(self) -> list[Statement]:
        """Parse a ``{ stmt; ... }`` block and return the statement list."""
        self._expect(TokenKind.LEFT_BRACE, "Expected '{'")
        self._skip_newlines()

        statements: list[Statement] = []
        while not self._at_end() and self._peek().kind != TokenKind.RIGHT_BRACE:
            statements.append(self._parse_statement())
            self._skip_newlines()

        self._expect(TokenKind.RIGHT_BRACE, "Expected '}'")
        self._consume_newline()
        return statements

    def _parse_expression_statement(self) -> Statement:
        """Parse a bare expression as a statement.

        This is a fallback for expressions used as statements (e.g. function
        calls). The expression node is returned directly since it also
        satisfies the Statement type.
        """
        expr = self.parse_expression()
        self._consume_newline()
        return expr  # type: ignore[return-value]

    # -- Pratt precedence climbing --------------------------------------------

    def _parse_precedence(self, *, min_precedence: int) -> Expression:
        """Parse an expression with at least *min_precedence* binding power."""
        left = self._parse_prefix()

        while not self._at_end() and self._peek().kind in _INFIX_PRECEDENCE:
            prec = _INFIX_PRECEDENCE[self._peek().kind]
            if prec < min_precedence:
                break

            op_token = self._advance()
            op_text = _OPERATOR_TEXT[op_token.kind]
            # Left-associative: right side needs strictly higher precedence
            right = self._parse_precedence(min_precedence=prec + 1)
            left = BinaryOp(
                left=left,
                operator=op_text,
                right=right,
                location=op_token.location,
            )

        return left

    # -- Prefix (atoms and unary operators) -----------------------------------

    def _parse_prefix(self) -> Expression:
        """Parse a prefix expression (literal, identifier, unary, or group)."""
        if self._at_end():
            self._error("Expected expression")

        token = self._peek()
        parser = self._prefix_parsers.get(token.kind)
        if parser is not None:
            return parser(self)

        return self._error(f"Unexpected token '{token.value}'")

    # -- Individual expression parsers ----------------------------------------

    def _parse_integer(self) -> IntegerLiteral:
        """Parse an integer literal."""
        token = self._advance()
        return IntegerLiteral(value=int(token.value), location=token.location)

    def _parse_string(self) -> StringLiteral:
        """Parse a string literal."""
        token = self._advance()
        return StringLiteral(value=token.value, location=token.location)

    def _parse_boolean(self) -> BooleanLiteral:
        """Parse a boolean literal (true/false)."""
        token = self._advance()
        return BooleanLiteral(value=token.kind == TokenKind.TRUE, location=token.location)

    def _parse_identifier(self) -> Identifier:
        """Parse an identifier."""
        token = self._advance()
        return Identifier(name=token.value, location=token.location)

    def _parse_negate(self) -> UnaryOp:
        """Parse a unary negation (-x)."""
        token = self._advance()
        operand = self._parse_precedence(min_precedence=_PREFIX_PRECEDENCE)
        return UnaryOp(operator="-", operand=operand, location=token.location)

    def _parse_not(self) -> UnaryOp:
        """Parse a logical not (not x)."""
        token = self._advance()
        operand = self._parse_precedence(min_precedence=_PREFIX_PRECEDENCE)
        return UnaryOp(operator="not", operand=operand, location=token.location)

    def _parse_grouped(self) -> Expression:
        """Parse a parenthesised expression."""
        self._advance()  # consume '('
        expr = self._parse_precedence(min_precedence=0)
        self._expect(TokenKind.RIGHT_PAREN, "Expected ')'")
        return expr

    # -- Prefix dispatch table ------------------------------------------------

    _prefix_parsers: ClassVar[dict[TokenKind, Callable[[Parser], Expression]]] = {
        TokenKind.INTEGER: _parse_integer,
        TokenKind.STRING: _parse_string,
        TokenKind.TRUE: _parse_boolean,
        TokenKind.FALSE: _parse_boolean,
        TokenKind.IDENTIFIER: _parse_identifier,
        TokenKind.MINUS: _parse_negate,
        TokenKind.NOT: _parse_not,
        TokenKind.LEFT_PAREN: _parse_grouped,
    }

    # -- Token helpers --------------------------------------------------------

    def _peek(self) -> Token:
        """Return the current token without advancing."""
        return self._tokens[self._pos]

    def _peek_next_kind(self) -> TokenKind:
        """Return the kind of the next token (after the current one)."""
        next_pos = self._pos + 1
        if next_pos < len(self._tokens):
            return self._tokens[next_pos].kind
        return TokenKind.EOF

    def _advance(self) -> Token:
        """Return the current token and advance to the next."""
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _at_end(self) -> bool:
        """Return True if the current token is EOF."""
        return self._tokens[self._pos].kind == TokenKind.EOF

    def _expect(self, kind: TokenKind, message: str) -> Token:
        """Consume a token of the expected kind, or raise ParseError."""
        if self._at_end() or self._peek().kind != kind:
            self._error(message)
        return self._advance()

    def _skip_newlines(self) -> None:
        """Skip any NEWLINE tokens at the current position."""
        while not self._at_end() and self._peek().kind == TokenKind.NEWLINE:
            self._advance()

    def _consume_newline(self) -> None:
        """Consume a NEWLINE or EOF (statement terminator)."""
        if self._at_end():
            return
        if self._peek().kind == TokenKind.NEWLINE:
            self._advance()

    def _error(self, message: str) -> Never:
        """Raise a ParseError at the current token's location."""
        token = self._tokens[self._pos]
        raise ParseError(message, line=token.location.line, column=token.location.column)
