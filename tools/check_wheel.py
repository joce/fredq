"""Verify installed-wheel imports and resources without contacting FRED.

Run through ``uv run tox -e wheel``; isolated Python must load the installed
package rather than the source checkout.
"""

# ruff: file-ignore[assert] - assertions are the executable artifact checks.

from __future__ import annotations

import sys
from importlib.resources import files
from pathlib import Path

import fredq

assert Path(fredq.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert not Path.cwd().joinpath("pyproject.toml").exists()
for name in fredq.__all__:
    assert getattr(fredq, name) is not None, name
assert files("fredq").joinpath("py.typed").is_file()
content = files("fredq.skills").joinpath("content")
assert content.joinpath("SKILL.md").read_text(encoding="utf-8")
for domain in ("catalog", "dataframes", "observations", "revisions"):
    for name in ("README.md", "SHARP-EDGES.md"):
        assert content.joinpath(domain).joinpath(name).read_text(encoding="utf-8")
print("Installed wheel imports and bundled resources verified.")
