"""Agent Skills packaging for fredq.

``content/`` under this package holds the fredq Agent Skill: a
standards-shaped ``SKILL.md`` router plus domain docs (observations,
revisions, catalog, dataframes) that teach an LLM agent this library's
Python surface and CLI. The files are plain package data — hatchling
ships everything under ``src/fredq`` in the wheel — and are meant to be
read, not imported; nothing in this package requires fredq's other
runtime dependencies (httpx2, polars, pydantic) to be importable.
"""

from __future__ import annotations
