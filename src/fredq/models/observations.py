"""Observations envelope model. Endpoint: series-observations. Corpus 2026-07-05."""

from __future__ import annotations

from datetime import date  # noqa: TC003 - pydantic needs runtime types
from typing import Literal

from fredq.models._base import FredModel


class ObservationsMeta(FredModel):
    """The series-observations response envelope (everything but the rows).

    ``units`` echoes the requested transform code (a request-validated
    closed set; kept ``str`` per the enum policy). ``output_type`` is
    always 1 via this library — the surface exposes no output_type
    parameter.
    """

    count: int
    file_type: Literal["json"]
    limit: int
    observation_end: date
    observation_start: date
    offset: int
    order_by: str
    output_type: int
    realtime_end: date
    realtime_start: date
    sort_order: str
    units: str
