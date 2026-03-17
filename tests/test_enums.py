"""Tests for the Pebble enum feature."""

from io import StringIO

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import EnumDef, EnumPattern
from pebble.builtins import EnumVariant
from pebble.bytecode import OpCode
from pebble.compiler import Compiler
from pebble.errors import ParseError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.repl import Repl
from pebble.tokens import TokenKind
from tests.conftest import run_source

# -- Named constants ----------------------------------------------------------

EXPECTED_VARIANT_OPCODE_COUNT = 2

# ---------------------------------------------------------------------------
# Lexer tests
# ---------------------------------------------------------------------------


class TestEnumLexer:
    """Verify the ``enum`` keyword is tokenised correctly."""

    def test_enum_keyword_tokenised(self) -> None:
        """The lexer produces an ENUM token for the ``enum`` keyword."""
        tokens = Lexer("enum").tokenize()
        assert tokens[0].kind == TokenKind.ENUM
        assert tokens[0].value == "enum"


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestEnumParser:
    """Verify parsing of ``enum`` definitions and ``EnumPattern``."""

    def test_enum_def_parsed(self) -> None:
        """A basic ``enum Color { Red, Green, Blue }`` is parsed correctly."""
        tokens = Lexer("enum Color { Red, Green, Blue }").tokenize()
        program = Parser(tokens).parse()
        stmt = program.statements[0]
        assert isinstance(stmt, EnumDef)
        assert stmt.name == "Color"
        assert stmt.variants == ["Red", "Green", "Blue"]

    def test_enum_single_variant(self) -> None:
        """An enum with a single variant is valid."""
        tokens = Lexer("enum Solo { One }").tokenize()
        program = Parser(tokens).parse()
        stmt = program.statements[0]
        assert isinstance(stmt, EnumDef)
        assert stmt.variants == ["One"]

    def test_enum_many_variants(self) -> None:
        """An enum with many variants is parsed correctly."""
        tokens = Lexer("enum Dir { N, S, E, W }").tokenize()
        program = Parser(tokens).parse()
        stmt = program.statements[0]
        assert isinstance(stmt, EnumDef)
        assert stmt.variants == ["N", "S", "E", "W"]

    def test_enum_trailing_comma(self) -> None:
        """A trailing comma after the last variant is allowed."""
        tokens = Lexer("enum Color { Red, Green, }").tokenize()
        program = Parser(tokens).parse()
        stmt = program.statements[0]
        assert isinstance(stmt, EnumDef)
        assert stmt.variants == ["Red", "Green"]

    def test_enum_pattern_in_match(self) -> None:
        """``case Color.Red`` is parsed as an ``EnumPattern``."""
        source = """\
enum Color { Red, Green }
match Color.Red {
  case Color.Red { print("red") }
  case _ { print("other") }
}
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        match_stmt = program.statements[1]
        assert hasattr(match_stmt, "cases")
        pattern = match_stmt.cases[0].pattern  # type: ignore[union-attr]
        assert isinstance(pattern, EnumPattern)
        assert pattern.enum_name == "Color"
        assert pattern.variant_name == "Red"

    def test_enum_empty_raises(self) -> None:
        """An enum with no variants raises a parse error."""
        tokens = Lexer("enum Empty { }").tokenize()
        with pytest.raises(ParseError, match="must have at least one variant"):
            Parser(tokens).parse()

    def test_enum_duplicate_variant_raises(self) -> None:
        """Duplicate variant names in an enum raise a parse error."""
        tokens = Lexer("enum Dup { A, A }").tokenize()
        with pytest.raises(ParseError, match="Duplicate variant 'A'"):
            Parser(tokens).parse()


# ---------------------------------------------------------------------------
# Analyzer tests
# ---------------------------------------------------------------------------


class TestEnumAnalyzer:
    """Verify semantic analysis of enums."""

    def test_enum_passes_analysis(self) -> None:
        """A valid enum definition passes semantic analysis."""
        source = "enum Color { Red, Green, Blue }"
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        analyzer.analyze(program)
        assert "Color" in analyzer.enums
        assert analyzer.enums["Color"] == ["Red", "Green", "Blue"]

    def test_unknown_variant_errors(self) -> None:
        """Accessing an unknown variant raises a semantic error."""
        source = """\
enum Color { Red, Green }
let c = Color.Yellow
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        with pytest.raises(SemanticError, match="has no variant 'Yellow'"):
            SemanticAnalyzer().analyze(program)

    def test_unknown_enum_in_pattern_errors(self) -> None:
        """Using an unknown enum in a match pattern raises a semantic error."""
        source = """\
enum Color { Red }
let c = Color.Red
match c {
  case Foo.Bar { print("x") }
  case _ { print("y") }
}
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        with pytest.raises(SemanticError, match="Unknown enum 'Foo'"):
            SemanticAnalyzer().analyze(program)

    def test_unknown_variant_in_pattern_errors(self) -> None:
        """Using an unknown variant in a match pattern raises a semantic error."""
        source = """\
enum Color { Red }
let c = Color.Red
match c {
  case Color.Blue { print("x") }
  case _ { print("y") }
}
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        with pytest.raises(SemanticError, match="has no variant 'Blue'"):
            SemanticAnalyzer().analyze(program)

    def test_enum_name_resolves_as_variable(self) -> None:
        """An enum name is registered as a variable (for field access)."""
        source = """\
enum Color { Red }
let c = Color.Red
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        # Should not raise — Color resolves as a variable
        SemanticAnalyzer().analyze(program)


# ---------------------------------------------------------------------------
# Compiler tests
# ---------------------------------------------------------------------------


class TestEnumCompiler:
    """Verify bytecode emission for enums."""

    def test_load_enum_variant_emitted_for_dot_access(self) -> None:
        """``Color.Red`` emits ``LOAD_ENUM_VARIANT``."""
        source = """\
enum Color { Red }
let c = Color.Red
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        analyzed = analyzer.analyze(program)
        compiled = Compiler(enums=analyzer.enums).compile(analyzed)
        opcodes = [i.opcode for i in compiled.main.instructions]
        assert OpCode.LOAD_ENUM_VARIANT in opcodes

    def test_load_enum_variant_emitted_for_match_pattern(self) -> None:
        """An ``EnumPattern`` in match/case emits ``LOAD_ENUM_VARIANT``."""
        source = """\
enum Color { Red, Green }
let c = Color.Red
match c {
  case Color.Red { print("red") }
  case _ { print("other") }
}
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        analyzed = analyzer.analyze(program)
        compiled = Compiler(enums=analyzer.enums).compile(analyzed)
        opcodes = [i.opcode for i in compiled.main.instructions]
        # Two LOAD_ENUM_VARIANT: one for `Color.Red` in let, one in match case
        variant_count = opcodes.count(OpCode.LOAD_ENUM_VARIANT)
        assert variant_count == EXPECTED_VARIANT_OPCODE_COUNT


# ---------------------------------------------------------------------------
# Integration tests (end-to-end)
# ---------------------------------------------------------------------------


class TestEnumIntegration:
    """End-to-end tests for the enum feature."""

    def test_print_enum_variant(self) -> None:
        """``print(Color.Red)`` outputs ``Color.Red``."""
        source = """\
enum Color { Red, Green, Blue }
print(Color.Red)
"""
        assert run_source(source) == "Color.Red\n"

    def test_type_of_enum_variant(self) -> None:
        """``type(Color.Red)`` returns the enum name."""
        source = """\
enum Color { Red, Green, Blue }
print(type(Color.Red))
"""
        assert run_source(source) == "Color\n"

    def test_enum_equality(self) -> None:
        """Two identical enum variants are equal."""
        source = """\
enum Color { Red, Green }
let c = Color.Red
print(c == Color.Red)
"""
        assert run_source(source) == "true\n"

    def test_enum_inequality(self) -> None:
        """Different enum variants are not equal."""
        source = """\
enum Color { Red, Green }
let c = Color.Red
print(c == Color.Green)
"""
        assert run_source(source) == "false\n"

    def test_enum_not_equal(self) -> None:
        """``!=`` works with enum variants."""
        source = """\
enum Color { Red, Green }
print(Color.Red != Color.Green)
"""
        assert run_source(source) == "true\n"

    def test_match_case_enum(self) -> None:
        """Match/case correctly dispatches on enum variants."""
        source = """\
enum Color { Red, Green, Blue }
let c = Color.Green
match c {
  case Color.Red { print("red") }
  case Color.Green { print("green") }
  case _ { print("other") }
}
"""
        assert run_source(source) == "green\n"

    def test_match_case_enum_wildcard(self) -> None:
        """Match/case falls through to wildcard for unmatched enum variant."""
        source = """\
enum Color { Red, Green, Blue }
let c = Color.Blue
match c {
  case Color.Red { print("red") }
  case Color.Green { print("green") }
  case _ { print("other") }
}
"""
        assert run_source(source) == "other\n"

    def test_if_else_with_enum(self) -> None:
        """Enums work in if/else conditions."""
        source = """\
enum Dir { Up, Down }
let d = Dir.Up
if d == Dir.Up {
  print("going up")
} else {
  print("going down")
}
"""
        assert run_source(source) == "going up\n"

    def test_reassignment(self) -> None:
        """An enum variable can be reassigned to a different variant."""
        source = """\
enum Color { Red, Green }
let c = Color.Red
c = Color.Green
print(c)
"""
        assert run_source(source) == "Color.Green\n"

    def test_multiple_enums(self) -> None:
        """Multiple independent enums can coexist."""
        source = """\
enum Color { Red, Green }
enum Dir { Up, Down }
print(Color.Red)
print(Dir.Up)
"""
        assert run_source(source) == "Color.Red\nDir.Up\n"

    def test_enum_in_list(self) -> None:
        """Enum variants can be stored in lists."""
        source = """\
enum Color { Red, Green, Blue }
let colors = [Color.Red, Color.Green, Color.Blue]
print(colors[1])
"""
        assert run_source(source) == "Color.Green\n"

    def test_enum_in_dict(self) -> None:
        """Enum variants can be stored as dict values."""
        source = """\
enum Color { Red, Green }
let d = {"fav": Color.Red}
print(d["fav"])
"""
        assert run_source(source) == "Color.Red\n"

    def test_string_interpolation(self) -> None:
        """Enum variants work in string interpolation."""
        source = """\
enum Color { Red }
let c = Color.Red
print("color is {c}")
"""
        assert run_source(source) == "color is Color.Red\n"

    def test_enum_not_callable(self) -> None:
        """Calling an enum name as a function raises an error."""
        source = """\
enum Color { Red }
Color()
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        with pytest.raises(SemanticError, match="'Color' is an enum, not a function"):
            SemanticAnalyzer().analyze(program)

    def test_enum_variant_frozen_equality(self) -> None:
        """``EnumVariant`` dataclass has correct equality from frozen=True."""
        a = EnumVariant(enum_name="Color", variant_name="Red")
        b = EnumVariant(enum_name="Color", variant_name="Red")
        c = EnumVariant(enum_name="Color", variant_name="Blue")
        assert a == b
        assert a != c

    def test_enum_variant_hashable(self) -> None:
        """``EnumVariant`` is hashable (frozen dataclass)."""
        v = EnumVariant(enum_name="Color", variant_name="Red")
        result = {v}
        assert len(result) == 1


# ---------------------------------------------------------------------------
# REPL tests
# ---------------------------------------------------------------------------


class TestEnumRepl:
    """Verify enum persistence across REPL evaluations."""

    def test_enum_persists_in_repl(self) -> None:
        """An enum defined in one REPL line is available in the next."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("enum Color { Red, Green }")
        r.eval_line("print(Color.Red)")
        assert buf.getvalue() == "Color.Red\n"

    def test_enum_match_in_repl(self) -> None:
        """An enum defined in one REPL line can be matched in a later line."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("enum Color { Red, Green }")
        r.eval_line("let c = Color.Red")
        r.eval_line('match c {\n  case Color.Red { print("red") }\n  case _ { print("other") }\n}')
        assert buf.getvalue() == "red\n"


# ---------------------------------------------------------------------------
# Bug regression: enum names as type annotations
# ---------------------------------------------------------------------------


class TestEnumTypeAnnotation:
    """Verify enum names are accepted as type annotations."""

    def test_enum_type_annotation_accepted(self) -> None:
        """``let c: Color = Color.Red`` should pass the analyzer."""
        source = "enum Color { Red, Green }\nlet c: Color = Color.Red\nprint(c)"
        assert run_source(source) == "Color.Red\n"

    def test_enum_type_annotation_in_function(self) -> None:
        """A function parameter annotated with an enum type is accepted."""
        source = "enum Color { Red, Green }\nfn show(c: Color) { print(c) }\nshow(Color.Green)"
        assert run_source(source) == "Color.Green\n"
