# midas-nx 2.9.3

A shared PyPI/npm version release. **Nothing executable changed on either
side.** `src/midas_nx/` and `packages/typescript/src/` are identical to
2.9.2 — no behaviour, no types, no API surface. What changed is the packaged
metadata and the documentation people read before installing.

| surface | what actually changed |
| --- | --- |
| Python | packaged metadata only. `Author` is `Dennis`, a LinkedIn contact URL is added to the project URLs, and the PyPI long description (the root README) gains that contact. The code in the wheel is byte-identical to 2.9.2 |
| npm | packaged metadata and README only. `author` becomes an object with a name and a LinkedIn URL, and the README is rewritten around getting a first read-only script running. `dist/` is unchanged |

## Why a release for this

The author credit and contact only exist once they are published — until
this release both registries showed a GitHub handle and offered no way to
reach anyone except by opening a bug report. The same is true of the npm
README rewrite: it is the page npmjs.com shows, and it was the one place a
new user could not get started from.

## Author and contact, on both registries

The SDK is written by **Dennis**. For questions, feedback, or anything that
is not a bug report, the contact is
[LinkedIn](https://www.linkedin.com/in/dennis58).

The existing routing is unchanged and still the right first stop:

- Problems with **this SDK** →
  [GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues)
- Problems with **the products, licensing, or the Open API service** →
  MIDAS IT's official support channels

## The npm package's front page

The npm README assumed you already knew this API and only needed the
JavaScript binding. Measured against the two audiences this project is for —
structural engineers new to coding, and engineers who code with an AI
assistant — it failed both. It never said what a MAPI key is or where to get
one, never linked the documentation site or the safety guide, and its first
API example created and deleted records with no warning.

It now opens with what you need before installing, labels its first example
**Risk level 1 — read-only**, and carries a "Where to go next" table near the
top pointing at the safety guide, the quickstart, the AI context pack and
runnable examples. The project-status paragraph is now also in Korean,
Traditional Chinese and Simplified Chinese, matching the root README.

## New in the repository, shipped in neither package

- **`examples/javascript/`** gives the npm package the two examples that
  matter first: `verify-and-read.mjs` (risk 1) and `quickstart.mjs` (risk 4),
  each matching its Python namesake payload for payload and stating its risk
  level. The other two Python examples - a load combination and a KDS wind
  load - have no JavaScript twin yet.
- **The AI context pack has a TypeScript half.** `docs/ai-coding/` previously
  described the Python API only; `safe-start.md` now gives both spellings
  wherever a name differs.
- **`docs/verification.md` no longer carries three retracted findings.** The
  `/db/TDMT` and `/db/SECF` documentation claims were retracted on
  2026-07-27 when they were re-checked against MIDAS IT's own published
  articles — one of them was this SDK's own docstring, not a vendor claim —
  and `/db/MVHL`'s followed on 2026-09-03. The live observations behind them
  stand; the conclusions about the documentation did not.
- Thirteen `docs/release_notes_v*_highlights.md` files are deleted. The
  practice stopped after 2.3.2 and the text lives on the GitHub Releases.
