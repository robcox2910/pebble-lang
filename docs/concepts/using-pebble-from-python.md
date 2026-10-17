# Using Pebble from Python

## The Front Door

Pebble is a machine with lots of parts inside: a lexer, a parser, an
analyzer, a type checker, a compiler and a virtual machine. Each one has
its own page in these docs, and it's fun to open the case and see how
they fit together.

But when you just want to *run* a Pebble program from your own Python
code, you don't want to wire all those parts up yourself. You want a
front door with a big "go" button.

That's what Pebble's **public API** is: four functions you can import
straight from `pebble`.

| Function | What it does |
|---|---|
| `run_source` | Run a program and hand back everything it printed |
| `compile_source` | Check a program once, then run it as often as you like |
| `check` | Is this program well-formed? |
| `format_source` | Tidy a program into Pebble's one true style |

Every example on this page really runs: the test suite executes each one,
and each checks its own result with `assert`.

## Running a Program

`run_source` takes Pebble code as a string and gives back whatever the
program printed, as a string:

```python
from pebble import run_source

output = run_source('print("Hello from Pebble!")')
assert output == "Hello from Pebble!\n"
```

Notice the `\n` on the end: `print` finishes every line with a newline,
just like Python's does.

## Watching It Print

Sometimes you want to *see* the output as it happens, not just get it
back at the end. Pass any writable text stream as `output` and Pebble
copies everything there as it prints. `sys.stdout` shows it on screen;
here we use a `StringIO` so the example can check what arrived:

```python
import io

from pebble import run_source

screen = io.StringIO()
result = run_source("for i in range(3) {\n    print(i)\n}", output=screen)
assert screen.getvalue() == "0\n1\n2\n"
assert result == screen.getvalue()
```

## When Something Goes Wrong

If the program has a mistake in it, Pebble raises a `PebbleError`. Every
kind of Pebble mistake -- a typo the parser can't read, a type that
doesn't match, a crash while running -- is a kind of `PebbleError`, so one
`except` catches them all:

```python
from pebble import PebbleError, run_source

try:
    run_source('let age: Int = "twelve"')
except PebbleError as error:
    message = str(error)
else:
    message = "no error?!"

assert "expected Int" in message
```

The error knows *where* the mistake is, too: `error.line` and
`error.column` point at it.

## Checking and Tidying

You don't have to run a program to learn something about it. `check`
asks "is this well-formed?" and stays quiet if it is. `format_source`
gives back the program tidied into Pebble's one canonical style -- the
same thing `pebble fmt` does:

```python
from pebble import PebbleError, check, format_source

check("let x = 1")  # fine: no error

try:
    check("let = 1")
except PebbleError:
    looked_wrong = True
assert looked_wrong

assert format_source("let   x=1") == "let x = 1\n"
```

## Compile Once, Run Many Times

`run_source` does two jobs every time: it *checks and compiles* the
program, then *runs* it. If you'll run the same program again and again,
`compile_source` lets you do the first job once and keep the result:

```python
from pebble import compile_source

program = compile_source('print("tick")')
assert program.run() == "tick\n"
assert program.run() == "tick\n"
```

Mistakes are caught by `compile_source`, before anything runs.

## Giving Pebble Your Own Module

Here's the most powerful trick. Pebble programs can `import` modules like
`math`. You can write a brand-new module **in Python** and hand it to
Pebble for one run.

A module is a `StdlibModule`: a dictionary of functions (each with how
many arguments it takes) and a dictionary of constants. Each function
receives its arguments as a list of Pebble values and returns a Pebble
value:

```python
from pebble import StdlibModule, Value, run_source


def hello(args: list[Value]) -> Value:
    return f"Hello, {args[0]}!"


greet = StdlibModule(
    functions={"hello": (1, hello)},
    constants={"PLANET": "Earth"},
)

program = 'import "greet"\nprint(hello("Ada"))\nprint(PLANET)'
output = run_source(program, modules={"greet": greet})
assert output == "Hello, Ada!\nEarth\n"
```

The module only exists for *that* run. Another program, running at the
same moment with different modules, can't see `greet` at all -- every run
gets its own toolbox. That's exactly how
[PyStack](https://github.com/robcox2910/pystack) gives each Pebble
program its own database.

You can't reuse a built-in name, though. Asking for a module called
`math` raises a `ValueError` instead of quietly replacing the real one:

```python
from pebble import StdlibModule, run_source

fake_math = StdlibModule(functions={}, constants={})
try:
    run_source("print(1)", modules={"math": fake_math})
except ValueError as error:
    refused = "math" in str(error)
assert refused
```

## Importing Pebble Files

`import "helpers.pbl"` looks for files in the current folder. To look
somewhere else, pass `base_dir`:

```python
import tempfile
from pathlib import Path

from pebble import run_source

with tempfile.TemporaryDirectory() as folder:
    Path(folder, "helpers.pbl").write_text("fn double(n) {\n    return n * 2\n}\n")
    output = run_source('import "helpers.pbl"\nprint(double(21))', base_dir=Path(folder))

assert output == "42\n"
```

## What's Public?

Only the names you can import straight from `pebble` are **promised**:
`run_source`, `compile_source`, `check`, `format_source`, `Program`,
`StdlibModule`, `Value` and `PebbleError`. If a new version of Pebble
changes one of those, its version number says so (the middle number goes
up, like `0.2.0` to `0.3.0`).

Everything else -- `pebble.lexer`, `pebble.vm` and friends -- is still
there for you to explore and learn from, but it may change between
versions without warning.

## How It Works

Behind the front door, `run_source` runs the same pipeline the rest of
these docs describe, one stage after another:

1. The [lexer](lexer.md) chops the text into tokens.
2. The [parser](parser.md) builds a tree (the [AST](ast.md)).
3. The [analyzer](analyzer.md) checks names and scopes, and the
   [module system](modules.md) pulls in anything you `import`.
4. The [type checker](type-checker.md) checks that the types line up.
5. The [compiler](compiler.md) turns the tree into bytecode, and the
   [optimizer](optimizer.md) tidies it.
6. The [virtual machine](vm.md) runs the bytecode.

The front door just presses all six buttons for you, in order.
