.PHONY: help tox lint wheel spell spell-changed coverage pre-push

help:
	@echo "Available commands:"
	@echo "  make tox           - Run tox: every Python version, spelling, wheel (installs uv + tox group if needed)"
	@echo "  make lint          - Run black, ruff and pyright once, on the current Python"
	@echo "  make wheel         - Smoke-test the built wheel installed on its own"
	@echo "  make spell         - Run cspell on all files (installs npm packages if needed)"
	@echo "  make spell-changed - Run cspell on files changed on this branch or not committed"
	@echo "  make coverage      - Run tox coverage env with HTML report"
	@echo "  make pre-push      - Run lint, coverage and spell-changed before pushing"

tox:
	@command -v uv >/dev/null 2>&1 || { echo >&2 "uv not found. Install from: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	@uv run tox --version >/dev/null 2>&1 || { echo "Installing tox group..."; uv sync --group tox --frozen; }
	uv run tox

lint:
	@command -v uv >/dev/null 2>&1 || { echo >&2 "uv not found. Install from: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	@uv run tox --version >/dev/null 2>&1 || { echo "Installing tox group..."; uv sync --group tox --frozen; }
	uv run tox -e lint

wheel:
	@command -v uv >/dev/null 2>&1 || { echo >&2 "uv not found. Install from: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	@uv run tox --version >/dev/null 2>&1 || { echo "Installing tox group..."; uv sync --group tox --frozen; }
	uv run tox -e wheel

node_modules/.bin/cspell:
	@command -v npm >/dev/null 2>&1 || { echo >&2 "npm not found. Install Node.js from: https://nodejs.org/"; exit 1; }
	npm install

spell: node_modules/.bin/cspell
	npm run spell

spell-changed: node_modules/.bin/cspell
	npm run spell:changed

coverage:
	@command -v uv >/dev/null 2>&1 || { echo >&2 "uv not found. Install from: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	@uv run tox --version >/dev/null 2>&1 || { echo "Installing tox group..."; uv sync --group tox --frozen; }
	uv run tox -e coverage -- --cov-report=html

# Each check once, on the current Python, with the tests run once (under
# coverage, on every core). CI also runs the tests on every supported Python
# version and checks Windows and the built wheel; `make tox` runs all but Windows.
pre-push: lint coverage spell-changed
	@echo "All pre-push checks passed!"
