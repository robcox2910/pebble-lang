"""Tests for the Pebble semantic analyzer.

Cover variable scoping, block scoping, function definitions, function calls,
return statements, for loops, and multi-feature integration scenarios.
"""

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import Program
from pebble.errors import ParseError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser

# -- Named constants ----------------------------------------------------------

ONE = 1
TWO = 2


# -- Helpers ------------------------------------------------------------------


def _analyze(source: str) -> Program:
    """Lex, parse, and analyze *source*, returning the Program AST."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    return SemanticAnalyzer().analyze(program)


# -- Variable scope -----------------------------------------------------------


class TestVariableScope:
    """Verify variable declaration and resolution rules."""

    def test_declared_variable_is_visible(self) -> None:
        """Pass when a declared variable is used later."""
        _analyze("let x = 5\nprint(x)")

    def test_undeclared_variable_raises(self) -> None:
        """Raise SemanticError for use of an undeclared variable."""
        with pytest.raises(SemanticError, match="Undeclared variable 'x'"):
            _analyze("print(x)")

    def test_duplicate_declaration_raises(self) -> None:
        """Raise SemanticError when re-declaring a variable in the same scope."""
        with pytest.raises(SemanticError, match="Variable 'x' already declared"):
            _analyze("let x = 1\nlet x = 2")

    def test_reassignment_of_declared_variable(self) -> None:
        """Pass when reassigning a previously declared variable."""
        _analyze("let x = 1\nx = 2")

    def test_reassignment_of_undeclared_variable_raises(self) -> None:
        """Raise SemanticError when reassigning an undeclared variable."""
        with pytest.raises(SemanticError, match="Undeclared variable 'x'"):
            _analyze("x = 5")

    def test_variable_used_in_declaration(self) -> None:
        """Pass when a declared variable is used in a later declaration."""
        _analyze("let a = 1\nlet b = a")

    def test_self_referencing_declaration_raises(self) -> None:
        """Raise SemanticError when a variable references itself in its initializer."""
        with pytest.raises(SemanticError, match="Undeclared variable 'x'"):
            _analyze("let x = x")


# -- Block scoping ------------------------------------------------------------


class TestBlockScoping:
    """Verify that blocks introduce new scopes and variable visibility."""

    def test_variable_in_if_body_not_visible_after(self) -> None:
        """Raise SemanticError for a variable declared in an if body used after."""
        with pytest.raises(SemanticError, match="Undeclared variable 'x'"):
            _analyze("if true {\n  let x = 1\n}\nprint(x)")

    def test_variable_in_else_body_not_visible_after(self) -> None:
        """Raise SemanticError for a variable declared in an else body used after."""
        with pytest.raises(SemanticError, match="Undeclared variable 'y'"):
            _analyze("if true {\n  print(1)\n} else {\n  let y = 2\n}\nprint(y)")

    def test_variable_in_while_body_not_visible_after(self) -> None:
        """Raise SemanticError for a variable declared in a while body used after."""
        with pytest.raises(SemanticError, match="Undeclared variable 'w'"):
            _analyze("while false {\n  let w = 1\n}\nprint(w)")

    def test_outer_variable_visible_in_block(self) -> None:
        """Pass when a variable declared before a block is used inside it."""
        _analyze("let x = 10\nif true {\n  print(x)\n}")

    def test_nested_blocks_see_outer_variables(self) -> None:
        """Pass when a nested block uses a variable from an outer scope."""
        _analyze("let x = 1\nif true {\n  if true {\n    print(x)\n  }\n}")

    def test_inner_scope_can_shadow_outer(self) -> None:
        """Pass when an inner scope re-declares a variable from an outer scope."""
        _analyze("let x = 1\nif true {\n  let x = 2\n  print(x)\n}")

    def test_sibling_blocks_reuse_same_name(self) -> None:
        """Pass when sibling blocks each declare a variable with the same name."""
        _analyze(
            "if true {\n  let x = 1\n}\nif true {\n  let x = 2\n}"
        )


# -- Function definitions ----------------------------------------------------


class TestFunctionDef:
    """Verify function declaration and parameter scoping."""

    def test_simple_function(self) -> None:
        """Pass for a valid no-parameter function."""
        _analyze('fn greet() {\n  print("hi")\n}')

    def test_duplicate_function_raises(self) -> None:
        """Raise SemanticError when re-declaring a function in the same scope."""
        with pytest.raises(SemanticError, match="Function 'greet' already defined"):
            _analyze('fn greet() {\n  print("hi")\n}\nfn greet() {\n  print("bye")\n}')

    def test_parameters_visible_in_body(self) -> None:
        """Pass when function parameters are used in the body."""
        _analyze("fn add(a, b) {\n  return a + b\n}")

    def test_parameter_used_in_expression(self) -> None:
        """Pass when a parameter is used in an expression inside the body."""
        _analyze("fn f(x) {\n  let y = x + 1\n}")

    def test_parameter_not_visible_outside(self) -> None:
        """Raise SemanticError when a parameter is used outside the function."""
        with pytest.raises(SemanticError, match="Undeclared variable 'a'"):
            _analyze("fn f(a) {\n  print(a)\n}\nprint(a)")

    def test_nested_function_sees_outer_variables(self) -> None:
        """Pass when a function body references a variable from the enclosing scope."""
        _analyze("let x = 1\nfn f() {\n  print(x)\n}")


# -- Return statements -------------------------------------------------------


class TestReturnStatement:
    """Verify return statement placement rules."""

    def test_return_outside_function_raises(self) -> None:
        """Raise SemanticError for a return statement at the top level."""
        with pytest.raises(SemanticError, match="Return statement outside function"):
            _analyze("return 42")

    def test_return_inside_function(self) -> None:
        """Pass for a return statement inside a function."""
        _analyze("fn f() {\n  return 42\n}")

    def test_bare_return_inside_function(self) -> None:
        """Pass for a bare return statement inside a function."""
        _analyze("fn f() {\n  return\n}")

    def test_return_in_nested_block_inside_function(self) -> None:
        """Pass for a return statement inside a nested block within a function."""
        _analyze("fn f() {\n  if true {\n    return 1\n  }\n}")


# -- Function calls -----------------------------------------------------------


class TestFunctionCall:
    """Verify function call resolution and arity checking."""

    def test_call_declared_function(self) -> None:
        """Pass when calling a previously declared function."""
        _analyze("fn greet() {\n  print(1)\n}\ngreet()")

    def test_call_undeclared_function_raises(self) -> None:
        """Raise SemanticError when calling an undeclared function."""
        with pytest.raises(SemanticError, match="Undeclared function 'foo'"):
            _analyze("foo()")

    def test_too_few_arguments_raises(self) -> None:
        """Raise SemanticError when calling with too few arguments."""
        with pytest.raises(
            SemanticError,
            match="Function 'add' expects 2 arguments, got 1",
        ):
            _analyze("fn add(a, b) {\n  return a + b\n}\nadd(1)")

    def test_too_many_arguments_raises(self) -> None:
        """Raise SemanticError when calling with too many arguments."""
        with pytest.raises(
            SemanticError,
            match="Function 'add' expects 2 arguments, got 3",
        ):
            _analyze("fn add(a, b) {\n  return a + b\n}\nadd(1, 2, 3)")

    def test_print_builtin_succeeds(self) -> None:
        """Pass when calling the built-in print with one argument."""
        _analyze("print(42)")

    def test_print_wrong_arity_raises_at_parse_time(self) -> None:
        """Raise ParseError when calling print with no argument (parser enforces this)."""
        with pytest.raises(ParseError):
            _analyze("print()")

    def test_argument_with_undeclared_variable_raises(self) -> None:
        """Raise SemanticError when an argument references an undeclared variable."""
        with pytest.raises(SemanticError, match="Undeclared variable 'x'"):
            _analyze("fn f(a) {\n  return a\n}\nf(x)")

    def test_function_declared_after_call_raises(self) -> None:
        """Raise SemanticError when a function is called before its declaration."""
        with pytest.raises(SemanticError, match="Undeclared function 'f'"):
            _analyze("f()\nfn f() {\n  print(1)\n}")


# -- For loops ----------------------------------------------------------------


class TestForLoop:
    """Verify for-loop variable scoping and iterable checking."""

    def test_loop_variable_visible_in_body(self) -> None:
        """Pass when the loop variable is used inside the body."""
        _analyze("for i in range(10) {\n  print(i)\n}")

    def test_undeclared_iterable_raises(self) -> None:
        """Raise SemanticError when the iterable is an undeclared variable."""
        with pytest.raises(SemanticError, match="Undeclared variable 'items'"):
            _analyze("for i in items {\n  print(i)\n}")

    def test_loop_variable_not_visible_after(self) -> None:
        """Raise SemanticError when the loop variable is used after the loop."""
        with pytest.raises(SemanticError, match="Undeclared variable 'i'"):
            _analyze("for i in range(5) {\n  print(i)\n}\nprint(i)")

    def test_inner_variable_not_visible_after(self) -> None:
        """Raise SemanticError for a variable declared in the loop body used after."""
        with pytest.raises(SemanticError, match="Undeclared variable 'x'"):
            _analyze("for i in range(5) {\n  let x = i\n}\nprint(x)")

    def test_loop_variable_shadows_outer(self) -> None:
        """Pass when a loop variable shadows an outer variable."""
        _analyze("let i = 99\nfor i in range(5) {\n  print(i)\n}")


# -- Integration tests -------------------------------------------------------


class TestAnalyzerIntegration:
    """Verify multi-feature programs pass or fail as expected."""

    def test_full_program(self) -> None:
        """Pass for a program using declarations, calls, loops, and conditionals."""
        _analyze(
            "let count = 0\n"
            "fn greet(name) {\n"
            "  print(name)\n"
            "}\n"
            "for i in range(3) {\n"
            "  if true {\n"
            "    count = count + 1\n"
            "  }\n"
            "}\n"
            'greet("hello")\n'
        )

    def test_function_calling_another_function(self) -> None:
        """Pass when one function calls another previously declared function."""
        _analyze(
            "fn double(x) {\n"
            "  return x + x\n"
            "}\n"
            "fn apply(n) {\n"
            "  return double(n)\n"
            "}\n"
            "print(apply(5))\n"  # expression statement with function call as arg
        )

    def test_for_inside_function(self) -> None:
        """Pass for a for loop inside a function body."""
        _analyze(
            "fn sum_range(n) {\n"
            "  let total = 0\n"
            "  for i in range(n) {\n"
            "    total = total + i\n"
            "  }\n"
            "  return total\n"
            "}\n"
        )

    def test_analyze_returns_program(self) -> None:
        """Verify that analyze returns the original Program AST unchanged."""
        program = _analyze("let x = 1\nprint(x)")
        assert isinstance(program, Program)
        assert len(program.statements) == TWO
