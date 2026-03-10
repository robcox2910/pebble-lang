"""Smoke tests to verify the project scaffold is working."""

import pebble
from pebble.cli import main


class TestSmoke:
    """Verify basic project setup."""

    def test_package_is_importable(self) -> None:
        """Verify the pebble package can be imported."""
        assert pebble.__name__ == "pebble"

    def test_cli_entry_point_exists(self) -> None:
        """Verify the CLI entry point is callable."""
        assert callable(main)

    def test_cli_runs_without_error(self) -> None:
        """Verify the CLI entry point runs without raising."""
        main()
