"""Tests for Frame containers, pinned against real corpus captures."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Final

import polars as pl
import pytest

from fredq.frames import Frame, FrameShapeError, Observations, build_observations

CORPUS: Final[Path] = Path(__file__).parent / "fixtures" / "corpus"
NOW: Final[datetime] = datetime(2026, 7, 5, tzinfo=timezone.utc)


def _capture(rel: str) -> dict[str, Any]:
    return json.loads((CORPUS / rel).read_text(encoding="utf-8"))


def test_build_observations_from_corpus_gnpca() -> None:
    """A real full-history capture builds with the pinned schema."""

    payload = _capture("series-observations/GNPCA.json")
    obs = build_observations(payload, fetched_at=NOW)
    assert isinstance(obs, Observations)
    assert obs.df.schema == pl.Schema(
        {
            "date": pl.Date,
            "value": pl.Float64,
            "realtime_start": pl.Date,
            "realtime_end": pl.Date,
        }
    )
    assert obs.df.height == len(payload["observations"])
    assert obs.fetched_at is NOW


def test_missing_values_become_null_not_nan() -> None:
    """FRED's "." sentinel maps to null (the float|None ruling), not NaN."""

    payload = _capture("series-observations/DEXCAUS_holidays.json")
    dots = sum(1 for o in payload["observations"] if o["value"] == ".")
    assert dots == 2  # corpus-pinned count (README ruling)  # noqa: PLR2004
    obs = build_observations(payload, fetched_at=NOW)
    assert obs.df["value"].null_count() == dots
    assert not obs.df["value"].is_nan().any()


def test_vintage_capture_builds_with_multiple_realtime_windows() -> None:
    """ALFRED windows survive into the realtime columns (corpus-pinned)."""

    payload = _capture("series-observations/UNRATE_vintage-2001.json")
    obs = build_observations(payload, fetched_at=NOW)
    windows = obs.df.select("realtime_start", "realtime_end").unique()
    assert windows.height == 3  # corpus-pinned (README ruling)  # noqa: PLR2004


def test_meta_is_envelope_without_observations() -> None:
    """Everything except the rows lands in meta, wire-faithfully typed."""

    payload = _capture("series-observations/GNPCA.json")
    obs = build_observations(payload, fetched_at=NOW)
    expected = {k: v for k, v in payload.items() if k != "observations"}
    # Typed envelope: wire-shaped dump round-trips to the raw envelope.
    assert obs.meta.model_dump(mode="json") == expected
    assert obs.meta.units == payload["units"]


def test_unknown_observation_key_is_rejected() -> None:
    """Schema drift in rows fails loudly instead of being silently eaten."""

    payload = _capture("series-observations/GNPCA.json")
    payload["observations"][0]["surprise"] = 1
    with pytest.raises(FrameShapeError, match="surprise"):
        build_observations(payload, fetched_at=NOW)


def test_missing_observation_key_is_rejected() -> None:
    """A row lacking one of the four pinned keys is a shape error."""

    payload = _capture("series-observations/GNPCA.json")
    del payload["observations"][0]["value"]
    with pytest.raises(FrameShapeError, match="value"):
        build_observations(payload, fetched_at=NOW)


def test_missing_observations_array_is_rejected() -> None:
    """A payload without an observations list is a shape error."""

    with pytest.raises(FrameShapeError, match="observations"):
        build_observations({"count": 0}, fetched_at=NOW)


def test_unparseable_value_is_rejected() -> None:
    """Only "." and float strings are valid values (corpus evidence)."""

    payload = _capture("series-observations/GNPCA.json")
    payload["observations"][0]["value"] = "n/a"
    with pytest.raises(FrameShapeError, match="value"):
        build_observations(payload, fetched_at=NOW)


def test_unparseable_date_is_rejected() -> None:
    """Dates must be ISO strings; anything else is a shape error."""

    payload = _capture("series-observations/GNPCA.json")
    payload["observations"][0]["date"] = "01/01/2020"
    with pytest.raises(FrameShapeError, match="date"):
        build_observations(payload, fetched_at=NOW)


def test_to_dicts_round_trips_types() -> None:
    """to_dicts gives python-typed rows (date objects, float|None)."""

    payload = _capture("series-observations/DEXCAUS_holidays.json")
    rows = build_observations(payload, fetched_at=NOW).to_dicts()
    assert isinstance(rows[0]["date"], date)
    assert any(row["value"] is None for row in rows)


def test_to_pandas_raises_helpful_import_error_without_extra() -> None:
    """Without the [pandas] extra, conversion errors tell you the fix.

    Never skip here: in the base env the ImportError path IS the behavior
    under test; in a pandas env (the Part-4 CI leg) conversion must work.
    """

    frame = Frame(df=pl.DataFrame({"a": [1]}), fetched_at=NOW)
    try:
        import pandas  # noqa: F401, ICN001, PLC0415
    except ImportError:
        with pytest.raises(ImportError, match=r"fredq\[pandas\]"):
            frame.to_pandas()
    else:
        assert list(frame.to_pandas()["a"]) == [1]


def test_to_arrow_raises_helpful_import_error_without_extra() -> None:
    """Same contract for pyarrow."""

    frame = Frame(df=pl.DataFrame({"a": [1]}), fetched_at=NOW)
    try:
        import pyarrow  # noqa: F401, ICN001, PLC0415
    except ImportError:
        with pytest.raises(ImportError, match=r"fredq\[pandas\]"):
            frame.to_arrow()
    else:
        assert frame.to_arrow().num_rows == 1


def test_save_parquet_writes_readable_file(tmp_path: Path) -> None:
    """save_parquet round-trips through polars."""

    payload = _capture("series-observations/GNPCA.json")
    obs = build_observations(payload, fetched_at=NOW)
    target = tmp_path / "gnpca.parquet"
    obs.save_parquet(target)
    assert pl.read_parquet(target).height == obs.df.height


def test_frames_are_immutable() -> None:
    """Frozen dataclass: attribute assignment raises."""

    frame = Frame(df=pl.DataFrame({"a": [1]}), fetched_at=NOW)
    with pytest.raises(AttributeError):
        frame.df = pl.DataFrame()  # type: ignore[misc]
