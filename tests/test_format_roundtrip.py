"""Formatting must never break a program or change what it means.

A formatter is a tidy-up robot for your bedroom: it can sort things into
neat piles, but it must never throw anything away or glue a drawer shut.
These tests check the two promises every formatter makes:

1. The tidied program still parses -- and means exactly the same thing.
2. Tidying an already-tidy program changes nothing at all.

Besides hand-picked examples, Hypothesis invents hundreds of random
programs to try, so we catch the cases nobody thought to write down.
"""

import dataclasses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pebble.formatter import Formatter
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.tokens import KEYWORDS

ROUND_TRIP_SOURCES = [
    "struct Point { x, y }",
    "struct Point { x: Int, y: Int }",
    "struct Point {\n    x,\n    y\n}",
    "struct Point {\n    x,\n    y,\n}",
    "struct Empty {}",
    "struct Point { x, y }\nlet p = Point(1, 2)\nprint(p.x)",
    "class Dog { name, age }",
    "enum Color { Red, Green, Blue }",
    "fn add(a, b) {\n    return a + b\n}",
    "if 1 < 2 {\n    print(1)\n} else {\n    print(2)\n}",
    "let xs = [1, 2, 3]\nfor x in xs {\n    print(x)\n}",
]


def _parse(source: str) -> object:
    """Parse Pebble source into its AST (raises on invalid code)."""
    return Parser(Lexer(source).tokenize()).parse()


def _shape(node: object) -> object:
    """Describe an AST without line/column positions, so we can compare meaning."""
    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        return (
            type(node).__name__,
            tuple(
                (f.name, _shape(getattr(node, f.name)))
                for f in dataclasses.fields(node)
                if f.name != "location"
            ),
        )
    if isinstance(node, list | tuple):
        items: list[object] | tuple[object, ...] = node  # pyright: ignore[reportUnknownVariableType]
        return tuple(_shape(item) for item in items)
    return node


def _check_round_trip(source: str) -> None:
    """Assert formatting keeps the program valid, unchanged in meaning, and stable."""
    formatted = Formatter(source).format()
    assert _shape(_parse(formatted)) == _shape(_parse(source)), formatted
    assert Formatter(formatted).format() == formatted


@pytest.mark.parametrize("source", ROUND_TRIP_SOURCES)
def test_formatting_keeps_programs_valid_and_stable(source: str) -> None:
    """Regression: one-line structs used to format into code that didn't parse."""
    _check_round_trip(source)


_NAMES = st.from_regex(r"[a-z][a-z0-9_]{0,5}", fullmatch=True).filter(
    lambda name: name not in KEYWORDS
)
_TYPES = st.sampled_from(["", ": Int", ": String", ": Bool", ": Float"])


@st.composite
def _struct_source(draw: st.DrawFn) -> str:
    """Invent a struct definition, written on one line or several."""
    name = draw(st.from_regex(r"[A-Z][a-z]{0,6}", fullmatch=True))
    field_names = draw(st.lists(_NAMES, max_size=4, unique=True))
    fields = [f"{field}{draw(_TYPES)}" for field in field_names]
    if draw(st.booleans()):
        return f"struct {name} {{ {', '.join(fields)} }}"
    trailing_comma = "," if fields and draw(st.booleans()) else ""
    body = ",\n".join(f"    {field}" for field in fields)
    return f"struct {name} {{\n{body}{trailing_comma}\n}}"


@st.composite
def _program_source(draw: st.DrawFn) -> str:
    """Invent a small program: some structs and some simple statements."""
    lines = draw(st.lists(_struct_source(), min_size=1, max_size=3))
    for name in draw(st.lists(_NAMES, max_size=3, unique=True)):
        value = draw(st.integers(min_value=-50, max_value=50))
        operand = draw(st.integers(min_value=0, max_value=9))
        lines.append(f"let {name} = {value} + {operand} * 2")
    return "\n".join(lines)


@given(_program_source())
def test_random_programs_survive_formatting(source: str) -> None:
    """Any program we can parse still parses -- and means the same -- after tidying."""
    _check_round_trip(source)


@st.composite
def _commented_program(draw: st.DrawFn) -> tuple[str, list[str]]:
    """Invent a program with comments sprinkled between and after statements."""
    statements = draw(st.lists(_NAMES, min_size=1, max_size=4, unique=True))
    lines: list[str] = []
    comments: list[str] = []
    for index, name in enumerate(statements):
        if draw(st.booleans()):
            comments.append(f"# note {index}")
            lines.append(comments[-1])
        line = f"let {name} = {index}"
        if draw(st.booleans()):
            comments.append(f"# tail {index}")
            line += f"  {comments[-1]}"
        lines.append(line)
    if draw(st.booleans()):
        block = ["fn helper() {", "# inside", "return 1", "}"]
        comments.append("# inside")
        lines.extend(block)
    return "\n".join(lines), comments


@given(_commented_program())
def test_comments_survive_formatting_once_each(case: tuple[str, list[str]]) -> None:
    """Every comment appears exactly once after tidying, and the code still round-trips."""
    source, comments = case
    formatted = Formatter(source).format()
    for comment in comments:
        assert formatted.count(comment) == 1, (comment, formatted)
    for line in formatted.splitlines():
        if line.strip().startswith("# tail"):
            pytest.fail(f"inline comment became a standalone line: {formatted!r}")
    _check_round_trip(source)
