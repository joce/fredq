"""Corpus gates for every response model: zero extras + required-set pins.

Every model in src/fredq/models/ MUST be registered in _GATES in the same
commit that creates it (the completeness test enforces this). The corpus
is the only authority: required fields == keys present in 100% of the
relevant captures.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Final, cast

import pytest

from fredq import models
from tests.conftest import (
    collect_nested_extras,
    required_field_names,
    universal_keys,
)

RecordsFn = Callable[[], list[dict[str, Any]]]

CORPUS: Final[Path] = Path(__file__).parent / "fixtures" / "corpus"


def _records(glob: str, key: str) -> list[dict[str, Any]]:
    """Collect wire records for a model: every `key` entry in matching captures.

    Returns:
        list[dict[str, Any]]: Raw wire records (dicts) across the corpus.
    """

    records: list[dict[str, Any]] = []
    for path in sorted(CORPUS.glob(glob)):
        raw: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or key not in raw:
            continue  # error captures etc.
        payload = cast("dict[str, Any]", raw)
        value: object = payload[key]
        if isinstance(value, list):
            items = cast("list[object]", value)
            records += [cast("dict[str, Any]", r) for r in items if isinstance(r, dict)]
        elif isinstance(value, dict):
            records.append(cast("dict[str, Any]", value))
    return records


def _series_records() -> list[dict[str, Any]]:
    """All seriess records across every endpoint SeriesInfo covers.

    Returns:
        list[dict[str, Any]]: The SeriesInfo evidence set.
    """

    globs = (
        "series/*.json",
        "series-search/*.json",
        "category-series/*.json",
        "release-series/*.json",
        "tags-series/*.json",
        "series-updates/*.json",
    )
    records: list[dict[str, Any]] = []
    for glob in globs:
        records += _records(glob, "seriess")
    return records


def _observation_envelopes() -> list[dict[str, Any]]:
    """Observation envelopes (payload minus rows) across ok captures.

    Returns:
        list[dict[str, Any]]: The ObservationsMeta evidence set.
    """

    envelopes: list[dict[str, Any]] = []
    for path in sorted(CORPUS.glob("series-observations/*.json")):
        raw: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or "observations" not in raw:
            continue
        payload = cast("dict[str, Any]", raw)
        envelopes.append({k: v for k, v in payload.items() if k != "observations"})
    return envelopes


def _payloads(
    globs: tuple[str, ...], marker: str, *, paginated: bool | None = None
) -> list[dict[str, Any]]:
    """Whole ok payloads containing ``marker``, optionally filtered by pagination.

    Returns:
        list[dict[str, Any]]: Full response payloads (envelope models
        validate the whole payload, list field included).
    """

    payloads: list[dict[str, Any]] = []
    for glob in globs:
        for path in sorted(CORPUS.glob(glob)):
            raw: object = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or marker not in raw:
                continue
            if paginated is not None and ("count" in raw) is not paginated:
                continue
            payloads.append(cast("dict[str, Any]", raw))
    return payloads


_CATEGORY_GLOBS: Final[tuple[str, ...]] = (
    "category/*.json",
    "category-children/*.json",
    "category-related/*.json",
    "series-categories/*.json",
)
_RELEASE_RECORD_GLOBS: Final[tuple[str, ...]] = (
    "releases/*.json",
    "release/*.json",
    "series-release/*.json",
    "source-releases/*.json",
)
_RELEASE_DATE_GLOBS: Final[tuple[str, ...]] = (
    "release-dates/*.json",
    "releases-dates/*.json",
)
_SOURCE_RECORD_GLOBS: Final[tuple[str, ...]] = (
    "sources/*.json",
    "source/*.json",
    "release-sources/*.json",
)
_TAG_GLOBS: Final[tuple[str, ...]] = (
    "tags/*.json",
    "related-tags/*.json",
    "series-tags/*.json",
    "category-tags/*.json",
    "category-related-tags/*.json",
    "release-tags/*.json",
    "release-related-tags/*.json",
    "series-search-tags/*.json",
    "series-search-related-tags/*.json",
)
_SERIES_LIST_GLOBS: Final[tuple[str, ...]] = (
    "series-search/*.json",
    "category-series/*.json",
    "release-series/*.json",
    "tags-series/*.json",
    "series-updates/*.json",
)


def _category_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for glob in _CATEGORY_GLOBS:
        records += _records(glob, "categories")
    return records


def _category_envelopes() -> list[dict[str, Any]]:
    return _payloads(_CATEGORY_GLOBS, "categories")


def _release_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for glob in _RELEASE_RECORD_GLOBS:
        records += _records(glob, "releases")
    return records


def _releases_envelopes() -> list[dict[str, Any]]:
    return _payloads(
        ("releases/*.json", "source-releases/*.json"), "releases", paginated=True
    )


def _release_date_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for glob in _RELEASE_DATE_GLOBS:
        records += _records(glob, "release_dates")
    return records


def _release_dates_envelopes() -> list[dict[str, Any]]:
    return _payloads(_RELEASE_DATE_GLOBS, "release_dates")


def _source_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for glob in _SOURCE_RECORD_GLOBS:
        records += _records(glob, "sources")
    return records


def _release_sources_envelopes() -> list[dict[str, Any]]:
    return _payloads(("release-sources/*.json",), "sources")


def _sources_envelopes() -> list[dict[str, Any]]:
    return _payloads(("sources/*.json",), "sources", paginated=True)


def _tag_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for glob in _TAG_GLOBS:
        records += _records(glob, "tags")
    return records


def _tags_envelopes() -> list[dict[str, Any]]:
    return _payloads(_TAG_GLOBS, "tags")


def _series_list_envelopes() -> list[dict[str, Any]]:
    return _payloads(_SERIES_LIST_GLOBS, "seriess", paginated=True)


def _vintage_dates_envelopes() -> list[dict[str, Any]]:
    return _payloads(("series-vintagedates/*.json",), "vintage_dates")


def _release_tables_payloads() -> list[dict[str, Any]]:
    return _payloads(("release-tables/*.json",), "elements")


def _element_records() -> list[dict[str, Any]]:
    """Every element node across the release-tables captures, recursively.

    Returns:
        list[dict[str, Any]]: Flattened element records (children walked).
    """

    def walk(element: dict[str, Any]) -> list[dict[str, Any]]:
        found = [element]
        children = element.get("children")
        if isinstance(children, list):
            items = cast("list[object]", children)
            for child in items:
                if isinstance(child, dict):
                    found += walk(cast("dict[str, Any]", child))
        return found

    records: list[dict[str, Any]] = []
    for payload in _release_tables_payloads():
        elements = payload.get("elements")
        if isinstance(elements, dict):
            mapping = cast("dict[str, Any]", elements)
            for element in mapping.values():
                if isinstance(element, dict):
                    records += walk(cast("dict[str, Any]", element))
    return records


# Registry: (model class, records callable). Every model gets one entry.
_GATES: Final[list[tuple[type[Any], RecordsFn]]] = [
    (models.SeriesInfo, _series_records),
    (models.ObservationsMeta, _observation_envelopes),
    (models.SeriesListResult, _series_list_envelopes),
    (models.CategoryInfo, _category_records),
    (models.CategoriesResult, _category_envelopes),
    (models.ReleaseInfo, _release_records),
    (models.ReleasesResult, _releases_envelopes),
    (models.ReleaseDate, _release_date_records),
    (models.ReleaseDatesResult, _release_dates_envelopes),
    (models.SourceInfo, _source_records),
    (models.ReleaseSourcesResult, _release_sources_envelopes),
    (models.SourcesResult, _sources_envelopes),
    (models.TagInfo, _tag_records),
    (models.TagsResult, _tags_envelopes),
    (models.VintageDatesResult, _vintage_dates_envelopes),
    (models.Element, _element_records),
    (models.ReleaseTablesResult, _release_tables_payloads),
]

_GATE_IDS: Final[list[str]] = [model_cls.__name__ for model_cls, _ in _GATES]


@pytest.mark.parametrize(("model_cls", "records_fn"), _GATES, ids=_GATE_IDS)
def test_zero_nested_extras(model_cls: type[Any], records_fn: RecordsFn) -> None:
    """Every relevant capture validates with NO unmodeled fields."""

    records = records_fn()
    assert records, model_cls.__name__
    for record in records:
        instance = model_cls.model_validate(record)
        extras = collect_nested_extras(instance)
        assert extras == [], f"{model_cls.__name__}: {extras[:5]}"


@pytest.mark.parametrize(("model_cls", "records_fn"), _GATES, ids=_GATE_IDS)
def test_required_set_matches_corpus(
    model_cls: type[Any], records_fn: RecordsFn
) -> None:
    """Required fields == corpus-universal keys, exactly."""

    expected = universal_keys(records_fn())
    assert required_field_names(model_cls) == expected, model_cls.__name__


@pytest.mark.parametrize(("model_cls", "records_fn"), _GATES, ids=_GATE_IDS)
def test_fields_are_alphabetical(model_cls: type[Any], records_fn: RecordsFn) -> None:
    """Model law: alphabetical field order, gate-asserted."""

    del records_fn
    names = list(model_cls.model_fields)
    assert names == sorted(names), model_cls.__name__


def test_every_model_is_gated() -> None:
    """Completeness: every public model in fredq.models has a _GATES entry."""

    from pydantic import BaseModel  # noqa: PLC0415

    gated = {model_cls for model_cls, _ in _GATES}
    public = {
        obj
        for name in models.__all__
        if isinstance(obj := getattr(models, name), type)
        and issubclass(obj, BaseModel)
        and obj is not models.FredModel
    }
    ungated = public - gated
    assert not ungated, f"ungated models: {[m.__name__ for m in ungated]}"


def test_pad_offset_leaves_bare_dates_untouched() -> None:
    """A date-only string must not be mistaken for a minute-less offset.

    "2026-04-09" ends in "-09", which looks like an offset tail; the
    padder requires a time separator before padding (retrospective-review
    catch, 2026-07-06).
    """

    from fredq.models._base import (  # noqa: PLC0415
        _pad_offset,  # pyright: ignore[reportPrivateUsage]
    )

    assert _pad_offset("2026-04-09") == "2026-04-09"
    assert _pad_offset("2026-04-09 07:53:12-05") == "2026-04-09 07:53:12-05:00"
    assert _pad_offset("2026-04-09T07:53:12+03") == "2026-04-09T07:53:12+03:00"
    assert _pad_offset("2026-04-09 07:53:12-05:00") == "2026-04-09 07:53:12-05:00"


def test_fred_datetime_parses_corpus_offset_spelling() -> None:
    """FRED's minute-less offset (corpus: last_updated) parses AWARE.

    Pinned against the exact GNPCA corpus value.
    """

    payload = json.loads((CORPUS / "series" / "GNPCA.json").read_text(encoding="utf-8"))
    info = models.SeriesInfo.model_validate(payload["seriess"][0])
    expected = datetime(2026, 4, 9, 7, 53, 12, tzinfo=timezone(timedelta(hours=-5)))
    assert info.last_updated == expected
    assert info.last_updated.tzinfo is not None
