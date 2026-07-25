"""Tests for the Parquet writer."""

from __future__ import annotations

import json
import math
from datetime import date
from typing import TYPE_CHECKING

import polars as pl
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
    assert descriptor["fredq_command"] == "series-observations"
    assert descriptor["fredq_series_id"] == "CPIAUCSL"
    expected_rows = 2
    assert descriptor["rows"] == expected_rows
    assert descriptor["bytes"] == out_path.stat().st_size

    df = pl.read_parquet(out_path)
    assert df.columns == ["date", "value", "realtime_start", "realtime_end"]
    assert df.dtypes == [pl.Date, pl.Float64, pl.Date, pl.Date]

    rows = df.to_dicts()
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

    metadata = pl.read_parquet_metadata(out_path)
    assert metadata["fredq_command"] == "series-observations"
    assert metadata["fredq_series_id"] == "CPIAUCSL"
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


# C5 — additional parquet_writer coverage


def test_empty_observations_writes_zero_row_table(tmp_path: Path) -> None:
    """An empty observations array writes a 0-row Parquet table (not an error)."""

    body = _envelope([])
    out_path = tmp_path / "empty.parquet"
    descriptor = write_observations_parquet(body, out_path, ObservationsContext("X"))

    assert descriptor["rows"] == 0
    df = pl.read_parquet(out_path)
    assert df.height == 0
    assert df.columns == ["date", "value", "realtime_start", "realtime_end"]


def test_all_dot_values_column_is_all_nan(tmp_path: Path) -> None:
    """Observations whose value is '.' are all NaN in the Parquet column."""

    body = _envelope(
        [
            {
                "realtime_start": "2026-05-25",
                "realtime_end": "2026-05-25",
                "date": "2024-01-01",
                "value": ".",
            },
            {
                "realtime_start": "2026-05-25",
                "realtime_end": "2026-05-25",
                "date": "2024-02-01",
                "value": ".",
            },
        ]
    )
    out_path = tmp_path / "dots.parquet"
    write_observations_parquet(body, out_path, ObservationsContext("X"))

    rows = pl.read_parquet(out_path).to_dicts()
    assert all(math.isnan(row["value"]) for row in rows)


def test_oserror_on_write_raises_parquet_writer_error(tmp_path: Path) -> None:
    """An OSError during write raises ParquetWriterError (not OSError)."""

    from unittest.mock import patch  # ruff: ignore[import-outside-top-level]

    body = _envelope(
        [
            {
                "realtime_start": "2026-05-25",
                "realtime_end": "2026-05-25",
                "date": "2024-01-01",
                "value": "1.0",
            }
        ]
    )
    out_path = tmp_path / "obs.parquet"

    with (
        patch("polars.DataFrame.write_parquet", side_effect=OSError("disk full")),
        pytest.raises(ParquetWriterError, match="failed to write"),
    ):
        write_observations_parquet(body, out_path, ObservationsContext("X"))


def test_non_scalar_envelope_value_does_not_crash(tmp_path: Path) -> None:
    """Nested-dict or list values in the envelope are silently skipped in metadata."""

    import json  # ruff: ignore[import-outside-top-level]

    # Inject a non-scalar value under a metadata key to simulate an unexpected
    # FRED response shape.
    body_dict = {
        "realtime_start": "2026-05-25",
        "realtime_end": "2026-05-25",
        "observation_start": {"nested": "dict"},  # non-scalar
        "observation_end": "2024-12-31",
        "units": "lin",
        "output_type": 1,
        "file_type": "json",
        "order_by": "observation_date",
        "sort_order": "asc",
        "count": 1,
        "offset": 0,
        "limit": 100000,
        "observations": [
            {
                "realtime_start": "2026-05-25",
                "realtime_end": "2026-05-25",
                "date": "2024-01-01",
                "value": "1",
            }
        ],
    }
    out_path = tmp_path / "obs.parquet"
    # Should not raise despite the nested dict.
    write_observations_parquet(
        json.dumps(body_dict), out_path, ObservationsContext("X")
    )

    metadata = pl.read_parquet_metadata(out_path)
    # The nested dict key should NOT appear in metadata.
    assert "envelope.observation_start" not in metadata
    # Scalar keys should still be present.
    assert "envelope.observation_end" in metadata


def test_output_type_not_1_raises(tmp_path: Path) -> None:
    """An envelope with output_type != 1 raises ParquetWriterError (A4)."""

    body = json.dumps(
        {
            "output_type": 2,
            "observations": [],
        }
    )
    with pytest.raises(ParquetWriterError, match="output_type=1"):
        write_observations_parquet(
            body, tmp_path / "obs.parquet", ObservationsContext("X")
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

    rows = pl.read_parquet(out_path).to_dicts()
    assert rows[0]["date"] == date(2024, 1, 1)
    assert rows[0]["realtime_start"] is None
