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
    ForLoop,
    FunctionCall,
    FunctionDef,
    Identifier,
    IfStatement,
    IntegerLiteral,
    PrintStatement,
    Program,
    Reassignment,
    ReturnStatement,
    Statement,
    StringInterpolation,
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

        # Keyword-driven dispatch
        keyword_parser = self._statement_parsers.get(kind)
        if keyword_parser is not None:
            return keyword_parser(self)

        # Identifier-specific: print or reassignment
        if kind == TokenKind.IDENTIFIER:
            if self._peek().value == "print":
                return self._parse_print()
            if self._peek_next_kind() == TokenKind.EQUAL:
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

    def _parse_for(self) -> ForLoop:
        """Parse a ``for variable in iterable { body }`` loop."""
        for_token = self._advance()  # consume 'for'
        var_token = self._expect(TokenKind.IDENTIFIER, "Expected loop variable after 'for'")
        self._expect(TokenKind.IN, "Expected 'in' after loop variable")
        iterable = self.parse_expression()
        body = self._parse_block()
        return ForLoop(
            variable=var_token.value,
            iterable=iterable,
            body=body,
            location=for_token.location,
        )

    def _parse_return(self) -> ReturnStatement:
        """Parse a ``return [expr]`` statement."""
        return_token = self._advance()  # consume 'return'

        # Bare return: next token is newline, closing brace, or end of file
        if (
            self._at_end()
            or self._peek().kind == TokenKind.NEWLINE
            or self._peek().kind == TokenKind.RIGHT_BRACE
        ):
            return ReturnStatement(value=None, location=return_token.location)

        value = self.parse_expression()
        self._consume_newline()
        return ReturnStatement(value=value, location=return_token.location)

    def _parse_function_def(self) -> FunctionDef:
        """Parse a ``fn name(params) { body }`` function definition."""
        fn_token = self._advance()  # consume 'fn'
        name_token = self._expect(TokenKind.IDENTIFIER, "Expected function name after 'fn'")
        self._expect(TokenKind.LEFT_PAREN, "Expected '(' after function name")

        parameters: list[str] = []
        if not self._at_end() and self._peek().kind != TokenKind.RIGHT_PAREN:
            param = self._expect(TokenKind.IDENTIFIER, "Expected parameter name")
            parameters.append(param.value)
            while not self._at_end() and self._peek().kind == TokenKind.COMMA:
                self._advance()  # consume ','
                param = self._expect(TokenKind.IDENTIFIER, "Expected parameter name")
                parameters.append(param.value)

        self._expect(TokenKind.RIGHT_PAREN, "Expected ')' after parameters")
        body = self._parse_block()
        return FunctionDef(
            name=name_token.value,
            parameters=parameters,
            body=body,
            location=fn_token.location,
        )

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

    def _parse_identifier(self) -> Identifier | FunctionCall:
        """Parse an identifier, or a function call if followed by ``(``."""
        token = self._advance()
        if not self._at_end() and self._peek().kind == TokenKind.LEFT_PAREN:
            return self._parse_call(token)
        return Identifier(name=token.value, location=token.location)

    def _parse_call(self, name_token: Token) -> FunctionCall:
        """Parse a function call argument list after the name has been consumed."""
        self._advance()  # consume '('
        arguments: list[Expression] = []
        if not self._at_end() and self._peek().kind != TokenKind.RIGHT_PAREN:
            arguments.append(self._parse_precedence(min_precedence=0))
            while not self._at_end() and self._peek().kind == TokenKind.COMMA:
                self._advance()  # consume ','
                arguments.append(self._parse_precedence(min_precedence=0))
        self._expect(TokenKind.RIGHT_PAREN, "Expected ')' after arguments")
        return FunctionCall(
            name=name_token.value,
            arguments=arguments,
            location=name_token.location,
        )

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

    def _parse_string_interpolation(self) -> StringInterpolation:
        """Parse an interpolated string: STRING_START expr (STRING_MIDDLE expr)* STRING_END."""
        start_token = self._advance()  # consume STRING_START
        parts: list[Expression] = []

        # First text segment (may be empty)
        if start_token.value:
            parts.append(StringLiteral(value=start_token.value, location=start_token.location))

        # First expression
        parts.append(self._parse_precedence(min_precedence=0))

        # Middle segments: STRING_MIDDLE text + expression
        while not self._at_end() and self._peek().kind == TokenKind.STRING_MIDDLE:
            mid_token = self._advance()
            if mid_token.value:
                parts.append(StringLiteral(value=mid_token.value, location=mid_token.location))
            parts.append(self._parse_precedence(min_precedence=0))

        # Final segment
        end_token = self._expect(TokenKind.STRING_END, "Expected end of interpolated string")
        if end_token.value:
            parts.append(StringLiteral(value=end_token.value, location=end_token.location))

        return StringInterpolation(parts=parts, location=start_token.location)

    # -- Prefix dispatch table ------------------------------------------------

    _prefix_parsers: ClassVar[dict[TokenKind, Callable[[Parser], Expression]]] = {
        TokenKind.INTEGER: _parse_integer,
        TokenKind.STRING: _parse_string,
        TokenKind.STRING_START: _parse_string_interpolation,
        TokenKind.TRUE: _parse_boolean,
        TokenKind.FALSE: _parse_boolean,
        TokenKind.IDENTIFIER: _parse_identifier,
        TokenKind.MINUS: _parse_negate,
        TokenKind.NOT: _parse_not,
        TokenKind.LEFT_PAREN: _parse_grouped,
    }

    # -- Statement dispatch table ---------------------------------------------

    _statement_parsers: ClassVar[dict[TokenKind, Callable[[Parser], Statement]]] = {
        TokenKind.LET: _parse_let,
        TokenKind.IF: _parse_if,
        TokenKind.WHILE: _parse_while,
        TokenKind.FOR: _parse_for,
        TokenKind.FN: _parse_function_def,
        TokenKind.RETURN: _parse_return,
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
