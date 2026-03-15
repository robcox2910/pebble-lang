"""Module resolver for the Pebble import system.

Resolve ``import`` and ``from ... import`` statements by compiling
imported modules through the full pipeline, caching results, and
detecting circular imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path  # noqa: TC003 — used at runtime
from typing import TYPE_CHECKING

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import FromImportStatement, FunctionDef, ImportStatement, StructDef
from pebble.compiler import Compiler
from pebble.errors import PebbleImportError
from pebble.lexer import Lexer
from pebble.parser import Parser

if TYPE_CHECKING:
    from pebble.ast_nodes import Program, Statement
    from pebble.bytecode import CodeObject
    from pebble.tokens import SourceLocation


@dataclass(frozen=True)
class ResolvedModule:
    """Definitions extracted from a compiled module.

    Attributes:
        functions: ALL function CodeObjects (including transitive imports).
        structs: ALL struct field lists (including transitive imports).
        exported_functions: Only THIS module's top-level fn names → arities.
        exported_structs: Only THIS module's top-level struct names → field counts.

    """

    functions: dict[str, CodeObject]
    structs: dict[str, list[str]]
    exported_functions: dict[str, int]
    exported_structs: dict[str, int]


class ModuleResolver:
    """Resolve import statements by compiling modules and caching results.

    Args:
        base_dir: Directory from which relative import paths are resolved.

    """

    def __init__(self, *, base_dir: Path) -> None:
        """Create a resolver rooted at *base_dir*."""
        self._base_dir = base_dir
        self._cache: dict[Path, ResolvedModule] = {}
        self._resolving: set[Path] = set()
        self._merged_functions: dict[str, CodeObject] = {}
        self._merged_structs: dict[str, list[str]] = {}

    # -- Public API -----------------------------------------------------------

    @property
    def merged_functions(self) -> dict[str, CodeObject]:
        """Return all imported function CodeObjects for merging into CompiledProgram."""
        return dict(self._merged_functions)

    @property
    def merged_structs(self) -> dict[str, list[str]]:
        """Return all imported struct definitions for merging into CompiledProgram."""
        return dict(self._merged_structs)

    def resolve_imports(self, program: Program, analyzer: SemanticAnalyzer) -> None:
        """Walk *program*'s import statements, resolve each, and register names in *analyzer*."""
        for stmt in program.statements:
            if isinstance(stmt, ImportStatement):
                self._resolve_import(stmt, analyzer)
            elif isinstance(stmt, FromImportStatement):
                self._resolve_from_import(stmt, analyzer)

    # -- Internal -------------------------------------------------------------

    def _resolve_import(self, stmt: ImportStatement, analyzer: SemanticAnalyzer) -> None:
        """Resolve an ``import "path.pbl"`` statement."""
        resolved = self._compile_module(stmt.path, stmt.location)
        # Register all exported names in analyzer scope
        for name, arity in resolved.exported_functions.items():
            analyzer.register_imported_function(name, arity, stmt.location)
        for name, field_count in resolved.exported_structs.items():
            analyzer.register_imported_struct(name, field_count, stmt.location)
        # Merge all definitions (including transitive) for CompiledProgram
        self._merged_functions.update(resolved.functions)
        self._merged_structs.update(resolved.structs)

    def _resolve_from_import(self, stmt: FromImportStatement, analyzer: SemanticAnalyzer) -> None:
        """Resolve a ``from "path.pbl" import name1, name2`` statement."""
        resolved = self._compile_module(stmt.path, stmt.location)
        for name in stmt.names:
            if name in resolved.exported_functions:
                arity = resolved.exported_functions[name]
                analyzer.register_imported_function(name, arity, stmt.location)
            elif name in resolved.exported_structs:
                field_count = resolved.exported_structs[name]
                analyzer.register_imported_struct(name, field_count, stmt.location)
            else:
                msg = f"Module '{stmt.path}' does not export '{name}'"
                raise PebbleImportError(msg, line=stmt.location.line, column=stmt.location.column)
        # Merge all definitions for CompiledProgram
        self._merged_functions.update(resolved.functions)
        self._merged_structs.update(resolved.structs)

    def _resolve_path(self, import_path: str, location: SourceLocation) -> Path:
        """Resolve *import_path* relative to *base_dir*."""
        resolved = (self._base_dir / import_path).resolve()
        if not resolved.is_file():
            msg = f"Module '{import_path}' not found"
            raise PebbleImportError(msg, line=location.line, column=location.column)
        return resolved

    def _compile_module(self, import_path: str, location: SourceLocation) -> ResolvedModule:
        """Compile an imported module and return its resolved definitions."""
        path = self._resolve_path(import_path, location)

        # Cache hit — no recompilation needed
        if path in self._cache:
            return self._cache[path]

        # Circular import detection
        if path in self._resolving:
            msg = f"Circular import detected: '{import_path}'"
            raise PebbleImportError(msg, line=location.line, column=location.column)

        self._resolving.add(path)
        try:
            source = path.read_text()
            tokens = Lexer(source).tokenize()
            program = Parser(tokens).parse()

            # Extract this module's own top-level defs
            exported_functions = _extract_function_defs(program.statements)
            exported_structs = _extract_struct_defs(program.statements)

            # Recursively resolve nested imports in a fresh sub-resolver
            sub_resolver = ModuleResolver(base_dir=path.parent.resolve())
            sub_resolver._cache = self._cache
            sub_resolver._resolving = self._resolving
            sub_analyzer = SemanticAnalyzer()
            sub_resolver.resolve_imports(program, sub_analyzer)

            # Analyze and compile
            analyzed = sub_analyzer.analyze(program)
            compiled = Compiler(
                cell_vars=sub_analyzer.cell_vars,
                free_vars=sub_analyzer.free_vars,
            ).compile(analyzed)

            # Build merged function/struct dicts (transitive + own)
            all_functions = {**sub_resolver.merged_functions, **compiled.functions}
            all_structs = {**sub_resolver.merged_structs, **compiled.structs}

            result = ResolvedModule(
                functions=all_functions,
                structs=all_structs,
                exported_functions=exported_functions,
                exported_structs=exported_structs,
            )
            self._cache[path] = result
            return result
        finally:
            self._resolving.discard(path)


# -- Extraction helpers -------------------------------------------------------


def _extract_function_defs(stmts: list[Statement]) -> dict[str, int]:
    """Extract top-level function names and arities from a statement list."""
    return {stmt.name: len(stmt.parameters) for stmt in stmts if isinstance(stmt, FunctionDef)}


def _extract_struct_defs(stmts: list[Statement]) -> dict[str, int]:
    """Extract top-level struct names and field counts from a statement list."""
    return {stmt.name: len(stmt.fields) for stmt in stmts if isinstance(stmt, StructDef)}
