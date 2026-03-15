"""Stack-based virtual machine for the Pebble language.

Execute compiled bytecode by maintaining a value stack, a call stack of
:class:`Frame` objects, and a dictionary of function :class:`CodeObject`
references.  The VM processes one instruction at a time until it reaches
a ``HALT`` opcode.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Never

from pebble.builtins import (
    BUILTIN_ARITIES,
    BUILTINS,
    LIST_METHODS,
    METHOD_NONE,
    STRING_METHODS,
    Cell,
    Closure,
    StructInstance,
    Value,
    format_value,
)
from pebble.bytecode import Instruction, OpCode
from pebble.errors import PebbleRuntimeError

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TextIO

    from pebble.bytecode import CodeObject, CompiledProgram

_DIVISION_BY_ZERO = "Division by zero"


class _PebbleThrow(Exception):  # noqa: N818
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
    variables: dict[str, Value] = field(
        default_factory=lambda: {},  # noqa: PIE807
    )
    cells: dict[str, Cell] = field(
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
        self._structs: dict[str, list[str]] = {}
        self._output: TextIO = output or sys.stdout
        self._current_instruction: Instruction | None = None
        self._exception_handlers: list[_ExceptionHandler] = []
        self._min_depth: int = 0

    # -- Public API -----------------------------------------------------------

    def run(self, program: CompiledProgram) -> None:
        """Execute *program* from the first instruction of ``main``."""
        self._functions = dict(program.functions)
        self._structs = dict(program.structs)
        self._frames = [Frame(code=program.main)]
        self._exception_handlers = []
        try:
            self._execute()
        except _PebbleThrow as exc:
            raise PebbleRuntimeError(str(exc.value), line=0, column=0) from None

    def run_repl(
        self,
        program: CompiledProgram,
        variables: dict[str, Value],
    ) -> dict[str, Value]:
        """Execute *program* with initial *variables*, return updated state.

        Used by the REPL to carry variable bindings across inputs.
        """
        self._functions = dict(program.functions)
        self._structs = dict(program.structs)
        self._frames = [Frame(code=program.main, variables=dict(variables))]
        self._exception_handlers = []
        try:
            self._execute()
        except _PebbleThrow as exc:
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
            except _PebbleThrow as exc:
                self._unwind_exception(exc.value)
            except PebbleRuntimeError as exc:
                if self._exception_handlers:
                    self._unwind_exception(exc.message)
                else:
                    raise

    def _dispatch(self, instruction: Instruction, frame: Frame) -> None:  # noqa: PLR0912
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
            case OpCode.PRINT:
                self._output.write(self._format_value(self._stack.pop()) + "\n")
            case OpCode.CALL:
                self._exec_call(instruction)
            case OpCode.CALL_METHOD:
                self._exec_call_method(instruction)
            case OpCode.RETURN:
                self._exec_return()
            case OpCode.MAKE_CLOSURE:
                self._exec_make_closure(instruction)
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
                raise _PebbleThrow(self._stack.pop())
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

    def _exec_arithmetic(self, instruction: Instruction) -> None:
        """Handle ADD, SUBTRACT, MULTIPLY, POWER, DIVIDE, FLOOR_DIVIDE, MODULO, NEGATE."""
        match instruction.opcode:
            case OpCode.ADD:
                self._exec_add()
            case OpCode.POWER:
                self._exec_power()
            case OpCode.SUBTRACT:
                right, left = self._stack.pop(), self._stack.pop()
                self._apply_numeric("-", left, right, lambda a, b: a - b)
            case OpCode.MULTIPLY:
                right, left = self._stack.pop(), self._stack.pop()
                self._apply_numeric("*", left, right, lambda a, b: a * b)
            case OpCode.DIVIDE:
                right, left = self._stack.pop(), self._stack.pop()
                self._check_zero_divisor(right)
                # True division — always returns float
                if _both_numeric(left, right):
                    result = float(left) / float(right)  # type: ignore[arg-type]
                    self._stack.append(result)
                else:
                    self._type_error("/", left, right)
            case OpCode.FLOOR_DIVIDE:
                right, left = self._stack.pop(), self._stack.pop()
                self._check_zero_divisor(right)
                self._apply_numeric("//", left, right, lambda a, b: a // b)
            case OpCode.MODULO:
                right, left = self._stack.pop(), self._stack.pop()
                self._check_zero_divisor(right)
                self._apply_numeric("%", left, right, lambda a, b: a % b)
            case OpCode.NEGATE:
                self._exec_negate()
            case _:  # pragma: no cover
                pass

    def _exec_add(self) -> None:
        """Handle ADD — support int+int, float+float, int+float, str+str."""
        right, left = self._stack.pop(), self._stack.pop()
        if isinstance(left, str) and isinstance(right, str):
            self._stack.append(left + right)
        elif _both_numeric(left, right):
            self._stack.append(left + right)  # type: ignore[operator]
        else:
            self._type_error("+", left, right)

    def _exec_negate(self) -> None:
        """Handle NEGATE — valid on integers and floats."""
        operand = self._stack.pop()
        if isinstance(operand, float) or (
            isinstance(operand, int) and not isinstance(operand, bool)
        ):
            self._stack.append(-operand)
        else:
            type_name = type(operand).__name__
            self._runtime_error(f"Unsupported operand type for negation: {type_name}")

    def _exec_power(self) -> None:
        """Handle POWER — int**int→int unless negative exponent, mixed→float."""
        right, left = self._stack.pop(), self._stack.pop()
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
                    type_name = type(operand).__name__
                    self._runtime_error(f"Unsupported operand type for bitwise NOT: {type_name}")
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
        assert isinstance(target, list)  # noqa: S101
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
        if not isinstance(index, int) or isinstance(index, bool):
            type_name = type(index).__name__
            self._runtime_error(f"List index must be an integer, got {type_name}")
        if index < -len(target) or index >= len(target):
            self._runtime_error(f"Index {index} out of bounds for list of length {len(target)}")
        if index < 0:
            index += len(target)
        self._stack.append(target[index])

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
        if not isinstance(index, int) or isinstance(index, bool):
            type_name = type(index).__name__
            self._runtime_error(f"List index must be an integer, got {type_name}")
        if index < -len(target) or index >= len(target):
            self._runtime_error(f"Index {index} out of bounds for list of length {len(target)}")
        if index < 0:
            index += len(target)
        target[index] = value

    _SLICE_SENTINEL: ClassVar[str] = "$SLICE_NONE"

    def _exec_slice_get(self) -> None:
        """Handle SLICE_GET — pop step, stop, start, target; push sliced result."""
        raw_step = self._stack.pop()
        raw_stop = self._stack.pop()
        raw_start = self._stack.pop()
        target = self._stack.pop()

        # Replace sentinel strings with None
        start = None if raw_start == self._SLICE_SENTINEL else raw_start
        stop = None if raw_stop == self._SLICE_SENTINEL else raw_stop
        step = None if raw_step == self._SLICE_SENTINEL else raw_step

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
        target.fields[field_name] = value

    # Map of VM-level builtin names to handler methods.
    _VM_BUILTINS: ClassVar[dict[str, str]] = {
        "map": "_vm_builtin_map",
        "filter": "_vm_builtin_filter",
        "reduce": "_vm_builtin_reduce",
    }

    def _exec_call(self, instruction: Instruction) -> None:
        """Handle CALL — check builtins, VM builtins, closures, then user functions."""
        name = _str_operand(instruction)

        # Built-in function dispatch (pure — no VM access needed)
        if name in BUILTINS:
            arity, handler = BUILTINS[name]
            builtin_args = [self._stack.pop() for _ in range(arity)]
            builtin_args.reverse()
            try:
                self._stack.append(handler(builtin_args))
            except PebbleRuntimeError as exc:
                self._runtime_error(exc.message)
            return

        # VM-level builtin dispatch (needs VM access for callbacks)
        if name in self._VM_BUILTINS:
            arity = BUILTIN_ARITIES[name]
            assert isinstance(arity, int)  # noqa: S101
            vm_args = [self._stack.pop() for _ in range(arity)]
            vm_args.reverse()
            getattr(self, self._VM_BUILTINS[name])(vm_args)
            return

        # Struct construction dispatch
        if name in self._structs:
            fields = self._structs[name]
            nfields = len(fields)
            args_list = [self._stack.pop() for _ in range(nfields)]
            args_list.reverse()
            if len(args_list) != nfields:
                self._runtime_error(
                    f"Struct '{name}' expects {nfields} arguments, got {len(args_list)}"
                )
            instance = StructInstance(
                type_name=name,
                fields=dict(zip(fields, args_list, strict=True)),
            )
            self._stack.append(instance)
            return

        # Closure dispatch — check if name resolves to a Closure in variables
        frame = self._frames[-1]
        if name in frame.variables:
            value = frame.variables[name]
            if isinstance(value, Closure):
                self._call_closure(value)
                return

        # Regular user function dispatch
        fn_code = self._functions[name]
        args: dict[str, Value] = {}
        for param in reversed(fn_code.parameters):
            args[param] = self._stack.pop()
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
        # Map free variable names to their Cell objects
        cells: dict[str, Cell] = dict(zip(fn_code.free_variables, closure.cells, strict=True))
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
        """Handle RETURN — pop frame, push return value."""
        return_value = self._stack.pop()
        self._frames.pop()
        self._stack.append(return_value)

    # -- Exception handling ---------------------------------------------------

    def _unwind_exception(self, value: Value) -> None:
        """Route an exception to the nearest handler, or re-raise."""
        if not self._exception_handlers:
            if isinstance(value, str):
                self._runtime_error(value)
            raise _PebbleThrow(value)

        handler = self._exception_handlers[-1]

        # If the handler belongs to an outer _execute context, re-raise
        if handler.frame_depth <= self._min_depth and self._min_depth > 0:
            raise _PebbleThrow(value)

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

    # -- Typed operation helpers -----------------------------------------------

    def _check_zero_divisor(self, right: Value) -> None:
        """Raise PebbleRuntimeError if *right* is numeric zero."""
        if isinstance(right, bool):
            return
        if isinstance(right, int | float) and right == 0:
            self._runtime_error(_DIVISION_BY_ZERO)

    def _type_error(self, symbol: str, left: Value, right: Value) -> Never:
        """Raise a PebbleRuntimeError for an unsupported operand pair."""
        left_type = type(left).__name__
        right_type = type(right).__name__
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

    # -- Formatting -----------------------------------------------------------

    @staticmethod
    def _format_value(value: Value) -> str:
        """Format *value* for Pebble-native output."""
        return format_value(value)


# -- Module-level helpers (no self needed) ------------------------------------


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
