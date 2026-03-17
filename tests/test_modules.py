"""Tests for the Pebble module/import system."""

from io import StringIO
from pathlib import Path

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import FromImportStatement, ImportStatement, Program
from pebble.errors import ParseError, PebbleError, PebbleImportError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.repl import Repl
from pebble.tokens import SourceLocation, Token, TokenKind
from tests.conftest import (
    analyze,
    run_source_with_imports,
)

# -- Named constants -----------------------------------------------------------

FIRST_LINE = 1
FIRST_COLUMN = 1
REGISTERED_ARITY = 2


# -- Helpers -------------------------------------------------------------------


def _lex(source: str) -> list[Token]:
    """Lex *source* and return the token list."""
    return Lexer(source).tokenize()


def _parse(source: str) -> Program:
    """Parse *source* and return the AST Program."""
    return Parser(_lex(source)).parse()


# ===========================================================================
# Cycle 1 — Tokens + AST nodes + Error class
# ===========================================================================


class TestImportTokens:
    """Verify import/from are lexed as keyword tokens."""

    def test_import_is_keyword_token(self) -> None:
        """Verify 'import' is lexed as IMPORT, not IDENTIFIER."""
        tokens = _lex('import "math.pbl"')
        assert tokens[0].kind == TokenKind.IMPORT

    def test_from_is_keyword_token(self) -> None:
        """Verify 'from' is lexed as FROM, not IDENTIFIER."""
        tokens = _lex('from "utils.pbl" import add')
        assert tokens[0].kind == TokenKind.FROM


class TestImportASTNodes:
    """Verify ImportStatement and FromImportStatement construction."""

    def test_import_statement_node(self) -> None:
        """Verify ImportStatement dataclass construction."""
        loc = SourceLocation(line=FIRST_LINE, column=FIRST_COLUMN)
        node = ImportStatement(path="math.pbl", location=loc)
        assert node.path == "math.pbl"
        assert node.location == loc

    def test_from_import_statement_node(self) -> None:
        """Verify FromImportStatement dataclass construction."""
        loc = SourceLocation(line=FIRST_LINE, column=FIRST_COLUMN)
        node = FromImportStatement(path="utils.pbl", names=["add", "sub"], location=loc)
        assert node.path == "utils.pbl"
        assert node.names == ["add", "sub"]
        assert node.location == loc


class TestPebbleImportError:
    """Verify PebbleImportError is a subclass of PebbleError."""

    def test_is_pebble_error_subclass(self) -> None:
        """Verify PebbleImportError inherits from PebbleError."""
        assert issubclass(PebbleImportError, PebbleError)

    def test_can_be_raised_and_caught(self) -> None:
        """Verify PebbleImportError carries line/column info."""
        msg = "Module not found"
        with pytest.raises(PebbleImportError, match="not found"):
            raise PebbleImportError(msg, line=1, column=1)


# ===========================================================================
# Cycle 2 — Parser
# ===========================================================================


class TestParserImport:
    """Verify parsing of import statements."""

    def test_parse_import(self) -> None:
        """Parse ``import "math.pbl"`` into ImportStatement."""
        program = _parse('import "math.pbl"')
        stmt = program.statements[0]
        assert isinstance(stmt, ImportStatement)
        assert stmt.path == "math.pbl"

    def test_parse_from_import_single_name(self) -> None:
        """Parse ``from "math.pbl" import add`` into FromImportStatement."""
        program = _parse('from "math.pbl" import add')
        stmt = program.statements[0]
        assert isinstance(stmt, FromImportStatement)
        assert stmt.path == "math.pbl"
        assert stmt.names == ["add"]

    def test_parse_from_import_multiple_names(self) -> None:
        """Parse ``from "math.pbl" import add, sub, mul``."""
        program = _parse('from "math.pbl" import add, sub, mul')
        stmt = program.statements[0]
        assert isinstance(stmt, FromImportStatement)
        assert stmt.names == ["add", "sub", "mul"]

    def test_import_missing_path(self) -> None:
        """Raise ParseError when path is missing after 'import'."""
        with pytest.raises(ParseError):
            _parse("import add")

    def test_from_import_missing_path(self) -> None:
        """Raise ParseError when path is missing after 'from'."""
        with pytest.raises(ParseError):
            _parse("from add import thing")

    def test_from_import_missing_import_keyword(self) -> None:
        """Raise ParseError when 'import' is missing after path."""
        with pytest.raises(ParseError):
            _parse('from "utils.pbl" add')

    def test_from_import_missing_name(self) -> None:
        """Raise ParseError when no names follow 'import'."""
        with pytest.raises(ParseError):
            _parse('from "utils.pbl" import')


# ===========================================================================
# Cycle 3 — Analyzer
# ===========================================================================


class TestAnalyzerImport:
    """Verify analyzer handles import ordering and registration."""

    def test_import_at_top_passes(self) -> None:
        """Import followed by a statement is valid."""
        analyze('import "math.pbl"\nlet x = 1')

    def test_multiple_imports_at_top(self) -> None:
        """Multiple imports at the top of a file pass analysis."""
        analyze('import "a.pbl"\nimport "b.pbl"\nlet x = 1')

    def test_import_after_statement_fails(self) -> None:
        """Import after a non-import statement raises SemanticError."""
        with pytest.raises(SemanticError, match="must appear at the top"):
            analyze('let x = 1\nimport "math.pbl"')

    def test_from_import_after_statement_fails(self) -> None:
        """From-import after a non-import statement raises SemanticError."""
        with pytest.raises(SemanticError, match="must appear at the top"):
            analyze('let x = 1\nfrom "math.pbl" import add')

    def test_register_imported_function(self) -> None:
        """Register an imported function so calls pass analysis."""
        program = _parse("print(add(1, 2))")
        analyzer = SemanticAnalyzer()
        loc = SourceLocation(line=0, column=0)
        analyzer.register_imported_function("add", REGISTERED_ARITY, loc)
        analyzer.analyze(program)  # should not raise

    def test_register_imported_struct(self) -> None:
        """Register an imported struct so constructor calls pass analysis."""
        program = _parse("let p = Point(3, 4)")
        analyzer = SemanticAnalyzer()
        loc = SourceLocation(line=0, column=0)
        analyzer.register_imported_struct("Point", REGISTERED_ARITY, loc)
        analyzer.analyze(program)  # should not raise

    def test_imported_function_arity_mismatch(self) -> None:
        """Call an imported function with wrong arity raises SemanticError."""
        program = _parse("print(add(1))")
        analyzer = SemanticAnalyzer()
        loc = SourceLocation(line=0, column=0)
        analyzer.register_imported_function("add", REGISTERED_ARITY, loc)
        with pytest.raises(SemanticError, match="expects 2"):
            analyzer.analyze(program)


# ===========================================================================
# Cycle 4 — Resolver + Integration
# ===========================================================================


class TestResolver:
    """Verify ModuleResolver compile-time resolution."""

    def test_simple_import_function(self, tmp_path: Path) -> None:
        """Import a module with one function and call it."""
        (tmp_path / "math.pbl").write_text("fn add(a, b) {\n    return a + b\n}\n")
        source = 'import "math.pbl"\nprint(add(1, 2))'
        assert run_source_with_imports(source, base_dir=tmp_path) == "3\n"

    def test_from_import_function(self, tmp_path: Path) -> None:
        """From-import a specific function."""
        (tmp_path / "math.pbl").write_text(
            "fn add(a, b) {\n    return a + b\n}\nfn sub(a, b) {\n    return a - b\n}\n"
        )
        source = 'from "math.pbl" import add\nprint(add(3, 4))'
        assert run_source_with_imports(source, base_dir=tmp_path) == "7\n"

    def test_from_import_name_not_found(self, tmp_path: Path) -> None:
        """From-import a name that doesn't exist raises PebbleImportError."""
        (tmp_path / "math.pbl").write_text("fn add(a, b) {\n    return a + b\n}\n")
        source = 'from "math.pbl" import multiply'
        with pytest.raises(PebbleImportError, match="does not export 'multiply'"):
            run_source_with_imports(source, base_dir=tmp_path)

    def test_module_not_found(self, tmp_path: Path) -> None:
        """Import a non-existent module raises PebbleImportError."""
        source = 'import "nonexistent.pbl"'
        with pytest.raises(PebbleImportError, match="not found"):
            run_source_with_imports(source, base_dir=tmp_path)

    def test_circular_import(self, tmp_path: Path) -> None:
        """Circular import raises PebbleImportError."""
        (tmp_path / "a.pbl").write_text('import "b.pbl"\nfn fa() { return 1 }\n')
        (tmp_path / "b.pbl").write_text('import "a.pbl"\nfn fb() { return 2 }\n')
        source = 'import "a.pbl"\nprint(fa())'
        with pytest.raises(PebbleImportError, match="Circular"):
            run_source_with_imports(source, base_dir=tmp_path)

    def test_nested_imports(self, tmp_path: Path) -> None:
        """A imports B, B imports C — transitive chain works."""
        (tmp_path / "c.pbl").write_text("fn double(x) {\n    return x * 2\n}\n")
        (tmp_path / "b.pbl").write_text('import "c.pbl"\nfn triple(x) {\n    return x * 3\n}\n')
        (tmp_path / "a.pbl").write_text('import "b.pbl"\nfn quad(x) {\n    return x * 4\n}\n')
        source = 'import "a.pbl"\nprint(quad(5))'
        assert run_source_with_imports(source, base_dir=tmp_path) == "20\n"

    def test_diamond_imports(self, tmp_path: Path) -> None:
        """A imports B and C; both B and C import D — no recompilation error."""
        (tmp_path / "d.pbl").write_text("fn helper() {\n    return 42\n}\n")
        (tmp_path / "b.pbl").write_text('import "d.pbl"\nfn fb() {\n    return helper()\n}\n')
        (tmp_path / "c.pbl").write_text('import "d.pbl"\nfn fc() {\n    return helper()\n}\n')
        source = 'import "b.pbl"\nimport "c.pbl"\nprint(fb())\nprint(fc())'
        assert run_source_with_imports(source, base_dir=tmp_path) == "42\n42\n"

    def test_import_struct(self, tmp_path: Path) -> None:
        """Import a module with a struct definition."""
        (tmp_path / "geom.pbl").write_text("struct Point { x, y }\n")
        source = 'import "geom.pbl"\nlet p = Point(3, 4)\nprint(p.x)'
        assert run_source_with_imports(source, base_dir=tmp_path) == "3\n"

    def test_from_import_struct(self, tmp_path: Path) -> None:
        """From-import a struct by name."""
        (tmp_path / "geom.pbl").write_text("struct Point { x, y }\nstruct Line { start, end }\n")
        source = 'from "geom.pbl" import Point\nlet p = Point(1, 2)\nprint(p.y)'
        assert run_source_with_imports(source, base_dir=tmp_path) == "2\n"

    def test_selective_import_limits_scope(self, tmp_path: Path) -> None:
        """From-import only brings in selected names; others are unavailable."""
        (tmp_path / "math.pbl").write_text(
            "fn add(a, b) {\n    return a + b\n}\nfn sub(a, b) {\n    return a - b\n}\n"
        )
        source = 'from "math.pbl" import add\nprint(sub(5, 3))'
        with pytest.raises(SemanticError, match="Undeclared function 'sub'"):
            run_source_with_imports(source, base_dir=tmp_path)

    def test_internal_helpers_included(self, tmp_path: Path) -> None:
        """An imported function that calls internal helpers works at runtime."""
        (tmp_path / "math.pbl").write_text(
            "fn _square(x) {\n    return x * x\n}\n"
            "fn sum_of_squares(a, b) {\n    return _square(a) + _square(b)\n}\n"
        )
        source = 'from "math.pbl" import sum_of_squares\nprint(sum_of_squares(3, 4))'
        assert run_source_with_imports(source, base_dir=tmp_path) == "25\n"

    def test_import_from_subdirectory(self, tmp_path: Path) -> None:
        """Import from a subdirectory path."""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "utils.pbl").write_text("fn greet() {\n    return 42\n}\n")
        source = 'import "lib/utils.pbl"\nprint(greet())'
        assert run_source_with_imports(source, base_dir=tmp_path) == "42\n"


class TestEndToEnd:
    """End-to-end integration tests for the module system."""

    def test_import_function_and_call(self, tmp_path: Path) -> None:
        """Import a function and call it — full pipeline."""
        (tmp_path / "math.pbl").write_text("fn add(a, b) {\n    return a + b\n}\n")
        source = 'import "math.pbl"\nprint(add(10, 20))'
        assert run_source_with_imports(source, base_dir=tmp_path) == "30\n"

    def test_import_struct_and_construct(self, tmp_path: Path) -> None:
        """Import a struct and construct an instance."""
        (tmp_path / "geom.pbl").write_text("struct Point { x, y }\n")
        source = 'import "geom.pbl"\nlet p = Point(5, 10)\nprint(p)'
        assert run_source_with_imports(source, base_dir=tmp_path) == "Point(x=5, y=10)\n"

    def test_imported_fn_calls_helper(self, tmp_path: Path) -> None:
        """An imported function that calls an internal helper works."""
        (tmp_path / "utils.pbl").write_text(
            "fn _helper(x) {\n    return x * 10\n}\n"
            "fn transform(x) {\n    return _helper(x) + 1\n}\n"
        )
        source = 'import "utils.pbl"\nprint(transform(5))'
        assert run_source_with_imports(source, base_dir=tmp_path) == "51\n"

    def test_import_from_multiple_modules(self, tmp_path: Path) -> None:
        """Import from two different modules."""
        (tmp_path / "math.pbl").write_text("fn add(a, b) {\n    return a + b\n}\n")
        (tmp_path / "str.pbl").write_text("fn greet() {\n    return 99\n}\n")
        source = 'import "math.pbl"\nimport "str.pbl"\nprint(add(1, greet()))'
        assert run_source_with_imports(source, base_dir=tmp_path) == "100\n"

    def test_from_import_multiple_names(self, tmp_path: Path) -> None:
        """From-import multiple names from one module."""
        (tmp_path / "math.pbl").write_text(
            "fn add(a, b) {\n    return a + b\n}\nfn mul(a, b) {\n    return a * b\n}\n"
        )
        source = 'from "math.pbl" import add, mul\nprint(add(2, mul(3, 4)))'
        assert run_source_with_imports(source, base_dir=tmp_path) == "14\n"

    def test_module_with_functions_and_structs(self, tmp_path: Path) -> None:
        """Import a module that has both functions and structs."""
        (tmp_path / "geom.pbl").write_text(
            "struct Point { x, y }\nfn origin() {\n    return Point(0, 0)\n}\n"
        )
        source = 'import "geom.pbl"\nlet o = origin()\nprint(o)'
        assert run_source_with_imports(source, base_dir=tmp_path) == "Point(x=0, y=0)\n"

    def test_nested_module_chain(self, tmp_path: Path) -> None:
        """Three-level nested import chain works end-to-end."""
        (tmp_path / "c.pbl").write_text("fn base() {\n    return 1\n}\n")
        (tmp_path / "b.pbl").write_text('import "c.pbl"\nfn mid() {\n    return base() + 10\n}\n')
        (tmp_path / "a.pbl").write_text('import "b.pbl"\nfn top() {\n    return mid() + 100\n}\n')
        source = 'import "a.pbl"\nprint(top())'
        assert run_source_with_imports(source, base_dir=tmp_path) == "111\n"

    def test_import_function_with_closure(self, tmp_path: Path) -> None:
        """Import a function that uses closures."""
        (tmp_path / "counter.pbl").write_text(
            "fn make_adder(n) {\n"
            "    fn adder(x) {\n"
            "        return x + n\n"
            "    }\n"
            "    return adder\n"
            "}\n"
        )
        source = 'import "counter.pbl"\nlet add5 = make_adder(5)\nprint(add5(10))'
        assert run_source_with_imports(source, base_dir=tmp_path) == "15\n"

    def test_module_level_print_does_not_execute(self, tmp_path: Path) -> None:
        """Top-level print in a module does NOT execute during import."""
        (tmp_path / "noisy.pbl").write_text("print(999)\nfn quiet() {\n    return 0\n}\n")
        source = 'import "noisy.pbl"\nprint(quiet())'
        # Only "0\n" — the module's print(999) should not run
        assert run_source_with_imports(source, base_dir=tmp_path) == "0\n"


class TestReplImport:
    """Verify REPL handles imports."""

    def test_import_in_repl(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Import a module in the REPL."""
        (tmp_path / "math.pbl").write_text("fn add(a, b) {\n    return a + b\n}\n")
        monkeypatch.setattr(Path, "cwd", staticmethod(lambda: tmp_path))
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line('import "math.pbl"')
        r.eval_line("print(add(1, 2))")
        assert buf.getvalue() == "3\n"
