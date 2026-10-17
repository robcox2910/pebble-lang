"""Command-line interface for the Pebble compiler and VM.

Run a ``.pbl`` file through the full pipeline::

    pebble examples/hello.pbl

Start the debugger::

    pebble --debug examples/hello.pbl

Format a ``.pbl`` file in place::

    pebble fmt file.pbl

Check formatting without modifying::

    pebble fmt --check file.pbl

Lint a ``.pbl`` file for style issues::

    pebble lint file.pbl

"""

import argparse
import sys
from pathlib import Path

from pebble._pipeline import compile_program, run_program
from pebble.debugger import Debugger
from pebble.errors import PebbleError, PebbleRuntimeError, format_error, format_traceback
from pebble.formatter import Formatter
from pebble.lexer import Lexer
from pebble.linter import Linter
from pebble.parser import Parser
from pebble.repl import repl
from pebble.stdlib import STDLIB_MODULES
from pebble.vm import DebugHook


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments from *argv*."""
    parser = argparse.ArgumentParser(prog="pebble", description="Pebble language interpreter")
    parser.add_argument("file", nargs="?", default=None, help="Source file to run (.pbl)")
    parser.add_argument("--debug", action="store_true", help="Start the interactive debugger")
    return parser.parse_args(argv)


def _run_fmt(argv: list[str]) -> None:
    """Run the ``pebble fmt`` subcommand."""
    check_mode = "--check" in argv
    files = [a for a in argv if a != "--check"]

    if not files:
        sys.stderr.write("Usage: pebble fmt [--check] <file.pbl>\n")
        sys.exit(1)

    path = Path(files[0])
    try:
        source = path.read_text()
    except FileNotFoundError:
        sys.stderr.write(f"Error: file not found: {path}\n")
        sys.exit(1)
    except OSError as exc:
        sys.stderr.write(f"Error: cannot read file: {exc}\n")
        sys.exit(1)

    formatted = Formatter(source).format()

    # ``fmt`` overwrites your file, so it must never save broken code. Parse
    # the tidied result first; if that fails, keep the original untouched.
    try:
        Parser(Lexer(formatted).tokenize()).parse()
    except PebbleError as exc:
        sys.stderr.write(
            f"{path}: formatter produced code that does not parse ({exc}); "
            "refusing to write. Please report this bug.\n"
        )
        sys.exit(1)

    if check_mode:
        if source != formatted:
            sys.stderr.write(f"{path}: not formatted\n")
            sys.exit(1)
        return

    path.write_text(formatted)


def _run_lint(argv: list[str]) -> None:
    """Run the ``pebble lint`` subcommand."""
    if not argv:
        sys.stderr.write("Usage: pebble lint <file.pbl>\n")
        sys.exit(1)

    path = Path(argv[0])
    try:
        source = path.read_text()
    except FileNotFoundError:
        sys.stderr.write(f"Error: file not found: {path}\n")
        sys.exit(1)
    except OSError as exc:
        sys.stderr.write(f"Error: cannot read file: {exc}\n")
        sys.exit(1)

    warnings = Linter(source).lint()
    for w in warnings:
        sys.stdout.write(f"{path}:{w.line}:{w.column}: {w.code} {w.message}\n")
    if warnings:
        sys.exit(1)


def main() -> None:
    """Entry point for the ``pebble`` command."""
    # Detect subcommands before argparse for backward compatibility
    if len(sys.argv) > 1 and sys.argv[1] == "fmt":
        _run_fmt(sys.argv[2:])
        return
    if len(sys.argv) > 1 and sys.argv[1] == "lint":
        _run_lint(sys.argv[2:])
        return

    args = _parse_args(sys.argv[1:])

    if args.file is None:
        repl()
        return

    path = Path(args.file)
    try:
        source = path.read_text()
    except FileNotFoundError:
        sys.stderr.write(f"Error: file not found: {path}\n")
        sys.exit(1)
    except OSError as exc:
        sys.stderr.write(f"Error: cannot read file: {exc}\n")
        sys.exit(1)

    debug_hook: DebugHook | None = None
    if args.debug:
        debug_hook = Debugger(source=source, output=sys.stdout, input_stream=sys.stdin)

    try:
        program = compile_program(source, modules=STDLIB_MODULES, base_dir=path.parent.resolve())
        run_program(program, sys.stdout, debug_hook=debug_hook)
    except PebbleError as exc:
        if isinstance(exc, PebbleRuntimeError) and exc.traceback:
            sys.stderr.write(format_traceback(exc) + "\n")
        elif exc.line > 0:
            formatted = format_error(source, line=exc.line, column=exc.column, message=exc.message)
            sys.stderr.write(formatted + "\n")
        else:
            sys.stderr.write(f"Error: {exc}\n")
        sys.exit(1)
