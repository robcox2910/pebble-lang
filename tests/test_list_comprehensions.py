"""Tests for list comprehensions: ``[x * 2 for x in range(5)]``."""

from io import StringIO

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import (
    ArrayLiteral,
    BinaryOp,
    Expression,
    FunctionCall,
    Identifier,
    ListComprehension,
)
from pebble.bytecode import Instruction, OpCode
from pebble.compiler import Compiler
from pebble.errors import ParseError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.tokens import SourceLocation
from pebble.vm import VirtualMachine

# -- Named constants ----------------------------------------------------------

RANGE_FIVE = 5
RANGE_SIX = 6
RANGE_TEN = 10
EXPECTED_ELEMENT_COUNT = 3


# -- Helpers ------------------------------------------------------------------


def _parse_expr(source: str) -> Expression:
    """Lex and parse a single expression from *source*."""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse_expression()


def _analyze(source: str) -> None:
    """Lex + parse + analyze — raise on semantic errors."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    SemanticAnalyzer().analyze(program)


def _compile_opcodes(source: str) -> list[OpCode]:
    """Lex + parse + analyze + compile, return main opcode list."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzer = SemanticAnalyzer()
    program = analyzer.analyze(program)
    compiled = Compiler(
        cell_vars=analyzer.cell_vars,
        free_vars=analyzer.free_vars,
    ).compile(program)
    return [instr.opcode for instr in compiled.main.instructions]


def _compile_instructions(source: str) -> list[Instruction]:
    """Return the main instruction list for *source*."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzer = SemanticAnalyzer()
    program = analyzer.analyze(program)
    compiled = Compiler(
        cell_vars=analyzer.cell_vars,
        free_vars=analyzer.free_vars,
    ).compile(program)
    return compiled.main.instructions


def _run_source(source: str) -> str:
    """Compile and run *source*, return captured output."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzer = SemanticAnalyzer()
    analyzed = analyzer.analyze(program)
    compiled = Compiler(
        cell_vars=analyzer.cell_vars,
        free_vars=analyzer.free_vars,
    ).compile(analyzed)
    buf = StringIO()
    VirtualMachine(output=buf).run(compiled)
    return buf.getvalue()


# =============================================================================
# Cycle 1: AST + Opcode
# =============================================================================


class TestListComprehensionAST:
    """Verify the ListComprehension AST node."""

    def test_node_construction(self) -> None:
        """Create a ListComprehension node with all fields."""
        loc = SourceLocation(line=1, column=0)
        ident = Identifier(name="x", location=loc)
        call = FunctionCall(name="range", arguments=[], location=loc)
        node = ListComprehension(
            mapping=ident,
            variable="x",
            iterable=call,
            condition=None,
            location=loc,
        )
        assert node.mapping == ident
        assert node.variable == "x"
        assert node.iterable == call
        assert node.condition is None

    def test_node_with_condition(self) -> None:
        """Create a ListComprehension node with a condition."""
        loc = SourceLocation(line=1, column=0)
        ident = Identifier(name="x", location=loc)
        call = FunctionCall(name="range", arguments=[], location=loc)
        cond = BinaryOp(left=ident, operator=">", right=ident, location=loc)
        node = ListComprehension(
            mapping=ident,
            variable="x",
            iterable=call,
            condition=cond,
            location=loc,
        )
        assert node.condition == cond


class TestListAppendOpcode:
    """Verify the LIST_APPEND opcode exists."""

    def test_list_append_is_str_enum(self) -> None:
        """LIST_APPEND is a valid OpCode member."""
        assert OpCode.LIST_APPEND == "LIST_APPEND"


# =============================================================================
# Cycle 2: Parser
# =============================================================================


class TestListComprehensionParser:
    """Verify the parser produces ListComprehension nodes."""

    def test_basic_comprehension(self) -> None:
        """``[x for x in range(5)]`` parses to a ListComprehension."""
        node = _parse_expr("[x for x in range(5)]")
        assert isinstance(node, ListComprehension)
        assert node.variable == "x"
        assert isinstance(node.mapping, Identifier)
        assert node.condition is None

    def test_with_mapping_expression(self) -> None:
        """``[x * 2 for x in range(5)]`` has a BinaryOp mapping."""
        node = _parse_expr("[x * 2 for x in range(5)]")
        assert isinstance(node, ListComprehension)
        assert isinstance(node.mapping, BinaryOp)
        assert node.mapping.operator == "*"

    def test_with_filter(self) -> None:
        """``[x for x in range(10) if x > 5]`` has a condition."""
        node = _parse_expr("[x for x in range(10) if x > 5]")
        assert isinstance(node, ListComprehension)
        assert node.condition is not None
        assert isinstance(node.condition, BinaryOp)
        assert node.condition.operator == ">"

    def test_iterable_is_function_call(self) -> None:
        """The iterable is parsed as a FunctionCall."""
        node = _parse_expr("[x for x in range(5)]")
        assert isinstance(node, ListComprehension)
        assert isinstance(node.iterable, FunctionCall)
        assert node.iterable.name == "range"

    def test_empty_array_still_works(self) -> None:
        """``[]`` still parses to an empty ArrayLiteral (regression)."""
        node = _parse_expr("[]")
        assert isinstance(node, ArrayLiteral)
        assert node.elements == []

    def test_regular_array_still_works(self) -> None:
        """``[1, 2, 3]`` still parses to an ArrayLiteral (regression)."""
        node = _parse_expr("[1, 2, 3]")
        assert isinstance(node, ArrayLiteral)
        assert len(node.elements) == EXPECTED_ELEMENT_COUNT

    def test_single_element_still_works(self) -> None:
        """``[42]`` still parses to an ArrayLiteral (regression)."""
        node = _parse_expr("[42]")
        assert isinstance(node, ArrayLiteral)
        assert len(node.elements) == 1

    def test_error_missing_variable_after_for(self) -> None:
        """Missing variable name after ``for`` raises ParseError."""
        with pytest.raises(ParseError):
            _parse_expr("[x for in range(5)]")

    def test_error_missing_in(self) -> None:
        """Missing ``in`` after loop variable raises ParseError."""
        with pytest.raises(ParseError):
            _parse_expr("[x for x range(5)]")

    def test_error_missing_closing_bracket(self) -> None:
        """Missing ``]`` raises ParseError."""
        with pytest.raises(ParseError):
            _parse_expr("[x for x in range(5)")


# =============================================================================
# Cycle 3: Analyzer
# =============================================================================


class TestListComprehensionAnalyzer:
    """Verify semantic analysis of list comprehensions."""

    def test_loop_variable_scoped_to_comprehension(self) -> None:
        """The loop variable is not visible outside the comprehension."""
        with pytest.raises(SemanticError, match="x"):
            _analyze("let result = [x for x in range(5)]\nprint(x)")

    def test_outer_variable_accessible_in_mapping(self) -> None:
        """An outer variable can be used in the mapping expression."""
        _analyze("let n = 2\nlet result = [x * n for x in range(5)]")

    def test_undeclared_variable_in_mapping(self) -> None:
        """Using an undeclared variable in the mapping raises SemanticError."""
        with pytest.raises(SemanticError, match="y"):
            _analyze("[y for x in range(5)]")

    def test_undeclared_variable_in_condition(self) -> None:
        """Using an undeclared variable in the condition raises SemanticError."""
        with pytest.raises(SemanticError, match="y"):
            _analyze("[x for x in range(5) if y > 0]")

    def test_valid_comprehension_passes(self) -> None:
        """A well-formed comprehension passes analysis."""
        _analyze("let result = [x * 2 for x in range(5)]")

    def test_valid_comprehension_with_filter(self) -> None:
        """A comprehension with filter passes analysis."""
        _analyze("let result = [x for x in range(10) if x > 5]")


# =============================================================================
# Cycle 4: Compiler
# =============================================================================


class TestListComprehensionCompiler:
    """Verify the compiler emits correct opcodes for comprehensions."""

    def test_emits_build_list_zero(self) -> None:
        """Compiler emits BUILD_LIST with operand 0 for the empty result list."""
        instructions = _compile_instructions("let r = [x for x in range(5)]")
        build_list_instrs = [i for i in instructions if i.opcode == OpCode.BUILD_LIST]
        assert any(i.operand == 0 for i in build_list_instrs)

    def test_emits_list_append(self) -> None:
        """Compiler emits LIST_APPEND for the comprehension."""
        opcodes = _compile_opcodes("let r = [x for x in range(5)]")
        assert OpCode.LIST_APPEND in opcodes


# =============================================================================
# Cycle 4: End-to-end
# =============================================================================


class TestListComprehensionEndToEnd:
    """Verify list comprehensions produce correct results end-to-end."""

    def test_identity(self) -> None:
        """``[x for x in range(5)]`` produces ``[0, 1, 2, 3, 4]``."""
        assert _run_source("print([x for x in range(5)])") == "[0, 1, 2, 3, 4]\n"

    def test_mapping(self) -> None:
        """``[x * 2 for x in range(5)]`` produces ``[0, 2, 4, 6, 8]``."""
        assert _run_source("print([x * 2 for x in range(5)])") == "[0, 2, 4, 6, 8]\n"

    def test_filter(self) -> None:
        """``[x for x in range(10) if x > 5]`` produces ``[6, 7, 8, 9]``."""
        assert _run_source("print([x for x in range(10) if x > 5])") == "[6, 7, 8, 9]\n"

    def test_mapping_and_filter(self) -> None:
        """``[x * x for x in range(6) if x > 2]`` produces ``[9, 16, 25]``."""
        assert _run_source("print([x * x for x in range(6) if x > 2])") == "[9, 16, 25]\n"

    def test_empty_range(self) -> None:
        """``[x for x in range(0)]`` produces ``[]``."""
        assert _run_source("print([x for x in range(0)])") == "[]\n"

    def test_filter_removes_all(self) -> None:
        """``[x for x in range(5) if x > 10]`` produces ``[]``."""
        assert _run_source("print([x for x in range(5) if x > 10])") == "[]\n"

    def test_range_two_args(self) -> None:
        """``[x for x in range(2, 5)]`` produces ``[2, 3, 4]``."""
        assert _run_source("print([x for x in range(2, 5)])") == "[2, 3, 4]\n"

    def test_range_three_args(self) -> None:
        """``[x for x in range(0, 10, 3)]`` produces ``[0, 3, 6, 9]``."""
        assert _run_source("print([x for x in range(0, 10, 3)])") == "[0, 3, 6, 9]\n"

    def test_assign_and_print(self) -> None:
        """Assign a comprehension to a variable and print it."""
        source = "let nums = [x * 2 for x in range(4)]\nprint(nums)"
        assert _run_source(source) == "[0, 2, 4, 6]\n"

    def test_inside_function(self) -> None:
        """Comprehension works inside a function body."""
        source = """\
fn squares(n) {
    return [x * x for x in range(n)]
}
print(squares(4))
"""
        assert _run_source(source) == "[0, 1, 4, 9]\n"

    def test_len_of_comprehension(self) -> None:
        """``len()`` works on comprehension result."""
        source = "print(len([x for x in range(5)]))"
        assert _run_source(source) == "5\n"

    def test_index_into_comprehension(self) -> None:
        """Index access works on comprehension result."""
        source = "let nums = [x * 10 for x in range(3)]\nprint(nums[2])"
        assert _run_source(source) == "20\n"

    def test_two_comprehensions_same_scope(self) -> None:
        """Two comprehensions in the same scope work independently."""
        source = """\
let a = [x for x in range(3)]
let b = [x * 2 for x in range(4)]
print(a)
print(b)
"""
        assert _run_source(source) == "[0, 1, 2]\n[0, 2, 4, 6]\n"

    def test_comprehension_inside_loop(self) -> None:
        """Comprehension inside a for loop."""
        source = """\
for i in range(3) {
    let row = [i * j for j in range(3)]
    print(row)
}
"""
        assert _run_source(source) == "[0, 0, 0]\n[0, 1, 2]\n[0, 2, 4]\n"

    def test_nested_comprehension(self) -> None:
        """Comprehension in the mapping expression (nested)."""
        source = "print([len([y for y in range(x)]) for x in range(4)])"
        assert _run_source(source) == "[0, 1, 2, 3]\n"
