## Overview

fredq 0.7.1 is a maintenance release. The library API, the CLI and the published dependency ranges are unchanged from 0.7.0; upgrading is optional.

## Highlights

- **Tag-driven releases.** Pushing a `vX.Y.Z` tag now runs the full CI suite on the tagged commit, builds and verifies the distribution, publishes to PyPI after approval, and creates the GitHub Release with the wheel and sdist attached. This is the first release made that way.
- **Broader CI.** Every change is now also checked on Windows and against the installed wheel.
- Internal dependency refresh: dev and CI tooling updates (including pytest-asyncio and the setup-uv action) and lockfile-only bumps. None of these change fredq's published dependency ranges.

**Full Changelog:** https://github.com/joce/fredq/compare/v0.7.0...v0.7.1
