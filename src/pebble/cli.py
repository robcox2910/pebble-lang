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
from pebble.repl import repl
from pebble.resolver import ModuleResolver
from pebble.vm import VirtualMachine

_MIN_FILE_ARGS = 2


def main() -> None:
    """Entry point for the ``pebble`` command."""
    if len(sys.argv) < _MIN_FILE_ARGS:
        repl()
        return

    path = Path(sys.argv[1])
    try:
        source = path.read_text()
    except FileNotFoundError:
        sys.stderr.write(f"Error: file not found: {path}\n")
        sys.exit(1)
    except OSError as exc:
        sys.stderr.write(f"Error: cannot read file: {exc}\n")
        sys.exit(1)
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
            variable_arity_functions=resolver.variable_arity_functions,
        ).compile(analyzed)
        all_functions = {**resolver.merged_functions, **compiled.functions}
        all_structs = {**resolver.merged_structs, **compiled.structs}
        all_struct_field_types = {
            **resolver.merged_struct_field_types,
            **compiled.struct_field_types,
        }
        all_class_methods = {
            **resolver.merged_class_methods,
            **compiled.class_methods,
        }
        all_enums = {**resolver.merged_enums, **compiled.enums}
        all_class_parents = {**resolver.merged_class_parents, **compiled.class_parents}
        full_program = CompiledProgram(
            main=compiled.main,
            functions=all_functions,
            structs=all_structs,
            struct_field_types=all_struct_field_types,
            class_methods=all_class_methods,
            enums=all_enums,
            class_parents=all_class_parents,
        )
        VirtualMachine().run(
            full_program,
            stdlib_handlers=resolver.merged_stdlib_handlers,
            stdlib_constants=resolver.merged_stdlib_constants,
        )
    except PebbleError as exc:
        if exc.line > 0:
            formatted = format_error(source, line=exc.line, column=exc.column, message=exc.message)
            sys.stderr.write(formatted + "\n")
        else:
            sys.stderr.write(f"Error: {exc}\n")
        sys.exit(1)
