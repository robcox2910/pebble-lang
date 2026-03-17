"""Tests for operator overloading via dunder methods on classes."""

from io import StringIO

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.errors import SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.repl import Repl
from tests.conftest import run_source

# -- Named constants ----------------------------------------------------------

BINARY_DUNDER_ARITY = 2
UNARY_DUNDER_ARITY = 1
STR_DUNDER_ARITY = 1
WRONG_ARITY_THREE = 3

# -- Shared class sources -----------------------------------------------------

VECTOR_CLASS = """\
class Vector {
    x, y,

    fn __add__(self, other) -> Vector {
        return Vector(self.x + other.x, self.y + other.y)
    }

    fn __sub__(self, other) -> Vector {
        return Vector(self.x - other.x, self.y - other.y)
    }

    fn __mul__(self, other) -> Vector {
        return Vector(self.x * other.x, self.y * other.y)
    }

    fn __eq__(self, other) -> Bool {
        return self.x == other.x and self.y == other.y
    }

    fn __ne__(self, other) -> Bool {
        return self.x != other.x or self.y != other.y
    }

    fn __lt__(self, other) -> Bool {
        return self.x < other.x
    }

    fn __le__(self, other) -> Bool {
        return self.x <= other.x
    }

    fn __gt__(self, other) -> Bool {
        return self.x > other.x
    }

    fn __ge__(self, other) -> Bool {
        return self.x >= other.x
    }

    fn __neg__(self) -> Vector {
        return Vector(0 - self.x, 0 - self.y)
    }

    fn __str__(self) -> String {
        return "(" + str(self.x) + ", " + str(self.y) + ")"
    }
}
"""

# ---------------------------------------------------------------------------
# Analyzer tests
# ---------------------------------------------------------------------------


class TestDunderAnalyzer:
    """Verify the analyzer validates dunder method arities."""

    def _analyze(self, source: str) -> SemanticAnalyzer:
        """Parse and analyze source, return the analyzer."""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        analyzer.analyze(program)
        return analyzer

    def test_valid_binary_dunder_passes(self) -> None:
        """A binary dunder with 2 params (self, other) passes analysis."""
        source = """\
class Num {
    val,
    fn __add__(self, other) { return Num(self.val + other.val) }
}"""
        self._analyze(source)  # no error

    def test_valid_unary_dunder_passes(self) -> None:
        """A unary dunder with 1 param (self) passes analysis."""
        source = """\
class Num {
    val,
    fn __neg__(self) { return Num(0 - self.val) }
}"""
        self._analyze(source)  # no error

    def test_valid_str_dunder_passes(self) -> None:
        """A __str__ dunder with 1 param (self) passes analysis."""
        source = """\
class Num {
    val,
    fn __str__(self) { return str(self.val) }
}"""
        self._analyze(source)  # no error

    def test_binary_dunder_too_few_params_errors(self) -> None:
        """A binary dunder with 1 param instead of 2 raises an error."""
        source = """\
class Num {
    val,
    fn __add__(self) { return self }
}"""
        with pytest.raises(SemanticError, match="'__add__' requires 2 parameters, got 1"):
            self._analyze(source)

    def test_binary_dunder_too_many_params_errors(self) -> None:
        """A binary dunder with 3 params instead of 2 raises an error."""
        source = """\
class Num {
    val,
    fn __add__(self, other, extra) { return self }
}"""
        with pytest.raises(SemanticError, match="'__add__' requires 2 parameters, got 3"):
            self._analyze(source)

    def test_unary_dunder_too_many_params_errors(self) -> None:
        """A unary dunder with 2 params instead of 1 raises an error."""
        source = """\
class Num {
    val,
    fn __neg__(self, other) { return self }
}"""
        with pytest.raises(SemanticError, match="'__neg__' requires 1 parameter, got 2"):
            self._analyze(source)

    def test_str_dunder_too_many_params_errors(self) -> None:
        """A __str__ dunder with 2 params instead of 1 raises an error."""
        source = """\
class Num {
    val,
    fn __str__(self, other) { return "hi" }
}"""
        with pytest.raises(SemanticError, match="'__str__' requires 1 parameter, got 2"):
            self._analyze(source)

    def test_non_dunder_underscore_method_treated_normally(self) -> None:
        """A method with underscores that isn't a dunder is treated normally."""
        source = """\
class Num {
    val,
    fn _helper(self) { return self.val }
    fn __custom(self) { return self.val }
    fn helper__(self) { return self.val }
}"""
        self._analyze(source)  # no error — not dunders

    def test_all_binary_dunders_validated(self) -> None:
        """All binary dunders are validated for arity 2."""
        binary_dunders = [
            "__add__",
            "__sub__",
            "__mul__",
            "__div__",
            "__floordiv__",
            "__mod__",
            "__pow__",
            "__eq__",
            "__ne__",
            "__lt__",
            "__le__",
            "__gt__",
            "__ge__",
        ]
        for dunder in binary_dunders:
            source = f"""\
class Num {{
    val,
    fn {dunder}(self) {{ return self }}
}}"""
            with pytest.raises(SemanticError, match=f"'{dunder}' requires 2 parameters, got 1"):
                self._analyze(source)


# ---------------------------------------------------------------------------
# Integration tests — arithmetic
# ---------------------------------------------------------------------------


class TestDunderArithmetic:
    """Test operator overloading for arithmetic operators."""

    def test_add(self) -> None:
        """__add__ dispatches for + operator."""
        source = (
            VECTOR_CLASS
            + """\
let a = Vector(1, 2)
let b = Vector(3, 4)
let c = a + b
print(c.x)
print(c.y)"""
        )
        assert run_source(source) == "4\n6\n"

    def test_sub(self) -> None:
        """__sub__ dispatches for - operator."""
        source = (
            VECTOR_CLASS
            + """\
let a = Vector(5, 7)
let b = Vector(2, 3)
let c = a - b
print(c.x)
print(c.y)"""
        )
        assert run_source(source) == "3\n4\n"

    def test_mul(self) -> None:
        """__mul__ dispatches for * operator."""
        source = (
            VECTOR_CLASS
            + """\
let a = Vector(2, 3)
let b = Vector(4, 5)
let c = a * b
print(c.x)
print(c.y)"""
        )
        assert run_source(source) == "8\n15\n"

    def test_div(self) -> None:
        """__div__ dispatches for / operator."""
        source = """\
class Num {
    val,
    fn __div__(self, other) -> Num {
        return Num(self.val / other.val)
    }
}
let a = Num(10)
let b = Num(4)
let c = a / b
print(c.val)"""
        assert run_source(source) == "2.5\n"

    def test_floordiv(self) -> None:
        """__floordiv__ dispatches for // operator."""
        source = """\
class Num {
    val,
    fn __floordiv__(self, other) -> Num {
        return Num(self.val // other.val)
    }
}
let a = Num(10)
let b = Num(3)
let c = a // b
print(c.val)"""
        assert run_source(source) == "3\n"

    def test_mod(self) -> None:
        """__mod__ dispatches for % operator."""
        source = """\
class Num {
    val,
    fn __mod__(self, other) -> Num {
        return Num(self.val % other.val)
    }
}
let a = Num(10)
let b = Num(3)
let c = a % b
print(c.val)"""
        assert run_source(source) == "1\n"

    def test_pow(self) -> None:
        """__pow__ dispatches for ** operator."""
        source = """\
class Num {
    val,
    fn __pow__(self, other) -> Num {
        return Num(self.val ** other.val)
    }
}
let a = Num(2)
let b = Num(10)
let c = a ** b
print(c.val)"""
        assert run_source(source) == "1024\n"

    def test_operator_without_dunder_falls_through(self) -> None:
        """Using + on a class without __add__ falls through to type error."""
        source = """\
class Plain { val }
let a = Plain(1)
let b = Plain(2)
let c = a + b"""
        with pytest.raises(Exception, match="Unsupported operand"):
            run_source(source)

    def test_mixed_operand_types(self) -> None:
        """__add__ can handle mixed types (class + int)."""
        source = """\
class Num {
    val,
    fn __add__(self, other) -> Num {
        return Num(self.val + other)
    }
}
let a = Num(10)
let b = a + 5
print(b.val)"""
        assert run_source(source) == "15\n"

    def test_chained_operators(self) -> None:
        """Chained operators: a + b + c dispatches correctly."""
        source = (
            VECTOR_CLASS
            + """\
let a = Vector(1, 0)
let b = Vector(0, 1)
let c = Vector(2, 2)
let d = a + b + c
print(d.x)
print(d.y)"""
        )
        assert run_source(source) == "3\n3\n"


# ---------------------------------------------------------------------------
# Integration tests — comparison
# ---------------------------------------------------------------------------


class TestDunderComparison:
    """Test operator overloading for comparison operators."""

    def test_eq(self) -> None:
        """__eq__ dispatches for == operator."""
        source = (
            VECTOR_CLASS
            + """\
let a = Vector(1, 2)
let b = Vector(1, 2)
let c = Vector(3, 4)
print(a == b)
print(a == c)"""
        )
        assert run_source(source) == "true\nfalse\n"

    def test_ne(self) -> None:
        """__ne__ dispatches for != operator."""
        source = (
            VECTOR_CLASS
            + """\
let a = Vector(1, 2)
let b = Vector(3, 4)
let c = Vector(1, 2)
print(a != b)
print(a != c)"""
        )
        assert run_source(source) == "true\nfalse\n"

    def test_lt(self) -> None:
        """__lt__ dispatches for < operator."""
        source = (
            VECTOR_CLASS
            + """\
let a = Vector(1, 0)
let b = Vector(2, 0)
print(a < b)
print(b < a)"""
        )
        assert run_source(source) == "true\nfalse\n"

    def test_le(self) -> None:
        """__le__ dispatches for <= operator."""
        source = (
            VECTOR_CLASS
            + """\
let a = Vector(1, 0)
let b = Vector(1, 0)
let c = Vector(2, 0)
print(a <= b)
print(a <= c)
print(c <= a)"""
        )
        assert run_source(source) == "true\ntrue\nfalse\n"

    def test_gt(self) -> None:
        """__gt__ dispatches for > operator."""
        source = (
            VECTOR_CLASS
            + """\
let a = Vector(2, 0)
let b = Vector(1, 0)
print(a > b)
print(b > a)"""
        )
        assert run_source(source) == "true\nfalse\n"

    def test_ge(self) -> None:
        """__ge__ dispatches for >= operator."""
        source = (
            VECTOR_CLASS
            + """\
let a = Vector(2, 0)
let b = Vector(2, 0)
let c = Vector(1, 0)
print(a >= b)
print(a >= c)
print(c >= a)"""
        )
        assert run_source(source) == "true\ntrue\nfalse\n"

    def test_comparison_without_dunder_falls_through(self) -> None:
        """== on class without __eq__ falls through to default (structural) equality."""
        source = """\
class Plain { val }
let a = Plain(1)
let b = Plain(1)
let c = Plain(2)
print(a == b)
print(a == c)"""
        # Default == uses Python's dataclass structural equality
        assert run_source(source) == "true\nfalse\n"


# ---------------------------------------------------------------------------
# Integration tests — unary
# ---------------------------------------------------------------------------


class TestDunderUnary:
    """Test operator overloading for unary operators."""

    def test_neg(self) -> None:
        """__neg__ dispatches for - operator."""
        source = (
            VECTOR_CLASS
            + """\
let a = Vector(3, 5)
let b = -a
print(b.x)
print(b.y)"""
        )
        assert run_source(source) == "-3\n-5\n"

    def test_negation_without_dunder_falls_through(self) -> None:
        """Negation on class without __neg__ falls through to type error."""
        source = """\
class Plain { val }
let a = Plain(1)
let b = -a"""
        with pytest.raises(Exception, match="Unsupported operand type for negation"):
            run_source(source)


# ---------------------------------------------------------------------------
# Integration tests — __str__
# ---------------------------------------------------------------------------


class TestDunderStr:
    """Test __str__ dispatch for print, str(), and string interpolation."""

    def test_print_uses_str(self) -> None:
        """print(a) uses __str__ when defined."""
        source = (
            VECTOR_CLASS
            + """\
let a = Vector(1, 2)
print(a)"""
        )
        assert run_source(source) == "(1, 2)\n"

    def test_str_builtin_uses_str(self) -> None:
        """str(a) uses __str__ when defined."""
        source = (
            VECTOR_CLASS
            + """\
let a = Vector(3, 4)
let s = str(a)
print(s)"""
        )
        assert run_source(source) == "(3, 4)\n"

    def test_string_interpolation_uses_str(self) -> None:
        """String interpolation "{a}" uses __str__ when defined."""
        source = (
            VECTOR_CLASS
            + """\
let a = Vector(5, 6)
print("vec: {a}")"""
        )
        assert run_source(source) == "vec: (5, 6)\n"

    def test_default_format_without_str(self) -> None:
        """Instance without __str__ uses default ClassName(...) format."""
        source = """\
class Plain { val }
let a = Plain(42)
print(a)"""
        assert run_source(source) == "Plain(val=42)\n"


# ---------------------------------------------------------------------------
# Integration tests — inheritance
# ---------------------------------------------------------------------------


class TestDunderInheritance:
    """Test that dunder methods work with inheritance."""

    def test_child_inherits_parent_dunder(self) -> None:
        """A child class inherits the parent's __add__ dunder."""
        source = """\
class Base {
    val,
    fn __add__(self, other) -> Base {
        return Base(self.val + other.val)
    }
}
class Child extends Base { tag }
let a = Child(10, "a")
let b = Child(20, "b")
let c = a + b
print(c.val)"""
        assert run_source(source) == "30\n"

    def test_child_overrides_parent_dunder(self) -> None:
        """A child class can override the parent's __add__ dunder."""
        source = """\
class Base {
    val,
    fn __add__(self, other) -> Base {
        return Base(self.val + other.val)
    }
}
class Child extends Base {
    tag,
    fn __add__(self, other) -> Child {
        return Child(self.val + other.val + 100, self.tag)
    }
}
let a = Child(10, "a")
let b = Child(20, "b")
let c = a + b
print(c.val)"""
        assert run_source(source) == "130\n"

    def test_super_dunder_call(self) -> None:
        """super.__add__() works inside a child's __add__ override."""
        source = """\
class Base {
    val,
    fn __add__(self, other) -> Base {
        return Base(self.val + other.val)
    }
    fn get_val(self) { return self.val }
}
class Child extends Base {
    tag,
    fn __add__(self, other) -> Child {
        let base_result = super.__add__(other)
        return Child(base_result.get_val() * 2, self.tag)
    }
}
let a = Child(5, "x")
let b = Child(3, "y")
let c = a + b
print(c.val)"""
        assert run_source(source) == "16\n"


# ---------------------------------------------------------------------------
# REPL tests
# ---------------------------------------------------------------------------


class TestDunderRepl:
    """Verify operator overloading works across REPL evaluations."""

    def test_class_then_operator_across_evals(self) -> None:
        """Define class with dunders in one eval, use operators in next."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("""\
class Num {
    val,
    fn __add__(self, other) -> Num {
        return Num(self.val + other.val)
    }
    fn __str__(self) -> String {
        return "Num(" + str(self.val) + ")"
    }
}""")
        r.eval_line("let a = Num(10)")
        r.eval_line("let b = Num(20)")
        r.eval_line("print(a + b)")
        assert buf.getvalue() == "Num(30)\n"
