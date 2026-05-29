# Releasing fredq

fredq publishes to [PyPI](https://pypi.org/project/fredq/) via GitHub Actions
using **Trusted Publishing** (OIDC) — no API tokens are stored. The workflow is
`.github/workflows/publish.yml`, triggered when a GitHub Release is published.

## One-time setup

1. **PyPI trusted publisher.** On PyPI, add a *pending publisher* for the project
   (Account → Publishing, or the project's Settings → Publishing once it exists):
   - PyPI Project Name: `fredq`
   - Owner: `joce`
   - Repository: `fredq`
   - Workflow filename: `publish.yml`
   - Environment name: `pypi`

2. **GitHub environment.** Create an environment named `pypi`
   (repo Settings → Environments). Optionally add required reviewers so a
   release must be approved before it publishes.

3. (Optional) Repeat step 1 on [TestPyPI](https://test.pypi.org/) to rehearse.

## Cutting a release

Version is single-sourced from `src/fredq/__init__.py` (`__version__`); hatchling
reads it at build time. There is no separate version in `pyproject.toml`.

1. Bump `__version__` in `src/fredq/__init__.py` (SemVer).
2. Move the `## [Unreleased]` notes in `CHANGELOG.md` under a new
   `## [X.Y.Z]` heading and update the compare links at the bottom.
3. Commit: `change: release vX.Y.Z`.
4. Tag and push:

   ```bash
   git tag vX.Y.Z
   git push origin main --tags
   ```

5. Create a GitHub Release for the `vX.Y.Z` tag. Publishing the release triggers
   `publish.yml`, which builds the sdist + wheel, runs `twine check`, and
   uploads to PyPI via OIDC.

## Verify locally before tagging

```bash
uv build
uvx twine check dist/*
uv run --version    # sanity
```

Confirm the built version matches `__version__`:

```bash
ls dist/   # fredq-X.Y.Z.tar.gz and fredq-X.Y.Z-py3-none-any.whl
```
