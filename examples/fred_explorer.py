"""FRED explorer — an interactive marimo notebook over the fredq library.

Run (from the repo root; fredq resolves from the project venv, marimo and
altair are ephemeral overlays):

    uv run --with marimo --with altair marimo edit examples/fred_explorer.py

Panels: a series explorer (units transforms, frequency aggregation, typed
errors in the UI), multi-series comparison with correlations, catalog
search, ALFRED vintage revisions, and mortgage-vs-Treasury spread analysis.
"""

import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium")


@app.cell
def _():
    import functools

    import marimo as mo
    import polars as pl

    import fredq

    return fredq, functools, mo, pl


@app.cell
def _(mo):
    mo.md("""
    # FRED explorer (fredq dogfood)

    Everything below flows through the typed `fredq` library: observations
    as polars frames, catalog searches as corpus-gated models, ALFRED
    vintages via realtime windows, and `FredApiError` surfaced in the UI.
    """)
    return


@app.cell
def _(fredq, functools):
    @functools.lru_cache(maxsize=64)
    def fetch_observations(
        series_id: str,
        start: str | None,
        end: str | None,
        units: str | None,
        frequency: str | None,
    ):
        """One cached fredq call per unique control combination."""
        return fredq.Series(series_id).observations(
            observation_start=start,
            observation_end=end,
            units=units,
            frequency=frequency,
        )

    @functools.lru_cache(maxsize=16)
    def fetch_info(series_id: str):
        return fredq.Series(series_id).info()

    @functools.lru_cache(maxsize=16)
    def fetch_vintages(series_id: str):
        return fredq.Series(series_id).vintage_dates(
            limit=24, sort_order="desc"
        )

    @functools.lru_cache(maxsize=32)
    def fetch_vintage_observations(series_id: str, vintage: str, start: str):
        return fredq.Series(series_id).observations(
            realtime_start=vintage,
            realtime_end=vintage,
            observation_start=start,
        )

    return (
        fetch_info,
        fetch_observations,
        fetch_vintage_observations,
        fetch_vintages,
    )


@app.cell
def _(mo):
    UNITS = ["lin", "chg", "ch1", "pch", "pc1", "pca", "cch", "cca", "log"]
    FREQS = ["native", "d", "w", "bw", "m", "q", "sa", "a"]

    explorer_form = (
        mo.md(
            """
            **Series** {series_id} &nbsp; **From** {start} **To** {end}

            **Units transform** {units} &nbsp; **Frequency** {frequency}
            """
        )
        .batch(
            series_id=mo.ui.text(value="DGS10", label=""),
            start=mo.ui.date(value="2015-01-01", label=""),
            end=mo.ui.date(value="2026-07-01", label=""),
            units=mo.ui.dropdown(options=UNITS, value="lin", label=""),
            frequency=mo.ui.dropdown(options=FREQS, value="native", label=""),
        )
        .form(submit_button_label="Fetch")
    )
    explorer_form
    return (explorer_form,)


@app.cell
def _(explorer_form, fetch_info, fetch_observations, fredq, mo):
    _defaults = {
        "series_id": "DGS10",
        "start": "2015-01-01",
        "end": "2026-07-01",
        "units": "lin",
        "frequency": "native",
    }
    _v = explorer_form.value or _defaults

    explorer_error = None
    obs = None
    info = None
    try:
        info = fetch_info(str(_v["series_id"]).strip().upper())
        obs = fetch_observations(
            str(_v["series_id"]).strip().upper(),
            str(_v["start"]),
            str(_v["end"]),
            None if _v["units"] == "lin" else str(_v["units"]),
            None if _v["frequency"] == "native" else str(_v["frequency"]),
        )
    except fredq.FredApiError as exc:
        explorer_error = mo.callout(
            mo.md(
                f"**FRED rejected the request** (HTTP {exc.status_code}, "
                f"error_code {exc.error_code}): {exc.error_message}"
            ),
            kind="danger",
        )
    explorer_error
    return info, obs


@app.cell
def _(info, mo, obs):
    _out = None
    if obs is not None and info is not None:
        _missing = obs.df["value"].null_count()
        _out = mo.vstack(
            [
                mo.md(
                    f"### {info.title}\n"
                    f"*{info.units} — {info.frequency}, "
                    f"{info.seasonal_adjustment_short}; "
                    f"last updated {info.last_updated:%Y-%m-%d %H:%M}*"
                ),
                mo.hstack(
                    [
                        mo.stat(value=str(obs.df.height), label="rows"),
                        mo.stat(value=str(_missing), label="missing (null)"),
                        mo.stat(value=obs.meta.units, label="transform"),
                        mo.stat(
                            value=f"{obs.meta.realtime_start}",
                            label="realtime",
                        ),
                    ]
                ),
                obs.df.drop_nulls("value").plot.line(x="date", y="value"),
                mo.ui.table(obs.df, page_size=10),
            ]
        )
    _out
    return


@app.cell
def _(mo):
    mo.md("""
    ## Compare series (joined on date, min-max normalized)
    """)
    return


@app.cell
def _(mo):
    compare_select = mo.ui.multiselect(
        options=["DGS10", "UNRATE", "CPIAUCSL", "FEDFUNDS", "MORTGAGE30US", "GDP"],
        value=["DGS10", "UNRATE"],
        label="Series to compare (monthly, since 2000)",
    )
    compare_select
    return (compare_select,)


@app.cell
def _(compare_select, fetch_observations, mo, pl):
    _frames = []
    for _sid in compare_select.value:
        _o = fetch_observations(_sid, "2000-01-01", None, None, "m")
        _frames.append(
            _o.df.select(
                "date",
                pl.col("value").alias(_sid),
            )
        )

    compare_df = None
    _chart = None
    if _frames:
        compare_df = _frames[0]
        for _f in _frames[1:]:
            compare_df = compare_df.join(_f, on="date", how="full", coalesce=True)
        compare_df = compare_df.sort("date")
        _norm = compare_df.select(
            "date",
            *[
                ((pl.col(c) - pl.col(c).min()) / (pl.col(c).max() - pl.col(c).min()))
                .alias(c)
                for c in compare_df.columns
                if c != "date"
            ],
        )
        _long = _norm.unpivot(
            index="date", variable_name="series", value_name="normalized"
        ).drop_nulls("normalized")
        _chart = _long.plot.line(x="date", y="normalized", color="series")

    mo.vstack([x for x in (_chart, mo.ui.table(compare_df, page_size=8)) if x is not None])
    return (compare_df,)


@app.cell
def _(compare_df, mo, pl):
    _out = None
    if compare_df is not None:
        _cols = [c for c in compare_df.columns if c != "date"]
        _rows = []
        for _a in _cols:
            _row: dict[str, object] = {"series": _a}
            for _b in _cols:
                _row[_b] = round(
                    compare_df.select(pl.corr(_a, _b)).item() or 0.0, 3
                )
            _rows.append(_row)
        _out = mo.vstack(
            [mo.md("**Pairwise correlation** (levels)"), mo.ui.table(pl.DataFrame(_rows))]
        )
    _out
    return


@app.cell
def _(mo):
    mo.md("""
    ## Search the catalog
    """)
    return


@app.cell
def _(mo):
    search_box = mo.ui.text(
        value="unemployment rate", label="Full-text search", debounce=True
    )
    search_box
    return (search_box,)


@app.cell
def _(fredq, mo, pl, search_box):
    _result = fredq.search_series(search_box.value or "unemployment", limit=10)
    _table = pl.DataFrame(
        [
            {
                "id": s.id,
                "title": s.title,
                "frequency": s.frequency_short,
                "units": s.units_short,
                "popularity": s.popularity,
                "range": f"{s.observation_start} - {s.observation_end}",
            }
            for s in _result.seriess
        ]
    )
    mo.vstack(
        [
            mo.md(f"{_result.count} matches (showing {len(_result.seriess)})"),
            mo.ui.table(_table, page_size=10),
        ]
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Revisions (ALFRED vintages)

    The same series as it looked on two different publication dates —
    fetched with `realtime_start == realtime_end == vintage`. Not all
    series revise alike: **retail sales (RSAFS)** and **industrial
    production (INDPRO)** rework recent months on every release,
    **payrolls (PAYEMS)** revises its prior two months, **GDP** mostly
    moves only between its estimate rounds, and **UNRATE/CPIAUCSL**
    change only at annual seasonal-factor benchmarks (adjacent vintages
    look identical). Rows are classified so new-in-newer observations
    aren't silently dropped by the join.
    """)
    return


@app.cell
def _(mo):
    revision_series = mo.ui.dropdown(
        options=["RSAFS", "INDPRO", "PAYEMS", "GDP", "UNRATE", "CPIAUCSL"],
        value="RSAFS",
        label="Series (heavy revisers first)",
    )
    revision_series
    return (revision_series,)


@app.cell
def _(fetch_vintages, mo, revision_series):
    _vintages = [
        str(d) for d in fetch_vintages(str(revision_series.value)).vintage_dates
    ]

    vintage_old = mo.ui.dropdown(
        options=_vintages,
        value=_vintages[min(4, len(_vintages) - 1)],
        label="Older vintage",
    )
    vintage_new = mo.ui.dropdown(
        options=_vintages, value=_vintages[0], label="Newer vintage"
    )
    mo.hstack([vintage_old, vintage_new])
    return vintage_new, vintage_old


@app.cell
def _(
    fetch_vintage_observations,
    mo,
    pl,
    revision_series,
    vintage_new,
    vintage_old,
):
    _sid = str(revision_series.value)
    _start = "2024-01-01"
    _old = fetch_vintage_observations(_sid, str(vintage_old.value), _start)
    _new = fetch_vintage_observations(_sid, str(vintage_new.value), _start)

    revisions = (
        _old.df.select("date", pl.col("value").alias("older"))
        .join(
            _new.df.select("date", pl.col("value").alias("newer")),
            on="date",
            how="full",
            coalesce=True,
        )
        .with_columns((pl.col("newer") - pl.col("older")).alias("revision"))
        .with_columns(
            pl.when(pl.col("older").is_null())
            .then(pl.lit("new in newer vintage"))
            .when(pl.col("newer").is_null())
            .then(pl.lit("only in older vintage"))
            .when(pl.col("revision") != 0)
            .then(pl.lit("revised"))
            .otherwise(pl.lit("unchanged"))
            .alias("status")
        )
        .sort("date")
    )
    _revised = revisions.filter(pl.col("status") == "revised")
    _new_rows = revisions.filter(pl.col("status") == "new in newer vintage")
    _max_delta = (
        _revised.select(pl.col("revision").abs().max()).item()
        if _revised.height
        else 0.0
    )
    _chart = (
        _revised.plot.bar(x="date", y="revision") if _revised.height else None
    )

    mo.vstack(
        [
            mo.md(
                f"**{_sid}** between vintages {vintage_old.value} and "
                f"{vintage_new.value} (observations since {_start})"
            ),
            mo.hstack(
                [
                    mo.stat(value=str(revisions.height), label="rows"),
                    mo.stat(value=str(_revised.height), label="revised"),
                    mo.stat(value=str(_new_rows.height), label="new in newer"),
                    mo.stat(value=f"{_max_delta:g}", label="max |revision|"),
                ]
            ),
            _chart
            if _chart is not None
            else mo.callout(
                mo.md(
                    "No revised overlapping observations between these two "
                    "vintages — pick vintages further apart, or a heavier "
                    "reviser (RSAFS, INDPRO, PAYEMS)."
                ),
                kind="info",
            ),
            mo.ui.table(
                revisions.filter(pl.col("status") != "unchanged").sort(
                    "date", descending=True
                ),
                page_size=10,
            ),
        ]
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Mortgage rates vs the 10-Year Treasury

    30-year fixed mortgage (MORTGAGE30US, weekly) against the 10-year
    constant-maturity Treasury yield (DGS10, daily), as-of joined: each
    weekly mortgage print pairs with the latest Treasury close at or
    before it. The spread between them is the price of mortgage credit
    and prepayment risk — overlaid with unemployment (UNRATE, monthly,
    as-of joined the same way), since spread blowouts and unemployment
    spikes mark the same stress episodes. Note UNRATE for month M is
    published in early M+1; for strict real-time alignment use the ALFRED
    vintage panel's technique instead.
    """)
    return


@app.cell
def _(mo):
    spread_window = mo.ui.dropdown(
        options={
            "Full history (1971+)": "1971-04-01",
            "Since 2000": "2000-01-01",
            "Since 2015": "2015-01-01",
            "Since 2022": "2022-01-01",
        },
        value="Since 2015",
        label="Window",
    )
    spread_window
    return (spread_window,)


@app.cell
def _(fetch_observations, mo, pl, spread_window):
    _start = str(spread_window.value)
    _mortgage = fetch_observations("MORTGAGE30US", _start, None, None, None)
    _treasury = fetch_observations("DGS10", _start, None, None, None)
    _unrate = fetch_observations("UNRATE", _start, None, None, None)

    spread_df = (
        _mortgage.df.drop_nulls("value")
        .select("date", pl.col("value").alias("mortgage_30y"))
        .sort("date")
        .join_asof(
            _treasury.df.drop_nulls("value")
            .select("date", pl.col("value").alias("treasury_10y"))
            .sort("date"),
            on="date",
        )
        .join_asof(
            _unrate.df.drop_nulls("value")
            .select("date", pl.col("value").alias("unemployment"))
            .sort("date"),
            on="date",
        )
        .drop_nulls()
        .with_columns(
            (pl.col("mortgage_30y") - pl.col("treasury_10y")).alias("spread")
        )
    )

    _latest = spread_df.tail(1).to_dicts()[0]
    _levels_chart = (
        spread_df.unpivot(
            index="date",
            on=["mortgage_30y", "treasury_10y", "unemployment"],
            variable_name="series",
            value_name="percent",
        ).plot.line(x="date", y="percent", color="series")
    )
    _stress_chart = (
        spread_df.unpivot(
            index="date",
            on=["spread", "unemployment"],
            variable_name="series",
            value_name="percent",
        ).plot.line(x="date", y="percent", color="series")
    )
    _corr_spread_unrate = spread_df.select(
        pl.corr("spread", "unemployment")
    ).item()
    _corr_treasury_unrate = spread_df.select(
        pl.corr("treasury_10y", "unemployment")
    ).item()

    mo.vstack(
        [
            mo.hstack(
                [
                    mo.stat(
                        value=f"{_latest['mortgage_30y']:.2f}%",
                        label=f"30y mortgage ({_latest['date']})",
                    ),
                    mo.stat(
                        value=f"{_latest['treasury_10y']:.2f}%",
                        label="10y Treasury (as-of)",
                    ),
                    mo.stat(
                        value=f"{_latest['spread']:.2f}%",
                        label="current spread",
                    ),
                    mo.stat(
                        value=f"{_latest['unemployment']:.1f}%",
                        label="unemployment (as-of)",
                    ),
                    mo.stat(
                        value=f"{spread_df['spread'].mean():.2f}%",
                        label="mean spread (window)",
                    ),
                ]
            ),
            _levels_chart,
            mo.md(
                "**Credit stress view** — spread (mortgage − Treasury) vs "
                f"unemployment. Window correlations: spread↔unemployment "
                f"**{_corr_spread_unrate:.2f}**, Treasury↔unemployment "
                f"**{_corr_treasury_unrate:.2f}**."
            ),
            _stress_chart,
            mo.ui.table(spread_df.sort("date", descending=True), page_size=8),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
