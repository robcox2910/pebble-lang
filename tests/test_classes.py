"""Tests for class definitions with methods."""

from io import StringIO
from pathlib import Path

import pytest

from pebble.ast_nodes import ClassDef, FunctionDef, Parameter, Statement, TypeAnnotation
from pebble.bytecode import CodeObject, CompiledProgram, OpCode
from pebble.errors import ParseError, PebbleRuntimeError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.repl import Repl
from pebble.tokens import SourceLocation, TokenKind
from tests.conftest import (
    analyze,
    compile_source,
    run_source,
    run_source_with_imports,
)

# -- Named constants ----------------------------------------------------------

FIELD_COUNT_TWO = 2
METHOD_COUNT_TWO = 2

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lex(source: str) -> list[tuple[TokenKind, str]]:
    """Lex *source* and return a list of (kind, value) pairs."""
    return [(t.kind, t.value) for t in Lexer(source).tokenize()]


def _parse(source: str) -> list[Statement]:
    """Parse *source* and return the list of statements."""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse().statements


# ===========================================================================
# Cycle 1 — Token + AST + Bytecode
# ===========================================================================


class TestClassToken:
    """Verify CLASS lexes as a keyword."""

    def test_class_is_keyword(self) -> None:
        """The word 'class' produces a CLASS token, not IDENTIFIER."""
        tokens = _lex("class")
        assert tokens[0] == (TokenKind.CLASS, "class")

    def test_class_identifier_prefix(self) -> None:
        """A word starting with 'class' but longer is an IDENTIFIER."""
        tokens = _lex("classy")
        assert tokens[0] == (TokenKind.IDENTIFIER, "classy")


class TestClassASTNode:
    """Verify the ClassDef dataclass works correctly."""

    def test_class_def_construction(self) -> None:
        """ClassDef stores name, fields, methods, and location."""
        loc = SourceLocation(line=1, column=1)
        method = FunctionDef(
            name="bark",
            parameters=[Parameter(name="self")],
            body=[],
            location=loc,
        )
        node = ClassDef(
            name="Dog",
            fields=[Parameter(name="name"), Parameter(name="age")],
            methods=[method],
            location=loc,
        )
        assert node.name == "Dog"
        assert len(node.fields) == FIELD_COUNT_TWO
        assert len(node.methods) == 1
        assert node.methods[0].name == "bark"

    def test_class_def_empty_methods(self) -> None:
        """ClassDef with no methods is valid."""
        loc = SourceLocation(line=1, column=1)
        node = ClassDef(
            name="Point",
            fields=[Parameter(name="x"), Parameter(name="y")],
            methods=[],
            location=loc,
        )
        assert node.methods == []


class TestClassBytecode:
    """Verify CALL_INSTANCE_METHOD opcode and class_methods metadata."""

    def test_call_instance_method_opcode_exists(self) -> None:
        """CALL_INSTANCE_METHOD is a valid OpCode."""
        assert OpCode.CALL_INSTANCE_METHOD == "CALL_INSTANCE_METHOD"

    def test_class_methods_field_on_compiled_program(self) -> None:
        """CompiledProgram has a class_methods field that defaults to empty."""
        program = CompiledProgram(
            main=CodeObject(name="<main>"),
            functions={},
        )
        assert program.class_methods == {}


# ===========================================================================
# Cycle 2 — Parser
# ===========================================================================


class TestClassParser:
    """Verify _parse_class_def handles all class forms."""

    def test_fields_only(self) -> None:
        """A class with fields but no methods parses correctly."""
        stmts = _parse("class Point { x, y }")
        assert len(stmts) == 1
        node = stmts[0]
        assert isinstance(node, ClassDef)
        assert node.name == "Point"
        assert [f.name for f in node.fields] == ["x", "y"]
        assert node.methods == []

    def test_one_method(self) -> None:
        """A class with one method parses correctly."""
        source = """class Dog {
            name,
            fn bark(self) -> String {
                return "Woof"
            }
        }"""
        stmts = _parse(source)
        node = stmts[0]
        assert isinstance(node, ClassDef)
        assert [f.name for f in node.fields] == ["name"]
        assert len(node.methods) == 1
        assert node.methods[0].name == "bark"
        assert node.methods[0].return_type == TypeAnnotation(name="String")

    def test_multiple_methods(self) -> None:
        """A class with multiple methods parses correctly."""
        source = """class Counter {
            value,
            fn increment(self) {
                self.value = self.value + 1
            }
            fn get(self) -> Int {
                return self.value
            }
        }"""
        stmts = _parse(source)
        node = stmts[0]
        assert isinstance(node, ClassDef)
        assert len(node.methods) == METHOD_COUNT_TWO
        assert node.methods[0].name == "increment"
        assert node.methods[1].name == "get"

    def test_fields_and_methods(self) -> None:
        """A class with multiple fields and methods parses correctly."""
        source = """class Dog {
            name, age,
            fn bark(self) {
                return "Woof"
            }
        }"""
        stmts = _parse(source)
        node = stmts[0]
        assert isinstance(node, ClassDef)
        assert [f.name for f in node.fields] == ["name", "age"]
        assert len(node.methods) == 1

    def test_typed_fields(self) -> None:
        """Fields with type annotations are preserved."""
        source = "class Point { x: Int, y: Int }"
        stmts = _parse(source)
        node = stmts[0]
        assert isinstance(node, ClassDef)
        assert node.fields[0].type_annotation == TypeAnnotation(name="Int")
        assert node.fields[1].type_annotation == TypeAnnotation(name="Int")

    def test_return_type_on_method(self) -> None:
        """Method return type annotations are preserved."""
        source = """class Dog {
            name,
            fn bark(self) -> String {
                return "Woof"
            }
        }"""
        stmts = _parse(source)
        node = stmts[0]
        assert isinstance(node, ClassDef)
        assert node.methods[0].return_type == TypeAnnotation(name="String")

    def test_duplicate_field_error(self) -> None:
        """Duplicate field names in a class raise ParseError."""
        with pytest.raises(ParseError, match="Duplicate field"):
            _parse("class Bad { x, x }")

    def test_duplicate_method_error(self) -> None:
        """Duplicate method names in a class raise ParseError."""
        source = """class Bad {
            fn foo(self) { }
            fn foo(self) { }
        }"""
        with pytest.raises(ParseError, match="Duplicate method"):
            _parse(source)

    def test_method_params_parsed(self) -> None:
        """Method parameters (beyond self) are parsed correctly."""
        source = """class Calc {
            fn add(self, a: Int, b: Int) -> Int {
                return a + b
            }
        }"""
        stmts = _parse(source)
        node = stmts[0]
        assert isinstance(node, ClassDef)
        method = node.methods[0]
        assert [p.name for p in method.parameters] == ["self", "a", "b"]
        assert method.parameters[1].type_annotation == TypeAnnotation(name="Int")

    def test_empty_class(self) -> None:
        """A class with no fields and no methods is valid."""
        stmts = _parse("class Empty { }")
        node = stmts[0]
        assert isinstance(node, ClassDef)
        assert node.fields == []
        assert node.methods == []


# ===========================================================================
# Cycle 3 — Analyzer
# ===========================================================================


class TestClassAnalyzer:
    """Verify semantic analysis of class definitions."""

    def test_basic_class_passes(self) -> None:
        """A well-formed class definition passes analysis."""
        source = """class Dog {
            name,
            fn bark(self) -> String {
                return "Woof"
            }
        }"""
        analyze(source)  # should not raise

    def test_constructor_arity(self) -> None:
        """The class constructor is registered with the correct arity."""
        source = """class Dog {
            name, age,
            fn bark(self) {
                return "Woof"
            }
        }
        let d = Dog("Rex", 3)"""
        analyze(source)  # should not raise

    def test_wrong_constructor_arity_error(self) -> None:
        """Calling the constructor with wrong arity raises SemanticError."""
        source = """class Dog {
            name, age
        }
        let d = Dog("Rex")"""
        with pytest.raises(SemanticError, match="expects 2 argument"):
            analyze(source)

    def test_method_missing_self_error(self) -> None:
        """A method without self as first param raises SemanticError."""
        source = """class Bad {
            fn foo() {
                return 0
            }
        }"""
        with pytest.raises(SemanticError, match="self"):
            analyze(source)

    def test_method_body_validated(self) -> None:
        """Undeclared variables in method body raise SemanticError."""
        source = """class Bad {
            fn foo(self) {
                print(unknown)
            }
        }"""
        with pytest.raises(SemanticError, match="Undeclared variable 'unknown'"):
            analyze(source)

    def test_method_type_annotations_validated(self) -> None:
        """Invalid type annotations on method params raise SemanticError."""
        source = """class Bad {
            fn foo(self, x: Nonexistent) {
                return x
            }
        }"""
        with pytest.raises(SemanticError, match="Unknown type 'Nonexistent'"):
            analyze(source)

    def test_class_method_call_passes(self) -> None:
        """Calling a method defined on a class passes analysis."""
        source = """class Dog {
            name,
            fn bark(self) {
                return "Woof"
            }
        }
        let d = Dog("Rex")
        d.bark()"""
        analyze(source)  # should not raise

    def test_unknown_method_still_errors(self) -> None:
        """Calling a truly unknown method still raises SemanticError."""
        source = """class Dog {
            name,
            fn bark(self) {
                return "Woof"
            }
        }
        let d = Dog("Rex")
        d.nonexistent()"""
        with pytest.raises(SemanticError, match="Unknown method"):
            analyze(source)

    def test_builtin_method_name_collision_error(self) -> None:
        """A class method name that collides with a builtin method raises SemanticError."""
        source = """class Bad {
            fn push(self) {
                return 0
            }
        }"""
        with pytest.raises(SemanticError, match="reserved"):
            analyze(source)

    def test_class_as_type_annotation(self) -> None:
        """A class name can be used as a type annotation."""
        source = """class Dog {
            name
        }
        let d: Dog = Dog("Rex")"""
        analyze(source)  # should not raise


# ===========================================================================
# Cycle 4 — Compiler
# ===========================================================================


class TestClassCompiler:
    """Verify bytecode compilation of class definitions."""

    def test_class_stores_struct_metadata(self) -> None:
        """A class stores its field names in the structs dict."""
        source = """class Dog { name, age }"""
        compiled = compile_source(source)
        assert "Dog" in compiled.structs
        assert compiled.structs["Dog"] == ["name", "age"]

    def test_methods_compiled_as_mangled_functions(self) -> None:
        """Methods are compiled as 'ClassName.methodName' in functions dict."""
        source = """class Dog {
            name,
            fn bark(self) {
                return "Woof"
            }
        }"""
        compiled = compile_source(source)
        assert "Dog.bark" in compiled.functions

    def test_method_code_object_has_self_param(self) -> None:
        """The mangled method's CodeObject includes 'self' as first parameter."""
        source = """class Dog {
            name,
            fn bark(self) {
                return "Woof"
            }
        }"""
        compiled = compile_source(source)
        code = compiled.functions["Dog.bark"]
        assert code.parameters[0] == "self"

    def test_call_instance_method_emitted(self) -> None:
        """Calling a class method emits CALL_INSTANCE_METHOD opcode."""
        source = """class Dog {
            name,
            fn bark(self) {
                return "Woof"
            }
        }
        let d = Dog("Rex")
        d.bark()"""
        compiled = compile_source(source)
        opcodes = [i.opcode for i in compiled.main.instructions]
        assert OpCode.CALL_INSTANCE_METHOD in opcodes

    def test_call_method_still_for_builtins(self) -> None:
        """Builtin method calls still use CALL_METHOD opcode."""
        source = """let xs = [1, 2, 3]
        xs.push(4)"""
        compiled = compile_source(source)
        opcodes = [i.opcode for i in compiled.main.instructions]
        assert OpCode.CALL_METHOD in opcodes

    def test_class_methods_metadata(self) -> None:
        """The class_methods dict is populated in CompiledProgram."""
        source = """class Dog {
            name,
            fn bark(self) {
                return "Woof"
            }
            fn sit(self) {
                return "sitting"
            }
        }"""
        compiled = compile_source(source)
        assert "Dog" in compiled.class_methods
        assert sorted(compiled.class_methods["Dog"]) == ["bark", "sit"]

    def test_method_return_type(self) -> None:
        """Method return type annotation is preserved on CodeObject."""
        source = """class Dog {
            name,
            fn bark(self) -> String {
                return "Woof"
            }
        }"""
        compiled = compile_source(source)
        code = compiled.functions["Dog.bark"]
        assert code.return_type == TypeAnnotation(name="String")

    def test_implicit_return(self) -> None:
        """Methods without explicit return get implicit return 0."""
        source = """class Dog {
            name,
            fn bark(self) {
                let x = 1
            }
        }"""
        compiled = compile_source(source)
        code = compiled.functions["Dog.bark"]
        assert code.instructions[-1].opcode == OpCode.RETURN


# ===========================================================================
# Cycle 5 — VM Runtime
# ===========================================================================


class TestClassVM:
    """Verify runtime execution of class methods."""

    def test_simple_method_call(self) -> None:
        """A simple method call returns the correct value."""
        source = """class Dog {
            name,
            fn bark(self) -> String {
                return "Woof"
            }
        }
        let d = Dog("Rex")
        print(d.bark())"""
        assert run_source(source) == "Woof\n"

    def test_method_reads_self_field(self) -> None:
        """A method can read fields from self."""
        source = """class Dog {
            name,
            fn greet(self) -> String {
                return "I'm " + self.name
            }
        }
        let d = Dog("Rex")
        print(d.greet())"""
        assert run_source(source) == "I'm Rex\n"

    def test_method_mutates_self(self) -> None:
        """A method can mutate fields on self."""
        source = """class Counter {
            value,
            fn increment(self) {
                self.value = self.value + 1
            }
        }
        let c = Counter(0)
        c.increment()
        c.increment()
        print(c.value)"""
        assert run_source(source) == "2\n"

    def test_method_with_extra_args(self) -> None:
        """A method can accept additional arguments beyond self."""
        source = """class Calc {
            base,
            fn add(self, n: Int) -> Int {
                return self.base + n
            }
        }
        let c = Calc(10)
        print(c.add(5))"""
        assert run_source(source) == "15\n"

    def test_return_type_checked(self) -> None:
        """A method with a return type annotation is type-checked statically."""
        source = """class Dog {
            name,
            fn bark(self) -> Int {
                return "not an int"
            }
        }
        let d = Dog("Rex")
        d.bark()"""
        with pytest.raises(SemanticError, match="Type error"):
            run_source(source)

    def test_method_on_non_struct_errors(self) -> None:
        """Calling an instance method on a non-struct value raises PebbleRuntimeError."""
        source = """class Dog {
            name,
            fn bark(self) {
                return "Woof"
            }
        }
        let x = 42
        x.bark()"""
        with pytest.raises(PebbleRuntimeError, match="not a struct"):
            run_source(source)

    def test_nonexistent_method_errors(self) -> None:
        """Calling a method not defined on the struct's class raises PebbleRuntimeError."""
        source = """class Dog {
            name,
            fn bark(self) {
                return "Woof"
            }
        }
        class Cat {
            name,
            fn meow(self) {
                return "Meow"
            }
        }
        let d = Dog("Rex")
        d.meow()"""
        with pytest.raises(PebbleRuntimeError, match="has no method"):
            run_source(source)

    def test_field_access_works(self) -> None:
        """Field access on class instances works the same as structs."""
        source = """class Dog {
            name, age,
            fn bark(self) {
                return "Woof"
            }
        }
        let d = Dog("Rex", 3)
        print(d.name)
        print(d.age)"""
        assert run_source(source) == "Rex\n3\n"

    def test_field_mutation_works(self) -> None:
        """Field mutation on class instances works the same as structs."""
        source = """class Dog {
            name, age,
            fn birthday(self) {
                self.age = self.age + 1
            }
        }
        let d = Dog("Rex", 3)
        d.birthday()
        print(d.age)"""
        assert run_source(source) == "4\n"

    def test_print_representation(self) -> None:
        """Printing a class instance shows the struct representation."""
        source = """class Dog {
            name, age,
            fn bark(self) {
                return "Woof"
            }
        }
        let d = Dog("Rex", 3)
        print(d)"""
        assert run_source(source) == "Dog(name=Rex, age=3)\n"

    def test_multiple_instances_independent(self) -> None:
        """Multiple instances of the same class are independent."""
        source = """class Counter {
            value,
            fn increment(self) {
                self.value = self.value + 1
            }
        }
        let a = Counter(0)
        let b = Counter(10)
        a.increment()
        a.increment()
        b.increment()
        print(a.value)
        print(b.value)"""
        assert run_source(source) == "2\n11\n"

    def test_method_calls_method(self) -> None:
        """A method can call another method on self."""
        source = """class Dog {
            name,
            fn bark(self) -> String {
                return "Woof! " + self.greeting()
            }
            fn greeting(self) -> String {
                return "I'm " + self.name
            }
        }
        let d = Dog("Rex")
        print(d.bark())"""
        assert run_source(source) == "Woof! I'm Rex\n"

    def test_typed_params_checked(self) -> None:
        """Type annotations on method params are checked at runtime."""
        source = """class Calc {
            base,
            fn add(self, n: Int) -> Int {
                return self.base + n
            }
        }
        let c = Calc(10)
        c.add("oops")"""
        with pytest.raises(PebbleRuntimeError, match="Type error"):
            run_source(source)


# ===========================================================================
# Cycle 6 — Integration
# ===========================================================================


class TestClassEndToEnd:
    """Full end-to-end class workflows."""

    def test_full_workflow(self) -> None:
        """A complete class with fields, methods, mutation, and output."""
        source = """class Dog {
            name, age,
            fn bark(self) -> String {
                return "Woof! I'm " + self.name
            }
            fn birthday(self) {
                self.age = self.age + 1
            }
        }
        let d = Dog("Rex", 3)
        print(d.bark())
        d.birthday()
        print(d.age)"""
        assert run_source(source) == "Woof! I'm Rex\n4\n"

    def test_mixed_typed_untyped(self) -> None:
        """Class with a mix of typed and untyped fields."""
        source = """class Point {
            x: Int, y: Int
        }
        let p = Point(1, 2)
        print(p.x + p.y)"""
        assert run_source(source) == "3\n"

    def test_class_in_list(self) -> None:
        """Class instances can be stored in a list."""
        source = """class Dog {
            name,
            fn bark(self) -> String {
                return self.name
            }
        }
        let dogs = [Dog("Rex"), Dog("Buddy")]
        print(dogs[0].bark())
        print(dogs[1].bark())"""
        assert run_source(source) == "Rex\nBuddy\n"

    def test_class_passed_to_function(self) -> None:
        """A class instance can be passed to a regular function."""
        source = """class Dog {
            name,
            fn bark(self) -> String {
                return "Woof from " + self.name
            }
        }
        fn make_bark(dog) {
            return dog.bark()
        }
        let d = Dog("Rex")
        print(make_bark(d))"""
        assert run_source(source) == "Woof from Rex\n"

    def test_struct_still_works(self) -> None:
        """Structs still work alongside classes."""
        source = """struct Point {
            x, y
        }
        class Dog {
            name,
            fn bark(self) -> String {
                return "Woof"
            }
        }
        let p = Point(1, 2)
        let d = Dog("Rex")
        print(p.x)
        print(d.bark())"""
        assert run_source(source) == "1\nWoof\n"


class TestClassResolver:
    """Verify class imports work through the resolver."""

    def test_imported_class_method(self, tmp_path: Path) -> None:
        """A class imported from another module works correctly."""
        lib = tmp_path / "lib.pbl"
        lib.write_text("""class Dog {
            name,
            fn bark(self) -> String {
                return "Woof from " + self.name
            }
        }
""")
        source = """import "lib.pbl"
let d = Dog("Rex")
print(d.bark())"""
        assert run_source_with_imports(source, base_dir=tmp_path) == "Woof from Rex\n"

    def test_from_import_class(self, tmp_path: Path) -> None:
        """A class imported via from-import works correctly."""
        lib = tmp_path / "lib.pbl"
        lib.write_text("""class Counter {
            value,
            fn increment(self) {
                self.value = self.value + 1
            }
        }
""")
        source = """from "lib.pbl" import Counter
let c = Counter(0)
c.increment()
c.increment()
print(c.value)"""
        assert run_source_with_imports(source, base_dir=tmp_path) == "2\n"


class TestClassREPL:
    """Verify class persistence across REPL evaluations."""

    def test_different_classes_same_method_name_different_arities(self) -> None:
        """Two classes with same method name but different arities should both be accepted."""
        source = (
            "class A {\n"
            "    x,\n"
            "    fn foo(self) -> Int { return self.x }\n"
            "}\n"
            "class B {\n"
            "    x,\n"
            "    fn foo(self, n: Int) -> Int { return self.x + n }\n"
            "}\n"
            "let a = A(10)\n"
            "let b = B(20)\n"
            "print(a.foo())\n"
            "print(b.foo(5))\n"
        )
        assert run_source(source) == "10\n25\n"

    def test_class_persists_across_evals(self) -> None:
        """A class defined in one REPL eval is available in the next."""
        buf = StringIO()
        r = Repl(output=buf)
        r.eval_line("""class Dog {
            name,
            fn bark(self) -> String {
                return "Woof from " + self.name
            }
        }""")
        r.eval_line('let d = Dog("Rex")')
        r.eval_line("print(d.bark())")
        assert buf.getvalue() == "Woof from Rex\n"
