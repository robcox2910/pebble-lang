"""Abstract Syntax Tree node definitions for the Pebble language.

Every node is a frozen dataclass. Expression nodes carry a ``location``
pointing back to the source token that produced them. Statement nodes
likewise carry a ``location`` for error reporting.

The ``Program`` root node holds the top-level list of statements.

Type aliases:

- ``Expression`` — union of all expression node types
- ``Statement`` — union of all statement node types
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pebble.tokens import SourceLocation

# ---------------------------------------------------------------------------
# Parameter node
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Parameter:
    """A named slot with optional type annotation."""

    name: str
    type_annotation: str | None = None


# ---------------------------------------------------------------------------
# Expression nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntegerLiteral:
    """A whole-number literal like ``42``."""

    value: int
    location: SourceLocation


@dataclass(frozen=True)
class StringLiteral:
    """A double-quoted string literal like ``"hello"``."""

    value: str
    location: SourceLocation


@dataclass(frozen=True)
class BooleanLiteral:
    """A boolean literal: ``true`` or ``false``."""

    value: bool
    location: SourceLocation


@dataclass(frozen=True)
class FloatLiteral:
    """A floating-point literal like ``3.14``."""

    value: float
    location: SourceLocation


@dataclass(frozen=True)
class Identifier:
    """A variable or function name like ``x`` or ``print``."""

    name: str
    location: SourceLocation


@dataclass(frozen=True)
class UnaryOp:
    """A unary operation like ``-x`` or ``not flag``."""

    operator: str
    operand: Expression
    location: SourceLocation


@dataclass(frozen=True)
class BinaryOp:
    """A binary operation like ``a + b`` or ``x >= 10``."""

    left: Expression
    operator: str
    right: Expression
    location: SourceLocation


@dataclass(frozen=True)
class FunctionCall:
    """A function call like ``print(x)`` or ``add(1, 2)``."""

    name: str
    arguments: list[Expression]
    location: SourceLocation


@dataclass(frozen=True)
class StringInterpolation:
    """An interpolated string like ``"hello {name}"``.

    Parts alternate between string segments (``StringLiteral``) and
    embedded expressions.
    """

    parts: list[Expression]
    location: SourceLocation


@dataclass(frozen=True)
class ArrayLiteral:
    """An array literal like ``[1, 2, 3]``."""

    elements: list[Expression]
    location: SourceLocation


@dataclass(frozen=True)
class ListComprehension:
    """A list comprehension like ``[x * 2 for x in range(10)]``."""

    mapping: Expression
    variable: str
    iterable: Expression
    condition: Expression | None
    location: SourceLocation


@dataclass(frozen=True)
class DictLiteral:
    """A dictionary literal like ``{"name": "Alice", "age": 12}``."""

    entries: list[tuple[Expression, Expression]]
    location: SourceLocation


@dataclass(frozen=True)
class IndexAccess:
    """An index access like ``xs[0]``."""

    target: Expression
    index: Expression
    location: SourceLocation


@dataclass(frozen=True)
class SliceAccess:
    """A slice access like ``xs[1:3]`` or ``xs[::2]``."""

    target: Expression
    start: Expression | None
    stop: Expression | None
    step: Expression | None
    location: SourceLocation


@dataclass(frozen=True)
class MethodCall:
    """A method call like ``xs.push(42)`` or ``s.upper()``."""

    target: Expression
    method: str
    arguments: list[Expression]
    location: SourceLocation


@dataclass(frozen=True)
class FieldAccess:
    """A ``target.field`` read expression like ``p.x``."""

    target: Expression
    field: str
    location: SourceLocation


@dataclass(frozen=True)
class FunctionExpression:
    """An anonymous function expression like ``fn(x) { return x + 1 }``."""

    name: str
    parameters: list[Parameter]
    body: list[Statement]
    location: SourceLocation
    return_type: str | None = None


# ---------------------------------------------------------------------------
# Statement nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Assignment:
    """A ``let`` declaration like ``let x = 42``."""

    name: str
    value: Expression
    location: SourceLocation
    type_annotation: str | None = None


@dataclass(frozen=True)
class UnpackAssignment:
    """A ``let x, y = expr`` unpacking declaration."""

    names: list[str]
    value: Expression
    location: SourceLocation


@dataclass(frozen=True)
class ConstAssignment:
    """A ``const`` declaration like ``const x = 42``."""

    name: str
    value: Expression
    location: SourceLocation
    type_annotation: str | None = None


@dataclass(frozen=True)
class UnpackConstAssignment:
    """A ``const x, y = expr`` unpacking declaration."""

    names: list[str]
    value: Expression
    location: SourceLocation


@dataclass(frozen=True)
class Reassignment:
    """A variable reassignment like ``x = 10``."""

    name: str
    value: Expression
    location: SourceLocation


@dataclass(frozen=True)
class UnpackReassignment:
    """A ``x, y = expr`` unpacking reassignment."""

    names: list[str]
    value: Expression
    location: SourceLocation


@dataclass(frozen=True)
class PrintStatement:
    """A ``print(expr)`` statement."""

    expression: Expression
    location: SourceLocation


@dataclass(frozen=True)
class IfStatement:
    """An ``if`` / ``else`` conditional block."""

    condition: Expression
    body: list[Statement]
    else_body: list[Statement] | None
    location: SourceLocation


@dataclass(frozen=True)
class WhileLoop:
    """A ``while`` loop."""

    condition: Expression
    body: list[Statement]
    location: SourceLocation


@dataclass(frozen=True)
class ForLoop:
    """A ``for`` loop like ``for i in range(10) { ... }``."""

    variable: str
    iterable: Expression
    body: list[Statement]
    location: SourceLocation


@dataclass(frozen=True)
class FunctionDef:
    """A function definition like ``fn add(a, b) { ... }``."""

    name: str
    parameters: list[Parameter]
    body: list[Statement]
    location: SourceLocation
    return_type: str | None = None


@dataclass(frozen=True)
class IndexAssignment:
    """An index assignment like ``xs[0] = 42``."""

    target: Expression
    index: Expression
    value: Expression
    location: SourceLocation


@dataclass(frozen=True)
class ReturnStatement:
    """A ``return`` statement, optionally with a value."""

    value: Expression | None
    location: SourceLocation


@dataclass(frozen=True)
class BreakStatement:
    """A ``break`` statement to exit a loop."""

    location: SourceLocation


@dataclass(frozen=True)
class ContinueStatement:
    """A ``continue`` statement to skip to next iteration."""

    location: SourceLocation


@dataclass(frozen=True)
class TryCatch:
    """A ``try/catch/finally`` block."""

    body: list[Statement]
    catch_variable: str | None
    catch_body: list[Statement]
    finally_body: list[Statement] | None
    location: SourceLocation


@dataclass(frozen=True)
class ThrowStatement:
    """A ``throw expr`` statement."""

    value: Expression
    location: SourceLocation


# ---------------------------------------------------------------------------
# Pattern nodes (for match/case)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LiteralPattern:
    """A pattern that matches an exact literal value."""

    value: int | float | str | bool
    location: SourceLocation


@dataclass(frozen=True)
class WildcardPattern:
    """A pattern that matches anything without binding."""

    location: SourceLocation


@dataclass(frozen=True)
class CapturePattern:
    """A pattern that matches anything and binds the value to a name."""

    name: str
    location: SourceLocation


@dataclass(frozen=True)
class OrPattern:
    """A pattern that matches any of several literal alternatives."""

    patterns: list[LiteralPattern]
    location: SourceLocation


Pattern = LiteralPattern | WildcardPattern | CapturePattern | OrPattern


@dataclass(frozen=True)
class MatchCase:
    """A single ``case`` arm inside a ``match`` statement."""

    pattern: Pattern
    body: list[Statement]
    location: SourceLocation


@dataclass(frozen=True)
class MatchStatement:
    """A ``match value { case ... }`` statement."""

    value: Expression
    cases: list[MatchCase]
    location: SourceLocation


@dataclass(frozen=True)
class StructDef:
    """A ``struct Point { x, y }`` definition."""

    name: str
    fields: list[Parameter]
    body: list[Statement]
    location: SourceLocation


@dataclass(frozen=True)
class FieldAssignment:
    """A ``target.field = value`` write statement like ``p.x = 5``."""

    target: Expression
    field: str
    value: Expression
    location: SourceLocation


@dataclass(frozen=True)
class ImportStatement:
    """An ``import "path.pbl"`` statement."""

    path: str
    location: SourceLocation


@dataclass(frozen=True)
class FromImportStatement:
    """A ``from "path.pbl" import name1, name2`` statement."""

    path: str
    names: list[str]
    location: SourceLocation


@dataclass(frozen=True)
class Program:
    """The root AST node containing the top-level statements."""

    statements: list[Statement]


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

Expression = (
    IntegerLiteral
    | FloatLiteral
    | StringLiteral
    | BooleanLiteral
    | Identifier
    | UnaryOp
    | BinaryOp
    | FunctionCall
    | StringInterpolation
    | ArrayLiteral
    | ListComprehension
    | DictLiteral
    | IndexAccess
    | SliceAccess
    | MethodCall
    | FieldAccess
    | FunctionExpression
)

Statement = (
    Assignment
    | UnpackAssignment
    | ConstAssignment
    | UnpackConstAssignment
    | Reassignment
    | UnpackReassignment
    | PrintStatement
    | IfStatement
    | WhileLoop
    | ForLoop
    | FunctionDef
    | ReturnStatement
    | IndexAssignment
    | BreakStatement
    | ContinueStatement
    | TryCatch
    | ThrowStatement
    | MatchStatement
    | StructDef
    | FieldAssignment
    | ImportStatement
    | FromImportStatement
)
