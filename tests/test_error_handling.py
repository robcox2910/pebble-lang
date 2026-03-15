"""Tests for error handling: try/catch/finally and throw."""

from io import StringIO

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import (
    IntegerLiteral,
    StringLiteral,
    ThrowStatement,
    TryCatch,
)
from pebble.bytecode import OpCode
from pebble.compiler import Compiler
from pebble.errors import ParseError, PebbleRuntimeError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.vm import VirtualMachine

# -- Named constants ----------------------------------------------------------

THROWN_INT = 42

# -- Helpers ------------------------------------------------------------------


def _parse(source: str) -> list[object]:
    """Lex + parse helper returning the statement list."""
    tokens = Lexer(source).tokenize()
    return list(Parser(tokens).parse().statements)


def _analyze(source: str) -> None:
    """Lex + parse + analyze helper — raises on semantic errors."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    SemanticAnalyzer().analyze(program)


def _compile(source: str) -> list[OpCode]:
    """Lex + parse + analyze + compile, return main opcode list."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzer = SemanticAnalyzer()
    program = analyzer.analyze(program)
    compiled = Compiler(
        cell_vars=analyzer.cell_vars,
        free_vars=analyzer.free_vars,
    ).compile(program)
    return [instr.opcode for instr in compiled.main.instructions]


def _run(source: str) -> str:
    """Lex + parse + analyze + compile + run, return captured output."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    analyzer = SemanticAnalyzer()
    program = analyzer.analyze(program)
    compiled = Compiler(
        cell_vars=analyzer.cell_vars,
        free_vars=analyzer.free_vars,
    ).compile(program)
    output = StringIO()
    VirtualMachine(output=output).run(compiled)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Cycle 2: AST + Parser
# ---------------------------------------------------------------------------


class TestParseTryCatch:
    """Verify try/catch/finally parsing produces the correct AST nodes."""

    def test_try_catch_basic(self) -> None:
        """Parse ``try { x } catch e { y }`` into a TryCatch node."""
        stmts = _parse("try {\n  let x = 1\n} catch e {\n  let y = 2\n}\n")
        assert len(stmts) == 1
        node = stmts[0]
        assert isinstance(node, TryCatch)
        assert len(node.body) == 1
        assert node.catch_variable == "e"
        assert len(node.catch_body) == 1
        assert node.finally_body is None

    def test_try_catch_no_variable(self) -> None:
        """Parse ``try { x } catch { y }`` with no catch variable."""
        stmts = _parse("try {\n  let x = 1\n} catch {\n  let y = 2\n}\n")
        node = stmts[0]
        assert isinstance(node, TryCatch)
        assert node.catch_variable is None

    def test_try_catch_finally(self) -> None:
        """Parse ``try { x } catch e { y } finally { z }``."""
        source = "try {\n  let x = 1\n} catch e {\n  let y = 2\n} finally {\n  let z = 3\n}\n"
        stmts = _parse(source)
        node = stmts[0]
        assert isinstance(node, TryCatch)
        assert node.catch_variable == "e"
        assert node.finally_body is not None
        assert len(node.finally_body) == 1

    def test_try_without_catch_raises_parse_error(self) -> None:
        """Missing catch after try raises ParseError."""
        with pytest.raises(ParseError, match="Expected 'catch'"):
            _parse("try {\n  let x = 1\n}\n")

    def test_try_catch_missing_brace_raises_parse_error(self) -> None:
        """Missing '{' after catch raises ParseError."""
        with pytest.raises(ParseError):
            _parse("try {\n  let x = 1\n} catch e\n")

    def test_try_catch_has_location(self) -> None:
        """TryCatch node preserves the 'try' token location."""
        stmts = _parse("try {\n  let x = 1\n} catch e {\n  let y = 2\n}\n")
        node = stmts[0]
        assert isinstance(node, TryCatch)
        assert node.location.line == 1
        assert node.location.column == 1


class TestParseThrow:
    """Verify throw statement parsing produces ThrowStatement nodes."""

    def test_throw_string(self) -> None:
        """Parse ``throw "error"`` into a ThrowStatement."""
        stmts = _parse('throw "error"\n')
        assert len(stmts) == 1
        node = stmts[0]
        assert isinstance(node, ThrowStatement)
        assert isinstance(node.value, StringLiteral)
        assert node.value.value == "error"

    def test_throw_integer(self) -> None:
        """Parse ``throw 42`` into a ThrowStatement with integer expression."""
        stmts = _parse("throw 42\n")
        node = stmts[0]
        assert isinstance(node, ThrowStatement)
        assert isinstance(node.value, IntegerLiteral)
        assert node.value.value == THROWN_INT

    def test_throw_has_location(self) -> None:
        """ThrowStatement node preserves the 'throw' token location."""
        stmts = _parse('throw "err"\n')
        node = stmts[0]
        assert isinstance(node, ThrowStatement)
        assert node.location.line == 1


# ---------------------------------------------------------------------------
# Cycle 3: Analyzer
# ---------------------------------------------------------------------------


class TestAnalyzeTryCatch:
    """Verify semantic analysis of try/catch/finally and throw."""

    def test_catch_variable_in_scope(self) -> None:
        """Catch variable is accessible inside the catch body."""
        _analyze("try {\n  let x = 1\n} catch e {\n  print(e)\n}\n")

    def test_catch_variable_not_in_outer_scope(self) -> None:
        """Catch variable is NOT accessible after the catch block."""
        with pytest.raises(SemanticError, match="Undeclared variable 'e'"):
            _analyze("try {\n  let x = 1\n} catch e {\n  print(e)\n}\nprint(e)\n")

    def test_throw_undeclared_variable_raises_error(self) -> None:
        """Throw expression with undeclared variable raises SemanticError."""
        with pytest.raises(SemanticError, match="Undeclared variable 'oops'"):
            _analyze("throw oops\n")

    def test_try_catch_inside_function(self) -> None:
        """Try/catch inside a function body is valid."""
        _analyze("fn safe() {\n  try {\n    let x = 1\n  } catch e {\n    print(e)\n  }\n}\n")

    def test_nested_try_blocks(self) -> None:
        """Nested try/catch blocks are valid."""
        source = (
            "try {\n"
            "  try {\n"
            "    let x = 1\n"
            "  } catch inner {\n"
            "    print(inner)\n"
            "  }\n"
            "} catch outer {\n"
            "  print(outer)\n"
            "}\n"
        )
        _analyze(source)

    def test_throw_string_literal(self) -> None:
        """Throw with a string literal passes analysis."""
        _analyze('throw "error"\n')

    def test_finally_body_analyzed(self) -> None:
        """Finally body with undeclared variable raises SemanticError."""
        with pytest.raises(SemanticError, match="Undeclared variable 'z'"):
            _analyze("try {\n  let x = 1\n} catch e {\n  print(e)\n} finally {\n  print(z)\n}\n")


# ---------------------------------------------------------------------------
# Cycle 4: Bytecode + Compiler
# ---------------------------------------------------------------------------


class TestCompileTryCatch:
    """Verify the compiler emits correct opcodes for try/catch/throw."""

    def test_try_catch_emits_setup_and_pop(self) -> None:
        """``try { } catch e { }`` emits SETUP_TRY and POP_TRY."""
        opcodes = _compile("try {\n  let x = 1\n} catch e {\n  let y = 2\n}\n")
        assert OpCode.SETUP_TRY in opcodes
        assert OpCode.POP_TRY in opcodes

    def test_throw_emits_throw_opcode(self) -> None:
        """``throw "err"`` emits LOAD_CONST + THROW."""
        opcodes = _compile('throw "err"\n')
        assert OpCode.LOAD_CONST in opcodes
        assert OpCode.THROW in opcodes

    def test_catch_without_variable_emits_pop(self) -> None:
        """``catch { }`` without variable emits POP to discard exception."""
        opcodes = _compile("try {\n  let x = 1\n} catch {\n  let y = 2\n}\n")
        # After SETUP_TRY section, there should be a POP for the discarded exception
        assert OpCode.POP in opcodes

    def test_catch_with_variable_emits_store(self) -> None:
        """``catch e { }`` with variable emits STORE_NAME for the exception."""
        opcodes = _compile("try {\n  let x = 1\n} catch e {\n  print(e)\n}\n")
        assert OpCode.STORE_NAME in opcodes

    def test_break_inside_try_emits_pop_try(self) -> None:
        """Emit POP_TRY before JUMP for break inside try in a loop."""
        source = "while true {\n  try {\n    break\n  } catch e {\n    let y = 1\n  }\n}\n"
        opcodes = _compile(source)
        # Should have POP_TRY before the break's JUMP
        pop_try_indices = [i for i, op in enumerate(opcodes) if op is OpCode.POP_TRY]
        assert len(pop_try_indices) >= 1

    def test_continue_inside_try_emits_pop_try(self) -> None:
        """Emit POP_TRY before JUMP for continue inside try in a loop."""
        source = "while true {\n  try {\n    continue\n  } catch e {\n    let y = 1\n  }\n}\n"
        opcodes = _compile(source)
        pop_try_indices = [i for i, op in enumerate(opcodes) if op is OpCode.POP_TRY]
        assert len(pop_try_indices) >= 1

    def test_return_inside_try_emits_pop_try(self) -> None:
        """Emit POP_TRY before RETURN for return inside try in a function."""
        source = "fn f() {\n  try {\n    return 1\n  } catch e {\n    return 2\n  }\n}\n"
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        program = analyzer.analyze(program)
        compiled = Compiler(
            cell_vars=analyzer.cell_vars,
            free_vars=analyzer.free_vars,
        ).compile(program)
        fn_opcodes = [instr.opcode for instr in compiled.functions["f"].instructions]
        pop_try_indices = [i for i, op in enumerate(fn_opcodes) if op is OpCode.POP_TRY]
        assert len(pop_try_indices) >= 1

    def test_break_outside_try_no_extra_pop_try(self) -> None:
        """No extra POP_TRY for break in loop around try (not inside try)."""
        source = (
            "while true {\n  try {\n    let x = 1\n  } catch e {\n    let y = 2\n  }\n  break\n}\n"
        )
        opcodes = _compile(source)
        # The POP_TRY in the try block is the only one (normal exit)
        # break after the try block should NOT emit POP_TRY
        # Find position of the break's JUMP - it's the last JUMP before the final patch
        pop_try_indices = [i for i, op in enumerate(opcodes) if op is OpCode.POP_TRY]
        # Only one POP_TRY from the try block's normal exit
        assert len(pop_try_indices) == 1


# ---------------------------------------------------------------------------
# Cycle 5: VM — throw/catch basics
# ---------------------------------------------------------------------------


class TestVMThrowCatch:
    """Verify throw/catch execution in the VM."""

    def test_throw_without_try_raises_runtime_error(self) -> None:
        """Bare ``throw "error"`` without try raises PebbleRuntimeError."""
        with pytest.raises(PebbleRuntimeError, match="error"):
            _run('throw "error"\n')

    def test_try_catch_prints_thrown_value(self) -> None:
        """Thrown string caught and printed via catch variable."""
        output = _run('try {\n  throw "oops"\n} catch e {\n  print(e)\n}\n')
        assert output.strip() == "oops"

    def test_try_catch_integer_value(self) -> None:
        """Thrown integer caught and printed."""
        output = _run("try {\n  throw 42\n} catch e {\n  print(e)\n}\n")
        assert output.strip() == "42"

    def test_try_safe_code_catch_not_executed(self) -> None:
        """When try body succeeds, catch body is NOT executed."""
        output = _run('try {\n  print("ok")\n} catch e {\n  print("caught")\n}\n')
        assert output.strip() == "ok"

    def test_try_catch_no_variable(self) -> None:
        """Catch without variable discards the exception."""
        output = _run('try {\n  throw "x"\n} catch {\n  print("caught")\n}\n')
        assert output.strip() == "caught"

    def test_throw_in_function_caught_by_caller(self) -> None:
        """Exception thrown inside a function is caught by caller's try/catch."""
        source = 'fn boom() {\n  throw "bang"\n}\ntry {\n  boom()\n} catch e {\n  print(e)\n}\n'
        output = _run(source)
        assert output.strip() == "bang"


# ---------------------------------------------------------------------------
# Cycle 6: VM — catching runtime errors
# ---------------------------------------------------------------------------


class TestVMCatchRuntimeErrors:
    """Verify that built-in runtime errors are caught by try/catch."""

    def test_division_by_zero_caught(self) -> None:
        """Division by zero caught in try/catch."""
        output = _run("try {\n  let x = 1 / 0\n} catch e {\n  print(e)\n}\n")
        assert "Division by zero" in output

    def test_index_out_of_bounds_caught(self) -> None:
        """Index out of bounds caught in try/catch."""
        source = "let xs = [1, 2, 3]\ntry {\n  let v = xs[99]\n} catch e {\n  print(e)\n}\n"
        output = _run(source)
        assert "out of bounds" in output

    def test_type_error_caught(self) -> None:
        """Type error caught in try/catch."""
        output = _run('try {\n  let x = 1 + "a"\n} catch e {\n  print(e)\n}\n')
        assert "Unsupported" in output


# ---------------------------------------------------------------------------
# Cycle 7: VM — finally + nested + loops
# ---------------------------------------------------------------------------


class TestVMFinallyAndNested:
    """Verify finally, nested try, and try inside loops."""

    def test_finally_runs_after_normal_try(self) -> None:
        """Finally runs after normal try completion."""
        output = _run(
            'try {\n  print("try")\n} catch e {\n  print("catch")\n}'
            ' finally {\n  print("finally")\n}\n'
        )
        lines = output.strip().split("\n")
        assert lines == ["try", "finally"]

    def test_finally_runs_after_catch(self) -> None:
        """Finally runs after catch execution."""
        output = _run(
            'try {\n  throw "err"\n} catch e {\n  print("catch")\n}'
            ' finally {\n  print("finally")\n}\n'
        )
        lines = output.strip().split("\n")
        assert lines == ["catch", "finally"]

    def test_nested_try_inner_catch(self) -> None:
        """Inner throw caught by inner catch, outer catch untouched."""
        source = (
            "try {\n"
            '  try {\n    throw "inner"\n  } catch e {\n    print(e)\n  }\n'
            '  print("outer ok")\n'
            '} catch e {\n  print("outer catch")\n}\n'
        )
        output = _run(source)
        lines = output.strip().split("\n")
        assert lines == ["inner", "outer ok"]

    def test_nested_try_rethrow(self) -> None:
        """Inner catch re-throws and outer catch catches it."""
        source = (
            "try {\n"
            '  try {\n    throw "deep"\n  } catch e {\n    throw "rethrown"\n  }\n'
            "} catch e {\n  print(e)\n}\n"
        )
        output = _run(source)
        assert output.strip() == "rethrown"

    def test_break_inside_try_in_loop(self) -> None:
        """Break inside try/catch inside a loop exits the loop."""
        source = (
            "let count = 0\n"
            "while true {\n"
            "  try {\n"
            "    break\n"
            "  } catch e {\n"
            '    print("caught")\n'
            "  }\n"
            "  count = count + 1\n"
            "}\n"
            "print(count)\n"
        )
        output = _run(source)
        assert output.strip() == "0"

    def test_continue_inside_try_in_loop(self) -> None:
        """Continue inside try/catch in a loop skips rest of body."""
        source = (
            "let total = 0\n"
            "for i in range(3) {\n"
            "  try {\n"
            "    continue\n"
            "  } catch e {\n"
            '    print("caught")\n'
            "  }\n"
            "  total = total + 1\n"
            "}\n"
            "print(total)\n"
        )
        output = _run(source)
        assert output.strip() == "0"

    def test_return_inside_try(self) -> None:
        """Return inside try pops handler and returns from function."""
        source = (
            'fn f() {\n  try {\n    return "early"\n  } catch e {\n    return "caught"\n  }\n}\n'
            "print(f())\n"
        )
        output = _run(source)
        assert output.strip() == "early"

    def test_try_in_for_loop_multiple_iterations(self) -> None:
        """Each iteration of a for loop gets a fresh handler."""
        source = (
            "for i in range(3) {\n"
            "  try {\n"
            "    if i == 1 {\n"
            '      throw "err"\n'
            "    }\n"
            "    print(i)\n"
            "  } catch e {\n"
            '    print("caught")\n'
            "  }\n"
            "}\n"
        )
        output = _run(source)
        lines = output.strip().split("\n")
        assert lines == ["0", "caught", "2"]


# ---------------------------------------------------------------------------
# Cycle 8: Integration
# ---------------------------------------------------------------------------


class TestVMIntegration:
    """Integration tests for error handling with other features."""

    def test_error_in_string_interpolation(self) -> None:
        """Caught error value used in string interpolation."""
        source = 'try {\n  throw "bad"\n} catch e {\n  print("caught: {e}")\n}\n'
        output = _run(source)
        assert output.strip() == "caught: bad"

    def test_catch_convert_continue(self) -> None:
        """Catch an error, convert to a default, and continue."""
        source = (
            "fn safe_div(a, b) {\n"
            "  try {\n"
            "    return a / b\n"
            "  } catch e {\n"
            "    return 0\n"
            "  }\n"
            "}\n"
            "print(safe_div(10, 2))\n"
            "print(safe_div(10, 0))\n"
        )
        output = _run(source)
        lines = output.strip().split("\n")
        assert lines == ["5", "0"]

    def test_throw_from_deeply_nested_calls(self) -> None:
        """Exception propagates through multiple function call levels."""
        source = (
            'fn a() {\n  throw "deep"\n}\n'
            "fn b() {\n  a()\n}\n"
            "fn c() {\n  b()\n}\n"
            "try {\n  c()\n} catch e {\n  print(e)\n}\n"
        )
        output = _run(source)
        assert output.strip() == "deep"

    def test_try_catch_around_map_with_throwing_callback(self) -> None:
        """try/catch around map where callback throws."""
        source = (
            "fn maybe_double(x) {\n"
            '  if x == 2 {\n    throw "bad value"\n  }\n'
            "  return x * 2\n"
            "}\n"
            "try {\n"
            "  let result = map(maybe_double, [1, 2, 3])\n"
            "  print(result)\n"
            "} catch e {\n  print(e)\n}\n"
        )
        output = _run(source)
        assert output.strip() == "bad value"

    def test_validate_or_default_pattern(self) -> None:
        """Validate-or-default pattern using try/catch."""
        source = (
            "fn get_item(xs, i) {\n"
            "  try {\n"
            "    return xs[i]\n"
            "  } catch e {\n"
            "    return -1\n"
            "  }\n"
            "}\n"
            "let xs = [10, 20, 30]\n"
            "print(get_item(xs, 1))\n"
            "print(get_item(xs, 99))\n"
        )
        output = _run(source)
        lines = output.strip().split("\n")
        assert lines == ["20", "-1"]
