"""Regression checks for the reviewed external boundaries."""

from __future__ import annotations

import io
import json
import logging
import os
import stat
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import httpx2 as httpx
import polars as pl
import pytest

from fredq import api
from fredq.auth import resolve_api_key
from fredq.cli import main
from fredq.client import (  # pyright: ignore[reportPrivateUsage]
    FredClient,
    _ApiKeyRedactFilter,  # pyright: ignore[reportPrivateUsage]
)
from fredq.commands import COMMANDS_BY_NAME
from fredq.exceptions import FredApiError, FredApiKeyMissingError, FredRequestError
from fredq.frames import Frame
from fredq.params import coerce_param, parse_date
from fredq.parquet_writer import (
    ObservationsContext,
    ParquetWriterError,
    write_observations_parquet,
)
from fredq.skills import install, uninstall

if TYPE_CHECKING:
    from collections.abc import Callable

    from fredq.skills import TargetReport

EXIT_USAGE = 2


@pytest.mark.parametrize(
    "text",
    [
        "# Example\n```yaml\nname: fredq\n```\n",
        "---\nname: fredq\nname: other\n---\n",
        "---\nname: fredq\ndescription: [broken\n---\n",
        "---\nname: fredq\ndescription: fine\n",
        "---\nname: fredq\ndescription: bad: mapping\n---\n",
        "---\nname: fredq\ndescription: bad:\n---\n",
        "---\nname: fredq\ndescription: - sequence\n---\n",
    ],
)
@pytest.mark.parametrize("operation", [install, uninstall])
def test_unowned_skill_is_preserved(
    tmp_path: Path, text: str, operation: Callable[[list[Path]], list[TargetReport]]
) -> None:
    """Unowned skill is preserved."""
    skill = tmp_path / "fredq"
    skill.mkdir()
    (skill / "SKILL.md").write_text(text)
    sentinel = skill / "keep.txt"
    sentinel.write_text("keep")
    assert operation([tmp_path])[0].action == "refused"
    assert sentinel.read_text() == "keep"


@pytest.mark.parametrize(
    "value",
    [
        "999999999999999999999999",
        "0001-01-01T00:00:00+01:00",
        "9999-12-31T23:00:00-02:00",
    ],
)
def test_date_overflow_is_value_error(value: str) -> None:
    """Date overflow is value error."""
    with pytest.raises(ValueError, match="range"):
        parse_date(value)


def test_pre_epoch_date() -> None:
    """Pre epoch date."""
    assert parse_date("-315619200") == "1960-01-01"


def test_shared_key_file_disable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Shared key file disable."""
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setenv("FREDQ_DISABLE_KEY_FILE", "1")
    key = tmp_path / "key"
    key.write_text("file-key")
    with pytest.raises(FredApiKeyMissingError):
        resolve_api_key(key_path=key)


@pytest.mark.parametrize(
    "row",
    [
        None,
        {},
        {
            "date": "bad",
            "value": "1",
            "realtime_start": "2024-01-01",
            "realtime_end": "2024-01-01",
        },
        {
            "date": "2024-01-01",
            "value": "garbage",
            "realtime_start": "2024-01-01",
            "realtime_end": "2024-01-01",
        },
    ],
)
def test_parquet_rejects_malformed_rows(tmp_path: Path, row: object) -> None:
    """Parquet rejects malformed rows."""
    destination = tmp_path / "out.parquet"
    with pytest.raises(ParquetWriterError):
        write_observations_parquet(
            json.dumps({"observations": [row]}), destination, ObservationsContext("X")
        )
    assert not destination.exists()


@pytest.mark.parametrize("surface", ["cli", "library"])
def test_failed_export_preserves_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    """Failed export preserves file."""
    destination = tmp_path / "out.parquet"
    destination.write_bytes(b"original")

    def fail(self: pl.DataFrame, file: Path, **kwargs: object) -> None:
        del self, kwargs
        Path(file).write_bytes(b"partial")
        message = "disk full"
        raise OSError(message)

    monkeypatch.setattr(pl.DataFrame, "write_parquet", fail)
    with pytest.raises(  # ruff: ignore[pytest-raises-with-multiple-statements]
        (OSError, ParquetWriterError),
    ):
        if surface == "cli":
            write_observations_parquet(
                '{"observations": []}', destination, ObservationsContext("X")
            )
        else:
            Frame(pl.DataFrame(), datetime.now(timezone.utc)).save_parquet(destination)
    assert destination.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [destination]


def test_formatter_redacts_exception_text() -> None:
    """Formatter redacts exception text."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(_ApiKeyRedactFilter())
    logger = logging.getLogger("boundary-test")
    logger.addHandler(handler)
    try:
        message = "https://example.test/?api_key=synthetic-secret"
        raise RuntimeError(message)  # ruff: ignore[raise-within-try]
    except RuntimeError:
        logger.exception("failed")
    logger.removeHandler(handler)
    handler.close()
    assert "synthetic-secret" not in stream.getvalue()


@pytest.mark.asyncio
async def test_http_traceback_hides_key() -> None:
    """Http traceback hides key."""
    key = "synthetic-secret"
    client = FredClient(key)
    request = httpx.Request("GET", "https://example.test/?api_key=" + key)
    response = httpx.Response(
        400, request=request, text='{"error_code":400,"error_message":"bad"}'
    )
    with patch.object(
        client._client,  # pyright: ignore[reportPrivateUsage]
        "request",
        return_value=response,
    ):
        try:
            with pytest.raises(FredRequestError) as caught:
                await client.get("/fred/series", {})
            assert key not in "".join(traceback.format_exception(caught.value))
        finally:
            await client.aclose()


def test_malformed_typed_response_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Malformed typed response contract."""

    def malformed(*_args: object) -> dict[str, Any]:
        return {"seriess": [{}]}

    monkeypatch.setattr(api, "_call", malformed)
    with pytest.raises(FredApiError) as caught:
        api.Series("X").info()
    assert caught.value.error_code is None


def test_unknown_format_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown format rejected."""
    monkeypatch.setenv("FRED_API_KEY", "synthetic")
    assert (
        main(
            ["series", "show", "X", "--format", "csv"],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )
        == EXIT_USAGE
    )


@pytest.mark.parametrize(
    "body", [b'{"x": 1}', b'{\r\n "x": "\xc3\xa9"\r\n}\n', b"\xef\xbb\xbf{}"]
)
def test_cli_preserves_response_bytes(body: bytes) -> None:
    """Cli preserves response bytes."""
    client = FredClient("synthetic")
    response = httpx.Response(200, content=body)
    buffer = io.BytesIO()
    output = io.TextIOWrapper(buffer, encoding="utf-8", newline="\r\n")
    with patch.object(
        client._client,  # pyright: ignore[reportPrivateUsage]
        "request",
        return_value=response,
    ):
        assert (
            main(
                ["series", "show", "X"],
                client=client,
                stdout=output,
                stderr=io.StringIO(),
            )
            == 0
        )
    output.flush()
    assert buffer.getvalue() == body


@pytest.mark.parametrize("surface", ["cli", "library"])
def test_export_preserves_existing_permissions(tmp_path: Path, surface: str) -> None:
    """Successful replacement preserves the destination permission bits."""
    destination = tmp_path / "out.parquet"
    destination.write_bytes(b"old")
    destination.chmod(0o600)
    mode = stat.S_IMODE(destination.stat().st_mode)
    if surface == "cli":
        write_observations_parquet(
            '{"observations": []}', destination, ObservationsContext("X")
        )
    else:
        Frame(pl.DataFrame(), datetime.now(timezone.utc)).save_parquet(destination)
    assert stat.S_IMODE(destination.stat().st_mode) == mode
    assert pl.read_parquet(destination).height == 0


@pytest.mark.parametrize("surface", ["cli", "library"])
def test_export_new_file_respects_umask(tmp_path: Path, surface: str) -> None:
    """New exports use ordinary file permissions filtered through the umask."""
    destination = tmp_path / "out.parquet"
    previous = os.umask(0o027)
    try:
        if surface == "cli":
            write_observations_parquet(
                '{"observations": []}', destination, ObservationsContext("X")
            )
        else:
            Frame(pl.DataFrame(), datetime.now(timezone.utc)).save_parquet(destination)
    finally:
        os.umask(previous)
    if os.name != "nt":
        expected = 0o640
        assert stat.S_IMODE(destination.stat().st_mode) == expected
    assert pl.read_parquet(destination).height == 0


@pytest.mark.parametrize("frequency", ["m-e", "q-e", "m-ss", "q-ss"])
def test_invented_frequency_codes_are_rejected(frequency: str) -> None:
    """Frequency codes cannot encode aggregation methods or seasonal smoothing."""
    spec = next(
        p
        for p in COMMANDS_BY_NAME["series-observations"].params
        if p.name == "frequency"
    )
    with pytest.raises(ValueError, match="unsupported value"):
        coerce_param(spec, frequency)


@pytest.mark.parametrize("surface", ["cli", "library"])
def test_failed_export_cleans_read_only_temporary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    """A failed write preserves its error and removes a read-only temporary."""
    destination = tmp_path / "out.parquet"
    destination.write_bytes(b"original")
    destination.chmod(0o444)

    def fail(*_args: object, **_kwargs: object) -> None:
        message = "original write failure"
        raise OSError(message)

    monkeypatch.setattr(pl.DataFrame, "write_parquet", fail)
    try:
        with pytest.raises(  # ruff: ignore[pytest-raises-with-multiple-statements]
            (OSError, ParquetWriterError),
            match="original write failure",
        ):
            if surface == "cli":
                write_observations_parquet(
                    '{"observations": []}', destination, ObservationsContext("X")
                )
            else:
                Frame(pl.DataFrame(), datetime.now(timezone.utc)).save_parquet(
                    destination
                )
        assert destination.read_bytes() == b"original"
        assert list(tmp_path.iterdir()) == [destination]
    finally:
        destination.chmod(0o600)


def test_cli_parquet_invalid_utf8_reports_error(tmp_path: Path) -> None:
    """Invalid response bytes produce a clean CLI error without an output file."""
    destination = tmp_path / "out.parquet"
    client = FredClient("synthetic")
    response = httpx.Response(200, content=b"\xff")
    stderr = io.StringIO()
    with patch.object(
        client._client,  # pyright: ignore[reportPrivateUsage]
        "request",
        return_value=response,
    ):
        result = main(
            [
                "series",
                "observations",
                "X",
                "--format",
                "parquet",
                "--out",
                str(destination),
            ],
            client=client,
            stdout=io.StringIO(),
            stderr=stderr,
        )
    expected_failure = 1
    assert result == expected_failure
    assert "valid JSON" in stderr.getvalue()
    assert not destination.exists()


@pytest.mark.parametrize("operation", [install, uninstall])
def test_truncated_header_is_not_an_eof_fence(
    tmp_path: Path, operation: Callable[[list[Path]], list[TargetReport]]
) -> None:
    """A bounded read cannot turn a longer line into a closing YAML fence."""
    skill = tmp_path / "fredq"
    skill.mkdir()
    prefix = "---\nname: fredq\ndescription: "
    limit = 16 * 1024
    text = prefix + "A" * (limit - len(prefix) - 4) + "\n---not-a-closing-fence\n"
    (skill / "SKILL.md").write_text(text, encoding="utf-8")
    sentinel = skill / "keep.txt"
    sentinel.write_text("keep")
    assert operation([tmp_path])[0].action == "refused"
    assert sentinel.read_text() == "keep"


@pytest.mark.parametrize(
    "character",
    [
        "\x7f",
        "\x80",
        "\x81",
        "\x85",
        "\x86",
        "\x9f",
        "\ufffe",
        "\uffff",
        "\u2028",
        "\u2029",
    ],
)
@pytest.mark.parametrize("operation", [install, uninstall])
def test_nonprintable_header_is_refused(
    tmp_path: Path,
    character: str,
    operation: Callable[[list[Path]], list[TargetReport]],
) -> None:
    """Control characters and Unicode line breaks cannot authorize deletion."""
    skill = tmp_path / "fredq"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        f"---\nname: fredq\ndescription: Something{character}else\n---\n",
        encoding="utf-8",
    )
    sentinel = skill / "keep.txt"
    sentinel.write_text("keep")
    assert operation([tmp_path])[0].action == "refused"
    assert sentinel.read_text() == "keep"
