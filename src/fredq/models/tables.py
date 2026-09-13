"""Release-table models. Endpoint: release-tables. Corpus: 2026-07-05 and 2026-09-13."""

from __future__ import annotations

from fredq.models._base import FredModel


class Element(FredModel):
    """One release-table element (a node in the table tree).

    ``line``, ``parent_id``, and ``series_id`` are null on section nodes
    and populated on series nodes. Observation fields appear only when
    values are requested (2026-09-13 captures). ``observation_date`` is a
    display period label, such as "2025" or "Aug 2026", not an ISO date.
    """

    children: list[Element]
    element_id: int
    level: str
    line: str | None
    name: str
    observation_date: str | None = None
    observation_value: str | None = None
    parent_id: int | None
    release_id: int
    series_id: str | None
    type: str


class ReleaseTablesResult(FredModel):
    """The release-tables response: a keyed tree of table elements.

    ``release_id`` echoes the request parameter and arrives as a STRING
    (unlike the integer ``release_id`` inside each element) — wire-faithful.
    ``element_id`` and ``name`` appear for a selected subtree (2026-09-13).
    """

    element_id: int | None = None
    elements: dict[str, Element]
    name: str | None = None
    release_id: str


Element.model_rebuild()
