"""Cheap import / package-shape sanity checks."""

from __future__ import annotations

from pathlib import Path

import fredq
from fredq.commands import COMMANDS


def test_version_string_is_populated() -> None:
    """``fredq.__version__`` exposes a non-empty string."""

    assert isinstance(fredq.__version__, str)
    assert fredq.__version__


def test_commands_have_unique_names() -> None:
    """Command names are unique."""

    names = [c.name for c in COMMANDS]
    assert len(names) == len(set(names))


def test_commands_paths_are_rooted() -> None:
    """All endpoint paths start with ``/fred/`` or ``/geofred/``."""

    for command in COMMANDS:
        assert command.path.startswith(("/fred/", "/geofred/")), command.path


def test_py_typed_marker_ships_with_the_package() -> None:
    """PEP 561: the wheel must carry py.typed for downstream type checkers."""

    marker = Path(fredq.__file__).parent / "py.typed"
    assert marker.is_file()
