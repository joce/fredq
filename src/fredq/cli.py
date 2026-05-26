"""Command-line interface for fredq."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import TYPE_CHECKING, Final, Protocol

from fredq import __version__
from fredq.auth import resolve_api_key
from fredq.client import FredClient
from fredq.commands import COMMANDS, COMMANDS_BY_NAME, CommandSpec
from fredq.exceptions import FredqError
from fredq.params import ParamKind, ParamSpec, coerce_param

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fredq.types import ParamValue

_HELP_WIDTH: Final[int] = 100
_HELP_MAX_POSITION: Final[int] = 32


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
            "FRED_API_KEY environment variable, or from ~/.fredq/api_key."
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
    if param.kind is ParamKind.BOOLEAN:
        const = not param.default if isinstance(param.default, bool) else True
        parser.add_argument(
            param.option,
            dest=param.name,
            required=param.required,
            default=param.default,
            action="store_const",
            const=const,
            help=param.help,
        )
        return
    parser.add_argument(
        param.option,
        dest=param.name,
        required=param.required,
        default=param.default,
        metavar=param.metavar,
        help=param.help,
    )


def _set_command_parser(parser: argparse.ArgumentParser, command: CommandSpec) -> None:
    for param in command.params:
        _add_command_param(parser, param)
    parser.set_defaults(command_name=command.name)


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


async def _run_command(
    client: _FredClientProtocol,
    command: CommandSpec,
    params: dict[str, ParamValue],
) -> str:
    try:
        return await client.get(command.path, params, base_url=command.base_url)
    finally:
        await client.aclose()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the fredq CLI.

    Returns:
        int: Process exit code.
    """

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    command_name = getattr(args, "command_name", None)
    if not command_name:
        parser.print_help()
        return 2

    command = COMMANDS_BY_NAME[command_name]

    try:
        api_key = resolve_api_key(explicit=args.api_key)
    except FredqError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    try:
        params = _collect_params(command, args)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    client = FredClient(api_key)
    try:
        body = asyncio.run(_run_command(client, command, params))
    except FredqError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    sys.stdout.write(body)
    if not body.endswith("\n"):
        sys.stdout.write("\n")
    return 0
