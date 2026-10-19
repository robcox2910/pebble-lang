"""Tests for the size limit on whole numbers.

A whole number may be at most ``MAX_INT_BITS`` (1,000,000) bits long,
about 300,000 digits. Anything that would make a bigger one stops with an
ordinary Pebble runtime error instead -- and ``**``, ``*``, ``<<`` and
``math.pow`` work out the size of the answer *before* they make it, so
``2 ** 10 ** 9`` fails at once instead of eating all the memory.
"""

import time
from collections.abc import Callable

import pytest

import pebble
from pebble.builtins import MAX_INT_BITS, NUMBER_TOO_LARGE
from pebble.bytecode import OpCode
from pebble.errors import PebbleRuntimeError
from tests.conftest import compile_instructions_optimized, run_source

RUNNERS = [run_source, pebble.run_source]
# Each of these would build a number far bigger than the limit; Pebble
# must notice before it starts, so they all fail at once.
QUICKLY = 2.0
LIMIT = 1_000_000
JUST_FITS = LIMIT - 1  # 1 << JUST_FITS has exactly LIMIT bits


def fails_quickly(run: Callable[[str], str], source: str) -> None:
    """Assert that running *source* stops with the size error, and quickly."""
    start = time.perf_counter()
    with pytest.raises(
        PebbleRuntimeError, match=r"Number is too large \(more than 1,000,000 bits\)"
    ):
        run(source)
    assert time.perf_counter() - start < QUICKLY


class TestTheLimit:
    """The limit is one named constant with one message."""

    def test_limit_is_a_million_bits(self) -> None:
        """Whole numbers may be at most 1,000,000 bits long."""
        assert MAX_INT_BITS == LIMIT

    def test_message(self) -> None:
        """The error says what the limit is."""
        assert NUMBER_TOO_LARGE == "Number is too large (more than 1,000,000 bits)"


@pytest.mark.parametrize("run", RUNNERS)
class TestHugeAnswersFailAtOnce:
    """An answer far past the limit is refused before Python tries to build it."""

    @pytest.mark.parametrize(
        "expression",
        [
            "2 ** 10 ** 9",
            "(-3) ** 10 ** 9",
            "2 ** (10 ** 5000)",
            "(10 ** 5000) ** (10 ** 5000)",
            "1 << 10 ** 9",
            "(-1) << 10 ** 20",
            "1 << (10 ** 5000)",
        ],
    )
    def test_operator(self, run: Callable[[str], str], expression: str) -> None:
        """``**`` and ``<<`` refuse a huge answer at once, optimised or not."""
        fails_quickly(run, f"let a = {expression}\nprint(a > 0)")

    def test_repeated_squaring(self, run: Callable[[str], str]) -> None:
        """Squaring a number over and over stops as soon as it would pass the limit."""
        fails_quickly(run, "let x = 3\nwhile true {\n    x = x * x\n}")

    def test_repeated_powers(self, run: Callable[[str], str]) -> None:
        """Raising a number to a power over and over stops at the limit too."""
        fails_quickly(run, "let x = 3\nwhile true {\n    x = x ** 3\n}")

    def test_can_be_caught(self, run: Callable[[str], str]) -> None:
        """The error is an ordinary Pebble error, so ``try``/``catch`` catches it."""
        source = "try {\n    print(2 ** 10 ** 9)\n} catch e {\n    print(e)\n}"
        assert run(source) == "Number is too large (more than 1,000,000 bits)\n"


@pytest.mark.parametrize("run", RUNNERS)
class TestRightAtTheLimit:
    """An answer of exactly 1,000,000 bits is allowed; one more bit is not."""

    @pytest.mark.parametrize(
        "expression",
        [
            f"1 << {JUST_FITS}",
            f"2 ** {JUST_FITS}",
            f"(-2) ** {JUST_FITS}",
            # 2 ** 500000 has 500,001 bits and 2 ** 499999 has 500,000: the
            # bit lengths add up to 1,000,001, but the product has 1,000,000.
            "(2 ** 500000) * (2 ** 499999)",
            # 2 ** 1000000 - 1 is the biggest number that fits.
            f"(1 << {JUST_FITS}) - 1 + (1 << {JUST_FITS})",
        ],
    )
    def test_just_fits(self, run: Callable[[str], str], expression: str) -> None:
        """A number of exactly 1,000,000 bits is fine."""
        assert run(f"let a = {expression}\nprint(a != 0)") == "true\n"

    @pytest.mark.parametrize(
        "expression",
        [
            f"1 << {LIMIT}",
            f"2 ** {LIMIT}",
            "(2 ** 500000) * (2 ** 500000)",
            f"(1 << {JUST_FITS}) + (1 << {JUST_FITS})",
            f"-(1 << {JUST_FITS}) - (1 << {JUST_FITS})",
            f"~((1 << {JUST_FITS}) - 1 + (1 << {JUST_FITS}))",
        ],
    )
    def test_one_bit_too_many(self, run: Callable[[str], str], expression: str) -> None:
        """A number of 1,000,001 bits is refused, however it was made."""
        fails_quickly(run, f"let a = {expression}\nprint(a != 0)")


@pytest.mark.parametrize("run", RUNNERS)
class TestPowersThatStaySmall:
    """0, 1 and -1 to any power stay small, so they're worked out straight away."""

    @pytest.mark.parametrize(
        ("expression", "answer"),
        [
            ("0 ** (10 ** 5000)", "0"),
            ("1 ** (10 ** 5000)", "1"),
            ("(-1) ** (10 ** 5000)", "1"),
            ("(-1) ** (10 ** 5000 + 1)", "-1"),
            ("0 ** 0", "1"),
            ("(10 ** 5000) ** 0", "1"),
            ("0 << (10 ** 20)", "0"),
            ("2 ** -(10 ** 9)", "0.0"),
            ("1 >> (10 ** 20)", "0"),
        ],
    )
    def test_small_answer(self, run: Callable[[str], str], expression: str, answer: str) -> None:
        """The answer is exact, and comes back quickly."""
        start = time.perf_counter()
        assert run(f"print({expression})") == f"{answer}\n"
        assert time.perf_counter() - start < QUICKLY


class TestMathPow:
    """``math.pow`` keeps to the same limit as ``**``."""

    @pytest.mark.parametrize("call", ["pow(2, 10 ** 9)", "pow(2, 10 ** 5000)", "pow(-7, 10 ** 6)"])
    def test_huge_answer_fails_at_once(self, call: str) -> None:
        """``math.pow`` refuses a huge whole-number answer at once."""
        fails_quickly(pebble.run_source, f'import "math"\nlet a = {call}\nprint(a > 0)')

    def test_just_fits(self) -> None:
        """``math.pow`` can make a number of exactly 1,000,000 bits."""
        source = f'import "math"\nlet a = pow(2, {JUST_FITS})\nprint(a != 0)'
        assert pebble.run_source(source) == "true\n"

    def test_one_bit_too_many(self) -> None:
        """``math.pow`` refuses a number of 1,000,001 bits."""
        fails_quickly(pebble.run_source, f'import "math"\nlet a = pow(2, {LIMIT})\nprint(a != 0)')

    @pytest.mark.parametrize(
        ("call", "answer"), [("pow(1, 10 ** 5000)", "1"), ("pow(0, 10 ** 5000)", "0")]
    )
    def test_small_answer(self, call: str, answer: str) -> None:
        """``pow(1, 10 ** 5000)`` is 1, straight away."""
        assert pebble.run_source(f'import "math"\nprint({call})') == f"{answer}\n"


class TestFloatsAreUnchanged:
    """Floats keep their own rules: the limit is for whole numbers only."""

    def test_float_power_too_big_for_a_float(self) -> None:
        """``2.0 ** 1000000`` is still the float error."""
        with pytest.raises(PebbleRuntimeError, match="Exponentiation result is too large"):
            run_source(f"print(2.0 ** {LIMIT})")

    def test_printing_is_still_limited_to_4300_digits(self) -> None:
        """A number well inside the limit still can't be printed past 4,300 digits."""
        with pytest.raises(PebbleRuntimeError, match="more than 4,300 digits"):
            run_source("print(10 ** 5000)")


class TestTheOptimiserLeavesHugeAnswersAlone:
    """The optimiser never folds a constant past the limit: the VM reports it."""

    @pytest.mark.parametrize(
        ("expression", "opcode"),
        [
            ("2 ** 1000000000", OpCode.POWER),
            (f"1 << {LIMIT}", OpCode.LEFT_SHIFT),
            ("(2 ** 500000) * (2 ** 500000)", OpCode.MULTIPLY),
            (f"(1 << {JUST_FITS}) + (1 << {JUST_FITS})", OpCode.ADD),
        ],
    )
    def test_not_folded(self, expression: str, opcode: OpCode) -> None:
        """The operator that would pass the limit is still there after optimising."""
        start = time.perf_counter()
        opcodes = [i.opcode for i in compile_instructions_optimized(f"print({expression})")]
        assert opcode in opcodes
        assert time.perf_counter() - start < QUICKLY

    def test_small_answers_still_fold(self) -> None:
        """``2 ** 10`` still folds to 1024."""
        opcodes = [i.opcode for i in compile_instructions_optimized("print(2 ** 10)")]
        assert OpCode.POWER not in opcodes
