"""Copy-only installer for the fredq agent skill (spec: agent-skills design)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import regex

from fredq import __version__

SKILL_DIR_NAME = "fredq"
CONTENT_DIR = Path(__file__).parent / "content"

AGENT_TARGETS: dict[str, tuple[str, str]] = {
    # name -> (user-level root relative to home, project-level root relative
    # to cwd). Each pair is the agent's DOCUMENTED skill-discovery location,
    # not a name-derived guess: Codex discovers only `.agents/skills` roots
    # (developers.openai.com/codex/skills), and Copilot's project-level
    # discovery is `.github/skills` (its user level is `~/.copilot/skills`;
    # a project `.copilot/skills` is not scanned — docs.github.com Copilot
    # CLI "add skills"). Verified 2026-07-06 against agent documentation,
    # see yoghurt ab12d4f.
    "claude": (".claude/skills", ".claude/skills"),
    "codex": (".agents/skills", ".agents/skills"),
    "copilot": (".copilot/skills", ".github/skills"),
    "cursor": (".cursor/skills", ".cursor/skills"),
    "gemini": (".gemini/skills", ".gemini/skills"),
    "pi": (".pi/agent/skills", ".pi/skills"),
}


@dataclass(frozen=True)
class TargetReport:
    """Outcome of one install/uninstall/status operation on one skills root."""

    root: Path
    action: str  # installed | removed | absent | refused | stale | current
    detail: str = ""


def resolve_roots(agents: list[str], *, project: bool, to: Path | None) -> list[Path]:
    """Turn --agent names (+ optional --to) into skills-root paths.

    Returns:
        list[Path]: One resolved skills root per named agent, plus ``to``
        appended if given.

    Raises:
        ValueError: For an unrecognized agent name.
    """
    roots: list[Path] = []
    for name in agents:
        try:
            user_rel, project_rel = AGENT_TARGETS[name]
        except KeyError:
            known = ", ".join(sorted(AGENT_TARGETS))
            message = f"unknown agent {name!r} (known: {known})"
            raise ValueError(message) from None
        base = Path.cwd() / project_rel if project else Path.home() / user_rel
        roots.append(base)
    if to is not None:
        roots.append(to)
    return roots


def _installed_name(skill_dir: Path) -> str | None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    match = regex.search(
        r"^name:\s*(\S+)",
        skill_md.read_text(encoding="utf-8"),
        flags=regex.MULTILINE,
    )
    return match.group(1) if match else None


def _installed_version(skill_dir: Path) -> str | None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    match = regex.search(
        r"^\s+version:\s*(\S+)",
        skill_md.read_text(encoding="utf-8"),
        flags=regex.MULTILINE,
    )
    return match.group(1) if match else None


def _stamp_version(skill_md: Path) -> None:
    text = skill_md.read_text(encoding="utf-8")
    stamped = text.replace(
        "\n---\n", f"\nmetadata:\n  version: {__version__}\n---\n", 1
    )
    skill_md.write_text(stamped, encoding="utf-8", newline="\n")


def install(roots: list[Path]) -> list[TargetReport]:
    """Copy the skill into each root, replacing only installs we own.

    Returns:
        list[TargetReport]: One report per requested root.
    """
    reports: list[TargetReport] = []
    for root in roots:
        skill_dir = root / SKILL_DIR_NAME
        if skill_dir.exists() and _installed_name(skill_dir) != SKILL_DIR_NAME:
            reports.append(
                TargetReport(
                    root, "refused", "existing directory is not the fredq skill"
                )
            )
            continue
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        shutil.copytree(CONTENT_DIR, skill_dir)
        _stamp_version(skill_dir / "SKILL.md")
        reports.append(TargetReport(root, "installed", __version__))
    return reports


def uninstall(roots: list[Path]) -> list[TargetReport]:
    """Remove the skill from each root; only dirs we own.

    Returns:
        list[TargetReport]: One report per requested root.
    """
    reports: list[TargetReport] = []
    for root in roots:
        skill_dir = root / SKILL_DIR_NAME
        if not skill_dir.exists():
            reports.append(TargetReport(root, "absent"))
        elif _installed_name(skill_dir) != SKILL_DIR_NAME:
            reports.append(
                TargetReport(
                    root, "refused", "existing directory is not the fredq skill"
                )
            )
        else:
            shutil.rmtree(skill_dir)
            reports.append(TargetReport(root, "removed"))
    return reports


def status() -> list[TargetReport]:
    """Walk every named target x {user, project} and report install state.

    Returns:
        list[TargetReport]: One report per (agent, scope) pair.
    """
    reports: list[TargetReport] = []
    for name in sorted(AGENT_TARGETS):
        user_rel, project_rel = AGENT_TARGETS[name]
        for scope, base in (
            ("user", Path.home() / user_rel),
            ("project", Path.cwd() / project_rel),
        ):
            skill_dir = base / SKILL_DIR_NAME
            label = f"{name} {scope}"
            if _installed_name(skill_dir) != SKILL_DIR_NAME:
                reports.append(TargetReport(base, "absent", label))
                continue
            version = _installed_version(skill_dir) or "unknown"
            action = "current" if version == __version__ else "stale"
            reports.append(TargetReport(base, action, f"{label} {version}"))
    return reports
