"""Public workflows for observation controls and saved provenance."""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl
import pytest

if TYPE_CHECKING:
    from tests.conftest import HTTPXMock

from examples.workflows import (
    as_of_snapshot,
    catalog,
    export_roundtrip,
    monthly_comparison,
)
from fredq import _core, api
from fredq.cli import main
from fredq.exceptions import FredClientUsageError
from fredq.frames import build_observations


def test_observation_controls_reach_fred(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Explicit controls are sent exactly once without reshaping JSON."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    httpx_mock.add_response(
        url="https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&aggregation_method=eop&limit=2&offset=3&sort_order=desc&api_key=secret&file_type=json",
        text='{"observations":[]}',
    )
    out = io.StringIO()
    assert (
        main(
            [
                "series",
                "observations",
                "DGS10",
                "--aggregation-method",
                "eop",
                "--limit",
                "2",
                "--offset",
                "3",
                "--sort-order",
                "desc",
            ],
            stdout=out,
        )
        == 0
    )
    assert out.getvalue() == '{"observations":[]}'


@pytest.mark.parametrize(
    "encoded", ["secret", r"\u0073" + "ecret"]
)  # cspell:ignore ecret
def test_cli_explains_fred_rejection_without_key(
    encoded: str, httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FRED's explanation reaches stderr, with reflected credentials removed."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    httpx_mock.add_response(
        url="https://api.stlouisfed.org/fred/series?series_id=INVALID&api_key=secret&file_type=json",
        status_code=400,
        text='{"error_code":400,"error_message":"Unknown series for ' + encoded + '"}',
    )
    out, err = io.StringIO(), io.StringIO()
    assert main(["series", "show", "INVALID"], stdout=out, stderr=err) != 0
    assert "Unknown series for [REDACTED]" in err.getvalue()
    assert "secret" not in err.getvalue()
    assert not out.getvalue()


def test_library_export_keeps_normalized_request_and_envelope(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A fetched frame keeps provenance when saved later."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    _core._reset_for_tests()  # pyright: ignore[reportPrivateUsage]
    body = (
        Path(__file__).parent / "fixtures/corpus/series-observations/GNPCA.json"
    ).read_text(encoding="utf-8")
    httpx_mock.add_response(
        url="https://api.stlouisfed.org/fred/series/observations?series_id=GNPCA&observation_start=2024-01-01&aggregation_method=sum&limit=2&offset=0&sort_order=desc&api_key=secret&file_type=json",
        text=body,
    )
    try:
        observations = api.Series("GNPCA").observations(
            observation_start="2024-01-01T12:00:00Z",
            aggregation_method="sum",
            limit=2,
            offset=0,
            sort_order="desc",
        )
        path = tmp_path / "observations.parquet"
        observations.save_parquet(path)
        metadata = pl.read_parquet_metadata(path)
        assert json.loads(metadata["fredq_request"]) == {
            "series_id": "GNPCA",
            "observation_start": "2024-01-01",
            "aggregation_method": "sum",
            "limit": 2,
            "offset": 0,
            "sort_order": "desc",
        }
        assert json.loads(metadata["fredq_envelope"]) == {
            k: v for k, v in json.loads(body).items() if k != "observations"
        }
        assert (
            datetime.fromisoformat(metadata["fredq_fetched_at"])
            == observations.fetched_at
        )
        assert observations.fetched_at.utcoffset() == timezone.utc.utcoffset(None)
        assert metadata["fredq_missing_value"] == "null"
        assert "secret" not in str(metadata)
        second = tmp_path / "saved-later.parquet"
        observations.save_parquet(second)
        assert pl.read_parquet_metadata(second) == metadata
    finally:
        _core._reset_for_tests()  # pyright: ignore[reportPrivateUsage]


def test_manual_observations_do_not_invent_request_context(tmp_path: Path) -> None:
    """Manual construction retains its timestamp and envelope, not a guessed ID."""
    payload = json.loads(
        (
            Path(__file__).parent / "fixtures/corpus/series-observations/GNPCA.json"
        ).read_text(encoding="utf-8")
    )
    fetched_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    observations = build_observations(payload, fetched_at=fetched_at)
    path = tmp_path / "manual.parquet"
    observations.save_parquet(path)
    metadata = pl.read_parquet_metadata(path)
    assert "fredq_series_id" not in metadata
    assert json.loads(metadata["fredq_request"]) == {}
    assert datetime.fromisoformat(metadata["fredq_fetched_at"]) == fetched_at


@pytest.mark.parametrize("surface", ["cli", "library"])
@pytest.mark.parametrize("method", ["avg", "sum", "eop"])
def test_explicit_observation_defaults_and_aggregation_methods(
    surface: str, method: str, httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every supported aggregation and the upper page bound reach FRED."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    _core._reset_for_tests()  # pyright: ignore[reportPrivateUsage]
    body = (
        Path(__file__).parent / "fixtures/corpus/series-observations/GNPCA.json"
    ).read_text(encoding="utf-8")
    httpx_mock.add_response(
        url=f"https://api.stlouisfed.org/fred/series/observations?series_id=GNPCA&aggregation_method={method}&limit=100000&offset=0&sort_order=asc&api_key=secret&file_type=json",
        text=body,
    )
    try:
        if surface == "cli":
            assert (
                main(
                    [
                        "series",
                        "observations",
                        "GNPCA",
                        "--aggregation-method",
                        method,
                        "--limit",
                        "100000",
                        "--offset",
                        "0",
                        "--sort-order",
                        "asc",
                    ],
                    stdout=io.StringIO(),
                )
                == 0
            )
        else:
            assert (
                api.Series("GNPCA")
                .observations(
                    aggregation_method=method, limit=100000, offset=0, sort_order="asc"
                )
                .df.height
                > 0
            )
    finally:
        _core._reset_for_tests()  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("surface", ["cli", "library"])
def test_omitted_controls_and_export_provenance(
    surface: str,
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Omission leaves FRED defaults alone and both exports retain the envelope."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    _core._reset_for_tests()  # pyright: ignore[reportPrivateUsage]
    payload = json.loads(
        (
            Path(__file__).parent / "fixtures/corpus/series-observations/GNPCA.json"
        ).read_text(encoding="utf-8")
    )
    payload["future_field"] = {"nested": [1, 2]}
    httpx_mock.add_response(
        url="https://api.stlouisfed.org/fred/series/observations?series_id=GNPCA&api_key=secret&file_type=json",
        text=json.dumps(payload),
    )
    path = tmp_path / "page.parquet"
    before = datetime.now(timezone.utc)
    try:
        if surface == "cli":
            assert (
                main(
                    [
                        "series",
                        "observations",
                        "GNPCA",
                        "--format",
                        "parquet",
                        "--out",
                        str(path),
                    ],
                    stdout=io.StringIO(),
                )
                == 0
            )
        else:
            api.Series("GNPCA").observations().save_parquet(path)
        metadata = pl.read_parquet_metadata(path)
        assert json.loads(metadata["fredq_request"]) == {"series_id": "GNPCA"}
        assert json.loads(metadata["fredq_envelope"])["future_field"] == {
            "nested": [1, 2]
        }
        assert (
            before
            <= datetime.fromisoformat(metadata["fredq_fetched_at"])
            <= datetime.now(timezone.utc)
        )
        assert metadata["fredq_missing_value"] == (
            "NaN" if surface == "cli" else "null"
        )
    finally:
        _core._reset_for_tests()  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("limit", 0),
        ("limit", 100001),
        ("offset", -1),
        ("aggregation_method", "median"),
        ("sort_order", "sideways"),
    ],
)
def test_observation_controls_reject_invalid_values(
    name: str, value: int | str
) -> None:
    """Both public surfaces validate the new controls before HTTP."""
    series = api.Series("DGS10")
    with pytest.raises(FredClientUsageError):
        series.observations(**{name: value})  # pyright: ignore[reportArgumentType]
    assert (
        main(
            [
                "series",
                "observations",
                "DGS10",
                "--" + name.replace("_", "-"),
                str(value),
            ],
            stderr=io.StringIO(),
        )
        == 2  # ruff: ignore[magic-value-comparison]
    )


@pytest.mark.parametrize(
    "body", ["<html>gateway error</html>", '{"error_message":"unstructured"}', "[]"]
)
def test_cli_does_not_dump_unstructured_errors(
    body: str, httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a structured FRED explanation is printed from an error body."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    httpx_mock.add_response(
        url="https://api.stlouisfed.org/fred/series?series_id=X&api_key=secret&file_type=json",
        status_code=400,
        text=body,
    )
    err = io.StringIO()
    assert main(["series", "show", "X"], stderr=err) == 1
    assert "HTTP 400" in err.getvalue()
    assert body not in err.getvalue()


def test_recipes_use_complete_public_workflows(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Recipes run real public calls, page catalog results, join and reload."""
    monkeypatch.setenv("FRED_API_KEY", "secret")
    _core._reset_for_tests()  # pyright: ignore[reportPrivateUsage]
    corpus = Path(__file__).parent / "fixtures/corpus"
    observations = (corpus / "series-observations/GNPCA.json").read_text(
        encoding="utf-8"
    )
    for query in (
        "series_id=UNRATE&observation_start=2000-01-01&observation_end=2000-12-31&realtime_start=2001-01-01&realtime_end=2001-01-01",
        "series_id=DGS10&observation_start=2024-01-01&observation_end=2024-12-31&frequency=m&aggregation_method=avg",
        "series_id=CPIAUCSL&observation_start=2024-01-01&observation_end=2024-12-31&units=pc1&frequency=m&aggregation_method=avg",
        "series_id=DGS10&observation_start=2024-01-01&observation_end=2024-12-31",
    ):
        httpx_mock.add_response(
            url=f"https://api.stlouisfed.org/fred/series/observations?{query}&api_key=secret&file_type=json",
            text=observations,
        )
    series = json.loads((corpus / "series/DGS10.json").read_text(encoding="utf-8"))[
        "seriess"
    ]
    for offset in (0, 1):
        page = {
            "count": 2,
            "offset": offset,
            "limit": 1,
            "order_by": "series_id",
            "sort_order": "asc",
            "realtime_start": "2024-01-01",
            "realtime_end": "2024-01-01",
            "seriess": series,
        }
        httpx_mock.add_response(
            url=f"https://api.stlouisfed.org/fred/category/series?category_id=125&limit=1&offset={offset}&order_by=series_id&sort_order=asc&api_key=secret&file_type=json",
            text=json.dumps(page),
        )
    try:
        assert as_of_snapshot().df.height > 0
        expected_pages = 2
        assert len(list(catalog(page_size=1))) == expected_pages
        assert monthly_comparison().columns == ["date", "ten_year_yield", "cpi_yoy"]
        loaded, metadata = export_roundtrip(tmp_path / "roundtrip.parquet")
        assert loaded.height > 0
        assert json.loads(metadata["fredq_request"])["series_id"] == "DGS10"
    finally:
        _core._reset_for_tests()  # pyright: ignore[reportPrivateUsage]
