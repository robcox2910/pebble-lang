"""Interactive REPL for the Pebble language.

Start a read-eval-print loop that compiles and executes each input line
immediately, persisting variables and function definitions between inputs.

Usage::

    pebble          # starts the REPL
    pebble> let x = 42
    pebble> print(x + 1)
    43

"""

import sys
from pathlib import Path
from typing import TextIO

from pebble.analyzer import SemanticAnalyzer
from pebble.builtins import Value
from pebble.bytecode import CodeObject, CompiledProgram
from pebble.compiler import Compiler
from pebble.errors import PebbleError
from pebble.lexer import Lexer
from pebble.optimizer import optimize
from pebble.parser import Parser
from pebble.resolver import ModuleResolver
from pebble.stdlib import StdlibHandler
from pebble.type_checker import type_check
from pebble.vm import VirtualMachine

_PROMPT = "pebble> "
_CONTINUATION = "... "


class Repl:
    """Maintain persistent state across REPL evaluations.

    Each call to :meth:`eval_line` compiles and executes one input,
    carrying forward variables, functions, and analyzer scope.

    Args:
        output: Writable text stream for ``print`` output (default ``sys.stdout``).

    """

    def __init__(self, output: TextIO | None = None) -> None:
        """Create a REPL with empty state."""
        self._analyzer = SemanticAnalyzer()
        self._variables: dict[str, Value] = {}
        self._functions: dict[str, CodeObject] = {}
        self._structs: dict[str, list[str]] = {}
        self._struct_field_types: dict[str, dict[str, str]] = {}
        self._class_methods: dict[str, list[str]] = {}
        self._class_parents: dict[str, str] = {}
        self._enums: dict[str, list[str]] = {}
        self._stdlib_handlers: dict[str, tuple[int | tuple[int, ...], StdlibHandler]] = {}
        self._stdlib_constants: dict[str, Value] = {}
        self._variable_arity_functions: dict[str, int] = {}
        self._output: TextIO = output or sys.stdout

    def eval_line(self, source: str) -> None:
        """Evaluate a single REPL input.

        Raises :class:`~pebble.errors.PebbleError` on syntax, semantic,
        or runtime errors.  On error the persistent state is **not** updated.
        """
        if not source.strip():
            return

        self._analyzer.reset_import_barrier()
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()

        resolver = ModuleResolver(base_dir=Path.cwd())
        resolver.resolve_imports(program, self._analyzer)

        analyzed = self._analyzer.analyze(program)
        type_check(analyzed, analyzer=self._analyzer)

        # Merge variable-arity functions for compiler padding
        all_var_arity = {
            **self._variable_arity_functions,
            **resolver.variable_arity_functions,
        }
        compiled = Compiler(
            cell_vars=self._analyzer.cell_vars,
            free_vars=self._analyzer.free_vars,
            enums=self._enums,
            class_parents=self._class_parents,
            structs=self._structs,
            class_methods=self._class_methods,
            functions=self._functions,
            variable_arity_functions=all_var_arity,
        ).compile(analyzed)
        compiled = optimize(compiled)

        # Merge new functions and structs with previously-defined ones
        all_functions = self._functions | resolver.merged_functions | compiled.functions
        all_structs = self._structs | resolver.merged_structs | compiled.structs
        all_struct_field_types = (
            self._struct_field_types
            | resolver.merged_struct_field_types
            | compiled.struct_field_types
        )
        all_class_methods = (
            self._class_methods | resolver.merged_class_methods | compiled.class_methods
        )
        all_enums = self._enums | resolver.merged_enums | compiled.enums
        all_class_parents = (
            self._class_parents | resolver.merged_class_parents | compiled.class_parents
        )
        full_program = CompiledProgram(
            main=compiled.main,
            functions=all_functions,
            structs=all_structs,
            struct_field_types=all_struct_field_types,
            class_methods=all_class_methods,
            enums=all_enums,
            class_parents=all_class_parents,
        )

        # Merge stdlib handlers from this eval round
        all_stdlib_handlers = self._stdlib_handlers | resolver.merged_stdlib_handlers
        all_stdlib_constants = self._stdlib_constants | resolver.merged_stdlib_constants

        vm = VirtualMachine(output=self._output)
        new_vars = vm.run_repl(
            full_program,
            self._variables,
            stdlib_handlers=all_stdlib_handlers,
            stdlib_constants=all_stdlib_constants,
        )

        # Success — persist state
        self._variables = new_vars
        self._functions.update(resolver.merged_functions)
        self._functions.update(compiled.functions)
        self._structs.update(resolver.merged_structs)
        self._structs.update(compiled.structs)
        self._struct_field_types.update(resolver.merged_struct_field_types)
        self._struct_field_types.update(compiled.struct_field_types)
        self._class_methods.update(resolver.merged_class_methods)
        self._class_methods.update(compiled.class_methods)
        self._class_parents.update(resolver.merged_class_parents)
        self._class_parents.update(compiled.class_parents)
        self._enums.update(resolver.merged_enums)
        self._enums.update(compiled.enums)
        self._stdlib_handlers.update(resolver.merged_stdlib_handlers)
        self._stdlib_constants.update(resolver.merged_stdlib_constants)
        self._variable_arity_functions.update(resolver.variable_arity_functions)


# -- Input handling -----------------------------------------------------------


def read_input(prompt: str) -> str | None:
    """Read a possibly multi-line input from the user.

    If the first line has unbalanced ``{`` braces, keep reading
    continuation lines until they balance.  Return ``None`` on EOF.
    """
    try:
        line = input(prompt)
    except EOFError:
        return None

    depth = line.count("{") - line.count("}")
    while depth > 0:
        try:
            continuation = input(_CONTINUATION)
        except EOFError:
            break
        line += "\n" + continuation
        depth += continuation.count("{") - continuation.count("}")

    return line


# -- Main REPL loop ----------------------------------------------------------


def repl(output: TextIO | None = None) -> None:
    """Run the interactive REPL until EOF (Ctrl-D).

    Args:
        output: Writable text stream for program output (default ``sys.stdout``).

    """
    out = output or sys.stdout
    r = Repl(output=out)

    while True:
        source = read_input(_PROMPT)
        if source is None:
            print(file=out)
            break
        if not source.strip():
            continue
        try:
            r.eval_line(source)
        except PebbleError as exc:
            sys.stderr.write(f"Error: {exc.message}\n")
