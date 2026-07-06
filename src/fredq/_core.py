"""Async endpoint core: shared client, param building, error contract."""

from __future__ import annotations

import json
from typing import Any, cast

from fredq.exceptions import FredApiError, FredRequestError


def _as_object_dict(value: object) -> dict[str, Any] | None:
    """Narrow an arbitrary JSON value to a string-keyed dict, if it is one.

    Returns:
        dict[str, Any] | None: The value, re-typed, or None if not a dict.
    """

    if not isinstance(value, dict):
        return None
    return cast("dict[str, Any]", value)


def _fred_error_shape(payload: object) -> tuple[int, str] | None:
    """Extract FRED's error shape from a parsed body, if present.

    The shape is ``{"error_code": <int>, "error_message": <str>}`` — both
    keys required (corpus evidence: every captured FRED error carries
    both). Anything else is not a FRED API error.

    Returns:
        tuple[int, str] | None: (error_code, error_message), or None.
    """

    payload_dict = _as_object_dict(payload)
    if payload_dict is None:
        return None
    code = payload_dict.get("error_code")
    message = payload_dict.get("error_message")
    if isinstance(code, int) and isinstance(message, str):
        return code, message
    return None


def map_http_error(exc: FredRequestError) -> None:
    """Translate an HTTP-level rejection into the library error contract.

    Always raises: ``FredApiError`` when the body carries FRED's error
    shape, otherwise the original ``FredRequestError`` (a generic gateway
    error is not an API error — mapping is by status + shape, never
    wording).

    Raises:
        FredApiError: If the body matches FRED's error shape.
    """

    if exc.body:
        try:
            payload: object = json.loads(exc.body)
        except json.JSONDecodeError:
            payload = None
        shape = _fred_error_shape(payload)
        if shape is not None:
            code, message = shape
            raise FredApiError(
                error_message=message,
                error_code=code,
                status_code=exc.status_code,
            ) from exc
    raise exc


def interpret_body(body: str) -> dict[str, Any]:
    """Parse a FRED 200 body per the malformed-response contract.

    FRED never envelopes errors inside 200 responses (errors are HTTP
    4xx/5xx; empty result lists are values) — so a 200 only needs to be a
    valid JSON object.

    Returns:
        dict[str, Any]: The full parsed payload.

    Raises:
        FredApiError: If the body is not valid JSON or not a JSON object
            (``error_code=None`` marks the malformed-response contract).
    """

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        message = f"FRED response is not valid JSON: {exc}"
        raise FredApiError(error_message=message) from exc
    payload_dict = _as_object_dict(payload)
    if payload_dict is None:
        message = "FRED response is not a JSON object"
        raise FredApiError(error_message=message)
    return payload_dict
