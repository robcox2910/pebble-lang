"""Tests for the Pebble bytecode compiler.

Cover every compilation pattern: literals, variables, print, arithmetic,
comparisons, logical operators, unary operators, if/else, while loops,
for loops, function definitions, function calls, return statements,
expression statements, and multi-feature integration programs.
"""

from pebble.analyzer import SemanticAnalyzer
from pebble.bytecode import CompiledProgram, Instruction, OpCode
from pebble.compiler import Compiler
from pebble.lexer import Lexer
from pebble.parser import Parser

# -- Named constants ----------------------------------------------------------

ZERO = 0
ONE = 1
TWO = 2
THREE = 3
FOUR = 4
FIVE = 5
SIX = 6
SEVEN = 7
EIGHT = 8
NINE = 9
TEN = 10
ELEVEN = 11
TWELVE = 12
THIRTEEN = 13
FOURTEEN = 14
FIFTEEN = 15


# -- Helpers ------------------------------------------------------------------


def _compile(source: str) -> CompiledProgram:
    """Lex, parse, analyze, and compile *source*."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzed = SemanticAnalyzer().analyze(program)
    return Compiler().compile(analyzed)


def _strip_locations(instructions: list[Instruction]) -> list[Instruction]:
    """Strip location fields from instructions for comparison."""
    return [Instruction(i.opcode, i.operand) for i in instructions]


def _instructions(source: str) -> list[Instruction]:
    """Return the main instruction list for *source*, locations stripped."""
    return _strip_locations(_compile(source).main.instructions)


def _constants(source: str) -> list[int | str | bool]:
    """Return the main constant pool for *source*."""
    return _compile(source).main.constants


# -- Cycle 1: Literals -------------------------------------------------------


class TestCompileLiterals:
    """Verify compilation of literal values and empty programs."""

    def test_integer_literal(self) -> None:
        """``let x = 42`` loads the constant and stores the name."""
        ins = _instructions("let x = 42")
        assert ins == [
            Instruction(OpCode.LOAD_CONST, ZERO),
            Instruction(OpCode.STORE_NAME, "x"),
            Instruction(OpCode.HALT),
        ]
        assert _constants("let x = 42") == [42]

    def test_string_literal(self) -> None:
        """``let s = "hello"`` stores the string in the constant pool."""
        assert _constants('let s = "hello"') == ["hello"]

    def test_boolean_true(self) -> None:
        """``let b = true`` stores True in the constant pool."""
        assert _constants("let b = true") == [True]

    def test_boolean_false(self) -> None:
        """``let b = false`` stores False in the constant pool."""
        assert _constants("let b = false") == [False]

    def test_empty_program(self) -> None:
        """An empty program produces only HALT."""
        ins = _instructions("")
        assert ins == [Instruction(OpCode.HALT)]


# -- Cycle 2: Variables + Print -----------------------------------------------


class TestCompileVariables:
    """Verify variable load, store, reassignment, and print."""

    def test_let_and_print(self) -> None:
        """``let x = 42`` then ``print(x)`` loads and prints."""
        ins = _instructions("let x = 42\nprint(x)")
        assert ins == [
            Instruction(OpCode.LOAD_CONST, ZERO),
            Instruction(OpCode.STORE_NAME, "x"),
            Instruction(OpCode.LOAD_NAME, "x"),
            Instruction(OpCode.PRINT),
            Instruction(OpCode.HALT),
        ]

    def test_reassignment(self) -> None:
        """Reassignment uses STORE_NAME just like let."""
        ins = _instructions("let x = 1\nx = 2\nprint(x)")
        assert ins == [
            Instruction(OpCode.LOAD_CONST, ZERO),
            Instruction(OpCode.STORE_NAME, "x"),
            Instruction(OpCode.LOAD_CONST, ONE),
            Instruction(OpCode.STORE_NAME, "x"),
            Instruction(OpCode.LOAD_NAME, "x"),
            Instruction(OpCode.PRINT),
            Instruction(OpCode.HALT),
        ]
        assert _constants("let x = 1\nx = 2\nprint(x)") == [1, 2]

    def test_print_literal(self) -> None:
        """``print("hello")`` loads the constant and prints."""
        ins = _instructions('print("hello")')
        assert ins == [
            Instruction(OpCode.LOAD_CONST, ZERO),
            Instruction(OpCode.PRINT),
            Instruction(OpCode.HALT),
        ]

    def test_every_program_ends_with_halt(self) -> None:
        """The last instruction is always HALT."""
        ins = _instructions("let a = 1")
        assert ins[-1] == Instruction(OpCode.HALT)


# -- Cycle 3: Binary + Unary Expressions -------------------------------------


class TestCompileBinaryOps:
    """Verify compilation of all binary operators."""

    def test_add(self) -> None:
        """``1 + 2`` → LOAD_CONST 0, LOAD_CONST 1, ADD."""
        ins = _instructions("let x = 1 + 2")
        assert ins[:THREE] == [
            Instruction(OpCode.LOAD_CONST, ZERO),
            Instruction(OpCode.LOAD_CONST, ONE),
            Instruction(OpCode.ADD),
        ]

    def test_subtract(self) -> None:
        """``3 - 1`` → SUBTRACT."""
        ins = _instructions("let x = 3 - 1")
        assert ins[TWO] == Instruction(OpCode.SUBTRACT)

    def test_multiply(self) -> None:
        """``2 * 3`` → MULTIPLY."""
        ins = _instructions("let x = 2 * 3")
        assert ins[TWO] == Instruction(OpCode.MULTIPLY)

    def test_divide(self) -> None:
        """``6 / 2`` → DIVIDE."""
        ins = _instructions("let x = 6 / 2")
        assert ins[TWO] == Instruction(OpCode.DIVIDE)

    def test_modulo(self) -> None:
        """``7 % 3`` → MODULO."""
        ins = _instructions("let x = 7 % 3")
        assert ins[TWO] == Instruction(OpCode.MODULO)

    def test_equal(self) -> None:
        """``1 == 1`` → EQUAL."""
        ins = _instructions("let x = 1 == 1")
        assert ins[TWO] == Instruction(OpCode.EQUAL)

    def test_not_equal(self) -> None:
        """``1 != 2`` → NOT_EQUAL."""
        ins = _instructions("let x = 1 != 2")
        assert ins[TWO] == Instruction(OpCode.NOT_EQUAL)

    def test_less_than(self) -> None:
        """``1 < 2`` → LESS_THAN."""
        ins = _instructions("let x = 1 < 2")
        assert ins[TWO] == Instruction(OpCode.LESS_THAN)

    def test_less_equal(self) -> None:
        """``1 <= 2`` → LESS_EQUAL."""
        ins = _instructions("let x = 1 <= 2")
        assert ins[TWO] == Instruction(OpCode.LESS_EQUAL)

    def test_greater_than(self) -> None:
        """``2 > 1`` → GREATER_THAN."""
        ins = _instructions("let x = 2 > 1")
        assert ins[TWO] == Instruction(OpCode.GREATER_THAN)

    def test_greater_equal(self) -> None:
        """``2 >= 1`` → GREATER_EQUAL."""
        ins = _instructions("let x = 2 >= 1")
        assert ins[TWO] == Instruction(OpCode.GREATER_EQUAL)

    def test_and(self) -> None:
        """``true and false`` → AND."""
        ins = _instructions("let x = true and false")
        assert ins[TWO] == Instruction(OpCode.AND)

    def test_or(self) -> None:
        """``true or false`` → OR."""
        ins = _instructions("let x = true or false")
        assert ins[TWO] == Instruction(OpCode.OR)

    def test_nested_expression_ordering(self) -> None:
        """``1 + 2 * 3`` compiles with correct operand order from the AST."""
        ins = _instructions("let x = 1 + 2 * 3")
        # AST: BinaryOp(+, 1, BinaryOp(*, 2, 3))
        # → LOAD 1, LOAD 2, LOAD 3, MULTIPLY, ADD
        assert ins == [
            Instruction(OpCode.LOAD_CONST, ZERO),  # 1
            Instruction(OpCode.LOAD_CONST, ONE),  # 2
            Instruction(OpCode.LOAD_CONST, TWO),  # 3
            Instruction(OpCode.MULTIPLY),
            Instruction(OpCode.ADD),
            Instruction(OpCode.STORE_NAME, "x"),
            Instruction(OpCode.HALT),
        ]

    def test_constant_deduplication(self) -> None:
        """``1 + 1`` reuses the same constant pool entry."""
        consts = _constants("let x = 1 + 1")
        assert consts == [1]
        ins = _instructions("let x = 1 + 1")
        assert ins[ZERO] == Instruction(OpCode.LOAD_CONST, ZERO)
        assert ins[ONE] == Instruction(OpCode.LOAD_CONST, ZERO)


class TestCompileUnaryOps:
    """Verify compilation of unary operators."""

    def test_negate(self) -> None:
        """``-42`` → LOAD_CONST 0, NEGATE."""
        ins = _instructions("let x = -42")
        assert ins[:TWO] == [
            Instruction(OpCode.LOAD_CONST, ZERO),
            Instruction(OpCode.NEGATE),
        ]

    def test_not(self) -> None:
        """``not true`` → LOAD_CONST 0, NOT."""
        ins = _instructions("let x = not true")
        assert ins[:TWO] == [
            Instruction(OpCode.LOAD_CONST, ZERO),
            Instruction(OpCode.NOT),
        ]


# -- Cycle 4: If/Else --------------------------------------------------------


class TestCompileIfStatement:
    """Verify if/else compilation with jump backpatching."""

    def test_if_without_else(self) -> None:
        """``if true { print(1) }`` jumps past the body when false."""
        ins = _instructions("if true { print(1) }")
        assert ins == [
            Instruction(OpCode.LOAD_CONST, ZERO),  # 0: true
            Instruction(OpCode.JUMP_IF_FALSE, FOUR),  # 1: skip body
            Instruction(OpCode.LOAD_CONST, ONE),  # 2: 1
            Instruction(OpCode.PRINT),  # 3
            Instruction(OpCode.HALT),  # 4
        ]

    def test_if_else(self) -> None:
        """``if true { print(1) } else { print(2) }`` has both branches."""
        ins = _instructions("if true { print(1) } else { print(2) }")
        assert ins == [
            Instruction(OpCode.LOAD_CONST, ZERO),  # 0: true
            Instruction(OpCode.JUMP_IF_FALSE, FIVE),  # 1: skip to else
            Instruction(OpCode.LOAD_CONST, ONE),  # 2: 1
            Instruction(OpCode.PRINT),  # 3
            Instruction(OpCode.JUMP, SEVEN),  # 4: skip else
            Instruction(OpCode.LOAD_CONST, TWO),  # 5: 2
            Instruction(OpCode.PRINT),  # 6
            Instruction(OpCode.HALT),  # 7
        ]

    def test_nested_if(self) -> None:
        """Nested if statements produce correct jump targets."""
        source = "if true { if false { print(1) } }"
        ins = _instructions(source)
        # Outer if: condition at 0, JUMP_IF_FALSE past inner
        assert ins[ZERO] == Instruction(OpCode.LOAD_CONST, ZERO)  # true
        assert ins[ONE].opcode is OpCode.JUMP_IF_FALSE
        # Inner if: condition at 2, JUMP_IF_FALSE past inner body
        assert ins[TWO] == Instruction(OpCode.LOAD_CONST, ONE)  # false
        assert ins[THREE].opcode is OpCode.JUMP_IF_FALSE
        assert ins[-1] == Instruction(OpCode.HALT)

    def test_if_with_condition_expression(self) -> None:
        """``if x == 1`` compiles the condition as an expression."""
        ins = _instructions("let x = 1\nif x == 1 { print(x) }")
        # After let x = 1 (instructions 0-1), condition starts at 2
        assert ins[TWO] == Instruction(OpCode.LOAD_NAME, "x")
        assert ins[THREE] == Instruction(OpCode.LOAD_CONST, ZERO)  # 1 (dedup with let)
        assert ins[FOUR] == Instruction(OpCode.EQUAL)


# -- Cycle 5: While Loops ----------------------------------------------------


class TestCompileWhileLoop:
    """Verify while loop compilation with forward and backward jumps."""

    def test_while_loop(self) -> None:
        """``while x < 5`` produces a loop with backward JUMP."""
        source = "let x = 0\nwhile x < 5 { x = x + 1 }"
        ins = _instructions(source)
        assert ins == [
            Instruction(OpCode.LOAD_CONST, ZERO),  # 0: 0
            Instruction(OpCode.STORE_NAME, "x"),  # 1
            Instruction(OpCode.LOAD_NAME, "x"),  # 2: loop_start
            Instruction(OpCode.LOAD_CONST, ONE),  # 3: 5
            Instruction(OpCode.LESS_THAN),  # 4
            Instruction(OpCode.JUMP_IF_FALSE, ELEVEN),  # 5: exit
            Instruction(OpCode.LOAD_NAME, "x"),  # 6
            Instruction(OpCode.LOAD_CONST, TWO),  # 7: 1
            Instruction(OpCode.ADD),  # 8
            Instruction(OpCode.STORE_NAME, "x"),  # 9
            Instruction(OpCode.JUMP, TWO),  # 10: back to start
            Instruction(OpCode.HALT),  # 11
        ]
        assert _constants(source) == [0, 5, 1]

    def test_while_false(self) -> None:
        """``while false { }`` still emits the loop structure."""
        ins = _instructions("while false { print(1) }")
        # condition → JUMP_IF_FALSE past body + JUMP
        assert ins[ZERO] == Instruction(OpCode.LOAD_CONST, ZERO)
        assert ins[ONE].opcode is OpCode.JUMP_IF_FALSE
        # Body's last JUMP loops back to 0
        jump_back = [i for i in ins if i.opcode is OpCode.JUMP]
        assert len(jump_back) == ONE
        assert jump_back[ZERO].operand == ZERO


# -- Cycle 6: For Loops ------------------------------------------------------


class TestCompileForLoop:
    """Verify for-loop desugaring to a counted while loop."""

    def test_for_range(self) -> None:
        """``for i in range(3) { print(i) }`` desugars correctly."""
        source = "for i in range(3) { print(i) }"
        ins = _instructions(source)
        assert ins == [
            Instruction(OpCode.LOAD_CONST, ZERO),  # 0: 3
            Instruction(OpCode.STORE_NAME, "$for_limit_0"),  # 1
            Instruction(OpCode.LOAD_CONST, ONE),  # 2: 0
            Instruction(OpCode.STORE_NAME, "i"),  # 3
            Instruction(OpCode.LOAD_NAME, "i"),  # 4: loop_start
            Instruction(OpCode.LOAD_NAME, "$for_limit_0"),  # 5
            Instruction(OpCode.LESS_THAN),  # 6
            Instruction(OpCode.JUMP_IF_FALSE, FIFTEEN),  # 7: exit
            Instruction(OpCode.LOAD_NAME, "i"),  # 8: body
            Instruction(OpCode.PRINT),  # 9
            Instruction(OpCode.LOAD_NAME, "i"),  # 10: increment
            Instruction(OpCode.LOAD_CONST, TWO),  # 11: 1
            Instruction(OpCode.ADD),  # 12
            Instruction(OpCode.STORE_NAME, "i"),  # 13
            Instruction(OpCode.JUMP, FOUR),  # 14: back to start
            Instruction(OpCode.HALT),  # 15
        ]
        assert _constants(source) == [3, 0, 1]

    def test_two_for_loops_use_unique_limits(self) -> None:
        """Two for loops get ``$for_limit_0`` and ``$for_limit_1``."""
        source = "for i in range(2) { print(i) }\nfor j in range(3) { print(j) }"
        result = _compile(source)
        names = [
            i.operand
            for i in result.main.instructions
            if i.opcode is OpCode.STORE_NAME
            and isinstance(i.operand, str)
            and i.operand.startswith("$")
        ]
        assert "$for_limit_0" in names
        assert "$for_limit_1" in names

    def test_for_range_with_variable(self) -> None:
        """``for i in range(n)`` compiles the range argument as an expression."""
        source = "let n = 5\nfor i in range(n) { print(i) }"
        ins = _instructions(source)
        # After `let n = 5` (LOAD_CONST, STORE_NAME), the range arg is LOAD_NAME "n"
        assert ins[TWO] == Instruction(OpCode.LOAD_NAME, "n")
        assert ins[THREE] == Instruction(OpCode.STORE_NAME, "$for_limit_0")


# -- Cycle 7: Functions -------------------------------------------------------


class TestCompileFunctionDef:
    """Verify function definitions create separate CodeObjects."""

    def test_function_creates_code_object(self) -> None:
        """``fn add(a, b) { return a + b }`` creates a function CodeObject."""
        result = _compile("fn add(a, b) { return a + b }")
        assert "add" in result.functions
        fn = result.functions["add"]
        assert fn.name == "add"
        assert _strip_locations(fn.instructions) == [
            Instruction(OpCode.LOAD_NAME, "a"),
            Instruction(OpCode.LOAD_NAME, "b"),
            Instruction(OpCode.ADD),
            Instruction(OpCode.RETURN),
        ]

    def test_function_not_in_main(self) -> None:
        """Function body does not appear in main; main only has HALT."""
        result = _compile("fn greet() { print(1) }")
        assert result.main.instructions == [Instruction(OpCode.HALT)]

    def test_implicit_return(self) -> None:
        """A function without explicit return gets LOAD_CONST <idx>, RETURN."""
        result = _compile("fn greet() { print(1) }")
        fn = result.functions["greet"]
        # Constant pool: [1, 0] — print(1) adds 1 at index 0, implicit return adds 0 at index 1
        implicit_load = fn.instructions[-TWO]
        assert implicit_load.opcode is OpCode.LOAD_CONST
        assert fn.constants[implicit_load.operand] == 0  # type: ignore[index]
        assert fn.instructions[-ONE] == Instruction(OpCode.RETURN)


class TestCompileFunctionParameters:
    """Verify function parameters are stored in CodeObject."""

    def test_function_stores_parameters(self) -> None:
        """``fn add(a, b)`` stores ["a", "b"] in CodeObject.parameters."""
        result = _compile("fn add(a, b) { return a + b }")
        fn = result.functions["add"]
        assert fn.parameters == ["a", "b"]

    def test_no_parameters_function(self) -> None:
        """``fn greet()`` stores an empty parameter list."""
        result = _compile("fn greet() { print(1) }")
        fn = result.functions["greet"]
        assert fn.parameters == []

    def test_main_has_no_parameters(self) -> None:
        """The main CodeObject always has empty parameters."""
        result = _compile("print(1)")
        assert result.main.parameters == []


class TestCompileReturn:
    """Verify return statement compilation."""

    def test_return_with_value(self) -> None:
        """``return 42`` loads the value and returns."""
        result = _compile("fn f() { return 42 }")
        fn = result.functions["f"]
        assert _strip_locations(fn.instructions) == [
            Instruction(OpCode.LOAD_CONST, ZERO),
            Instruction(OpCode.RETURN),
        ]
        assert fn.constants == [42]

    def test_bare_return(self) -> None:
        """``return`` without a value returns 0."""
        result = _compile("fn f() { return }")
        fn = result.functions["f"]
        assert _strip_locations(fn.instructions) == [
            Instruction(OpCode.LOAD_CONST, ZERO),
            Instruction(OpCode.RETURN),
        ]
        assert fn.constants == [0]


class TestCompileFunctionCall:
    """Verify function call compilation."""

    def test_call_in_print(self) -> None:
        """``print(add(1, 2))`` pushes args, calls, then prints."""
        source = "fn add(a, b) { return a + b }\nprint(add(1, 2))"
        ins = _instructions(source)
        assert ins == [
            Instruction(OpCode.LOAD_CONST, ZERO),  # 0: 1
            Instruction(OpCode.LOAD_CONST, ONE),  # 1: 2
            Instruction(OpCode.CALL, "add"),  # 2
            Instruction(OpCode.PRINT),  # 3
            Instruction(OpCode.HALT),  # 4
        ]

    def test_call_no_args(self) -> None:
        """``greet()`` with no arguments emits CALL."""
        source = "fn greet() { print(1) }\ngreet()"
        ins = _instructions(source)
        # greet() is an expression statement → CALL, POP
        assert Instruction(OpCode.CALL, "greet") in ins


class TestCompileExpressionStatements:
    """Verify bare expression statements emit POP to discard the value."""

    def test_bare_function_call_pops(self) -> None:
        """``greet()`` as a statement emits CALL then POP."""
        source = "fn greet() { print(1) }\ngreet()"
        ins = _instructions(source)
        call_idx = next(
            i for i, inst in enumerate(ins) if inst == Instruction(OpCode.CALL, "greet")
        )
        assert ins[call_idx + 1] == Instruction(OpCode.POP)


# -- Cycle 8: Integration ----------------------------------------------------


class TestCompilerIntegration:
    """Full programs exercising multiple features together."""

    def test_full_program(self) -> None:
        """Variables, if/else, while, print, and functions together."""
        source = """\
fn double(n) { return n * 2 }
let x = 5
if x > 3 {
    print(double(x))
} else {
    print(x)
}"""
        result = _compile(source)
        assert isinstance(result, CompiledProgram)
        assert "double" in result.functions
        assert result.main.instructions[-1] == Instruction(OpCode.HALT)

    def test_function_calling_function(self) -> None:
        """One function calls another."""
        source = """\
fn add(a, b) { return a + b }
fn add3(a, b, c) { return add(add(a, b), c) }
print(add3(1, 2, 3))"""
        result = _compile(source)
        assert "add" in result.functions
        assert "add3" in result.functions
        fn = result.functions["add3"]
        calls = [i for i in fn.instructions if i.opcode is OpCode.CALL]
        assert len(calls) == TWO

    def test_for_loop_inside_function(self) -> None:
        """For loop inside a function body uses the function's CodeObject."""
        source = """\
fn sum_to(n) {
    let total = 0
    for i in range(n) {
        total = total + i
    }
    return total
}
print(sum_to(5))"""
        result = _compile(source)
        fn = result.functions["sum_to"]
        # The function should contain a $for_limit variable
        store_names = [i.operand for i in fn.instructions if i.opcode is OpCode.STORE_NAME]
        assert any(isinstance(n, str) and n.startswith("$for_limit") for n in store_names)

    def test_nested_while_if(self) -> None:
        """While loop containing an if statement."""
        source = """\
let x = 0
while x < 10 {
    if x > 5 {
        print(x)
    }
    x = x + 1
}"""
        ins = _instructions(source)
        # Should have JUMP_IF_FALSE (while exit), JUMP_IF_FALSE (if skip),
        # and JUMP (while back)
        jump_if_false = [i for i in ins if i.opcode is OpCode.JUMP_IF_FALSE]
        jumps = [i for i in ins if i.opcode is OpCode.JUMP]
        assert len(jump_if_false) == TWO
        assert len(jumps) == ONE
        assert ins[-1] == Instruction(OpCode.HALT)

    def test_compile_returns_compiled_program(self) -> None:
        """``compile()`` always returns a CompiledProgram."""
        result = _compile("print(1)")
        assert isinstance(result, CompiledProgram)
        assert isinstance(result.main.instructions, list)
        assert isinstance(result.functions, dict)
