"""Tests for new operators: exponentiation, floor division, and bitwise."""

from collections.abc import Callable

import pytest

import pebble
from pebble.errors import PebbleRuntimeError
from tests.conftest import run_source

# -- Exponentiation -----------------------------------------------------------


class TestExponentiation:
    """Verify the ``**`` exponentiation operator."""

    def test_int_power(self) -> None:
        """Verify ``2 ** 3`` produces ``8``."""
        assert run_source("print(2 ** 3)") == "8\n"

    def test_right_associative(self) -> None:
        """Verify ``2 ** 2 ** 3`` groups as ``2 ** (2 ** 3)`` = ``256``."""
        assert run_source("print(2 ** 2 ** 3)") == "256\n"

    def test_negative_exponent(self) -> None:
        """Verify ``2 ** -1`` produces ``0.5`` (float)."""
        assert run_source("print(2 ** -1)") == "0.5\n"

    def test_float_base(self) -> None:
        """Verify ``4.0 ** 0.5`` produces ``2.0``."""
        assert run_source("print(4.0 ** 0.5)") == "2.0\n"

    def test_int_to_zero(self) -> None:
        """Verify ``5 ** 0`` produces ``1``."""
        assert run_source("print(5 ** 0)") == "1\n"

    def test_power_binds_tighter_than_multiply(self) -> None:
        """Verify ``2 ** 3 * 2`` groups as ``(2 ** 3) * 2`` = ``16``."""
        assert run_source("print(2 ** 3 * 2)") == "16\n"

    def test_power_with_unary_minus_on_base(self) -> None:
        """Verify ``-2 ** 2`` groups as ``-(2 ** 2)`` = ``-4`` (Python convention)."""
        assert run_source("print(-2 ** 2)") == "-4\n"

    def test_power_complex_result_raises(self) -> None:
        """Verify ``(-1) ** 0.5`` raises a runtime error instead of leaking complex."""
        with pytest.raises(PebbleRuntimeError, match="complex"):
            run_source("print((-1) ** 0.5)")

    def test_zero_to_a_negative_power_raises(self) -> None:
        """Regression (found by a property test): ``0 ** -1`` used to crash Python itself."""
        with pytest.raises(PebbleRuntimeError, match="Division by zero"):
            run_source("print(0 ** -1)")

    def test_power_too_big_for_a_float_raises(self) -> None:
        """Regression: ``10.0 ** 400`` used to crash Python itself with OverflowError."""
        with pytest.raises(PebbleRuntimeError, match="too large"):
            run_source("print(10.0 ** 400)")


# -- Bitwise operators ---------------------------------------------------------


class TestBitwiseOperators:
    """Verify bitwise operators on integers."""

    def test_bitwise_and(self) -> None:
        """Verify ``5 & 3`` produces ``1``."""
        assert run_source("print(5 & 3)") == "1\n"

    def test_bitwise_or(self) -> None:
        """Verify ``5 | 3`` produces ``7``."""
        assert run_source("print(5 | 3)") == "7\n"

    def test_bitwise_xor(self) -> None:
        """Verify ``5 ^ 3`` produces ``6``."""
        assert run_source("print(5 ^ 3)") == "6\n"

    def test_bitwise_not(self) -> None:
        """Verify ``~5`` produces ``-6``."""
        assert run_source("print(~5)") == "-6\n"

    def test_left_shift(self) -> None:
        """Verify ``1 << 3`` produces ``8``."""
        assert run_source("print(1 << 3)") == "8\n"

    def test_right_shift(self) -> None:
        """Verify ``16 >> 2`` produces ``4``."""
        assert run_source("print(16 >> 2)") == "4\n"

    def test_bitwise_and_float_error(self) -> None:
        """Verify ``5 & 3.0`` raises a type error."""
        with pytest.raises(PebbleRuntimeError, match="Unsupported"):
            run_source("print(5 & 3.0)")

    def test_bitwise_or_float_error(self) -> None:
        """Verify ``5 | 3.0`` raises a type error."""
        with pytest.raises(PebbleRuntimeError, match="Unsupported"):
            run_source("print(5 | 3.0)")

    def test_bitwise_xor_float_error(self) -> None:
        """Verify ``5 ^ 3.0`` raises a type error."""
        with pytest.raises(PebbleRuntimeError, match="Unsupported"):
            run_source("print(5 ^ 3.0)")

    def test_bitwise_not_float_error(self) -> None:
        """Verify ``~3.0`` raises a type error."""
        with pytest.raises(PebbleRuntimeError, match="Unsupported"):
            run_source("print(~3.0)")

    def test_bitwise_and_bool_error(self) -> None:
        """Verify ``5 & true`` raises a type error."""
        with pytest.raises(PebbleRuntimeError, match="Unsupported"):
            run_source("print(5 & true)")

    def test_left_shift_negative_error(self) -> None:
        """Verify ``1 << -1`` raises a runtime error."""
        with pytest.raises(PebbleRuntimeError, match="negative"):
            run_source("print(1 << -1)")

    def test_right_shift_negative_error(self) -> None:
        """Verify ``1 >> -1`` raises a runtime error."""
        with pytest.raises(PebbleRuntimeError, match="negative"):
            run_source("print(1 >> -1)")

    @pytest.mark.parametrize("run", [run_source, pebble.run_source])
    def test_left_shift_too_big_raises(self, run: Callable[[str], str]) -> None:
        """Regression (found by a property test): ``1 << 10 ** 20`` crashed with OverflowError."""
        with pytest.raises(PebbleRuntimeError, match="Shift result is too large"):
            run("let a = 1 << 10 ** 20\nprint(a)")


# -- Precedence ----------------------------------------------------------------


class TestPrecedence:
    """Verify operator precedence is correct."""

    def test_mul_before_add(self) -> None:
        """Verify ``2 + 3 * 4`` groups as ``2 + (3 * 4)`` = ``14``."""
        assert run_source("print(2 + 3 * 4)") == "14\n"

    def test_bitwise_and_before_or(self) -> None:
        """Verify ``1 | 2 & 3`` groups as ``1 | (2 & 3)`` = ``3``."""
        assert run_source("print(1 | 2 & 3)") == "3\n"

    def test_shift_before_bitwise_and(self) -> None:
        """Verify ``1 & 3 << 1`` groups as ``1 & (3 << 1)`` = ``0``."""
        assert run_source("print(1 & 3 << 1)") == "0\n"

    def test_add_before_shift(self) -> None:
        """Verify ``1 << 1 + 1`` groups as ``1 << (1 + 1)`` = ``4``."""
        assert run_source("print(1 << 1 + 1)") == "4\n"

    def test_comparison_before_bitwise_or(self) -> None:
        """Verify ``1 < 2 | 0`` groups correctly — comparison binds tighter in Python.

        Wait — actually in Python, comparison binds *looser* than bitwise.
        ``1 < (2 | 0)`` = ``1 < 2`` = ``True``.

        But in our precedence table, comparison (level 4) is *below* bitwise OR (level 5).
        So ``1 < 2 | 0`` groups as ``1 < (2 | 0)`` = ``1 < 2`` = ``true``.
        """
        assert run_source("print(1 < 2 | 0)") == "true\n"

    def test_power_right_assoc_with_parens(self) -> None:
        """Verify parentheses override right-associativity."""
        assert run_source("print((2 ** 2) ** 3)") == "64\n"

    def test_xor_between_and_and_or(self) -> None:
        """Verify ``3 | 1 ^ 2`` groups as ``3 | (1 ^ 2)`` = ``3``."""
        assert run_source("print(3 | 1 ^ 2)") == "3\n"


# -- Short-circuit evaluation -------------------------------------------------


class TestShortCircuitEvaluation:
    """Verify ``and`` / ``or`` skip the right operand when possible."""

    def test_and_skips_right_side_effect(self) -> None:
        """A falsy left operand of ``and`` skips the right operand entirely."""
        source = (
            "fn boom() {\n"
            '  print("evaluated")\n'
            "  return true\n"
            "}\n"
            "let flag = false\n"
            "print(flag and boom())\n"
        )
        # "evaluated" must NOT appear — boom() is never called.
        assert run_source(source).strip().split("\n") == ["false"]

    def test_or_skips_right_side_effect(self) -> None:
        """A truthy left operand of ``or`` skips the right operand entirely."""
        source = (
            "fn boom() {\n"
            '  print("evaluated")\n'
            "  return false\n"
            "}\n"
            "let flag = true\n"
            "print(flag or boom())\n"
        )
        assert run_source(source).strip().split("\n") == ["true"]

    def test_and_guard_avoids_division_by_zero(self) -> None:
        """The classic guard ``b != 0 and 10 / b > 1`` must not divide by zero."""
        source = "let b = 0\nprint(b != 0 and 10 / b > 1)\n"
        assert run_source(source) == "false\n"

    def test_or_guard_avoids_division_by_zero(self) -> None:
        """The guard ``b == 0 or 10 / b > 1`` must not divide by zero."""
        source = "let b = 0\nprint(b == 0 or 10 / b > 1)\n"
        assert run_source(source) == "true\n"

    def test_and_right_side_runs_when_left_true(self) -> None:
        """The right operand of ``and`` still runs when the left is truthy."""
        source = (
            "fn boom() {\n"
            '  print("evaluated")\n'
            "  return true\n"
            "}\n"
            "let flag = true\n"
            "print(flag and boom())\n"
        )
        assert run_source(source).strip().split("\n") == ["evaluated", "true"]

    def test_and_returns_operand_value(self) -> None:
        """``and`` returns the actual operand, matching prior value semantics."""
        assert run_source("print(2 and 3)") == "3\n"
        assert run_source("print(0 and 3)") == "0\n"

    def test_or_returns_operand_value(self) -> None:
        """``or`` returns the actual operand, matching prior value semantics."""
        assert run_source("print(0 or 5)") == "5\n"
        assert run_source("print(7 or 5)") == "7\n"


# -- Error message consistency ------------------------------------------------


class TestErrorMessageTypeNames:
    """Verify error messages use Pebble type names, not Python ones."""

    def test_type_error_uses_pebble_names(self) -> None:
        """Unsupported operand error should say 'Int' not 'int'."""
        with pytest.raises(PebbleRuntimeError, match="Int"):
            run_source('print(1 + "hello")')

    def test_type_error_string_name(self) -> None:
        """Unsupported operand error should say 'String' not 'str'."""
        with pytest.raises(PebbleRuntimeError, match="String"):
            run_source('print("a" - "b")')


# -- Huge numbers -------------------------------------------------------------

# 10 ** 5000 has 5,001 digits: more than Python will turn into text.
HUGE = "let a = 10 ** 5000\n"


class TestHugeNumbers:
    """Whole numbers can be as big as you like, but some things can't be done with them."""

    @pytest.mark.parametrize(
        "line",
        ["print(a)", "print(str(a))", 'print("{a}")', "print([a])", 'print({"k": a})'],
    )
    @pytest.mark.parametrize("run", [run_source, pebble.run_source])
    def test_too_long_to_print_raises(self, run: Callable[[str], str], line: str) -> None:
        """Regression (found by a property test): ``print(10 ** 5000)`` crashed with ValueError."""
        with pytest.raises(PebbleRuntimeError, match="too long to turn into text"):
            run(HUGE + line)

    def test_too_long_to_print_can_be_caught(self) -> None:
        """The error is an ordinary Pebble error, so ``try``/``catch`` catches it."""
        source = HUGE + 'try {\n    print(a)\n} catch e {\n    print("caught")\n}'
        assert run_source(source) == "caught\n"

    def test_huge_numbers_still_work_in_sums(self) -> None:
        """Only turning one into text is refused: sums and comparisons are fine."""
        assert run_source(HUGE + "print(a - a)\nprint(a > 1)") == "0\ntrue\n"

    def test_throwing_a_huge_number_raises_pebble_error(self) -> None:
        """Regression: an uncaught ``throw 10 ** 5000`` crashed with ValueError."""
        with pytest.raises(PebbleRuntimeError, match="digits long"):
            run_source(HUGE + "throw a")

    def test_huge_index_raises_pebble_error(self) -> None:
        """Regression: the error for a huge list index crashed with ValueError."""
        with pytest.raises(PebbleRuntimeError, match="digits long"):
            run_source(HUGE + "let xs = [1]\nprint(xs[a])")
