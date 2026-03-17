"""Semantic analyzer for the Pebble language.

Walk the AST to check that a program makes logical sense before compilation.
Catch errors the parser cannot — undeclared variables, duplicate declarations,
arity mismatches, and return statements outside functions.

The analyzer uses a linked-list of :class:`Scope` objects to implement
block scoping: each block (``if``, ``while``, ``for``, ``fn``) introduces
a new child scope.  Variable lookup walks the chain toward the root.
"""

from dataclasses import dataclass, field
from typing import ClassVar

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
    EnumPattern,
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
    Program,
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
    TypeAnnotation,
    UnaryOp,
    UnpackAssignment,
    UnpackConstAssignment,
    UnpackReassignment,
    WhileLoop,
    WildcardPattern,
    YieldStatement,
)
from pebble.builtins import BUILTIN_ARITIES, METHOD_ARITIES, Arity
from pebble.errors import SemanticError
from pebble.tokens import SourceLocation

# -- Dunder method arities ---------------------------------------------------

_DUNDER_ARITIES: dict[str, int] = {
    # Binary operators (self + other)
    "__add__": 2,
    "__sub__": 2,
    "__mul__": 2,
    "__div__": 2,
    "__floordiv__": 2,
    "__mod__": 2,
    "__pow__": 2,
    # Comparison operators (self, other)
    "__eq__": 2,
    "__ne__": 2,
    "__lt__": 2,
    "__le__": 2,
    "__gt__": 2,
    "__ge__": 2,
    # Unary operators (self only)
    "__neg__": 1,
    # String representation (self only)
    "__str__": 1,
}

# -- Built-in declarations ---------------------------------------------------

_BUILTIN_LOCATION = SourceLocation(line=0, column=0)

_BUILTIN_TYPES = frozenset(
    {
        "Int",
        "Float",
        "String",
        "Bool",
        "Null",
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

    variables: dict[str, SourceLocation] = field(default_factory=lambda: {})
    functions: dict[str, tuple[Arity, SourceLocation]] = field(default_factory=lambda: {})
    constants: set[str] = field(default_factory=lambda: set())
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
        self._in_async_function = False
        self._loop_depth = 0
        self._try_depth = 0
        self._past_imports = False
        self._cell_vars: dict[str, set[str]] = {}
        self._free_vars: dict[str, set[str]] = {}
        self._class_methods: dict[str, dict[str, int]] = {}
        self._class_parents: dict[str, str] = {}
        self._class_fields: dict[str, list[str]] = {}
        self._enums: dict[str, list[str]] = {}

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

    @property
    def enums(self) -> dict[str, list[str]]:
        """Map of enum name → list of variant names."""
        return self._enums

    @property
    def class_parents(self) -> dict[str, str]:
        """Map of child class name → parent class name."""
        return self._class_parents

    @property
    def class_fields(self) -> dict[str, list[str]]:
        """Map of class name → full field list (including inherited)."""
        return self._class_fields

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
        if self._scope.parent is None:
            msg = "Cannot pop the global scope"
            raise RuntimeError(msg)
        self._scope = self._scope.parent

    _GENERIC_PARAM_COUNTS: ClassVar[dict[str, int]] = {"List": 1, "Dict": 2}

    def _validate_type_annotation(
        self, annotation: TypeAnnotation, location: SourceLocation
    ) -> None:
        """Validate a type annotation recursively.

        Check that the base type is known, the parameter count matches for
        generic types, and all inner type parameters are themselves valid.
        """
        name = annotation.name
        # Check base type exists (builtins, struct/class constructors, or enums)
        if (
            name not in _BUILTIN_TYPES
            and self._scope.resolve_function(name) is None
            and name not in self._enums
        ):
            msg = f"Unknown type '{name}'"
            raise SemanticError(msg, line=location.line, column=location.column)

        # Check type parameter count
        if annotation.params:
            if name in self._GENERIC_PARAM_COUNTS:
                expected = self._GENERIC_PARAM_COUNTS[name]
                actual = len(annotation.params)
                if actual != expected:
                    s = "s" if expected != 1 else ""
                    msg = f"{name} expects {expected} type parameter{s}, got {actual}"
                    raise SemanticError(msg, line=location.line, column=location.column)
            else:
                msg = f"{name} does not accept type parameters"
                raise SemanticError(msg, line=location.line, column=location.column)

        # Recursively validate inner type parameters
        for param in annotation.params:
            self._validate_type_annotation(param, location)

    # -- Statement dispatch ---------------------------------------------------

    def _visit_statement(self, stmt: Statement) -> None:  # noqa: C901, PLR0912, PLR0915
        """Dispatch to the appropriate visitor based on statement type."""
        self._enforce_import_ordering(stmt)

        match stmt:
            # Variable declarations and reassignments
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
            # Control flow
            case IfStatement():
                self._visit_if(stmt)
            case WhileLoop():
                self._visit_while(stmt)
            case ForLoop():
                self._visit_for(stmt)
            case MatchStatement():
                self._visit_match(stmt)
            # Definitions
            case FunctionDef():
                self._visit_function_def(stmt)
            case AsyncFunctionDef():
                self._visit_async_function_def(stmt)
            case ReturnStatement():
                self._visit_return(stmt)
            case YieldStatement():
                self._visit_yield(stmt)
            case StructDef():
                self._visit_struct_def(stmt)
            case ClassDef():
                self._visit_class_def(stmt)
            case EnumDef():
                self._visit_enum_def(stmt)
            # Other statements
            case IndexAssignment():
                self._visit_index_assignment(stmt)
            case FieldAssignment():
                self._visit_field_assignment(stmt)
            case BreakStatement():
                self._visit_break(stmt)
            case ContinueStatement():
                self._visit_continue(stmt)
            case TryCatch():
                self._visit_try(stmt)
            case ThrowStatement():
                self._visit_throw(stmt)
            case ImportStatement() | FromImportStatement():
                pass  # Names registered by resolver before analyze()
            case _:
                # Expression statements (e.g. bare function calls)
                self._visit_expression(stmt)  # type: ignore[arg-type]

    def _enforce_import_ordering(self, stmt: Statement) -> None:
        """Ensure all imports appear before non-import statements."""
        if isinstance(stmt, ImportStatement | FromImportStatement):
            if self._past_imports:
                loc = stmt.location
                msg = "Imports must appear at the top of the file"
                raise SemanticError(msg, line=loc.line, column=loc.column)
        else:
            self._past_imports = True

    # -- Statement visitors ---------------------------------------------------

    def _visit_assignment(self, node: Assignment) -> None:
        """Visit a ``let`` declaration — check value, then declare name."""
        self._visit_expression(node.value)
        if node.type_annotation is not None:
            self._validate_type_annotation(node.type_annotation, node.location)
        self._scope.declare_variable(node.name, node.location)

    def _visit_const_assignment(self, node: ConstAssignment) -> None:
        """Visit a ``const`` declaration — check value, then declare as constant."""
        self._visit_expression(node.value)
        if node.type_annotation is not None:
            self._validate_type_annotation(node.type_annotation, node.location)
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
                    IntegerLiteral | FloatLiteral | StringLiteral | BooleanLiteral | NullLiteral,
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
                self._validate_type_annotation(param.type_annotation, node.location)
        if node.return_type is not None:
            self._validate_type_annotation(node.return_type, node.location)
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

    def _visit_yield(self, node: YieldStatement) -> None:
        """Visit a ``yield`` statement — must be inside a function, not in try or async."""
        if not self._in_function:
            msg = "Yield statement outside function"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
        if self._in_async_function:
            msg = "Cannot use yield inside an async function"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
        if self._try_depth > 0:
            msg = "Yield inside try block is not supported"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
        if node.value is not None:
            self._visit_expression(node.value)

    def _visit_async_function_def(self, node: AsyncFunctionDef) -> None:
        """Visit an ``async fn`` definition — like function def but sets async flag."""
        self._visit_async_function_body(node)
        self._scope.variables[node.name] = node.location

    def _visit_async_function_body(self, node: AsyncFunctionDef | FunctionExpression) -> None:
        """Visit the shared scope/param/body logic for async functions."""
        # Validate default parameter ordering and literal-only restriction
        seen_default = False
        for param in node.parameters:
            if param.default is not None:
                seen_default = True
                if not isinstance(
                    param.default,
                    IntegerLiteral | FloatLiteral | StringLiteral | BooleanLiteral | NullLiteral,
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
                self._validate_type_annotation(param.type_annotation, node.location)
        if node.return_type is not None:
            self._validate_type_annotation(node.return_type, node.location)
        prev_in_function = self._in_function
        prev_in_async = self._in_async_function
        self._in_function = True
        self._in_async_function = True
        for stmt in node.body:
            self._visit_statement(stmt)
        self._in_function = prev_in_function
        self._in_async_function = prev_in_async
        self._pop_scope()

    def _visit_await(self, node: AwaitExpression) -> None:
        """Visit an ``await`` expression — must be inside an async function."""
        if not self._in_async_function:
            msg = "Cannot use await outside an async function"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)
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
        self._try_depth += 1
        self._visit_block(node.body)
        self._try_depth -= 1
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

            if isinstance(case.pattern, EnumPattern):
                self._validate_enum_pattern(case.pattern)

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

    def _visit_expression(self, expr: Expression) -> None:  # noqa: C901, PLR0912
        """Dispatch to the appropriate visitor based on expression type."""
        match expr:
            case Identifier():
                self._visit_identifier(expr)
            case BinaryOp():
                self._visit_binary_op(expr)
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
                self._visit_dict_literal(expr)
            case IndexAccess() | SliceAccess():
                self._visit_index_or_slice(expr)
            # Member access
            case MethodCall():
                self._visit_method_call(expr)
            case FieldAccess():
                self._visit_field_access(expr)
            case SuperMethodCall():
                self._visit_super_method_call(expr)
            case FunctionExpression():
                self._visit_function_expression(expr)
            case AwaitExpression():
                self._visit_await(expr)
            case (
                IntegerLiteral()
                | FloatLiteral()
                | StringLiteral()
                | BooleanLiteral()
                | NullLiteral()
            ):
                pass  # Literals need no semantic checks

    def _visit_binary_op(self, node: BinaryOp) -> None:
        """Visit a binary operation — check both operands."""
        self._visit_expression(node.left)
        self._visit_expression(node.right)

    def _visit_dict_literal(self, node: DictLiteral) -> None:
        """Visit a dict literal — check all key-value pairs."""
        for key, value in node.entries:
            self._visit_expression(key)
            self._visit_expression(value)

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
            # Enum names are not callable
            if node.name in self._enums:
                msg = f"'{node.name}' is an enum, not a function"
                raise SemanticError(msg, line=node.location.line, column=node.location.column)
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
                self._validate_type_annotation(f.type_annotation, node.location)

    def _visit_class_def(self, node: ClassDef) -> None:
        """Visit a class definition — register constructor, validate methods."""
        for f in node.fields:
            if f.type_annotation is not None:
                self._validate_type_annotation(f.type_annotation, node.location)

        all_fields, inherited_methods = self._validate_class_inheritance(node)

        all_fields.extend(f.name for f in node.fields)
        self._class_fields[node.name] = all_fields

        self._scope.declare_function(node.name, len(all_fields), node.location)
        self._scope.variables[node.name] = node.location

        method_arities = self._register_class_methods(node, inherited_methods)
        self._class_methods[node.name] = method_arities

        self._visit_class_method_bodies(node)

    def _validate_class_inheritance(self, node: ClassDef) -> tuple[list[str], dict[str, int]]:
        """Validate the parent class and collect inherited fields and methods.

        Return a ``(field_list, method_dict)`` pair.  The field list contains
        ancestor fields in declaration order; the method dict maps inherited
        method names to their user-visible arities (excluding ``self``).
        """
        all_fields: list[str] = []
        inherited_methods: dict[str, int] = {}

        if node.parent is None:
            return all_fields, inherited_methods

        if node.parent == node.name:
            msg = "A class cannot extend itself"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)

        if node.parent not in self._class_methods:
            self._raise_bad_parent_error(node.parent, node.location)

        parent_fields = self._get_all_fields(node.parent)
        all_fields.extend(parent_fields)

        parent_field_set = set(parent_fields)
        for f in node.fields:
            if f.name in parent_field_set:
                msg = f"Duplicate field '{f.name}' (already inherited from '{node.parent}')"
                raise SemanticError(msg, line=node.location.line, column=node.location.column)

        inherited_methods = dict(self._class_methods[node.parent])
        self._class_parents[node.name] = node.parent
        return all_fields, inherited_methods

    def _raise_bad_parent_error(self, parent: str, location: SourceLocation) -> None:
        """Raise an appropriate error when a parent class reference is invalid."""
        if parent in self._enums:
            msg = f"'{parent}' is an enum, not a class"
        elif self._scope.resolve_function(parent) is not None:
            msg = f"'{parent}' is not a class"
        else:
            msg = f"Unknown parent class '{parent}'"
        raise SemanticError(msg, line=location.line, column=location.column)

    def _register_class_methods(
        self, node: ClassDef, inherited_methods: dict[str, int]
    ) -> dict[str, int]:
        """Validate and pre-register method arities for *node*.

        Return the full method-arity dict (inherited + own) so that
        inter-method calls resolve during body analysis.
        """
        method_arities: dict[str, int] = dict(inherited_methods)
        for method in node.methods:
            self._validate_method_signature(method)
            method_arities[method.name] = len(method.parameters) - 1
        return method_arities

    def _validate_method_signature(self, method: FunctionDef) -> None:
        """Check that *method* has ``self`` first, no builtin name clash, and valid dunder arity."""
        if not method.parameters or method.parameters[0].name != "self":
            msg = f"Method '{method.name}' must have 'self' as first parameter"
            raise SemanticError(msg, line=method.location.line, column=method.location.column)

        if method.name in METHOD_ARITIES:
            msg = f"Method name '{method.name}' is reserved for builtin methods"
            raise SemanticError(msg, line=method.location.line, column=method.location.column)

        if method.name in _DUNDER_ARITIES:
            expected = _DUNDER_ARITIES[method.name]
            actual = len(method.parameters)
            if actual != expected:
                s = "" if expected == 1 else "s"
                msg = (
                    f"Dunder method '{method.name}' requires {expected} parameter{s}, got {actual}"
                )
                raise SemanticError(msg, line=method.location.line, column=method.location.column)

    def _visit_class_method_bodies(self, node: ClassDef) -> None:
        """Visit each method body in *node*, validating parameters and statements."""
        for method in node.methods:
            self._push_scope()
            self._scope.function_name = f"{node.name}.{method.name}"
            for param in method.parameters:
                self._scope.declare_variable(param.name, method.location)
                if param.type_annotation is not None and param.name != "self":
                    self._validate_type_annotation(param.type_annotation, method.location)
            if method.return_type is not None:
                self._validate_type_annotation(method.return_type, method.location)
            prev_in_function = self._in_function
            self._in_function = True
            for stmt in method.body:
                self._visit_statement(stmt)
            self._in_function = prev_in_function
            self._pop_scope()

    def _visit_enum_def(self, node: EnumDef) -> None:
        """Visit an enum definition — register name as variable, store variants."""
        self._scope.declare_variable(node.name, node.location)
        self._enums[node.name] = list(node.variants)

    def _get_all_fields(self, class_name: str) -> list[str]:
        """Walk the parent chain to collect fields in ancestor-first order."""
        if class_name in self._class_fields:
            return list(self._class_fields[class_name])
        return []

    def _visit_super_method_call(self, node: SuperMethodCall) -> None:
        """Visit a ``super.method(args)`` call — validate context and arity."""
        # Must be inside a method (function name has form "ClassName.method")
        fn_name = self._scope.owning_function
        if fn_name is None or "." not in fn_name:
            msg = "'super' can only be used inside a method"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)

        class_name = fn_name.split(".")[0]

        # Class must have a parent
        if class_name not in self._class_parents:
            msg = f"'super' used in class '{class_name}' which has no parent"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)

        parent_name = self._class_parents[class_name]

        # Parent must have the called method
        if (
            parent_name not in self._class_methods
            or node.method not in self._class_methods[parent_name]
        ):
            msg = f"Parent class '{parent_name}' has no method '{node.method}'"
            raise SemanticError(msg, line=node.location.line, column=node.location.column)

        # Check arity (excluding self)
        expected = self._class_methods[parent_name][node.method]
        self._check_arity("Method", node.method, expected, len(node.arguments), node.location)

        for arg in node.arguments:
            self._visit_expression(arg)

    def _visit_field_access(self, node: FieldAccess) -> None:
        """Visit a field access — validate enum variants, or defer to runtime."""
        if isinstance(node.target, Identifier) and node.target.name in self._enums:
            variants = self._enums[node.target.name]
            if node.field not in variants:
                msg = f"Enum '{node.target.name}' has no variant '{node.field}'"
                raise SemanticError(msg, line=node.location.line, column=node.location.column)
            return
        self._visit_expression(node.target)

    def _visit_field_assignment(self, node: FieldAssignment) -> None:
        """Visit a field assignment — validate target and value expressions."""
        self._visit_expression(node.target)
        self._visit_expression(node.value)

    # -- Import registration (called by resolver before analyze()) ----------

    def register_imported_function(
        self, name: str, arity: int | tuple[int, ...], location: SourceLocation
    ) -> None:
        """Register an imported function in the global scope."""
        self._scope.declare_function(name, arity, location)
        self._scope.variables[name] = location

    def register_imported_constant(self, name: str, location: SourceLocation) -> None:
        """Register an imported constant (stdlib value) in the global scope."""
        self._scope.declare_variable(name, location)

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
        *,
        fields: list[str] | None = None,
    ) -> None:
        """Register an imported class in the global scope."""
        self._scope.declare_function(name, field_count, location)
        self._scope.variables[name] = location
        # Register method arities so _visit_method_call can validate calls
        self._class_methods[name] = dict(method_arities)
        if fields is not None:
            self._class_fields[name] = list(fields)

    def register_imported_enum(
        self, name: str, variants: list[str], location: SourceLocation
    ) -> None:
        """Register an imported enum in the global scope."""
        self._scope.declare_variable(name, location)
        self._enums[name] = list(variants)

    def register_imported_class_parent(
        self, name: str, parent: str, parent_fields: list[str]
    ) -> None:
        """Register an imported class's parent relationship."""
        self._class_parents[name] = parent
        self._class_fields[name] = list(parent_fields)

    def _validate_enum_pattern(self, pattern: EnumPattern) -> None:
        """Validate that an enum pattern references a known enum and variant."""
        if pattern.enum_name not in self._enums:
            msg = f"Unknown enum '{pattern.enum_name}'"
            raise SemanticError(msg, line=pattern.location.line, column=pattern.location.column)
        variants = self._enums[pattern.enum_name]
        if pattern.variant_name not in variants:
            msg = f"Enum '{pattern.enum_name}' has no variant '{pattern.variant_name}'"
            raise SemanticError(msg, line=pattern.location.line, column=pattern.location.column)

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

        # Class instance method path — collect all arities from every class
        # that defines this method.  We intentionally allow any class method on
        # any instance because the target's concrete type is unknown at
        # static-analysis time; the VM performs the real type check at runtime.
        matching_arities: set[int] = set()
        for methods in self._class_methods.values():
            if node.method in methods:
                matching_arities.add(methods[node.method])

        if matching_arities:
            actual = len(node.arguments)
            if actual not in matching_arities:
                # Pick the first arity for the error message
                expected = sorted(matching_arities)[0]
                self._check_arity("Method", node.method, expected, actual, node.location)
            for arg in node.arguments:
                self._visit_expression(arg)
            return

        msg = f"Unknown method '{node.method}'"
        raise SemanticError(msg, line=node.location.line, column=node.location.column)
