"""Base class and shared field types for FRED response models."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Final

from pydantic import BaseModel, BeforeValidator, ConfigDict


class FredModel(BaseModel):
    """Frozen wire-faithful base for every FRED response model.

    ``extra="allow"`` is load-bearing: unmodeled wire fields land on
    ``model_extra`` where the corpus gates (tests/test_models_gates.py)
    detect them. Field names mirror wire keys exactly; FRED's keys are
    already snake_case, so no alias generator exists.
    """

    model_config = ConfigDict(
        extra="allow",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


_OFFSET_TAIL_LENGTH: Final[int] = 3


def _pad_offset(value: object) -> object:
    """Normalize FRED's minute-less UTC offsets for datetime parsing.

    FRED spells datetimes like ``2026-04-09 07:53:12-05`` (offset hours
    only). Padding the two-digit offset to ``-05:00`` makes the value
    unambiguous ISO 8601 for any parser; values already carrying minutes
    (or no offset) pass through unchanged.

    Returns:
        object: The padded string, or the value unchanged if not shaped so.
    """

    if (
        isinstance(value, str)
        # Only datetimes carry an offset; a bare date like "2026-04-09"
        # must pass through untouched (its "-09" tail is not an offset).
        and (" " in value or "T" in value)
        and len(value) > _OFFSET_TAIL_LENGTH
    ):
        tail = value[-_OFFSET_TAIL_LENGTH:]
        if tail[0] in "+-" and tail[1:].isdigit():
            return f"{value}:00"
    return value


FredDatetime = Annotated[datetime, BeforeValidator(_pad_offset)]
"""Aware datetime accepting FRED's minute-less offset spelling."""
