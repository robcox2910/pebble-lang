"""Tests for the Pebble linter.

Cover W001 (unused variable), W002 (naming conventions),
W003 (unreachable code), and W004 (empty block).
"""

from pebble.linter import Linter, LintWarning

# -- Named constants -----------------------------------------------------------

W001 = "W001"
W002 = "W002"
W003 = "W003"
W004 = "W004"
LINE_ONE = 1
LINE_TWO = 2
LINE_THREE = 3
LINE_FOUR = 4
LINE_FIVE = 5


# -- Linter scaffold -----------------------------------------------------------


class TestLinterScaffold:
    """Verify basic linter structure."""

    def test_lint_returns_list(self) -> None:
        """Linter returns a list of LintWarning objects."""
        result = Linter("let x = 42\nprint(x)").lint()
        assert isinstance(result, list)

    def test_no_warnings_for_clean_code(self) -> None:
        """No warnings for clean code."""
        assert Linter("let x = 42\nprint(x)").lint() == []

    def test_warning_has_code_and_line(self) -> None:
        """LintWarning has code, message, and line number."""
        warnings = Linter("let x = 42").lint()
        assert len(warnings) >= LINE_ONE
        w = warnings[0]
        assert isinstance(w, LintWarning)
        assert w.code == W001
        assert w.line >= LINE_ONE


# -- W001: Unused variable ----------------------------------------------------


class TestW001UnusedVariable:
    """Verify W001 — unused variable detection."""

    def test_unused_let_warned(self) -> None:
        """Warn for unused let variable."""
        warnings = Linter("let x = 42").lint()
        codes = [w.code for w in warnings]
        assert W001 in codes

    def test_unused_const_warned(self) -> None:
        """Warn for unused const variable."""
        warnings = Linter("const x = 42").lint()
        codes = [w.code for w in warnings]
        assert W001 in codes

    def test_used_variable_no_warning(self) -> None:
        """No warning for a variable used in an expression."""
        warnings = Linter("let x = 42\nprint(x)").lint()
        codes = [w.code for w in warnings]
        assert W001 not in codes

    def test_used_in_binary_op(self) -> None:
        """No warning when variable is used in a binary op."""
        warnings = Linter("let x = 1\nlet y = x + 2\nprint(y)").lint()
        codes = [w.code for w in warnings]
        assert W001 not in codes

    def test_loop_variable_used(self) -> None:
        """No warning when loop variable is used."""
        warnings = Linter("for i in range(10) { print(i) }").lint()
        codes = [w.code for w in warnings]
        assert W001 not in codes

    def test_loop_variable_unused(self) -> None:
        """Warn for unused loop variable."""
        warnings = Linter("for i in range(10) { print(42) }").lint()
        w001_warnings = [w for w in warnings if w.code == W001]
        names = [w.message for w in w001_warnings]
        assert any("i" in m for m in names)

    def test_function_params_not_warned(self) -> None:
        """Do not warn for unused function parameters."""
        source = "fn callback(x) { return 1 }\nlet r = callback(42)\nprint(r)"
        warnings = Linter(source).lint()
        w001_warnings = [w for w in warnings if w.code == W001]
        param_warnings = [w for w in w001_warnings if "'x'" in w.message]
        assert param_warnings == []

    def test_catch_variable_unused(self) -> None:
        """Warn for unused catch variable."""
        source = 'try { print(1) } catch e { print("error") }'
        warnings = Linter(source).lint()
        w001_warnings = [w for w in warnings if w.code == W001]
        assert any("'e'" in w.message for w in w001_warnings)

    def test_underscore_prefixed_not_warned(self) -> None:
        """Do not warn for _-prefixed variables."""
        warnings = Linter("let _x = 42").lint()
        w001_warnings = [w for w in warnings if w.code == W001]
        assert w001_warnings == []

    def test_function_name_not_warned(self) -> None:
        """Do not warn for function names defined but only called."""
        source = "fn greet() { print(42) }\ngreet()"
        warnings = Linter(source).lint()
        w001_warnings = [w for w in warnings if w.code == W001]
        assert w001_warnings == []

    def test_correct_line_number(self) -> None:
        """W001 reports the correct declaration line."""
        source = "let a = 1\nlet b = 2\nprint(a)"
        warnings = Linter(source).lint()
        w001 = [w for w in warnings if w.code == W001 and "'b'" in w.message]
        assert len(w001) == LINE_ONE
        assert w001[0].line == LINE_TWO


# -- W002: Naming conventions -------------------------------------------------


class TestW002NamingConventions:
    """Verify W002 — naming convention checks."""

    def test_snake_case_variable_ok(self) -> None:
        """No warning for snake_case variable."""
        warnings = Linter("let my_var = 42\nprint(my_var)").lint()
        w002 = [w for w in warnings if w.code == W002]
        assert w002 == []

    def test_camel_case_variable_warned(self) -> None:
        """Warn for camelCase variable."""
        warnings = Linter("let myVar = 42\nprint(myVar)").lint()
        w002 = [w for w in warnings if w.code == W002]
        assert len(w002) >= LINE_ONE

    def test_snake_case_function_ok(self) -> None:
        """No warning for snake_case function."""
        warnings = Linter("fn my_func() { return 1 }\nlet r = my_func()\nprint(r)").lint()
        w002 = [w for w in warnings if w.code == W002]
        assert w002 == []

    def test_camel_case_function_warned(self) -> None:
        """Warn for camelCase function."""
        warnings = Linter("fn myFunc() { return 1 }\nlet r = myFunc()\nprint(r)").lint()
        w002 = [w for w in warnings if w.code == W002]
        assert len(w002) >= LINE_ONE

    def test_pascal_case_class_ok(self) -> None:
        """No warning for PascalCase class."""
        source = "class MyClass { x\nfn get(self) { return self.x } }\nlet c = MyClass(1)\nprint(c.get())"
        warnings = Linter(source).lint()
        w002 = [w for w in warnings if w.code == W002]
        assert w002 == []

    def test_snake_case_class_warned(self) -> None:
        """Warn for snake_case class name."""
        source = "class my_class { x\nfn get(self) { return self.x } }\nlet c = my_class(1)\nprint(c.get())"
        warnings = Linter(source).lint()
        w002 = [w for w in warnings if w.code == W002]
        assert len(w002) >= LINE_ONE

    def test_pascal_case_struct_ok(self) -> None:
        """No warning for PascalCase struct."""
        source = "struct Point { x, y }\nlet p = Point(1, 2)\nprint(p.x)"
        warnings = Linter(source).lint()
        w002 = [w for w in warnings if w.code == W002]
        assert w002 == []

    def test_pascal_case_enum_ok(self) -> None:
        """No warning for PascalCase enum."""
        source = "enum Color { Red, Green, Blue }\nprint(Color.Red)"
        warnings = Linter(source).lint()
        w002 = [w for w in warnings if w.code == W002]
        assert w002 == []

    def test_underscore_prefixed_not_warned(self) -> None:
        """No warning for _-prefixed names."""
        warnings = Linter("let _camelCase = 42").lint()
        w002 = [w for w in warnings if w.code == W002]
        assert w002 == []

    def test_internal_anon_names_skipped(self) -> None:
        """Internal $anon_0 names are skipped."""
        source = "let f = fn(x) { return x + 1 }\nlet r = f(42)\nprint(r)"
        warnings = Linter(source).lint()
        w002 = [w for w in warnings if w.code == W002]
        anon_warnings = [w for w in w002 if "$anon" in w.message]
        assert anon_warnings == []


# -- W003: Unreachable code ----------------------------------------------------


class TestW003UnreachableCode:
    """Verify W003 — unreachable code detection."""

    def test_code_after_return(self) -> None:
        """Warn for code after return."""
        source = "fn foo() { return 1\nprint(42) }"
        warnings = Linter(source).lint()
        w003 = [w for w in warnings if w.code == W003]
        assert len(w003) >= LINE_ONE

    def test_code_after_break(self) -> None:
        """Warn for code after break."""
        source = "while true { break\nprint(42) }"
        warnings = Linter(source).lint()
        w003 = [w for w in warnings if w.code == W003]
        assert len(w003) >= LINE_ONE

    def test_code_after_continue(self) -> None:
        """Warn for code after continue."""
        source = "while true { continue\nprint(42) }"
        warnings = Linter(source).lint()
        w003 = [w for w in warnings if w.code == W003]
        assert len(w003) >= LINE_ONE

    def test_code_after_throw(self) -> None:
        """Warn for code after throw."""
        source = 'fn foo() { throw "err"\nprint(42) }'
        warnings = Linter(source).lint()
        w003 = [w for w in warnings if w.code == W003]
        assert len(w003) >= LINE_ONE

    def test_last_statement_return_ok(self) -> None:
        """No warning when return is the last statement."""
        source = "fn foo() { return 1 }\nlet r = foo()\nprint(r)"
        warnings = Linter(source).lint()
        w003 = [w for w in warnings if w.code == W003]
        assert w003 == []

    def test_return_in_if_branch_not_unreachable(self) -> None:
        """Code after if-with-return is NOT unreachable."""
        source = "fn foo(x) {\nif x { return 1 }\nreturn 2 }\nprint(foo(true))"
        warnings = Linter(source).lint()
        w003 = [w for w in warnings if w.code == W003]
        assert w003 == []


# -- W004: Empty block ---------------------------------------------------------


class TestW004EmptyBlock:
    """Verify W004 — empty block detection."""

    def test_empty_if_body(self) -> None:
        """Warn for empty if body."""
        source = "if true { }"
        warnings = Linter(source).lint()
        w004 = [w for w in warnings if w.code == W004]
        assert len(w004) >= LINE_ONE

    def test_empty_while_body(self) -> None:
        """Warn for empty while body."""
        source = "while false { }"
        warnings = Linter(source).lint()
        w004 = [w for w in warnings if w.code == W004]
        assert len(w004) >= LINE_ONE

    def test_empty_for_body(self) -> None:
        """Warn for empty for body."""
        source = "for i in range(10) { }"
        warnings = Linter(source).lint()
        w004 = [w for w in warnings if w.code == W004]
        assert len(w004) >= LINE_ONE

    def test_empty_function_body(self) -> None:
        """Warn for empty function body."""
        source = "fn noop() { }"
        warnings = Linter(source).lint()
        w004 = [w for w in warnings if w.code == W004]
        assert len(w004) >= LINE_ONE

    def test_empty_catch_body(self) -> None:
        """Warn for empty catch body."""
        source = "try { print(1) } catch e { }"
        warnings = Linter(source).lint()
        w004 = [w for w in warnings if w.code == W004]
        assert len(w004) >= LINE_ONE

    def test_non_empty_blocks_ok(self) -> None:
        """No warning for non-empty blocks."""
        source = "if true { print(1) }\nwhile false { print(2) }"
        warnings = Linter(source).lint()
        w004 = [w for w in warnings if w.code == W004]
        assert w004 == []

    def test_empty_else_body(self) -> None:
        """Warn for empty else body."""
        source = "if true { print(1) } else { }"
        warnings = Linter(source).lint()
        w004 = [w for w in warnings if w.code == W004]
        assert len(w004) >= LINE_ONE

    def test_empty_try_body(self) -> None:
        """Warn for empty try body."""
        source = "try { } catch e { print(e) }"
        warnings = Linter(source).lint()
        w004 = [w for w in warnings if w.code == W004]
        assert len(w004) >= LINE_ONE
