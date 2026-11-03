"""Tests for functions whose control flow can run past their last statement.

A jump may target the index one past a trailing ``return``; the function must
then give back ``null`` rather than crash the VM.
"""

import pytest

from pebble.bytecode import OpCode
from tests.conftest import compile_source_optimized, run_source

IF_ENDS = "fn f(a) {\n    if a {\n        return 1\n    }\n}\n"
WHILE_ENDS = "fn f(a) {\n    while a > 0 {\n        return 1\n    }\n}\n"
ELSE_IF_ENDS = (
    "fn f(a) {\n"
    "    if a == 1 {\n        return 1\n    } else if a == 2 {\n        return 2\n    }\n"
    "}\n"
)
METHOD_ENDS = (
    "class C {\n    fn m(self, a) {\n        if a {\n            return 1\n        }\n    }\n}\n"
)


class TestFallOffFunctionEnd:
    """Functions ending in a conditional return give back null when it is skipped."""

    def test_if_ending_function(self) -> None:
        """A false ``if`` containing ``return`` at the end returns null."""
        assert run_source(IF_ENDS + "print(f(0))") == "null\n"

    def test_if_ending_function_taken(self) -> None:
        """The taken branch still returns its value."""
        assert run_source(IF_ENDS + "print(f(1))") == "1\n"

    def test_while_ending_function(self) -> None:
        """A never-entered ``while`` containing ``return`` at the end returns null."""
        assert run_source(WHILE_ENDS + "print(f(0))") == "null\n"

    def test_else_if_chain_ending_function(self) -> None:
        """An ``if / else if`` chain with no matching branch returns null."""
        assert run_source(ELSE_IF_ENDS + "print(f(3))\nprint(f(2))") == "null\n2\n"

    def test_method_ending_in_if(self) -> None:
        """A method ending in a skipped ``if`` with ``return`` returns null."""
        assert run_source(METHOD_ENDS + "print(C().m(0))") == "null\n"

    @pytest.mark.parametrize("source", [IF_ENDS, WHILE_ENDS, ELSE_IF_ENDS])
    def test_last_instruction_is_return(self, source: str) -> None:
        """Every jump target stays inside the instruction list."""
        program = compile_source_optimized(source)
        code = program.functions["f"]
        assert code.instructions[-1].opcode is OpCode.RETURN
        for instr in code.instructions:
            if instr.opcode in (OpCode.JUMP, OpCode.JUMP_IF_FALSE):
                assert isinstance(instr.operand, int)
                assert instr.operand < len(code.instructions)

    def test_plain_return_has_no_dead_tail(self) -> None:
        """A function that always returns keeps a single trailing RETURN."""
        program = compile_source_optimized("fn f() {\n    return 1\n}\n")
        ops = [i.opcode for i in program.functions["f"].instructions]
        assert ops == [OpCode.LOAD_CONST, OpCode.RETURN]
