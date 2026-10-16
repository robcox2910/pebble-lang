"""Tests for ``pebble fmt`` -- the tidy-up command that rewrites your file.

Because ``pebble fmt`` overwrites your file in place, it must never save
something broken: if the tidied code wouldn't parse, it refuses and leaves
your original untouched.
"""

from pathlib import Path

import pytest

from pebble import cli
from pebble.formatter import Formatter


def test_fmt_tidies_a_file_in_place(tmp_path: Path) -> None:
    """A messy but valid file is rewritten in the canonical style."""
    path = tmp_path / "shapes.pbl"
    path.write_text("struct Point { x, y }\n")
    cli._run_fmt([str(path)])  # pyright: ignore[reportPrivateUsage]
    assert path.read_text() == "struct Point {\n    x,\n    y\n}\n"


def test_fmt_refuses_to_save_code_that_would_not_parse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """If tidying ever produced broken code, the original file is kept safe."""
    path = tmp_path / "keep_me.pbl"
    original = "let x = 1\n"
    path.write_text(original)

    def broken_format(_self: Formatter) -> str:
        return "let = broken\n"

    monkeypatch.setattr(Formatter, "format", broken_format)
    with pytest.raises(SystemExit) as exit_info:
        cli._run_fmt([str(path)])  # pyright: ignore[reportPrivateUsage]
    assert exit_info.value.code == 1
    assert path.read_text() == original
    assert "refusing to write" in capsys.readouterr().err
