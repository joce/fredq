"""Tests for the lazy public package surface."""

from __future__ import annotations

import subprocess
import sys

import pytest

import fredq


def test_all_names_are_importable() -> None:
    """Every name in __all__ resolves at runtime (lazy-routing parity)."""

    for name in fredq.__all__:
        assert getattr(fredq, name) is not None, name


def test_dir_lists_public_surface() -> None:
    """dir() exposes __all__ (tab completion) without internals."""

    listed = dir(fredq)
    assert set(fredq.__all__) <= set(listed)
    assert "importlib" not in listed


def test_unknown_attribute_raises() -> None:
    """PEP 562 fallback raises AttributeError for unknown names."""

    with pytest.raises(AttributeError, match="definitely_not_a_thing"):
        _ = fredq.definitely_not_a_thing  # type: ignore[attr-defined]


def test_importing_fredq_stays_light() -> None:
    """`import fredq` must not pull polars or the api layer (CLI cost)."""

    code = (
        "import sys; import fredq; "
        "heavy = {'polars', 'fredq.api', 'fredq.frames'} & set(sys.modules); "
        "print(sorted(heavy))"
    )
    out = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "[]"


def test_cli_module_stays_light() -> None:
    """Importing the CLI never pays for polars either."""

    code = "import sys; import fredq.cli; print('polars' in sys.modules)"
    out = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"


def test_cli_help_defers_http_stack_on_lazy_import_pythons() -> None:
    """Building the parser skips httpx2/asyncio where PEP 810 applies (3.15+)."""

    code = (
        "import sys; import fredq.cli; fredq.cli.build_parser(); "
        "print(sorted({'asyncio', 'httpx2'} & set(sys.modules)))"
    )
    out = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    # __lazy_modules__ is ignored before 3.15, where these load eagerly.
    lazy_imports_supported = sys.version_info >= (3, 15)
    expected = "[]" if lazy_imports_supported else "['asyncio', 'httpx2']"
    assert out.stdout.strip() == expected


def test_lazy_names_resolve_to_api_objects() -> None:
    """Spot-check the lazy routing targets."""

    from fredq.api import Series  # ruff: ignore[import-outside-top-level]
    from fredq.frames import Frame  # ruff: ignore[import-outside-top-level]

    assert fredq.Series is Series
    assert fredq.Frame is Frame


def test_configure_is_the_core_configure() -> None:
    """fredq.configure is the singleton-config entry point, one object."""

    from fredq._core import configure  # ruff: ignore[import-outside-top-level]

    assert fredq.configure is configure
