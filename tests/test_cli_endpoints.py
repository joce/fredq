"""CLI endpoint tests for Group 1 (series discovery) and Group 3 (releases)."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Final

import pytest

from fredq.cli import main
from fredq.commands import COMMANDS

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


@pytest.mark.parametrize("command", [c.name for c in COMMANDS])
def test_all_commands_help_exits_cleanly(command: str) -> None:
    """Every command in COMMANDS must respond to --help with exit 0."""
    with pytest.raises(SystemExit) as exc_info:
        main([command, "--help"])
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
        ["series-search", "--search-text", "inflation", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"seriess"' in stdout


def test_series_search_invalid_search_type_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """series-search rejects an invalid --search-type value."""
    rc, _, err = _run(
        ["series-search", "--search-text", "cpi", "--search-type", "bad"],
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
        ["series-search", "--search-text", "cpi", "--filter-variable", "bogus"],
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
        ["series-search", "--search-text", "cpi", "--order-by", "invalid_field"],
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
        ["series-search-tags", "--series-search-text", "monetary", "--limit", "3"],
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
            "series-search-tags",
            "--series-search-text",
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
            "series-search-related-tags",
            "--series-search-text",
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
            "series-search-related-tags",
            "--series-search-text",
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
        ["series-categories", "--series-id", "GNPCA"],
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
        ["series-tags", "--series-id", "GNPCA"],
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
        ["series-tags", "--series-id", "GNPCA", "--order-by", "bad_field"],
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
        ["series-release", "--series-id", "GNPCA"],
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
        ["series-updates", "--limit", "3"],
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
        ["series-updates", "--filter-value", "national"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "national" in err


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
        ["releases", "--limit", "3"],
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
        ["releases", "--order-by", "bad_field"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "bad_field" in err


def test_releases_dates_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """releases-dates returns raw FRED JSON body."""
    body = '{"release_dates": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/releases/dates?limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["releases-dates", "--limit", "3"],
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
    """releases-dates sends include_release_dates_with_no_data=true when flag is set."""
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
        ["releases-dates", "--include-release-dates-with-no-data"],
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
        ["release", "--release-id", "53"],
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
    """release-dates returns raw FRED JSON body."""
    body = '{"release_dates": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/release/dates?release_id=53&limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["release-dates", "--release-id", "53", "--limit", "3"],
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
    """release-dates sends include_release_dates_with_no_data=true when flag is set."""
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
            "release-dates",
            "--release-id",
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
    """release-series returns raw FRED JSON body."""
    body = '{"seriess": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/release/series?release_id=53&limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["release-series", "--release-id", "53", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"seriess"' in stdout


def test_release_series_invalid_order_by_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """release-series rejects an invalid --order-by value."""
    rc, _, err = _run(
        ["release-series", "--release-id", "53", "--order-by", "bad_field"],
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
    """release-sources returns raw FRED JSON body."""
    body = '{"sources": [{"id": 1}]}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/release/sources?release_id=53{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["release-sources", "--release-id", "53"],
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
    """release-tags returns raw FRED JSON body."""
    body = '{"tags": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/release/tags?release_id=53&limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["release-tags", "--release-id", "53", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"tags"' in stdout


def test_release_tags_invalid_tag_group_id_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """release-tags rejects an invalid --tag-group-id value."""
    rc, _, err = _run(
        ["release-tags", "--release-id", "53", "--tag-group-id", "invalid"],
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
    """release-related-tags returns raw FRED JSON body."""
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
            "release-related-tags",
            "--release-id",
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
    """release-related-tags rejects an invalid --order-by value."""
    rc, _, err = _run(
        [
            "release-related-tags",
            "--release-id",
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
    """release-tables returns raw FRED JSON body."""
    body = '{"elements": {}}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/release/tables?release_id=53{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["release-tables", "--release-id", "53"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"elements"' in stdout


def test_release_tables_include_observation_values_flag(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """release-tables sends include_observation_values=true when flag is set."""
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
        ["release-tables", "--release-id", "53", "--include-observation-values"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK


def test_release_tables_element_id_integer_param(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """release-tables sends element_id as an integer query param."""
    body = '{"elements": {}}'
    httpx_mock.add_response(
        method="GET",
        url=(
            f"{_BASE}/fred/release/tables?release_id=53&element_id=12886{_KEY_SUFFIX}"
        ),
        text=body,
    )
    rc, _, _ = _run(
        ["release-tables", "--release-id", "53", "--element-id", "12886"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
