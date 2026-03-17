"""Tests for better error reporting (Phase 14).

Verify that runtime errors carry correct source locations from the AST
through the compiler and VM.
"""

import pytest

from pebble.bytecode import Instruction, OpCode
from pebble.errors import PebbleRuntimeError
from pebble.tokens import SourceLocation
from tests.conftest import (
    compile_source,
    run_source,
)

# -- Named constants ----------------------------------------------------------

LINE_1 = 1
LINE_2 = 2
LINE_3 = 3
COLUMN_5 = 5


# -- Cycle 1: Instruction location field --------------------------------------


class TestInstructionLocation:
    """Verify Instruction location field."""

    def test_default_location_is_none(self) -> None:
        """Location defaults to None when not provided."""
        inst = Instruction(OpCode.ADD)
        assert inst.location is None

    def test_location_can_be_set(self) -> None:
        """Location can be set via keyword argument."""
        loc = SourceLocation(line=LINE_1, column=COLUMN_5)
        inst = Instruction(OpCode.ADD, location=loc)
        assert inst.location == loc

    def test_location_is_frozen(self) -> None:
        """Location is immutable like other Instruction fields."""
        inst = Instruction(OpCode.ADD, location=SourceLocation(line=LINE_1, column=LINE_1))
        with pytest.raises(AttributeError):
            inst.location = None  # type: ignore[misc]


# -- Cycle 2: Compiler threading ----------------------------------------------


class TestCompilerLocations:
    """Verify compiler emits instructions with source locations."""

    def test_binary_op_has_location(self) -> None:
        """Binary operator instructions carry source location."""
        compiled = compile_source("let x = 1 + 2")
        add_insts = [i for i in compiled.main.instructions if i.opcode is OpCode.ADD]
        assert len(add_insts) == LINE_1
        assert add_insts[0].location is not None
        assert add_insts[0].location.line == LINE_1

    def test_call_has_location(self) -> None:
        """CALL instructions carry source location."""
        compiled = compile_source("print(len([1, 2]))")
        call_insts = [i for i in compiled.main.instructions if i.opcode is OpCode.CALL]
        assert len(call_insts) == LINE_1
        assert call_insts[0].location is not None

    def test_index_get_has_location(self) -> None:
        """INDEX_GET instructions carry source location."""
        compiled = compile_source("let xs = [1]\nprint(xs[0])")
        idx_insts = [i for i in compiled.main.instructions if i.opcode is OpCode.INDEX_GET]
        assert len(idx_insts) == LINE_1
        assert idx_insts[0].location is not None
        assert idx_insts[0].location.line == LINE_2

    def test_literal_has_location(self) -> None:
        """LOAD_CONST from a literal carries source location."""
        compiled = compile_source("let x = 42")
        load_insts = [i for i in compiled.main.instructions if i.opcode is OpCode.LOAD_CONST]
        assert load_insts[0].location is not None
        assert load_insts[0].location.line == LINE_1

    def test_negate_has_location(self) -> None:
        """NEGATE instruction carries source location."""
        compiled = compile_source("let x = -5")
        neg_insts = [i for i in compiled.main.instructions if i.opcode is OpCode.NEGATE]
        assert len(neg_insts) == LINE_1
        assert neg_insts[0].location is not None


# -- Cycle 3: VM error locations ----------------------------------------------


class TestRuntimeErrorLocations:
    """Verify runtime errors carry correct source locations."""

    def test_division_by_zero_line(self) -> None:
        """Division by zero reports correct line number."""
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source("let x = 10 / 0")
        assert exc_info.value.line == LINE_1

    def test_type_error_line(self) -> None:
        """Type error in addition reports correct line number."""
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source('let x = 1 + "hello"')
        assert exc_info.value.line == LINE_1

    def test_multiline_error_correct_line(self) -> None:
        """Error on line 3 reports line 3, not line 1."""
        source = "let a = 1\nlet b = 2\nlet c = a / 0"
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source(source)
        assert exc_info.value.line == LINE_3

    def test_index_out_of_bounds_line(self) -> None:
        """Out-of-bounds index reports correct line number."""
        source = "let xs = [1]\nprint(xs[5])"
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source(source)
        assert exc_info.value.line == LINE_2

    def test_builtin_error_line(self) -> None:
        """Builtin error (len on int) reports correct line number."""
        source = "let x = 42\nprint(len(x))"
        with pytest.raises(PebbleRuntimeError, match="len") as exc_info:
            run_source(source)
        assert exc_info.value.line == LINE_2

    def test_negate_type_error_line(self) -> None:
        """Negation type error reports correct line number."""
        with pytest.raises(PebbleRuntimeError, match="negation") as exc_info:
            run_source('let x = -"hello"')
        assert exc_info.value.line == LINE_1

    def test_error_column_is_nonzero(self) -> None:
        """Error column is set (not the default 0)."""
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source("let x = 10 / 0")
        assert exc_info.value.column > 0

    def test_comparison_type_error_line(self) -> None:
        """Comparison type error reports correct line."""
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source('let x = 1 < "two"')
        assert exc_info.value.line == LINE_1

    def test_index_set_out_of_bounds_line(self) -> None:
        """Out-of-bounds index assignment reports correct line."""
        source = "let xs = [1]\nxs[5] = 42"
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source(source)
        assert exc_info.value.line == LINE_2


# -- Cycle 4: CLI formatted errors -------------------------------------------


class TestCLIFormatting:
    """Verify CLI uses format_error for runtime errors."""

    def test_normal_execution_still_works(self) -> None:
        """Programs without errors run normally."""
        assert run_source("print(42)") == "42\n"

    def test_error_message_includes_line(self) -> None:
        """Runtime error str() includes the correct line number."""
        with pytest.raises(PebbleRuntimeError) as exc_info:
            run_source("let x = 1 / 0")
        assert "line 1" in str(exc_info.value)
