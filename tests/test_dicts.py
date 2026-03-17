"""Tests for dictionaries / maps.

Cover lexer tokenization, parser AST construction, analyzer validation,
compiler bytecode generation, and VM execution of dictionary operations.
"""

import pytest

from pebble.ast_nodes import DictLiteral, Expression, IntegerLiteral, StringLiteral
from pebble.bytecode import OpCode
from pebble.errors import ParseError, PebbleRuntimeError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.tokens import TokenKind
from tests.conftest import (
    compile_instructions,
    run_source,
)

# -- Named constants ----------------------------------------------------------

ZERO = 0
ONE = 1
TWO = 2
THREE = 3


# -- Helpers ------------------------------------------------------------------


def _kinds(source: str) -> list[TokenKind]:
    """Return just the token kinds for *source* (excluding EOF)."""
    tokens = Lexer(source).tokenize()
    return [t.kind for t in tokens if t.kind != TokenKind.EOF]


def _parse_expr(source: str) -> Expression:
    """Lex and parse a single expression from *source*."""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse_expression()


# -- Cycle 1: Lexer — COLON token --------------------------------------------


class TestLexerColon:
    """Verify ``:`` tokenizes as COLON."""

    def test_colon_token(self) -> None:
        """A bare ``:`` produces a COLON token."""
        assert _kinds(":") == [TokenKind.COLON]

    def test_dict_literal_tokens(self) -> None:
        """``{"a": 1}`` produces the expected token sequence."""
        assert _kinds('{"a": 1}') == [
            TokenKind.LEFT_BRACE,
            TokenKind.STRING,
            TokenKind.COLON,
            TokenKind.INTEGER,
            TokenKind.RIGHT_BRACE,
        ]

    def test_two_entry_dict_tokens(self) -> None:
        """``{"a": 1, "b": 2}`` produces the expected token sequence."""
        assert _kinds('{"a": 1, "b": 2}') == [
            TokenKind.LEFT_BRACE,
            TokenKind.STRING,
            TokenKind.COLON,
            TokenKind.INTEGER,
            TokenKind.COMMA,
            TokenKind.STRING,
            TokenKind.COLON,
            TokenKind.INTEGER,
            TokenKind.RIGHT_BRACE,
        ]


# -- Cycle 2: Parser — DictLiteral -------------------------------------------


class TestParserDictLiteral:
    """Verify parsing of dictionary literals."""

    def test_single_entry(self) -> None:
        """``{"a": 1}`` parses to DictLiteral with 1 entry."""
        node = _parse_expr('{"a": 1}')
        assert isinstance(node, DictLiteral)
        assert len(node.entries) == ONE
        key, value = node.entries[0]
        assert isinstance(key, StringLiteral)
        assert isinstance(value, IntegerLiteral)

    def test_two_entries(self) -> None:
        """``{"a": 1, "b": 2}`` parses to DictLiteral with 2 entries."""
        node = _parse_expr('{"a": 1, "b": 2}')
        assert isinstance(node, DictLiteral)
        assert len(node.entries) == TWO

    def test_empty_dict(self) -> None:
        """``{}`` parses to DictLiteral with 0 entries."""
        node = _parse_expr("{}")
        assert isinstance(node, DictLiteral)
        assert node.entries == []

    def test_missing_colon_raises(self) -> None:
        """Missing ``:`` between key and value raises ParseError."""
        with pytest.raises(ParseError, match="Expected ':'"):
            _parse_expr('{"a" 1}')

    def test_missing_brace_raises(self) -> None:
        """Missing closing ``}`` raises ParseError."""
        with pytest.raises(ParseError, match="Expected '}'"):
            _parse_expr('{"a": 1')


# -- Cycle 3: Analyzer — scoping ---------------------------------------------


class TestAnalyzerDict:
    """Verify semantic analysis of dictionary expressions."""

    def test_undeclared_variable_in_value_raises(self) -> None:
        """Undeclared variable in dict value raises SemanticError."""
        with pytest.raises(SemanticError, match="Undeclared variable 'x'"):
            run_source('let d = {"a": x}')

    def test_outer_variable_visible_in_dict(self) -> None:
        """Variables from outer scope can be used in dict values."""
        output = run_source('let x = 42\nlet d = {"val": x}\nprint(d["val"])')
        assert output == "42\n"


# -- Cycle 4: Compiler — BUILD_DICT ------------------------------------------


class TestCompilerDict:
    """Verify BUILD_DICT opcode generation."""

    def test_single_entry_emits_build_dict_1(self) -> None:
        """``{"a": 1}`` emits BUILD_DICT with operand 1."""
        ins = compile_instructions('let d = {"a": 1}')
        build_ops = [i for i in ins if i.opcode is OpCode.BUILD_DICT]
        assert len(build_ops) == ONE
        assert build_ops[0].operand == ONE

    def test_empty_dict_emits_build_dict_0(self) -> None:
        """``{}`` emits BUILD_DICT with operand 0."""
        ins = compile_instructions("let d = {}")
        build_ops = [i for i in ins if i.opcode is OpCode.BUILD_DICT]
        assert len(build_ops) == ONE
        assert build_ops[0].operand == ZERO


# -- Cycle 5: VM + Builtins — execution --------------------------------------


class TestVMDictCreation:
    """Verify dictionary creation and printing."""

    def test_print_dict(self) -> None:
        """Print a simple dictionary."""
        output = run_source('print({"name": "Alice", "age": 12})')
        assert output == "{name: Alice, age: 12}\n"

    def test_print_empty_dict(self) -> None:
        """Print an empty dictionary."""
        assert run_source("print({})") == "{}\n"

    def test_dict_in_variable(self) -> None:
        """Store a dict in a variable and print it."""
        source = 'let d = {"x": 1}\nprint(d)'
        assert run_source(source) == "{x: 1}\n"


class TestVMDictAccess:
    """Verify dictionary key access."""

    def test_key_access(self) -> None:
        """Read a value by key."""
        source = 'let d = {"a": 10, "b": 20}\nprint(d["b"])'
        assert run_source(source) == "20\n"

    def test_missing_key_error(self) -> None:
        """Accessing a missing key raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="Key 'z' not found"):
            run_source('let d = {"a": 1}\nprint(d["z"])')


class TestVMDictAssignment:
    """Verify dictionary key assignment."""

    def test_modify_existing_key(self) -> None:
        """Reassigning an existing key updates the value."""
        source = 'let d = {"a": 1}\nd["a"] = 99\nprint(d["a"])'
        assert run_source(source) == "99\n"

    def test_add_new_key(self) -> None:
        """Assigning to a new key creates it (upsert)."""
        source = 'let d = {"a": 1}\nd["b"] = 2\nprint(d["b"])'
        assert run_source(source) == "2\n"


class TestVMDictBuiltins:
    """Verify built-in functions with dicts."""

    def test_len_of_dict(self) -> None:
        """``len()`` returns number of keys."""
        assert run_source('print(len({"a": 1, "b": 2}))') == "2\n"

    def test_len_of_empty_dict(self) -> None:
        """``len({})`` returns 0."""
        assert run_source("print(len({}))") == "0\n"

    def test_type_of_dict(self) -> None:
        """``type({})`` returns ``"dict"``."""
        assert run_source("print(type({}))") == "dict\n"

    def test_keys_builtin(self) -> None:
        """``keys(d)`` returns a list of keys."""
        source = 'let d = {"a": 1, "b": 2}\nprint(keys(d))'
        assert run_source(source) == "[a, b]\n"

    def test_values_builtin(self) -> None:
        """``values(d)`` returns a list of values."""
        source = 'let d = {"a": 1, "b": 2}\nprint(values(d))'
        assert run_source(source) == "[1, 2]\n"

    def test_keys_empty_dict(self) -> None:
        """``keys({})`` returns an empty list."""
        assert run_source("print(keys({}))") == "[]\n"

    def test_values_empty_dict(self) -> None:
        """``values({})`` returns an empty list."""
        assert run_source("print(values({}))") == "[]\n"


# -- Cycle 6: Integration ----------------------------------------------------


class TestDictIntegration:
    """End-to-end tests combining dicts with other features."""

    def test_dict_in_function(self) -> None:
        """Pass a dict to a function and read a key."""
        source = """\
fn get_name(d) { return d["name"] }
print(get_name({"name": "Bob"}))"""
        assert run_source(source) == "Bob\n"

    def test_nested_dicts(self) -> None:
        """Dict values can be dicts."""
        source = """\
let d = {"inner": {"x": 42}}
print(d["inner"]["x"])"""
        assert run_source(source) == "42\n"

    def test_dict_with_expression_values(self) -> None:
        """Dict values can be arbitrary expressions."""
        source = """\
let x = 10
let d = {"val": x + 5}
print(d["val"])"""
        assert run_source(source) == "15\n"

    def test_non_string_key_raises_runtime_error(self) -> None:
        """Using a non-string key raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="Dict keys must be strings"):
            run_source("let d = {}\nd[42] = 1")

    def test_dict_with_interpolation(self) -> None:
        """Use dict values in string interpolation."""
        source = """\
let d = {"name": "Alice"}
print("hello {d["name"]}")"""
        assert run_source(source) == "hello Alice\n"

    def test_dict_keys_preserves_insertion_order(self) -> None:
        """``keys()`` returns keys in insertion order."""
        source = """\
let d = {"z": 1, "a": 2, "m": 3}
print(keys(d))"""
        assert run_source(source) == "[z, a, m]\n"

    def test_dict_equality(self) -> None:
        """Dicts with same entries are equal."""
        source = """\
let a = {"x": 1}
let b = {"x": 1}
print(a == b)"""
        assert run_source(source) == "true\n"

    def test_non_string_key_in_literal_raises(self) -> None:
        """Using a non-string key in a literal raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="Dict keys must be strings"):
            run_source("let d = {42: 1}")
