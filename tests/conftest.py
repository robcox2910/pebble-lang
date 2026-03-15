"""Shared test fixtures for the Pebble test suite."""

from io import StringIO

from pebble.analyzer import SemanticAnalyzer
from pebble.compiler import Compiler
from pebble.lexer import Lexer
from pebble.parser import Parser
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
    ).compile(analyzed)
    buf = StringIO()
    VirtualMachine(output=buf).run(compiled)
    return buf.getvalue()
