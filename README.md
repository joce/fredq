# fredq

LLM-friendly CLI for raw [FRED](https://fred.stlouisfed.org/docs/api/fred/) (Federal Reserve Economic Data) API JSON.

Companion to [yoghurt](https://github.com/joce/yoghurt) (Yahoo Finance) and `edgarq` (SEC EDGAR). Same shape: one process per call, print exactly what the upstream service returned, let the caller pipe it into whatever they want.

## Status

Alpha. Scaffolding in place; endpoints being added incrementally.

## Install

```bash
uv tool install fredq
```

Or for development:

```bash
git clone git@github.com:joce/fredq.git
cd fredq
uv sync --all-groups
uv run fredq --help
```

## API key

Get a free key from <https://fred.stlouisfed.org/docs/api/api_key.html>.

`fredq` reads the key from, in order:

1. `FRED_API_KEY` environment variable.
2. File at `~/.fredq/api_key` (single line, key only).

On POSIX systems, restrict the file so only your user can read it:

```bash
chmod 600 ~/.fredq/api_key
```

`fredq` emits a warning if the file is readable by group or world.

## Usage

```bash
# Discovery
fredq --help
fredq <command> --help

# Fetch a series' observations
fredq series-observations --series-id GNPCA

# Search for series
fredq series-search --search-text "consumer price index"
```

## Output

By default, `fredq` prints the FRED JSON body to stdout exactly as returned. Pipe it through `jq`, parse it in Python, feed it to an LLM, whatever.

Observation-style endpoints also accept `--format parquet --out PATH` for binary, columnar output when JSON gets unwieldy. JSON stays the default everywhere.

## Out of scope

- **GeoFRED (Maps API)** — deferred. See [docs/v2-geofred.md](docs/v2-geofred.md).
- Modeling FRED JSON into Python objects.
- Discovery sub-commands beyond `--help`.

## License

MIT. See [LICENSE](LICENSE).
