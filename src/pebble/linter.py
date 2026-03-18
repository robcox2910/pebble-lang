"""AST-based linter for the Pebble language.

Detect style issues and common mistakes that the semantic analyzer
doesn't catch. The analyzer catches *errors* (code won't work);
the linter catches *warnings* (code works but could be better).

Usage::

    warnings = Linter(source).lint()
    for w in warnings:
        print(f"{w.line}:{w.column}: {w.code} {w.message}")

Rules:

- **W001** — Unused variable
- **W002** — Naming convention violation
- **W003** — Unreachable code
- **W004** — Empty block
"""

import re
from dataclasses import dataclass

from pebble.ast_nodes import (
    ArrayLiteral,
    Assignment,
    AsyncFunctionDef,
    AwaitExpression,
    BinaryOp,
    BooleanLiteral,
    BreakStatement,
    CapturePattern,
    ClassDef,
    ConstAssignment,
    ContinueStatement,
    DictLiteral,
    EnumDef,
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
    MatchStatement,
    MethodCall,
    NullLiteral,
    PrintStatement,
    Reassignment,
    ReturnStatement,
    SliceAccess,
    Statement,
    StringInterpolation,
    StringLiteral,
    StructDef,
    SuperMethodCall,
    ThrowStatement,
    TryCatch,
    UnaryOp,
    UnpackAssignment,
    UnpackConstAssignment,
    UnpackReassignment,
    WhileLoop,
    YieldStatement,
)
from pebble.lexer import Lexer
from pebble.parser import Parser

__all__ = ["LintWarning", "Linter"]

# -- Naming convention patterns ------------------------------------------------

_SNAKE_CASE_RE = re.compile(r"^_?[a-z][a-z0-9_]*$")
_PASCAL_CASE_RE = re.compile(r"^[A-Z][a-zA-Z0-9]*$")


@dataclass(frozen=True)
class LintWarning:
    """A single lint warning with location information.

    Attributes:
        code: Rule code like ``W001``.
        message: Human-readable description.
        line: 1-based source line number.
        column: 1-based source column number.

    """

    code: str
    message: str
    line: int
    column: int


# -- Declaration info ----------------------------------------------------------


@dataclass
class _DeclInfo:
    """Track a variable declaration for W001 analysis."""

    name: str
    line: int
    column: int
    is_param: bool = False


class Linter:
    """Walk the AST and collect lint warnings.

    Usage::

        warnings = Linter(source).lint()
    """

    def __init__(self, source: str) -> None:
        """Create a linter for the given source text."""
        self._source = source
        self._warnings: list[LintWarning] = []
        self._declarations: list[_DeclInfo] = []
        self._reads: set[str] = set()
        self._defined_names: set[str] = set()  # fn/class/struct/enum names

    def lint(self) -> list[LintWarning]:
        """Lint the source and return collected warnings."""
        tokens = Lexer(self._source).tokenize()
        program = Parser(tokens).parse()

        # Two-pass for W001: first collect all declarations and reads
        for stmt in program.statements:
            self._visit_statement(stmt)

        # Emit W001 for unused declarations
        self._check_unused()

        return sorted(self._warnings, key=lambda w: (w.line, w.column, w.code))

    # -- W001 helpers ----------------------------------------------------------

    def _declare(self, name: str, line: int, column: int, *, is_param: bool = False) -> None:
        """Record a variable declaration."""
        self._declarations.append(_DeclInfo(name=name, line=line, column=column, is_param=is_param))

    def _read(self, name: str) -> None:
        """Record a variable read."""
        self._reads.add(name)

    def _check_unused(self) -> None:
        """Emit W001 for declared-but-never-read variables."""
        for decl in self._declarations:
            if decl.is_param:
                continue
            if decl.name.startswith("_"):
                continue
            if decl.name in self._defined_names:
                continue
            if decl.name not in self._reads:
                self._warn(
                    "W001",
                    f"Unused variable '{decl.name}'",
                    decl.line,
                    decl.column,
                )

    # -- Warning emission ------------------------------------------------------

    def _warn(self, code: str, message: str, line: int, column: int) -> None:
        """Add a lint warning."""
        self._warnings.append(LintWarning(code=code, message=message, line=line, column=column))

    # -- Statement dispatch ----------------------------------------------------

    def _visit_statement(self, stmt: Statement) -> None:  # noqa: C901, PLR0912, PLR0915
        """Visit a single statement, collecting declarations, reads, and warnings."""
        match stmt:
            case Assignment():
                self._visit_expression(stmt.value)
                self._declare(stmt.name, stmt.location.line, stmt.location.column)
                self._check_naming_var(stmt.name, stmt.location.line, stmt.location.column)
            case ConstAssignment():
                self._visit_expression(stmt.value)
                self._declare(stmt.name, stmt.location.line, stmt.location.column)
                self._check_naming_var(stmt.name, stmt.location.line, stmt.location.column)
            case UnpackAssignment():
                self._visit_expression(stmt.value)
                for name in stmt.names:
                    self._declare(name, stmt.location.line, stmt.location.column)
                    self._check_naming_var(name, stmt.location.line, stmt.location.column)
            case UnpackConstAssignment():
                self._visit_expression(stmt.value)
                for name in stmt.names:
                    self._declare(name, stmt.location.line, stmt.location.column)
                    self._check_naming_var(name, stmt.location.line, stmt.location.column)
            case Reassignment():
                self._visit_expression(stmt.value)
                self._read(stmt.name)
            case UnpackReassignment():
                self._visit_expression(stmt.value)
                for name in stmt.names:
                    self._read(name)
            case PrintStatement():
                self._visit_expression(stmt.expression)
            case IfStatement():
                self._visit_if(stmt)
            case WhileLoop():
                self._visit_while(stmt)
            case ForLoop():
                self._visit_for(stmt)
            case FunctionDef():
                self._visit_function_def(stmt)
            case AsyncFunctionDef():
                self._visit_async_function_def(stmt)
            case ReturnStatement():
                if stmt.value is not None:
                    self._visit_expression(stmt.value)
            case YieldStatement():
                if stmt.value is not None:
                    self._visit_expression(stmt.value)
            case BreakStatement() | ContinueStatement():
                pass
            case IndexAssignment():
                self._visit_expression(stmt.target)
                self._visit_expression(stmt.index)
                self._visit_expression(stmt.value)
            case FieldAssignment():
                self._visit_expression(stmt.target)
                self._visit_expression(stmt.value)
            case TryCatch():
                self._visit_try(stmt)
            case ThrowStatement():
                self._visit_expression(stmt.value)
            case MatchStatement():
                self._visit_match(stmt)
            case StructDef():
                self._visit_struct_def(stmt)
            case ClassDef():
                self._visit_class_def(stmt)
            case EnumDef():
                self._visit_enum_def(stmt)
            case ImportStatement() | FromImportStatement():
                pass
            case _:
                # Expression statement
                self._visit_expression(stmt)  # type: ignore[arg-type]

    # -- Block visitor with W003 + W004 ----------------------------------------

    def _visit_block(self, stmts: list[Statement], line: int, column: int) -> None:
        """Visit a block, checking for W003 (unreachable) and W004 (empty)."""
        if len(stmts) == 0:
            self._warn("W004", "Empty block", line, column)
            return

        terminal_seen = False
        for stmt in stmts:
            if terminal_seen:
                loc = getattr(stmt, "location", None)
                stmt_line = loc.line if loc else line
                stmt_col = loc.column if loc else column
                self._warn("W003", "Unreachable code", stmt_line, stmt_col)
                break
            self._visit_statement(stmt)
            if isinstance(
                stmt, ReturnStatement | BreakStatement | ContinueStatement | ThrowStatement
            ):
                terminal_seen = True

    # -- Statement visitors ----------------------------------------------------

    def _visit_if(self, stmt: IfStatement) -> None:
        """Visit an if/else statement."""
        self._visit_expression(stmt.condition)
        self._visit_block(stmt.body, stmt.location.line, stmt.location.column)
        if stmt.else_body is not None:
            self._visit_block(stmt.else_body, stmt.location.line, stmt.location.column)

    def _visit_while(self, stmt: WhileLoop) -> None:
        """Visit a while loop."""
        self._visit_expression(stmt.condition)
        self._visit_block(stmt.body, stmt.location.line, stmt.location.column)

    def _visit_for(self, stmt: ForLoop) -> None:
        """Visit a for loop."""
        self._visit_expression(stmt.iterable)
        self._declare(stmt.variable, stmt.location.line, stmt.location.column)
        self._check_naming_var(stmt.variable, stmt.location.line, stmt.location.column)
        self._visit_block(stmt.body, stmt.location.line, stmt.location.column)

    def _visit_function_def(self, stmt: FunctionDef) -> None:
        """Visit a function definition."""
        self._defined_names.add(stmt.name)
        self._check_naming_fn(stmt.name, stmt.location.line, stmt.location.column)
        for param in stmt.parameters:
            self._declare(param.name, stmt.location.line, stmt.location.column, is_param=True)
            if param.default is not None:
                self._visit_expression(param.default)
        self._visit_block(stmt.body, stmt.location.line, stmt.location.column)

    def _visit_async_function_def(self, stmt: AsyncFunctionDef) -> None:
        """Visit an async function definition."""
        self._defined_names.add(stmt.name)
        self._check_naming_fn(stmt.name, stmt.location.line, stmt.location.column)
        for param in stmt.parameters:
            self._declare(param.name, stmt.location.line, stmt.location.column, is_param=True)
            if param.default is not None:
                self._visit_expression(param.default)
        self._visit_block(stmt.body, stmt.location.line, stmt.location.column)

    def _visit_try(self, stmt: TryCatch) -> None:
        """Visit a try/catch/finally block."""
        self._visit_block(stmt.body, stmt.location.line, stmt.location.column)
        if stmt.catch_variable is not None:
            self._declare(stmt.catch_variable, stmt.location.line, stmt.location.column)
        self._visit_block(stmt.catch_body, stmt.location.line, stmt.location.column)
        if stmt.finally_body is not None:
            self._visit_block(stmt.finally_body, stmt.location.line, stmt.location.column)

    def _visit_match(self, stmt: MatchStatement) -> None:
        """Visit a match statement."""
        self._visit_expression(stmt.value)
        for case in stmt.cases:
            if isinstance(case.pattern, CapturePattern):
                self._declare(
                    case.pattern.name, case.pattern.location.line, case.pattern.location.column
                )
            self._visit_block(case.body, case.location.line, case.location.column)

    def _visit_struct_def(self, stmt: StructDef) -> None:
        """Visit a struct definition."""
        self._defined_names.add(stmt.name)
        self._check_naming_type(stmt.name, stmt.location.line, stmt.location.column)

    def _visit_class_def(self, stmt: ClassDef) -> None:
        """Visit a class definition."""
        self._defined_names.add(stmt.name)
        self._check_naming_type(stmt.name, stmt.location.line, stmt.location.column)
        for method in stmt.methods:
            self._check_naming_fn(method.name, method.location.line, method.location.column)
            for param in method.parameters:
                self._declare(
                    param.name, method.location.line, method.location.column, is_param=True
                )
            self._visit_block(method.body, method.location.line, method.location.column)

    def _visit_enum_def(self, stmt: EnumDef) -> None:
        """Visit an enum definition."""
        self._defined_names.add(stmt.name)
        self._check_naming_type(stmt.name, stmt.location.line, stmt.location.column)

    # -- Expression visitor ----------------------------------------------------

    def _visit_expression(self, expr: Expression) -> None:  # noqa: C901, PLR0912
        """Visit an expression, recording reads."""
        match expr:
            case Identifier():
                self._read(expr.name)
            case BinaryOp():
                self._visit_expression(expr.left)
                self._visit_expression(expr.right)
            case UnaryOp():
                self._visit_expression(expr.operand)
            case FunctionCall():
                self._read(expr.name)
                self._visit_expressions(expr.arguments)
            case StringInterpolation():
                self._visit_expressions(expr.parts)
            case ArrayLiteral():
                self._visit_expressions(expr.elements)
            case ListComprehension():
                self._visit_expression(expr.iterable)
                self._visit_expression(expr.mapping)
                if expr.condition is not None:
                    self._visit_expression(expr.condition)
            case DictLiteral():
                for key, value in expr.entries:
                    self._visit_expression(key)
                    self._visit_expression(value)
            case IndexAccess():
                self._visit_expression(expr.target)
                self._visit_expression(expr.index)
            case SliceAccess():
                self._visit_slice(expr)
            case MethodCall():
                self._visit_expression(expr.target)
                self._visit_expressions(expr.arguments)
            case FieldAccess():
                self._visit_expression(expr.target)
            case FunctionExpression():
                self._visit_fn_expr(expr)
            case SuperMethodCall():
                self._visit_expressions(expr.arguments)
            case AwaitExpression():
                self._visit_expression(expr.value)
            case (
                IntegerLiteral()
                | FloatLiteral()
                | StringLiteral()
                | BooleanLiteral()
                | NullLiteral()
            ):
                pass

    def _visit_expressions(self, exprs: list[Expression]) -> None:
        """Visit a list of expressions."""
        for expr in exprs:
            self._visit_expression(expr)

    def _visit_slice(self, expr: SliceAccess) -> None:
        """Visit a slice access expression."""
        self._visit_expression(expr.target)
        if expr.start is not None:
            self._visit_expression(expr.start)
        if expr.stop is not None:
            self._visit_expression(expr.stop)
        if expr.step is not None:
            self._visit_expression(expr.step)

    def _visit_fn_expr(self, expr: FunctionExpression) -> None:
        """Visit a function expression."""
        for param in expr.parameters:
            self._declare(param.name, expr.location.line, expr.location.column, is_param=True)
            if param.default is not None:
                self._visit_expression(param.default)
        self._visit_block(expr.body, expr.location.line, expr.location.column)

    # -- W002 naming helpers ---------------------------------------------------

    def _check_naming_var(self, name: str, line: int, column: int) -> None:
        """Check W002 for variable/function names (expect snake_case)."""
        if name.startswith(("_", "$")):
            return
        if not _SNAKE_CASE_RE.match(name):
            self._warn(
                "W002",
                f"Variable '{name}' should use snake_case",
                line,
                column,
            )

    def _check_naming_fn(self, name: str, line: int, column: int) -> None:
        """Check W002 for function names (expect snake_case)."""
        if name.startswith(("_", "$")):
            return
        if not _SNAKE_CASE_RE.match(name):
            self._warn(
                "W002",
                f"Function '{name}' should use snake_case",
                line,
                column,
            )

    def _check_naming_type(self, name: str, line: int, column: int) -> None:
        """Check W002 for class/struct/enum names (expect PascalCase)."""
        if name.startswith("_"):
            return
        if not _PASCAL_CASE_RE.match(name):
            self._warn(
                "W002",
                f"Type '{name}' should use PascalCase",
                line,
                column,
            )
