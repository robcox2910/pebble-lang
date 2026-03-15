"""Tests for string & list methods with method-call syntax (Phase 18).

Cover lexer DOT token, parser MethodCall node, analyzer validation,
compiler CALL_METHOD bytecode, and VM execution of string methods.
"""

from io import StringIO

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import Expression, Identifier, IndexAccess, MethodCall, StringLiteral
from pebble.builtins import METHOD_NONE
from pebble.bytecode import Instruction, OpCode
from pebble.compiler import Compiler
from pebble.errors import PebbleRuntimeError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.tokens import TokenKind
from pebble.vm import VirtualMachine

# -- Named constants ----------------------------------------------------------

ONE = 1
TWO = 2
THREE = 3


# -- Helpers ------------------------------------------------------------------


def _kinds(source: str) -> list[TokenKind]:
    """Return just the token kinds for *source* (excluding EOF)."""
    tokens = Lexer(source).tokenize()
    return [t.kind for t in tokens if t.kind != TokenKind.EOF]


def _run_source(source: str) -> str:
    """Compile and run *source*, returning captured output."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzer = SemanticAnalyzer()
    analyzed = analyzer.analyze(program)
    compiled = Compiler(cell_vars=analyzer.cell_vars, free_vars=analyzer.free_vars).compile(
        analyzed
    )
    buf = StringIO()
    VirtualMachine(output=buf).run(compiled)
    return buf.getvalue()


def _parse_expr(source: str) -> Expression:
    """Lex and parse a single expression from *source*."""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse_expression()


def _compile_instructions(source: str) -> list[Instruction]:
    """Return the main instruction list for *source*."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzed = SemanticAnalyzer().analyze(program)
    return Compiler().compile(analyzed).main.instructions


# -- Cycle 1: Lexer — DOT token -----------------------------------------------


class TestLexerDot:
    """Verify ``.`` tokenizes as DOT."""

    def test_dot_token(self) -> None:
        """``.`` produces a DOT token."""
        assert _kinds(".") == [TokenKind.DOT]

    def test_identifier_dot_identifier(self) -> None:
        """``x.upper`` tokenizes to IDENTIFIER, DOT, IDENTIFIER."""
        assert _kinds("x.upper") == [
            TokenKind.IDENTIFIER,
            TokenKind.DOT,
            TokenKind.IDENTIFIER,
        ]

    def test_dot_with_parens(self) -> None:
        """``s.upper()`` includes DOT in the token stream."""
        kinds = _kinds("s.upper()")
        assert TokenKind.DOT in kinds


# -- Cycle 2: Parser — MethodCall node ----------------------------------------


class TestParserMethodCall:
    """Verify ``target.method(args)`` parses to a MethodCall node."""

    def test_no_args(self) -> None:
        """``s.upper()`` parses to MethodCall with 0 args."""
        node = _parse_expr("s.upper()")
        assert isinstance(node, MethodCall)
        assert node.method == "upper"
        assert node.arguments == []
        assert isinstance(node.target, Identifier)

    def test_one_arg(self) -> None:
        """``s.split(",")`` parses to MethodCall with 1 arg."""
        node = _parse_expr('s.split(",")')
        assert isinstance(node, MethodCall)
        assert node.method == "split"
        assert len(node.arguments) == ONE

    def test_two_args(self) -> None:
        """``s.replace("a", "b")`` parses to MethodCall with 2 args."""
        node = _parse_expr('s.replace("a", "b")')
        assert isinstance(node, MethodCall)
        assert node.method == "replace"
        assert len(node.arguments) == TWO

    def test_chaining(self) -> None:
        """``s.upper().lower()`` parses to nested MethodCall."""
        node = _parse_expr("s.upper().lower()")
        assert isinstance(node, MethodCall)
        assert node.method == "lower"
        assert isinstance(node.target, MethodCall)
        assert node.target.method == "upper"

    def test_on_string_literal(self) -> None:
        """``"hello".upper()`` parses to MethodCall on a StringLiteral."""
        node = _parse_expr('"hello".upper()')
        assert isinstance(node, MethodCall)
        assert isinstance(node.target, StringLiteral)
        assert node.method == "upper"

    def test_on_index_result(self) -> None:
        """``xs[0].upper()`` parses to MethodCall on an IndexAccess."""
        node = _parse_expr("xs[0].upper()")
        assert isinstance(node, MethodCall)
        assert isinstance(node.target, IndexAccess)


# -- Cycle 3: Analyzer — method call validation -------------------------------


class TestAnalyzerMethodCall:
    """Verify the analyzer validates method names and arities."""

    def test_unknown_method_error(self) -> None:
        """Calling an unknown method raises SemanticError."""
        with pytest.raises(SemanticError, match="Unknown method 'foo'"):
            _run_source('let s = "hello"\ns.foo()')

    def test_wrong_arity_error(self) -> None:
        """Wrong argument count raises SemanticError."""
        with pytest.raises(SemanticError, match="expects 0 arguments"):
            _run_source('let s = "hello"\ns.upper(1)')

    def test_split_zero_args_valid(self) -> None:
        """``split()`` with 0 args is valid (variable arity)."""
        # Should not raise — just needs to pass analysis
        tokens = Lexer('let s = "hello"\ns.split()').tokenize()
        program = Parser(tokens).parse()
        SemanticAnalyzer().analyze(program)

    def test_split_one_arg_valid(self) -> None:
        """``split(",")`` with 1 arg is valid."""
        tokens = Lexer('let s = "a,b"\ns.split(",")').tokenize()
        program = Parser(tokens).parse()
        SemanticAnalyzer().analyze(program)

    def test_undeclared_target_error(self) -> None:
        """Undeclared target variable raises SemanticError."""
        with pytest.raises(SemanticError, match="Undeclared variable 'unknown'"):
            _run_source("unknown.upper()")


# -- Cycle 4: Compiler — CALL_METHOD bytecode --------------------------------


class TestCompilerMethodCall:
    """Verify the compiler emits CALL_METHOD instructions."""

    def test_upper_emits_call_method(self) -> None:
        """``s.upper()`` emits a CALL_METHOD "upper" instruction."""
        ins = _compile_instructions('let s = "hello"\ns.upper()')
        method_ops = [i for i in ins if i.opcode is OpCode.CALL_METHOD]
        assert len(method_ops) == ONE
        assert method_ops[0].operand == "upper"

    def test_split_no_args_pads_sentinel(self) -> None:
        """``s.split()`` pads with METHOD_NONE sentinel before CALL_METHOD."""
        tokens = Lexer('let s = "hello"\ns.split()').tokenize()
        program = Parser(tokens).parse()
        analyzed = SemanticAnalyzer().analyze(program)
        compiled = Compiler().compile(analyzed)
        assert METHOD_NONE in compiled.main.constants


# -- Cycle 5: VM — string methods (12) ----------------------------------------


class TestStringUpper:
    """Verify ``upper()`` string method."""

    def test_basic(self) -> None:
        """``"hello".upper()`` returns "HELLO"."""
        assert _run_source('print("hello".upper())') == "HELLO\n"

    def test_empty(self) -> None:
        """``"".upper()`` returns ""."""
        assert _run_source('print("".upper())') == "\n"

    def test_already_upper(self) -> None:
        """``"ABC".upper()`` returns "ABC"."""
        assert _run_source('print("ABC".upper())') == "ABC\n"


class TestStringLower:
    """Verify ``lower()`` string method."""

    def test_basic(self) -> None:
        """``"HELLO".lower()`` returns "hello"."""
        assert _run_source('print("HELLO".lower())') == "hello\n"

    def test_empty(self) -> None:
        """``"".lower()`` returns ""."""
        assert _run_source('print("".lower())') == "\n"


class TestStringStrip:
    """Verify ``strip()`` string method."""

    def test_basic(self) -> None:
        """``"  hello  ".strip()`` returns "hello"."""
        assert _run_source('print("  hello  ".strip())') == "hello\n"

    def test_no_whitespace(self) -> None:
        """``"hello".strip()`` returns "hello"."""
        assert _run_source('print("hello".strip())') == "hello\n"


class TestStringSplit:
    """Verify ``split()`` string method."""

    def test_whitespace_default(self) -> None:
        """``"a b c".split()`` splits on whitespace."""
        assert _run_source('print("a b c".split())') == "[a, b, c]\n"

    def test_separator(self) -> None:
        """``"a,b,c".split(",")`` splits on comma."""
        assert _run_source('print("a,b,c".split(","))') == "[a, b, c]\n"

    def test_empty_separator_error(self) -> None:
        """``"abc".split("")`` raises a runtime error."""
        with pytest.raises(PebbleRuntimeError, match="cannot be empty"):
            _run_source('"abc".split("")')


class TestStringReplace:
    """Verify ``replace()`` string method."""

    def test_all_occurrences(self) -> None:
        """``"aabbcc".replace("b", "x")`` replaces all b's."""
        assert _run_source('print("aabbcc".replace("b", "x"))') == "aaxxcc\n"

    def test_no_match(self) -> None:
        """``"hello".replace("z", "x")`` returns "hello"."""
        assert _run_source('print("hello".replace("z", "x"))') == "hello\n"


class TestStringContains:
    """Verify ``contains()`` string method."""

    def test_found(self) -> None:
        """``"hello".contains("ell")`` returns true."""
        assert _run_source('print("hello".contains("ell"))') == "true\n"

    def test_not_found(self) -> None:
        """``"hello".contains("xyz")`` returns false."""
        assert _run_source('print("hello".contains("xyz"))') == "false\n"


class TestStringStartsWith:
    """Verify ``starts_with()`` string method."""

    def test_true(self) -> None:
        """``"hello".starts_with("hel")`` returns true."""
        assert _run_source('print("hello".starts_with("hel"))') == "true\n"

    def test_false(self) -> None:
        """``"hello".starts_with("xyz")`` returns false."""
        assert _run_source('print("hello".starts_with("xyz"))') == "false\n"


class TestStringEndsWith:
    """Verify ``ends_with()`` string method."""

    def test_true(self) -> None:
        """``"hello".ends_with("llo")`` returns true."""
        assert _run_source('print("hello".ends_with("llo"))') == "true\n"

    def test_false(self) -> None:
        """``"hello".ends_with("xyz")`` returns false."""
        assert _run_source('print("hello".ends_with("xyz"))') == "false\n"


class TestStringFind:
    """Verify ``find()`` string method."""

    def test_found(self) -> None:
        """``"hello".find("ll")`` returns 2."""
        assert _run_source('print("hello".find("ll"))') == "2\n"

    def test_not_found(self) -> None:
        """``"hello".find("xyz")`` returns -1."""
        assert _run_source('print("hello".find("xyz"))') == "-1\n"


class TestStringCount:
    """Verify ``count()`` string method."""

    def test_multiple(self) -> None:
        """``"banana".count("a")`` returns 3."""
        assert _run_source('print("banana".count("a"))') == "3\n"

    def test_none(self) -> None:
        """``"hello".count("z")`` returns 0."""
        assert _run_source('print("hello".count("z"))') == "0\n"


class TestStringJoin:
    """Verify ``join()`` string method."""

    def test_basic(self) -> None:
        """``", ".join(["a", "b", "c"])`` returns "a, b, c"."""
        assert _run_source('print(", ".join(["a", "b", "c"]))') == "a, b, c\n"

    def test_empty_separator(self) -> None:
        """``"".join(["a", "b"])`` returns "ab"."""
        assert _run_source('print("".join(["a", "b"]))') == "ab\n"

    def test_non_string_in_list_error(self) -> None:
        """``", ".join([1, 2])`` raises a runtime error."""
        with pytest.raises(PebbleRuntimeError, match="must contain strings"):
            _run_source('", ".join([1, 2])')


class TestStringRepeat:
    """Verify ``repeat()`` string method."""

    def test_basic(self) -> None:
        """``"ab".repeat(3)`` returns "ababab"."""
        assert _run_source('print("ab".repeat(3))') == "ababab\n"

    def test_zero(self) -> None:
        """``"ab".repeat(0)`` returns ""."""
        assert _run_source('print("ab".repeat(0))') == "\n"

    def test_negative_error(self) -> None:
        """``"ab".repeat(-1)`` raises a runtime error."""
        with pytest.raises(PebbleRuntimeError, match="must not be negative"):
            _run_source('"ab".repeat(-1)')


# -- Cycle 7: Integration tests -----------------------------------------------


class TestMethodIntegration:
    """End-to-end tests combining methods with other features."""

    def test_method_in_interpolation(self) -> None:
        """Method call inside string interpolation."""
        source = 'let s = "hello"\nprint("{s.upper()}")'
        assert _run_source(source) == "HELLO\n"

    def test_chaining(self) -> None:
        """Method chaining: strip then lower."""
        source = 'print("  HELLO  ".strip().lower())'
        assert _run_source(source) == "hello\n"

    def test_method_in_condition(self) -> None:
        """Use method result in an if condition."""
        source = """\
let s = "hello world"
if s.contains("world") {
    print("found it")
}"""
        assert _run_source(source) == "found it\n"

    def test_split_and_loop(self) -> None:
        """Split a string then loop over the parts."""
        source = """\
let parts = "a,b,c".split(",")
for i in range(len(parts)) {
    print(parts[i])
}"""
        assert _run_source(source) == "a\nb\nc\n"

    def test_join_after_split(self) -> None:
        """Split and rejoin produces the original string."""
        source = """\
let s = "a-b-c"
let parts = s.split("-")
let result = "-".join(parts)
print(result)"""
        assert _run_source(source) == "a-b-c\n"

    def test_contains_on_both_types(self) -> None:
        """``contains`` works on both strings and lists."""
        source = """\
let s = "hello"
let xs = [1, 2, 3]
print(s.contains("ell"))
print(xs.contains(2))"""
        assert _run_source(source) == "true\ntrue\n"

    def test_method_on_wrong_type(self) -> None:
        """Calling a string method on an int raises error."""
        with pytest.raises(PebbleRuntimeError, match="Cannot call methods on"):
            _run_source("let x = 42\nx.upper()")

    def test_string_method_on_list_error(self) -> None:
        """Calling ``upper()`` on a list raises error."""
        with pytest.raises(PebbleRuntimeError, match="has no method"):
            _run_source("let xs = [1]\nxs.upper()")

    def test_list_method_on_string_error(self) -> None:
        """Calling ``push()`` on a string raises error."""
        with pytest.raises(PebbleRuntimeError, match="has no method"):
            _run_source('let s = "hello"\ns.push("x")')

    def test_method_on_variable(self) -> None:
        """Method call on a variable (not a literal)."""
        source = 'let s = "hello world"\nprint(s.upper())'
        assert _run_source(source) == "HELLO WORLD\n"

    def test_method_result_in_assignment(self) -> None:
        """Store method result in a variable."""
        source = 'let s = "hello"\nlet u = s.upper()\nprint(u)'
        assert _run_source(source) == "HELLO\n"

    def test_method_in_function(self) -> None:
        """Use method inside a function."""
        source = """\
fn shout(s) {
    return s.upper()
}
print(shout("hello"))"""
        assert _run_source(source) == "HELLO\n"
