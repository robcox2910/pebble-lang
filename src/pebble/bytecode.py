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
    DIVIDE = "DIVIDE"
    MODULO = "MODULO"

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

    # -- Stack ----------------------------------------------------------------
    POP = "POP"

    # -- Functions ------------------------------------------------------------
    CALL = "CALL"
    RETURN = "RETURN"

    # -- Strings --------------------------------------------------------------
    BUILD_STRING = "BUILD_STRING"

    # -- Lists ----------------------------------------------------------------
    BUILD_LIST = "BUILD_LIST"
    INDEX_GET = "INDEX_GET"
    INDEX_SET = "INDEX_SET"

    # -- I/O ------------------------------------------------------------------
    PRINT = "PRINT"

    # -- Program --------------------------------------------------------------
    HALT = "HALT"


@dataclass(frozen=True)
class Instruction:
    """A single bytecode instruction.

    Attributes:
        opcode: The operation to perform.
        operand: Optional argument — a constant-pool index (int), variable or
            function name (str), or jump target (int).

    """

    opcode: OpCode
    operand: int | str | None = None


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
    constants: list[int | str | bool] = field(
        default_factory=lambda: [],  # noqa: PIE807
    )
    parameters: list[str] = field(
        default_factory=lambda: [],  # noqa: PIE807
    )

    def add_constant(self, value: int | str | bool) -> int:  # noqa: FBT001
        """Add *value* to the constant pool and return its index.

        Duplicate entries (same value *and* type) are reused.
        """
        for idx, existing in enumerate(self.constants):
            if existing == value and type(existing) is type(value):
                return idx
        self.constants.append(value)
        return len(self.constants) - 1


@dataclass(frozen=True)
class CompiledProgram:
    """Final compiler output: a main code object plus per-function code objects.

    Attributes:
        main: The top-level instruction sequence.
        functions: Map of function name to its ``CodeObject``.

    """

    main: CodeObject
    functions: dict[str, CodeObject]
