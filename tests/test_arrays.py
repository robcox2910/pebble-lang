"""Tests for arrays / lists (Phase 12).

Cover lexer tokenization, parser AST construction, analyzer validation,
compiler bytecode generation, and VM execution of array operations.
"""

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import ArrayLiteral, Expression, IndexAccess, IntegerLiteral, SliceAccess
from pebble.bytecode import Instruction, OpCode
from pebble.compiler import Compiler
from pebble.errors import PebbleRuntimeError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.tokens import TokenKind
from tests.conftest import (  # pyright: ignore[reportMissingImports]
    run_source,  # pyright: ignore[reportUnknownVariableType]
)


def _run_source(source: str) -> str:
    """Compile and run *source*, return captured output."""
    return run_source(source)  # type: ignore[no-any-return]


TEN = 10

# -- Named constants ----------------------------------------------------------

ONE = 1
TWO = 2
THREE = 3
FOUR = 4
FIVE = 5


# -- Helpers ------------------------------------------------------------------


def _kinds(source: str) -> list[TokenKind]:
    """Return just the token kinds for *source* (excluding EOF)."""
    tokens = Lexer(source).tokenize()
    return [t.kind for t in tokens if t.kind != TokenKind.EOF]


def _parse_expr(source: str) -> Expression:
    """Lex and parse a single expression from *source*."""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse_expression()


def _compile_instructions(source: str) -> list[Instruction]:
    """Return the main instruction list for *source*."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzed = SemanticAnalyzer().analyze(program)
    return Compiler().compile(analyzed).main.instructions


# -- Cycle 1: Tokens + Lexer --------------------------------------------------


class TestLexerBrackets:
    """Verify ``[`` and ``]`` tokenize correctly."""

    def test_left_bracket(self) -> None:
        """``[`` tokenizes as LEFT_BRACKET."""
        assert _kinds("[") == [TokenKind.LEFT_BRACKET]

    def test_right_bracket(self) -> None:
        """``]`` tokenizes as RIGHT_BRACKET."""
        assert _kinds("]") == [TokenKind.RIGHT_BRACKET]

    def test_array_literal_tokens(self) -> None:
        """``[1, 2, 3]`` tokenizes correctly."""
        assert _kinds("[1, 2, 3]") == [
            TokenKind.LEFT_BRACKET,
            TokenKind.INTEGER,
            TokenKind.COMMA,
            TokenKind.INTEGER,
            TokenKind.COMMA,
            TokenKind.INTEGER,
            TokenKind.RIGHT_BRACKET,
        ]


# -- Cycle 2: Parser - array literal ------------------------------------------


class TestParserArrayLiteral:
    """Verify parsing of array literals."""

    def test_array_with_elements(self) -> None:
        """``[1, 2, 3]`` parses to ArrayLiteral with 3 elements."""
        node = _parse_expr("[1, 2, 3]")
        assert isinstance(node, ArrayLiteral)
        assert len(node.elements) == THREE
        assert all(isinstance(e, IntegerLiteral) for e in node.elements)

    def test_empty_array(self) -> None:
        """``[]`` parses to ArrayLiteral with 0 elements."""
        node = _parse_expr("[]")
        assert isinstance(node, ArrayLiteral)
        assert node.elements == []

    def test_single_element_array(self) -> None:
        """``[42]`` parses to ArrayLiteral with 1 element."""
        node = _parse_expr("[42]")
        assert isinstance(node, ArrayLiteral)
        assert len(node.elements) == ONE


# -- Cycle 3: Compiler + VM - array creation -----------------------------------


class TestVMArrayCreation:
    """Verify array creation and printing."""

    def test_print_array(self) -> None:
        """``print([1, 2, 3])`` outputs ``[1, 2, 3]``."""
        assert _run_source("print([1, 2, 3])") == "[1, 2, 3]\n"

    def test_print_empty_array(self) -> None:
        """``print([])`` outputs ``[]``."""
        assert _run_source("print([])") == "[]\n"

    def test_array_in_variable(self) -> None:
        """Store an array in a variable and print it."""
        source = "let xs = [10, 20, 30]\nprint(xs)"
        assert _run_source(source) == "[10, 20, 30]\n"

    def test_nested_array(self) -> None:
        """Nested arrays print correctly."""
        source = "print([[1, 2], [3, 4]])"
        assert _run_source(source) == "[[1, 2], [3, 4]]\n"

    def test_array_with_mixed_types(self) -> None:
        """Arrays can hold mixed types."""
        source = 'print([1, "hello", true])'
        assert _run_source(source) == "[1, hello, true]\n"

    def test_build_list_opcode(self) -> None:
        """Compiler emits BUILD_LIST with correct count."""
        ins = _compile_instructions("let xs = [1, 2, 3]")
        build_list_ops = [i for i in ins if i.opcode is OpCode.BUILD_LIST]
        assert len(build_list_ops) == ONE
        assert build_list_ops[0].operand == THREE


# -- Cycle 4: Parser + VM - index access --------------------------------------


class TestParserIndexAccess:
    """Verify parsing of index access expressions."""

    def test_index_access_ast(self) -> None:
        """``xs[0]`` parses to IndexAccess."""
        node = _parse_expr("xs[0]")
        assert isinstance(node, IndexAccess)

    def test_chained_index_access(self) -> None:
        """``xs[0][1]`` parses to nested IndexAccess."""
        node = _parse_expr("xs[0][1]")
        assert isinstance(node, IndexAccess)
        assert isinstance(node.target, IndexAccess)


class TestVMIndexAccess:
    """Verify index access at runtime."""

    def test_read_first_element(self) -> None:
        """``xs[0]`` reads the first element."""
        source = "let xs = [10, 20, 30]\nprint(xs[0])"
        assert _run_source(source) == "10\n"

    def test_read_last_element(self) -> None:
        """``xs[2]`` reads the last element."""
        source = "let xs = [10, 20, 30]\nprint(xs[2])"
        assert _run_source(source) == "30\n"

    def test_index_with_variable(self) -> None:
        """Index access works with a variable index."""
        source = "let xs = [10, 20, 30]\nlet i = 1\nprint(xs[i])"
        assert _run_source(source) == "20\n"

    def test_index_out_of_bounds(self) -> None:
        """Out-of-bounds index raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="out of bounds"):
            _run_source("let xs = [1, 2, 3]\nprint(xs[5])")

    def test_index_negative_out_of_bounds(self) -> None:
        """Excessively negative index raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="out of bounds"):
            _run_source("let xs = [1, 2, 3]\nprint(xs[-10])")


# -- Cycle 5: Index assignment -------------------------------------------------


class TestVMIndexAssignment:
    """Verify index assignment at runtime."""

    def test_modify_element(self) -> None:
        """``xs[0] = 42`` modifies the list in place."""
        source = "let xs = [1, 2, 3]\nxs[0] = 42\nprint(xs)"
        assert _run_source(source) == "[42, 2, 3]\n"

    def test_modify_middle_element(self) -> None:
        """``xs[1] = 99`` modifies the middle element."""
        source = "let xs = [10, 20, 30]\nxs[1] = 99\nprint(xs[1])"
        assert _run_source(source) == "99\n"

    def test_index_set_out_of_bounds(self) -> None:
        """Out-of-bounds index assignment raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="out of bounds"):
            _run_source("let xs = [1]\nxs[5] = 99")


# -- Cycle 6: len() builtin ---------------------------------------------------


class TestVMLenBuiltin:
    """Verify the len() built-in function."""

    def test_len_of_list(self) -> None:
        """``len([1, 2, 3])`` returns 3."""
        assert _run_source("print(len([1, 2, 3]))") == "3\n"

    def test_len_of_empty_list(self) -> None:
        """``len([])`` returns 0."""
        assert _run_source("print(len([]))") == "0\n"

    def test_len_of_string(self) -> None:
        """``len("hello")`` returns 5."""
        assert _run_source('print(len("hello"))') == "5\n"

    def test_len_of_variable(self) -> None:
        """``len(xs)`` works with a variable."""
        source = "let xs = [1, 2, 3, 4]\nprint(len(xs))"
        assert _run_source(source) == "4\n"


# -- Negative Indexing: Read --------------------------------------------------


class TestNegativeIndexGet:
    """Verify negative index read access."""

    def test_last_element(self) -> None:
        """``xs[-1]`` returns the last element."""
        source = "let xs = [10, 20, 30]\nprint(xs[-1])"
        assert _run_source(source) == "30\n"

    def test_second_to_last(self) -> None:
        """``xs[-2]`` returns the second-to-last element."""
        source = "let xs = [10, 20, 30]\nprint(xs[-2])"
        assert _run_source(source) == "20\n"

    def test_negative_len_returns_first(self) -> None:
        """``xs[-len(xs)]`` returns the first element (boundary)."""
        source = "let xs = [10, 20, 30]\nprint(xs[-3])"
        assert _run_source(source) == "10\n"

    def test_too_negative_raises(self) -> None:
        """``xs[-(len+1)]`` raises out-of-bounds error."""
        with pytest.raises(PebbleRuntimeError, match="out of bounds"):
            _run_source("let xs = [10, 20, 30]\nprint(xs[-4])")


# -- Negative Indexing: Write -------------------------------------------------


class TestNegativeIndexSet:
    """Verify negative index write access."""

    def test_set_last_element(self) -> None:
        """``xs[-1] = 99`` modifies the last element."""
        source = "let xs = [10, 20, 30]\nxs[-1] = 99\nprint(xs)"
        assert _run_source(source) == "[10, 20, 99]\n"

    def test_set_second_to_last(self) -> None:
        """``xs[-2] = 42`` modifies the second-to-last element."""
        source = "let xs = [10, 20, 30]\nxs[-2] = 42\nprint(xs)"
        assert _run_source(source) == "[10, 42, 30]\n"

    def test_set_too_negative_raises(self) -> None:
        """``xs[-(len+1)] = 0`` raises out-of-bounds error."""
        with pytest.raises(PebbleRuntimeError, match="out of bounds"):
            _run_source("let xs = [10, 20, 30]\nxs[-4] = 0")


# -- Negative Indexing: Integration -------------------------------------------


class TestNegativeIndexIntegration:
    """Integration tests for negative indexing with other features."""

    def test_negative_index_with_variable(self) -> None:
        """Negative index via a variable expression: ``xs[-i]``."""
        source = "let xs = [10, 20, 30]\nlet i = 1\nprint(xs[-i])"
        assert _run_source(source) == "30\n"

    def test_equivalence_with_len(self) -> None:
        """``xs[-1]`` and ``xs[len(xs) - 1]`` return the same value."""
        source = """\
let xs = [10, 20, 30]
let a = xs[-1]
let b = xs[len(xs) - 1]
print(a == b)"""
        assert _run_source(source) == "true\n"

    def test_positive_indexing_still_works(self) -> None:
        """Regression: positive indexing unchanged."""
        source = """\
let xs = [10, 20, 30, 40]
print(xs[0])
print(xs[1])
print(xs[2])
print(xs[3])"""
        assert _run_source(source) == "10\n20\n30\n40\n"


# -- Cycle 7: Integration -----------------------------------------------------


class TestArrayIntegration:
    """End-to-end tests combining arrays with other features."""

    def test_array_in_for_loop(self) -> None:
        """Use array with index access in a for loop."""
        source = """\
let xs = [10, 20, 30]
for i in range(3) {
    print(xs[i])
}"""
        assert _run_source(source) == "10\n20\n30\n"

    def test_array_in_function(self) -> None:
        """Pass an array to a function and access elements."""
        source = """\
fn first(xs) { return xs[0] }
print(first([42, 99]))"""
        assert _run_source(source) == "42\n"

    def test_array_with_interpolation(self) -> None:
        """Use array values in string interpolation."""
        source = """\
let xs = [1, 2, 3]
print("first: {xs[0]}, len: {len(xs)}")"""
        assert _run_source(source) == "first: 1, len: 3\n"

    def test_modify_array_in_loop(self) -> None:
        """Modify array elements in a loop."""
        source = """\
let xs = [0, 0, 0]
for i in range(3) {
    xs[i] = i * 10
}
print(xs)"""
        assert _run_source(source) == "[0, 10, 20]\n"


# -- Slicing: Parser ----------------------------------------------------------


class TestParserSliceAccess:
    """Verify parsing of slice expressions."""

    def test_start_stop(self) -> None:
        """``xs[1:3]`` parses to SliceAccess with start and stop."""
        node = _parse_expr("xs[1:3]")
        assert isinstance(node, SliceAccess)
        assert isinstance(node.start, IntegerLiteral)
        assert node.start.value == ONE
        assert isinstance(node.stop, IntegerLiteral)
        assert node.stop.value == THREE
        assert node.step is None

    def test_stop_only(self) -> None:
        """``xs[:3]`` parses to SliceAccess with stop only."""
        node = _parse_expr("xs[:3]")
        assert isinstance(node, SliceAccess)
        assert node.start is None
        assert isinstance(node.stop, IntegerLiteral)
        assert node.stop.value == THREE
        assert node.step is None

    def test_start_only(self) -> None:
        """``xs[1:]`` parses to SliceAccess with start only."""
        node = _parse_expr("xs[1:]")
        assert isinstance(node, SliceAccess)
        assert isinstance(node.start, IntegerLiteral)
        assert node.start.value == ONE
        assert node.stop is None
        assert node.step is None

    def test_all_none(self) -> None:
        """``xs[:]`` parses to SliceAccess with all components None."""
        node = _parse_expr("xs[:]")
        assert isinstance(node, SliceAccess)
        assert node.start is None
        assert node.stop is None
        assert node.step is None

    def test_step_only(self) -> None:
        """``xs[::2]`` parses to SliceAccess with step only."""
        node = _parse_expr("xs[::2]")
        assert isinstance(node, SliceAccess)
        assert node.start is None
        assert node.stop is None
        assert isinstance(node.step, IntegerLiteral)
        assert node.step.value == TWO

    def test_all_present(self) -> None:
        """``xs[1:3:2]`` parses to SliceAccess with all components."""
        node = _parse_expr("xs[1:3:2]")
        assert isinstance(node, SliceAccess)
        assert isinstance(node.start, IntegerLiteral)
        assert node.start.value == ONE
        assert isinstance(node.stop, IntegerLiteral)
        assert node.stop.value == THREE
        assert isinstance(node.step, IntegerLiteral)
        assert node.step.value == TWO

    def test_plain_index_still_works(self) -> None:
        """``xs[0]`` still parses as IndexAccess (regression check)."""
        node = _parse_expr("xs[0]")
        assert isinstance(node, IndexAccess)


# -- Slicing: Analyzer -------------------------------------------------------


class TestAnalyzerSlice:
    """Verify semantic analysis catches errors in slices."""

    def test_undeclared_in_slice(self) -> None:
        """Undeclared variable inside a slice raises SemanticError."""
        with pytest.raises(SemanticError, match="Undeclared variable 'unknown'"):
            _run_source("let xs = [1, 2, 3]\nprint(xs[unknown:])")


# -- Slicing: Compiler -------------------------------------------------------


class TestCompilerSlice:
    """Verify the compiler emits SLICE_GET for slices."""

    def test_slice_emits_opcode(self) -> None:
        """``xs[1:3]`` emits a SLICE_GET opcode."""
        ins = _compile_instructions("let xs = [1, 2, 3]\nprint(xs[1:3])")
        slice_ops = [i for i in ins if i.opcode is OpCode.SLICE_GET]
        assert len(slice_ops) == ONE


# -- Slicing: VM — list slicing -----------------------------------------------


class TestVMListSlicing:
    """Verify list slicing at runtime."""

    def test_start_stop(self) -> None:
        """``xs[1:3]`` extracts elements at index 1 and 2."""
        source = "let xs = [10, 20, 30, 40, 50]\nprint(xs[1:3])"
        assert _run_source(source) == "[20, 30]\n"

    def test_stop_only(self) -> None:
        """``xs[:3]`` takes the first three elements."""
        source = "let xs = [10, 20, 30, 40, 50]\nprint(xs[:3])"
        assert _run_source(source) == "[10, 20, 30]\n"

    def test_start_only(self) -> None:
        """``xs[2:]`` takes from index 2 to the end."""
        source = "let xs = [10, 20, 30, 40, 50]\nprint(xs[2:])"
        assert _run_source(source) == "[30, 40, 50]\n"

    def test_copy(self) -> None:
        """``xs[:]`` returns a copy of the full list."""
        source = "let xs = [10, 20, 30, 40, 50]\nprint(xs[:])"
        assert _run_source(source) == "[10, 20, 30, 40, 50]\n"

    def test_step(self) -> None:
        """``xs[::2]`` takes every other element."""
        source = "let xs = [10, 20, 30, 40, 50]\nprint(xs[::2])"
        assert _run_source(source) == "[10, 30, 50]\n"

    def test_start_stop_step(self) -> None:
        """``xs[1:4:2]`` takes elements 1 and 3."""
        source = "let xs = [10, 20, 30, 40, 50]\nprint(xs[1:4:2])"
        assert _run_source(source) == "[20, 40]\n"

    def test_negative_start(self) -> None:
        """``xs[-2:]`` takes the last two elements."""
        source = "let xs = [10, 20, 30, 40, 50]\nprint(xs[-2:])"
        assert _run_source(source) == "[40, 50]\n"

    def test_negative_stop(self) -> None:
        """``xs[:-1]`` takes all but the last element."""
        source = "let xs = [10, 20, 30, 40, 50]\nprint(xs[:-1])"
        assert _run_source(source) == "[10, 20, 30, 40]\n"

    def test_reverse(self) -> None:
        """``xs[::-1]`` reverses the list."""
        source = "let xs = [10, 20, 30, 40, 50]\nprint(xs[::-1])"
        assert _run_source(source) == "[50, 40, 30, 20, 10]\n"

    def test_out_of_bounds_clamps(self) -> None:
        """``xs[0:100]`` silently clamps to the list length."""
        source = "let xs = [10, 20, 30]\nprint(xs[0:100])"
        assert _run_source(source) == "[10, 20, 30]\n"

    def test_step_zero_errors(self) -> None:
        """``xs[::0]`` raises a runtime error."""
        with pytest.raises(PebbleRuntimeError, match="Slice step cannot be zero"):
            _run_source("let xs = [1, 2, 3]\nprint(xs[::0])")


# -- Slicing: VM — string slicing --------------------------------------------


class TestVMStringSlicing:
    """Verify string slicing at runtime."""

    def test_start_stop(self) -> None:
        """``s[1:4]`` extracts a substring."""
        source = 'let s = "hello"\nprint(s[1:4])'
        assert _run_source(source) == "ell\n"

    def test_stop_only(self) -> None:
        """``s[:3]`` takes the first three characters."""
        source = 'let s = "hello"\nprint(s[:3])'
        assert _run_source(source) == "hel\n"

    def test_start_only(self) -> None:
        """``s[3:]`` takes from index 3 to the end."""
        source = 'let s = "hello"\nprint(s[3:])'
        assert _run_source(source) == "lo\n"

    def test_reverse(self) -> None:
        """``s[::-1]`` reverses the string."""
        source = 'let s = "hello"\nprint(s[::-1])'
        assert _run_source(source) == "olleh\n"


# -- Slicing: Integration ----------------------------------------------------


class TestSliceIntegration:
    """End-to-end tests combining slicing with other features."""

    def test_slice_in_variable(self) -> None:
        """Store a slice result in a variable."""
        source = """\
let xs = [10, 20, 30, 40, 50]
let sub = xs[1:3]
print(sub)"""
        assert _run_source(source) == "[20, 30]\n"

    def test_len_of_slice(self) -> None:
        """``len()`` works on a slice result."""
        source = """\
let xs = [10, 20, 30, 40, 50]
print(len(xs[1:4]))"""
        assert _run_source(source) == "3\n"

    def test_variable_indices(self) -> None:
        """Slice with variable start and stop."""
        source = """\
let xs = [10, 20, 30, 40, 50]
let i = 1
let j = 4
print(xs[i:j])"""
        assert _run_source(source) == "[20, 30, 40]\n"

    def test_chained_slice_and_index(self) -> None:
        """``xs[1:3][0]`` chains slice then index."""
        source = """\
let xs = [10, 20, 30, 40, 50]
print(xs[1:3][0])"""
        assert _run_source(source) == "20\n"

    def test_original_unchanged(self) -> None:
        """Slicing creates a copy — original is unchanged."""
        source = """\
let xs = [10, 20, 30]
let ys = xs[:]
ys[0] = 99
print(xs[0])"""
        assert _run_source(source) == "10\n"

    def test_slice_in_interpolation(self) -> None:
        """Slice inside string interpolation."""
        source = """\
let xs = [10, 20, 30, 40]
print("sub: {xs[1:3]}")"""
        assert _run_source(source) == "sub: [20, 30]\n"

    def test_slice_non_list_non_string_errors(self) -> None:
        """Slicing a non-list/non-string raises a runtime error."""
        with pytest.raises(PebbleRuntimeError, match="Cannot slice"):
            _run_source("let x = 42\nprint(x[1:3])")


# -- List methods: push (method syntax) ---------------------------------------


class TestListMethodPush:
    """Verify ``xs.push(val)`` method syntax."""

    def test_method_push(self) -> None:
        """``xs.push(4)`` appends to the list."""
        source = "let xs = [1, 2, 3]\nxs.push(4)\nprint(xs)"
        assert _run_source(source) == "[1, 2, 3, 4]\n"

    def test_push_to_empty(self) -> None:
        """``xs.push(1)`` works on empty lists."""
        source = "let xs = []\nxs.push(1)\nprint(xs)"
        assert _run_source(source) == "[1]\n"

    def test_functional_push_still_works(self) -> None:
        """Functional ``push(xs, 4)`` backward compat."""
        source = "let xs = [1, 2, 3]\npush(xs, 4)\nprint(xs)"
        assert _run_source(source) == "[1, 2, 3, 4]\n"


# -- List methods: pop (method syntax) ----------------------------------------


class TestListMethodPop:
    """Verify ``xs.pop()`` method syntax."""

    def test_method_pop(self) -> None:
        """``xs.pop()`` removes and returns the last element."""
        source = "let xs = [1, 2, 3]\nlet v = xs.pop()\nprint(v)\nprint(xs)"
        assert _run_source(source) == "3\n[1, 2]\n"

    def test_pop_empty_error(self) -> None:
        """``xs.pop()`` on empty list raises error."""
        with pytest.raises(PebbleRuntimeError, match="empty list"):
            _run_source("let xs = []\nxs.pop()")

    def test_functional_pop_still_works(self) -> None:
        """Functional ``pop(xs)`` backward compat."""
        source = "let xs = [1, 2, 3]\nlet v = pop(xs)\nprint(v)\nprint(xs)"
        assert _run_source(source) == "3\n[1, 2]\n"


# -- List methods: contains ---------------------------------------------------


class TestListMethodContains:
    """Verify ``xs.contains(val)`` method syntax."""

    def test_found(self) -> None:
        """``xs.contains(2)`` returns true when present."""
        source = "let xs = [1, 2, 3]\nprint(xs.contains(2))"
        assert _run_source(source) == "true\n"

    def test_not_found(self) -> None:
        """``xs.contains(99)`` returns false when absent."""
        source = "let xs = [1, 2, 3]\nprint(xs.contains(99))"
        assert _run_source(source) == "false\n"


# -- List methods: reverse ----------------------------------------------------


class TestListMethodReverse:
    """Verify ``xs.reverse()`` method syntax."""

    def test_reverse(self) -> None:
        """``xs.reverse()`` reverses in place."""
        source = "let xs = [1, 2, 3]\nxs.reverse()\nprint(xs)"
        assert _run_source(source) == "[3, 2, 1]\n"


# -- List methods: sort -------------------------------------------------------


class TestListMethodSort:
    """Verify ``xs.sort()`` method syntax."""

    def test_sort_ints(self) -> None:
        """``xs.sort()`` sorts integers in place."""
        source = "let xs = [3, 1, 2]\nxs.sort()\nprint(xs)"
        assert _run_source(source) == "[1, 2, 3]\n"

    def test_sort_strings(self) -> None:
        """``xs.sort()`` sorts strings alphabetically."""
        source = 'let xs = ["cherry", "apple", "banana"]\nxs.sort()\nprint(xs)'
        assert _run_source(source) == "[apple, banana, cherry]\n"

    def test_sort_mixed_error(self) -> None:
        """``xs.sort()`` on mixed types raises error."""
        with pytest.raises(PebbleRuntimeError, match="same type"):
            _run_source('let xs = [1, "a"]\nxs.sort()')

    def test_sort_empty(self) -> None:
        """``xs.sort()`` on empty list is a no-op."""
        source = "let xs = []\nxs.sort()\nprint(xs)"
        assert _run_source(source) == "[]\n"

    def test_sort_ten_elements(self) -> None:
        """``sort()`` handles a larger list."""
        source = "let xs = [5, 3, 8, 1, 9, 2, 7, 4, 6, 0]\nxs.sort()\nprint(xs[0])"
        assert _run_source(source) == "0\n"
