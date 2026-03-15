"""Command-line interface for the Pebble compiler and VM.

Run a ``.pbl`` file through the full pipeline::

    pebble examples/hello.pbl

"""

from __future__ import annotations

import sys
from pathlib import Path

from pebble.analyzer import SemanticAnalyzer
from pebble.bytecode import CompiledProgram
from pebble.compiler import Compiler
from pebble.errors import PebbleError, format_error
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.resolver import ModuleResolver
from pebble.vm import VirtualMachine


def main() -> None:
    """Entry point for the ``pebble`` command."""
    if len(sys.argv) < 2:  # noqa: PLR2004
        from pebble.repl import repl  # noqa: PLC0415

        repl()
        return

    path = Path(sys.argv[1])
    source = path.read_text()
    try:
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        resolver = ModuleResolver(base_dir=path.parent.resolve())
        resolver.resolve_imports(program, analyzer)
        analyzed = analyzer.analyze(program)
        compiled = Compiler(
            cell_vars=analyzer.cell_vars,
            free_vars=analyzer.free_vars,
        ).compile(analyzed)
        all_functions = {**resolver.merged_functions, **compiled.functions}
        all_structs = {**resolver.merged_structs, **compiled.structs}
        all_struct_field_types = {
            **resolver.merged_struct_field_types,
            **compiled.struct_field_types,
        }
        full_program = CompiledProgram(
            main=compiled.main,
            functions=all_functions,
            structs=all_structs,
            struct_field_types=all_struct_field_types,
        )
        VirtualMachine().run(full_program)
    except PebbleError as exc:
        if exc.line > 0:
            formatted = format_error(source, line=exc.line, column=exc.column, message=exc.message)
            print(formatted, file=sys.stderr)  # noqa: T201
        else:
            print(f"Error: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(1)
