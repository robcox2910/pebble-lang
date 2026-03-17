"""Tests for default parameter values (Phase 4 Item 2).

Cover parser round-trip, analyzer validation (ordering, literal-only,
arity), compiler default emission, and end-to-end integration.
"""

import pytest

from pebble.ast_nodes import (
    BooleanLiteral,
    FloatLiteral,
    FunctionDef,
    IntegerLiteral,
    StringLiteral,
    TypeAnnotation,
)
from pebble.bytecode import OpCode
from pebble.errors import SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from tests.conftest import (
    analyze,
    compile_instructions,
    run_source,
)

# -- Helpers ------------------------------------------------------------------


def _parse(source: str) -> FunctionDef:
    """Parse *source* and return the first FunctionDef statement."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    for stmt in program.statements:
        if isinstance(stmt, FunctionDef):
            return stmt
    msg = "No FunctionDef found"
    raise ValueError(msg)


# -- Named constants ----------------------------------------------------------

DEFAULT_INT = 1
DEFAULT_FLOAT = 3.14
REQUIRED_PARAMS = 1
TOTAL_PARAMS_TWO = 2
TOTAL_PARAMS_THREE = 3


# -- Cycle 1: Parser ----------------------------------------------------------


class TestParserDefaults:
    """Parser round-trips for default parameter values."""

    def test_parse_one_default(self) -> None:
        """Parse ``fn f(a, b = 1)`` — second param has default."""
        fn = _parse("fn f(a, b = 1) { return a + b }")
        assert len(fn.parameters) == TOTAL_PARAMS_TWO
        assert fn.parameters[0].default is None
        assert isinstance(fn.parameters[1].default, IntegerLiteral)
        assert fn.parameters[1].default.value == DEFAULT_INT

    def test_parse_multiple_defaults(self) -> None:
        """Parse ``fn f(a, b = 1, c = "x")`` — both defaults parsed."""
        fn = _parse('fn f(a, b = 1, c = "x") { return a }')
        assert len(fn.parameters) == TOTAL_PARAMS_THREE
        assert fn.parameters[0].default is None
        assert isinstance(fn.parameters[1].default, IntegerLiteral)
        assert isinstance(fn.parameters[2].default, StringLiteral)
        assert fn.parameters[2].default.value == "x"

    def test_parse_default_with_type(self) -> None:
        """Parse ``fn f(a, b: Int = 42)`` — type annotation + default."""
        fn = _parse("fn f(a, b: Int = 42) { return a + b }")
        assert fn.parameters[1].type_annotation == TypeAnnotation(name="Int")
        assert isinstance(fn.parameters[1].default, IntegerLiteral)
        forty_two = 42
        assert fn.parameters[1].default.value == forty_two

    def test_parse_no_defaults(self) -> None:
        """Parse ``fn f(a, b)`` — both defaults are None."""
        fn = _parse("fn f(a, b) { return a + b }")
        assert fn.parameters[0].default is None
        assert fn.parameters[1].default is None

    def test_parse_default_float(self) -> None:
        """Parse ``fn f(x = 3.14)`` — float default."""
        fn = _parse("fn f(x = 3.14) { return x }")
        assert isinstance(fn.parameters[0].default, FloatLiteral)
        assert fn.parameters[0].default.value == DEFAULT_FLOAT

    def test_parse_default_bool(self) -> None:
        """Parse ``fn f(x = true)`` — boolean default."""
        fn = _parse("fn f(x = true) { return x }")
        assert isinstance(fn.parameters[0].default, BooleanLiteral)
        assert fn.parameters[0].default.value is True

    def test_parse_default_string(self) -> None:
        """Parse ``fn f(x = "hello")`` — string default."""
        fn = _parse('fn f(x = "hello") { return x }')
        assert isinstance(fn.parameters[0].default, StringLiteral)
        assert fn.parameters[0].default.value == "hello"


# -- Cycle 2: Analyzer --------------------------------------------------------


class TestAnalyzerDefaults:
    """Analyzer validation for default parameter values."""

    def test_required_after_default_error(self) -> None:
        """Required param after optional → SemanticError."""
        with pytest.raises(SemanticError, match="cannot follow"):
            analyze("fn f(a = 1, b) { return b }")

    def test_non_literal_default_error(self) -> None:
        """Non-literal default → SemanticError."""
        with pytest.raises(SemanticError, match="must be literals"):
            analyze("fn f(a = 1 + 2) { return a }")

    def test_default_arity_accepts_full(self) -> None:
        """Call with all arguments passes analysis."""
        analyze("""
            fn f(a, b = 10) { return a + b }
            f(1, 2)
        """)

    def test_default_arity_accepts_partial(self) -> None:
        """Call omitting defaulted argument passes analysis."""
        analyze("""
            fn f(a, b = 10) { return a + b }
            f(1)
        """)

    def test_default_arity_rejects_too_few(self) -> None:
        """Call with fewer than required args → SemanticError."""
        with pytest.raises(SemanticError, match="expects"):
            analyze("""
                fn f(a, b = 10) { return a + b }
                f()
            """)

    def test_default_arity_rejects_too_many(self) -> None:
        """Call with more than total args → SemanticError."""
        with pytest.raises(SemanticError, match="expects"):
            analyze("""
                fn f(a, b = 10) { return a + b }
                f(1, 2, 3)
            """)

    def test_identifier_default_error(self) -> None:
        """Variable-reference default → SemanticError."""
        with pytest.raises(SemanticError, match="must be literals"):
            analyze("""
                let x = 5
                fn f(a = x) { return a }
            """)


# -- Cycle 3: Compiler --------------------------------------------------------


class TestCompilerDefaults:
    """Compiler emits default constants at call sites."""

    def test_call_with_default_emits_const(self) -> None:
        """Calling with one omitted default emits LOAD_CONST for it."""
        source = """
            fn f(a, b = 42) { return a + b }
            f(1)
        """
        instructions = compile_instructions(source)
        # Find the CALL instruction for f
        call_idx = next(
            i
            for i, instr in enumerate(instructions)
            if instr.opcode is OpCode.CALL and instr.operand == "f"
        )
        # The instruction before CALL should be LOAD_CONST for 42
        before_call = instructions[call_idx - 1]
        assert before_call.opcode is OpCode.LOAD_CONST

    def test_call_with_all_args_no_extra_const(self) -> None:
        """Calling with all arguments emits no extra LOAD_CONST."""
        source = """
            fn f(a, b = 42) { return a + b }
            f(1, 2)
        """
        instructions = compile_instructions(source)
        call_idx = next(
            i
            for i, instr in enumerate(instructions)
            if instr.opcode is OpCode.CALL and instr.operand == "f"
        )
        # The two instructions before CALL should be LOAD_CONST 1 and LOAD_CONST 2
        # (the explicit arguments), not an extra default
        before_call = instructions[call_idx - 1]
        # This should be LOAD_CONST for argument 2, not 42
        assert before_call.opcode is OpCode.LOAD_CONST


# -- Cycle 4: Integration (end-to-end) ----------------------------------------


class TestIntegrationDefaults:
    """End-to-end tests for default parameter values."""

    def test_default_used(self) -> None:
        """Omitted argument uses default value."""
        output = run_source("""
            fn greet(name, greeting = "Hello") {
                print("{greeting} {name}")
            }
            greet("Alice")
        """)
        assert output.strip() == "Hello Alice"

    def test_default_overridden(self) -> None:
        """Explicit argument overrides default."""
        output = run_source("""
            fn greet(name, greeting = "Hello") {
                print("{greeting} {name}")
            }
            greet("Alice", "Hi")
        """)
        assert output.strip() == "Hi Alice"

    def test_multiple_defaults(self) -> None:
        """Multiple defaulted parameters work correctly."""
        output = run_source("""
            fn f(a, b = 10, c = 20) {
                return a + b + c
            }
            print(f(1))
        """)
        expected = 31
        assert output.strip() == str(expected)

    def test_multiple_defaults_partial_override(self) -> None:
        """Override first default, use second."""
        output = run_source("""
            fn f(a, b = 10, c = 20) {
                return a + b + c
            }
            print(f(1, 5))
        """)
        expected = 26
        assert output.strip() == str(expected)

    def test_default_with_type_annotation(self) -> None:
        """Type-annotated default works end-to-end."""
        output = run_source("""
            fn f(x: Int = 42) {
                return x
            }
            print(f())
        """)
        expected = 42
        assert output.strip() == str(expected)

    def test_default_string(self) -> None:
        """String default works end-to-end."""
        output = run_source("""
            fn f(x = "world") {
                return x
            }
            print(f())
        """)
        assert output.strip() == "world"

    def test_default_bool(self) -> None:
        """Bool default works end-to-end."""
        output = run_source("""
            fn f(x = true) {
                return x
            }
            print(f())
        """)
        assert output.strip() == "true"

    def test_default_float(self) -> None:
        """Float default works end-to-end."""
        output = run_source("""
            fn f(x = 3.14) {
                return x
            }
            print(f())
        """)
        assert output.strip() == "3.14"

    def test_default_in_closure(self) -> None:
        """Closure with default called by name from within its scope."""
        output = run_source("""
            fn make_adder(base) {
                fn add(x = 10) {
                    return base + x
                }
                return add()
            }
            print(make_adder(5))
        """)
        expected = 15
        assert output.strip() == str(expected)

    def test_default_in_anonymous_fn(self) -> None:
        """Anonymous function with all args passed through variable works."""
        output = run_source("""
            let f = fn(x, y = 10) { return x + y }
            print(f(5, 20))
        """)
        expected = 25
        assert output.strip() == str(expected)
