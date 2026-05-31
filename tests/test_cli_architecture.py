"""Tests for nested subcommand groups and body-to-file output architecture."""

from __future__ import annotations

import argparse
import io
import json
from typing import TYPE_CHECKING, Final

import pytest

from fredq.cli import (
    _set_command_parser,  # pyright: ignore[reportPrivateUsage]
    _write_body_to_file,  # pyright: ignore[reportPrivateUsage]
    main,
)
from fredq.commands import COMMANDS, CommandSpec
from fredq.params import ParamKind, ParamSpec

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock

EXIT_USAGE: Final[int] = 2
EXIT_OK: Final[int] = 0

_BASE = "https://api.stlouisfed.org"
_KEY_SUFFIX = "&api_key=secret&file_type=json"


def _run(
    args: list[str],
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[int, str, str]:
    """Run main() with a fake API key and home dir.

    Returns:
        tuple[int, str, str]: (exit code, stdout, stderr).
    """
    monkeypatch.setenv("FRED_API_KEY", "secret")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    out = io.StringIO()
    err = io.StringIO()
    rc = main(args, stdout=out, stderr=err)
    return rc, out.getvalue(), err.getvalue()


def _make_file_output_command() -> CommandSpec:
    """Return a synthetic output_to_file command for testing."""
    return CommandSpec(
        name="test-body-dump",
        path="/geofred/shapes/file",
        summary="Test body-to-file command.",
        description="Synthetic command for body-to-file architecture tests.",
        params=(
            ParamSpec(
                name="shape",
                cli_name="shape",
                kind=ParamKind.STRING,
                help="Shape type.",
                required=True,
                metavar="SHAPE",
            ),
        ),
        examples=("fredq test-body-dump --shape state --out out.geojson",),
        output_to_file=True,
    )


# ---------------------------------------------------------------------------
# Nested subcommand group — architecture tests
# ---------------------------------------------------------------------------


def test_flat_command_still_resolves_after_group_support(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Existing flat commands (group=None) still work after group-support addition."""
    body = '{"seriess": [{"id": "GNPCA"}]}'
    httpx_mock.add_response(
        method="GET",
        url=f"{_BASE}/fred/series?series_id=GNPCA{_KEY_SUFFIX}",
        text=body,
    )
    rc, stdout, _ = _run(
        ["series", "GNPCA"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert '"seriess"' in stdout


def test_top_level_help_includes_series(capsys: pytest.CaptureFixture[str]) -> None:
    """Top-level --help still lists flat commands."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "series" in captured.out


def test_group_without_subcommand_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Invoking a group name alone (no subcommand) exits 2."""
    group_names = {c.group for c in COMMANDS if c.group is not None}
    if not group_names:
        pytest.skip("No grouped commands defined yet.")
    group_name = next(iter(group_names))
    rc, _, _ = _run([group_name], monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == EXIT_USAGE


def test_geofred_no_subcommand_shows_geofred_help(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``fredq geofred`` (no subcommand) prints the geofred group help, not root help.

    The geofred subcommands must appear; root-only commands like ``releases``
    and ``category`` must NOT appear.
    """
    rc, stdout, _ = _run(["geofred"], monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == EXIT_USAGE
    # The four geofred subcommands must be listed.
    assert "series-group" in stdout
    assert "series-data" in stdout
    assert "regional-data" in stdout
    assert "shapes" in stdout
    # Root-level-only commands must not bleed into the group help.
    assert "releases" not in stdout
    assert "category" not in stdout


def test_fredq_no_command_still_shows_root_help(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``fredq`` (no command at all) still prints root help — no regression."""
    rc, stdout, _ = _run([], monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == EXIT_USAGE
    # Root help lists flat commands.
    assert "releases" in stdout or "series" in stdout


def test_fredq_nonexistent_command_still_exits_2() -> None:
    """``fredq nonexistent`` still exits 2 (root unknown-command path unchanged).

    argparse calls sys.exit(2) directly for an invalid choice, so we catch
    SystemExit rather than using the _run helper.
    """
    with pytest.raises(SystemExit) as exc_info:
        main(["nonexistent"], stdout=io.StringIO(), stderr=io.StringIO())
    assert exc_info.value.code == EXIT_USAGE


def test_command_spec_group_field_defaults_to_none() -> None:
    """All commands with group=None are recognizably flat top-level."""
    flat = [c for c in COMMANDS if c.group is None]
    assert len(flat) > 0, "Expected at least some flat commands"


def test_command_spec_output_to_file_synthetic_true() -> None:
    """A CommandSpec with output_to_file=True round-trips the field correctly."""
    cmd = _make_file_output_command()
    assert cmd.output_to_file is True


# ---------------------------------------------------------------------------
# Body-to-file output — architecture tests via a synthetic CommandSpec
# ---------------------------------------------------------------------------


def test_output_to_file_command_requires_out() -> None:
    """A command with output_to_file=True requires --out (omitting it exits 2)."""
    command = _make_file_output_command()
    sub_parser = argparse.ArgumentParser()
    _set_command_parser(sub_parser, command)

    with pytest.raises(SystemExit) as exc_info:
        sub_parser.parse_args(["--shape", "state"])
    assert exc_info.value.code == EXIT_USAGE


def test_output_to_file_writes_body_to_file(tmp_path: Path) -> None:
    """Body-to-file: response body written verbatim to --out; descriptor on stdout."""
    out_path = tmp_path / "body.geojson"
    body = '{"type":"FeatureCollection","features":[]}'

    command = _make_file_output_command()
    args = argparse.Namespace(
        out_path=out_path,
        shape="state",
        _body_to_file=True,
    )
    out_stream = io.StringIO()
    _write_body_to_file(args, body, command, out_stream)

    # File written verbatim.
    assert out_path.read_text(encoding="utf-8") == body

    # Descriptor JSON on stdout.
    descriptor = json.loads(out_stream.getvalue().strip())
    assert descriptor["command"] == "test-body-dump"
    assert descriptor["out"] == str(out_path)
    assert descriptor["bytes"] == len(body.encode("utf-8"))


def test_output_to_file_descriptor_stdout_format(tmp_path: Path) -> None:
    """Descriptor JSON has command, out, and bytes keys."""
    out_path = tmp_path / "test.json"
    body = '{"hello": "world"}'
    command = _make_file_output_command()
    args = argparse.Namespace(out_path=out_path)
    out_stream = io.StringIO()
    _write_body_to_file(args, body, command, out_stream)

    descriptor = json.loads(out_stream.getvalue().strip())
    assert set(descriptor.keys()) == {"command", "out", "bytes"}


def test_non_file_output_command_unchanged(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Commands with output_to_file=False (default) still write body to stdout."""
    body = '{"seriess": [{"id": "GNPCA"}]}'
    httpx_mock.add_response(
        method="GET",
        url=f"{_BASE}/fred/series?series_id=GNPCA{_KEY_SUFFIX}",
        text=body,
    )
    rc, stdout, _ = _run(
        ["series", "GNPCA"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert stdout.strip() == body


def test_grouped_command_registers_under_leaf_and_routes_by_name() -> None:
    """CommandSpec.leaf is the display token; name stays the routing key."""
    spec = CommandSpec(
        name="series-observations",
        path="/x",
        summary="s",
        description="d",
        params=(),
        examples=(),
        group="series",
        leaf="observations",
    )
    assert (spec.leaf or spec.name) == "observations"
    assert spec.name == "series-observations"  # routing key unchanged
