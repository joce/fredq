"""Tests for the async endpoint core: error contract, config, calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest

from fredq._core import interpret_body, map_http_error
from fredq.exceptions import FredApiError, FredRequestError

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
