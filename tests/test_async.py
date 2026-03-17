"""Tests for async/await — simulated concurrency in Pebble."""

import pytest

from pebble.analyzer import SemanticAnalyzer
from pebble.ast_nodes import Assignment, AsyncFunctionDef, AwaitExpression
from pebble.bytecode import OpCode
from pebble.errors import PebbleRuntimeError, SemanticError
from pebble.lexer import Lexer
from pebble.parser import Parser
from pebble.tokens import TokenKind
from tests.conftest import compile_source, run_source

# -- Named constants ----------------------------------------------------------

FIRST_LINE = 1
FIRST_COLUMN = 1
ASYNC_FN_PARAM_COUNT = 2


# =============================================================================
# Cycle 1: Tokens
# =============================================================================


class TestAsyncAwaitTokens:
    """Verify ASYNC and AWAIT token kinds and keyword mapping."""

    def test_async_in_token_kind(self) -> None:
        """ASYNC should be a member of TokenKind."""
        assert TokenKind.ASYNC == "ASYNC"

    def test_await_in_token_kind(self) -> None:
        """AWAIT should be a member of TokenKind."""
        assert TokenKind.AWAIT == "AWAIT"

    def test_async_keyword_maps(self) -> None:
        """The keyword 'async' should lex as ASYNC."""
        tokens = Lexer("async").tokenize()
        assert tokens[0].kind == TokenKind.ASYNC

    def test_await_keyword_maps(self) -> None:
        """The keyword 'await' should lex as AWAIT."""
        tokens = Lexer("await").tokenize()
        assert tokens[0].kind == TokenKind.AWAIT


# =============================================================================
# Cycle 2: Parser
# =============================================================================


class TestAsyncFunctionParser:
    """Verify async fn definitions parse correctly."""

    def test_async_fn_parses(self) -> None:
        """``async fn foo() { ... }`` should produce an AsyncFunctionDef node."""
        source = "async fn fetch() { return 42 }"
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        assert len(program.statements) == 1
        node = program.statements[0]
        assert isinstance(node, AsyncFunctionDef)
        assert node.name == "fetch"
        assert len(node.parameters) == 0

    def test_async_fn_with_params(self) -> None:
        """``async fn foo(x, y) { ... }`` should capture parameters."""
        source = "async fn add(x, y) { return x + y }"
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        node = program.statements[0]
        assert isinstance(node, AsyncFunctionDef)
        assert len(node.parameters) == ASYNC_FN_PARAM_COUNT
        assert node.parameters[0].name == "x"
        assert node.parameters[1].name == "y"

    def test_async_fn_with_return_type(self) -> None:
        """``async fn foo() -> Int { ... }`` should capture return type."""
        source = "async fn get_num() -> Int { return 42 }"
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        node = program.statements[0]
        assert isinstance(node, AsyncFunctionDef)
        assert node.return_type is not None
        assert node.return_type.name == "Int"


class TestAwaitParser:
    """Verify await expressions parse correctly."""

    def test_await_parses(self) -> None:
        """``await expr`` should produce an AwaitExpression node."""
        source = "async fn foo() { let x = await bar() }"
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        fn_def = program.statements[0]
        assert isinstance(fn_def, AsyncFunctionDef)
        # let x = await bar() → Assignment whose value is AwaitExpression
        assignment = fn_def.body[0]
        assert isinstance(assignment, Assignment)
        assert isinstance(assignment.value, AwaitExpression)


# =============================================================================
# Cycle 3: Analyzer
# =============================================================================


class TestAsyncAnalyzer:
    """Verify semantic analysis of async/await."""

    def test_await_outside_async_is_error(self) -> None:
        """``await`` outside an async function should be a semantic error."""
        source = """\
fn regular() {
    let x = await sleep(1)
}
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        with pytest.raises(SemanticError, match=r"await.*async"):
            SemanticAnalyzer().analyze(program)

    def test_yield_in_async_is_error(self) -> None:
        """``yield`` inside an async function should be a semantic error."""
        source = """\
async fn gen() {
    yield 1
}
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        with pytest.raises(SemanticError, match=r"yield.*async"):
            SemanticAnalyzer().analyze(program)

    def test_valid_async_fn_passes(self) -> None:
        """A well-formed async fn should pass analysis without error."""
        source = """\
async fn fetch() {
    await sleep(1)
    return 42
}
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        SemanticAnalyzer().analyze(program)  # should not raise

    def test_async_run_arity(self) -> None:
        """async_run(expr) should be accepted as a 1-arg builtin."""
        source = """\
async fn main() { return 1 }
async_run(main())
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        SemanticAnalyzer().analyze(program)  # should not raise

    def test_spawn_arity(self) -> None:
        """spawn(expr) should be accepted as a 1-arg builtin."""
        source = """\
async fn worker() { return 1 }
async fn main() {
    let h = spawn(worker())
    return await h
}
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        SemanticAnalyzer().analyze(program)  # should not raise

    def test_sleep_arity(self) -> None:
        """sleep(n) should be accepted as a 1-arg builtin."""
        source = """\
async fn main() {
    await sleep(2)
}
"""
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        SemanticAnalyzer().analyze(program)  # should not raise


# =============================================================================
# Cycle 4: Compiler
# =============================================================================


class TestAsyncCompiler:
    """Verify bytecode generation for async/await."""

    def test_async_fn_sets_is_async(self) -> None:
        """An async fn's CodeObject should have is_async=True."""
        source = """\
async fn fetch() {
    return 42
}
"""
        compiled = compile_source(source)
        assert "fetch" in compiled.functions
        fn_code = compiled.functions["fetch"]
        assert fn_code.is_async is True

    def test_await_emits_await_opcode(self) -> None:
        """An await expression should emit the AWAIT opcode."""
        source = """\
async fn fetch() {
    await sleep(1)
}
"""
        compiled = compile_source(source)
        fn_code = compiled.functions["fetch"]
        opcodes = [i.opcode for i in fn_code.instructions]
        assert OpCode.AWAIT in opcodes


# =============================================================================
# Cycle 5: Integration — end-to-end execution
# =============================================================================


class TestAsyncRunSimple:
    """Test basic async_run execution."""

    def test_async_run_simple(self) -> None:
        """async_run should run a simple async fn and return its result."""
        source = """\
async fn main() {
    return 42
}
let result = async_run(main())
print(result)
"""
        assert run_source(source) == "42\n"

    def test_async_run_returns_value(self) -> None:
        """async_run should return the final value to top-level."""
        source = """\
async fn greet() {
    return "hello"
}
let msg = async_run(greet())
print(msg)
"""
        assert run_source(source) == "hello\n"


class TestAwaitCoroutine:
    """Test await returning a value from another coroutine."""

    def test_await_returns_value(self) -> None:
        """Await on a completed coroutine should return its result."""
        source = """\
async fn get_value() {
    return 42
}
async fn main() {
    let v = await get_value()
    return v
}
let result = async_run(main())
print(result)
"""
        assert run_source(source) == "42\n"

    def test_nested_await_chains(self) -> None:
        """Await chains should resolve correctly."""
        source = """\
async fn inner() {
    return 10
}
async fn middle() {
    let x = await inner()
    return x + 5
}
async fn outer() {
    let y = await middle()
    return y * 2
}
let result = async_run(outer())
print(result)
"""
        assert run_source(source) == "30\n"


class TestSpawnAndAwait:
    """Test spawn + await handle pattern."""

    def test_spawn_await_handle(self) -> None:
        """Spawn should register a task; await on handle should return result."""
        source = """\
async fn worker() {
    return 99
}
async fn main() {
    let h = spawn(worker())
    let result = await h
    return result
}
print(async_run(main()))
"""
        assert run_source(source) == "99\n"

    def test_multiple_spawned_tasks(self) -> None:
        """Multiple spawned tasks should all complete."""
        source = """\
async fn make_value(n) {
    return n * 10
}
async fn main() {
    let h1 = spawn(make_value(1))
    let h2 = spawn(make_value(2))
    let h3 = spawn(make_value(3))
    let r1 = await h1
    let r2 = await h2
    let r3 = await h3
    print(r1)
    print(r2)
    print(r3)
}
async_run(main())
"""
        assert run_source(source) == "10\n20\n30\n"


class TestSleep:
    """Test sleep yields control and other tasks interleave."""

    def test_sleep_interleaving(self) -> None:
        """Sleep should yield control so other tasks can run."""
        source = """\
async fn task_a() {
    print("a1")
    await sleep(2)
    print("a2")
}
async fn task_b() {
    print("b1")
    await sleep(1)
    print("b2")
}
async fn main() {
    let ha = spawn(task_a())
    let hb = spawn(task_b())
    await ha
    await hb
}
async_run(main())
"""
        output = run_source(source)
        lines = output.strip().split("\n")
        # Both tasks should print their first message before either prints second
        assert "a1" in lines
        assert "b1" in lines
        assert "a2" in lines
        assert "b2" in lines
        # b sleeps less, so b2 should come before a2
        assert lines.index("b2") < lines.index("a2")

    def test_sleep_zero_ticks(self) -> None:
        """sleep(0) should still yield control but resume immediately."""
        source = """\
async fn main() {
    await sleep(0)
    return "done"
}
print(async_run(main()))
"""
        assert run_source(source) == "done\n"


class TestAsyncErrorPropagation:
    """Test error propagation through await."""

    def test_error_propagates_through_await(self) -> None:
        """An error in an awaited coroutine should propagate to the caller."""
        source = """\
async fn failing() {
    throw "boom"
}
async fn main() {
    let result = await failing()
    return result
}
async_run(main())
"""
        with pytest.raises(PebbleRuntimeError, match="boom"):
            run_source(source)


class TestCoroutineTypeAndFormat:
    """Test type() and string formatting of coroutines."""

    def test_coroutine_type(self) -> None:
        """type() on a coroutine should return 'coroutine'."""
        source = """\
async fn foo() { return 1 }
let c = foo()
print(type(c))
"""
        assert run_source(source) == "coroutine\n"

    def test_coroutine_format(self) -> None:
        """Printing a coroutine should show <coroutine name>."""
        source = """\
async fn foo() { return 1 }
let c = foo()
print(c)
"""
        assert run_source(source) == "<coroutine foo>\n"


class TestAsyncClosures:
    """Test async functions that capture variables (closures)."""

    def test_async_closure(self) -> None:
        """An async function defined in a closure should work."""
        source = """\
fn make_adder(n) {
    async fn add(x) {
        return x + n
    }
    return add
}
let adder = make_adder(10)
let result = async_run(adder(5))
print(result)
"""
        assert run_source(source) == "15\n"


class TestAsyncWithParams:
    """Test async functions with parameters."""

    def test_async_fn_with_params(self) -> None:
        """Async functions should accept and use parameters."""
        source = """\
async fn multiply(a, b) {
    return a * b
}
let result = async_run(multiply(6, 7))
print(result)
"""
        assert run_source(source) == "42\n"


class TestAsyncRunInvalidInput:
    """Test async_run with invalid arguments."""

    def test_async_run_non_coroutine(self) -> None:
        """async_run with a non-coroutine should raise a runtime error."""
        source = "async_run(42)"
        with pytest.raises(PebbleRuntimeError, match="coroutine"):
            run_source(source)

    def test_spawn_non_coroutine(self) -> None:
        """Spawn with a non-coroutine should raise a runtime error."""
        source = """\
async fn main() {
    let h = spawn(42)
}
async_run(main())
"""
        with pytest.raises(PebbleRuntimeError, match="coroutine"):
            run_source(source)

    def test_sleep_non_integer(self) -> None:
        """Sleep with a non-integer should raise a runtime error."""
        source = """\
async fn main() {
    await sleep("abc")
}
async_run(main())
"""
        with pytest.raises(PebbleRuntimeError, match="integer"):
            run_source(source)
