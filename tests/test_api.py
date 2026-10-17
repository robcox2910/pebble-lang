"""Tests for Pebble's public API -- the front door for running Pebble from Python.

Each run gets its own extra modules, so two programs running side by side
can never see (or remove) each other's modules, and Pebble's shared table
of built-in modules is never changed.
"""

import io
import threading
from pathlib import Path

import pytest

from pebble import (
    PebbleError,
    Program,
    StdlibModule,
    Value,
    check,
    compile_source,
    format_source,
    run_source,
)
from pebble.stdlib import STDLIB_MODULES

RUNS_PER_THREAD = 50


def _constant_module(name: str, result: str) -> StdlibModule:
    """Return a module with one function, ``name()``, that always returns *result*."""

    def handler(_args: list[Value]) -> Value:
        return result

    return StdlibModule(functions={name: (0, handler)}, constants={})


def _hello(args: list[Value]) -> Value:
    """Greet whoever is named in the first argument."""
    return f"hello {args[0]}"


GREET = StdlibModule(functions={"hello": (1, _hello)}, constants={})


class TestRunSource:
    """``run_source`` compiles and runs a program, returning what it printed."""

    def test_returns_what_the_program_printed(self) -> None:
        """The program's printed text comes back as a string."""
        assert run_source('print("hi")') == "hi\n"

    def test_also_writes_to_a_given_output(self) -> None:
        """When given an output stream, the printed text is written there too."""
        out = io.StringIO()
        run_source("print(1)", output=out)
        assert out.getvalue() == "1\n"

    def test_extra_module_is_importable_for_that_run_only(self) -> None:
        """A module passed with ``modules=`` works in that run and no other."""
        source = 'import "greet"\nprint(hello("Ada"))'
        assert run_source(source, modules={"greet": GREET}) == "hello Ada\n"
        with pytest.raises(PebbleError):
            run_source(source)

    def test_shared_builtin_table_is_never_changed(self) -> None:
        """Running with extra modules leaves Pebble's built-in table alone."""
        before = dict(STDLIB_MODULES)
        run_source('import "greet"\nprint(hello("x"))', modules={"greet": GREET})
        assert before == STDLIB_MODULES

    def test_module_named_like_a_builtin_is_rejected(self) -> None:
        """A module can't silently replace a built-in like ``math``."""
        with pytest.raises(ValueError, match="math"):
            run_source("print(1)", modules={"math": GREET})

    def test_concurrent_runs_keep_their_own_modules(self) -> None:
        """Two threads running at once each only ever see their own module."""
        source = 'import "who"\nprint(who())'
        failures: list[str] = []

        def worker(letter: str) -> None:
            modules = {"who": _constant_module("who", letter)}
            for _ in range(RUNS_PER_THREAD):
                result = run_source(source, modules=modules)
                if result != f"{letter}\n":
                    failures.append(f"{letter} saw {result!r}")

        threads = [threading.Thread(target=worker, args=(letter,)) for letter in "AB"]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert failures == []

    def test_base_dir_controls_file_imports(self, tmp_path: Path) -> None:
        """``import "file.pbl"`` looks in ``base_dir``."""
        (tmp_path / "lib.pbl").write_text("fn double(n) {\n    return n * 2\n}\n")
        source = 'import "lib.pbl"\nprint(double(4))'
        assert run_source(source, base_dir=tmp_path) == "8\n"


class TestCompileSource:
    """``compile_source`` checks a program once so it can be run many times."""

    def test_program_runs_more_than_once(self) -> None:
        """A compiled program can be run again and gives the same output."""
        program = compile_source("print(2)")
        assert isinstance(program, Program)
        assert program.run() == "2\n"
        assert program.run() == "2\n"

    def test_type_errors_surface_at_compile_time(self) -> None:
        """Mistakes are reported when compiling, before anything runs."""
        with pytest.raises(PebbleError, match="expected Int"):
            compile_source('let x: Int = "no"')


class TestCheckAndFormat:
    """``check`` and ``format_source`` work on source text without running it."""

    def test_check_accepts_valid_source(self) -> None:
        """Valid source passes the check quietly."""
        check("let x = 1")

    def test_check_rejects_invalid_source(self) -> None:
        """Source that doesn't parse raises a PebbleError."""
        with pytest.raises(PebbleError):
            check("let = 1")

    def test_format_source_is_canonical(self) -> None:
        """Messy spacing comes back in Pebble's one tidy style."""
        assert format_source("let   x=1") == "let x = 1\n"

    def test_format_source_rejects_invalid(self) -> None:
        """Formatting refuses source that doesn't parse."""
        with pytest.raises(PebbleError):
            format_source("let = 1")
