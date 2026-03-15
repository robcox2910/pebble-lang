"""Bytecode compiler for the Pebble language.

Walk a validated AST and emit stack-based bytecode instructions. The compiler
produces a :class:`CompiledProgram` containing a *main* :class:`CodeObject`
(the top-level program) and a dictionary of per-function ``CodeObject``s.

The semantic analyzer is assumed to have already validated the program, so the
compiler does not duplicate error checking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pebble.ast_nodes import (
    ArrayLiteral,
    Assignment,
    BinaryOp,
    BooleanLiteral,
    BreakStatement,
    CapturePattern,
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
    MatchStatement,
    MethodCall,
    OrPattern,
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
from pebble.builtins import METHOD_ARITIES, METHOD_NONE
from pebble.bytecode import CodeObject, CompiledProgram, Instruction, OpCode

if TYPE_CHECKING:
    from pebble.tokens import SourceLocation

# -- Operator mapping ---------------------------------------------------------

_BINARY_OPS: dict[str, OpCode] = {
    "+": OpCode.ADD,
    "-": OpCode.SUBTRACT,
    "*": OpCode.MULTIPLY,
    "**": OpCode.POWER,
    "/": OpCode.DIVIDE,
    "//": OpCode.FLOOR_DIVIDE,
    "%": OpCode.MODULO,
    "==": OpCode.EQUAL,
    "!=": OpCode.NOT_EQUAL,
    "<": OpCode.LESS_THAN,
    "<=": OpCode.LESS_EQUAL,
    ">": OpCode.GREATER_THAN,
    ">=": OpCode.GREATER_EQUAL,
    "and": OpCode.AND,
    "or": OpCode.OR,
    "&": OpCode.BIT_AND,
    "|": OpCode.BIT_OR,
    "^": OpCode.BIT_XOR,
    "<<": OpCode.LEFT_SHIFT,
    ">>": OpCode.RIGHT_SHIFT,
}

_UNARY_OPS: dict[str, OpCode] = {
    "-": OpCode.NEGATE,
    "not": OpCode.NOT,
    "~": OpCode.BIT_NOT,
}


@dataclass
class _LoopContext:
    """Track pending break/continue jump patches for the current loop."""

    break_patches: list[int] = field(
        default_factory=lambda: [],  # noqa: PIE807
    )
    continue_patches: list[int] = field(
        default_factory=lambda: [],  # noqa: PIE807
    )
    try_depth_at_entry: int = 0


class Compiler:
    """Compile a validated AST into stack-based bytecode.

    Usage::

        program = SemanticAnalyzer().analyze(Parser(tokens).parse())
        compiled = Compiler().compile(program)

    """

    def __init__(
        self,
        *,
        cell_vars: dict[str, set[str]] | None = None,
        free_vars: dict[str, set[str]] | None = None,
    ) -> None:
        """Create a compiler with an empty main CodeObject."""
        self._main = CodeObject(name="<main>")
        self._functions: dict[str, CodeObject] = {}
        self._current = self._main
        self._loop_var_counter = 0
        self._match_var_counter = 0
        self._comp_var_counter = 0
        self._loop_contexts: list[_LoopContext] = []
        self._try_depth: int = 0
        self._structs: dict[str, list[str]] = {}
        self._struct_field_types: dict[str, dict[str, str]] = {}
        self._cell_vars = cell_vars or {}
        self._free_vars = free_vars or {}

    def _is_cell_var(self, name: str) -> bool:
        """Return True if *name* is a cell or free variable of the current function."""
        fn_name = self._current.name
        return name in self._cell_vars.get(fn_name, set()) or name in self._free_vars.get(
            fn_name, set()
        )

    # -- Public API -----------------------------------------------------------

    def compile(self, program: Program) -> CompiledProgram:
        """Compile *program* and return a :class:`CompiledProgram`."""
        for stmt in program.statements:
            self._compile_statement(stmt)
        self._emit(OpCode.HALT)
        return CompiledProgram(
            main=self._main,
            functions=self._functions,
            structs=self._structs,
            struct_field_types=self._struct_field_types,
        )

    # -- Emit helpers ---------------------------------------------------------

    def _emit(
        self,
        opcode: OpCode,
        operand: int | str | None = None,
        *,
        location: SourceLocation | None = None,
    ) -> int:
        """Append an instruction and return its index."""
        self._current.instructions.append(Instruction(opcode, operand, location=location))
        return len(self._current.instructions) - 1

    def _emit_constant(
        self,
        value: int | float | str | bool,  # noqa: FBT001
        *,
        location: SourceLocation | None = None,
    ) -> None:
        """Add *value* to the constant pool and emit LOAD_CONST."""
        idx = self._current.add_constant(value)
        self._emit(OpCode.LOAD_CONST, idx, location=location)

    def _emit_store(
        self,
        name: str,
        *,
        location: SourceLocation | None = None,
    ) -> None:
        """Emit STORE_CELL or STORE_NAME depending on closure analysis."""
        opcode = OpCode.STORE_CELL if self._is_cell_var(name) else OpCode.STORE_NAME
        self._emit(opcode, name, location=location)

    def _emit_load(
        self,
        name: str,
        *,
        location: SourceLocation | None = None,
    ) -> None:
        """Emit LOAD_CELL or LOAD_NAME depending on closure analysis."""
        opcode = OpCode.LOAD_CELL if self._is_cell_var(name) else OpCode.LOAD_NAME
        self._emit(opcode, name, location=location)

    def _current_index(self) -> int:
        """Return the index where the *next* instruction will be emitted."""
        return len(self._current.instructions)

    def _patch_jump_to(self, instruction_index: int, target: int) -> None:
        """Backpatch the jump at *instruction_index* to *target*."""
        old = self._current.instructions[instruction_index]
        self._current.instructions[instruction_index] = Instruction(
            old.opcode, target, location=old.location
        )

    def _patch_jump(self, instruction_index: int) -> None:
        """Backpatch the jump at *instruction_index* to the current position."""
        self._patch_jump_to(instruction_index, self._current_index())

    # -- Statement dispatch ---------------------------------------------------

    def _compile_statement(self, stmt: Statement) -> None:  # noqa: C901, PLR0912
        """Dispatch to the appropriate compilation method."""
        match stmt:
            case Assignment():
                self._compile_assignment(stmt)
            case UnpackAssignment():
                self._compile_unpack_assignment(stmt)
            case ConstAssignment():
                self._compile_const_assignment(stmt)
            case UnpackConstAssignment():
                self._compile_unpack_const_assignment(stmt)
            case Reassignment():
                self._compile_reassignment(stmt)
            case UnpackReassignment():
                self._compile_unpack_reassignment(stmt)
            case PrintStatement():
                self._compile_print(stmt)
            case IfStatement():
                self._compile_if(stmt)
            case WhileLoop():
                self._compile_while(stmt)
            case ForLoop():
                self._compile_for(stmt)
            case FunctionDef():
                self._compile_function_def(stmt)
            case ReturnStatement():
                self._compile_return(stmt)
            case IndexAssignment():
                self._compile_index_assignment(stmt)
            case BreakStatement():
                self._compile_break(stmt)
            case ContinueStatement():
                self._compile_continue(stmt)
            case TryCatch():
                self._compile_try(stmt)
            case ThrowStatement():
                self._compile_throw(stmt)
            case MatchStatement():
                self._compile_match(stmt)
            case StructDef():
                self._compile_struct_def(stmt)
            case FieldAssignment():
                self._compile_field_assignment(stmt)
            case ImportStatement() | FromImportStatement():
                pass  # Resolved at compile time by ModuleResolver
            case _:
                # Expression statement (e.g. bare function call)
                self._compile_expression(stmt)  # type: ignore[arg-type]
                self._emit(OpCode.POP)

    # -- Statement compilers --------------------------------------------------

    def _compile_assignment(self, node: Assignment) -> None:
        """Compile ``let name[: Type] = value``."""
        self._compile_expression(node.value)
        if node.type_annotation is not None:
            self._emit(OpCode.CHECK_TYPE, node.type_annotation, location=node.location)
        self._emit_store(node.name, location=node.location)

    def _compile_const_assignment(self, node: ConstAssignment) -> None:
        """Compile ``const name[: Type] = value`` — identical to ``let`` at bytecode level."""
        self._compile_expression(node.value)
        if node.type_annotation is not None:
            self._emit(OpCode.CHECK_TYPE, node.type_annotation, location=node.location)
        self._emit_store(node.name, location=node.location)

    def _compile_reassignment(self, node: Reassignment) -> None:
        """Compile ``name = value``."""
        self._compile_expression(node.value)
        self._emit_store(node.name, location=node.location)

    def _compile_unpack_assignment(self, node: UnpackAssignment) -> None:
        """Compile ``let x, y = value`` — emit value, UNPACK_SEQUENCE, then STORE each name."""
        self._compile_expression(node.value)
        self._emit(OpCode.UNPACK_SEQUENCE, len(node.names), location=node.location)
        for name in node.names:
            self._emit_store(name, location=node.location)

    def _compile_unpack_const_assignment(self, node: UnpackConstAssignment) -> None:
        """Compile ``const x, y = value`` — identical to unpack let at bytecode level."""
        self._compile_expression(node.value)
        self._emit(OpCode.UNPACK_SEQUENCE, len(node.names), location=node.location)
        for name in node.names:
            self._emit_store(name, location=node.location)

    def _compile_unpack_reassignment(self, node: UnpackReassignment) -> None:
        """Compile ``x, y = value`` — emit value, UNPACK_SEQUENCE, then STORE each name."""
        self._compile_expression(node.value)
        self._emit(OpCode.UNPACK_SEQUENCE, len(node.names), location=node.location)
        for name in node.names:
            self._emit_store(name, location=node.location)

    def _compile_print(self, node: PrintStatement) -> None:
        """Compile ``print(expr)``."""
        self._compile_expression(node.expression)
        self._emit(OpCode.PRINT, location=node.location)

    def _compile_if(self, node: IfStatement) -> None:
        """Compile ``if condition { body } else { else_body }``."""
        self._compile_expression(node.condition)
        jump_if_false = self._emit(OpCode.JUMP_IF_FALSE, 0, location=node.location)

        for stmt in node.body:
            self._compile_statement(stmt)

        if node.else_body is not None:
            jump_past_else = self._emit(OpCode.JUMP, 0)
            self._patch_jump(jump_if_false)
            for stmt in node.else_body:
                self._compile_statement(stmt)
            self._patch_jump(jump_past_else)
        else:
            self._patch_jump(jump_if_false)

    def _compile_while(self, node: WhileLoop) -> None:
        """Compile ``while condition { body }``."""
        loop_start = self._current_index()
        self._compile_expression(node.condition)
        exit_jump = self._emit(OpCode.JUMP_IF_FALSE, 0, location=node.location)

        self._loop_contexts.append(_LoopContext(try_depth_at_entry=self._try_depth))
        for stmt in node.body:
            self._compile_statement(stmt)
        ctx = self._loop_contexts.pop()

        # continue → back to condition check
        for patch in ctx.continue_patches:
            self._patch_jump_to(patch, loop_start)

        self._emit(OpCode.JUMP, loop_start, location=node.location)

        # break + normal exit → here (after loop)
        self._patch_jump(exit_jump)
        for patch in ctx.break_patches:
            self._patch_jump(patch)

    def _compile_for(self, node: ForLoop) -> None:
        """Compile ``for var in range(...) { body }`` as a counted while loop.

        Support three forms:
        - ``range(stop)`` — count from 0 to stop-1, step 1
        - ``range(start, stop)`` — count from start to stop-1, step 1
        - ``range(start, stop, step)`` — count with arbitrary step
        """
        counter = self._loop_var_counter
        limit_name = f"$for_limit_{counter}"
        self._loop_var_counter += 1
        loc = node.location

        match node.iterable:
            case FunctionCall(name="range"):
                args = node.iterable.arguments
            case _:  # pragma: no cover
                args = []
                self._compile_expression(node.iterable)

        nargs = len(args)

        # -- Init: set limit, step (if 3-arg), and loop variable --------------
        self._compile_for_init(args, nargs, limit_name, node.variable, counter, loc)

        # -- Condition --------------------------------------------------------
        loop_start = self._current_index()
        exit_jump = self._compile_for_condition(nargs, node.variable, limit_name, counter, loc)

        # -- Body -------------------------------------------------------------
        self._loop_contexts.append(_LoopContext(try_depth_at_entry=self._try_depth))
        for stmt in node.body:
            self._compile_statement(stmt)
        ctx = self._loop_contexts.pop()

        # continue → increment section (current position)
        for patch in ctx.continue_patches:
            self._patch_jump(patch)

        # -- Increment --------------------------------------------------------
        self._emit_load(node.variable, location=loc)
        if nargs <= 2:  # noqa: PLR2004
            self._emit_constant(1, location=loc)
        else:
            self._emit_load(f"$for_step_{counter}", location=loc)
        self._emit(OpCode.ADD, location=loc)
        self._emit_store(node.variable, location=loc)

        self._emit(OpCode.JUMP, loop_start, location=loc)

        # break + normal exit → here (after loop)
        self._patch_jump(exit_jump)
        for patch in ctx.break_patches:
            self._patch_jump(patch)

    def _compile_for_init(
        self,
        args: list[Expression],
        nargs: int,
        limit_name: str,
        variable: str,
        counter: int,
        loc: SourceLocation,
    ) -> None:
        """Emit initialisation code for a for-loop's hidden variables."""
        if nargs == 1:
            # range(stop): limit = stop, start = 0
            self._compile_expression(args[0])
            self._emit_store(limit_name, location=loc)
            self._emit_constant(0, location=loc)
            self._emit_store(variable, location=loc)
        elif nargs == 2:  # noqa: PLR2004
            # range(start, stop): limit = stop, start = start
            self._compile_expression(args[1])
            self._emit_store(limit_name, location=loc)
            self._compile_expression(args[0])
            self._emit_store(variable, location=loc)
        else:
            # Three-arg form: store step, limit, then start
            step_name = f"$for_step_{counter}"
            self._compile_expression(args[2])
            self._emit_store(step_name, location=loc)
            self._compile_expression(args[1])
            self._emit_store(limit_name, location=loc)
            self._compile_expression(args[0])
            self._emit_store(variable, location=loc)

    def _compile_for_condition(
        self,
        nargs: int,
        variable: str,
        limit_name: str,
        counter: int,
        loc: SourceLocation,
    ) -> int:
        """Emit the loop condition and return the exit-jump instruction index."""
        if nargs <= 2:  # noqa: PLR2004
            # Simple condition: i < limit
            self._emit_load(variable, location=loc)
            self._emit_load(limit_name, location=loc)
            self._emit(OpCode.LESS_THAN, location=loc)
            return self._emit(OpCode.JUMP_IF_FALSE, 0, location=loc)

        # Dynamic condition: if step > 0 then i < limit else i > limit
        step_name = f"$for_step_{counter}"
        self._emit_load(step_name, location=loc)
        self._emit_constant(0, location=loc)
        self._emit(OpCode.GREATER_THAN, location=loc)
        neg_jump = self._emit(OpCode.JUMP_IF_FALSE, 0, location=loc)
        # Positive branch: i < limit
        self._emit_load(variable, location=loc)
        self._emit_load(limit_name, location=loc)
        self._emit(OpCode.LESS_THAN, location=loc)
        done_jump = self._emit(OpCode.JUMP, 0, location=loc)
        # Negative branch: i > limit
        self._patch_jump(neg_jump)
        self._emit_load(variable, location=loc)
        self._emit_load(limit_name, location=loc)
        self._emit(OpCode.GREATER_THAN, location=loc)
        self._patch_jump(done_jump)
        return self._emit(OpCode.JUMP_IF_FALSE, 0, location=loc)

    def _compile_function_def(self, node: FunctionDef) -> None:
        """Compile a function definition into a separate CodeObject."""
        fn_code = CodeObject(name=node.name)
        fn_code.parameters = [p.name for p in node.parameters]
        fn_code.param_types = [p.type_annotation for p in node.parameters]
        fn_code.return_type = node.return_type
        fn_code.cell_variables = sorted(self._cell_vars.get(node.name, set()))
        fn_code.free_variables = sorted(self._free_vars.get(node.name, set()))
        previous = self._current
        previous_loop_counter = self._loop_var_counter
        previous_match_counter = self._match_var_counter
        previous_comp_counter = self._comp_var_counter
        previous_loop_contexts = self._loop_contexts
        previous_try_depth = self._try_depth
        self._current = fn_code
        self._loop_var_counter = 0
        self._match_var_counter = 0
        self._comp_var_counter = 0
        self._loop_contexts = []
        self._try_depth = 0

        for stmt in node.body:
            self._compile_statement(stmt)

        # Implicit return 0 if no explicit return at the end
        if not fn_code.instructions or fn_code.instructions[-1].opcode is not OpCode.RETURN:
            self._emit_constant(0)
            if node.return_type is not None:
                self._emit(OpCode.CHECK_TYPE, node.return_type)
            self._emit(OpCode.RETURN)

        self._functions[node.name] = fn_code
        self._current = previous
        self._loop_var_counter = previous_loop_counter
        self._match_var_counter = previous_match_counter
        self._comp_var_counter = previous_comp_counter
        self._loop_contexts = previous_loop_contexts
        self._try_depth = previous_try_depth

        # If the function captures variables, it's a closure — emit MAKE_CLOSURE
        if fn_code.free_variables:
            self._emit(OpCode.MAKE_CLOSURE, node.name, location=node.location)
            self._emit(OpCode.STORE_NAME, node.name, location=node.location)

    def _compile_return(self, node: ReturnStatement) -> None:
        """Compile ``return`` or ``return expr`` — pop try handlers first."""
        if node.value is not None:
            self._compile_expression(node.value)
        else:
            self._emit_constant(0, location=node.location)
        if self._current.return_type is not None:
            self._emit(OpCode.CHECK_TYPE, self._current.return_type, location=node.location)
        for _ in range(self._try_depth):
            self._emit(OpCode.POP_TRY, location=node.location)
        self._emit(OpCode.RETURN, location=node.location)

    def _compile_break(self, node: BreakStatement) -> None:
        """Compile ``break`` — emit POP_TRY for handlers inside the loop, then JUMP."""
        ctx = self._loop_contexts[-1]
        for _ in range(self._try_depth - ctx.try_depth_at_entry):
            self._emit(OpCode.POP_TRY, location=node.location)
        patch = self._emit(OpCode.JUMP, 0, location=node.location)
        ctx.break_patches.append(patch)

    def _compile_continue(self, node: ContinueStatement) -> None:
        """Compile ``continue`` — emit POP_TRY for handlers inside the loop, then JUMP."""
        ctx = self._loop_contexts[-1]
        for _ in range(self._try_depth - ctx.try_depth_at_entry):
            self._emit(OpCode.POP_TRY, location=node.location)
        patch = self._emit(OpCode.JUMP, 0, location=node.location)
        ctx.continue_patches.append(patch)

    def _compile_try(self, node: TryCatch) -> None:
        """Compile ``try { body } catch [e] { handler } [finally { cleanup }]``."""
        loc = node.location

        # SETUP_TRY catch_ip
        setup_try = self._emit(OpCode.SETUP_TRY, 0, location=loc)
        self._try_depth += 1

        # [try body]
        for stmt in node.body:
            self._compile_statement(stmt)

        # POP_TRY — normal exit removes handler
        self._emit(OpCode.POP_TRY, location=loc)
        self._try_depth -= 1

        # JUMP finally_or_end
        jump_past_catch = self._emit(OpCode.JUMP, 0, location=loc)

        # catch_ip: (handler was already popped by _unwind_exception)
        self._patch_jump(setup_try)

        # Bind or discard exception value
        if node.catch_variable is not None:
            self._emit_store(node.catch_variable, location=loc)
        else:
            self._emit(OpCode.POP, location=loc)

        # [catch body]
        for stmt in node.catch_body:
            self._compile_statement(stmt)

        # finally_ip: both normal and catch paths flow here
        self._patch_jump(jump_past_catch)
        if node.finally_body is not None:
            for stmt in node.finally_body:
                self._compile_statement(stmt)

    def _compile_throw(self, node: ThrowStatement) -> None:
        """Compile ``throw expr`` — evaluate expression and emit THROW."""
        self._compile_expression(node.value)
        self._emit(OpCode.THROW, location=node.location)

    def _compile_match(self, node: MatchStatement) -> None:
        """Compile ``match value { case pattern { body } ... }``."""
        loc = node.location
        match_var = f"$match_{self._match_var_counter}"
        self._match_var_counter += 1

        # Evaluate value and store in hidden variable
        self._compile_expression(node.value)
        self._emit(OpCode.STORE_NAME, match_var, location=loc)

        end_jumps: list[int] = []

        for case in node.cases:
            pattern = case.pattern

            match pattern:
                case LiteralPattern():
                    self._emit(OpCode.LOAD_NAME, match_var, location=loc)
                    self._emit_constant(pattern.value, location=loc)
                    self._emit(OpCode.EQUAL, location=loc)
                    skip = self._emit(OpCode.JUMP_IF_FALSE, 0, location=loc)
                    for stmt in case.body:
                        self._compile_statement(stmt)
                    end_jumps.append(self._emit(OpCode.JUMP, 0, location=loc))
                    self._patch_jump(skip)

                case OrPattern():
                    # First alternative
                    self._emit(OpCode.LOAD_NAME, match_var, location=loc)
                    self._emit_constant(pattern.patterns[0].value, location=loc)
                    self._emit(OpCode.EQUAL, location=loc)
                    # Remaining alternatives: OR-chain
                    for alt in pattern.patterns[1:]:
                        self._emit(OpCode.LOAD_NAME, match_var, location=loc)
                        self._emit_constant(alt.value, location=loc)
                        self._emit(OpCode.EQUAL, location=loc)
                        self._emit(OpCode.OR, location=loc)
                    skip = self._emit(OpCode.JUMP_IF_FALSE, 0, location=loc)
                    for stmt in case.body:
                        self._compile_statement(stmt)
                    end_jumps.append(self._emit(OpCode.JUMP, 0, location=loc))
                    self._patch_jump(skip)

                case CapturePattern():
                    # Bind value to capture variable, then body (always last)
                    self._emit(OpCode.LOAD_NAME, match_var, location=loc)
                    self._emit(OpCode.STORE_NAME, pattern.name, location=loc)
                    for stmt in case.body:
                        self._compile_statement(stmt)

                case WildcardPattern():
                    # Always matches, no test needed (always last)
                    for stmt in case.body:
                        self._compile_statement(stmt)

        # Backpatch all end jumps
        for jump_idx in end_jumps:
            self._patch_jump(jump_idx)

    # -- Expression dispatch --------------------------------------------------

    def _compile_expression(self, expr: Expression) -> None:  # noqa: PLR0912
        """Dispatch to the appropriate expression compiler."""
        match expr:
            case IntegerLiteral() | FloatLiteral() | StringLiteral() | BooleanLiteral():
                self._emit_constant(expr.value, location=expr.location)
            case Identifier():
                self._emit_load(expr.name, location=expr.location)
            case BinaryOp():
                self._compile_binary(expr)
            case UnaryOp():
                self._compile_unary(expr)
            case FunctionCall():
                self._compile_call(expr)
            case StringInterpolation():
                self._compile_string_interpolation(expr)
            case ArrayLiteral():
                self._compile_array_literal(expr)
            case ListComprehension():
                self._compile_list_comprehension(expr)
            case DictLiteral():
                self._compile_dict_literal(expr)
            case IndexAccess() | SliceAccess():
                self._compile_index_or_slice(expr)
            case MethodCall():
                self._compile_method_call(expr)
            case FieldAccess():
                self._compile_field_access(expr)
            case FunctionExpression():
                self._compile_function_expression(expr)

    # -- Expression compilers -------------------------------------------------

    def _compile_binary(self, node: BinaryOp) -> None:
        """Compile a binary operation: left, right, then operator."""
        self._compile_expression(node.left)
        self._compile_expression(node.right)
        self._emit(_BINARY_OPS[node.operator], location=node.location)

    def _compile_unary(self, node: UnaryOp) -> None:
        """Compile a unary operation: operand, then operator."""
        self._compile_expression(node.operand)
        self._emit(_UNARY_OPS[node.operator], location=node.location)

    def _compile_call(self, node: FunctionCall) -> None:
        """Compile a function call: push arguments, then CALL."""
        for arg in node.arguments:
            self._compile_expression(arg)
        self._emit(OpCode.CALL, node.name, location=node.location)

    def _compile_method_call(self, node: MethodCall) -> None:
        """Compile a method call: push target, push args, pad, CALL_METHOD."""
        self._compile_expression(node.target)
        for arg in node.arguments:
            self._compile_expression(arg)
        # Pad with sentinels so the VM always pops the max arity
        expected = METHOD_ARITIES[node.method]
        max_arity = max(expected) if isinstance(expected, tuple) else expected
        for _ in range(max_arity - len(node.arguments)):
            self._emit_constant(METHOD_NONE, location=node.location)
        self._emit(OpCode.CALL_METHOD, node.method, location=node.location)

    def _compile_string_interpolation(self, node: StringInterpolation) -> None:
        """Compile a string interpolation: push each part, then BUILD_STRING."""
        for part in node.parts:
            self._compile_expression(part)
        self._emit(OpCode.BUILD_STRING, len(node.parts), location=node.location)

    def _compile_array_literal(self, node: ArrayLiteral) -> None:
        """Compile an array literal: push elements, then BUILD_LIST."""
        for element in node.elements:
            self._compile_expression(element)
        self._emit(OpCode.BUILD_LIST, len(node.elements), location=node.location)

    def _compile_list_comprehension(self, node: ListComprehension) -> None:
        """Compile ``[mapping for var in range(...)]`` with optional filter.

        Emit an empty list, iterate using the same init/condition logic as
        ``for`` loops, append each mapped value via LIST_APPEND, and leave
        the result list on the stack.
        """
        loc = node.location
        comp_name = f"$comp_{self._comp_var_counter}"
        self._comp_var_counter += 1

        # Reuse the for-loop counter for hidden limit/step variables
        counter = self._loop_var_counter
        limit_name = f"$for_limit_{counter}"
        self._loop_var_counter += 1

        # Build empty result list and store in hidden variable
        self._emit(OpCode.BUILD_LIST, 0, location=loc)
        self._emit_store(comp_name, location=loc)

        # Extract range() arguments
        match node.iterable:
            case FunctionCall(name="range"):
                args = node.iterable.arguments
            case _:  # pragma: no cover
                args = []
                self._compile_expression(node.iterable)

        nargs = len(args)

        # Init: set limit, step (if 3-arg), and loop variable
        self._compile_for_init(args, nargs, limit_name, node.variable, counter, loc)

        # Condition
        loop_start = self._current_index()
        exit_jump = self._compile_for_condition(nargs, node.variable, limit_name, counter, loc)

        # Optional filter
        skip_jump: int | None = None
        if node.condition is not None:
            self._compile_expression(node.condition)
            skip_jump = self._emit(OpCode.JUMP_IF_FALSE, 0, location=loc)

        # Compile mapping expression and append to result list
        self._compile_expression(node.mapping)
        self._emit(OpCode.LIST_APPEND, comp_name, location=loc)

        # Patch skip jump (filter false → skip append)
        if skip_jump is not None:
            self._patch_jump(skip_jump)

        # Increment loop variable
        self._emit_load(node.variable, location=loc)
        if nargs <= 2:  # noqa: PLR2004
            self._emit_constant(1, location=loc)
        else:
            self._emit_load(f"$for_step_{counter}", location=loc)
        self._emit(OpCode.ADD, location=loc)
        self._emit_store(node.variable, location=loc)

        self._emit(OpCode.JUMP, loop_start, location=loc)

        # Exit
        self._patch_jump(exit_jump)

        # Leave the result list on the stack
        self._emit_load(comp_name, location=loc)

    def _compile_dict_literal(self, node: DictLiteral) -> None:
        """Compile a dict literal: push key/value pairs, then BUILD_DICT."""
        for key, value in node.entries:
            self._compile_expression(key)
            self._compile_expression(value)
        self._emit(OpCode.BUILD_DICT, len(node.entries), location=node.location)

    def _compile_index_or_slice(self, expr: IndexAccess | SliceAccess) -> None:
        """Dispatch to index or slice compilation."""
        match expr:
            case IndexAccess():
                self._compile_index_access(expr)
            case SliceAccess():
                self._compile_slice_access(expr)

    def _compile_index_access(self, node: IndexAccess) -> None:
        """Compile an index access: push target and index, then INDEX_GET."""
        self._compile_expression(node.target)
        self._compile_expression(node.index)
        self._emit(OpCode.INDEX_GET, location=node.location)

    def _compile_slice_access(self, node: SliceAccess) -> None:
        """Compile a slice access: push target, start, stop, step, then SLICE_GET."""
        self._compile_expression(node.target)
        for component in (node.start, node.stop, node.step):
            if component is not None:
                self._compile_expression(component)
            else:
                self._emit_constant("$SLICE_NONE", location=node.location)
        self._emit(OpCode.SLICE_GET, location=node.location)

    def _compile_function_expression(self, node: FunctionExpression) -> None:
        """Compile an anonymous function expression into a closure on the stack."""
        fn_code = CodeObject(name=node.name)
        fn_code.parameters = [p.name for p in node.parameters]
        fn_code.param_types = [p.type_annotation for p in node.parameters]
        fn_code.return_type = node.return_type
        fn_code.cell_variables = sorted(self._cell_vars.get(node.name, set()))
        fn_code.free_variables = sorted(self._free_vars.get(node.name, set()))
        previous = self._current
        previous_loop_counter = self._loop_var_counter
        previous_match_counter = self._match_var_counter
        previous_comp_counter = self._comp_var_counter
        previous_loop_contexts = self._loop_contexts
        previous_try_depth = self._try_depth
        self._current = fn_code
        self._loop_var_counter = 0
        self._match_var_counter = 0
        self._comp_var_counter = 0
        self._loop_contexts = []
        self._try_depth = 0

        for stmt in node.body:
            self._compile_statement(stmt)

        if not fn_code.instructions or fn_code.instructions[-1].opcode is not OpCode.RETURN:
            self._emit_constant(0)
            if node.return_type is not None:
                self._emit(OpCode.CHECK_TYPE, node.return_type)
            self._emit(OpCode.RETURN)

        self._functions[node.name] = fn_code
        self._current = previous
        self._loop_var_counter = previous_loop_counter
        self._match_var_counter = previous_match_counter
        self._comp_var_counter = previous_comp_counter
        self._loop_contexts = previous_loop_contexts
        self._try_depth = previous_try_depth

        # Always emit MAKE_CLOSURE — leaves a Closure value on the stack
        self._emit(OpCode.MAKE_CLOSURE, node.name, location=node.location)

    def _compile_index_assignment(self, node: IndexAssignment) -> None:
        """Compile an index assignment: push target, index, value, then INDEX_SET."""
        self._compile_expression(node.target)
        self._compile_expression(node.index)
        self._compile_expression(node.value)
        self._emit(OpCode.INDEX_SET, location=node.location)

    def _compile_struct_def(self, node: StructDef) -> None:
        """Compile a struct definition — store field metadata, emit no bytecode."""
        self._structs[node.name] = [f.name for f in node.fields]
        annotated = {f.name: f.type_annotation for f in node.fields if f.type_annotation}
        if annotated:
            self._struct_field_types[node.name] = annotated

    def _compile_field_access(self, node: FieldAccess) -> None:
        """Compile a field read: push target, then GET_FIELD."""
        self._compile_expression(node.target)
        self._emit(OpCode.GET_FIELD, node.field, location=node.location)

    def _compile_field_assignment(self, node: FieldAssignment) -> None:
        """Compile a field write: push target, push value, then SET_FIELD."""
        self._compile_expression(node.target)
        self._compile_expression(node.value)
        self._emit(OpCode.SET_FIELD, node.field, location=node.location)
