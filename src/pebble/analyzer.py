"""Semantic analyzer for the Pebble language.

Walk the AST to check that a program makes logical sense before compilation.
Catch errors the parser cannot — undeclared variables, duplicate declarations,
arity mismatches, and return statements outside functions.

The analyzer uses a linked-list of :class:`Scope` objects to implement
block scoping: each block (``if``, ``while``, ``for``, ``fn``) introduces
a new child scope.  Variable lookup walks the chain toward the root.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pebble.ast_nodes import (
    ArrayLiteral,
    Assignment,
    BinaryOp,
    BooleanLiteral,
    Expression,
    ForLoop,
    FunctionCall,
    FunctionDef,
    Identifier,
    IfStatement,
    IndexAccess,
    IndexAssignment,
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
from pebble.errors import SemanticError
from pebble.tokens import SourceLocation

# -- Built-in declarations ---------------------------------------------------

_BUILTIN_LOCATION = SourceLocation(line=0, column=0)
_PRINT_ARITY = 1
_RANGE_ARITY = 1
_LEN_ARITY = 1


# -- Scope --------------------------------------------------------------------


@dataclass
class Scope:
    """Symbol table for a single lexical scope.

    Variables and functions live in separate namespaces — you can have a
    variable ``x`` and a function ``x`` without conflict.

    Attributes:
        variables: Map of variable names to the location where they were declared.
        functions: Map of function names to ``(param_count, location)`` tuples.
        parent: Enclosing scope, or ``None`` for the global scope.

    """

    variables: dict[str, SourceLocation] = field(
        default_factory=lambda: {},  # noqa: PIE807
    )
    functions: dict[str, tuple[int, SourceLocation]] = field(
        default_factory=lambda: {},  # noqa: PIE807
    )
    parent: Scope | None = None

    # -- Variables ------------------------------------------------------------

    def declare_variable(self, name: str, location: SourceLocation) -> None:
        """Declare *name* in this scope, raising if it already exists here."""
        if name in self.variables:
            prev = self.variables[name]
            msg = f"Variable '{name}' already declared at line {prev.line}"
            raise SemanticError(msg, line=location.line, column=location.column)
        self.variables[name] = location

    def resolve_variable(self, name: str) -> SourceLocation | None:
        """Walk the parent chain to find *name*; return ``None`` if missing."""
        if name in self.variables:
            return self.variables[name]
        if self.parent is not None:
            return self.parent.resolve_variable(name)
        return None

    # -- Functions ------------------------------------------------------------

    def declare_function(
        self,
        name: str,
        param_count: int,
        location: SourceLocation,
    ) -> None:
        """Declare a function in this scope, raising if it already exists here."""
        if name in self.functions:
            prev = self.functions[name][1]
            msg = f"Function '{name}' already defined at line {prev.line}"
            raise SemanticError(msg, line=location.line, column=location.column)
        self.functions[name] = (param_count, location)

    def resolve_function(self, name: str) -> tuple[int, SourceLocation] | None:
        """Walk the parent chain to find *name*; return ``None`` if missing."""
        if name in self.functions:
            return self.functions[name]
        if self.parent is not None:
            return self.parent.resolve_function(name)
        return None


# -- Analyzer -----------------------------------------------------------------


class SemanticAnalyzer:
    """Walk the AST and verify semantic rules.

    Usage::

        program = Parser(tokens).parse()
        program = SemanticAnalyzer().analyze(program)

    Raises :class:`SemanticError` on the first problem found (fail-fast).
    """

    def __init__(self) -> None:
        """Create an analyzer with a global scope and built-in declarations."""
        self._scope = Scope()
        self._scope.functions["print"] = (_PRINT_ARITY, _BUILTIN_LOCATION)
        self._scope.functions["range"] = (_RANGE_ARITY, _BUILTIN_LOCATION)
        self._scope.functions["len"] = (_LEN_ARITY, _BUILTIN_LOCATION)
        self._in_function = False

    # -- Public API -----------------------------------------------------------

    def analyze(self, program: Program) -> Program:
        """Analyze *program* and return it unchanged if valid."""
        for stmt in program.statements:
            self._visit_statement(stmt)
        return program

    # -- Scope helpers --------------------------------------------------------

    def _push_scope(self) -> None:
        """Enter a new child scope."""
        self._scope = Scope(parent=self._scope)

    def _pop_scope(self) -> None:
        """Return to the enclosing scope."""
        assert self._scope.parent is not None  # noqa: S101
        self._scope = self._scope.parent

    # -- Statement dispatch ---------------------------------------------------

    def _visit_statement(self, stmt: Statement) -> None:
        """Dispatch to the appropriate visitor based on statement type."""
        match stmt:
            case Assignment():
                self._visit_assignment(stmt)
            case Reassignment():
                self._visit_reassignment(stmt)
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
            case ReturnStatement():
                self._visit_return(stmt)
            case IndexAssignment():
                self._visit_index_assignment(stmt)
            case _:
                # Expression statements (e.g. bare function calls)
                self._visit_expression(stmt)  # type: ignore[arg-type]

    # -- Statement visitors ---------------------------------------------------

    def _visit_assignment(self, node: Assignment) -> None:
        """Visit a ``let`` declaration — check value, then declare name."""
        self._visit_expression(node.value)
        self._scope.declare_variable(node.name, node.location)

    def _visit_reassignment(self, node: Reassignment) -> None:
        """Visit a reassignment — resolve name, then check value."""
        if self._scope.resolve_variable(node.name) is None:
            msg = f"Undeclared variable '{node.name}'"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
        self._visit_expression(node.value)

    def _visit_if(self, node: IfStatement) -> None:
        """Visit an ``if/else`` — condition in current scope, bodies in new scopes."""
        self._visit_expression(node.condition)
        self._visit_block(node.body)
        if node.else_body is not None:
            self._visit_block(node.else_body)

    def _visit_while(self, node: WhileLoop) -> None:
        """Visit a ``while`` loop — condition in current scope, body in new scope."""
        self._visit_expression(node.condition)
        self._visit_block(node.body)

    def _visit_for(self, node: ForLoop) -> None:
        """Visit a ``for`` loop — iterable in current scope, variable + body in new scope."""
        self._visit_expression(node.iterable)
        self._push_scope()
        self._scope.declare_variable(node.variable, node.location)
        for stmt in node.body:
            self._visit_statement(stmt)
        self._pop_scope()

    def _visit_function_def(self, node: FunctionDef) -> None:
        """Visit a function definition — declare in current scope, parameters in new scope."""
        self._scope.declare_function(node.name, len(node.parameters), node.location)
        self._push_scope()
        for param in node.parameters:
            self._scope.declare_variable(param, node.location)
        prev_in_function = self._in_function
        self._in_function = True
        for stmt in node.body:
            self._visit_statement(stmt)
        self._in_function = prev_in_function
        self._pop_scope()

    def _visit_index_assignment(self, node: IndexAssignment) -> None:
        """Visit an index assignment — check target, index, and value."""
        self._visit_expression(node.target)
        self._visit_expression(node.index)
        self._visit_expression(node.value)

    def _visit_return(self, node: ReturnStatement) -> None:
        """Visit a ``return`` statement — must be inside a function."""
        if not self._in_function:
            msg = "Return statement outside function"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
        if node.value is not None:
            self._visit_expression(node.value)

    # -- Block helper ---------------------------------------------------------

    def _visit_block(self, stmts: list[Statement]) -> None:
        """Visit a block of statements in a new child scope."""
        self._push_scope()
        for stmt in stmts:
            self._visit_statement(stmt)
        self._pop_scope()

    # -- Expression dispatch --------------------------------------------------

    def _visit_expression(self, expr: Expression) -> None:
        """Dispatch to the appropriate visitor based on expression type."""
        match expr:
            case Identifier():
                self._visit_identifier(expr)
            case BinaryOp():
                self._visit_expression(expr.left)
                self._visit_expression(expr.right)
            case UnaryOp():
                self._visit_expression(expr.operand)
            case FunctionCall():
                self._visit_function_call(expr)
            case StringInterpolation():
                for part in expr.parts:
                    self._visit_expression(part)
            case ArrayLiteral():
                for element in expr.elements:
                    self._visit_expression(element)
            case IndexAccess():
                self._visit_expression(expr.target)
                self._visit_expression(expr.index)
            case IntegerLiteral() | StringLiteral() | BooleanLiteral():
                pass  # Literals need no semantic checks

    # -- Expression visitors --------------------------------------------------

    def _visit_identifier(self, node: Identifier) -> None:
        """Resolve a variable reference, raising if undeclared."""
        if self._scope.resolve_variable(node.name) is None:
            msg = f"Undeclared variable '{node.name}'"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)

    def _visit_function_call(self, node: FunctionCall) -> None:
        """Resolve a function call, checking existence and arity."""
        resolved = self._scope.resolve_function(node.name)
        if resolved is None:
            msg = f"Undeclared function '{node.name}'"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
        expected, _ = resolved
        actual = len(node.arguments)
        if actual != expected:
            s = "" if expected == 1 else "s"
            msg = f"Function '{node.name}' expects {expected} argument{s}, got {actual}"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
        for arg in node.arguments:
            self._visit_expression(arg)
