"""Tests for nested subcommand groups."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Final

import pytest

from fredq.cli import build_parser, main
from fredq.commands import COMMANDS, CommandSpec

if TYPE_CHECKING:
    from pathlib import Path

    from tests.conftest import HTTPXMock

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
        ["series", "show", "GNPCA"],
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


def test_series_no_subcommand_shows_series_help(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``fredq series`` (no subcommand) prints the series group help, not root help.

    The series subcommands must appear; root-only commands like ``releases``
    and ``category`` must NOT appear.
    """
    rc, stdout, _ = _run(["series"], monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == EXIT_USAGE
    # A sample of the series subcommands must be listed.
    assert "show" in stdout
    assert "observations" in stdout
    assert "search" in stdout
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


def test_all_commands_have_a_group() -> None:
    """Every command now belongs to a named group (no flat top-level commands)."""
    flat = [c for c in COMMANDS if c.group is None]
    msg = f"Expected all commands to have a group, found flat: {[c.name for c in flat]}"
    assert flat == [], msg


@pytest.mark.parametrize(
    ("argv", "attr", "expected"),
    [
        # Root globals before the group token must survive into the leaf.
        (["--api-key", "ROOTKEY", "series", "show", "GNPCA"], "api_key", "ROOTKEY"),
        (["--no-key-file", "series", "show", "GNPCA"], "no_key_file", True),
        (["--verbose", "series", "show", "GNPCA"], "verbose", True),
        (["--api-key", "K", "release", "show", "53"], "api_key", "K"),
        # Supplied after the group token (before the leaf) — the reason the group
        # parser re-registers the globals at all.
        (["series", "--api-key", "MID", "show", "GNPCA"], "api_key", "MID"),
        # Repeated: the value after the group token wins.
        (
            ["--api-key", "ROOT", "series", "--api-key", "MID", "show", "GNPCA"],
            "api_key",
            "MID",
        ),
        # Absent → defaults are still present on the namespace.
        (["series", "show", "GNPCA"], "api_key", None),
        (["series", "show", "GNPCA"], "no_key_file", False),
        (["series", "show", "GNPCA"], "verbose", False),
    ],
)
def test_root_globals_survive_grouped_commands(
    argv: list[str], attr: str, expected: object
) -> None:
    """Group parsers must not clobber root-level --api-key/--no-key-file/--verbose."""
    args = build_parser().parse_args(argv)
    assert getattr(args, attr) == expected


def test_command_writes_body_to_stdout(
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A command's response body is written verbatim to stdout."""
    body = '{"seriess": [{"id": "GNPCA"}]}'
    httpx_mock.add_response(
        method="GET",
        url=f"{_BASE}/fred/series?series_id=GNPCA{_KEY_SUFFIX}",
        text=body,
    )
    rc, stdout, _ = _run(
        ["series", "show", "GNPCA"],
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert rc == EXIT_OK
    assert stdout.strip() == body


@pytest.mark.parametrize("group", ["series", "category", "release", "source", "tag"])
def test_bare_group_prints_help_exits_2(
    group: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Invoking a group name alone (no subcommand) prints group help and exits 2."""
    rc, stdout, _ = _run([group], monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == EXIT_USAGE
    assert group in stdout  # group help/usage mentions the group name


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


def test_root_epilog_uses_grouped_command_tokens(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Root --help epilog uses noun-verb grouped form (no flat legacy tokens)."""
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    # Grouped discovery examples must appear in the epilog.
    assert "series search" in out
    assert "release list" in out
    assert "source list" in out
    assert "tag list" in out
    assert "category children 0" in out
    # Grouped follow-up examples.
    assert "series observations" in out
    assert "category series" in out
    assert "release series" in out
    # Old flat tokens must NOT appear in the epilog.
    assert "series-search" not in out
    assert "releases\n" not in out  # flat 'releases' command token
    assert "sources\n" not in out
    assert "tags\n" not in out
    assert "category-children" not in out
    assert "series-observations" not in out
    assert "category-series" not in out
    assert "release-series" not in out
