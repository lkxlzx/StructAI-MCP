Packaged-metadata-only release. No `src/midas_nx/` behaviour changed.

## Changed

- **`README.md` trimmed from ~15.7 KB to ~4.3 KB.** It ships verbatim as the
  PyPI project description, and had grown to duplicate content that already
  lives on the [documentation site](https://dennis5882.github.io/MIDAS-API-NX-SDK/):
  the SDK-design bullets (`docs/index.md`), the full known-issues list
  (`docs/safety.md`), and the pytest/dev-setup instructions
  (`CONTRIBUTING.md`). Each language block now carries only the project-status
  statement, the install command, and a link to its beginner quickstart guide,
  with a short "Learn more" table at the bottom pointing to the fuller docs.
- Added a 简体中文 (Simplified Chinese) block, alongside the existing
  English/한국어/繁體中文 ones.
- The one section that wasn't already duplicated elsewhere — the
  corporate-firewall / SSL-inspection connectivity table — was moved into
  `docs/safety.md` (new "Connectivity troubleshooting" section) before being
  cut from the README, so nothing was lost.

## Why a version bump for a docs change

`pyproject.toml` declares `readme = "README.md"`, so the README is packaged
metadata, not just a repo file — this is the one category of doc change this
project's release policy treats as bump-worthy on its own.
