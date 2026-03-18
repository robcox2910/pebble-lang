"""Tests for the bytecode optimizer."""

from pebble.bytecode import CodeObject, CompiledProgram, Instruction, OpCode
from pebble.optimizer import optimize
from tests.conftest import (
    compile_instructions_optimized,
    compile_source_optimized,
    run_source,
)

# ---------------------------------------------------------------------------
# Named constants for expected results (PLR2004)
# ---------------------------------------------------------------------------
FOLDED_LEN = 2  # LOAD_CONST + terminator after a successful fold
ALL_ALIVE_COUNT = 6  # number of instructions when jump target keeps code alive

# Expected results for unary folding tests
EXPECTED_NEG_42 = -42
EXPECTED_NEG_PI = -3.14
EXPECTED_BIT_NOT_5 = -6

# Expected results for bitwise tests
EXPECTED_OR_F0_0F = 0xFF
EXPECTED_XOR_FF_0F = 0xF0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_program(
    instructions: list[Instruction],
    constants: list[object] | None = None,
) -> CompiledProgram:
    """Build a minimal CompiledProgram from raw instructions and constants."""
    code = CodeObject(name="<main>")
    if constants is not None:
        for c in constants:
            code.add_constant(c)  # type: ignore[arg-type]
    code.instructions = instructions
    return CompiledProgram(main=code, functions={})


def _optimized_instructions(
    instructions: list[Instruction],
    constants: list[object] | None = None,
) -> list[Instruction]:
    """Optimize and return the main code object's instructions."""
    return optimize(_make_program(instructions, constants)).main.instructions


def _optimized_constants(
    instructions: list[Instruction],
    constants: list[object] | None = None,
) -> list[int | float | str | bool | None]:
    """Optimize and return the main code object's constant pool."""
    return optimize(_make_program(instructions, constants)).main.constants


class TestOptimizeSkeleton:
    """Verify optimize() returns a valid CompiledProgram."""

    def test_returns_compiled_program(self) -> None:
        """Return a CompiledProgram from a minimal input."""
        main = CodeObject(name="<main>", instructions=[Instruction(OpCode.HALT)])
        program = CompiledProgram(main=main, functions={})
        result = optimize(program)
        assert isinstance(result, CompiledProgram)

    def test_empty_program_preserved(self) -> None:
        """Preserve an empty main code object with just HALT."""
        main = CodeObject(name="<main>", instructions=[Instruction(OpCode.HALT)])
        program = CompiledProgram(main=main, functions={})
        result = optimize(program)
        assert len(result.main.instructions) == 1
        assert result.main.instructions[0].opcode == OpCode.HALT

    def test_metadata_passed_through(self) -> None:
        """Pass through structs, enums, and other metadata unchanged."""
        main = CodeObject(name="<main>", instructions=[Instruction(OpCode.HALT)])
        program = CompiledProgram(
            main=main,
            functions={},
            structs={"Point": ["x", "y"]},
            struct_field_types={"Point": {"x": "int", "y": "int"}},
            class_methods={"Point": ["distance"]},
            enums={"Color": ["Red", "Green", "Blue"]},
            class_parents={"Dog": "Animal"},
        )
        result = optimize(program)
        assert result.structs == {"Point": ["x", "y"]}
        assert result.struct_field_types == {"Point": {"x": "int", "y": "int"}}
        assert result.class_methods == {"Point": ["distance"]}
        assert result.enums == {"Color": ["Red", "Green", "Blue"]}
        assert result.class_parents == {"Dog": "Animal"}

    def test_function_code_objects_optimized(self) -> None:
        """Optimize function code objects, not just main."""
        main = CodeObject(name="<main>", instructions=[Instruction(OpCode.HALT)])
        func = CodeObject(
            name="add",
            instructions=[Instruction(OpCode.RETURN)],
            parameters=["a", "b"],
        )
        program = CompiledProgram(main=main, functions={"add": func})
        result = optimize(program)
        assert "add" in result.functions
        assert result.functions["add"].parameters == ["a", "b"]


class TestConstantFoldingArithmetic:
    """Fold basic arithmetic on constant operands."""

    def test_add_int(self) -> None:
        """Fold 1 + 2 into LOAD_CONST 3."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.ADD),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [1, 2])
        opcodes = [i.opcode for i in result]
        assert opcodes == [OpCode.LOAD_CONST, OpCode.HALT]
        expected_sum = 3
        assert expected_sum in _optimized_constants(instrs, [1, 2])

    def test_add_float(self) -> None:
        """Fold 1.5 + 2.5 into LOAD_CONST 4.0."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.ADD),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [1.5, 2.5])
        assert len(result) == FOLDED_LEN
        expected = 4.0
        assert expected in _optimized_constants(instrs, [1.5, 2.5])

    def test_add_mixed_int_float(self) -> None:
        """Fold 1 + 2.0 into LOAD_CONST 3.0."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.ADD),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [1, 2.0])
        assert len(result) == FOLDED_LEN
        expected = 3.0
        assert expected in _optimized_constants(instrs, [1, 2.0])

    def test_add_string_concat(self) -> None:
        """Fold "hello" + " world" into LOAD_CONST "hello world"."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.ADD),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, ["hello", " world"])
        assert len(result) == FOLDED_LEN
        assert "hello world" in _optimized_constants(instrs, ["hello", " world"])

    def test_subtract_int(self) -> None:
        """Fold 5 - 3 into LOAD_CONST 2."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.SUBTRACT),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [5, 3])
        assert len(result) == FOLDED_LEN
        expected_diff = 2
        assert expected_diff in _optimized_constants(instrs, [5, 3])

    def test_multiply_int(self) -> None:
        """Fold 3 * 4 into LOAD_CONST 12."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.MULTIPLY),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [3, 4])
        assert len(result) == FOLDED_LEN
        expected_product = 12
        assert expected_product in _optimized_constants(instrs, [3, 4])

    def test_power_int(self) -> None:
        """Fold 2 ** 3 into LOAD_CONST 8."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.POWER),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [2, 3])
        assert len(result) == FOLDED_LEN
        expected_power = 8
        assert expected_power in _optimized_constants(instrs, [2, 3])

    def test_power_complex_result_not_folded(self) -> None:
        """Do NOT fold (-1) ** 0.5 — produces complex, let VM raise at runtime."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.POWER),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [-1, 0.5])
        opcodes = [i.opcode for i in result]
        assert OpCode.POWER in opcodes


class TestConstantFoldingDivision:
    """Fold division/modulo with zero-division guard."""

    def test_divide_float(self) -> None:
        """Fold 6.0 / 2.0 into LOAD_CONST 3.0."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.DIVIDE),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [6.0, 2.0])
        assert len(result) == FOLDED_LEN
        expected = 3.0
        assert expected in _optimized_constants(instrs, [6.0, 2.0])

    def test_floor_divide_int(self) -> None:
        """Fold 7 // 2 into LOAD_CONST 3."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.FLOOR_DIVIDE),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [7, 2])
        assert len(result) == FOLDED_LEN
        expected_quotient = 3
        assert expected_quotient in _optimized_constants(instrs, [7, 2])

    def test_modulo_int(self) -> None:
        """Fold 7 % 3 into LOAD_CONST 1."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.MODULO),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [7, 3])
        assert len(result) == FOLDED_LEN
        expected_remainder = 1
        assert expected_remainder in _optimized_constants(instrs, [7, 3])

    def test_divide_by_zero_not_folded(self) -> None:
        """Do NOT fold division by zero — keep for runtime error."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.DIVIDE),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [6, 0])
        opcodes = [i.opcode for i in result]
        assert opcodes == [OpCode.LOAD_CONST, OpCode.LOAD_CONST, OpCode.DIVIDE, OpCode.HALT]

    def test_floor_divide_by_zero_not_folded(self) -> None:
        """Do NOT fold floor division by zero."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.FLOOR_DIVIDE),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [7, 0])
        opcodes = [i.opcode for i in result]
        assert opcodes == [OpCode.LOAD_CONST, OpCode.LOAD_CONST, OpCode.FLOOR_DIVIDE, OpCode.HALT]

    def test_modulo_by_zero_not_folded(self) -> None:
        """Do NOT fold modulo by zero."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.MODULO),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [7, 0])
        opcodes = [i.opcode for i in result]
        assert opcodes == [OpCode.LOAD_CONST, OpCode.LOAD_CONST, OpCode.MODULO, OpCode.HALT]


class TestConstantFoldingUnary:
    """Fold unary operations on constant operands."""

    def test_negate_int(self) -> None:
        """Fold -42 into LOAD_CONST -42."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.NEGATE),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [42])
        opcodes = [i.opcode for i in result]
        assert opcodes == [OpCode.LOAD_CONST, OpCode.HALT]
        assert EXPECTED_NEG_42 in _optimized_constants(instrs, [42])

    def test_negate_float(self) -> None:
        """Fold -3.14 into LOAD_CONST -3.14."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.NEGATE),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [3.14])
        assert len(result) == FOLDED_LEN
        assert EXPECTED_NEG_PI in _optimized_constants(instrs, [3.14])

    def test_not_true(self) -> None:
        """Fold `not true` into LOAD_CONST false."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.NOT),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [True])
        assert len(result) == FOLDED_LEN
        assert False in _optimized_constants(instrs, [True])

    def test_not_false(self) -> None:
        """Fold `not false` into LOAD_CONST true."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.NOT),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [False])
        assert len(result) == FOLDED_LEN
        assert True in _optimized_constants(instrs, [False])

    def test_bit_not_int(self) -> None:
        """Fold ~5 into LOAD_CONST -6."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.BIT_NOT),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [5])
        assert len(result) == FOLDED_LEN
        assert EXPECTED_BIT_NOT_5 in _optimized_constants(instrs, [5])

    def test_negate_bool_not_folded(self) -> None:
        """Do NOT fold -true — Pebble treats bools differently from ints."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.NEGATE),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [True])
        opcodes = [i.opcode for i in result]
        assert opcodes == [OpCode.LOAD_CONST, OpCode.NEGATE, OpCode.HALT]

    def test_bit_not_bool_not_folded(self) -> None:
        """Do NOT fold ~true — Pebble treats bools differently from ints."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.BIT_NOT),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [True])
        opcodes = [i.opcode for i in result]
        assert opcodes == [OpCode.LOAD_CONST, OpCode.BIT_NOT, OpCode.HALT]


class TestConstantFoldingComparisons:
    """Fold comparison and logical operations on constants."""

    def test_equal_true(self) -> None:
        """Fold 1 == 1 into LOAD_CONST true."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.EQUAL),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [1])
        assert len(result) == FOLDED_LEN
        assert True in _optimized_constants(instrs, [1])

    def test_not_equal(self) -> None:
        """Fold 1 != 2 into LOAD_CONST true."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.NOT_EQUAL),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [1, 2])
        assert len(result) == FOLDED_LEN

    def test_less_than(self) -> None:
        """Fold 1 < 2 into LOAD_CONST true."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.LESS_THAN),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [1, 2])
        assert len(result) == FOLDED_LEN
        assert True in _optimized_constants(instrs, [1, 2])

    def test_greater_equal(self) -> None:
        """Fold 5 >= 3 into LOAD_CONST true."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.GREATER_EQUAL),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [5, 3])
        assert len(result) == FOLDED_LEN

    def test_and_false(self) -> None:
        """Fold true and false into LOAD_CONST false."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.AND),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [True, False])
        assert len(result) == FOLDED_LEN
        assert False in _optimized_constants(instrs, [True, False])

    def test_or_true(self) -> None:
        """Fold false or true into LOAD_CONST true."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.OR),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [False, True])
        assert len(result) == FOLDED_LEN
        assert True in _optimized_constants(instrs, [False, True])

    def test_and_string_operands(self) -> None:
        """Fold "hello" and "world" into "world" (logical, not bitwise)."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.AND),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, ["hello", "world"])
        assert len(result) == FOLDED_LEN
        assert "world" in _optimized_constants(instrs, ["hello", "world"])

    def test_or_string_operands(self) -> None:
        """Fold "hello" or "world" into "hello" (truthy short-circuits)."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.OR),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, ["hello", "world"])
        assert len(result) == FOLDED_LEN
        assert "hello" in _optimized_constants(instrs, ["hello", "world"])

    def test_and_int_uses_logical_not_bitwise(self) -> None:
        """Fold 3 and 5 into 5 (logical), NOT 1 (bitwise)."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.AND),
            Instruction(OpCode.HALT),
        ]
        consts = _optimized_constants(instrs, [3, 5])
        expected_logical_and = 5
        assert expected_logical_and in consts

    def test_or_int_uses_logical_not_bitwise(self) -> None:
        """Fold 3 or 5 into 3 (logical), NOT 7 (bitwise)."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.OR),
            Instruction(OpCode.HALT),
        ]
        consts = _optimized_constants(instrs, [3, 5])
        expected_logical_or = 3
        assert expected_logical_or in consts

    def test_and_null_short_circuits(self) -> None:
        """Fold null and "hello" into null (falsy short-circuits)."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.AND),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [None, "hello"])
        assert len(result) == FOLDED_LEN
        consts = _optimized_constants(instrs, [None, "hello"])
        # The folded constant should be None (falsy short-circuit)
        assert None in consts

    def test_or_empty_string_falls_through(self) -> None:
        """Fold "" or "default" into "default" (empty string is falsy)."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.OR),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, ["", "default"])
        assert len(result) == FOLDED_LEN
        assert "default" in _optimized_constants(instrs, ["", "default"])


class TestConstantFoldingBitwise:
    """Fold bitwise binary operations on constant operands."""

    def test_bit_and(self) -> None:
        """Fold 0xFF & 0x0F into LOAD_CONST 15."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.BIT_AND),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [0xFF, 0x0F])
        assert len(result) == FOLDED_LEN
        expected_and = 15
        assert expected_and in _optimized_constants(instrs, [0xFF, 0x0F])

    def test_bit_or(self) -> None:
        """Fold 0xF0 | 0x0F into LOAD_CONST 0xFF."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.BIT_OR),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [0xF0, 0x0F])
        assert len(result) == FOLDED_LEN
        assert EXPECTED_OR_F0_0F in _optimized_constants(instrs, [0xF0, 0x0F])

    def test_bit_xor(self) -> None:
        """Fold 0xFF ^ 0x0F into LOAD_CONST 0xF0."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.BIT_XOR),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [0xFF, 0x0F])
        assert len(result) == FOLDED_LEN
        assert EXPECTED_XOR_FF_0F in _optimized_constants(instrs, [0xFF, 0x0F])

    def test_left_shift(self) -> None:
        """Fold 1 << 3 into LOAD_CONST 8."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.LEFT_SHIFT),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [1, 3])
        assert len(result) == FOLDED_LEN
        expected_shift = 8
        assert expected_shift in _optimized_constants(instrs, [1, 3])

    def test_right_shift(self) -> None:
        """Fold 16 >> 2 into LOAD_CONST 4."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.RIGHT_SHIFT),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [16, 2])
        assert len(result) == FOLDED_LEN
        expected_shift = 4
        assert expected_shift in _optimized_constants(instrs, [16, 2])

    def test_negative_shift_not_folded(self) -> None:
        """Do NOT fold shift by negative amount — let VM raise at runtime."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.LEFT_SHIFT),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [1, -1])
        opcodes = [i.opcode for i in result]
        assert opcodes == [OpCode.LOAD_CONST, OpCode.LOAD_CONST, OpCode.LEFT_SHIFT, OpCode.HALT]


class TestCascadingFoldsAndJumpSafety:
    """Fold cascading expressions and handle jump targets correctly."""

    def test_cascading_add(self) -> None:
        """Fold 1 + 2 + 3 into LOAD_CONST 6 via two passes."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),  # 1
            Instruction(OpCode.LOAD_CONST, 1),  # 2
            Instruction(OpCode.ADD),
            Instruction(OpCode.LOAD_CONST, 2),  # 3
            Instruction(OpCode.ADD),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [1, 2, 3])
        opcodes = [i.opcode for i in result]
        assert opcodes == [OpCode.LOAD_CONST, OpCode.HALT]
        expected_sum = 6
        assert expected_sum in _optimized_constants(instrs, [1, 2, 3])

    def test_fold_does_not_cross_jump_target(self) -> None:
        """Do NOT fold when the second LOAD_CONST is a jump target."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),  # 0: value 10
            Instruction(OpCode.LOAD_CONST, 1),  # 1: value 20 — jump target!
            Instruction(OpCode.ADD),  # 2
            Instruction(OpCode.HALT),  # 3
            Instruction(OpCode.JUMP_IF_FALSE, 1),  # 4: jumps to index 1
        ]
        result = _optimized_instructions(instrs, [10, 20])
        opcodes = [i.opcode for i in result]
        assert OpCode.ADD in opcodes

    def test_jump_targets_adjusted_after_fold(self) -> None:
        """Adjust jump targets when folding removes instructions."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),  # 0
            Instruction(OpCode.LOAD_CONST, 1),  # 1
            Instruction(OpCode.ADD),  # 2
            Instruction(OpCode.POP),  # 3
            Instruction(OpCode.JUMP, 3),  # 4: jump to POP
        ]
        result = _optimized_instructions(instrs, [1, 2])
        opcodes = [i.opcode for i in result]
        assert opcodes == [OpCode.LOAD_CONST, OpCode.POP, OpCode.JUMP]
        jump_instr = result[2]
        assert jump_instr.operand == 1

    def test_jump_if_false_target_adjusted(self) -> None:
        """Adjust JUMP_IF_FALSE targets after folding."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),  # 0
            Instruction(OpCode.LOAD_CONST, 1),  # 1
            Instruction(OpCode.ADD),  # 2
            Instruction(OpCode.STORE_NAME, "x"),  # 3
            Instruction(OpCode.LOAD_NAME, "y"),  # 4
            Instruction(OpCode.JUMP_IF_FALSE, 3),  # 5: jump to STORE_NAME
            Instruction(OpCode.HALT),  # 6
        ]
        result = _optimized_instructions(instrs, [1, 2])
        jump_instr = next(i for i in result if i.opcode == OpCode.JUMP_IF_FALSE)
        assert jump_instr.operand == 1  # STORE_NAME moved from 3 to 1


class TestDeadCodeAfterReturn:
    """Remove unreachable code after RETURN instructions."""

    def test_dead_code_after_return_removed(self) -> None:
        """Remove instructions after RETURN that are not jump targets."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.RETURN),
            Instruction(OpCode.LOAD_CONST, 1),  # dead
            Instruction(OpCode.PRINT),  # dead
        ]
        result = _optimized_instructions(instrs, [42, 99])
        opcodes = [i.opcode for i in result]
        assert opcodes == [OpCode.LOAD_CONST, OpCode.RETURN]

    def test_code_at_jump_target_after_return_kept(self) -> None:
        """Keep code at a jump target even after RETURN."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.JUMP_IF_FALSE, 4),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.RETURN),
            Instruction(OpCode.LOAD_CONST, 0),  # jump target — NOT dead
            Instruction(OpCode.RETURN),
        ]
        result = _optimized_instructions(instrs, [42, 99])
        opcodes = [i.opcode for i in result]
        assert OpCode.RETURN in opcodes
        assert len(result) == ALL_ALIVE_COUNT

    def test_jump_targets_adjusted_after_dce(self) -> None:
        """Adjust jump targets after dead code is removed."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.RETURN),
            Instruction(OpCode.LOAD_CONST, 1),  # dead
            Instruction(OpCode.PRINT),  # dead
            Instruction(OpCode.LOAD_CONST, 0),  # dead
        ]
        result = _optimized_instructions(instrs, [42, 99])
        opcodes = [i.opcode for i in result]
        assert opcodes == [OpCode.LOAD_CONST, OpCode.RETURN]


class TestDeadCodeAfterJumpAndHalt:
    """Remove unreachable code after unconditional JUMP and HALT."""

    def test_dead_code_after_jump_removed(self) -> None:
        """Remove instructions after unconditional JUMP that are not jump targets."""
        instrs = [
            Instruction(OpCode.JUMP, 3),
            Instruction(OpCode.LOAD_CONST, 0),  # dead
            Instruction(OpCode.PRINT),  # dead
            Instruction(OpCode.HALT),  # jump target — alive
        ]
        result = _optimized_instructions(instrs, [42])
        opcodes = [i.opcode for i in result]
        assert opcodes == [OpCode.JUMP, OpCode.HALT]
        assert result[0].operand == 1

    def test_dead_code_after_halt_removed(self) -> None:
        """Remove instructions after HALT."""
        instrs = [
            Instruction(OpCode.HALT),
            Instruction(OpCode.LOAD_CONST, 0),  # dead
            Instruction(OpCode.PRINT),  # dead
        ]
        result = _optimized_instructions(instrs, [42])
        opcodes = [i.opcode for i in result]
        assert opcodes == [OpCode.HALT]

    def test_jump_if_false_does_not_eliminate_next(self) -> None:
        """JUMP_IF_FALSE does NOT make the next instruction dead."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.JUMP_IF_FALSE, 4),
            Instruction(OpCode.LOAD_CONST, 1),  # NOT dead
            Instruction(OpCode.PRINT),  # NOT dead
            Instruction(OpCode.HALT),  # jump target
        ]
        result = _optimized_instructions(instrs, [True, 42])
        opcodes = [i.opcode for i in result]
        assert opcodes == [
            OpCode.LOAD_CONST,
            OpCode.JUMP_IF_FALSE,
            OpCode.LOAD_CONST,
            OpCode.PRINT,
            OpCode.HALT,
        ]


class TestPipelineIntegration:
    """End-to-end tests using source code through the optimizer."""

    def test_print_folded_expression(self) -> None:
        """print(1+2) produces '3' with fewer instructions."""
        instrs = compile_instructions_optimized("print(1 + 2)")
        opcodes = [i.opcode for i in instrs]
        assert OpCode.ADD not in opcodes
        assert run_source("print(1 + 2)") == "3\n"

    def test_function_with_dead_code(self) -> None:
        """Function with dead code after return works correctly."""
        source = """\
fn greet() {
    return "hello"
    print("unreachable")
}
print(greet())
"""
        assert run_source(source) == "hello\n"

    def test_function_metadata_preserved(self) -> None:
        """Optimizer preserves function parameters and metadata."""
        source = """\
fn add(a, b) {
    return a + b
}
"""
        result = compile_source_optimized(source)
        assert "add" in result.functions
        assert result.functions["add"].parameters == ["a", "b"]


class TestEdgeCases:
    """Edge cases: bool arithmetic, null, generators, closures, empty functions."""

    def test_bool_plus_int_not_folded(self) -> None:
        """Do NOT fold true + 1 — Pebble treats bools differently from ints."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.ADD),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [True, 1])
        opcodes = [i.opcode for i in result]
        assert OpCode.ADD in opcodes

    def test_null_plus_int_not_folded(self) -> None:
        """Do NOT fold null + 1 — type error at runtime."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.LOAD_CONST, 1),
            Instruction(OpCode.ADD),
            Instruction(OpCode.HALT),
        ]
        result = _optimized_instructions(instrs, [None, 1])
        opcodes = [i.opcode for i in result]
        assert OpCode.ADD in opcodes

    def test_generator_code_object_optimized(self) -> None:
        """Optimize CodeObjects with is_generator flag set."""
        gen = CodeObject(
            name="gen",
            is_generator=True,
            instructions=[
                Instruction(OpCode.LOAD_CONST, 0),
                Instruction(OpCode.LOAD_CONST, 1),
                Instruction(OpCode.ADD),
                Instruction(OpCode.YIELD),
                Instruction(OpCode.RETURN),
            ],
        )
        gen.add_constant(1)
        gen.add_constant(2)
        main = CodeObject(name="<main>", instructions=[Instruction(OpCode.HALT)])
        program = CompiledProgram(main=main, functions={"gen": gen})
        result = optimize(program)
        gen_result = result.functions["gen"]
        assert gen_result.is_generator is True
        opcodes = [i.opcode for i in gen_result.instructions]
        assert OpCode.ADD not in opcodes

    def test_closure_code_object_optimized(self) -> None:
        """Optimize CodeObjects with cell_variables set."""
        closure = CodeObject(
            name="make_adder",
            cell_variables=["x"],
            instructions=[
                Instruction(OpCode.LOAD_CONST, 0),
                Instruction(OpCode.LOAD_CONST, 1),
                Instruction(OpCode.ADD),
                Instruction(OpCode.RETURN),
            ],
        )
        closure.add_constant(10)
        closure.add_constant(20)
        main = CodeObject(name="<main>", instructions=[Instruction(OpCode.HALT)])
        program = CompiledProgram(main=main, functions={"make_adder": closure})
        result = optimize(program)
        closure_result = result.functions["make_adder"]
        assert closure_result.cell_variables == ["x"]
        opcodes = [i.opcode for i in closure_result.instructions]
        assert OpCode.ADD not in opcodes

    def test_empty_function_preserved(self) -> None:
        """Optimize an empty function body (just RETURN) without crashing."""
        func = CodeObject(
            name="noop",
            instructions=[Instruction(OpCode.RETURN)],
        )
        main = CodeObject(name="<main>", instructions=[Instruction(OpCode.HALT)])
        program = CompiledProgram(main=main, functions={"noop": func})
        result = optimize(program)
        assert result.functions["noop"].instructions[0].opcode == OpCode.RETURN

    def test_duplicate_fold_results_remap_correctly(self) -> None:
        """Constant pool dedup after folding must remap LOAD_CONST operands.

        When two folds produce the same constant, the pool shrinks during rebuild.
        Instructions must point to valid indices in the new pool.
        """
        # let x = 1 + 2  (folds to 3)
        # let y = 1 + 2  (folds to 3 — same constant!)
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),  # 1
            Instruction(OpCode.LOAD_CONST, 1),  # 2
            Instruction(OpCode.ADD),
            Instruction(OpCode.STORE_NAME, "x"),
            Instruction(OpCode.LOAD_CONST, 0),  # 1
            Instruction(OpCode.LOAD_CONST, 1),  # 2
            Instruction(OpCode.ADD),
            Instruction(OpCode.STORE_NAME, "y"),
            Instruction(OpCode.HALT),
        ]
        result = optimize(_make_program(instrs, [1, 2]))
        # Both folds produce 3 — the pool should contain it once,
        # and both LOAD_CONST instructions should point to a valid index.
        expected_value = 3
        assert expected_value in result.main.constants
        pool_size = len(result.main.constants)
        for instr in result.main.instructions:
            if instr.opcode == OpCode.LOAD_CONST:
                assert isinstance(instr.operand, int)
                assert instr.operand < pool_size, (
                    f"LOAD_CONST operand {instr.operand} >= pool size {pool_size}"
                )

    def test_no_instructions(self) -> None:
        """Handle a CodeObject with no instructions gracefully."""
        main = CodeObject(name="<main>", instructions=[])
        program = CompiledProgram(main=main, functions={})
        result = optimize(program)
        assert result.main.instructions == []


class TestDeadCodeAfterThrow:
    """Remove unreachable code after THROW instructions."""

    def test_dead_code_after_throw_removed(self) -> None:
        """Remove instructions after THROW that are not jump targets."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.THROW),
            Instruction(OpCode.LOAD_CONST, 1),  # dead
            Instruction(OpCode.PRINT),  # dead
        ]
        result = _optimized_instructions(instrs, [42, 99])
        opcodes = [i.opcode for i in result]
        assert opcodes == [OpCode.LOAD_CONST, OpCode.THROW]

    def test_throw_jump_target_stays_alive(self) -> None:
        """Instructions after THROW survive if they are jump targets."""
        instrs = [
            Instruction(OpCode.LOAD_CONST, 0),
            Instruction(OpCode.THROW),
            Instruction(OpCode.LOAD_CONST, 1),  # dead
            Instruction(OpCode.PRINT),  # jump target — alive
            Instruction(OpCode.HALT),
            Instruction(OpCode.JUMP_IF_FALSE, 3),  # points at PRINT
        ]
        result = _optimized_instructions(instrs, [42, 99])
        opcodes = [i.opcode for i in result]
        assert OpCode.PRINT in opcodes


class TestUnaryFoldJumpTargetSafety:
    """Ensure unary folds respect jump target boundaries."""

    def test_unary_fold_skips_jump_target(self) -> None:
        """Do NOT fold when the LOAD_CONST is itself a jump target."""
        instrs = [
            Instruction(OpCode.JUMP_IF_FALSE, 1),  # jumps to index 1
            Instruction(OpCode.LOAD_CONST, 0),  # 1: value 42 — jump target!
            Instruction(OpCode.NEGATE),  # 2
            Instruction(OpCode.HALT),  # 3
        ]
        result = _optimized_instructions(instrs, [42])
        opcodes = [i.opcode for i in result]
        # NEGATE must still be present — fold should NOT happen
        assert OpCode.NEGATE in opcodes
