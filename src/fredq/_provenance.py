"""Shared observation export provenance; no dataframe or model imports."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from fredq import __version__


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
    aggregation_method: str | None = None
    limit: int | None = None
    offset: int | None = None
    sort_order: str | None = None
    fetched_at: datetime | None = None


def observations_metadata(
    envelope: dict[str, Any],
    context: ObservationsContext | None,
    *,
    missing_value: str,
    fetched_at: datetime | None = None,
) -> dict[str, str]:
    """Return shared metadata, retaining the original CLI scalar keys.

    Returns:
        dict[str, str]: Parquet key-value metadata. Request fields are only
        explicitly sent parameters, not inferred upstream defaults.

    Raises:
        ValueError: If a supplied timestamp is not timezone-aware.
    """
    request = asdict(context) if context is not None else {}
    timestamp = request.pop("fetched_at", None) or fetched_at
    request = {key: value for key, value in request.items() if value is not None}
    envelope = {key: value for key, value in envelope.items() if key != "observations"}
    result = {
        "fredq_version": __version__,
        "fredq_command": "series-observations",
        "fredq_request": json.dumps(request, separators=(",", ":")),
        "fredq_envelope": json.dumps(envelope, separators=(",", ":")),
        "fredq_missing_value": missing_value,
    }
    if context is not None:
        result["fredq_series_id"] = context.series_id
    if timestamp is not None:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            message = "fetched_at must be timezone-aware"
            raise ValueError(message)
        result["fredq_fetched_at"] = timestamp.astimezone(timezone.utc).isoformat()
    for prefix, values in (("request", request), ("envelope", envelope)):
        result.update(
            {
                f"{prefix}.{key}": str(value)
                for key, value in values.items()
                if value is not None and isinstance(value, str | int | float | bool)
            }
        )
    return result
