"""Tests for class inheritance: extends, method overriding, and super calls."""

from io import StringIO

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import ClassDef, SuperMethodCall
from pebble.bytecode import CompiledProgram, OpCode
from pebble.compiler import Compiler
from pebble.errors import ParseError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.repl import Repl
from pebble.tokens import TokenKind
from tests.conftest import (  # pyright: ignore[reportMissingImports]
    run_source,  # pyright: ignore[reportUnknownVariableType]
)

# -- Named constants ----------------------------------------------------------

SUPER_ARG_COUNT = 2

# ---------------------------------------------------------------------------
# Lexer tests
# ---------------------------------------------------------------------------


class TestInheritanceLexer:
    """Verify the lexer produces EXTENDS and SUPER tokens."""

    def test_extends_token(self) -> None:
        """Verify 'extends' produces an EXTENDS token."""
        tokens = Lexer("extends").tokenize()
        assert tokens[0].kind == TokenKind.EXTENDS
        assert tokens[0].value == "extends"

    def test_super_token(self) -> None:
        """Verify 'super' produces a SUPER token."""
        tokens = Lexer("super").tokenize()
        assert tokens[0].kind == TokenKind.SUPER
        assert tokens[0].value == "super"

    def test_extends_in_context(self) -> None:
        """Verify 'extends' tokenizes correctly inside a class definition."""
        tokens = Lexer("class Dog extends Animal {}").tokenize()
        kinds = [t.kind for t in tokens]
        assert TokenKind.CLASS in kinds
        assert TokenKind.EXTENDS in kinds

    def test_super_in_context(self) -> None:
        """Verify 'super' tokenizes correctly inside a method body."""
        tokens = Lexer("super.speak()").tokenize()
        assert tokens[0].kind == TokenKind.SUPER
        assert tokens[1].kind == TokenKind.DOT


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestInheritanceParser:
    """Verify the parser handles extends and super syntax."""

    def test_class_with_extends(self) -> None:
        """Parse a class with an extends clause."""
        source = "class Dog extends Animal { breed }"
        program = Parser(Lexer(source).tokenize()).parse()
        cls = program.statements[0]
        assert isinstance(cls, ClassDef)
        assert cls.name == "Dog"
        assert cls.parent == "Animal"
        assert len(cls.fields) == 1
        assert cls.fields[0].name == "breed"

    def test_class_without_extends(self) -> None:
        """Parse a class without extends — parent is None."""
        source = "class Animal { name }"
        program = Parser(Lexer(source).tokenize()).parse()
        cls = program.statements[0]
        assert isinstance(cls, ClassDef)
        assert cls.parent is None

    def test_child_with_fields_and_methods(self) -> None:
        """Parse a child class with both fields and methods."""
        source = """\
class Dog extends Animal {
    breed,
    fn bark(self) { return "woof" }
}"""
        program = Parser(Lexer(source).tokenize()).parse()
        cls = program.statements[0]
        assert isinstance(cls, ClassDef)
        assert cls.parent == "Animal"
        assert len(cls.fields) == 1
        assert len(cls.methods) == 1

    def test_child_with_only_methods(self) -> None:
        """Parse a child class with no extra fields."""
        source = """\
class Dog extends Animal {
    fn bark(self) { return "woof" }
}"""
        program = Parser(Lexer(source).tokenize()).parse()
        cls = program.statements[0]
        assert isinstance(cls, ClassDef)
        assert cls.parent == "Animal"
        assert len(cls.fields) == 0
        assert len(cls.methods) == 1

    def test_super_method_call(self) -> None:
        """Parse super.method() as a SuperMethodCall node."""
        source = "super.speak()"
        expr = Parser(Lexer(source).tokenize()).parse_expression()
        assert isinstance(expr, SuperMethodCall)
        assert expr.method == "speak"
        assert len(expr.arguments) == 0

    def test_super_method_call_with_args(self) -> None:
        """Parse super.method(args) with arguments."""
        source = "super.damage(10, 20)"
        expr = Parser(Lexer(source).tokenize()).parse_expression()
        assert isinstance(expr, SuperMethodCall)
        assert expr.method == "damage"
        assert len(expr.arguments) == SUPER_ARG_COUNT

    def test_super_without_dot_raises(self) -> None:
        """Bare 'super' without dot is a parse error."""
        source = "super()"
        with pytest.raises(ParseError, match=r"Expected '\.' after 'super'"):
            Parser(Lexer(source).tokenize()).parse_expression()

    def test_super_dot_no_parens_raises(self) -> None:
        """'super.field' without parens is a parse error."""
        source = "super.name"
        with pytest.raises(ParseError, match=r"Expected '\(' after method name"):
            Parser(Lexer(source).tokenize()).parse_expression()


# ---------------------------------------------------------------------------
# Analyzer tests
# ---------------------------------------------------------------------------

ANIMAL_CLASS = """\
class Animal {
    name, hp,
    fn speak(self) { return "I'm " + self.name }
    fn take_damage(self, n) { self.hp = self.hp - n }
}
"""


class TestInheritanceAnalyzer:
    """Verify semantic analysis of inheritance features."""

    def _analyze(self, source: str) -> SemanticAnalyzer:
        """Parse and analyze source, return the analyzer."""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        analyzer.analyze(program)
        return analyzer

    def test_basic_inheritance_passes(self) -> None:
        """A child class extending a valid parent passes analysis."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal {
    breed,
    fn bark(self) { return "woof" }
}"""
        )
        self._analyze(source)  # no error

    def test_unknown_parent_errors(self) -> None:
        """Extending a non-existent class raises an error."""
        source = "class Dog extends Ghost { breed }"
        with pytest.raises(SemanticError, match="Unknown parent class 'Ghost'"):
            self._analyze(source)

    def test_extending_struct_errors(self) -> None:
        """Extending a struct (not a class) raises an error."""
        source = """\
struct Point { x, y }
class Dot extends Point { color }"""
        with pytest.raises(SemanticError, match="'Point' is not a class"):
            self._analyze(source)

    def test_extending_enum_errors(self) -> None:
        """Extending an enum raises an error."""
        source = """\
enum Color { Red, Green, Blue }
class Thing extends Color { data }"""
        with pytest.raises(SemanticError, match="'Color' is an enum, not a class"):
            self._analyze(source)

    def test_self_extension_errors(self) -> None:
        """A class cannot extend itself."""
        source = "class Dog extends Dog { name }"
        with pytest.raises(SemanticError, match="A class cannot extend itself"):
            self._analyze(source)

    def test_constructor_arity_includes_parent_fields(self) -> None:
        """Child constructor arity includes parent + own fields."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal { breed }
let d = Dog("Rex", 100, "Lab")"""
        )
        self._analyze(source)  # no error — arity 3

    def test_constructor_wrong_arity_errors(self) -> None:
        """Wrong number of constructor args raises an error."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal { breed }
let d = Dog("Rex")"""
        )
        with pytest.raises(SemanticError, match="expects 3 argument"):
            self._analyze(source)

    def test_inherited_method_callable(self) -> None:
        """A method inherited from the parent can be called on the child."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal { breed }
let d = Dog("Rex", 100, "Lab")
d.take_damage(10)"""
        )
        self._analyze(source)  # no error

    def test_super_outside_child_class_errors(self) -> None:
        """Using super in a class with no parent raises an error."""
        source = """\
class Animal {
    name,
    fn speak(self) { return super.speak() }
}"""
        with pytest.raises(SemanticError, match="has no parent"):
            self._analyze(source)

    def test_super_outside_method_errors(self) -> None:
        """Using super outside a method raises an error."""
        source = """\
fn foo() { return super.bar() }"""
        with pytest.raises(SemanticError, match="can only be used inside a method"):
            self._analyze(source)

    def test_super_calling_nonexistent_method_errors(self) -> None:
        """Calling a method via super that the parent doesn't have raises an error."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal {
    breed,
    fn bark(self) { return super.bark() }
}"""
        )
        with pytest.raises(SemanticError, match="Parent class 'Animal' has no method 'bark'"):
            self._analyze(source)

    def test_method_override_valid(self) -> None:
        """A child can override a parent method."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal {
    breed,
    fn speak(self) { return "Woof!" }
}"""
        )
        self._analyze(source)  # no error

    def test_multi_level_inheritance_valid(self) -> None:
        """Multi-level inheritance (A → B → C) passes analysis."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal {
    breed,
    fn fetch(self) { return "fetching" }
}
class Puppy extends Dog {
    toy,
    fn play(self) { return "playing" }
}
let p = Puppy("Rex", 100, "Lab", "ball")"""
        )
        self._analyze(source)  # no error — arity 4

    def test_duplicate_field_with_parent_errors(self) -> None:
        """A child field that duplicates a parent field raises an error."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal { name }"""
        )
        with pytest.raises(SemanticError, match="Duplicate field 'name'"):
            self._analyze(source)

    def test_super_arity_mismatch_errors(self) -> None:
        """super.method() with wrong number of args raises an error."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal {
    breed,
    fn speak(self) { return super.take_damage() }
}"""
        )
        with pytest.raises(SemanticError, match="expects 1 argument"):
            self._analyze(source)

    def test_class_parents_tracked(self) -> None:
        """Verify analyzer tracks class parent relationships."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal { breed }"""
        )
        analyzer = self._analyze(source)
        assert analyzer.class_parents["Dog"] == "Animal"

    def test_class_fields_tracked(self) -> None:
        """Verify analyzer tracks full field lists including inherited."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal { breed }"""
        )
        analyzer = self._analyze(source)
        assert analyzer.class_fields["Dog"] == ["name", "hp", "breed"]


# ---------------------------------------------------------------------------
# Compiler tests
# ---------------------------------------------------------------------------


class TestInheritanceCompiler:
    """Verify the compiler handles inheritance correctly."""

    def _compile(self, source: str) -> tuple[Compiler, CompiledProgram]:
        """Parse, analyze, compile source, return (compiler, compiled)."""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        analyzed = analyzer.analyze(program)
        compiler = Compiler(
            cell_vars=analyzer.cell_vars,
            free_vars=analyzer.free_vars,
            enums=analyzer.enums,
            class_parents=analyzer.class_parents,
        )
        compiled = compiler.compile(analyzed)
        return compiler, compiled

    def test_child_struct_has_all_fields(self) -> None:
        """Child's struct entry contains parent + own fields."""
        source = ANIMAL_CLASS + "class Dog extends Animal { breed }"
        _, compiled = self._compile(source)
        assert compiled.structs["Dog"] == ["name", "hp", "breed"]

    def test_inherited_method_registered_under_child(self) -> None:
        """Inherited method appears as child-mangled function name."""
        source = ANIMAL_CLASS + "class Dog extends Animal { breed }"
        _, compiled = self._compile(source)
        assert "Dog.speak" in compiled.functions
        assert "Dog.take_damage" in compiled.functions

    def test_overridden_method_replaces_parent(self) -> None:
        """Overridden method uses the child's CodeObject."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal {
    breed,
    fn speak(self) { return "Woof!" }
}"""
        )
        _, compiled = self._compile(source)
        # Dog.speak should be different from Animal.speak
        assert compiled.functions["Dog.speak"] is not compiled.functions["Animal.speak"]

    def test_non_overridden_method_shares_code_object(self) -> None:
        """Non-overridden inherited method shares parent's CodeObject."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal {
    breed,
    fn bark(self) { return "woof" }
}"""
        )
        _, compiled = self._compile(source)
        # Dog.take_damage should be the same as Animal.take_damage
        assert compiled.functions["Dog.take_damage"] is compiled.functions["Animal.take_damage"]

    def test_super_compiles_to_call_parent_mangled(self) -> None:
        """super.speak() compiles to CALL 'Animal.speak'."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal {
    breed,
    fn speak(self) { return super.speak() }
}"""
        )
        _, compiled = self._compile(source)
        fn_code = compiled.functions["Dog.speak"]
        call_instructions = [i for i in fn_code.instructions if i.opcode == OpCode.CALL]
        assert any(i.operand == "Animal.speak" for i in call_instructions)

    def test_class_parents_metadata(self) -> None:
        """CompiledProgram includes class_parents mapping."""
        source = ANIMAL_CLASS + "class Dog extends Animal { breed }"
        _, compiled = self._compile(source)
        assert compiled.class_parents["Dog"] == "Animal"

    def test_class_methods_includes_inherited(self) -> None:
        """class_methods for child includes both own and inherited methods."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal {
    breed,
    fn bark(self) { return "woof" }
}"""
        )
        _, compiled = self._compile(source)
        methods = compiled.class_methods["Dog"]
        assert "bark" in methods
        assert "speak" in methods
        assert "take_damage" in methods


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestInheritanceIntegration:
    """End-to-end tests running inherited classes through the full pipeline."""

    def test_child_inherits_parent_fields(self) -> None:
        """Child instances store parent fields."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal { breed }
let d = Dog("Rex", 100, "Lab")
print(d.name)
print(d.hp)
print(d.breed)"""
        )
        assert run_source(source) == "Rex\n100\nLab\n"

    def test_child_inherits_parent_method(self) -> None:
        """A method defined on the parent is callable on the child."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal { breed }
let d = Dog("Rex", 100, "Lab")
d.take_damage(30)
print(d.hp)"""
        )
        assert run_source(source) == "70\n"

    def test_method_override(self) -> None:
        """A child method overrides the parent's version."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal {
    breed,
    fn speak(self) { return "Woof!" }
}
let d = Dog("Rex", 100, "Lab")
print(d.speak())"""
        )
        assert run_source(source) == "Woof!\n"

    def test_super_method_call(self) -> None:
        """super.method() calls the parent's version."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal {
    breed,
    fn speak(self) { return "Woof! " + super.speak() }
}
let d = Dog("Rex", 100, "Lab")
print(d.speak())"""
        )
        assert run_source(source) == "Woof! I'm Rex\n"

    def test_multi_level_inheritance(self) -> None:
        """Three-level inheritance chain with fields, methods, and super."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal {
    breed,
    fn speak(self) { return "Woof! " + super.speak() }
    fn fetch(self) { return self.name + " fetches!" }
}
class Puppy extends Dog {
    toy,
    fn speak(self) { return "Yip! " + super.speak() }
    fn play(self) { return self.name + " plays with " + self.toy }
}
let p = Puppy("Rex", 100, "Lab", "ball")
print(p.speak())
print(p.fetch())
print(p.play())
print(p.hp)"""
        )
        output = run_source(source)  # pyright: ignore[reportUnknownVariableType]
        assert output == "Yip! Woof! I'm Rex\nRex fetches!\nRex plays with ball\n100\n"

    def test_type_returns_child_name(self) -> None:
        """type() returns the child class name, not the parent."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal { breed }
let d = Dog("Rex", 100, "Lab")
print(type(d))"""
        )
        assert run_source(source) == "Dog\n"

    def test_printing_shows_all_fields(self) -> None:
        """Printing a child instance shows all fields."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal { breed }
let d = Dog("Rex", 100, "Lab")
print(d)"""
        )
        output = run_source(source)  # pyright: ignore[reportUnknownVariableType]
        assert "Rex" in output
        assert "100" in output
        assert "Lab" in output

    def test_field_mutation_via_inherited_method(self) -> None:
        """Inherited methods can mutate fields."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal { breed }
let d = Dog("Rex", 100, "Lab")
d.take_damage(50)
d.take_damage(20)
print(d.hp)"""
        )
        assert run_source(source) == "30\n"

    def test_super_with_args(self) -> None:
        """super.method(args) passes arguments correctly."""
        source = """\
class Base {
    val,
    fn add(self, n) { self.val = self.val + n }
    fn get(self) { return self.val }
}
class Child extends Base {
    fn add(self, n) {
        super.add(n * 2)
    }
}
let c = Child(10)
c.add(5)
print(c.get())"""
        assert run_source(source) == "20\n"

    def test_child_only_methods_accessing_parent_fields(self) -> None:
        """Child-only methods can access inherited fields."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal {
    breed,
    fn info(self) { return self.name + " (" + self.breed + ")" }
}
let d = Dog("Rex", 100, "Lab")
print(d.info())"""
        )
        assert run_source(source) == "Rex (Lab)\n"

    def test_child_with_no_extra_fields(self) -> None:
        """Child class with no extra fields works correctly."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal {
    fn bark(self) { return self.name + " says woof" }
}
let d = Dog("Rex", 100)
print(d.bark())
print(d.speak())"""
        )
        assert run_source(source) == "Rex says woof\nI'm Rex\n"

    def test_polymorphism_list_of_subclasses(self) -> None:
        """Different subclass instances in a list call overridden methods."""
        source = (
            ANIMAL_CLASS
            + """\
class Dog extends Animal {
    fn speak(self) { return "Woof! " + self.name }
}
class Cat extends Animal {
    fn speak(self) { return "Meow! " + self.name }
}
let animals = [Dog("Rex", 100), Cat("Whiskers", 80)]
for i in range(2) {
    print(animals[i].speak())
}"""
        )
        assert run_source(source) == "Woof! Rex\nMeow! Whiskers\n"

    def test_multi_level_fields(self) -> None:
        """Three-level chain accumulates fields correctly."""
        source = """\
class A { x }
class B extends A { y }
class C extends B { z }
let c = C(1, 2, 3)
print(c.x)
print(c.y)
print(c.z)"""
        assert run_source(source) == "1\n2\n3\n"

    def test_multi_level_method_inheritance(self) -> None:
        """Methods defined at level 1 are callable at level 3."""
        source = """\
class A {
    x,
    fn get_x(self) { return self.x }
}
class B extends A { y }
class C extends B { z }
let c = C(10, 20, 30)
print(c.get_x())"""
        assert run_source(source) == "10\n"


# ---------------------------------------------------------------------------
# REPL tests
# ---------------------------------------------------------------------------


class TestInheritanceRepl:
    """Verify inheritance works across REPL evaluations."""

    def test_parent_then_child_across_evals(self) -> None:
        """Define parent in one eval, child in next, use in third."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line(ANIMAL_CLASS)
        r.eval_line('class Dog extends Animal { breed, fn bark(self) { return "woof" } }')
        r.eval_line('let d = Dog("Rex", 100, "Lab")')
        r.eval_line("print(d.bark())")
        r.eval_line("print(d.speak())")
        assert buf.getvalue() == "woof\nI'm Rex\n"

    def test_super_across_evals(self) -> None:
        """super.method() works when parent and child are defined in separate evals."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line(ANIMAL_CLASS)
        r.eval_line("""\
class Dog extends Animal {
    breed,
    fn speak(self) { return "Woof! " + super.speak() }
}""")
        r.eval_line('let d = Dog("Rex", 100, "Lab")')
        r.eval_line("print(d.speak())")
        assert buf.getvalue() == "Woof! I'm Rex\n"

    def test_inherited_method_across_evals(self) -> None:
        """Inherited methods work across REPL evaluations."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line(ANIMAL_CLASS)
        r.eval_line("class Dog extends Animal { breed }")
        r.eval_line('let d = Dog("Rex", 100, "Lab")')
        r.eval_line("d.take_damage(30)")
        r.eval_line("print(d.hp)")
        assert buf.getvalue() == "70\n"

    def test_multi_level_repl(self) -> None:
        """Multi-level inheritance works across REPL evaluations."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("class A { x, fn get(self) { return self.x } }")
        r.eval_line("class B extends A { y }")
        r.eval_line("class C extends B { z }")
        r.eval_line("let c = C(1, 2, 3)")
        r.eval_line("print(c.get())")
        r.eval_line("print(c.z)")
        assert buf.getvalue() == "1\n3\n"
