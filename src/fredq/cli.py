"""Command-line interface for fredq."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, TextIO

from typing_extensions import override

from fredq import __version__
from fredq.auth import resolve_api_key
from fredq.client import FredClient
from fredq.commands import COMMANDS, COMMANDS_BY_NAME, CommandSpec
from fredq.exceptions import FredqError
from fredq.params import ParamKind, ParamSpec, coerce_param, parse_boolean

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fredq.types import ParamValue

_HELP_WIDTH: Final[int] = 100
_HELP_MAX_POSITION: Final[int] = 32

# Commands that support Parquet output. The default JSON path stays in
# effect everywhere else.
_PARQUET_COMMANDS: Final[frozenset[str]] = frozenset({"series-observations"})
_PARQUET_COMMANDS_HELP: Final[str] = ", ".join(sorted(_PARQUET_COMMANDS))


class _FredClientProtocol(Protocol):
    async def get(
        self,
        path: str,
        params: dict[str, ParamValue],
        *,
        base_url: str | None = None,
    ) -> str: ...

    async def aclose(self) -> None: ...


class _HelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawDescriptionHelpFormatter,
):
    def __init__(self, prog: str) -> None:
        """Initialize a stable-width formatter for LLM-readable help."""

        super().__init__(prog, max_help_position=_HELP_MAX_POSITION, width=_HELP_WIDTH)

    @override
    def _get_help_string(self, action: argparse.Action) -> str:
        help_text = action.help
        if help_text is None:
            help_text = ""
        if action.default is argparse.SUPPRESS or action.default is None:
            return help_text
        if "%(default)" in help_text:
            return help_text
        return f"{help_text} (default: %(default)s)"


def _examples_text(examples: tuple[str, ...]) -> str:
    return "\n".join(f"  {example}" for example in examples)


def _epilog_for_command(command: CommandSpec) -> str:
    notes = ""
    if command.notes:
        notes = "\n\nNotes:\n" + "\n".join(f"  {note}" for note in command.notes)
    return (
        f"FRED endpoint:\n  {command.fred_url}\n\n"
        f"Examples:\n{_examples_text(command.examples)}"
        f"{notes}"
    )


def _add_global_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--version",
        action="version",
        version=f"fredq {__version__}",
        help="Show the program version and exit.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging to stderr.",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        metavar="KEY",
        default=None,
        help=(
            "FRED API key override. By default fredq reads the key from the "
            "FRED_API_KEY environment variable, or from ~/.fredq/api_key. "
            "(visible in process listings; prefer FRED_API_KEY)"
        ),
    )
    parser.add_argument(
        "--no-key-file",
        dest="no_key_file",
        action="store_true",
        default=False,
        help=(
            "Skip the ~/.fredq/api_key fallback. Equivalent to setting "
            "FREDQ_DISABLE_KEY_FILE=1."
        ),
    )


def _add_command_param(parser: argparse.ArgumentParser, param: ParamSpec) -> None:
    if param.positional:
        parser.add_argument(
            param.name,
            metavar=param.metavar,
            help=param.help,
        )
        return
    if param.kind is ParamKind.BOOLEAN:  # pragma: no cover
        # No FRED endpoint params use BOOLEAN yet; kept for future commands.
        const = (
            not param.default if isinstance(param.default, bool) else True
        )  # pragma: no cover
        parser.add_argument(  # pragma: no cover
            param.option,
            dest=param.name,
            required=param.required,
            default=param.default,
            action="store_const",
            const=const,
            help=param.help,
        )
        return  # pragma: no cover
    parser.add_argument(
        param.option,
        dest=param.name,
        required=param.required,
        default=param.default,
        metavar=param.metavar,
        help=param.help,
    )


def _add_parquet_output_options(parser: argparse.ArgumentParser) -> None:
    """Register ``--format`` and ``--out`` on a Parquet-capable subparser."""

    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("json", "parquet"),
        default="json",
        help=(
            "Output format. Default writes the raw FRED JSON body to stdout. "
            "Parquet parses the response into a typed table written to --out."
        ),
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Destination file for the Parquet table. Required when "
            "--format parquet; rejected otherwise."
        ),
    )


def _add_parquet_negative_guards(parser: argparse.ArgumentParser) -> None:
    """Register hidden ``--format`` / ``--out`` on a non-Parquet command.

    Accepts the flags so argparse does not bail with the generic
    ``unrecognized arguments`` message; the post-parse check in
    :func:`_enforce_parquet_arg_pairing` then emits a directed error that
    names the commands that DO support Parquet. Help output is suppressed
    so unrelated commands' help pages stay clean.
    """

    parser.add_argument(
        "--format",
        dest="output_format",
        default="json",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.set_defaults(_parquet_unsupported=True)


def _set_command_parser(parser: argparse.ArgumentParser, command: CommandSpec) -> None:
    for param in command.params:
        _add_command_param(parser, param)
    parser.set_defaults(command_name=command.name)
    if command.name in _PARQUET_COMMANDS:
        _add_parquet_output_options(parser)
    else:
        _add_parquet_negative_guards(parser)


def build_parser() -> argparse.ArgumentParser:
    """Build fredq's argument parser.

    Returns:
        argparse.ArgumentParser: The configured root parser.
    """

    parser = argparse.ArgumentParser(
        prog="fredq",
        description=(
            "Expose FRED (Federal Reserve Economic Data) endpoints to the "
            "command line and print raw JSON response bodies."
        ),
        formatter_class=_HelpFormatter,
    )
    _add_global_options(parser)
    subparsers = parser.add_subparsers(dest="command_name", metavar="COMMAND")
    for command in COMMANDS:
        sub = subparsers.add_parser(
            command.name,
            help=command.summary,
            description=command.description,
            epilog=_epilog_for_command(command),
            formatter_class=_HelpFormatter,
        )
        _set_command_parser(sub, command)
    return parser


def _collect_params(
    command: CommandSpec, namespace: argparse.Namespace
) -> dict[str, ParamValue]:
    collected: dict[str, ParamValue] = {}
    for spec in command.params:
        raw = getattr(namespace, spec.name, None)
        if raw is None:
            continue
        if isinstance(raw, bool):
            collected[spec.name] = raw
            continue
        coerced = coerce_param(spec, str(raw))
        collected[spec.name] = coerced
    return collected


def _enforce_parquet_arg_pairing(args: argparse.Namespace) -> str | None:
    """Validate ``--format`` / ``--out`` pairing.

    Returns:
        str | None: An error message when the combination is invalid, or
            ``None`` when it is valid.
    """

    fmt = getattr(args, "output_format", "json")
    out_path = getattr(args, "out_path", None)
    unsupported = getattr(args, "_parquet_unsupported", False)

    if unsupported and (fmt == "parquet" or out_path is not None):
        return (
            f"--format parquet / --out is only supported on: {_PARQUET_COMMANDS_HELP}."
        )
    if fmt == "parquet" and out_path is None:
        return "--format parquet requires --out PATH."
    if fmt != "parquet" and out_path is not None:
        return "--out is only valid with --format parquet."
    return None


async def _run_command(
    client: _FredClientProtocol,
    command: CommandSpec,
    params: dict[str, ParamValue],
) -> str:
    try:
        return await client.get(command.path, params)
    finally:
        await client.aclose()


def _handle_parquet_output(
    args: argparse.Namespace,
    body: str,
    params: dict[str, ParamValue],
    out: TextIO,
) -> None:
    """Convert ``body`` to Parquet and write to ``args.out_path``.

    Imports the parquet writer lazily so the JSON path never pays the
    pyarrow import cost.
    """

    from fredq.parquet_writer import (  # noqa: PLC0415 - lazy import.
        ObservationsContext,
        write_observations_parquet,
    )

    context = ObservationsContext(
        series_id=str(params.get("series_id", "")),
        units=_optional_str(params.get("units")),
        frequency=_optional_str(params.get("frequency")),
        observation_start=_optional_str(params.get("observation_start")),
        observation_end=_optional_str(params.get("observation_end")),
        realtime_start=_optional_str(params.get("realtime_start")),
        realtime_end=_optional_str(params.get("realtime_end")),
    )
    descriptor = write_observations_parquet(body, args.out_path, context)
    out.write(json.dumps(descriptor, separators=(",", ":")))
    out.write("\n")


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _reconfigure_stream(stream: TextIO, encoding: str = "utf-8") -> None:
    """Reconfigure a text stream's encoding if the stream supports it.

    On Windows the default console encoding may not be UTF-8.  Calling
    ``reconfigure(encoding='utf-8')`` is the standard idiom to fix that
    without replacing the stream object.  The call is a no-op on streams
    that do not expose ``reconfigure`` (e.g. ``io.StringIO`` in tests).
    """

    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding=encoding)


def _dispatch_command(
    args: argparse.Namespace,
    command: CommandSpec,
    out: TextIO,
    err: TextIO,
    active_client: _FredClientProtocol,
) -> int:
    """Resolve params, call FRED, and write output.

    Extracted from :func:`main` to remove ``PLR0911`` / ``C901`` violations
    and make the dispatch step unit-testable independently of argument parsing.

    Args:
        args: Parsed namespace (includes ``output_format``, ``out_path``, etc.).
        command: The matched :class:`CommandSpec`.
        out: Destination stream for the response body / descriptor.
        err: Destination stream for error messages.
        active_client: Constructed or injected FRED client.

    Returns:
        int: Process exit code (0 = success, 1 = request error, 2 = usage error).
    """

    try:
        params = _collect_params(command, args)
    except ValueError as exc:
        err.write(f"{exc}\n")
        return 2

    try:
        body = asyncio.run(_run_command(active_client, command, params))
    except FredqError as exc:
        err.write(f"{exc}\n")
        return 1

    if getattr(args, "output_format", "json") == "parquet":
        try:
            _handle_parquet_output(args, body, params, out)
        except FredqError as exc:
            err.write(f"{exc}\n")
            return 1
        return 0

    out.write(body)
    if not body.endswith("\n"):
        out.write("\n")
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    client: _FredClientProtocol | None = None,
) -> int:
    """Run the fredq CLI.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).
        stdout: Output stream (defaults to ``sys.stdout``).
        stderr: Error stream (defaults to ``sys.stderr``).
        client: Pre-built FRED client for dependency injection in tests.
            When ``None``, a :class:`FredClient` is constructed from the
            resolved API key.

    Returns:
        int: Process exit code.
    """

    out = stdout or sys.stdout
    err = stderr or sys.stderr

    # Ensure UTF-8 on Windows where the default console encoding may differ.
    # Skip reconfiguration when caller-supplied streams are passed in (e.g.
    # io.StringIO used in tests), as those do not need it.
    if stdout is None:
        _reconfigure_stream(out)
    if stderr is None:
        _reconfigure_stream(err)

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    command_name = getattr(args, "command_name", None)
    if not command_name:
        parser.print_help(out)
        return 2

    command = COMMANDS_BY_NAME[command_name]

    pairing_error = _enforce_parquet_arg_pairing(args)
    if pairing_error is not None:
        err.write(f"{pairing_error}\n")
        return 2

    if client is None:
        disable_key_file_env = os.environ.get("FREDQ_DISABLE_KEY_FILE", "").strip()
        if disable_key_file_env:
            try:
                env_disable_key_file = parse_boolean(disable_key_file_env)
            except ValueError:
                err.write(
                    f"FREDQ_DISABLE_KEY_FILE: invalid boolean value "
                    f"{disable_key_file_env!r}; "
                    "expected 1/0, true/false, yes/no, etc.\n"
                )
                return 2
        else:
            env_disable_key_file = False
        no_key_file = getattr(args, "no_key_file", False)
        use_key_file = not no_key_file and not env_disable_key_file
        try:
            api_key = resolve_api_key(
                explicit=args.api_key, use_key_file=use_key_file, stderr=err
            )
        except FredqError as exc:
            err.write(f"{exc}\n")
            return 2
        active_client: _FredClientProtocol = FredClient(api_key)
    else:
        active_client = client

    return _dispatch_command(args, command, out, err, active_client)
