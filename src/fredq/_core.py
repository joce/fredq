"""Async endpoint core: shared client, param building, error contract."""

from __future__ import annotations

import atexit
import concurrent.futures
import contextlib
import json
import threading
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Final, cast

from fredq._bridge import run
from fredq.auth import resolve_api_key
from fredq.client import FredClient
from fredq.commands import COMMANDS_BY_NAME
from fredq.exceptions import FredApiError, FredClientUsageError, FredRequestError
from fredq.params import coerce_param, enforce_cross_param_rules

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx2 as httpx

    from fredq.types import ParamValue


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


_client: FredClient | None = None
_client_options: dict[str, Any] = {}
_client_lock = threading.Lock()

_CLOSE_TIMEOUT_SECONDS: Final[float] = 2.0


def configure(
    *,
    api_key: str | None = None,
    timeout: httpx.Timeout | None = None,
) -> None:
    """Set options for the library's shared FRED client.

    Must be called before the first data call; raises RuntimeError after.
    When ``api_key`` is None, the key resolves like the CLI's: the
    ``FRED_API_KEY`` environment variable, then ``~/.fredq/api_key``.

    Each call replaces the *entire* option set, not just the kwargs you
    pass: any kwarg you omit reverts to its default, even if a previous
    call set it explicitly. Prefer a single ``configure()`` call.

    Raises:
        RuntimeError: If the shared client has already been created.
    """

    with _client_lock:
        if _client is not None:
            message = "configure() must be called before the first fredq call"
            raise RuntimeError(message)
        _client_options.clear()
        _client_options.update(api_key=api_key, timeout=timeout)


def _get_client() -> FredClient:
    global _client  # noqa: PLW0603 - module singleton by design
    with _client_lock:
        if _client is None:
            api_key = _client_options.get("api_key") or resolve_api_key()
            _client = FredClient(api_key, timeout=_client_options.get("timeout"))
    return _client


def _reset_for_tests() -> None:  # pyright: ignore[reportUnusedFunction]
    """Drop the shared client so tests can reconfigure. Test-only."""

    global _client  # noqa: PLW0603 - module singleton by design
    with _client_lock:
        if _client is not None:
            with contextlib.suppress(Exception):
                run(_client.aclose(), timeout=_CLOSE_TIMEOUT_SECONDS)
        _client = None
        _client_options.clear()


def _close_default_client() -> None:
    """Best-effort aclose of the shared client at interpreter exit.

    The wait is bounded: at interpreter exit the bridge's daemon loop
    thread may already be dead, and an unbounded wait would hang forever
    (this exact hang shipped once in the reference implementation).
    """

    if _client is not None:
        with contextlib.suppress(Exception, concurrent.futures.TimeoutError):
            run(_client.aclose(), timeout=_CLOSE_TIMEOUT_SECONDS)


atexit.register(_close_default_client)


def _stringify(value: object) -> str:
    """Render a typed Python value exactly as a CLI user would spell it.

    Lists/tuples join on "," — the separator ``_coerce_csv_param`` SPLITS
    on — so per-item validation tokenizes correctly; coercion then owns
    the re-join to the wire separator (e.g. ";"). Joining on the wire
    separator here would bypass item validation entirely (review catch).

    Returns:
        str: The CLI-equivalent spelling of ``value``.

    Raises:
        FredClientUsageError: If the value's type has no CLI equivalent.
    """

    if isinstance(value, bool):
        # Defensive only: _build_params intercepts bools before calling
        # here. Do NOT delete — bool subclasses int, so falling through
        # would produce Python's "True"/"False" spellings.
        return "true" if value else "false"
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, list | tuple):
        items = cast("list[object] | tuple[object, ...]", value)
        return ",".join(str(item) for item in items)
    if isinstance(value, int | float | str):
        return str(value)
    message = f"unsupported parameter value type: {type(value).__name__}"
    raise FredClientUsageError(message)


def _build_params(
    command_name: str, values: Mapping[str, object]
) -> dict[str, ParamValue]:
    """Validate typed values against the CommandSpec; return wire params.

    Reuses the CLI's own coercion (``coerce_param``) and cross-parameter
    rules so the library sends exactly what an equivalent CLI invocation
    would send.

    Returns:
        dict[str, ParamValue]: Validated wire parameters.

    Raises:
        FredClientUsageError: For unknown parameters, missing required
            parameters, invalid values, or cross-parameter violations.
    """

    command = COMMANDS_BY_NAME[command_name]
    specs = {spec.name: spec for spec in command.params}

    unknown = set(values) - set(specs)
    if unknown:
        names = ", ".join(sorted(unknown))
        message = f"unknown parameter(s) for {command_name}: {names}"
        raise FredClientUsageError(message)

    provided = {name: v for name, v in values.items() if v is not None}
    missing = [
        spec.name
        for spec in command.params
        if spec.required and spec.name not in provided
    ]
    if missing:
        names = ", ".join(missing)
        message = f"{command_name} is missing required parameter(s): {names}"
        raise FredClientUsageError(message)

    params: dict[str, ParamValue] = {}
    for name, value in provided.items():
        spec = specs[name]
        if isinstance(value, bool):
            # FRED requires lowercase 'true'/'false', not Python's
            # 'True'/'False' — mirrors the CLI's own bool handling
            # (cli.py:_collect_params), which bypasses coerce_param.
            params[name] = "true" if value else "false"
            continue
        text = _stringify(value)
        try:
            params[name] = coerce_param(spec, text)
        except ValueError as exc:
            raise FredClientUsageError(str(exc)) from exc

    rule_error = enforce_cross_param_rules(command, params)
    if rule_error is not None:
        raise FredClientUsageError(rule_error)
    return params


async def call_endpoint(
    command_name: str, *, values: Mapping[str, object]
) -> dict[str, Any]:
    """Call one FRED endpoint with typed values; return the parsed payload.

    FRED-reported errors are translated per the library error contract
    (:func:`map_http_error`); an HTTP failure without FRED's error shape
    propagates unchanged.

    Returns:
        dict[str, Any]: The full parsed response payload.

    Raises:
        FredRequestError: If the HTTP failure carries no mappable payload
            (see :func:`map_http_error`).
    """

    command = COMMANDS_BY_NAME[command_name]
    params = _build_params(command_name, values)
    client = _get_client()
    try:
        body = await client.get(command.path, params)
    except FredRequestError as exc:
        map_http_error(exc)
        raise  # unreachable; map_http_error always raises
    return interpret_body(body)
