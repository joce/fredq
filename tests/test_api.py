"""Tests for the public sync surface: totality, routing, signatures."""

from __future__ import annotations

import inspect
import json
from datetime import date
from pathlib import Path
from typing import Any, Final

import pytest

from fredq import api
from fredq._core import map_http_error
from fredq.commands import COMMANDS_BY_NAME
from fredq.exceptions import FredApiError, FredClientUsageError, FredRequestError
from fredq.frames import Observations
from fredq.models import (
    CategoriesResult,
    CategoryInfo,
    ReleaseDatesResult,
    ReleaseInfo,
    ReleaseSourcesResult,
    ReleasesResult,
    ReleaseTablesResult,
    SeriesInfo,
    SeriesListResult,
    SourceInfo,
    SourcesResult,
    TagsResult,
    VintageDatesResult,
)

CORPUS: Final[Path] = Path(__file__).parent / "fixtures" / "corpus"

# Minimal valid invocation for every public callable, keyed by command.
_CALLS: Final[dict[str, Any]] = {
    "series": lambda: api.Series("DGS10").info(),
    "series-observations": lambda: api.Series("DGS10").observations(),
    "series-vintagedates": lambda: api.Series("DGS10").vintage_dates(),
    "series-categories": lambda: api.Series("DGS10").categories(),
    "series-tags": lambda: api.Series("DGS10").tags(),
    "series-release": lambda: api.Series("DGS10").release(),
    "series-search": lambda: api.search_series("monetary"),
    "series-search-tags": lambda: api.search_series_tags("monetary"),
    "series-search-related-tags": lambda: api.search_series_related_tags(
        "monetary", ["usa"]
    ),
    "series-updates": api.series_updates,
    "category": lambda: api.Category(125).info(),
    "category-children": lambda: api.Category(125).children(),
    "category-related": lambda: api.Category(125).related(),
    "category-series": lambda: api.Category(125).series(),
    "category-tags": lambda: api.Category(125).tags(),
    "category-related-tags": lambda: api.Category(125).related_tags(["usa"]),
    "releases": api.releases,
    "releases-dates": api.release_calendar,
    "release": lambda: api.Release(53).info(),
    "release-dates": lambda: api.Release(53).dates(),
    "release-series": lambda: api.Release(53).series(),
    "release-sources": lambda: api.Release(53).sources(),
    "release-tags": lambda: api.Release(53).tags(),
    "release-related-tags": lambda: api.Release(53).related_tags(["usa"]),
    "release-tables": lambda: api.Release(53).tables(),
    "sources": api.sources,
    "source": lambda: api.Source(1).info(),
    "source-releases": lambda: api.Source(1).releases(),
    "tags": api.tags,
    "tags-series": lambda: api.tag_series(["usa"]),
    "related-tags": lambda: api.related_tags(["usa"]),
}

# command -> raw function object, for signature introspection.
_FUNCS: Final[dict[str, Any]] = {
    "series": api.Series.info,
    "series-observations": api.Series.observations,
    "series-vintagedates": api.Series.vintage_dates,
    "series-categories": api.Series.categories,
    "series-tags": api.Series.tags,
    "series-release": api.Series.release,
    "series-search": api.search_series,
    "series-search-tags": api.search_series_tags,
    "series-search-related-tags": api.search_series_related_tags,
    "series-updates": api.series_updates,
    "category": api.Category.info,
    "category-children": api.Category.children,
    "category-related": api.Category.related,
    "category-series": api.Category.series,
    "category-tags": api.Category.tags,
    "category-related-tags": api.Category.related_tags,
    "releases": api.releases,
    "releases-dates": api.release_calendar,
    "release": api.Release.info,
    "release-dates": api.Release.dates,
    "release-series": api.Release.series,
    "release-sources": api.Release.sources,
    "release-tags": api.Release.tags,
    "release-related-tags": api.Release.related_tags,
    "release-tables": api.Release.tables,
    "sources": api.sources,
    "source": api.Source.info,
    "source-releases": api.Source.releases,
    "tags": api.tags,
    "tags-series": api.tag_series,
    "related-tags": api.related_tags,
}

_BOUND_IDS: Final[frozenset[str]] = frozenset(
    {"series_id", "category_id", "release_id", "source_id"}
)

# Per-command stub payloads: the SMALLEST ok corpus capture for each
# command, so routing tests exercise real wire shapes as endpoints flip
# from dict to typed models (Part 3 batches update _EXPECTED only).
_STUB_PAYLOADS: Final[dict[str, str]] = {
    "series": "series/GNPCA.json",
    "series-observations": "series-observations/DEXCAUS_holidays.json",
    "series-vintagedates": "series-vintagedates/GNPCA_page-desc.json",
    "series-categories": "series-categories/DGS10.json",
    "series-tags": "series-tags/DGS10.json",
    "series-release": "series-release/DGS10.json",
    "series-search": "series-search/monetary_page2.json",
    "series-search-tags": "series-search-tags/monetary_filtered.json",
    "series-search-related-tags": "series-search-related-tags/monetary_usa.json",
    "series-updates": "series-updates/limit10.json",
    "category": "category/125.json",
    "category-children": "category-children/32991.json",
    "category-related": "category-related/32073.json",
    "category-series": "category-series/125_page-desc.json",
    "category-tags": "category-tags/125_group-gen.json",
    "category-related-tags": "category-related-tags/125_services-quarterly.json",
    "releases": "releases/page-desc.json",
    "releases-dates": "releases-dates/nodata.json",
    "release": "release/53.json",
    "release-dates": "release-dates/53_desc.json",
    "release-series": "release-series/53.json",
    "release-sources": "release-sources/53.json",
    "release-tags": "release-tags/53.json",
    "release-related-tags": "release-related-tags/53_usa.json",
    "release-tables": "release-tables/53.json",
    "sources": "sources/limit5.json",
    "source": "source/1.json",
    "source-releases": "source-releases/1_page-desc.json",
    "tags": "tags/group-freq.json",
    "tags-series": "tags-series/usa-quarterly.json",
    "related-tags": "related-tags/usa.json",
}

# Expected result type per command; dict until that endpoint's batch flips.
_EXPECTED: Final[dict[str, type]] = {
    "series": SeriesInfo,
    "series-observations": Observations,
    "series-categories": CategoriesResult,
    "series-tags": TagsResult,
    "series-release": ReleaseInfo,
    "series-search": SeriesListResult,
    "category": CategoryInfo,
    "category-children": CategoriesResult,
    "category-related": CategoriesResult,
    "category-series": SeriesListResult,
    "category-tags": TagsResult,
    "category-related-tags": TagsResult,
    "releases": ReleasesResult,
    "releases-dates": ReleaseDatesResult,
    "release": ReleaseInfo,
    "release-dates": ReleaseDatesResult,
    "release-series": SeriesListResult,
    "release-sources": ReleaseSourcesResult,
    "release-tags": TagsResult,
    "release-related-tags": TagsResult,
    "sources": SourcesResult,
    "source": SourceInfo,
    "source-releases": ReleasesResult,
    "tags": TagsResult,
    "tags-series": SeriesListResult,
    "related-tags": TagsResult,
    "series-vintagedates": VintageDatesResult,
    "series-search-tags": TagsResult,
    "series-search-related-tags": TagsResult,
    "series-updates": SeriesListResult,
    "release-tables": ReleaseTablesResult,
}


def test_typed_surface_is_total() -> None:
    """Every mapped callable returns a model or Frame — no dicts remain.

    raw() stays dict by design. This is the Part 3 done-criterion pin.
    """

    untyped = set(_CALLS) - set(_EXPECTED)
    assert untyped == set(), f"still dict-returning: {sorted(untyped)}"
    assert all(expected is not dict for expected in _EXPECTED.values())


def _stub_payload(command_name: str) -> dict[str, Any]:
    """Load the registered corpus capture for a command.

    Returns:
        dict[str, Any]: The parsed capture payload.
    """

    rel = _STUB_PAYLOADS[command_name]
    return json.loads((CORPUS / rel).read_text(encoding="utf-8"))


@pytest.fixture
def capture_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, dict[str, Any]]]:
    """Stub the async core; record (command_name, values) per call."""

    calls: list[tuple[str, dict[str, Any]]] = []

    async def _fake_call_endpoint(  # noqa: RUF029 - coroutine required by call_endpoint's API
        command_name: str, *, values: dict[str, Any]
    ) -> dict[str, Any]:
        calls.append((command_name, dict(values)))
        return _stub_payload(command_name)

    core = api._core  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(core, "call_endpoint", _fake_call_endpoint)
    return calls


def test_surface_is_total_over_commands() -> None:
    """Mapped callables cover every command exactly (spec pin)."""

    mapped = set(_CALLS)
    assert mapped == set(COMMANDS_BY_NAME)
    assert _FUNCS.keys() == _CALLS.keys()


@pytest.mark.parametrize("command_name", sorted(_CALLS))
def test_every_callable_routes_to_its_command(
    command_name: str, capture_calls: list[tuple[str, dict[str, Any]]]
) -> None:
    """Each public callable drives exactly its CommandSpec."""

    result = _CALLS[command_name]()
    assert [c[0] for c in capture_calls] == [command_name]
    assert isinstance(result, _EXPECTED.get(command_name, dict))


def test_entity_ids_reach_the_wire_values(
    capture_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    """The bound entity id lands in values under the wire param name."""

    api.Series(" DGS10 ").info()  # constructor strips
    api.Category(125).children()
    api.Release(53).dates()
    api.Source(1).releases()
    values = dict(capture_calls)
    assert values["series"]["series_id"] == "DGS10"
    assert values["category-children"]["category_id"] == 125  # noqa: PLR2004
    assert values["release-dates"]["release_id"] == 53  # noqa: PLR2004
    assert values["source-releases"]["source_id"] == 1


def test_none_kwargs_are_dropped(
    capture_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    """Unset optional params never reach the request."""

    api.releases(limit=5)
    assert capture_calls[0][1] == {"limit": 5}


@pytest.mark.parametrize("command_name", sorted(_FUNCS))
def test_kwargs_cover_every_wire_param(command_name: str) -> None:
    """Each callable exposes exactly its CommandSpec's params (no drift)."""

    func = _FUNCS[command_name]
    sig_names = {
        p.name for p in inspect.signature(func).parameters.values() if p.name != "self"
    }
    spec_names = {p.name for p in COMMANDS_BY_NAME[command_name].params}
    is_method = "self" in inspect.signature(func).parameters
    expected = spec_names - _BOUND_IDS if is_method else spec_names
    assert sig_names == expected, command_name


def test_raw_routes_to_a_mapped_command(
    capture_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    """raw() reaches any known command by name, same as the typed surface."""

    payload = api.raw("series", series_id="GNPCA")
    assert payload["seriess"][0]["id"] == "GNPCA"
    assert capture_calls == [("series", {"series_id": "GNPCA"})]


def test_raw_rejects_unknown_command() -> None:
    """A typo'd command name is a usage error, not a KeyError."""

    with pytest.raises(FredClientUsageError, match="unknown command"):
        api.raw("seriess")


def test_raw_error_path_maps_corpus_bodies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """raw()'s failure path maps FRED error bodies like every other call.

    The reference implementation shipped a raw() whose synthetic path
    bypassed error mapping; this pins ours against a real corpus body.
    """

    body = (CORPUS / "series" / "ERR_invalid-id.json").read_text(encoding="utf-8")

    async def _raise_and_map(  # noqa: RUF029 - coroutine required by call_endpoint's API
        command_name: str,  # noqa: ARG001 - signature must match call_endpoint's
        *,
        values: dict[str, Any],  # noqa: ARG001 - signature must match call_endpoint's
    ) -> dict[str, Any]:
        map_http_error(FredRequestError(400, "https://x", body=body))
        message = "unreachable"
        raise AssertionError(message)

    core = api._core  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(core, "call_endpoint", _raise_and_map)
    with pytest.raises(FredApiError) as exc_info:
        api.raw("series", series_id="ZZZNOTREAL")
    assert exc_info.value.error_code == 400  # noqa: PLR2004


def test_repr_is_useful() -> None:
    """Entity reprs name the class and id."""

    assert repr(api.Series("DGS10")) == "Series('DGS10')"
    assert repr(api.Category(125)) == "Category(125)"
    assert repr(api.Release(53)) == "Release(53)"
    assert repr(api.Source(1)) == "Source(1)"


def test_observations_meta_and_fetched_at(
    capture_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    """observations() splits the envelope into meta and stamps fetched_at."""

    obs = api.Series("DGS10").observations()
    assert capture_calls[0][0] == "series-observations"
    # Typed envelope from the DEXCAUS_holidays stub capture.
    assert obs.meta.units == "lin"
    assert obs.meta.count == 13  # noqa: PLR2004 - corpus-pinned
    assert obs.fetched_at.tzinfo is not None  # aware UTC stamp


def test_date_objects_reach_the_wire_as_iso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A datetime.date through the PUBLIC surface serializes to ISO wire form.

    capture_calls stubs call_endpoint (pre-serialization), so this test
    stubs one level lower — the client — to pin the full public promise.
    """

    class _WireStub:
        def __init__(self) -> None:
            self.params: dict[str, object] = {}

        async def get(
            self,
            path: str,  # noqa: ARG002
            params: dict[str, object],
            *,
            base_url: str | None = None,  # noqa: ARG002
        ) -> str:
            self.params = dict(params)
            # A full valid capture: the meta envelope must validate now.
            rel = _STUB_PAYLOADS["series-observations"]
            return (CORPUS / rel).read_text(encoding="utf-8")

        async def aclose(self) -> None:  # noqa: PLR6301 - protocol shape
            return None

    stub = _WireStub()
    core = api._core  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(core, "_get_client", lambda: stub)
    api.Series("DGS10").observations(observation_start=date(2024, 1, 1))
    assert stub.params["observation_start"] == "2024-01-01"
    assert stub.params["series_id"] == "DGS10"


def _stub_series_payload(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]
) -> None:
    """Make the next Series.info() call receive ``payload`` verbatim."""

    async def _fake(  # noqa: RUF029 - coroutine required by call_endpoint's API
        command_name: str,  # noqa: ARG001 - signature must match call_endpoint's
        *,
        values: dict[str, Any],  # noqa: ARG001 - signature must match call_endpoint's
    ) -> dict[str, Any]:
        return payload

    core = api._core  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(core, "call_endpoint", _fake)


_UNWRAP_VIOLATIONS: Final[list[tuple[dict[str, Any], str]]] = [
    ({"count": 0}, "got no list"),
    ({"seriess": []}, "got 0"),
    ({"seriess": [{}, {}]}, "got 2"),
    ({"seriess": ["not-an-object"]}, "not an object"),
]


@pytest.mark.parametrize(
    ("payload", "match"),
    _UNWRAP_VIOLATIONS,
    ids=["missing-key", "empty-list", "two-records", "non-dict-record"],
)
def test_unwrap_violations_raise_malformed_contract(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any], match: str
) -> None:
    """Single-entity unwrap violations raise the malformed-response contract.

    Spec pin (Part 3): FredApiError with error_code=None — the same
    contract as any other malformed 200. Corpus evidence says success
    payloads always carry exactly one record; anything else is drift and
    must fail loudly, never index-error or silently mis-parse.
    """

    _stub_series_payload(monkeypatch, payload)
    with pytest.raises(FredApiError, match=match) as exc_info:
        api.Series("DGS10").info()
    assert exc_info.value.error_code is None
    assert exc_info.value.status_code is None
