"""Tests for the async endpoint core: error contract, config, calls."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

import fredq._core as core
from fredq._bridge import run
from fredq._core import interpret_body, map_http_error
from fredq.exceptions import FredApiError, FredClientUsageError, FredRequestError

if TYPE_CHECKING:
    from collections.abc import Iterator

CORPUS: Final[Path] = Path(__file__).parent / "fixtures" / "corpus"


def _corpus_error(rel: str, status: int) -> FredRequestError:
    """Build the exact FredRequestError the client would raise for a capture.

    Returns:
        FredRequestError: Error carrying the real corpus body.
    """

    body = (CORPUS / rel).read_text(encoding="utf-8")
    return FredRequestError(status, "https://api.stlouisfed.org/x", body=body)


def test_http_error_with_fred_shape_maps_to_api_error() -> None:
    """A 400 with FRED's error shape becomes FredApiError (corpus-pinned)."""

    exc = _corpus_error("series/ERR_invalid-id.json", 400)
    with pytest.raises(FredApiError) as exc_info:
        map_http_error(exc)
    err = exc_info.value
    assert err.status_code == 400  # noqa: PLR2004
    assert err.error_code == 400  # noqa: PLR2004
    assert "does not exist" in err.error_message
    assert err.__cause__ is exc


def test_http_500_with_fred_shape_maps_to_api_error() -> None:
    """GeoFRED-style 500s with the shape map the same way (corpus-pinned)."""

    exc = _corpus_error("series-group/ERR_invalid-id.json", 500)
    with pytest.raises(FredApiError) as exc_info:
        map_http_error(exc)
    assert exc_info.value.status_code == 500  # noqa: PLR2004
    assert exc_info.value.error_code == 500  # noqa: PLR2004


def test_no_not_found_subclass_exists() -> None:
    """Evidence ruling: FRED's 400 shape is identical for bad key, bad param.

    Missing entity (corpus 2026-07-05) is included too, so a not-found
    subclass would require wording-sniffing, which is forbidden.
    """

    import fredq.exceptions as exc_mod  # noqa: PLC0415

    not_foundish = [n for n in dir(exc_mod) if "notfound" in n.lower()]
    assert not_foundish == []


def test_http_error_without_shape_reraises_original() -> None:
    """A body that is not FRED's error shape leaves FredRequestError alone."""

    exc = FredRequestError(502, "https://x", body="<html>gateway</html>")
    with pytest.raises(FredRequestError) as exc_info:
        map_http_error(exc)
    assert exc_info.value is exc


def test_http_error_without_body_reraises_original() -> None:
    """No body at all: the transport-level error stands."""

    exc = FredRequestError(503, "https://x", body=None)
    with pytest.raises(FredRequestError):
        map_http_error(exc)


def test_interpret_body_parses_ok_payload() -> None:
    """A real ok capture parses to its full envelope dict (corpus-pinned)."""

    body = (CORPUS / "series" / "GNPCA.json").read_text(encoding="utf-8")
    payload = interpret_body(body)
    assert isinstance(payload, dict)
    assert "seriess" in payload


def test_interpret_body_rejects_malformed_json() -> None:
    """A 200 with a non-JSON body raises FredApiError (malformed contract)."""

    with pytest.raises(FredApiError) as exc_info:
        interpret_body("<html>corrupt</html>")
    assert exc_info.value.error_code is None
    assert "not valid JSON" in exc_info.value.error_message


def test_interpret_body_rejects_non_object_json() -> None:
    """A 200 whose JSON is not an object raises the same contract error."""

    with pytest.raises(FredApiError):
        interpret_body(json.dumps([1, 2, 3]))


class _StubClient:
    """Records the get() call; returns a canned body. No network."""

    def __init__(self, body: str = "{}") -> None:
        self.body = body
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.closed = False

    async def get(
        self,
        path: str,
        params: dict[str, object],
        *,
        base_url: str | None = None,  # noqa: ARG002
    ) -> str:
        self.calls.append((path, dict(params)))
        return self.body

    async def aclose(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _fresh_core() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """Reset the module singleton around every test in this file."""

    core._reset_for_tests()  # pyright: ignore[reportPrivateUsage]
    yield
    core._reset_for_tests()  # pyright: ignore[reportPrivateUsage]


def _install_stub(monkeypatch: pytest.MonkeyPatch, body: str = "{}") -> _StubClient:
    stub = _StubClient(body)
    monkeypatch.setattr(core, "_get_client", lambda: stub)
    return stub


def test_call_endpoint_builds_validated_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typed values serialize to the exact wire spellings the CLI sends."""

    stub = _install_stub(monkeypatch, body='{"observations": []}')
    payload = run(
        core.call_endpoint(
            "series-observations",
            values={
                "series_id": "DGS10",
                "observation_start": date(2024, 1, 1),
                "frequency": "m",
            },
        )
    )
    assert payload == {"observations": []}
    path, params = stub.calls[0]
    assert path == "/fred/series/observations"
    assert params == {
        "series_id": "DGS10",
        "observation_start": "2024-01-01",
        "frequency": "m",
    }


def test_call_endpoint_serializes_bool_and_csv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Booleans go as lowercase strings; CSV lists join on the spec separator."""

    stub = _install_stub(monkeypatch)
    run(
        core.call_endpoint(
            "release-dates",
            values={"release_id": 53, "include_release_dates_with_no_data": True},
        )
    )
    assert stub.calls[0][1]["include_release_dates_with_no_data"] == "true"

    run(
        core.call_endpoint(
            "tags-series",
            values={"tag_names": ["usa", "quarterly"]},
        )
    )
    assert stub.calls[1][1]["tag_names"] == "usa;quarterly"


def test_call_endpoint_rejects_unknown_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A kwarg that is not a wire param of the command is a usage error."""

    _install_stub(monkeypatch)
    with pytest.raises(FredClientUsageError, match="unknown parameter"):
        run(core.call_endpoint("series", values={"series_id": "X", "nope": 1}))


def test_call_endpoint_rejects_missing_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omitting a required wire param is a usage error, not a FRED 400."""

    _install_stub(monkeypatch)
    with pytest.raises(FredClientUsageError, match="required"):
        run(core.call_endpoint("series", values={}))


def test_call_endpoint_rejects_invalid_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Values run through the same coercion the CLI uses (bounds, choices)."""

    _install_stub(monkeypatch)
    with pytest.raises(FredClientUsageError, match="limit"):
        run(core.call_endpoint("releases", values={"limit": 0}))  # min is 1


def test_call_endpoint_enforces_cross_param_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CommandSpec cross-parameter rules apply to library calls too.

    series-search declares filter_variable/filter_value as mutually
    dependent (commands.py); providing one without the other is a usage
    error before any request is sent.
    """

    stub = _install_stub(monkeypatch)
    with pytest.raises(FredClientUsageError, match="filter-value"):
        run(
            core.call_endpoint(
                "series-search",
                values={"search_text": "gdp", "filter_variable": "frequency"},
            )
        )
    assert stub.calls == []  # rejected before reaching the client


def test_call_endpoint_maps_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP failures route through map_http_error (corpus body -> FredApiError)."""

    body = (CORPUS / "series" / "ERR_invalid-id.json").read_text(encoding="utf-8")

    class _ErrClient(_StubClient):
        async def get(
            self,
            path: str,
            params: dict[str, object],
            *,
            base_url: str | None = None,  # noqa: ARG002
        ) -> str:
            self.calls.append((path, dict(params)))
            raise FredRequestError(400, "https://x", body=body)

    def _get_err_client() -> _ErrClient:
        return _ErrClient()

    monkeypatch.setattr(core, "_get_client", _get_err_client)
    with pytest.raises(FredApiError) as exc_info:
        run(core.call_endpoint("series", values={"series_id": "ZZZNOTREAL"}))
    assert exc_info.value.error_code == 400  # noqa: PLR2004


def test_configure_before_first_call_only() -> None:
    """configure() raises once the shared client exists."""

    core.configure(api_key="k1")
    assert core._get_client() is not None  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(RuntimeError, match="before the first"):
        core.configure(api_key="k2")


def test_configure_replace_all_semantics() -> None:
    """Each configure() call replaces the entire option set."""

    core.configure(api_key="k1", timeout=None)
    core._reset_for_tests()  # pyright: ignore[reportPrivateUsage]
    core.configure(api_key="k2")
    assert core._client_options == {  # pyright: ignore[reportPrivateUsage]
        "api_key": "k2",
        "timeout": None,
    }


def test_stringify_joins_lists_on_comma_for_coercion() -> None:
    """Lists join on "," — the separator _coerce_csv_param splits on.

    Joining on the wire separator (";") instead would make per-item
    validation see one giant token and bypass allowed_values/min_items
    checks (review catch). Coercion owns the re-join to the wire form.
    """

    stringify = core._stringify  # pyright: ignore[reportPrivateUsage]
    assert stringify(["usa", "quarterly"]) == "usa,quarterly"
    assert stringify(("a", "b", "c")) == "a,b,c"


def test_call_endpoint_rejects_unsupported_value_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A param value with no CLI-equivalent spelling is a usage error."""

    _install_stub(monkeypatch)
    with pytest.raises(FredClientUsageError, match="unsupported parameter value"):
        run(core.call_endpoint("series", values={"series_id": {"not": "a str"}}))
