"""Run with uv run python examples/workflows.py {asof,catalog,compare,export}."""

# Standalone executable recipe, not an installed package.
# ruff: file-ignore[implicit-namespace-package, print]

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

import fredq

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fredq.frames import Observations
    from fredq.models import SeriesInfo


def as_of_snapshot() -> Observations:
    """Fetch 2000 unemployment as known on one date, without later revisions.

    Returns:
        Observations: A single-date ALFRED snapshot.
    """
    return fredq.Series("UNRATE").observations(
        observation_start="2000-01-01",
        observation_end="2000-12-31",
        realtime_start="2001-01-01",
        realtime_end="2001-01-01",
    )


def catalog(page_size: int = 20) -> Iterator[SeriesInfo]:
    """Walk category 125 in stable ID order, explicitly requesting each page.

    Yields:
        SeriesInfo: Each series returned by FRED. A changing upstream catalog
        can still change between requests; this is not a database snapshot.
    """
    offset = 0
    while True:
        page = fredq.Category(125).series(
            limit=page_size, offset=offset, order_by="series_id", sort_order="asc"
        )
        yield from page.seriess
        offset += len(page.seriess)
        if not page.seriess or offset >= page.count:
            return


def monthly_comparison() -> pl.DataFrame:
    """Align monthly average yields with CPI year-over-year percent changes.

    Returns:
        pl.DataFrame: Both series, retaining dates missing from either side.
    """
    ten_year = (
        fredq.Series("DGS10")
        .observations(
            observation_start="2024-01-01",
            observation_end="2024-12-31",
            frequency="m",
            aggregation_method="avg",
        )
        .to_polars()
        .select("date", pl.col("value").alias("ten_year_yield"))
    )
    cpi = (
        fredq.Series("CPIAUCSL")
        .observations(
            observation_start="2024-01-01",
            observation_end="2024-12-31",
            units="pc1",
            frequency="m",
            aggregation_method="avg",
        )
        .to_polars()
        .select("date", pl.col("value").alias("cpi_yoy"))
    )
    return ten_year.join(cpi, on="date", how="full", coalesce=True).sort("date")


def export_roundtrip(path: Path) -> tuple[pl.DataFrame, dict[str, str]]:
    """Save observations and reload their table and provenance with Polars.

    Returns:
        tuple[pl.DataFrame, dict[str, str]]: Reloaded rows and schema metadata.
    """
    observations = fredq.Series("DGS10").observations(
        observation_start="2024-01-01", observation_end="2024-12-31"
    )
    observations.save_parquet(path)
    return pl.read_parquet(path), pl.read_parquet_metadata(path)


def main() -> None:
    """Run one recipe using the configured FRED API key."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", choices=("asof", "catalog", "compare", "export"))
    parser.add_argument("--out", type=Path, default=Path("observations.parquet"))
    args = parser.parse_args()
    if args.recipe == "asof":
        print(as_of_snapshot().to_polars())
    elif args.recipe == "catalog":
        for series in catalog():
            print(series.id, series.title)
    elif args.recipe == "compare":
        print(monthly_comparison())
    else:
        table, metadata = export_roundtrip(args.out)
        print(table)
        print(metadata)


if __name__ == "__main__":
    main()
