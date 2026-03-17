"""Stack-based virtual machine for the Pebble language.

Execute compiled bytecode by maintaining a value stack, a call stack of
:class:`Frame` objects, and a dictionary of function :class:`CodeObject`
references.  The VM processes one instruction at a time until it reaches
a ``HALT`` opcode.
"""

import operator
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ClassVar, Never, TextIO

from pebble.ast_nodes import TypeAnnotation
from pebble.builtins import (
    BUILTIN_ARITIES,
    BUILTINS,
    LIST_METHODS,
    METHOD_NONE,
    SLICE_NONE,
    STRING_METHODS,
    Cell,
    Closure,
    EnumVariant,
    GeneratorObject,
    SequenceIterator,
    StructInstance,
    Value,
    format_value,
)
from pebble.bytecode import CodeObject, CompiledProgram, Instruction, OpCode
from pebble.errors import PebbleRuntimeError
from pebble.stdlib import StdlibHandler

_DIVISION_BY_ZERO = "Division by zero"

_TYPE_MAP: dict[str, type] = {
    "Int": int,
    "Float": float,
    "String": str,
    "Bool": bool,
    "Null": type(None),
    "List": list,
    "Dict": dict,
    "Fn": Closure,
}

_TYPE_DISPLAY: dict[str, str] = {
    "int": "Int",
    "float": "Float",
    "str": "String",
    "bool": "Bool",
    "NoneType": "Null",
    "list": "List",
    "dict": "Dict",
}

# Dispatch table for binary arithmetic ops that share a dunder + _apply_numeric pattern.
# Each entry: (dunder_name, symbol, operator_func, check_zero_divisor).
_ARITH_OPS: dict[
    OpCode,
    tuple[str, str, Callable[[int | float, int | float], int | float], bool],
] = {
    OpCode.SUBTRACT: ("__sub__", "-", operator.sub, False),
    OpCode.MULTIPLY: ("__mul__", "*", operator.mul, False),
    OpCode.FLOOR_DIVIDE: ("__floordiv__", "//", operator.floordiv, True),
    OpCode.MODULO: ("__mod__", "%", operator.mod, True),
}

# Dispatch table for equality operators.
# Each entry: (dunder_name, fallback_func).
_EQUALITY_OPS: dict[
    OpCode,
    tuple[str, Callable[[Value, Value], bool]],
] = {
    OpCode.EQUAL: ("__eq__", operator.eq),
    OpCode.NOT_EQUAL: ("__ne__", operator.ne),
}

# Dispatch table for ordering comparison operators.
# Each entry: (dunder_name, symbol, operator_func).
_COMPARISON_OPS: dict[
    OpCode,
    tuple[str, str, Callable[[int | float, int | float], bool]],
] = {
    OpCode.LESS_THAN: ("__lt__", "<", operator.lt),
    OpCode.LESS_EQUAL: ("__le__", "<=", operator.le),
    OpCode.GREATER_THAN: ("__gt__", ">", operator.gt),
    OpCode.GREATER_EQUAL: ("__ge__", ">=", operator.ge),
}


class _PebbleThrowError(Exception):
    """Internal exception for Pebble throw/catch unwinding."""

    def __init__(self, value: Value) -> None:
        """Create a throw with the given Pebble value."""
        self.value = value


@dataclass
class _ExceptionHandler:
    """Bookkeeping for one active try block.

    Attributes:
        handler_ip: IP to jump to (catch block).
        stack_depth: Stack size to restore on unwind.
        frame_depth: Call-stack size to restore on unwind.

    """

    handler_ip: int
    stack_depth: int
    frame_depth: int


@dataclass
class Frame:
    """A single activation record on the call stack.

    Attributes:
        code: The :class:`CodeObject` this frame executes.
        ip: Instruction pointer — index of the *next* instruction to fetch.
        variables: Local variable bindings for this scope.

    """

    code: CodeObject
    ip: int = 0
    variables: dict[str, Value] = field(default_factory=lambda: {})
    cells: dict[str, Cell] = field(default_factory=lambda: {})
    generator: GeneratorObject | None = None


class VirtualMachine:
    """Execute a :class:`CompiledProgram` on a stack-based VM.

    Args:
        output: Writable text stream for ``print`` output (default ``sys.stdout``).
        input_stream: Readable text stream for ``input()`` (default ``sys.stdin``).

    """

    def __init__(
        self,
        output: TextIO | None = None,
        input_stream: TextIO | None = None,
    ) -> None:
        """Create a VM with an empty stack and call stack."""
        self._stack: list[Value] = []
        self._frames: list[Frame] = []
        self._functions: dict[str, CodeObject] = {}
        self._structs: dict[str, list[str]] = {}
        self._struct_field_types: dict[str, dict[str, str]] = {}
        self._class_methods: dict[str, list[str]] = {}
        self._class_parents: dict[str, str] = {}
        self._enums: dict[str, list[str]] = {}
        self._output: TextIO = output or sys.stdout
        self._input_stream: TextIO = input_stream or sys.stdin
        self._current_instruction: Instruction | None = None
        self._exception_handlers: list[_ExceptionHandler] = []
        self._min_depth: int = 0
        self._stdlib_handlers: dict[str, tuple[int | tuple[int, ...], StdlibHandler]] = {}
        self._globals: dict[str, Value] = {}

    # -- Public API -----------------------------------------------------------

    def run(
        self,
        program: CompiledProgram,
        *,
        stdlib_handlers: dict[str, tuple[int | tuple[int, ...], StdlibHandler]] | None = None,
        stdlib_constants: dict[str, Value] | None = None,
    ) -> None:
        """Execute *program* from the first instruction of ``main``."""
        self._functions = dict(program.functions)
        self._structs = dict(program.structs)
        self._struct_field_types = dict(program.struct_field_types)
        self._class_methods = dict(program.class_methods)
        self._class_parents = dict(program.class_parents)
        self._enums = dict(program.enums)
        self._stdlib_handlers = dict(stdlib_handlers) if stdlib_handlers else {}
        self._globals = dict(stdlib_constants) if stdlib_constants else {}
        self._frames = [Frame(code=program.main, variables=dict(self._globals))]
        self._exception_handlers = []
        try:
            self._execute()
        except _PebbleThrowError as exc:
            raise PebbleRuntimeError(str(exc.value), line=0, column=0) from None

    def run_repl(
        self,
        program: CompiledProgram,
        variables: dict[str, Value],
        *,
        stdlib_handlers: dict[str, tuple[int | tuple[int, ...], StdlibHandler]] | None = None,
        stdlib_constants: dict[str, Value] | None = None,
    ) -> dict[str, Value]:
        """Execute *program* with initial *variables*, return updated state.

        Used by the REPL to carry variable bindings across inputs.
        """
        self._functions = dict(program.functions)
        self._structs = dict(program.structs)
        self._struct_field_types = dict(program.struct_field_types)
        self._class_methods = dict(program.class_methods)
        self._class_parents = dict(program.class_parents)
        self._enums = dict(program.enums)
        self._stdlib_handlers = dict(stdlib_handlers) if stdlib_handlers else {}
        self._globals = dict(stdlib_constants) if stdlib_constants else {}
        initial_vars = {**self._globals, **variables}
        self._frames = [Frame(code=program.main, variables=initial_vars)]
        self._exception_handlers = []
        try:
            self._execute()
        except _PebbleThrowError as exc:
            raise PebbleRuntimeError(str(exc.value), line=0, column=0) from None
        return dict(self._frames[-1].variables)

    # -- Error helper ---------------------------------------------------------

    def _runtime_error(self, msg: str) -> Never:
        """Raise a PebbleRuntimeError with the current instruction's location."""
        line, column = 0, 0
        if self._current_instruction and self._current_instruction.location:
            loc = self._current_instruction.location
            line, column = loc.line, loc.column
        raise PebbleRuntimeError(msg, line=line, column=column)

    # -- Execution loop -------------------------------------------------------

    def _execute(self, *, min_depth: int = 0) -> None:
        """Fetch-decode-execute loop.

        Run until the call-stack depth drops to *min_depth*, allowing nested
        execution for callbacks invoked by VM-level builtins.
        """
        previous_min = self._min_depth
        self._min_depth = min_depth
        try:
            self._execute_loop(min_depth)
        finally:
            self._min_depth = previous_min

    def _execute_loop(self, min_depth: int) -> None:
        """Inner execution loop with exception handling."""
        while len(self._frames) > min_depth:
            frame = self._frames[-1]
            instruction = frame.code.instructions[frame.ip]
            frame.ip += 1
            self._current_instruction = instruction

            if instruction.opcode is OpCode.HALT:
                return

            try:
                self._dispatch(instruction, frame)
            except _PebbleThrowError as exc:
                self._unwind_exception(exc.value)
            except PebbleRuntimeError as exc:
                if self._exception_handlers:
                    self._unwind_exception(exc.message)
                else:
                    raise

    def _dispatch(self, instruction: Instruction, frame: Frame) -> None:
        """Dispatch a single instruction."""
        match instruction.opcode:
            case (
                OpCode.LOAD_CONST
                | OpCode.STORE_NAME
                | OpCode.LOAD_NAME
                | OpCode.LOAD_CELL
                | OpCode.STORE_CELL
            ):
                self._exec_variables(instruction, frame)
            case (
                OpCode.ADD
                | OpCode.SUBTRACT
                | OpCode.MULTIPLY
                | OpCode.POWER
                | OpCode.DIVIDE
                | OpCode.FLOOR_DIVIDE
                | OpCode.MODULO
                | OpCode.NEGATE
            ):
                self._exec_arithmetic(instruction)
            case (
                OpCode.NOT
                | OpCode.EQUAL
                | OpCode.NOT_EQUAL
                | OpCode.LESS_THAN
                | OpCode.LESS_EQUAL
                | OpCode.GREATER_THAN
                | OpCode.GREATER_EQUAL
                | OpCode.AND
                | OpCode.OR
            ):
                self._exec_logic(instruction)
            case OpCode.JUMP | OpCode.JUMP_IF_FALSE | OpCode.POP:
                self._exec_control(instruction, frame)
            case (
                OpCode.BUILD_STRING
                | OpCode.BUILD_LIST
                | OpCode.LIST_APPEND
                | OpCode.BUILD_DICT
                | OpCode.INDEX_GET
                | OpCode.INDEX_SET
                | OpCode.SLICE_GET
                | OpCode.UNPACK_SEQUENCE
                | OpCode.GET_FIELD
                | OpCode.SET_FIELD
            ):
                self._exec_collection(instruction)
            case (
                OpCode.BIT_AND
                | OpCode.BIT_OR
                | OpCode.BIT_XOR
                | OpCode.BIT_NOT
                | OpCode.LEFT_SHIFT
                | OpCode.RIGHT_SHIFT
            ):
                self._exec_bitwise(instruction)
            case OpCode.CALL | OpCode.CALL_METHOD | OpCode.CALL_INSTANCE_METHOD:
                self._exec_call_dispatch(instruction)
            case (
                OpCode.PRINT
                | OpCode.RETURN
                | OpCode.YIELD
                | OpCode.CHECK_TYPE
                | OpCode.LOAD_ENUM_VARIANT
            ):
                self._exec_misc(instruction)
            case OpCode.SETUP_TRY | OpCode.POP_TRY | OpCode.THROW:
                self._exec_exception(instruction)
            case OpCode.GET_ITER | OpCode.FOR_ITER | OpCode.MAKE_CLOSURE:
                self._exec_iter_closure(instruction, frame)
            case _:  # pragma: no cover
                pass

    # -- Dispatch groups ------------------------------------------------------

    def _exec_variables(self, instruction: Instruction, frame: Frame) -> None:
        """Handle LOAD_CONST, STORE_NAME, LOAD_NAME, LOAD_CELL, STORE_CELL."""
        match instruction.opcode:
            case OpCode.LOAD_CONST:
                operand = _int_operand(instruction)
                self._stack.append(frame.code.constants[operand])
            case OpCode.STORE_NAME:
                operand = _str_operand(instruction)
                frame.variables[operand] = self._stack.pop()
            case OpCode.LOAD_NAME:
                operand = _str_operand(instruction)
                if operand in frame.variables:
                    self._stack.append(frame.variables[operand])
                elif operand in self._functions:
                    # Wrap a regular function as a Closure so it's first-class
                    fn_code = self._functions[operand]
                    self._stack.append(Closure(code=fn_code, cells=[]))
                else:
                    self._runtime_error(f"Undefined variable '{operand}'")
            case OpCode.STORE_CELL:
                operand = _str_operand(instruction)
                value = self._stack.pop()
                if operand in frame.cells:
                    frame.cells[operand].value = value
                else:
                    frame.cells[operand] = Cell(value)
            case OpCode.LOAD_CELL:
                operand = _str_operand(instruction)
                self._stack.append(frame.cells[operand].value)
            case _:  # pragma: no cover
                pass

    # -- Dunder dispatch helpers ------------------------------------------------

    def _dispatch_dunder_binary(self, dunder: str, left: StructInstance, right: Value) -> bool:
        """Dispatch a binary dunder method on *left*, return True if found."""
        mangled = f"{left.type_name}.{dunder}"
        if mangled not in self._functions:
            return False
        fn_code = self._functions[mangled]
        args: dict[str, Value] = {
            fn_code.parameters[0]: left,
            fn_code.parameters[1]: right,
        }
        new_frame = Frame(code=fn_code, variables=args)
        self._init_cells(new_frame)
        self._frames.append(new_frame)
        return True

    def _dispatch_dunder_unary(self, dunder: str, operand: StructInstance) -> bool:
        """Dispatch a unary dunder method on *operand*, return True if found."""
        mangled = f"{operand.type_name}.{dunder}"
        if mangled not in self._functions:
            return False
        fn_code = self._functions[mangled]
        args: dict[str, Value] = {fn_code.parameters[0]: operand}
        new_frame = Frame(code=fn_code, variables=args)
        self._init_cells(new_frame)
        self._frames.append(new_frame)
        return True

    def _format_value(self, value: Value) -> str:
        """Format *value* using __str__ if available, else fall back to builtins."""
        if isinstance(value, StructInstance):
            mangled = f"{value.type_name}.__str__"
            if mangled in self._functions:
                fn_code = self._functions[mangled]
                params: dict[str, Value] = {fn_code.parameters[0]: value}
                frame = Frame(code=fn_code, variables=params)
                self._init_cells(frame)
                depth = len(self._frames)
                self._frames.append(frame)
                self._execute(min_depth=depth)
                result = self._stack.pop()
                if not isinstance(result, str):
                    self._runtime_error("__str__ must return a string")
                return result
        return format_value(value)

    def _exec_arithmetic(self, instruction: Instruction) -> None:
        """Handle ADD, SUBTRACT, MULTIPLY, POWER, DIVIDE, FLOOR_DIVIDE, MODULO, NEGATE."""
        match instruction.opcode:
            case OpCode.ADD:
                self._exec_add()
            case OpCode.POWER:
                self._exec_power()
            case OpCode.DIVIDE:
                self._exec_divide()
            case OpCode.NEGATE:
                self._exec_negate()
            case OpCode.SUBTRACT | OpCode.MULTIPLY | OpCode.FLOOR_DIVIDE | OpCode.MODULO:
                self._exec_binary_arith(instruction.opcode)
            case _:  # pragma: no cover
                pass

    def _exec_binary_arith(self, opcode: OpCode) -> None:
        """Handle SUBTRACT, MULTIPLY, FLOOR_DIVIDE, MODULO via dispatch table."""
        dunder, symbol, op, check_zero = _ARITH_OPS[opcode]
        right, left = self._stack.pop(), self._stack.pop()
        if isinstance(left, StructInstance) and self._dispatch_dunder_binary(dunder, left, right):
            return
        if check_zero:
            self._check_zero_divisor(right)
        self._apply_numeric(symbol, left, right, op)

    def _exec_divide(self) -> None:
        """Handle DIVIDE — true division that always returns a float, or __div__."""
        right, left = self._stack.pop(), self._stack.pop()
        if isinstance(left, StructInstance) and self._dispatch_dunder_binary(
            "__div__", left, right
        ):
            return
        self._check_zero_divisor(right)
        if _both_numeric(left, right):
            result = float(left) / float(right)  # type: ignore[arg-type]
            self._stack.append(result)
        else:
            self._type_error("/", left, right)

    def _exec_add(self) -> None:
        """Handle ADD — support int+int, float+float, int+float, str+str, or __add__."""
        right, left = self._stack.pop(), self._stack.pop()
        if isinstance(left, StructInstance) and self._dispatch_dunder_binary(
            "__add__", left, right
        ):
            return
        if isinstance(left, str) and isinstance(right, str):
            self._stack.append(left + right)
        elif _both_numeric(left, right):
            self._stack.append(left + right)  # type: ignore[operator]
        else:
            self._type_error("+", left, right)

    def _exec_negate(self) -> None:
        """Handle NEGATE — valid on integers, floats, or instances with __neg__."""
        operand = self._stack.pop()
        if isinstance(operand, StructInstance) and self._dispatch_dunder_unary("__neg__", operand):
            return
        if isinstance(operand, float) or (
            isinstance(operand, int) and not isinstance(operand, bool)
        ):
            self._stack.append(-operand)
        else:
            self._runtime_error(f"Unsupported operand type for negation: {_display_type(operand)}")

    def _exec_power(self) -> None:
        """Handle POWER — int**int→int unless negative exponent, mixed→float, or __pow__."""
        right, left = self._stack.pop(), self._stack.pop()
        if isinstance(left, StructInstance) and self._dispatch_dunder_binary(
            "__pow__", left, right
        ):
            return
        if not _both_numeric(left, right):
            self._type_error("**", left, right)
        # Python's ** on int|float may return int, float, or complex.
        # For Pebble we only produce int or float results.
        self._stack.append(left**right)  # type: ignore[operator,arg-type]

    def _exec_bitwise(self, instruction: Instruction) -> None:
        """Handle BIT_AND, BIT_OR, BIT_XOR, BIT_NOT, LEFT_SHIFT, RIGHT_SHIFT."""
        match instruction.opcode:
            case OpCode.BIT_NOT:
                operand = self._stack.pop()
                if not _is_plain_int(operand):
                    self._runtime_error(
                        f"Unsupported operand type for bitwise NOT: {_display_type(operand)}"
                    )
                self._stack.append(~operand)  # type: ignore[operator]
            case _:
                right, left = self._stack.pop(), self._stack.pop()
                self._apply_bitwise(instruction.opcode, left, right)

    def _apply_bitwise(self, opcode: OpCode, left: Value, right: Value) -> None:
        """Apply a binary bitwise operation to two plain-int operands."""
        if not _is_plain_int(left) or not _is_plain_int(right):
            symbol = {
                OpCode.BIT_AND: "&",
                OpCode.BIT_OR: "|",
                OpCode.BIT_XOR: "^",
                OpCode.LEFT_SHIFT: "<<",
                OpCode.RIGHT_SHIFT: ">>",
            }[opcode]
            self._type_error(symbol, left, right)
        match opcode:
            case OpCode.BIT_AND:
                self._stack.append(left & right)  # type: ignore[operator]
            case OpCode.BIT_OR:
                self._stack.append(left | right)  # type: ignore[operator]
            case OpCode.BIT_XOR:
                self._stack.append(left ^ right)  # type: ignore[operator]
            case OpCode.LEFT_SHIFT:
                if right < 0:  # type: ignore[operator]
                    self._runtime_error("Shift amount cannot be negative")
                self._stack.append(left << right)  # type: ignore[operator]
            case OpCode.RIGHT_SHIFT:
                if right < 0:  # type: ignore[operator]
                    self._runtime_error("Shift amount cannot be negative")
                self._stack.append(left >> right)  # type: ignore[operator]
            case _:  # pragma: no cover
                pass

    def _exec_logic(self, instruction: Instruction) -> None:
        """Handle NOT, comparisons, AND, and OR."""
        match instruction.opcode:
            case OpCode.NOT:
                self._stack.append(not self._stack.pop())
            case OpCode.EQUAL | OpCode.NOT_EQUAL:
                self._exec_equality(instruction.opcode)
            case OpCode.LESS_THAN | OpCode.LESS_EQUAL | OpCode.GREATER_THAN | OpCode.GREATER_EQUAL:
                self._exec_comparison(instruction.opcode)
            case OpCode.AND:
                right, left = self._stack.pop(), self._stack.pop()
                self._stack.append(left and right)
            case OpCode.OR:
                right, left = self._stack.pop(), self._stack.pop()
                self._stack.append(left or right)
            case _:  # pragma: no cover
                pass

    def _exec_equality(self, opcode: OpCode) -> None:
        """Handle EQUAL and NOT_EQUAL with dunder dispatch."""
        dunder, fallback = _EQUALITY_OPS[opcode]
        right, left = self._stack.pop(), self._stack.pop()
        if isinstance(left, StructInstance) and self._dispatch_dunder_binary(dunder, left, right):
            return
        self._stack.append(fallback(left, right))

    def _exec_comparison(self, opcode: OpCode) -> None:
        """Handle ordering comparisons (LT, LE, GT, GE) via dispatch table."""
        dunder, symbol, op = _COMPARISON_OPS[opcode]
        right, left = self._stack.pop(), self._stack.pop()
        if isinstance(left, StructInstance) and self._dispatch_dunder_binary(dunder, left, right):
            return
        self._apply_comparison(symbol, left, right, op)

    def _exec_control(self, instruction: Instruction, frame: Frame) -> None:
        """Handle JUMP, JUMP_IF_FALSE, and POP."""
        match instruction.opcode:
            case OpCode.JUMP:
                frame.ip = _int_operand(instruction)
            case OpCode.JUMP_IF_FALSE:
                target = _int_operand(instruction)
                if not self._stack.pop():
                    frame.ip = target
            case OpCode.POP:
                self._stack.pop()
            case _:  # pragma: no cover
                pass

    def _exec_call_dispatch(self, instruction: Instruction) -> None:
        """Route CALL, CALL_METHOD, and CALL_INSTANCE_METHOD to their handlers."""
        match instruction.opcode:
            case OpCode.CALL:
                self._exec_call(instruction)
            case OpCode.CALL_METHOD:
                self._exec_call_method(instruction)
            case OpCode.CALL_INSTANCE_METHOD:
                self._exec_call_instance_method(instruction)
            case _:  # pragma: no cover
                pass

    def _exec_misc(self, instruction: Instruction) -> None:
        """Handle PRINT, RETURN, YIELD, CHECK_TYPE, and LOAD_ENUM_VARIANT."""
        match instruction.opcode:
            case OpCode.PRINT:
                self._output.write(self._format_value(self._stack.pop()) + "\n")
            case OpCode.RETURN:
                self._exec_return()
            case OpCode.YIELD:
                self._exec_yield()
            case OpCode.CHECK_TYPE:
                self._exec_check_type(instruction)
            case OpCode.LOAD_ENUM_VARIANT:
                self._exec_load_enum_variant(instruction)
            case _:  # pragma: no cover
                pass

    def _exec_exception(self, instruction: Instruction) -> None:
        """Handle SETUP_TRY, POP_TRY, and THROW."""
        match instruction.opcode:
            case OpCode.SETUP_TRY:
                target = _int_operand(instruction)
                self._exception_handlers.append(
                    _ExceptionHandler(
                        handler_ip=target,
                        stack_depth=len(self._stack),
                        frame_depth=len(self._frames),
                    )
                )
            case OpCode.POP_TRY:
                self._exception_handlers.pop()
            case OpCode.THROW:
                raise _PebbleThrowError(self._stack.pop())
            case _:  # pragma: no cover
                pass

    def _exec_iter_closure(self, instruction: Instruction, frame: Frame) -> None:
        """Handle GET_ITER, FOR_ITER, and MAKE_CLOSURE."""
        match instruction.opcode:
            case OpCode.GET_ITER:
                self._exec_get_iter()
            case OpCode.FOR_ITER:
                self._exec_for_iter(instruction, frame)
            case OpCode.MAKE_CLOSURE:
                self._exec_make_closure(instruction)
            case _:  # pragma: no cover
                pass

    def _exec_collection(self, instruction: Instruction) -> None:
        """Handle collection opcodes including BUILD_STRING, BUILD_LIST, and UNPACK_SEQUENCE."""
        match instruction.opcode:
            case OpCode.BUILD_STRING:
                self._exec_build_string(instruction)
            case OpCode.BUILD_LIST:
                self._exec_build_list(instruction)
            case OpCode.LIST_APPEND:
                self._exec_list_append(instruction)
            case OpCode.BUILD_DICT:
                self._exec_build_dict(instruction)
            case OpCode.INDEX_GET:
                self._exec_index_get()
            case OpCode.INDEX_SET:
                self._exec_index_set()
            case OpCode.SLICE_GET:
                self._exec_slice_get()
            case OpCode.UNPACK_SEQUENCE:
                self._exec_unpack_sequence(instruction)
            case OpCode.GET_FIELD:
                self._exec_get_field(instruction)
            case OpCode.SET_FIELD:
                self._exec_set_field(instruction)
            case _:  # pragma: no cover
                pass

    def _exec_build_string(self, instruction: Instruction) -> None:
        """Handle BUILD_STRING — pop *n* values, stringify and concatenate."""
        count = _int_operand(instruction)
        parts = [self._format_value(self._stack.pop()) for _ in range(count)]
        parts.reverse()
        self._stack.append("".join(parts))

    def _exec_build_list(self, instruction: Instruction) -> None:
        """Handle BUILD_LIST — pop *n* values and create a list."""
        count = _int_operand(instruction)
        elements = [self._stack.pop() for _ in range(count)]
        elements.reverse()
        self._stack.append(elements)

    def _exec_list_append(self, instruction: Instruction) -> None:
        """Handle LIST_APPEND — pop value, append to named list variable."""
        name = _str_operand(instruction)
        value = self._stack.pop()
        frame = self._frames[-1]
        target = frame.variables[name]
        if not isinstance(target, list):
            self._runtime_error(f"LIST_APPEND target '{name}' is not a list")
        target.append(value)

    def _exec_unpack_sequence(self, instruction: Instruction) -> None:
        """Handle UNPACK_SEQUENCE — pop list, validate length, push elements."""
        expected = _int_operand(instruction)
        value = self._stack.pop()
        if not isinstance(value, list):
            type_name = type(value).__name__
            self._runtime_error(f"Cannot unpack {type_name}, expected a list")
        if len(value) != expected:
            self._runtime_error(f"Expected {expected} values to unpack, got {len(value)}")
        for item in reversed(value):
            self._stack.append(item)

    def _exec_build_dict(self, instruction: Instruction) -> None:
        """Handle BUILD_DICT — pop 2*n values and create a dict."""
        count = _int_operand(instruction)
        pairs: list[tuple[Value, Value]] = []
        for _ in range(count):
            value = self._stack.pop()
            key = self._stack.pop()
            pairs.append((key, value))
        pairs.reverse()
        result: dict[str, Value] = {}
        for key, value in pairs:
            if not isinstance(key, str):
                type_name = type(key).__name__
                self._runtime_error(f"Dict keys must be strings, got {type_name}")
            result[key] = value
        self._stack.append(result)

    def _validate_list_index(self, target: list[Value], index: Value) -> int:
        """Validate *index* for a list *target* and return the normalised index."""
        if not isinstance(index, int) or isinstance(index, bool):
            type_name = type(index).__name__
            self._runtime_error(f"List index must be an integer, got {type_name}")
        if index < -len(target) or index >= len(target):
            self._runtime_error(f"Index {index} out of bounds for list of length {len(target)}")
        if index < 0:
            return index + len(target)
        return index

    def _exec_index_get(self) -> None:
        """Handle INDEX_GET — pop index and target, push target[index]."""
        index = self._stack.pop()
        target = self._stack.pop()
        if isinstance(target, dict):
            if not isinstance(index, str):
                type_name = type(index).__name__
                self._runtime_error(f"Dict keys must be strings, got {type_name}")
            if index not in target:
                self._runtime_error(f"Key '{index}' not found in dict")
            self._stack.append(target[index])
            return
        if not isinstance(target, list):
            type_name = type(target).__name__
            self._runtime_error(f"Cannot index into {type_name}")
        idx = self._validate_list_index(target, index)
        self._stack.append(target[idx])

    def _exec_index_set(self) -> None:
        """Handle INDEX_SET — pop value, index, target; mutate target[index]."""
        value = self._stack.pop()
        index = self._stack.pop()
        target = self._stack.pop()
        if isinstance(target, dict):
            if not isinstance(index, str):
                type_name = type(index).__name__
                self._runtime_error(f"Dict keys must be strings, got {type_name}")
            target[index] = value
            return
        if not isinstance(target, list):
            type_name = type(target).__name__
            self._runtime_error(f"Cannot index into {type_name}")
        idx = self._validate_list_index(target, index)
        target[idx] = value

    def _exec_slice_get(self) -> None:
        """Handle SLICE_GET — pop step, stop, start, target; push sliced result."""
        raw_step = self._stack.pop()
        raw_stop = self._stack.pop()
        raw_start = self._stack.pop()
        target = self._stack.pop()

        # Replace sentinel strings with None
        start = None if raw_start == SLICE_NONE else raw_start
        stop = None if raw_stop == SLICE_NONE else raw_stop
        step = None if raw_step == SLICE_NONE else raw_step

        # Validate target type
        if not isinstance(target, list | str):
            type_name = type(target).__name__
            self._runtime_error(f"Cannot slice {type_name}")

        # Validate index types
        for name, val in (("start", start), ("stop", stop), ("step", step)):
            if val is not None and (not isinstance(val, int) or isinstance(val, bool)):
                type_name = type(val).__name__
                self._runtime_error(f"Slice {name} must be an integer, got {type_name}")

        # Step 0 is invalid
        if step is not None and step == 0:
            self._runtime_error("Slice step cannot be zero")

        # Delegate to Python's slice machinery
        self._stack.append(target[start:stop:step])  # type: ignore[index]

    def _exec_get_field(self, instruction: Instruction) -> None:
        """Handle GET_FIELD — pop struct instance, push field value."""
        field_name = _str_operand(instruction)
        target = self._stack.pop()
        if not isinstance(target, StructInstance):
            type_name = type(target).__name__
            self._runtime_error(f"Value of type '{type_name}' is not a struct")
        if field_name not in target.fields:
            self._runtime_error(f"Struct '{target.type_name}' has no field '{field_name}'")
        self._stack.append(target.fields[field_name])

    def _exec_set_field(self, instruction: Instruction) -> None:
        """Handle SET_FIELD — pop value and struct instance, set field."""
        field_name = _str_operand(instruction)
        value = self._stack.pop()
        target = self._stack.pop()
        if not isinstance(target, StructInstance):
            type_name = type(target).__name__
            self._runtime_error(f"Value of type '{type_name}' is not a struct")
        if field_name not in target.fields:
            self._runtime_error(f"Struct '{target.type_name}' has no field '{field_name}'")
        # Check field type annotation
        struct_name = target.type_name
        if struct_name in self._struct_field_types:
            field_types = self._struct_field_types[struct_name]
            if field_name in field_types:
                self._check_field_type(value, field_types[field_name], field_name, struct_name)
        target.fields[field_name] = value

    # Map of VM-level builtin names to handler methods.
    _VM_BUILTINS: ClassVar[dict[str, str]] = {
        "str": "_vm_builtin_str",
        "map": "_vm_builtin_map",
        "filter": "_vm_builtin_filter",
        "reduce": "_vm_builtin_reduce",
        "next": "_vm_builtin_next",
    }

    def _exec_call(self, instruction: Instruction) -> None:
        """Handle CALL — check builtins, VM builtins, closures, then user functions."""
        name = _str_operand(instruction)

        if name in BUILTINS:
            self._call_builtin(name)
            return
        if name in self._VM_BUILTINS:
            self._call_vm_builtin(name)
            return
        if name in self._stdlib_handlers:
            self._call_stdlib(name)
            return
        if name in self._structs:
            self._call_struct_constructor(name)
            return

        # Closure dispatch — check if name resolves to a Closure in variables
        frame = self._frames[-1]
        if name in frame.variables:
            value = frame.variables[name]
            if isinstance(value, Closure):
                self._call_closure(value)
                return

        # Regular user function dispatch
        self._call_user_function(name)

    def _call_builtin(self, name: str) -> None:
        """Dispatch a pure built-in function (no VM access needed)."""
        arity, handler = BUILTINS[name]
        builtin_args = [self._stack.pop() for _ in range(arity)]
        builtin_args.reverse()
        try:
            self._stack.append(handler(builtin_args))
        except PebbleRuntimeError as exc:
            self._runtime_error(exc.message)

    def _call_vm_builtin(self, name: str) -> None:
        """Dispatch a VM-level builtin (needs VM access for callbacks)."""
        arity = BUILTIN_ARITIES[name]
        if not isinstance(arity, int):
            self._runtime_error(f"VM builtin '{name}' has non-integer arity")
        vm_args = [self._stack.pop() for _ in range(arity)]
        vm_args.reverse()
        getattr(self, self._VM_BUILTINS[name])(vm_args)

    def _call_stdlib(self, name: str) -> None:
        """Dispatch a stdlib function (importable modules like math, io)."""
        stdlib_arity, stdlib_handler = self._stdlib_handlers[name]
        if stdlib_handler is None:
            self._dispatch_vm_stdlib(name, stdlib_arity)
            return
        pop_count = stdlib_arity if isinstance(stdlib_arity, int) else max(stdlib_arity)
        raw = [self._stack.pop() for _ in range(pop_count)]
        raw.reverse()
        stdlib_args: list[Value] = [a for a in raw if a != METHOD_NONE]
        try:
            self._stack.append(stdlib_handler(stdlib_args))
        except PebbleRuntimeError as exc:
            self._runtime_error(exc.message)

    def _call_struct_constructor(self, name: str) -> None:
        """Dispatch a struct constructor call."""
        fields = self._structs[name]
        nfields = len(fields)
        args_list = [self._stack.pop() for _ in range(nfields)]
        args_list.reverse()
        if name in self._struct_field_types:
            field_types = self._struct_field_types[name]
            for field_name, arg_val in zip(fields, args_list, strict=True):
                if field_name in field_types:
                    expected = field_types[field_name]
                    self._check_field_type(arg_val, expected, field_name, name)
        instance = StructInstance(
            type_name=name,
            fields=dict(zip(fields, args_list, strict=True)),
        )
        self._stack.append(instance)

    def _call_user_function(self, name: str) -> None:
        """Dispatch a regular user-defined function call."""
        fn_code = self._functions[name]
        args: dict[str, Value] = {}
        for param in reversed(fn_code.parameters):
            args[param] = self._stack.pop()
        # Check parameter type annotations
        if fn_code.param_types:
            for param_name, param_type in zip(fn_code.parameters, fn_code.param_types, strict=True):
                if param_type is not None:
                    self._check_param_type(args[param_name], param_type, param_name)
        # Generator functions: create GeneratorObject, don't execute yet
        if fn_code.is_generator:
            cells: dict[str, Cell] = {}
            for cell_var in fn_code.cell_variables:
                if cell_var in args:
                    cells[cell_var] = Cell(args.pop(cell_var))
            gen = GeneratorObject(
                code=fn_code,
                ip=0,
                variables=args,
                cells=cells,
            )
            self._stack.append(gen)
            return
        new_frame = Frame(code=fn_code, variables=args)
        self._init_cells(new_frame)
        self._frames.append(new_frame)

    def _exec_call_method(self, instruction: Instruction) -> None:
        """Handle CALL_METHOD — pop args and target, dispatch to method handler."""
        method_name = _str_operand(instruction)

        # Determine max arity from whichever registry has this method
        if method_name in STRING_METHODS:
            max_arity = STRING_METHODS[method_name][0]
        elif method_name in LIST_METHODS:
            max_arity = LIST_METHODS[method_name][0]
        else:
            self._runtime_error(f"Unknown method '{method_name}'")

        # Pop max_arity args, then target
        raw_args = [self._stack.pop() for _ in range(max_arity)]
        raw_args.reverse()
        target = self._stack.pop()

        # Filter out sentinel values
        args: list[Value] = [a for a in raw_args if a != METHOD_NONE]

        # Type dispatch
        if isinstance(target, str):
            if method_name not in STRING_METHODS:
                self._runtime_error(f"String has no method '{method_name}'")
            _, handler = STRING_METHODS[method_name]
        elif isinstance(target, list):
            if method_name not in LIST_METHODS:
                self._runtime_error(f"List has no method '{method_name}'")
            _, handler = LIST_METHODS[method_name]
        else:
            type_name = type(target).__name__
            self._runtime_error(f"Cannot call methods on {type_name}")

        try:
            result = handler(target, args)
        except PebbleRuntimeError as exc:
            self._runtime_error(exc.message)
        self._stack.append(result)

    def _exec_call_instance_method(self, instruction: Instruction) -> None:
        """Handle CALL_INSTANCE_METHOD — dispatch to user-defined class method."""
        operand = _str_operand(instruction)
        method_name, arg_count_str = operand.rsplit(":", 1)
        arg_count = int(arg_count_str)

        # Pop args (in reverse) then target
        args_list = [self._stack.pop() for _ in range(arg_count)]
        args_list.reverse()
        target = self._stack.pop()

        if not isinstance(target, StructInstance):
            type_name = type(target).__name__
            self._runtime_error(f"Value of type '{type_name}' is not a struct")

        # Look up the mangled function name
        mangled = f"{target.type_name}.{method_name}"
        if mangled not in self._functions:
            self._runtime_error(f"Class '{target.type_name}' has no method '{method_name}'")

        fn_code = self._functions[mangled]

        # Build args dict: self=target + remaining params
        args: dict[str, Value] = {
            "self": target,
            **dict(zip(fn_code.parameters[1:], args_list, strict=True)),
        }

        # Check parameter type annotations (skip self's type)
        if fn_code.param_types:
            for param_name, param_type in zip(
                fn_code.parameters[1:], fn_code.param_types[1:], strict=True
            ):
                if param_type is not None:
                    self._check_param_type(args[param_name], param_type, param_name)

        new_frame = Frame(code=fn_code, variables=args)
        self._init_cells(new_frame)
        self._frames.append(new_frame)

    def _exec_make_closure(self, instruction: Instruction) -> None:
        """Handle MAKE_CLOSURE — create a Closure from a function and captured cells."""
        name = _str_operand(instruction)
        fn_code = self._functions[name]
        frame = self._frames[-1]
        cells = [frame.cells[var] for var in fn_code.free_variables]
        self._stack.append(Closure(code=fn_code, cells=cells))

    def _call_closure(self, closure: Closure) -> None:
        """Call a Closure value, setting up a new frame with captured cells."""
        fn_code = closure.code
        args: dict[str, Value] = {}
        for param in reversed(fn_code.parameters):
            args[param] = self._stack.pop()
        # Check parameter type annotations
        if fn_code.param_types:
            for param_name, param_type in zip(fn_code.parameters, fn_code.param_types, strict=True):
                if param_type is not None:
                    self._check_param_type(args[param_name], param_type, param_name)
        # Map free variable names to their Cell objects
        cells: dict[str, Cell] = dict(zip(fn_code.free_variables, closure.cells, strict=True))
        # Generator closures: create GeneratorObject, don't execute yet
        if fn_code.is_generator:
            for cell_var in fn_code.cell_variables:
                if cell_var in args:
                    cells[cell_var] = Cell(args.pop(cell_var))
            gen = GeneratorObject(
                code=fn_code,
                ip=0,
                variables=args,
                cells=cells,
            )
            self._stack.append(gen)
            return
        new_frame = Frame(code=fn_code, variables=args, cells=cells)
        self._init_cells(new_frame)
        self._frames.append(new_frame)

    @staticmethod
    def _init_cells(frame: Frame) -> None:
        """Move parameters that are cell variables into Cell storage."""
        for cell_var in frame.code.cell_variables:
            if cell_var in frame.variables:
                frame.cells[cell_var] = Cell(frame.variables.pop(cell_var))

    def _exec_return(self) -> None:
        """Handle RETURN — pop frame, push return value.

        If the frame belongs to a generator, mark it exhausted.
        """
        return_value = self._stack.pop()
        frame = self._frames.pop()
        if frame.generator is not None:
            frame.generator.exhausted = True
        self._stack.append(return_value)

    # -- Generator support ----------------------------------------------------

    def _exec_yield(self) -> None:
        """Handle YIELD — save frame state to generator, pop frame, push value."""
        value = self._stack.pop()
        frame = self._frames.pop()
        gen = frame.generator
        if gen is None:
            self._runtime_error("YIELD executed outside of a generator")
        # Save frame state back to generator
        gen.ip = frame.ip
        gen.variables = dict(frame.variables)
        gen.cells = dict(frame.cells)
        self._stack.append(value)

    def _advance_generator(self, gen: GeneratorObject) -> Value:
        """Resume a generator, run until YIELD or RETURN, return the yielded value.

        If the generator hits RETURN (exhaustion), mark it and raise an error
        when called from next(). When called from FOR_ITER, the caller checks
        ``gen.exhausted`` to decide whether to jump or push.
        """
        if gen.exhausted:
            self._runtime_error("Generator is exhausted")
        frame = Frame(
            code=gen.code,
            ip=gen.ip,
            variables=dict(gen.variables),
            cells=dict(gen.cells),
        )
        frame.generator = gen
        depth = len(self._frames)
        self._frames.append(frame)
        self._execute(min_depth=depth)
        return self._stack.pop()

    def _vm_builtin_next(self, args: list[Value]) -> None:
        """Implement next(generator) — advance generator and push result."""
        arg = args[0]
        if not isinstance(arg, GeneratorObject):
            self._runtime_error("next() requires a generator")
        result = self._advance_generator(arg)
        if arg.exhausted:
            self._runtime_error("Generator is exhausted")
        self._stack.append(result)

    # -- Iteration support ----------------------------------------------------

    def _exec_get_iter(self) -> None:
        """Handle GET_ITER — convert TOS to an iterator."""
        value = self._stack.pop()
        if isinstance(value, list):
            self._stack.append(SequenceIterator(items=list(value)))
        elif isinstance(value, str):
            self._stack.append(SequenceIterator(items=value))
        elif isinstance(value, GeneratorObject):
            self._stack.append(value)
        else:
            type_name = type(value).__name__
            self._runtime_error(f"Cannot iterate over {type_name}")

    def _exec_for_iter(self, instruction: Instruction, frame: Frame) -> None:
        """Handle FOR_ITER — advance iterator; push value or jump if exhausted."""
        target = _int_operand(instruction)
        iterator = self._stack.pop()
        if isinstance(iterator, SequenceIterator):
            length = len(iterator.items)
            if iterator.index < length:
                self._stack.append(iterator.items[iterator.index])
                iterator.index += 1
            else:
                frame.ip = target
        elif isinstance(iterator, GeneratorObject):
            if iterator.exhausted:
                frame.ip = target
            else:
                result = self._advance_generator(iterator)
                if iterator.exhausted:
                    frame.ip = target
                else:
                    self._stack.append(result)
        else:
            self._runtime_error("FOR_ITER requires an iterator")

    # -- Enum support ---------------------------------------------------------

    def _exec_load_enum_variant(self, instruction: Instruction) -> None:
        """Handle LOAD_ENUM_VARIANT — construct an EnumVariant and push it."""
        idx = _int_operand(instruction)
        frame = self._frames[-1]
        key = frame.code.constants[idx]
        if not isinstance(key, str):
            self._runtime_error("LOAD_ENUM_VARIANT constant must be a string")
        enum_name, variant_name = key.split(":", 1)
        self._stack.append(EnumVariant(enum_name=enum_name, variant_name=variant_name))

    # -- Type checking --------------------------------------------------------

    @staticmethod
    def _value_type_display(value: Value) -> str:
        """Return the annotation-style type name of *value*."""
        if value is None:
            return "Null"
        if isinstance(value, StructInstance):
            return value.type_name
        if isinstance(value, EnumVariant):
            return value.enum_name
        if isinstance(value, Closure):
            return "Fn"
        name = type(value).__name__
        return _TYPE_DISPLAY.get(name, name)

    @staticmethod
    def _matches_type(value: Value, type_name: str) -> bool:
        """Return True if *value* conforms to *type_name*."""
        match type_name:
            case "Int":
                return type(value) is int
            case "Bool":
                return isinstance(value, bool)
            case "Null":
                return value is None
            case _ if type_name in _TYPE_MAP:
                return isinstance(value, _TYPE_MAP[type_name])
            case _:
                return (isinstance(value, StructInstance) and value.type_name == type_name) or (
                    isinstance(value, EnumVariant) and value.enum_name == type_name
                )

    @staticmethod
    def _matches_type_annotation(value: Value, annotation: TypeAnnotation) -> bool:
        """Return True if *value* conforms to *annotation*, with deep element checking.

        For ``List[T]``, check that every element matches ``T``.
        For ``Dict[K, V]``, check that every key matches ``K`` and every value
        matches ``V``.  Nested annotations are validated recursively.
        Empty containers pass any parameterized check.
        """
        name = annotation.name
        params = annotation.params

        # Simple (non-parameterized) type — delegate to the flat checker
        if not params:
            return VirtualMachine._matches_type(value, name)

        # List[T] — container must be a list, then check each element
        if name == "List":
            if not isinstance(value, list):
                return False
            elem_ann = params[0]
            return all(VirtualMachine._matches_type_annotation(elem, elem_ann) for elem in value)

        # Dict[K, V] — container must be a dict, then check keys and values
        if name == "Dict":
            if not isinstance(value, dict):
                return False
            key_ann, val_ann = params[0], params[1]
            return all(
                VirtualMachine._matches_type_annotation(k, key_ann)
                and VirtualMachine._matches_type_annotation(v, val_ann)
                for k, v in value.items()
            )

        # Unknown parameterized type — fall back to base type check only
        return VirtualMachine._matches_type(value, name)

    def _check_type_annotation(self, value: Value, annotation: TypeAnnotation) -> None:
        """Validate *value* matches *annotation*, raising on mismatch."""
        if not self._matches_type_annotation(value, annotation):
            actual = self._value_type_display(value)
            self._runtime_error(f"Type error: expected {annotation}, got {actual}")

    def _exec_check_type(self, instruction: Instruction) -> None:
        """Handle CHECK_TYPE — peek TOS and validate type."""
        type_str = _str_operand(instruction)
        value = self._stack[-1]
        annotation = TypeAnnotation.from_string(type_str)
        self._check_type_annotation(value, annotation)

    def _check_param_type(self, value: Value, param_type: TypeAnnotation, param_name: str) -> None:
        """Validate a function parameter value matches its type annotation."""
        if not self._matches_type_annotation(value, param_type):
            actual = self._value_type_display(value)
            self._runtime_error(
                f"Type error: parameter '{param_name}' expected {param_type}, got {actual}"
            )

    def _check_field_type(
        self, value: Value, type_str: str, field_name: str, struct_name: str
    ) -> None:
        """Validate a struct field value matches its type annotation."""
        annotation = TypeAnnotation.from_string(type_str)
        if not self._matches_type_annotation(value, annotation):
            actual = self._value_type_display(value)
            self._runtime_error(
                f"Type error: field '{field_name}' of '{struct_name}' expected {annotation}, got {actual}"
            )

    # -- Exception handling ---------------------------------------------------

    def _unwind_exception(self, value: Value) -> None:
        """Route an exception to the nearest handler, or re-raise."""
        if not self._exception_handlers:
            if isinstance(value, str):
                self._runtime_error(value)
            raise _PebbleThrowError(value)

        handler = self._exception_handlers[-1]

        # If the handler belongs to an outer _execute context, re-raise
        if handler.frame_depth <= self._min_depth and self._min_depth > 0:
            raise _PebbleThrowError(value)

        self._exception_handlers.pop()

        # Unwind call frames
        while len(self._frames) > handler.frame_depth:
            self._frames.pop()

        # Unwind value stack
        while len(self._stack) > handler.stack_depth:
            self._stack.pop()

        # Push exception value and jump to handler
        self._stack.append(value)
        self._frames[-1].ip = handler.handler_ip

    # -- Callable helper ------------------------------------------------------

    def _call_callable(self, closure: Closure, args: list[Value]) -> Value:
        """Call *closure* with *args*, run to completion, return result."""
        fn_code = closure.code
        params = dict(zip(fn_code.parameters, args, strict=True))
        cells = dict(zip(fn_code.free_variables, closure.cells, strict=True))
        frame = Frame(code=fn_code, variables=params, cells=cells)
        self._init_cells(frame)
        depth = len(self._frames)
        self._frames.append(frame)
        self._execute(min_depth=depth)
        return self._stack.pop()

    # -- VM-level builtins (need VM access for callbacks) ---------------------

    def _vm_builtin_str(self, args: list[Value]) -> None:
        """Implement str(value) with __str__ dispatch."""
        self._stack.append(self._format_value(args[0]))

    def _vm_builtin_map(self, args: list[Value]) -> None:
        """Implement map(fn, list) -> list."""
        fn_val, list_val = args
        if not isinstance(fn_val, Closure):
            self._runtime_error("map() expects a function as the first argument")
        if not isinstance(list_val, list):
            self._runtime_error("map() expects a list as the second argument")
        result: list[Value] = [self._call_callable(fn_val, [elem]) for elem in list_val]
        self._stack.append(result)

    def _vm_builtin_filter(self, args: list[Value]) -> None:
        """Implement filter(fn, list) -> list."""
        fn_val, list_val = args
        if not isinstance(fn_val, Closure):
            self._runtime_error("filter() expects a function as the first argument")
        if not isinstance(list_val, list):
            self._runtime_error("filter() expects a list as the second argument")
        result: list[Value] = [elem for elem in list_val if self._call_callable(fn_val, [elem])]
        self._stack.append(result)

    def _vm_builtin_reduce(self, args: list[Value]) -> None:
        """Implement reduce(fn, list, initial) -> value."""
        fn_val, list_val, acc = args
        if not isinstance(fn_val, Closure):
            self._runtime_error("reduce() expects a function as the first argument")
        if not isinstance(list_val, list):
            self._runtime_error("reduce() expects a list as the second argument")
        for elem in list_val:
            acc = self._call_callable(fn_val, [acc, elem])
        self._stack.append(acc)

    # -- Stdlib VM-dispatched functions ----------------------------------------

    def _dispatch_vm_stdlib(self, name: str, arity: int | tuple[int, ...]) -> None:
        """Dispatch a VM-dispatched stdlib function (handler is None)."""
        actual_arity = arity if isinstance(arity, int) else max(arity)
        raw_args = [self._stack.pop() for _ in range(actual_arity)]
        raw_args.reverse()
        # Filter out sentinel padding values
        args: list[Value] = [a for a in raw_args if a != METHOD_NONE]
        match name:
            case "input":
                self._stdlib_input(args)
            case _:  # pragma: no cover
                self._runtime_error(f"Unknown VM-stdlib function '{name}'")

    def _stdlib_input(self, args: list[Value]) -> None:
        """Implement input([prompt]) — read a line from the input stream."""
        if args:
            self._output.write(str(args[0]))
            self._output.flush()
        line = self._input_stream.readline()
        self._stack.append(line.rstrip("\n"))

    # -- Typed operation helpers -----------------------------------------------

    def _check_zero_divisor(self, right: Value) -> None:
        """Raise PebbleRuntimeError if *right* is numeric zero."""
        if isinstance(right, bool):
            return
        if isinstance(right, int | float) and right == 0:
            self._runtime_error(_DIVISION_BY_ZERO)

    def _type_error(self, symbol: str, left: Value, right: Value) -> Never:
        """Raise a PebbleRuntimeError for an unsupported operand pair."""
        left_type = _display_type(left)
        right_type = _display_type(right)
        self._runtime_error(f"Unsupported operand types for {symbol}: {left_type} and {right_type}")

    def _apply_numeric(
        self,
        symbol: str,
        left: Value,
        right: Value,
        op: Callable[[int | float, int | float], int | float],
    ) -> None:
        """Apply *op* to two numeric operands (int or float), or raise a type error."""
        if _both_numeric(left, right):
            self._stack.append(op(left, right))  # type: ignore[arg-type]
        else:
            self._type_error(symbol, left, right)

    def _apply_comparison(
        self,
        symbol: str,
        left: Value,
        right: Value,
        op: Callable[[int | float, int | float], bool],
    ) -> None:
        """Apply comparison *op* to two numeric operands, or raise a type error."""
        if _both_numeric(left, right):
            self._stack.append(op(left, right))  # type: ignore[arg-type]
        else:
            self._type_error(symbol, left, right)


# -- Module-level helpers (no self needed) ------------------------------------


def _display_type(value: Value) -> str:
    """Return a Pebble-friendly type name for *value*."""
    if value is None:
        return "Null"
    if isinstance(value, StructInstance):
        return value.type_name
    if isinstance(value, EnumVariant):
        return value.enum_name
    name = type(value).__name__
    return _TYPE_DISPLAY.get(name, name)


def _both_numeric(left: Value, right: Value) -> bool:
    """Return True if both operands are plain ints or floats (not bools)."""
    return _is_numeric(left) and _is_numeric(right)


def _is_numeric(value: Value) -> bool:
    """Return True if *value* is a plain int or float (not bool)."""
    if isinstance(value, bool):
        return False
    return isinstance(value, int | float)


def _is_plain_int(value: Value) -> bool:
    """Return True if *value* is a plain int (not bool or float)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _int_operand(instruction: Instruction) -> int:
    """Extract an int operand from *instruction*."""
    operand = instruction.operand
    if not isinstance(operand, int):  # pragma: no cover
        msg = f"Expected int operand, got {type(operand)}"
        raise TypeError(msg)
    return operand


def _str_operand(instruction: Instruction) -> str:
    """Extract a str operand from *instruction*."""
    operand = instruction.operand
    if not isinstance(operand, str):  # pragma: no cover
        msg = f"Expected str operand, got {type(operand)}"
        raise TypeError(msg)
    return operand
