"""Bytecode representation for the Pebble compiler.

The compiler translates an AST into a flat sequence of :class:`Instruction`
objects, each carrying an :class:`OpCode` and an optional operand.

:class:`CodeObject` holds the instruction sequence and constant pool for one
compilation unit (the main program or a single function).

:class:`CompiledProgram` is the final output — one *main* ``CodeObject`` plus a
dictionary of function ``CodeObject``s.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pebble.tokens import SourceLocation


class OpCode(StrEnum):
    """Bytecode operation codes for the Pebble VM.

    Each opcode maps to a single stack-machine instruction.
    """

    # -- Constants & variables ------------------------------------------------
    LOAD_CONST = "LOAD_CONST"
    STORE_NAME = "STORE_NAME"
    LOAD_NAME = "LOAD_NAME"

    # -- Arithmetic -----------------------------------------------------------
    ADD = "ADD"
    SUBTRACT = "SUBTRACT"
    MULTIPLY = "MULTIPLY"
    POWER = "POWER"
    DIVIDE = "DIVIDE"
    FLOOR_DIVIDE = "FLOOR_DIVIDE"
    MODULO = "MODULO"

    # -- Bitwise --------------------------------------------------------------
    BIT_AND = "BIT_AND"
    BIT_OR = "BIT_OR"
    BIT_XOR = "BIT_XOR"
    BIT_NOT = "BIT_NOT"
    LEFT_SHIFT = "LEFT_SHIFT"
    RIGHT_SHIFT = "RIGHT_SHIFT"

    # -- Unary ----------------------------------------------------------------
    NEGATE = "NEGATE"
    NOT = "NOT"

    # -- Comparison -----------------------------------------------------------
    EQUAL = "EQUAL"
    NOT_EQUAL = "NOT_EQUAL"
    LESS_THAN = "LESS_THAN"
    LESS_EQUAL = "LESS_EQUAL"
    GREATER_THAN = "GREATER_THAN"
    GREATER_EQUAL = "GREATER_EQUAL"

    # -- Logical --------------------------------------------------------------
    AND = "AND"
    OR = "OR"

    # -- Control flow ---------------------------------------------------------
    JUMP = "JUMP"
    JUMP_IF_FALSE = "JUMP_IF_FALSE"
    SETUP_TRY = "SETUP_TRY"
    POP_TRY = "POP_TRY"
    THROW = "THROW"

    # -- Stack ----------------------------------------------------------------
    POP = "POP"

    # -- Functions ------------------------------------------------------------
    CALL = "CALL"
    CALL_METHOD = "CALL_METHOD"
    CALL_INSTANCE_METHOD = "CALL_INSTANCE_METHOD"
    RETURN = "RETURN"

    # -- Closures -------------------------------------------------------------
    MAKE_CLOSURE = "MAKE_CLOSURE"
    LOAD_CELL = "LOAD_CELL"
    STORE_CELL = "STORE_CELL"

    # -- Strings --------------------------------------------------------------
    BUILD_STRING = "BUILD_STRING"

    # -- Lists ----------------------------------------------------------------
    BUILD_LIST = "BUILD_LIST"
    LIST_APPEND = "LIST_APPEND"
    BUILD_DICT = "BUILD_DICT"
    INDEX_GET = "INDEX_GET"
    INDEX_SET = "INDEX_SET"
    SLICE_GET = "SLICE_GET"

    # -- Structs --------------------------------------------------------------
    GET_FIELD = "GET_FIELD"
    SET_FIELD = "SET_FIELD"

    # -- Enums ----------------------------------------------------------------
    LOAD_ENUM_VARIANT = "LOAD_ENUM_VARIANT"

    # -- Unpacking ------------------------------------------------------------
    UNPACK_SEQUENCE = "UNPACK_SEQUENCE"

    # -- I/O ------------------------------------------------------------------
    PRINT = "PRINT"

    # -- Type checking --------------------------------------------------------
    CHECK_TYPE = "CHECK_TYPE"

    # -- Program --------------------------------------------------------------
    HALT = "HALT"


@dataclass(frozen=True)
class Instruction:
    """A single bytecode instruction.

    Attributes:
        opcode: The operation to perform.
        operand: Optional argument — a constant-pool index (int), variable or
            function name (str), or jump target (int).
        location: Source location this instruction was compiled from, used for
            runtime error reporting.

    """

    opcode: OpCode
    operand: int | str | None = None
    location: SourceLocation | None = None


@dataclass
class CodeObject:
    """Instruction sequence and constant pool for one compilation unit.

    Use :meth:`add_constant` to populate the constant pool — it deduplicates
    by both value *and* type so that ``0`` (int) and ``False`` (bool) remain
    distinct entries.

    Attributes:
        name: Human-readable label (``"<main>"`` or the function name).
        instructions: Mutable list built up during compilation.
        constants: Deduplicated pool of literal values.
        parameters: Ordered list of parameter names for function code objects.

    """

    name: str
    instructions: list[Instruction] = field(
        default_factory=lambda: [],  # noqa: PIE807
    )
    constants: list[int | float | str | bool | None] = field(
        default_factory=lambda: [],  # noqa: PIE807
    )
    parameters: list[str] = field(
        default_factory=lambda: [],  # noqa: PIE807
    )
    cell_variables: list[str] = field(
        default_factory=lambda: [],  # noqa: PIE807
    )
    free_variables: list[str] = field(
        default_factory=lambda: [],  # noqa: PIE807
    )
    param_types: list[str | None] = field(
        default_factory=lambda: [],  # noqa: PIE807
    )
    return_type: str | None = None

    _constant_index: dict[tuple[type, int | float | str | bool | None], int] = field(
        default_factory=lambda: {},  # noqa: PIE807
        repr=False,
    )

    def add_constant(self, value: int | float | str | bool | None) -> int:  # noqa: FBT001
        """Add *value* to the constant pool and return its index.

        Duplicate entries (same value *and* type) are reused.  A cache
        dictionary keeps lookups O(1) instead of scanning the pool.
        """
        key = (type(value), value)
        if key in self._constant_index:
            return self._constant_index[key]
        idx = len(self.constants)
        self.constants.append(value)
        self._constant_index[key] = idx
        return idx


@dataclass(frozen=True)
class CompiledProgram:
    """Final compiler output: a main code object plus per-function code objects.

    Attributes:
        main: The top-level instruction sequence.
        functions: Map of function name to its ``CodeObject``.

    """

    main: CodeObject
    functions: dict[str, CodeObject]
    structs: dict[str, list[str]] = field(default_factory=lambda: {})  # noqa: PIE807
    struct_field_types: dict[str, dict[str, str]] = field(
        default_factory=lambda: {},  # noqa: PIE807
    )
    class_methods: dict[str, list[str]] = field(
        default_factory=lambda: {},  # noqa: PIE807
    )
    enums: dict[str, list[str]] = field(default_factory=lambda: {})  # noqa: PIE807
    class_parents: dict[str, str] = field(default_factory=lambda: {})  # noqa: PIE807
