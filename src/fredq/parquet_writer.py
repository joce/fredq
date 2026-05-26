"""Parquet writer for observation-style FRED endpoints.

A scoped exception to the ``AGENTS.md`` rule that fredq prints FRED
response bodies to stdout exactly as returned. The exception applies
only when the user opts in via ``--format parquet --out PATH`` on a
parquet-capable command.

PyArrow is imported lazily so the JSON path does not pay the import
cost or require the optional ``pyarrow`` dependency.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any, Final

from fredq import __version__
from fredq.exceptions import FredqError

if TYPE_CHECKING:
    from pathlib import Path

_MISSING_PYARROW_MESSAGE: Final[str] = (
    "--format parquet requires the parquet extra: "
    "pip install 'fredq[parquet]' (or uv sync --extra parquet)"
)

# FRED encodes missing observations as ".".
_MISSING_VALUE_SENTINEL: Final[str] = "."


class ParquetWriterError(FredqError):
    """Raised when Parquet writing fails for a user-visible reason."""


@dataclass(frozen=True, slots=True)
class ObservationsContext:
    """Per-call context recorded as Parquet key-value metadata.

    Stored alongside the table so a future reader can recover what the
    request asked for without re-fetching from FRED.
    """

    series_id: str
    units: str | None = None
    frequency: str | None = None
    observation_start: str | None = None
    observation_end: str | None = None
    realtime_start: str | None = None
    realtime_end: str | None = None


def write_observations_parquet(
    observations_json_text: str,
    out_path: Path,
    context: ObservationsContext,
) -> dict[str, Any]:
    """Parse a FRED ``series/observations`` body and write a Parquet table.

    The helpers below raise :class:`ParquetWriterError` for any user-visible
    failure mode: missing pyarrow, undecodable JSON, missing observations
    array, or filesystem errors during write.

    Args:
        observations_json_text: Raw JSON body from FRED.
        out_path: Destination Parquet file path.
        context: Request parameters to record as table metadata.

    Returns:
        dict[str, Any]: Single-line descriptor of the write, suitable for
            stdout reporting (``format``, ``out``, ``command``, ``series_id``,
            ``rows``, ``bytes``).
    """

    pa, pq = _import_pyarrow()
    envelope = _parse_envelope(observations_json_text)
    _check_output_type(envelope)
    observations = _extract_observations(envelope)
    table = _build_table(observations, envelope, context, pa)
    _write_table(pq, table, out_path)
    return {
        "format": "parquet",
        "out": str(out_path),
        "fredq_command": "series-observations",
        "fredq_series_id": context.series_id,
        "rows": table.num_rows,
        "bytes": out_path.stat().st_size,
    }


def _import_pyarrow() -> tuple[Any, Any]:
    """Lazily import pyarrow + pyarrow.parquet.

    Returns:
        tuple[Any, Any]: ``(pyarrow_module, pyarrow_parquet_module)``.

    Raises:
        ParquetWriterError: If pyarrow is not installed.
    """

    try:
        import pyarrow as pa  # noqa: PLC0415 - lazy import keeps JSON path free.
        import pyarrow.parquet as pq  # noqa: PLC0415
    except ImportError as exc:
        raise ParquetWriterError(_MISSING_PYARROW_MESSAGE) from exc
    return pa, pq


_EXPECTED_OUTPUT_TYPE: Final[int] = 1


def _check_output_type(envelope: dict[str, Any]) -> None:
    """Raise if the envelope's output_type is not 1 (FRED default).

    FRED's ``output_type`` controls observation format: 1 = date/value pairs,
    2 = vintage dates x series, 3 = initial release only, 4 = latest + vintage
    dates. The Parquet writer only knows how to flatten the default type-1
    shape into rows; other types produce a different structure.

    Raises:
        ParquetWriterError: If ``output_type`` is present and not equal to 1.
    """

    output_type = envelope.get("output_type")
    if output_type is None or output_type == _EXPECTED_OUTPUT_TYPE:
        return
    message = f"--format parquet requires output_type=1; got {output_type}"
    raise ParquetWriterError(message)


def _parse_envelope(text: str) -> dict[str, Any]:
    try:
        envelope = json.loads(text)
    except json.JSONDecodeError as exc:
        message = f"FRED response was not valid JSON: {exc.msg}"
        raise ParquetWriterError(message) from exc
    if not isinstance(envelope, dict):
        message = "FRED response envelope was not a JSON object"
        raise ParquetWriterError(message)
    return envelope


def _extract_observations(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    observations = envelope.get("observations")
    if not isinstance(observations, list):
        message = "FRED response did not contain an 'observations' array"
        raise ParquetWriterError(message)
    return [obs for obs in observations if isinstance(obs, dict)]


def _parse_date(raw: object) -> date | None:
    """Parse a date string from an observation dict, returning None on failure.

    The parameter is typed as ``object`` because ``obs.get("date")`` returns
    ``Any`` and narrowing at the call site would add noise.  We isinstance-
    check before calling ``date.fromisoformat`` so the type-checker is happy.

    Returns:
        date | None: Parsed date, or ``None`` if ``raw`` is not a valid date
        string.
    """

    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _parse_value(raw: object) -> float:
    if raw is None or raw == _MISSING_VALUE_SENTINEL:
        return math.nan
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return math.nan


def _build_table(
    observations: list[dict[str, Any]],
    envelope: dict[str, Any],
    context: ObservationsContext,
    pa: Any,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    dates: list[date | None] = []
    values: list[float] = []
    realtime_starts: list[date | None] = []
    realtime_ends: list[date | None] = []
    for obs in observations:
        dates.append(_parse_date(obs.get("date")))
        values.append(_parse_value(obs.get("value")))
        realtime_starts.append(_parse_date(obs.get("realtime_start")))
        realtime_ends.append(_parse_date(obs.get("realtime_end")))

    schema = pa.schema(
        [
            pa.field("date", pa.date32()),
            pa.field("value", pa.float64()),
            pa.field("realtime_start", pa.date32()),
            pa.field("realtime_end", pa.date32()),
        ],
        metadata=_build_metadata(envelope, context),
    )
    arrays = [
        pa.array(dates, type=pa.date32()),
        pa.array(values, type=pa.float64()),
        pa.array(realtime_starts, type=pa.date32()),
        pa.array(realtime_ends, type=pa.date32()),
    ]
    return pa.Table.from_arrays(arrays, schema=schema)


_ENVELOPE_METADATA_KEYS: Final[tuple[str, ...]] = (
    "realtime_start",
    "realtime_end",
    "observation_start",
    "observation_end",
    "units",
    "order_by",
    "sort_order",
    "count",
    "offset",
    "limit",
)


def _build_metadata(
    envelope: dict[str, Any], context: ObservationsContext
) -> dict[bytes, bytes]:
    # Key naming: use "fredq_" prefix for tool-owned fields to match sister
    # tools (yoghurt uses "yoghurt_command", "yoghurt_version" etc.).
    payload: dict[str, str] = {
        "fredq_version": __version__,
        "fredq_command": "series-observations",
        "fredq_series_id": context.series_id,
    }
    for key in _ENVELOPE_METADATA_KEYS:
        val = envelope.get(key)
        # Guard: only scalar values can be safely encoded as metadata strings.
        # Non-scalar values (dicts, lists) are silently skipped (D4).
        if val is not None and isinstance(val, str | int | float | bool):
            payload[f"envelope.{key}"] = str(val)
    request_fields: dict[str, str | None] = {
        "request.units": context.units,
        "request.frequency": context.frequency,
        "request.observation_start": context.observation_start,
        "request.observation_end": context.observation_end,
        "request.realtime_start": context.realtime_start,
        "request.realtime_end": context.realtime_end,
    }
    payload.update({k: v for k, v in request_fields.items() if v is not None})
    return {k.encode("utf-8"): v.encode("utf-8") for k, v in payload.items()}


def _write_table(
    pq: Any,  # noqa: ANN401
    table: Any,  # noqa: ANN401
    out_path: Path,
) -> None:
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, out_path, compression="snappy")
    except OSError as exc:
        message = f"failed to write Parquet file {out_path}: {exc}"
        raise ParquetWriterError(message) from exc
