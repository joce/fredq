"""Tests for the `fredq skills` CLI group (spec: agent-skills design, Task 3).

Filesystem operations run against ``tmp_path``: ``pathlib.Path.home`` is
monkeypatched directly, and the CWD is redirected via ``monkeypatch.chdir``,
mirroring ``tests/test_skills_install.py``. No ``FRED_API_KEY`` is ever set
in this module: the `skills` group is packaging/installer surface that must
work with no API key configured (AGENTS.md CLI-layer rules).
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

import fredq
from fredq.cli import main
from fredq.skills import AGENT_TARGETS

ARGPARSE_ERROR = 2


@pytest.fixture
def home_and_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Point Path.home()/Path.cwd() at isolated tmp_path subdirectories.

    Also clears FRED_API_KEY and points HOME/USERPROFILE at tmp_path so no
    real ``~/.fredq/api_key`` can leak into a test, and skills commands can
    be shown to run without any API key configured.

    Returns:
        tuple[Path, Path]: The fake (home, cwd) directories.
    """

    home = tmp_path / "home"
    cwd = tmp_path / "project"
    home.mkdir()
    cwd.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(cwd)
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.delenv("FREDQ_DISABLE_KEY_FILE", raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home, cwd


def _write_foreign_skill(skill_dir: Path, *, name: str = "other") -> None:
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: not ours\n---\nbody\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# skills install
# ---------------------------------------------------------------------------


def test_skills_install_agent_comma_list_prints_one_line_per_target(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """--agent claude,codex installs both and prints one installed line each."""

    home, _cwd = home_and_cwd
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        ["skills", "install", "--agent", "claude,codex"],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert not stderr.getvalue()
    claude_root = home / ".claude" / "skills"
    codex_root = home / ".agents" / "skills"
    lines = stdout.getvalue().splitlines()
    assert lines == [
        f"installed: {claude_root / 'fredq'} (fredq {fredq.__version__})",
        f"installed: {codex_root / 'fredq'} (fredq {fredq.__version__})",
    ]
    assert (claude_root / "fredq" / "SKILL.md").is_file()
    assert (codex_root / "fredq" / "SKILL.md").is_file()


def test_skills_install_requires_agent_or_to(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """Neither --agent nor --to is a usage error mentioning both flags."""

    del home_and_cwd
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(["skills", "install"], stdout=stdout, stderr=stderr)

    assert exit_code == ARGPARSE_ERROR
    message = stderr.getvalue()
    assert "--agent" in message
    assert "--to" in message


def test_skills_install_bogus_agent_names_offender_and_known_agents(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """--agent bogus exits 2 naming the bogus value and known agents."""

    del home_and_cwd
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        ["skills", "install", "--agent", "bogus"], stdout=stdout, stderr=stderr
    )

    assert exit_code == ARGPARSE_ERROR
    message = stderr.getvalue()
    assert "bogus" in message
    for agent in AGENT_TARGETS:
        assert agent in message


def test_skills_install_empty_comma_item_is_a_usage_error(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """--agent "claude,,codex" exits 2 like a CSV param would, not silently.

    Mirrors ``params._coerce_csv_param``'s CSV contract: empty
    comma-separated values are rejected, never dropped.
    """

    home, _cwd = home_and_cwd
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        ["skills", "install", "--agent", "claude,,codex"],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == ARGPARSE_ERROR
    assert "empty comma-separated" in stderr.getvalue()
    assert not (home / ".claude" / "skills" / "fredq").exists()


def test_skills_install_only_commas_is_a_usage_error(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """--agent "," exits 2 as empty items, not as a missing flag."""

    del home_and_cwd
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        ["skills", "install", "--agent", ","], stdout=stdout, stderr=stderr
    )

    assert exit_code == ARGPARSE_ERROR
    assert "empty comma-separated" in stderr.getvalue()


def test_skills_install_project_switches_to_project_roots(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """--project resolves pi's project-level .pi/skills root."""

    _home, cwd = home_and_cwd
    stdout = StringIO()

    exit_code = main(
        ["skills", "install", "--agent", "pi", "--project"],
        stdout=stdout,
    )

    assert exit_code == 0
    project_root = cwd / ".pi" / "skills"
    assert stdout.getvalue().splitlines() == [
        f"installed: {project_root / 'fredq'} (fredq {fredq.__version__})",
    ]
    assert (project_root / "fredq" / "SKILL.md").is_file()


def test_skills_install_to_adds_a_root(
    home_and_cwd: tuple[Path, Path], tmp_path: Path
) -> None:
    """--to PATH adds an extra root alongside any --agent roots."""

    del home_and_cwd
    stdout = StringIO()
    custom_root = tmp_path / "custom-root"

    exit_code = main(
        ["skills", "install", "--to", str(custom_root)],
        stdout=stdout,
    )

    assert exit_code == 0
    assert stdout.getvalue().splitlines() == [
        f"installed: {custom_root / 'fredq'} (fredq {fredq.__version__})",
    ]
    assert (custom_root / "fredq" / "SKILL.md").is_file()


def test_skills_install_refused_target_reports_and_continues(
    home_and_cwd: tuple[Path, Path], tmp_path: Path
) -> None:
    """A refused target prints skipped and other targets still install; exit 1."""

    home, _cwd = home_and_cwd
    foreign_root = tmp_path / "foreign"
    _write_foreign_skill(foreign_root / "fredq", name="other")
    stdout = StringIO()

    exit_code = main(
        ["skills", "install", "--agent", "claude", "--to", str(foreign_root)],
        stdout=stdout,
    )

    assert exit_code == 1
    claude_root = home / ".claude" / "skills"
    lines = stdout.getvalue().splitlines()
    assert f"installed: {claude_root / 'fredq'} (fredq {fredq.__version__})" in lines
    assert f"skipped (not the fredq skill): {foreign_root / 'fredq'}" in lines


# ---------------------------------------------------------------------------
# skills uninstall
# ---------------------------------------------------------------------------


def test_skills_uninstall_removed_and_absent_lines(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """Uninstall mirrors targeting and prints removed:/absent: lines."""

    home, _cwd = home_and_cwd
    main(["skills", "install", "--agent", "claude"])
    stdout = StringIO()

    exit_code = main(
        ["skills", "uninstall", "--agent", "claude,codex"],
        stdout=stdout,
    )

    assert exit_code == 0
    claude_root = home / ".claude" / "skills"
    codex_root = home / ".agents" / "skills"
    assert stdout.getvalue().splitlines() == [
        f"removed: {claude_root / 'fredq'}",
        f"absent: {codex_root / 'fredq'}",
    ]
    assert not (claude_root / "fredq").exists()


def test_skills_uninstall_refused_target_reports_exit_1(
    home_and_cwd: tuple[Path, Path], tmp_path: Path
) -> None:
    """A foreign directory refuses uninstall and sets exit code 1."""

    del home_and_cwd
    foreign_root = tmp_path / "foreign"
    _write_foreign_skill(foreign_root / "fredq", name="other")
    stdout = StringIO()

    exit_code = main(
        ["skills", "uninstall", "--to", str(foreign_root)],
        stdout=stdout,
    )

    assert exit_code == 1
    assert (
        f"skipped (not the fredq skill): {foreign_root / 'fredq'}" in stdout.getvalue()
    )
    assert (foreign_root / "fredq" / "SKILL.md").exists()


def test_skills_uninstall_requires_agent_or_to(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """Uninstall also requires at least one of --agent/--to."""

    del home_and_cwd
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(["skills", "uninstall"], stdout=stdout, stderr=stderr)

    assert exit_code == ARGPARSE_ERROR
    message = stderr.getvalue()
    assert "--agent" in message
    assert "--to" in message


# ---------------------------------------------------------------------------
# skills list
# ---------------------------------------------------------------------------


def test_skills_list_reports_absent_for_every_named_target(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """List prints one absent line per named target x scope on a clean machine."""

    del home_and_cwd
    stdout = StringIO()

    exit_code = main(["skills", "list"], stdout=stdout)

    assert exit_code == 0
    lines = stdout.getvalue().splitlines()
    assert len(lines) == len(AGENT_TARGETS) * 2
    for agent in AGENT_TARGETS:
        assert any(
            line.startswith(f"{agent} user ") and line.endswith(" absent")
            for line in lines
        )
        assert any(
            line.startswith(f"{agent} project ") and line.endswith(" absent")
            for line in lines
        )


def test_skills_list_reports_installed_current_and_stale(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """List reports installed <version> (current) after a fresh install."""

    home, _cwd = home_and_cwd
    main(["skills", "install", "--agent", "claude"])
    stdout = StringIO()

    exit_code = main(["skills", "list"], stdout=stdout)

    assert exit_code == 0
    claude_root = home / ".claude" / "skills"
    expected = f"claude user {claude_root} installed {fredq.__version__} (current)"
    assert expected in stdout.getvalue().splitlines()


def test_skills_list_reports_stale_with_current_version(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """List reports a stale install with a message naming the current version."""

    home, _cwd = home_and_cwd
    main(["skills", "install", "--agent", "claude"])
    skill_md = home / ".claude" / "skills" / "fredq" / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    doctored = text.replace(f"version: {fredq.__version__}", "version: 0.0.0-old")
    skill_md.write_text(doctored, encoding="utf-8", newline="\n")
    stdout = StringIO()

    exit_code = main(["skills", "list"], stdout=stdout)

    assert exit_code == 0
    claude_root = home / ".claude" / "skills"
    expected = (
        f"claude user {claude_root} installed 0.0.0-old "
        f"(stale; current is {fredq.__version__})"
    )
    assert expected in stdout.getvalue().splitlines()


def test_skills_list_exits_zero_even_with_no_flags(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """List takes no targeting flags and always exits 0."""

    del home_and_cwd
    exit_code = main(["skills", "list"])

    assert exit_code == 0


# ---------------------------------------------------------------------------
# No API key required — skills is packaging/installer surface
# ---------------------------------------------------------------------------


def test_skills_list_succeeds_with_no_api_key_and_no_key_file(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """``fredq skills list`` works with FRED_API_KEY unset and no ~/.fredq/api_key.

    Dispatch happens before any FredClient construction / auth resolution,
    so the skills group must never require an API key.
    """

    home, _cwd = home_and_cwd
    assert not (home / ".fredq" / "api_key").exists()
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(["skills", "list"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert not stderr.getvalue()
    assert stdout.getvalue()


def test_skills_install_succeeds_with_no_api_key_and_no_key_file(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """``fredq skills install`` also works with no API key configured."""

    home, _cwd = home_and_cwd
    assert not (home / ".fredq" / "api_key").exists()
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        ["skills", "install", "--agent", "claude"], stdout=stdout, stderr=stderr
    )

    assert exit_code == 0
    assert not stderr.getvalue()


# ---------------------------------------------------------------------------
# Help surface
# ---------------------------------------------------------------------------


def test_skills_group_appears_in_top_level_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Top-level help lists the skills command group."""

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "skills" in captured.out


def test_skills_bare_group_prints_group_help_and_exits_2(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """`fredq skills` alone (no subcommand) prints skills group help; exit 2."""

    del home_and_cwd
    stdout = StringIO()

    exit_code = main(["skills"], stdout=stdout)

    assert exit_code == ARGPARSE_ERROR
    out = stdout.getvalue()
    assert "install" in out
    assert "uninstall" in out
    assert "list" in out


def test_skills_group_help_lists_pinned_subcommand_summaries(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Skills --help lists the three pinned per-AGENTS.md summary strings."""

    with pytest.raises(SystemExit) as exc_info:
        main(["skills", "--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Install the fredq agent skill into agent skill directories." in captured.out
    assert "Remove the fredq agent skill from agent skill directories." in captured.out
    assert "Show where the fredq agent skill is installed." in captured.out


def test_skills_install_help_documents_targeting_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Skills install --help documents --agent/--to/--project."""

    with pytest.raises(SystemExit) as exc_info:
        main(["skills", "install", "--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "--agent" in captured.out
    assert "--to" in captured.out
    assert "--project" in captured.out


def test_skills_uninstall_help_documents_targeting_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Skills uninstall --help documents --agent/--to/--project."""

    with pytest.raises(SystemExit) as exc_info:
        main(["skills", "uninstall", "--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "--agent" in captured.out
    assert "--to" in captured.out
    assert "--project" in captured.out


def test_skills_list_help_takes_no_targeting_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Skills list --help documents no targeting flags (list walks everything)."""

    with pytest.raises(SystemExit) as exc_info:
        main(["skills", "list", "--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "--agent" not in captured.out
    assert "--to" not in captured.out
