"""Shared test fixtures for the Pebble test suite."""

from __future__ import annotations

from io import StringIO
from pathlib import Path  # noqa: TC003 — used at runtime by ModuleResolver

from pebble.analyzer import SemanticAnalyzer
from pebble.bytecode import CompiledProgram
from pebble.compiler import Compiler
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.resolver import ModuleResolver
from pebble.vm import VirtualMachine


def run_source(source: str) -> str:
    """Compile and run *source*, return captured output."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzer = SemanticAnalyzer()
    analyzed = analyzer.analyze(program)
    compiled = Compiler(
        cell_vars=analyzer.cell_vars,
        free_vars=analyzer.free_vars,
        enums=analyzer.enums,
    ).compile(analyzed)
    buf = StringIO()
    VirtualMachine(output=buf).run(compiled)
    return buf.getvalue()


def run_source_with_imports(source: str, *, base_dir: Path) -> str:
    """Compile and run *source* with module import support, return captured output."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzer = SemanticAnalyzer()
    resolver = ModuleResolver(base_dir=base_dir)
    resolver.resolve_imports(program, analyzer)
    analyzed = analyzer.analyze(program)
    compiled = Compiler(
        cell_vars=analyzer.cell_vars,
        free_vars=analyzer.free_vars,
        enums=analyzer.enums,
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
    full_program = CompiledProgram(
        main=compiled.main,
        functions=all_functions,
        structs=all_structs,
        struct_field_types=all_struct_field_types,
        class_methods=all_class_methods,
        enums=all_enums,
    )
    buf = StringIO()
    VirtualMachine(output=buf).run(full_program)
    return buf.getvalue()
