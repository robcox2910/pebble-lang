"""Tests for the static type checker — catch type mismatches before runtime.

The type checker walks the analyzed AST and infers expression types,
raising ``SemanticError`` when an annotated target receives a value
of an incompatible type.
"""

import pytest

from pebble.ast_nodes import TypeAnnotation
from pebble.errors import SemanticError
from pebble.type_checker import UNKNOWN, TypeChecker, _types_compatible, type_check
from tests.conftest import analyze_with_context

# -- Named constants ----------------------------------------------------------

FIRST_INDEX = 0


# -- Helpers ------------------------------------------------------------------


def _check(source: str) -> None:
    """Lex, parse, analyze, and type-check *source*."""
    program, analyzer = analyze_with_context(source)
    type_check(program, analyzer=analyzer)


# =============================================================================
# Cycle 1: Module skeleton
# =============================================================================


class TestModuleSkeleton:
    """Verify the type checker module exists and has the expected API."""

    def test_unknown_sentinel_exists(self) -> None:
        """UNKNOWN is a TypeAnnotation with name 'Unknown'."""
        assert isinstance(UNKNOWN, TypeAnnotation)
        assert UNKNOWN.name == "Unknown"

    def test_type_checker_class_exists(self) -> None:
        """TypeChecker can be instantiated."""
        program, analyzer = analyze_with_context("let x = 5")
        checker = TypeChecker(program, analyzer=analyzer)
        assert checker is not None

    def test_type_check_on_unannotated_code(self) -> None:
        """Fully unannotated code passes without error."""
        _check("let x = 5")

    def test_type_check_empty_program(self) -> None:
        """An empty program passes without error."""
        _check("")

    def test_type_check_print_passes(self) -> None:
        """A simple print statement passes without error."""
        _check("print(42)")


# =============================================================================
# Cycle 2: Literal type inference + assignment checking
# =============================================================================


class TestLiteralAssignments:
    """Verify type checking on annotated let/const declarations."""

    def test_int_literal_matches_int(self) -> None:
        """``let x: Int = 42`` passes."""
        _check("let x: Int = 42")

    def test_float_literal_matches_float(self) -> None:
        """``let x: Float = 3.14`` passes."""
        _check("let x: Float = 3.14")

    def test_string_literal_matches_string(self) -> None:
        """``let x: String = "hello"`` passes."""
        _check('let x: String = "hello"')

    def test_bool_literal_matches_bool(self) -> None:
        """``let x: Bool = true`` passes."""
        _check("let x: Bool = true")

    def test_null_literal_matches_null(self) -> None:
        """``let x: Null = null`` passes."""
        _check("let x: Null = null")

    def test_int_mismatch_string(self) -> None:
        """``let x: Int = "hello"`` fails."""
        with pytest.raises(SemanticError, match="expected Int, got String"):
            _check('let x: Int = "hello"')

    def test_string_mismatch_int(self) -> None:
        """``let x: String = 42`` fails."""
        with pytest.raises(SemanticError, match="expected String, got Int"):
            _check("let x: String = 42")

    def test_bool_is_not_int(self) -> None:
        """``let x: Int = true`` fails because Bool is not Int."""
        with pytest.raises(SemanticError, match="expected Int, got Bool"):
            _check("let x: Int = true")

    def test_int_is_not_bool(self) -> None:
        """``let x: Bool = 0`` fails because Int is not Bool."""
        with pytest.raises(SemanticError, match="expected Bool, got Int"):
            _check("let x: Bool = 0")

    def test_unannotated_let_passes(self) -> None:
        """``let x = 5`` passes without error."""
        _check("let x = 5")

    def test_const_int_matches(self) -> None:
        """``const x: Int = 42`` passes."""
        _check("const x: Int = 42")

    def test_const_mismatch(self) -> None:
        """``const x: Int = "oops"`` fails."""
        with pytest.raises(SemanticError, match="expected Int, got String"):
            _check('const x: Int = "oops"')

    def test_float_mismatch_int(self) -> None:
        """``let x: Float = 5`` fails because Int is not Float."""
        with pytest.raises(SemanticError, match="expected Float, got Int"):
            _check("let x: Float = 5")


# =============================================================================
# Cycle 3: Variable reference tracking
# =============================================================================


class TestVariableReferences:
    """Verify that inferred variable types flow through references."""

    def test_annotated_var_to_annotated_var(self) -> None:
        """``let x: Int = 5; let y: Int = x`` passes."""
        _check("let x: Int = 5\nlet y: Int = x")

    def test_annotated_var_type_mismatch(self) -> None:
        """``let x: Int = 5; let y: String = x`` fails."""
        with pytest.raises(SemanticError, match="expected String, got Int"):
            _check("let x: Int = 5\nlet y: String = x")

    def test_inferred_var_tracks_type(self) -> None:
        """Unannotated ``let x = 5`` infers Int; ``let y: Int = x`` passes."""
        _check("let x = 5\nlet y: Int = x")

    def test_inferred_var_mismatch(self) -> None:
        """Unannotated ``let x = 5``; ``let y: String = x`` fails."""
        with pytest.raises(SemanticError, match="expected String, got Int"):
            _check("let x = 5\nlet y: String = x")

    def test_unknown_var_passes_any_check(self) -> None:
        """An UNKNOWN variable is compatible with any annotation."""
        _check("fn f(x) { let y: Int = x }")

    def test_const_inferred_type(self) -> None:
        """Const inferred type flows to references."""
        _check('const s = "hi"\nlet y: String = s')


# =============================================================================
# Cycle 4: Binary expression inference
# =============================================================================


class TestBinaryExpressions:
    """Verify binary op type inference."""

    def test_int_plus_int(self) -> None:
        """``let x: Int = 1 + 2`` passes."""
        _check("let x: Int = 1 + 2")

    def test_float_promotion(self) -> None:
        """``let x: Float = 1 + 2.0`` passes (Int + Float → Float)."""
        _check("let x: Float = 1 + 2.0")

    def test_string_concat(self) -> None:
        """``let x: String = "a" + "b"`` passes."""
        _check('let x: String = "a" + "b"')

    def test_int_plus_int_not_string(self) -> None:
        """``let x: String = 1 + 2`` fails."""
        with pytest.raises(SemanticError, match="expected String, got Int"):
            _check("let x: String = 1 + 2")

    def test_division_returns_float(self) -> None:
        """``let x: Float = 10 / 3`` passes (true division → Float)."""
        _check("let x: Float = 10 / 3")

    def test_floor_division_returns_int(self) -> None:
        """``let x: Int = 10 // 3`` passes."""
        _check("let x: Int = 10 // 3")

    def test_modulo(self) -> None:
        """``let x: Int = 10 % 3`` passes."""
        _check("let x: Int = 10 % 3")

    def test_power(self) -> None:
        """``let x: Int = 2 ** 3`` passes."""
        _check("let x: Int = 2 ** 3")

    def test_subtraction(self) -> None:
        """``let x: Int = 5 - 3`` passes."""
        _check("let x: Int = 5 - 3")

    def test_multiplication(self) -> None:
        """``let x: Int = 5 * 3`` passes."""
        _check("let x: Int = 5 * 3")

    def test_comparison_returns_bool(self) -> None:
        """``let x: Bool = 1 < 2`` passes."""
        _check("let x: Bool = 1 < 2")

    def test_equality_returns_bool(self) -> None:
        """``let x: Bool = 1 == 2`` passes."""
        _check("let x: Bool = 1 == 2")

    def test_logical_and_returns_bool(self) -> None:
        """``let x: Bool = true and false`` passes."""
        _check("let x: Bool = true and false")

    def test_logical_or_returns_bool(self) -> None:
        """``let x: Bool = true or false`` passes."""
        _check("let x: Bool = true or false")

    def test_bitwise_and_int(self) -> None:
        """``let x: Int = 5 & 3`` passes."""
        _check("let x: Int = 5 & 3")

    def test_bitwise_or_int(self) -> None:
        """``let x: Int = 5 | 3`` passes."""
        _check("let x: Int = 5 | 3")

    def test_shift_left(self) -> None:
        """``let x: Int = 1 << 3`` passes."""
        _check("let x: Int = 1 << 3")


# =============================================================================
# Cycle 5: Unary and comparison expressions
# =============================================================================


class TestUnaryExpressions:
    """Verify unary op type inference."""

    def test_negate_int(self) -> None:
        """``let x: Int = -5`` passes."""
        _check("let x: Int = -5")

    def test_negate_float(self) -> None:
        """``let x: Float = -3.14`` passes."""
        _check("let x: Float = -3.14")

    def test_not_bool(self) -> None:
        """``let x: Bool = not true`` passes."""
        _check("let x: Bool = not true")

    def test_bitwise_not_int(self) -> None:
        """``let x: Int = ~5`` passes."""
        _check("let x: Int = ~5")

    def test_not_returns_bool_not_int(self) -> None:
        """``let x: Int = not true`` fails."""
        with pytest.raises(SemanticError, match="expected Int, got Bool"):
            _check("let x: Int = not true")


# =============================================================================
# Cycle 6: Function parameter checking
# =============================================================================


class TestFunctionParams:
    """Verify function argument type checking at call sites."""

    def test_matching_args(self) -> None:
        """Correct argument types pass."""
        _check("fn add(a: Int, b: Int) -> Int { return a + b }\nadd(1, 2)")

    def test_mismatched_arg(self) -> None:
        """Wrong argument type raises error with parameter name."""
        with pytest.raises(SemanticError, match="argument 'b' expected Int"):
            _check('fn f(a: Int, b: Int) { return a }\nf(1, "hi")')

    def test_unannotated_params_accept_anything(self) -> None:
        """Unannotated parameters accept any type."""
        _check('fn f(a, b) { return a }\nf(1, "hi")')

    def test_mixed_annotated_unannotated(self) -> None:
        """Only annotated params are checked."""
        _check('fn f(a: Int, b) { return a }\nf(1, "anything")')

    def test_first_param_mismatch(self) -> None:
        """First argument mismatch is reported."""
        with pytest.raises(SemanticError, match="argument 'a' expected Int"):
            _check('fn f(a: Int) { return a }\nf("wrong")')


# =============================================================================
# Cycle 7: Function return type checking
# =============================================================================


class TestFunctionReturns:
    """Verify function return type checking."""

    def test_matching_return(self) -> None:
        """Correct return type passes."""
        _check("fn f() -> Int { return 42 }")

    def test_mismatched_return(self) -> None:
        """Wrong return type raises error."""
        with pytest.raises(SemanticError, match="expected Int, got String"):
            _check('fn f() -> Int { return "oops" }')

    def test_no_return_annotation_passes(self) -> None:
        """Function without return type accepts any return."""
        _check('fn f() { return "anything" }')

    def test_return_variable_with_known_type(self) -> None:
        """Return a variable whose type is known."""
        _check("fn f() -> Int {\n  let x: Int = 5\n  return x\n}")

    def test_return_variable_mismatch(self) -> None:
        """Return a variable with the wrong type."""
        with pytest.raises(SemanticError, match="expected Int, got String"):
            _check('fn f() -> Int {\n  let x: String = "hi"\n  return x\n}')

    def test_return_inferred_variable(self) -> None:
        """Return an inferred variable matching the return type."""
        _check("fn f() -> Int {\n  let x = 42\n  return x\n}")


# =============================================================================
# Cycle 8: Struct construction checking
# =============================================================================


class TestStructConstruction:
    """Verify struct constructor argument type checking."""

    def test_matching_fields(self) -> None:
        """Correct field types at construction pass."""
        _check("struct Point { x: Float, y: Float }\nPoint(1.0, 2.0)")

    def test_mismatched_field(self) -> None:
        """Wrong field type at construction fails."""
        with pytest.raises(SemanticError, match="argument 'x' expected Float, got Int"):
            _check("struct Point { x: Float, y: Float }\nPoint(1, 2.0)")

    def test_struct_call_infers_struct_type(self) -> None:
        """Struct construction infers the struct type."""
        _check("struct Point { x: Float, y: Float }\nlet p: Point = Point(1.0, 2.0)")

    def test_struct_type_mismatch(self) -> None:
        """Assigning a struct to the wrong type fails."""
        with pytest.raises(SemanticError, match="expected Int, got Point"):
            _check("struct Point { x: Float, y: Float }\nlet p: Int = Point(1.0, 2.0)")

    def test_mixed_typed_untyped_fields(self) -> None:
        """Only annotated fields are checked."""
        _check('struct Mixed { x: Int, y }\nMixed(5, "anything")')


# =============================================================================
# Cycle 9: Complex expressions
# =============================================================================


class TestComplexExpressions:
    """Verify type inference for complex expressions."""

    def test_function_return_type_inferred(self) -> None:
        """Function call return type is inferred."""
        _check("fn f() -> Int { return 42 }\nlet x: Int = f()")

    def test_function_return_type_mismatch(self) -> None:
        """Function call with wrong target type fails."""
        with pytest.raises(SemanticError, match="expected String, got Int"):
            _check("fn f() -> Int { return 42 }\nlet x: String = f()")

    def test_field_access_infers_type(self) -> None:
        """Field access on a known struct infers field type."""
        _check(
            "struct Point { x: Float, y: Float }\n"
            "let p: Point = Point(1.0, 2.0)\n"
            "let val: Float = p.x"
        )

    def test_field_access_type_mismatch(self) -> None:
        """Field access with wrong target type fails."""
        with pytest.raises(SemanticError, match="expected Int, got Float"):
            _check(
                "struct Point { x: Float, y: Float }\n"
                "let p: Point = Point(1.0, 2.0)\n"
                "let val: Int = p.x"
            )

    def test_string_interpolation_returns_string(self) -> None:
        """String interpolation infers as String."""
        _check('let x = 42\nlet s: String = "{x}"')

    def test_array_literal_returns_list(self) -> None:
        """Array literal infers as List."""
        _check("let xs: List = [1, 2, 3]")

    def test_dict_literal_returns_dict(self) -> None:
        """Dict literal infers as Dict."""
        _check('let d: Dict = {"a": 1}')

    def test_function_expression_returns_fn(self) -> None:
        """Anonymous function infers as Fn."""
        _check("let f: Fn = fn(x) { return x }")


# =============================================================================
# Cycle 11: Edge cases + gradual typing
# =============================================================================


class TestGradualTyping:
    """Verify gradual typing: UNKNOWN passes any check."""

    def test_fully_untyped_program(self) -> None:
        """A fully untyped program passes without error."""
        _check("let x = 5\nlet y = x + 1\nprint(y)")

    def test_unknown_function_return_passes(self) -> None:
        """A function without return type passes any annotation."""
        _check("fn f(x) { return x }\nlet y: Int = f(5)")

    def test_enum_type_annotation(self) -> None:
        """Enum type annotations pass analysis."""
        _check("enum Color { Red, Green, Blue }\nlet c = Color.Red")

    def test_closure_infers_fn(self) -> None:
        """Closure assigned to Fn annotation passes."""
        _check("let f: Fn = fn(x: Int) -> Int { return x * 2 }")

    def test_nested_function_scopes(self) -> None:
        """Nested functions have independent type environments."""
        _check(
            'fn outer() -> Int {\n  fn inner() -> String {\n    return "hi"\n  }\n  return 42\n}'
        )

    def test_if_else_scoping(self) -> None:
        """Variables in if/else bodies don't leak."""
        _check('let x: Bool = true\nif x {\n  let y: Int = 5\n} else {\n  let y: String = "hi"\n}')

    def test_for_loop_variable_scoped(self) -> None:
        """For loop variable is scoped to the loop body."""
        _check("for i in range(10) {\n  let x: Int = i\n}")

    def test_try_catch_passes(self) -> None:
        """Try/catch blocks are type-checked."""
        _check("try {\n  let x: Int = 42\n} catch e {\n  print(e)\n}")


class TestTypeCompatibility:
    """Verify the _types_compatible function."""

    def test_unknown_compatible_with_int(self) -> None:
        """UNKNOWN is compatible with Int."""
        assert _types_compatible(TypeAnnotation(name="Int"), UNKNOWN)

    def test_int_compatible_with_unknown(self) -> None:
        """Int is compatible with UNKNOWN."""
        assert _types_compatible(UNKNOWN, TypeAnnotation(name="Int"))

    def test_bare_list_matches_parameterized(self) -> None:
        """Bare ``List`` matches ``List[Int]``."""
        bare = TypeAnnotation(name="List")
        parameterized = TypeAnnotation(name="List", params=[TypeAnnotation(name="Int")])
        assert _types_compatible(bare, parameterized)

    def test_parameterized_matches_bare(self) -> None:
        """``List[Int]`` matches bare ``List``."""
        bare = TypeAnnotation(name="List")
        parameterized = TypeAnnotation(name="List", params=[TypeAnnotation(name="Int")])
        assert _types_compatible(parameterized, bare)

    def test_same_params_compatible(self) -> None:
        """``List[Int]`` matches ``List[Int]``."""
        a = TypeAnnotation(name="List", params=[TypeAnnotation(name="Int")])
        b = TypeAnnotation(name="List", params=[TypeAnnotation(name="Int")])
        assert _types_compatible(a, b)

    def test_different_params_incompatible(self) -> None:
        """``List[Int]`` does not match ``List[String]``."""
        a = TypeAnnotation(name="List", params=[TypeAnnotation(name="Int")])
        b = TypeAnnotation(name="List", params=[TypeAnnotation(name="String")])
        assert not _types_compatible(a, b)
