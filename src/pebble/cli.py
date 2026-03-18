"""Command-line interface for the Pebble compiler and VM.

Run a ``.pbl`` file through the full pipeline::

    pebble examples/hello.pbl

Start the debugger::

    pebble --debug examples/hello.pbl

"""

import argparse
import sys
from pathlib import Path

from pebble.analyzer import SemanticAnalyzer
from pebble.bytecode import CompiledProgram
from pebble.compiler import Compiler
from pebble.debugger import Debugger
from pebble.errors import PebbleError, PebbleRuntimeError, format_error, format_traceback
from pebble.lexer import Lexer
from pebble.optimizer import optimize
from pebble.parser import Parser
from pebble.repl import repl
from pebble.resolver import ModuleResolver
from pebble.type_checker import type_check
from pebble.vm import DebugHook, VirtualMachine


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments from *argv*."""
    parser = argparse.ArgumentParser(prog="pebble", description="Pebble language interpreter")
    parser.add_argument("file", nargs="?", default=None, help="Source file to run (.pbl)")
    parser.add_argument("--debug", action="store_true", help="Start the interactive debugger")
    return parser.parse_args(argv)


def main() -> None:
    """Entry point for the ``pebble`` command."""
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
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        resolver = ModuleResolver(base_dir=path.parent.resolve())
        resolver.resolve_imports(program, analyzer)
        analyzed = analyzer.analyze(program)
        type_check(analyzed, analyzer=analyzer)
        compiled = Compiler(
            cell_vars=analyzer.cell_vars,
            free_vars=analyzer.free_vars,
            enums=resolver.merged_enums,
            class_parents=resolver.merged_class_parents,
            structs=resolver.merged_structs,
            class_methods=resolver.merged_class_methods,
            functions=resolver.merged_functions,
            variable_arity_functions=resolver.variable_arity_functions,
        ).compile(analyzed)
        compiled = optimize(compiled)
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
            debug_hook=debug_hook,
        )
    except PebbleError as exc:
        if isinstance(exc, PebbleRuntimeError) and exc.traceback:
            sys.stderr.write(format_traceback(exc) + "\n")
        elif exc.line > 0:
            formatted = format_error(source, line=exc.line, column=exc.column, message=exc.message)
            sys.stderr.write(formatted + "\n")
        else:
            sys.stderr.write(f"Error: {exc}\n")
        sys.exit(1)
