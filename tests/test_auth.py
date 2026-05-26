"""Tests for FRED API key resolution."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import patch

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


# C3 — auth.py edge cases


def test_read_key_file_oserror_treated_as_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """OSError while reading the key file is treated as if the key is absent."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    key_file = tmp_path / "key"
    key_file.write_text("from-file\n", encoding="utf-8")

    # Patch Path.read_text on the auth module's Path so the existing file
    # appears unreadable.
    with (
        patch("fredq.auth.Path.read_text", side_effect=OSError("permission denied")),
        pytest.raises(FredApiKeyMissingError),
    ):
        resolve_api_key(key_path=key_file)


def test_multiline_key_file_uses_first_non_empty_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When the key file has multiple lines, only the first non-empty one is used."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    key_file = tmp_path / "key"
    key_file.write_text("first-key\nsecond-line\n", encoding="utf-8")

    assert resolve_api_key(key_path=key_file) == "first-key"


def test_whitespace_only_key_file_treated_as_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A key file containing only whitespace is treated as missing."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    key_file = tmp_path / "key"
    key_file.write_text("   \n\t\n", encoding="utf-8")

    with pytest.raises(FredApiKeyMissingError):
        resolve_api_key(key_path=key_file)


# B6 — use_key_file=False skips file even when present


def test_use_key_file_false_skips_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """use_key_file=False causes the file fallback to be skipped."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    key_file = tmp_path / "key"
    key_file.write_text("from-file\n", encoding="utf-8")

    with pytest.raises(FredApiKeyMissingError):
        resolve_api_key(key_path=key_file, use_key_file=False)


# A5 — file permission warnings (POSIX only)


@pytest.mark.skipif(os.name == "nt", reason="chmod not meaningful on Windows")
def test_wide_mode_key_file_emits_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A key file with group/world read bits triggers a stderr warning."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    key_file = tmp_path / "api_key"
    key_file.write_text("mykey\n", encoding="utf-8")
    key_file.chmod(0o644)

    key = resolve_api_key(key_path=key_file)

    assert key == "mykey"
    captured = capsys.readouterr()
    assert "warning" in captured.err
    assert "chmod 600" in captured.err


@pytest.mark.skipif(os.name == "nt", reason="chmod not meaningful on Windows")
def test_tight_mode_key_file_no_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A key file with mode 600 produces no warning."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    key_file = tmp_path / "api_key"
    key_file.write_text("mykey\n", encoding="utf-8")
    key_file.chmod(0o600)

    key = resolve_api_key(key_path=key_file)

    assert key == "mykey"
    captured = capsys.readouterr()
    assert not captured.err
