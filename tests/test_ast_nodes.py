"""Tests for the Pebble AST node dataclasses."""

import dataclasses

import pytest

from pebble.ast_nodes import (
    Assignment,
    BinaryOp,
    BooleanLiteral,
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
    StringLiteral,
    UnaryOp,
    WhileLoop,
)
from pebble.tokens import SourceLocation

# -- Named constants ----------------------------------------------------------

FIRST_LINE = 1
SECOND_LINE = 2
FIRST_COLUMN = 1
FIFTH_COLUMN = 5
ANSWER = 42
OTHER_VALUE = 7


def _loc(line: int = FIRST_LINE, column: int = FIRST_COLUMN) -> SourceLocation:
    """Return a SourceLocation helper."""
    return SourceLocation(line=line, column=column)


# -- Expression nodes ---------------------------------------------------------


class TestIntegerLiteral:
    """Verify the IntegerLiteral node."""

    def test_stores_value(self) -> None:
        """Verify an IntegerLiteral stores its integer value."""
        node = IntegerLiteral(value=ANSWER, location=_loc())
        assert node.value == ANSWER

    def test_stores_location(self) -> None:
        """Verify an IntegerLiteral stores its source location."""
        loc = _loc(line=SECOND_LINE, column=FIFTH_COLUMN)
        node = IntegerLiteral(value=ANSWER, location=loc)
        assert node.location == loc

    def test_is_frozen(self) -> None:
        """Verify IntegerLiteral is immutable."""
        node = IntegerLiteral(value=ANSWER, location=_loc())
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.value = OTHER_VALUE  # type: ignore[misc]


class TestStringLiteral:
    """Verify the StringLiteral node."""

    def test_stores_value(self) -> None:
        """Verify a StringLiteral stores its string value."""
        node = StringLiteral(value="hello", location=_loc())
        assert node.value == "hello"

    def test_empty_string(self) -> None:
        """Verify a StringLiteral can hold an empty string."""
        node = StringLiteral(value="", location=_loc())
        assert node.value == ""

    def test_is_frozen(self) -> None:
        """Verify StringLiteral is immutable."""
        node = StringLiteral(value="hi", location=_loc())
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.value = "bye"  # type: ignore[misc]


class TestBooleanLiteral:
    """Verify the BooleanLiteral node."""

    def test_true_value(self) -> None:
        """Verify a BooleanLiteral can store True."""
        node = BooleanLiteral(value=True, location=_loc())
        assert node.value is True

    def test_false_value(self) -> None:
        """Verify a BooleanLiteral can store False."""
        node = BooleanLiteral(value=False, location=_loc())
        assert node.value is False

    def test_is_frozen(self) -> None:
        """Verify BooleanLiteral is immutable."""
        node = BooleanLiteral(value=True, location=_loc())
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.value = False  # type: ignore[misc]


class TestIdentifier:
    """Verify the Identifier node."""

    def test_stores_name(self) -> None:
        """Verify an Identifier stores its name."""
        node = Identifier(name="x", location=_loc())
        assert node.name == "x"

    def test_is_frozen(self) -> None:
        """Verify Identifier is immutable."""
        node = Identifier(name="x", location=_loc())
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.name = "y"  # type: ignore[misc]


class TestUnaryOp:
    """Verify the UnaryOp node."""

    def test_stores_operator_and_operand(self) -> None:
        """Verify UnaryOp stores operator string and operand expression."""
        operand = IntegerLiteral(value=ANSWER, location=_loc())
        node = UnaryOp(operator="-", operand=operand, location=_loc())
        assert node.operator == "-"
        assert node.operand is operand

    def test_not_operator(self) -> None:
        """Verify UnaryOp supports 'not' operator."""
        operand = BooleanLiteral(value=True, location=_loc())
        node = UnaryOp(operator="not", operand=operand, location=_loc())
        assert node.operator == "not"

    def test_is_frozen(self) -> None:
        """Verify UnaryOp is immutable."""
        operand = IntegerLiteral(value=ANSWER, location=_loc())
        node = UnaryOp(operator="-", operand=operand, location=_loc())
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.operator = "+"  # type: ignore[misc]


class TestBinaryOp:
    """Verify the BinaryOp node."""

    def test_stores_left_operator_right(self) -> None:
        """Verify BinaryOp stores left, operator, and right."""
        left = IntegerLiteral(value=FIRST_LINE, location=_loc())
        right = IntegerLiteral(value=SECOND_LINE, location=_loc())
        node = BinaryOp(left=left, operator="+", right=right, location=_loc())
        assert node.left is left
        assert node.operator == "+"
        assert node.right is right

    def test_comparison_operator(self) -> None:
        """Verify BinaryOp supports comparison operators."""
        left = Identifier(name="x", location=_loc())
        right = IntegerLiteral(value=ANSWER, location=_loc())
        node = BinaryOp(left=left, operator=">=", right=right, location=_loc())
        assert node.operator == ">="

    def test_is_frozen(self) -> None:
        """Verify BinaryOp is immutable."""
        left = IntegerLiteral(value=FIRST_LINE, location=_loc())
        right = IntegerLiteral(value=SECOND_LINE, location=_loc())
        node = BinaryOp(left=left, operator="+", right=right, location=_loc())
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.operator = "-"  # type: ignore[misc]


class TestFunctionCall:
    """Verify the FunctionCall node."""

    def test_stores_name_and_args(self) -> None:
        """Verify FunctionCall stores function name and argument list."""
        arg = IntegerLiteral(value=ANSWER, location=_loc())
        node = FunctionCall(name="print", arguments=[arg], location=_loc())
        assert node.name == "print"
        assert node.arguments == [arg]

    def test_no_arguments(self) -> None:
        """Verify FunctionCall works with an empty argument list."""
        node = FunctionCall(name="greet", arguments=[], location=_loc())
        assert node.arguments == []

    def test_is_frozen(self) -> None:
        """Verify FunctionCall is immutable."""
        node = FunctionCall(name="f", arguments=[], location=_loc())
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.name = "g"  # type: ignore[misc]


# -- Statement nodes ----------------------------------------------------------


class TestAssignment:
    """Verify the Assignment (let declaration) node."""

    def test_stores_name_and_value(self) -> None:
        """Verify Assignment stores variable name and value expression."""
        value = IntegerLiteral(value=ANSWER, location=_loc())
        node = Assignment(name="x", value=value, location=_loc())
        assert node.name == "x"
        assert node.value is value

    def test_is_frozen(self) -> None:
        """Verify Assignment is immutable."""
        value = IntegerLiteral(value=ANSWER, location=_loc())
        node = Assignment(name="x", value=value, location=_loc())
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.name = "y"  # type: ignore[misc]


class TestReassignment:
    """Verify the Reassignment node."""

    def test_stores_name_and_value(self) -> None:
        """Verify Reassignment stores variable name and new value."""
        value = IntegerLiteral(value=OTHER_VALUE, location=_loc())
        node = Reassignment(name="x", value=value, location=_loc())
        assert node.name == "x"
        assert node.value is value


class TestPrintStatement:
    """Verify the PrintStatement node."""

    def test_stores_expression(self) -> None:
        """Verify PrintStatement stores the expression to print."""
        expr = StringLiteral(value="hello", location=_loc())
        node = PrintStatement(expression=expr, location=_loc())
        assert node.expression is expr


class TestIfStatement:
    """Verify the IfStatement node."""

    def test_stores_condition_and_body(self) -> None:
        """Verify IfStatement stores condition, body, and no else_body."""
        cond = BooleanLiteral(value=True, location=_loc())
        body_stmt = PrintStatement(
            expression=StringLiteral(value="yes", location=_loc()), location=_loc()
        )
        node = IfStatement(condition=cond, body=[body_stmt], else_body=None, location=_loc())
        assert node.condition is cond
        assert node.body == [body_stmt]
        assert node.else_body is None

    def test_stores_else_body(self) -> None:
        """Verify IfStatement stores an else body when present."""
        cond = BooleanLiteral(value=False, location=_loc())
        then_stmt = PrintStatement(
            expression=StringLiteral(value="yes", location=_loc()), location=_loc()
        )
        else_stmt = PrintStatement(
            expression=StringLiteral(value="no", location=_loc()), location=_loc()
        )
        node = IfStatement(condition=cond, body=[then_stmt], else_body=[else_stmt], location=_loc())
        assert node.else_body == [else_stmt]

    def test_is_frozen(self) -> None:
        """Verify IfStatement is immutable."""
        cond = BooleanLiteral(value=True, location=_loc())
        node = IfStatement(condition=cond, body=[], else_body=None, location=_loc())
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.condition = BooleanLiteral(value=False, location=_loc())  # type: ignore[misc]


class TestWhileLoop:
    """Verify the WhileLoop node."""

    def test_stores_condition_and_body(self) -> None:
        """Verify WhileLoop stores condition and body statements."""
        cond = BooleanLiteral(value=True, location=_loc())
        body_stmt = PrintStatement(
            expression=StringLiteral(value="loop", location=_loc()), location=_loc()
        )
        node = WhileLoop(condition=cond, body=[body_stmt], location=_loc())
        assert node.condition is cond
        assert node.body == [body_stmt]


class TestForLoop:
    """Verify the ForLoop node."""

    def test_stores_variable_iterable_body(self) -> None:
        """Verify ForLoop stores variable name, iterable, and body."""
        iterable = FunctionCall(
            name="range", arguments=[IntegerLiteral(value=ANSWER, location=_loc())], location=_loc()
        )
        body_stmt = PrintStatement(
            expression=Identifier(name="i", location=_loc()), location=_loc()
        )
        node = ForLoop(variable="i", iterable=iterable, body=[body_stmt], location=_loc())
        assert node.variable == "i"
        assert node.iterable is iterable
        assert node.body == [body_stmt]


class TestFunctionDef:
    """Verify the FunctionDef node."""

    def test_stores_name_params_body(self) -> None:
        """Verify FunctionDef stores name, parameters, and body."""
        body_stmt = ReturnStatement(
            value=IntegerLiteral(value=ANSWER, location=_loc()), location=_loc()
        )
        node = FunctionDef(name="add", parameters=["a", "b"], body=[body_stmt], location=_loc())
        assert node.name == "add"
        assert node.parameters == ["a", "b"]
        assert node.body == [body_stmt]

    def test_no_parameters(self) -> None:
        """Verify FunctionDef works with an empty parameter list."""
        node = FunctionDef(name="greet", parameters=[], body=[], location=_loc())
        assert node.parameters == []


class TestReturnStatement:
    """Verify the ReturnStatement node."""

    def test_stores_value(self) -> None:
        """Verify ReturnStatement stores the return value expression."""
        value = IntegerLiteral(value=ANSWER, location=_loc())
        node = ReturnStatement(value=value, location=_loc())
        assert node.value is value

    def test_none_value(self) -> None:
        """Verify ReturnStatement allows None (bare return)."""
        node = ReturnStatement(value=None, location=_loc())
        assert node.value is None


class TestProgram:
    """Verify the Program root node."""

    def test_stores_statements(self) -> None:
        """Verify Program stores a list of top-level statements."""
        stmt1 = Assignment(
            name="x", value=IntegerLiteral(value=FIRST_LINE, location=_loc()), location=_loc()
        )
        stmt2 = PrintStatement(expression=Identifier(name="x", location=_loc()), location=_loc())
        node = Program(statements=[stmt1, stmt2])
        assert len(node.statements) == SECOND_LINE
        assert node.statements[0] is stmt1
        assert node.statements[1] is stmt2

    def test_empty_program(self) -> None:
        """Verify Program works with no statements."""
        node = Program(statements=[])
        assert node.statements == []

    def test_is_frozen(self) -> None:
        """Verify Program is immutable."""
        node = Program(statements=[])
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.statements = []  # type: ignore[misc]
