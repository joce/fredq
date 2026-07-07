# Observations

Fetching the actual data values for a FRED series: request windows, units
transforms, frequency aggregation, and how FRED spells "no value here."

## Fetching observations

```python
obs = fredq.Series("GNPCA").observations()
```

`observations()` returns an `Observations` frame (a polars-backed `Frame`
subclass): rows via `.to_polars()`/`.to_pandas()`/`.to_arrow()`/`.to_dicts()`,
plus the full response envelope as typed `.meta`. Omitted
`observation_start`/`observation_end` default to a series' entire history.

CLI equivalent (raw JSON to stdout):

```bash
fredq series observations GNPCA
```

## Units transforms

FRED can transform the raw values server-side instead of you doing it
client-side — percent change, log, year-over-year, and more:

```python
pch = fredq.Series("CPIAUCSL").observations(
    units="pch", observation_start="2020-01-01", observation_end="2022-12-31"
)
```

`units` mirrors FRED's wire codes exactly (`"lin"` default, `"pch"`,
`"log"`, `"chg"`, ...) — see `--help` for the full set.

CLI equivalent:

```bash
fredq series observations CPIAUCSL --units pch --observation-start 2020-01-01 --observation-end 2022-12-31
```

## Frequency aggregation

`frequency` resamples the series to a coarser cadence server-side (e.g.
FRED's own daily 10-year yield, aggregated to monthly):

```python
monthly = fredq.Series("DGS10").observations(
    frequency="m", observation_start="2023-01-01", observation_end="2024-12-31"
)
```

CLI equivalent:

```bash
fredq series observations DGS10 --frequency m --observation-start 2023-01-01 --observation-end 2024-12-31
```

## Missing values

```python
obs = fredq.Series("DEXCAUS").observations(
    observation_start="2023-12-20", observation_end="2024-01-05"
)
```

Not every calendar day in the window has a value — bank holidays and
market closures come back as a row whose `value` is `None`, not `0.0` and
not `NaN`. See [SHARP-EDGES.md](SHARP-EDGES.md) for how fredq parses
FRED's missing-value sentinel.

CLI equivalent:

```bash
fredq series observations DEXCAUS --observation-start 2023-12-20 --observation-end 2024-01-05
```

## Parameters

Full parameter lists, defaults, and examples live in `--help`, not here:

```bash
fredq series observations --help
```

See [SHARP-EDGES.md](SHARP-EDGES.md) for proven pitfalls in this domain.
