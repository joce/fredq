"""Tests for parameter coercion."""

from __future__ import annotations

from typing import Final

import pytest

from fredq.params import ParamKind, ParamSpec, coerce_param, parse_boolean, parse_date

ANSWER: Final[int] = 42


def _spec(kind: ParamKind, **overrides: object) -> ParamSpec:
    return ParamSpec(
        name="frequency",
        cli_name="frequency",
        kind=kind,
        help="test",
        **overrides,  # type: ignore[arg-type]
    )


def test_string_param_strips_whitespace() -> None:
    """STRING values are stripped before being returned."""

    spec = _spec(ParamKind.STRING)
    assert coerce_param(spec, "  m  ") == "m"


def test_string_param_allowed_values() -> None:
    """STRING values with allowed_values are validated against the set."""

    spec = _spec(ParamKind.STRING, allowed_values=("d", "w", "m"))
    assert coerce_param(spec, "m") == "m"
    with pytest.raises(ValueError, match="unsupported value"):
        coerce_param(spec, "x")


def test_integer_param() -> None:
    """INTEGER values are parsed and validated."""

    spec = _spec(ParamKind.INTEGER)
    assert coerce_param(spec, "42") == ANSWER
    with pytest.raises(ValueError, match="expects an integer"):
        coerce_param(spec, "not-an-int")


def test_boolean_param() -> None:
    """BOOLEAN values cover common spellings."""

    assert parse_boolean("yes") is True
    assert parse_boolean("no") is False
    with pytest.raises(ValueError, match="expected boolean"):
        parse_boolean("maybe")


def test_date_param_yyyy_mm_dd() -> None:
    """Calendar dates pass through unchanged."""

    spec = _spec(ParamKind.DATE)
    assert coerce_param(spec, "2024-05-01") == "2024-05-01"


def test_date_param_iso_datetime() -> None:
    """ISO datetimes are converted to YYYY-MM-DD (UTC)."""

    assert parse_date("2024-05-01T13:00:00Z") == "2024-05-01"


def test_date_param_unix_timestamp() -> None:
    """Unix-second timestamps are converted to YYYY-MM-DD (UTC)."""

    # 2024-01-01T00:00:00Z = 1704067200
    assert parse_date("1704067200") == "2024-01-01"


def test_date_param_rejects_garbage() -> None:
    """Unrecognized input raises with a helpful message."""

    with pytest.raises(ValueError, match="expected YYYY-MM-DD"):
        parse_date("not-a-date")


def test_csv_param() -> None:
    """CSV values are split, stripped, and rejoined."""

    spec = ParamSpec(
        name="tags",
        cli_name="tags",
        kind=ParamKind.CSV,
        help="test",
    )
    assert coerce_param(spec, " a , b , c ") == "a,b,c"
