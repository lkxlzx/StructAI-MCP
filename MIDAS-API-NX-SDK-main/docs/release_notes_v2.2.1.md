## Fixed

- **`design.src_aiksrc2k.perform_src_optimal_design()` (SRC Optimal Design,
  `OCHECK`) called a path MIDASIT quietly retired.** Per MIDASIT's reply
  to the crash this SDK reported against the endpoint (closed as "not a
  defect"): `OCHECK` is an unofficial API paused mid-development with no
  resume date, and MIDASIT moved it from
  `/DESIGN/SRC/AIK-SRC2K/OCHECK` to `/TEMP/DESIGN/SRC/AIK-SRC2K/OCHECK`
  specifically to mark it as such. Confirmed live 2026-08-07: the old path
  now cleanly 404s, so every call through this SDK's old code was failing
  outright. `perform_src_optimal_design()` now points at the new path.

## Docs

- **The path move is not a fix, and the docstring says so.** Re-tested the
  new `/TEMP/` path live on Gen NX 2026-08-07 against a session with real
  non-SRC-eligible sections (the same shape that crashed Civil NX
  2026-07-31): identical crash — timeout, then the session unresponsive,
  full restart required. `perform_src_optimal_design()`'s docstring gained
  a 🛑 unofficial/paused-API warning up front and a dated repro paragraph;
  calling it is still expected to crash the running NX session.
- `docs/coverage.json`'s entry renamed to the new path and gained a new
  `live_verified` block, `outcome: "crash_or_hang"` — first use of that
  outcome value, added this release to distinguish a reproducible
  crash/hang from `success_empty`/`success_populated`.

## How this was found

Live re-verification pass immediately after a 2026-08-06 Gen/Civil NX
patch, checking whether previously-reported issues were actually fixed.
Two were (`/ope/EDMP`/`/ope/USLC`, already verified separately); the
`OCHECK` crash report turned out to be closed not by a fix but by moving
the endpoint under `/TEMP/` and documenting it as unofficial — this SDK
needed to follow that move rather than keep calling a dead path. `_BASE`
in `src_aiksrc2k.py` is shared by ~25 other endpoints in the same module;
none of those changed, since MIDASIT's move only touched `OCHECK`. The
SDK never wrapped the sibling endpoints MIDASIT's reply also mentioned
(steel's own `OCHECK`, `DCHECK`), so there was nothing to update for
those.
