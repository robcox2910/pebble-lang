"""Tests for the Pebble parser — statement parsing.

Covers ``let`` declarations, reassignments, ``print()``, ``if/else``,
``else if``, ``while``, ``for``, ``fn``, ``return``, block parsing, and the
``Program`` root node.
"""

import pytest

from pebble.ast_nodes import (
    Assignment,
    BinaryOp,
    BooleanLiteral,
    BreakStatement,
    ContinueStatement,
    ForLoop,
    FunctionCall,
    FunctionDef,
    Identifier,
    IfStatement,
    IntegerLiteral,
    PrintStatement,
    Program,
    Reassignment,
    ReturnStatement,
    Statement,
    StringLiteral,
    WhileLoop,
)
from pebble.errors import ParseError
from pebble.lexer import Lexer
from pebble.parser import Parser

# -- Named constants ----------------------------------------------------------

ANSWER = 42
TEN = 10
FIVE = 5
THREE = 3
TWO = 2
ONE = 1
ZERO = 0


def _parse(source: str) -> Program:
    """Lex and parse *source* into a Program AST."""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def _stmts(source: str) -> list[Statement]:
    """Return the top-level statements from *source*."""
    return _parse(source).statements


# -- Let declarations --------------------------------------------------------


class TestLetDeclaration:
    """Verify parsing of ``let`` variable declarations."""

    def test_let_integer(self) -> None:
        """Verify 'let x = 42' parses to Assignment."""
        stmts = _stmts("let x = 42")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, Assignment)
        assert stmt.name == "x"
        assert isinstance(stmt.value, IntegerLiteral)
        assert stmt.value.value == ANSWER

    def test_let_string(self) -> None:
        """Verify 'let msg = "hello"' parses to Assignment."""
        stmts = _stmts('let msg = "hello"')
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, Assignment)
        assert stmt.name == "msg"
        assert isinstance(stmt.value, StringLiteral)
        assert stmt.value.value == "hello"

    def test_let_expression(self) -> None:
        """Verify 'let sum = 1 + 2' parses to Assignment with BinaryOp value."""
        stmts = _stmts("let sum = 1 + 2")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, Assignment)
        assert isinstance(stmt.value, BinaryOp)
        assert stmt.value.operator == "+"

    def test_let_missing_name_raises(self) -> None:
        """Verify 'let = 5' raises ParseError."""
        with pytest.raises(ParseError, match="Expected variable name"):
            _parse("let = 5")

    def test_let_missing_equals_raises(self) -> None:
        """Verify 'let x 5' raises ParseError."""
        with pytest.raises(ParseError, match="Expected '='"):
            _parse("let x 5")


# -- Reassignment ------------------------------------------------------------


class TestReassignment:
    """Verify parsing of variable reassignment."""

    def test_reassign_integer(self) -> None:
        """Verify 'x = 10' parses to Reassignment."""
        stmts = _stmts("x = 10")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, Reassignment)
        assert stmt.name == "x"
        assert isinstance(stmt.value, IntegerLiteral)
        assert stmt.value.value == TEN

    def test_reassign_expression(self) -> None:
        """Verify 'x = x + 1' parses to Reassignment with BinaryOp."""
        stmts = _stmts("x = x + 1")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, Reassignment)
        assert stmt.name == "x"
        assert isinstance(stmt.value, BinaryOp)
        assert stmt.value.operator == "+"


# -- Print statement ----------------------------------------------------------


class TestPrintStatement:
    """Verify parsing of ``print()`` statements."""

    def test_print_integer(self) -> None:
        """Verify 'print(42)' parses to PrintStatement."""
        stmts = _stmts("print(42)")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, PrintStatement)
        assert isinstance(stmt.expression, IntegerLiteral)
        assert stmt.expression.value == ANSWER

    def test_print_string(self) -> None:
        """Verify 'print("hello")' parses to PrintStatement."""
        stmts = _stmts('print("hello")')
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, PrintStatement)
        assert isinstance(stmt.expression, StringLiteral)
        assert stmt.expression.value == "hello"

    def test_print_expression(self) -> None:
        """Verify 'print(1 + 2)' parses to PrintStatement with BinaryOp."""
        stmts = _stmts("print(1 + 2)")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, PrintStatement)
        assert isinstance(stmt.expression, BinaryOp)
        assert stmt.expression.operator == "+"

    def test_print_missing_paren_raises(self) -> None:
        """Verify 'print 42' raises ParseError."""
        with pytest.raises(ParseError, match="Expected '\\('"):
            _parse("print 42")

    def test_print_missing_close_paren_raises(self) -> None:
        """Verify 'print(42' raises ParseError."""
        with pytest.raises(ParseError, match="Expected '\\)'"):
            _parse("print(42")


# -- If statement -------------------------------------------------------------


class TestIfStatement:
    """Verify parsing of ``if/else`` statements."""

    def test_if_without_else(self) -> None:
        """Verify 'if true { print(1) }' parses to IfStatement."""
        stmts = _stmts("if true {\n    print(1)\n}")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, IfStatement)
        assert isinstance(stmt.condition, BooleanLiteral)
        assert stmt.condition.value is True
        assert len(stmt.body) == ONE
        assert isinstance(stmt.body[0], PrintStatement)
        assert stmt.else_body is None

    def test_if_with_else(self) -> None:
        """Verify 'if cond { ... } else { ... }' parses with else_body."""
        source = "if x > 0 {\n    print(x)\n} else {\n    print(0)\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, IfStatement)
        assert isinstance(stmt.condition, BinaryOp)
        assert stmt.condition.operator == ">"
        assert stmt.else_body is not None
        assert len(stmt.else_body) == ONE
        assert isinstance(stmt.else_body[0], PrintStatement)

    def test_if_empty_body(self) -> None:
        """Verify 'if true { }' parses with empty body."""
        stmts = _stmts("if true {\n}")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, IfStatement)
        assert stmt.body == []

    def test_if_missing_brace_raises(self) -> None:
        """Verify missing '{' after condition raises ParseError."""
        with pytest.raises(ParseError, match="Expected '\\{'"):
            _parse("if true print(1)")

    def test_if_missing_closing_brace_raises(self) -> None:
        """Verify missing '}' raises ParseError."""
        with pytest.raises(ParseError, match="Expected '\\}'"):
            _parse("if true {\n    print(1)")


# -- Else if chains -----------------------------------------------------------


class TestElseIfChain:
    """Verify parsing of ``else if`` chains as nested IfStatement nodes."""

    def test_basic_else_if(self) -> None:
        """Verify ``if/else if/else`` desugars to nested IfStatement."""
        source = (
            "if x > 90 {\n    print(1)\n} else if x > 80 {\n    print(2)\n} else {\n    print(3)\n}"
        )
        stmts = _stmts(source)
        assert len(stmts) == ONE
        outer = stmts[0]
        assert isinstance(outer, IfStatement)
        assert isinstance(outer.condition, BinaryOp)
        assert outer.condition.operator == ">"
        # else_body contains a single nested IfStatement
        assert outer.else_body is not None
        assert len(outer.else_body) == ONE
        inner = outer.else_body[0]
        assert isinstance(inner, IfStatement)
        assert isinstance(inner.condition, BinaryOp)
        assert inner.condition.operator == ">"
        assert inner.else_body is not None
        assert len(inner.else_body) == ONE
        assert isinstance(inner.else_body[0], PrintStatement)

    def test_else_if_without_final_else(self) -> None:
        """Verify ``if/else if`` with no trailing else has else_body=None on inner."""
        source = "if x > 90 {\n    print(1)\n} else if x > 80 {\n    print(2)\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        outer = stmts[0]
        assert isinstance(outer, IfStatement)
        assert outer.else_body is not None
        assert len(outer.else_body) == ONE
        inner = outer.else_body[0]
        assert isinstance(inner, IfStatement)
        assert inner.else_body is None

    def test_triple_else_if_chain(self) -> None:
        """Verify three-deep ``else if`` nesting."""
        source = (
            "if x > 90 {\n    print(1)\n"
            "} else if x > 80 {\n    print(2)\n"
            "} else if x > 70 {\n    print(3)\n"
            "} else {\n    print(4)\n}"
        )
        stmts = _stmts(source)
        assert len(stmts) == ONE
        outer = stmts[0]
        assert isinstance(outer, IfStatement)
        # outer → middle
        assert outer.else_body is not None
        assert len(outer.else_body) == ONE
        middle = outer.else_body[0]
        assert isinstance(middle, IfStatement)
        # middle → inner
        assert middle.else_body is not None
        assert len(middle.else_body) == ONE
        inner = middle.else_body[0]
        assert isinstance(inner, IfStatement)
        # inner has a final else
        assert inner.else_body is not None
        assert len(inner.else_body) == ONE
        assert isinstance(inner.else_body[0], PrintStatement)


# -- While loop ---------------------------------------------------------------


class TestWhileLoop:
    """Verify parsing of ``while`` loops."""

    def test_while_loop(self) -> None:
        """Verify 'while x < 10 { ... }' parses to WhileLoop."""
        source = "while x < 10 {\n    x = x + 1\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, WhileLoop)
        assert isinstance(stmt.condition, BinaryOp)
        assert stmt.condition.operator == "<"
        assert len(stmt.body) == ONE

    def test_while_empty_body(self) -> None:
        """Verify 'while true { }' parses with empty body."""
        stmts = _stmts("while true {\n}")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, WhileLoop)
        assert stmt.body == []

    def test_while_missing_brace_raises(self) -> None:
        """Verify missing '{' after while condition raises ParseError."""
        with pytest.raises(ParseError, match="Expected '\\{'"):
            _parse("while true print(1)")


# -- For loop -----------------------------------------------------------------


class TestForLoop:
    """Verify parsing of ``for`` loops."""

    def test_for_with_function_call_iterable(self) -> None:
        """Verify 'for i in range(10) { print(i) }' parses to ForLoop."""
        source = "for i in range(10) {\n    print(i)\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, ForLoop)
        assert stmt.variable == "i"
        assert isinstance(stmt.iterable, FunctionCall)
        assert stmt.iterable.name == "range"
        assert len(stmt.body) == ONE
        assert isinstance(stmt.body[0], PrintStatement)

    def test_for_with_identifier_iterable(self) -> None:
        """Verify 'for x in items { print(x) }' parses with Identifier iterable."""
        source = "for x in items {\n    print(x)\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, ForLoop)
        assert stmt.variable == "x"
        assert isinstance(stmt.iterable, Identifier)
        assert stmt.iterable.name == "items"

    def test_for_empty_body(self) -> None:
        """Verify 'for i in items { }' parses with empty body."""
        stmts = _stmts("for i in items {\n}")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, ForLoop)
        assert stmt.body == []

    def test_for_multiple_body_statements(self) -> None:
        """Verify for loop with multiple body statements parses correctly."""
        source = "for i in range(5) {\n    print(i)\n    x = x + 1\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, ForLoop)
        assert len(stmt.body) == TWO
        assert isinstance(stmt.body[0], PrintStatement)
        assert isinstance(stmt.body[1], Reassignment)

    def test_for_missing_variable_raises(self) -> None:
        """Verify 'for in items { }' raises ParseError."""
        with pytest.raises(ParseError, match="Expected loop variable"):
            _parse("for in items {\n}")

    def test_for_missing_in_raises(self) -> None:
        """Verify 'for i items { }' raises ParseError."""
        with pytest.raises(ParseError, match="Expected 'in'"):
            _parse("for i items {\n}")

    def test_for_missing_brace_raises(self) -> None:
        """Verify 'for i in items print(i)' raises ParseError."""
        with pytest.raises(ParseError, match="Expected '\\{'"):
            _parse("for i in items print(i)")


# -- Break and Continue -------------------------------------------------------


class TestBreakStatement:
    """Verify parsing of ``break`` statements."""

    def test_break_parses_to_break_statement(self) -> None:
        """Verify 'break' inside a block parses to BreakStatement."""
        source = "while true {\n    break\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        loop = stmts[0]
        assert isinstance(loop, WhileLoop)
        assert len(loop.body) == ONE
        assert isinstance(loop.body[0], BreakStatement)

    def test_break_has_source_location(self) -> None:
        """Verify BreakStatement carries the correct source location."""
        source = "while true {\n    break\n}"
        stmts = _stmts(source)
        loop = stmts[0]
        assert isinstance(loop, WhileLoop)
        brk = loop.body[0]
        assert isinstance(brk, BreakStatement)
        assert brk.location.line == TWO
        assert brk.location.column == FIVE


class TestContinueStatement:
    """Verify parsing of ``continue`` statements."""

    def test_continue_parses_to_continue_statement(self) -> None:
        """Verify 'continue' inside a block parses to ContinueStatement."""
        source = "while true {\n    continue\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        loop = stmts[0]
        assert isinstance(loop, WhileLoop)
        assert len(loop.body) == ONE
        assert isinstance(loop.body[0], ContinueStatement)

    def test_continue_has_source_location(self) -> None:
        """Verify ContinueStatement carries the correct source location."""
        source = "while true {\n    continue\n}"
        stmts = _stmts(source)
        loop = stmts[0]
        assert isinstance(loop, WhileLoop)
        cont = loop.body[0]
        assert isinstance(cont, ContinueStatement)
        assert cont.location.line == TWO
        assert cont.location.column == FIVE


# -- Function definition ------------------------------------------------------


class TestFunctionDef:
    """Verify parsing of ``fn`` function definitions."""

    def test_no_params(self) -> None:
        """Verify 'fn greet() { print("hi") }' parses to FunctionDef."""
        source = 'fn greet() {\n    print("hi")\n}'
        stmts = _stmts(source)
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, FunctionDef)
        assert stmt.name == "greet"
        assert stmt.parameters == []
        assert len(stmt.body) == ONE
        assert isinstance(stmt.body[0], PrintStatement)

    def test_one_param(self) -> None:
        """Verify 'fn square(x) { return x * x }' parses with one parameter."""
        source = "fn square(x) {\n    return x * x\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, FunctionDef)
        assert stmt.name == "square"
        assert stmt.parameters == ["x"]

    def test_multiple_params(self) -> None:
        """Verify 'fn add(a, b) { return a + b }' parses with two parameters."""
        source = "fn add(a, b) {\n    return a + b\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, FunctionDef)
        assert stmt.name == "add"
        assert stmt.parameters == ["a", "b"]

    def test_empty_body(self) -> None:
        """Verify 'fn noop() { }' parses with empty body."""
        stmts = _stmts("fn noop() {\n}")
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, FunctionDef)
        assert stmt.name == "noop"
        assert stmt.body == []

    def test_multiple_body_statements(self) -> None:
        """Verify function with multiple body statements parses correctly."""
        source = "fn f(x) {\n    let y = x + 1\n    return y\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, FunctionDef)
        assert len(stmt.body) == TWO
        assert isinstance(stmt.body[0], Assignment)
        assert isinstance(stmt.body[1], ReturnStatement)

    def test_missing_name_raises(self) -> None:
        """Verify 'fn () { }' raises ParseError."""
        with pytest.raises(ParseError, match="Expected function name"):
            _parse("fn () {\n}")

    def test_missing_open_paren_raises(self) -> None:
        """Verify 'fn greet { }' raises ParseError."""
        with pytest.raises(ParseError, match="Expected '\\('"):
            _parse("fn greet {\n}")

    def test_missing_close_paren_raises(self) -> None:
        """Verify 'fn greet(x { }' raises ParseError."""
        with pytest.raises(ParseError, match="Expected '\\)'"):
            _parse("fn greet(x {\n}")


# -- Return statement ---------------------------------------------------------


class TestReturnStatement:
    """Verify parsing of ``return`` statements."""

    def test_return_integer(self) -> None:
        """Verify 'return 42' inside a function parses to ReturnStatement."""
        source = "fn f() {\n    return 42\n}"
        stmts = _stmts(source)
        fn = stmts[0]
        assert isinstance(fn, FunctionDef)
        ret = fn.body[0]
        assert isinstance(ret, ReturnStatement)
        assert isinstance(ret.value, IntegerLiteral)
        assert ret.value.value == ANSWER

    def test_return_expression(self) -> None:
        """Verify 'return x + 1' parses with BinaryOp value."""
        source = "fn f(x) {\n    return x + 1\n}"
        stmts = _stmts(source)
        fn = stmts[0]
        assert isinstance(fn, FunctionDef)
        ret = fn.body[0]
        assert isinstance(ret, ReturnStatement)
        assert isinstance(ret.value, BinaryOp)
        assert ret.value.operator == "+"

    def test_bare_return(self) -> None:
        """Verify bare 'return' with no expression sets value to None."""
        source = "fn f() {\n    return\n}"
        stmts = _stmts(source)
        fn = stmts[0]
        assert isinstance(fn, FunctionDef)
        ret = fn.body[0]
        assert isinstance(ret, ReturnStatement)
        assert ret.value is None

    def test_return_before_closing_brace(self) -> None:
        """Verify 'return' right before '}' sets value to None."""
        source = "fn f() { return }"
        stmts = _stmts(source)
        fn = stmts[0]
        assert isinstance(fn, FunctionDef)
        ret = fn.body[0]
        assert isinstance(ret, ReturnStatement)
        assert ret.value is None


# -- Multiple statements ------------------------------------------------------


class TestMultipleStatements:
    """Verify parsing of multiple statements separated by newlines."""

    def test_two_statements(self) -> None:
        """Verify two newline-separated statements parse correctly."""
        stmts = _stmts("let x = 1\nprint(x)")
        assert len(stmts) == TWO
        assert isinstance(stmts[0], Assignment)
        assert stmts[0].name == "x"
        assert isinstance(stmts[1], PrintStatement)

    def test_three_statements(self) -> None:
        """Verify three statements parse correctly."""
        stmts = _stmts("let x = 1\nlet y = 2\nprint(x)")
        assert len(stmts) == THREE
        assert isinstance(stmts[0], Assignment)
        assert stmts[0].name == "x"
        assert isinstance(stmts[1], Assignment)
        assert stmts[1].name == "y"
        assert isinstance(stmts[2], PrintStatement)

    def test_empty_program(self) -> None:
        """Verify empty source parses to Program with no statements."""
        program = _parse("")
        assert isinstance(program, Program)
        assert program.statements == []

    def test_blank_lines_between_statements(self) -> None:
        """Verify blank lines between statements are tolerated."""
        stmts = _stmts("let x = 1\n\n\nprint(x)")
        assert len(stmts) == TWO


# -- Expression statements ---------------------------------------------------


class TestExpressionStatements:
    """Verify that bare expressions are parsed as statements.

    A bare identifier or function call on its own line should be accepted.
    """

    def test_bare_identifier_as_statement(self) -> None:
        """Verify a bare identifier is treated as a statement."""
        stmts = _stmts("x")
        assert len(stmts) == ONE

    def test_bare_expression_as_statement(self) -> None:
        """Verify a bare expression (e.g. function call) is a statement."""
        stmts = _stmts("1 + 2")
        assert len(stmts) == ONE


# -- Edge cases ---------------------------------------------------------------


class TestParserEdgeCases:
    """Verify edge cases and error paths in statement parsing."""

    def test_let_missing_expression_at_eof(self) -> None:
        """Verify 'let x =' with no expression raises ParseError."""
        with pytest.raises(ParseError, match="Expected expression"):
            _parse("let x = ")

    def test_let_newline_after_equals(self) -> None:
        """Verify 'let x =' followed by newline raises ParseError."""
        with pytest.raises(ParseError):
            _parse("let x =\n")

    def test_while_with_multiple_body_statements(self) -> None:
        """Verify a while loop with multiple body statements parses correctly."""
        source = "while x < 10 {\n    print(x)\n    x = x + 1\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, WhileLoop)
        assert len(stmt.body) == TWO
        assert isinstance(stmt.body[0], PrintStatement)
        assert isinstance(stmt.body[1], Reassignment)

    def test_nested_if_in_while(self) -> None:
        """Verify an if statement nested inside a while loop parses."""
        source = "while true {\n    if x > 0 {\n        print(x)\n    }\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        stmt = stmts[0]
        assert isinstance(stmt, WhileLoop)
        assert len(stmt.body) == ONE
        assert isinstance(stmt.body[0], IfStatement)

    def test_while_missing_closing_brace_raises(self) -> None:
        """Verify missing '}' in while loop raises ParseError."""
        with pytest.raises(ParseError, match="Expected '\\}'"):
            _parse("while true {\n    print(1)")

    def test_bare_identifier_is_expression_statement(self) -> None:
        """Verify a bare identifier parses as an Identifier expression."""
        stmts = _stmts("myvar")
        assert len(stmts) == ONE
        assert isinstance(stmts[0], Identifier)
        assert stmts[0].name == "myvar"

    def test_only_newlines_is_empty_program(self) -> None:
        """Verify source with only newlines is an empty program."""
        program = _parse("\n\n\n")
        assert program.statements == []

    def test_deeply_nested_blocks(self) -> None:
        """Verify nested if/while blocks parse correctly."""
        source = "if true {\n    if false {\n        print(1)\n    }\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        outer = stmts[0]
        assert isinstance(outer, IfStatement)
        assert len(outer.body) == ONE
        inner = outer.body[0]
        assert isinstance(inner, IfStatement)
        assert len(inner.body) == ONE


# -- Functions integration ----------------------------------------------------


class TestFunctionsIntegration:
    """Verify combined parsing of functions, for-loops, and return."""

    def test_function_call_as_expression_statement(self) -> None:
        """Verify 'greet()' on its own line parses as FunctionCall."""
        stmts = _stmts("greet()")
        assert len(stmts) == ONE
        assert isinstance(stmts[0], FunctionCall)
        assert stmts[0].name == "greet"

    def test_for_loop_containing_if(self) -> None:
        """Verify a for loop with a nested if statement parses correctly."""
        source = "for i in items {\n    if i > 0 {\n        print(i)\n    }\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        loop = stmts[0]
        assert isinstance(loop, ForLoop)
        assert len(loop.body) == ONE
        assert isinstance(loop.body[0], IfStatement)

    def test_function_containing_for_loop(self) -> None:
        """Verify a function definition containing a for loop parses."""
        source = "fn process(items) {\n    for x in items {\n        print(x)\n    }\n}"
        stmts = _stmts(source)
        assert len(stmts) == ONE
        fn = stmts[0]
        assert isinstance(fn, FunctionDef)
        assert len(fn.body) == ONE
        assert isinstance(fn.body[0], ForLoop)

    def test_multiple_function_definitions(self) -> None:
        """Verify two function definitions parse as separate FunctionDef nodes."""
        source = "fn first() {\n    print(1)\n}\nfn second() {\n    print(2)\n}"
        stmts = _stmts(source)
        assert len(stmts) == TWO
        assert isinstance(stmts[0], FunctionDef)
        assert stmts[0].name == "first"
        assert isinstance(stmts[1], FunctionDef)
        assert stmts[1].name == "second"

    def test_range_as_for_loop_iterable(self) -> None:
        """Verify 'range(10)' as for-loop iterable parses as FunctionCall."""
        source = "for i in range(10) {\n    print(i)\n}"
        stmts = _stmts(source)
        loop = stmts[0]
        assert isinstance(loop, ForLoop)
        assert isinstance(loop.iterable, FunctionCall)
        assert loop.iterable.name == "range"
        assert len(loop.iterable.arguments) == ONE
