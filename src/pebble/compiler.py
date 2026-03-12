"""Bytecode compiler for the Pebble language.

Walk a validated AST and emit stack-based bytecode instructions. The compiler
produces a :class:`CompiledProgram` containing a *main* :class:`CodeObject`
(the top-level program) and a dictionary of per-function ``CodeObject``s.

The semantic analyzer is assumed to have already validated the program, so the
compiler does not duplicate error checking.
"""

from __future__ import annotations

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
from pebble.bytecode import CodeObject, CompiledProgram, Instruction, OpCode

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


class Compiler:
    """Compile a validated AST into stack-based bytecode.

    Usage::

        program = SemanticAnalyzer().analyze(Parser(tokens).parse())
        compiled = Compiler().compile(program)

    """

    def __init__(self) -> None:
        """Create a compiler with an empty main CodeObject."""
        self._main = CodeObject(name="<main>")
        self._functions: dict[str, CodeObject] = {}
        self._current = self._main
        self._for_counter = 0

    # -- Public API -----------------------------------------------------------

    def compile(self, program: Program) -> CompiledProgram:
        """Compile *program* and return a :class:`CompiledProgram`."""
        for stmt in program.statements:
            self._compile_statement(stmt)
        self._emit(OpCode.HALT)
        return CompiledProgram(main=self._main, functions=self._functions)

    # -- Emit helpers ---------------------------------------------------------

    def _emit(self, opcode: OpCode, operand: int | str | None = None) -> int:
        """Append an instruction and return its index."""
        self._current.instructions.append(Instruction(opcode, operand))
        return len(self._current.instructions) - 1

    def _emit_constant(self, value: int | str | bool) -> None:  # noqa: FBT001
        """Add *value* to the constant pool and emit LOAD_CONST."""
        idx = self._current.add_constant(value)
        self._emit(OpCode.LOAD_CONST, idx)

    def _current_index(self) -> int:
        """Return the index where the *next* instruction will be emitted."""
        return len(self._current.instructions)

    def _patch_jump(self, instruction_index: int) -> None:
        """Backpatch the jump at *instruction_index* to the current position."""
        old = self._current.instructions[instruction_index]
        self._current.instructions[instruction_index] = Instruction(
            old.opcode, self._current_index()
        )

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
            case _:
                # Expression statement (e.g. bare function call)
                self._compile_expression(stmt)  # type: ignore[arg-type]
                self._emit(OpCode.POP)

    # -- Statement compilers --------------------------------------------------

    def _compile_assignment(self, node: Assignment) -> None:
        """Compile ``let name = value``."""
        self._compile_expression(node.value)
        self._emit(OpCode.STORE_NAME, node.name)

    def _compile_reassignment(self, node: Reassignment) -> None:
        """Compile ``name = value``."""
        self._compile_expression(node.value)
        self._emit(OpCode.STORE_NAME, node.name)

    def _compile_print(self, node: PrintStatement) -> None:
        """Compile ``print(expr)``."""
        self._compile_expression(node.expression)
        self._emit(OpCode.PRINT)

    def _compile_if(self, node: IfStatement) -> None:
        """Compile ``if condition { body } else { else_body }``."""
        self._compile_expression(node.condition)
        jump_if_false = self._emit(OpCode.JUMP_IF_FALSE, 0)

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
        jump_if_false = self._emit(OpCode.JUMP_IF_FALSE, 0)

        for stmt in node.body:
            self._compile_statement(stmt)

        self._emit(OpCode.JUMP, loop_start)
        self._patch_jump(jump_if_false)

    def _compile_for(self, node: ForLoop) -> None:
        """Compile ``for var in range(n) { body }`` as a counted while loop."""
        limit_name = f"$for_limit_{self._for_counter}"
        self._for_counter += 1

        # Evaluate range argument and store as hidden limit variable
        match node.iterable:
            case FunctionCall(name="range"):
                self._compile_expression(node.iterable.arguments[0])
            case _:  # pragma: no cover
                self._compile_expression(node.iterable)
        self._emit(OpCode.STORE_NAME, limit_name)

        # Initialize loop variable to 0
        self._emit_constant(0)
        self._emit(OpCode.STORE_NAME, node.variable)

        loop_start = self._current_index()
        self._emit(OpCode.LOAD_NAME, node.variable)
        self._emit(OpCode.LOAD_NAME, limit_name)
        self._emit(OpCode.LESS_THAN)
        jump_if_false = self._emit(OpCode.JUMP_IF_FALSE, 0)

        # Body
        for stmt in node.body:
            self._compile_statement(stmt)

        self._emit(OpCode.LOAD_NAME, node.variable)
        self._emit_constant(1)
        self._emit(OpCode.ADD)
        self._emit(OpCode.STORE_NAME, node.variable)

        self._emit(OpCode.JUMP, loop_start)
        self._patch_jump(jump_if_false)

    def _compile_function_def(self, node: FunctionDef) -> None:
        """Compile a function definition into a separate CodeObject."""
        fn_code = CodeObject(name=node.name)
        fn_code.parameters = list(node.parameters)
        previous = self._current
        previous_counter = self._for_counter
        self._current = fn_code
        self._for_counter = 0

        for stmt in node.body:
            self._compile_statement(stmt)

        # Implicit return 0 if no explicit return at the end
        if not fn_code.instructions or fn_code.instructions[-1].opcode is not OpCode.RETURN:
            self._emit_constant(0)
            self._emit(OpCode.RETURN)

        self._functions[node.name] = fn_code
        self._current = previous
        self._for_counter = previous_counter

    def _compile_return(self, node: ReturnStatement) -> None:
        """Compile ``return`` or ``return expr``."""
        if node.value is not None:
            self._compile_expression(node.value)
        else:
            self._emit_constant(0)
        self._emit(OpCode.RETURN)

    # -- Expression dispatch --------------------------------------------------

    def _compile_expression(self, expr: Expression) -> None:
        """Dispatch to the appropriate expression compiler."""
        match expr:
            case IntegerLiteral():
                self._emit_constant(expr.value)
            case StringLiteral():
                self._emit_constant(expr.value)
            case BooleanLiteral():
                self._emit_constant(expr.value)
            case Identifier():
                self._emit(OpCode.LOAD_NAME, expr.name)
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
            case IndexAccess():
                self._compile_index_access(expr)

    # -- Expression compilers -------------------------------------------------

    def _compile_binary(self, node: BinaryOp) -> None:
        """Compile a binary operation: left, right, then operator."""
        self._compile_expression(node.left)
        self._compile_expression(node.right)
        self._emit(_BINARY_OPS[node.operator])

    def _compile_unary(self, node: UnaryOp) -> None:
        """Compile a unary operation: operand, then operator."""
        self._compile_expression(node.operand)
        self._emit(_UNARY_OPS[node.operator])

    def _compile_call(self, node: FunctionCall) -> None:
        """Compile a function call: push arguments, then CALL."""
        for arg in node.arguments:
            self._compile_expression(arg)
        self._emit(OpCode.CALL, node.name)

    def _compile_string_interpolation(self, node: StringInterpolation) -> None:
        """Compile a string interpolation: push each part, then BUILD_STRING."""
        for part in node.parts:
            self._compile_expression(part)
        self._emit(OpCode.BUILD_STRING, len(node.parts))

    def _compile_array_literal(self, node: ArrayLiteral) -> None:
        """Compile an array literal: push elements, then BUILD_LIST."""
        for element in node.elements:
            self._compile_expression(element)
        self._emit(OpCode.BUILD_LIST, len(node.elements))

    def _compile_index_access(self, node: IndexAccess) -> None:
        """Compile an index access: push target and index, then INDEX_GET."""
        self._compile_expression(node.target)
        self._compile_expression(node.index)
        self._emit(OpCode.INDEX_GET)

    def _compile_index_assignment(self, node: IndexAssignment) -> None:
        """Compile an index assignment: push target, index, value, then INDEX_SET."""
        self._compile_expression(node.target)
        self._compile_expression(node.index)
        self._compile_expression(node.value)
        self._emit(OpCode.INDEX_SET)
