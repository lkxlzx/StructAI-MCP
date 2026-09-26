## Fixed

- **`post.design.get_brace_design_forces_table()` docstring updated:
  `BRACEDESIGNFORCES` independently confirmed crashing Gen NX.** Third of
  the Column/Beam/Brace Design-Forces family to reproduce the same crash
  signature (no response, then `verify_connection()` reports
  `"disconnected"`, every subsequent `/db/*` call 404s) — live-tested
  2026-08-10 against a blank `/doc/NEW` document on Gen NX 2026 (v2.2),
  build 08/06/2026. Confirmed clean on Civil NX. No code change; the
  docstring's crash warning is now backed by an independent reproduction
  rather than "equally at risk, untested by analogy."

## Docs — live-verification coverage

Two Gen NX sweeps closed most of the remaining Gen/Civil read-coverage gap:

- **Full `DbResource` GET sweep** (`scripts/live_readonly_sweep.py
  --product gen`): all 266 GET-capable classes answered cleanly, no
  crashes. Merged 32 new Gen confirmations onto existing Civil-only
  `live_verified` entries.
- **Manual batch of 38 non-crash-family design-chapter endpoints**
  (`view.py`'s `CAPTURE`/`PRECAPTURE`; `design.rc_kds.design_forces`'s
  BD/CD/BRD/WD/HCD `*-ANAL`/`*-TABLE`/`*-REPORT`;
  `design.rc_kds.checks`'s BC/CC/BRC/WC `*-ANAL`/`*-TABLE`/`*-REPORT` +
  `CDESIGN`; `design.steel_kds`'s `CODE-ANAL`/`CODE-TABLE`/
  `CODE-REPORT`/`DREULT`; `design.src_aiksrc2k`'s BC/CC
  `*-ANAL`/`*-TABLE`/`*-REPORT`) — deliberately excluding the Design-Forces
  crash family and `OCHECK` (already confirmed crashing separately). Run
  against a blank document; all 38 answered with clean, informative
  refusals (`"Please perform analysis."` and similar) — no crash, no
  hang, including the historically hang-prone `WD-ANAL`, tested last and
  deliberately, with an explicit go-ahead given the past hang history.

  This also corrects a mid-session miscount: only 3 of
  `design.rc_kds.checks`'s untested entries (Column/Brace/Beam Design
  Forces) are actually crash-family; the other 11 (`BC`/`CC`/`BRC`/`WC`
  check functions + `CDESIGN`) are unrelated and were already partly
  re-verified clean via the QuickRebar NX production tool.

**`Verified on Gen NX`: 266/399 → 337/399.** Full detail in
`docs/live_verification_notes.md`'s 2026-08-10 entries.

## How this was found

Continuing the same session's crash-family investigation (Column and Beam
Design Forces already confirmed crashing) and closing the read-coverage
gap opened by the earlier Civil-side sweep, both against a live Gen NX
2026 (v2.2, build 08/06/2026) session with explicit user go-ahead before
each risk-carrying batch.
