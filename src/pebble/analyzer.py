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
    BreakStatement,
    ConstAssignment,
    ContinueStatement,
    DictLiteral,
    Expression,
    ForLoop,
    FunctionCall,
    FunctionDef,
    FunctionExpression,
    Identifier,
    IfStatement,
    IndexAccess,
    IndexAssignment,
    IntegerLiteral,
    MethodCall,
    PrintStatement,
    Program,
    Reassignment,
    ReturnStatement,
    SliceAccess,
    Statement,
    StringInterpolation,
    StringLiteral,
    ThrowStatement,
    TryCatch,
    UnaryOp,
    WhileLoop,
)
from pebble.builtins import BUILTIN_ARITIES, METHOD_ARITIES, Arity
from pebble.errors import SemanticError
from pebble.tokens import SourceLocation

# -- Built-in declarations ---------------------------------------------------

_BUILTIN_LOCATION = SourceLocation(line=0, column=0)


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
        function_name: Name of the enclosing function, or ``None`` at top level.

    """

    variables: dict[str, SourceLocation] = field(
        default_factory=lambda: {},  # noqa: PIE807
    )
    functions: dict[str, tuple[Arity, SourceLocation]] = field(
        default_factory=lambda: {},  # noqa: PIE807
    )
    constants: set[str] = field(
        default_factory=lambda: set(),  # noqa: PLW0108
    )
    parent: Scope | None = None
    function_name: str | None = None

    # -- Variables ------------------------------------------------------------

    def declare_variable(self, name: str, location: SourceLocation) -> None:
        """Declare *name* in this scope, raising if it already exists here."""
        if name in self.variables:
            prev = self.variables[name]
            msg = f"Variable '{name}' already declared at line {prev.line}"
            raise SemanticError(msg, line=location.line, column=location.column)
        self.variables[name] = location

    def declare_constant(self, name: str, location: SourceLocation) -> None:
        """Declare *name* as a constant — also records it as a variable."""
        self.declare_variable(name, location)
        self.constants.add(name)

    def is_constant(self, name: str) -> bool:
        """Walk the parent chain to check whether *name* is a constant."""
        if name in self.constants:
            return True
        if self.parent is not None:
            return self.parent.is_constant(name)
        return False

    def resolve_variable(self, name: str) -> SourceLocation | None:
        """Walk the parent chain to find *name*; return ``None`` if missing."""
        if name in self.variables:
            return self.variables[name]
        if self.parent is not None:
            return self.parent.resolve_variable(name)
        return None

    def resolve_variable_scope(self, name: str) -> Scope | None:
        """Walk the parent chain and return the scope that declares *name*."""
        if name in self.variables:
            return self
        if self.parent is not None:
            return self.parent.resolve_variable_scope(name)
        return None

    @property
    def owning_function(self) -> str | None:
        """Return the function name that owns this scope."""
        if self.function_name is not None:
            return self.function_name
        if self.parent is not None:
            return self.parent.owning_function
        return None

    # -- Functions ------------------------------------------------------------

    def declare_function(
        self,
        name: str,
        param_count: Arity,
        location: SourceLocation,
    ) -> None:
        """Declare a function in this scope, raising if it already exists here."""
        if name in self.functions:
            prev = self.functions[name][1]
            msg = f"Function '{name}' already defined at line {prev.line}"
            raise SemanticError(msg, line=location.line, column=location.column)
        self.functions[name] = (param_count, location)

    def resolve_function(self, name: str) -> tuple[Arity, SourceLocation] | None:
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
        for name, arity in BUILTIN_ARITIES.items():
            self._scope.functions[name] = (arity, _BUILTIN_LOCATION)
        self._in_function = False
        self._loop_depth = 0
        self._cell_vars: dict[str, set[str]] = {}
        self._free_vars: dict[str, set[str]] = {}

    # -- Closure metadata -----------------------------------------------------

    @property
    def cell_vars(self) -> dict[str, set[str]]:
        """Map of function name → variables captured by inner functions."""
        return self._cell_vars

    @property
    def free_vars(self) -> dict[str, set[str]]:
        """Map of function name → variables captured from outer functions."""
        return self._free_vars

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

    def _visit_statement(self, stmt: Statement) -> None:  # noqa: PLR0912
        """Dispatch to the appropriate visitor based on statement type."""
        match stmt:
            case Assignment():
                self._visit_assignment(stmt)
            case ConstAssignment():
                self._visit_const_assignment(stmt)
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
            case BreakStatement():
                self._visit_break(stmt)
            case ContinueStatement():
                self._visit_continue(stmt)
            case TryCatch():
                self._visit_try(stmt)
            case ThrowStatement():
                self._visit_throw(stmt)
            case _:
                # Expression statements (e.g. bare function calls)
                self._visit_expression(stmt)  # type: ignore[arg-type]

    # -- Statement visitors ---------------------------------------------------

    def _visit_assignment(self, node: Assignment) -> None:
        """Visit a ``let`` declaration — check value, then declare name."""
        self._visit_expression(node.value)
        self._scope.declare_variable(node.name, node.location)

    def _visit_const_assignment(self, node: ConstAssignment) -> None:
        """Visit a ``const`` declaration — check value, then declare as constant."""
        self._visit_expression(node.value)
        self._scope.declare_constant(node.name, node.location)

    def _visit_reassignment(self, node: Reassignment) -> None:
        """Visit a reassignment — resolve name, then check value."""
        if self._scope.resolve_variable(node.name) is None:
            msg = f"Undeclared variable '{node.name}'"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
        if self._scope.is_constant(node.name):
            msg = f"Cannot reassign constant '{node.name}'"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
        self._check_capture(node.name)
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
        self._loop_depth += 1
        self._visit_block(node.body)
        self._loop_depth -= 1

    def _visit_for(self, node: ForLoop) -> None:
        """Visit a ``for`` loop — iterable in current scope, variable + body in new scope."""
        self._visit_expression(node.iterable)
        self._push_scope()
        self._scope.declare_variable(node.variable, node.location)
        self._loop_depth += 1
        for stmt in node.body:
            self._visit_statement(stmt)
        self._loop_depth -= 1
        self._pop_scope()

    def _visit_function_def(self, node: FunctionDef) -> None:
        """Visit a function definition — declare in current scope, parameters in new scope."""
        self._scope.declare_function(node.name, len(node.parameters), node.location)
        self._push_scope()
        self._scope.function_name = node.name
        for param in node.parameters:
            self._scope.declare_variable(param, node.location)
        prev_in_function = self._in_function
        self._in_function = True
        for stmt in node.body:
            self._visit_statement(stmt)
        self._in_function = prev_in_function
        self._pop_scope()

        # All functions are first-class values — declare the function name
        # as a variable so it can be stored, returned, and passed as an argument.
        self._scope.variables[node.name] = node.location

    def _visit_function_expression(self, node: FunctionExpression) -> None:
        """Visit an anonymous function expression — same as function def."""
        self._scope.declare_function(node.name, len(node.parameters), node.location)
        self._push_scope()
        self._scope.function_name = node.name
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

    def _visit_index_or_slice(self, expr: IndexAccess | SliceAccess) -> None:
        """Visit an index access or slice access expression."""
        self._visit_expression(expr.target)
        match expr:
            case IndexAccess():
                self._visit_expression(expr.index)
            case SliceAccess():
                if expr.start is not None:
                    self._visit_expression(expr.start)
                if expr.stop is not None:
                    self._visit_expression(expr.stop)
                if expr.step is not None:
                    self._visit_expression(expr.step)

    def _visit_return(self, node: ReturnStatement) -> None:
        """Visit a ``return`` statement — must be inside a function."""
        if not self._in_function:
            msg = "Return statement outside function"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
        if node.value is not None:
            self._visit_expression(node.value)

    def _visit_break(self, node: BreakStatement) -> None:
        """Visit a ``break`` statement — must be inside a loop."""
        if self._loop_depth == 0:
            msg = "'break' outside loop"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)

    def _visit_continue(self, node: ContinueStatement) -> None:
        """Visit a ``continue`` statement — must be inside a loop."""
        if self._loop_depth == 0:
            msg = "'continue' outside loop"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)

    def _visit_try(self, node: TryCatch) -> None:
        """Visit a ``try/catch/finally`` block — scope catch variable."""
        self._visit_block(node.body)
        self._push_scope()
        if node.catch_variable is not None:
            self._scope.declare_variable(node.catch_variable, node.location)
        for stmt in node.catch_body:
            self._visit_statement(stmt)
        self._pop_scope()
        if node.finally_body is not None:
            self._visit_block(node.finally_body)

    def _visit_throw(self, node: ThrowStatement) -> None:
        """Visit a ``throw`` statement — validate the expression."""
        self._visit_expression(node.value)

    # -- Block helper ---------------------------------------------------------

    def _visit_block(self, stmts: list[Statement]) -> None:
        """Visit a block of statements in a new child scope."""
        self._push_scope()
        for stmt in stmts:
            self._visit_statement(stmt)
        self._pop_scope()

    # -- Expression dispatch --------------------------------------------------

    def _visit_expressions(self, exprs: list[Expression]) -> None:
        """Visit each expression in *exprs*."""
        for expr in exprs:
            self._visit_expression(expr)

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
                self._visit_expressions(expr.parts)
            case ArrayLiteral():
                self._visit_expressions(expr.elements)
            case DictLiteral():
                for key, value in expr.entries:
                    self._visit_expression(key)
                    self._visit_expression(value)
            case IndexAccess() | SliceAccess():
                self._visit_index_or_slice(expr)
            case MethodCall():
                self._visit_method_call(expr)
            case FunctionExpression():
                self._visit_function_expression(expr)
            case IntegerLiteral() | StringLiteral() | BooleanLiteral():
                pass  # Literals need no semantic checks

    # -- Closure helpers ------------------------------------------------------

    def _check_capture(self, name: str) -> None:
        """Record a cross-function variable capture if applicable."""
        current_fn = self._scope.owning_function
        declaring_scope = self._scope.resolve_variable_scope(name)
        if declaring_scope is None or current_fn is None:
            return
        declaring_fn = declaring_scope.owning_function
        if declaring_fn is not None and declaring_fn != current_fn:
            self._free_vars.setdefault(current_fn, set()).add(name)
            self._cell_vars.setdefault(declaring_fn, set()).add(name)

    # -- Expression visitors --------------------------------------------------

    def _visit_identifier(self, node: Identifier) -> None:
        """Resolve a variable reference, raising if undeclared."""
        if self._scope.resolve_variable(node.name) is None:
            msg = f"Undeclared variable '{node.name}'"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
        self._check_capture(node.name)

    def _visit_function_call(self, node: FunctionCall) -> None:
        """Resolve a function call, checking existence and arity."""
        resolved = self._scope.resolve_function(node.name)
        if resolved is None:
            # Allow calling variables that may hold closures
            if self._scope.resolve_variable(node.name) is not None:
                self._check_capture(node.name)
                for arg in node.arguments:
                    self._visit_expression(arg)
                return
            msg = f"Undeclared function '{node.name}'"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
        expected, _ = resolved
        actual = len(node.arguments)
        if isinstance(expected, tuple):
            if actual not in expected:
                options = ", ".join(str(a) for a in expected)
                msg = f"Function '{node.name}' expects {options} arguments, got {actual}"
                raise SemanticError(msg, line=node.location.line, column=node.location.column)
        elif actual != expected:
            s = "" if expected == 1 else "s"
            msg = f"Function '{node.name}' expects {expected} argument{s}, got {actual}"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
        for arg in node.arguments:
            self._visit_expression(arg)

    def _visit_method_call(self, node: MethodCall) -> None:
        """Visit a method call — validate method name and argument count."""
        self._visit_expression(node.target)
        if node.method not in METHOD_ARITIES:
            msg = f"Unknown method '{node.method}'"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
        expected = METHOD_ARITIES[node.method]
        actual = len(node.arguments)
        if isinstance(expected, tuple):
            if actual not in expected:
                options = ", ".join(str(a) for a in expected)
                msg = f"Method '{node.method}' expects {options} arguments, got {actual}"
                raise SemanticError(msg, line=node.location.line, column=node.location.column)
        elif actual != expected:
            s = "" if expected == 1 else "s"
            msg = f"Method '{node.method}' expects {expected} argument{s}, got {actual}"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
        for arg in node.arguments:
            self._visit_expression(arg)
