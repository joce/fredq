"""Immutable tabular results with one conversion vocabulary."""

# pandas/pyarrow are optional (the fredq[pandas] extra) and absent from the
# base dev environment, so pyright sees their types as Unknown here. Relax
# only the Unknown-type checks; the ImportError probes keep runtime honest.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any, Final

import polars as pl

from fredq.exceptions import FredqError
from fredq.models import ObservationsMeta

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    import pandas as pd  # pyright: ignore[reportMissingImports, reportMissingTypeStubs]
    import pyarrow as pa  # pyright: ignore[reportMissingImports, reportMissingTypeStubs]

# FRED encodes missing observations as ".".
_MISSING: Final[str] = "."

_OBSERVATION_KEYS: Final[frozenset[str]] = frozenset(
    {"date", "value", "realtime_start", "realtime_end"}
)


class FrameShapeError(FredqError):
    """Raised when a tabular FRED payload does not match its pinned shape."""


@dataclass(frozen=True, slots=True)
class Frame:
    """A fetched tabular result wrapping a polars DataFrame."""

    df: pl.DataFrame
    fetched_at: datetime

    def to_polars(self) -> pl.DataFrame:
        """Return the underlying polars DataFrame (not a copy).

        Returns:
            pl.DataFrame: The result table.
        """

        return self.df

    def to_pandas(self) -> pd.DataFrame:
        """Convert to pandas (requires the fredq[pandas] extra).

        Returns:
            pd.DataFrame: The result table as pandas.

        Raises:
            ImportError: If pandas is not installed.
        """

        try:
            import pandas  # noqa: F401, ICN001, PLC0415 - optional dependency probe  # pyright: ignore[reportMissingImports, reportMissingTypeStubs, reportUnusedImport]
        except ImportError as exc:
            message = (
                "to_pandas() requires the optional extra: pip install fredq[pandas]"
            )
            raise ImportError(message) from exc
        return self.df.to_pandas()

    def to_arrow(self) -> pa.Table:
        """Convert to a pyarrow Table (requires the fredq[pandas] extra).

        Returns:
            pa.Table: The result table as Arrow.

        Raises:
            ImportError: If pyarrow is not installed.
        """

        try:
            import pyarrow  # noqa: F401, ICN001, PLC0415 - optional dependency probe  # pyright: ignore[reportMissingImports, reportMissingTypeStubs, reportUnusedImport]
        except ImportError as exc:
            message = (
                "to_arrow() requires the optional extra: pip install fredq[pandas]"
            )
            raise ImportError(message) from exc
        return self.df.to_arrow()

    def to_dicts(self) -> list[dict[str, Any]]:
        """Return the rows as plain Python dicts.

        Returns:
            list[dict[str, Any]]: One dict per row, python-typed values.
        """

        return self.df.to_dicts()

    def save_parquet(self, path: Path | str) -> None:
        """Write the table to a Parquet file (snappy compression)."""

        self.df.write_parquet(path, compression="snappy")


@dataclass(frozen=True, slots=True)
class Observations(Frame):
    """Series observations plus their typed response envelope.

    ``meta`` carries every envelope field FRED sent alongside the rows
    (realtime bounds, units, count, ...), corpus-gated.
    """

    meta: ObservationsMeta


def _parse_date(field: str, raw: object) -> date:
    if not isinstance(raw, str):
        message = f"observation {field} is not a string: {raw!r}"
        raise FrameShapeError(message)
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        message = f"observation {field} is not an ISO date: {raw!r}"
        raise FrameShapeError(message) from exc


def _parse_value(raw: object) -> float | None:
    """Parse FRED's observation value: a float string, or "." for missing.

    Returns:
        float | None: The value, or None for FRED's missing sentinel.

    Raises:
        FrameShapeError: For any other shape (corpus evidence says only
            float strings and "." occur; drift must fail loudly).
    """

    if raw == _MISSING:
        return None
    if isinstance(raw, str):
        try:
            return float(raw)
        except ValueError:
            pass
    message = f"observation value is not a float string or '.': {raw!r}"
    raise FrameShapeError(message)


def build_observations(
    payload: dict[str, Any], *, fetched_at: datetime
) -> Observations:
    """Build an Observations frame from a parsed series/observations payload.

    Returns:
        Observations: Rows as polars columns, envelope as ``meta``.

    Raises:
        FrameShapeError: If the payload or any row deviates from the
            corpus-pinned shape (missing rows array, unknown row keys,
            unparseable dates or values).
    """

    rows = payload.get("observations")
    if not isinstance(rows, list):
        message = "payload has no 'observations' array"
        raise FrameShapeError(message)

    dates: list[date] = []
    values: list[float | None] = []
    starts: list[date] = []
    ends: list[date] = []
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            message = f"observation row is not an object: {raw_row!r}"
            raise FrameShapeError(message)
        row: dict[str, object] = raw_row
        keys = frozenset(row.keys())
        unknown = keys - _OBSERVATION_KEYS
        if unknown:
            names = ", ".join(sorted(unknown))
            message = f"unknown observation key(s): {names}"
            raise FrameShapeError(message)
        missing = _OBSERVATION_KEYS - keys
        if missing:
            names = ", ".join(sorted(missing))
            message = f"observation row missing key(s): {names}"
            raise FrameShapeError(message)
        dates.append(_parse_date("date", row["date"]))
        values.append(_parse_value(row["value"]))
        starts.append(_parse_date("realtime_start", row["realtime_start"]))
        ends.append(_parse_date("realtime_end", row["realtime_end"]))

    df = pl.DataFrame(
        {
            "date": dates,
            "value": values,
            "realtime_start": starts,
            "realtime_end": ends,
        },
        schema={
            "date": pl.Date,
            "value": pl.Float64,
            "realtime_start": pl.Date,
            "realtime_end": pl.Date,
        },
    )
    meta = ObservationsMeta.model_validate(
        {key: value for key, value in payload.items() if key != "observations"}
    )
    return Observations(df=df, fetched_at=fetched_at, meta=meta)
