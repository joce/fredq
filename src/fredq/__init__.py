"""Fully-typed FRED data, one call at a time.

fredq is a synchronous library over the FRED (Federal Reserve Economic
Data) API — ``import fredq`` then
``obs = fredq.Series("DGS10").observations()`` for a polars-backed frame,
or ``fredq.Series("DGS10").info()`` for the series record — plus an
LLM-friendly CLI (``fredq --help``) that prints raw FRED JSON.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

# __version__ is derived from the git tag by hatch-vcs and written to
# _version.py at build/install time (see pyproject.toml [tool.hatch.version]).
from fredq._version import __version__
from fredq.exceptions import (
    FredApiError,
    FredApiKeyMissingError,
    FredClientUsageError,
    FredqError,
    FredRequestError,
    FredUnavailableError,
)

if TYPE_CHECKING:
    # Real imports for type checkers only; at runtime these resolve lazily
    # via __getattr__ below so importing the fredq package (which the CLI
    # does by virtue of fredq.cli being a submodule) never pays the polars
    # import cost. Keep this block in manual parity with __all__ and
    # __getattr__'s routing (test_all_names_are_importable is the gate).
    from fredq.api import (
        Category,
        Release,
        Series,
        Source,
        configure,
        raw,
        related_tags,
        release_calendar,
        releases,
        search_series,
        search_series_related_tags,
        search_series_tags,
        series_updates,
        sources,
        tag_series,
        tags,
    )
    from fredq.frames import Frame, FrameShapeError, Observations


# PEP 562 module __getattr__
def __getattr__(name: str) -> Any:  # ruff: ignore[any-type]
    """Lazily import heavy public names on first access (PEP 562).

    Returns:
        Any: The resolved attribute, also cached on the module for reuse.

    Raises:
        AttributeError: If ``name`` is not a lazily-exported attribute.
    """

    frames_names = {"Frame", "FrameShapeError", "Observations"}
    lazy_names = set(__all__) - set(globals())
    if name in frames_names:
        module_name = "fredq.frames"
    elif name in lazy_names:
        module_name = "fredq.api"
    else:
        message = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(message)
    module = importlib.import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """List the public surface plus dunders, hiding internal imports.

    Returns:
        list[str]: Sorted attributes for dir() and tab completion.
    """

    return sorted(set(__all__) | {name for name in globals() if name.startswith("__")})


__all__ = [
    "Category",
    "Frame",
    "FrameShapeError",
    "FredApiError",
    "FredApiKeyMissingError",
    "FredClientUsageError",
    "FredRequestError",
    "FredUnavailableError",
    "FredqError",
    "Observations",
    "Release",
    "Series",
    "Source",
    "__version__",
    "configure",
    "raw",
    "related_tags",
    "release_calendar",
    "releases",
    "search_series",
    "search_series_related_tags",
    "search_series_tags",
    "series_updates",
    "sources",
    "tag_series",
    "tags",
]
