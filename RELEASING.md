# Releasing fredq

fredq publishes to [PyPI](https://pypi.org/project/fredq/) from GitHub Actions
using **Trusted Publishing** (OIDC) — no API tokens. Two workflows chain off a
pushed tag:

1. `release.yml` — on a pushed `vX.Y.Z` tag, creates a **GitHub Release** with
   notes pulled from the matching `CHANGELOG.md` section.
2. `publish.yml` — on that **Release being published**, builds the sdist +
   wheel, runs `twine check`, and uploads to PyPI.

> **Why a tag alone wasn't enough (and the PAT requirement).** A git tag and a
> GitHub Release are different objects: `publish.yml` listens for the `release`
> event, which a bare `git push` of a tag does not emit. `release.yml` bridges
> that gap. It must create the release with a **Personal Access Token**
> (`secrets.RELEASE_PAT`, needs `contents: write`), **not** the default
> `GITHUB_TOKEN` — releases created by `GITHUB_TOKEN` do not fire the `release`
> event, so `publish.yml` would never run.

> Trusted publisher, the `pypi` environment (with required-reviewer approval),
> and `RELEASE_PAT` are configured once. No per-release infrastructure setup.

## Cutting a release

The version is derived from the git tag by `hatch-vcs` — there is **no manual
version bump**. `src/fredq/__init__.py` reads it from a generated `_version.py`
at build time. Tagging `vX.Y.Z` makes the build `X.Y.Z`; commits after a tag get
a `X.Y.(Z+1).devN` version automatically.

1. Move the `## [Unreleased]` notes in `CHANGELOG.md` under a new `## [X.Y.Z]`
   heading and update the compare links at the bottom. Commit and push to `main`.
   Wait for CI to go green.
2. Tag and push — this is the only manual trigger; the release is created for you:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

   (If a tag was already pushed before `release.yml` existed, run the workflow
   manually instead: Actions → *Create Release* → *Run workflow* → enter the tag.)
3. The `publish` job pauses on the `pypi` environment. **Approve the deployment**:
   the run page shows *"Review pending deployments"* → tick `pypi` → *Approve and
   deploy*. After approval it uploads to PyPI.
4. Verify: <https://pypi.org/project/fredq/> shows the new version.

## Verify locally before releasing

```bash
uv build
uvx twine check dist/*
```

The built filenames carry the version `hatch-vcs` derived from git
(`fredq-X.Y.Z...`). A clean checkout *at* the tag yields exactly `X.Y.Z`; a dirty
tree or post-tag commit yields a `.devN`/`+g<sha>` suffix.
