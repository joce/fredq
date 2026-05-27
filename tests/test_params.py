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


# A1 — parse_date digit-only boundary tests


def test_parse_date_bare_year_raises() -> None:
    """A bare 4-digit year like '2024' must not silently become 1970-01-01."""

    with pytest.raises(ValueError, match="expected YYYY-MM-DD"):
        parse_date("2024")


def test_parse_date_compact_yyyymmdd_raises() -> None:
    """'20240101' is not ISO 8601 (no separators) and must be rejected."""

    with pytest.raises(ValueError, match="expected YYYY-MM-DD"):
        parse_date("20240101")


def test_parse_date_unix_timestamp_still_works() -> None:
    """10-digit Unix timestamps continue to be converted correctly."""

    assert parse_date("1704067200") == "2024-01-01"


def test_parse_date_iso_date_still_works() -> None:
    """YYYY-MM-DD dates pass through unchanged."""

    assert parse_date("2024-01-01") == "2024-01-01"


def test_parse_date_iso_datetime_with_z_still_works() -> None:
    """ISO datetimes ending with Z are accepted and stripped to the date part."""

    assert parse_date("2024-01-01T00:00:00Z") == "2024-01-01"


def test_parse_date_invalid_month_raises() -> None:
    """Month 13 is invalid; date.fromisoformat rejects it."""

    with pytest.raises(ValueError, match="expected YYYY-MM-DD"):
        parse_date("2024-13-40")


def test_parse_date_invalid_day_raises() -> None:
    """Day 30 does not exist in February; date.fromisoformat rejects it."""

    with pytest.raises(ValueError, match="expected YYYY-MM-DD"):
        parse_date("2024-02-30")


def test_csv_param() -> None:
    """CSV values are split, stripped, and rejoined."""

    spec = ParamSpec(
        name="tags",
        cli_name="tags",
        kind=ParamKind.CSV,
        help="test",
    )
    assert coerce_param(spec, " a , b , c ") == "a,b,c"


# C4 — additional params coverage


def test_csv_allowed_values_mismatch_raises() -> None:
    """CSV items not in allowed_values raise ValueError."""

    spec = ParamSpec(
        name="units",
        cli_name="units",
        kind=ParamKind.CSV,
        help="test",
        allowed_values=("lin", "pch"),
    )
    with pytest.raises(ValueError, match="unsupported value"):
        coerce_param(spec, "lin,xyz")


def test_csv_min_items_enforced() -> None:
    """CSV param with min_items rejects lists that are too short."""

    spec = ParamSpec(
        name="tags",
        cli_name="tags",
        kind=ParamKind.CSV,
        help="test",
        min_items=2,
    )
    with pytest.raises(ValueError, match="at least"):
        coerce_param(spec, "a")


def test_csv_max_items_enforced() -> None:
    """CSV param with max_items rejects lists that are too long."""

    spec = ParamSpec(
        name="tags",
        cli_name="tags",
        kind=ParamKind.CSV,
        help="test",
        max_items=2,
    )
    with pytest.raises(ValueError, match="at most"):
        coerce_param(spec, "a,b,c")


def test_parse_boolean_case_insensitive() -> None:
    """parse_boolean is case-insensitive for common true/false spellings."""

    assert parse_boolean("YES") is True
    assert parse_boolean("True") is True
    assert parse_boolean("NO") is False
    assert parse_boolean("FALSE") is False


def test_string_allowed_values_rejects_unknown() -> None:
    """STRING param with allowed_values rejects values not in the set."""

    spec = _spec(ParamKind.STRING, allowed_values=("lin", "pch", "log"))
    with pytest.raises(ValueError, match="unsupported value"):
        coerce_param(spec, "xyz")


# Item 8 — edge-case date string tests


def test_parse_date_negative_year_raises() -> None:
    """'-2024' has a '-' so it enters the ISO path, which rejects it."""

    with pytest.raises(ValueError, match="expected YYYY-MM-DD"):
        parse_date("-2024")


def test_parse_date_trailing_dash_raises() -> None:
    """'2024-' has a '-'; enters the ISO path, then both parse attempts fail."""

    with pytest.raises(ValueError, match="expected YYYY-MM-DD"):
        parse_date("2024-")


def test_parse_date_whitespace_only_raises() -> None:
    """A whitespace-only string is rejected (stripped becomes empty)."""

    with pytest.raises(ValueError, match="expected YYYY-MM-DD"):
        parse_date("   ")


# Bug 2 — INTEGER min_value / max_value bounds


def test_integer_min_value_rejects_below_minimum() -> None:
    """INTEGER with min_value=1 rejects 0 and negative values."""

    spec = _spec(ParamKind.INTEGER, min_value=1, max_value=1000)
    with pytest.raises(ValueError, match="must be >= 1"):
        coerce_param(spec, "0")


def test_integer_min_value_rejects_negative() -> None:
    """INTEGER with min_value=1 rejects -5."""

    spec = _spec(ParamKind.INTEGER, min_value=1, max_value=1000)
    with pytest.raises(ValueError, match="must be >= 1"):
        coerce_param(spec, "-5")


def test_integer_max_value_rejects_above_maximum() -> None:
    """INTEGER with max_value=1000 rejects 1001."""

    spec = _spec(ParamKind.INTEGER, min_value=1, max_value=1000)
    with pytest.raises(ValueError, match="must be <= 1000"):
        coerce_param(spec, "1001")


def test_integer_min_value_boundary_accepted() -> None:
    """INTEGER with min_value=1 accepts 1 (boundary value)."""

    spec = _spec(ParamKind.INTEGER, min_value=1, max_value=1000)
    assert coerce_param(spec, "1") == 1


def test_integer_max_value_boundary_accepted() -> None:
    """INTEGER with max_value=1000 accepts 1000 (boundary value)."""

    spec = _spec(ParamKind.INTEGER, min_value=1, max_value=1000)
    result = coerce_param(spec, "1000")
    assert result == 1000  # noqa: PLR2004


def test_integer_without_bounds_any_value_works() -> None:
    """INTEGER with no bounds still accepts any integer (no regression)."""

    spec = _spec(ParamKind.INTEGER)
    assert coerce_param(spec, "-999") == -999  # noqa: PLR2004
    assert coerce_param(spec, "9999999") == 9999999  # noqa: PLR2004


def test_integer_offset_min_zero_rejects_negative() -> None:
    """INTEGER with min_value=0 (offset) rejects -1."""

    spec = _spec(ParamKind.INTEGER, min_value=0)
    with pytest.raises(ValueError, match="must be >= 0"):
        coerce_param(spec, "-1")


def test_integer_offset_min_zero_accepts_zero() -> None:
    """INTEGER with min_value=0 accepts 0."""

    spec = _spec(ParamKind.INTEGER, min_value=0)
    assert coerce_param(spec, "0") == 0
