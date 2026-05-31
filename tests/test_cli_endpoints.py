"""CLI endpoint tests for Group 1 (series discovery) and Group 3 (releases)."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Final

import pytest

from fredq.cli import build_parser, main
from fredq.commands import COMMANDS, CommandSpec

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock

EXIT_USAGE: Final[int] = 2
EXIT_OK: Final[int] = 0

_BASE = "https://api.stlouisfed.org"
_KEY_SUFFIX = "&api_key=secret&file_type=json"


def _run(
    args: list[str],
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[int, str, str]:
    """Run main() with a fake API key and home dir.

    Returns:
        tuple[int, str, str]: (exit code, stdout, stderr).
    """
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    out = io.StringIO()
    err = io.StringIO()
    rc = main(args, stdout=out, stderr=err)
    return rc, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# Help smoke test — all commands must expose --help without crashing
# ---------------------------------------------------------------------------


def _help_args_for(command: CommandSpec) -> list[str]:
    """Return the argv list to invoke --help for a command (handles groups)."""
    if command.group is not None:
        return [command.group, command.leaf or command.name, "--help"]
    return [command.name, "--help"]


@pytest.mark.parametrize("command", list(COMMANDS))
def test_all_commands_help_exits_cleanly(command: CommandSpec) -> None:
    """Every command in COMMANDS must respond to --help with exit 0."""
    with pytest.raises(SystemExit) as exc_info:
        main(_help_args_for(command))
    assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Group 1 — Series discovery
# ---------------------------------------------------------------------------


def test_series_search_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-search returns raw FRED JSON body."""
    body = '{"seriess": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/series/search?search_text=inflation&limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["series", "search", "inflation", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"seriess"' in stdout


def test_series_search_missing_positional_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-search exits 2 when the required positional search text is omitted."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main(["series", "search"], stdout=io.StringIO(), stderr=io.StringIO())
    assert exc_info.value.code == EXIT_USAGE


def test_series_search_invalid_search_type_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-search rejects an invalid --search-type value."""
    rc, _, err = _run(
        ["series", "search", "cpi", "--search-type", "bad"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "bad" in err


def test_series_search_invalid_filter_variable_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-search rejects an invalid --filter-variable value."""
    rc, _, err = _run(
        ["series", "search", "cpi", "--filter-variable", "bogus"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "bogus" in err


def test_series_search_invalid_order_by_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-search rejects an invalid --order-by value."""
    rc, _, err = _run(
        ["series", "search", "cpi", "--order-by", "invalid_field"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "invalid_field" in err


def test_series_search_tags_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-search-tags returns raw FRED JSON body."""
    body = '{"tags": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(
            f"{_BASE}/fred/series/search/tags"
            f"?series_search_text=monetary&limit=3{_KEY_SUFFIX}"
        ),
        text=body,
    )
    rc, stdout, _ = _run(
        ["series", "search-tags", "monetary", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"tags"' in stdout


def test_series_search_tags_invalid_tag_group_id_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-search-tags rejects an invalid --tag-group-id value."""
    rc, _, err = _run(
        [
            "series",
            "search-tags",
            "monetary",
            "--tag-group-id",
            "invalid",
        ],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "invalid" in err


def test_series_search_related_tags_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-search-related-tags returns raw FRED JSON body."""
    body = '{"tags": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(
            f"{_BASE}/fred/series/search/related_tags"
            f"?series_search_text=monetary&tag_names=usa&limit=3{_KEY_SUFFIX}"
        ),
        text=body,
    )
    rc, stdout, _ = _run(
        [
            "series",
            "search-related-tags",
            "monetary",
            "--tag-names",
            "usa",
            "--limit",
            "3",
        ],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"tags"' in stdout


def test_series_search_related_tags_semicolon_separator(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-search-related-tags sends tag_names with semicolons."""
    body = '{"tags": []}'
    httpx_mock.add_response(
        method="GET",
        url=(
            f"{_BASE}/fred/series/search/related_tags"
            f"?series_search_text=cpi&tag_names=usa%3Bannual{_KEY_SUFFIX}"
        ),
        text=body,
    )
    rc, _, _ = _run(
        [
            "series",
            "search-related-tags",
            "cpi",
            "--tag-names",
            "usa;annual",
        ],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK


def test_series_categories_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-categories returns raw FRED JSON body."""
    body = '{"categories": [{"id": 32991}]}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/series/categories?series_id=GNPCA{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["series", "categories", "GNPCA"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"categories"' in stdout


def test_series_tags_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-tags returns raw FRED JSON body."""
    body = '{"tags": [{"name": "usa"}]}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/series/tags?series_id=GNPCA{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["series", "tags", "GNPCA"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"tags"' in stdout


def test_series_tags_invalid_order_by_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-tags rejects an invalid --order-by value."""
    rc, _, err = _run(
        ["series", "tags", "GNPCA", "--order-by", "bad_field"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "bad_field" in err


def test_series_release_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-release returns raw FRED JSON body."""
    body = '{"releases": [{"id": 53, "name": "Gross Domestic Product"}]}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/series/release?series_id=GNPCA{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["series", "release", "GNPCA"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"releases"' in stdout


def test_series_updates_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-updates returns raw FRED JSON body."""
    body = '{"seriess": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/series/updates?limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["series", "updates", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"seriess"' in stdout


def test_series_updates_invalid_filter_value_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-updates rejects an invalid --filter-value value."""
    rc, _, err = _run(
        ["series", "updates", "--filter-value", "national"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "national" in err


# ---------------------------------------------------------------------------
# series-vintagedates
# ---------------------------------------------------------------------------


def test_series_vintagedates_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-vintagedates returns raw FRED JSON body."""
    body = '{"vintage_dates": ["1958-12-21", "1959-02-19"], "count": 2}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/series/vintagedates?series_id=GNPCA&limit=5{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["series", "vintage-dates", "GNPCA", "--limit", "5"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"vintage_dates"' in stdout


def test_series_vintagedates_missing_series_id_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-vintagedates exits 2 when positional series_id is omitted."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main(["series", "vintage-dates"], stdout=io.StringIO(), stderr=io.StringIO())
    assert exc_info.value.code == EXIT_USAGE


def test_series_requires_positional_id() -> None:
    """'series show' exits 2 when positional series_id is omitted."""
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["series", "show"])
    assert exc.value.code == EXIT_USAGE


# ---------------------------------------------------------------------------
# Group 3 — Releases / calendar
# ---------------------------------------------------------------------------


def test_releases_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Releases command returns raw FRED JSON body."""
    body = '{"releases": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/releases?limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["release", "list", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"releases"' in stdout


def test_releases_invalid_order_by_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Releases command rejects an invalid --order-by value."""
    rc, _, err = _run(
        ["release", "list", "--order-by", "bad_field"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "bad_field" in err


# Bug 2 — --limit client-side bounds validation


def test_releases_limit_zero_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The releases command rejects --limit 0 (below minimum of 1)."""
    rc, _, err = _run(
        ["release", "list", "--limit", "0"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert ">= 1" in err or "1" in err


def test_releases_limit_negative_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The releases command rejects --limit -5 (negative)."""
    rc, _, _ = _run(
        ["release", "list", "--limit", "-5"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE


def test_releases_limit_above_max_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The releases command rejects --limit 1001 (above maximum of 1000)."""
    rc, _, err = _run(
        ["release", "list", "--limit", "1001"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "<= 1000" in err or "1000" in err


def test_releases_dates_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release calendar returns raw FRED JSON body."""
    body = '{"release_dates": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/releases/dates?limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["release", "calendar", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"release_dates"' in stdout


def test_releases_dates_include_no_data_flag(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release calendar sends include_release_dates_with_no_data=true when set."""
    body = '{"release_dates": []}'
    httpx_mock.add_response(
        method="GET",
        url=(
            f"{_BASE}/fred/releases/dates"
            f"?include_release_dates_with_no_data=true{_KEY_SUFFIX}"
        ),
        text=body,
    )
    rc, _, _ = _run(
        ["release", "calendar", "--include-release-dates-with-no-data"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK


def test_release_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release command returns raw FRED JSON body."""
    body = '{"releases": [{"id": 53, "name": "Gross Domestic Product"}]}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/release?release_id=53{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["release", "show", "53"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"releases"' in stdout


def test_release_dates_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release dates returns raw FRED JSON body."""
    body = '{"release_dates": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/release/dates?release_id=53&limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["release", "dates", "53", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"release_dates"' in stdout


def test_release_dates_include_no_data_flag(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release dates sends include_release_dates_with_no_data=true when flag is set."""
    body = '{"release_dates": []}'
    httpx_mock.add_response(
        method="GET",
        url=(
            f"{_BASE}/fred/release/dates"
            f"?release_id=53&include_release_dates_with_no_data=true{_KEY_SUFFIX}"
        ),
        text=body,
    )
    rc, _, _ = _run(
        [
            "release",
            "dates",
            "53",
            "--include-release-dates-with-no-data",
        ],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK


def test_release_series_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release series returns raw FRED JSON body."""
    body = '{"seriess": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/release/series?release_id=53&limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["release", "series", "53", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"seriess"' in stdout


def test_release_series_invalid_order_by_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release series rejects an invalid --order-by value."""
    rc, _, err = _run(
        ["release", "series", "53", "--order-by", "bad_field"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "bad_field" in err


def test_release_sources_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release sources returns raw FRED JSON body."""
    body = '{"sources": [{"id": 1}]}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/release/sources?release_id=53{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["release", "sources", "53"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"sources"' in stdout


def test_release_tags_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release tags returns raw FRED JSON body."""
    body = '{"tags": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/release/tags?release_id=53&limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["release", "tags", "53", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"tags"' in stdout


def test_release_tags_invalid_tag_group_id_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release tags rejects an invalid --tag-group-id value."""
    rc, _, err = _run(
        ["release", "tags", "53", "--tag-group-id", "invalid"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "invalid" in err


def test_release_related_tags_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release related-tags returns raw FRED JSON body."""
    body = '{"tags": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(
            f"{_BASE}/fred/release/related_tags"
            f"?release_id=53&tag_names=usa&limit=3{_KEY_SUFFIX}"
        ),
        text=body,
    )
    rc, stdout, _ = _run(
        [
            "release",
            "related-tags",
            "53",
            "--tag-names",
            "usa",
            "--limit",
            "3",
        ],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"tags"' in stdout


def test_release_related_tags_invalid_order_by_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release related-tags rejects an invalid --order-by value."""
    rc, _, err = _run(
        [
            "release",
            "related-tags",
            "53",
            "--tag-names",
            "usa",
            "--order-by",
            "bad_field",
        ],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "bad_field" in err


def test_release_tables_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release tables returns raw FRED JSON body."""
    body = '{"elements": {}}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/release/tables?release_id=53{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["release", "tables", "53"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"elements"' in stdout


@pytest.mark.parametrize(
    "args",
    [
        ["release", "show"],
        ["release", "dates"],
        ["release", "series"],
        ["release", "sources"],
        ["release", "tags"],
        ["release", "tables"],
    ],
)
def test_release_missing_positional_exits_2(
    args: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release commands exit 2 when the required positional release-id is omitted."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main(args, stdout=io.StringIO(), stderr=io.StringIO())
    assert exc_info.value.code == EXIT_USAGE


def test_release_related_tags_missing_positional_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release related-tags exits 2 when the required positional ID is omitted."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main(["release", "related-tags"], stdout=io.StringIO(), stderr=io.StringIO())
    assert exc_info.value.code == EXIT_USAGE


# ---------------------------------------------------------------------------
# Item 1 — FRED ID bounds:
#   category_id >= 0 (0 is the documented FRED root category)
#   source_id, release_id, element_id >= 1 (FRED rejects 0 for these)
# ---------------------------------------------------------------------------


def test_category_id_negative_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Negative category_id values exit 2 (category_id must be >= 0)."""
    rc, _, err = _run(
        ["category", "show", "--", "-5"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert ">= 0" in err, f"expected '>= 0' in stderr, got: {err!r}"


@pytest.mark.parametrize(
    ("args", "description"),
    [
        (["source", "show", "--", "0"], "source show 0"),
        (["source", "show", "--", "-1"], "source show -1"),
        (["release", "show", "--", "0"], "release show 0"),
        (["release", "show", "--", "-3"], "release show -3"),
        (
            ["release", "tables", "53", "--element-id", "0"],
            "release tables --element-id 0",
        ),
        (
            ["release", "tables", "53", "--element-id", "-1"],
            "release tables --element-id -1",
        ),
    ],
)
def test_fred_id_zero_or_negative_exits_2(
    args: list[str],
    description: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Source/release/element IDs must be >= 1; zero or negative values exit 2.

    Note: category_id is excluded — category_id=0 is the FRED root and is valid;
    see test_category_id_zero_accepted and test_category_id_negative_exits_2.
    """
    rc, _, err = _run(args, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == EXIT_USAGE, f"{description}: expected exit 2"
    assert ">= 1" in err, f"{description}: expected '>= 1' in stderr, got: {err!r}"


def test_category_id_zero_accepted(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """category_id=0 is the FRED root category and must be accepted (not exit 2)."""
    body = '{"categories": [{"id": 0, "name": "Categories", "parent_id": 0}]}'
    httpx_mock.add_response(
        method="GET",
        url=f"{_BASE}/fred/category?category_id=0{_KEY_SUFFIX}",
        text=body,
    )
    rc, _out, _ = _run(
        ["category", "show", "0"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK


@pytest.mark.parametrize(
    ("args", "url_suffix", "body"),
    [
        (
            ["category", "show", "1"],
            "/fred/category?category_id=1",
            '{"categories": [{"id": 1}]}',
        ),
        (
            ["source", "show", "1"],
            "/fred/source?source_id=1",
            '{"sources": [{"id": 1}]}',
        ),
        (
            ["release", "show", "1"],
            "/fred/release?release_id=1",
            '{"releases": [{"id": 1}]}',
        ),
    ],
)
def test_fred_id_positive_accepted(  # noqa: PLR0913, PLR0917
    args: list[str],
    url_suffix: str,
    body: str,
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FRED integer IDs >= 1 are accepted and forwarded to the API."""
    httpx_mock.add_response(
        method="GET",
        url=f"{_BASE}{url_suffix}{_KEY_SUFFIX}",
        text=body,
    )
    rc, _out, _ = _run(args, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == EXIT_OK


def test_release_tables_include_observation_values_flag(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release tables sends include_observation_values=true when flag is set."""
    body = '{"elements": {}}'
    httpx_mock.add_response(
        method="GET",
        url=(
            f"{_BASE}/fred/release/tables"
            f"?release_id=53&include_observation_values=true{_KEY_SUFFIX}"
        ),
        text=body,
    )
    rc, _, _ = _run(
        ["release", "tables", "53", "--include-observation-values"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK


def test_release_tables_element_id_integer_param(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Release tables sends element_id as an integer query param."""
    body = '{"elements": {}}'
    httpx_mock.add_response(
        method="GET",
        url=(
            f"{_BASE}/fred/release/tables?release_id=53&element_id=12886{_KEY_SUFFIX}"
        ),
        text=body,
    )
    rc, _, _ = _run(
        ["release", "tables", "53", "--element-id", "12886"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK


# ---------------------------------------------------------------------------
# Bug 3 — --filter-variable and --filter-value must appear together
# ---------------------------------------------------------------------------


_FILTER_COMMANDS: Final[list[tuple[list[str], list[str]]]] = [
    (["series", "search"], ["gdp"]),
    (["category", "series"], ["32991"]),
    (["release", "series"], ["53"]),
]


@pytest.mark.parametrize(("command", "required_args"), _FILTER_COMMANDS)
def test_filter_variable_without_filter_value_exits_2(
    command: list[str],
    required_args: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """--filter-variable without --filter-value exits 2 with a directed message."""
    rc, _, err = _run(
        [*command, *required_args, "--filter-variable", "frequency"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "--filter-value" in err


@pytest.mark.parametrize(("command", "required_args"), _FILTER_COMMANDS)
def test_filter_value_without_filter_variable_exits_2(
    command: list[str],
    required_args: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """--filter-value without --filter-variable exits 2 with a directed message."""
    rc, _, err = _run(
        [*command, *required_args, "--filter-value", "Annual"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "--filter-variable" in err


_FILTER_COMMANDS_WITH_URLS: Final[list[tuple[list[str], list[str], str]]] = [
    (
        ["series", "search"],
        ["gdp"],
        "/fred/series/search?search_text=gdp&filter_variable=frequency&filter_value=Annual",
    ),
    (
        ["category", "series"],
        ["32991"],
        "/fred/category/series?category_id=32991&filter_variable=frequency&filter_value=Annual",
    ),
    (
        ["release", "series"],
        ["53"],
        "/fred/release/series?release_id=53&filter_variable=frequency&filter_value=Annual",
    ),
]

_FILTER_COMMANDS_BASE_URLS: Final[list[tuple[list[str], list[str], str]]] = [
    (["series", "search"], ["gdp"], "/fred/series/search?search_text=gdp"),
    (
        ["category", "series"],
        ["32991"],
        "/fred/category/series?category_id=32991",
    ),
    (["release", "series"], ["53"], "/fred/release/series?release_id=53"),
]


@pytest.mark.parametrize(
    ("command", "required_args", "url_suffix"), _FILTER_COMMANDS_WITH_URLS
)
def test_filter_variable_and_value_together_exit_0(  # noqa: PLR0913, PLR0917
    command: list[str],
    required_args: list[str],
    url_suffix: str,
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """--filter-variable and --filter-value together succeed (exit 0)."""
    body = '{"seriess": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=f"{_BASE}{url_suffix}{_KEY_SUFFIX}",
        text=body,
    )
    rc, _, _ = _run(
        [
            *command,
            *required_args,
            "--filter-variable",
            "frequency",
            "--filter-value",
            "Annual",
        ],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK


@pytest.mark.parametrize(
    ("command", "required_args", "url_suffix"), _FILTER_COMMANDS_BASE_URLS
)
def test_neither_filter_variable_nor_value_exits_0(  # noqa: PLR0913, PLR0917
    command: list[str],
    required_args: list[str],
    url_suffix: str,
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Neither --filter-variable nor --filter-value is also valid (exit 0)."""
    body = '{"seriess": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=f"{_BASE}{url_suffix}{_KEY_SUFFIX}",
        text=body,
    )
    rc, _, _ = _run(
        [*command, *required_args],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK


# ---------------------------------------------------------------------------
# Bug 4 — tag-name partner requirements
# ---------------------------------------------------------------------------


def test_tags_series_no_tags_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Tag series with no positional TAGS arg exits 2."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main(
            ["tag", "series", "--limit", "3"],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )
    assert exc_info.value.code == EXIT_USAGE


def test_tags_series_with_tag_names_exits_0(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Tag series with positional TAGS exits 0."""
    body = '{"seriess": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=f"{_BASE}/fred/tags/series?tag_names=usa{_KEY_SUFFIX}",
        text=body,
    )
    rc, _, _ = _run(
        ["tag", "series", "usa"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK


def test_tags_series_with_exclude_only_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The tag series command with only --exclude-tag-names exits 2."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main(
            ["tag", "series", "--exclude-tag-names", "monthly"],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )
    assert exc_info.value.code == EXIT_USAGE


_EXCLUDE_TAG_COMMANDS: Final[list[tuple[list[str], list[str]]]] = [
    (["release", "series"], ["53"]),
    (["category", "series"], ["32991"]),
    (["series", "search"], ["gdp"]),
]


@pytest.mark.parametrize(("command", "required_args"), _EXCLUDE_TAG_COMMANDS)
def test_exclude_tag_names_without_tag_names_exits_2(
    command: list[str],
    required_args: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """--exclude-tag-names without --tag-names exits 2 with a directed message."""
    rc, _, err = _run(
        [*command, *required_args, "--exclude-tag-names", "nsa"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "--tag-names" in err


# ---------------------------------------------------------------------------
# Item 3 — tags-series: tag-names is a required positional argument
# ---------------------------------------------------------------------------


def test_tags_series_exclude_only_missing_positional_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Tag series --exclude-tag-names without the positional TAGS exits 2.

    Rejection comes from the missing required positional argument.
    """
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main(
            ["tag", "series", "--exclude-tag-names", "usa", "--limit", "3"],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )
    assert exc_info.value.code == EXIT_USAGE
