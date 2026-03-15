"""Recursive-descent parser with Pratt-style precedence climbing.

The parser consumes a list of :class:`~pebble.tokens.Token` objects produced
by the lexer and builds an :class:`~pebble.ast_nodes.Program` AST.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Never

if TYPE_CHECKING:
    from collections.abc import Callable

from pebble.ast_nodes import (
    ArrayLiteral,
    Assignment,
    BinaryOp,
    BooleanLiteral,
    BreakStatement,
    CapturePattern,
    ClassDef,
    ConstAssignment,
    ContinueStatement,
    DictLiteral,
    Expression,
    FieldAccess,
    FieldAssignment,
    FloatLiteral,
    ForLoop,
    FromImportStatement,
    FunctionCall,
    FunctionDef,
    FunctionExpression,
    Identifier,
    IfStatement,
    ImportStatement,
    IndexAccess,
    IndexAssignment,
    IntegerLiteral,
    ListComprehension,
    LiteralPattern,
    MatchCase,
    MatchStatement,
    MethodCall,
    OrPattern,
    Parameter,
    Pattern,
    PrintStatement,
    Program,
    Reassignment,
    ReturnStatement,
    SliceAccess,
    Statement,
    StringInterpolation,
    StringLiteral,
    StructDef,
    ThrowStatement,
    TryCatch,
    UnaryOp,
    UnpackAssignment,
    UnpackConstAssignment,
    UnpackReassignment,
    WhileLoop,
    WildcardPattern,
)
from pebble.errors import ParseError
from pebble.tokens import Token, TokenKind

# ---------------------------------------------------------------------------
# Precedence levels (higher number = tighter binding)
# ---------------------------------------------------------------------------

_PREFIX_PRECEDENCE = 12  # unary -, not, ~

_RIGHT_ASSOCIATIVE: set[TokenKind] = {TokenKind.STAR_STAR}

_INFIX_PRECEDENCE: dict[TokenKind, int] = {
    # Logical
    TokenKind.OR: 1,
    TokenKind.AND: 2,
    # Equality
    TokenKind.EQUAL_EQUAL: 3,
    TokenKind.BANG_EQUAL: 3,
    # Relational
    TokenKind.LESS: 4,
    TokenKind.LESS_EQUAL: 4,
    TokenKind.GREATER: 4,
    TokenKind.GREATER_EQUAL: 4,
    # Bitwise
    TokenKind.PIPE: 5,
    TokenKind.CARET: 6,
    TokenKind.AMPERSAND: 7,
    # Shifts
    TokenKind.LESS_LESS: 8,
    TokenKind.GREATER_GREATER: 8,
    # Additive
    TokenKind.PLUS: 9,
    TokenKind.MINUS: 9,
    # Multiplicative
    TokenKind.STAR: 10,
    TokenKind.SLASH: 10,
    TokenKind.SLASH_SLASH: 10,
    TokenKind.PERCENT: 10,
    TokenKind.STAR_STAR: 11,
}

_OPERATOR_TEXT: dict[TokenKind, str] = {
    TokenKind.PLUS: "+",
    TokenKind.MINUS: "-",
    TokenKind.STAR: "*",
    TokenKind.STAR_STAR: "**",
    TokenKind.SLASH: "/",
    TokenKind.SLASH_SLASH: "//",
    TokenKind.PERCENT: "%",
    TokenKind.EQUAL_EQUAL: "==",
    TokenKind.BANG_EQUAL: "!=",
    TokenKind.LESS: "<",
    TokenKind.LESS_EQUAL: "<=",
    TokenKind.GREATER: ">",
    TokenKind.GREATER_EQUAL: ">=",
    TokenKind.AND: "and",
    TokenKind.OR: "or",
    TokenKind.AMPERSAND: "&",
    TokenKind.PIPE: "|",
    TokenKind.CARET: "^",
    TokenKind.LESS_LESS: "<<",
    TokenKind.GREATER_GREATER: ">>",
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

        # Identifier-specific: print, reassignment, or unpack reassignment
        if kind == TokenKind.IDENTIFIER:
            if self._peek().value == "print":
                return self._parse_print()
            if self._peek_next_kind() == TokenKind.EQUAL:
                return self._parse_reassignment()
            if self._peek_next_kind() == TokenKind.COMMA and self._is_unpack_reassignment():
                return self._parse_unpack_reassignment()

        # Fall through to expression statement
        return self._parse_expression_statement()

    def _parse_let(self) -> Assignment | UnpackAssignment:
        """Parse ``let name[: Type] = expr`` or ``let x, y = expr`` declaration."""
        let_token = self._advance()  # consume 'let'
        name_token = self._expect(TokenKind.IDENTIFIER, "Expected variable name after 'let'")

        # Optional type annotation
        type_annotation: str | None = None
        if not self._at_end() and self._peek().kind == TokenKind.COLON:
            self._advance()  # consume ':'
            type_token = self._expect(TokenKind.IDENTIFIER, "Expected type name after ':'")
            type_annotation = type_token.value

        # Type annotation + comma → error (no annotations on unpack)
        if (
            type_annotation is not None
            and not self._at_end()
            and self._peek().kind == TokenKind.COMMA
        ):
            self._error("Type annotations not supported in unpacking declarations")

        # Multi-target unpack: let x, y = expr
        if not self._at_end() and self._peek().kind == TokenKind.COMMA:
            names = [name_token.value]
            while not self._at_end() and self._peek().kind == TokenKind.COMMA:
                self._advance()  # consume ','
                next_name = self._expect(TokenKind.IDENTIFIER, "Expected variable name after ','")
                names.append(next_name.value)
            self._expect(TokenKind.EQUAL, "Expected '=' after variable names")
            value = self.parse_expression()
            self._consume_newline()
            return UnpackAssignment(names=names, value=value, location=let_token.location)

        self._expect(TokenKind.EQUAL, "Expected '=' after variable name")
        value = self.parse_expression()
        self._consume_newline()
        return Assignment(
            name=name_token.value,
            value=value,
            location=let_token.location,
            type_annotation=type_annotation,
        )

    def _parse_const(self) -> ConstAssignment | UnpackConstAssignment:
        """Parse ``const name[: Type] = expr`` or ``const x, y = expr`` declaration."""
        const_token = self._advance()  # consume 'const'
        name_token = self._expect(TokenKind.IDENTIFIER, "Expected variable name after 'const'")

        # Optional type annotation
        type_annotation: str | None = None
        if not self._at_end() and self._peek().kind == TokenKind.COLON:
            self._advance()  # consume ':'
            type_token = self._expect(TokenKind.IDENTIFIER, "Expected type name after ':'")
            type_annotation = type_token.value

        # Type annotation + comma → error (no annotations on unpack)
        if (
            type_annotation is not None
            and not self._at_end()
            and self._peek().kind == TokenKind.COMMA
        ):
            self._error("Type annotations not supported in unpacking declarations")

        # Multi-target unpack: const x, y = expr
        if not self._at_end() and self._peek().kind == TokenKind.COMMA:
            names = [name_token.value]
            while not self._at_end() and self._peek().kind == TokenKind.COMMA:
                self._advance()  # consume ','
                next_name = self._expect(TokenKind.IDENTIFIER, "Expected variable name after ','")
                names.append(next_name.value)
            self._expect(TokenKind.EQUAL, "Expected '=' after variable names")
            value = self.parse_expression()
            self._consume_newline()
            return UnpackConstAssignment(names=names, value=value, location=const_token.location)

        self._expect(TokenKind.EQUAL, "Expected '=' after variable name")
        value = self.parse_expression()
        self._consume_newline()
        return ConstAssignment(
            name=name_token.value,
            value=value,
            location=const_token.location,
            type_annotation=type_annotation,
        )

    def _parse_reassignment(self) -> Reassignment:
        """Parse a ``name = expr`` reassignment."""
        name_token = self._advance()  # consume identifier
        self._advance()  # consume '='
        value = self.parse_expression()
        self._consume_newline()
        return Reassignment(name=name_token.value, value=value, location=name_token.location)

    def _is_unpack_reassignment(self) -> bool:
        """Scan ahead to check for ``identifier, identifier... =`` pattern."""
        saved = self._pos
        try:
            self._advance()  # skip first identifier
            while not self._at_end() and self._peek().kind == TokenKind.COMMA:
                self._advance()  # skip ','
                if self._at_end() or self._peek().kind != TokenKind.IDENTIFIER:
                    return False
                self._advance()  # skip identifier
            return not self._at_end() and self._peek().kind == TokenKind.EQUAL
        finally:
            self._pos = saved

    def _parse_unpack_reassignment(self) -> UnpackReassignment:
        """Parse ``x, y = expr`` unpack reassignment."""
        first_token = self._advance()  # consume first identifier
        names = [first_token.value]
        while not self._at_end() and self._peek().kind == TokenKind.COMMA:
            self._advance()  # consume ','
            name_token = self._expect(TokenKind.IDENTIFIER, "Expected variable name after ','")
            names.append(name_token.value)
        self._expect(TokenKind.EQUAL, "Expected '=' after variable names")
        value = self.parse_expression()
        self._consume_newline()
        return UnpackReassignment(names=names, value=value, location=first_token.location)

    def _parse_print(self) -> PrintStatement:
        """Parse a ``print(expr)`` statement."""
        print_token = self._advance()  # consume 'print'
        self._expect(TokenKind.LEFT_PAREN, "Expected '(' after 'print'")
        expr = self.parse_expression()
        self._expect(TokenKind.RIGHT_PAREN, "Expected ')' after print argument")
        self._consume_newline()
        return PrintStatement(expression=expr, location=print_token.location)

    def _parse_if(self) -> IfStatement:
        """Parse an ``if cond { body } [else [if] { body }]`` statement."""
        if_token = self._advance()  # consume 'if'
        condition = self.parse_expression()
        body = self._parse_block()

        else_body: list[Statement] | None = None
        if not self._at_end() and self._peek().kind == TokenKind.ELSE:
            self._advance()  # consume 'else'
            if not self._at_end() and self._peek().kind == TokenKind.IF:
                else_body = [self._parse_if()]
            else:
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

    def _parse_break(self) -> BreakStatement:
        """Parse a ``break`` statement."""
        token = self._advance()  # consume 'break'
        self._consume_newline()
        return BreakStatement(location=token.location)

    def _parse_continue(self) -> ContinueStatement:
        """Parse a ``continue`` statement."""
        token = self._advance()  # consume 'continue'
        self._consume_newline()
        return ContinueStatement(location=token.location)

    def _parse_try(self) -> TryCatch:
        """Parse a ``try { body } catch [e] { handler } [finally { cleanup }]`` statement."""
        try_token = self._advance()  # consume 'try'
        body = self._parse_block()

        self._expect(TokenKind.CATCH, "Expected 'catch' after try block")

        # Optional catch variable
        catch_variable: str | None = None
        if not self._at_end() and self._peek().kind == TokenKind.IDENTIFIER:
            catch_variable = self._advance().value

        catch_body = self._parse_block()

        # Optional finally block
        finally_body: list[Statement] | None = None
        if not self._at_end() and self._peek().kind == TokenKind.FINALLY:
            self._advance()  # consume 'finally'
            finally_body = self._parse_block()

        return TryCatch(
            body=body,
            catch_variable=catch_variable,
            catch_body=catch_body,
            finally_body=finally_body,
            location=try_token.location,
        )

    def _parse_throw(self) -> ThrowStatement:
        """Parse a ``throw expr`` statement."""
        throw_token = self._advance()  # consume 'throw'
        value = self.parse_expression()
        self._consume_newline()
        return ThrowStatement(value=value, location=throw_token.location)

    def _parse_return(self) -> ReturnStatement:
        """Parse ``return [expr]`` or ``return a, b, c`` (multi-value sugar)."""
        return_token = self._advance()  # consume 'return'

        # Bare return: next token is newline, closing brace, or end of file
        if (
            self._at_end()
            or self._peek().kind == TokenKind.NEWLINE
            or self._peek().kind == TokenKind.RIGHT_BRACE
        ):
            return ReturnStatement(value=None, location=return_token.location)

        value = self.parse_expression()

        # Multi-value return: return a, b, c → return [a, b, c]
        if not self._at_end() and self._peek().kind == TokenKind.COMMA:
            elements = [value]
            while not self._at_end() and self._peek().kind == TokenKind.COMMA:
                self._advance()  # consume ','
                elements.append(self.parse_expression())
            value = ArrayLiteral(elements=elements, location=return_token.location)

        self._consume_newline()
        return ReturnStatement(value=value, location=return_token.location)

    def _parse_parameter(self) -> Parameter:
        """Parse ``name[: Type]`` — a parameter with optional type annotation."""
        name_token = self._expect(TokenKind.IDENTIFIER, "Expected parameter name")
        type_annotation: str | None = None
        if not self._at_end() and self._peek().kind == TokenKind.COLON:
            self._advance()  # consume ':'
            type_token = self._expect(TokenKind.IDENTIFIER, "Expected type name after ':'")
            type_annotation = type_token.value
        return Parameter(name=name_token.value, type_annotation=type_annotation)

    def _parse_return_type(self) -> str | None:
        """Parse optional ``-> Type`` return type annotation."""
        if not self._at_end() and self._peek().kind == TokenKind.ARROW:
            self._advance()  # consume '->'
            type_token = self._expect(TokenKind.IDENTIFIER, "Expected return type after '->'")
            return type_token.value
        return None

    def _parse_function_def(self) -> FunctionDef:
        """Parse a ``fn name(params) [-> Type] { body }`` function definition."""
        fn_token = self._advance()  # consume 'fn'
        name_token = self._expect(TokenKind.IDENTIFIER, "Expected function name after 'fn'")
        self._expect(TokenKind.LEFT_PAREN, "Expected '(' after function name")

        parameters: list[Parameter] = []
        if not self._at_end() and self._peek().kind != TokenKind.RIGHT_PAREN:
            parameters.append(self._parse_parameter())
            while not self._at_end() and self._peek().kind == TokenKind.COMMA:
                self._advance()  # consume ','
                parameters.append(self._parse_parameter())

        self._expect(TokenKind.RIGHT_PAREN, "Expected ')' after parameters")
        return_type = self._parse_return_type()
        body = self._parse_block()
        return FunctionDef(
            name=name_token.value,
            parameters=parameters,
            body=body,
            location=fn_token.location,
            return_type=return_type,
        )

    def _parse_match(self) -> MatchStatement:
        """Parse a ``match value { case pattern { body } ... }`` statement."""
        match_token = self._advance()  # consume 'match'
        value = self.parse_expression()
        self._expect(TokenKind.LEFT_BRACE, "Expected '{'")
        self._skip_newlines()

        cases: list[MatchCase] = []
        while not self._at_end() and self._peek().kind != TokenKind.RIGHT_BRACE:
            cases.append(self._parse_match_case())
            self._skip_newlines()

        self._expect(TokenKind.RIGHT_BRACE, "Expected '}'")
        self._consume_newline()
        return MatchStatement(value=value, cases=cases, location=match_token.location)

    def _parse_match_case(self) -> MatchCase:
        """Parse a single ``case pattern { body }`` arm."""
        case_token = self._expect(TokenKind.CASE, "Expected 'case'")
        pattern = self._parse_match_pattern()
        body = self._parse_block()
        return MatchCase(pattern=pattern, body=body, location=case_token.location)

    def _parse_match_pattern(self) -> Pattern:
        """Parse a pattern: literal, wildcard, capture, or OR."""
        if self._at_end():
            self._error("Expected pattern")

        token = self._peek()

        # Wildcard pattern: bare underscore
        if token.kind == TokenKind.IDENTIFIER and token.value == "_":
            self._advance()
            return WildcardPattern(location=token.location)

        # Capture: let <name>
        if token.kind == TokenKind.LET:
            self._advance()  # consume 'let'
            name_token = self._expect(TokenKind.IDENTIFIER, "Expected variable name after 'let'")
            if name_token.value == "_":
                self._error("Cannot use '_' as capture name; use 'case _' for wildcard")
            return CapturePattern(name=name_token.value, location=token.location)

        # Negative literal: -<int|float>
        if token.kind == TokenKind.MINUS:
            return self._parse_negative_literal_pattern()

        # Positive literal or OR pattern
        first = self._parse_single_literal_pattern()

        # Check for OR: literal | literal | ...
        if not self._at_end() and self._peek().kind == TokenKind.PIPE:
            alternatives = [first]
            while not self._at_end() and self._peek().kind == TokenKind.PIPE:
                self._advance()  # consume '|'
                alternatives.append(self._parse_single_literal_pattern())
            return OrPattern(patterns=alternatives, location=first.location)

        return first

    def _parse_single_literal_pattern(self) -> LiteralPattern:
        """Parse a single literal pattern value (int, float, string, bool)."""
        if self._at_end():
            self._error("Expected pattern")

        token = self._peek()

        if token.kind == TokenKind.MINUS:
            return self._parse_negative_literal_pattern()

        if token.kind == TokenKind.INTEGER:
            self._advance()
            return LiteralPattern(value=int(token.value), location=token.location)

        if token.kind == TokenKind.FLOAT:
            self._advance()
            return LiteralPattern(value=float(token.value), location=token.location)

        if token.kind == TokenKind.STRING:
            self._advance()
            return LiteralPattern(value=token.value, location=token.location)

        if token.kind in (TokenKind.TRUE, TokenKind.FALSE):
            self._advance()
            return LiteralPattern(value=token.kind == TokenKind.TRUE, location=token.location)

        return self._error("Expected pattern (literal, '_', or 'let name')")

    def _parse_negative_literal_pattern(self) -> LiteralPattern:
        """Parse a negative literal pattern: ``-<int>`` or ``-<float>``."""
        minus_token = self._advance()  # consume '-'
        token = self._peek()
        if token.kind == TokenKind.INTEGER:
            self._advance()
            return LiteralPattern(value=-int(token.value), location=minus_token.location)
        if token.kind == TokenKind.FLOAT:
            self._advance()
            return LiteralPattern(value=-float(token.value), location=minus_token.location)
        return self._error("Expected number after '-' in pattern")

    def _parse_struct_def(self) -> StructDef:
        """Parse a ``struct Name { field1[: Type], field2[: Type] }`` definition."""
        struct_token = self._advance()  # consume 'struct'
        name_token = self._expect(TokenKind.IDENTIFIER, "Expected struct name after 'struct'")
        self._expect(TokenKind.LEFT_BRACE, "Expected '{' after struct name")
        self._skip_newlines()

        fields: list[Parameter] = []
        seen: set[str] = set()
        if not self._at_end() and self._peek().kind != TokenKind.RIGHT_BRACE:
            field = self._parse_parameter()
            if field.name in seen:
                self._error(f"Duplicate field '{field.name}' in struct '{name_token.value}'")
            fields.append(field)
            seen.add(field.name)
            while not self._at_end() and self._peek().kind == TokenKind.COMMA:
                self._advance()  # consume ','
                field = self._parse_parameter()
                if field.name in seen:
                    self._error(f"Duplicate field '{field.name}' in struct '{name_token.value}'")
                fields.append(field)
                seen.add(field.name)
            self._skip_newlines()

        self._expect(TokenKind.RIGHT_BRACE, "Expected '}' after struct fields")
        self._consume_newline()
        return StructDef(
            name=name_token.value,
            fields=fields,
            body=[],
            location=struct_token.location,
        )

    def _parse_class_def(self) -> ClassDef:
        """Parse a ``class Name { fields, fn method(self) { ... } }`` definition."""
        class_token = self._advance()  # consume 'class'
        name_token = self._expect(TokenKind.IDENTIFIER, "Expected class name after 'class'")
        self._expect(TokenKind.LEFT_BRACE, "Expected '{' after class name")
        self._skip_newlines()

        fields: list[Parameter] = []
        methods: list[FunctionDef] = []
        seen_fields: set[str] = set()
        seen_methods: set[str] = set()

        # Parse fields: comma-separated parameters until we hit FN or }
        while (
            not self._at_end()
            and self._peek().kind != TokenKind.RIGHT_BRACE
            and self._peek().kind != TokenKind.FN
        ):
            param = self._parse_parameter()
            if param.name in seen_fields:
                self._error(f"Duplicate field '{param.name}' in class '{name_token.value}'")
            fields.append(param)
            seen_fields.add(param.name)
            if not self._at_end() and self._peek().kind == TokenKind.COMMA:
                self._advance()  # consume ','
                self._skip_newlines()
            else:
                self._skip_newlines()

        # Parse methods
        while not self._at_end() and self._peek().kind == TokenKind.FN:
            method = self._parse_function_def()
            if method.name in seen_methods:
                self._error(f"Duplicate method '{method.name}' in class '{name_token.value}'")
            methods.append(method)
            seen_methods.add(method.name)
            self._skip_newlines()

        self._expect(TokenKind.RIGHT_BRACE, "Expected '}' after class body")
        self._consume_newline()
        return ClassDef(
            name=name_token.value,
            fields=fields,
            methods=methods,
            location=class_token.location,
        )

    def _parse_import(self) -> ImportStatement:
        """Parse ``import "path.pbl"``."""
        import_token = self._advance()  # consume 'import'
        path_token = self._expect(TokenKind.STRING, "Expected module path string after 'import'")
        self._consume_newline()
        return ImportStatement(path=path_token.value, location=import_token.location)

    def _parse_from_import(self) -> FromImportStatement:
        """Parse ``from "path.pbl" import name1, name2``."""
        from_token = self._advance()  # consume 'from'
        path_token = self._expect(TokenKind.STRING, "Expected module path string after 'from'")
        self._expect(TokenKind.IMPORT, "Expected 'import' after module path")
        name_token = self._expect(TokenKind.IDENTIFIER, "Expected name after 'import'")
        names = [name_token.value]
        while not self._at_end() and self._peek().kind == TokenKind.COMMA:
            self._advance()  # consume ','
            name_token = self._expect(TokenKind.IDENTIFIER, "Expected name after ','")
            names.append(name_token.value)
        self._consume_newline()
        return FromImportStatement(path=path_token.value, names=names, location=from_token.location)

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
        calls). Also handles index assignment: ``expr[index] = value``.
        """
        expr = self.parse_expression()

        # Check for index assignment: expr[index] = value
        if (
            isinstance(expr, IndexAccess)
            and not self._at_end()
            and self._peek().kind == TokenKind.EQUAL
        ):
            self._advance()  # consume '='
            value = self.parse_expression()
            self._consume_newline()
            return IndexAssignment(
                target=expr.target,
                index=expr.index,
                value=value,
                location=expr.location,
            )

        # Check for field assignment: expr.field = value
        if (
            isinstance(expr, FieldAccess)
            and not self._at_end()
            and self._peek().kind == TokenKind.EQUAL
        ):
            self._advance()  # consume '='
            value = self.parse_expression()
            self._consume_newline()
            return FieldAssignment(
                target=expr.target,
                field=expr.field,
                value=value,
                location=expr.location,
            )

        self._consume_newline()
        return expr  # type: ignore[return-value]

    # -- Pratt precedence climbing --------------------------------------------

    def _parse_precedence(self, *, min_precedence: int) -> Expression:
        """Parse an expression with at least *min_precedence* binding power."""
        left = self._parse_prefix()

        while not self._at_end():
            # Postfix index access: expr[index]
            if self._peek().kind == TokenKind.LEFT_BRACKET:
                left = self._parse_index_access(left)
                continue

            # Postfix dot access: method call or field access
            if self._peek().kind == TokenKind.DOT:
                left = self._parse_dot_access(left)
                continue

            if self._peek().kind not in _INFIX_PRECEDENCE:
                break
            prec = _INFIX_PRECEDENCE[self._peek().kind]
            if prec < min_precedence:
                break

            op_token = self._advance()
            op_text = _OPERATOR_TEXT[op_token.kind]
            # Right-associative: use same precedence; left-associative: strictly higher
            next_prec = prec if op_token.kind in _RIGHT_ASSOCIATIVE else prec + 1
            right = self._parse_precedence(min_precedence=next_prec)
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

    def _parse_float(self) -> FloatLiteral:
        """Parse a float literal."""
        token = self._advance()
        return FloatLiteral(value=float(token.value), location=token.location)

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
        """Parse a unary negation (``-x``).

        Negation binds less tightly than ``**`` so ``-2 ** 2`` is ``-(2**2)``.
        """
        token = self._advance()
        operand = self._parse_precedence(
            min_precedence=_INFIX_PRECEDENCE[TokenKind.STAR_STAR],
        )
        return UnaryOp(operator="-", operand=operand, location=token.location)

    def _parse_not(self) -> UnaryOp:
        """Parse a logical not (``not x``)."""
        token = self._advance()
        operand = self._parse_precedence(min_precedence=_PREFIX_PRECEDENCE)
        return UnaryOp(operator="not", operand=operand, location=token.location)

    def _parse_bitwise_not(self) -> UnaryOp:
        """Parse a bitwise not (``~x``)."""
        token = self._advance()
        operand = self._parse_precedence(min_precedence=_PREFIX_PRECEDENCE)
        return UnaryOp(operator="~", operand=operand, location=token.location)

    def _parse_grouped(self) -> Expression:
        """Parse a parenthesised expression."""
        self._advance()  # consume '('
        expr = self._parse_precedence(min_precedence=0)
        self._expect(TokenKind.RIGHT_PAREN, "Expected ')'")
        return expr

    def _parse_array(self) -> ArrayLiteral | ListComprehension:
        """Parse an array literal or list comprehension.

        After parsing the first element, peek for ``for`` to decide
        between ``[expr, ...]`` (array) and ``[expr for var in iter]``
        (comprehension).
        """
        bracket_token = self._advance()  # consume '['
        elements: list[Expression] = []
        if not self._at_end() and self._peek().kind != TokenKind.RIGHT_BRACKET:
            first = self._parse_precedence(min_precedence=0)
            # Detect list comprehension: [expr for var in range(...)]
            if not self._at_end() and self._peek().kind == TokenKind.FOR:
                return self._parse_list_comprehension(first, bracket_token)
            elements.append(first)
            while not self._at_end() and self._peek().kind == TokenKind.COMMA:
                self._advance()  # consume ','
                elements.append(self._parse_precedence(min_precedence=0))
        self._expect(TokenKind.RIGHT_BRACKET, "Expected ']' after array elements")
        return ArrayLiteral(elements=elements, location=bracket_token.location)

    def _parse_list_comprehension(
        self, mapping: Expression, bracket_token: Token
    ) -> ListComprehension:
        """Parse the rest of ``[mapping for var in iterable if cond]``."""
        self._advance()  # consume 'for'
        var_token = self._expect(TokenKind.IDENTIFIER, "Expected variable name after 'for'")
        self._expect(TokenKind.IN, "Expected 'in' after loop variable")
        iterable = self._parse_precedence(min_precedence=0)
        condition: Expression | None = None
        if not self._at_end() and self._peek().kind == TokenKind.IF:
            self._advance()  # consume 'if'
            condition = self._parse_precedence(min_precedence=0)
        self._expect(TokenKind.RIGHT_BRACKET, "Expected ']' after list comprehension")
        return ListComprehension(
            mapping=mapping,
            variable=var_token.value,
            iterable=iterable,
            condition=condition,
            location=bracket_token.location,
        )

    def _parse_dict(self) -> DictLiteral:
        """Parse a dictionary literal: ``{key: value, ...}``."""
        brace_token = self._advance()  # consume '{'
        entries: list[tuple[Expression, Expression]] = []
        if not self._at_end() and self._peek().kind != TokenKind.RIGHT_BRACE:
            key = self._parse_precedence(min_precedence=0)
            self._expect(TokenKind.COLON, "Expected ':' after dict key")
            value = self._parse_precedence(min_precedence=0)
            entries.append((key, value))
            while not self._at_end() and self._peek().kind == TokenKind.COMMA:
                self._advance()  # consume ','
                key = self._parse_precedence(min_precedence=0)
                self._expect(TokenKind.COLON, "Expected ':' after dict key")
                value = self._parse_precedence(min_precedence=0)
                entries.append((key, value))
        self._expect(TokenKind.RIGHT_BRACE, "Expected '}' after dict entries")
        return DictLiteral(entries=entries, location=brace_token.location)

    _anon_counter: int = 0

    def _parse_fn_expression(self) -> FunctionExpression:
        """Parse an anonymous function expression: ``fn(params) [-> Type] { body }``."""
        fn_token = self._advance()  # consume 'fn'
        self._expect(TokenKind.LEFT_PAREN, "Expected '(' after 'fn'")

        parameters: list[Parameter] = []
        if not self._at_end() and self._peek().kind != TokenKind.RIGHT_PAREN:
            parameters.append(self._parse_parameter())
            while not self._at_end() and self._peek().kind == TokenKind.COMMA:
                self._advance()  # consume ','
                parameters.append(self._parse_parameter())

        self._expect(TokenKind.RIGHT_PAREN, "Expected ')' after parameters")
        return_type = self._parse_return_type()
        body = self._parse_block()
        name = f"$anon_{Parser._anon_counter}"
        Parser._anon_counter += 1
        return FunctionExpression(
            name=name,
            parameters=parameters,
            body=body,
            location=fn_token.location,
            return_type=return_type,
        )

    def _parse_index_access(self, target: Expression) -> Expression:
        """Parse a postfix index or slice access: ``target[index]`` or ``target[start:stop]``."""
        bracket_token = self._advance()  # consume '['

        # Leading colon → slice with start=None
        if not self._at_end() and self._peek().kind == TokenKind.COLON:
            return self._parse_slice(target, start=None, bracket_token=bracket_token)

        first = self._parse_precedence(min_precedence=0)

        # Colon after first expression → slice
        if not self._at_end() and self._peek().kind == TokenKind.COLON:
            return self._parse_slice(target, start=first, bracket_token=bracket_token)

        # No colon → plain index access
        self._expect(TokenKind.RIGHT_BRACKET, "Expected ']' after index")
        return IndexAccess(target=target, index=first, location=bracket_token.location)

    def _parse_dot_access(self, target: Expression) -> MethodCall | FieldAccess:
        """Parse a dot expression: method call or field access."""
        dot_token = self._advance()  # consume '.'
        name_token = self._expect(TokenKind.IDENTIFIER, "Expected name after '.'")

        # Method call: target.name(args)
        if not self._at_end() and self._peek().kind == TokenKind.LEFT_PAREN:
            self._advance()  # consume '('
            arguments: list[Expression] = []
            if not self._at_end() and self._peek().kind != TokenKind.RIGHT_PAREN:
                arguments.append(self._parse_precedence(min_precedence=0))
                while not self._at_end() and self._peek().kind == TokenKind.COMMA:
                    self._advance()  # consume ','
                    arguments.append(self._parse_precedence(min_precedence=0))
            self._expect(TokenKind.RIGHT_PAREN, "Expected ')' after method arguments")
            return MethodCall(
                target=target,
                method=name_token.value,
                arguments=arguments,
                location=dot_token.location,
            )

        # Field access: target.name
        return FieldAccess(
            target=target,
            field=name_token.value,
            location=dot_token.location,
        )

    def _parse_slice(
        self,
        target: Expression,
        *,
        start: Expression | None,
        bracket_token: Token,
    ) -> SliceAccess:
        """Parse a slice after the first ``:`` has been detected."""
        self._advance()  # consume first ':'

        # Parse optional stop (not present if next is ':' or ']')
        stop: Expression | None = None
        if (
            not self._at_end()
            and self._peek().kind != TokenKind.COLON
            and self._peek().kind != TokenKind.RIGHT_BRACKET
        ):
            stop = self._parse_precedence(min_precedence=0)

        # Parse optional second ':' and step
        step: Expression | None = None
        if not self._at_end() and self._peek().kind == TokenKind.COLON:
            self._advance()  # consume second ':'
            if not self._at_end() and self._peek().kind != TokenKind.RIGHT_BRACKET:
                step = self._parse_precedence(min_precedence=0)

        self._expect(TokenKind.RIGHT_BRACKET, "Expected ']' after slice")
        return SliceAccess(
            target=target,
            start=start,
            stop=stop,
            step=step,
            location=bracket_token.location,
        )

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
        TokenKind.FLOAT: _parse_float,
        TokenKind.STRING: _parse_string,
        TokenKind.STRING_START: _parse_string_interpolation,
        TokenKind.TRUE: _parse_boolean,
        TokenKind.FALSE: _parse_boolean,
        TokenKind.IDENTIFIER: _parse_identifier,
        TokenKind.MINUS: _parse_negate,
        TokenKind.NOT: _parse_not,
        TokenKind.TILDE: _parse_bitwise_not,
        TokenKind.LEFT_PAREN: _parse_grouped,
        TokenKind.LEFT_BRACKET: _parse_array,
        TokenKind.LEFT_BRACE: _parse_dict,
        TokenKind.FN: _parse_fn_expression,
    }

    # -- Statement dispatch table ---------------------------------------------

    _statement_parsers: ClassVar[dict[TokenKind, Callable[[Parser], Statement]]] = {
        TokenKind.CONST: _parse_const,
        TokenKind.LET: _parse_let,
        TokenKind.IF: _parse_if,
        TokenKind.WHILE: _parse_while,
        TokenKind.FOR: _parse_for,
        TokenKind.FN: _parse_function_def,
        TokenKind.RETURN: _parse_return,
        TokenKind.BREAK: _parse_break,
        TokenKind.CONTINUE: _parse_continue,
        TokenKind.TRY: _parse_try,
        TokenKind.THROW: _parse_throw,
        TokenKind.MATCH: _parse_match,
        TokenKind.STRUCT: _parse_struct_def,
        TokenKind.CLASS: _parse_class_def,
        TokenKind.IMPORT: _parse_import,
        TokenKind.FROM: _parse_from_import,
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
