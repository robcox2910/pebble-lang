"""Tests for multiple return values and tuple unpacking."""

from io import StringIO

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import (
    ArrayLiteral,
    Assignment,
    ConstAssignment,
    Identifier,
    ReturnStatement,
    Statement,
    UnpackAssignment,
    UnpackConstAssignment,
    UnpackReassignment,
)
from pebble.bytecode import Instruction, OpCode
from pebble.compiler import Compiler
from pebble.errors import ParseError, PebbleRuntimeError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.tokens import SourceLocation
from pebble.vm import VirtualMachine

# -- Named constants ----------------------------------------------------------

TWO_NAMES = 2
THREE_NAMES = 3


# -- Helpers ------------------------------------------------------------------


def _parse(source: str) -> list[Statement]:
    """Lex and parse *source*, return statement list."""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse().statements


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


class TestUnpackAssignmentAST:
    """Verify the UnpackAssignment AST node."""

    def test_node_construction(self) -> None:
        """Create an UnpackAssignment with two names."""
        loc = SourceLocation(line=1, column=0)
        ident = Identifier(name="expr", location=loc)
        node = UnpackAssignment(names=["x", "y"], value=ident, location=loc)
        assert node.names == ["x", "y"]
        assert node.value == ident
        assert node.location == loc

    def test_node_is_frozen(self) -> None:
        """UnpackAssignment is immutable."""
        loc = SourceLocation(line=1, column=0)
        ident = Identifier(name="expr", location=loc)
        node = UnpackAssignment(names=["x", "y"], value=ident, location=loc)
        with pytest.raises(AttributeError):
            node.names = ["a"]  # type: ignore[misc]


class TestUnpackConstAssignmentAST:
    """Verify the UnpackConstAssignment AST node."""

    def test_node_construction(self) -> None:
        """Create an UnpackConstAssignment with two names."""
        loc = SourceLocation(line=1, column=0)
        ident = Identifier(name="expr", location=loc)
        node = UnpackConstAssignment(names=["x", "y"], value=ident, location=loc)
        assert node.names == ["x", "y"]
        assert node.value == ident


class TestUnpackReassignmentAST:
    """Verify the UnpackReassignment AST node."""

    def test_node_construction(self) -> None:
        """Create an UnpackReassignment with two names."""
        loc = SourceLocation(line=1, column=0)
        ident = Identifier(name="expr", location=loc)
        node = UnpackReassignment(names=["a", "b"], value=ident, location=loc)
        assert node.names == ["a", "b"]
        assert node.value == ident


class TestUnpackSequenceOpcode:
    """Verify the UNPACK_SEQUENCE opcode exists."""

    def test_unpack_sequence_is_str_enum(self) -> None:
        """UNPACK_SEQUENCE is a valid OpCode member."""
        assert OpCode.UNPACK_SEQUENCE == "UNPACK_SEQUENCE"


# =============================================================================
# Cycle 2: Parser
# =============================================================================


class TestUnpackLetParser:
    """Verify the parser produces UnpackAssignment nodes."""

    def test_two_names(self) -> None:
        """``let x, y = expr`` parses to an UnpackAssignment."""
        stmts = _parse("let x, y = [1, 2]")
        assert len(stmts) == 1
        node = stmts[0]
        assert isinstance(node, UnpackAssignment)
        assert node.names == ["x", "y"]

    def test_three_names(self) -> None:
        """``let a, b, c = expr`` parses to UnpackAssignment with three names."""
        stmts = _parse("let a, b, c = [1, 2, 3]")
        assert len(stmts) == 1
        node = stmts[0]
        assert isinstance(node, UnpackAssignment)
        assert node.names == ["a", "b", "c"]
        assert len(node.names) == THREE_NAMES

    def test_single_let_still_works(self) -> None:
        """``let x = 1`` still parses to a regular Assignment (regression)."""
        stmts = _parse("let x = 1")
        assert len(stmts) == 1
        assert isinstance(stmts[0], Assignment)

    def test_error_trailing_comma(self) -> None:
        """``let x, = expr`` raises ParseError."""
        with pytest.raises(ParseError):
            _parse("let x, = [1]")

    def test_error_missing_first_name(self) -> None:
        """``let , y = expr`` raises ParseError."""
        with pytest.raises(ParseError):
            _parse("let , y = [1]")


class TestUnpackConstParser:
    """Verify the parser produces UnpackConstAssignment nodes."""

    def test_two_names(self) -> None:
        """``const x, y = expr`` parses to an UnpackConstAssignment."""
        stmts = _parse("const x, y = [1, 2]")
        assert len(stmts) == 1
        node = stmts[0]
        assert isinstance(node, UnpackConstAssignment)
        assert node.names == ["x", "y"]

    def test_single_const_still_works(self) -> None:
        """``const x = 1`` still parses to a regular ConstAssignment (regression)."""
        stmts = _parse("const x = 1")
        assert len(stmts) == 1
        assert isinstance(stmts[0], ConstAssignment)


class TestUnpackReassignmentParser:
    """Verify the parser produces UnpackReassignment nodes."""

    def test_two_names(self) -> None:
        """``x, y = expr`` parses to an UnpackReassignment."""
        stmts = _parse("let x = 0\nlet y = 0\nx, y = [1, 2]")
        node = stmts[2]
        assert isinstance(node, UnpackReassignment)
        assert node.names == ["x", "y"]


class TestReturnMultipleParser:
    """Verify return with multiple comma-separated values."""

    def test_return_two_values(self) -> None:
        """``return a, b`` parses to ReturnStatement with ArrayLiteral."""
        stmts = _parse("fn f(a, b) {\n    return a, b\n}")
        fn_body = stmts[0]
        assert hasattr(fn_body, "body")
        ret = fn_body.body[0]  # type: ignore[attr-defined]
        assert isinstance(ret, ReturnStatement)
        assert isinstance(ret.value, ArrayLiteral)
        assert len(ret.value.elements) == TWO_NAMES

    def test_return_three_values(self) -> None:
        """``return a, b, c`` has a three-element ArrayLiteral."""
        stmts = _parse("fn f(a, b, c) {\n    return a, b, c\n}")
        ret = stmts[0].body[0]  # type: ignore[attr-defined]
        assert isinstance(ret, ReturnStatement)
        assert isinstance(ret.value, ArrayLiteral)
        assert len(ret.value.elements) == THREE_NAMES

    def test_single_return_still_works(self) -> None:
        """``return x`` still parses normally (regression)."""
        stmts = _parse("fn f(x) {\n    return x\n}")
        ret = stmts[0].body[0]  # type: ignore[attr-defined]
        assert isinstance(ret, ReturnStatement)
        assert isinstance(ret.value, Identifier)


# =============================================================================
# Cycle 3: Analyzer
# =============================================================================


class TestUnpackAnalyzer:
    """Verify semantic analysis of unpack statements."""

    def test_unpack_let_declares_names(self) -> None:
        """Each name in ``let x, y = expr`` is declared."""
        _analyze("let x, y = [1, 2]\nprint(x)\nprint(y)")

    def test_unpack_const_declares_constants(self) -> None:
        """Each name in ``const x, y = expr`` is declared as a constant."""
        _analyze("const x, y = [1, 2]\nprint(x)\nprint(y)")

    def test_unpack_const_prevents_reassignment(self) -> None:
        """Reassigning a const-unpacked variable raises SemanticError."""
        with pytest.raises(SemanticError, match="Cannot reassign constant"):
            _analyze("const x, y = [1, 2]\nx = 3")

    def test_unpack_reassignment_requires_declaration(self) -> None:
        """Undeclared variable in unpack reassignment raises SemanticError."""
        with pytest.raises(SemanticError, match="Undeclared variable"):
            _analyze("a, b = [1, 2]")

    def test_unpack_reassignment_checks_const(self) -> None:
        """Cannot unpack-reassign a const variable."""
        with pytest.raises(SemanticError, match="Cannot reassign constant"):
            _analyze("const x = 1\nlet y = 2\nx, y = [3, 4]")

    def test_undeclared_variable_in_rhs(self) -> None:
        """Undeclared variable in the RHS expression raises SemanticError."""
        with pytest.raises(SemanticError, match="Undeclared variable"):
            _analyze("let x, y = unknown")

    def test_outer_variable_in_rhs(self) -> None:
        """Outer variable can be used in the RHS of an unpack assignment."""
        _analyze("let vals = [1, 2]\nlet x, y = vals")


# =============================================================================
# Cycle 4: Compiler
# =============================================================================


class TestUnpackCompiler:
    """Verify the compiler emits UNPACK_SEQUENCE."""

    def test_emits_unpack_sequence(self) -> None:
        """Compiler emits UNPACK_SEQUENCE for a let unpack."""
        opcodes = _compile_opcodes("let x, y = [1, 2]")
        assert OpCode.UNPACK_SEQUENCE in opcodes

    def test_unpack_sequence_operand(self) -> None:
        """UNPACK_SEQUENCE has the correct count operand."""
        instructions = _compile_instructions("let x, y = [1, 2]")
        unpack_instrs = [i for i in instructions if i.opcode == OpCode.UNPACK_SEQUENCE]
        assert len(unpack_instrs) == 1
        assert unpack_instrs[0].operand == TWO_NAMES

    def test_emits_store_names_after_unpack(self) -> None:
        """N STORE_NAME instructions follow UNPACK_SEQUENCE."""
        instructions = _compile_instructions("let x, y = [1, 2]")
        unpack_idx = next(
            i for i, inst in enumerate(instructions) if inst.opcode == OpCode.UNPACK_SEQUENCE
        )
        store_x = instructions[unpack_idx + 1]
        store_y = instructions[unpack_idx + 2]
        assert store_x.opcode == OpCode.STORE_NAME
        assert store_x.operand == "x"
        assert store_y.opcode == OpCode.STORE_NAME
        assert store_y.operand == "y"


# =============================================================================
# Cycle 4: End-to-end
# =============================================================================


class TestUnpackEndToEnd:
    """Verify tuple unpacking works end to end."""

    def test_let_two_values(self) -> None:
        """``let x, y = [1, 2]`` unpacks correctly."""
        assert _run_source("let x, y = [1, 2]\nprint(x)\nprint(y)") == "1\n2\n"

    def test_let_three_values(self) -> None:
        """``let a, b, c = [10, 20, 30]`` unpacks correctly."""
        out = _run_source("let a, b, c = [10, 20, 30]\nprint(a)\nprint(b)\nprint(c)")
        assert out == "10\n20\n30\n"

    def test_const_unpacking(self) -> None:
        """``const x, y = [1, 2]`` creates immutable bindings."""
        assert _run_source("const x, y = [1, 2]\nprint(x)\nprint(y)") == "1\n2\n"

    def test_return_multiple_values(self) -> None:
        """A function returning multiple values can be unpacked at the call site."""
        source = """\
fn swap(a, b) {
    return b, a
}
let x, y = swap(1, 2)
print(x)
print(y)
"""
        assert _run_source(source) == "2\n1\n"

    def test_reassignment_unpacking(self) -> None:
        """``x, y = [3, 4]`` reassigns existing variables."""
        source = """\
let x = 0
let y = 0
x, y = [3, 4]
print(x)
print(y)
"""
        assert _run_source(source) == "3\n4\n"

    def test_swap_idiom(self) -> None:
        """``a, b = [b, a]`` swaps two variables."""
        source = """\
let a = 1
let b = 2
a, b = [b, a]
print(a)
print(b)
"""
        assert _run_source(source) == "2\n1\n"

    def test_function_returning_three_values(self) -> None:
        """A function can return three values via unpack."""
        source = """\
fn min_max_sum(a, b, c) {
    let lo = a
    let hi = a
    if b < lo { lo = b }
    if c < lo { lo = c }
    if b > hi { hi = b }
    if c > hi { hi = c }
    return lo, hi, a + b + c
}
let lo, hi, total = min_max_sum(3, 1, 2)
print(lo)
print(hi)
print(total)
"""
        assert _run_source(source) == "1\n3\n6\n"

    def test_wrong_count_too_many(self) -> None:
        """Unpacking a 3-element list into 2 variables raises runtime error."""
        with pytest.raises(PebbleRuntimeError, match="Expected 2 values to unpack, got 3"):
            _run_source("let x, y = [1, 2, 3]")

    def test_wrong_count_too_few(self) -> None:
        """Unpacking a 2-element list into 3 variables raises runtime error."""
        with pytest.raises(PebbleRuntimeError, match="Expected 3 values to unpack, got 2"):
            _run_source("let x, y, z = [1, 2]")

    def test_non_list_error(self) -> None:
        """Unpacking a non-list value raises runtime error."""
        with pytest.raises(PebbleRuntimeError, match="Cannot unpack"):
            _run_source("let x, y = 42")

    def test_unpack_inside_loop(self) -> None:
        """Unpack works inside a for loop."""
        source = """\
let pairs = [[1, 2], [3, 4], [5, 6]]
for i in range(3) {
    let a, b = pairs[i]
    print(a + b)
}
"""
        assert _run_source(source) == "3\n7\n11\n"

    def test_unpack_inside_function(self) -> None:
        """Unpack works inside a function body."""
        source = """\
fn process() {
    let x, y = [10, 20]
    return x + y
}
print(process())
"""
        assert _run_source(source) == "30\n"

    def test_nested_unpack_from_function(self) -> None:
        """Unpack result of a function that itself returns unpacked values."""
        source = """\
fn inner() {
    return 1, 2
}
fn outer() {
    let a, b = inner()
    return a + b, a * b
}
let sum, prod = outer()
print(sum)
print(prod)
"""
        assert _run_source(source) == "3\n2\n"

    def test_unpack_from_list_comprehension(self) -> None:
        """Unpack from a list comprehension result."""
        source = """\
let a, b, c = [x * x for x in range(3)]
print(a)
print(b)
print(c)
"""
        assert _run_source(source) == "0\n1\n4\n"
