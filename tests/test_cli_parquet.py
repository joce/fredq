"""End-to-end CLI tests for the Parquet output path."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final

import pyarrow.parquet as pq

from fredq.cli import main

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from pytest_httpx import HTTPXMock

EXIT_OK: Final[int] = 0
EXIT_USAGE: Final[int] = 2


def _stub_observations_body() -> str:
    return json.dumps(
        {
            "realtime_start": "2026-05-25",
            "realtime_end": "2026-05-25",
            "observation_start": "1947-01-01",
            "observation_end": "2024-12-31",
            "units": "pch",
            "output_type": 1,
            "file_type": "json",
            "order_by": "observation_date",
            "sort_order": "asc",
            "count": 2,
            "offset": 0,
            "limit": 100000,
            "observations": [
                {
                    "realtime_start": "2026-05-25",
                    "realtime_end": "2026-05-25",
                    "date": "2024-01-01",
                    "value": "1.5",
                },
                {
                    "realtime_start": "2026-05-25",
                    "realtime_end": "2026-05-25",
                    "date": "2024-02-01",
                    "value": ".",
                },
            ],
        }
    )


def test_parquet_round_trip(
    httpx_mock: HTTPXMock,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``--format parquet --out PATH`` writes a typed table and prints a descriptor."""

    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://api.stlouisfed.org/fred/series/observations?"
            "series_id=CPIAUCSL&units=pch&frequency=m&"
            "api_key=secret&file_type=json"
        ),
        text=_stub_observations_body(),
    )

    out_path = tmp_path / "cpi.parquet"
    rc = main(
        [
            "series-observations",
            "--series-id",
            "CPIAUCSL",
            "--units",
            "pch",
            "--frequency",
            "m",
            "--format",
            "parquet",
            "--out",
            str(out_path),
        ]
    )

    captured = capsys.readouterr()
    assert rc == EXIT_OK
    assert out_path.exists()
    descriptor = json.loads(captured.out)
    assert descriptor["format"] == "parquet"
    assert descriptor["fredq_command"] == "series-observations"
    assert descriptor["fredq_series_id"] == "CPIAUCSL"

    table = pq.read_table(out_path)
    expected_rows = 2
    assert table.num_rows == expected_rows
    assert table.column_names == ["date", "value", "realtime_start", "realtime_end"]


def test_parquet_requires_out(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``--format parquet`` without ``--out`` errors before any HTTP call."""

    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    rc = main(
        [
            "series-observations",
            "--series-id",
            "CPIAUCSL",
            "--format",
            "parquet",
        ]
    )

    captured = capsys.readouterr()
    assert rc == EXIT_USAGE
    assert "requires --out" in captured.err


def test_out_without_parquet_errors(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``--out`` without ``--format parquet`` is a usage error."""

    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    rc = main(
        [
            "series-observations",
            "--series-id",
            "CPIAUCSL",
            "--out",
            str(tmp_path / "x.parquet"),
        ]
    )

    captured = capsys.readouterr()
    assert rc == EXIT_USAGE
    assert "--out is only valid with --format parquet" in captured.err


def test_parquet_on_unsupported_command_errors(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Using ``--format parquet`` on a non-parquet command lists the right ones."""

    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    rc = main(
        [
            "series",
            "--series-id",
            "GNPCA",
            "--format",
            "parquet",
            "--out",
            str(tmp_path / "x.parquet"),
        ]
    )

    captured = capsys.readouterr()
    assert rc == EXIT_USAGE
    assert "series-observations" in captured.err
