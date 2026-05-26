"""Tests for FRED API key resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from fredq.auth import resolve_api_key
from fredq.exceptions import FredApiKeyMissingError

if TYPE_CHECKING:
    from pathlib import Path


def test_explicit_key_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Explicit override beats the environment and the file fallback."""

    monkeypatch.setenv("FRED_API_KEY", "from-env")
    key_file = tmp_path / "key"
    key_file.write_text("from-file\n", encoding="utf-8")

    assert resolve_api_key(explicit="from-cli", key_path=key_file) == "from-cli"


def test_env_used_when_no_explicit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The environment variable beats the file fallback."""

    monkeypatch.setenv("FRED_API_KEY", "from-env")
    key_file = tmp_path / "key"
    key_file.write_text("from-file\n", encoding="utf-8")

    assert resolve_api_key(key_path=key_file) == "from-env"


def test_file_used_when_no_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The fallback file is used when no environment variable is set."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    key_file = tmp_path / "key"
    key_file.write_text("from-file\n", encoding="utf-8")

    assert resolve_api_key(key_path=key_file) == "from-file"


def test_missing_key_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No key anywhere raises FredApiKeyMissingError."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    key_file = tmp_path / "key"  # not created

    with pytest.raises(FredApiKeyMissingError):
        resolve_api_key(key_path=key_file)


def test_empty_file_treated_as_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A blank key file is not a valid source."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    key_file = tmp_path / "key"
    key_file.write_text("\n", encoding="utf-8")

    with pytest.raises(FredApiKeyMissingError):
        resolve_api_key(key_path=key_file)
