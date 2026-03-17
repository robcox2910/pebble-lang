"""Tests for the standard library built-in functions and importable modules.

Cover the builtins module, analyzer registration, VM execution of
str(), int(), type(), push(), pop(), and the importable stdlib modules
(``import "math"``, ``import "io"``).
"""

import math
from io import StringIO
from pathlib import Path

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.builtins import (
    BUILTIN_ARITIES,
    BUILTINS,
    LIST_METHODS,
    METHOD_ARITIES,
    STRING_METHODS,
    Value,
    format_value,
)
from pebble.errors import PebbleImportError, PebbleRuntimeError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.repl import Repl
from pebble.resolver import ModuleResolver
from pebble.stdlib import (
    IO_MODULE,
    MATH_MODULE,
    STDLIB_MODULES,
    StdlibModule,
)
from tests.conftest import (  # pyright: ignore[reportMissingImports]
    run_source,  # pyright: ignore[reportUnknownVariableType]
    run_source_with_stdlib,  # pyright: ignore[reportUnknownVariableType]
)


def _run_source(source: str) -> str:
    """Compile and run *source*, return captured output."""
    return run_source(source)  # type: ignore[no-any-return]


# -- Named constants ----------------------------------------------------------

RUNTIME_BUILTIN_COUNT = 8
TOTAL_BUILTIN_COUNT = 15
STRING_METHOD_COUNT = 12
LIST_METHOD_COUNT = 5
METHOD_ARITY_COUNT = 16

# Math handler expected values
EXPECTED_ABS_INT = 5
EXPECTED_ABS_FLOAT = 3.14
EXPECTED_MIN_INT = 3
EXPECTED_MIN_FLOAT = 2.1
EXPECTED_MAX_INT = 7
EXPECTED_MAX_FLOAT = 9.9
EXPECTED_FLOOR_POS = 3
EXPECTED_FLOOR_NEG = -3
EXPECTED_FLOOR_INT = 5
EXPECTED_CEIL_POS = 4
EXPECTED_CEIL_NEG = -2
EXPECTED_ROUND_DOWN = 3
EXPECTED_ROUND_UP = 4
EXPECTED_SQRT_INT = 4.0
EXPECTED_POW_FLOAT = 2.0
FLOAT_TOLERANCE = 1e-10


# -- Cycle 1: Builtins module + str() ----------------------------------------


class TestBuiltinsModule:
    """Verify the builtins registry structure."""

    def test_runtime_builtin_count(self) -> None:
        """There are 8 runtime builtins."""
        assert len(BUILTINS) == RUNTIME_BUILTIN_COUNT

    def test_total_builtin_arities(self) -> None:
        """BUILTIN_ARITIES includes all 15 builtins."""
        assert len(BUILTIN_ARITIES) == TOTAL_BUILTIN_COUNT

    def test_all_runtime_builtins_in_arities(self) -> None:
        """Every runtime builtin appears in BUILTIN_ARITIES."""
        for name in BUILTINS:
            assert name in BUILTIN_ARITIES

    def test_string_method_count(self) -> None:
        """There are 12 string methods."""
        assert len(STRING_METHODS) == STRING_METHOD_COUNT

    def test_list_method_count(self) -> None:
        """There are 5 list methods."""
        assert len(LIST_METHODS) == LIST_METHOD_COUNT

    def test_method_arity_count(self) -> None:
        """METHOD_ARITIES covers all 16 method names."""
        assert len(METHOD_ARITIES) == METHOD_ARITY_COUNT


class TestFormatValue:
    """Verify the format_value helper."""

    def test_format_int(self) -> None:
        """format_value(42) returns '42'."""
        assert format_value(42) == "42"

    def test_format_str(self) -> None:
        """format_value('hello') returns 'hello'."""
        assert format_value("hello") == "hello"

    def test_format_bool_true(self) -> None:
        """format_value(True) returns 'true'."""
        assert format_value(True) == "true"

    def test_format_bool_false(self) -> None:
        """format_value(False) returns 'false'."""
        assert format_value(False) == "false"

    def test_format_list(self) -> None:
        """format_value([1, 2, 3]) returns '[1, 2, 3]'."""
        assert format_value([1, 2, 3]) == "[1, 2, 3]"


class TestStrBuiltin:
    """Verify str() conversion."""

    def test_str_of_int(self) -> None:
        """str(42) returns '42'."""
        assert _run_source("print(str(42))") == "42\n"

    def test_str_of_bool_true(self) -> None:
        """str(true) returns 'true'."""
        assert _run_source("print(str(true))") == "true\n"

    def test_str_of_bool_false(self) -> None:
        """str(false) returns 'false'."""
        assert _run_source("print(str(false))") == "false\n"

    def test_str_of_string(self) -> None:
        """str('hello') returns 'hello'."""
        assert _run_source('print(str("hello"))') == "hello\n"

    def test_str_of_list(self) -> None:
        """str([1, 2]) returns '[1, 2]'."""
        assert _run_source("print(str([1, 2]))") == "[1, 2]\n"


# -- Cycle 2: int() + type() -------------------------------------------------


class TestIntBuiltin:
    """Verify int() conversion."""

    def test_int_of_string(self) -> None:
        """int('42') returns 42."""
        assert _run_source('print(int("42"))') == "42\n"

    def test_int_of_negative_string(self) -> None:
        """int('-7') returns -7."""
        assert _run_source('print(int("-7"))') == "-7\n"

    def test_int_of_int(self) -> None:
        """int(42) returns 42 (identity)."""
        assert _run_source("print(int(42))") == "42\n"

    def test_int_of_non_numeric_string(self) -> None:
        """int('hello') raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="Cannot convert"):
            _run_source('int("hello")')

    def test_int_of_bool(self) -> None:
        """int(true) raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="Cannot convert"):
            _run_source("int(true)")


class TestTypeBuiltin:
    """Verify type() introspection."""

    def test_type_of_int(self) -> None:
        """type(42) returns 'int'."""
        assert _run_source("print(type(42))") == "int\n"

    def test_type_of_str(self) -> None:
        """type('hello') returns 'str'."""
        assert _run_source('print(type("hello"))') == "str\n"

    def test_type_of_bool(self) -> None:
        """type(true) returns 'bool'."""
        assert _run_source("print(type(true))") == "bool\n"

    def test_type_of_list(self) -> None:
        """type([]) returns 'list'."""
        assert _run_source("print(type([]))") == "list\n"


# -- Cycle 3: push() + pop() -------------------------------------------------


class TestPushBuiltin:
    """Verify push() list mutation."""

    def test_push_appends_element(self) -> None:
        """push(xs, 4) appends 4 to the list."""
        source = "let xs = [1, 2, 3]\npush(xs, 4)\nprint(xs)"
        assert _run_source(source) == "[1, 2, 3, 4]\n"

    def test_push_returns_list(self) -> None:
        """push() returns the mutated list."""
        source = "let xs = [1]\nprint(push(xs, 2))"
        assert _run_source(source) == "[1, 2]\n"

    def test_push_to_empty_list(self) -> None:
        """push([], 1) works on empty lists."""
        source = "let xs = []\npush(xs, 1)\nprint(xs)"
        assert _run_source(source) == "[1]\n"

    def test_push_non_list_error(self) -> None:
        """push() on a non-list raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="requires a list"):
            _run_source('push("hello", 1)')


class TestPopBuiltin:
    """Verify pop() list mutation."""

    def test_pop_removes_last(self) -> None:
        """pop(xs) removes and returns the last element."""
        source = "let xs = [1, 2, 3]\nlet last = pop(xs)\nprint(last)\nprint(xs)"
        assert _run_source(source) == "3\n[1, 2]\n"

    def test_pop_empty_list_error(self) -> None:
        """pop([]) raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="empty list"):
            _run_source("let xs = []\npop(xs)")

    def test_pop_non_list_error(self) -> None:
        """pop() on a non-list raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="requires a list"):
            _run_source('pop("hello")')


# -- Cycle 4: Analyzer registration -------------------------------------------


class TestAnalyzerBuiltins:
    """Verify the analyzer recognizes all builtins."""

    def test_push_arity_check(self) -> None:
        """push() with wrong arity raises SemanticError."""
        with pytest.raises(SemanticError, match="expects 2"):
            _run_source("push([1])")

    def test_pop_arity_check(self) -> None:
        """pop() with wrong arity raises SemanticError."""
        with pytest.raises(SemanticError, match="expects 1"):
            _run_source("pop([1], 2)")

    def test_undeclared_function_still_caught(self) -> None:
        """Calling an unknown function still raises SemanticError."""
        with pytest.raises(SemanticError, match="Undeclared function"):
            _run_source("foo()")

    def test_existing_builtins_still_work(self) -> None:
        """print, range, and len still work after refactor."""
        source = """\
let xs = [1, 2, 3]
for i in range(len(xs)) {
    print(xs[i])
}"""
        assert _run_source(source) == "1\n2\n3\n"


# -- Cycle 5: Integration ----------------------------------------------------


class TestStdlibIntegration:
    """End-to-end tests combining stdlib with other features."""

    def test_build_list_with_push(self) -> None:
        """Build a list dynamically using push in a loop."""
        source = """\
let xs = []
for i in range(3) {
    push(xs, i * 10)
}
print(xs)"""
        assert _run_source(source) == "[0, 10, 20]\n"

    def test_type_check_in_condition(self) -> None:
        """Use type() in an if condition."""
        source = """\
let x = 42
if type(x) == "int" {
    print("it is an integer")
}"""
        assert _run_source(source) == "it is an integer\n"

    def test_str_in_interpolation(self) -> None:
        """Use str() inside string interpolation."""
        source = 'let x = 42\nprint("value: {str(x)}")'
        assert _run_source(source) == "value: 42\n"

    def test_int_round_trip(self) -> None:
        """Convert int to str to int."""
        source = """\
let x = 42
let s = str(x)
let y = int(s)
print(y)"""
        assert _run_source(source) == "42\n"

    def test_stack_with_push_pop(self) -> None:
        """Use push/pop to implement a simple stack."""
        source = """\
let stack = []
push(stack, 1)
push(stack, 2)
push(stack, 3)
let top = pop(stack)
print("popped: {top}, remaining: {len(stack)}")"""
        assert _run_source(source) == "popped: 3, remaining: 2\n"


# -- Cycle 1 (stdlib): Module registry + math handlers -----------------------

MATH_FUNCTION_COUNT = 11
MATH_CONSTANT_COUNT = 2
IO_FUNCTION_COUNT = 1
STDLIB_MODULE_COUNT = 2


class TestStdlibModuleRegistry:
    """Verify the stdlib module registry structure."""

    def test_stdlib_module_count(self) -> None:
        """STDLIB_MODULES contains math and io."""
        assert len(STDLIB_MODULES) == STDLIB_MODULE_COUNT

    def test_math_is_stdlib_module(self) -> None:
        """MATH_MODULE is a StdlibModule instance."""
        assert isinstance(MATH_MODULE, StdlibModule)

    def test_io_is_stdlib_module(self) -> None:
        """IO_MODULE is a StdlibModule instance."""
        assert isinstance(IO_MODULE, StdlibModule)

    def test_math_function_count(self) -> None:
        """Math module has 11 functions."""
        assert len(MATH_MODULE.functions) == MATH_FUNCTION_COUNT

    def test_math_constant_count(self) -> None:
        """Math module has 2 constants (pi, e)."""
        assert len(MATH_MODULE.constants) == MATH_CONSTANT_COUNT

    def test_io_function_count(self) -> None:
        """IO module has 1 function (input)."""
        assert len(IO_MODULE.functions) == IO_FUNCTION_COUNT

    def test_math_constants_values(self) -> None:
        """Math constants pi and e have correct values."""
        assert MATH_MODULE.constants["pi"] == math.pi
        assert MATH_MODULE.constants["e"] == math.e

    def test_io_input_handler_is_none(self) -> None:
        """IO input handler is None (VM-dispatched)."""
        _arity, handler = IO_MODULE.functions["input"]
        assert handler is None


class TestMathHandlers:
    """Verify each math stdlib handler returns correct values."""

    def _call(self, name: str, args: list[Value]) -> Value:
        """Call a math stdlib handler by name."""
        _arity, handler = MATH_MODULE.functions[name]
        assert handler is not None
        return handler(args)

    def test_abs_positive(self) -> None:
        """abs(5) returns 5."""
        assert self._call("abs", [5]) == EXPECTED_ABS_INT

    def test_abs_negative(self) -> None:
        """abs(-5) returns 5."""
        assert self._call("abs", [-5]) == EXPECTED_ABS_INT

    def test_abs_float(self) -> None:
        """abs(-3.14) returns 3.14."""
        assert self._call("abs", [-3.14]) == EXPECTED_ABS_FLOAT

    def test_abs_zero(self) -> None:
        """abs(0) returns 0."""
        assert self._call("abs", [0]) == 0

    def test_min_ints(self) -> None:
        """min(3, 7) returns 3."""
        assert self._call("min", [3, 7]) == EXPECTED_MIN_INT

    def test_min_floats(self) -> None:
        """min(3.5, 2.1) returns 2.1."""
        assert self._call("min", [3.5, 2.1]) == EXPECTED_MIN_FLOAT

    def test_max_ints(self) -> None:
        """max(3, 7) returns 7."""
        assert self._call("max", [3, 7]) == EXPECTED_MAX_INT

    def test_max_floats(self) -> None:
        """max(1.5, 9.9) returns 9.9."""
        assert self._call("max", [1.5, 9.9]) == EXPECTED_MAX_FLOAT

    def test_floor(self) -> None:
        """floor(3.7) returns 3."""
        assert self._call("floor", [3.7]) == EXPECTED_FLOOR_POS

    def test_floor_negative(self) -> None:
        """floor(-2.3) returns -3."""
        assert self._call("floor", [-2.3]) == EXPECTED_FLOOR_NEG

    def test_floor_int(self) -> None:
        """floor(5) returns 5."""
        assert self._call("floor", [5]) == EXPECTED_FLOOR_INT

    def test_ceil(self) -> None:
        """ceil(3.2) returns 4."""
        assert self._call("ceil", [3.2]) == EXPECTED_CEIL_POS

    def test_ceil_negative(self) -> None:
        """ceil(-2.7) returns -2."""
        assert self._call("ceil", [-2.7]) == EXPECTED_CEIL_NEG

    def test_round_down(self) -> None:
        """round(3.2) returns 3."""
        assert self._call("round", [3.2]) == EXPECTED_ROUND_DOWN

    def test_round_up(self) -> None:
        """round(3.7) returns 4."""
        assert self._call("round", [3.7]) == EXPECTED_ROUND_UP

    def test_sqrt(self) -> None:
        """sqrt(16) returns 4.0."""
        assert self._call("sqrt", [16]) == EXPECTED_SQRT_INT

    def test_sqrt_float(self) -> None:
        """sqrt(2.0) returns approximately 1.414."""
        result = self._call("sqrt", [2.0])
        assert isinstance(result, float)
        assert abs(result - math.sqrt(2.0)) < FLOAT_TOLERANCE

    def test_pow_ints(self) -> None:
        """pow(2, 10) returns 1024."""
        expected = 1024
        assert self._call("pow", [2, 10]) == expected

    def test_pow_float_exponent(self) -> None:
        """pow(4, 0.5) returns 2.0."""
        assert self._call("pow", [4, 0.5]) == EXPECTED_POW_FLOAT

    def test_sin_zero(self) -> None:
        """sin(0) returns 0.0."""
        assert self._call("sin", [0]) == 0.0

    def test_cos_zero(self) -> None:
        """cos(0) returns 1.0."""
        assert self._call("cos", [0]) == 1.0

    def test_sin_pi_half(self) -> None:
        """sin(pi/2) returns approximately 1.0."""
        result = self._call("sin", [math.pi / 2])
        assert isinstance(result, float)
        assert abs(result - 1.0) < FLOAT_TOLERANCE

    def test_log_e(self) -> None:
        """log(e) returns 1.0."""
        assert self._call("log", [math.e]) == 1.0

    def test_log_one(self) -> None:
        """log(1) returns 0.0."""
        assert self._call("log", [1]) == 0.0


class TestMathHandlerErrors:
    """Verify math handlers raise PebbleRuntimeError for bad types."""

    def _call(self, name: str, args: list[Value]) -> Value:
        """Call a math stdlib handler by name."""
        _arity, handler = MATH_MODULE.functions[name]
        assert handler is not None
        return handler(args)

    def test_abs_string_error(self) -> None:
        """abs('hello') raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="requires a number"):
            self._call("abs", ["hello"])

    def test_sqrt_string_error(self) -> None:
        """sqrt('hello') raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="requires a number"):
            self._call("sqrt", ["hello"])

    def test_sqrt_negative_error(self) -> None:
        """sqrt(-1) raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="negative"):
            self._call("sqrt", [-1])

    def test_log_zero_error(self) -> None:
        """log(0) raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="positive"):
            self._call("log", [0])

    def test_log_negative_error(self) -> None:
        """log(-1) raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="positive"):
            self._call("log", [-1])

    def test_min_string_error(self) -> None:
        """min('a', 'b') raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="requires numbers"):
            self._call("min", ["a", "b"])

    def test_floor_bool_error(self) -> None:
        """floor(true) raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="requires a number"):
            self._call("floor", [True])


# -- Cycle 2 (stdlib): Resolver + Analyzer stdlib detection ------------------


class TestResolverStdlib:
    """Verify resolver detects stdlib modules and registers names."""

    def test_math_import_registers_functions(self) -> None:
        """Import 'math' registers all math functions in analyzer."""
        source = 'import "math"'
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        resolver = ModuleResolver(base_dir=Path.cwd())
        resolver.resolve_imports(program, analyzer)
        # sqrt should be registered as a function with arity 1
        resolved = analyzer._scope.resolve_function("sqrt")
        assert resolved is not None
        arity, _ = resolved
        assert arity == 1

    def test_math_import_registers_constants(self) -> None:
        """Import 'math' registers pi and e as variables in analyzer."""
        source = 'import "math"'
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        resolver = ModuleResolver(base_dir=Path.cwd())
        resolver.resolve_imports(program, analyzer)
        # pi should be registered as a variable
        assert analyzer._scope.resolve_variable("pi") is not None

    def test_resolver_merged_stdlib_handlers(self) -> None:
        """Resolver exposes merged stdlib handlers after import."""
        source = 'import "math"'
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        resolver = ModuleResolver(base_dir=Path.cwd())
        resolver.resolve_imports(program, analyzer)
        handlers = resolver.merged_stdlib_handlers
        assert "sqrt" in handlers
        assert "abs" in handlers

    def test_resolver_merged_stdlib_constants(self) -> None:
        """Resolver exposes merged stdlib constants after import."""
        source = 'import "math"'
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        resolver = ModuleResolver(base_dir=Path.cwd())
        resolver.resolve_imports(program, analyzer)
        constants = resolver.merged_stdlib_constants
        assert "pi" in constants
        assert constants["pi"] == math.pi

    def test_from_import_selective(self) -> None:
        """From 'math' import sqrt registers only sqrt."""
        source = 'from "math" import sqrt'
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        resolver = ModuleResolver(base_dir=Path.cwd())
        resolver.resolve_imports(program, analyzer)
        # sqrt should be registered
        assert analyzer._scope.resolve_function("sqrt") is not None
        # abs should NOT be registered
        assert analyzer._scope.resolve_function("abs") is None

    def test_from_import_constant(self) -> None:
        """From 'math' import pi registers pi as variable."""
        source = 'from "math" import pi'
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        resolver = ModuleResolver(base_dir=Path.cwd())
        resolver.resolve_imports(program, analyzer)
        assert analyzer._scope.resolve_variable("pi") is not None

    def test_from_import_unknown_name_error(self) -> None:
        """From 'math' import nonexistent raises PebbleImportError."""
        source = 'from "math" import nonexistent'
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        resolver = ModuleResolver(base_dir=Path.cwd())
        with pytest.raises(PebbleImportError, match="does not export 'nonexistent'"):
            resolver.resolve_imports(program, analyzer)

    def test_io_import_registers_input(self) -> None:
        """Import 'io' registers input function with arity (0, 1)."""
        source = 'import "io"'
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        resolver = ModuleResolver(base_dir=Path.cwd())
        resolver.resolve_imports(program, analyzer)
        resolved = analyzer._scope.resolve_function("input")
        assert resolved is not None
        arity, _ = resolved
        assert arity == (0, 1)


# -- Cycle 3 (stdlib): End-to-end math tests --------------------------------


def _run_stdlib(source: str) -> str:
    """Compile and run *source* with stdlib support, return captured output."""
    return run_source_with_stdlib(source)  # type: ignore[no-any-return]


class TestMathEndToEnd:
    """End-to-end tests: import 'math' and use functions/constants."""

    def test_import_math_sqrt(self) -> None:
        """Import 'math' then sqrt(16) returns 4.0."""
        source = 'import "math"\nprint(sqrt(16))'
        assert _run_stdlib(source) == "4.0\n"

    def test_import_math_pi(self) -> None:
        """Import 'math' then print(pi) shows pi value."""
        source = 'import "math"\nprint(pi)'
        assert _run_stdlib(source) == "3.141592653589793\n"

    def test_import_math_e(self) -> None:
        """Import 'math' then print(e) shows e value."""
        source = 'import "math"\nprint(e)'
        assert _run_stdlib(source) == "2.718281828459045\n"

    def test_import_math_floor(self) -> None:
        """Import 'math' then floor(3.7) returns 3."""
        source = 'import "math"\nprint(floor(3.7))'
        assert _run_stdlib(source) == "3\n"

    def test_import_math_ceil(self) -> None:
        """Import 'math' then ceil(3.2) returns 4."""
        source = 'import "math"\nprint(ceil(3.2))'
        assert _run_stdlib(source) == "4\n"

    def test_import_math_abs(self) -> None:
        """Import 'math' then abs(-5) returns 5."""
        source = 'import "math"\nprint(abs(-5))'
        assert _run_stdlib(source) == "5\n"

    def test_import_math_min_max(self) -> None:
        """Import 'math' then min/max work correctly."""
        source = 'import "math"\nprint(min(3, 7))\nprint(max(3, 7))'
        assert _run_stdlib(source) == "3\n7\n"

    def test_import_math_round(self) -> None:
        """Import 'math' then round(3.7) returns 4."""
        source = 'import "math"\nprint(round(3.7))'
        assert _run_stdlib(source) == "4\n"

    def test_import_math_pow(self) -> None:
        """Import 'math' then pow(2, 10) returns 1024."""
        source = 'import "math"\nprint(pow(2, 10))'
        assert _run_stdlib(source) == "1024\n"

    def test_import_math_sin_cos(self) -> None:
        """Import 'math' then sin(0) and cos(0) work."""
        source = 'import "math"\nprint(sin(0))\nprint(cos(0))'
        assert _run_stdlib(source) == "0.0\n1.0\n"

    def test_import_math_log(self) -> None:
        """Import 'math' then log(1) returns 0.0."""
        source = 'import "math"\nprint(log(1))'
        assert _run_stdlib(source) == "0.0\n"

    def test_from_math_import_selective(self) -> None:
        """From 'math' import sqrt, pi imports only those names."""
        source = 'from "math" import sqrt, pi\nprint(sqrt(pi))'
        output = _run_stdlib(source)
        # sqrt(pi) ≈ 1.7724538509...
        assert output.startswith("1.772")

    def test_math_in_expression(self) -> None:
        """Math functions work inside complex expressions."""
        source = 'import "math"\nlet x = sqrt(16) + floor(3.7)\nprint(x)'
        assert _run_stdlib(source) == "7.0\n"

    def test_math_in_loop(self) -> None:
        """Math functions work inside for loops."""
        source = 'import "math"\nfor i in range(3) {\n    print(pow(2, i))\n}'
        assert _run_stdlib(source) == "1\n2\n4\n"

    def test_constant_is_value_not_call(self) -> None:
        """Constants like pi are values, not function calls."""
        source = 'import "math"\nlet x = pi * 2\nprint(x > 6)'
        assert _run_stdlib(source) == "true\n"


# -- Cycle 4 (stdlib): io module — input() ----------------------------------


class TestIOInput:
    """Verify the io module's input() function."""

    def test_input_no_prompt(self) -> None:
        """input() with no prompt reads a line from stdin."""
        source = 'import "io"\nlet name = input()\nprint(name)'
        output = run_source_with_stdlib(  # type: ignore[no-any-return]
            source, input_stream=StringIO("Alice\n")
        )
        assert output == "Alice\n"

    def test_input_with_prompt(self) -> None:
        """input('prompt') prints the prompt then reads a line."""
        source = 'import "io"\nlet name = input("What? ")\nprint(name)'
        output = run_source_with_stdlib(  # type: ignore[no-any-return]
            source, input_stream=StringIO("Bob\n")
        )
        assert output == "What? Bob\n"

    def test_input_strips_newline(self) -> None:
        """input() strips the trailing newline from input."""
        source = 'import "io"\nlet x = input()\nprint(x + "!")'
        output = run_source_with_stdlib(  # type: ignore[no-any-return]
            source, input_stream=StringIO("hello\n")
        )
        assert output == "hello!\n"

    def test_input_from_import(self) -> None:
        """From 'io' import input brings in input function."""
        source = 'from "io" import input\nlet x = input()\nprint(x)'
        output = run_source_with_stdlib(  # type: ignore[no-any-return]
            source, input_stream=StringIO("world\n")
        )
        assert output == "world\n"

    def test_input_used_in_expression(self) -> None:
        """input() result can be used in string concatenation."""
        source = 'import "io"\nlet name = input("Name? ")\nprint("Hello, " + name)'
        output = run_source_with_stdlib(  # type: ignore[no-any-return]
            source, input_stream=StringIO("Pebble\n")
        )
        assert output == "Name? Hello, Pebble\n"


# -- Cycle 5 (stdlib): Edge cases + REPL + errors ---------------------------


class TestStdlibEdgeCases:
    """Edge cases for stdlib import and usage."""

    def test_from_import_only_sqrt_abs_unavailable(self) -> None:
        """From 'math' import sqrt — abs is not available."""
        source = 'from "math" import sqrt\nprint(abs(-5))'
        with pytest.raises(SemanticError, match="Undeclared function 'abs'"):
            _run_stdlib(source)

    def test_from_import_only_pi_sqrt_unavailable(self) -> None:
        """From 'math' import pi — sqrt is not available."""
        source = 'from "math" import pi\nprint(sqrt(16))'
        with pytest.raises(SemanticError, match="Undeclared function 'sqrt'"):
            _run_stdlib(source)

    def test_unknown_module_import_error(self) -> None:
        """Import 'unknown' raises PebbleImportError when no .pbl file exists."""
        source = 'import "unknown"'
        with pytest.raises(PebbleImportError, match="not found"):
            _run_stdlib(source)

    def test_stdlib_wrong_arity(self) -> None:
        """Calling sqrt with wrong arity raises SemanticError."""
        source = 'import "math"\nprint(sqrt(1, 2))'
        with pytest.raises(SemanticError, match="expects 1"):
            _run_stdlib(source)

    def test_stdlib_runtime_type_error(self) -> None:
        """Calling sqrt with a string raises PebbleRuntimeError."""
        source = 'import "math"\nsqrt("hello")'
        with pytest.raises(PebbleRuntimeError, match="requires a number"):
            _run_stdlib(source)

    def test_math_functions_in_while_loop(self) -> None:
        """Math functions work inside while loops."""
        source = """\
import "math"
let x = 100
let count = 0
while x > 1 {
    x = floor(x / 2)
    count = count + 1
}
print(count)"""
        output = _run_stdlib(source)
        expected_count = 6
        assert output == f"{expected_count}\n"

    def test_math_functions_in_if(self) -> None:
        """Math functions work inside if conditions."""
        source = 'import "math"\nif abs(-3) > 2 {\n    print("yes")\n}'
        assert _run_stdlib(source) == "yes\n"

    def test_from_import_mix_function_and_constant(self) -> None:
        """From 'math' import sqrt, pi brings in both."""
        source = 'from "math" import sqrt, pi\nprint(sqrt(4))\nprint(pi > 3)'
        assert _run_stdlib(source) == "2.0\ntrue\n"

    def test_import_math_and_io_together(self) -> None:
        """Both math and io can be imported in the same program."""
        source = 'import "math"\nimport "io"\nlet x = input()\nprint(sqrt(int(x)))'
        output = run_source_with_stdlib(  # type: ignore[no-any-return]
            source, input_stream=StringIO("25\n")
        )
        assert output == "5.0\n"


class TestStdlibREPL:
    """Verify stdlib works across REPL evaluations."""

    def test_repl_import_then_use(self) -> None:
        """Import in one eval, use in the next."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line('import "math"')
        r.eval_line("print(sqrt(16))")
        assert buf.getvalue() == "4.0\n"

    def test_repl_from_import_then_use(self) -> None:
        """from-import in one eval, use in the next."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line('from "math" import pi')
        r.eval_line("print(pi > 3)")
        assert buf.getvalue() == "true\n"

    def test_repl_constant_persists(self) -> None:
        """Stdlib constants persist across REPL evaluations."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line('import "math"')
        r.eval_line("let x = pi * 2")
        r.eval_line("print(x > 6)")
        assert buf.getvalue() == "true\n"

    def test_repl_stdlib_with_user_functions(self) -> None:
        """Stdlib functions work alongside user-defined functions in REPL."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line('import "math"')
        r.eval_line("fn hypotenuse(a, b) { return sqrt(a * a + b * b) }")
        r.eval_line("print(hypotenuse(3, 4))")
        assert buf.getvalue() == "5.0\n"


# ---------------------------------------------------------------------------
# Bug regression: math_pow with complex results
# ---------------------------------------------------------------------------


class TestMathPowComplexGuard:
    """Verify pow() rejects negative base with fractional exponent."""

    def test_pow_complex_result_raises(self) -> None:
        """``pow(-1, 0.5)`` raises instead of returning a complex number."""
        with pytest.raises(PebbleRuntimeError, match="complex result"):
            run_source_with_stdlib('import "math"\nprint(pow(-1, 0.5))')

    def test_pow_negative_base_integer_exponent_ok(self) -> None:
        """``pow(-2, 3)`` is fine: -8."""
        output = run_source_with_stdlib('import "math"\nprint(pow(-2, 3))')  # type: ignore[no-any-return]
        assert output == "-8\n"
