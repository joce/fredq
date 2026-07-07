"""Tag models. Endpoint noun: tag. Corpus: 2026-07-05 run."""

from __future__ import annotations

from datetime import date  # noqa: TC003 - pydantic needs runtime types

from fredq.models._base import FredDatetime, FredModel


class TagInfo(FredModel):
    """One FRED tag record (a ``tags`` list element).

    Appears in: tags, related-tags, series-tags, category-tags,
    category-related-tags, release-tags, release-related-tags,
    series-search-tags, series-search-related-tags. ``notes`` is always
    present but sometimes null (corpus-measured) — required-but-nullable.
    """

    created: FredDatetime
    group_id: str
    name: str
    notes: str | None
    popularity: int
    series_count: int


class TagsResult(FredModel):
    """A paginated tag-list response (every tag-returning endpoint)."""

    count: int
    limit: int
    offset: int
    order_by: str
    realtime_end: date
    realtime_start: date
    sort_order: str
    tags: list[TagInfo]
