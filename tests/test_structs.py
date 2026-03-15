"""Tests for structs/records: custom data types with named fields."""

from io import StringIO

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import (
    FieldAccess,
    FieldAssignment,
    Identifier,
    IntegerLiteral,
    MethodCall,
    PrintStatement,
    StructDef,
)
from pebble.builtins import StructInstance, _builtin_type, format_value
from pebble.bytecode import OpCode
from pebble.compiler import Compiler
from pebble.errors import ParseError, PebbleRuntimeError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.tokens import SourceLocation, TokenKind
from pebble.vm import VirtualMachine

# -- Named constants ----------------------------------------------------------

FIELD_X = 10
FIELD_Y = 20
FIELD_NEW_X = 30
TWO_FIELDS = 2
THREE_FIELDS = 3


# -- Helpers ------------------------------------------------------------------


def _lex(source: str) -> list[TokenKind]:
    """Lex and return just the token kinds."""
    return [t.kind for t in Lexer(source).tokenize()]


def _parse(source: str) -> list[object]:
    """Lex + parse helper returning the statement list."""
    tokens = Lexer(source).tokenize()
    return list(Parser(tokens).parse().statements)


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


def _compile_instructions(source: str) -> list[tuple[OpCode, object]]:
    """Lex + parse + analyze + compile, return (opcode, operand) pairs."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzer = SemanticAnalyzer()
    program = analyzer.analyze(program)
    compiled = Compiler(
        cell_vars=analyzer.cell_vars,
        free_vars=analyzer.free_vars,
    ).compile(program)
    return [(i.opcode, i.operand) for i in compiled.main.instructions]


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
# Cycle 1: Token + AST + Builtins foundations
# =============================================================================


class TestStructToken:
    """Verify struct tokenizes as a keyword."""

    def test_struct_keyword_token(self) -> None:
        """Verify 'struct' produces a STRUCT token."""
        kinds = _lex("struct")
        assert TokenKind.STRUCT in kinds

    def test_struct_not_identifier(self) -> None:
        """Verify 'struct' is not lexed as IDENTIFIER."""
        kinds = _lex("struct")
        assert TokenKind.IDENTIFIER not in kinds


class TestStructASTNodes:
    """Verify the three new AST nodes can be constructed."""

    def test_struct_def_construction(self) -> None:
        """StructDef stores name, fields, body, and location."""
        node = StructDef(
            name="Point",
            fields=["x", "y"],
            body=[],
            location=SourceLocation(1, 1),
        )
        assert node.name == "Point"
        assert node.fields == ["x", "y"]
        assert node.body == []

    def test_field_access_construction(self) -> None:
        """FieldAccess stores target, field, and location."""
        target = Identifier(name="p", location=SourceLocation(1, 1))
        node = FieldAccess(
            target=target,
            field="x",
            location=SourceLocation(1, 2),
        )
        assert node.field == "x"
        assert isinstance(node.target, Identifier)

    def test_field_assignment_construction(self) -> None:
        """FieldAssignment stores target, field, value, and location."""
        target = Identifier(name="p", location=SourceLocation(1, 1))
        value = IntegerLiteral(value=5, location=SourceLocation(1, 7))
        node = FieldAssignment(
            target=target,
            field="x",
            value=value,
            location=SourceLocation(1, 2),
        )
        assert node.field == "x"
        assert isinstance(node.value, IntegerLiteral)


class TestStructInstanceBuiltin:
    """Verify StructInstance, format_value, and _builtin_type."""

    def test_struct_instance_creation(self) -> None:
        """StructInstance stores type_name and fields dict."""
        inst = StructInstance(type_name="Point", fields={"x": 10, "y": 20})
        assert inst.type_name == "Point"
        assert inst.fields["x"] == FIELD_X
        assert inst.fields["y"] == FIELD_Y

    def test_struct_instance_field_mutation(self) -> None:
        """StructInstance fields are mutable."""
        inst = StructInstance(type_name="Point", fields={"x": 10, "y": 20})
        inst.fields["x"] = 30
        assert inst.fields["x"] == FIELD_NEW_X

    def test_format_value_struct(self) -> None:
        """format_value renders a struct as Name(field=value, ...)."""
        inst = StructInstance(type_name="Point", fields={"x": 10, "y": 20})
        assert format_value(inst) == "Point(x=10, y=20)"

    def test_builtin_type_struct(self) -> None:
        """type() returns the struct's type name."""
        inst = StructInstance(type_name="Point", fields={"x": 10, "y": 20})
        assert _builtin_type([inst]) == "Point"


class TestStructOpcodes:
    """Verify the two new opcodes exist."""

    def test_get_field_opcode_exists(self) -> None:
        """GET_FIELD is a valid OpCode."""
        assert OpCode.GET_FIELD == "GET_FIELD"

    def test_set_field_opcode_exists(self) -> None:
        """SET_FIELD is a valid OpCode."""
        assert OpCode.SET_FIELD == "SET_FIELD"


# =============================================================================
# Cycle 2: Parser
# =============================================================================


class TestStructParser:
    """Verify parsing of struct definitions, field access, and field assignment."""

    def test_parse_struct_def(self) -> None:
        """Parse 'struct Point { x, y }' into StructDef."""
        stmts = _parse("struct Point { x, y }")
        assert len(stmts) == 1
        node = stmts[0]
        assert isinstance(node, StructDef)
        assert node.name == "Point"
        assert node.fields == ["x", "y"]

    def test_parse_struct_single_field(self) -> None:
        """Parse struct with a single field."""
        stmts = _parse("struct Single { value }")
        node = stmts[0]
        assert isinstance(node, StructDef)
        assert node.fields == ["value"]

    def test_parse_struct_three_fields(self) -> None:
        """Parse struct with three fields."""
        stmts = _parse("struct Color { r, g, b }")
        node = stmts[0]
        assert isinstance(node, StructDef)
        assert len(node.fields) == THREE_FIELDS

    def test_parse_struct_duplicate_field_error(self) -> None:
        """Duplicate field names are a parse error."""
        with pytest.raises(ParseError, match="Duplicate field"):
            _parse("struct Bad { x, x }")

    def test_parse_field_access(self) -> None:
        """Parse 'p.x' into FieldAccess."""
        stmts = _parse("let p = Point(1, 2)\nprint(p.x)")
        # The print statement contains a FieldAccess as its expression
        print_stmt = stmts[1]
        assert isinstance(print_stmt, PrintStatement)
        assert isinstance(print_stmt.expression, FieldAccess)
        assert print_stmt.expression.field == "x"

    def test_parse_field_assignment(self) -> None:
        """Parse 'p.x = 5' into FieldAssignment."""
        stmts = _parse("let p = Point(1, 2)\np.x = 5")
        node = stmts[1]
        assert isinstance(node, FieldAssignment)
        assert node.field == "x"

    def test_parse_method_call_still_works(self) -> None:
        """Method calls like 's.upper()' still produce MethodCall."""
        stmts = _parse('let s = "hello"\nprint(s.upper())')
        print_stmt = stmts[1]
        assert isinstance(print_stmt, PrintStatement)
        assert isinstance(print_stmt.expression, MethodCall)


# =============================================================================
# Cycle 3: Analyzer
# =============================================================================


class TestStructAnalyzer:
    """Verify semantic analysis of struct definitions and field operations."""

    def test_struct_declared_in_scope(self) -> None:
        """Struct definition passes analysis without error."""
        _analyze("struct Point { x, y }")

    def test_struct_constructor_arity(self) -> None:
        """Struct constructor arity matches field count."""
        _analyze("struct Point { x, y }\nlet p = Point(1, 2)")

    def test_struct_constructor_wrong_arity(self) -> None:
        """Wrong argument count to struct constructor is a semantic error."""
        with pytest.raises(SemanticError, match="expects 2 arguments"):
            _analyze("struct Point { x, y }\nlet p = Point(1)")

    def test_duplicate_struct_name_error(self) -> None:
        """Redefining a struct in the same scope is a semantic error."""
        with pytest.raises(SemanticError, match="already defined"):
            _analyze("struct Point { x, y }\nstruct Point { a, b }")

    def test_field_access_undeclared_target(self) -> None:
        """Field access on undeclared variable is a semantic error."""
        with pytest.raises(SemanticError, match="Undeclared variable"):
            _analyze("print(p.x)")

    def test_field_assignment_undeclared_target(self) -> None:
        """Field assignment on undeclared variable is a semantic error."""
        with pytest.raises(SemanticError, match="Undeclared variable"):
            _analyze("p.x = 5")

    def test_field_access_passes_analysis(self) -> None:
        """Field access on declared variable passes analysis."""
        _analyze("struct Point { x, y }\nlet p = Point(1, 2)\nprint(p.x)")

    def test_field_assignment_passes_analysis(self) -> None:
        """Field assignment on declared variable passes analysis."""
        _analyze("struct Point { x, y }\nlet p = Point(1, 2)\np.x = 5")


# =============================================================================
# Cycle 4: Compiler + VM
# =============================================================================


class TestStructCompiler:
    """Verify compilation of struct operations."""

    def test_struct_def_stores_metadata(self) -> None:
        """Struct definition stores metadata but emits no bytecode."""
        opcodes = _compile_opcodes("struct Point { x, y }")
        # Only HALT should be emitted — no bytecode for the struct def itself
        assert opcodes == [OpCode.HALT]

    def test_field_access_emits_get_field(self) -> None:
        """Field access emits GET_FIELD opcode."""
        opcodes = _compile_opcodes("struct Point { x, y }\nlet p = Point(1, 2)\nprint(p.x)")
        assert OpCode.GET_FIELD in opcodes

    def test_field_assignment_emits_set_field(self) -> None:
        """Field assignment emits SET_FIELD opcode."""
        opcodes = _compile_opcodes("struct Point { x, y }\nlet p = Point(1, 2)\np.x = 5")
        assert OpCode.SET_FIELD in opcodes

    def test_get_field_operand_is_field_name(self) -> None:
        """GET_FIELD instruction carries the field name as operand."""
        instructions = _compile_instructions(
            "struct Point { x, y }\nlet p = Point(1, 2)\nprint(p.x)"
        )
        get_fields = [(op, operand) for op, operand in instructions if op == OpCode.GET_FIELD]
        assert get_fields == [(OpCode.GET_FIELD, "x")]

    def test_set_field_operand_is_field_name(self) -> None:
        """SET_FIELD instruction carries the field name as operand."""
        instructions = _compile_instructions("struct Point { x, y }\nlet p = Point(1, 2)\np.x = 5")
        set_fields = [(op, operand) for op, operand in instructions if op == OpCode.SET_FIELD]
        assert set_fields == [(OpCode.SET_FIELD, "x")]


# =============================================================================
# End-to-end tests
# =============================================================================


class TestStructEndToEnd:
    """End-to-end tests for struct construction, access, and mutation."""

    def test_construct_and_read_fields(self) -> None:
        """Construct a struct and read its fields."""
        output = _run_source(
            "struct Point { x, y }\nlet p = Point(10, 20)\nprint(p.x)\nprint(p.y)\n"
        )
        assert output.strip() == "10\n20"

    def test_field_assignment_mutates(self) -> None:
        """Field assignment mutates the struct instance."""
        output = _run_source("struct Point { x, y }\nlet p = Point(10, 20)\np.x = 30\nprint(p.x)\n")
        assert output.strip() == "30"

    def test_type_returns_struct_name(self) -> None:
        """type() returns the struct's type name."""
        output = _run_source("struct Point { x, y }\nlet p = Point(10, 20)\nprint(type(p))\n")
        assert output.strip() == "Point"

    def test_print_displays_struct(self) -> None:
        """print() displays struct as Name(field=value, ...)."""
        output = _run_source("struct Point { x, y }\nlet p = Point(10, 20)\nprint(p)\n")
        assert output.strip() == "Point(x=10, y=20)"

    def test_equality_same_fields(self) -> None:
        """Structs with same type and field values are equal."""
        output = _run_source(
            "struct Point { x, y }\nlet a = Point(10, 20)\nlet b = Point(10, 20)\nprint(a == b)\n"
        )
        assert output.strip() == "true"

    def test_equality_different_values(self) -> None:
        """Structs with different field values are not equal."""
        output = _run_source(
            "struct Point { x, y }\nlet a = Point(10, 20)\nlet b = Point(10, 30)\nprint(a == b)\n"
        )
        assert output.strip() == "false"

    def test_equality_different_types(self) -> None:
        """Different struct types with same values are not equal."""
        output = _run_source(
            "struct Point { x, y }\n"
            "struct Vec { x, y }\n"
            "let a = Point(10, 20)\n"
            "let b = Vec(10, 20)\n"
            "print(a == b)\n"
        )
        assert output.strip() == "false"

    def test_wrong_arg_count_error(self) -> None:
        """Wrong argument count to struct constructor is a semantic error."""
        with pytest.raises(SemanticError, match="expects 2 arguments"):
            _run_source("struct Point { x, y }\nlet p = Point(1)")

    def test_access_nonexistent_field_error(self) -> None:
        """Accessing a nonexistent field is a runtime error."""
        with pytest.raises(PebbleRuntimeError, match="has no field 'z'"):
            _run_source("struct Point { x, y }\nlet p = Point(10, 20)\nprint(p.z)\n")

    def test_set_nonexistent_field_error(self) -> None:
        """Setting a nonexistent field is a runtime error."""
        with pytest.raises(PebbleRuntimeError, match="has no field 'z'"):
            _run_source("struct Point { x, y }\nlet p = Point(10, 20)\np.z = 5\n")

    def test_get_field_on_non_struct_error(self) -> None:
        """GET_FIELD on a non-struct value is a runtime error."""
        with pytest.raises(PebbleRuntimeError, match="not a struct"):
            _run_source("let x = 42\nprint(x.y)\n")

    def test_set_field_on_non_struct_error(self) -> None:
        """SET_FIELD on a non-struct value is a runtime error."""
        with pytest.raises(PebbleRuntimeError, match="not a struct"):
            _run_source("let x = 42\nx.y = 5\n")

    def test_struct_inside_function(self) -> None:
        """Struct defined inside a function body works."""
        output = _run_source(
            "fn make_point() {\n"
            "  struct Point { x, y }\n"
            "  return Point(1, 2)\n"
            "}\n"
            "let p = make_point()\n"
            "print(p.x)\n"
        )
        assert output.strip() == "1"

    def test_struct_as_function_parameter(self) -> None:
        """Struct instance can be passed as a function argument."""
        output = _run_source(
            "struct Point { x, y }\n"
            "fn get_x(p) { return p.x }\n"
            "let p = Point(10, 20)\n"
            "print(get_x(p))\n"
        )
        assert output.strip() == "10"

    def test_struct_as_return_value(self) -> None:
        """Struct instance can be returned from a function."""
        output = _run_source(
            "struct Point { x, y }\n"
            "fn origin() { return Point(0, 0) }\n"
            "let p = origin()\n"
            "print(p.x)\n"
            "print(p.y)\n"
        )
        assert output.strip() == "0\n0"

    def test_struct_in_list(self) -> None:
        """Struct instances can be stored in a list."""
        output = _run_source(
            "struct Point { x, y }\n"
            "let points = [Point(1, 2), Point(3, 4)]\n"
            "print(points[0].x)\n"
            "print(points[1].y)\n"
        )
        assert output.strip() == "1\n4"

    def test_nested_struct(self) -> None:
        """Struct field can hold another struct."""
        output = _run_source(
            "struct Point { x, y }\n"
            "struct Line { start, end }\n"
            "let line = Line(Point(0, 0), Point(10, 10))\n"
            "print(line.start.x)\n"
            "print(line.end.y)\n"
        )
        assert output.strip() == "0\n10"

    def test_const_binding_field_mutation(self) -> None:
        """Field mutation through const binding is allowed (like const lists)."""
        output = _run_source(
            "struct Point { x, y }\nconst p = Point(10, 20)\np.x = 30\nprint(p.x)\n"
        )
        assert output.strip() == "30"

    def test_struct_in_loop(self) -> None:
        """Structs work correctly inside a loop."""
        output = _run_source(
            "struct Point { x, y }\n"
            "for i in range(3) {\n"
            "  let p = Point(i, i * 2)\n"
            "  print(p.y)\n"
            "}\n"
        )
        assert output.strip() == "0\n2\n4"

    def test_struct_with_match_on_field(self) -> None:
        """Pattern matching on a struct field value works."""
        output = _run_source(
            "struct Point { x, y }\n"
            "let p = Point(1, 2)\n"
            "match p.x {\n"
            "  case 1 { print(1) }\n"
            "  case _ { print(0) }\n"
            "}\n"
        )
        assert output.strip() == "1"

    def test_struct_in_dict(self) -> None:
        """Struct instance can be stored as a dict value."""
        output = _run_source(
            'struct Point { x, y }\nlet d = {"origin": Point(0, 0)}\nprint(d["origin"].x)\n'
        )
        assert output.strip() == "0"

    def test_print_mutated_struct(self) -> None:
        """Print displays updated field values after mutation."""
        output = _run_source("struct Point { x, y }\nlet p = Point(10, 20)\np.x = 30\nprint(p)\n")
        assert output.strip() == "Point(x=30, y=20)"

    def test_inequality_operator(self) -> None:
        """Structs support != comparison."""
        output = _run_source(
            "struct Point { x, y }\nlet a = Point(1, 2)\nlet b = Point(3, 4)\nprint(a != b)\n"
        )
        assert output.strip() == "true"

    def test_struct_field_access_chain(self) -> None:
        """Chained field access like line.start.x works."""
        output = _run_source(
            "struct Point { x, y }\n"
            "struct Line { start, end }\n"
            "let line = Line(Point(1, 2), Point(3, 4))\n"
            "print(line.start.x)\n"
            "print(line.end.y)\n"
        )
        assert output.strip() == "1\n4"
