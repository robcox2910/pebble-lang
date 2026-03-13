"""Smoke tests to verify the project scaffold and CLI are working."""

from __future__ import annotations

import subprocess
import sys
from textwrap import dedent
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

import pebble
from pebble.cli import main

if TYPE_CHECKING:
    from pathlib import Path

# -- Named constants ----------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_FAILURE = 1


class TestSmoke:
    """Verify basic project setup."""

    def test_package_is_importable(self) -> None:
        """Verify the pebble package can be imported."""
        assert pebble.__name__ == "pebble"


class TestCLIInProcess:
    """Verify the CLI entry point via direct function calls."""

    def test_no_args_starts_repl(self) -> None:
        """``main()`` with no args starts the REPL (exits on EOF)."""
        with patch("sys.argv", ["pebble"]), patch("builtins.input", side_effect=EOFError):
            main()  # Should return normally, not sys.exit(1)

    def test_run_pbl_file(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """``main()`` runs a .pbl file through the full pipeline."""
        pbl = tmp_path / "hello.pbl"
        pbl.write_text("print(42)")
        with patch("sys.argv", ["pebble", str(pbl)]):
            main()
        assert capsys.readouterr().out == "42\n"

    def test_pebble_error_exits_with_error(self, tmp_path: Path) -> None:
        """A PebbleError prints the error message and exits 1."""
        pbl = tmp_path / "bad.pbl"
        pbl.write_text("let = oops")
        with patch("sys.argv", ["pebble", str(pbl)]), pytest.raises(SystemExit, match="1"):
            main()


class TestCLI:
    """Verify the ``pebble`` CLI entry point via subprocess."""

    def test_no_args_starts_repl(self) -> None:
        """Running without arguments starts REPL (exits on empty stdin)."""
        result = subprocess.run(
            [sys.executable, "-m", "pebble"],
            input="",
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == EXIT_SUCCESS

    def test_run_pbl_file(self, tmp_path: Path) -> None:
        """Running a .pbl file produces the expected output."""
        pbl = tmp_path / "hello.pbl"
        pbl.write_text(
            dedent("""\
            print(1 + 2)
        """)
        )
        result = subprocess.run(
            [sys.executable, "-m", "pebble", str(pbl)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == EXIT_SUCCESS
        assert result.stdout.strip() == "3"

    def test_run_full_program(self, tmp_path: Path) -> None:
        """Run a multi-feature Pebble program through the CLI."""
        pbl = tmp_path / "program.pbl"
        pbl.write_text(
            dedent("""\
            fn add(a, b) { return a + b }
            let x = add(10, 20)
            print(x)
            for i in range(3) {
                print(i)
            }
        """)
        )
        result = subprocess.run(
            [sys.executable, "-m", "pebble", str(pbl)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == EXIT_SUCCESS
        assert result.stdout == "30\n0\n1\n2\n"

    def test_syntax_error_exits_with_error(self, tmp_path: Path) -> None:
        """A syntax error in the source prints an error to stderr."""
        pbl = tmp_path / "bad.pbl"
        pbl.write_text("let = oops")
        result = subprocess.run(
            [sys.executable, "-m", "pebble", str(pbl)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == EXIT_FAILURE
        assert "Expected variable name" in result.stderr
