"""End-to-end CLI tests for fredq."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest

from fredq.cli import build_parser, main

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock

EXIT_USAGE: Final[int] = 2
EXIT_OK: Final[int] = 0


def test_parser_lists_known_commands() -> None:
    """The parser exposes every command defined in COMMANDS."""

    parser = build_parser()
    help_text = parser.format_help()

    assert "series" in help_text
    assert "series-observations" in help_text


def test_main_help_exits_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    """``fredq --help`` prints help and exits with code 0."""

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "fredq" in captured.out.lower()
    assert "series" in captured.out


def test_main_without_command_prints_help_and_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No subcommand is treated as a usage error (exit 2)."""

    rc = main([])

    captured = capsys.readouterr()
    assert rc == EXIT_USAGE
    assert "series" in captured.out


def test_main_series_command_prints_raw_body(
    httpx_mock: HTTPXMock,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A successful series call prints the raw FRED JSON body to stdout."""

    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))  # isolate key-file fallback
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://api.stlouisfed.org/fred/series?"
            "series_id=GNPCA&api_key=secret&file_type=json"
        ),
        text='{"seriess": [{"id": "GNPCA"}]}',
    )

    rc = main(["series", "--series-id", "GNPCA"])

    captured = capsys.readouterr()
    assert rc == EXIT_OK
    assert '"seriess"' in captured.out
    assert '"GNPCA"' in captured.out


def test_main_missing_key_errors_cleanly(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Missing API key surfaces a clear stderr message and exits non-zero."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    rc = main(["series", "--series-id", "GNPCA"])

    captured = capsys.readouterr()
    assert rc == EXIT_USAGE
    assert "FRED API key" in captured.err
