"""Tests for new operators: exponentiation, floor division, and bitwise."""

import pytest

from pebble.errors import PebbleRuntimeError
from tests.conftest import (  # pyright: ignore[reportMissingImports]
    run_source,  # pyright: ignore[reportUnknownVariableType]
)

# -- Named constants ----------------------------------------------------------

POWER_RESULT = 8
RIGHT_ASSOC_RESULT = 256
NEGATIVE_EXPONENT_RESULT = 0.5
FLOAT_POWER_RESULT = 2.0


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
