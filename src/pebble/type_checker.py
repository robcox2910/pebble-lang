"""Static type checker for the Pebble language.

Walk the analyzed AST between semantic analysis and compilation to catch
type mismatches *before* the program runs.  Think of it as a spell-checker
for types — it catches obvious mistakes early, but the runtime type checks
remain as a safety net for dynamic values.

Pipeline position::

    Lexer → Parser → Analyzer → **Type Checker** → Compiler → Optimizer → VM

The checker uses **gradual typing**: unannotated code is left alone
(assigned the ``UNKNOWN`` sentinel), and ``UNKNOWN`` is compatible with
every type.  Only annotated targets are validated against the inferred
type of the value they receive.
"""

from __future__ import annotations

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import (
    ArrayLiteral,
    Assignment,
    AsyncFunctionDef,
    BinaryOp,
    BooleanLiteral,
    ClassDef,
    ConstAssignment,
    DictLiteral,
    EnumDef,
    Expression,
    FieldAccess,
    FieldAssignment,
    FloatLiteral,
    ForLoop,
    FunctionCall,
    FunctionDef,
    FunctionExpression,
    Identifier,
    IfStatement,
    IntegerLiteral,
    ListComprehension,
    MatchStatement,
    NullLiteral,
    Parameter,
    PrintStatement,
    Program,
    Reassignment,
    ReturnStatement,
    Statement,
    StringInterpolation,
    StringLiteral,
    StructDef,
    TryCatch,
    TypeAnnotation,
    UnaryOp,
    WhileLoop,
)
from pebble.errors import SemanticError
from pebble.tokens import SourceLocation

# ---------------------------------------------------------------------------
# Sentinel for unknown / uninferrable types
# ---------------------------------------------------------------------------

UNKNOWN = TypeAnnotation(name="Unknown")
"""Sentinel representing a type that cannot be determined statically.

Compatible with every other type — this is the gradual-typing escape hatch.
"""

# ---------------------------------------------------------------------------
# Built-in type annotations
# ---------------------------------------------------------------------------

_INT = TypeAnnotation(name="Int")
_FLOAT = TypeAnnotation(name="Float")
_STRING = TypeAnnotation(name="String")
_BOOL = TypeAnnotation(name="Bool")
_NULL = TypeAnnotation(name="Null")
_LIST = TypeAnnotation(name="List")
_DICT = TypeAnnotation(name="Dict")
_FN = TypeAnnotation(name="Fn")

# ---------------------------------------------------------------------------
# Type compatibility
# ---------------------------------------------------------------------------


def _types_compatible(expected: TypeAnnotation, actual: TypeAnnotation) -> bool:
    """Return True if *actual* is assignable to a slot expecting *expected*.

    Rules:
    1. Either type is ``UNKNOWN`` → compatible (gradual typing).
    2. Names differ → incompatible.
    3. Both bare (no params) → compatible if names match.
    4. One has params, the other is bare → compatible (bare ``List`` matches ``List[Int]``).
    5. Both have params → check each param recursively.
    """
    if UNKNOWN in (expected, actual):
        return True
    if expected.name != actual.name:
        return False
    if not expected.params or not actual.params:
        return True
    if len(expected.params) != len(actual.params):
        return False
    return all(
        _types_compatible(ep, ap) for ep, ap in zip(expected.params, actual.params, strict=True)
    )


# ---------------------------------------------------------------------------
# Scoped type environment
# ---------------------------------------------------------------------------


class _TypeEnv:
    """A scoped type environment mapping variable names to inferred types."""

    def __init__(self, parent: _TypeEnv | None = None) -> None:
        """Create a new scope, optionally chained to *parent*."""
        self._bindings: dict[str, TypeAnnotation] = {}
        self._parent = parent

    def define(self, name: str, typ: TypeAnnotation) -> None:
        """Bind *name* to *typ* in this scope."""
        self._bindings[name] = typ

    def lookup(self, name: str) -> TypeAnnotation:
        """Look up *name* in the scope chain; return ``UNKNOWN`` if absent."""
        if name in self._bindings:
            return self._bindings[name]
        if self._parent is not None:
            return self._parent.lookup(name)
        return UNKNOWN

    def child(self) -> _TypeEnv:
        """Create a new child scope."""
        return _TypeEnv(parent=self)


# ---------------------------------------------------------------------------
# Type checker
# ---------------------------------------------------------------------------


class TypeChecker:
    """Walk the analyzed AST and raise ``SemanticError`` on type mismatches.

    Usage::

        program, analyzer = analyze_with_context(source)
        TypeChecker(program, analyzer=analyzer).check()

    """

    def __init__(self, program: Program, *, analyzer: SemanticAnalyzer) -> None:
        """Create a type checker for *program* using metadata from *analyzer*."""
        self._program = program
        self._analyzer = analyzer
        self._env = _TypeEnv()
        self._current_return_type: TypeAnnotation | None = None

        # Populated during the first pass
        self._function_sigs: dict[str, tuple[list[Parameter], TypeAnnotation | None]] = {}
        self._struct_fields: dict[str, list[Parameter]] = {}

    # -- Public API -----------------------------------------------------------

    def check(self) -> None:
        """Run the type checker on the program.

        Performs a two-pass walk: first collects all function/struct/class
        signatures, then checks types.
        """
        self._collect_signatures()
        for stmt in self._program.statements:
            self._visit_statement(stmt)

    # -- Pass 1: signature collection -----------------------------------------

    def _collect_signatures(self) -> None:
        """Collect function and struct signatures from top-level statements."""
        for stmt in self._program.statements:
            match stmt:
                case FunctionDef():
                    self._function_sigs[stmt.name] = (stmt.parameters, stmt.return_type)
                case AsyncFunctionDef():
                    self._function_sigs[stmt.name] = (stmt.parameters, stmt.return_type)
                case StructDef():
                    self._struct_fields[stmt.name] = list(stmt.fields)
                    self._function_sigs[stmt.name] = (stmt.fields, None)
                case ClassDef():
                    self._struct_fields[stmt.name] = list(stmt.fields)
                    self._function_sigs[stmt.name] = (stmt.fields, None)
                case _:
                    pass

    # -- Statement dispatch ---------------------------------------------------

    def _visit_statement(self, stmt: Statement) -> None:  # noqa: C901, PLR0912
        """Dispatch to the appropriate visitor based on statement type."""
        match stmt:
            case Assignment():
                self._visit_assignment(stmt)
            case ConstAssignment():
                self._visit_const_assignment(stmt)
            case Reassignment():
                pass  # Reassignment type tracking is runtime-only
            case PrintStatement():
                pass  # No type constraints on print
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
                self._visit_return(stmt)
            case StructDef():
                pass  # Signatures already collected
            case ClassDef():
                self._visit_class_def(stmt)
            case EnumDef():
                pass  # Enum variants are not type-checked
            case MatchStatement():
                self._visit_match(stmt)
            case TryCatch():
                self._visit_try(stmt)
            case FieldAssignment():
                pass  # Field reassignment is runtime-only
            case _:
                # Expression statements (bare function calls, etc.)
                self._infer_expression(stmt)  # type: ignore[arg-type]

    # -- Statement visitors ---------------------------------------------------

    def _visit_assignment(self, node: Assignment) -> None:
        """Check a ``let`` declaration against its type annotation."""
        inferred = self._infer_expression(node.value)
        if node.type_annotation is not None:
            self._check_assignable(node.type_annotation, inferred, node.location)
            self._env.define(node.name, node.type_annotation)
        else:
            self._env.define(node.name, inferred)

    def _visit_const_assignment(self, node: ConstAssignment) -> None:
        """Check a ``const`` declaration against its type annotation."""
        inferred = self._infer_expression(node.value)
        if node.type_annotation is not None:
            self._check_assignable(node.type_annotation, inferred, node.location)
            self._env.define(node.name, node.type_annotation)
        else:
            self._env.define(node.name, inferred)

    def _visit_if(self, node: IfStatement) -> None:
        """Visit an if/else — bodies in child scopes."""
        self._visit_block(node.body)
        if node.else_body is not None:
            self._visit_block(node.else_body)

    def _visit_while(self, node: WhileLoop) -> None:
        """Visit a while loop body in a child scope."""
        self._visit_block(node.body)

    def _visit_for(self, node: ForLoop) -> None:
        """Visit a for loop body in a child scope."""
        env = self._env.child()
        env.define(node.variable, UNKNOWN)
        prev = self._env
        self._env = env
        for stmt in node.body:
            self._visit_statement(stmt)
        self._env = prev

    def _visit_function_def(self, node: FunctionDef) -> None:
        """Visit a function body — check returns against declared return type."""
        self._env.define(node.name, _FN)
        env = self._env.child()
        for param in node.parameters:
            env.define(param.name, param.type_annotation or UNKNOWN)
        prev_env = self._env
        prev_return = self._current_return_type
        self._env = env
        self._current_return_type = node.return_type
        for stmt in node.body:
            self._visit_statement(stmt)
        self._env = prev_env
        self._current_return_type = prev_return

    def _visit_async_function_def(self, node: AsyncFunctionDef) -> None:
        """Visit an async function body — same as function def."""
        self._env.define(node.name, _FN)
        env = self._env.child()
        for param in node.parameters:
            env.define(param.name, param.type_annotation or UNKNOWN)
        prev_env = self._env
        prev_return = self._current_return_type
        self._env = env
        self._current_return_type = node.return_type
        for stmt in node.body:
            self._visit_statement(stmt)
        self._env = prev_env
        self._current_return_type = prev_return

    def _visit_return(self, node: ReturnStatement) -> None:
        """Check a return statement against the enclosing function's return type."""
        if self._current_return_type is None:
            return
        actual = _NULL if node.value is None else self._infer_expression(node.value)
        self._check_assignable(self._current_return_type, actual, node.location)

    def _visit_class_def(self, node: ClassDef) -> None:
        """Visit class methods — check return types and param types."""
        for method in node.methods:
            env = self._env.child()
            for param in method.parameters:
                env.define(param.name, param.type_annotation or UNKNOWN)
            prev_env = self._env
            prev_return = self._current_return_type
            self._env = env
            self._current_return_type = method.return_type
            for stmt in method.body:
                self._visit_statement(stmt)
            self._env = prev_env
            self._current_return_type = prev_return

    def _visit_match(self, node: MatchStatement) -> None:
        """Visit match case bodies in child scopes."""
        for case in node.cases:
            self._visit_block(case.body)

    def _visit_try(self, node: TryCatch) -> None:
        """Visit try/catch/finally bodies."""
        self._visit_block(node.body)
        self._visit_block(node.catch_body)
        if node.finally_body is not None:
            self._visit_block(node.finally_body)

    def _visit_block(self, stmts: list[Statement]) -> None:
        """Visit a block of statements in a new child scope."""
        prev = self._env
        self._env = self._env.child()
        for stmt in stmts:
            self._visit_statement(stmt)
        self._env = prev

    # -- Expression type inference --------------------------------------------

    def _infer_expression(self, expr: Expression) -> TypeAnnotation:  # noqa: C901, PLR0911, PLR0912
        """Infer the static type of *expr*."""
        match expr:
            case IntegerLiteral():
                return _INT
            case FloatLiteral():
                return _FLOAT
            case StringLiteral():
                return _STRING
            case BooleanLiteral():
                return _BOOL
            case NullLiteral():
                return _NULL
            case Identifier():
                return self._env.lookup(expr.name)
            case BinaryOp():
                return self._infer_binary_op(expr)
            case UnaryOp():
                return self._infer_unary_op(expr)
            case FunctionCall():
                return self._infer_function_call(expr)
            case StringInterpolation():
                return _STRING
            case ArrayLiteral():
                return _LIST
            case ListComprehension():
                return _LIST
            case DictLiteral():
                return _DICT
            case FieldAccess():
                return self._infer_field_access(expr)
            case FunctionExpression():
                return _FN
            case _:
                return UNKNOWN

    # -- Binary op inference --------------------------------------------------

    def _infer_binary_op(self, node: BinaryOp) -> TypeAnnotation:  # noqa: PLR0911
        """Infer the result type of a binary operation."""
        left = self._infer_expression(node.left)
        right = self._infer_expression(node.right)

        # Comparison operators always return Bool
        if node.operator in {"==", "!=", "<", "<=", ">", ">="}:
            return _BOOL

        # Logical operators always return Bool
        if node.operator in {"and", "or"}:
            return _BOOL

        # Bitwise operators: both Int → Int
        if node.operator in {"&", "|", "^", "<<", ">>"}:
            if left == _INT and right == _INT:
                return _INT
            return UNKNOWN

        # True division always returns Float for numeric operands
        if node.operator == "/":
            if _is_numeric(left) and _is_numeric(right):
                return _FLOAT
            return UNKNOWN

        # Addition: String + String → String
        if node.operator == "+":
            if left == _STRING and right == _STRING:
                return _STRING
            if _is_numeric(left) and _is_numeric(right):
                return _wider_numeric(left, right)
            return UNKNOWN

        # Other arithmetic: -, *, **, //, %
        if node.operator in {"-", "*", "**", "//", "%"}:
            if _is_numeric(left) and _is_numeric(right):
                return _wider_numeric(left, right)
            return UNKNOWN

        return UNKNOWN

    # -- Unary op inference ---------------------------------------------------

    def _infer_unary_op(self, node: UnaryOp) -> TypeAnnotation:
        """Infer the result type of a unary operation."""
        operand = self._infer_expression(node.operand)
        if node.operator == "not":
            return _BOOL
        if node.operator == "-":
            if operand in (_INT, _FLOAT):
                return operand
            return UNKNOWN
        if node.operator == "~":
            if operand == _INT:
                return _INT
            return UNKNOWN
        return UNKNOWN

    # -- Function call inference + checking -----------------------------------

    def _infer_function_call(self, node: FunctionCall) -> TypeAnnotation:
        """Infer the return type and check argument types of a function call."""
        # Check argument types if we know the function's signature
        if node.name in self._function_sigs:
            params, return_type = self._function_sigs[node.name]
            self._check_call_args(node, params)
            # Struct/class constructor returns the struct/class type
            if node.name in self._struct_fields:
                return TypeAnnotation(name=node.name)
            return return_type or UNKNOWN
        return UNKNOWN

    def _check_call_args(self, node: FunctionCall, params: list[Parameter]) -> None:
        """Check each argument against the corresponding parameter's type annotation."""
        for arg, param in zip(node.arguments, params, strict=False):
            if param.type_annotation is not None:
                actual = self._infer_expression(arg)
                if not _types_compatible(param.type_annotation, actual):
                    msg = (
                        f"Type error: argument '{param.name}' expected "
                        f"{param.type_annotation}, got {actual}"
                    )
                    raise SemanticError(msg, line=node.location.line, column=node.location.column)

    # -- Field access inference -----------------------------------------------

    def _infer_field_access(self, node: FieldAccess) -> TypeAnnotation:
        """Infer the type of a field access on a known struct."""
        # Infer the type of the target expression
        target_type = self._infer_expression(node.target)
        if target_type == UNKNOWN:
            return UNKNOWN
        struct_name = target_type.name
        if struct_name in self._struct_fields:
            for field in self._struct_fields[struct_name]:
                if field.name == node.field:
                    return field.type_annotation or UNKNOWN
        return UNKNOWN

    # -- Checking helpers -----------------------------------------------------

    def _check_assignable(
        self, expected: TypeAnnotation, actual: TypeAnnotation, location: SourceLocation
    ) -> None:
        """Raise ``SemanticError`` if *actual* is not assignable to *expected*."""
        if not _types_compatible(expected, actual):
            msg = f"Type error: expected {expected}, got {actual}"
            raise SemanticError(msg, line=location.line, column=location.column)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_numeric(typ: TypeAnnotation) -> bool:
    """Return True if *typ* is ``Int`` or ``Float``."""
    return typ in (_INT, _FLOAT)


def _wider_numeric(left: TypeAnnotation, right: TypeAnnotation) -> TypeAnnotation:
    """Return ``Float`` if either operand is ``Float``, else ``Int``."""
    if _FLOAT in (left, right):
        return _FLOAT
    return _INT


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def type_check(program: Program, *, analyzer: SemanticAnalyzer) -> None:
    """Walk the analyzed AST and raise ``SemanticError`` on type mismatches."""
    TypeChecker(program, analyzer=analyzer).check()
