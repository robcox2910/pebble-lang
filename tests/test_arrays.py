"""Tests for arrays / lists (Phase 12).

Cover lexer tokenization, parser AST construction, analyzer validation,
compiler bytecode generation, and VM execution of array operations.
"""

from io import StringIO

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import ArrayLiteral, Expression, IndexAccess, IntegerLiteral
from pebble.bytecode import Instruction, OpCode
from pebble.compiler import Compiler
from pebble.errors import PebbleRuntimeError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.tokens import TokenKind
from pebble.vm import VirtualMachine

# -- Named constants ----------------------------------------------------------

ONE = 1
TWO = 2
THREE = 3


# -- Helpers ------------------------------------------------------------------


def _kinds(source: str) -> list[TokenKind]:
    """Return just the token kinds for *source* (excluding EOF)."""
    tokens = Lexer(source).tokenize()
    return [t.kind for t in tokens if t.kind != TokenKind.EOF]


def _run_source(source: str) -> str:
    """Compile and run *source*, returning captured output."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzed = SemanticAnalyzer().analyze(program)
    compiled = Compiler().compile(analyzed)
    buf = StringIO()
    VirtualMachine(output=buf).run(compiled)
    return buf.getvalue()


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
        """Negative index raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="out of bounds"):
            _run_source("let xs = [1, 2, 3]\nprint(xs[-1])")


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
