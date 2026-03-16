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
    MatchStatement,
    MethodCall,
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
from pebble.builtins import BUILTIN_ARITIES, METHOD_ARITIES, Arity
from pebble.errors import SemanticError
from pebble.tokens import SourceLocation

# -- Built-in declarations ---------------------------------------------------

_BUILTIN_LOCATION = SourceLocation(line=0, column=0)

_BUILTIN_TYPES = frozenset(
    {
        "Int",
        "Float",
        "String",
        "Bool",
        "List",
        "Dict",
        "Fn",
    }
)


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
        self._past_imports = False
        self._cell_vars: dict[str, set[str]] = {}
        self._free_vars: dict[str, set[str]] = {}
        self._class_methods: dict[str, dict[str, int]] = {}

    # -- Closure metadata -----------------------------------------------------

    @property
    def cell_vars(self) -> dict[str, set[str]]:
        """Map of function name → variables captured by inner functions."""
        return self._cell_vars

    @property
    def free_vars(self) -> dict[str, set[str]]:
        """Map of function name → variables captured from outer functions."""
        return self._free_vars

    @property
    def class_methods(self) -> dict[str, dict[str, int]]:
        """Map of class name → {method_name: user_arity (excluding self)}."""
        return self._class_methods

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

    def _validate_type_name(self, name: str, location: SourceLocation) -> None:
        """Validate that *name* is a known type (builtin or struct)."""
        if name in _BUILTIN_TYPES:
            return
        if self._scope.resolve_function(name) is not None:
            return
        msg = f"Unknown type '{name}'"
        raise SemanticError(msg, line=location.line, column=location.column)

    # -- Statement dispatch ---------------------------------------------------

    def _visit_statement(self, stmt: Statement) -> None:  # noqa: C901, PLR0912, PLR0915
        """Dispatch to the appropriate visitor based on statement type."""
        # -- Import ordering enforcement --
        if isinstance(stmt, ImportStatement | FromImportStatement):
            if self._past_imports:
                loc = stmt.location
                msg = "Imports must appear at the top of the file"
                raise SemanticError(msg, line=loc.line, column=loc.column)
        else:
            self._past_imports = True

        match stmt:
            case Assignment():
                self._visit_assignment(stmt)
            case UnpackAssignment():
                self._visit_unpack_assignment(stmt)
            case ConstAssignment():
                self._visit_const_assignment(stmt)
            case UnpackConstAssignment():
                self._visit_unpack_const_assignment(stmt)
            case Reassignment():
                self._visit_reassignment(stmt)
            case UnpackReassignment():
                self._visit_unpack_reassignment(stmt)
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
            case MatchStatement():
                self._visit_match(stmt)
            case StructDef():
                self._visit_struct_def(stmt)
            case ClassDef():
                self._visit_class_def(stmt)
            case FieldAssignment():
                self._visit_field_assignment(stmt)
            case ImportStatement() | FromImportStatement():
                pass  # Names registered by resolver before analyze()
            case _:
                # Expression statements (e.g. bare function calls)
                self._visit_expression(stmt)  # type: ignore[arg-type]

    # -- Statement visitors ---------------------------------------------------

    def _visit_assignment(self, node: Assignment) -> None:
        """Visit a ``let`` declaration — check value, then declare name."""
        self._visit_expression(node.value)
        if node.type_annotation is not None:
            self._validate_type_name(node.type_annotation, node.location)
        self._scope.declare_variable(node.name, node.location)

    def _visit_const_assignment(self, node: ConstAssignment) -> None:
        """Visit a ``const`` declaration — check value, then declare as constant."""
        self._visit_expression(node.value)
        if node.type_annotation is not None:
            self._validate_type_name(node.type_annotation, node.location)
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

    def _visit_unpack_assignment(self, node: UnpackAssignment) -> None:
        """Visit a ``let x, y = expr`` — check value, then declare each name."""
        self._visit_expression(node.value)
        for name in node.names:
            self._scope.declare_variable(name, node.location)

    def _visit_unpack_const_assignment(self, node: UnpackConstAssignment) -> None:
        """Visit a ``const x, y = expr`` — check value, then declare each as constant."""
        self._visit_expression(node.value)
        for name in node.names:
            self._scope.declare_constant(name, node.location)

    def _visit_unpack_reassignment(self, node: UnpackReassignment) -> None:
        """Visit a ``x, y = expr`` — resolve each name, check not const, then check value."""
        for name in node.names:
            if self._scope.resolve_variable(name) is None:
                msg = f"Undeclared variable '{name}'"
                raise SemanticError(msg, line=node.location.line, column=node.location.column)
            if self._scope.is_constant(name):
                msg = f"Cannot reassign constant '{name}'"
                raise SemanticError(msg, line=node.location.line, column=node.location.column)
            self._check_capture(name)
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

    def _visit_list_comprehension(self, node: ListComprehension) -> None:
        """Visit a list comprehension — iterable in current scope, variable + mapping in new scope."""
        self._visit_expression(node.iterable)
        self._push_scope()
        self._scope.declare_variable(node.variable, node.location)
        self._visit_expression(node.mapping)
        if node.condition is not None:
            self._visit_expression(node.condition)
        self._pop_scope()

    def _visit_function_body(self, node: FunctionDef | FunctionExpression) -> None:
        """Visit the shared scope/param/body logic for functions and function expressions."""
        # Validate default parameter ordering and literal-only restriction
        seen_default = False
        for param in node.parameters:
            if param.default is not None:
                seen_default = True
                if not isinstance(
                    param.default,
                    IntegerLiteral | FloatLiteral | StringLiteral | BooleanLiteral,
                ):
                    msg = "Default parameter values must be literals"
                    raise SemanticError(msg, line=node.location.line, column=node.location.column)
            elif seen_default:
                msg = f"Required parameter '{param.name}' cannot follow a parameter with a default"
                raise SemanticError(msg, line=node.location.line, column=node.location.column)

        required = sum(1 for p in node.parameters if p.default is None)
        total = len(node.parameters)
        arity: int | tuple[int, ...] = (
            tuple(range(required, total + 1)) if required != total else total
        )
        self._scope.declare_function(node.name, arity, node.location)
        self._push_scope()
        self._scope.function_name = node.name
        for param in node.parameters:
            self._scope.declare_variable(param.name, node.location)
            if param.type_annotation is not None:
                self._validate_type_name(param.type_annotation, node.location)
        if node.return_type is not None:
            self._validate_type_name(node.return_type, node.location)
        prev_in_function = self._in_function
        self._in_function = True
        for stmt in node.body:
            self._visit_statement(stmt)
        self._in_function = prev_in_function
        self._pop_scope()

    def _visit_function_def(self, node: FunctionDef) -> None:
        """Visit a function definition — declare in current scope, parameters in new scope."""
        self._visit_function_body(node)
        # All functions are first-class values — declare the function name
        # as a variable so it can be stored, returned, and passed as an argument.
        self._scope.variables[node.name] = node.location

    def _visit_function_expression(self, node: FunctionExpression) -> None:
        """Visit an anonymous function expression — same as function def."""
        self._visit_function_body(node)

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

    def _visit_match(self, node: MatchStatement) -> None:
        """Visit a ``match`` statement — check scoping, exhaustiveness, and reachability."""
        self._visit_expression(node.value)
        loc = node.location

        if not node.cases:
            msg = "Match statement must have at least one case"
            raise SemanticError(msg, line=loc.line, column=loc.column)

        seen_catchall = False
        for case in node.cases:
            if seen_catchall:
                msg = "Unreachable case after wildcard or capture pattern"
                raise SemanticError(msg, line=case.location.line, column=case.location.column)
            if isinstance(case.pattern, WildcardPattern | CapturePattern):
                seen_catchall = True

            self._push_scope()
            if isinstance(case.pattern, CapturePattern):
                self._scope.declare_variable(case.pattern.name, case.pattern.location)
            for stmt in case.body:
                self._visit_statement(stmt)
            self._pop_scope()

        last_pattern = node.cases[-1].pattern
        if not isinstance(last_pattern, WildcardPattern | CapturePattern):
            msg = "Match must end with a wildcard or capture pattern for exhaustiveness"
            raise SemanticError(msg, line=loc.line, column=loc.column)

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

    def _visit_expression(self, expr: Expression) -> None:  # noqa: PLR0912
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
            case ListComprehension():
                self._visit_list_comprehension(expr)
            case DictLiteral():
                for key, value in expr.entries:
                    self._visit_expression(key)
                    self._visit_expression(value)
            case IndexAccess() | SliceAccess():
                self._visit_index_or_slice(expr)
            case MethodCall():
                self._visit_method_call(expr)
            case FieldAccess():
                self._visit_field_access(expr)
            case FunctionExpression():
                self._visit_function_expression(expr)
            case IntegerLiteral() | FloatLiteral() | StringLiteral() | BooleanLiteral():
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

    @staticmethod
    def _check_arity(
        kind: str, name: str, expected: Arity, actual: int, location: SourceLocation
    ) -> None:
        """Raise :class:`SemanticError` if *actual* doesn't match *expected* arity."""
        if isinstance(expected, tuple):
            if actual not in expected:
                options = ", ".join(str(a) for a in expected)
                msg = f"{kind} '{name}' expects {options} arguments, got {actual}"
                raise SemanticError(msg, line=location.line, column=location.column)
        elif actual != expected:
            s = "" if expected == 1 else "s"
            msg = f"{kind} '{name}' expects {expected} argument{s}, got {actual}"
            raise SemanticError(msg, line=location.line, column=location.column)

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
        self._check_arity("Function", node.name, expected, len(node.arguments), node.location)
        for arg in node.arguments:
            self._visit_expression(arg)

    def _visit_struct_def(self, node: StructDef) -> None:
        """Visit a struct definition — register as both struct and function."""
        self._scope.declare_function(node.name, len(node.fields), node.location)
        self._scope.variables[node.name] = node.location
        for f in node.fields:
            if f.type_annotation is not None:
                self._validate_type_name(f.type_annotation, node.location)

    def _visit_class_def(self, node: ClassDef) -> None:
        """Visit a class definition — register constructor, validate methods."""
        # Register constructor with arity = field count
        self._scope.declare_function(node.name, len(node.fields), node.location)
        self._scope.variables[node.name] = node.location

        # Validate field type annotations
        for f in node.fields:
            if f.type_annotation is not None:
                self._validate_type_name(f.type_annotation, node.location)

        # Pre-register method arities so methods can call each other
        method_arities: dict[str, int] = {}
        for method in node.methods:
            # First param must be 'self'
            if not method.parameters or method.parameters[0].name != "self":
                msg = f"Method '{method.name}' must have 'self' as first parameter"
                raise SemanticError(msg, line=method.location.line, column=method.location.column)

            # Reject builtin method name collisions
            if method.name in METHOD_ARITIES:
                msg = f"Method name '{method.name}' is reserved for builtin methods"
                raise SemanticError(msg, line=method.location.line, column=method.location.column)

            method_arities[method.name] = len(method.parameters) - 1

        # Register before visiting bodies so inter-method calls resolve
        self._class_methods[node.name] = method_arities

        # Now validate method bodies
        for method in node.methods:
            self._push_scope()
            self._scope.function_name = f"{node.name}.{method.name}"
            for param in method.parameters:
                self._scope.declare_variable(param.name, method.location)
                if param.type_annotation is not None and param.name != "self":
                    self._validate_type_name(param.type_annotation, method.location)
            if method.return_type is not None:
                self._validate_type_name(method.return_type, method.location)
            prev_in_function = self._in_function
            self._in_function = True
            for stmt in method.body:
                self._visit_statement(stmt)
            self._in_function = prev_in_function
            self._pop_scope()

    def _visit_field_access(self, node: FieldAccess) -> None:
        """Visit a field access — validate target, defer field check to runtime."""
        self._visit_expression(node.target)

    def _visit_field_assignment(self, node: FieldAssignment) -> None:
        """Visit a field assignment — validate target and value expressions."""
        self._visit_expression(node.target)
        self._visit_expression(node.value)

    # -- Import registration (called by resolver before analyze()) ----------

    def register_imported_function(self, name: str, arity: int, location: SourceLocation) -> None:
        """Register an imported function in the global scope."""
        self._scope.declare_function(name, arity, location)
        self._scope.variables[name] = location

    def register_imported_struct(
        self, name: str, field_count: int, location: SourceLocation
    ) -> None:
        """Register an imported struct in the global scope."""
        self._scope.declare_function(name, field_count, location)
        self._scope.variables[name] = location

    def register_imported_class(
        self,
        name: str,
        field_count: int,
        method_arities: dict[str, int],
        location: SourceLocation,
    ) -> None:
        """Register an imported class in the global scope."""
        self._scope.declare_function(name, field_count, location)
        self._scope.variables[name] = location
        # Register method arities so _visit_method_call can validate calls
        self._class_methods[name] = dict(method_arities)

    def reset_import_barrier(self) -> None:
        """Reset the import-ordering flag (for REPL re-entry)."""
        self._past_imports = False

    def _visit_method_call(self, node: MethodCall) -> None:
        """Visit a method call — validate method name and argument count."""
        self._visit_expression(node.target)

        # Builtin method path
        if node.method in METHOD_ARITIES:
            self._check_arity(
                "Method",
                node.method,
                METHOD_ARITIES[node.method],
                len(node.arguments),
                node.location,
            )
            for arg in node.arguments:
                self._visit_expression(arg)
            return

        # Class instance method path — check if ANY class defines this method.
        # We intentionally allow any class method on any instance because the
        # target's concrete type is unknown at static-analysis time; the VM
        # performs the real type check at runtime.
        for methods in self._class_methods.values():
            if node.method in methods:
                self._check_arity(
                    "Method",
                    node.method,
                    methods[node.method],
                    len(node.arguments),
                    node.location,
                )
                for arg in node.arguments:
                    self._visit_expression(arg)
                return

        msg = f"Unknown method '{node.method}'"
        raise SemanticError(msg, line=node.location.line, column=node.location.column)
