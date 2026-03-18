"""Tests for the Pebble code formatter.

Cover comment extraction, literal formatting, operator spacing,
parenthesization, control flow, functions, data structures, structs,
classes, enums, match/case, try/catch, imports, comment interleaving,
idempotency, and edge cases.
"""

from pebble.formatter import Formatter, extract_comments

# -- Cycle 1: Comment extraction -----------------------------------------------


class TestExtractComments:
    """Verify comment extraction from raw source."""

    def test_no_comments_returns_empty(self) -> None:
        """Return empty dict when source has no comments."""
        assert extract_comments("let x = 42") == {}

    def test_full_line_comment(self) -> None:
        """Extract a full-line comment."""
        result = extract_comments("# hello")
        assert result == {1: "# hello"}

    def test_inline_comment(self) -> None:
        """Extract an inline comment after code."""
        result = extract_comments("let x = 42  # the answer")
        assert result == {1: "# the answer"}

    def test_multiple_lines(self) -> None:
        """Extract comments from multiple lines."""
        source = "# first\nlet x = 1\n# second"
        result = extract_comments(source)
        assert result == {1: "# first", 3: "# second"}

    def test_hash_inside_string_ignored(self) -> None:
        """Ignore # characters inside string literals."""
        result = extract_comments('let x = "hello # world"')
        assert result == {}

    def test_hash_inside_interpolated_string_ignored(self) -> None:
        """Ignore # inside string after interpolation."""
        result = extract_comments('let x = "value is {y}#end"')
        assert result == {}

    def test_comment_after_string_with_hash(self) -> None:
        """Extract comment after a string that itself contains hash."""
        result = extract_comments('let x = "a#b"  # real comment')
        assert result == {1: "# real comment"}


# -- Cycle 2: Formatter scaffold + literals ------------------------------------


class TestFormatterLiterals:
    """Verify formatting of simple declarations and literals."""

    def test_let_integer(self) -> None:
        """Format a let-integer declaration."""
        assert Formatter("let x = 42").format() == "let x = 42\n"

    def test_let_float(self) -> None:
        """Format a let-float declaration."""
        assert Formatter("let pi = 3.14").format() == "let pi = 3.14\n"

    def test_let_string(self) -> None:
        """Format a let-string declaration."""
        assert Formatter('let s = "hello"').format() == 'let s = "hello"\n'

    def test_let_boolean_true(self) -> None:
        """Format a let-true declaration."""
        assert Formatter("let b = true").format() == "let b = true\n"

    def test_let_boolean_false(self) -> None:
        """Format a let-false declaration."""
        assert Formatter("let b = false").format() == "let b = false\n"

    def test_let_null(self) -> None:
        """Format a let-null declaration."""
        assert Formatter("let n = null").format() == "let n = null\n"

    def test_const_declaration(self) -> None:
        """Format a const declaration."""
        assert Formatter("const MAX = 100").format() == "const MAX = 100\n"

    def test_trailing_newline(self) -> None:
        """Ensure output always ends with a trailing newline."""
        result = Formatter("let x = 1").format()
        assert result.endswith("\n")

    def test_trailing_whitespace_stripped(self) -> None:
        """Ensure no trailing whitespace on any line."""
        result = Formatter("let x = 1").format()
        for line in result.split("\n"):
            assert line == line.rstrip()


# -- Cycle 3: Operators, print, parenthesization ------------------------------


class TestFormatterOperators:
    """Verify operator formatting and parenthesization."""

    def test_binary_op_spacing(self) -> None:
        """Binary operators get spaces around them."""
        assert Formatter("let x = 1+2").format() == "let x = 1 + 2\n"

    def test_multiple_operators(self) -> None:
        """Multiple binary operators formatted correctly."""
        assert Formatter("let x = 1+2*3").format() == "let x = 1 + 2 * 3\n"

    def test_unary_negate_no_space(self) -> None:
        """Unary negation has no space after -."""
        assert Formatter("let x = -5").format() == "let x = -5\n"

    def test_unary_not_with_space(self) -> None:
        """Unary not has a space before operand."""
        assert Formatter("let x = not true").format() == "let x = not true\n"

    def test_unary_bitwise_not(self) -> None:
        """Unary bitwise not has no space."""
        assert Formatter("let x = ~5").format() == "let x = ~5\n"

    def test_print_statement(self) -> None:
        """Format a print statement."""
        assert Formatter("print(42)").format() == "print(42)\n"

    def test_parenthesized_lower_precedence(self) -> None:
        """Wrap lower-precedence child in parens."""
        # (1 + 2) * 3 — the addition needs parens because it's inside multiplication
        assert Formatter("let x = (1 + 2) * 3").format() == "let x = (1 + 2) * 3\n"

    def test_no_unnecessary_parens(self) -> None:
        """Don't add parens when not needed."""
        # 1 + 2 * 3 — multiplication is higher precedence, no parens needed
        assert Formatter("let x = 1 + 2 * 3").format() == "let x = 1 + 2 * 3\n"

    def test_right_associative_power(self) -> None:
        """Right-associative ** formatted without extra parens."""
        assert Formatter("let x = 2 ** 3 ** 4").format() == "let x = 2 ** 3 ** 4\n"

    def test_comparison_ops(self) -> None:
        """Comparison operators spaced correctly."""
        assert Formatter("let x = a == b").format() == "let x = a == b\n"

    def test_logical_ops(self) -> None:
        """Logical operators spaced correctly."""
        assert Formatter("let x = a and b or c").format() == "let x = a and b or c\n"


# -- Cycle 4: Assignments, types, unpacking -----------------------------------


class TestFormatterAssignments:
    """Verify various assignment and type annotation formats."""

    def test_reassignment(self) -> None:
        """Format a reassignment."""
        assert Formatter("let x = 1\nx = 2").format() == "let x = 1\nx = 2\n"

    def test_type_annotation(self) -> None:
        """Format a let with type annotation."""
        assert Formatter("let x: Int = 42").format() == "let x: Int = 42\n"

    def test_const_type_annotation(self) -> None:
        """Format a const with type annotation."""
        assert Formatter("const MAX: Int = 100").format() == "const MAX: Int = 100\n"

    def test_generic_type_annotation(self) -> None:
        """Format a let with generic type annotation."""
        assert Formatter("let xs: List[Int] = [1, 2]").format() == "let xs: List[Int] = [1, 2]\n"

    def test_unpack_assignment(self) -> None:
        """Format a let unpack assignment."""
        assert Formatter("let a, b = [1, 2]").format() == "let a, b = [1, 2]\n"

    def test_unpack_const_assignment(self) -> None:
        """Format a const unpack assignment."""
        assert Formatter("const a, b = [1, 2]").format() == "const a, b = [1, 2]\n"

    def test_unpack_reassignment(self) -> None:
        """Format an unpack reassignment."""
        source = "let a = 1\nlet b = 2\na, b = [3, 4]"
        result = Formatter(source).format()
        assert "a, b = [3, 4]\n" in result


# -- Cycle 5: Control flow ----------------------------------------------------


class TestFormatterControlFlow:
    """Verify if/else, while, for, break, continue formatting."""

    def test_if_statement(self) -> None:
        """Format an if block with 4-space indentation."""
        source = "if true { print(1) }"
        expected = "if true {\n    print(1)\n}\n"
        assert Formatter(source).format() == expected

    def test_if_else(self) -> None:
        """Format an if/else block."""
        source = "if true { print(1) } else { print(2) }"
        expected = "if true {\n    print(1)\n} else {\n    print(2)\n}\n"
        assert Formatter(source).format() == expected

    def test_else_if_chain(self) -> None:
        """Format else-if chains without nesting."""
        source = "if true { print(1) } else if false { print(2) } else { print(3) }"
        expected = (
            "if true {\n    print(1)\n} else if false {\n    print(2)\n} else {\n    print(3)\n}\n"
        )
        assert Formatter(source).format() == expected

    def test_while_loop(self) -> None:
        """Format a while loop."""
        source = "while true { print(1) }"
        expected = "while true {\n    print(1)\n}\n"
        assert Formatter(source).format() == expected

    def test_for_loop(self) -> None:
        """Format a for loop."""
        source = "for i in range(10) { print(i) }"
        expected = "for i in range(10) {\n    print(i)\n}\n"
        assert Formatter(source).format() == expected

    def test_break_continue(self) -> None:
        """Format break and continue statements."""
        source = "while true { break }"
        expected = "while true {\n    break\n}\n"
        assert Formatter(source).format() == expected

    def test_nested_indentation(self) -> None:
        """Nested blocks increase indentation."""
        source = "if true { if false { print(1) } }"
        expected = "if true {\n    if false {\n        print(1)\n    }\n}\n"
        assert Formatter(source).format() == expected


# -- Cycle 6: Functions --------------------------------------------------------


class TestFormatterFunctions:
    """Verify function formatting."""

    def test_simple_function(self) -> None:
        """Format a simple function definition."""
        source = "fn greet() { print(42) }"
        expected = "fn greet() {\n    print(42)\n}\n"
        assert Formatter(source).format() == expected

    def test_function_with_params(self) -> None:
        """Format a function with parameters."""
        source = "fn add(a, b) { return a + b }"
        expected = "fn add(a, b) {\n    return a + b\n}\n"
        assert Formatter(source).format() == expected

    def test_typed_params(self) -> None:
        """Format a function with typed parameters."""
        source = "fn add(a: Int, b: Int) -> Int { return a + b }"
        expected = "fn add(a: Int, b: Int) -> Int {\n    return a + b\n}\n"
        assert Formatter(source).format() == expected

    def test_default_params(self) -> None:
        """Format a function with default parameters."""
        source = 'fn greet(name = "world") { print(name) }'
        expected = 'fn greet(name = "world") {\n    print(name)\n}\n'
        assert Formatter(source).format() == expected

    def test_async_function(self) -> None:
        """Format an async function definition."""
        source = "async fn fetch(url) { return await get(url) }"
        expected = "async fn fetch(url) {\n    return await get(url)\n}\n"
        assert Formatter(source).format() == expected

    def test_bare_return(self) -> None:
        """Format a bare return statement."""
        source = "fn stop() { return }"
        expected = "fn stop() {\n    return\n}\n"
        assert Formatter(source).format() == expected

    def test_yield_statement(self) -> None:
        """Format a yield statement."""
        source = "fn gen() { yield 1 }"
        expected = "fn gen() {\n    yield 1\n}\n"
        assert Formatter(source).format() == expected

    def test_function_expression(self) -> None:
        """Format an anonymous function expression."""
        source = "let f = fn(x) { return x + 1 }"
        expected = "let f = fn(x) {\n    return x + 1\n}\n"
        assert Formatter(source).format() == expected

    def test_blank_line_between_top_level_defs(self) -> None:
        """Blank line between top-level definitions."""
        source = "fn a() { return 1 }\nfn b() { return 2 }"
        result = Formatter(source).format()
        assert "\n\nfn b()" in result


# -- Cycle 7: Data structures and access --------------------------------------


class TestFormatterDataStructures:
    """Verify array, dict, index, slice, interpolation, method, field formatting."""

    def test_array_literal(self) -> None:
        """Format an array literal."""
        assert Formatter("let xs = [1, 2, 3]").format() == "let xs = [1, 2, 3]\n"

    def test_empty_array(self) -> None:
        """Format an empty array."""
        assert Formatter("let xs = []").format() == "let xs = []\n"

    def test_dict_literal(self) -> None:
        """Format a dict literal."""
        result = Formatter('let d = {"a": 1, "b": 2}').format()
        assert result == 'let d = {"a": 1, "b": 2}\n'

    def test_index_access(self) -> None:
        """Format index access."""
        assert Formatter("let xs = [1]\nlet x = xs[0]").format().endswith("let x = xs[0]\n")

    def test_index_assignment(self) -> None:
        """Format index assignment."""
        source = "let xs = [1, 2]\nxs[0] = 42"
        assert "xs[0] = 42\n" in Formatter(source).format()

    def test_slice_access(self) -> None:
        """Format slice access."""
        source = "let xs = [1, 2, 3]\nlet s = xs[1:3]"
        assert "xs[1:3]" in Formatter(source).format()

    def test_slice_with_step(self) -> None:
        """Format slice with step."""
        source = "let xs = [1, 2, 3, 4]\nlet s = xs[::2]"
        assert "xs[::2]" in Formatter(source).format()

    def test_string_interpolation(self) -> None:
        """Format string interpolation."""
        source = 'let name = "world"\nlet s = "hello {name}"'
        result = Formatter(source).format()
        assert 'let s = "hello {name}"' in result

    def test_string_interpolation_with_expression(self) -> None:
        """Format string interpolation with expression."""
        source = 'let x = 5\nlet s = "value is {x + 1}"'
        result = Formatter(source).format()
        assert '"value is {x + 1}"' in result

    def test_method_call(self) -> None:
        """Format a method call."""
        source = "let xs = [3, 1, 2]\nlet s = xs.sorted()"
        assert "xs.sorted()" in Formatter(source).format()

    def test_field_access(self) -> None:
        """Format field access."""
        source = "struct Point { x, y }\nlet p = Point(1, 2)\nlet a = p.x"
        assert "p.x" in Formatter(source).format()

    def test_field_assignment(self) -> None:
        """Format field assignment."""
        source = "struct Point { x, y }\nlet p = Point(1, 2)\np.x = 5"
        assert "p.x = 5" in Formatter(source).format()

    def test_list_comprehension(self) -> None:
        """Format a list comprehension."""
        source = "let xs = [x * 2 for x in range(10)]"
        assert Formatter(source).format() == "let xs = [x * 2 for x in range(10)]\n"

    def test_list_comprehension_with_condition(self) -> None:
        """Format a list comprehension with condition."""
        source = "let xs = [x for x in range(10) if x > 5]"
        assert Formatter(source).format() == "let xs = [x for x in range(10) if x > 5]\n"

    def test_super_method_call(self) -> None:
        """Format a super method call."""
        source = (
            "class Animal {\n"
            "    name\n"
            "    fn speak(self) { return self.name }\n"
            "}\n"
            "class Dog extends Animal {\n"
            "    fn speak(self) { return super.speak() }\n"
            "}"
        )
        assert "super.speak()" in Formatter(source).format()


# -- Cycle 8: Structs, classes, enums ------------------------------------------


class TestFormatterStructsClassesEnums:
    """Verify struct, class, and enum formatting."""

    def test_struct_simple(self) -> None:
        """Format a simple struct."""
        source = "struct Point { x, y }"
        expected = "struct Point {\n    x,\n    y\n}\n"
        assert Formatter(source).format() == expected

    def test_struct_typed_fields(self) -> None:
        """Format a struct with typed fields."""
        source = "struct Point { x: Int, y: Int }"
        expected = "struct Point {\n    x: Int,\n    y: Int\n}\n"
        assert Formatter(source).format() == expected

    def test_class_with_methods(self) -> None:
        """Format a class with fields and methods."""
        source = (
            "class Dog { name, age\n"
            'fn bark(self) { return "woof" }\n'
            "fn age_in_human_years(self) { return self.age * 7 } }"
        )
        result = Formatter(source).format()
        assert "class Dog {" in result
        assert "    name," in result
        assert "    age" in result
        assert "    fn bark(self) {" in result

    def test_class_inheritance(self) -> None:
        """Format a class with extends."""
        source = "class Animal { name }\nclass Dog extends Animal { breed }"
        result = Formatter(source).format()
        assert "class Dog extends Animal {" in result

    def test_enum(self) -> None:
        """Format an enum definition."""
        source = "enum Color { Red, Green, Blue }"
        expected = "enum Color {\n    Red,\n    Green,\n    Blue\n}\n"
        assert Formatter(source).format() == expected

    def test_blank_lines_between_definitions(self) -> None:
        """Blank lines between top-level struct/class/enum defs."""
        source = "struct A { x }\nstruct B { y }"
        result = Formatter(source).format()
        assert "\n\nstruct B {" in result


# -- Cycle 9: Match/case and try/catch ----------------------------------------


class TestFormatterMatchAndTryCatch:
    """Verify match/case and try/catch formatting."""

    def test_match_literal(self) -> None:
        """Format a match with literal patterns."""
        source = "let x = 1\nmatch x { case 1 { print(1) } case _ { print(0) } }"
        result = Formatter(source).format()
        assert "match x {" in result
        assert "    case 1 {" in result
        assert "        print(1)" in result
        assert "    case _ {" in result

    def test_match_capture(self) -> None:
        """Format a match with capture pattern."""
        source = "let x = 42\nmatch x { case let val { print(val) } }"
        result = Formatter(source).format()
        assert "case let val {" in result

    def test_match_or_pattern(self) -> None:
        """Format a match with or pattern."""
        source = "let x = 1\nmatch x { case 1 | 2 { print(1) } case _ { print(0) } }"
        result = Formatter(source).format()
        assert "case 1 | 2 {" in result

    def test_match_enum_pattern(self) -> None:
        """Format a match with enum pattern."""
        source = (
            "enum Color { Red, Green, Blue }\n"
            "let c = Color.Red\n"
            "match c { case Color.Red { print(1) } case _ { print(0) } }"
        )
        result = Formatter(source).format()
        assert "case Color.Red {" in result

    def test_try_catch(self) -> None:
        """Format a try/catch block."""
        source = "try { print(1) } catch e { print(e) }"
        result = Formatter(source).format()
        assert "try {" in result
        assert "} catch e {" in result

    def test_try_catch_finally(self) -> None:
        """Format a try/catch/finally block."""
        source = "try { print(1) } catch e { print(e) } finally { print(3) }"
        result = Formatter(source).format()
        assert "} finally {" in result

    def test_throw_statement(self) -> None:
        """Format a throw statement."""
        source = 'throw "error"'
        assert Formatter(source).format() == 'throw "error"\n'


# -- Cycle 10: Imports and comment interleaving --------------------------------


class TestFormatterImportsAndComments:
    """Verify import formatting and comment preservation."""

    def test_import_statement(self) -> None:
        """Format an import statement."""
        assert Formatter('import "math.pbl"').format() == 'import "math.pbl"\n'

    def test_from_import(self) -> None:
        """Format a from-import statement."""
        result = Formatter('from "math.pbl" import sqrt, pow').format()
        assert result == 'from "math.pbl" import sqrt, pow\n'

    def test_full_line_comment_preserved(self) -> None:
        """Full-line comments preserved in formatted output."""
        source = "# header\nlet x = 42"
        result = Formatter(source).format()
        assert "# header\n" in result

    def test_inline_comment_preserved(self) -> None:
        """Inline comments preserved in formatted output."""
        source = "let x = 42  # the answer"
        result = Formatter(source).format()
        assert "# the answer" in result

    def test_comment_between_statements(self) -> None:
        """Comments between statements preserved in order."""
        source = "let x = 1\n# middle\nlet y = 2"
        result = Formatter(source).format()
        lines = result.strip().split("\n")
        x_idx = next(i for i, ln in enumerate(lines) if "let x" in ln)
        comment_idx = next(i for i, ln in enumerate(lines) if "# middle" in ln)
        y_idx = next(i for i, ln in enumerate(lines) if "let y" in ln)
        assert x_idx < comment_idx < y_idx

    def test_trailing_comment_at_eof(self) -> None:
        """Trailing comment at end of file preserved."""
        source = "let x = 1\n# end"
        result = Formatter(source).format()
        assert result.strip().endswith("# end")


# -- Cycle 11: Idempotency and edge cases -------------------------------------


class TestFormatterIdempotency:
    """Verify idempotent formatting and edge cases."""

    def test_idempotent_simple(self) -> None:
        """Formatting twice produces identical output."""
        source = "let x=1+2"
        first = Formatter(source).format()
        second = Formatter(first).format()
        assert first == second

    def test_idempotent_complex(self) -> None:
        """Formatting a complex program twice is idempotent."""
        source = (
            "fn add(a: Int, b: Int) -> Int {\n"
            "    return a + b\n"
            "}\n\n"
            "if true {\n"
            "    let x = add(1, 2)\n"
            "    print(x)\n"
            "}\n"
        )
        first = Formatter(source).format()
        second = Formatter(first).format()
        assert first == second

    def test_empty_source(self) -> None:
        """Empty source produces just a newline."""
        assert Formatter("").format() == "\n"

    def test_string_escape_newline(self) -> None:
        """Escaped newline in strings preserved."""
        source = r'let s = "hello\nworld"'
        result = Formatter(source).format()
        assert r'"hello\nworld"' in result

    def test_string_escape_tab(self) -> None:
        """Escaped tab in strings preserved."""
        source = r'let s = "col1\tcol2"'
        result = Formatter(source).format()
        assert r'"col1\tcol2"' in result

    def test_string_escape_backslash(self) -> None:
        """Escaped backslash in strings preserved."""
        source = r'let s = "path\\file"'
        result = Formatter(source).format()
        assert r'"path\\file"' in result

    def test_string_escape_quote(self) -> None:
        r"""Escaped quote in strings preserved."""
        source = r'let s = "say \"hi\""'
        result = Formatter(source).format()
        assert r'"say \"hi\""' in result

    def test_string_escape_brace(self) -> None:
        r"""Escaped brace in strings preserved."""
        source = r'let s = "use \{braces}"'
        result = Formatter(source).format()
        assert r"\{braces}" in result

    def test_string_escape_null(self) -> None:
        r"""Escaped null in strings preserved."""
        source = r'let s = "null\0byte"'
        result = Formatter(source).format()
        assert r'"null\0byte"' in result

    def test_expression_statement(self) -> None:
        """Bare function calls formatted as expression statements."""
        source = "fn greet() { return 1 }\ngreet()"
        result = Formatter(source).format()
        assert "greet()\n" in result

    def test_function_call_expression_statement(self) -> None:
        """Function call as expression statement with args."""
        source = "fn add(a, b) { return a + b }\nadd(1, 2)"
        result = Formatter(source).format()
        assert "add(1, 2)\n" in result

    def test_await_expression(self) -> None:
        """Format await expression."""
        source = "async fn fetch(url) { return await get(url) }"
        result = Formatter(source).format()
        assert "await get(url)" in result
