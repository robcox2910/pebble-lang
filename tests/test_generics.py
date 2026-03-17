"""Tests for generics: parameterized type annotations like List[Int] and Dict[String, Int].

Cover the full pipeline — AST node, parser, analyzer, compiler, VM runtime, resolver,
and REPL.
"""

from io import StringIO

import pytest

from pebble.ast_nodes import (
    Assignment,
    ConstAssignment,
    FunctionDef,
    FunctionExpression,
    StructDef,
    TypeAnnotation,
)
from pebble.bytecode import OpCode
from pebble.errors import PebbleRuntimeError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.repl import Repl
from tests.conftest import (
    analyze,
    compile_source,
    run_source,
)

# -- Named constants ----------------------------------------------------------

FIRST_INDEX = 0
SECOND_INDEX = 1


# -- Helpers ------------------------------------------------------------------


def _parse(source: str) -> list[object]:
    """Lex + parse helper returning the statement list."""
    tokens = Lexer(source).tokenize()
    return list(Parser(tokens).parse().statements)


# =============================================================================
# Cycle 1: TypeAnnotation node + Parser
# =============================================================================


class TestTypeAnnotationNode:
    """Verify the TypeAnnotation dataclass works correctly."""

    def test_simple_type(self) -> None:
        """Simple type has name only, no params."""
        t = TypeAnnotation(name="Int")
        assert t.name == "Int"
        assert t.params == []
        assert str(t) == "Int"

    def test_parameterized_list(self) -> None:
        """List[Int] has one type parameter."""
        t = TypeAnnotation(name="List", params=[TypeAnnotation(name="Int")])
        assert t.name == "List"
        assert len(t.params) == 1
        assert t.params[FIRST_INDEX].name == "Int"
        assert str(t) == "List[Int]"

    def test_parameterized_dict(self) -> None:
        """Dict[String, Int] has two type parameters."""
        t = TypeAnnotation(
            name="Dict",
            params=[TypeAnnotation(name="String"), TypeAnnotation(name="Int")],
        )
        assert str(t) == "Dict[String, Int]"

    def test_nested_type(self) -> None:
        """List[List[Int]] has nested type parameters."""
        inner = TypeAnnotation(name="List", params=[TypeAnnotation(name="Int")])
        outer = TypeAnnotation(name="List", params=[inner])
        assert str(outer) == "List[List[Int]]"

    def test_from_string_simple(self) -> None:
        """from_string parses 'Int' correctly."""
        t = TypeAnnotation.from_string("Int")
        assert t == TypeAnnotation(name="Int")

    def test_from_string_parameterized(self) -> None:
        """from_string parses 'List[Int]' correctly."""
        t = TypeAnnotation.from_string("List[Int]")
        assert t == TypeAnnotation(name="List", params=[TypeAnnotation(name="Int")])

    def test_from_string_dict(self) -> None:
        """from_string parses 'Dict[String, Int]' correctly."""
        t = TypeAnnotation.from_string("Dict[String, Int]")
        assert t == TypeAnnotation(
            name="Dict",
            params=[TypeAnnotation(name="String"), TypeAnnotation(name="Int")],
        )

    def test_from_string_nested(self) -> None:
        """from_string parses 'List[List[Int]]' correctly."""
        t = TypeAnnotation.from_string("List[List[Int]]")
        inner = TypeAnnotation(name="List", params=[TypeAnnotation(name="Int")])
        assert t == TypeAnnotation(name="List", params=[inner])

    def test_from_string_complex_nested(self) -> None:
        """from_string parses 'Dict[String, List[Float]]' correctly."""
        t = TypeAnnotation.from_string("Dict[String, List[Float]]")
        expected = TypeAnnotation(
            name="Dict",
            params=[
                TypeAnnotation(name="String"),
                TypeAnnotation(name="List", params=[TypeAnnotation(name="Float")]),
            ],
        )
        assert t == expected

    def test_roundtrip(self) -> None:
        """Str → from_string → str roundtrip preserves structure."""
        original = TypeAnnotation(
            name="Dict",
            params=[
                TypeAnnotation(name="String"),
                TypeAnnotation(name="List", params=[TypeAnnotation(name="Int")]),
            ],
        )
        assert TypeAnnotation.from_string(str(original)) == original

    def test_frozen(self) -> None:
        """TypeAnnotation is immutable."""
        t = TypeAnnotation(name="Int")
        with pytest.raises(AttributeError):
            t.name = "Float"  # type: ignore[misc]


class TestParserGenericTypes:
    """Verify parser handles parameterized type annotations."""

    def test_let_list_int(self) -> None:
        """``let x: List[Int] = [1]`` parses the type annotation."""
        stmts = _parse("let x: List[Int] = [1]")
        stmt = stmts[FIRST_INDEX]
        assert isinstance(stmt, Assignment)
        assert stmt.type_annotation == TypeAnnotation(
            name="List", params=[TypeAnnotation(name="Int")]
        )

    def test_let_dict_string_int(self) -> None:
        """``let x: Dict[String, Int] = {}`` parses two type params."""
        stmts = _parse('let x: Dict[String, Int] = {"a": 1}')
        stmt = stmts[FIRST_INDEX]
        assert isinstance(stmt, Assignment)
        assert stmt.type_annotation == TypeAnnotation(
            name="Dict",
            params=[TypeAnnotation(name="String"), TypeAnnotation(name="Int")],
        )

    def test_nested_list_list_int(self) -> None:
        """``let x: List[List[Int]] = [[1]]`` parses nested type."""
        stmts = _parse("let x: List[List[Int]] = [[1]]")
        stmt = stmts[FIRST_INDEX]
        assert isinstance(stmt, Assignment)
        inner = TypeAnnotation(name="List", params=[TypeAnnotation(name="Int")])
        assert stmt.type_annotation == TypeAnnotation(name="List", params=[inner])

    def test_const_generic(self) -> None:
        """``const x: List[Int] = [1]`` parses the type annotation."""
        stmts = _parse("const x: List[Int] = [1]")
        stmt = stmts[FIRST_INDEX]
        assert isinstance(stmt, ConstAssignment)
        assert stmt.type_annotation == TypeAnnotation(
            name="List", params=[TypeAnnotation(name="Int")]
        )

    def test_param_generic(self) -> None:
        """Function parameter with generic type."""
        stmts = _parse("fn f(xs: List[Int]) { return xs }")
        fn = stmts[FIRST_INDEX]
        assert isinstance(fn, FunctionDef)
        assert fn.parameters[FIRST_INDEX].type_annotation == TypeAnnotation(
            name="List", params=[TypeAnnotation(name="Int")]
        )

    def test_return_type_generic(self) -> None:
        """Function with generic return type."""
        stmts = _parse("fn f() -> List[Int] { return [1] }")
        fn = stmts[FIRST_INDEX]
        assert isinstance(fn, FunctionDef)
        assert fn.return_type == TypeAnnotation(name="List", params=[TypeAnnotation(name="Int")])

    def test_struct_field_generic(self) -> None:
        """Struct field with generic type."""
        stmts = _parse("struct S { items: List[Int] }")
        struct = stmts[FIRST_INDEX]
        assert isinstance(struct, StructDef)
        assert struct.fields[FIRST_INDEX].type_annotation == TypeAnnotation(
            name="List", params=[TypeAnnotation(name="Int")]
        )

    def test_simple_type_still_works(self) -> None:
        """Plain type annotations still produce TypeAnnotation with no params."""
        stmts = _parse("let x: Int = 5")
        stmt = stmts[FIRST_INDEX]
        assert isinstance(stmt, Assignment)
        assert stmt.type_annotation == TypeAnnotation(name="Int")

    def test_array_literal_not_confused(self) -> None:
        """Array literal [1, 2, 3] is not confused with type parameters."""
        stmts = _parse("let x = [1, 2, 3]")
        stmt = stmts[FIRST_INDEX]
        assert isinstance(stmt, Assignment)
        assert stmt.type_annotation is None

    def test_empty_array_not_confused(self) -> None:
        """Empty array [] is not confused with type parameters."""
        stmts = _parse("let x: List = []")
        stmt = stmts[FIRST_INDEX]
        assert isinstance(stmt, Assignment)
        assert stmt.type_annotation == TypeAnnotation(name="List")

    def test_fn_expression_return_type_generic(self) -> None:
        """Anonymous function with generic return type."""
        stmts = _parse("let f = fn() -> List[Int] { return [1] }")
        stmt = stmts[FIRST_INDEX]
        assert isinstance(stmt, Assignment)
        fn_expr = stmt.value
        assert isinstance(fn_expr, FunctionExpression)
        assert fn_expr.return_type == TypeAnnotation(
            name="List", params=[TypeAnnotation(name="Int")]
        )

    def test_dict_nested_generic(self) -> None:
        """Dict[String, List[Float]] parses correctly."""
        stmts = _parse("let x: Dict[String, List[Float]] = {}")
        stmt = stmts[FIRST_INDEX]
        assert isinstance(stmt, Assignment)
        expected = TypeAnnotation(
            name="Dict",
            params=[
                TypeAnnotation(name="String"),
                TypeAnnotation(name="List", params=[TypeAnnotation(name="Float")]),
            ],
        )
        assert stmt.type_annotation == expected


# =============================================================================
# Cycle 2: Analyzer — recursive type validation
# =============================================================================


class TestAnalyzerGenericTypes:
    """Verify the analyzer validates parameterized type annotations."""

    def test_valid_list_int(self) -> None:
        """List[Int] passes validation."""
        analyze("let x: List[Int] = [1]")

    def test_valid_dict_string_int(self) -> None:
        """Dict[String, Int] passes validation."""
        analyze('let x: Dict[String, Int] = {"a": 1}')

    def test_valid_nested(self) -> None:
        """List[List[Int]] passes validation."""
        analyze("let x: List[List[Int]] = [[1]]")

    def test_bare_list_still_valid(self) -> None:
        """Bare List without params still passes."""
        analyze("let x: List = [1]")

    def test_bare_dict_still_valid(self) -> None:
        """Bare Dict without params still passes."""
        analyze('let x: Dict = {"a": 1}')

    def test_wrong_param_count_list(self) -> None:
        """List[Int, Float] — List expects 1 type parameter."""
        with pytest.raises(SemanticError, match="List expects 1 type parameter"):
            analyze("let x: List[Int, Float] = []")

    def test_wrong_param_count_dict(self) -> None:
        """Dict[String] — Dict expects 2 type parameters."""
        with pytest.raises(SemanticError, match="Dict expects 2 type parameters"):
            analyze("let x: Dict[String] = {}")

    def test_non_generic_type_with_params(self) -> None:
        """Int[Float] — Int does not accept type parameters."""
        with pytest.raises(SemanticError, match="Int does not accept type parameters"):
            analyze("let x: Int[Float] = 5")

    def test_unknown_inner_type(self) -> None:
        """List[Foo] — unknown inner type."""
        with pytest.raises(SemanticError, match="Unknown type 'Foo'"):
            analyze("let x: List[Foo] = []")

    def test_param_with_generic(self) -> None:
        """Function parameter with generic type passes."""
        analyze("fn f(xs: List[Int]) { return xs }")

    def test_return_type_generic(self) -> None:
        """Function with generic return type passes."""
        analyze("fn f() -> List[Int] { return [1] }")

    def test_struct_field_generic(self) -> None:
        """Struct field with generic type passes."""
        analyze("struct S { items: List[Int] }")

    def test_dict_three_params(self) -> None:
        """Dict[String, Int, Bool] — Dict expects 2 type parameters."""
        with pytest.raises(SemanticError, match="Dict expects 2 type parameters"):
            analyze("let x: Dict[String, Int, Bool] = {}")


# =============================================================================
# Cycle 3: Bytecode + Compiler
# =============================================================================


class TestCompilerGenericTypes:
    """Verify the compiler emits CHECK_TYPE with serialized generic types."""

    def test_check_type_emitted_for_list_int(self) -> None:
        """CHECK_TYPE operand is 'List[Int]' for a List[Int] annotation."""
        compiled = compile_source("let x: List[Int] = [1, 2]")
        check_types = [i for i in compiled.main.instructions if i.opcode is OpCode.CHECK_TYPE]
        assert len(check_types) == 1
        assert check_types[FIRST_INDEX].operand == "List[Int]"

    def test_check_type_simple_still_works(self) -> None:
        """CHECK_TYPE operand is 'Int' for a plain Int annotation."""
        compiled = compile_source("let x: Int = 5")
        check_types = [i for i in compiled.main.instructions if i.opcode is OpCode.CHECK_TYPE]
        assert len(check_types) == 1
        assert check_types[FIRST_INDEX].operand == "Int"

    def test_function_param_types_stored(self) -> None:
        """Function CodeObject stores TypeAnnotation in param_types."""
        compiled = compile_source("fn f(xs: List[Int]) { return xs }")
        fn = compiled.functions["f"]
        assert fn.param_types[FIRST_INDEX] == TypeAnnotation(
            name="List", params=[TypeAnnotation(name="Int")]
        )

    def test_function_return_type_stored(self) -> None:
        """Function CodeObject stores TypeAnnotation in return_type."""
        compiled = compile_source("fn f() -> List[Int] { return [1] }")
        fn = compiled.functions["f"]
        assert fn.return_type == TypeAnnotation(name="List", params=[TypeAnnotation(name="Int")])

    def test_struct_field_types_stored(self) -> None:
        """Struct field types store serialized TypeAnnotation string."""
        compiled = compile_source("struct S { items: List[Int] }")
        assert "S" in compiled.struct_field_types
        assert compiled.struct_field_types["S"]["items"] == "List[Int]"

    def test_check_type_dict(self) -> None:
        """CHECK_TYPE operand is 'Dict[String, Int]' for a Dict annotation."""
        compiled = compile_source('let x: Dict[String, Int] = {"a": 1}')
        check_types = [i for i in compiled.main.instructions if i.opcode is OpCode.CHECK_TYPE]
        assert len(check_types) == 1
        assert check_types[FIRST_INDEX].operand == "Dict[String, Int]"


# =============================================================================
# Cycle 4: VM — Recursive type matching
# =============================================================================


class TestVMGenericTypeChecking:
    """Verify the VM validates generic types at runtime."""

    def test_list_int_pass(self) -> None:
        """List[Int] passes for a list of integers."""
        output = run_source("let x: List[Int] = [1, 2, 3]\nprint(x)")
        assert output.strip() == "[1, 2, 3]"

    def test_list_int_fail(self) -> None:
        """List[Int] fails when a string is in the list."""
        with pytest.raises(PebbleRuntimeError, match="Type error"):
            run_source('let x: List[Int] = [1, "two", 3]')

    def test_dict_string_int_pass(self) -> None:
        """Dict[String, Int] passes for a dict with string keys and int values."""
        output = run_source('let x: Dict[String, Int] = {"a": 1, "b": 2}\nprint(x)')
        assert "a" in output

    def test_dict_string_int_fail_value(self) -> None:
        """Dict[String, Int] fails when a value is a string."""
        with pytest.raises(PebbleRuntimeError, match="Type error"):
            run_source('let x: Dict[String, Int] = {"a": "one"}')

    def test_empty_list_passes_any(self) -> None:
        """Empty list [] passes any List[T] check."""
        output = run_source("let x: List[Int] = []\nprint(x)")
        assert output.strip() == "[]"

    def test_empty_dict_passes_any(self) -> None:
        """Empty dict {} passes any Dict[K, V] check."""
        output = run_source("let x: Dict[String, Int] = {}\nprint(x)")
        assert output.strip() == "{}"

    def test_bare_list_still_works(self) -> None:
        """Bare List (no params) only checks container type."""
        output = run_source('let x: List = [1, "two"]\nprint(x)')
        assert output.strip() == "[1, two]"

    def test_bare_dict_still_works(self) -> None:
        """Bare Dict (no params) only checks container type."""
        output = run_source('let x: Dict = {"a": 1, "b": "two"}\nprint(x)')
        assert "a" in output

    def test_nested_list_list_int_pass(self) -> None:
        """List[List[Int]] passes for nested lists of ints."""
        output = run_source("let x: List[List[Int]] = [[1, 2], [3, 4]]\nprint(x)")
        assert output.strip() == "[[1, 2], [3, 4]]"

    def test_nested_list_list_int_fail(self) -> None:
        """List[List[Int]] fails when inner list contains a string."""
        with pytest.raises(PebbleRuntimeError, match="Type error"):
            run_source('let x: List[List[Int]] = [[1, "two"]]')

    def test_param_type_generic(self) -> None:
        """Function parameter with List[Int] type is checked."""
        with pytest.raises(PebbleRuntimeError, match="Type error"):
            run_source('fn f(xs: List[Int]) { return xs }\nf([1, "two"])')

    def test_param_type_generic_pass(self) -> None:
        """Function parameter with List[Int] type passes for valid input."""
        output = run_source("fn f(xs: List[Int]) { return xs }\nprint(f([1, 2]))")
        assert output.strip() == "[1, 2]"

    def test_return_type_generic(self) -> None:
        """Function with List[Int] return type is checked."""
        with pytest.raises(PebbleRuntimeError, match="Type error"):
            run_source('fn f() -> List[Int] { return [1, "two"] }\nf()')

    def test_return_type_generic_pass(self) -> None:
        """Function with List[Int] return type passes for valid return."""
        output = run_source("fn f() -> List[Int] { return [1, 2] }\nprint(f())")
        assert output.strip() == "[1, 2]"

    def test_list_float_fail(self) -> None:
        """List[Float] fails when an int is in the list."""
        with pytest.raises(PebbleRuntimeError, match="Type error"):
            run_source("let x: List[Float] = [1.0, 2]")

    def test_list_string_pass(self) -> None:
        """List[String] passes for a list of strings."""
        output = run_source('let x: List[String] = ["a", "b"]\nprint(x)')
        assert output.strip() == "[a, b]"

    def test_dict_nested_value_pass(self) -> None:
        """Dict[String, List[Int]] passes for valid nested structure."""
        output = run_source('let x: Dict[String, List[Int]] = {"a": [1, 2]}\nprint(x)')
        assert "a" in output

    def test_dict_nested_value_fail(self) -> None:
        """Dict[String, List[Int]] fails when inner list has wrong type."""
        with pytest.raises(PebbleRuntimeError, match="Type error"):
            run_source('let x: Dict[String, List[Int]] = {"a": [1, "two"]}')

    def test_list_not_a_list(self) -> None:
        """List[Int] fails when the value is not a list at all."""
        with pytest.raises(PebbleRuntimeError, match="Type error"):
            run_source("let x: List[Int] = 42")

    def test_dict_not_a_dict(self) -> None:
        """Dict[String, Int] fails when the value is not a dict."""
        with pytest.raises(PebbleRuntimeError, match="Type error"):
            run_source("let x: Dict[String, Int] = [1, 2]")

    def test_const_generic(self) -> None:
        """Const with generic type annotation is checked."""
        output = run_source("const x: List[Int] = [1, 2]\nprint(x)")
        assert output.strip() == "[1, 2]"


# =============================================================================
# Cycle 5: Struct/class fields + REPL
# =============================================================================


class TestStructGenericFields:
    """Verify struct and class fields with generic type annotations."""

    def test_struct_list_field_construction(self) -> None:
        """Struct with List[Int] field validates on construction."""
        output = run_source("struct S { items: List[Int] }\nlet s = S([1, 2])\nprint(s.items)")
        assert output.strip() == "[1, 2]"

    def test_struct_list_field_construction_fail(self) -> None:
        """Struct with List[Int] field rejects wrong element types."""
        with pytest.raises(PebbleRuntimeError, match="Type error"):
            run_source('struct S { items: List[Int] }\nlet s = S([1, "two"])')

    def test_struct_field_reassignment(self) -> None:
        """Struct field reassignment with generic type is checked."""
        with pytest.raises(PebbleRuntimeError, match="Type error"):
            run_source('struct S { items: List[Int] }\nlet s = S([1, 2])\ns.items = [1, "two"]')

    def test_struct_field_reassignment_pass(self) -> None:
        """Struct field reassignment with generic type passes for valid value."""
        output = run_source(
            "struct S { items: List[Int] }\nlet s = S([1, 2])\ns.items = [3, 4]\nprint(s.items)"
        )
        assert output.strip() == "[3, 4]"

    def test_class_generic_field(self) -> None:
        """Class with generic field validates on construction."""
        source = """\
class Container {
    items: List[Int]

    fn get_first(self) -> Int {
        return self.items[0]
    }
}
let c = Container([10, 20])
print(c.get_first())
"""
        output = run_source(source)
        assert output.strip() == "10"

    def test_class_generic_field_fail(self) -> None:
        """Class with generic field rejects wrong element types."""
        source = """\
class Container {
    items: List[Int]

    fn size(self) { return 0 }
}
let c = Container([1, "two"])
"""
        with pytest.raises(PebbleRuntimeError, match="Type error"):
            run_source(source)


class TestReplGeneric:
    """Verify REPL handles generic type annotations."""

    def test_repl_generic_let(self) -> None:
        """REPL accepts let with generic type."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("let x: List[Int] = [1, 2, 3]")
        r.eval_line("print(x)")
        assert buf.getvalue().strip() == "[1, 2, 3]"

    def test_repl_generic_fail(self) -> None:
        """REPL rejects invalid generic type at runtime."""
        buf = StringIO()
        r = Repl(output=buf)
        with pytest.raises(PebbleRuntimeError, match="Type error"):
            r.eval_line('let x: List[Int] = [1, "two"]')
