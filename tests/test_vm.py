"""Tests for the Pebble virtual machine.

Cover all opcodes: constants, variables, print, arithmetic, comparisons,
logical operators, control flow, function calls, and runtime errors.
"""

from io import StringIO

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.bytecode import CodeObject, CompiledProgram, Instruction, OpCode
from pebble.compiler import Compiler
from pebble.errors import PebbleRuntimeError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.vm import Frame, VirtualMachine

# -- Named constants ----------------------------------------------------------

FIRST_INDEX = 0
SECOND_INDEX = 1


# -- Helpers ------------------------------------------------------------------


def _run(program: CompiledProgram, *, output: StringIO | None = None) -> str:
    """Run *program* on a fresh VM and return captured output."""
    buf = output or StringIO()
    vm = VirtualMachine(output=buf)
    vm.run(program)
    return buf.getvalue()


def _compile(source: str) -> CompiledProgram:
    """Lex, parse, analyze, and compile *source*."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzed = SemanticAnalyzer().analyze(program)
    return Compiler().compile(analyzed)


def _run_source(source: str) -> str:
    """Compile and run *source*, returning captured output."""
    return _run(_compile(source))


def _program(
    instructions: list[Instruction],
    constants: list[int | str | bool] | None = None,
) -> CompiledProgram:
    """Build a minimal CompiledProgram from raw instructions."""
    main = CodeObject(name="<main>")
    main.instructions = instructions
    main.constants = constants or []
    return CompiledProgram(main=main, functions={})


# -- Cycle 1: Frame + HALT ---------------------------------------------------


class TestFrame:
    """Verify Frame dataclass construction and defaults."""

    def test_frame_defaults(self) -> None:
        """A fresh Frame starts at ip=0 with empty variables."""
        code = CodeObject(name="test")
        frame = Frame(code=code)
        assert frame.ip == 0
        assert frame.variables == {}

    def test_frame_stores_code(self) -> None:
        """Frame holds a reference to its CodeObject."""
        code = CodeObject(name="fn")
        frame = Frame(code=code)
        assert frame.code is code


class TestVMHalt:
    """Verify the VM stops on HALT."""

    def test_empty_program_halts(self) -> None:
        """A program with only HALT runs without error."""
        prog = _program([Instruction(OpCode.HALT)])
        result = _run(prog)
        assert result == ""


# -- Cycle 2: Constants + Variables + Print -----------------------------------


class TestVMPrint:
    """Verify LOAD_CONST, STORE_NAME, LOAD_NAME, and PRINT."""

    def test_print_integer(self) -> None:
        """``print(42)`` outputs ``42`` followed by a newline."""
        assert _run_source("print(42)") == "42\n"

    def test_print_string(self) -> None:
        """``print("hello")`` outputs the string without quotes."""
        assert _run_source('print("hello")') == "hello\n"

    def test_print_true(self) -> None:
        """``print(true)`` outputs ``true`` (not Python's ``True``)."""
        assert _run_source("print(true)") == "true\n"

    def test_print_false(self) -> None:
        """``print(false)`` outputs ``false`` (not Python's ``False``)."""
        assert _run_source("print(false)") == "false\n"

    def test_print_variable(self) -> None:
        """``let x = 42`` then ``print(x)`` outputs ``42``."""
        assert _run_source("let x = 42\nprint(x)") == "42\n"

    def test_reassignment(self) -> None:
        """After reassignment, print shows the updated value."""
        assert _run_source("let x = 1\nx = 2\nprint(x)") == "2\n"


# -- Cycle 3: Arithmetic + Unary ---------------------------------------------


class TestVMArithmetic:
    """Verify arithmetic opcodes produce correct results."""

    def test_add(self) -> None:
        """``print(1 + 2)`` outputs ``3``."""
        assert _run_source("print(1 + 2)") == "3\n"

    def test_subtract(self) -> None:
        """``print(5 - 3)`` outputs ``2``."""
        assert _run_source("print(5 - 3)") == "2\n"

    def test_multiply(self) -> None:
        """``print(4 * 3)`` outputs ``12``."""
        assert _run_source("print(4 * 3)") == "12\n"

    def test_divide_floor(self) -> None:
        """``print(6 / 4)`` outputs ``1`` (floor division)."""
        assert _run_source("print(6 / 4)") == "1\n"

    def test_divide_exact(self) -> None:
        """``print(10 / 2)`` outputs ``5``."""
        assert _run_source("print(10 / 2)") == "5\n"

    def test_modulo(self) -> None:
        """``print(7 % 3)`` outputs ``1``."""
        assert _run_source("print(7 % 3)") == "1\n"

    def test_negate(self) -> None:
        """``print(-42)`` outputs ``-42``."""
        assert _run_source("print(-42)") == "-42\n"

    def test_nested_arithmetic(self) -> None:
        """``print(1 + 2 * 3)`` outputs ``7``."""
        assert _run_source("print(1 + 2 * 3)") == "7\n"

    def test_string_concatenation(self) -> None:
        """``print("hello" + " world")`` outputs ``hello world``."""
        assert _run_source('print("hello" + " world")') == "hello world\n"


# -- Cycle 4: Comparisons + Logical + NOT ------------------------------------


class TestVMComparisons:
    """Verify comparison opcodes produce correct boolean results."""

    def test_equal_true(self) -> None:
        """``print(1 == 1)`` outputs ``true``."""
        assert _run_source("print(1 == 1)") == "true\n"

    def test_equal_false(self) -> None:
        """``print(1 == 2)`` outputs ``false``."""
        assert _run_source("print(1 == 2)") == "false\n"

    def test_not_equal_true(self) -> None:
        """``print(1 != 2)`` outputs ``true``."""
        assert _run_source("print(1 != 2)") == "true\n"

    def test_not_equal_false(self) -> None:
        """``print(1 != 1)`` outputs ``false``."""
        assert _run_source("print(1 != 1)") == "false\n"

    def test_less_than_true(self) -> None:
        """``print(1 < 2)`` outputs ``true``."""
        assert _run_source("print(1 < 2)") == "true\n"

    def test_less_than_false(self) -> None:
        """``print(2 < 1)`` outputs ``false``."""
        assert _run_source("print(2 < 1)") == "false\n"

    def test_less_equal_true(self) -> None:
        """``print(1 <= 1)`` outputs ``true``."""
        assert _run_source("print(1 <= 1)") == "true\n"

    def test_less_equal_false(self) -> None:
        """``print(2 <= 1)`` outputs ``false``."""
        assert _run_source("print(2 <= 1)") == "false\n"

    def test_greater_than_true(self) -> None:
        """``print(2 > 1)`` outputs ``true``."""
        assert _run_source("print(2 > 1)") == "true\n"

    def test_greater_than_false(self) -> None:
        """``print(1 > 2)`` outputs ``false``."""
        assert _run_source("print(1 > 2)") == "false\n"

    def test_greater_equal_true(self) -> None:
        """``print(1 >= 1)`` outputs ``true``."""
        assert _run_source("print(1 >= 1)") == "true\n"

    def test_greater_equal_false(self) -> None:
        """``print(1 >= 2)`` outputs ``false``."""
        assert _run_source("print(1 >= 2)") == "false\n"


class TestVMLogical:
    """Verify logical opcodes AND, OR, NOT."""

    def test_and_true(self) -> None:
        """``print(true and true)`` outputs ``true``."""
        assert _run_source("print(true and true)") == "true\n"

    def test_and_false(self) -> None:
        """``print(true and false)`` outputs ``false``."""
        assert _run_source("print(true and false)") == "false\n"

    def test_or_true(self) -> None:
        """``print(false or true)`` outputs ``true``."""
        assert _run_source("print(false or true)") == "true\n"

    def test_or_false(self) -> None:
        """``print(false or false)`` outputs ``false``."""
        assert _run_source("print(false or false)") == "false\n"

    def test_not_true(self) -> None:
        """``print(not true)`` outputs ``false``."""
        assert _run_source("print(not true)") == "false\n"

    def test_not_false(self) -> None:
        """``print(not false)`` outputs ``true``."""
        assert _run_source("print(not false)") == "true\n"


# -- Cycle 5: Control Flow ---------------------------------------------------


class TestVMControlFlow:
    """Verify JUMP, JUMP_IF_FALSE, and POP opcodes."""

    def test_if_true_branch(self) -> None:
        """``if true`` executes the then-branch."""
        assert _run_source("if true { print(1) } else { print(2) }") == "1\n"

    def test_if_false_branch(self) -> None:
        """``if false`` executes the else-branch."""
        assert _run_source("if false { print(1) } else { print(2) }") == "2\n"

    def test_while_loop(self) -> None:
        """While loop counts to 5."""
        source = """\
let x = 0
while x < 5 {
    x = x + 1
}
print(x)"""
        assert _run_source(source) == "5\n"

    def test_for_loop(self) -> None:
        """For loop prints 0, 1, 2."""
        source = """\
for i in range(3) {
    print(i)
}"""
        assert _run_source(source) == "0\n1\n2\n"

    def test_nested_if_in_while(self) -> None:
        """Nested if inside a while loop."""
        source = """\
let x = 0
while x < 5 {
    if x > 2 {
        print(x)
    }
    x = x + 1
}"""
        assert _run_source(source) == "3\n4\n"

    def test_if_without_else(self) -> None:
        """If without else — false condition produces no output."""
        assert _run_source("if false { print(1) }") == ""

    def test_while_false(self) -> None:
        """While false never executes the body."""
        assert _run_source("while false { print(1) }") == ""


# -- Cycle 6: Functions ------------------------------------------------------


class TestVMFunctions:
    """Verify CALL and RETURN opcodes."""

    def test_function_with_return(self) -> None:
        """``fn add(a, b) { return a + b }`` returns the sum."""
        source = """\
fn add(a, b) { return a + b }
print(add(1, 2))"""
        assert _run_source(source) == "3\n"

    def test_function_no_return(self) -> None:
        """A function with no explicit return returns 0."""
        source = """\
fn greet() { print(42) }
print(greet())"""
        assert _run_source(source) == "42\n0\n"

    def test_function_calling_function(self) -> None:
        """One function calls another."""
        source = """\
fn add(a, b) { return a + b }
fn add3(a, b, c) { return add(add(a, b), c) }
print(add3(1, 2, 3))"""
        assert _run_source(source) == "6\n"

    def test_bare_function_call(self) -> None:
        """A bare function call (expression statement) discards its return value."""
        source = """\
fn say_hello() { print(1) }
say_hello()"""
        assert _run_source(source) == "1\n"

    def test_function_with_for_loop(self) -> None:
        """A function body can contain a for loop."""
        source = """\
fn sum_to(n) {
    let total = 0
    for i in range(n) {
        total = total + i
    }
    return total
}
print(sum_to(5))"""
        assert _run_source(source) == "10\n"

    def test_function_with_if(self) -> None:
        """A function body can contain if/else."""
        source = """\
fn max(a, b) {
    if a > b {
        return a
    } else {
        return b
    }
}
print(max(3, 7))"""
        assert _run_source(source) == "7\n"

    def test_function_with_while(self) -> None:
        """A function body can contain a while loop."""
        source = """\
fn count_down(n) {
    while n > 0 {
        print(n)
        n = n - 1
    }
}
count_down(3)"""
        assert _run_source(source) == "3\n2\n1\n"


# -- Cycle 7: Runtime Errors -------------------------------------------------


class TestVMRuntimeErrors:
    """Verify PebbleRuntimeError for invalid operations."""

    def test_division_by_zero(self) -> None:
        """Division by zero raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="Division by zero"):
            _run_source("print(1 / 0)")

    def test_modulo_by_zero(self) -> None:
        """Modulo by zero raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="Division by zero"):
            _run_source("print(1 % 0)")

    def test_string_plus_integer(self) -> None:
        """Adding a string and integer raises PebbleRuntimeError."""
        prog = _program(
            [
                Instruction(OpCode.LOAD_CONST, FIRST_INDEX),
                Instruction(OpCode.LOAD_CONST, SECOND_INDEX),
                Instruction(OpCode.ADD),
                Instruction(OpCode.HALT),
            ],
            constants=["hello", 42],
        )
        with pytest.raises(PebbleRuntimeError, match="Unsupported operand types for"):
            _run(prog)

    def test_negate_string(self) -> None:
        """Negating a string raises PebbleRuntimeError."""
        prog = _program(
            [
                Instruction(OpCode.LOAD_CONST, FIRST_INDEX),
                Instruction(OpCode.NEGATE),
                Instruction(OpCode.HALT),
            ],
            constants=["hello"],
        )
        with pytest.raises(PebbleRuntimeError, match="Unsupported operand type for negation"):
            _run(prog)

    def test_subtract_string_and_int(self) -> None:
        """Subtracting a string and integer raises PebbleRuntimeError."""
        prog = _program(
            [
                Instruction(OpCode.LOAD_CONST, FIRST_INDEX),
                Instruction(OpCode.LOAD_CONST, SECOND_INDEX),
                Instruction(OpCode.SUBTRACT),
                Instruction(OpCode.HALT),
            ],
            constants=["hello", 42],
        )
        with pytest.raises(PebbleRuntimeError, match="Unsupported operand types for"):
            _run(prog)

    def test_compare_string_and_int(self) -> None:
        """Comparing a string and integer raises PebbleRuntimeError."""
        prog = _program(
            [
                Instruction(OpCode.LOAD_CONST, FIRST_INDEX),
                Instruction(OpCode.LOAD_CONST, SECOND_INDEX),
                Instruction(OpCode.LESS_THAN),
                Instruction(OpCode.HALT),
            ],
            constants=["hello", 42],
        )
        with pytest.raises(PebbleRuntimeError, match="Unsupported operand types for"):
            _run(prog)
