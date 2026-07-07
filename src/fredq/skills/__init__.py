"""Agent Skills packaging for fredq: skill content plus its installer.

``content/`` under this package holds the fredq Agent Skill: a
standards-shaped ``SKILL.md`` router plus domain docs (observations,
revisions, catalog, dataframes) that teach an LLM agent this library's
Python surface and CLI. The files are plain package data — hatchling
ships everything under ``src/fredq`` in the wheel — and are meant to be
read, not imported; nothing in this package requires fredq's other
runtime dependencies (httpx2, polars, pydantic) to be importable.
``fredq.skills._install`` copies that content tree into named agent
skill directories (see the ``fredq skills`` CLI group).
"""

from __future__ import annotations

from fredq.skills._install import (
    AGENT_TARGETS,
    TargetReport,
    install,
    resolve_roots,
    status,
    uninstall,
)

__all__ = [
    "AGENT_TARGETS",
    "TargetReport",
    "install",
    "resolve_roots",
    "status",
    "uninstall",
]
