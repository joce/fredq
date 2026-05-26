"""Tests for the Parquet writer."""

from __future__ import annotations

import json
import math
from datetime import date
from typing import TYPE_CHECKING

import pyarrow.parquet as pq
import pytest

from fredq.parquet_writer import (
    ObservationsContext,
    ParquetWriterError,
    write_observations_parquet,
)

if TYPE_CHECKING:
    from pathlib import Path


def _envelope(observations: list[dict[str, str]]) -> str:
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
            "count": len(observations),
            "offset": 0,
            "limit": 100000,
            "observations": observations,
        }
    )


def test_write_round_trip(tmp_path: Path) -> None:
    """Writing then reading the Parquet file recovers the typed columns."""

    body = _envelope(
        [
            {
                "realtime_start": "2026-05-25",
                "realtime_end": "2026-05-25",
                "date": "2024-01-01",
                "value": "2.5",
            },
            {
                "realtime_start": "2026-05-25",
                "realtime_end": "2026-05-25",
                "date": "2024-02-01",
                "value": ".",
            },
        ]
    )
    out_path = tmp_path / "obs.parquet"
    context = ObservationsContext(series_id="CPIAUCSL", units="pch", frequency="m")

    descriptor = write_observations_parquet(body, out_path, context)

    assert descriptor["format"] == "parquet"
    assert descriptor["command"] == "series-observations"
    assert descriptor["series_id"] == "CPIAUCSL"
    expected_rows = 2
    assert descriptor["rows"] == expected_rows
    assert descriptor["bytes"] == out_path.stat().st_size

    table = pq.read_table(out_path)
    assert table.column_names == ["date", "value", "realtime_start", "realtime_end"]

    rows = table.to_pylist()
    expected_first_value = 2.5
    assert rows[0]["date"] == date(2024, 1, 1)
    assert rows[0]["value"] == expected_first_value
    assert rows[1]["date"] == date(2024, 2, 1)
    assert math.isnan(rows[1]["value"])


def test_envelope_metadata_recorded(tmp_path: Path) -> None:
    """Envelope + request fields are recorded in the schema metadata."""

    body = _envelope(
        [
            {
                "realtime_start": "2026-05-25",
                "realtime_end": "2026-05-25",
                "date": "2024-01-01",
                "value": "1",
            }
        ]
    )
    out_path = tmp_path / "obs.parquet"
    context = ObservationsContext(
        series_id="CPIAUCSL",
        units="pch",
        frequency="m",
        observation_start="2024-01-01",
        realtime_start="2024-01-01",
    )

    write_observations_parquet(body, out_path, context)

    schema = pq.read_schema(out_path)
    metadata = {k.decode(): v.decode() for k, v in (schema.metadata or {}).items()}
    assert metadata["command"] == "series-observations"
    assert metadata["series_id"] == "CPIAUCSL"
    assert metadata["envelope.units"] == "pch"
    assert metadata["envelope.count"] == "1"
    assert metadata["request.units"] == "pch"
    assert metadata["request.frequency"] == "m"
    assert metadata["request.observation_start"] == "2024-01-01"
    assert metadata["request.realtime_start"] == "2024-01-01"
    assert "fredq_version" in metadata


def test_invalid_json_raises(tmp_path: Path) -> None:
    """Bad JSON surfaces as ParquetWriterError, not a JSONDecodeError."""

    with pytest.raises(ParquetWriterError, match="not valid JSON"):
        write_observations_parquet(
            "{not json", tmp_path / "obs.parquet", ObservationsContext("X")
        )


def test_missing_observations_array_raises(tmp_path: Path) -> None:
    """An envelope without an observations array is a user-visible error."""

    body = json.dumps({"realtime_start": "2026-05-25"})
    with pytest.raises(ParquetWriterError, match="observations"):
        write_observations_parquet(
            body, tmp_path / "obs.parquet", ObservationsContext("X")
        )


def test_envelope_not_object_raises(tmp_path: Path) -> None:
    """A non-object envelope (e.g. a bare array) is a user-visible error."""

    with pytest.raises(ParquetWriterError, match="not a JSON object"):
        write_observations_parquet(
            "[]", tmp_path / "obs.parquet", ObservationsContext("X")
        )


def test_unparseable_dates_become_null(tmp_path: Path) -> None:
    """Malformed date strings are written as null rather than failing the write."""

    body = _envelope(
        [
            {
                "realtime_start": "not-a-date",
                "realtime_end": "2026-05-25",
                "date": "2024-01-01",
                "value": "1",
            }
        ]
    )
    out_path = tmp_path / "obs.parquet"
    write_observations_parquet(body, out_path, ObservationsContext("X"))

    rows = pq.read_table(out_path).to_pylist()
    assert rows[0]["date"] == date(2024, 1, 1)
    assert rows[0]["realtime_start"] is None
