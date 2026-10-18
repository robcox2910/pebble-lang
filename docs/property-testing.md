# Property Testing (A Monkey at the Typewriter)

## The Typing Monkey

Pebble is a translator: it reads what you type and turns it into steps
the virtual machine can follow. How would you check a translator works?

The usual way: type one program, `print(1 + 2)`, run it, see `3`, and
smile. That's an **example test**. It's useful, but it only tells you
about the one program you thought of.

Now imagine a monkey at a typewriter. It bashes out thousands of things --
random letters, emoji, half a keyword, five thousand open brackets, and
now and then a small, sensible program -- and hands every one to Pebble.
For each one it checks a single rule:

> Whatever I type, Pebble either understands it or tells me politely
> what's wrong. It never falls over.

That rule is a **property**. It doesn't say what any one program should
do. It says something that must be true for *everything* the monkey
types.

When the monkey finds something that breaks the rule, it doesn't hand
you three pages of gibberish. It tries again with less and less, checking
it still breaks each time, until what's left is as small as it can be.
That boiling-down is called **shrinking**, and it's the best part: the
smallest failing input usually points straight at the bug.

In Python, the typing monkey is a library called
[Hypothesis](https://hypothesis.readthedocs.io/). Pebble's property tests
live in `tests/test_properties.py`, next to the ordinary example tests.

## A Property from Pebble

[`check`](concepts/using-pebble-from-python.md) is the button on Pebble's
front panel that asks "is this a well-formed program?" It promises to
answer by returning (yes) or raising a `PebbleError` (no, and here's
where). Here's the property that holds it to that promise:

```python
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


# What a tower starts with, and the piece it stacks: "List[" only nests
# inside a type annotation, and "else if" only follows an "if".
TOWER_PIECES = [
    ("", "("), ("", "["), ("", "{"), ("", "-"), ("", "not "), ("", "~"),
    ("", "0"), ("", "9"), ("", "if x { "),
    ("let x: ", "List["), ("if x {}", " else if x {}"),
]  # fmt: skip


@st.composite
def towers(draw: st.DrawFn) -> str:
    """Make one piece stacked up to 5,000 times, like 5,000 open brackets."""
    start, piece = draw(st.sampled_from(TOWER_PIECES))
    times = draw(st.integers(min_value=0, max_value=LONGEST_REPEAT))
    return start + piece * times


def scraps_of_text() -> st.SearchStrategy[str]:
    """Make text that might be Pebble: random characters, a jumble, or a tall tower."""
    return st.one_of(any_text(), pebble_soup(), towers())


@given(text=scraps_of_text())
def test_check_only_ever_raises_pebble_error(text: str) -> None:
    """Whatever text you hand to ``check``, it either accepts it or raises a PebbleError."""
    with suppress(PebbleError):
        check(text)
```

Line by line:

- **The functions at the top** are **strategies**: recipes for making
  random inputs, each named for what it makes.
- **`any_text()`** is the monkey hitting any keys at all.
- **`pebble_soup()`** is the monkey that has learnt some Pebble. It glues
  real pieces together (`let`, `{`, `"`...), so the parser gets past the
  first character and has real work to do.
- **`towers()`** stacks one piece up to 5,000 times: an opener, a digit,
  `List[` after `let x: `, or `else if x {}` after `if x {}`. Very deep or
  very long input is where hand-written code most often gives up.
- **`@st.composite`** lets a strategy `draw` from other strategies, one
  step at a time, and then build its answer from what it drew.
- **`st.one_of(...)`** picks one of the three recipes each time.
- **`@given(text=scraps_of_text())`** tells Hypothesis to run the test
  many times (100 in a normal run), each time with a fresh `text`.
- **`with suppress(PebbleError):`** is the rule itself. A `PebbleError` is
  a polite "no", so we let it go. *Any other* exception escapes and fails
  the test.

Notice what the test *doesn't* say. It never says which texts are
valid Pebble, or what the error message should be. It doesn't need to
know any answers. It only needs a rule that's always true.

There's a catch, though. **A do-nothing `check` that accepts everything
passes this property**, and a do-nothing formatter that hands your
program back untouched passes the formatter's round-trip tests. That's
why the formatter also gets a rule that only real tidying can pass.

| Rule | Test |
|---|---|
| A program prints exactly the same thing, errors included, with or without the [optimizer](concepts/optimizer.md) | `test_optimiser_never_changes_what_a_program_prints` |
| However oddly a program is spaced, the [formatter](concepts/formatter.md) turns it into the same tidy text | `test_formatting_ignores_how_a_program_was_spaced` |
| Any program we can parse still parses, and means the same, after formatting (in `tests/test_format_roundtrip.py`) | `test_random_programs_survive_formatting` |
| Every comment appears exactly once after formatting (in `tests/test_format_roundtrip.py`) | `test_comments_survive_formatting_once_each` |

The optimiser one is a **reference check**: Pebble with the optimiser
switched off is the "right answer", and Pebble with it switched on must
agree. The optimiser is only allowed to make programs faster, never
different.

## Try It Yourself

Let's break the optimiser on purpose and watch the typing monkey find it.

Open `src/pebble/optimizer.py` and change the line that folds `*`, as if
someone had decided every product should be a decimal:

```python
    OpCode.MULTIPLY: ((int, float), (int, float), lambda a, b: float(a * b)),  # was: operator.mul
```

Run the property tests:

```bash
uv run pytest tests/test_properties.py --no-cov
```

Hypothesis reports this (trimmed to the interesting part):

```
source = 'print ( ( 0 * 0 ) )'

    @given(source=tidy_programs())
    def test_optimiser_never_changes_what_a_program_prints(source: str) -> None:
        """A program prints exactly the same thing, errors included, with or without the optimiser."""
        plain = what_it_prints(compile_source, source)
        optimised = what_it_prints(compile_source_optimized, source)
>       assert optimised == plain
E       AssertionError: assert '0.0\n' == '0\n'
E
E         - 0
E         + 0.0
E       Failing test case: test_optimiser_never_changes_what_a_program_prints(
E           source='print ( ( 0 * 0 ) )',
E       )
```

Look at how small that is. Hypothesis made programs with `let`s, `if`s
and long sums, then shrank the failure all the way down to **one line,
`print((0 * 0))`**. (The test writes one space between every token, which
is why it looks stretched out.) Without the optimiser, Pebble prints `0`.
With it, `0 * 0` is worked out before the program runs, comes out as
`0.0`, and that's what gets printed.

The optimiser property catches it. The check and formatter properties
stay green, because neither of them runs a program.

The example tests all still pass. Only the property notices. The
optimiser's own tests check that `3 * 4` folds to `12`, and in Python
`12 == 12.0`, so they can't see the difference. The property compares
what actually gets *printed*, and `"0"` is not `"0.0"`.

Now put the line back to `operator.mul` and run the tests again. They
pass.

!!! tip "Older Hypothesis versions"
    Older versions of Hypothesis print `Falsifying example:` instead of
    `Failing test case:`. It means the same thing.

## A Bug We Found

When we first ran the `check` property the long way, it failed on
Pebble's real code -- no deliberate bug needed:

```
E   RecursionError: maximum recursion depth exceeded
E   Failing test case: test_check_only_ever_raises_pebble_error(
E       text='(' * 1111,
E   )
```

(Shortened: Hypothesis prints all 1,111 brackets.)

1,111 open brackets, and `check` didn't say "that's not a program". It
crashed with a Python error instead.

Here's why. The parser reads `(` by calling itself to read what's
inside, which meets another `(` and calls itself again. Python only lets
functions call each other about 1,000 deep, so somewhere in the tower it
gave up. No example test nested more than a few brackets. Nobody thinks
to type 1,111.

The fix gives the parser a counter. Every bracket, operator and block
goes one level deeper, and at about 100 levels it raises a polite
`ParseError` instead:

```python
        if self._depth >= MAX_NESTING:  # was: (no limit at all)
            self._error(NESTED_TOO_DEEPLY)
```

The shrunk input became an example test in
`tests/test_parser_expressions.py`, so it can never sneak back:

```python
    @pytest.mark.parametrize("opener", ["(", "[", "-", "not ", "2 ** ", "if true { "])
    def test_too_deep_nesting_raises_parse_error(self, opener: str) -> None:
        """Regression (found by a property test): ``"(" * 1111`` used to crash with RecursionError."""
        with pytest.raises(ParseError, match="nested too deeply"):
            check(opener * 1111)
```

It wasn't the only one. The properties found five more real bugs, and
reading the code while fixing them turned up the rest. Each now has its
own example test:

| Input | What went wrong | Found by |
|---|---|---|
| `"0" * 4301` | `check` crashed: Python won't read a number that long | property |
| `print(0 ** -1)` | the optimiser crashed, and so did the VM | property |
| `print(0 < true)` | printed `true` with the optimiser, an error without | property |
| `print(-(0.0))` | printed `0.0` with the optimiser, `-0.0` without | property |
| `print(-(1 or 0))` | printed `0` with the optimiser, `-1` without | property |
| `print(10.0 ** 400)` | the optimiser crashed, and so did the VM | reading the code |
| `²` | `check` crashed: Python calls `²` a digit, but can't read it as a number | reading the code |
| 1,111 `else if`s | `check` crashed on a perfectly good program | reading the code |
| `let x: List[List[...` | `check` crashed on 1,111 `List[`s | reading the code |

The last two now have towers of their own in `towers()`, so the
property keeps watching them.

## Run It Yourself

Run just the property tests (100 examples each, the same every time):

```bash
uv run pytest tests/test_properties.py --no-cov
```

The `--no-cov` turns off the coverage check, which expects the *whole*
test suite to run and would fail on one file.

Run them the long way (2,000 random examples each, different every run)
to hunt for rarer bugs. It takes a minute or two:

```bash
uv run pytest tests/test_properties.py --no-cov --hypothesis-profile=thorough
```

The normal run uses a fixed seed, so it tries the same inputs every time
and a passing build means the same thing on every computer. The thorough
run is random, so each time you run it the monkey types brand-new
nonsense. Both settings live in `conftest.py` at the top of the project.

## Your Turn

A compiled `Program` promises you can run it as many times as you like.
Write a property for that: "compile once, run twice, and it prints the
same thing both times". What's the strategy? (`tidy_programs()` is
already in the file.) What's the `assert`? Some programs won't compile,
or stop with an error: what should happen then?

Then break `run_program` on purpose, say by sharing one `_Capture`
between runs, and see what Hypothesis shrinks it to.
