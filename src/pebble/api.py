"""Pebble's front door: run Pebble programs from your own Python code.

Think of Pebble as a machine with lots of parts inside -- a lexer, a
parser, an analyzer, a compiler, a virtual machine. You *can* open the
case and wire the parts together yourself, but most of the time you just
want to press "go". These four functions are the buttons on the front:

- :func:`run_source` -- run a program and get back what it printed.
- :func:`compile_source` -- check a program once, run it many times.
- :func:`check` -- does this even parse?
- :func:`format_source` -- tidy a program into Pebble's one true style.

Only the names exported from :mod:`pebble` are promised to stay the same
between versions. Everything else inside Pebble may change.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import TextIO

from pebble._pipeline import Program, compile_program
from pebble.formatter import Formatter
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.stdlib import STDLIB_MODULES, StdlibModule


def check(source: str) -> None:
    """Check that *source* is a well-formed Pebble program (it lexes and parses).

    Args:
        source: The Pebble program.

    Raises:
        PebbleError: If the program isn't well-formed.

    """
    Parser(Lexer(source).tokenize()).parse()


def format_source(source: str) -> str:
    """Return *source* tidied into Pebble's one canonical formatting.

    Args:
        source: The Pebble program.

    Returns:
        The formatted program.

    Raises:
        PebbleError: If the program isn't well-formed.

    """
    check(source)
    return Formatter(source).format()


def compile_source(
    source: str,
    *,
    modules: Mapping[str, StdlibModule] | None = None,
    base_dir: Path | None = None,
) -> Program:
    """Check and compile *source* into a :class:`Program` you can run.

    Args:
        source: The Pebble program.
        modules: Extra modules the program may ``import``, by name, for
            this program only. They sit alongside the built-in ones.
        base_dir: Where ``import "file.pbl"`` looks (default: the current
            folder).

    Returns:
        The runnable program.

    Raises:
        PebbleError: If the program has a mistake in it.
        ValueError: If an extra module has the same name as a built-in one.

    """
    return compile_program(
        source,
        modules=_module_table(modules or {}),
        base_dir=Path.cwd() if base_dir is None else base_dir,
    )


def run_source(
    source: str,
    *,
    modules: Mapping[str, StdlibModule] | None = None,
    base_dir: Path | None = None,
    output: TextIO | None = None,
) -> str:
    """Compile and run *source*, returning everything it printed.

    Args:
        source: The Pebble program.
        modules: Extra modules the program may ``import`` (see
            :func:`compile_source`).
        base_dir: Where ``import "file.pbl"`` looks (default: the current
            folder).
        output: Also write the printed text here as it happens. Optional.

    Returns:
        Everything the program printed.

    Raises:
        PebbleError: If the program has a mistake or fails while running.
        ValueError: If an extra module has the same name as a built-in one.

    """
    return compile_source(source, modules=modules, base_dir=base_dir).run(output)


def _module_table(extra: Mapping[str, StdlibModule]) -> dict[str, StdlibModule]:
    """Return the built-in modules plus *extra*, refusing to replace a built-in."""
    for name in extra:
        if name in STDLIB_MODULES:
            msg = f"module name {name!r} is already a built-in"
            raise ValueError(msg)
    return {**STDLIB_MODULES, **extra}
