"""Shared test fixtures for the Pebble test suite."""

from io import StringIO
from pathlib import Path
from typing import TextIO

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import Program
from pebble.bytecode import CompiledProgram, Instruction, OpCode
from pebble.compiler import Compiler
from pebble.debugger import Debugger
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.resolver import ModuleResolver
from pebble.vm import VirtualMachine


def analyze(source: str) -> Program:
    """Lex, parse, and analyze *source*, returning the analyzed program."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    return SemanticAnalyzer().analyze(program)


def analyze_with_context(source: str) -> tuple[Program, SemanticAnalyzer]:
    """Lex, parse, and analyze *source*, returning program and analyzer."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzer = SemanticAnalyzer()
    analyzed = analyzer.analyze(program)
    return analyzed, analyzer


def compile_source(source: str) -> CompiledProgram:
    """Full pipeline: lex, parse, analyze, compile."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzer = SemanticAnalyzer()
    analyzed = analyzer.analyze(program)
    return Compiler(
        cell_vars=analyzer.cell_vars,
        free_vars=analyzer.free_vars,
        enums=analyzer.enums,
        class_parents=analyzer.class_parents,
    ).compile(analyzed)


def compile_instructions(source: str) -> list[Instruction]:
    """Compile *source* and return the main code object's instructions."""
    return compile_source(source).main.instructions


def compile_opcodes(source: str) -> list[OpCode]:
    """Compile *source* and return just the opcode sequence."""
    return [i.opcode for i in compile_instructions(source)]


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
        class_parents=analyzer.class_parents,
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
        class_parents=analyzer.class_parents,
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
    buf = StringIO()
    VirtualMachine(output=buf).run(full_program)
    return buf.getvalue()


def run_source_with_stdlib(
    source: str,
    *,
    input_stream: TextIO | None = None,
    base_dir: Path | None = None,
) -> str:
    """Compile and run *source* with stdlib import support, return captured output."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzer = SemanticAnalyzer()
    resolver = ModuleResolver(base_dir=base_dir or Path.cwd())
    resolver.resolve_imports(program, analyzer)
    analyzed = analyzer.analyze(program)
    compiled = Compiler(
        cell_vars=analyzer.cell_vars,
        free_vars=analyzer.free_vars,
        enums=analyzer.enums,
        class_parents=analyzer.class_parents,
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
    buf = StringIO()
    vm = VirtualMachine(output=buf, input_stream=input_stream)
    vm.run(
        full_program,
        stdlib_handlers=resolver.merged_stdlib_handlers,
        stdlib_constants=resolver.merged_stdlib_constants,
    )
    return buf.getvalue()


def debug_run_source(source: str, commands: str) -> tuple[str, str]:
    """Compile and run *source* under the debugger, return (debugger_output, program_output).

    *commands* is a newline-separated string of debugger commands fed as input.
    """
    compiled = compile_source(source)
    program_buf = StringIO()
    debug_buf = StringIO()
    cmd_input = StringIO(commands)
    debugger = Debugger(
        source=source,
        output=debug_buf,
        input_stream=cmd_input,
    )
    vm = VirtualMachine(output=program_buf)
    vm.run(compiled, debug_hook=debugger)
    return debug_buf.getvalue(), program_buf.getvalue()
