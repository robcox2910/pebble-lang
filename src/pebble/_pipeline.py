"""The one place Pebble's pieces are wired together into a runnable program.

Private: use :mod:`pebble.api` instead. The ``pebble`` command and the
public API both build programs here, so the wiring is written once.
"""

import io
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, override

from pebble.analyzer import SemanticAnalyzer
from pebble.builtins import Value
from pebble.bytecode import CompiledProgram
from pebble.compiler import Compiler
from pebble.lexer import Lexer
from pebble.optimizer import optimize
from pebble.parser import Parser
from pebble.resolver import ModuleResolver
from pebble.stdlib import StdlibHandler, StdlibModule
from pebble.type_checker import type_check
from pebble.vm import DebugHook, VirtualMachine

type StdlibHandlers = dict[str, tuple[int | tuple[int, ...], StdlibHandler]]


class _Capture(io.StringIO):
    """Collect everything a program prints, copying it to *echo* as it goes."""

    def __init__(self, echo: TextIO | None) -> None:
        super().__init__()
        self._echo = echo

    @override
    def write(self, s: str, /) -> int:
        if self._echo is not None:
            self._echo.write(s)
        return super().write(s)

    @override
    def flush(self) -> None:
        if self._echo is not None:
            self._echo.flush()


@dataclass(frozen=True)
class Program:
    """A checked, compiled Pebble program, ready to run as many times as you like.

    Make one with :func:`pebble.compile_source`. It remembers its own
    modules, so running it never looks anything up in a shared table.
    Its attributes are Pebble internals and may change between versions;
    :meth:`run` is the promised way to use it.
    """

    compiled: CompiledProgram
    stdlib_handlers: StdlibHandlers
    stdlib_constants: dict[str, Value]

    def run(self, output: TextIO | None = None) -> str:
        """Run the program and return everything it printed.

        Args:
            output: Also write the printed text here as it happens
                (for example ``sys.stdout``). Optional.

        Returns:
            Everything the program printed.

        Raises:
            PebbleRuntimeError: If the program fails while running.

        """
        return run_program(self, output)


def run_program(
    program: Program, output: TextIO | None, debug_hook: DebugHook | None = None
) -> str:
    """Run *program*, optionally with a debugger attached (used by ``pebble --debug``)."""
    capture = _Capture(output)
    VirtualMachine(output=capture).run(
        program.compiled,
        stdlib_handlers=program.stdlib_handlers,
        stdlib_constants=program.stdlib_constants,
        debug_hook=debug_hook,
    )
    return capture.getvalue()


def compile_program(source: str, *, modules: Mapping[str, StdlibModule], base_dir: Path) -> Program:
    """Lex, parse, analyze, type-check, compile and optimize *source*.

    Args:
        source: The Pebble program.
        modules: Every importable module by name (built-ins included).
        base_dir: Where ``import "file.pbl"`` looks for files.

    Returns:
        The runnable program.

    """
    program = Parser(Lexer(source).tokenize()).parse()
    analyzer = SemanticAnalyzer()
    resolver = ModuleResolver(base_dir=base_dir, modules=modules)
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
    full_program = CompiledProgram(
        main=compiled.main,
        functions={**resolver.merged_functions, **compiled.functions},
        structs={**resolver.merged_structs, **compiled.structs},
        struct_field_types={
            **resolver.merged_struct_field_types,
            **compiled.struct_field_types,
        },
        class_methods={**resolver.merged_class_methods, **compiled.class_methods},
        enums={**resolver.merged_enums, **compiled.enums},
        class_parents={**resolver.merged_class_parents, **compiled.class_parents},
    )
    return Program(
        full_program,
        dict(resolver.merged_stdlib_handlers),
        dict(resolver.merged_stdlib_constants),
    )
