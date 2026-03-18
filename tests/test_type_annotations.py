"""Tests for type annotations: optional type checking with runtime enforcement.

Cover the full pipeline — tokens, AST, lexer, parser, analyzer, bytecode,
compiler, VM runtime, integration, resolver, and REPL.
"""

from io import StringIO
from pathlib import Path

import pytest

from pebble.ast_nodes import (
    Assignment,
    ConstAssignment,
    FunctionDef,
    FunctionExpression,
    IntegerLiteral,
    Parameter,
    StructDef,
    TypeAnnotation,
)
from pebble.bytecode import CodeObject, OpCode
from pebble.errors import ParseError, PebbleRuntimeError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.repl import Repl
from pebble.tokens import SourceLocation, TokenKind
from tests.conftest import (
    analyze,
    compile_opcodes,
    compile_source,
    run_source,
    run_source_with_imports,
)

# -- Named constants ----------------------------------------------------------

FIRST_INDEX = 0
SECOND_INDEX = 1
THIRD_INDEX = 2


# -- Helpers ------------------------------------------------------------------


def _lex(source: str) -> list[TokenKind]:
    """Lex and return just the token kinds."""
    return [t.kind for t in Lexer(source).tokenize()]


def _parse(source: str) -> list[object]:
    """Lex + parse helper returning the statement list."""
    tokens = Lexer(source).tokenize()
    return list(Parser(tokens).parse().statements)


# =============================================================================
# Cycle 1: Token + AST
# =============================================================================


class TestArrowToken:
    """Verify the ARROW token kind exists."""

    def test_arrow_in_token_kind(self) -> None:
        """ARROW is a valid TokenKind member."""
        assert TokenKind.ARROW == "ARROW"

    def test_arrow_is_str_enum(self) -> None:
        """ARROW value is also a str."""
        assert isinstance(TokenKind.ARROW, str)


class TestParameterNode:
    """Verify the Parameter dataclass works correctly."""

    def test_parameter_with_annotation(self) -> None:
        """Create a Parameter with a type annotation."""
        param = Parameter(name="x", type_annotation=TypeAnnotation(name="Int"))
        assert param.name == "x"
        assert param.type_annotation == TypeAnnotation(name="Int")

    def test_parameter_without_annotation(self) -> None:
        """Type annotation defaults to None."""
        param = Parameter(name="x")
        assert param.name == "x"
        assert param.type_annotation is None


class TestModifiedASTNodes:
    """Verify modified AST nodes accept type annotations."""

    def test_function_def_with_return_type(self) -> None:
        """FunctionDef accepts Parameter objects and return_type."""
        loc = SourceLocation(line=1, column=1)
        node = FunctionDef(
            name="add",
            parameters=[Parameter(name="a", type_annotation=TypeAnnotation(name="Int"))],
            body=[],
            return_type=TypeAnnotation(name="Int"),
            location=loc,
        )
        assert node.parameters[FIRST_INDEX].type_annotation == TypeAnnotation(name="Int")
        assert node.return_type == TypeAnnotation(name="Int")

    def test_assignment_with_type_annotation(self) -> None:
        """Assignment node stores type annotation."""
        loc = SourceLocation(line=1, column=1)
        node = Assignment(
            name="x",
            value=IntegerLiteral(value=5, location=loc),
            type_annotation=TypeAnnotation(name="Int"),
            location=loc,
        )
        assert node.type_annotation == TypeAnnotation(name="Int")

    def test_struct_def_with_typed_fields(self) -> None:
        """StructDef fields use Parameter with type annotations."""
        loc = SourceLocation(line=1, column=1)
        node = StructDef(
            name="Point",
            fields=[
                Parameter(name="x", type_annotation=TypeAnnotation(name="Float")),
                Parameter(name="y", type_annotation=TypeAnnotation(name="Float")),
            ],
            body=[],
            location=loc,
        )
        assert node.fields[FIRST_INDEX].type_annotation == TypeAnnotation(name="Float")
        assert node.fields[SECOND_INDEX].type_annotation == TypeAnnotation(name="Float")

    def test_gradual_typing_no_annotations(self) -> None:
        """Nodes work without any type annotations (gradual typing)."""
        loc = SourceLocation(line=1, column=1)
        node = FunctionDef(
            name="greet",
            parameters=[Parameter(name="name")],
            body=[],
            location=loc,
        )
        assert node.parameters[FIRST_INDEX].type_annotation is None
        assert node.return_type is None


# =============================================================================
# Cycle 2: Lexer + Parser
# =============================================================================


class TestLexerArrow:
    """Verify the lexer handles ``->`` and ``-`` correctly."""

    def test_arrow_token(self) -> None:
        """``->`` produces a single ARROW token."""
        kinds = _lex("->")
        assert TokenKind.ARROW in kinds

    def test_minus_token(self) -> None:
        """``- 5`` produces MINUS, not ARROW."""
        kinds = _lex("- 5")
        assert TokenKind.MINUS in kinds
        assert TokenKind.ARROW not in kinds

    def test_full_function_signature(self) -> None:
        """A full typed function signature lexes correctly."""
        kinds = _lex("fn add(a: Int, b: Int) -> Int {}")
        assert TokenKind.ARROW in kinds
        assert TokenKind.COLON in kinds


class TestParseParamAnnotations:
    """Verify parser handles function parameter type annotations."""

    def test_single_typed_param(self) -> None:
        """``fn f(x: Int)`` produces Parameter with type_annotation."""
        stmts = _parse("fn f(x: Int) { return x }")
        fn = stmts[FIRST_INDEX]
        assert isinstance(fn, FunctionDef)
        assert fn.parameters == [Parameter(name="x", type_annotation=TypeAnnotation(name="Int"))]

    def test_multiple_typed_params(self) -> None:
        """``fn f(a: Int, b: String)`` produces correct parameters."""
        stmts = _parse("fn f(a: Int, b: String) { return a }")
        fn = stmts[FIRST_INDEX]
        assert isinstance(fn, FunctionDef)
        assert fn.parameters == [
            Parameter(name="a", type_annotation=TypeAnnotation(name="Int")),
            Parameter(name="b", type_annotation=TypeAnnotation(name="String")),
        ]

    def test_mixed_typed_and_untyped(self) -> None:
        """Some params typed, others not."""
        stmts = _parse("fn f(a: Int, b) { return a }")
        fn = stmts[FIRST_INDEX]
        assert isinstance(fn, FunctionDef)
        assert fn.parameters == [
            Parameter(name="a", type_annotation=TypeAnnotation(name="Int")),
            Parameter(name="b"),
        ]

    def test_no_annotations(self) -> None:
        """Unannotated params still work."""
        stmts = _parse("fn f(x) { return x }")
        fn = stmts[FIRST_INDEX]
        assert isinstance(fn, FunctionDef)
        assert fn.parameters == [Parameter(name="x")]


class TestParseReturnTypes:
    """Verify parser handles return type annotations."""

    def test_with_return_type(self) -> None:
        """``fn f() -> Int`` stores return_type."""
        stmts = _parse("fn f() -> Int { return 0 }")
        fn = stmts[FIRST_INDEX]
        assert isinstance(fn, FunctionDef)
        assert fn.return_type == TypeAnnotation(name="Int")

    def test_without_return_type(self) -> None:
        """No ``->`` means return_type is None."""
        stmts = _parse("fn f() { return 0 }")
        fn = stmts[FIRST_INDEX]
        assert isinstance(fn, FunctionDef)
        assert fn.return_type is None

    def test_combined_params_and_return(self) -> None:
        """Full signature with typed params and return type."""
        stmts = _parse("fn add(a: Int, b: Int) -> Int { return a + b }")
        fn = stmts[FIRST_INDEX]
        assert isinstance(fn, FunctionDef)
        assert fn.parameters == [
            Parameter(name="a", type_annotation=TypeAnnotation(name="Int")),
            Parameter(name="b", type_annotation=TypeAnnotation(name="Int")),
        ]
        assert fn.return_type == TypeAnnotation(name="Int")


class TestParseVariableAnnotations:
    """Verify parser handles let/const type annotations."""

    def test_let_with_type(self) -> None:
        """``let x: Int = 5`` stores type_annotation."""
        stmts = _parse("let x: Int = 5")
        node = stmts[FIRST_INDEX]
        assert isinstance(node, Assignment)
        assert node.type_annotation == TypeAnnotation(name="Int")

    def test_let_without_type(self) -> None:
        """``let x = 5`` has type_annotation = None."""
        stmts = _parse("let x = 5")
        node = stmts[FIRST_INDEX]
        assert isinstance(node, Assignment)
        assert node.type_annotation is None

    def test_const_with_type(self) -> None:
        """``const pi: Float = 3.14`` stores type_annotation."""
        stmts = _parse("const pi: Float = 3.14")
        node = stmts[FIRST_INDEX]
        assert isinstance(node, ConstAssignment)
        assert node.type_annotation == TypeAnnotation(name="Float")

    def test_const_without_type(self) -> None:
        """``const pi = 3.14`` has type_annotation = None."""
        stmts = _parse("const pi = 3.14")
        node = stmts[FIRST_INDEX]
        assert isinstance(node, ConstAssignment)
        assert node.type_annotation is None

    def test_unpack_with_type_annotation_rejected(self) -> None:
        """Type annotations on unpacking declarations are rejected."""
        with pytest.raises(ParseError, match="Type annotations not supported"):
            _parse("let x: Int, y = [1, 2]")


class TestParseStructAnnotations:
    """Verify parser handles struct field type annotations."""

    def test_typed_fields(self) -> None:
        """``struct Point { x: Float, y: Float }`` uses Parameter."""
        stmts = _parse("struct Point { x: Float, y: Float }")
        struct = stmts[FIRST_INDEX]
        assert isinstance(struct, StructDef)
        assert struct.fields == [
            Parameter(name="x", type_annotation=TypeAnnotation(name="Float")),
            Parameter(name="y", type_annotation=TypeAnnotation(name="Float")),
        ]

    def test_mixed_fields(self) -> None:
        """Some fields typed, some not."""
        stmts = _parse("struct Mixed { x: Int, y }")
        struct = stmts[FIRST_INDEX]
        assert isinstance(struct, StructDef)
        assert struct.fields == [
            Parameter(name="x", type_annotation=TypeAnnotation(name="Int")),
            Parameter(name="y"),
        ]

    def test_untyped_fields(self) -> None:
        """No annotations — backward compatible."""
        stmts = _parse("struct Pair { a, b }")
        struct = stmts[FIRST_INDEX]
        assert isinstance(struct, StructDef)
        assert struct.fields == [
            Parameter(name="a"),
            Parameter(name="b"),
        ]


class TestParseFunctionExpressions:
    """Verify parser handles anonymous function type annotations."""

    def test_anon_fn_with_types(self) -> None:
        """``let f = fn(x: Int) -> Int { return x }`` parses correctly."""
        stmts = _parse("let f = fn(x: Int) -> Int { return x }")
        assign = stmts[FIRST_INDEX]
        assert isinstance(assign, Assignment)
        assert isinstance(assign.value, FunctionExpression)
        fn_expr = assign.value
        assert fn_expr.parameters == [
            Parameter(name="x", type_annotation=TypeAnnotation(name="Int"))
        ]
        assert fn_expr.return_type == TypeAnnotation(name="Int")

    def test_anon_fn_without_types(self) -> None:
        """``let f = fn(x) { return x }`` still works."""
        stmts = _parse("let f = fn(x) { return x }")
        assign = stmts[FIRST_INDEX]
        assert isinstance(assign, Assignment)
        fn_expr = assign.value
        assert isinstance(fn_expr, FunctionExpression)
        assert fn_expr.parameters == [Parameter(name="x")]
        assert fn_expr.return_type is None


# =============================================================================
# Cycle 3: Analyzer
# =============================================================================


class TestAnalyzerTypeValidation:
    """Verify the analyzer validates type names."""

    def test_builtin_int_valid(self) -> None:
        """``Int`` is accepted as a valid type."""
        analyze("let x: Int = 5")

    def test_builtin_float_valid(self) -> None:
        """``Float`` is accepted as a valid type."""
        analyze("let x: Float = 3.14")

    def test_builtin_string_valid(self) -> None:
        """``String`` is accepted as a valid type."""
        analyze('let x: String = "hello"')

    def test_builtin_bool_valid(self) -> None:
        """``Bool`` is accepted as a valid type."""
        analyze("let x: Bool = true")

    def test_builtin_list_valid(self) -> None:
        """``List`` is accepted as a valid type."""
        analyze("let x: List = [1, 2]")

    def test_builtin_dict_valid(self) -> None:
        """``Dict`` is accepted as a valid type."""
        analyze('let x: Dict = {"a": 1}')

    def test_builtin_fn_valid(self) -> None:
        """``Fn`` is accepted as a valid type."""
        analyze("let f: Fn = fn(x) { return x }")

    def test_struct_type_valid(self) -> None:
        """A defined struct name is valid as a type."""
        analyze("struct Point { x, y }\nlet p: Point = Point(1, 2)")

    def test_unknown_type_error(self) -> None:
        """An unknown type name raises SemanticError."""
        with pytest.raises(SemanticError, match="Unknown type 'Xyz'"):
            analyze("let x: Xyz = 5")

    def test_undefined_struct_type_error(self) -> None:
        """Using an undefined struct as a type raises SemanticError."""
        with pytest.raises(SemanticError, match="Unknown type 'Widget'"):
            analyze("let w: Widget = 0")

    def test_recursive_struct_type_valid(self) -> None:
        """A struct can reference itself as a field type."""
        analyze("struct Node { value: Int, next }")


class TestAnalyzerFieldTypes:
    """Verify analyzer validates struct field type annotations."""

    def test_valid_field_type(self) -> None:
        """Valid builtin type on a struct field passes analysis."""
        analyze("struct Point { x: Float, y: Float }")

    def test_invalid_field_type(self) -> None:
        """Unknown type on a struct field raises SemanticError."""
        with pytest.raises(SemanticError, match="Unknown type 'Xyz'"):
            analyze("struct Bad { x: Xyz }")


# =============================================================================
# Cycle 4: Bytecode + Compiler
# =============================================================================


class TestCheckTypeOpcode:
    """Verify CHECK_TYPE opcode exists."""

    def test_check_type_exists(self) -> None:
        """CHECK_TYPE is a valid OpCode member."""
        assert OpCode.CHECK_TYPE == "CHECK_TYPE"


class TestCodeObjectMetadata:
    """Verify CodeObject stores param_types and return_type."""

    def test_param_types_default(self) -> None:
        """param_types defaults to empty list."""
        code = CodeObject(name="test")
        assert code.param_types == []

    def test_return_type_default(self) -> None:
        """return_type defaults to None."""
        code = CodeObject(name="test")
        assert code.return_type is None


class TestCompiledProgramFieldTypes:
    """Verify CompiledProgram stores struct_field_types."""

    def test_struct_field_types_stored(self) -> None:
        """Compiling a typed struct stores field type metadata."""
        prog = compile_source("struct Point { x: Float, y: Float }")
        assert "Point" in prog.struct_field_types
        assert prog.struct_field_types["Point"] == {
            "x": "Float",
            "y": "Float",
        }


class TestCompilerEmitsCheckType:
    """Verify the compiler emits CHECK_TYPE instructions."""

    def test_let_with_type_emits_check(self) -> None:
        """``let x: Int = 5`` emits CHECK_TYPE before STORE_NAME."""
        opcodes = compile_opcodes("let x: Int = 5")
        assert OpCode.CHECK_TYPE in opcodes
        check_idx = opcodes.index(OpCode.CHECK_TYPE)
        store_idx = opcodes.index(OpCode.STORE_NAME)
        assert check_idx < store_idx

    def test_let_without_type_no_check(self) -> None:
        """``let x = 5`` does NOT emit CHECK_TYPE."""
        opcodes = compile_opcodes("let x = 5")
        assert OpCode.CHECK_TYPE not in opcodes

    def test_const_with_type_emits_check(self) -> None:
        """``const pi: Float = 3.14`` emits CHECK_TYPE."""
        opcodes = compile_opcodes("const pi: Float = 3.14")
        assert OpCode.CHECK_TYPE in opcodes

    def test_return_with_type_emits_check(self) -> None:
        """A function with return type emits CHECK_TYPE before RETURN."""
        prog = compile_source("fn f() -> Int { return 42 }")
        fn_opcodes = [i.opcode for i in prog.functions["f"].instructions]
        assert OpCode.CHECK_TYPE in fn_opcodes
        check_idx = fn_opcodes.index(OpCode.CHECK_TYPE)
        ret_idx = fn_opcodes.index(OpCode.RETURN)
        assert check_idx < ret_idx

    def test_implicit_return_with_type_emits_check(self) -> None:
        """Implicit return on typed function emits CHECK_TYPE."""
        prog = compile_source("fn f() -> Int { let x = 0 }")
        fn_opcodes = [i.opcode for i in prog.functions["f"].instructions]
        assert OpCode.CHECK_TYPE in fn_opcodes


class TestCompilerStoresMetadata:
    """Verify the compiler stores type metadata in CodeObjects."""

    def test_function_param_and_return_types(self) -> None:
        """Compiled function stores param_types and return_type."""
        prog = compile_source("fn add(a: Int, b: Int) -> Int { return a + b }")
        fn = prog.functions["add"]
        assert fn.param_types == [TypeAnnotation(name="Int"), TypeAnnotation(name="Int")]
        assert fn.return_type == TypeAnnotation(name="Int")


# =============================================================================
# Cycle 5: VM Runtime
# =============================================================================


class TestVMCheckType:
    """Verify CHECK_TYPE opcode runtime behavior."""

    def test_int_check_passes(self) -> None:
        """``let x: Int = 5`` succeeds."""
        run_source("let x: Int = 5\nprint(x)")

    def test_float_check_passes(self) -> None:
        """``let x: Float = 3.14`` succeeds."""
        run_source("let x: Float = 3.14\nprint(x)")

    def test_string_check_passes(self) -> None:
        """``let x: String = "hi"`` succeeds."""
        run_source('let x: String = "hi"\nprint(x)')

    def test_bool_check_passes(self) -> None:
        """``let x: Bool = true`` succeeds."""
        run_source("let x: Bool = true\nprint(x)")

    def test_struct_type_check_passes(self) -> None:
        """``let p: Point = Point(1.0, 2.0)`` succeeds."""
        run_source("struct Point { x, y }\nlet p: Point = Point(1.0, 2.0)\nprint(p.x)")

    def test_type_mismatch_error(self) -> None:
        """``let x: Int = "hello"`` raises a type error."""
        with pytest.raises(SemanticError, match="Type error: expected Int, got String"):
            run_source('let x: Int = "hello"')


class TestVariableTypeChecking:
    """Verify variable declaration type checking."""

    def test_let_match(self) -> None:
        """Matching type passes."""
        out = run_source("let x: Int = 42\nprint(x)")
        assert out.strip() == "42"

    def test_let_mismatch(self) -> None:
        """Mismatched type raises error."""
        with pytest.raises(SemanticError, match="Type error"):
            run_source("let x: Int = 3.14")

    def test_const_match(self) -> None:
        """Const with matching type passes."""
        out = run_source("const pi: Float = 3.14\nprint(pi)")
        assert out.strip() == "3.14"

    def test_const_mismatch(self) -> None:
        """Const with mismatched type raises error."""
        with pytest.raises(SemanticError, match="Type error"):
            run_source('const x: Int = "oops"')

    def test_bool_not_treated_as_int(self) -> None:
        """``let x: Int = true`` fails because Bool is not Int."""
        with pytest.raises(SemanticError, match="Type error: expected Int, got Bool"):
            run_source("let x: Int = true")

    def test_int_not_treated_as_bool(self) -> None:
        """``let x: Bool = 0`` fails because Int is not Bool."""
        with pytest.raises(SemanticError, match="Type error: expected Bool, got Int"):
            run_source("let x: Bool = 0")


class TestFunctionParamTypeChecking:
    """Verify function parameter type checking at call time."""

    def test_params_match(self) -> None:
        """Correct argument types pass."""
        out = run_source("fn add(a: Int, b: Int) -> Int { return a + b }\nprint(add(1, 2))")
        assert out.strip() == "3"

    def test_params_mismatch(self) -> None:
        """Wrong argument type raises error."""
        with pytest.raises(SemanticError, match="argument 'b' expected Int"):
            run_source('fn f(a: Int, b: Int) { return a }\nf(1, "x")')

    def test_mixed_annotated_and_unannotated(self) -> None:
        """Only annotated params are checked."""
        out = run_source('fn f(a: Int, b) { print(a) }\nf(5, "any")')
        assert out.strip() == "5"

    def test_no_annotations_no_check(self) -> None:
        """Fully unannotated function accepts anything."""
        out = run_source('fn f(x) { print(x) }\nf("hello")')
        assert out.strip() == "hello"


class TestFunctionReturnTypeChecking:
    """Verify function return type checking."""

    def test_return_match(self) -> None:
        """Correct return type passes."""
        out = run_source("fn f() -> Int { return 42 }\nprint(f())")
        assert out.strip() == "42"

    def test_return_mismatch(self) -> None:
        """Wrong return type raises error."""
        with pytest.raises(SemanticError, match="Type error: expected Int, got String"):
            run_source('fn f() -> Int { return "oops" }\nf()')

    def test_no_return_type_no_check(self) -> None:
        """Function without return type annotation returns anything."""
        out = run_source('fn f() { return "anything" }\nprint(f())')
        assert out.strip() == "anything"


class TestStructFieldTypeChecking:
    """Verify struct field type checking at construction and assignment."""

    def test_construction_match(self) -> None:
        """Correct field types at construction pass."""
        out = run_source("struct Point { x: Float, y: Float }\nlet p = Point(1.0, 2.0)\nprint(p.x)")
        assert out.strip() == "1.0"

    def test_construction_mismatch(self) -> None:
        """Wrong field type at construction raises error."""
        with pytest.raises(
            SemanticError,
            match="argument 'x' expected Float, got Int",
        ):
            run_source("struct Point { x: Float, y: Float }\nPoint(1, 2.0)")

    def test_field_assignment_match(self) -> None:
        """Correct type on field reassignment passes."""
        out = run_source(
            "struct Point { x: Float, y: Float }\nlet p = Point(1.0, 2.0)\np.x = 3.0\nprint(p.x)"
        )
        assert out.strip() == "3.0"

    def test_field_assignment_mismatch(self) -> None:
        """Wrong type on field reassignment raises error."""
        with pytest.raises(
            PebbleRuntimeError,
            match="field 'x' of 'Point' expected Float",
        ):
            run_source('struct Point { x: Float, y: Float }\nlet p = Point(1.0, 2.0)\np.x = "oops"')

    def test_mixed_typed_and_untyped_fields(self) -> None:
        """Only annotated fields are checked."""
        out = run_source('struct Mixed { x: Int, y }\nlet m = Mixed(5, "anything")\nprint(m.x)')
        assert out.strip() == "5"


class TestClosureTypeChecking:
    """Verify closure parameter type checking."""

    def test_closure_param_match(self) -> None:
        """Closure with typed param accepts correct type."""
        out = run_source("let double = fn(x: Int) -> Int { return x * 2 }\nprint(double(5))")
        assert out.strip() == "10"

    def test_closure_param_mismatch(self) -> None:
        """Closure with typed param rejects wrong type."""
        with pytest.raises(PebbleRuntimeError, match="parameter 'x' expected Int"):
            run_source('let f = fn(x: Int) { return x }\nf("wrong")')


# =============================================================================
# Cycle 6: Integration
# =============================================================================


class TestEndToEnd:
    """End-to-end integration tests for type annotations."""

    def test_fully_typed_program(self) -> None:
        """A fully typed program runs correctly."""
        out = run_source(
            "struct Point { x: Float, y: Float }\n"
            "fn distance(p: Point) -> Float {\n"
            "    return (p.x ** 2 + p.y ** 2) ** 0.5\n"
            "}\n"
            "let origin: Point = Point(3.0, 4.0)\n"
            "let d: Float = distance(origin)\n"
            "print(d)"
        )
        assert out.strip() == "5.0"

    def test_fully_untyped_program(self) -> None:
        """An untyped program runs without type checks."""
        out = run_source("fn add(a, b) { return a + b }\nlet result = add(3, 4)\nprint(result)")
        assert out.strip() == "7"

    def test_mixed_typed_and_untyped(self) -> None:
        """Mixing typed and untyped code works."""
        out = run_source(
            "fn square(x: Int) -> Int { return x * x }\nlet result = square(5)\nprint(result)"
        )
        assert out.strip() == "25"

    def test_typed_struct_with_methods(self) -> None:
        """Struct with typed fields and a typed method."""
        out = run_source(
            "struct Rect { w: Float, h: Float }\n"
            "fn area(r: Rect) -> Float { return r.w * r.h }\n"
            "let r: Rect = Rect(3.0, 4.0)\n"
            "print(area(r))"
        )
        assert out.strip() == "12.0"


class TestResolverTypeMetadata:
    """Verify imported module type metadata flows through the resolver."""

    def test_imported_struct_types_preserved(self, tmp_path: Path) -> None:
        """Struct field types from imported module are available at runtime."""
        lib = tmp_path / "shapes.pbl"
        lib.write_text("struct Circle { radius: Float }")
        main_source = 'import "shapes.pbl"\nlet c = Circle(3.14)\nprint(c.radius)'
        out = run_source_with_imports(main_source, base_dir=tmp_path)
        assert out.strip() == "3.14"

    def test_imported_struct_type_checking(self, tmp_path: Path) -> None:
        """Type checking works on imported structs."""
        lib = tmp_path / "shapes.pbl"
        lib.write_text("struct Circle { radius: Float }")
        main_source = 'import "shapes.pbl"\nCircle("bad")'
        with pytest.raises(
            PebbleRuntimeError,
            match="field 'radius' of 'Circle' expected Float, got String",
        ):
            run_source_with_imports(main_source, base_dir=tmp_path)

    def test_imported_fn_types_preserved(self, tmp_path: Path) -> None:
        """Function parameter types from imported module are checked."""
        lib = tmp_path / "math_lib.pbl"
        lib.write_text("fn double(x: Int) -> Int { return x * 2 }")
        main_source = 'import "math_lib.pbl"\nprint(double(5))'
        out = run_source_with_imports(main_source, base_dir=tmp_path)
        assert out.strip() == "10"


class TestREPL:
    """Verify type annotations work in the REPL."""

    def test_typed_declaration(self) -> None:
        """REPL evaluates typed declarations correctly."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("let x: Int = 42")
        r.eval_line("print(x)")
        assert buf.getvalue().strip() == "42"

    def test_type_error_caught(self) -> None:
        """REPL catches type errors at runtime."""
        r = Repl()
        with pytest.raises(SemanticError, match="Type error"):
            r.eval_line('let x: Int = "wrong"')

    def test_typed_struct_persists(self) -> None:
        """Struct field types persist across REPL evaluations."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("struct Point { x: Float, y: Float }")
        r.eval_line("let p = Point(1.0, 2.0)")
        r.eval_line("print(p.x)")
        assert buf.getvalue().strip() == "1.0"

    def test_typed_struct_enforced_across_evals(self) -> None:
        """Struct field types are enforced in subsequent evaluations."""
        r = Repl()
        r.eval_line("struct Point { x: Float, y: Float }")
        with pytest.raises(
            PebbleRuntimeError,
            match="field 'x' of 'Point' expected Float, got String",
        ):
            r.eval_line('Point("bad", 2.0)')
