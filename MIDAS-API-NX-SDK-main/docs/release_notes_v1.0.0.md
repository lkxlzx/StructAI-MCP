## Public API freeze

Endpoint coverage is now 398/398 (100%) — every documented endpoint across all
27 manual chapters, plus the 8 previously-undocumented Hyper-S `-M1` stubs, is
implemented. `PRODUCTS` gen/civil classification has been re-verified live
with both products open simultaneously, write round trips are confirmed on
43/43 Civil resources and 38/43 Gen (the other 5 are genuinely Civil-only, not
untested), and the manual-diff discipline has now caught and fixed a real
upstream defect by hand (see `/db/REBW` below). This is the bar this project
set for 1.0: a frozen public surface, live-verified core paths, and a
demonstrated change-detection discipline — not just a high endpoint count.

Three releases' worth of `src/` changes are bundled here, all from live
testing against real Civil NX and Gen NX sessions rather than the manual
alone.

## ⚠️ Breaking

### 21 endpoints are Gen NX only (`GEN_ONLY`)

`STOR`, `SWIND`, `SSEIS`, `POSP`, `EPST`, `DRLS`, `SDHY`, `SDIS`, `REBB`,
`REBC`, `REBR`, `REBW` (`/db/*`), plus 9 design-chapter endpoints under
`RC/KDS-41-20-2022`, `SRC/AIK-SRC2K`, and `STEEL/KDS-41-30-2022` — the SDK
previously offered these to Civil clients, who could only ever get a 404 back
from the server. Live testing (independently reproduced by a second,
externally-run validation sweep) confirmed all 21 answer under Gen NX and
404 — at both the route and `/info` schema level — under Civil NX.

A Civil client now raises `ProductMismatchError` before issuing the request,
via the new `GEN_ONLY` constant in `db/base.py` (mirrors the existing
`HYPER_S_ONLY`/`CIVIL_ONLY`).

### `/db/REBW`'s entire field-name schema was wrong

Every field name `WallRebarPayload`/`WallRebarItem` documented
(`VERTICAL_REBAR`, `HORIZONTAL_REBAR`, `STORY: {FROM, TO}`,
`CONCRETE_FACE_TO_CENTER_OF_REBAR`, ...) turned out to be wrong — confirmed
against a real production Gen NX model's live GET, a `/info/db/REBW` schema
check, and a reversible live PUT round trip. The real wire contract uses
`VER_BAR`, `HOR_BAR`, top-level `DW`/`DE`, and `vSTORY_NAME` (a story-name
array, not a numeric range) — and this isn't a vendored-copy transcription
error: MIDASIT's own official Zendesk article documents the same wrong
long-form names. Its siblings `/db/REBB` and the KDS-specific
`/DESIGN/RC/KDS-41-20-2022/REBW` both matched their own docs exactly, so this
was isolated to this one endpoint's manual section, not systemic.

If you were calling `WallRebar.create()`/`.update()` with the old field
names, every call has been silently failing (or writing nothing). The
TypedDict now matches the server; update your payloads to the new field
names.

## Fixed

- **`POST /db/NMAS` no longer crashes Civil NX or Gen NX.** Root-caused after
  15+ reproductions across both products, multiple builds, and both
  throwaway and real production models: the server crashes when the optional
  `rmX`/`rmY`/`rmZ` fields are omitted, and does not crash when they're sent
  explicitly — even as `0.0`, their own documented default. `NodalMass.create()`
  and `.update()` now fill them in automatically before sending, so calling
  the class through this SDK is safe without knowing any of this.
- **32 endpoints wrongly declared Civil-only now also work on Gen NX**,
  including `/db/LCOM-CONC` (494 real rows on a live model) and the rest of
  ch08/ch17's moving-load and bridge family, the `MVCT` analysis-control
  variants, and `LCOM-STLCOMP`. They were reverted to the class default
  (gen+civil); 15 endpoints remain genuinely Civil-only. Whether an
  engineer *should* drive a bridge/moving-load feature from a Gen NX session
  is a judgment call for the calling engineer — this only corrects what the
  API itself will answer.
- `/ope/STORY_IRR_PARAM`'s `StoryIrregularityCheckParameterArgument` now
  documents the server's real space-containing enum values (`"Drift at the
  Center of Mass"`, `"1 / Story Drift Ratio"`) instead of the space-stripped
  forms the manual's own worked example used — confirmed against a real
  configured value on a production Gen NX model.
- Story Drift's `X_DIR`/`X-DIR` key spelling synced to the vendor's own
  official correction.
- `/db/SECF` (`SectionStiffnessPayload`) is keyed by section id, not element
  id as previously documented — posting under an element id silently stores
  nothing.
- `/db/PRES`'s documented `DIRECTION` default of `"NORMAL"` is rejected for
  the commonest case (a `PLATE`/`FACE` load); use `"LZ"` instead.

## Added

- **The 8 previously-undocumented Hyper-S `-M1` stubs are now implemented**:
  `StructureTypeHyperS` (`STYP-M1`), `MaterialHyperS` (`MATL-M1`),
  `InelasticFiberMaterialLinkHyperS` (`IMFM-M1`), `PlasticMaterialHyperS`
  (`EPMT-M1`), and `InelasticHingePropertyHyperS{Beam,Truss,GeneralLink,Pss}`
  (`IEHG-{BEAM,TRUSS,GL,PSS}-M1`). None had a Specifications table in the
  manual to transcribe from, so their payload TypedDicts are derived from
  live `GET /info/db/...` server introspection instead — documented in-module
  as server-derived. 5 of 8 have a directly-confirmed `/info` schema; the
  other 3 (`IEHG-TRUSS/GL/PSS-M1`) have no `/info` route at all, so their
  shape is assumed by sibling analogy to `IEHG-BEAM-M1` and flagged as such.
  Two of them (`MATL-M1`, `IMFM-M1`) turned out to have a genuinely different
  wire shape from their non-Hyper-S sibling, not just a product gate on an
  identical schema.
- `GEN_ONLY` constant in `db/base.py`.

## Verification

- Endpoint coverage: **398/398 (100%)**.
- Live-verified (GET, both products, `docs/coverage.json`): **303/398**.
- Write round trips (`scripts/live_crud_check.py`, create→read→update→read→
  delete→read): **43/43 confirmed on Civil NX**, **38/43 on Gen NX** (the
  other 5 are genuinely Civil-only cases, not untested).
- **680 tests**, `responses`-mocked, no live server needed.

## Live-server behaviour worth knowing

All of this is new in `docs/live_verification_notes.md`:

- **A `GET` can still pop a Windows access-denied dialog** if the open
  document lives under `Program Files` (or another path a standard account
  can't write to) — some read-shaped commands write an auxiliary file next
  to the document even to answer a `GET`. Keep working documents off
  `Program Files`-style paths.
- **Route existence and per-value licensing are different questions.**
  `/db/MVCD` answers on Gen NX, but creating with `CODE: "KOREA"` (or
  `"CHINA"`/`"KSCE-LSD15"`) is rejected as an unavailable moving-load code,
  while `"AASHTO STANDARD"`/`"AASHTO LRFD"`/`"EUROCODE"`/`"BS"` all succeed.
  A `GET`/`.info()` route check only confirms the route, not every value.

## Compatibility

Python 3.9+, `requests` only.
