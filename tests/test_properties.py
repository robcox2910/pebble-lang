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

from collections.abc import Callable
from contextlib import suppress
from functools import cache
from io import StringIO

from hypothesis import given
from hypothesis import strategies as st

from pebble import PebbleError, check, format_source, run_source
from pebble.bytecode import CompiledProgram
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
    """Make a whole number from -2 to 6, for the right of ``**``, ``<<`` and ``>>``."""
    # Kept small on purpose: ``9 ** 9 ** 9`` or ``1 << 10 ** 9`` would take
    # ages and eat all the memory, which is a different test from this one.
    positive = st.integers(min_value=0, max_value=6).map(str).map(one_token)
    negative = st.sampled_from(["1", "2"]).map(minus)
    return st.one_of(positive, negative)


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


@st.composite
def runnable_towers(draw: st.DrawFn) -> str:
    """Make a whole program with one piece stacked up to 5,000 times, like ``1 + 1 + 1 ...``."""
    start, piece, end = draw(st.sampled_from(RUNNABLE_TOWERS))
    times = draw(st.integers(min_value=0, max_value=LONGEST_REPEAT))
    return start + piece * times + end


def huge_numbers() -> st.SearchStrategy[Tokens]:
    """Make a huge whole number: ``( 10 ** 309 )``, ``( 10 ** 5000 )`` or ``( 1 << 10 ** 20 )``."""
    exponents = st.sampled_from(HUGE_POWERS_OF_TEN).map(one_token)
    power = st.builds(in_brackets, st.just(["10"]), st.just("**"), exponents)
    shift = st.just(["(", "1", "<<", "10", "**", "20", ")"])
    return st.one_of(power, shift)


@st.composite
def programs_with_huge_numbers(draw: st.DrawFn) -> str:
    """Make a program that prints a huge number, then does sums with it and prints those."""
    # The second line mixes it with a number like 2 or 0.5 (a float), the
    # rest with anything at all. Some programs end by throwing an answer.
    operator = draw(st.sampled_from(ARITHMETIC_OPERATORS))
    lines: Lines = [
        (0, ["let", "a", "=", *draw(huge_numbers())]),
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
