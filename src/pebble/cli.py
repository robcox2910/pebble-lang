"""Command-line interface for the Pebble compiler and VM.

Run a ``.pbl`` file through the full pipeline::

    pebble examples/hello.pbl

"""

from __future__ import annotations

import sys
from pathlib import Path

from pebble.analyzer import SemanticAnalyzer
from pebble.compiler import Compiler
from pebble.errors import PebbleError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.vm import VirtualMachine


def main() -> None:
    """Entry point for the ``pebble`` command."""
    if len(sys.argv) < 2:  # noqa: PLR2004
        print("Usage: pebble <file.pbl>", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    path = Path(sys.argv[1])
    try:
        source = path.read_text()
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzed = SemanticAnalyzer().analyze(program)
        compiled = Compiler().compile(analyzed)
        VirtualMachine().run(compiled)
    except PebbleError as exc:
        print(f"Error: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(1)
