"""Tests for the public sync surface: totality, routing, signatures."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Final

import pytest

from fredq import api
from fredq._core import map_http_error
from fredq.commands import COMMANDS_BY_NAME
from fredq.exceptions import FredApiError, FredClientUsageError, FredRequestError
from fredq.frames import Observations

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
        if command_name == "series-observations":
            return {"units": "lin", "observations": []}
        return {"stub": True}

    core = api._core  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(core, "call_endpoint", _fake_call_endpoint)
    return calls


def test_surface_is_total_over_commands() -> None:
    """Mapped + geofred-excluded == all 35 commands, disjoint (spec pin)."""

    mapped = set(_CALLS)
    excluded = set(api.GEOFRED_EXCLUDED)
    assert mapped.isdisjoint(excluded)
    assert mapped | excluded == set(COMMANDS_BY_NAME)
    assert _FUNCS.keys() == _CALLS.keys()


@pytest.mark.parametrize("command_name", sorted(_CALLS))
def test_every_callable_routes_to_its_command(
    command_name: str, capture_calls: list[tuple[str, dict[str, Any]]]
) -> None:
    """Each public callable drives exactly its CommandSpec."""

    result = _CALLS[command_name]()
    assert [c[0] for c in capture_calls] == [command_name]
    if command_name == "series-observations":
        assert isinstance(result, Observations)
    else:
        assert result == {"stub": True}


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


def test_raw_routes_to_excluded_commands(
    capture_calls: list[tuple[str, dict[str, Any]]],
) -> None:
    """raw() reaches the geofred family the surface deliberately omits."""

    payload = api.raw("series-group", series_id="WIPCPI")
    assert payload == {"stub": True}
    assert capture_calls == [("series-group", {"series_id": "WIPCPI"})]


def test_raw_rejects_unknown_command() -> None:
    """A typo'd command name is a usage error, not a KeyError."""

    with pytest.raises(FredClientUsageError, match="unknown command"):
        api.raw("series-groupp")


def test_raw_error_path_maps_corpus_bodies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """raw()'s failure path maps FRED error bodies like every other call.

    The reference implementation shipped a raw() whose synthetic path
    bypassed error mapping; this pins ours against a real corpus body.
    """

    body = (CORPUS / "series-group" / "ERR_invalid-id.json").read_text(encoding="utf-8")

    async def _raise_and_map(  # noqa: RUF029 - coroutine required by call_endpoint's API
        command_name: str,  # noqa: ARG001 - signature must match call_endpoint's
        *,
        values: dict[str, Any],  # noqa: ARG001 - signature must match call_endpoint's
    ) -> dict[str, Any]:
        map_http_error(FredRequestError(500, "https://x", body=body))
        message = "unreachable"
        raise AssertionError(message)

    core = api._core  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(core, "call_endpoint", _raise_and_map)
    with pytest.raises(FredApiError) as exc_info:
        api.raw("series-group", series_id="ZZZNOTREAL")
    assert exc_info.value.error_code == 500  # noqa: PLR2004


def test_repr_is_useful() -> None:
    """Entity reprs name the class and id."""

    assert repr(api.Series("DGS10")) == "Series('DGS10')"
    assert repr(api.Category(125)) == "Category(125)"
    assert repr(api.Release(53)) == "Release(53)"
    assert repr(api.Source(1)) == "Source(1)"
