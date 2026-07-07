# Dataframes

The polars-backed `Frame`/`Observations` vocabulary that
`Series.observations()` returns: conversions, the `pandas` extra, Parquet
export, and joining series that don't share a frequency.

## Conversion vocabulary

```python
obs = fredq.Series("TWEXB").observations()
obs.to_polars()
obs.to_pandas()  # requires: pip install fredq[pandas]
obs.to_arrow()  # requires: pip install fredq[pandas]
obs.to_dicts()
obs.save_parquet("twexb.parquet")
```

`Observations` is a `Frame`: five conversions, one vocabulary, no
reshaping in between. `to_pandas()`/`to_arrow()` raise `ImportError` with
an actionable install message until `fredq[pandas]` is installed; the
other three work out of the box.

CLI equivalent (writes a typed Parquet file instead of stdout JSON,
`series observations` only):

```bash
fredq series observations TWEXB --format parquet --out twexb.parquet
```

## The response envelope

Every field FRED sent alongside the observation rows survives as `.meta`,
not just the rows themselves:

```python
obs = fredq.Series("DGS10").observations(
    observation_start="2024-01-01", observation_end="2024-12-31"
)
meta = obs.meta
```

`meta` is an `ObservationsMeta`: the requested/echoed `units`, the
realtime window FRED answered with, `count`/`limit`/`offset`, and
`observation_start`/`observation_end` as typed `date`s — everything
you'd otherwise have to re-derive from the request you sent.

## Joining series of different frequencies

Two `Observations` frames are ordinary polars `DataFrame`s once you call
`.to_polars()` — join them like any other table:

```python
ten_year = fredq.Series("DGS10").observations(frequency="m").to_polars()
cpi_pch = fredq.Series("CPIAUCSL").observations(units="pch").to_polars()
combined = ten_year.join(cpi_pch, on="date", how="full", suffix="_cpi")
```

Use `how="full"` (or `"left"` anchored on the more-current frame), not
`"inner"` — see [SHARP-EDGES.md](SHARP-EDGES.md).

## Parameters

Full parameter lists, defaults, and examples live in `--help`, not here:

```bash
fredq series observations --help
```

See [SHARP-EDGES.md](SHARP-EDGES.md) for proven pitfalls in this domain.
