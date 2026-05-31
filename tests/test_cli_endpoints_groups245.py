"""CLI endpoint tests for Group 2 (categories), Group 4 (tags), Group 5 (sources)."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Final

import pytest

from fredq.cli import main

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
# Required-param omission tests — commands with required params
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        ["category", "show"],
        ["category", "children"],
        ["category", "related"],
        ["category", "series"],
        ["category", "tags"],
        ["category", "related-tags"],
    ],
)
def test_category_required_param_omission_exits_2(
    args: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Category commands exit 2 when the required category-id is omitted."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main(args, stdout=io.StringIO(), stderr=io.StringIO())
    assert exc_info.value.code == EXIT_USAGE


def test_category_missing_positional_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """'category show' exits 2 when the required positional category-id is omitted."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main(["category", "show"], stdout=io.StringIO(), stderr=io.StringIO())
    assert exc_info.value.code == EXIT_USAGE


# ---------------------------------------------------------------------------
# Group 2 — Category browse
# ---------------------------------------------------------------------------


def test_category_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Category returns raw FRED JSON body."""
    body = '{"categories": [{"id": 0, "name": "Categories", "parent_id": 0}]}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/category?category_id=0{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["category", "show", "0"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"categories"' in stdout


def test_category_children_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """category-children returns raw FRED JSON body."""
    body = '{"categories": []}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/category/children?category_id=0{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["category", "children", "0"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"categories"' in stdout


def test_category_related_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """category-related returns raw FRED JSON body."""
    body = '{"categories": []}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/category/related?category_id=32991{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["category", "related", "32991"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"categories"' in stdout


def test_category_series_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """category-series returns raw FRED JSON body."""
    body = '{"seriess": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/category/series?category_id=32991&limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["category", "series", "32991", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"seriess"' in stdout


def test_category_series_invalid_filter_variable_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """category-series rejects an invalid --filter-variable value."""
    rc, _, err = _run(
        [
            "category",
            "series",
            "32991",
            "--filter-variable",
            "bogus",
        ],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "bogus" in err


def test_category_series_invalid_order_by_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """category-series rejects an invalid --order-by value."""
    rc, _, err = _run(
        [
            "category",
            "series",
            "32991",
            "--order-by",
            "bad_field",
        ],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "bad_field" in err


def test_category_tags_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """category-tags returns raw FRED JSON body."""
    body = '{"tags": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/category/tags?category_id=32991&limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["category", "tags", "32991", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"tags"' in stdout


def test_category_tags_invalid_tag_group_id_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """category-tags rejects an invalid --tag-group-id value."""
    rc, _, err = _run(
        ["category", "tags", "32991", "--tag-group-id", "invalid"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "invalid" in err


def test_category_related_tags_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """category-related-tags returns raw FRED JSON body."""
    body = '{"tags": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(
            f"{_BASE}/fred/category/related_tags"
            f"?category_id=32991&tag_names=usa&limit=3{_KEY_SUFFIX}"
        ),
        text=body,
    )
    rc, stdout, _ = _run(
        [
            "category",
            "related-tags",
            "32991",
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


def test_category_related_tags_invalid_order_by_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """category-related-tags rejects an invalid --order-by value."""
    rc, _, err = _run(
        [
            "category",
            "related-tags",
            "32991",
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


def test_category_related_tags_missing_tag_names_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """category-related-tags exits 2 when --tag-names is omitted."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main(
            ["category", "related-tags", "32991"],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )
    assert exc_info.value.code == EXIT_USAGE


# ---------------------------------------------------------------------------
# Group 4 — Tags
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", ["related-tags"])
def test_tags_required_param_omission_exits_2(
    command: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """related-tags exits 2 when the required tag-names param is omitted."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main([command], stdout=io.StringIO(), stderr=io.StringIO())
    assert exc_info.value.code == EXIT_USAGE


def test_tags_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Tags returns raw FRED JSON body."""
    body = '{"tags": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/tags?limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["tags", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"tags"' in stdout


def test_tags_invalid_tag_group_id_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Tags rejects an invalid --tag-group-id value."""
    rc, _, err = _run(
        ["tags", "--tag-group-id", "invalid"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "invalid" in err


def test_tags_invalid_order_by_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Tags rejects an invalid --order-by value."""
    rc, _, err = _run(
        ["tags", "--order-by", "bad_field"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "bad_field" in err


def test_tags_tag_names_semicolon_url_encoded(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Tags sends tag_names with URL-encoded semicolons."""
    body = '{"tags": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/tags?tag_names=usa%3Bannual{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["tags", "--tag-names", "usa;annual"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"tags"' in stdout


def test_related_tags_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """related-tags returns raw FRED JSON body."""
    body = '{"tags": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/related_tags?tag_names=usa&limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["related-tags", "usa", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"tags"' in stdout


def test_related_tags_missing_positional_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """related-tags exits 2 when the required TAGS positional is omitted."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main(
            ["related-tags", "--limit", "3"],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )
    assert exc_info.value.code == EXIT_USAGE


def test_related_tags_invalid_order_by_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """related-tags rejects an invalid --order-by value."""
    rc, _, err = _run(
        ["related-tags", "usa", "--order-by", "bad_field"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "bad_field" in err


def test_tags_series_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """tags-series returns raw FRED JSON body."""
    body = '{"seriess": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/tags/series?tag_names=usa%3Bannual&limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["tags-series", "usa;annual", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"seriess"' in stdout


def test_tags_series_invalid_order_by_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """tags-series rejects an invalid --order-by value."""
    rc, _, err = _run(
        ["tags-series", "usa", "--order-by", "bad_field"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "bad_field" in err


# ---------------------------------------------------------------------------
# Group 5 — Sources
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", ["source", "source-releases"])
def test_sources_required_param_omission_exits_2(
    command: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Source and source-releases exit 2 when the required source-id is omitted."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main([command], stdout=io.StringIO(), stderr=io.StringIO())
    assert exc_info.value.code == EXIT_USAGE


def test_sources_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Sources returns raw FRED JSON body."""
    body = '{"sources": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/sources?limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["sources", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"sources"' in stdout


def test_sources_invalid_order_by_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Sources rejects an invalid --order-by value."""
    rc, _, err = _run(
        ["sources", "--order-by", "bad_field"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "bad_field" in err


def test_source_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Source returns raw FRED JSON body."""
    body = '{"sources": [{"id": 1, "name": "Board of Governors"}]}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/source?source_id=1{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["source", "1"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"sources"' in stdout


def test_source_releases_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """source-releases returns raw FRED JSON body."""
    body = '{"releases": [], "count": 0}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/fred/source/releases?source_id=1&limit=3{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["source-releases", "1", "--limit", "3"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"releases"' in stdout


def test_source_releases_invalid_order_by_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """source-releases rejects an invalid --order-by value."""
    rc, _, err = _run(
        ["source-releases", "1", "--order-by", "bad_field"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "bad_field" in err


def test_source_missing_positional_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Source exits 2 when the required positional source-id is omitted."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main(["source"], stdout=io.StringIO(), stderr=io.StringIO())
    assert exc_info.value.code == EXIT_USAGE


def test_source_releases_missing_positional_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """source-releases exits 2 when the required positional source-id is omitted."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        main(["source-releases"], stdout=io.StringIO(), stderr=io.StringIO())
    assert exc_info.value.code == EXIT_USAGE
