# Revisions

ALFRED, the archival companion to FRED: the list of dates a series was
revised on, point-in-time ("as of a past date") observations, and how to
reason about revision size and cadence before treating fredq's numbers as
ground truth for a backtest.

## Vintage dates

```python
dates = fredq.Series("GNPCA").vintage_dates()
```

`vintage_dates()` returns a `VintageDatesResult`: `.vintage_dates` is the
full list of `datetime.date`s FRED published a revision on, `.count` is
how many. Real GNP (`GNPCA`) has been revised well over a hundred times
since ALFRED's archive begins.

CLI equivalent:

```bash
fredq series vintage-dates GNPCA
```

## Point-in-time observations

Pass `realtime_start`/`realtime_end` to `observations()` to see the data
exactly as FRED would have answered on a past date. When a revision
happened inside the window you asked for, the same observation `date` can
come back more than once — once per realtime span:

```python
asof = fredq.Series("UNRATE").observations(
    realtime_start="2001-01-01",
    realtime_end="2001-12-31",
    observation_start="2000-01-01",
    observation_end="2000-12-31",
)
```

Querying UNRATE's realtime year 2001 for calendar year 2000 returns 14
rows for 12 months: March and April 2000 were each revised once inside
that window, so both the pre- and post-revision value show up as separate
rows with adjoining `realtime_start`/`realtime_end` spans.

CLI equivalent:

```bash
fredq series observations UNRATE --realtime-start 2001-01-01 --realtime-end 2001-12-31 --observation-start 2000-01-01 --observation-end 2000-12-31
```

## Revision cadence is series-specific

Don't assume every series revises the same way. GDP-family estimates go
through a handful of scheduled estimate rounds (advance, second, third)
rather than continuous smoothing:

```python
gdp = fredq.Series("GDP").observations(
    observation_start="2015-01-01", observation_end="2024-12-31"
)
```

See [SHARP-EDGES.md](SHARP-EDGES.md) for the measured cadence differences
across series like RSAFS, INDPRO, PAYEMS, GDP, UNRATE, and CPIAUCSL, and
for a look-ahead caveat worth knowing before backtesting on observation
dates alone.

CLI equivalent:

```bash
fredq series observations GDP --observation-start 2015-01-01 --observation-end 2024-12-31
```

## Parameters

Full parameter lists, defaults, and examples live in `--help`, not here:

```bash
fredq series vintage-dates --help
fredq series observations --help
```

See [SHARP-EDGES.md](SHARP-EDGES.md) for proven pitfalls in this domain.
