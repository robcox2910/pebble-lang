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
import re
from contextlib import suppress
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pebble import PebbleError, check, format_source
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


DOCS = Path(__file__).parent.parent / "docs"
_PEBBLE_FENCE = re.compile(r"```pebble\n(.*?)```", re.DOTALL)


def _docs_snippets() -> list[str]:
    """Return every ```pebble snippet in the docs that parses (some show errors on purpose)."""
    snippets: list[str] = []
    for page in sorted(DOCS.rglob("*.md")):
        for match in _PEBBLE_FENCE.finditer(page.read_text(encoding="utf-8")):
            with suppress(PebbleError):
                check(match.group(1))
                snippets.append(match.group(1))
    return snippets


def test_docs_snippets_format_once_and_stay_put() -> None:
    """Formatting every docs snippet works, and formatting the result changes nothing.

    Regression (found in review): the comment in linter.md's empty-block
    example jumped to the top of the file, indented, and moved again on the
    next format.
    """
    snippets = _docs_snippets()
    assert snippets, "no ```pebble snippets found in docs/"
    for snippet in snippets:
        formatted = format_source(snippet)
        assert format_source(formatted) == formatted, snippet


# Pieces of program to build from, as (indent level, code) lines. Each one
# opens and closes its own blocks, and some blocks are left empty, because
# a comment alone in a block, or on a closing ``}``, is where comments used
# to go missing.
type CodeLines = list[tuple[int, str]]
_PIECES: list[CodeLines] = [
    [(0, "print(1)")],
    [(0, "let n = 2")],
    [(0, "if true {"), (1, "print(1)"), (0, "}")],
    [(0, "if true {"), (0, "}")],
    [(0, "if true {"), (1, "print(1)"), (0, "} else {"), (1, "print(2)"), (0, "}")],
    [(0, "if true {"), (0, "} else if false {"), (1, "print(2)"), (0, "} else {"), (0, "}")],
    [(0, "while false {"), (0, "}")],
    [(0, "while false {"), (1, "if true {"), (2, "print(1)"), (1, "}"), (0, "}")],
    [(0, "fn helper() {"), (1, "return 1"), (0, "}")],
    [(0, "fn nothing() {"), (0, "}")],
    [(0, "struct Point {"), (1, "x,"), (1, "y"), (0, "}")],
    [(0, "let f = fn(x) {"), (1, "return x"), (0, "}")],
    [(0, "enum Color {"), (1, "Red,"), (1, "Green"), (0, "}")],
    [(0, "class Dog {"), (1, "name,"), (1, "fn bark(self) {"), (2, "print(1)"), (1, "}"), (0, "}")],
    [(0, "match n {"), (1, "case 1 {"), (2, "print(1)"), (1, "}"), (1, "case _ {"), (1, "}"), (0, "}")],
    [(0, "try {"), (1, "print(1)"), (0, "} catch e {"), (0, "}")],
    # Typed fields, one named like another field's type.
    [(0, "struct Pair {"), (1, "a: b,"), (1, "b: Int,"), (1, "c: List[b]"), (0, "}")],
    [(0, "class Box {"), (1, "size: Int,"), (1, "Int"), (0, "}")],
    # Braces inside strings and dict literals aren't blocks.
    [(0, 'print("a } b \\{ c")')],
    [(0, 'print("n is {n} }")')],
    [(0, 'let d = {"a": 1, "b": {"c": "}"}}')],
    [(0, "if true {"), (1, 'let e = {"k": "{n}"}'), (0, "}")],
]  # fmt: skip
# The lines of a fn value are printed as part of one line, so a comment
# written inside one moves to the end of that line: it's checked for
# turning up once, but not for staying standalone.
_FN_VALUE_START = "let f = fn(x) {"


@st.composite
def _programs_with_comments_everywhere(draw: st.DrawFn) -> tuple[str, list[str], list[str]]:
    """Invent a program with comments before lines, after code, and on closing braces.

    Return the program, the inline comments (written after code) and the
    standalone comments (alone on a line, outside fn values).
    """
    pieces = draw(st.lists(st.sampled_from(_PIECES), min_size=1, max_size=5))
    written: list[str] = []
    inline: list[str] = []
    standalone: list[str] = []
    for piece in pieces:
        is_fn_value = piece[0][1] == _FN_VALUE_START
        for index, (level, code) in enumerate(piece):
            inside_fn_value = is_fn_value and index > 0
            place = draw(st.sampled_from(["none", "before", "after", "both"]))
            number = len(inline) + len(standalone)
            if place in {"before", "both"}:
                comment = f"# s{number}"
                written.append("    " * level + comment)
                (inline if inside_fn_value else standalone).append(comment)
            line = "    " * level + code
            if place in {"after", "both"}:
                comment = f"# i{number}"
                line += f"  {comment}"
                inline.append(comment)
            written.append(line)
    if draw(st.booleans()):
        standalone.append("# the end")
        written.append("# the end")
    return "\n".join(written) + "\n", inline, standalone


@given(_programs_with_comments_everywhere())
def test_formatting_twice_is_formatting_once(case: tuple[str, list[str], list[str]]) -> None:
    """Formatting tidy, commented code keeps every comment once, in its place, and is idempotent."""
    source, inline, standalone = case
    formatted = format_source(source)
    assert format_source(formatted) == formatted, formatted
    check(formatted)
    lines = formatted.splitlines()
    for comment in inline + standalone:
        assert formatted.count(comment + "\n") + formatted.count(comment + "  ") == 1, (
            comment,
            formatted,
        )
    for comment in inline:
        assert not any(line.strip().split("  ")[0] == comment for line in lines), (
            comment,
            formatted,
        )
    for comment in standalone:
        assert any(line.strip() == comment for line in lines), (comment, formatted)
