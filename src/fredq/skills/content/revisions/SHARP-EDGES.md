# Sharp edges: revisions

## Revision cadence is series-specific, not a library constant

**Severity:** medium

How much (and how often) a series revises varies enormously by series,
and fredq applies no smoothing or normalization across that variance.

Wrong way: assuming every series carries the same amount of revision
risk, or hard-coding one "look back N vintages" window and applying it to
every series in a pipeline.

Right way: check `Series(id).vintage_dates()` for the series you actually
depend on before assuming a backtest is revision-safe. Retail sales
(`RSAFS`) and industrial production (`INDPRO`) revise heavily and often;
nonfarm payrolls (`PAYEMS`) revises roughly its prior two months on every
monthly release; GDP-family series revise in a handful of scheduled
estimate rounds rather than continuously; the unemployment rate
(`UNRATE`) and CPI (`CPIAUCSL`) mostly hold steady between their own
annual (seasonal-adjustment) revision cycles.

Evidence: 2026-07-07, live-measured (vintage-date histories compared
across RSAFS, INDPRO, PAYEMS, GDP, UNRATE, and CPIAUCSL).

## An observation's `date` does not tell you when it became public

**Severity:** medium

The observation `date` is the period the value describes, not the day
FRED first published it — the two can be close together, not a month or
more apart, for some series.

Wrong way: assuming an observation dated the 1st of month M was not
knowable until month M closed, and structuring a backtest so that a
signal is only used starting the following month.

Right way: for employment-situation-cadence series like `UNRATE`, the
reading for month M is typically public within the first days of month
M+1 — check the actual publication date via the series' own release
(`Series.release()` then `Release(id).dates()`, or `release_calendar()`)
rather than inferring it from the observation `date`.

Evidence: 2026-07-07, live-measured.
