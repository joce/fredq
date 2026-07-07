"""Tests for the copy-only agent-skill installer (spec: agent-skills design).

All filesystem operations run against ``tmp_path``: ``pathlib.Path.home`` is
monkeypatched directly, and the CWD is redirected via ``monkeypatch.chdir``
(rather than patching ``Path.cwd``, which ``chdir`` makes unnecessary and
which is fragile to patch correctly across platforms).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import regex

import fredq
from fredq.skills import (
    AGENT_TARGETS,
    TargetReport,
    install,
    resolve_roots,
    status,
    uninstall,
)

CONTENT = Path(__file__).parent.parent / "src" / "fredq" / "skills" / "content"
DOMAIN_FILES = [
    "catalog/README.md",
    "catalog/SHARP-EDGES.md",
    "dataframes/README.md",
    "dataframes/SHARP-EDGES.md",
    "observations/README.md",
    "observations/SHARP-EDGES.md",
    "revisions/README.md",
    "revisions/SHARP-EDGES.md",
]


@pytest.fixture
def home_and_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Point Path.home()/Path.cwd() at isolated tmp_path subdirectories.

    Returns:
        tuple[Path, Path]: The fake (home, cwd) directories.
    """

    home = tmp_path / "home"
    cwd = tmp_path / "project"
    home.mkdir()
    cwd.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(cwd)
    return home, cwd


def _write_foreign_skill(skill_dir: Path, *, name: str = "other") -> None:
    """Write a SKILL.md with a different frontmatter name, to test ownership checks."""

    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: not ours\n---\nbody\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# resolve_roots
# ---------------------------------------------------------------------------


def test_resolve_roots_user_level_maps_every_named_agent(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """Every named agent maps to its exact user-level root."""

    home, _cwd = home_and_cwd
    expected = {
        "claude": home / ".claude" / "skills",
        "codex": home / ".agents" / "skills",
        "copilot": home / ".copilot" / "skills",
        "cursor": home / ".cursor" / "skills",
        "gemini": home / ".gemini" / "skills",
        "pi": home / ".pi" / "agent" / "skills",
    }
    for agent, root in expected.items():
        assert resolve_roots([agent], project=False, to=None) == [root]


def test_resolve_roots_project_level_maps_every_named_agent(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """project=True maps every named agent to its project-level root (CWD-relative)."""

    _home, cwd = home_and_cwd
    expected = {
        "claude": cwd / ".claude" / "skills",
        "codex": cwd / ".agents" / "skills",
        "copilot": cwd / ".github" / "skills",
        "cursor": cwd / ".cursor" / "skills",
        "gemini": cwd / ".gemini" / "skills",
        "pi": cwd / ".pi" / "skills",
    }
    for agent, root in expected.items():
        assert resolve_roots([agent], project=True, to=None) == [root]


def test_resolve_roots_pi_asymmetry_is_pinned_explicitly(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """Pi's user root nests under agent/; its project root does not."""

    home, cwd = home_and_cwd
    assert resolve_roots(["pi"], project=False, to=None) == [
        home / ".pi" / "agent" / "skills"
    ]
    assert resolve_roots(["pi"], project=True, to=None) == [cwd / ".pi" / "skills"]


def test_resolve_roots_codex_and_copilot_documented_paths_are_pinned(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """Codex and Copilot map to their DOCUMENTED discovery roots.

    Codex discovers only ``.agents/skills`` roots (user and project); a
    ``.codex/skills`` install would never be found. Copilot's user root is
    ``~/.copilot/skills`` but its project-level discovery is
    ``.github/skills`` — a project ``.copilot/skills`` is not scanned.
    Verified against both agents' documentation 2026-07-06 (yoghurt fix
    ab12d4f, PR #25 review finding).
    """

    home, cwd = home_and_cwd
    assert resolve_roots(["codex"], project=False, to=None) == [
        home / ".agents" / "skills"
    ]
    assert resolve_roots(["codex"], project=True, to=None) == [
        cwd / ".agents" / "skills"
    ]
    assert resolve_roots(["copilot"], project=False, to=None) == [
        home / ".copilot" / "skills"
    ]
    assert resolve_roots(["copilot"], project=True, to=None) == [
        cwd / ".github" / "skills"
    ]


def test_resolve_roots_unknown_agent_raises_value_error_naming_offender_and_known(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """An unknown agent raises ValueError naming the offender and known agents."""

    del home_and_cwd
    with pytest.raises(ValueError, match="bogus") as exc_info:
        resolve_roots(["bogus"], project=False, to=None)
    message = str(exc_info.value)
    for agent in AGENT_TARGETS:
        assert agent in message


def test_resolve_roots_to_appends_extra_root(
    home_and_cwd: tuple[Path, Path], tmp_path: Path
) -> None:
    """to= appends the extra root after the named-agent roots."""

    home, _cwd = home_and_cwd
    extra = tmp_path / "custom-root"
    roots = resolve_roots(["claude"], project=False, to=extra)
    assert roots == [home / ".claude" / "skills", extra]


def test_resolve_roots_empty_agents_and_no_to_returns_empty_list(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """Empty agents + to=None returns []; the CLI enforces at-least-one, not us."""

    del home_and_cwd
    assert resolve_roots([], project=False, to=None) == []


def test_resolve_roots_multiple_agents_in_order(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """Multiple agent names resolve to roots in the same order they were given."""

    home, _cwd = home_and_cwd
    roots = resolve_roots(["claude", "codex"], project=False, to=None)
    assert roots == [home / ".claude" / "skills", home / ".agents" / "skills"]


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


def test_install_creates_missing_root_with_parents(tmp_path: Path) -> None:
    """install() creates a missing root, including missing parent directories."""

    root = tmp_path / "does" / "not" / "exist" / "yet"
    assert not root.exists()

    reports = install([root])

    assert root.is_dir()
    assert reports == [TargetReport(root, "installed", fredq.__version__)]


def test_install_copies_the_full_content_tree(tmp_path: Path) -> None:
    """install() copies SKILL.md and all 8 domain files into the target root."""

    root = tmp_path / "root"

    install([root])

    installed = root / "fredq"
    assert (installed / "SKILL.md").is_file()
    for rel in DOMAIN_FILES:
        assert (installed / rel).is_file(), f"missing {rel}"


def test_install_stamps_version_inside_frontmatter_source_stays_unstamped(
    tmp_path: Path,
) -> None:
    """install() stamps metadata.version inside the frontmatter block only."""

    root = tmp_path / "root"

    install([root])

    installed_text = (root / "fredq" / "SKILL.md").read_text(encoding="utf-8")
    match = regex.match(r"---\n(.*?)\n---\n", installed_text, flags=regex.DOTALL)
    assert match, "installed SKILL.md must still open with frontmatter"
    frontmatter = match.group(1)
    assert f"metadata:\n  version: {fredq.__version__}" in frontmatter

    # The stamp must land INSIDE the frontmatter block, i.e. before the
    # closing '---' -- not appended after it as body content.
    closing_index = installed_text.index("\n---\n", 4)
    stamp_index = installed_text.index("metadata:")
    assert stamp_index < closing_index

    source_text = (CONTENT / "SKILL.md").read_text(encoding="utf-8")
    assert "metadata:" not in source_text
    assert "version:" not in source_text


def test_install_reinstall_over_prior_install_succeeds_and_drops_stale_extra(
    tmp_path: Path,
) -> None:
    """Reinstalling over a prior install succeeds and removes old extra files."""

    root = tmp_path / "root"
    install([root])

    stray = root / "fredq" / "leftover-from-old-version.md"
    stray.write_text("stale", encoding="utf-8")
    assert stray.exists()

    reports = install([root])

    assert reports == [TargetReport(root, "installed", fredq.__version__)]
    assert not stray.exists()
    assert (root / "fredq" / "SKILL.md").is_file()


def test_install_refuses_foreign_dir_with_mismatched_skill_md_name(
    tmp_path: Path,
) -> None:
    """A foreign dir with a SKILL.md naming a different skill is refused, unremoved."""

    root = tmp_path / "root"
    _write_foreign_skill(root / "fredq", name="other")

    reports = install([root])

    assert len(reports) == 1
    assert reports[0].root == root
    assert reports[0].action == "refused"
    # Refused, not deleted.
    assert (
        (root / "fredq" / "SKILL.md")
        .read_text(encoding="utf-8")
        .startswith("---\nname: other")
    )


def test_install_refuses_foreign_dir_with_no_skill_md(tmp_path: Path) -> None:
    """A foreign dir with no SKILL.md at all is refused, not deleted."""

    root = tmp_path / "root"
    foreign_dir = root / "fredq"
    foreign_dir.mkdir(parents=True)
    (foreign_dir / "some-other-file.txt").write_text("hello", encoding="utf-8")

    reports = install([root])

    assert len(reports) == 1
    assert reports[0].action == "refused"
    # Refused, not deleted.
    assert (foreign_dir / "some-other-file.txt").is_file()
    assert not (foreign_dir / "SKILL.md").exists()


def test_install_refused_target_does_not_block_other_targets(tmp_path: Path) -> None:
    """A refused target is reported but other targets still install successfully."""

    foreign_root = tmp_path / "foreign"
    good_root = tmp_path / "good"
    _write_foreign_skill(foreign_root / "fredq", name="other")

    reports = install([foreign_root, good_root])

    by_root = {report.root: report for report in reports}
    assert by_root[foreign_root].action == "refused"
    assert by_root[good_root].action == "installed"
    assert (good_root / "fredq" / "SKILL.md").is_file()
    # Foreign dir at the refused target remains untouched.
    assert (
        (foreign_root / "fredq" / "SKILL.md")
        .read_text(encoding="utf-8")
        .startswith("---\nname: other")
    )


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------


def test_uninstall_removes_owned_install(tmp_path: Path) -> None:
    """uninstall() removes an install it owns."""

    root = tmp_path / "root"
    install([root])
    assert (root / "fredq").exists()

    reports = uninstall([root])

    assert reports == [TargetReport(root, "removed")]
    assert not (root / "fredq").exists()


def test_uninstall_reports_absent_when_missing(tmp_path: Path) -> None:
    """uninstall() reports absent when there is nothing installed at the root."""

    root = tmp_path / "root"

    reports = uninstall([root])

    assert reports == [TargetReport(root, "absent")]


def test_uninstall_refuses_foreign_dir_which_remains_present(tmp_path: Path) -> None:
    """uninstall() refuses a foreign dir, which remains present afterward."""

    root = tmp_path / "root"
    _write_foreign_skill(root / "fredq", name="other")

    reports = uninstall([root])

    assert len(reports) == 1
    assert reports[0].action == "refused"
    assert (root / "fredq" / "SKILL.md").exists()


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_reports_absent_for_empty_machine(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """status() reports absent for every named target x scope on an empty machine."""

    del home_and_cwd
    reports = status()

    assert reports, "status() should cover every named target x scope"
    assert all(report.action == "absent" for report in reports)
    # Covers user AND project scopes for every named agent.
    assert len(reports) == len(AGENT_TARGETS) * 2


def test_status_reports_current_after_install(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """status() reports current for a target just installed at the running version."""

    home, _cwd = home_and_cwd
    claude_user_root = home / ".claude" / "skills"
    install([claude_user_root])

    reports = status()

    matching = [
        report
        for report in reports
        if report.root == claude_user_root and report.action != "absent"
    ]
    assert len(matching) == 1
    assert matching[0].action == "current"
    assert fredq.__version__ in matching[0].detail


def test_status_reports_stale_after_doctoring_stamped_version(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """status() reports stale after the stamped version is edited to something else."""

    home, _cwd = home_and_cwd
    claude_user_root = home / ".claude" / "skills"
    install([claude_user_root])

    skill_md = claude_user_root / "fredq" / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    doctored = text.replace(f"version: {fredq.__version__}", "version: 0.0.0-doctored")
    assert doctored != text
    skill_md.write_text(doctored, encoding="utf-8", newline="\n")

    reports = status()

    matching = [report for report in reports if report.root == claude_user_root]
    assert len(matching) == 1
    assert matching[0].action == "stale"
    assert "0.0.0-doctored" in matching[0].detail


def test_status_covers_user_and_project_scopes_for_project_install(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """status() finds a project-scope install as well as user-scope ones."""

    _home, cwd = home_and_cwd
    codex_project_root = cwd / ".agents" / "skills"
    install([codex_project_root])

    reports = status()

    installed = [report for report in reports if report.action != "absent"]
    assert len(installed) == 1
    assert installed[0].root == codex_project_root
    assert installed[0].action == "current"


def test_uninstall_refused_target_does_not_block_other_targets(
    tmp_path: Path,
) -> None:
    """uninstall() keeps processing targets after refusing a foreign dir."""

    foreign_root = tmp_path / "foreign"
    owned_root = tmp_path / "owned"
    _write_foreign_skill(foreign_root / "fredq", name="other")
    install([owned_root])

    reports = uninstall([foreign_root, owned_root])

    assert [report.action for report in reports] == ["refused", "removed"]
    assert (foreign_root / "fredq" / "SKILL.md").exists()
    assert not (owned_root / "fredq").exists()


def test_status_does_not_track_to_locations(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """Installs at --to roots stay invisible to status() (spec: not tracked)."""

    home, _cwd = home_and_cwd
    to_root = home / "custom-skills"
    install(resolve_roots([], project=False, to=to_root))
    assert (to_root / "fredq" / "SKILL.md").exists()

    reports = status()

    assert all(report.action == "absent" for report in reports)
    assert to_root not in {report.root for report in reports}


def test_status_reports_foreign_dir_as_absent_by_design(
    home_and_cwd: tuple[Path, Path],
) -> None:
    """A foreign dir at a named target reads as absent in status().

    Deliberate: status answers "is the fredq skill installed here?" — for
    a foreign directory the honest answer is no. The naming collision
    surfaces as a refusal at install/uninstall time, when it is actionable
    (pinned by the refusal tests above).
    """

    home, _cwd = home_and_cwd
    _write_foreign_skill(home / ".gemini" / "skills" / "fredq", name="other")

    reports = status()

    assert all(report.action == "absent" for report in reports)
