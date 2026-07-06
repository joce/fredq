"""Source models. Endpoint noun: source. Corpus: 2026-07-05 run."""

from __future__ import annotations

from datetime import date  # noqa: TC003 - pydantic needs runtime types

from fredq.models._base import FredModel


class SourceInfo(FredModel):
    """One FRED source record (a ``sources`` list element).

    Appears in: source show (unwrapped), sources, release-sources.
    ``link`` and ``notes`` are absent on some records (corpus-measured),
    hence optional.
    """

    id: int
    link: str | None = None
    name: str
    notes: str | None = None
    realtime_end: date
    realtime_start: date


class ReleaseSourcesResult(FredModel):
    """The release-sources response: realtime bounds + sources, unpaginated.

    Distinct from :class:`SourcesResult` by corpus evidence: FRED's
    release/sources envelope carries no count/limit/offset/ordering.
    """

    realtime_end: date
    realtime_start: date
    sources: list[SourceInfo]


class SourcesResult(FredModel):
    """A paginated source-list response (sources)."""

    count: int
    limit: int
    offset: int
    order_by: str
    realtime_end: date
    realtime_start: date
    sort_order: str
    sources: list[SourceInfo]
