"""Release-table models. Endpoint: release-tables. Corpus: 2026-07-05 run."""

from __future__ import annotations

from fredq.models._base import FredModel


class Element(FredModel):
    """One release-table element (a node in the table tree).

    ``line``, ``parent_id``, and ``series_id`` are present on every corpus
    record but always null there (top-level section nodes); ``line`` is a
    string per FRED's documentation when populated — required-but-nullable
    per the law.
    """

    children: list[Element]
    element_id: int
    level: str
    line: str | None
    name: str
    parent_id: int | None
    release_id: int
    series_id: str | None
    type: str


class ReleaseTablesResult(FredModel):
    """The release-tables response: a keyed tree of table elements.

    ``release_id`` echoes the request parameter and arrives as a STRING
    (unlike the integer ``release_id`` inside each element) — wire-faithful.
    """

    elements: dict[str, Element]
    release_id: str


Element.model_rebuild()
