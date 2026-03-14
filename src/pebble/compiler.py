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
from pebble.bytecode import CodeObject, CompiledProgram, Instruction, OpCode

if TYPE_CHECKING:
    from pebble.tokens import SourceLocation

# -- Operator mapping ---------------------------------------------------------

_BINARY_OPS: dict[str, OpCode] = {
    "+": OpCode.ADD,
    "-": OpCode.SUBTRACT,
    "*": OpCode.MULTIPLY,
    "/": OpCode.DIVIDE,
    "%": OpCode.MODULO,
    "==": OpCode.EQUAL,
    "!=": OpCode.NOT_EQUAL,
    "<": OpCode.LESS_THAN,
    "<=": OpCode.LESS_EQUAL,
    ">": OpCode.GREATER_THAN,
    ">=": OpCode.GREATER_EQUAL,
    "and": OpCode.AND,
    "or": OpCode.OR,
}

_UNARY_OPS: dict[str, OpCode] = {
    "-": OpCode.NEGATE,
    "not": OpCode.NOT,
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
        self._loop_contexts: list[_LoopContext] = []
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
        return CompiledProgram(main=self._main, functions=self._functions)

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
        value: int | str | bool,  # noqa: FBT001
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

    def _compile_statement(self, stmt: Statement) -> None:
        """Dispatch to the appropriate compilation method."""
        match stmt:
            case Assignment():
                self._compile_assignment(stmt)
            case Reassignment():
                self._compile_reassignment(stmt)
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
            case _:
                # Expression statement (e.g. bare function call)
                self._compile_expression(stmt)  # type: ignore[arg-type]
                self._emit(OpCode.POP)

    # -- Statement compilers --------------------------------------------------

    def _compile_assignment(self, node: Assignment) -> None:
        """Compile ``let name = value``."""
        self._compile_expression(node.value)
        self._emit_store(node.name, location=node.location)

    def _compile_reassignment(self, node: Reassignment) -> None:
        """Compile ``name = value``."""
        self._compile_expression(node.value)
        self._emit_store(node.name, location=node.location)

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

        self._loop_contexts.append(_LoopContext())
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
        """Compile ``for var in range(n) { body }`` as a counted while loop."""
        limit_name = f"$for_limit_{self._loop_var_counter}"
        self._loop_var_counter += 1
        loc = node.location

        # Evaluate range argument and store as hidden limit variable
        match node.iterable:
            case FunctionCall(name="range"):
                self._compile_expression(node.iterable.arguments[0])
            case _:  # pragma: no cover
                self._compile_expression(node.iterable)
        self._emit_store(limit_name, location=loc)

        # Initialize loop variable to 0
        self._emit_constant(0, location=loc)
        self._emit_store(node.variable, location=loc)

        loop_start = self._current_index()
        self._emit_load(node.variable, location=loc)
        self._emit_load(limit_name, location=loc)
        self._emit(OpCode.LESS_THAN, location=loc)
        exit_jump = self._emit(OpCode.JUMP_IF_FALSE, 0, location=loc)

        # Body
        self._loop_contexts.append(_LoopContext())
        for stmt in node.body:
            self._compile_statement(stmt)
        ctx = self._loop_contexts.pop()

        # continue → increment section (current position)
        for patch in ctx.continue_patches:
            self._patch_jump(patch)

        # Increment loop variable
        self._emit_load(node.variable, location=loc)
        self._emit_constant(1, location=loc)
        self._emit(OpCode.ADD, location=loc)
        self._emit_store(node.variable, location=loc)

        self._emit(OpCode.JUMP, loop_start, location=loc)

        # break + normal exit → here (after loop)
        self._patch_jump(exit_jump)
        for patch in ctx.break_patches:
            self._patch_jump(patch)

    def _compile_function_def(self, node: FunctionDef) -> None:
        """Compile a function definition into a separate CodeObject."""
        fn_code = CodeObject(name=node.name)
        fn_code.parameters = list(node.parameters)
        fn_code.cell_variables = sorted(self._cell_vars.get(node.name, set()))
        fn_code.free_variables = sorted(self._free_vars.get(node.name, set()))
        previous = self._current
        previous_counter = self._loop_var_counter
        previous_loop_contexts = self._loop_contexts
        self._current = fn_code
        self._loop_var_counter = 0
        self._loop_contexts = []

        for stmt in node.body:
            self._compile_statement(stmt)

        # Implicit return 0 if no explicit return at the end
        if not fn_code.instructions or fn_code.instructions[-1].opcode is not OpCode.RETURN:
            self._emit_constant(0)
            self._emit(OpCode.RETURN)

        self._functions[node.name] = fn_code
        self._current = previous
        self._loop_var_counter = previous_counter
        self._loop_contexts = previous_loop_contexts

        # If the function captures variables, it's a closure — emit MAKE_CLOSURE
        if fn_code.free_variables:
            self._emit(OpCode.MAKE_CLOSURE, node.name, location=node.location)
            self._emit(OpCode.STORE_NAME, node.name, location=node.location)

    def _compile_return(self, node: ReturnStatement) -> None:
        """Compile ``return`` or ``return expr``."""
        if node.value is not None:
            self._compile_expression(node.value)
        else:
            self._emit_constant(0, location=node.location)
        self._emit(OpCode.RETURN, location=node.location)

    def _compile_break(self, node: BreakStatement) -> None:
        """Compile ``break`` — emit a forward JUMP to be patched after the loop."""
        patch = self._emit(OpCode.JUMP, 0, location=node.location)
        self._loop_contexts[-1].break_patches.append(patch)

    def _compile_continue(self, node: ContinueStatement) -> None:
        """Compile ``continue`` — emit a JUMP to be patched to the continue target."""
        patch = self._emit(OpCode.JUMP, 0, location=node.location)
        self._loop_contexts[-1].continue_patches.append(patch)

    # -- Expression dispatch --------------------------------------------------

    def _compile_expression(self, expr: Expression) -> None:
        """Dispatch to the appropriate expression compiler."""
        match expr:
            case IntegerLiteral():
                self._emit_constant(expr.value, location=expr.location)
            case StringLiteral():
                self._emit_constant(expr.value, location=expr.location)
            case BooleanLiteral():
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
            case DictLiteral():
                self._compile_dict_literal(expr)
            case IndexAccess():
                self._compile_index_access(expr)
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

    def _compile_dict_literal(self, node: DictLiteral) -> None:
        """Compile a dict literal: push key/value pairs, then BUILD_DICT."""
        for key, value in node.entries:
            self._compile_expression(key)
            self._compile_expression(value)
        self._emit(OpCode.BUILD_DICT, len(node.entries), location=node.location)

    def _compile_index_access(self, node: IndexAccess) -> None:
        """Compile an index access: push target and index, then INDEX_GET."""
        self._compile_expression(node.target)
        self._compile_expression(node.index)
        self._emit(OpCode.INDEX_GET, location=node.location)

    def _compile_function_expression(self, node: FunctionExpression) -> None:
        """Compile an anonymous function expression into a closure on the stack."""
        fn_code = CodeObject(name=node.name)
        fn_code.parameters = list(node.parameters)
        fn_code.cell_variables = sorted(self._cell_vars.get(node.name, set()))
        fn_code.free_variables = sorted(self._free_vars.get(node.name, set()))
        previous = self._current
        previous_counter = self._loop_var_counter
        previous_loop_contexts = self._loop_contexts
        self._current = fn_code
        self._loop_var_counter = 0
        self._loop_contexts = []

        for stmt in node.body:
            self._compile_statement(stmt)

        if not fn_code.instructions or fn_code.instructions[-1].opcode is not OpCode.RETURN:
            self._emit_constant(0)
            self._emit(OpCode.RETURN)

        self._functions[node.name] = fn_code
        self._current = previous
        self._loop_var_counter = previous_counter
        self._loop_contexts = previous_loop_contexts

        # Always emit MAKE_CLOSURE — leaves a Closure value on the stack
        self._emit(OpCode.MAKE_CLOSURE, node.name, location=node.location)

    def _compile_index_assignment(self, node: IndexAssignment) -> None:
        """Compile an index assignment: push target, index, value, then INDEX_SET."""
        self._compile_expression(node.target)
        self._compile_expression(node.index)
        self._compile_expression(node.value)
        self._emit(OpCode.INDEX_SET, location=node.location)
