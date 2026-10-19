"""Property-based tests -- rules that must hold for *every* program.

An ordinary test checks one program someone thought of: "``print(1 + 2)``
prints 3". A property test states a rule instead, such as "the optimiser
never changes what a program prints, whatever the program", and lets
Hypothesis invent hundreds of programs to try to break it. If one breaks
the rule, Hypothesis *shrinks* it down to the smallest program that still
fails, and shows you that.

Each test below says its rule in plain English in its docstring. The
strategies at the top are recipes for making random inputs; each one is
named for what it makes. The formatter's own round-trip properties live
in ``tests/test_format_roundtrip.py``.

See ``docs/property-testing.md`` for the walk-through.
"""

import math
import operator
import time
from collections.abc import Callable
from contextlib import suppress
from functools import cache
from io import StringIO

from hypothesis import example, given
from hypothesis import strategies as st

from pebble import PebbleError, check, format_source, run_source
from pebble.builtins import MAX_INT_BITS, NUMBER_TOO_LARGE, Value
from pebble.bytecode import CompiledProgram
from pebble.optimizer import optimize
from pebble.stdlib import MATH_MODULE
from pebble.tokens import KEYWORDS
from pebble.vm import VirtualMachine
from tests.conftest import compile_source, compile_source_optimized

# --- Strategies: recipes for random inputs -----------------------------------

# A program is made as a list of lines. Each line is an indent level and a
# list of tokens (the words and symbols of Pebble, like ``let``, ``x``,
# ``=`` and ``(``), so the same program can be written out tidily or messily.
type Tokens = list[str]
type Lines = list[tuple[int, Tokens]]

VARIABLE_NAMES = ["a", "b", "c", "total", "n"]
ARITHMETIC_OPERATORS = ["+", "-", "*", "/", "//", "%"]
ALL_OPERATORS = [
    *ARITHMETIC_OPERATORS,
    "==", "!=", "<", "<=", ">", ">=",
    "and", "or", "&", "|", "^",
]  # fmt: skip
LONGEST_REPEAT = 5_000
# What a tower starts with, and the piece it stacks: "List[" only nests
# inside a type annotation, and "else if" only follows an "if".
TOWER_PIECES = [
    ("", "("), ("", "["), ("", "{"), ("", "-"), ("", "not "), ("", "~"),
    ("", "0"), ("", "9"), ("", "if x { "),
    ("let x: ", "List["), ("if x {}", " else if x {}"),
]  # fmt: skip
MOST_VALUES_PER_EXPRESSION = 6


def any_text() -> st.SearchStrategy[str]:
    """Make any text at all: empty, emoji, accents, control characters, the lot."""
    return st.text()


def pebble_pieces() -> st.SearchStrategy[str]:
    """Make one piece of Pebble: a keyword, a symbol, a name, a number or a quote."""
    symbols = [*'(){}[],.:+-*/%<>=!&|^~"\n ', "**", "//", "==", "->", "{{"]
    words = [*KEYWORDS, "x", "print", "0", "7", "1.5", "1e9"]
    return st.sampled_from(symbols + words)


def pebble_soup() -> st.SearchStrategy[str]:
    """Make a jumble of Pebble pieces: it looks like Pebble but rarely is."""
    return st.lists(pebble_pieces(), max_size=30).map("".join)


@st.composite
def towers(draw: st.DrawFn) -> str:
    """Make one piece stacked up to 5,000 times, like 5,000 open brackets."""
    start, piece = draw(st.sampled_from(TOWER_PIECES))
    times = draw(st.integers(min_value=0, max_value=LONGEST_REPEAT))
    return start + piece * times


def scraps_of_text() -> st.SearchStrategy[str]:
    """Make text that might be Pebble: random characters, a jumble, or a tall tower."""
    return st.one_of(any_text(), pebble_soup(), towers())


def one_token(token: str) -> Tokens:
    """Return an expression that is just *token* on its own."""
    return [token]


def in_brackets(left: Tokens, operator: str, right: Tokens) -> Tokens:
    """Return ``( left operator right )``."""
    return ["(", *left, operator, *right, ")"]


def minus(digit: str) -> Tokens:
    """Return ``- digit``, a negative number written out."""
    return ["-", digit]


def applied(operator: str, operand: Tokens) -> Tokens:
    """Return ``operator ( operand )``, such as ``not ( x )``."""
    return [operator, "(", *operand, ")"]


def numbers() -> st.SearchStrategy[Tokens]:
    """Make a number written out: a whole number from 0 to 20, or a decimal like 3.25."""
    whole = st.integers(min_value=0, max_value=20).map(str)
    decimal = st.builds("{}.{}".format, st.integers(0, 9), st.integers(0, 99))
    return st.one_of(whole, decimal).map(one_token)


def literals() -> st.SearchStrategy[Tokens]:
    """Make any value written out: a number, a word in quotes, or true/false."""
    others = st.sampled_from(['"hi"', '"pebble"', '""', "true", "false"]).map(one_token)
    return st.one_of(numbers(), others)


def small_numbers() -> st.SearchStrategy[Tokens]:
    """Make a whole number from -2 to 6, or now and then 10 ** 9, for the right of ``**``, ``<<`` and ``>>``."""
    # Mostly small, so most sums give an answer. ``10 ** 9`` makes answers
    # like ``9 ** 10 ** 9``, far past the size limit for whole numbers:
    # Pebble refuses those at once, optimised or not.
    positive = st.integers(min_value=0, max_value=6).map(str).map(one_token)
    negative = st.sampled_from(["1", "2"]).map(minus)
    huge = st.just(["(", "10", "**", "9", ")"])
    return st.one_of(positive, negative, huge)


def bigger_sums(smaller: st.SearchStrategy[Tokens]) -> st.SearchStrategy[Tokens]:
    """Make a sum by joining smaller ones with an arithmetic operator."""
    return st.one_of(
        st.builds(in_brackets, smaller, st.sampled_from(ARITHMETIC_OPERATORS), smaller),
        st.builds(in_brackets, smaller, st.just("**"), small_numbers()),
        st.builds(applied, st.just("-"), smaller),
    )


def bigger_expressions(smaller: st.SearchStrategy[Tokens]) -> st.SearchStrategy[Tokens]:
    """Make an expression by joining smaller ones with any operator at all."""
    return st.one_of(
        st.builds(in_brackets, smaller, st.sampled_from(ALL_OPERATORS), smaller),
        st.builds(in_brackets, smaller, st.sampled_from(["**", "<<", ">>"]), small_numbers()),
        st.builds(applied, st.sampled_from(["-", "not", "~"]), smaller),
    )


@cache
def sums(names: tuple[str, ...]) -> st.SearchStrategy[Tokens]:
    """Make arithmetic on numbers and the variables in *names*, like ``( a * 2.5 )``."""
    atoms = numbers()
    if names:
        atoms = st.one_of(atoms, st.sampled_from(names).map(one_token))
    return st.recursive(atoms, bigger_sums, max_leaves=MOST_VALUES_PER_EXPRESSION)


@cache
def expressions(names: tuple[str, ...]) -> st.SearchStrategy[Tokens]:
    """Make any expression: values of every kind, the variables in *names*, any operator."""
    atoms = literals()
    if names:
        atoms = st.one_of(atoms, st.sampled_from(names).map(one_token))
    return st.recursive(atoms, bigger_expressions, max_leaves=MOST_VALUES_PER_EXPRESSION)


@st.composite
def programs(draw: st.DrawFn) -> Lines:
    """Make a small program of ``let``, ``print`` and ``if``/``else`` lines."""
    # Variables only ever hold numbers, and most lines print a sum, so a
    # program usually runs to the end. A few lines mix in every kind of
    # value and operator, which is where the strange cases live. At the end
    # it prints every variable, so a wrong answer can't hide in one.
    lines: Lines = []
    defined: tuple[str, ...] = ()
    for name in draw(st.lists(st.sampled_from(VARIABLE_NAMES), max_size=3, unique=True)):
        lines.append((0, ["let", name, "=", *draw(sums(defined))]))
        defined = (*defined, name)
    for _ in range(draw(st.integers(min_value=1, max_value=4))):
        kind = draw(st.sampled_from(["print a sum", "print anything", "if"]))
        if kind == "if":
            lines.append((0, ["if", *draw(expressions(defined)), "{"]))
            lines.append((1, ["print", "(", *draw(sums(defined)), ")"]))
            lines.append((0, ["}", "else", "{"]))
            lines.append((1, ["print", "(", *draw(sums(defined)), ")"]))
            lines.append((0, ["}"]))
        else:
            value = sums(defined) if kind == "print a sum" else expressions(defined)
            lines.append((0, ["print", "(", *draw(value), ")"]))
    lines.extend((0, ["print", "(", name, ")"]) for name in defined)
    return lines


def write_out(lines: Lines, gap: Callable[[], str], indent: str) -> str:
    """Write a program as text, with ``gap()`` between tokens and *indent* per level."""
    written: list[str] = []
    for level, tokens in lines:
        spaced = "".join(token + gap() for token in tokens[:-1]) + tokens[-1]
        written.append(indent * level + spaced)
    return "\n".join(written)


def tidy(lines: Lines) -> str:
    """Write a program with one space between tokens and four-space indents."""
    return write_out(lines, lambda: " ", "    ")


def tidy_programs() -> st.SearchStrategy[str]:
    """Make a small program, written out tidily."""
    return programs().map(tidy)


@st.composite
def messy_and_tidy_programs(draw: st.DrawFn) -> tuple[str, str]:
    """Make a small program written out twice: once with odd spacing, once tidily."""
    lines = draw(programs())
    indent = draw(st.sampled_from(["", " ", "  ", "\t"]))
    messy = write_out(lines, lambda: draw(st.sampled_from([" ", "  ", "    "])), indent)
    return messy, tidy(lines)


# Towers that are whole programs, so they get past the parser and run:
# what goes before the stacked piece, the piece, and what closes it off.
RUNNABLE_TOWERS = [
    ("print(1", " + 1", ")"),
    ("print(true", " and true", ")"),
    ("print(0", " < 1", ")"),
    ('print("a"', ".upper()", ")"),
    ("let a = [0]\nprint(a", "[0]", ")"),
    ("print(", "-", "1)"),
    ("print(2", " ** 1", ")"),
    ("let x = 1\nif x == 0 {}", " else if x == 0 {}", " else {\n    print(x)\n}"),
]  # fmt: skip
# Powers of ten for huge numbers: 10 ** 309 is too big for a float, and
# 10 ** 5000 has 5,001 digits, more than Python will turn into text.
HUGE_POWERS_OF_TEN = ["309", "5000"]
# Built-in and math functions that take one number, to call on a huge one.
ONE_NUMBER_FUNCTIONS = [
    "int", "float", "str", "abs", "floor", "ceil", "round", "sqrt", "sin", "cos", "log",
]  # fmt: skip


@st.composite
def runnable_towers(draw: st.DrawFn) -> str:
    """Make a whole program with one piece stacked up to 5,000 times, like ``1 + 1 + 1 ...``."""
    start, piece, end = draw(st.sampled_from(RUNNABLE_TOWERS))
    times = draw(st.integers(min_value=0, max_value=LONGEST_REPEAT))
    return start + piece * times + end


def huge_numbers() -> st.SearchStrategy[Tokens]:
    """Make a number at the edge: ``( 10 ** 309 )``, ``( 10 ** 5000 )``, ``( 1 << 999999 )``, inf or nan."""
    exponents = st.sampled_from(HUGE_POWERS_OF_TEN).map(one_token)
    power = st.builds(in_brackets, st.just(["10"]), st.just("**"), exponents)
    # 1 << 999999 has 1,000,000 bits: the biggest size a whole number may be.
    shift = st.just(["(", "1", "<<", "999999", ")"])
    # Pebble has no literal for infinity or nan, so make them from floats.
    infinity = ["(", "10.0", "**", "308", "*", "10", ")"]
    nan = ["(", *infinity, "-", *infinity, ")"]
    return st.one_of(power, shift, st.sampled_from([infinity, nan]))


def decimals() -> st.SearchStrategy[Tokens]:
    """Make a decimal number, like 2.5 (a float, never a whole number)."""
    return st.builds("{}.{}".format, st.integers(0, 9), st.integers(0, 99)).map(one_token)


@st.composite
def programs_with_huge_numbers(draw: st.DrawFn) -> str:
    """Make a program that hands a huge number to functions, prints it, then does sums with it."""
    # Every built-in or math function gets a go, each inside try/catch so
    # one polite error doesn't stop the rest. ``pow`` gets a float or a
    # whole number on the other side: pow(2, 10 ** 5000) would have more
    # digits than there are atoms in the universe, so it stops at once with
    # "Number is too large". Then the number is printed, mixed with a
    # number like 2 or 0.5 (a float), and with anything at all. Some
    # programs end by throwing.
    other = draw(st.one_of(decimals(), numbers()))
    calls = [[name, "(", "a", ")"] for name in ONE_NUMBER_FUNCTIONS]
    calls += [["pow", "(", "a", ",", *other, ")"], ["pow", "(", *other, ",", "a", ")"]]
    operator = draw(st.sampled_from(ARITHMETIC_OPERATORS))
    lines: Lines = [
        (0, ["import", '"math"']),
        (0, ["let", "a", "=", *draw(huge_numbers())]),
    ]
    for call in calls:
        lines += [
            (0, ["try", "{"]),
            (1, ["print", "(", *call, ")"]),
            (0, ["}", "catch", "e", "{"]),
            (1, ["print", "(", "e", ")"]),
            (0, ["}"]),
        ]
    lines += [
        (0, ["print", "(", "a", ")"]),
        (0, ["print", "(", "a", operator, *draw(numbers()), ")"]),
    ]
    for _ in range(draw(st.integers(min_value=0, max_value=2))):
        lines.append((0, ["print", "(", *draw(expressions(("a",))), ")"]))
    if draw(st.booleans()):
        lines.append((0, ["throw", *draw(expressions(("a",)))]))
    return tidy(lines)


def runnable_programs() -> st.SearchStrategy[str]:
    """Make a program to run: an ordinary one, one with huge numbers, or a tall tower."""
    return st.one_of(tidy_programs(), programs_with_huge_numbers(), runnable_towers())


# --- Helpers -----------------------------------------------------------------


def what_it_prints(build: Callable[[str], CompiledProgram], source: str) -> str:
    """Compile *source* with *build*, run it, and return what it printed, and any error."""
    output = StringIO()
    try:
        VirtualMachine(output=output).run(build(source))
    except PebbleError as error:
        output.write(f"<error: {error}>")
    return output.getvalue()


# --- The parser: any text gets an answer, never a crash ----------------------


@given(text=scraps_of_text())
def test_check_only_ever_raises_pebble_error(text: str) -> None:
    """Whatever text you hand to ``check``, it either accepts it or raises a PebbleError."""
    with suppress(PebbleError):
        check(text)


# --- Running a program: it prints, or stops with a Pebble error -------------


@given(source=runnable_programs())
def test_run_source_only_ever_raises_pebble_error(source: str) -> None:
    """Whatever program you run, ``run_source`` returns what it printed or raises a PebbleError."""
    with suppress(PebbleError):
        run_source(source)


# --- The optimiser: faster, never different ----------------------------------


@given(source=tidy_programs())
def test_optimiser_never_changes_what_a_program_prints(source: str) -> None:
    """A program prints exactly the same thing, errors included, with or without the optimiser."""
    plain = what_it_prints(compile_source, source)
    optimised = what_it_prints(compile_source_optimized, source)
    assert optimised == plain


# --- The formatter: how you spaced it out doesn't matter ---------------------


@given(versions=messy_and_tidy_programs())
def test_formatting_ignores_how_a_program_was_spaced(versions: tuple[str, str]) -> None:
    """However oddly a program is spaced, the formatter turns it into the same tidy text."""
    messy, tidy_version = versions
    assert format_source(messy) == format_source(tidy_version)


# --- Whole numbers: the right answer, or the size error, and quickly ---------

# The operations that can make a whole number bigger. ``pow`` is math.pow.
GROWING_OPERATIONS = ["+", "-", "*", "**", "<<", "~", "pow"]
# Bit lengths right by the edges that matter: half the limit (for ``*``),
# a third (for ``** 3``) and the limit itself.
EDGE_BITS = [MAX_INT_BITS // 3, MAX_INT_BITS // 2, MAX_INT_BITS]
# How far to land from the limit when aiming at it.
NUDGE = 2
# Python's own answer is only worked out when it has at most this many
# bits, so the test stays quick. Past it, the answer can't fit (see
# ``most_bits``), so Pebble must refuse it.
MOST_BITS_TO_CHECK = 2 * MAX_INT_BITS + 2
QUICKLY = 2.0
# Stand-ins for the two operands: compiled into a program, then swapped
# for the real (maybe huge) numbers, which are too long to write out.
LEFT_STAND_IN = 7
RIGHT_STAND_IN = 11


@st.composite
def numbers_of(draw: st.DrawFn, bits: int) -> int:
    """Make a whole number with exactly *bits* bits, either sign."""
    if bits <= 0:
        return 0
    top = 1 << (bits - 1)
    shape = draw(st.sampled_from(["power of two", "all ones", "a few low bits"]))
    if shape == "power of two":
        value = top
    elif shape == "all ones":
        value = (top << 1) - 1
    else:
        value = top | (draw(st.integers(0, 2**64)) & (top - 1))
    return -value if draw(st.booleans()) else value


def nudged(bits: int, nudge: int) -> int:
    """Return *bits* moved by *nudge*, kept between 0 and the limit."""
    return max(0, min(MAX_INT_BITS, bits + nudge))


def whole_numbers() -> st.SearchStrategy[int]:
    """Make a whole number of up to 1,000,000 bits, often right by an edge."""
    near_an_edge = st.builds(nudged, st.sampled_from(EDGE_BITS), st.integers(-NUDGE, NUDGE))
    bits = st.one_of(st.integers(0, 70), st.integers(0, MAX_INT_BITS), near_an_edge)
    return bits.flatmap(numbers_of)


def exponents() -> st.SearchStrategy[int]:
    """Make a right-hand side for ``**``, ``<<`` and ``pow``: small, big or absurd."""
    return st.one_of(
        st.integers(0, 70),
        st.integers(0, 3 * MAX_INT_BITS),
        st.integers(0, 10**30),
        whole_numbers().map(abs),
    )


@st.composite
def aimed_at_the_limit(draw: st.DrawFn, operation: str, left: int) -> int:
    """Make a right-hand side that puts the answer within a few bits of the limit."""
    nudge = draw(st.integers(-NUDGE, NUDGE))
    bits = left.bit_length()
    match operation:
        case "**" | "pow":
            size = math.log2(abs(left)) if abs(left) > 1 else 1.0
            return max(0, int(MAX_INT_BITS / size) + nudge)
        case "<<":
            return max(0, MAX_INT_BITS - bits + nudge)
        case "*":
            return draw(numbers_of(nudged(MAX_INT_BITS + 1 - bits, nudge)))
        case _:  # "+" and "-"
            return draw(numbers_of(nudged(bits, nudge)))


@st.composite
def growing_sums(draw: st.DrawFn) -> tuple[str, int, int]:
    """Make an operation that can grow a number, and its two operands."""
    operation = draw(st.sampled_from(GROWING_OPERATIONS))
    is_a_power = operation in {"**", "<<", "pow"}
    # A small base (like 3) makes the most interesting powers: 3 ** 630929
    # fits, but 3 ** 630930 doesn't.
    small = st.builds(operator.mul, st.integers(2, 1000), st.sampled_from([1, -1]))
    left = draw(small if is_a_power and draw(st.booleans()) else whole_numbers())
    if draw(st.integers(0, 3)):  # three times in four, aim right at the limit
        right = draw(aimed_at_the_limit(operation, left))
    else:
        right = draw(exponents() if is_a_power else whole_numbers())
    return operation, left, right


def most_bits(operation: str, left: int, right: int) -> int:
    """Return the most bits Python's answer could have, without working it out.

    The answer always has more than half this many bits, so when this is
    past ``MOST_BITS_TO_CHECK`` the answer is past the limit.
    """
    match operation:
        case "+" | "-":
            return max(left.bit_length(), right.bit_length()) + 1
        case "*":
            return left.bit_length() + right.bit_length()
        case "**" | "pow":
            return 1 if abs(left) <= 1 else left.bit_length() * right
        case "<<":
            return left.bit_length() + right if left else 0
        case _:  # "~"
            return left.bit_length() + 1


def python_answer(operation: str, left: int, right: int) -> int:
    """Return Python's answer to ``left operation right``."""
    match operation:
        case "+":
            return left + right
        case "-":
            return left - right
        case "*":
            return left * right
        case "**" | "pow":
            return left**right
        case "<<":
            return left << right
        case _:  # "~"
            return ~left


def pebble_answers(operation: str, left: int, right: int) -> list[Value]:
    """Return Pebble's answer, or its error message, with and without the optimiser."""
    if operation == "pow":
        handler = MATH_MODULE.functions["pow"][1]
        assert handler is not None
        try:
            return [handler([left, right])]
        except PebbleError as error:
            return [error.message]
    source = "let r = ~7" if operation == "~" else f"let r = 7 {operation} 11"
    plain = compile_source(source)
    constants = plain.main.constants
    constants[constants.index(LEFT_STAND_IN)] = left
    if operation != "~":
        constants[constants.index(RIGHT_STAND_IN)] = right
    answers: list[Value] = []
    for build in (lambda: plain, lambda: optimize(plain)):
        try:
            answers.append(VirtualMachine().run_repl(build(), {})["r"])
        except PebbleError as error:
            answers.append(error.message)
    return answers


# The edges, always tried: 3 ** 630929 has 999,999 bits and 3 ** 630930
# has 1,000,001; 2 ** 500000 * 2 ** 499999 adds up to 1,000,001 bits but
# has 1,000,000; and so on.
@given(growing_sum=growing_sums())
@example(growing_sum=("**", 3, 630929))
@example(growing_sum=("**", -3, 630930))
@example(growing_sum=("pow", 3, 630929))
@example(growing_sum=("pow", 3, 630930))
@example(growing_sum=("*", 1 << 500000, 1 << 499999))
@example(growing_sum=("*", (1 << 500000) - 1, (1 << 500001) - 1))
@example(growing_sum=("<<", -1, MAX_INT_BITS - 1))
@example(growing_sum=("<<", 1, MAX_INT_BITS))
@example(growing_sum=("+", 1 << (MAX_INT_BITS - 1), 1 << (MAX_INT_BITS - 1)))
@example(growing_sum=("~", (1 << MAX_INT_BITS) - 1, 0))
def test_whole_numbers_are_right_or_too_large(growing_sum: tuple[str, int, int]) -> None:
    """A sum gives Python's answer when it fits in 1,000,000 bits, the size error when not, and quickly."""
    operation, left, right = growing_sum
    start = time.perf_counter()
    answers = pebble_answers(operation, left, right)
    assert time.perf_counter() - start < QUICKLY
    if most_bits(operation, left, right) <= MOST_BITS_TO_CHECK:
        answer = python_answer(operation, left, right)
        expected = answer if answer.bit_length() <= MAX_INT_BITS else NUMBER_TOO_LARGE
    else:
        expected = NUMBER_TOO_LARGE
    assert all(answer == expected for answer in answers)
