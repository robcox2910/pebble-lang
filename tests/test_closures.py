"""Tests for closures (Phase 15).

Verify that inner functions can capture variables from enclosing scopes,
that Cell/Closure types work correctly, and that the full pipeline supports
first-class functions returned from and passed to other functions.
"""

import pytest

from pebble.builtins import Cell, Closure, format_value
from pebble.bytecode import CodeObject, OpCode
from tests.conftest import (
    analyze_with_context,
    compile_source,
    run_source,
)

# -- Named constants ----------------------------------------------------------

ONE = 1
LINE_1 = 1
LINE_2 = 2
LINE_3 = 3
CELL_COUNT = 2
VALUE_10 = 10
VALUE_42 = 42
VALUE_99 = 99


# -- Cycle 1: Cell + Closure data structures ----------------------------------


class TestCell:
    """Verify Cell is a mutable value container."""

    def test_create_with_value(self) -> None:
        """Cell wraps a value."""
        cell = Cell(VALUE_42)
        assert cell.value == VALUE_42

    def test_value_is_mutable(self) -> None:
        """Cell value can be updated."""
        cell = Cell(0)
        cell.value = VALUE_10
        assert cell.value == VALUE_10

    def test_shared_reference(self) -> None:
        """Two references to the same Cell share state."""
        cell = Cell(0)
        alias = cell
        alias.value = VALUE_99
        assert cell.value == VALUE_99


class TestClosure:
    """Verify Closure pairs a CodeObject with captured cells."""

    def test_create_closure(self) -> None:
        """Closure bundles code and cells."""
        code = CodeObject(name="test_fn")
        cells = [Cell(1), Cell(2)]
        closure = Closure(code=code, cells=cells)
        assert closure.code is code
        assert len(closure.cells) == CELL_COUNT

    def test_closure_is_frozen(self) -> None:
        """Closure instances are immutable."""
        closure = Closure(code=CodeObject(name="f"), cells=[])
        with pytest.raises(AttributeError):
            closure.code = CodeObject(name="g")  # type: ignore[misc]


class TestValueTypeExpansion:
    """Verify Value type includes Closure and format_value handles it."""

    def test_format_closure(self) -> None:
        """format_value displays closures as <fn name>."""
        code = CodeObject(name="increment")
        closure = Closure(code=code, cells=[])
        assert format_value(closure) == "<fn increment>"

    def test_type_builtin_closure(self) -> None:
        """type() returns 'fn' for closure values."""
        source = """\
fn make() {
    let x = 0
    fn inner() { return x }
    return inner
}
let f = make()
print(type(f))"""
        assert run_source(source) == "fn\n"


# -- Cycle 2: New opcodes + CodeObject fields --------------------------------


class TestClosureOpcodes:
    """Verify new opcodes and CodeObject closure fields."""

    def test_make_closure_opcode_exists(self) -> None:
        """MAKE_CLOSURE is a valid OpCode."""
        assert OpCode.MAKE_CLOSURE == "MAKE_CLOSURE"

    def test_load_cell_opcode_exists(self) -> None:
        """LOAD_CELL is a valid OpCode."""
        assert OpCode.LOAD_CELL == "LOAD_CELL"

    def test_store_cell_opcode_exists(self) -> None:
        """STORE_CELL is a valid OpCode."""
        assert OpCode.STORE_CELL == "STORE_CELL"

    def test_code_object_cell_variables_default(self) -> None:
        """CodeObject cell_variables defaults to empty list."""
        code = CodeObject(name="test")
        assert code.cell_variables == []

    def test_code_object_free_variables_default(self) -> None:
        """CodeObject free_variables defaults to empty list."""
        code = CodeObject(name="test")
        assert code.free_variables == []


# -- Cycle 3: Analyzer free-variable detection --------------------------------


class TestAnalyzerClosureDetection:
    """Verify the analyzer detects cross-function variable captures."""

    def test_no_closures_by_default(self) -> None:
        """Simple programs have empty cell_vars and free_vars."""
        _, analyzer = analyze_with_context("let x = 1\nprint(x)")
        assert analyzer.cell_vars == {}
        assert analyzer.free_vars == {}

    def test_simple_capture(self) -> None:
        """Inner function reading outer variable is detected."""
        source = """\
fn outer() {
    let x = 1
    fn inner() {
        return x
    }
    return inner
}"""
        _, analyzer = analyze_with_context(source)
        assert "x" in analyzer.cell_vars.get("outer", set())
        assert "x" in analyzer.free_vars.get("inner", set())

    def test_capture_via_reassignment(self) -> None:
        """Inner function writing outer variable is detected."""
        source = """\
fn outer() {
    let count = 0
    fn increment() {
        count = count + 1
        return count
    }
    return increment
}"""
        _, analyzer = analyze_with_context(source)
        assert "count" in analyzer.cell_vars.get("outer", set())
        assert "count" in analyzer.free_vars.get("increment", set())

    def test_parameter_capture(self) -> None:
        """Parameter captured by inner function is detected."""
        source = """\
fn make_adder(n) {
    fn add(x) {
        return n + x
    }
    return add
}"""
        _, analyzer = analyze_with_context(source)
        assert "n" in analyzer.cell_vars.get("make_adder", set())
        assert "n" in analyzer.free_vars.get("add", set())

    def test_no_capture_same_function(self) -> None:
        """Variable used in the same function is not a capture."""
        source = """\
fn f() {
    let x = 1
    return x
}"""
        _, analyzer = analyze_with_context(source)
        assert analyzer.cell_vars == {}
        assert analyzer.free_vars == {}


# -- Cycle 4: Compiler closure instructions -----------------------------------


class TestCompilerClosureInstructions:
    """Verify compiler emits cell and closure opcodes."""

    def test_cell_var_uses_store_cell(self) -> None:
        """Captured variable uses STORE_CELL instead of STORE_NAME."""
        source = """\
fn outer() {
    let x = 1
    fn inner() { return x }
    return inner
}"""
        compiled = compile_source(source)
        outer_code = compiled.functions["outer"]
        store_cell = [i for i in outer_code.instructions if i.opcode is OpCode.STORE_CELL]
        assert len(store_cell) >= ONE
        assert store_cell[0].operand == "x"

    def test_free_var_uses_load_cell(self) -> None:
        """Free variable in inner function uses LOAD_CELL."""
        source = """\
fn outer() {
    let x = 42
    fn inner() { return x }
    return inner
}"""
        compiled = compile_source(source)
        inner_code = compiled.functions["inner"]
        load_cell = [i for i in inner_code.instructions if i.opcode is OpCode.LOAD_CELL]
        assert len(load_cell) >= ONE
        assert load_cell[0].operand == "x"

    def test_make_closure_emitted(self) -> None:
        """MAKE_CLOSURE is emitted for functions with free variables."""
        source = """\
fn outer() {
    let x = 1
    fn inner() { return x }
    return inner
}"""
        compiled = compile_source(source)
        outer_code = compiled.functions["outer"]
        make_closure = [i for i in outer_code.instructions if i.opcode is OpCode.MAKE_CLOSURE]
        assert len(make_closure) == ONE
        assert make_closure[0].operand == "inner"

    def test_code_object_has_free_variables(self) -> None:
        """Inner function's CodeObject lists free variables."""
        source = """\
fn outer() {
    let x = 1
    fn inner() { return x }
    return inner
}"""
        compiled = compile_source(source)
        assert "x" in compiled.functions["inner"].free_variables

    def test_code_object_has_cell_variables(self) -> None:
        """Outer function's CodeObject lists cell variables."""
        source = """\
fn outer() {
    let x = 1
    fn inner() { return x }
    return inner
}"""
        compiled = compile_source(source)
        assert "x" in compiled.functions["outer"].cell_variables


# -- Cycle 5: VM closure execution -------------------------------------------


class TestVMClosureExecution:
    """Verify the VM correctly executes closures."""

    def test_simple_closure_read(self) -> None:
        """Closure reads a captured variable."""
        source = """\
fn make() {
    let x = 42
    fn get() { return x }
    return get
}
let f = make()
print(f())"""
        assert run_source(source) == "42\n"

    def test_closure_mutation(self) -> None:
        """Closure mutates a captured variable, changes persist."""
        source = """\
fn make_counter() {
    let count = 0
    fn increment() {
        count = count + 1
        return count
    }
    return increment
}
let inc = make_counter()
print(inc())
print(inc())
print(inc())"""
        assert run_source(source) == "1\n2\n3\n"

    def test_parameter_capture(self) -> None:
        """Closure captures a function parameter."""
        source = """\
fn make_adder(n) {
    fn add(x) {
        return n + x
    }
    return add
}
let add5 = make_adder(5)
print(add5(10))
print(add5(20))"""
        assert run_source(source) == "15\n25\n"

    def test_independent_closures(self) -> None:
        """Each call creates independent closure state."""
        source = """\
fn make_counter() {
    let count = 0
    fn increment() {
        count = count + 1
        return count
    }
    return increment
}
let a = make_counter()
let b = make_counter()
print(a())
print(a())
print(b())"""
        assert run_source(source) == "1\n2\n1\n"

    def test_closure_called_inside_defining_function(self) -> None:
        """Closure can be called inside the function that defines it."""
        source = """\
fn outer() {
    let x = 10
    fn inner() { return x }
    print(inner())
}
outer()"""
        assert run_source(source) == "10\n"

    def test_closure_with_multiple_captures(self) -> None:
        """Closure captures multiple variables."""
        source = """\
fn make(a, b) {
    fn compute(x) {
        return a + b + x
    }
    return compute
}
let f = make(10, 20)
print(f(3))"""
        assert run_source(source) == "33\n"

    def test_format_closure_value(self) -> None:
        """Printing a closure shows <fn name>."""
        source = """\
fn make() {
    let x = 0
    fn inner() { return x }
    return inner
}
let f = make()
print(f)"""
        assert run_source(source) == "<fn inner>\n"

    def test_regular_functions_still_work(self) -> None:
        """Non-closure functions are unaffected by closure support."""
        source = """\
fn add(a, b) { return a + b }
print(add(3, 4))"""
        assert run_source(source) == "7\n"

    def test_nested_function_no_capture(self) -> None:
        """Nested function without captures works as a regular function."""
        source = """\
fn outer() {
    fn inner(x) { return x + 1 }
    print(inner(5))
}
outer()"""
        assert run_source(source) == "6\n"


# -- Cycle 6: Integration & edge cases ---------------------------------------


class TestClosureIntegration:
    """End-to-end integration tests for closures."""

    def test_closure_in_loop(self) -> None:
        """Closure used inside a loop."""
        source = """\
fn make_counter() {
    let count = 0
    fn increment() {
        count = count + 1
        return count
    }
    return increment
}
let inc = make_counter()
for i in range(3) {
    print(inc())
}"""
        assert run_source(source) == "1\n2\n3\n"

    def test_closure_with_conditional(self) -> None:
        """Closure works correctly with conditional logic."""
        source = """\
fn make_toggle() {
    let state = 0
    fn toggle() {
        if state == 0 {
            state = 1
        } else {
            state = 0
        }
        return state
    }
    return toggle
}
let t = make_toggle()
print(t())
print(t())
print(t())"""
        assert run_source(source) == "1\n0\n1\n"

    def test_closure_with_while_loop(self) -> None:
        """Closure with while loop modifying captured state."""
        source = """\
fn make_summer() {
    let total = 0
    fn add(n) {
        total = total + n
        return total
    }
    return add
}
let sum = make_summer()
print(sum(10))
print(sum(20))
print(sum(5))"""
        assert run_source(source) == "10\n30\n35\n"

    def test_closure_with_list(self) -> None:
        """Closure captures a list and mutates it."""
        source = """\
fn make_collector() {
    let items = []
    fn add(item) {
        push(items, item)
        return items
    }
    return add
}
let collect = make_collector()
collect(1)
collect(2)
print(collect(3))"""
        assert run_source(source) == "[1, 2, 3]\n"
