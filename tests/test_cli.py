"""End-to-end CLI tests for fredq."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Final

import pytest

from fredq.cli import build_parser, main

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock

    from fredq.types import ParamValue

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
    # Redirect Path.home() on every platform so the real ~/.fredq/api_key
    # cannot leak into the test.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
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
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    rc = main(["series", "--series-id", "GNPCA"])

    captured = capsys.readouterr()
    assert rc == EXIT_USAGE
    assert "FRED API key" in captured.err


# A3 — non-ASCII body round-trips without raising


def test_main_non_ascii_body_does_not_crash(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A response body containing non-ASCII characters is written without crashing.

    Uses ``io.StringIO`` streams so the test is platform-independent;
    the important assertion is that no UnicodeEncodeError is raised.
    """

    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    body = '{"note": "café"}'
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://api.stlouisfed.org/fred/series?"
            "series_id=GNPCA&api_key=secret&file_type=json"
        ),
        text=body,
    )

    out = io.StringIO()
    err = io.StringIO()
    rc = main(["series", "--series-id", "GNPCA"], stdout=out, stderr=err)

    assert rc == EXIT_OK
    assert "é" in out.getvalue()


# B4 — frequency allowed-values validation


def test_invalid_frequency_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An unrecognized --frequency value is rejected before any HTTP call."""

    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    out = io.StringIO()
    err = io.StringIO()
    rc = main(
        ["series-observations", "--series-id", "GNPCA", "--frequency", "xyz"],
        stdout=out,
        stderr=err,
    )

    assert rc != EXIT_OK
    assert "unsupported value" in err.getvalue() or "xyz" in err.getvalue()


def test_valid_frequency_end_of_period_accepted(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """End-of-period frequency suffixes like 'q-e' and 'm-ss' are accepted."""

    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://api.stlouisfed.org/fred/series/observations?"
            "series_id=GNPCA&frequency=q-e&api_key=secret&file_type=json"
        ),
        text='{"observations": []}',
    )

    out = io.StringIO()
    err = io.StringIO()
    rc = main(
        ["series-observations", "--series-id", "GNPCA", "--frequency", "q-e"],
        stdout=out,
        stderr=err,
    )

    assert rc == EXIT_OK


def test_valid_frequency_smooth_seasonal_accepted(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Smooth-seasonal frequency 'm-ss' is accepted."""

    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://api.stlouisfed.org/fred/series/observations?"
            "series_id=GNPCA&frequency=m-ss&api_key=secret&file_type=json"
        ),
        text='{"observations": []}',
    )

    out = io.StringIO()
    err = io.StringIO()
    rc = main(
        ["series-observations", "--series-id", "GNPCA", "--frequency", "m-ss"],
        stdout=out,
        stderr=err,
    )

    assert rc == EXIT_OK


# B6 — --no-key-file and FREDQ_DISABLE_KEY_FILE


def test_no_key_file_flag_skips_file_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """--no-key-file causes FredApiKeyMissingError even when key file exists."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    key_file = tmp_path / ".fredq" / "api_key"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text("from-file\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    out = io.StringIO()
    err = io.StringIO()
    rc = main(
        ["--no-key-file", "series", "--series-id", "GNPCA"],
        stdout=out,
        stderr=err,
    )

    assert rc == EXIT_USAGE
    assert "FRED API key" in err.getvalue()


def test_fredq_disable_key_file_env_skips_file_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FREDQ_DISABLE_KEY_FILE=1 skips the key file even when it exists."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setenv("FREDQ_DISABLE_KEY_FILE", "1")
    key_file = tmp_path / ".fredq" / "api_key"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text("from-file\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    out = io.StringIO()
    err = io.StringIO()
    rc = main(
        ["series", "--series-id", "GNPCA"],
        stdout=out,
        stderr=err,
    )

    assert rc == EXIT_USAGE
    assert "FRED API key" in err.getvalue()


# C6 — verbose does not leak api_key; FredRequestError URL is redacted


def test_verbose_does_not_include_api_key_in_logs(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--verbose debug logging must never emit the FRED API key."""

    import logging  # noqa: PLC0415

    monkeypatch.setenv("FRED_API_KEY", "my-secret-api-key")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://api.stlouisfed.org/fred/series?"
            "series_id=GNPCA&api_key=my-secret-api-key&file_type=json"
        ),
        text='{"seriess": []}',
    )

    with caplog.at_level(logging.DEBUG):
        out = io.StringIO()
        err = io.StringIO()
        rc = main(
            ["--verbose", "series", "--series-id", "GNPCA"],
            stdout=out,
            stderr=err,
        )

    assert rc == EXIT_OK
    for record in caplog.records:
        assert "my-secret-api-key" not in record.getMessage()


def test_fred_request_error_url_has_no_api_key(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FredRequestError written to stderr must not contain api_key= or its value."""

    monkeypatch.setenv("FRED_API_KEY", "top-secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://api.stlouisfed.org/fred/series?"
            "series_id=GNPCA&api_key=top-secret&file_type=json"
        ),
        status_code=403,
    )

    out = io.StringIO()
    err = io.StringIO()
    rc = main(["series", "--series-id", "GNPCA"], stdout=out, stderr=err)

    assert rc == 1
    err_text = err.getvalue()
    assert "top-secret" not in err_text
    assert "api_key=" not in err_text


# Item 4 — parse_boolean for FREDQ_DISABLE_KEY_FILE


def _make_key_file(tmp_path: Path, key: str = "from-file") -> None:
    """Write a key file at the standard location under tmp_path."""

    key_file = tmp_path / ".fredq" / "api_key"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text(f"{key}\n", encoding="utf-8")


def test_fredq_disable_key_file_1_disables(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FREDQ_DISABLE_KEY_FILE=1 skips the key file."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setenv("FREDQ_DISABLE_KEY_FILE", "1")
    _make_key_file(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    out = io.StringIO()
    err = io.StringIO()
    rc = main(["series", "--series-id", "GNPCA"], stdout=out, stderr=err)

    assert rc == EXIT_USAGE
    assert "FRED API key" in err.getvalue()


def test_fredq_disable_key_file_true_disables(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FREDQ_DISABLE_KEY_FILE=true skips the key file."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setenv("FREDQ_DISABLE_KEY_FILE", "true")
    _make_key_file(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    out = io.StringIO()
    err = io.StringIO()
    rc = main(["series", "--series-id", "GNPCA"], stdout=out, stderr=err)

    assert rc == EXIT_USAGE
    assert "FRED API key" in err.getvalue()


def test_fredq_disable_key_file_yes_mixed_case_disables(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FREDQ_DISABLE_KEY_FILE=YES (mixed case) skips the key file."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setenv("FREDQ_DISABLE_KEY_FILE", "YES")
    _make_key_file(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    out = io.StringIO()
    err = io.StringIO()
    rc = main(["series", "--series-id", "GNPCA"], stdout=out, stderr=err)

    assert rc == EXIT_USAGE
    assert "FRED API key" in err.getvalue()


def test_fredq_disable_key_file_0_does_not_disable(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FREDQ_DISABLE_KEY_FILE=0 must NOT disable the key file (regression fix)."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setenv("FREDQ_DISABLE_KEY_FILE", "0")
    _make_key_file(tmp_path, key="from-file-key")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://api.stlouisfed.org/fred/series?"
            "series_id=GNPCA&api_key=from-file-key&file_type=json"
        ),
        text='{"seriess": []}',
    )

    out = io.StringIO()
    err = io.StringIO()
    rc = main(["series", "--series-id", "GNPCA"], stdout=out, stderr=err)

    assert rc == EXIT_OK


def test_fredq_disable_key_file_false_does_not_disable(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FREDQ_DISABLE_KEY_FILE=false must NOT disable the key file."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setenv("FREDQ_DISABLE_KEY_FILE", "false")
    _make_key_file(tmp_path, key="from-file-key")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://api.stlouisfed.org/fred/series?"
            "series_id=GNPCA&api_key=from-file-key&file_type=json"
        ),
        text='{"seriess": []}',
    )

    out = io.StringIO()
    err = io.StringIO()
    rc = main(["series", "--series-id", "GNPCA"], stdout=out, stderr=err)

    assert rc == EXIT_OK


def test_fredq_disable_key_file_empty_does_not_disable(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FREDQ_DISABLE_KEY_FILE= (empty) must NOT disable the key file."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setenv("FREDQ_DISABLE_KEY_FILE", "")
    _make_key_file(tmp_path, key="from-file-key")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://api.stlouisfed.org/fred/series?"
            "series_id=GNPCA&api_key=from-file-key&file_type=json"
        ),
        text='{"seriess": []}',
    )

    out = io.StringIO()
    err = io.StringIO()
    rc = main(["series", "--series-id", "GNPCA"], stdout=out, stderr=err)

    assert rc == EXIT_OK


def test_fredq_disable_key_file_garbage_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FREDQ_DISABLE_KEY_FILE=garbage exits with code 2 and an error message."""

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setenv("FREDQ_DISABLE_KEY_FILE", "garbage")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    out = io.StringIO()
    err = io.StringIO()
    rc = main(["series", "--series-id", "GNPCA"], stdout=out, stderr=err)

    assert rc == EXIT_USAGE
    assert "FREDQ_DISABLE_KEY_FILE" in err.getvalue()
    assert "garbage" in err.getvalue()


def test_fredq_disable_key_file_garbage_with_empty_api_key_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FREDQ_DISABLE_KEY_FILE=garbage exits 2 even when FRED_API_KEY is set but empty.

    Regression: when FRED_API_KEY="" (set but empty) the env var parse failure
    must still exit 2 immediately, not fall through to the key file or succeed
    via any other mechanism.
    """

    monkeypatch.setenv("FRED_API_KEY", "")
    monkeypatch.setenv("FREDQ_DISABLE_KEY_FILE", "garbage")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    out = io.StringIO()
    err = io.StringIO()
    rc = main(["series", "--series-id", "GNPCA"], stdout=out, stderr=err)

    assert rc == EXIT_USAGE
    assert "invalid boolean value" in err.getvalue()
    assert "garbage" in err.getvalue()


# Item 5 — DI smoke test for _FredClientProtocol


class _FakeFredClient:
    """Minimal fake satisfying _FredClientProtocol for DI testing."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, ParamValue]]] = []
        self.closed = False

    async def get(
        self,
        path: str,
        params: dict[str, ParamValue],
        *,
        base_url: str | None = None,  # noqa: ARG002
    ) -> str:
        self.calls.append((path, dict(params)))
        return self.response

    async def aclose(self) -> None:
        self.closed = True


def test_di_fake_client_used_without_http() -> None:
    """main() with a fake client exercises _FredClientProtocol without real HTTP."""

    fake = _FakeFredClient('{"seriess": [{"id": "GNPCA"}]}')
    out = io.StringIO()
    err = io.StringIO()

    rc = main(
        ["series", "--series-id", "GNPCA"],
        client=fake,
        stdout=out,
        stderr=err,
    )

    assert rc == EXIT_OK
    # Fake was called with the expected path and series_id param.
    assert len(fake.calls) == 1
    path, params = fake.calls[0]
    assert path == "/fred/series"
    assert params.get("series_id") == "GNPCA"
    # No real HTTP was made (no httpx_mock needed).
    # Response body written to stdout.
    assert '"GNPCA"' in out.getvalue()
    assert fake.closed
