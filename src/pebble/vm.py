"""Stack-based virtual machine for the Pebble language.

Execute compiled bytecode by maintaining a value stack, a call stack of
:class:`Frame` objects, and a dictionary of function :class:`CodeObject`
references.  The VM processes one instruction at a time until it reaches
a ``HALT`` opcode.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Never

from pebble.bytecode import Instruction, OpCode
from pebble.errors import PebbleRuntimeError

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TextIO

    from pebble.bytecode import CodeObject, CompiledProgram

type Value = int | str | bool | list[Value]

_DIVISION_BY_ZERO = "Division by zero"


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
    variables: dict[str, Value] = field(
        default_factory=lambda: {},  # noqa: PIE807
    )


class VirtualMachine:
    """Execute a :class:`CompiledProgram` on a stack-based VM.

    Args:
        output: Writable text stream for ``print`` output (default ``sys.stdout``).

    """

    def __init__(self, output: TextIO | None = None) -> None:
        """Create a VM with an empty stack and call stack."""
        self._stack: list[Value] = []
        self._frames: list[Frame] = []
        self._functions: dict[str, CodeObject] = {}
        self._output: TextIO = output or sys.stdout

    # -- Public API -----------------------------------------------------------

    def run(self, program: CompiledProgram) -> None:
        """Execute *program* from the first instruction of ``main``."""
        self._functions = dict(program.functions)
        self._frames = [Frame(code=program.main)]
        self._execute()

    # -- Execution loop -------------------------------------------------------

    def _execute(self) -> None:
        """Fetch-decode-execute loop."""
        while self._frames:
            frame = self._frames[-1]
            instruction = frame.code.instructions[frame.ip]
            frame.ip += 1

            match instruction.opcode:
                case OpCode.LOAD_CONST | OpCode.STORE_NAME | OpCode.LOAD_NAME:
                    self._exec_variables(instruction, frame)
                case (
                    OpCode.ADD
                    | OpCode.SUBTRACT
                    | OpCode.MULTIPLY
                    | OpCode.DIVIDE
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
                case OpCode.BUILD_STRING | OpCode.BUILD_LIST | OpCode.INDEX_GET | OpCode.INDEX_SET:
                    self._exec_collection(instruction)
                case OpCode.PRINT:
                    self._output.write(self._format_value(self._stack.pop()) + "\n")
                case OpCode.CALL:
                    self._exec_call(instruction)
                case OpCode.RETURN:
                    self._exec_return()
                case OpCode.HALT:
                    return

    # -- Dispatch groups ------------------------------------------------------

    def _exec_variables(self, instruction: Instruction, frame: Frame) -> None:
        """Handle LOAD_CONST, STORE_NAME, and LOAD_NAME."""
        match instruction.opcode:
            case OpCode.LOAD_CONST:
                operand = _int_operand(instruction)
                self._stack.append(frame.code.constants[operand])
            case OpCode.STORE_NAME:
                operand = _str_operand(instruction)
                frame.variables[operand] = self._stack.pop()
            case OpCode.LOAD_NAME:
                operand = _str_operand(instruction)
                self._stack.append(frame.variables[operand])
            case _:  # pragma: no cover
                pass

    def _exec_arithmetic(self, instruction: Instruction) -> None:
        """Handle ADD, SUBTRACT, MULTIPLY, DIVIDE, MODULO, NEGATE."""
        match instruction.opcode:
            case OpCode.ADD:
                self._exec_add()
            case OpCode.SUBTRACT:
                right, left = self._stack.pop(), self._stack.pop()
                self._apply_arithmetic("-", left, right, lambda a, b: a - b)
            case OpCode.MULTIPLY:
                right, left = self._stack.pop(), self._stack.pop()
                self._apply_arithmetic("*", left, right, lambda a, b: a * b)
            case OpCode.DIVIDE:
                right, left = self._stack.pop(), self._stack.pop()
                _check_zero_divisor(right)
                self._apply_arithmetic("/", left, right, lambda a, b: a // b)
            case OpCode.MODULO:
                right, left = self._stack.pop(), self._stack.pop()
                _check_zero_divisor(right)
                self._apply_arithmetic("%", left, right, lambda a, b: a % b)
            case OpCode.NEGATE:
                self._exec_negate()
            case _:  # pragma: no cover
                pass

    def _exec_add(self) -> None:
        """Handle ADD — supports int + int and str + str."""
        right, left = self._stack.pop(), self._stack.pop()
        if isinstance(left, str) and isinstance(right, str):
            self._stack.append(left + right)
        elif _both_int(left, right):
            # Type-checker knows they are int after _both_int, but we need
            # explicit narrowing since _both_int is a plain bool return.
            self._stack.append(left + right)  # type: ignore[operator]
        else:
            _type_error("+", left, right)

    def _exec_negate(self) -> None:
        """Handle NEGATE — only valid on integers."""
        operand = self._stack.pop()
        if not isinstance(operand, int) or isinstance(operand, bool):
            type_name = type(operand).__name__
            msg = f"Unsupported operand type for negation: {type_name}"
            raise PebbleRuntimeError(msg, line=0, column=0)
        self._stack.append(-operand)

    def _exec_logic(self, instruction: Instruction) -> None:
        """Handle NOT, comparisons, AND, and OR."""
        match instruction.opcode:
            case OpCode.NOT:
                self._stack.append(not self._stack.pop())
            case OpCode.EQUAL:
                right, left = self._stack.pop(), self._stack.pop()
                self._stack.append(left == right)
            case OpCode.NOT_EQUAL:
                right, left = self._stack.pop(), self._stack.pop()
                self._stack.append(left != right)
            case OpCode.LESS_THAN:
                right, left = self._stack.pop(), self._stack.pop()
                self._apply_comparison("<", left, right, lambda a, b: a < b)
            case OpCode.LESS_EQUAL:
                right, left = self._stack.pop(), self._stack.pop()
                self._apply_comparison("<=", left, right, lambda a, b: a <= b)
            case OpCode.GREATER_THAN:
                right, left = self._stack.pop(), self._stack.pop()
                self._apply_comparison(">", left, right, lambda a, b: a > b)
            case OpCode.GREATER_EQUAL:
                right, left = self._stack.pop(), self._stack.pop()
                self._apply_comparison(">=", left, right, lambda a, b: a >= b)
            case OpCode.AND:
                right, left = self._stack.pop(), self._stack.pop()
                self._stack.append(left and right)
            case OpCode.OR:
                right, left = self._stack.pop(), self._stack.pop()
                self._stack.append(left or right)
            case _:  # pragma: no cover
                pass

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

    def _exec_collection(self, instruction: Instruction) -> None:
        """Handle BUILD_STRING, BUILD_LIST, INDEX_GET, and INDEX_SET."""
        match instruction.opcode:
            case OpCode.BUILD_STRING:
                self._exec_build_string(instruction)
            case OpCode.BUILD_LIST:
                self._exec_build_list(instruction)
            case OpCode.INDEX_GET:
                self._exec_index_get()
            case OpCode.INDEX_SET:
                self._exec_index_set()
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

    def _exec_index_get(self) -> None:
        """Handle INDEX_GET — pop index and target, push target[index]."""
        index = self._stack.pop()
        target = self._stack.pop()
        if not isinstance(target, list):
            type_name = type(target).__name__
            msg = f"Cannot index into {type_name}"
            raise PebbleRuntimeError(msg, line=0, column=0)
        if not isinstance(index, int) or isinstance(index, bool):
            type_name = type(index).__name__
            msg = f"List index must be an integer, got {type_name}"
            raise PebbleRuntimeError(msg, line=0, column=0)
        if index < 0 or index >= len(target):
            msg = f"Index {index} out of bounds for list of length {len(target)}"
            raise PebbleRuntimeError(msg, line=0, column=0)
        self._stack.append(target[index])

    def _exec_index_set(self) -> None:
        """Handle INDEX_SET — pop value, index, target; mutate target[index]."""
        value = self._stack.pop()
        index = self._stack.pop()
        target = self._stack.pop()
        if not isinstance(target, list):
            type_name = type(target).__name__
            msg = f"Cannot index into {type_name}"
            raise PebbleRuntimeError(msg, line=0, column=0)
        if not isinstance(index, int) or isinstance(index, bool):
            type_name = type(index).__name__
            msg = f"List index must be an integer, got {type_name}"
            raise PebbleRuntimeError(msg, line=0, column=0)
        if index < 0 or index >= len(target):
            msg = f"Index {index} out of bounds for list of length {len(target)}"
            raise PebbleRuntimeError(msg, line=0, column=0)
        target[index] = value

    def _exec_call(self, instruction: Instruction) -> None:
        """Handle CALL — check builtins first, then user functions."""
        name = _str_operand(instruction)

        # Built-in function dispatch
        if name == "len":
            arg = self._stack.pop()
            if isinstance(arg, list | str):
                self._stack.append(len(arg))
            else:
                type_name = type(arg).__name__
                msg = f"len() not supported for {type_name}"
                raise PebbleRuntimeError(msg, line=0, column=0)
            return

        fn_code = self._functions[name]
        args: dict[str, Value] = {}
        for param in reversed(fn_code.parameters):
            args[param] = self._stack.pop()
        self._frames.append(Frame(code=fn_code, variables=args))

    def _exec_return(self) -> None:
        """Handle RETURN — pop frame, push return value."""
        return_value = self._stack.pop()
        self._frames.pop()
        self._stack.append(return_value)

    # -- Typed operation helpers -----------------------------------------------

    def _apply_arithmetic(
        self,
        symbol: str,
        left: Value,
        right: Value,
        op: Callable[[int, int], int],
    ) -> None:
        """Apply *op* to two integer operands, or raise a type error."""
        if _both_int(left, right):
            self._stack.append(op(left, right))  # type: ignore[arg-type]
        else:
            _type_error(symbol, left, right)

    def _apply_comparison(
        self,
        symbol: str,
        left: Value,
        right: Value,
        op: Callable[[int, int], bool],
    ) -> None:
        """Apply comparison *op* to two integer operands, or raise a type error."""
        if _both_int(left, right):
            self._stack.append(op(left, right))  # type: ignore[arg-type]
        else:
            _type_error(symbol, left, right)

    # -- Formatting -----------------------------------------------------------

    @staticmethod
    def _format_value(value: Value) -> str:
        """Format *value* for Pebble-native output."""
        match value:
            case bool():
                return "true" if value else "false"
            case int():
                return str(value)
            case str():
                return value
            case list():
                items = ", ".join(VirtualMachine._format_value(v) for v in value)
                return f"[{items}]"


# -- Module-level helpers (no self needed) ------------------------------------


def _both_int(left: Value, right: Value) -> bool:
    """Return True if both operands are plain ints (not bools)."""
    return (
        isinstance(left, int)
        and isinstance(right, int)
        and not isinstance(left, bool)
        and not isinstance(right, bool)
    )


def _check_zero_divisor(right: Value) -> None:
    """Raise PebbleRuntimeError if *right* is integer zero."""
    if isinstance(right, int) and not isinstance(right, bool) and right == 0:
        raise PebbleRuntimeError(_DIVISION_BY_ZERO, line=0, column=0)


def _type_error(symbol: str, left: Value, right: Value) -> Never:
    """Raise a PebbleRuntimeError for an unsupported operand pair."""
    left_type = type(left).__name__
    right_type = type(right).__name__
    msg = f"Unsupported operand types for {symbol}: {left_type} and {right_type}"
    raise PebbleRuntimeError(msg, line=0, column=0)


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
