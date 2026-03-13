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
class IndexAccess:
    """An index access like ``xs[0]``."""

    target: Expression
    index: Expression
    location: SourceLocation


# ---------------------------------------------------------------------------
# Statement nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Assignment:
    """A ``let`` declaration like ``let x = 42``."""

    name: str
    value: Expression
    location: SourceLocation


@dataclass(frozen=True)
class Reassignment:
    """A variable reassignment like ``x = 10``."""

    name: str
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
    parameters: list[str]
    body: list[Statement]
    location: SourceLocation


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
class Program:
    """The root AST node containing the top-level statements."""

    statements: list[Statement]


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

Expression = (
    IntegerLiteral
    | StringLiteral
    | BooleanLiteral
    | Identifier
    | UnaryOp
    | BinaryOp
    | FunctionCall
    | StringInterpolation
    | ArrayLiteral
    | IndexAccess
)

Statement = (
    Assignment
    | Reassignment
    | PrintStatement
    | IfStatement
    | WhileLoop
    | ForLoop
    | FunctionDef
    | ReturnStatement
    | IndexAssignment
    | BreakStatement
    | ContinueStatement
)
