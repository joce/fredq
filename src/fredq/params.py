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

    @property
    def option(self) -> str:
        """Return this parameter's long CLI option."""

        if self.positional:
            return self.name
        return f"--{self.cli_name}"


_TRUE_VALUES: Final[frozenset[str]] = frozenset({"1", "true", "t", "yes", "y", "on"})
_FALSE_VALUES: Final[frozenset[str]] = frozenset({"0", "false", "f", "no", "n", "off"})


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

    # Unix timestamp shortcut.
    try:
        ts = int(stripped)
    except ValueError:
        ts = None
    if ts is not None:
        return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()

    # Calendar date or ISO datetime.
    try:
        parsed_dt = datetime.fromisoformat(stripped.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed_date = date.fromisoformat(stripped)
        except ValueError as exc:
            message = (
                f"expected YYYY-MM-DD date, ISO datetime, or Unix timestamp; "
                f"got {value!r}"
            )
            raise ValueError(message) from exc
        return parsed_date.isoformat()

    if parsed_dt.tzinfo is None:
        parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
    return parsed_dt.astimezone(timezone.utc).date().isoformat()


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
            return int(value)
        except ValueError as exc:
            message = f"{spec.option} expects an integer"
            raise ValueError(message) from exc
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
