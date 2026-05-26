"""FRED API key resolution."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from fredq.exceptions import FredApiKeyMissingError

_ENV_VAR: Final[str] = "FRED_API_KEY"


def default_key_path() -> Path:
    """Return fredq's default API key file path.

    Returns:
        Path: Default location for the FRED API key file.
    """

    return Path.home() / ".fredq" / "api_key"


def _read_key_file(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        contents = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not contents:
        return None
    # Take only the first non-empty line so trailing whitespace or a
    # comment-style second line cannot leak into the request.
    return contents.splitlines()[0].strip() or None


def resolve_api_key(
    *,
    explicit: str | None = None,
    key_path: Path | None = None,
) -> str:
    """Resolve the FRED API key.

    Lookup order:
        1. ``explicit`` argument (e.g. from a CLI override).
        2. ``FRED_API_KEY`` environment variable.
        3. Single-line file at ``key_path`` (defaults to ``~/.fredq/api_key``).

    Args:
        explicit: Explicit API key from a CLI override; ignored when ``None``.
        key_path: Override the fallback file path. Defaults to
            :func:`default_key_path`.

    Returns:
        str: A non-empty FRED API key.

    Raises:
        FredApiKeyMissingError: If no key can be located by any mechanism.
    """

    if explicit:
        stripped = explicit.strip()
        if stripped:
            return stripped

    env_value = os.environ.get(_ENV_VAR, "").strip()
    if env_value:
        return env_value

    path = key_path or default_key_path()
    from_file = _read_key_file(path)
    if from_file:
        return from_file

    raise FredApiKeyMissingError
