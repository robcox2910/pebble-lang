"""Every Python example in "Using Pebble from Python" really runs.

The chapter's examples check their own results with ``assert``, so running
them here keeps the docs and the code from drifting apart.
"""

import re
from pathlib import Path

CHAPTER = Path(__file__).parent.parent / "docs/concepts/using-pebble-from-python.md"
MIN_EXAMPLES = 5


def test_every_python_example_in_the_chapter_runs() -> None:
    """Each fenced ``python`` block runs without raising."""
    blocks = re.findall(r"```python\n(.*?)```", CHAPTER.read_text(encoding="utf-8"), re.DOTALL)
    assert len(blocks) >= MIN_EXAMPLES
    for block in blocks:
        exec(compile(block, str(CHAPTER), "exec"), {})  # noqa: S102 -- our own docs
