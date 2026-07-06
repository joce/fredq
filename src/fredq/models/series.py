"""Series record model. Endpoint noun: series. Corpus: 2026-07-05 run."""

from __future__ import annotations

from datetime import date  # noqa: TC003 - pydantic needs runtime types

from fredq.models._base import FredDatetime, FredModel


class SeriesInfo(FredModel):
    """One FRED series record (a ``seriess`` list element).

    Appears in: series show (unwrapped), series-search, category-series,
    release-series, tags-series, series-updates. Reuse across all six is
    corpus-verified by the gates (zero extras + one shared required set
    over every source's captures).

    ``group_popularity`` is observed only on list/search results
    (category-series, release-series, tags-series, series-search), never
    on series-show or series-updates records — hence optional. ``notes``
    is absent on some records (corpus-measured), hence optional.
    """

    frequency: str
    frequency_short: str
    group_popularity: int | None = None
    id: str
    last_updated: FredDatetime
    notes: str | None = None
    observation_end: date
    observation_start: date
    popularity: int
    realtime_end: date
    realtime_start: date
    seasonal_adjustment: str
    seasonal_adjustment_short: str
    title: str
    units: str
    units_short: str


class SeriesListResult(FredModel):
    """A paginated series-list response.

    Appears in: series-search, category-series, release-series,
    tags-series (corpus-gated across all four; series-updates has its own
    envelope, measured in Part 3c). FRED echoes ``filter_variable`` and
    ``filter_value`` in the envelope only when the request filtered
    (corpus-measured), hence optional.
    """

    count: int
    filter_value: str | None = None
    filter_variable: str | None = None
    limit: int
    offset: int
    order_by: str
    realtime_end: date
    realtime_start: date
    seriess: list[SeriesInfo]
    sort_order: str
