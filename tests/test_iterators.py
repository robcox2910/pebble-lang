"""Tests for iterators and generators in Pebble."""

from io import StringIO

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import FunctionDef, YieldStatement
from pebble.errors import PebbleRuntimeError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.repl import Repl
from pebble.tokens import TokenKind
from tests.conftest import run_source

# -- Named constants ----------------------------------------------------------

FIRST_LINE = 1
FIRST_COLUMN = 1


# =============================================================================
# Cycle 1: Tokens + AST + Parser + Analyzer
# =============================================================================


class TestYieldToken:
    """Verify the YIELD token kind and keyword mapping."""

    def test_yield_in_token_kind(self) -> None:
        """YIELD should be a member of TokenKind."""
        assert TokenKind.YIELD == "YIELD"

    def test_yield_keyword_maps(self) -> None:
        """The keyword 'yield' should lex as YIELD."""
        tokens = Lexer("yield").tokenize()
        assert tokens[0].kind == TokenKind.YIELD


class TestYieldParser:
    """Verify that yield statements parse correctly."""

    def test_yield_expression(self) -> None:
        """``yield expr`` should produce a YieldStatement with a value."""
        source = "fn gen() { yield 42 }"
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        fn_def = program.statements[0]
        assert isinstance(fn_def, FunctionDef)
        stmt = fn_def.body[0]
        assert isinstance(stmt, YieldStatement)
        assert stmt.value is not None

    def test_bare_yield(self) -> None:
        """``yield`` with no expression should produce value=None."""
        source = "fn gen() { yield\n }"
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        fn_def = program.statements[0]
        assert isinstance(fn_def, FunctionDef)
        stmt = fn_def.body[0]
        assert isinstance(stmt, YieldStatement)
        assert stmt.value is None


class TestYieldAnalyzer:
    """Verify semantic analysis of yield statements."""

    def test_yield_outside_function(self) -> None:
        """``yield`` at top level should be a semantic error."""
        source = "yield 1"
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        with pytest.raises(SemanticError, match="outside function"):
            SemanticAnalyzer().analyze(program)

    def test_yield_inside_try(self) -> None:
        """``yield`` inside a try block should be a semantic error."""
        source = """\
fn gen() {
    try {
        yield 1
    } catch e {
        print(e)
    }
}
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        with pytest.raises(SemanticError, match="try"):
            SemanticAnalyzer().analyze(program)

    def test_yield_inside_function_is_valid(self) -> None:
        """``yield`` inside a function should pass analysis."""
        source = """\
fn gen() {
    yield 1
    yield 2
}
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        SemanticAnalyzer().analyze(program)  # should not raise


# =============================================================================
# Cycle 2-5: Full end-to-end generator tests
# =============================================================================


class TestGeneratorBasic:
    """Test basic generator creation and next() advancement."""

    def test_next_returns_yielded_values(self) -> None:
        """next() should return successive yielded values."""
        source = """\
fn gen() {
    yield 10
    yield 20
    yield 30
}
let g = gen()
print(next(g))
print(next(g))
print(next(g))
"""
        assert run_source(source) == "10\n20\n30\n"

    def test_generator_exhaustion_error(self) -> None:
        """next() on an exhausted generator should raise an error."""
        source = """\
fn gen() {
    yield 1
}
let g = gen()
next(g)
next(g)
"""
        with pytest.raises(PebbleRuntimeError, match="exhausted"):
            run_source(source)

    def test_bare_yield_produces_null(self) -> None:
        """A bare yield should produce null."""
        source = """\
fn gen() {
    yield
}
let g = gen()
print(next(g))
"""
        assert run_source(source) == "null\n"


class TestGeneratorWithParams:
    """Test generators that take parameters."""

    def test_generator_with_parameter(self) -> None:
        """Generator functions should accept parameters."""
        source = """\
fn count_up(n) {
    let i = 0
    while i < n {
        yield i
        i = i + 1
    }
}
let g = count_up(3)
print(next(g))
print(next(g))
print(next(g))
"""
        assert run_source(source) == "0\n1\n2\n"

    def test_generator_with_range_loop(self) -> None:
        """Generators using for-in-range should work."""
        source = """\
fn squares(n) {
    for i in range(n) {
        yield i * i
    }
}
let g = squares(4)
print(next(g))
print(next(g))
print(next(g))
print(next(g))
"""
        assert run_source(source) == "0\n1\n4\n9\n"


class TestForIterLoop:
    """Test for-in loops with general iterables (lists and strings)."""

    def test_for_in_list(self) -> None:
        """for-in over a list should iterate each element."""
        source = """\
for x in [10, 20, 30] {
    print(x)
}
"""
        assert run_source(source) == "10\n20\n30\n"

    def test_for_in_string(self) -> None:
        """for-in over a string should iterate each character."""
        source = """\
for ch in "abc" {
    print(ch)
}
"""
        assert run_source(source) == "a\nb\nc\n"

    def test_for_in_empty_list(self) -> None:
        """for-in over an empty list should produce no output."""
        source = """\
for x in [] {
    print(x)
}
print("done")
"""
        assert run_source(source) == "done\n"

    def test_for_in_empty_string(self) -> None:
        """for-in over an empty string should produce no output."""
        source = """\
for ch in "" {
    print(ch)
}
print("done")
"""
        assert run_source(source) == "done\n"

    def test_for_in_generator(self) -> None:
        """for-in over a generator should consume all yielded values."""
        source = """\
fn gen() {
    yield 1
    yield 2
    yield 3
}
for val in gen() {
    print(val)
}
"""
        assert run_source(source) == "1\n2\n3\n"

    def test_for_in_list_variable(self) -> None:
        """for-in over a list stored in a variable should work."""
        source = """\
let xs = [4, 5, 6]
for x in xs {
    print(x)
}
"""
        assert run_source(source) == "4\n5\n6\n"

    def test_nested_for_iter_loops(self) -> None:
        """Nested for-in loops should each maintain their own iterator."""
        source = """\
for x in [1, 2] {
    for y in [10, 20] {
        print(x * y)
    }
}
"""
        assert run_source(source) == "10\n20\n20\n40\n"

    def test_break_in_for_iter(self) -> None:
        """Break should exit a for-iter loop early."""
        source = """\
for x in [1, 2, 3, 4, 5] {
    if x == 3 {
        break
    }
    print(x)
}
"""
        assert run_source(source) == "1\n2\n"

    def test_continue_in_for_iter(self) -> None:
        """Continue should skip to the next iteration in a for-iter loop."""
        source = """\
for x in [1, 2, 3, 4, 5] {
    if x == 3 {
        continue
    }
    print(x)
}
"""
        assert run_source(source) == "1\n2\n4\n5\n"

    def test_iterate_over_non_iterable_error(self) -> None:
        """Iterating over a non-iterable (int) should raise a runtime error."""
        source = """\
for x in 42 {
    print(x)
}
"""
        with pytest.raises(PebbleRuntimeError, match="Cannot iterate"):
            run_source(source)


class TestListComprehensionIter:
    """Test list comprehensions with general iterables."""

    def test_comprehension_over_list(self) -> None:
        """List comprehension over a list should work."""
        source = """\
let doubled = [x * 2 for x in [1, 2, 3]]
print(doubled)
"""
        assert run_source(source) == "[2, 4, 6]\n"

    def test_comprehension_over_string(self) -> None:
        """List comprehension over a string should work."""
        source = """\
let chars = [ch for ch in "hi"]
print(chars)
"""
        assert run_source(source) == "[h, i]\n"

    def test_comprehension_over_generator(self) -> None:
        """List comprehension over a generator should work."""
        source = """\
fn gen() {
    yield 1
    yield 2
    yield 3
}
let result = [x * 10 for x in gen()]
print(result)
"""
        assert run_source(source) == "[10, 20, 30]\n"

    def test_comprehension_with_filter_over_list(self) -> None:
        """Filtered list comprehension over a list should work."""
        source = """\
let evens = [x for x in [1, 2, 3, 4, 5, 6] if x % 2 == 0]
print(evens)
"""
        assert run_source(source) == "[2, 4, 6]\n"


class TestGeneratorClosure:
    """Test generators that capture variables from enclosing scope."""

    def test_generator_captures_variable(self) -> None:
        """Generator should capture variables from enclosing scope."""
        source = """\
fn make_counter(start) {
    fn counter() {
        let i = start
        while i < start + 3 {
            yield i
            i = i + 1
        }
    }
    return counter
}
let c = make_counter(10)
let g = c()
print(next(g))
print(next(g))
print(next(g))
"""
        assert run_source(source) == "10\n11\n12\n"


class TestNextBuiltin:
    """Test the next() builtin function."""

    def test_next_on_non_generator_error(self) -> None:
        """next() on a non-generator should raise a runtime error."""
        source = "next(42)"
        with pytest.raises(PebbleRuntimeError, match=r"next.*generator"):
            run_source(source)


class TestGeneratorFormatAndType:
    """Test type() and string formatting of generators and iterators."""

    def test_generator_type(self) -> None:
        """type() on a generator should return 'generator'."""
        source = """\
fn gen() { yield 1 }
let g = gen()
print(type(g))
"""
        assert run_source(source) == "generator\n"

    def test_generator_format(self) -> None:
        """Printing a generator should show <generator name>."""
        source = """\
fn gen() { yield 1 }
let g = gen()
print(g)
"""
        assert run_source(source) == "<generator gen>\n"


class TestRangeRegression:
    """Ensure existing range() for-loops still work after refactoring."""

    def test_range_one_arg(self) -> None:
        """range(n) in a for loop should still work."""
        source = """\
for i in range(3) {
    print(i)
}
"""
        assert run_source(source) == "0\n1\n2\n"

    def test_range_two_args(self) -> None:
        """range(start, stop) in a for loop should still work."""
        source = """\
for i in range(2, 5) {
    print(i)
}
"""
        assert run_source(source) == "2\n3\n4\n"

    def test_range_three_args(self) -> None:
        """range(start, stop, step) in a for loop should still work."""
        source = """\
for i in range(0, 10, 3) {
    print(i)
}
"""
        assert run_source(source) == "0\n3\n6\n9\n"

    def test_range_comprehension(self) -> None:
        """List comprehension with range() should still work."""
        source = """\
let xs = [i * i for i in range(4)]
print(xs)
"""
        assert run_source(source) == "[0, 1, 4, 9]\n"


class TestReplIterators:
    """Test generators and iterators in the REPL."""

    def test_repl_generator_across_evals(self) -> None:
        """Define a generator in one REPL eval and use it in another."""
        buf = StringIO()
        repl = Repl(output=buf)
        repl.eval_line("fn gen() { yield 10\nyield 20 }")
        repl.eval_line("let g = gen()")
        repl.eval_line("print(next(g))")
        repl.eval_line("print(next(g))")
        assert buf.getvalue() == "10\n20\n"

    def test_repl_for_iter_list(self) -> None:
        """for-in over a list should work in the REPL."""
        buf = StringIO()
        repl = Repl(output=buf)
        repl.eval_line("for x in [1, 2, 3] { print(x) }")
        assert buf.getvalue() == "1\n2\n3\n"
