"""CLI endpoint tests for the GeoFRED (Maps) API commands."""

from __future__ import annotations

import io
import json
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
# geofred series-group
# ---------------------------------------------------------------------------


def test_geofred_series_group_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Geofred series-group returns raw JSON body."""
    body = '{"series_group":{"series_id":"WIPCPI","season":"NSA","frequency":"a"}}'
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/geofred/series/group?series_id=WIPCPI{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["geofred", "series-group", "--series-id", "WIPCPI"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"series_group"' in stdout


def test_geofred_series_group_missing_series_id_exits_2() -> None:
    """Geofred series-group exits 2 when --series-id is omitted."""
    with pytest.raises(SystemExit) as exc_info:
        main(["geofred", "series-group"], stdout=io.StringIO(), stderr=io.StringIO())
    assert exc_info.value.code == EXIT_USAGE


# ---------------------------------------------------------------------------
# geofred series-data
# ---------------------------------------------------------------------------


def test_geofred_series_data_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Geofred series-data returns raw JSON body."""
    body = '{"meta":{},"data":[]}'
    httpx_mock.add_response(
        method="GET",
        url=(
            f"{_BASE}/geofred/series/data"
            f"?series_id=WIPCPI&start_date=2020-01-01{_KEY_SUFFIX}"
        ),
        text=body,
    )
    rc, stdout, _ = _run(
        [
            "geofred",
            "series-data",
            "--series-id",
            "WIPCPI",
            "--start-date",
            "2020-01-01",
        ],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"meta"' in stdout


def test_geofred_series_data_missing_series_id_exits_2() -> None:
    """Geofred series-data exits 2 when --series-id is omitted."""
    with pytest.raises(SystemExit) as exc_info:
        main(["geofred", "series-data"], stdout=io.StringIO(), stderr=io.StringIO())
    assert exc_info.value.code == EXIT_USAGE


# ---------------------------------------------------------------------------
# geofred regional-data
# ---------------------------------------------------------------------------


def test_geofred_regional_data_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Geofred regional-data returns raw JSON body."""
    body = '{"meta":{},"data":[]}'
    httpx_mock.add_response(
        method="GET",
        url=(
            f"{_BASE}/geofred/regional/data"
            "?series_group=882&region_type=state&date=2020-01-01"
            f"&season=NSA&frequency=a&units=Dollars{_KEY_SUFFIX}"
        ),
        text=body,
    )
    rc, stdout, _ = _run(
        [
            "geofred",
            "regional-data",
            "--series-group",
            "882",
            "--region-type",
            "state",
            "--date",
            "2020-01-01",
            "--season",
            "NSA",
            "--frequency",
            "a",
            "--units",
            "Dollars",
        ],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"meta"' in stdout


def test_geofred_regional_data_missing_required_param_exits_2() -> None:
    """Geofred regional-data exits 2 when required params are omitted."""
    with pytest.raises(SystemExit) as exc_info:
        main(
            ["geofred", "regional-data"],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )
    assert exc_info.value.code == EXIT_USAGE


def test_geofred_regional_data_invalid_region_type_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Geofred regional-data rejects an invalid --region-type value."""
    rc, _, err = _run(
        [
            "geofred",
            "regional-data",
            "--series-group",
            "882",
            "--region-type",
            "invalid-region",
            "--date",
            "2020-01-01",
            "--season",
            "NSA",
            "--frequency",
            "a",
            "--units",
            "Dollars",
        ],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "invalid-region" in err


def test_geofred_regional_data_invalid_season_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Geofred regional-data rejects an invalid --season value."""
    rc, _, err = _run(
        [
            "geofred",
            "regional-data",
            "--series-group",
            "882",
            "--region-type",
            "state",
            "--date",
            "2020-01-01",
            "--season",
            "BADSEASON",
            "--frequency",
            "a",
            "--units",
            "Dollars",
        ],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "BADSEASON" in err


def test_geofred_regional_data_invalid_aggregation_method_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Geofred regional-data rejects an invalid --aggregation-method value."""
    rc, _, err = _run(
        [
            "geofred",
            "regional-data",
            "--series-group",
            "882",
            "--region-type",
            "state",
            "--date",
            "2020-01-01",
            "--season",
            "NSA",
            "--frequency",
            "a",
            "--units",
            "Dollars",
            "--aggregation-method",
            "badmethod",
        ],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "badmethod" in err


# ---------------------------------------------------------------------------
# geofred shapes
# ---------------------------------------------------------------------------


def test_geofred_shapes_happy_path(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Geofred shapes writes body to file and emits descriptor to stdout."""
    body = '{"type":"FeatureCollection","features":[]}'
    out_path = tmp_path / "states.geojson"
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/geofred/shapes/file?shape=state{_KEY_SUFFIX}"),
        text=body,
    )
    rc, stdout, _ = _run(
        ["geofred", "shapes", "--shape", "state", "--out", str(out_path)],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK

    # Body written to file verbatim.
    assert out_path.exists()
    assert out_path.read_text(encoding="utf-8") == body

    # Descriptor on stdout.
    descriptor = json.loads(stdout.strip())
    assert descriptor["command"] == "shapes"
    assert descriptor["out"] == str(out_path)
    assert descriptor["bytes"] == len(body.encode("utf-8"))


def test_geofred_shapes_missing_out_exits_2() -> None:
    """Geofred shapes exits 2 when --out is omitted."""
    with pytest.raises(SystemExit) as exc_info:
        main(
            ["geofred", "shapes", "--shape", "state"],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )
    assert exc_info.value.code == EXIT_USAGE


def test_geofred_shapes_missing_shape_exits_2() -> None:
    """Geofred shapes exits 2 when --shape is omitted."""
    with pytest.raises(SystemExit) as exc_info:
        main(
            ["geofred", "shapes", "--out", "out.geojson"],
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )
    assert exc_info.value.code == EXIT_USAGE


def test_geofred_shapes_invalid_shape_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Geofred shapes rejects an invalid --shape value."""
    rc, _, err = _run(
        [
            "geofred",
            "shapes",
            "--shape",
            "invalid-shape",
            "--out",
            "out.geojson",
        ],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_USAGE
    assert "unsupported value" in err or "invalid-shape" in err


def test_geofred_shapes_missing_parent_dir_exits_1_with_message(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Geofred shapes exits 1 when the output parent directory does not exist.

    A raw FileNotFoundError traceback must not appear; only a clean stderr
    message and exit code 1.
    """
    body = '{"type":"FeatureCollection","features":[]}'
    # The parent directory "missing-dir" is never created.
    out_path = tmp_path / "missing-dir" / "out.geojson"
    httpx_mock.add_response(
        method="GET",
        url=(f"{_BASE}/geofred/shapes/file?shape=state{_KEY_SUFFIX}"),
        text=body,
    )
    rc, _, err = _run(
        ["geofred", "shapes", "--shape", "state", "--out", str(out_path)],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == 1
    # Stderr must mention what went wrong — either the failing path fragment or
    # a generic "failed to write" style message.
    assert "missing-dir" in err or "failed to write" in err.lower()
