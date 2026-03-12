"""Tests for the Pebble bytecode data structures.

Cover OpCode enumeration, Instruction immutability, CodeObject constant-pool
deduplication, and CompiledProgram construction.
"""

import pytest

from pebble.bytecode import CodeObject, CompiledProgram, Instruction, OpCode

# -- Named constants ----------------------------------------------------------

OPCODE_COUNT = 26
FIRST_INDEX = 0
SECOND_INDEX = 1
THIRD_INDEX = 2


# -- OpCode ------------------------------------------------------------------


class TestOpCode:
    """Verify OpCode is a StrEnum with the correct members."""

    def test_is_str_enum(self) -> None:
        """Each OpCode value is also a str."""
        assert isinstance(OpCode.ADD, str)

    def test_has_24_members(self) -> None:
        """The enum defines exactly 24 opcodes."""
        assert len(OpCode) == OPCODE_COUNT

    def test_representative_values(self) -> None:
        """Spot-check a few opcode string values."""
        assert OpCode.LOAD_CONST == "LOAD_CONST"
        assert OpCode.HALT == "HALT"
        assert OpCode.JUMP_IF_FALSE == "JUMP_IF_FALSE"


# -- Instruction --------------------------------------------------------------


class TestInstruction:
    """Verify Instruction is frozen and stores opcode + optional operand."""

    def test_instruction_with_operand(self) -> None:
        """Create an instruction with an integer operand."""
        inst = Instruction(OpCode.LOAD_CONST, FIRST_INDEX)
        assert inst.opcode is OpCode.LOAD_CONST
        assert inst.operand == FIRST_INDEX

    def test_instruction_without_operand(self) -> None:
        """Operand defaults to None when omitted."""
        inst = Instruction(OpCode.ADD)
        assert inst.opcode is OpCode.ADD
        assert inst.operand is None

    def test_instruction_with_string_operand(self) -> None:
        """Create an instruction with a string operand (variable name)."""
        inst = Instruction(OpCode.STORE_NAME, "x")
        assert inst.operand == "x"

    def test_instruction_is_frozen(self) -> None:
        """Instruction instances are immutable."""
        inst = Instruction(OpCode.ADD)
        with pytest.raises(AttributeError):
            inst.opcode = OpCode.SUBTRACT  # type: ignore[misc]


# -- CodeObject ---------------------------------------------------------------


class TestCodeObject:
    """Verify CodeObject constant pool and mutability."""

    def test_add_constant_returns_index(self) -> None:
        """First constant gets index 0, second gets index 1."""
        code = CodeObject(name="test")
        assert code.add_constant(42) == FIRST_INDEX
        assert code.add_constant(99) == SECOND_INDEX

    def test_add_constant_deduplicates(self) -> None:
        """Adding the same value twice returns the original index."""
        code = CodeObject(name="test")
        first = code.add_constant(42)
        second = code.add_constant(42)
        assert first == second
        assert len(code.constants) == 1

    def test_add_constant_distinguishes_int_and_bool(self) -> None:
        """``0`` (int) and ``False`` (bool) are stored as separate entries."""
        code = CodeObject(name="test")
        int_idx = code.add_constant(0)
        bool_idx = code.add_constant(False)  # noqa: FBT003
        assert int_idx != bool_idx
        assert len(code.constants) == 2  # noqa: PLR2004

    def test_add_constant_distinguishes_one_and_true(self) -> None:
        """``1`` (int) and ``True`` (bool) are stored as separate entries."""
        code = CodeObject(name="test")
        int_idx = code.add_constant(1)
        bool_idx = code.add_constant(True)  # noqa: FBT003
        assert int_idx != bool_idx
        assert len(code.constants) == 2  # noqa: PLR2004

    def test_starts_with_empty_instructions(self) -> None:
        """A fresh CodeObject has no instructions."""
        code = CodeObject(name="main")
        assert code.instructions == []

    def test_parameters_defaults_to_empty_list(self) -> None:
        """A fresh CodeObject has no parameters."""
        code = CodeObject(name="main")
        assert code.parameters == []

    def test_parameters_stores_names(self) -> None:
        """Parameters can be set to a list of parameter names."""
        code = CodeObject(name="add")
        code.parameters = ["a", "b"]
        assert code.parameters == ["a", "b"]

    def test_instructions_are_mutable(self) -> None:
        """Instructions can be appended during compilation."""
        code = CodeObject(name="main")
        code.instructions.append(Instruction(OpCode.HALT))
        assert len(code.instructions) == 1


# -- CompiledProgram ----------------------------------------------------------


class TestCompiledProgram:
    """Verify CompiledProgram is frozen and bundles main + functions."""

    def test_compiled_program_construction(self) -> None:
        """Build a CompiledProgram with a main CodeObject and functions."""
        main = CodeObject(name="<main>")
        add_fn = CodeObject(name="add")
        prog = CompiledProgram(main=main, functions={"add": add_fn})
        assert prog.main is main
        assert prog.functions["add"] is add_fn

    def test_compiled_program_is_frozen(self) -> None:
        """CompiledProgram instances are immutable."""
        main = CodeObject(name="<main>")
        prog = CompiledProgram(main=main, functions={})
        with pytest.raises(AttributeError):
            prog.main = CodeObject(name="other")  # type: ignore[misc]
