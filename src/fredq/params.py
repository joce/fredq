"""Endpoint parameter metadata and coercion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from fredq.types import ParamValue


class ParamKind(str, Enum):
    """Supported CLI parameter kinds."""

    STRING = "string"
    CSV = "csv"
    INTEGER = "integer"
    DATE = "date"
    BOOLEAN = "boolean"


@dataclass(frozen=True, slots=True)
class ParamSpec:
    """Describe one endpoint query parameter."""

    name: str
    cli_name: str
    kind: ParamKind
    help: str
    positional: bool = False
    required: bool = False
    default: ParamValue | None = None
    metavar: str | None = None
    min_items: int | None = None
    max_items: int | None = None
    allowed_values: tuple[str, ...] = ()
    csv_separator: str = ","
    min_value: int | None = None
    max_value: int | None = None

    @property
    def option(self) -> str:
        """Return this parameter's long CLI option."""

        if self.positional:
            return self.name
        return f"--{self.cli_name}"


_TRUE_VALUES: Final[frozenset[str]] = frozenset({"1", "true", "t", "yes", "y", "on"})
_FALSE_VALUES: Final[frozenset[str]] = frozenset({"0", "false", "f", "no", "n", "off"})


def bounds_suffix(min_value: int | None, max_value: int | None) -> str:
    """Return a parenthesised bounds annotation suitable for help text.

    Examples:
        bounds_suffix(1, 1000) -> " (1-1000)"
        bounds_suffix(0, None) -> " (>= 0)"
        bounds_suffix(None, 100) -> " (<= 100)"
        bounds_suffix(None, None) -> ""

    Returns:
        str: The bounds suffix, including a leading space when non-empty.
    """

    if min_value is not None and max_value is not None:
        return f" ({min_value}-{max_value})"
    if min_value is not None:
        return f" (>= {min_value})"
    if max_value is not None:
        return f" (<= {max_value})"
    return ""


def _coerce_string_param(spec: ParamSpec, value: str) -> str:
    stripped = value.strip()
    if not stripped:
        message = f"{spec.option} cannot be empty"
        raise ValueError(message)
    if spec.allowed_values and stripped not in spec.allowed_values:
        allowed_text = ", ".join(spec.allowed_values)
        message = (
            f"{spec.option} unsupported value {stripped!r}; "
            f"expected one of: {allowed_text}"
        )
        raise ValueError(message)
    return stripped


def _coerce_csv_param(spec: ParamSpec, value: str) -> str:
    stripped = value.strip()
    if not stripped:
        message = f"{spec.option} cannot be empty"
        raise ValueError(message)
    items = [item.strip() for item in stripped.split(",")]
    if any(not item for item in items):
        message = f"{spec.option} cannot contain empty comma-separated values"
        raise ValueError(message)
    if spec.min_items is not None and len(items) < spec.min_items:
        message = (
            f"{spec.option} expects at least {spec.min_items} "
            f"comma-separated value; got {len(items)}"
        )
        raise ValueError(message)
    if spec.max_items is not None and len(items) > spec.max_items:
        message = (
            f"{spec.option} accepts at most {spec.max_items} "
            f"comma-separated values; got {len(items)}"
        )
        raise ValueError(message)
    if spec.allowed_values:
        allowed_values = set(spec.allowed_values)
        for item in items:
            if item not in allowed_values:
                allowed_text = ", ".join(spec.allowed_values)
                message = (
                    f"{spec.option} unsupported value {item!r}; "
                    f"expected one of: {allowed_text}"
                )
                raise ValueError(message)
    return spec.csv_separator.join(items)


def parse_boolean(value: str) -> bool:
    """Parse a CLI boolean value.

    Returns:
        bool: Parsed boolean.

    Raises:
        ValueError: If the value is not a recognized boolean spelling.
    """

    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    message = f"expected boolean value, got {value!r}"
    raise ValueError(message)


def parse_date(value: str) -> str:
    """Parse a calendar date and return FRED's required ``YYYY-MM-DD`` form.

    Accepts:
        * ``YYYY-MM-DD`` calendar dates.
        * ISO 8601 datetimes (the time component is dropped; UTC assumed
          when the value is naive).
        * Unix timestamps in seconds.

    Returns:
        str: Date in ``YYYY-MM-DD`` form.

    Raises:
        ValueError: If the value is not a recognized date or timestamp.
    """

    stripped = value.strip()
    if not stripped:
        message = "expected YYYY-MM-DD date, ISO datetime, or Unix timestamp"
        raise ValueError(message)

    # Calendar date or ISO datetime — try before the Unix-timestamp shortcut
    # so that bare-digit strings like "2024" are not silently treated as an
    # epoch second (which would return 1970-01-01).
    #
    # Python 3.11+ accepts compact ISO forms like "20240101" in
    # datetime.fromisoformat, but FRED requires the separator form
    # "YYYY-MM-DD", and we do not want to silently coerce compact strings.
    # Require at least one "-" so "20240101" is rejected here and falls
    # through to the Unix-timestamp path (which also rejects it since it
    # is only 8 digits, below the 10-digit threshold).
    if "-" in stripped:
        try:
            parsed_dt = datetime.fromisoformat(stripped.replace("Z", "+00:00"))
        except ValueError:
            parsed_dt = None

        if parsed_dt is not None:
            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
            return parsed_dt.astimezone(timezone.utc).date().isoformat()

        try:
            parsed_date = date.fromisoformat(stripped)
            return parsed_date.isoformat()
        except ValueError:
            pass

    # Unix timestamp — only accepted when the string is ≥10 digits (epoch
    # seconds since 2001-09-09 require 10 digits) so that short digit strings
    # like "2024" or "20240101" are not silently mis-interpreted.
    try:
        ts = int(stripped)
    except ValueError:
        ts = None
    if ts is not None and len(stripped) >= 10:  # noqa: PLR2004
        return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()

    message = (
        f"expected YYYY-MM-DD date, ISO datetime, or Unix timestamp; got {value!r}"
    )
    raise ValueError(message)


def coerce_param(spec: ParamSpec, value: str) -> ParamValue:
    """Coerce one CLI parameter value according to its endpoint spec.

    Returns:
        ParamValue: Coerced scalar query value.

    Raises:
        ValueError: If the value does not satisfy the parameter spec.
    """

    if spec.kind is ParamKind.STRING:
        return _coerce_string_param(spec, value)
    if spec.kind is ParamKind.CSV:
        return _coerce_csv_param(spec, value)
    if spec.kind is ParamKind.INTEGER:
        try:
            int_value = int(value)
        except ValueError as exc:
            message = f"{spec.option} expects an integer"
            raise ValueError(message) from exc
        if spec.min_value is not None and int_value < spec.min_value:
            message = f"{spec.option} must be >= {spec.min_value}"
            raise ValueError(message)
        if spec.max_value is not None and int_value > spec.max_value:
            message = f"{spec.option} must be <= {spec.max_value}"
            raise ValueError(message)
        return int_value
    if spec.kind is ParamKind.DATE:
        try:
            return parse_date(value)
        except ValueError as exc:
            message = f"{spec.option} {exc}"
            raise ValueError(message) from exc
    if spec.kind is ParamKind.BOOLEAN:
        return parse_boolean(value)

    message = f"unsupported parameter kind: {spec.kind}"
    raise ValueError(message)
