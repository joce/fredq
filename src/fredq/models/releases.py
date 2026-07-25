"""Release models. Endpoint noun: release. Corpus: 2026-07-05 run."""

from __future__ import annotations

# pydantic needs runtime types
# ruff: ignore[typing-only-standard-library-import]
from datetime import date

from fredq.models._base import FredDatetime, FredModel


class ReleaseInfo(FredModel):
    """One FRED release record (a ``releases`` list element).

    Appears in: release show + series-release (unwrapped), releases,
    source-releases. ``link`` and ``notes`` are absent on some records
    (corpus-measured), hence optional.
    """

    id: int
    link: str | None = None
    name: str
    notes: str | None = None
    press_release: bool
    realtime_end: date
    realtime_start: date


class ReleasesResult(FredModel):
    """A paginated release-list response (releases, source-releases)."""

    count: int
    limit: int
    offset: int
    order_by: str
    realtime_end: date
    realtime_start: date
    releases: list[ReleaseInfo]
    sort_order: str


class ReleaseDate(FredModel):
    """One release-date record (a ``release_dates`` list element).

    Appears in: release-dates (per-release: only ``release_id`` + ``date``)
    and releases-dates (the calendar: adds ``release_name`` and
    ``release_last_updated``) — one model, calendar-only fields optional
    (corpus-measured).
    """

    date: date
    release_id: int
    release_last_updated: FredDatetime | None = None
    release_name: str | None = None


class ReleaseDatesResult(FredModel):
    """A paginated release-dates response (release-dates, releases-dates)."""

    count: int
    limit: int
    offset: int
    order_by: str
    realtime_end: date
    realtime_start: date
    release_dates: list[ReleaseDate]
    sort_order: str
