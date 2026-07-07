"""Category models. Endpoint noun: category. Corpus: 2026-07-05 run."""

from __future__ import annotations

from fredq.models._base import FredModel


class CategoryInfo(FredModel):
    """One FRED category record (a ``categories`` list element).

    Appears in: category show (unwrapped), category-children,
    category-related, series-categories. ``notes`` is absent on most
    records (corpus-measured), hence optional.
    """

    id: int
    name: str
    notes: str | None = None
    parent_id: int


class CategoriesResult(FredModel):
    """A category list response.

    FRED's category-list envelopes carry nothing besides the list itself
    (corpus-measured across category show/children/related and
    series-categories) — no realtime bounds, no pagination.
    """

    categories: list[CategoryInfo]
