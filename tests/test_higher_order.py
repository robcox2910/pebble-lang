"""Tests for higher-order builtins: map(), filter(), reduce() (Phase 17).

Verify that all functions are first-class values (passable by name),
and that map, filter, and reduce correctly invoke user-provided callbacks
via the VM's nested execution support.
"""

import pytest

from pebble.builtins import BUILTIN_ARITIES
from pebble.errors import PebbleRuntimeError, SemanticError
from tests.conftest import (  # pyright: ignore[reportMissingImports]
    run_source,  # pyright: ignore[reportUnknownVariableType]
)


def _run_source(source: str) -> str:
    """Compile and run *source*, return captured output."""
    return run_source(source)  # type: ignore[no-any-return]


# -- Named constants ----------------------------------------------------------

TOTAL_BUILTIN_COUNT = 14
MAP_ARITY = 2
FILTER_ARITY = 2
REDUCE_ARITY = 3


# -- Cycle 1: First-class functions -------------------------------------------


class TestFirstClassFunctions:
    """Verify that all functions (not just closures) are first-class values."""

    def test_assign_function_to_variable(self) -> None:
        """A named function can be stored in a variable."""
        source = """\
fn double(x) { return x * 2 }
let f = double
print(f(5))"""
        assert _run_source(source) == "10\n"

    def test_type_of_function(self) -> None:
        """type() returns 'fn' for a regular named function."""
        source = """\
fn greet(name) { return name }
print(type(greet))"""
        assert _run_source(source) == "fn\n"

    def test_pass_function_as_argument(self) -> None:
        """A named function can be passed to another function."""
        source = """\
fn double(x) { return x * 2 }
fn apply(f, val) { return f(val) }
print(apply(double, 5))"""
        assert _run_source(source) == "10\n"

    def test_function_in_list(self) -> None:
        """A named function can be stored in a list."""
        source = """\
fn inc(x) { return x + 1 }
let fns = [inc]
let f = fns[0]
print(f(10))"""
        assert _run_source(source) == "11\n"


# -- Cycle 2: map() ----------------------------------------------------------


class TestMapBuiltin:
    """Verify map(fn, list) -> list."""

    def test_map_inline_closure(self) -> None:
        """Apply map() with an inline closure to double each element."""
        source = """\
let result = map(fn(x) { return x * 2 }, [1, 2, 3])
print(result)"""
        assert _run_source(source) == "[2, 4, 6]\n"

    def test_map_named_function(self) -> None:
        """Apply map() with a named function."""
        source = """\
fn double(x) { return x * 2 }
let result = map(double, [1, 2, 3])
print(result)"""
        assert _run_source(source) == "[2, 4, 6]\n"

    def test_map_empty_list(self) -> None:
        """Apply map() over empty list to return empty list."""
        source = """\
let result = map(fn(x) { return x }, [])
print(result)"""
        assert _run_source(source) == "[]\n"

    def test_map_not_a_function_error(self) -> None:
        """Raise runtime error when map() gets a non-function first arg."""
        with pytest.raises(PebbleRuntimeError, match="expects a function"):
            _run_source("map(42, [1])")

    def test_map_not_a_list_error(self) -> None:
        """Raise runtime error when map() gets a non-list second arg."""
        with pytest.raises(PebbleRuntimeError, match="expects a list"):
            _run_source("map(fn(x) { return x }, 42)")

    def test_map_arity_in_registry(self) -> None:
        """Verify map() is registered with arity 2."""
        assert BUILTIN_ARITIES["map"] == MAP_ARITY


# -- Cycle 3: filter() -------------------------------------------------------


class TestFilterBuiltin:
    """Verify filter(fn, list) -> list."""

    def test_filter_inline_closure(self) -> None:
        """Keep elements where the predicate returns true."""
        source = """\
let result = filter(fn(x) { return x > 2 }, [1, 2, 3, 4])
print(result)"""
        assert _run_source(source) == "[3, 4]\n"

    def test_filter_named_function(self) -> None:
        """Apply filter() with a named predicate function."""
        source = """\
fn is_even(x) { return x % 2 == 0 }
let result = filter(is_even, [1, 2, 3, 4])
print(result)"""
        assert _run_source(source) == "[2, 4]\n"

    def test_filter_empty_list(self) -> None:
        """Apply filter() over empty list to return empty list."""
        source = """\
let result = filter(fn(x) { return true }, [])
print(result)"""
        assert _run_source(source) == "[]\n"

    def test_filter_none_match(self) -> None:
        """Return empty list when no elements match the predicate."""
        source = """\
let result = filter(fn(x) { return x > 100 }, [1, 2, 3])
print(result)"""
        assert _run_source(source) == "[]\n"

    def test_filter_not_a_function_error(self) -> None:
        """Raise runtime error when filter() gets a non-function first arg."""
        with pytest.raises(PebbleRuntimeError, match="expects a function"):
            _run_source('filter("nope", [1])')

    def test_filter_not_a_list_error(self) -> None:
        """Raise runtime error when filter() gets a non-list second arg."""
        with pytest.raises(PebbleRuntimeError, match="expects a list"):
            _run_source('filter(fn(x) { return true }, "abc")')

    def test_filter_arity_in_registry(self) -> None:
        """Verify filter() is registered with arity 2."""
        assert BUILTIN_ARITIES["filter"] == FILTER_ARITY


# -- Cycle 4: reduce() -------------------------------------------------------


class TestReduceBuiltin:
    """Verify reduce(fn, list, initial) -> value."""

    def test_reduce_sum(self) -> None:
        """Sum a list using reduce() with initial 0."""
        source = """\
let result = reduce(fn(a, b) { return a + b }, [1, 2, 3], 0)
print(result)"""
        assert _run_source(source) == "6\n"

    def test_reduce_named_function(self) -> None:
        """Apply reduce() with a named function."""
        source = """\
fn add(a, b) { return a + b }
let result = reduce(add, [1, 2, 3], 0)
print(result)"""
        assert _run_source(source) == "6\n"

    def test_reduce_empty_list(self) -> None:
        """Return the initial value when reduce() is applied to an empty list."""
        source = """\
let result = reduce(fn(a, b) { return a + b }, [], 10)
print(result)"""
        assert _run_source(source) == "10\n"

    def test_reduce_product(self) -> None:
        """Compute a product using reduce()."""
        source = """\
let result = reduce(fn(a, b) { return a * b }, [2, 3, 4], 1)
print(result)"""
        assert _run_source(source) == "24\n"

    def test_reduce_not_a_function_error(self) -> None:
        """Raise runtime error when reduce() gets a non-function first arg."""
        with pytest.raises(PebbleRuntimeError, match="expects a function"):
            _run_source("reduce(42, [1], 0)")

    def test_reduce_not_a_list_error(self) -> None:
        """Raise runtime error when reduce() gets a non-list second arg."""
        with pytest.raises(PebbleRuntimeError, match="expects a list"):
            _run_source("reduce(fn(a, b) { return a + b }, 42, 0)")

    def test_reduce_arity_in_registry(self) -> None:
        """Verify reduce() is registered with arity 3."""
        assert BUILTIN_ARITIES["reduce"] == REDUCE_ARITY


# -- Cycle 5: Integration ----------------------------------------------------


class TestHigherOrderIntegration:
    """End-to-end tests combining map, filter, reduce with closures."""

    def test_chained_map_reduce(self) -> None:
        """reduce(add, map(double, list), 0) chains correctly."""
        source = """\
fn double(x) { return x * 2 }
fn add(a, b) { return a + b }
let result = reduce(add, map(double, [1, 2, 3]), 0)
print(result)"""
        assert _run_source(source) == "12\n"

    def test_filter_then_map(self) -> None:
        """Apply map() over a filtered list."""
        source = """\
fn is_even(x) { return x % 2 == 0 }
fn double(x) { return x * 2 }
let result = map(double, filter(is_even, [1, 2, 3, 4]))
print(result)"""
        assert _run_source(source) == "[4, 8]\n"

    def test_closure_capturing_variable(self) -> None:
        """Higher-order builtin works with a closure that captures state."""
        source = """\
fn make_adder(n) {
    fn add(x) { return x + n }
    return add
}
let add10 = make_adder(10)
let result = map(add10, [1, 2, 3])
print(result)"""
        assert _run_source(source) == "[11, 12, 13]\n"

    def test_higher_order_with_dict_values(self) -> None:
        """Apply map() over dict values extracted with values()."""
        source = """\
let d = {"a": 1, "b": 2, "c": 3}
let vals = values(d)
let result = map(fn(x) { return x * 10 }, vals)
print(result)"""
        assert _run_source(source) == "[10, 20, 30]\n"

    def test_arity_validation_map(self) -> None:
        """map() with wrong number of arguments is caught by analyzer."""
        with pytest.raises(SemanticError, match="expects 2"):
            _run_source("map(fn(x) { return x })")

    def test_arity_validation_filter(self) -> None:
        """filter() with wrong number of arguments is caught by analyzer."""
        with pytest.raises(SemanticError, match="expects 2"):
            _run_source("filter(fn(x) { return x }, [1], 99)")

    def test_arity_validation_reduce(self) -> None:
        """reduce() with wrong number of arguments is caught by analyzer."""
        with pytest.raises(SemanticError, match="expects 3"):
            _run_source("reduce(fn(a, b) { return a + b }, [1])")

    def test_builtin_arities_count(self) -> None:
        """BUILTIN_ARITIES includes all 14 builtins after adding map/filter/reduce."""
        assert len(BUILTIN_ARITIES) == TOTAL_BUILTIN_COUNT

    def test_existing_closures_still_work(self) -> None:
        """Existing closure functionality is not broken."""
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
        assert _run_source(source) == "1\n2\n3\n"

    def test_regular_functions_still_work(self) -> None:
        """Regular function calls are unaffected."""
        source = """\
fn add(a, b) { return a + b }
print(add(3, 4))"""
        assert _run_source(source) == "7\n"
