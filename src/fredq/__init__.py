"""Expose FRED (Federal Reserve Economic Data) endpoints as a raw JSON CLI."""

from __future__ import annotations

# __version__ is derived from the git tag by hatch-vcs and written to
# _version.py at build/install time (see pyproject.toml [tool.hatch.version]).
from fredq._version import __version__

__all__ = ["__version__"]
