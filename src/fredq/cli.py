"""Command-line interface for fredq."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Protocol, TextIO

from typing_extensions import override

from fredq import __version__
from fredq.auth import resolve_api_key
from fredq.client import FredClient
from fredq.commands import COMMANDS, COMMANDS_BY_NAME, GROUP_HELP, CommandSpec
from fredq.exceptions import FredqError
from fredq.params import (
    ParamKind,
    ParamSpec,
    coerce_param,
    enforce_cross_param_rules,
    parse_boolean,
)
from fredq.skills import AGENT_TARGETS, TargetReport
from fredq.skills import install as skills_install
from fredq.skills import resolve_roots as skills_resolve_roots
from fredq.skills import status as skills_status
from fredq.skills import uninstall as skills_uninstall

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fredq.types import ParamValue

_HELP_WIDTH: Final[int] = 100
_HELP_MAX_POSITION: Final[int] = 32

# Commands that support Parquet output. The default JSON path stays in
# effect everywhere else.
_PARQUET_COMMANDS: Final[frozenset[str]] = frozenset({"series-observations"})


def _grouped_display(name: str) -> str:
    """Render a command's user-facing invocation (``group leaf``) for messages.

    Falls back to the routing ``name`` for ungrouped commands.

    Returns:
        str: The grouped ``"group leaf"`` form, or the bare name if ungrouped.
    """

    spec = COMMANDS_BY_NAME.get(name)
    if spec is not None and spec.group is not None:
        return f"{spec.group} {spec.leaf or spec.name}"
    return name


_PARQUET_COMMANDS_HELP: Final[str] = ", ".join(
    sorted(_grouped_display(name) for name in _PARQUET_COMMANDS)
)


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


# Gap (in spaces) between a command and its explanation in the epilog table.
_EPILOG_GAP: Final[int] = 5

# (command, explanation) rows for the root --help "Discovering IDs" table.
_DISCOVERY_ROWS: Final[tuple[tuple[str, str], ...]] = (
    ('fredq series search "unemployment"', "find series IDs by keyword"),
    ("fredq release list", "list release IDs"),
    ("fredq source list", "list source IDs"),
    ("fredq tag list", "list tag names"),
    ("fredq category children 0", "root categories (0 = root; drill down)"),
)

# Follow-up "use an ID" examples in the root --help epilog.
_FOLLOWUP_EXAMPLES: Final[tuple[str, ...]] = (
    "fredq series observations DGS10",
    "fredq category series 106",
    "fredq release series 10",
)


def _build_root_epilog() -> str:
    """Render the root ``--help`` epilog.

    Commands are padded to a fixed gap before their explanation.

    Returns:
        str: The fully rendered epilog text.
    """

    width = max(len(cmd) for cmd, _ in _DISCOVERY_ROWS)
    lines = ["Discovering IDs (start here — these commands need no ID):"]
    for cmd, desc in _DISCOVERY_ROWS:
        pad = " " * (width - len(cmd) + _EPILOG_GAP)
        lines.append(f"  {cmd}{pad}{desc}")
    lines.extend(("", "Then use an ID with the matching command, e.g.:"))
    lines.extend(f"  {cmd}" for cmd in _FOLLOWUP_EXAMPLES)
    lines.extend(("", "Every command has its own --help with parameters and examples."))
    return "\n".join(lines)


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


def _add_global_options(
    parser: argparse.ArgumentParser, *, suppress_defaults: bool = False
) -> None:
    """Register the global options on ``parser``.

    These options live on the root parser and are re-registered on each group
    parser so they can also appear right after a group token. On the group
    parsers, ``suppress_defaults=True`` makes absent options use
    ``argparse.SUPPRESS`` as their default so they do NOT overwrite the value
    already parsed by the root parser (argparse otherwise resets the namespace
    attribute to the subparser's default when the option is not repeated).
    """

    # SUPPRESS-defaulted options leave the namespace attribute untouched when
    # absent, preserving the root-parsed value.
    flag_default = argparse.SUPPRESS if suppress_defaults else None
    bool_default = argparse.SUPPRESS if suppress_defaults else False
    parser.add_argument(
        "--version",
        action="version",
        version=f"fredq {__version__}",
        help="Show the program version and exit.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=bool_default,
        help="Enable debug logging to stderr.",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        metavar="KEY",
        default=flag_default,
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
        default=bool_default,
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
    if param.kind is ParamKind.BOOLEAN:
        # Boolean params are exposed as on/off flags (no value argument).
        # When present, the flag sets the param to True; absent means None
        # (omitted from the request).
        parser.add_argument(
            param.option,
            dest=param.name,
            required=param.required,
            default=param.default,
            action="store_const",
            const=True,
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


# Directory name the installer copies the skill content under (see
# fredq.skills._install.SKILL_DIR_NAME); duplicated here as a literal rather
# than imported so the CLI's report-line formatting stays a pure string
# operation independent of the installer's internals.
_SKILL_DIR_NAME: Final[str] = "fredq"


def _add_skills_targeting_options(parser: argparse.ArgumentParser) -> None:
    """Register ``--agent``/``--to``/``--project`` on an install/uninstall subparser."""

    parser.add_argument(
        "--agent",
        dest="agent",
        default=None,
        metavar="NAME[,NAME...]",
        help=(
            f"Comma-separated named agent targets ({', '.join(sorted(AGENT_TARGETS))})."
        ),
    )
    parser.add_argument(
        "--to",
        dest="to",
        type=Path,
        default=None,
        metavar="PATH",
        help="Additional skills root to install into or remove from.",
    )
    parser.add_argument(
        "--project",
        dest="project",
        action="store_true",
        default=False,
        help="Use project-level roots (relative to the current directory).",
    )


def _add_skills_command_group(
    subparsers: Any,  # noqa: ANN401
) -> argparse.ArgumentParser:
    """Build the ``fredq skills {install,uninstall,list}`` subparser tree.

    Kept separate from the ``COMMANDS``-driven loop in
    :func:`_build_parser_impl`: skills is packaging/installer surface (pure
    filesystem, no FRED endpoint) rather than a modeled FRED command.

    Returns:
        argparse.ArgumentParser: The ``skills`` group parser, so callers can
            print its help when no subcommand is given (same convention as
            the noun-group parsers).
    """

    skills_parser = subparsers.add_parser(
        "skills",
        help="Install, remove, or list the fredq agent skill.",
        description=(
            "Manage the fredq agent skill in agent skill directories. See "
            "`fredq skills <subcommand> --help` for each operation."
        ),
        formatter_class=_HelpFormatter,
    )
    skills_subparsers = skills_parser.add_subparsers(
        dest="skills_action", metavar="SUBCOMMAND"
    )

    install_parser = skills_subparsers.add_parser(
        "install",
        help="Install the fredq agent skill into agent skill directories.",
        description=(
            "Copy the fredq agent skill into the named agent skill "
            "directories, stamping the installed package version. Refuses "
            "to overwrite a directory it does not own."
        ),
        formatter_class=_HelpFormatter,
    )
    _add_skills_targeting_options(install_parser)

    uninstall_parser = skills_subparsers.add_parser(
        "uninstall",
        help="Remove the fredq agent skill from agent skill directories.",
        description=(
            "Remove the fredq agent skill from the named agent skill "
            "directories. Refuses to remove a directory it does not own."
        ),
        formatter_class=_HelpFormatter,
    )
    _add_skills_targeting_options(uninstall_parser)

    skills_subparsers.add_parser(
        "list",
        help="Show where the fredq agent skill is installed.",
        description=(
            "Show the fredq agent skill's install state across every named "
            "agent, at both user and project scope."
        ),
        formatter_class=_HelpFormatter,
    )

    return skills_parser


# Type alias used by _build_parser_impl to keep the return annotation concise.
_GroupParsers = dict[str, argparse.ArgumentParser]


def _build_parser_impl() -> tuple[argparse.ArgumentParser, _GroupParsers]:
    """Core parser construction shared by :func:`build_parser` and :func:`main`.

    Returns:
        tuple: ``(root_parser, group_parsers)`` where ``group_parsers`` maps
            each group name (e.g. ``"series"``) to its
            :class:`argparse.ArgumentParser` so callers can print group-scoped
            help when the user stops at the group level.
    """

    parser = argparse.ArgumentParser(
        prog="fredq",
        description=(
            "Expose FRED (Federal Reserve Economic Data) endpoints to the "
            "command line and print raw JSON response bodies."
        ),
        epilog=_build_root_epilog(),
        formatter_class=_HelpFormatter,
    )
    _add_global_options(parser)
    # Use a private dest so the root-level choice (flat command name or group
    # name) is not clobbered when a group's own subparsers also writes to
    # "command_name".  Flat commands set command_name via set_defaults; grouped
    # leaf commands also set command_name via set_defaults.  The _top_command
    # key captures only the first-level token so main() can detect
    # group-without-subcommand invocations (where command_name stays None).
    subparsers = parser.add_subparsers(dest="_top_command", metavar="COMMAND")

    # Maps group name → group ArgumentParser (used to print group-scoped help).
    group_parsers: dict[str, argparse.ArgumentParser] = {}

    # Maps group name → _SubParsersAction (used to add group subcommands).
    # Stored as Any to avoid pyright complaints about the private argparse type.
    group_subparsers_map: dict[str, Any] = {}

    for command in COMMANDS:
        if command.group is None:
            # Flat top-level command — existing behavior.
            sub = subparsers.add_parser(
                command.name,
                help=command.summary,
                description=command.description,
                epilog=_epilog_for_command(command),
                formatter_class=_HelpFormatter,
            )
            _set_command_parser(sub, command)
        else:
            # Nested command: ensure the group subparser exists.
            if command.group not in group_subparsers_map:
                group_parser = subparsers.add_parser(
                    command.group,
                    help=GROUP_HELP.get(command.group, command.group),
                    description=GROUP_HELP.get(command.group, command.group),
                    formatter_class=_HelpFormatter,
                )
                _add_global_options(group_parser, suppress_defaults=True)
                group_parsers[command.group] = group_parser
                group_subparsers_map[command.group] = group_parser.add_subparsers(
                    dest="command_name", metavar="SUBCOMMAND"
                )

            group_sub: argparse.ArgumentParser = group_subparsers_map[
                command.group
            ].add_parser(
                command.leaf or command.name,
                help=command.summary,
                description=command.description,
                epilog=_epilog_for_command(command),
                formatter_class=_HelpFormatter,
            )
            _set_command_parser(group_sub, command)

    # Packaging/installer surface: not a FRED command, so it is not driven by
    # COMMANDS. Registered into group_parsers under the same convention as the
    # noun groups above so a bare `fredq skills` (no subcommand) prints its
    # help via the existing "group without subcommand" fallback in main().
    group_parsers["skills"] = _add_skills_command_group(subparsers)

    return parser, group_parsers


def build_parser() -> argparse.ArgumentParser:
    """Build fredq's argument parser.

    Flat commands (``group=None``) are added directly to the root subparser.
    Grouped commands (``group="series"``, etc.) are nested one level deeper:
    the group name becomes a top-level subcommand whose own subparsers hold
    the individual commands.  Routing still works by ``command_name`` (the
    globally unique ``CommandSpec.name``) so ``_dispatch_command`` is
    unchanged.

    Returns:
        argparse.ArgumentParser: The configured root parser.
    """

    parser, _ = _build_parser_impl()
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
            # FRED requires lowercase 'true'/'false', not Python's 'True'/'False'.
            collected[spec.name] = "true" if raw else "false"
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
    polars import cost.
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


def _write_json_body(body: str, out: TextIO) -> None:
    """Write a raw JSON body to ``out``, appending a newline if absent."""

    out.write(body)
    if not body.endswith("\n"):
        out.write("\n")


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

    cross_param_error = enforce_cross_param_rules(command, params)
    if cross_param_error is not None:
        err.write(f"{cross_param_error}\n")
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

    _write_json_body(body, out)
    return 0


def _skills_agents_from_namespace(args: argparse.Namespace) -> list[str]:
    """Parse ``--agent`` into a name list, mirroring ``params._coerce_csv_param``.

    Empty comma-separated items (``"claude,,codex"``, or a bare ``","``) are
    a hard usage error rather than silently dropped, matching the CSV
    contract every other ``--`` CSV option follows.

    Returns:
        list[str]: Agent names in the order given, or ``[]`` when ``--agent``
            was not supplied.

    Raises:
        ValueError: If any comma-separated item is empty.
    """

    raw = (getattr(args, "agent", None) or "").strip()
    if not raw:
        return []
    items = [item.strip() for item in raw.split(",")]
    if any(not item for item in items):
        message = "--agent cannot contain empty comma-separated values"
        raise ValueError(message)
    return items


def _skills_roots_or_usage_error(
    args: argparse.Namespace, err: TextIO
) -> list[Path] | None:
    """Resolve ``--agent``/``--to``/``--project`` into skills roots.

    Returns:
        list[Path] | None: The resolved roots, or ``None`` when a usage
            error was already written to ``err`` (caller returns exit code
            2).
    """

    to = getattr(args, "to", None)
    try:
        agents = _skills_agents_from_namespace(args)
    except ValueError as exc:
        err.write(f"{exc}\n")
        return None
    if not agents and to is None:
        err.write("one of --agent or --to is required\n")
        return None
    try:
        return skills_resolve_roots(agents, project=args.project, to=to)
    except ValueError as exc:
        err.write(f"{exc}\n")
        return None


def _skills_install_report_line(report: TargetReport) -> str:
    skill_dir = report.root / _SKILL_DIR_NAME
    if report.action == "refused":
        return f"skipped (not the fredq skill): {skill_dir}"
    return f"installed: {skill_dir} (fredq {report.detail})"


def _skills_uninstall_report_line(report: TargetReport) -> str:
    skill_dir = report.root / _SKILL_DIR_NAME
    if report.action == "refused":
        return f"skipped (not the fredq skill): {skill_dir}"
    if report.action == "removed":
        return f"removed: {skill_dir}"
    return f"absent: {skill_dir}"


def _skills_list_report_line(report: TargetReport) -> str:
    """Format one status() report as an ``agent scope root state`` line.

    ``report.detail`` carries ``"agent scope"`` for an absent target, or
    ``"agent scope version"`` for a current/stale one (see
    ``fredq.skills.status``).

    Returns:
        str: The formatted status line for one named target.
    """

    if report.action == "absent":
        return f"{report.detail} {report.root} absent"
    label, _, version = report.detail.rpartition(" ")
    if report.action == "current":
        return f"{label} {report.root} installed {version} (current)"
    return (
        f"{label} {report.root} installed {version} (stale; current is {__version__})"
    )


def _dispatch_skills(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    """Run a ``fredq skills`` subcommand: pure filesystem, no FRED client.

    Called from :func:`main` before any client construction or API-key
    resolution, so ``fredq skills list`` (and install/uninstall) work with no
    ``FRED_API_KEY`` configured.

    Returns:
        int: ``0`` on a clean run, ``1`` if any target refused (an existing
            directory that is not the fredq skill), ``2`` on a usage error
            (bad ``--agent`` value, or neither ``--agent`` nor ``--to``).
    """

    action = args.skills_action
    if action == "list":
        for report in skills_status():
            out.write(_skills_list_report_line(report))
            out.write("\n")
        return 0

    roots = _skills_roots_or_usage_error(args, err)
    if roots is None:
        return 2

    if action == "install":
        reports = skills_install(roots)
        line_for = _skills_install_report_line
    else:
        reports = skills_uninstall(roots)
        line_for = _skills_uninstall_report_line

    for report in reports:
        out.write(line_for(report))
        out.write("\n")
    return 1 if any(report.action == "refused" for report in reports) else 0


def _resolve_client(
    args: argparse.Namespace,
    client: _FredClientProtocol | None,
    err: TextIO,
) -> tuple[_FredClientProtocol, bool]:
    """Resolve the FRED client from args or an injected client.

    When ``had_error`` is True the caller should propagate exit code 2;
    the error message has already been written to ``err``.

    Returns:
        tuple[_FredClientProtocol, bool]: ``(client, had_error)`` pair.
    """

    if client is not None:
        return client, False

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
            # Return a dummy client; caller checks the error flag before using it.
            return FredClient(""), True
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
        return FredClient(""), True

    return FredClient(api_key), False


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

    parser, group_parsers = _build_parser_impl()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    top_command = getattr(args, "_top_command", None)
    skills_action = getattr(args, "skills_action", None)
    # Skills is packaging/installer surface (pure filesystem, no FRED
    # endpoint): dispatch it before command_name resolution, parquet-pairing
    # enforcement, and (crucially) _resolve_client — so it never constructs a
    # FredClient or touches API-key resolution. A bare `fredq skills` (no
    # skills_action) falls through to the ordinary "group without
    # subcommand" handling below via group_parsers["skills"].
    if top_command == "skills" and skills_action is not None:
        return _dispatch_skills(args, out, err)

    command_name = getattr(args, "command_name", None)
    # command_name is None when no leaf command was resolved:
    #   - No argument at all → top_command is also None → root help.
    #   - User typed a group name but omitted the subcommand → top_command is
    #     the group name, command_name is None → print group-scoped help so the
    #     user sees the group's subcommands rather than the full root listing.
    if not command_name:
        if top_command and top_command in group_parsers:
            group_parsers[top_command].print_help(out)
        else:
            parser.print_help(out)
        return 2
    if command_name not in COMMANDS_BY_NAME:
        parser.print_help(out)
        return 2

    command = COMMANDS_BY_NAME[command_name]

    pairing_error = _enforce_parquet_arg_pairing(args)
    if pairing_error is not None:
        err.write(f"{pairing_error}\n")
        return 2

    active_client, client_error = _resolve_client(args, client, err)
    if client_error:
        return 2

    return _dispatch_command(args, command, out, err, active_client)
