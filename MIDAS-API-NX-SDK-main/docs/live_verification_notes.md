# Live API verification notes

Empirical findings from running `midas-nx` v0.8.0 against real MIDAS NX Open
API sessions (one Gen NX session, one Civil NX session, both connected via
the live cloud relay at `moa-engineers.midasit.com`, not mocked). This is
**not** sourced from the vendored manual — everything else in this repo is
typed strictly from `docs/manual/*.md` and treated as the single source of
truth; this file exists precisely because these findings are *not* in the
manual and shouldn't be silently baked into the SDK's typed contracts
(`PRODUCTS`, `METHODS`) without independent reproduction. See the caveat at
the bottom before acting on anything here.

Date: 2026-07-15. One MIDASIT account, one Gen NX process, one Civil NX
process, both freshly reset via `/doc/new` before testing.

**Current live-session baseline (2026-09-16, author-confirmed):** MIDAS Gen NX
2026 v2.1, **Build 09/15/2026**; MIDAS Civil NX 2026 v2.2, **Build 09/15/2026**.
Both were read from their own About dialogs on 2026-09-16. The two products
carry the same build date for the first time in this file's history - they have
been patched separately all year - so do not infer one from the other next time
either; read both.
Record this baseline with every new live finding; it supersedes an endpoint's
older build metadata only when that endpoint was actually exercised in this
session.

**The API reports no build.** There is no `/doc/*`, `/ope/*` or `/view/*`
endpoint that returns one, and `verify_connection()` answers only `user`,
`program`, `connectionID`, `keyVerified` and `status` - confirmed 2026-09-06.
So every build string in this file and in `docs/coverage.json` is a human
reading the product's About dialog. **A build string you did not read is not a
measurement**; leave the field out rather than carry one forward from a
neighbouring entry. That is exactly how five 2026-09-06 entries came to claim
Builds 08/26 and 08/27 on machines running 09/02.

## Method

1. **Read-only smoke test**: every `DbResource` subclass across `db/`,
   `design/`, `post/` whose `METHODS` includes `GET` and whose `PRODUCTS`
   includes the product under test got a live `GET` call against a blank
   new document. No fixtures needed — a blank model returns an empty result
   for every valid endpoint (confirmed shape: `{"message": ""}` for
   zero-row tables, `{"<KEY>": {}}` for zero-row `/db/*` tables), so a
   non-2xx response reliably signals a real problem rather than "no data."
2. **Write round-trip** (Gen only): built a minimal model — 1 material
   (`MATL`, concrete C24), 1 section (`SECT`, 600×600), 2 nodes, 1 beam
   element, 1 fixed support — then exercised representative endpoints from
   each design-code chapter (ch24 `db/design.py`, ch25 `steel_kds.py`, ch26
   `rc_kds/setup.py`, ch27 `src_aiksrc2k.py`) against it.

## Read-only results

| Product | GET-capable & product-compatible classes tested | OK | Failed (all 404) |
|---|---|---|---|
| Gen  | 253 | 233 (92%) | 20 |
| Civil | 293 | 273 (93%) | 20 |

### Failure breakdown

**Hyper-S (`-M1`) endpoints — 13, fail under Gen.**

> ⚠️ **Corrected 2026-07-26.** The original text here said these were
> "absent from the Civil target set entirely (their `PRODUCTS` is already
> `{"gen"}`-only in the SDK)" and explained the Gen 404s as the session not
> running in Hyper-S solver mode. **Both halves were wrong.** Their
> `PRODUCTS` was `{"gen", "civil"}`, so they *were* in the Civil target set,
> and re-running the sweep shows all 13 **answering under Civil**. Hyper-S
> is the solver MIDASIT introduced with Civil NX — it is a Civil NX feature,
> not a Gen mode — so the Gen 404s are correct behaviour and the SDK's
> `PRODUCTS` was the thing that was wrong. Fixed via `HYPER_S_ONLY` in
> `db/base.py`. See the 2026-07-26 section below. The claim was never
> checked against a Civil run; it was inferred, and the inference was wrong
> in a way that a one-line `sorted(cls.PRODUCTS)` would have caught.

- `/db/ACTL-M1`, `/db/BCGA-M1`, `/db/BCGD-M1`, `/db/EIGV-M1`,
  `/db/HHCT-M1`, `/db/NLCT-M1`, `/db/NLNK-M1`, `/db/STCT-M1`,
  `/db/THGC-M1`, `/db/THIS-M1`, `/db/THOO-M1`, `/db/POGD-M1`,
  `/db/POLC-M1`

**Failed under Gen, succeeded under Civil (7)** — current SDK `PRODUCTS`
says `{"gen", "civil"}` for all of these (no restriction documented in the
manual), but this session's evidence points to Civil-only in practice:

- `midas_nx.db.construction_stage.CamberConstructionStage` (`/db/CMCS`)
- `midas_nx.db.design.RebarCheckInput` (`/db/RCHK`)
- `midas_nx.db.misc_loads.PreCompositeSection` (`/db/PLCB`)
- `midas_nx.db.misc_loads.WaveLoad` (`/db/WVLD`)
- `midas_nx.db.project.Span` (`/db/SPAN`)
- `midas_nx.db.properties.section.EffectiveWidthScaleFactor` (`/db/EWSF`)
- `midas_nx.db.properties.section.SectionStressPoints` (`/db/STRPSSM`)

**Failed under Civil, succeeded under Gen (20)** — same situation, opposite
direction; evidence points to Gen-only in practice:

- `midas_nx.db.boundary.DiaphragmDisconnect` (`/db/DRLS`)
- `midas_nx.db.boundary.SeismicDeviceHystereticIsolator` (`/db/SDHY`)
- `midas_nx.db.boundary.SeismicDeviceIsolator` (`/db/SDIS`)
- `midas_nx.db.design.BeamRebar` (`/db/REBB`)
- `midas_nx.db.design.BraceRebar` (`/db/REBR`)
- `midas_nx.db.design.WallRebar` (`/db/REBW`)
- `midas_nx.db.project.Story` (`/db/STOR`)
- `midas_nx.db.static_loads.SoilProperty` (`/db/POSP`)
- `midas_nx.db.static_loads.StaticEarthPressure` (`/db/EPST`)
- `midas_nx.db.static_loads.StaticSeismicLoad` (`/db/SSEIS`)
- `midas_nx.db.static_loads.StaticWindLoad` (`/db/SWIND`)
- `midas_nx.design.rc_kds.rebar.ModifyBeamRebarData` (`/DESIGN/RC/KDS-41-20-2022/REBB`)
- `midas_nx.design.rc_kds.rebar.ModifyBraceRebarData` (`/DESIGN/RC/KDS-41-20-2022/REBR`)
- `midas_nx.design.rc_kds.rebar.ModifyColumnRebarData` (`/DESIGN/RC/KDS-41-20-2022/REBC`)
- `midas_nx.design.rc_kds.rebar.ModifyWallRebarData` (`/DESIGN/RC/KDS-41-20-2022/REBW`)
- `midas_nx.design.rc_kds.rebar.TorsionReductionFactor` (`/DESIGN/RC/KDS-41-20-2022/TRFT`)
- `midas_nx.design.rc_kds.setup.ModifyConcreteMaterial` (`/DESIGN/RC/KDS-41-20-2022/MATD`)
- `midas_nx.design.rc_kds.setup.UndergroundLoadCombinationType` (`/DESIGN/RC/KDS-41-20-2022/ULCT`)
- `midas_nx.design.src_aiksrc2k.SrcModifyMaterial` (`/DESIGN/SRC/AIK-SRC2K/MATD`)
- `midas_nx.design.steel_kds.UndergroundLoadCombinationType` (`/DESIGN/STEEL/KDS-41-30-2022/ULCT`)

All URL paths above were double-checked character-for-character against the
manual's own "Input URI" for each endpoint — none of these are SDK
transcription bugs. The URLs are right; the routes just weren't reachable
from the product tested against.

## Write round-trip results (Gen)

- Model build (`MATL`, `SECT`, `NODE`, `ELEM`, `CONS`): all 5 calls returned
  exactly the documented response shape, verified byte-for-byte against
  what was sent.
- ch24–27 config-singleton `PUT` endpoints (`RcDesignCode`, `SteelDesignCode`,
  `SteelDesignCodeOption`, `ConcreteDesignCodeOption`, `SrcDesignCode`,
  `SrcDesignCodeOption`): all succeeded, response echoed the payload under
  the documented top-level key (`DCON`, `DSTL`, `DCO`, `DCORC`, `DSRC`,
  `SRCDCO`).
- ch24 `DesignMemberAssignment.create` (registers element 1 as design
  member 1): succeeded.
- **Operational nuance, not a bug**: once a design member is registered,
  the server auto-seeds a default per-member parameter record (e.g. `LENG`)
  for that member ID in every currently-selected design-code namespace.
  Calling `.create()` (`POST`) on that ID afterward returns
  `{"error": {"message": "Key Already Exist"}}` inside a 200 response
  (not an exception — `MidasClient.request()` only raises on non-2xx
  status, so callers must check for an `"error"` key even on success).
  Calling `.update()` (`PUT`) instead succeeds and a subsequent `GET`
  confirms the value round-trips exactly. Confirmed for
  `steel_kds.UnbracedLength`, `rc_kds.setup.UnbracedLength`, and
  `src_aiksrc2k.SrcUnbracedLength`, all targeting the same RC element —
  this also confirms the server does real semantic validation rather than
  blindly persisting writes (steel/SRC-code member parameters were still
  *accepted* on a plain-concrete element in this test, so no rejection was
  observed there, but the "already exists" behavior itself is a genuine
  cross-code-namespace side effect worth knowing about).

## Extended verification: Civil-only chapters + full analyze→results round-trip

Two more sessions were run after the initial pass above.

### Civil write test — ch08 moving loads / ch17 bridge (previously untested)

Built a minimal Civil model (30 m single-span concrete beam: 1 material, 1
section, 2 nodes, 1 element, 1 fixed support), then:

- `MovingLoadCode.update` (`/db/MVCD`, `CODE="AASHTO LRFD"`): succeeded.
- `TrafficLineLanes.create` (`/db/LLAN`) **first attempt failed** with a real
  server-side semantic validation error, not a schema rejection:
  `"[Error] Line Lane Data (Name:Lane1) contains errors.(Item:Centrifugal
  Force ( 0.0 < Value < 1.0))"`. The manual documents `LANE_ITEMS.CENT_F`
  as merely "optional (AASHTO LRFD only)" — this session's evidence is that
  once `AASHTO LRFD` is the selected moving-load code, `CENT_F` is
  effectively **required** (must be a value in the open interval (0, 1);
  the SDK's implicit default of omitting the field, which the server reads
  as 0.0, is rejected). Retried with `CENT_F: 0.1` — succeeded, and `GET`
  read back every field including server-filled defaults
  (`GROUP_NAME: ""`, `SKEW_START/END: 0`, `WHEEL_SPACE: 0`,
  `OPT_AUTO_LANE: False`, `ALLOW_WIDTH: 0`, `FACT: 0`, `SPAN_START: False`,
  `ECCEN_VERT_LOAD: 0`) — full round-trip confirmed once the semantically
  valid payload was sent. Not an SDK bug (the field genuinely is optional
  per the manual's schema, and the SDK correctly makes it optional in the
  `TypedDict`), but worth knowing if you hit the same error live: pass a
  nonzero `CENT_F` when `MVCD.CODE` is `"AASHTO LRFD"`.
- `BridgeGirderDiagram.create` (`/db/GSBG`) with a placeholder
  `BODY_ELEM_GRUP_K: 1` (no structure group with that ID actually existed):
  succeeded — the server did not validate the group reference exists at
  write time.

### Gen full analyze → results round-trip (post/* chapters, previously only mocked)

Added a static load case (`STLD`, `NAME="DL"`, `TYPE="D"`) and self-weight
(`BODF`, `FV=[0,0,-1]`) to the Gen cantilever-column model from the first
pass, then:

1. `doc.analyze()` (`/doc/ANAL`) — first call (no loads yet) correctly
   failed with `"[Error] Load information has not been entered for
   Analysis."`; after adding the load case, succeeded
   (`"MIDAS GEN NX command complete"`).
2. `post.result_1.get_reaction_table/get_displacement_table/
   get_beam_force_table` — first call used `load_case_names=["DL"]` and
   got back `{"message": ""}` for all three (looked like "no data", but
   was actually a caller mistake). `get_table`'s own docstring in
   `post/base.py` already documents the fix: load case names need a type
   suffix, e.g. `"DL(ST)"`. Retried with `["DL(ST)"]` — all three returned
   full documented `{FORCE, DIST, HEAD, DATA}` tables.
3. **The numbers are physically correct**, not just structurally valid:
   - Reaction at node 1 (base): `FZ = 28.243152` — matches hand-calc
     self-weight of a 0.6×0.6×3.2 m C24 concrete column (`0.36 m² × 3.2 m
     × ~24.5 kN/m³ ≈ 28.2–28.8 kN`).
   - Displacement at node 2 (free top): `DZ = -0.000005` m — negligible
     axial shortening under self-weight, correct sign (downward).
   - Beam force: axial force `-28.24 kN` at the I-end (base), decreasing
     linearly to `0.00` at the J-end (free top) across the 4 reported
     stations — exactly the expected self-weight axial-force diagram for a
     vertical cantilever.

This confirms the full chain end to end: SDK request shape → real Gen NX
solve → SDK response parsing, for both the `/db/*` write side and the
`/post/TABLE` read side.

## Civil full analyze → results round-trip, including moving-load envelope results (previously untested)

A later Civil session closed the remaining gap on the Civil side: static
analysis physically verified end to end, and — Civil's signature feature —
an actual moving-load analysis run and its `(MV:max)`/`(MV:min)` envelope
results read back and sanity-checked.

### Static self-weight round-trip — physically verified

Built a 30 m, 2-span (3-node) simply supported... in practice **fixed
against rotation at both ends** (constraint string `1111100` restrains
`RY` at both supports, not a true pin) concrete girder (`0.6×1.0 m`
rectangular section, `C24`/`KS01(RC)`), added a `DL` self-weight load case,
ran `doc.analyze()`, then read back reactions/displacements/beam forces:

- Total self-weight reaction: `ΣFZ = 423.647281 kN` across both supports
  (`211.823641` each) — consistent with a uniformly distributed self-weight
  load `w = 423.647 / 30 = 14.12 kN/m` on a `0.6 × 1.0 m` section.
- Support moment `MY = ±1059.11825 kN·m` — matches the fixed-end-moment
  formula for a fixed-fixed beam under UDL, `wL²/12 = 14.12 × 30² / 12 =
  1059.12` — an exact hand-calc match.
- Beam-force moment diagram across both elements' I/1/4/2/4/3/4/J stations
  forms a consistent parabola between the two support end-moments and the
  midspan value (`132.39`), matching continuous-beam bending-moment theory.

**Operational note, not a bug**: one `Material.create` attempt with
`STANDARD: "KS(RC)"` failed with `"Failed to get material data for:
C24"` — the correct Civil concrete standard code turned out to be
`"KS01(RC)"`, not `"KS(RC)"`. The manual doesn't enumerate every valid
`STANDARD` string per material type/product, so this is a live-only
finding, not a schema contradiction.

### Moving-load analysis — full chain verified, with real vehicle/lane data

Added `MovingLoadCode` (`CODE="KOREA"`), a Traffic Line Lane spanning both
elements, a `DB-24` Korean standard vehicle, and a moving-load case
referencing both, then re-ran analysis:

- `Vehicles.create` (`/db/MVHL`) **initially no-op'd silently**
  (`{"message": ""}`, not an error, and a subsequent `GET` confirmed
  nothing was actually saved) when `VEH_DEFAULT` was sent as `{}`. The
  manual's own worked example for `STANDARD_CODE="KS-RB"` always populates
  `VEH_DEFAULT` with explicit `DYN_LOAD_ALLOWANCE`/`CENT_F` values even
  though the schema marks those fields "optional" — copying the manual's
  exact worked example (`MVLD_CODE: 6`, `VEH_DEFAULT: {"DYN_LOAD_ALLOWANCE":
  0, "CENT_F": false}`) succeeded immediately. Worth knowing live: don't
  send an empty `VEH_DEFAULT: {}` even though every one of its fields is
  individually documented as optional — populate it per the manual's
  worked example for your `STANDARD_CODE`.
- `MovingLoadCase.create` (`/db/MVLD`, `TYPE=0` general load referencing
  the vehicle + lane by name) — succeeded.
- `doc.analyze()` — succeeded in **2.0s** (tiny model, no large-model delay
  here).
- `get_beam_force_table(load_case_names=["MV1(MV:max)"])` and
  `["MV1(MV:min)"]` — both returned full, real, non-degenerate envelope
  data: e.g. max positive midspan moment `615.61`–`732.12 kN·m`, min
  (most-negative) support moment `-1702.53 kN·m` (larger in magnitude than
  the plain self-weight case above, as expected — the DB-24 truck adds to
  the fixed-end moment at whichever support it's nearest). This is a
  believable, non-trivial moving-load envelope, not placeholder/zero data.

This confirms the full Civil-specific chain end to end: `MVCD` → `MVHL` →
`LLAN` → `MVLD` → `doc.analyze()` → `post/TABLE` with `(MV:max)`/`(MV:min)`
suffixes, previously only exercised as isolated writes (see the moving-load
write test above), not run through an actual analysis.

### Operational quirk shared with the Gen findings: a confirmation dialog blocks the whole API session, not just one call

Partway through this session, `MovingLoadCode.update` (changing the active
moving-load code) triggered a **Civil NX confirmation dialog** ("changing
this will delete existing analysis results") that the user hadn't
dismissed yet. While that dialog sat open, **every** subsequent API call —
including totally unrelated ones like a plain `GET /db/NODE` — timed out
with no response, not just the call that triggered the dialog. After the
user dismissed the dialog, the session immediately became responsive
again, and a `GET` on the field that triggered it confirmed the change had
already persisted despite the client-side timeout.

This is the same shape of finding as the Gen `CC-ANAL` stall (an API call
blocks on an unacknowledged UI dialog, and the underlying change completes
and persists regardless of whether the HTTP response ever arrives) — but
milder and expected: a normal user-confirmation dialog is not a bug, and
it explains itself once you know to check for it. Worth knowing for
scripted/batch use of this API: **any call that can trigger a confirmation
dialog (destructive/data-loss-risking changes) can make the entire session
appear hung until a human dismisses it**, not just that one call.

## ⚠️ CONFIRMED — `CC-ANAL` (RC column code-check perform) reproducibly stalls Gen NX at "Converting Design Results 0%" (often requires a forced process kill)

> **STATUS UPDATE (2026-07-25): `CC-ANAL`/`BC-ANAL`/`WC-ANAL` ran clean 4/4 —
> on the *same build* that hung here.** This is not a "fixed in a newer
> build" story: both the reproductions below and the clean re-runs happened
> on **Gen NX 2026 (v2.1), build 06/23/2026**. The trigger is therefore
> something other than the build, and is still unidentified — so nothing in
> this section is retracted. See
> [the re-verification section below](#status-update-2026-07-25--cc-analbc-anal-ran-clean-on-the-same-build-that-hung).

While extending the same Gen session above to verify design-code check
*execution* (as opposed to just config-singleton writes), the following
sequence **crashed/hung the Gen NX desktop application itself** (not just
an API error — the process stopped responding and required a manual
restart):

1. `design.rc_kds.setup.ModifyMemberType.create({1: {"TYPE": "COLUMN"}})` —
   succeeded.
2. `design.rc_kds.rebar.ModifyColumnRebarData.create({1: {"ITEMS": [...]}})`
   keyed by section number 1 (main bar D22×8, end/center hoop bars D10) —
   succeeded.
3. First `perform_column_check({"PERFORM_TYPE": "ALL"})` (`CC-ANAL`) —
   failed cleanly with `{"error": {"message": " Please perform
   analysis."}}` (expected — design parameters changed after the last
   solve, invalidating results).
4. Re-ran `doc.analyze()` — succeeded.
5. Retried `CC-ANAL` — failed cleanly with `{"error": {"message":
   "failed:LoadCombination"}}` (also expected — no load combination
   existed yet, only a raw load case).
6. Added `db.load_combinations.LoadCombinationGeneral.create({1: {"NAME":
   "COMB1", "ACTIVE": "ACTIVE", "iTYPE": 0, "vCOMB": [{"ANAL": "ST",
   "LCNAME": "DL", "FACTOR": 1.2}]}})` — succeeded.
7. Retried `CC-ANAL` a third time — **this call never returned**. Timed
   out client-side at both 30s (default) and 120s (explicit
   `MidasClient(timeout=120)`) with `ReadTimeoutError`/`ConnectionError`
   — no HTTP response at all, not even a slow one. The user confirmed the
   Gen NX desktop application itself had stopped responding and needed a
   full restart.

### Reproduction #2 — confirmed, with visual evidence

To rule out "messy session state" as the cause, the entire sequence was
redone from a **fresh `doc.new_project()`**, touching only RC design (no
`steel_kds`/`src_aiksrc2k` namespaces at all this time):

1. Fresh minimal model (1 material, 1 section, 2 nodes, 1 element, 1
   support, 1 static load case `DL`, self-weight) + `doc.analyze()` — all
   clean.
2. `ModifyMemberType` → `COLUMN`, `ModifyColumnRebarData` (same rebar
   payload as before), `doc.analyze()` again — all clean.
3. `CC-ANAL` before any load combination existed — failed cleanly and
   fast with `{"error": {"message": "failed:LoadCombination"}}`. **Did
   not hang.** This suggested the first hang might have been session-state
   related.
4. Manually written `db.load_combinations.LoadCombinationGeneral` combo
   — `CC-ANAL` retried — failed cleanly and fast again with the same
   `"failed:LoadCombination"` message (the manually-entered `LCOM-GEN`
   entry apparently isn't recognized as a valid design combination by the
   RC check module — a separate, milder finding, see below).
5. Used `ope.generate_load_combination_concrete({"OPTION": "ADD",
   "DGNCODE": "KDS 41 20 : 2022"})` instead — this **is** the right way to
   produce design-code-recognized combinations: it auto-generated
   `cLCB1` (`1.4(D)`, `ACTIVE: "STRENGTH"`) and `cLCB2`
   (`SERV:(D)`, `ACTIVE: "SERVICE"`) in `/db/LCOM-CONC`.
6. `CC-ANAL` retried a third time, now with a real, code-recognized
   design combination in place — **hung again**, this time with a 40s
   explicit client timeout.
7. The user checked the Gen NX window directly and found a **"Stop
   Design Thread" dialog, stuck at "Converting Design Results... 0%"**
   with a "Stop Execution" button. Clicking Stop Execution **did nothing**
   — the dialog stayed frozen. The application had to be force-killed via
   Task Manager; there was no graceful recovery path.

**Conclusion**: this is a real, reproducible Gen NX application defect,
not session-state flakiness and not an SDK issue. `CC-ANAL` (RC column
code-check "perform") appears to spawn an internal "Design Thread" that
can deadlock during its "Converting Design Results" phase, and the
deadlock is unrecoverable from the UI (Stop Execution is on the same
stuck thread/message loop). The Open API call blocks synchronously
waiting for that thread, so from the SDK's perspective it just looks like
a network read timeout with no way to distinguish "still computing" from
"permanently stuck" short of an arbitrarily long timeout.

### Reproduction #3 — confirmed a third time, on an unrelated large real-world model

To rule out "this only happens on a tiny synthetic 1-element model," the
same pattern was tested against a separate, pre-existing production-scale
Gen model (thousands of nodes/elements, real materials/loads/analysis
results already present, different RC design code originally selected).
Project-specific numeric details are intentionally omitted here — only the
reproduction pattern matters:

1. A read-only survey confirmed this model's active RC design code was
   **not** KDS 41 20:2022, so its `rc_kds.setup` (config-singleton) and
   `rc_kds.rebar` (member rebar) tables were empty for every member,
   despite the model already having real design-member registrations
   under a different code.
2. `CC-ANAL` on a real, verified-vertical concrete column element with
   `PERFORM_TYPE: "ELEMS"` (single element, not `"ALL"`) — failed cleanly
   and fast: `{"error": {"message": "failed:Rebar, BeamData"}}`. No hang.
3. Assigned `ModifyMemberType` (`COLUMN`) + `ModifyColumnRebarData` (same
   rebar shape as the earlier reproductions) for that element's section,
   re-ran `doc.analyze()` (succeeded, no issue at this model's larger
   scale) — retried `CC-ANAL` — failed cleanly and fast again:
   `{"error": {"message": "failed:LoadCombination"}}` (the model's 50+
   pre-existing general load combinations were **not** recognized as valid
   design combinations, consistent with reproduction #2). No hang.
4. Ran `ope.generate_load_combination_concrete({"OPTION": "ADD", "DGNCODE":
   "KDS 41 20 : 2022"})` — succeeded, auto-generated proper factored
   combinations from the model's real load cases.
5. Retried `CC-ANAL` a third time on the same single element — **hung
   again**, 40s client timeout, no HTTP response. The user confirmed Gen
   NX was frozen again and required another forced kill.

**This is now the exact, minimal, deterministic trigger pattern across
three independent reproductions** (one synthetic model, one real
production model tested twice): `CC-ANAL` hangs specifically once **both**
(a) the target element/section has member-type + rebar data assigned for
the KDS 41 20:2022 namespace, **and** (b) at least one load combination
exists that the KDS check module itself recognizes as a valid design
combination (i.e., one generated via `ope.generate_load_combination_concrete`
or equivalent, not a plain manually-written `/db/LCOM-GEN` entry). In
other words: it hangs at the exact moment the check has *enough real data
to actually attempt the P-M-interaction calculation* — every precondition
short of that fails fast and cleanly instead.

**Do not call `design.rc_kds.checks.perform_column_check` (`CC-ANAL`)
against a live session with both preconditions satisfied, without an
escape plan** (expect to force-kill Gen NX — "Stop Execution" does not
work). Given the shared "Design Thread" architecture across every other
`perform_*_check`/`*-ANAL` function in this SDK (`perform_beam_check`,
`perform_brace_check`, `perform_wall_check` in the same file;
`perform_steel_code_check` in `steel_kds.py`;
`perform_src_beam_check`/`perform_src_column_check` in
`src_aiksrc2k.py`; `perform_optimal_design`/`OCHECK` variants), **treat
the entire "perform design check" family as carrying the same likely hang
risk once both analogous preconditions are met** until each is
independently tested. This session did not attempt any of the others.

### Reproduction #4 — cleanest case: a natively KDS-configured real model, no forced setup

A fourth session opened a separate, unrelated pre-existing Gen model whose
RC design code was **already** `"KDS 41 20 : 2022"` natively (not forced
onto it like reproductions #2/#3) — `rc_kds.setup.ConcreteDesignCodeOption`
and `rc_kds.rebar.ModifyColumnRebarData` already had real data (4 sections)
before any of this session's calls. This is the most realistic scenario
yet: a normal user, on a normal KDS-native model, checking one column.

1. `CC-ANAL` on a real column element (`PERFORM_TYPE: "ELEMS"`, single
   element) — failed cleanly: `{"error": {"message": " Please perform
   analysis."}}`.
2. `doc.analyze()` via the API returned `"MIDAS GEN NX command complete"`,
   but a subsequent `get_reaction_table()` call still reported
   `"[empty] Cannot generate table data as there is no analysis result."`
   — i.e. the API's "complete" acknowledgment did not reliably mean
   results were actually queryable yet on this larger model (4044 nodes).
   Re-running the analysis **from the Gen NX GUI directly** resolved this
   (reaction table then returned real data) — worth noting as a separate,
   milder finding: don't assume `doc.analyze()`'s response means results
   are immediately queryable for large models; confirm with a cheap
   results call before proceeding, or retry.
3. `CC-ANAL` retried on the same element — the HTTP call hung again (40s
   timeout, no response), and the same "Stop Design Thread — Converting
   Design Results... 0%" dialog appeared. **This time the user also
   checked Gen NX's internal message/log window while it was stuck**, and
   it showed the entire check had already finished:

   ```text
   *** Start Code Checking by KDS 41 20 : 2022.
       End preparing Design Informations.
       End Design/Checking of Member.
       Creating design result file...
       End creating design result file.
       End converting Design Results.
   *** End Code Checking by KDS 41 20 : 2022
   ```

   Every step, including "End converting Design Results" and the final
   "End Code Checking" line, had already logged as complete — while the
   progress dialog was still frozen at 0% on that same step. The user
   clicked Stop Execution; the dialog closed and the app recovered
   cleanly, no forced kill needed this time (unlike reproductions #1–#3,
   where an additional error popup appeared and the app had to be
   force-killed).

**Revised diagnosis: this is very likely a stuck progress-dialog / stale
completion-signal bug, not a genuine backend computation deadlock.** The
underlying KDS code check appears to actually finish — the message log
says so explicitly, end to end — but something (the progress dialog's
own close/refresh logic, and/or whatever signal the Open API layer itself
waits on to consider the request "done" and return an HTTP response)
never fires. That would also explain why the API call kept timing out
even in this 4th case: it's plausibly blocked on the *same* stuck signal
as the dialog, not on the design check itself. Reproductions #1–#3 didn't
have this log checked at the time, so it's unconfirmed whether they were
the same underlying issue or a genuinely different (deadlocked, not just
signal-stuck) failure — worth checking the message log first thing if
this is reproduced again.

**Four for four on the stall itself; consequences vary.** Every attempt
where the check had a real target element with real rebar data, a real
recognized load combination, and real analysis results triggered the same
"Converting Design Results... 0%" stall — including this cleanest case
with no artificial setup at all and, per the log, a design check that had
actually completed. That part is no longer a corner case; it's the
expected outcome of calling `CC-ANAL` for its actual intended purpose in
this Gen NX build. What differs is the outcome: an additional error popup
and a required forced kill 3 of 4 times, vs. a clean recovery via Stop
Execution (with the check apparently having already finished
successfully) the 4th time. **Testing was stopped after this
reproduction** — no further value in repeating it, and most attempts
still cost a forced restart or at least a stuck dialog.

### Confirmed: the check result is actually there — `CC-TABLE` proves it

After reconnecting post-reproduction #4, `get_column_check_table` (`CC-TABLE`)
was called for the same element (371) that the "hung" `CC-ANAL` call had
targeted — **it returned full, real design-check results**:
`CHK_STR: "OK"`, `CHK_RBR: "OK"`, real P-M interaction ratios
(`Rat_P: 0.468`, `Rat_M: 0.151`), real assigned rebar (`"28-6-D25"`), real
shear/hoop-spacing checks — not placeholder or empty data. This
conclusively confirms the diagnosis above: the design check itself
genuinely completes and its results genuinely persist to the model, even
when the triggering `CC-ANAL` call times out with no HTTP response.

**Practical workaround for callers**: if `perform_column_check` (`CC-ANAL`)
times out or the connection errors, **don't assume the check failed** —
retry with `get_column_check_table` (`CC-TABLE`) for the same
element/section shortly after. The check very likely already ran to
completion; only the "done" acknowledgment got lost, not the work.

### Reproduction #5 — retried with Gen NX run as Administrator: same result

To rule out a permissions/UAC-related cause, the user closed Gen NX, relaunched
it with "Run as administrator," reopened the same natively-KDS-configured
model from reproduction #4, and re-ran the full analysis from the GUI before
retrying.

1. `perform_column_check` (`CC-ANAL`) on the same element (371) — the API call
   hung again, timing out client-side after 60s with no HTTP response
   (`MidasConnectionError: ... Read timed out`), and the Gen NX progress
   dialog stalled at "Converting Design Results... 0%" again, same as every
   prior reproduction.
2. The user waited briefly without clicking Stop, then clicked **Stop
   Execution** — the dialog closed and the app recovered cleanly, no forced
   process kill needed (matching reproduction #4's recovery behavior, not the
   forced-kill behavior of #1–#3).
3. `get_column_check_table` (`CC-TABLE`) for the same element immediately
   after — returned the identical full result set as reproduction #4
   (`CHK_STR: "OK"`, `CHK_RBR: "OK"`, `Rat_P: 0.468`, `28-6-D25`, ...),
   confirming the workaround holds here too.

**Conclusion: administrator privileges are not a factor.** The stall, the
Stop-Execution recovery path, and the CC-TABLE workaround are all identical
running elevated vs. running normally — this rules out a UAC/file-permission
explanation for the stuck dialog.

**Build/localization confirmed: this is the English/international build,
not a Korean-localized one.** All five reproductions were run against
**Gen NX 2026 v2.1, English version** — so the stall is not a
Korean-UI-localization artifact; it reproduces on the same build
international users install. What remains genuinely untested is the
**design-code axis**: every reproduction used **KDS 41 20 : 2022**
specifically. It's still an open question — not tested here — whether the
same "Converting Design Results 0%" stall occurs for non-Korean design
codes (AISC, Eurocode, etc., via `steel_kds.py` or other `design/*`
modules) or is somehow specific to the KDS check module's own
implementation. Don't generalize "every `perform_*_check` call hangs" past
KDS 41 20:2022 without independent testing of another code.

### `perform_wall_check` (WC-ANAL) — tested, does NOT reproduce the stall

Using a sixth session (a separate, wall-heavy Korean production model, KDS
41 20:2022 native, with pre-existing real wall-check results already present
from prior GUI use — `WID`/`Story`/`WallMark` rows like `101`/`B1`/`RW1`
with real `CHK_STR: "OK"` data), `perform_wall_check` was tested for the
first time:

1. Single wall/story (`SELECTIONS: [{"WALL_IDS": {"KEYS": [101]}, "STORY":
   ["B1"]}]`) — returned `{"message": "success"}` in **3.5s**. No stall.
2. All walls/stories (`SELECTIONS` omitted) — returned `{"message":
   "success"}` in **5.9s**. No stall.

**`WC-ANAL` does not reproduce the `CC-ANAL` stall**, at least on this
model, in either single-target or full-scope form. This is useful negative
evidence: whatever's stuck in the column-check "Design Thread" progress
dialog is not a blanket property of every `perform_*_check` function in
this file — it may be specific to `CC-ANAL` (or to the member-based
ELEMS/SECTIONS-targeted check family: beam/column/brace, vs. the
WID+STORY-targeted wall check, which may run through different internal
code entirely). Don't assume `perform_wall_check` carries the same risk as
`perform_column_check` going forward.

### `perform_beam_check` (BC-ANAL) — CONFIRMED to hang too, on two separate models, with a new crash variant

Same wall-heavy-model session, real beam rebar data already present
(`ModifyBeamRebarData` had entries for elements `11`, `12`, `13`). Walked
the same precondition sequence as the `CC-ANAL` reproductions:

1. `BC-ANAL` on element 11 before member type was registered in this
   design-code namespace — failed cleanly and fast: `{"error": {"message":
   "failed:Rebar"}}` (`ModifyMemberType.get()` was empty for this
   namespace even though rebar data existed — same "each precondition
   fails independently and cleanly" pattern as the column reproductions).
2. `ModifyMemberType.update({11: {"TYPE": "BEAM"}})` — succeeded.
3. `BC-ANAL` retried — failed cleanly: `{"error": {"message": " Please
   perform analysis."}}` (member-type change invalidated prior results,
   same as CC-ANAL reproduction #1/#4).
4. `doc.analyze()` via the API — **timed out after 90s** with no response.
   This one was just a genuinely long-running solve on this large model
   (4000+ nodes), not the progress-dialog bug — the user confirmed Gen
   NX's own progress UI was actively solving, not stuck. See the
   timeout-guidance note below. After the user re-ran analysis from the
   GUI and confirmed it completed, `BC-ANAL` was retried:
5. `BC-ANAL` retried a third time on element 11 — **hung again**, 60s
   client timeout, no HTTP response. This time the user reported the Gen
   NX app itself looked normal (no visible stuck dialog) — but
   `get_beam_check_table` (`BC-TABLE`) for that *same* element also then
   hung repeatedly (multiple retries, up to 30s each), while `BC-TABLE`
   for a different, nonexistent element (12 — actually absent from this
   model, confirmed by the clean fast `"Element 12 does not exist."`
   response) returned instantly. Basic connectivity (`GET /db/NODE`) also
   remained fully responsive throughout. This points to something
   specifically locked/stuck server-side scoped to *that element's* beam
   check state, even without a visibly stuck dialog — consistent with the
   "stuck signal, not a real deadlock" diagnosis, just manifesting without
   an obvious UI symptom this time.

A **second, independent model** was then opened to rule out anything
specific to the wall-heavy model: a real production Taiwan RC frame
("rahmen") structure, 315 nodes / 564 elements, active design code
`TWN-USD112` (not KDS — so, like reproduction #3, the KDS module's own
`MBTP`/`REBB` tables were empty and had to be populated directly, which
the API allowed with no validation against the model's "actual" active
code, consistent with prior findings):

1. `ModifyMemberType.update({1: {"TYPE": "BEAM"}})` (element 1, a real
   `TYPE: "BEAM"` element, section 11) — succeeded.
2. `ModifyBeamRebarData.update({11: {"ITEMS": [...]}})` (keyed by section
   number 11, matching element 1's `SECT`) — succeeded.
3. `doc.analyze()` — this model is much smaller; completed in **16.4s**,
   and a subsequent `get_reaction_table(load_case_names=["DL(ST)"])` call
   confirmed real, queryable results immediately (no large-model delay
   this time).
4. `ope.generate_load_combination_concrete({"OPTION": "ADD", "DGNCODE":
   "KDS 41 20 : 2022"})` — succeeded, generated a full set of KDS strength
   combinations (`cLCB1`..`cLCB7`+) from this model's real load cases
   (`DL`, `LL`, `EXN`, `EXP`, `EYN`, `EYP`, `EZ`, `WX`, `WY`).
5. `BC-ANAL` on element 1, all preconditions now satisfied on this fresh
   model — **hung again**, 60s client timeout, no HTTP response.
6. This time the user reported the exact text of the crash dialog for the
   first time — *"[Error] Failed to disconnect the work session due to an
   unidentified error. Since you have not logged out, other PCs may have
   limited access to the license. In order to properly terminate the
   program, try to re-execute the program, press 'New Project' and then
   close the program."* — and the application crashed/closed. **The user
   confirmed this is the same popup that appeared during the earlier
   forced-kill `CC-ANAL` reproductions (#1-#3)** — it just hadn't been
   transcribed verbatim before (previously logged generically as "an
   additional error popup"). **The user's stated rule: whenever this
   specific license-work-session-disconnect popup appears, the program
   always dies — there is no recovering from it.** This is a different,
   worse outcome than the clean "Stop Execution" recovery seen in
   reproductions #4/#5 (where this popup did not appear at all).

**This confirms `BC-ANAL` shares `CC-ANAL`'s hang, on two independent
models (one forced-KDS-setup wall-heavy Korean model, one forced-KDS-setup
Taiwan RC frame model), both under the same precondition pattern
(member-type + rebar assigned in the KDS namespace, a KDS-recognized load
combination present, confirmed-queryable analysis results).** Combined
with the earlier `CC-ANAL` reproductions, the observed outcomes now form
two consistent buckets rather than random variation: (a) the "Converting
Design Results" dialog gets stuck but recovers cleanly via Stop Execution,
no popup, no crash (`CC-ANAL` reproductions #4/#5) — the check likely did
finish and its results persist (confirmed via `CC-TABLE`); or (b) the
**"Failed to disconnect the work session"** license-error dialog appears
and the program crashes outright, unrecoverable (`CC-ANAL` reproductions 1
through 3, and this session's Taiwan-model `BC-ANAL` reproduction). This
raises the severity of the underlying MIDASIT bug report beyond "a stuck
progress bar" — outcome (b) is a licensing-visible crash that, per the
dialog's own text, may affect *other PCs'* access to the license until the
process is fully terminated.

### This exact crash signature has a prior precedent — it isn't new to v2.1

A separate, earlier round of live MIDAS Gen NX Open API testing (same
account, a different local project, pre-v2.1 build) independently hit the
**identical** `"Failed to disconnect the work session..."` crash text —
from a completely different trigger: calling `doc/new` rapidly and
repeatedly (back-to-back x10, concurrent x5/x15). That round's writeup
retested the `doc/new` trigger specifically against the v2.1 build and
found it **no longer reproducible**, and closed it out as resolved,
concluding the original crash was "limited to a previous build or a
specific sequence." **This session's `CC-ANAL`/`BC-ANAL` reproductions
show that conclusion was premature** — the same crash signature, verbatim,
resurfaces under a different trigger (a design-check "perform" call) in
the same v2.1 build. This is valuable context for framing a MIDASIT bug
report: not a one-off, but a recurring session-teardown defect that keeps
resurfacing under different trigger conditions across builds and across
independent testing sessions — worth reporting as a *class* of bug rather
than a single reproducible steps list tied to one endpoint.

**Useful diagnostic tool for next time**: that same earlier round
identified `GET https://moa-engineers.midasit.com:443/mapikey/verify`
(note: base URL with the product path — `/gen` or `/civil` — removed) as a
live-verified health-check endpoint, undocumented in the vendored manual,
that reliably distinguishes "AWS relay server alive, Gen NX process alive"
(`status: "connected"`) from "AWS relay alive, Gen NX process died"
(other endpoints then return HTTP 404 with `"Client Disconnected"` /
`"client does not exist"`, while `/mapikey/verify` itself still resolves
against the relay). This wasn't used during today's reproductions — relied
on the user's visual confirmation of the Gen NX window instead — but would
give a definitive, scriptable way to confirm process death vs. a merely
slow/busy session in future reproductions, without waiting on manual
screen-watching.

### `perform_wall_design` (WD-ANAL) — CONFIRMED to hang too, even though the sibling `perform_wall_check` (WC-ANAL) does not

Same wall-heavy model, same wall (`WID 101`, `Story B1`) already confirmed
clean under `WC-ANAL`. `perform_wall_design` (a *different* endpoint,
manual item #48, `WD-ANAL` — RC Wall **Design** Perform, distinct from
`WC-ANAL`'s RC Wall **Check** Perform, item #63) was tested for the first
time:

1. First attempt — failed cleanly and fast: `{"error": {"message": "
   Please perform analysis."}}`. Unrelated `steel_kds`/`src_aiksrc2k`
   member-type writes made earlier in this session (while probing whether
   other design-code modules share the `CC-ANAL` bug — see above)
   apparently invalidated the model's analysis results, consistent with
   the established "any design-parameter write invalidates results"
   pattern.
2. Re-ran `doc.analyze()` — completed in **151.3s** (large model, expected
   per the timeout-guidance note below, not a stall).
3. `WD-ANAL` retried on the same wall/story — **hung**, 60s client
   timeout, no HTTP response. The user checked Gen NX and reported the
   app looked completely normal — no visible stuck dialog this time
   either.
4. `get_wall_design_table` (`WD-TABLE`) for the same wall/story —
   **returned full, real design results** immediately (`Pu: 126.106`,
   `Rat-Py: 0.748`, `phiVn: 1804.81`, `Rat-V: 0.634`, real rebar
   `"D13 @300"`/`"D10 @190"`, `CHK: "OK"`). Same workaround as `CC-ANAL`:
   the design computation completed and persisted; only the HTTP
   acknowledgment never arrived.

**Separate schema finding, unrelated to the hang**: the manual documents
`WD-TABLE`'s response as `{"data": {"COMPONENTS": [...], "ROWS": [{col:
val, ...}, ...]}}` (with a worked example iterating `data["ROWS"]`), but
the live response above came back in the same `{"Result Table": {"FORCE":
..., "DIST": ..., "HEAD": [...], "DATA": [[...], ...]}}` HEAD/DATA shape
every other member-check table in this chapter uses. Confirmed by
re-reading the manual's own JSON Schema and worked example for this
endpoint side by side with the live response — this isn't a caller
mistake. `get_wall_design_table`'s docstring now flags this.

**This means the earlier "WID+STORY-targeted checks are safe" hypothesis
(based on `WC-ANAL` alone) was wrong** — `WD-ANAL` is also WID+STORY-
targeted and still hangs. The safe/unsafe split isn't about the targeting
scheme (`ELEMS`/`SECTIONS` vs `WID`/`STORY`); `perform_wall_check`
(`WC-ANAL`) remains the only tested "perform" function in this file so far
that does **not** reproduce the stall — `perform_column_check`,
`perform_beam_check`, and now `perform_wall_design` all do, across every
model tested. What distinguishes `WC-ANAL` from the other three is still
unclear — possibly that a wall "check" only reads/verifies existing rebar
against demand, while `WD-ANAL`/`CC-ANAL`/`BC-ANAL` all compute and
*write* new required-design data back into the model (rebar layout,
member-check parameter records) — but this is a hypothesis, not confirmed.

### Other design-code modules (steel_kds, SRC) — inconclusive, blocked by license/model limitations, not evidence either way

While looking for a fast way to test whether the `CC-ANAL`-style stall
extends beyond the RC-KDS module, two other design-code "perform check"
families were attempted on the same wall-heavy model and both were blocked
before reaching the actual "perform" call, for reasons unrelated to this
bug:

- **`steel_kds.perform_steel_code_check`**: blocked at the load-combination
  step — `ope.generate_load_combination_steel` returned `{"error":
  {"message": "There is no license to use the specified Steel Design
  Code."}}`. A real license limitation, not a bug; this account/model
  cannot exercise the steel design-check module at all.
- **SRC (`src_aiksrc2k`)**: the design code itself is licensed
  (`ope.generate_load_combination_src` succeeded), but `SrcBeamSectionData`
  (the rebar-equivalent registration for SRC composite beams) returned
  `{"error": {"message": "Unknown Error"}}` on every attempt, and
  `SrcModifyMaterial` writes didn't appear to persist (`GET` came back
  empty afterward). Likely cause: every section in this model is a plain
  rectangular RC shape (`SB`) — SRC (steel-reinforced-concrete composite)
  design plausibly requires an actual composite section geometry that
  doesn't exist anywhere in this model, unlike the RC-KDS rebar overlay
  which worked on any section regardless of the model's "real" design
  code.

**Neither result says anything about whether steel/SRC "perform check"
calls share the `CC-ANAL` stall** — both were blocked upstream of the
precondition chain this file's other reproductions establish as necessary
(member type + rebar/section data + recognized load combination +
queryable analysis results). Testing this properly would need a model with
real steel or SRC composite members, not a forced setup on an RC-only
model. Left as a genuinely open question.

### Timeout guidance for `doc.analyze()` on large models — a separate, milder finding

While waiting on step 4 above, it became clear a plain client-side read
timeout on `doc.analyze()` is not by itself evidence of a hang — on a
4000+ node model, analysis can legitimately take longer than
`MidasClient`'s default 30s timeout (observed: still running past 90s,
with the user confirming Gen NX's own progress UI showed it actively
solving, not stuck). **Don't conflate this with the `CC-ANAL` stuck-dialog
bug** — that one is confirmed via the message log to have a specific
"finished but dialog didn't update" signature; a slow `doc.analyze()` on a
big model is just... slow. Pass a larger `MidasClient(timeout=...)` for
big-model analysis calls rather than treating a timeout as failure.

**Practical takeaway for this SDK**: nothing to fix in `midas-nx` itself —
every request shape sent was correct per the manual (confirmed by the
clean, correctly-shaped `{"error": ...}` responses on every call that
didn't hang, across four separate reproductions on three different
models), and the SDK has no way to add a client-side guard against a
server-side dialog/signal bug it can't see. This is a confirmed,
reproducible Gen NX application defect worth reporting to MIDASIT
directly — most usefully framed as "the KDS column-check progress dialog
gets stuck at 'Converting Design Results 0%' even after the message log
shows the check completed, and the Open API call that triggered it never
receives a response either," together with this file's exact precondition
pattern (member-type + rebar assigned, plus a KDS-recognized design load
combination present, plus confirmed-queryable analysis results) —
reproduced 4 for 4 times that all conditions were met, across a trivial
synthetic model, a production-scale model (twice), and a natively
KDS-configured production model.

## Repeatable smoke test — `scripts/live_smoke.py` (2026-07-22)

Everything above was run by hand, one call at a time. This session turned
the core write → analyze → read round trip (new project, unit, material,
section, node, element, support, load case, self-weight, `doc.analyze()`,
reaction/displacement/beam-force tables, checked against a hand-calc) into
`scripts/live_smoke.py`, then ran it fresh against both a live Gen NX and a
live Civil NX session (same MIDASIT account, both freshly reset via
`/doc/NEW`). Both runs succeeded end to end and reported
`reaction_matches_hand_calc: true`. Confirmed builds (via each app's
About/도움말 dialog): **MIDAS Gen NX 2026 (v2.1), build 06/23/2026** and
**MIDAS Civil NX 2026 (v2.1), build 06/05/2026** — the same v2.1 line as
the English-build Gen NX used in the `CC-ANAL`/`BC-ANAL` reproductions
above, now with an exact build date on record for the first time.
`docs/coverage.json` now tags the ten endpoints this script exercises
(`/doc/NEW`, `/doc/ANAL`, `/db/UNIT`, `/db/MATL`, `/db/SECT`, `/db/NODE`,
`/db/ELEM`, `/db/CONS`, `/db/STLD`, `/db/BODF`) with a `"live_verified"`
field carrying this date and both builds; `ROADMAP.md` surfaces the count
and a Gen/Civil build matrix generated from it (PLAN.md's D4).

New findings from this run, beyond what's already recorded above:

- **The `/post/TABLE` response's top-level key is not stable across
  sessions.** Earlier findings in this file saw it as `"Result Table"`;
  this session got back the literal string `"empty"` for the same
  reaction/displacement/beam-force calls (with `table_name` left at its
  default `""`). Don't hardcode either key — `scripts/live_smoke.py`'s
  `_find_head_data()` scans the response's values for the first dict
  containing both `"HEAD"` and `"DATA"` instead, which is robust across
  whatever this key turns out to be call-to-call.
- **A 200 response can carry an `{"error": ...}` body even from a `DbResource.create()` call, and this is easy to miss if a caller only checks
  the HTTP status.** `live_smoke.py`'s first draft didn't check for this
  and silently treated a failed `Constraint.create()` as successful — the
  fix (checking for an `"error"` key in every 2xx body) is the same
  pattern already noted above for design-code "already exists" responses;
  worth treating as a general rule for every `DbResource`/`doc.*` call, not
  just the design-code family.
- **Gen's concrete `STANDARD` code for C24 is `"KS01(RC)"`, same as Civil**
  — confirmed by first trying the plausible-looking `"KS(RC)"` on Gen,
  which failed with `{"error": {"message": "Unknown Error"}}` (an
  unhelpful message with no hint about the actual problem being the
  standard-code string), then retrying with `"KS01(RC)"`, which succeeded
  immediately. The manual doesn't enumerate valid `STANDARD` strings per
  product, so — as with the original Civil finding above — this is a
  live-only data point, not a schema contradiction.
- **Physically-grounded cross-check, both products**: a 0.6×0.6 m, 3.2 m
  tall C24/KS01(RC) cantilever column's self-weight reaction came back as
  `FZ = 27.113426 kN` on both Gen and Civil (byte-identical, same model) —
  about 4% below a naive hand-calc using a generic 24.5 kN/m³ unit weight
  (`0.36 m² × 3.2 m × 24.5 ≈ 28.22 kN`), implying MIDAS's actual `C24`/
  `KS01(RC)` preset unit weight is closer to `27.113 / (0.36 × 3.2) ≈
  23.53 kN/m³`. Useful reference point for anyone else hand-calc-checking
  a KS01(RC) C24 model; `scripts/live_smoke.py` uses a 5% tolerance for
  exactly this reason rather than an exact-match assertion.

## STATUS UPDATE (2026-07-25) — `CC-ANAL`/`BC-ANAL` ran clean on the same build that hung

The `*-ANAL` design-check stall documented at length above — the single
most severe finding in this file, reproduced across three models and five
attempts, and the reason every `perform_*` docstring in `design/` carried a
"treat as a hang risk" warning — **did not reproduce in a later round of
live use.** Critically, this is **not** a "fixed in a newer build" story.

**Source of this finding.** Unlike the rest of this file, this did not come
from a dedicated SDK test session. It comes from *QuickRebar NX*
(`rebar-repair.vercel.app`), a separate production web tool by the same
author that drives the same Gen NX Open API endpoints over HTTP. Its own
project notes record a live re-test on 2026-07-25 that ran:

- `CC-ANAL` — including the whole-model `PERFORM_TYPE: "ALL"` variant, the
  exact shape that reproducibly killed the app in the reproductions above
- `BC-ANAL` — the beam equivalent, also previously confirmed to hang
- `WC-ANAL` — the wall check, which never reproduced the stall anyway

**4 out of 4 clean, with the app staying connected throughout.**
`PERFORM_TYPE: "ALL"` re-checks an entire model in roughly 2 seconds. The
tool now ships `BC-ANAL` wired to a user-facing "Gen NX 재검토" button,
followed by a `BC-TABLE` read of `CHK_STR` / `Rat-N` / `Rat-P` / `Rat-V` —
i.e. this is not a one-off lab result but an endpoint running in a
deployed tool against real users' models.

### ⚠️ The build did not change — so the trigger is still unidentified

The About dialog was checked on 2026-07-25 and reports **MIDAS Gen NX 2026
(v2.1), build 06/23/2026** — byte-for-byte the same build recorded for the
`CC-ANAL`/`BC-ANAL` reproductions above and for the 2026-07-22 smoke test.
**The same binary both hangs and does not hang.**

That rules out the most comforting explanation (a vendor patch) and leaves
the actual variable unknown. Plausible candidates, none of them tested:

- **Model state.** The reproductions established a precondition chain
  (member type + rebar + a *KDS-recognized* load combination, the last one
  generated via `ope.generate_load_combination_concrete` rather than a
  hand-written `/db/LCOM-GEN`) and hung at the exact point the check had
  enough real data to attempt the P-M calculation. Whether the QuickRebar
  models satisfied that same chain was never checked.
- **Call sequence.** The reproductions ran the check immediately after
  API-side writes of member-type/rebar data; the tool's flow may differ in
  ordering or in how much settles first.
- **Client/transport.** Python `requests` from a local machine vs. Node
  `fetch` from a Vercel serverless function — different timeouts and
  connection handling against the same relay.
- **Genuine intermittency in the trigger.** The defect was already known to
  be intermittent in its *consequences* (forced kill 3 of 5 times, clean
  "Stop Execution" recovery the other 2). Intermittency in the trigger
  itself was assumed absent, but four clean runs do not disprove it.

**Nothing in the reproduction sections above is retracted.** The correct
reading is "this is not universal and not always triggered," not "this is
fixed."

### What this does and does not license

| Endpoint | Earlier status (build 06/23/2026) | 2026-07-25 (same build) |
| --- | --- | --- |
| `CC-ANAL` (column check) | hung 5/5 | ✅ clean 4/4 |
| `BC-ANAL` (beam check) | hung on 2 models | ✅ clean |
| `WC-ANAL` (wall check) | never hung | ✅ still clean |
| `WD-ANAL` (wall **design**) | hung | ❓ **not re-tested** |
| `BRC-ANAL`, steel `CODE-ANAL`, SRC `*-ANAL`, `OCHECK` | never tested | ❓ **not re-tested** |

One further limit on the evidence: **KDS 41 20:2022 only.** Every test on
both sides of this — the original reproductions and the re-verification —
used the KDS RC design code. Nothing here says anything about the steel
(`steel_kds.py`), SRC (`src_aiksrc2k.py`), or non-Korean code paths.

### Keep the defensive pattern — this is now the main takeaway

Because the trigger is unidentified rather than removed, the defensive
pattern is not optional hygiene; it is the actual mitigation. The
production tool wraps these calls this way, and the SDK's docstrings
recommend the same:

- **Short timeout** on the `*-ANAL` call (the tool uses 25s).
- **Read the `*-TABLE` back regardless of whether `*-ANAL` returned.** This
  was the confirmed workaround during the hang era — a timed-out check had
  usually completed and persisted anyway — and it remains the correct shape
  for a call whose HTTP acknowledgment is known to be unreliable.
- **Prefer reading `*-TABLE` alone when possible.** Design results the user
  already computed in Gen NX's own GUI are readable with no perform call at
  all. That path never carried any of this risk and is still the zero-risk
  option.

### Why the docstrings kept the history

The `perform_*` docstrings in `design/` now lead with this re-verification
rather than the old "never call this" rule, but they retain a compressed
version of the reproductions. That is deliberate, and the same-build
finding above is why: this exact crash signature (`"Failed to disconnect
the work session..."`) has now resurfaced twice under *different* triggers
— once via rapid `doc/new` calls on a pre-v2.1 build, once via `*-ANAL` on
v2.1 — and was declared resolved after the first. Treating "did not
reproduce" as "fixed" is the mistake this file has already recorded once,
and the first draft of this very section repeated it by assuming a newer
build was responsible before the About dialog was actually checked.

## 2026-07-26 — read-only sweep reproduced on a real model, same build

Re-ran the whole GET surface with the new `scripts/live_readonly_sweep.py`
(read-only; safe against an open document, unlike `live_smoke.py`) against a
**real production model — 710 nodes, 1272 elements, 60 sections, with
analysis results already present** — on **the same build as the 2026-07-22
session** (Gen NX 2026 v2.1, build 06/23/2026).

| | 2026-07-22 (blank model) | 2026-07-26 (710-node model) |
|---|---|---|
| GET-capable Gen resources swept | 253 | 253 |
| Answered | 233 | 233 |
| Failed (all 404) | 20 | 20 |

Civil NX 2026 (v2.1), build 06/05/2026 was swept the same day and also
reproduced exactly — **293 swept, 273 answered, 20 404s**. The Civil session
had a near-empty document (2 nodes, 1 element), so unlike the Gen run it is a
same-conditions repeat, not a different-model one.

**The failing 20 are the same 20 endpoints**, all `MidasNotFoundError` 404:
the 13 Hyper-S `-M1` routes plus `CMCS`, `EWSF`, `PLCB`, `RCHK`, `SPAN`,
`STRPSSM`, `WVLD`. Run twice in the same session, byte-identical both times.

What this does and does not settle:

- **Model state is eliminated as an explanation.** The two sessions differ in
  everything about the document — empty vs. a real analyzed structure — and
  the failure set did not move by one endpoint.
- **License tier is not.** Same MIDASIT account, same license/edition, same
  build. Per this file's own caveat below, that is not yet the "different
  account" trigger, so **`PRODUCTS` was left unchanged** for the 7
  Gen-fails/Civil-succeeds classes. This section is the second data point;
  a third from a different account or license would be the one to act on.
- Results recorded per endpoint in `docs/coverage.json` (`live_verified`),
  taking the count from 10/390 to 235/390.

### Hyper-S is Civil NX only — the SDK's `PRODUCTS` was wrong

Running both products the same day made this unmissable:

| Hyper-S (`-M1`) endpoint family | Gen NX 2026 v2.1 | Civil NX 2026 v2.1 |
|---|---|---|
| Implemented `-M1` endpoints | 13/13 → **404** | 13/13 → **answered** |
| Undocumented `-M1` stubs | 8/8 → **404** | 8/8 → **answered** |

`/db/ACTL-M1` returned a populated row under Civil, not just an empty table,
so these are live routes rather than registered-but-inert ones.

**Confirmed by the project author**: Hyper-S is the name MIDASIT gave the
solver introduced with the Civil NX release. It is a Civil NX product
feature, so the Gen 404s were correct all along and the SDK's
`PRODUCTS = {"gen", "civil"}` was the defect. All 21 `-M1` rows (13
implemented + 8 stubs) are now Civil-only, via a dedicated `HYPER_S_ONLY`
constant in `db/base.py` and a parametrized guard in
`tests/db/test_hyper_s_products.py`.

**This one is expected to change again.** The author notes Hyper-S may reach
Gen NX in a future release. That is why it is its own constant rather than
`CIVIL_ONLY`: when it happens, widen `HYPER_S_ONLY` and re-run
`scripts/live_readonly_sweep.py --product gen` to confirm, instead of
treating the current state as permanent.

Note this changes the Gen failure accounting for the better. Of the 20 Gen
404s, 13 were never SDK-callable errors at all — they were Civil-only
endpoints the SDK wrongly offered to Gen clients. With `PRODUCTS` corrected,
a Gen sweep covers 240 endpoints with **7** unexplained 404s (`CMCS`,
`EWSF`, `PLCB`, `RCHK`, `SPAN`, `STRPSSM`, `WVLD`), and a Gen client now
raises `ProductMismatchError` before issuing a doomed request.

### The 8 "un-transcribable" Hyper-S stubs are introspectable after all

`docs/coverage.json` carries 8 `-M1` rows as `planned`, not implemented,
because the manual gives a URL, methods and a Zendesk link but no JSON
Schema — and this project's v1.0.0 gate has been waiting on exactly that.
Against a live Civil session, **all 8 answer a plain GET**, and 5 return a
field-level schema from `/info/db/...`:

| Endpoint | `/info/db/...` | Top-level fields |
|---|---|---|
| `/db/STYP-M1` | schema | `STYPE`, `GRAV`, `TEMP`, `ALIGNBEAM`, `ALIGNSLAB`, `MASS_CONTROL` |
| `/db/MATL-M1` | schema | `MATL_NAME`, `MATL_TYPE`, `DAMP_RAT`, `PARAM` |
| `/db/IMFM-M1` | schema | `CONCRETE`, `STEEL` |
| `/db/EPMT-M1` | schema | `NAME`, `MODEL_TYPE`, `TRESCA`, `VMISES`, `MOHRCL`, `DRUCKER`, `MASONRY`, `CONCDMG` |
| `/db/IEHG-BEAM-M1` | schema | `INEL_PROP_NAME` |
| `/db/IEHG-TRUSS-M1` | 404 | GET works, no schema route |
| `/db/IEHG-GL-M1` | 404 | GET works, no schema route |
| `/db/IEHG-PSS-M1` | 404 | GET works, no schema route |

`/db/STYP-M1` and `/db/MATL-M1` also returned real data (`{"STYPE": "3D",
"GRAV": 9.806, ...}`, `{"MATL_NAME": "C24", "MATL_TYPE": "CONC", ...}`).

This does not make them transcribed — server introspection is a different
source from the manual, and `DbResource.info()`'s docstring already frames it
as a fallback rather than a substitute. But the v1.0.0 gate's premise, that
these are "genuinely not transcribable without depending on an external,
non-versioned source", no longer holds: the server itself is the source, and
it is the same server the SDK talks to. Deciding whether that clears the gate
is a call for the author, not something this file should assume.

### The `{"message": ""}` zero-row shape is the common case, not an edge case

Of the 233 endpoints that answered, **176 returned `{"message": ""}` and only
57 returned the keyed `{"<KEY>": {...}}` shape** — on a fully populated model.
A zero-row table is the normal state for most endpoints because a given model
uses a small fraction of the API surface. This matters more than it looks:
`DbResource.items()` assumed the keyed shape and raised `AttributeError` on
the string value, so before v0.12.0 that helper failed on roughly three
quarters of the endpoints it was supposed to serve. Fixed in v0.12.0.

### `/post/TABLE`'s unstable top-level key, explained

Earlier sessions recorded the response key varying between `TABLE_NAME`,
`"Result Table"`, and `"empty"` with no known trigger. It is simply the
default: **omit or blank `TABLE_NAME` and the server keys the response
`"empty"`; pass a name and you get that name back.** Same call, same 78 rows
of real data, both ways:

```text
get_story_drift_table(STORY_DRIFT_X)                     -> keys=['empty'] rows=78
get_story_drift_table(STORY_DRIFT_X, table_name="Drift") -> keys=['Drift'] rows=78
```

`"empty"` is *not* an error marker — it carried a full table here. Matching on
shape (`post.base.unwrap_table()`, v0.12.0) remains the right approach, since
this doesn't explain the `"Result Table"` sighting, but "empty means no data"
is a wrong inference to guard against.

### HTTP 200 with an error body — reproduced deliberately

Sending an unknown `TABLE_TYPE` returns **HTTP 200** with:

```json
{"error": {"message": "MIDAS GEN NX there was an error creating utbl. (ex PostMode ...)"}}
```

This is the failure mode the client silently returned as a result until
v0.12.0; it now raises `MidasResultError`. Confirmed against the live server,
not just reasoned from the docs.

### Two practitioner traps found while probing

- **An invalid load-case name is not an error.** `get_reaction_table(
  load_case_names=["NoSuchCase(ST)"])` returned `{"message": ...}` with zero
  rows — after **23 seconds**. Nothing distinguishes "wrong case name" from
  "genuinely no results" in the response, so validate case names against
  `/db/STLD` before trusting an empty table.
- **Unfiltered result tables can exceed a sane timeout.** The beam-force
  table for all 1272 elements timed out at 30s; the same table filtered to a
  single load case returned 6350 rows in **2.2s**. The displacement table came
  back at 4.1 MB / 39760 rows. Pass `load_case_names` rather than raising the
  timeout.

## 2026-07-26 — write verification on Civil NX, and a table-destroying bug

First session with permission to create, modify and delete freely on Civil NX
2026 (v2.1), build 06/05/2026. `scripts/live_crud_check.py` was written for it:
create → read back → update → read back → delete → confirm gone, per resource.
Read sweeps prove an endpoint answers; only this proves the SDK's *write*
shapes are the ones the server accepts.

### 🛑 `DbResource.delete([id])` was deleting the entire table

The single most serious defect found so far, and it was invisible to every
mocked test in `tests/`.

```text
after create      : [1, 2, 3, 101]
after delete([101]): []              <- expected [1, 2, 3]
```

For `/db/NODE` this also takes out every element attached to those nodes, so
one `delete()` call empties a model. It surfaced by accident: the CRUD run
deleted one throwaway node, and the seeded model was gone afterwards.

**The SDK was following the manual exactly.** `03_DB_Node_Element.md` documents
`DELETE /db/NODE` with `{"Assign": {"4": None}}`, and `db/base.py` had reasoned
carefully about `None` vs `{}` across chapters. Both forms behave the same way
live, and neither one respects the ids:

| Request | Result |
|---|---|
| `DELETE /db/NODE` + `{"Assign": {"3": null}}` | table emptied |
| `DELETE /db/NODE` + `{"Assign": {"3": {}}}` | table emptied |
| `DELETE /db/NODE` + `{"Assign": {"2": {}, "3": {}}}` | table emptied |
| **`DELETE /db/NODE/3`** | **only node 3 removed, and returned** |

The per-id URL is undocumented — `db/base.py` explicitly declined to invent it
("no documented per-ID URL filtering across the manual, so we don't invent
one"). It works, and it is the only form that does what `delete()` claims.
Verified on `/db/NODE`, `/db/STLD`, `/db/LDGR` and `/db/MATL`; deleting an id
that doesn't exist is a harmless no-op returning `{"message": ""}`.

Fixed in v0.14.0: `delete()` issues one `DELETE {endpoint}/{id}` per id, and
the whole-table behaviour is kept under the name `delete_all()`.

### Two more "a 200 is not success" variants

v0.12.0 taught the client to reject a 2xx carrying `{"error": ...}`. Writing
turned up two cases that slip past it:

- **`/doc/ANAL` reports a failed solve as `{"message": "MIDAS CIVIL NX
  Analysis failed."}`** — the same `message` key a successful call uses for
  `"... command complete"`, with no `error` object anywhere. Every result table
  then comes back empty with nothing explaining why. `doc.analyze()` now
  inspects that message; the check is deliberately not in the client, since
  `message` is the normal success carrier elsewhere.
- **`/doc/SAVEAS` returns `{"message": "... command complete"}` for a save
  that did not happen.** Given a path NX rejects it raises a modal *"잘못된
  경로가 있습니다"* dialog, blocks the session until someone clicks it, and then
  answers with the success string. No file on disk. There is no way to tell
  success from failure from the response — check the filesystem.

Note also that error bodies arrive under **201** as well as 200
(`POST /db/CONS` → `201` + `{"error": ...}`), so any check keyed on the status
being exactly 200 misses them.

### `verify_connection()` cannot detect a blocked session

While a dialog was up, `/mapikey/verify` answered `{"status": "connected"}`
in milliseconds while every `/db/*` call timed out. The health check is served
by the relay, not by the blocked application. It tells you the process is alive
and the key is valid — it does not tell you the app can currently answer.

### Field-level findings from the round trips

- **`/db/CONS`'s `CONSTRAINT` must be exactly 7 characters.** Six is rejected
  outright; **eight is accepted and silently truncated to seven**, giving a
  support that was never requested with no error raised.
- **`/db/STLD` ignores the `"Assign"` key and renumbers.** Posting under key
  `7` produced record `2` (`NO: 2`), the next free slot. `/db/NODE` honours the
  key exactly (posting under `77` yields node `77`). So the ID-keyed convention
  is not uniform, and code that writes a record and then reads it back by the
  key it sent will miss for load cases.
- **`create()` is not an upsert.** Re-posting an existing key returns `201`
  with `{"error": ...}` "Key Already Exist".

Round-trip results: **Civil 10/10, Gen 9/9** (`/db/MVCD` is Civil-only and
correctly skipped there) across `/db/GRUP`, `/db/BNGR`, `/db/LDGR`,
`/db/NODE`, `/db/SKEW`, `/db/STLD`, `/db/CNLD`, `/db/BMLD`, `/db/CONS` and
`/db/MVCD` — all create/read/update/delete once the payloads above are right.
The four that failed on the first run were all bad test fixtures (deleted
prerequisites, a 6-character constraint), not SDK defects; that is worth
stating plainly, because a checker that cries wolf gets ignored.

The Gen run doubles as confirmation that the per-id delete fix works there
too, without needing a separate assertion: the `/db/CNLD`, `/db/BMLD` and
`/db/CONS` cases attach to seeded node 1, element 1 and node 2, and they run
*after* the `/db/NODE` case deletes node 101. Under the old whole-table
delete, that one call would have taken the seed with it and all three would
have failed — which is exactly how the bug was found on Civil.

## 2026-07-26 — `/doc/NEW` killed Gen NX once, and nothing explains it

> Read the follow-up sections before acting on this one. The framing here —
> that the old `doc/new` concurrency trigger had returned — did not survive
> testing, and every hypothesis raised below was subsequently eliminated,
> including by reopening the very model involved. The crash is real and the
> mitigation stands; the cause is unidentified.

A single `/doc/NEW` against **Gen NX 2026 (v2.1), build 06/23/2026** with a
real 710-node / 1272-element analyzed model open produced the license
work-session crash dialog and killed the application:

> `[Error] Failed to disconnect the work session due to an unidentified error.`
> `Since you have not logged out, other PCs may have limited access to the`
> `license. In order to properly terminate the program, try to re-execute the`
> `program, press 'New Project' and then close the program.`

The API side reported it correctly and immediately: `POST /doc/NEW -> 404:
Client Disconnected`, surfaced as `MidasNotFoundError`. No hang, no timeout —
the SDK's only involvement was issuing one documented call.

**This reopens a trigger this file had closed.** The section "This exact crash
signature has a prior precedent" records that the `doc/new` trigger was
retested against v2.1, found no longer reproducible, and closed out as
"limited to a previous build or a specific sequence". That conclusion is now
wrong twice over: it was already questioned by the `*-ANAL` reproductions, and
here the original `doc/new` trigger itself reproduces on the current build.

Two things are different from the earlier `doc/new` reproductions, and both
make this worse, not better:

- **It was one call, not a burst.** The earlier round needed back-to-back x10
  or concurrent x5/x15 to trigger it. This was a single request.
- **The document mattered.** `/doc/NEW` had been called perhaps a dozen times
  earlier the same day against small scratch documents on Civil NX with no
  incident. The one that crashed was the first against a large, analyzed,
  loaded-from-disk model.

That points at document teardown of a real model, not at call frequency. It is
one occurrence, so treat the size/state correlation as a hypothesis worth
testing deliberately rather than an established cause — but the "resolved"
label on the `doc/new` trigger should not be restored without a reproduction
attempt on a comparable model.

**Practical consequence, unchanged from the earlier findings:** once this
dialog appears the program always dies, and the license stays checked out
until the process is properly terminated — which per the dialog means
re-running the program, pressing New Project, and closing it cleanly. Do not
point `/doc/NEW` at a session holding a model that matters.

## 2026-07-26 — narrowing the `/doc/NEW` crash, and `/doc/SAVEAS` looks broken

### What the `/doc/NEW` crash is *not*

Four controlled runs against Gen NX 2026 (v2.1, build 06/23/2026), each
building the document through the API so only one variable moves:

| Document under `/doc/NEW` | Result |
|---|---|
| 2-node scratch | ✅ 3.1s |
| 710 nodes / 1339 elements, API-built | ✅ 3.6s |
| 750 nodes / 1300 elements, API-built, **solved, reactions readable** | ✅ 4.1s |
| 710 nodes / 700 elements, **saved then reopened from disk** | ✅ 4.1s |
| 710 nodes / 1272 elements, the user's real model, opened from disk, solved | 🛑 crash |

Four candidate causes tested and **all four eliminated**: the product being
Gen, model size, the presence of analysis results, and the document being
disk-backed. The last of those was the leading hypothesis after the first
three fell, and it did not survive contact with a controlled test — a document
saved via `/doc/SAVEAS` and reopened via `/doc/OPEN` tore down cleanly.

What still separates the one document that crashed:

- **Content, not size.** It carried 60 sections, 3 materials, structure and
  boundary groups, story data, load combinations, rebar data, and 190 design
  members each for RC/steel/SRC. Every test model had one material, one
  section and no design data at all.
- **Session history.** That session had served two full 253-endpoint read
  sweeps plus dozens of ad-hoc probes over several hours before the crash. The
  clean runs were minutes old.

Both are testable; neither is cheap, since each attempt costs a crash and a
license recovery. Recorded as the two surviving hypotheses rather than picked
between.

#### The session hypothesis, and why it is now the leading one

The project author proposed a mechanism for the second one that fits the
evidence better than anything model-side: **the server retains a record of the
existing session, and a later request is read as a second client connecting**,
so the session/licence layer refuses the teardown. Three things support it:

1. **The dialog only ever talks about sessions and licences.** It says nothing
   about the model — which is what you would expect given that four
   model-side variables have now been eliminated by experiment.
2. **The original documented trigger was literally concurrency.** The earlier
   pre-v2.1 round reproduced this crash with `doc/new` called *concurrently*
   x5/x15. That was filed here as an obsolete build-specific quirk; under this
   hypothesis it is the same defect seen from the other end, and the "resolved"
   label was hiding a mechanism rather than a fixed bug.
3. **NX runs on a separate machine**, reached through MIDASIT's relay, so
   there really is distributed session state to get out of sync — this was not
   understood when the earlier notes were written.

What does *not* yet fit: Gen and Civil were both connected on the same account
(`sjj0507@midasit.com`, distinct `connectionID`s) during the four clean
`/doc/NEW` runs as well as the crash, so two products sharing an account is
not sufficient on its own.

The one session-level difference that survives: the crashed session was the
**original long-lived connection** — hours old, two 253-endpoint sweeps and
dozens of probes deep — while every clean run happened on a freshly restarted
NX process minutes old.

#### Tested: the historical concurrency trigger does NOT reproduce

Run against a trivial empty document on the same build, reproducing the
pre-v2.1 pattern exactly, each phase followed by a health check:

| Phase | Result |
|---|---|
| 10 back-to-back `/doc/NEW`, no pause | 10/10 fine |
| **5 concurrent** `/doc/NEW`, separate clients | 5/5 fine (18.6s) |
| **15 concurrent** `/doc/NEW`, separate clients | 15/15 fine (59.5s) |

Session stayed healthy throughout, same `connectionID`, app responsive after
every phase. So **concurrency alone does not do it**, and the earlier round's
`doc/new`-burst trigger really does look fixed on v2.1 — the "resolved" label
was right about *that pattern*, even though the endpoint can still crash.

This corrects the framing in the section above, which read the single-call
crash as evidence that the concurrency trigger had returned. It had not. What
they share is the endpoint and the crash text, not the route to it.

Where that leaves the two hypotheses: the session-age one is weakened (an
idle-but-old session is still untested, but burst load on a fresh one is
clean), and **model content is now the leading candidate by elimination**.
Every clean run — including 30 `/doc/NEW` calls across these phases — was
against a document with one material, one section and no design data.

#### Tested: the model is innocent, and so is session load

The decisive test was run — the user reopened the exact model that crashed,
on the same build, same account, same machine:

```text
nodes 710 · elements 1272 · materials 3 · sections 60 · constraints 44
load cases 5 · load combos 6 · structure groups 3
RC design members 190 · beam rebar 31
    /doc/NEW -> {"message": "MIDAS GEN NX command complete"}  (3.7s)
    session survived
```

**No crash.** Model content is eliminated too.

Session load was then tested on its own: two full read sweeps back to back
(~480 calls) followed by `/doc/NEW` — the shape of what preceded the original
crash. Also clean, 4.5s.

So every variable isolated so far is eliminated:

| Hypothesis | Verdict |
|---|---|
| Product being Gen | ✗ |
| Model size | ✗ |
| Analysis results present | ✗ |
| Document loaded from disk | ✗ |
| Request concurrency (10 serial / 5 / 15 parallel) | ✗ |
| Model content (**the very model that crashed**) | ✗ |
| Accumulated session load (~480 calls) | ✗ |

#### What this most likely is

This now matches the pattern already recorded in this file for `CC-ANAL` /
`BC-ANAL`: reproducible five times out of five, then clean on the same build
with nothing changed. Two different endpoints, the same crash text, the same
inability to pin a trigger. Reading them as one intermittent defect in
**session teardown** explains more than any per-endpoint story does — and it
is consistent with everything eliminated above, all of which is about the
document rather than the session.

Untested combinations remain (rich model *and* heavy session load together —
yesterday's actual state; or wall-clock session age measured in hours rather
than call count). But the useful conclusion for this SDK does not depend on
resolving that:

- **Treat `/doc/NEW` and `*-ANAL` as calls that can kill the application**,
  regardless of what the document holds. There is no precondition to check.
- The mitigation is unchanged and is not going to improve: don't point them at
  a session holding work that isn't saved, and expect to restart the product
  and recover the licence when it happens.
- For a vendor report, the honest framing is a **class** of intermittent
  session-teardown failure across `/doc/NEW` and `*-ANAL`, with this file's
  elimination table attached to show what it is *not*. That is more useful
  than a steps-to-reproduce list nobody can run.

### 🧭 Every path in this API belongs to the machine running NX, not yours

The single most useful thing learned today, and it cost five failed
`/doc/SAVEAS` attempts to notice.

The API is reached through MIDASIT's relay at `moa-engineers.midasit.com`, so
the NX process answering your calls **may be on a different computer entirely**
— it was here. Every path-valued field is therefore resolved on *that* machine:

- `/doc/SAVEAS`, `/doc/OPEN`, `/doc/IMPORT*`, `/doc/EXPORT*`
- `EXPORT_PATH` on every `/post/TABLE` call and every design report/image call
- image capture paths in `/view/*` and `/ope/*`

Writing to `C:/Users/<your-windows-account>/Documents/...` fails when that
account exists only on your machine. The failure is quiet in the worst way:

| Path sent | Response | What actually happened |
|---|---|---|
| `C:/Users/Dennis/Documents/x.mgbx` (local account) | `command complete`, 58.2s | modal "invalid path" dialog on the NX machine, blocking until dismissed |
| `C:/Users/sjj0507/Documents/x.mgbx` (NX machine's account) | `command complete`, 0.4s | saved |

**Both answers are byte-identical.** The only signals are the latency — a
blocked dialog inflates it — and, decisively, whether the file is really
there. Checking `os.path.exists()` from the calling script proves nothing; it
is looking at the wrong filesystem. `/doc/OPEN` on the path you just wrote is
the check that works, since it asks the same machine.

The manual repo's `examples/javascript/auto-save-before-analysis.html` already
warns about this — *"%USERPROFILE% 같은 환경변수는 MAPI 서버(Gen NX 프로세스)가
인식하지 못합니다"* — and derives the folder from the account name in
`/mapikey/verify`'s `user` email (`sjj0507@midasit.com` → `sjj0507`). That is
the right pattern: **ask the server who it is, then build the path.**

Two corrections to earlier drafts of this file, kept because the reasoning
error is instructive:

- `/doc/SAVEAS` is **not** broken. It was writing files correctly the whole
  time, to a machine this script could not see.
- Its response is still not proof of success — but the reason is the dialog,
  not the endpoint.

Same lesson for `.mgbx`: the manual's example still shows the pre-NX `.mcb`,
and Gen NX 2026 writes `.mgbx`. That turned out not to be what was failing
here, but the example extension is stale regardless.

## 2026-07-26 (later) — 🛑 `POST /db/NMAS` kills Civil NX, deterministically

The first crash in this file with a **reproducible one-call trigger**. Read it
alongside the `/doc/NEW` section above, whose "cause unidentified, survives
every hypothesis" conclusion it partly supersedes: the license dialog those
sections treat as an unexplained session-teardown symptom can now be produced
on demand.

```text
POST /db/NMAS  {"Assign": {"3": {"mX": 1.0, "mY": 1.0, "mZ": 1.0}}}
```

Civil NX 2026 (v2.1), build 06/05/2026. Four reproductions, no exceptions.
The call times out, **every** subsequent `/db/*` call times out, and the
application raises

> [Error] Failed to disconnect the work session due to an unidentified error.
> Since you have not logged out, other PCs may have limited access to the
> license.

and exits — holding the license until the product is re-run, `New Project` is
pressed, and it is closed properly. A second dialog names it outright:
*"Program will be closed due to an unexpected problem."*

Where NX puts its crash-recovery file varies with the document, and one of the
two locations it chose is unusable. Twice it tried
`C:\Program Files\MIDAS\MIDAS CIVIL NX\DgnPlugIn\_restore.mcb` and was
refused, since a standard account cannot write there; on the fourth
reproduction it wrote to the user's `Downloads` folder successfully. So
auto-recovery is not universally broken here — but it fails silently in the
Program Files case, which is worth knowing before relying on it. That is an
install-level problem, separate from the crash.

### The three reproductions, and why the third one settles it

| # | Preceding activity | `/doc/NEW`? | Idle | Outcome |
|---|---|---|---|---|
| 1 | full `core` + `boundary` tiers; `/db/SDSP` create→update→delete completed immediately before | yes | none | died on `/db/NMAS` |
| 2 | `verify_connection`, `GET /db/NODE` (10 nodes), `GET /db/NMAS` (`{}`) | no | **~32 min** | died on `/db/NMAS` |
| 3 | `/doc/NEW`, seed model, `GET /db/NODE`, **control `POST /db/CNLD` (0.1s)**, `GET /db/CNLD` | yes | none — 20s-old session | died on `/db/NMAS` |
| 4 | `POST /db/NODE`, **`POST /db/SKEW`, `POST /db/CONS`**, `GET /db/NMAS`, `GET /db/NODE` — five calls at 0.08–0.17s each, all within the 1.3s before | **no** | none | died on `/db/NMAS` |

Two competing explanations were raised. Both are excluded by the table.

**An idle work-session timeout**, since a ~32-minute absence sat in front of
reproduction 2. It does not survive the evidence.

- In run 2 itself, **three `/db/*` calls succeeded after the idle gap** and one
  of them returned all ten nodes. Those are answered by the application, not
  the relay, so the work session was alive.
- The narrower variant — "the first *write* after a long idle is what dies" —
  is excluded by run 1, where `/db/NMAS` was nowhere near the first write:
  100+ calls including dozens of writes had already succeeded, and `/db/SDSP`
  had just completed a full round trip.
- Run 3 then removes the confound entirely: a 20-second-old session, a control
  write to a *sibling* static-load endpoint succeeding in 0.1s, then this one
  call taking the session down.

**A blocking save-changes dialog**, since `/doc/NEW` raises one on a document
with unsaved changes, and this file already records that any modal dialog
freezes the whole API session rather than the one call. Reproduction 4 was run
specifically to test it: **no `/doc/NEW` anywhere in the run**, so nothing
could raise that dialog, and it worked on node ids 9001/9002 so the open
document was left alone. Three writes and two reads returned in 0.08–0.17s
each inside the 1.3 seconds before the call — which also excludes a dialog
raised by anything else, because a modal would have frozen those five too.
`POST /db/NMAS` died exactly as before.

The dialogs that appear *afterwards* are consistent with the crash rather than
an explanation of it: NX raises the license and "unexpected problem" dialogs on
its way out.

`GET /db/NMAS` and `/info/db/NMAS` are unaffected. Nothing about the payload is
unusual — three unit masses on a plain seeded node — and `/info/db/NMAS` lists
exactly the fields being sent. **This is a product defect, not a wrong request
shape in this SDK.**

### `verify_connection()` reports "connected" throughout

Worth restating because it was measured twice in a row here, 0.5s each time,
while `GET /db/NODE` timed out at 15s in between. The health check is served by
the relay. It confirms the key is valid and the connection record exists; it
tells you **nothing** about whether the application can answer.

### What was done about it

- `NodalMassPayload` in `db/static_loads.py` carries the warning, with the
  recommendation to use `LoadsToMass` (`/db/LTOM`) where the mass can be
  derived from loads instead.
- `scripts/live_crud_check.py` **quarantines** the case: `Case.crashes` marks
  it, it is skipped by default and reported as `SKIP`, and running it needs an
  explicit `--include-crashers`. It is also last in its tier, so opting in
  costs only that one case rather than the seven that sat behind it in run 1.
- The checker now aborts the whole run the moment a failure looks like a lost
  session (`client does not exist`, or a read timeout) instead of grinding
  through the remainder. Run 1 spent two 30s timeouts and six 404s reporting
  "failures" against an application that had already exited.

Untested on Gen NX. Do not assume it is Civil-only, and do not assume it is
version-specific on this evidence alone.

## 2026-07-26 (later) — write verification, tiers 2-6: 40 of 43 cases confirmed

`scripts/live_crud_check.py` grew from 11 cases to 43, grouped into six tiers
ordered by what a modelling script actually reaches for. Confirmed live on
Civil NX 2026 v2.1 the same day: **40/43**, across five runs. The three that
are not confirmed each have a recorded reason, and none of them is an SDK
defect: `/db/NMAS` crashes the product, `/db/TDMT` refuses every payload
server-side, and `/db/TMAT` cannot be reached without `/db/TDMT`.

> Superseded later the same day, and the numbers below are the v2.1 state, not
> the current one. `/db/TDMT` was **not** refusing anything server-side — the
> `CODE` value was wrong; it and `/db/TMAT` both round-trip, taking this to
> **42/43** on v2.2. See the two later sections.

Newly proven round trips (create → read → update → read → delete → read):

| Tier | Endpoints |
|---|---|
| `props` | `/db/THIK` `/db/ESSF` `/db/SECF` `/db/TSGR` `/db/TDME` |
| `boundary` | `/db/NSPR` `/db/GSTP` `/db/GSPR` `/db/ELNK` `/db/RIGD` `/db/MCON` `/db/FRLS` `/db/OFFS` `/db/SSPS` — 9/9 first time out |
| `static` | `/db/SDSP` `/db/LTOM` `/db/NBOF` `/db/FBLD` `/db/PSLT` `/db/PRES` `/db/ETMP` `/db/NTMP` — 8/8 once `/db/NMAS` was quarantined out of the way |
| `stage` | `/db/STAG` `/db/TMLD` `/db/CRPC` `/db/CMCS` |
| `moving` | `/db/LLAN` `/db/MVHL` `/db/MVHC` `/db/MVLD` |

Still unconfirmed: `/db/NMAS` (quarantined, above), `/db/TDMT` (below) and
`/db/TMAT` (blocked by `/db/TDMT`).

The quarantine paid for itself immediately: the seven `static` cases that had
never been *reached* — they sat behind `/db/NMAS` in the crashed run, and were
never evidence of anything — all passed once it was skipped and moved last.
Six on the first attempt, `/db/PRES` after the fix below.

### 🛑 `/db/SECF` is keyed by section id, and the SDK said element id

`db/properties/section.py` documented `/db/SECF` ("Section Manager -
Stiffness") as keyed by element id. It is keyed by **section** id.

| Request | Response | Stored |
|---|---|---|
| `POST /db/SECF` `{"Assign": {"3": {...}}}` (element 3) | 200, no error | **nothing** |
| `POST /db/SECF` `{"Assign": {"1": {...}}}` (section 1) | 200 | the record, echoed back in full |

The wrong-key form is silent — no error object, no message, nothing to notice
except reading back and finding an empty table. Since this project's TypedDicts
are explicitly documentation rather than runtime validation, a wrong comment
here *is* the defect; corrected in the docstring, with the evidence.

The fixture found it on purpose: the case was deliberately keyed to element 3
with a note saying a "missing after write" failure would mean the key was a
section id, because the manual's worked example keys it `9001` right next to
`/db/STRPSSM`'s `9003`, and `/db/STRPSSM` *is* section-keyed.

### `/db/MVHL` stores a user-defined vehicle when asked for one [superseded]

`VEHICLE_LOAD_NUM` must be `1` for a standard-DB vehicle. Send `2` and NX
**discards `VEHICLE_TYPE_NAME` and `STANDARD_CODE`** and stores a user-defined
"Truck/Lane" vehicle instead, with a 200 and no error:

```text
sent    {"MVLD_CODE": 6, "VEHICLE_LOAD_NAME": "KR(SRB)_DB-18",
         "VEHICLE_LOAD_NUM": 2, "VEHICLE_TYPE_NAME": "DB-18",
         "STANDARD_CODE": "KS-RB", "VEH_DEFAULT": {"DYN_LOAD_ALLOWANCE": 0, ...}}
stored  {"MVLD_CODE": 6, "VEHICLE_LOAD_NAME": "KR(SRB)_DB-18",
         "VEHICLE_LOAD_NUM": 2, "USER_LOAD_TYPE": "Truck/Lane",
         "VEH_DEFAULT": {"UNIFORM_LOAD": 0, "PL": 0, "PLM": 0, "PLV": 0}}
```

With `VEHICLE_LOAD_NUM: 1`, `DB-18`, `DB-24` and `DL-24` all store correctly
under `STANDARD_CODE: "KS-RB"`. This joins `/db/CONS` truncating an 8-character
`CONSTRAINT` and the empty-`VEH_DEFAULT` no-op as a **silent data-corruption**
shape: the only defence is to read the record back and compare.

> **Superseded 2026-09-03.** The observation reproduces exactly and the
> record above is what the server stores. The conclusion drawn from it does
> not hold: `VEHICLE_LOAD_NUM` is the endpoint's branch discriminator, `2`
> selects the user-defined vehicle, and discarding `VEHICLE_TYPE_NAME` and
> `STANDARD_CODE` is that branch behaving as documented - the KSCE-LSD15
> article added a `"VEHICLE_LOAD_NUM": 2` User Defined example on
> 2026-07-30, three days after this was written. Sent properly, branch 2
> loses nothing. This is not a data-corruption case and does not belong
> beside `/db/CONS`. See the 2026-09-03 entry at the end of this file for
> the measured branch table and for what *is* wrong, which is requiredness.

Also resolved: `/db/MVHC`'s `VEHICLE_LD_NAMES` takes the vehicle's
`VEHICLE_LOAD_NAME` (`"KR(SRB)_DB-24"`), not the type name (`"DB-18"`) the
manual's worked example shows.

### ⚠️ `/db/PRES`'s documented default `DIRECTION` is rejected

`DIRECTION` is documented (manual and SDK alike) as defaulting to `"NORMAL"`.
On a 4-node PLATE with `FACE_EDGE_TYPE: "FACE"` — the commonest pressure load
there is — Civil NX 2026 v2.1 rejects it:

```text
[Error] Errors detected in Pressure Loads Data.(Item:Load Direction)
```

**Omitting `DIRECTION` fails identically**, which confirms the default is
applied and the default is unusable. Working values on that same element:

| `DIRECTION` | Result |
|---|---|
| `LZ` (element local z — normal to the plate), `LX`, `GZ` | accepted |
| `VECTOR` with `VECTORS: [0, 0, -1]` | accepted |
| `NORMAL` | `(Item:Load Direction)` |
| `NORMAL_PLANE`, `NORMAL_ELEM`, `GLOBAL_Z`, `LOCAL_Z` | `Wrong Field` |

The two error strings separate the cases again: `"NORMAL"` earns the specific
"Load Direction" complaint rather than the generic `Wrong Field` that the
invented spellings get, so it *is* a recognised enum value — presumably valid
for some other `ELEM_TYPE`/`FACE_EDGE_TYPE` pair. For plate faces, pass `"LZ"`.

Two smaller notes from the same endpoint: the server echoes `FORCES` back with
five entries where the manual's example sends four, and `/info/db/PRES` gives
its `maxItems` as 5; and `/info/db/PRES` carries a `PSLT_KEY` field (a
`/db/PSLT` reference) that the manual chapter does not document.

Also on `/db/PSLT`: the manual spells `ELEM_TYPE` `"Plate/PlaneStress(Face)"`
in its worked example and `"Plate/Plane Stress (Face)"` in its Specifications
prose. This section originally concluded the unspaced form was "the one the
server accepts" — **that was wrong**, and it was inferred from the CRUD case
passing with the unspaced form without ever sending the spaced one. Both are
accepted (checked on v2.2, see the final-verification section). The manual's
inconsistency is cosmetic.

### ⚠️ The manual's only documented time-dependent-material code name is rejected

`"KDS2016"` — the value in the manual's worked example, its Python example and
its `NAME` field for both `/db/TDMT` and `/db/TDME` — is not accepted by Civil
NX 2026 v2.1. Probed against `/db/TDME`:

| `CODENAME` | Result |
|---|---|
| `CEB-FIP(2010)`, `CEB-FIP(1990)`, `Ohzagi` | accepted |
| `ACI` | accepted **once `A`/`B` are supplied** |
| `KDS2016`, `KDS(2016)`, `KDS`, `KCI-2007`, `Korea Standard` | `Wrong Field` |
| `KDS-2016` | recognised, but still rejected even with `A`/`B` |

The two error strings are diagnostic and worth knowing:

- `"Wrong Field"` — the code name is not one the product knows.
- `"[Error] Time Dependent Material(Comp. Strength) input data contain errors."`
  — the name *was* recognised; the code's own conditional fields are missing.

### ⚠️ `/db/TDMT` looked server-side broken and was not — see the correction below

Recorded as written at the time, because the reasoning error is the useful
part. `/db/TDMT` answered `201` + `{"error": {"message": "Wrong Field"}}` to
the manual's worked example, to every code name `/db/TDME` accepts, to each
documented field removed in turn, and to a bare `{"NAME": "C"}`; `PUT`
behaved the same; `/info/db/TDMT` listed every field being sent; and an
`{"Argument": ...}` body was refused with a *different*, correct error. From
that this file concluded "looks server-side".

That conclusion was wrong. Nothing about it was server-side — the `CODE` value
was simply not one this endpoint accepts, and "Wrong Field" is what it says
when it cannot resolve `CODE`. Resolved further down: **"Wrong Field" from
these endpoints means the code name is unknown, not that a field name is
wrong**, and the message being about "Field" is actively misleading. The
lesson worth keeping: an exhaustive-looking elimination sweep over the fields
proves nothing when the bad value is in a field you never varied.

### Fixture design rules, and why they earned their keep

Two rules, both paid for by the first run:

1. **Seed at the lowest free key, let the case take the next one.** Definition
   tables disagree about honouring the `"Assign"` key — `/db/NODE` honours it,
   `/db/STLD` and `/db/TDME` renumber to the next free slot (posting `/db/TDME`
   under keys 10/15/16/18 produced ids 1/2/3/4). Seeding first and taking the
   next sequential key makes both behaviours land on the same id. Where a
   record is referenceable by name — groups, spring types, lanes, vehicles —
   the fixtures use the name and the question never arises.
2. **Seed steps are per-case dependencies, not per-tier.** The first run
   blocked all 7 `props` cases behind the one `/db/TDMT` seed failure, though
   only `/db/TMAT` needed it. Four of those seven pass. A checker that reports
   6 false blockages out of 7 gets ignored, which is the whole point of
   separating **regression** (a confirmed case broke → SDK defect suspect,
   exit 1) from **unverified** (never passed → triage the fixture, exit 3)
   from **blocked** and **skipped**.

The classification held up: across three runs every single failure resolved to
a fixture defect, a documented-value defect, or a product defect — and none to
an SDK behaviour defect. The one SDK defect found was a wrong docstring
(`/db/SECF`), which no amount of round-tripping would have caught if the case
had been keyed correctly by accident.

## 2026-07-26 (later still) — Civil NX v2.2: nothing changed

The user upgraded to **MIDAS Civil NX 2026 (v2.2), build 06/18/2026** — a
version bump, not a reinstall of the crashing build — and the whole checker
was re-run against it.

### The 40 confirmed round trips are unchanged

`live_crud_check.py --product civil` gave a byte-identical verdict on v2.2:
**40/43**, zero regressions, the same three exceptions. That is worth having
on its own — it is the first evidence in this project that the SDK's write
shapes survive a Civil NX version change, and the endpoints in
`docs/coverage.json` now cite v2.2 as their verified version. (The same 40
passed on v2.1 build 06/05/2026 earlier the same day; the `nx_versions` field
holds one build per product, so it names the newer one.)

### 🛑 `/db/NMAS` reproduction #5 — the upgrade did not fix it

Same protocol as reproduction #4, deliberately: no `/doc/NEW` anywhere in the
run, control writes immediately before, node ids 9001+ so the open document is
untouched.

```text
[  0.6s] OK    POST /db/NODE 9001-9005 (fixture)      (0.11s)
[  0.7s] OK    CONTROL POST /db/SKEW 9001             (0.11s)
[  0.8s] OK    CONTROL POST /db/CONS 9002             (0.11s)
[  0.9s] OK    CONTROL GET  /db/NODE  (t-0)           (0.08s)
[ 15.9s] FAIL  POST /db/NMAS 9001                     (15.01s)  read timeout
[ 31.4s] FAIL  GET  /db/NODE                          (15.47s)  read timeout
```

The probe was written to keep going if the call had survived — five more
`POST`s, a `PUT`, a `DELETE` and a read-back — precisely so that a clean
result would not rest on one lucky call. It never got there.

**This is now five reproductions across two versions.** It matters because of
the precedent this file already records: `CC-ANAL`/`BC-ANAL` were reproducible
five times out of five and then ran clean on the *same* build with nothing
changed, and `/doc/NEW`'s crash never got a trigger at all. `/db/NMAS` is not
that. It is deterministic, it is one call, the payload is three unit masses on
a plain node, and a vendor version bump did not touch it.

Practical consequence: **do not wait for this to be fixed by upgrading**, and
the vendor report is worth actually sending — see the crash section above for
the evidence to attach.

### `/db/TDMT` is not version-specific either

Still `201` + `{"error": {"message": "Wrong Field"}}` on v2.2, for the manual's
own worked example. Whatever is wrong with that endpoint survived the same
upgrade, which removes "stale build" as an explanation and makes it worth
reporting alongside the crash rather than sitting on it.

## 2026-07-26 (later still) — `/db/TDMT` solved: the code-name enums differ

`/db/TDMT` and `/db/TDME` sit next to each other in chapter 04, take a code
name each, and **do not share a code-name enum.** That is the whole answer, and
it cost most of a session to find because a `Wrong Field` error pointed at the
fields rather than at the value.

Probed live on v2.2 with the CEB-FIP field set (`MSIZE`/`CTYPE`) and the ACI
field set (`VOL`/`CMETHOD`), 16 candidate names each:

| `CODE` on `/db/TDMT` | Result |
|---|---|
| `European` | accepted with either field set |
| `AASHTO` | accepted with either field set |
| `ACI` | accepted with `VOL`/`CMETHOD` |
| `Russian` | recognised — "input data contain errors", so it wants other fields |
| `CEB-FIP`, `CEB-FIP(2010)`, `CEB-FIP(1990)`, `CEB-FIP(1978)`, `CEB FIP` | `Wrong Field` |
| `Ohzagi`, `KDS-2016`, `KDS2016`, `Korea`, `KCI-USD12`, `JTG3362-2018` | `Wrong Field` |

So **MIDAS calls the CEB-FIP-based creep/shrinkage model `"European"` on this
endpoint**, and every CEB-FIP spelling is rejected — while `/db/TDME` accepts
`CEB-FIP(2010)`/`CEB-FIP(1990)`/`Ohzagi` and rejects `European`-flavoured
guesses. The manual's chapter blurb for `/db/TDMT` — "CEB-FIP(2010/1990/1978),
ACI, KDS 등" — describes a set of names the endpoint does not take. Stored
records come back with `CODE` upper-cased (`"European"` → `"EUROPEAN"`).

The two error strings are the same diagnostic pair seen on `/db/TDME`, and they
are the fastest way to triage this class of endpoint:

- `"Wrong Field"` → the **code name** is unknown. Vary the value, not the fields.
- `"[Error] ... input data contain errors."` → the name is recognised; the
  code's own conditional fields are missing or wrong.

With `CODE: "European"`, `/db/TDMT` round-trips, and `/db/TMAT` — which links a
`/db/TDMT` and a `/db/TDME` record **by name** — round-trips after it. That
takes the checker to **42/43 confirmed**, leaving only the `/db/NMAS` crash.

One more self-inflicted fixture defect on the way there, worth recording
because it is the exact rule this file lays out two sections up: `/db/TMAT`'s
update pointed `TDMT_NAME` at `TDMT_CRUD`, the record the `/db/TDMT` case
creates *and deletes*, so the update earned a `Wrong DB Name` for a reason that
had nothing to do with `/db/TMAT`. Fixed by seeding two creep/shrinkage records
(`TD_SEED`, `TD_SEED_2`) that outlive the tier and switching between them.

### What this changes about the vendor report

`/db/TDMT` comes **off** the product-defect list and moves to the manual team:
the endpoint works, its documented code names don't. What is worth reporting as
a product-side issue is the error text — `"Wrong Field"` for an unrecognised
*value* sends the reader to inspect field names, which is what happened here.

## 2026-07-26 (later still) — v2.2 re-check of the v2.1-only findings

Three findings had only ever been seen on v2.1 (build 06/05/2026) and were
about to be sent to MIDASIT on that basis. Re-run on v2.2 (build 06/18/2026)
before sending. Two hold, one does not.

| Finding | v2.1 | v2.2 |
| --- | --- | --- |
| `/db/CONS` silently truncates an 8-character `CONSTRAINT` to 7 | reproduces | **reproduces** |
| `DELETE {endpoint}` + ID-keyed `"Assign"` empties the whole table | reproduces | **reproduces** |
| `/db/MVHL` no-ops on an empty `VEH_DEFAULT: {}` | reproduces | **does not reproduce** |

### `/db/CONS` — and the response lies too

The truncation is unchanged, and re-checking it turned up something the
original write-up missed: **the POST response echoes the 8-character string
back**, while the stored record holds 7.

```text
POST /db/CONS {"Assign": {"3": {"ITEMS": [{"ID": 1, "CONSTRAINT": "11111111"}]}}}
  response -> {"CONS": {"3": {"ITEMS": [{"ID": 1, "CONSTRAINT": "11111111"}]}}}   8 chars
  GET      -> {"3": {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "CONSTRAINT": "1111111"}]}}   7
```

So the immediate response cannot be used to detect it either — a separate GET
is the only signal. Six characters is still rejected outright, so the asymmetry
is the real complaint: too short errors, too long is silently cut.

### `DELETE` — measured on v2.2, and it is as bad as recorded

```text
before  NODE 10, ELEM 4
        DELETE /db/NODE {"Assign": {"21": null}}     one node named
after   NODE 0,  ELEM 0                              the model is gone

before  STLD ['1', '2']
        DELETE /db/STLD {"Assign": {"1": {}}}        one load case named
after   STLD []

        DELETE /db/NODE/502                          the per-id form
        -> {"NODE": {"502": {...}}}, 501 and 503 untouched
```

One detail worth having: the response body returns **every** record it deleted,
so the response does reveal the over-deletion — after the fact. `delete()`
already uses the per-id URL, so nothing changes in the SDK.

### `/db/MVHL`'s empty `VEH_DEFAULT` — fixed, so it comes out of the report

On v2.2 the record saves and `VEH_DEFAULT` comes back populated with
`{"DYN_LOAD_ALLOWANCE": 0, "CENT_F": false}` — the product now fills the
defaults instead of discarding the write. Removed from the vendor report's
silent-write-failure list, since sending a claim that does not reproduce on the
current build costs credibility for the ones that do; kept in the report's
appendix as a note that it appears resolved, and the `VehicleDefaultParams`
docstring now scopes the warning to v2.1.

This is the argument for re-checking before reporting rather than after: the
same sweep that confirmed two findings retired a third and sharpened one of
the two.

## 2026-07-26 (final) — every vendor-report claim re-checked in one pass

Before sending anything to MIDASIT, all 16 claims were re-run against a single
v2.2 session (build 06/18/2026) **in ascending order of severity** — the
documentation items first, then the response conventions, then the silent
write failures, then the destructive `DELETE`, and the crash last. Ordering it
that way matters: the crash ends the session, so anything after it would go
unverified.

**14 of 16 reproduced.** The two that did not are the useful part.

### ❌ Retracted: `/db/PSLT`'s `ELEM_TYPE` spelling was never a defect

Both `"Plate/PlaneStress(Face)"` and `"Plate/Plane Stress (Face)"` are
accepted. The earlier claim that only the unspaced form works came from the
CRUD case passing with that form — the spaced form was never sent. That is an
inference dressed up as a finding, and it is exactly the failure mode this file
already records for `/db/TDMT`: **do not conclude anything about an enum from
one value working.** Removed from the vendor report.

### ⚠️ `A-4` failed its own check, not the claim

The assertion required two probes to both return an error body, and one of them
(`POST /db/CONS` with a 3-character `CONSTRAINT` on a node that does not exist)
returned `201` with no error at all. The claim itself is confirmed by the other
probe — `POST /db/TDMT` → **`201`** + `{"error": {"message": "Wrong Field"}}` —
and by `PUT /db/TMAT` → **`200`** + `Wrong DB Name` earlier the same day. Bad
test, good finding; the report's example list was corrected rather than the
claim.

That stray `201`-with-no-error on a nonexistent node is itself suspicious as
another silent no-op, but it was not checked with a follow-up GET and is not
claimed anywhere.

### `/mapikey/verify` is stale, not permanently wrong

Worth correcting because the report said it reports `"connected"` for a dead
application. It does — but not forever. Measured immediately after two crashes:
`"connected"`. Measured after this crash, roughly 30 seconds later and after
two 15s timeouts had elapsed: **`"disconnected"`**. So the relay's connection
record catches up; there is a window in which it lies. The report now says
that instead.

### Confirmed unchanged on v2.2

`/db/TDMT`'s code-name enum (B-1), `/db/TDME`'s (B-2), `/db/SECF`'s section
key (B-3), `/db/PRES`'s rejected `"NORMAL"` default and its 5-entry `FORCES`
(B-4, B-7), `/db/MVHC`'s `VEHICLE_LD_NAMES` — which rejects a vehicle *type*
name with `Unknown Error` (B-5) — `/db/STLD`'s renumbering, where a POST under
key `7` produced id `3` (B-6), the `"Wrong Field"` vs "input data contain
errors" split (A-6), all three silent write failures (A-3a/b/c), `DELETE`
emptying `/db/NODE` from 10 nodes and 4 elements to zero from a single named id
(A-2), the per-id form working correctly (A-2b), and **`POST /db/NMAS` killing
the application — reproduction #6** (A-1), with the three control calls
immediately before it all returning normally.

## 2026-07-27 — 🛑 four of the seven "documentation defects" were **ours**, not MIDASIT's

Before sending the vendor report, every B-item was re-checked against the
**official Zendesk articles** (`support.midasuser.com`, JSON Manual section
`30087500371097`) fetched that day — not against `E:\AI Study\MIDAS-API`.
That distinction is the whole finding. The vendored manual is a *curated
transcription*; section B had been written against it, so wherever the
transcription was wrong, we were about to accuse MIDASIT of our own error.

**B-1 `/db/TDMT` `CODE` — retracted.** The official article
([Creep/Shrinkage](https://support.midasuser.com/hc/en-us/articles/35808006330009))
documents a complete, exact 28-value enum: `CEB_FIP_2010`, `CEB`,
`CEB_FIP_1978`, `ACI`, `PCA`, `COMBINED`, `AASHTO`, `JSCE_12`, `JSCE_07`,
`JSCE`, `JAPAN`, `INDIA_IRC_18_2000`, `INDIA_IRC_112_2011`, `EUROPEAN`,
`AS_5100_5_2017`, `AS_5100_5_2016`, `AS_RTA_5100_5_2011`, `AS_3600_2009`,
`NEWZEALAND`, `RUSSIAN`, `CHINESE`, `JTG`, `CHINA_JTG3362_2018`, `KDS_2016`,
`KSI_USD12`, `KSCE_2010`, `KS`, `USER_DEFINED`.

The 16 values swept on 2026-07-26 were **`NAME` values read as `CODE` values**.
In the official example, `"NAME": "CEB-FIP(1990)"` sits directly above
`"CODE": "CEB"` — `NAME` is the free-text label, `CODE` is the enum. Every
"rejected CEB-FIP spelling" recorded above was a string the official article
never proposes for that field. `"European"` was not a discovery; `EUROPEAN`
is documented, and the match is case-insensitive.

**B-2 `/db/TDME` `CODENAME` — retracted.** The official article
([Compressive Strength](https://support.midasuser.com/hc/en-us/articles/35808102389401))
gives `"KDS-2016"`. `"KDS2016"`, the value probed and reported as rejected,
appears in **neither** official article — it is a vendored-copy error.

So the two endpoints do differ, and interestingly: `/db/TDMT` takes
`UNDERSCORED_UPPERCASE` tokens, `/db/TDME` takes the display string
(`CEB-FIP(2010)`, `KDS-2016`, `European`). Both are documented correctly and
in full. That the SDK's own seeds already use `CODENAME: "CEB-FIP(2010)"` and
pass live is confirmation, not coincidence.

**B-3 `/db/SECF` — retracted.** The official article is titled *Section
Manager - Stiffness* and never states what the `"Assign"` key means; it just
uses `9001`/`9002` as example keys. "Keyed by element id" was **our own
docstring**, already corrected in `db/properties/section.py`. The live finding
(section id is the right key) stands; the accusation does not.

**B-7 `/db/PRES` — retracted.** The official Specifications row reads
`"FORCES"  Array [Number, 5]`, and all four official examples carry five
entries. `PSLT_KEY` **is** present in the official JSON Schema. Both halves
described the vendored chapter, not the source.

**B-4 `/db/PRES` `DIRECTION` — narrowed, not retracted.** Footnote ¹⁾ of the
official article carries an availability matrix that documents the live
behaviour exactly: for `"PLATE"` + `"FACE"`, Normal is `-` while Local x/y/z,
Global X/Y/Z and Vectors are `O`. What survives is much smaller: the
Specifications row still marks `DIRECTION` *Optional, default `"NORMAL"`*,
which cannot hold for the one combination where `NORMAL` is unavailable —
hence omitting the field fails.

**B-5 and B-6 stand**, B-6 rephrased as an omission: the official `/db/STLD`
article marks `"NO"` *Read Only* and never says what the `"Assign"` key does,
so renumbering contradicts no published statement — it is undocumented, which
is a weaker and more accurate claim.

### The rule this produces

**Never cite the vendored manual as "the documentation" in anything sent
outside.** It exists to be corrected; `E:\AI Study\MIDAS-API`'s own CLAUDE.md
says it deliberately normalizes official typos and marks them `⚠️`. For an
internal decision it is the right source. For a claim *about MIDASIT's
documentation*, fetch the article and quote it. Four of seven claims died on
contact with the source, and the two that survived got weaker.

Still open: a live re-test with the official values (`CODE: "CEB_FIP_2010"`,
`"KDS_2016"` on `/db/TDMT`; `CODENAME: "KDS-2016"` on `/db/TDME`). It was not
possible on 2026-07-27 — the relay answered `client does not exist`, no
session. The retractions do not depend on it (dropping an unverified
accusation is the safe direction), but if any official value *does* fail,
that is a genuine product defect and a new A-item.

## 2026-07-29 — Gen NX v2.1 (build 07/28/2026): `props`/`boundary`/`static`/`stage` get their first Gen CRUD run, `/db/CMCS` corrected to Civil-only

*(Dated 2026-07-27 in an earlier draft of this section — wrong. This work
happened in the same conversation as the section above but after a real
multi-day gap; git's own commit timestamps settled it: `7f63ea6` and
`456d4fa`, the two commits from this session, are both stamped 2026-07-29.)*

New Gen NX install, new MAPI key, `scripts/live_crud_check.py --product gen`
(no `--include-crashers`). **Correction to get right before it goes stale:**
this was not the checker's first exposure to Gen NX — the `core` tier's own
comment already says "the baseline proven live on 2026-07-26 (Civil 10/10,
Gen 9/9)", and that 2026-07-26 Gen pass is what let `/db/TDMT` and
`/db/TDME` inherit `confirmed=True` in the first place. What today actually
added: the **`props`, `boundary`, `static` and `stage` tiers ran against Gen
for the first time** (27 endpoints), on top of `core` repeating clean. Of
those, `/db/TDMT`/`/db/TDME` are worth calling out specifically — they use
the seeds already fixed in the 2026-07-27 section above
(`CODE: "European"`, `CODENAME: "CEB-FIP(2010)"`), so this is the first
live confirmation of those *specific* values on a Gen session, not just
Civil. `/db/NMAS` stayed quarantined; not run.

First pass: 36/38 confirmed cases passed. **`/db/CMCS` came back a
REGRESSION** — `confirmed=True` in the checker, but that flag was earned on
Civil NX runs only; the `stage` tier had never touched Gen before today.
Before treating it as an SDK defect: `/db/CMCS` is one of the 7 endpoints
already flagged twice in this file (2026-07-22, 2026-07-26) as "manual says
gen+civil, but 404s under Gen in practice" — and both those were GET-only
read sweeps, deliberately left unactioned pending a third, independent data
point per this file's own caveat.

This run is that third point, on a different session (new build, new day)
and with **stronger evidence than either prior one** — an actual `POST`
attempting to create a record, not just a `GET` against an empty table. Same
account as before (`sjj0507@midasit.com`), so it doesn't clear the
stricter "different account" bar floated in the 2026-07-26 section, but it
does satisfy the caveat's actual rule below ("different session" is listed
as sufficient), and three same-account reproductions across seven days and
three separate sessions is not a coincidence worth waiting out further.

**Action taken:** `CamberConstructionStage.PRODUCTS` changed from
`{"gen", "civil"}` to `CIVIL_ONLY` in `db/construction_stage.py`, the
`live_crud_check.py` case given `products=("civil",)` so a future Gen run
skips it instead of false-flagging, and its mocked test switched from
`gen_client` to `civil_client`. The other 6 endpoints in that original list
(`EWSF`, `PLCB`, `RCHK`, `SPAN`, `STRPSSM`, `WVLD`) were **not** exercised by
`live_crud_check.py`, so this run added no new evidence for *them* — but see
2026-07-29's read-only sweep below, which closed that gap the same day.

**Re-run after the fix: 36/37, clean — 0 regressions, 0 unverified failures,
0 blocked**, `/db/CMCS` correctly filtered out for a Gen client rather than
skipped-and-counted. `docs/coverage.json` updated in bulk for all 36 passing
endpoints: `live_verified.products` gained `"gen"`,
`live_verified.nx_versions.gen` set to `"MIDAS Gen NX 2026 (v2.1), build
07/28/2026"`, date bumped to 2026-07-29. `/db/CMCS`'s own entry instead
dropped `"gen"` from top-level `products` (now `["civil"]`, matching
`PRODUCTS`) and its `live_verified` note records the three-session Gen 404
history.

## 2026-07-29 (later) — 🛑 `POST /db/NMAS` also crashes Gen NX: not a Civil-specific defect

With the user's explicit go-ahead, `--include-crashers --tier static` was run
once against the fresh Gen NX v2.1 (build 07/28/2026) session — the first
time this case has ever touched Gen. It crashed on the **first attempt**:

```
POST /db/NMAS -> 404: Client Disconnected (Hint: either the product isn't
connected ... or the id you asked for doesn't exist in the current model)
```

A follow-up `GET /db/NODE` a few seconds later confirmed the session was
actually gone, not just this one call rejected: `404 {"error": {"message":
"client does not exist"}}` — the exact string Civil NX gives after this same
crash. The user restarted Gen NX, pressed New Project, and reconnected;
`GET /db/NODE` on the new session returned `200 {"message": ""}` (empty
document), confirming recovery.

This settles the question left open in the 2026-07-26 Civil section: the
crash is **not** a Civil NX peculiarity. Six reproductions on Civil (two
versions) plus one on Gen (first-ever attempt, different build entirely,
different product) is the same failure on both of MIDASIT's NX flagship
products through what must be a shared write path. Not re-running this
again — one clean reproduction on Gen matching Civil's exact signature is
enough; further attempts just burn licenses for no new information.

**Updated everywhere this was recorded as Civil-only:** `CLAUDE.md`,
`NodalMassPayload`'s docstring in `db/static_loads.py`, the `crashes=` note
on the case in `live_crud_check.py`. The vendor report's A-1 needs the same
correction before it's sent — "Civil NX 한정" understates it.

## 2026-07-29 (later) — full read-only re-sweep on the new Gen NX build closes the remaining 6

With the NMAS-on-Gen question settled, the user asked what else the new Gen
NX patch was worth re-checking. `scripts/live_readonly_sweep.py --product
gen` — the same read-only GET sweep from 2026-07-22 and 2026-07-26 — was
re-run against **Gen NX 2026 v2.1, build 07/28/2026**, a session and build
distinct from both prior ones.

**239 GET-capable resources swept, 233 ok, 6 errors — the exact same 6, byte
for byte:** `EWSF`, `PLCB`, `RCHK`, `SPAN`, `STRPSSM`, `WVLD`, all
`MidasNotFoundError` 404 with the identical hint text. No drift, no new
failures, no fixes from the patch. (`CMCS` wasn't part of this sweep at
all — it's correctly excluded now that its `PRODUCTS` is Civil-only.)

That is the third independent reproduction this file's own caveat asked for
on these 6 — same bar `/db/CMCS` cleared a few hours earlier, same account,
different session and build each time (2026-07-22, 2026-07-26, 2026-07-29).
**Action taken:** all 6 classes' `PRODUCTS` changed from `{"gen", "civil"}`
to `CIVIL_ONLY` — `RebarCheckInput` (`db/design.py`), `PreCompositeSection`
and `WaveLoad` (`db/misc_loads.py`), `Span` (`db/project.py`),
`SectionStressPoints` and `EffectiveWidthScaleFactor`
(`db/properties/section.py`) — each with the same dated docstring note as
`CamberConstructionStage`. Their 6 mocked tests switched from `gen_client`
to `civil_client` (they were asserting a request shape against a product
that, per this finding, can't actually take that request).
`docs/coverage.json`'s top-level `products` for all 6 corrected to
`["civil"]` to match, and their `live_verified.method` notes now record the
three-session history the same way `/db/CMCS`'s does.

This closes out the "20 Gen 404s" accounting from the 2026-07-26 section
above for good: 13 were Hyper-S (corrected in v0.13.0), and these final 7
(`CMCS` plus these 6) are now all confirmed Civil-only after three
independent sessions apiece. Nothing in that original list of 20 remains
unexplained.

## 2026-07-29 (later still) — `/db/NMAS` reproductions #2 and #3 on Gen NX: 9/9 overall, confirmed on a real production model

The user asked to go back to `/db/NMAS` one more time, specifically on Gen
NX. Two more reproductions followed, back to back, each requiring the full
license-recovery cycle (restart, New Project, close properly) before the
next could run.

**Reproduction #2 (Gen, scratch document):** `scripts/live_crud_check.py
--product gen --tier static --include-crashers`, same throwaway-model setup
as the first Gen crash. This time the script's own `_session_lost` check
caught it inline and aborted the run immediately, rather than needing a
follow-up probe:

```
FAIL    /db/NMAS     create=FAIL
!! ABORTED: the product stopped answering at /db/NMAS — MIDAS NX is hung or
gone, so nothing after this point was tested
error: "POST /db/NMAS failed: ... Read timed out. (read timeout=60.0)"
```

A 60s timeout on the call itself this time, rather than the first crash's
immediate `404 Client Disconnected` — a different wire-level symptom, same
outcome.

**Reproduction #3 (Gen, real production model):** the user opened an actual
work file — not a scratch document — and asked to `GET /db/NMAS` against it
first (safe; returned `{"message": ""}`, no masses defined). Then,
explicitly confirming the model was already saved, asked to `POST` it.
Rather than risk the model's own node numbering, this run reused the
established protocol from `docs/vendor_repro_nmas.py` (control writes/reads
immediately before the target call, node ids 9001+ so nothing in the real
model is touched, no `/doc/NEW` anywhere):

```
[  1.0s] 201   POST /db/NODE 9001,9002        (0.56s)
[  1.4s] 201   POST /db/SKEW 9001             (0.47s)
[  1.9s] 201   POST /db/CONS 9002             (0.49s)
[  2.3s] 200   GET  /db/NMAS (target table)   (0.41s)  {"message": ""}
[  2.7s] 200   GET  /db/NODE                  (0.40s)
[ 18.1s] TIMEOUT  POST /db/NMAS 9001          (15.35s)
[ 18.5s] 404   GET /mapikey/verify            (0.39s)
[ 33.8s] TIMEOUT  GET /db/NODE                (15.34s)
```

Same shape as every prior reproduction: three control calls immediately
before the target call all returned normally in under 0.6s each, the target
call itself timed out, and everything after was dead. **This is the first
Gen NX reproduction against real production data**, which matters the same
way the Civil real-model evidence did earlier in this file: it rules out
"only happens on synthetic/throwaway test data" as an explanation. The user
had saved the model beforehand, so the crash cost a restart cycle, not work.

**Running total after this section: 9/9 — six on Civil NX, three on Gen NX,
zero survivals.** Every file that recorded this as "Civil NX" or cited a
specific reproduction count has been updated: `CLAUDE.md`,
`NodalMassPayload`'s docstring in `db/static_loads.py`, the `crashes=` note
in `live_crud_check.py`. The vendor report's A-1 gets this as its strongest
piece of evidence yet — see below.

## 2026-07-29 (still later) — `/db/NMAS` reproduction #10, on a freshly updated Civil NX build

The user installed a new Civil NX build the same day — v2.2 (build
07/28/2026), one build newer than the v2.2 (06/18/2026) build already on
record — and asked for a fresh round of checks before trusting it, ending
with a repeat of the NMAS reproduction to see if the build update happened
to fix it.

Read-only sweep first (293 GET-capable Civil resources, 273 ok / 20 error).
All 20 errors were 404, on both `GET` and the schema-only `/info/db/...`
probe (a control call, `Node.info()`, succeeded on the same session) — that
rules out "no data in this model" as the explanation, since a schema probe
doesn't touch model data at all. The 20: `/db/STOR`, `/db/SWIND`,
`/db/SSEIS`, `/db/POSP`, `/db/EPST`, `/db/DRLS`, `/db/SDHY`, `/db/SDIS`,
`/db/REBB`, `/db/REBR`, `/db/REBW`, plus 9 design-chapter endpoints —
`/DESIGN/RC/KDS-41-20-2022/{MATD,REBB,REBC,REBR,REBW,TRFT,ULCT}`,
`/DESIGN/SRC/AIK-SRC2K/MATD`, `/DESIGN/STEEL/KDS-41-30-2022/ULCT`. 11 of
these had previously been `live_verified` as `ok` specifically on **Gen NX**
(2026-07-26) and had never been probed live on Civil before — so this reads
as a first-time signal that these may actually be Gen-only (the SDK
currently declares `PRODUCTS={"gen","civil"}` for all 20), not a build
regression; coverage.json shows no prior Civil `live_verified` entry for any
of them. **Not acted on** — per the caveat below, one session's evidence isn't
enough to flip a `PRODUCTS` frozenset; the trigger to revisit these 20 is an
independent reproduction (different session/account, or a fresh Civil
document via `live_crud_check.py`'s throwaway-model setup) confirming the
same 404s. Separately, `scripts/check_manual_drift.py` found the
vendored manual repo two commits stale — the Story Drift `X_DIR`/`X-DIR`
contradiction (`21_POST_StoryTables.md`) was officially corrected by the
vendor (unified on the underscore spelling, type confirmed `Object`), so
`post/story.py`'s `StoryDriftVerticalLine(s)Selection` TypedDicts and their
tests were updated to match and the hyphen fallback was dropped;
`vendored_at_commit` bumped to `aeca67553dd078e2057f2ab5e87fe3391775e6ac`
and re-confirmed `has_diff: false`. The other stale file
(`04_DB_Properties.md`'s TDMT/TDME `KDS2016` correction) needed no code
change — the SDK already had the corrected values. Then
`scripts/live_crud_check.py --product civil` (all six tiers, `/db/NMAS`
auto-skipped): 42/42 non-quarantined cases passed, matching the existing
42/43-confirmed baseline with zero regressions from the build update.

Finally, with the user's explicit go-ahead, `--tier static
--include-crashers`:

```
PASS    /db/ETMP     create=ok read_back=ok update=ok read_updated=ok delete=ok read_deleted=ok
PASS    /db/NTMP     create=ok read_back=ok update=ok read_updated=ok delete=ok read_deleted=ok
FAIL    /db/NMAS     create=FAIL
!! ABORTED: the product stopped answering at /db/NMAS — MIDAS NX is hung or
gone, so nothing after this point was tested
error: "POST /db/NMAS failed: ... Read timed out. (read timeout=60.0)"
```

Same shape as every prior reproduction: a plain throwaway model, seven calls
that all passed immediately before it, then a 60s timeout on the `POST
/db/NMAS` call itself and the session gone. **The 07/28/2026 Civil build
does not fix this.**

**Running total after this section: 10/10 — seven on Civil NX (across three
version/build combinations), three on Gen NX, zero survivals.** Updated the
same three files as the prior count bump: `CLAUDE.md`, `NodalMassPayload`'s
docstring in `db/static_loads.py`, the `crashes=` note in
`live_crud_check.py`.

## 2026-07-29 (later yet) — `/db/NMAS` reproduction #11: a from-scratch minimal model rules out the "floating substructure" hypothesis

Before reproduction #10 (above), the user raised a legitimate structural-
engineering objection: every single reproduction to date had written the
mass to, or alongside, a node with no restraint and no connecting element —
`vendor_repro_nmas.py`'s node 9001 gets a `SKEW` (a local-axis rotation, not
a restraint) but no `CONS` and no element, so it is a literally free-
floating point in space; `live_crud_check.py`'s seed model targets node 3
(which *is* connected, via the beam chain back to node 1's fixity), but the
same model also permanently carries an entirely unrestrained, disconnected
plate (nodes 5-8) and, during the `static` tier, an unrestrained floating
node pair (21/22) left over from the `boundary` tier. A structural model
with an unrestrained, disconnected substructure has a singular stiffness
matrix (rigid-body modes with no associated stiffness) — if `POST
/db/NMAS` triggers any internal mass-matrix or modal bookkeeping, an
iterative solver hitting that singularity hanging instead of erroring out
cleanly is a real, previously-documented class of defect in commercial FEA
software. This was a serious enough alternative explanation to test before
trusting the vendor report's framing.

**Test**: build a deliberately minimal, structurally clean model directly
on the (already-blank, from the prior reproduction) open document — no
`/doc/NEW` — with nothing floating anywhere: node 1 (fixed, `CONS`
`"1111111"`), node 2 (free), one `BEAM` element connecting them, one
material, one section. The mass target, node 2, is unrestrained itself but
fully connected via the beam — a textbook, kinematically determinate
cantilever, not a mechanism, and the *only* thing in the document.

```
[  0.7s] OK      Unit                           (0.29s)
[  0.8s] OK      Material                       (0.12s)
[  0.9s] OK      Section                        (0.10s)
[  1.0s] OK      Node 1,2                       (0.15s)
[  1.2s] OK      Element (beam 1-2)             (0.16s)
[  1.3s] OK      Constraint (fix node 1)        (0.12s)
[  1.4s] OK      GET /db/NMAS (target table)    (0.09s)  {"message": ""}
[  1.5s] OK      GET /db/NODE                   (0.08s)
[ 48.3s] ERROR   POST /db/NMAS node 2           (46.85s)  404: Client Disconnected
[ 48.3s] OK      GET /mapikey/verify            (0.01s)
[ 48.3s] ERROR   GET /db/NODE                   (0.01s)  404: client does not exist
```

**Died identically.** The user watched it happen on screen this time (a
first for this investigation) and captured the exact sequence: the
in-app dialog read verbatim `[Error] Failed to disconnect the work session
due to an unidentified error. Since you have not logged out, other PCs may
have limited access to the license. In order to properly terminate the
program, try to re-execute the program, press 'New Project' and then close
the program.` — matching every prior paraphrase of this dialog exactly —
followed by a second, previously-undocumented dialog: `Program will be
closed due to an unexpected problem. The recovered file is saved in
[C:\Program Files\MIDAS\MIDAS CIVIL NX\MIDAS CIVIL NX\DgnPlugIn\_restore.mcb]`,
itself followed by an access-denied error for that exact path — the
crash-recovery autosave attempted to write under `Program Files` and was
denied, the same class of unchecked-write-permission issue as A-7 in the
vendor report (a different endpoint's report path), now also seen in the
crash handler itself. The model tree, visible on screen right before the
crash, confirmed the model was built exactly as intended: 2 nodes, 1 beam
element, 1 material, 1 section, 1 support — nothing else.

**This rules out model topology as an explanation.** A model with no
disconnected or unrestrained component anywhere, built from exactly the
fields the manual documents, dies the same way as every messier fixture
before it. The defect is in `/db/NMAS`'s write handling itself, not
triggered by a singular stiffness matrix elsewhere in the document.

**Running total after this section: 11/11 — eight on Civil NX (three
version/build combinations, one of them this minimal-model run), three on
Gen NX, zero survivals.** Updated `CLAUDE.md`, `NodalMassPayload`'s
docstring in `db/static_loads.py`, the `crashes=` note in
`live_crud_check.py`, and `docs/vendor_report_ko.md`'s A-1 section (which
now cites this reproduction explicitly as the rebuttal to a "malformed
model" explanation).

## 2026-07-29 (later still) — `/db/NMAS` reproduction #12: calling-machine location doesn't matter either

The user set up a second machine for this investigation: "A PC" runs Gen NX
itself plus a Codex CLI instance, both on the same host/LAN; this repo and
every prior reproduction had been run from a separate dev machine ("B PC"),
reaching Gen NX only through the public relay
(`moa-engineers.midasit.com`). Codex on A PC built its own client on top of
this SDK and called `POST /db/NMAS` — and it did not crash. That result, on
its own, would have reopened everything: eleven reproductions had already
ruled out idle timeouts, modal dialogs, and model topology, but never
whether the request's network path (same-LAN-as-the-product vs. a remote
relay round trip) was the actual variable.

Before trusting it, the target node needed to be checked. Asked for the
exact call, the user reported the response was `[Warning] DTO_NMAS.999999
The command is ignored because the specified node does not exist in the
model` — node `999999` was never created in the open document. Every prior
reproduction (this file's and `docs/vendor_repro_nmas.py`'s alike) creates
the target node with `POST /db/NODE` immediately before writing its mass,
specifically so the write reaches the actual crash-prone code path rather
than an earlier existence check. A's "success" was a clean, correct
rejection of bad input — evidence the validation layer works, not evidence
the write path is safe.

To settle it, `docs/vendor_repro_nmas.py --product gen` (unmodified, the
same script already used for reproduction #3 against a real production
model) was run from B PC once more, immediately after getting the Gen
MAPI-Key:

```
[  0.9s] 201      POST /db/NODE 9001,9002        (0.51s)
[  1.3s] 201      POST /db/SKEW 9001             (0.44s)
[  1.8s] 201      POST /db/CONS 9002             (0.46s)
[  2.2s] 200      GET  /db/NMAS (대상 테이블)      (0.41s)  {"message": ""}
[  2.6s] 200      GET  /db/NODE                  (0.40s)
[ 18.0s] TIMEOUT  POST /db/NMAS 9001             (15.37s)
[ 18.4s] 404      GET /mapikey/verify            (릴레이만 응답)
[ 33.7s] TIMEOUT  GET /db/NODE                  (15.35s)
```

Died identically — and the user immediately confirmed Gen NX on A PC had
also gone down ("죽음"), from a call made on B PC. **That is the decisive
part**: A PC and B PC were both looking at the same live Gen NX session
the whole time, so a crash triggered from B PC killed the process A PC was
using. Calling-machine location cannot be the variable — there was only
ever one process, and it dies regardless of which machine's HTTP request
reaches it, as long as the target node actually exists.

**Running total after this section: 12/12 — eight on Civil NX, four on Gen
NX, zero survivals.** Updated `CLAUDE.md`, `NodalMassPayload`'s docstring in
`db/static_loads.py`, the `crashes=` note in `live_crud_check.py`, and
`docs/vendor_report_ko.md`'s A-1 section with a fourth excluded hypothesis
(calling-machine location).

## 2026-07-29 (final) — `/db/NMAS`'s actual root cause: omitting `rmX`/`rmY`/`rmZ`

A PC's Codex instance built its own client on this SDK and reported one
more data point: `POST /db/NMAS` with `{"mX": 1.0, "mY": 1.0, "mZ": 1.0,
"rmX": 0.0, "rmY": 0.0, "rmZ": 0.0}` — all six fields, not just the three
this file's every prior reproduction sent — succeeded, verified with a GET
and cleanly deleted afterward. That is a real difference in payload shape,
not a location or SDK-version effect (the previous section had already
shown A PC and B PC hit the identical Gen NX session), so it needed
isolating properly rather than accepted at face value.

**First check: same session, immediately after A PC's success, from B PC.**
`docs/vendor_repro_nmas.py --product gen` (unmodified — omits rmX/rmY/rmZ,
same as every prior reproduction) was run right away and died on the same
live session A PC had just used successfully:

```
[  0.9s] 201      POST /db/NODE 9001,9002        (0.51s)
[  1.3s] 201      POST /db/SKEW 9001             (0.44s)
[  1.8s] 201      POST /db/CONS 9002             (0.46s)
[  2.2s] 200      GET  /db/NMAS (대상 테이블)      (0.41s)  {"message": ""}
[  2.6s] 200      GET  /db/NODE                  (0.40s)
[ 18.0s] TIMEOUT  POST /db/NMAS 9001             (15.37s)
```

Same live process, same account, minutes apart: full fields survived,
omitted fields died. That is close to conclusive on its own, but the two
calls used different HTTP clients (A PC's Codex-built client vs. this
repo's `requests`-based script), so a same-tool, same-session A/B was still
worth doing before rewriting the payload contract.

**Same-session A/B, one script, two nodes, Gen NX (after a restart):**

```
--- 1) node 9101, full fields (mX,mY,mZ,rmX=0,rmY=0,rmZ=0) ---
[  3.7s] 201      POST /db/NMAS 9101 (full fields)   {"NMAS": {"9101": {...,"rmX":0,"rmY":0,"rmZ":0}}}
[  4.1s] ...GET /mapikey/verify, GET /db/NODE - both fine, session alive

--- 2) node 9102, omitted fields (mX,mY,mZ only) ---
[  0.5s] 200      GET /db/NODE (pre-check)            - confirmed alive first
[ 15.9s] TIMEOUT  POST /db/NMAS 9102 (omitted fields)  - died
[ 16.3s] 404      GET /mapikey/verify (relay only)
[ 31.8s] TIMEOUT  GET /db/NODE
```

One script, one session, one node created fine, mass written with all six
fields — survives. A second node, mass written with three fields omitted —
kills the exact session that had just survived the first call, seconds
earlier. There is no cleaner isolation than that.

**Symmetric confirmation on both products, same day, after both were
restarted:** a single script ran the identical two-step protocol (full
fields on node N, then omitted fields on node N+1, in the same session)
against Civil NX and then Gen NX in sequence:

| Product | Full fields (`rmX/rmY/rmZ=0.0`) | Omitted fields |
| --- | --- | --- |
| Civil | survived (201, `GET /db/NODE` fine after) | died (15.41s timeout, then `GET /db/NODE` timeout) |
| Gen | survived (201, `GET /db/NODE` fine after) | died (15.46s timeout, then `GET /db/NODE` timeout) |

The user independently confirmed both products' UI showed the crash dialog
after their respective "omitted fields" call, and neither did after the
"full fields" call moments earlier.

**Root cause: `/db/NMAS` crashes when `rmX`/`rmY`/`rmZ` are absent from the
payload — an uninitialized-value read or missing-default bug server-side
for those three fields specifically — not a defect in nodal-mass writes in
general.** Re-checked against the official article directly (not the
vendored copy, per this file's own "fetch the Zendesk article" lesson from
the 2026-07-27 section-B correction):
[support.midasuser.com/hc/en-us/articles/35952994344985-Nodal-Masses](https://support.midasuser.com/hc/en-us/articles/35952994344985-Nodal-Masses)'s
Specifications table documents `rmX`/`rmY`/`rmZ` as Optional with Default
`0`, exactly as the vendored manual said — so every omitted-fields request
this investigation sent was fully spec-compliant, and the server crashing
on it is unambiguously a defect, not a documentation gap or a caller
mistake. The server apparently doesn't apply that documented default
safely when the fields are missing, but is fine when a caller supplies it
explicitly. This explains every prior reproduction (this file's,
`docs/vendor_repro_nmas.py`'s, and `live_crud_check.py`'s fixtures all
omitted these fields) without contradicting any of it — the crash was
always real, just narrower in scope than "the whole endpoint is broken"
implied.

**Fix applied**: `NodalMass.create()`/`.update()` in `db/static_loads.py`
now merge `{"rmX": 0.0, "rmY": 0.0, "rmZ": 0.0}` under any item that
doesn't set them, before sending — exactly the documented default, made
explicit because the server can't be trusted to apply it itself. Verified
live through the SDK (not just raw `requests`): a `NodalMass.create()` call
passing only `mX`/`mY`/`mZ` succeeded and the session stayed alive, and
`scripts/live_crud_check.py --product gen --tier static --include-crashers`
completed `/db/NMAS`'s full create→read→update→read→delete→read round trip
cleanly (9/9 for the tier). The case is un-quarantined and `confirmed=True`
in `live_crud_check.py` as of this session.

Updated everywhere this was recorded: `CLAUDE.md`, `NodalMassPayload`'s
docstring in `db/static_loads.py` (now describes the fix, not just the
symptom), `live_crud_check.py` (case un-quarantined, module docstring's
"42 of 43" corrected to all 43), and `docs/vendor_report_ko.md`'s A-1
(rewritten to lead with the root cause and the workaround).

## 2026-07-29 — the 20 Civil 404s independently reproduced, `PRODUCTS` corrected

The caveat below asked for independent reproduction — different account,
different session — before touching `PRODUCTS` for the 20 endpoints found
404ing on the Civil v2.2 (07/28/2026) sweep. That arrived the same day: a
separately run validation sweep (`docs/Codex Report/midas_nx_0.14.0_civil_*`
and `..._gen_*`, removed 2026-09-17; git history at `fa1332b`), executed from a different machine/session against the
same day's freshly patched Civil and Gen builds, landed on **the exact same
20 Civil endpoints** (`db_and_design_404_endpoints` in its JSON summary) and
**the exact same 7 Gen endpoints** (`CMCS`, `EWSF`, `PLCB`, `RCHK`, `SPAN`,
`STRPSSM`, `WVLD` — the latter three already `CIVIL_ONLY`/`HYPER_S_ONLY` in
the SDK, so unsurprising; the rest confirm the existing accounting). Both
tools also agree the 20 Civil 404s are 404 at the `/info` schema level too,
not just the GET route.

That satisfies this file's own reproduction bar, so all 20 are now declared
`GEN_ONLY` (new constant in `db/base.py`, same pattern as `HYPER_S_ONLY`):
the 11 `db/*` endpoints (`STOR`, `SWIND`, `SSEIS`, `POSP`, `EPST`, `DRLS`,
`SDHY`, `SDIS`, `REBB`, `REBR`, `REBW`) and the 9 design-chapter endpoints
(`/DESIGN/RC/KDS-41-20-2022/{MATD,REBB,REBC,REBR,REBW,TRFT,ULCT}`,
`/DESIGN/SRC/AIK-SRC2K/MATD`, `/DESIGN/STEEL/KDS-41-30-2022/ULCT`). Guarded
by a parametrized test, `tests/db/test_civil_v22_gen_only_products.py`,
mirroring `test_hyper_s_products.py`.

The independent sweep also surfaced three endpoints not previously in this
file's list, all looking like the same pattern but **not yet independently
reproduced twice**, so `PRODUCTS` was deliberately left unchanged for them:

- `/db/REBC` (ch24, POST-only, no GET) — its `/info` schema answers on Gen,
  404s on Civil.
- `/ope/STORY_PARAM` and `/ope/STORY_IRR_PARAM` — GET succeeds on Gen, 404s
  on Civil.

## 2026-07-29 (later same day) — live re-verification with both products open

With Civil NX and Gen NX both connected in the same session, re-ran every
classification claim above directly through the SDK (`MidasClient(...,
strict_product=False)` on both clients, so the SDK's own `PRODUCTS` guard
couldn't short-circuit the call — the point was to hit the real server, not
re-confirm the guard against itself):

| Family | Classification | Probed | Result |
|---|---|---:|---|
| `GEN_ONLY` (the 20 corrected above) | civil GET fails, gen GET ok | 20/20 | **20/20 matched**, byte-identical to the Civil v2.2 sweep and the independent Codex sweep |
| `HYPER_S_ONLY` (13 implemented `-M1` endpoints) | civil GET ok, gen GET fails | 13/13 | **13/13 matched**, no change since 2026-07-26 |

Both families are now confirmed a third time (`GEN_ONLY`) or a second time
(`HYPER_S_ONLY`, unchanged since first confirmed) with zero mismatches.

**The 3 previously-unconfirmed candidates also confirmed this session** —
this is their second independent reproduction, so this file's own bar for
acting is now met:

- `/db/REBC` (ch24, POST-only): `.info()` answers on Gen, 404s on Civil.
- `/ope/STORY_PARAM`: GET succeeds on Gen, 404s on Civil.
- `/ope/STORY_IRR_PARAM`: GET succeeds on Gen, 404s on Civil.

**Action taken**: `db.design.ColumnRebar` (`/db/REBC`) is now `PRODUCTS =
GEN_ONLY`, guarded in the same `test_civil_v22_gen_only_products.py` test
(now 21 endpoints). `docs/coverage.json` updated to match.
`/ope/STORY_PARAM` and `/ope/STORY_IRR_PARAM` are documented as Gen-only in
`get_story_check_parameter`'s and `get_story_irregularity_check_parameter`'s
docstrings in `ope.py`, but **not enforced** — plain `doc.py`/`ope.py`/
`view.py` functions have no `PRODUCTS` gate anywhere in this SDK (they're
functions, not `DbResource` subclasses), so a Civil call against either
still reaches the server and 404s there rather than raising client-side.
Adding a product-gate mechanism to that whole module family would be a
bigger design change than this session's scope — flagged for a future
decision, not done here.

**Final classification as of this session** (all three families now
independently confirmed at least twice, zero open mismatches):
`GEN_ONLY` = 21 endpoints (the 20 above + `/db/REBC`), `HYPER_S_ONLY` = 13
implemented + 8 undocumented-stub `-M1` endpoints (unchanged), `CIVIL_ONLY`
= the ch08/ch17 bridge/moving-load chapters plus the 7 endpoints corrected
2026-07-29 morning (`CMCS` and friends) — unchanged, not re-probed this
session since the user's request was specifically the Gen-only and
Hyper-S-only families plus the 3 unconfirmed candidates.

## 2026-07-29 (later still) — STORY_PARAM/STORY_IRR_PARAM against a real production Gen NX model, and a manual defect found in the process

The prior session's Gen NX GET check for `/ope/STORY_PARAM`/`/ope/STORY_IRR_PARAM`
ran against whatever model happened to be open — good enough to confirm the
route answers, not enough to confirm it answers *meaningfully*. With a real
production model open (`/ope/PROJECTSTATUS`: 4044 nodes, 4686 elements, 11
stories, 441+494+108 load combinations across three design codes — not a
scratch model), re-ran the GET calls directly:

```
GET /db/STOR              -> 11 real stories (B1, 1F..9F, Roof) with populated
                              wind/seismic eccentricity and torsional data
GET /ope/STORY_PARAM      -> {"COUNTRY_CODE": "NTC2018"}
GET /ope/STORY_IRR_PARAM  -> {"COUNTRY_CODE": "NTC2018",
                               "STORY_DRIFT_METHOD": "Drift at the Center of Mass",
                               "STORY_STIFFNESS_METHOD": "1 / Story Drift Ratio"}
```

Both endpoints answered with real, previously human-configured values (not
defaults or an empty shape), settling the "does this route actually work on
Gen, not just technically respond" question the user raised. No analysis run
was needed — both endpoints are pre-analysis configuration (country code and
calculation-method selection used by later story-drift/irregularity result
tables), not analysis output, so `/doc/ANAL` was never called this session.

**Found in the process: a real manual defect, not just a confirmation.**
`StoryIrregularityCheckParameterArgument` in `ope.py` had documented
`STORY_DRIFT_METHOD`/`STORY_STIFFNESS_METHOD`/`SEISMIC_BEHAVIOR_FACTOR` as
space-stripped (`"Max.DriftofOuterExtremePoints"`, `"1/StoryDriftRatio"`,
`"3orbelow"`), reasoning the manual's own worked JSON example was more
concrete evidence than the Parameters table's space-containing rendering.
The live GET above returned the **space-containing** form
(`"Drift at the Center of Mass"`, `"1 / Story Drift Ratio"`) for a
real, human-set value — directly contradicting that worked example, and
matching both the Parameters table and the sibling `post/story.py`
STORY_DRIFT endpoint's own already-live-confirmed convention (see that
file's `STORY_DRIFT_METHOD` comments, chapter `21_POST_StoryTables.md`).
Corrected `ope.py`'s docstring/comment and `tests/test_ope.py`'s example
values to the space-containing form as canonical. Not runtime-enforced
either way — TypedDicts here are documentation, not validation — but this
is exactly the "manual's worked example is the outlier, live evidence and
the Parameters table agree" pattern this project has hit before (KDS2016,
Story Drift X_DIR/X-DIR).

## 2026-07-29 (still later) — the mirror-image finding: 32 of 47 "Civil-only" endpoints answer on Gen too

Asked to also re-verify the plain `CIVIL_ONLY` family (excluding Hyper-S,
already reconfirmed above) with both Civil NX and Gen NX open at once.
Enumerated all 47 non-Hyper-S `CIVIL_ONLY` `DbResource` classes and probed
each with `MidasClient(..., strict_product=False)` on both clients (same
methodology as the `GEN_ONLY`/`HYPER_S_ONLY` re-check above — bypass the
SDK's own guard to see what the server actually does).

**32 of the 47 answered on Gen NX too** — not the expected 404. Checked
`/info/db/...` schema for all 32: every one resolves a full JSON Schema on
Gen, the same evidentiary bar this file has used everywhere else to call a
route "genuinely exists" rather than "coincidentally didn't error." Content
of the 32 GET responses:

- **`/db/LCOM-CONC`** (Load Combinations - Concrete Design): **494 real,
  populated rows** — matching this exact production model's own
  `/ope/PROJECTSTATUS` count (`'Load Comb(Concrete)': 494`). Unambiguous:
  this is a real, working, populated Gen NX feature, not an artifact.
- The other 31 returned `{"message": ""}` (the standard empty-table shape)
  — ambiguous on GET alone, but the matching `/info` schema on all 31 is the
  same signal this file already treats as sufficient elsewhere.

The 32: `IMPF`, `LCOM-CONC`, `LCOM-STLCOMP`, `LLAN`, `LLANch`, `LLANid`,
`LLANop`, `LLANtr`, `MLSP`, `MLSR`, `MVCD`, `MVCT`, `MVCTbs`, `MVCTch`,
`MVCTid`, `MVCTtr`, `MVHC`, `MVHL`, `MVHLtr`, `MVLD`, `MVLDbs`, `MVLDch`,
`MVLDeu`, `MVLDid`, `MVLDpl`, `MVLDtr`, `SINF`, `SLAN`, `SLANch`, `SLANop`,
`THGC`, `ULFC`.

**This directly contradicted `db/base.py`'s own `CIVIL_ONLY` docstring**,
which cited `/db/LCOM-CONC` and "the entire ch08/ch17 bridge/moving-load
chapters" as the canonical example of this constant's use — that example
turned out to be wrong.

**The remaining 15 stayed genuinely Civil-only** (404 on Gen, both GET and
by extension the route): `CAMB`, `CJFG`, `CMCS`, `CRGR`, `DYFG`, `DYLA`,
`DYNF`, `EWSF`, `GCMB`, `GSBG`, `PLCB`, `RCHK`, `SPAN`, `STRPSSM`, `WVLD` —
7 of these are the ones already corrected 2026-07-26 after independent Gen
404s, so no surprise there; the other 8 (bridge girder/camber-control trio
plus the railway/concurrent-group set) are newly reconfirmed, not new
corrections.

**Decision, made with the user (not unilateral)**: given the scale (32
endpoints) and that it contradicts documented domain framing the author
themselves wrote, this was raised as an explicit question rather than
auto-applied. The user's read on it: the API clearly does respond
("분명히 통신이 되는데 only라고 쓴 것은 아닌 것 같음" — "it clearly
communicates, so writing 'only' doesn't seem right"), and whether an
engineer *should* actually drive bridge/moving-load features from a Gen NX
session is a separate, per-project judgment call ("목적에 따라 다르겠지만
엔지니어가 판단해서 사용해야 할 것 같음") — not something `PRODUCTS`
should gate. Confirmed: apply the same evidentiary bar used for
`GEN_ONLY`/`HYPER_S_ONLY` and correct all 32.

**Action taken**: all 32 classes' `PRODUCTS = CIVIL_ONLY` override removed
(back to the class default, `gen+civil`) across `db/moving_loads.py` (23),
`db/analysis_control.py` (5, the `MVCT` family), `db/load_combinations.py`
(2), `db/dynamic_loads.py` (1, `THGC`), `db/bridge.py` (1, `ULFC`).
`docs/coverage.json` updated to match (24 of the 32 needed a `products`
fix; 8 already said `["gen","civil"]` there despite the SDK's `PRODUCTS`
disagreeing — the manual-derived coverage metadata had actually been right
and the SDK's own class attribute was the stale one). Five tests
(`test_*_is_civil_only` in `test_analysis_control.py`, `test_dynamic_loads.py`,
`test_load_combinations.py` ×2, `test_moving_loads.py`) that asserted a
`ProductMismatchError` on the Gen client were rewritten to assert the call
now succeeds instead. Module-level docstrings in `moving_loads.py`,
`bridge.py`, and the `CIVIL_ONLY` constant itself in `db/base.py` corrected
to stop citing the wrong example and to record the finding.

**During this session's live probing, the user observed a brief popup on
the Civil NX side** ("Civil에 뭔가 거부되었다는 팝업") — normal again by
the time it was reported, popup already dismissed, no session hang.
Everything run against Civil in this session was GET/`.info()` only (no
POST/PUT/DELETE), so the trigger isn't identified yet. The user was
re-attempting to reproduce it with a screenshot at the time of this note;
if a cause is confirmed, record it here rather than assuming GET is
unconditionally safe against this server the way this file has assumed
throughout.

## 2026-07-29 (final) — `GET /db/CAMB` can trigger the same `Program Files` write-permission dialog as crash recovery, confirmed A/B

While reproducing the CIVIL_ONLY sweep above for the user to watch, a modal
popup flashed on the Civil NX side mid-run: `"...5 FCM General.mcb
액세스가 거부되었습니다"` (access denied), for the product's own bundled
tutorial file at `C:\Program Files\MIDAS\MIDAS CIVIL NX\MIDAS CIVIL
NX\Tutorial\5 FCM General.mcb`. The user had that FCM tutorial model open at
the time. The API call itself still answered normally — this is the same
"HTTP success, modal dialog on the side" pattern this file has documented
before (see the crash-recovery `_restore.mcb` case and the `/doc/SAVEAS`
case in `CLAUDE.md`).

Isolated the trigger with a controlled A/B, same session, same call, one
variable changed:

| Document location | `GET /db/CAMB` (FCM Camber Control) | Popup |
|---|---|---|
| `C:\Program Files\...\Tutorial\5 FCM General.mcb` | `{"message": ""}` | **Yes** |
| Same file, moved to `Downloads` | `{"message": ""}` | **No** |

Confirmed: **`/db/CAMB` — a plain read GET, not a write, not a crash — can
still trigger this dialog**, whenever the open document sits in a
write-protected location. This generalizes the previously-known
crash-recovery-only case (`_restore.mcb` under `Program Files`, first seen
during the Gen NX hang investigation) into a broader pattern: some
GET-shaped commands apparently attempt to write an auxiliary/cache file next
to the document even to answer a read, and when that write is denied by
Windows, the dialog surfaces regardless of the command's nominal read/write
classification. Recorded as vendor report A-7's second, independently
reproduced trigger (`docs/vendor_report_ko.md`).

**Practical implication for this SDK and its scripts**: `GET` is not
unconditionally side-effect-free against this server the way this file has
assumed throughout — a document living under `Program Files` (or any other
path a standard account can't write to) is the actual risk factor, not the
HTTP method. `scripts/live_readonly_sweep.py`'s docstring claim ("SAFE TO
RUN AGAINST AN OPEN MODEL... issues GET only") still holds for *data*
safety (no mutation, no discarded work) but should not be read as "will
never pop a dialog" — advise users to keep working documents off
`Program Files`-style paths before a sweep, the same advice already given
for A-7's crash-recovery case.

## 2026-07-29 (last) — full CRUD re-run on the newest Civil build, 43/43 clean including NMAS

With the user's FCM model already saved aside as a disposable copy, ran
`scripts/live_crud_check.py --product civil --include-crashers` against the
same live Civil NX session (this discards the currently-open document via
`/doc/NEW`, same as always — the FCM file itself was unaffected since it
was saved separately first). All 6 tiers, all 43 resources, full
create→read→update→read→delete→read round trip: **43/43 PASS, zero
failures**, including `/db/NMAS` (`create=ok read_back=ok update=ok
read_updated=ok delete=ok read_deleted=ok`) — the first full Civil-side CRUD
confirmation of the omitted-`rmX`/`rmY`/`rmZ` fix from earlier today, not
just the Gen-side one already recorded above. Also ran a fresh
`live_readonly_sweep.py --product civil --record-coverage` against the FCM
model itself (before the CRUD run): 273/273 GET-capable resources answered,
zero 404s — a clean end-to-end confirmation that today's `GEN_ONLY`/
`CIVIL_ONLY` corrections match live behavior with no regressions.

Followed by `scripts/live_crud_check.py --product gen --include-crashers`
against the same-day Gen NX session: **37/37 PASS**, zero failures,
including `/db/NMAS` again. The 6 missing cases versus Civil's 43 are
`/db/CMCS` (stage tier) and the whole `moving` tier (4 cases) — both
declared `products=("civil",)` inside the checker script itself, which
wasn't updated for today's `CIVIL_ONLY`→`gen+civil` corrections above.
Worth widening in a future session (`MVCD`/`LLAN`/`MVHL`/`MVLD` are now
confirmed to work on Gen too), but out of scope for this one.

## 2026-07-29 (very last) — `/db/MVCD`'s Gen availability is per-CODE, not unconditional

Tried to widen `scripts/live_crud_check.py`'s `moving` tier to also run on
Gen NX, since today's finding above showed the whole ch08 chapter answering
there. The checker's own discipline caught a real nuance immediately: its
`/db/MVCD` seed (`CODE: "KOREA"`) came back `REGRESS` — a live 201 carrying
`[Error] Errors detected in Moving Load Code Data.(Item:Unavailable moving
load code)`.

Isolated with a quick sweep of every documented `CODE` value against Gen:

```
KOREA           -> [Error] ... Unavailable moving load code
CHINA           -> [Error] ... Unavailable moving load code
KSCE-LSD15      -> [Error] ... Unavailable moving load code
AASHTO STANDARD -> created ok
AASHTO LRFD     -> created ok
EUROCODE        -> created ok
BS              -> created ok
```

So `/db/MVCD` genuinely creates and round-trips on Gen NX — for the
US/Euro/UK codes. The Korea/China-specific codes 201 with an error there,
presumably a licensed-module gate scoped to the region code rather than a
route-level product restriction. This doesn't contradict the `GEN_ONLY`
finding above (route + `/info` both legitimately resolve on Gen) — it
refines it: **route existence and per-value availability are different
questions**, and GET/`.info()` alone can only answer the first.

**Action**: `live_crud_check.py`'s core-tier `/db/MVCD` case now uses
`"AASHTO STANDARD"`/`"AASHTO LRFD"` instead of `"KOREA"`/`"AASHTO LRFD"`, so
it runs unmodified and confirmed on both products (43/43 Civil, 38/38 Gen
after the change). The `moving` tier's other three cases (`LLAN`/`MVHL`/
`MVHC`/`MVLD`) stay Civil-only *in this checker*, since their fixture chain
is Korea-standard throughout (vehicle `STANDARD_CODE: "KS-RB"`) and hasn't
been rebuilt around a Gen-available code — that fixture work is unstarted,
not evidence those routes are Civil-only (they aren't, per the `GEN_ONLY`
finding). `PRODUCTS` on the SDK classes themselves is unchanged by this —
this section is entirely about the checker script's fixture coverage, not
a source-level correction.

## 2026-07-29 (truly last) — `/db/REBW`'s manual section doesn't match the live server at all

With a second real production Gen NX model opened (KDS/Korean-code
building, 4044 nodes, 4686 elements — the same model from this file's
`STORY_PARAM`/`STORY_IRR_PARAM` section above), re-ran the readonly sweep
(`--record-coverage`, 265/265 GET-capable Gen resources, zero errors) and
then spot-checked populated design-chapter data for manual drift, the same
way `/db/STAG`/`/db/TDNA` were checked against the Civil FCM model earlier.

`/db/REBW` (ch24, "Modify Wall Rebar," 102 real rows) came back completely
unrecognizable against its own documented schema:

```
Documented (manual's own JSON Schema, matches this SDK's old WallRebarItem):
  CREATE_SUB_WALL_ID, SUB_WALL_ID, STORY: {FROM, TO},
  VERTICAL_REBAR: {NAME, DIST}, HORIZONTAL_REBAR: {NAME, DIST},
  USE_END_REBAR, END_REBAR: {NAME, NUM, DIST},
  BE_HORIZONTAL_REBAR: {NAME, DIST}, BOUNDARY_ELEMENT_LENGTH,
  CONCRETE_FACE_TO_CENTER_OF_REBAR: {DW, DE},
  USE_MODEL_THICKNESS, THICKNESS

Live GET /db/REBW:
  {"ID": 0, "bUSE_MODEL_THICK": true, "THICK": 0, "DW": 0.05, "DE": 0.05,
   "VER_BAR": {"NAME": "D16", "DIST": 0.2},
   "HOR_BAR": {"NAME": "D13", "DIST": 0.25},
   "END_BAR": {"NAME": "", "DIST": 0}, "NUM_END_BAR": 0,
   "BE_HOR_BAR": {"NAME": "D10", "DIST": 0.2}, "BE_LENGTH": 0}
```

Every field is renamed (and `DW`/`DE` flattened out of any nesting), and
`STORY` doesn't exist as `{FROM,TO}` at all. Two checks isolated this to
`/db/REBW` specifically, not a systemic ch24 problem:

- **`/db/REBB`** (ch24's sibling, "Modify Beam Rebar") matched its own
  documentation exactly — `vMAIN_BAR_TOP`, `SHEAR_BAR`, `SKIN_BAR_NAME`,
  all present as documented, real data.
- **`/DESIGN/RC/KDS-41-20-2022/REBW`** (ch26, the KDS-specific sibling for
  the *same physical walls*, same 102 rows) also matched its own
  documentation exactly — `VERTICAL_REBAR`, `HORIZONTAL_REBAR`,
  `CONCRETE_FACE_TO_CENTER_OF_REBAR: {DW,DE}`, all present, long-form.

`GET /info/db/REBW` confirmed the abbreviated shape is the server's own
stated schema, not a GET-only quirk — it documents `bUSE_MODEL_THICK`,
`VER_BAR`, `HOR_BAR`, `END_BAR`, `NUM_END_BAR`, `BE_HOR_BAR`, `BE_LENGTH`,
and `vSTORY_NAME: [string]` (a story-name array, not a `{FROM,TO}` range)
as the `Argument` schema. Confirmed it's also the real write contract, not
just read: picked one existing wall (id 101), backed up its exact current
value, sent a `PUT` using the info-confirmed field names changing
`VER_BAR.DIST` from `0.2` to `0.99`, verified the change landed on a fresh
`GET`, then restored the original value and verified the restore matched
byte-for-byte. Full round trip, real data, real Gen NX session.

**Conclusion**: `docs/manual/24_DB_Design.md`'s `/db/REBW` section (and by
inheritance this SDK's old `WallRebarPayload`/`WallRebarItem`) documents a
schema the live server doesn't implement. A user following the manual's
worked example would have every field silently ignored or rejected — this
isn't a cosmetic drift, it's the whole payload contract. `/db/REBB` and the
ch26 KDS sibling being correct rules out "the whole rebar family is
misdocumented" — this looks like a defect isolated to `/db/REBW`'s specific
manual section.

**Checked against the official source directly — not just the vendored
copy.** Per this file's own standing rule (never cite the vendored manual
repo as "the documentation" in anything sent externally), searched
MIDASIT's Zendesk Help Center API directly: the dedicated article for this
endpoint is
[59359110968345 — "Modify Wall Rebar Data"](https://support.midasuser.com/hc/en-us/articles/59359110968345-Modify-Wall-Rebar-Data)
(distinct from
[59236271208729](https://support.midasuser.com/hc/en-us/articles/59236271208729-DESIGN-RC-KDS-41-20-2022-REBW-Modify-Wall-Rebar-Data),
the correct ch26 KDS-specific article). It documents the same long-form
names as the vendored copy (`VERTICAL_REBAR`, `HORIZONTAL_REBAR`,
`CONCRETE_FACE_TO_CENTER_OF_REBAR`, `STORY: {FROM,TO}`, ...). **This rules
out a vendored-repo transcription error** — the official MIDASIT
documentation itself doesn't match its own server's implementation. Direct
HTML fetches of Zendesk pages 403 for this tool; the JSON Help Center API
(`/api/v2/help_center/en-us/articles/<id>.json`) and article search
(`/api/v2/help_center/articles/search.json?query=...`) work and are the
way to reach a specific official article when a chapter's combined
reference article is too large to fetch in full.

**Fix applied**: `WallRebarItem`/`WallRebarPayload` in `db/design.py`
rewritten to the server-confirmed shape (`ID`, `bUSE_MODEL_THICK`, `THICK`,
`DW`, `DE`, `VER_BAR`, `HOR_BAR`, `END_BAR`, `NUM_END_BAR`, `BE_HOR_BAR`,
`BE_LENGTH`, `vSTORY_NAME`), with a docstring explaining the manual
mismatch and citing this section. The now-unused `StoryRange`/
`WallEndRebarSpec`/`ConcreteFaceToCenterOfRebar` helper TypedDicts were
removed (ch26's `RcWallStoryRange`/`RcWallEndRebarSpec`/
`RcWallConcreteFaceToCenterOfRebar` are separate, correct, untouched).
`tests/db/test_design_setup.py`'s `WallRebar` create test updated to the
corrected field names. This is a real correctness fix — the old TypedDict
would have led a caller straight into the exact defect this session found.
Worth reporting to MIDASIT: see `docs/vendor_report_ko.md`.

## 2026-07-29 (later same day) — the 8 Hyper-S `-M1` stubs, implemented from `/info/db/...`

Per the author's decision on the v1.0.0 gate's item (a) ("1번으로 해서 진행" —
go with option 1), pulled full `GET /info/db/...` JSON Schema bodies for all
8 previously-unimplemented Hyper-S stub endpoints against a live Civil NX
2026 (v2.2, build 06/18/2026) session, using a direct `MidasClient(...,
strict_product=False)` probe (not `scripts/live_readonly_sweep.py` this
time — the session disconnected from the relay partway through, before the
script itself could run; the direct probe's results were already captured).

5 of 8 resolved a full schema:

| Endpoint | GET | `/info` |
|---|---|---|
| `/db/STYP-M1` | real populated row (`STYPE: "3D"`, `GRAV: 9.806`, ...) | full schema |
| `/db/MATL-M1` | real populated row (`MATL_NAME: "C24"`, `MATL_TYPE: "CONC"`, `PARAM[0].P_TYPE: 0`) | full schema |
| `/db/IMFM-M1` | `{"message": ""}` (empty table) | full schema |
| `/db/EPMT-M1` | `{"message": ""}` (empty table) | full schema |
| `/db/IEHG-BEAM-M1` | `{"message": ""}` (empty table) | full schema |
| `/db/IEHG-TRUSS-M1` | `{"message": ""}` (empty table) | **404** |
| `/db/IEHG-GL-M1` | `{"message": ""}` (empty table) | **404** |
| `/db/IEHG-PSS-M1` | `{"message": ""}` (empty table) | **404** |

The 3 `IEHG-{TRUSS,GL,PSS}-M1` endpoints answer GET (empty table on this
model) but their own `/info/db/...` route 404s — no schema route exists for
them specifically, unlike their sibling `IEHG-BEAM-M1`.

Two of the five resolved schemas turned out to have a **genuinely different
wire shape** from their non-Hyper-S sibling, not just a product gate on an
identical schema:

- `/db/MATL-M1`'s `PARAM[].P_TYPE` is 0-indexed (`Standard:0, Isotropic:1,
  Orthotropic:2`) and nests user-defined fields under a `USER_DEFINED`
  sub-object, vs. non-Hyper-S `/db/MATL`'s 1-indexed `P_TYPE` with flat
  fields (`ELAST`, `POISN`, ... directly on the param object).
- `/db/IMFM-M1` nests fields under `CONCRETE`/`STEEL` sub-objects with
  different names entirely (`UN_CONC_NAME`, `CONF_CONC_NAME`) vs.
  non-Hyper-S `/db/IMFM`'s flat `CONC_NAME`/`CONFINED_CONC_NAME`.

`/db/EPMT-M1`'s `MODEL_TYPE` is also an int (`Tresca:0, VonMises:1,
MohrCoulomb:2, DruckerPrager:3, Masonry:4, ConcreteDamage:5`) vs.
non-Hyper-S `/db/EPMT`'s string codes (`"TR"`/`"VM"`/`"MC"`/...), and adds
two sub-objects (`DRUCKER`, `MASONRY`, `CONCDMG`) the non-Hyper-S variant's
chapter never documented at all.

**Fix applied**: implemented all 8 as proper `DbResource` subclasses —
`StructureTypeHyperS` (`db/project.py`), `MaterialHyperS` /
`InelasticFiberMaterialLinkHyperS` / `PlasticMaterialHyperS`
(`db/properties/material.py`), `InelasticHingePropertyHyperS{Beam,Truss,
GeneralLink,Pss}` (`db/properties/hinge.py`). Each payload TypedDict is
documented in its own docstring as `/info`-derived rather than
manual-transcribed. The 3 `IEHG-*` classes without their own `/info` route
carry an explicit `⚠️` docstring caveat that their single-field shape
(`INEL_PROP_NAME`) is assumed by sibling analogy to `IEHG-BEAM-M1`, not
independently confirmed — if that assumption is ever wrong, it'll surface
as a `"Wrong Field"` response on a real write, per this file's own
"`Wrong Field` usually means a bad value, not a bad field name" note (which
doesn't apply here since these would be genuinely wrong field *names*, an
exception worth remembering if it comes up).

`docs/coverage.json` updated: all 8 endpoints marked `"status":
"implemented"` with a `live_verified` entry citing this direct-probe method
(distinct from the sweep script's own `live_readonly_sweep.py` method
string, since the sweep script itself didn't get to run). Coverage is now
398/398 (100%). `tests/db/test_hyper_s_products.py`'s family-size assertion
updated 13→21. This resolves the v1.0.0 gate's item (a) — see PLAN.md.

**Two corrections caught by `/code-review` on 2026-07-30, after v1.0.0 shipped:**

1. `InelasticHingePropertyHyperSPss`'s docstring claimed "PSS" isn't stated
   in any available source — false. The manual repo's `INDEX.md` titles the
   endpoint "Assign Inelastic Hinges — Point Spring Support (Hyper-S)", and
   `04_DB_Properties.md`'s own chapter TOC calls it "... Point Spring
   (Hyper-S)" (a minor internal inconsistency in the manual — "Support"
   present in one title, absent in the other — but "Point Spring" either
   way). What's actually missing is a Specifications table, not the name.
   Fixed the docstring and its `NAME` field (now "... Point Spring,
   Hyper-S)"). This is why the day's own rule matters: verify a claim
   against the actual source before asserting it, even a claim about what a
   source *doesn't* say.
2. `docs/coverage.json`'s `live_verified.method` string was identical for
   all 8 Hyper-S stubs, which overclaimed schema confirmation for
   `IEHG-{TRUSS,GL,PSS}-M1` — their `/info` route 404s, so only GET was
   actually confirmed for them, unlike the other 5. Reworded their `method`
   field to say so explicitly, so a future reader of the coverage ledger
   (or `scripts/check_manual_drift.py`) doesn't skip re-verifying these
   three on the strength of a probe that never actually ran against their
   schema.

## 2026-07-30 — second independent live re-check of the 8 Hyper-S stubs

With a fresh Civil NX session (same build, v2.2 06/18/2026), re-ran
`scripts/live_readonly_sweep.py` for real this time (2026-07-29's original
recording used a direct probe, since the session disconnected — see above —
before the script itself could run). All 8 answered `ok`: `STYP-M1`,
`MATL-M1`, `IMFM-M1`, `EPMT-M1`, `IEHG-BEAM-M1`, `IEHG-TRUSS-M1`,
`IEHG-GL-M1`, `IEHG-PSS-M1`.

Also re-probed `/info/db/...` directly for all 8 to check the schema/no-schema
split still holds: it does, exactly. The 5 with a schema
(`STYP-M1`/`MATL-M1`/`IMFM-M1`/`EPMT-M1`/`IEHG-BEAM-M1`) returned the
identical field set as 2026-07-29 — a second independent confirmation, not
just a repeat of the same probe. The 3 without one (`IEHG-TRUSS-M1`,
`IEHG-GL-M1`, `IEHG-PSS-M1`) still 404 on `/info` — their `INEL_PROP_NAME`
shape remains an assumption by sibling analogy to `IEHG-BEAM-M1`, not
independently confirmed, and there is still no indication MIDASIT intends to
add an `/info` route for them.

`docs/coverage.json`'s `live_verified` entries for all 8 updated to cite
`scripts/live_readonly_sweep.py` (the intended method, now that it actually
ran) with today's date, keeping the same schema-confirmed/unconfirmed
distinction from the code-review fix above.

## 2026-07-30 — a real AASHTO arch-bridge model, and rebuilding the moving-tier fixture

With a different real production Civil NX model open (an AASHTO-coded arch
bridge), ran a full `scripts/live_readonly_sweep.py` (281/281 `ok`, zero
404s — reconfirms every `PRODUCTS` classification holds on a third,
structurally distinct real model) and spot-checked the genuinely
`CIVIL_ONLY` bridge-chapter endpoints (`CMCS`, `EWSF`, `PLCB`, `RCHK`,
`SPAN`, `STRPSSM`, `WVLD`, `CAMB`, `CJFG`, `CRGR`, `DYFG`, `DYLA`, `DYNF`,
`GCMB`, `GSBG`) — all answer cleanly with 0 rows, meaning this arch bridge
simply doesn't use girder-camber/composite-girder features, not an error.

The moving-load chapter had real, meaningful AASHTO LRFD data: `/db/MVCD`
(`CODE: "AASHTO LRFD"`), `/db/MVHL` (the actual HL-93 design truck/tandem,
`HL-93TRK`/`HL-93TDM`, `STANDARD_CODE: "AASHTO-LRFD"`), `/db/LLAN` (2 real
lanes with populated `LANE_ITEMS`), and `/db/MVLD` (a load case combining
both HL-93 vehicles with the AASHTO `SCALE_FACTORS` combination rule).
Cross-checked field-for-field against `VehiclePayload`, `TrafficLineLanePayload`,
and `MovingLoadCasePayload` in `db/moving_loads.py`: **zero drift** — every
field name, nesting, and type matched. This also independently reconfirmed
(against genuine production data, not a synthetic test) the existing
`LineLaneItem` docstring warning that `CENT_F` must be nonzero when
`MVCD.CODE="AASHTO LRFD"` (`CENT_F: 0.5` in the real data).

**Follow-on: rebuilt `scripts/live_crud_check.py`'s `moving` tier fixture
around this AASHTO LRFD/HL-93 shape**, replacing the Korea-standard
(`MVCD "KOREA"`, `STANDARD_CODE "KS-RB"`) fixture that had kept the tier
Civil-only in the checker since 2026-07-29 (Korea/China/KSCE-LSD15 codes
hit a licensed-module gate on Gen; AASHTO does not). Ran it live against
this same Civil session — the user explicitly authorized this knowing it
calls `/doc/NEW` and discards the open arch-bridge model ("자유롭게 해") —
and all 4 resources (`LLAN`/`MVHL`/`MVHC`/`MVLD`) passed a full
create→read→update→read→delete→read round trip on the first run. Still
`products=civil` in the checker for now: the fixture is now
code-portable and the route-level evidence says it should also pass on
Gen, but that is an expectation, not something watched pass live yet —
widen `products`/flip to Gen-confirmed only once someone actually runs
`--tier moving --product gen`.

## 2026-07-30 (same day) — a real Eurocode PSC bridge model finds four schema gaps

Same session, model swapped to a different real production Civil NX model:
a PSC (prestressed concrete) bridge built with Eurocode, evidently by the
Free Cantilever Method (4 construction stages, `ACT_ELEM`/`ACT_BNGR`/
`ACT_LOAD` populated per stage, 24 real tendon profiles across groups
A1-C4). Full `live_readonly_sweep.py` again 281/281 `ok`. The genuinely
`CIVIL_ONLY` bridge-chapter endpoints all answered with 0 rows (this bridge
type doesn't use girder-camber features), same as the arch-bridge model
above — reconfirms `PRODUCTS` holds on a third, structurally distinct real
model.

Cross-checked real tendon/prestress/creep-shrinkage/moving-load data against
their TypedDicts (`db/temperature_prestress.py`, `db/properties/material.py`,
`db/moving_loads.py`) and found four confirmed gaps — smaller in scope than
`/db/REBW` but the same species of defect (manual under-documents, `/info`
and real data reveal more):

1. **`/db/TDNT` (`TendonPropertyPayload`) was missing `bRELAX`** ("Relaxation
   coefficient - Check Box", boolean) — present in this model's real tendon
   data and in `/info/db/TDNT`, absent from both the manual's Specifications
   table and the TypedDict.
2. **`/db/TDPL` (`TendonPrestressItem`) was missing `GROUP_NAME`** ("Group
   Name", string) — same story: real data has `"GROUP_NAME": "PS1"` on every
   item, `/info/db/TDPL` confirms it, the manual's table doesn't mention it.
3. **`/db/TDMT` has a third code branch, `CODE="EUROPEAN"`, entirely
   undocumented.** This model's concrete (`C40/50`) uses it with two
   dedicated fields, `TCODE` (int) and `bSILICA` (bool), neither in the
   manual's table nor the TypedDict (which only covered CEB-FIP and ACI).
   `GET /info/db/TDMT` reveals this endpoint's real schema is far larger
   still — roughly 70 fields spanning many more codes (JSCE, GB, JTG, and
   others) — only the EUROPEAN branch's two extra fields were added; the
   rest is noted as a known gap, not fixed, in the TypedDict's own docstring.
4. **`/db/MVHL` (`VehiclePayload`) has 11 more country-specific sub-objects
   the manual never mentions at all.** `GET /info/db/MVHL` lists `VEH_FR`,
   `VEH_CN`, `VEH_IN`, `VEH_CA`, `VEH_BS`, `VEH_EUROCODE`, `VEH_RU`,
   `VEH_KSCE_LSD15`, `VEH_AU`, `VEH_PL`, `VEH_ZA` alongside the documented
   `VEH_DEFAULT`, plus a second load-items array `LOAD_ITEMS2`. This model's
   real Eurocode "Load Model 1" vehicle (`MVLD_CODE: 11`) uses
   `VEH_EUROCODE` instead of `VEH_DEFAULT` and — more surprising —
   **omits `STANDARD_CODE` entirely**, even though the manual's own
   Specifications table marks it "Required". `VEH_EUROCODE` itself has
   ~50 fields (`/info` schema) covering multiple Eurocode load-model
   sub-types (LM1/LM2/LM3, rail HSLM-A/B, permit loads); the flat scalar
   ones are now typed as `VehicleEurocodeParams`, with the three deeply
   nested, load-model-specific arrays (`LOADCASES`/`VEHICLES`/
   `PERMIT_LOAD`) left untyped, same treatment as `SECT_I`'s precedent.
   The other 10 country-specific sub-objects are confirmed to exist via
   `/info` but not individually typed — a real, larger backlog item if
   someone needs France/China/India/Canada/etc. moving-load support beyond
   what already works through `VEH_DEFAULT`.

All four fixed in `src/`, plus a new test (`test_vehicles_create_sends_veh_eurocode_without_standard_code`)
covering the `VEH_EUROCODE`-without-`STANDARD_CODE` shape. 681 tests passing,
ruff clean. This is a genuine `src/` correctness improvement (four
previously-unrepresentable real payload shapes now have accurate
TypedDicts) — adds to the pending version-bump case.

## 2026-07-30 (same day) — a real Eurocode railway bridge: confirms `VehicleEurocodeParams`, finds a CENT_F scope surprise

Model swapped again, same Civil session: a Eurocode railway bridge. Full
sweep 281/281 `ok` again; the `CIVIL_ONLY` railway-specific
`RailwayDynamicFactor` (`/db/DYFG`) has real, meaningful computed data
(`INPUT_TYPE: 0` = Auto, `DYN_FACTOR: 1.148...` computed) that matches
`RailwayDynamicFactorPayload` exactly — no drift.

`/db/MVHL` has three real Eurocode rail load models — "Load Model 71",
"Load Model SW/0", "Load Model SW/2" (`SUB_TYPE: 23`, distinct from Load
Model 1's `SUB_TYPE: 19` seen on the PSC bridge above) — using `W1`, `DD1`,
`D1`, `W2`, `DD2`, `D2`, `V_LOAD_FACTOR`, `LONGI_DIST`, `ECCEN_VERT_LOAD`.
**Every one of these fields was already covered by `VehicleEurocodeParams`**,
added minutes earlier from the PSC bridge's road-vehicle example — a second,
independent real-data confirmation of that fix, this time for the rail
load-model sub-type rather than the road one.

Also surfaced a genuine scope surprise in an *existing*, previously-trusted
note: `LineLaneItem.CENT_F` (`/db/LLAN`'s `LANE_ITEMS[].CENT_F`) was
documented "AASHTO LRFD only" after the 2026-07-29 finding that omitting it
under `MVCD.CODE="AASHTO LRFD"` gets rejected server-side. This Eurocode
railway bridge's own `LANE_ITEMS` carry the identical populated value
(`CENT_F: 0.5`) — same value as the AASHTO arch-bridge model. Left
unresolved rather than "corrected": it isn't yet clear whether CENT_F is
genuinely active under Eurocode too, or just echoed back inertly regardless
of code (as `FACT`/`WIDTH`/`ECCEN_VERT_LOAD` have been seen to be on codes
that don't use them). `LineLaneItem`'s docstring now flags this as an open
question rather than asserting either way — a candidate for a future
same-value-different-code write test if it matters to a caller.

## 2026-07-30 (same day) — a cable-stayed/suspension bridge: one more gap, `STAG`'s `NO`

Model swapped again to a cable-stayed bridge (this turned out to be the same
FCM model from earlier in the session — recognizable by its `ELNK` "Stay"
records at nodes 27/78 and 129/180, `LINK: "GEN"`, and a `GRUP` "Sag" node
group covering exactly those same two i-nodes for cable sag adjustment).
Full sweep 281/281 `ok` again.

Cross-checked `RigidLinkItem` (`/db/RIGD`, 49 real rows), `ConstraintItem`
(`/db/CONS`, 10 real rows), and `ElasticLinkPayload` (`/db/ELNK`) against
real data — all matched exactly, no drift.

`ConstructionStagePayload` (`/db/STAG`, 8 real stages including cable-sag-
specific ones that activate/deactivate the "Stay"/"Pin Connection" boundary
groups mid-sequence) was missing **`NO`** ("Construction Stage No.",
integer) — present in every real stage record and in `/info/db/STAG`, not
in the manual's Specifications table. Fixed. `DACT_BNGR`/`DACT_ELEM`'s
`REDIST` (element force redistribution %) were already correctly typed and
matched the real data exactly.

Running tally for 2026-07-30's cross-model spot-checking (four real
production Civil NX models: arch bridge, PSC bridge, railway bridge,
cable-stayed bridge): **6 schema gaps found and fixed** (`TDNT.bRELAX`,
`TDPL.GROUP_NAME`, `TDMT`'s EUROPEAN branch, `MVHL`'s `VEH_EUROCODE` +
10 other undocumented country sub-objects, `STAG.NO`), one open question
left unresolved (`CENT_F`'s true code scope), and one existing fix
(`VehicleEurocodeParams`) independently reconfirmed twice more against
different real Eurocode load-model sub-types. Zero drift found everywhere
else checked across all four models.

## 2026-07-30 (later) — first Gen NX pass of the day: a small solid-element cantilever model, `STLD.NO` gap

Switched to a fresh Gen NX session (v2.1, build 07/28/2026) with a small
real model open — not a bridge this time: a 5m x 0.4m x 0.2m concrete
block cantilever modeled as 10 `SOLID` (hexahedral) elements, fixed at one
end (`CONS` all-6-DOF on the 4 end nodes), one user-named load case
(`STLD` `"CASE1"`, `TYPE: "USER"`). Small model, but real (not `/doc/NEW`
scratch), and a different element family (`SOLID`) than anything spot-
checked so far this week (all bridge frame/beam models).

Full `live_readonly_sweep.py` re-run: 265/265 `ok`, zero newly-recorded
(all previously verified) — no regressions.

Cross-checked `MaterialPayload`/`MaterialParam` (`/db/MATL`, `P_TYPE=2`
isotropic concrete), `ElementPayload` (`/db/ELEM`, `TYPE: "SOLID"`),
`ConstraintItem` (`/db/CONS`), and `UnitPayload` (`/db/UNIT`) against real
data — all matched exactly.

`StaticLoadCasePayload` (`/db/STLD`) was missing **`NO`** ("Ordering Index
in GUI") — present in the real record (`{"NO": 1, "NAME": "CASE1", "TYPE":
"USER", "DESC": ""}`) and documented in the manual's own Specifications
table (`06_DB_Static_Loads.md`, marked "Read Only"), just never
transcribed into the TypedDict. Same class of gap as `STAG.NO` two
sections up — a read-only GUI-ordering field the manual documents but this
SDK hadn't typed yet. Fixed. `TYPE: "USER"` ("User Defined Load") is a
real documented code, not a mystery value — first row of the Load Type
table.

## 2026-07-30 (later still) — 🎉 `POST /db/NMAS` no longer crashes on Civil NX v2.2, build 07/29/2026

User reported MIDASIT shipped a patch and asked to verify. Fresh Civil NX
session, v2.2 build **07/29/2026** — one day newer than the build used for
reproductions #10-12 (v2.2 build 07/28/2026, see "final" root-cause
section above). Empty document (0 nodes), so no data at risk.

Reproduced the exact historical trigger on a raw `client.request()` call
(bypassing `NodalMass`'s own `rmX`/`rmY`/`rmZ` auto-fill workaround, which
would have masked the question): created node 1, `POST /db/NMAS` with only
`mX`/`mY`/`mZ` set — the omitted-rotational-fields shape that killed the
session in all 15+ prior reproductions across both products. This time:
**201 in 0.5s, session stayed alive.** Repeated on a second node (`mX/mY/
mZ` again omitted-rm) since the original bug specifically needed a *second*
call on a different node to trigger — same result, 0.1s, alive.
`verify_connection()` before/after both showed `"connected"`, and a
follow-up `GET /db/NMAS` showed both records with `rmX`/`rmY`/`rmZ` now
correctly defaulted to `0` server-side — meaning MIDASIT's fix isn't just
"stopped crashing", it's now applying the documented default like it
always should have. Cleaned up both test nodes/masses afterward; document
back to empty.

**This looks like a genuine server-side vendor fix**, not a fluke — same
account, same reproduction method that was 15/15 reliable before, now 2/2
clean on the newer build. Still only one account/session, so treat as
strong evidence rather than final confirmation (see the Caveat below); the
right trigger to fully retire `NodalMass`'s auto-fill workaround is
independent reproduction of the fix (different account/session, and a
matching Gen NX patch — this was Civil NX only, Gen NX's own last-known
build (v2.1, 07/28/2026) was not re-tested here and NMAS was never
observed to be product-specific anyway). **Not removing the workaround
yet** — it's harmless when the field is now defaulted correctly either way
(explicit `0.0` in, explicit `0` out), and removing it prematurely would
regress hard the moment someone hits this from an unpatched build.

## 2026-07-30 (later) — closing the "never GET-swept" gap: `/ope`, `/view`, `/post` plain-function endpoints

Coverage stood at 304/398 live-verified with 94 endpoints unaccounted for.
Checked why: `scripts/live_readonly_sweep.py` only discovers `DbResource`
subclasses (`_all_resources()` walks the class hierarchy), so the whole
`/doc/*`, `/ope/*`, `/view/*`, `/post/*`, `/DESIGN/*` families — all plain
functions per this SDK's own layout convention — were **never reachable by
the sweep regardless of whether they actually work**, not because they're
untested-and-risky. Some of them already had been tested live in earlier
sessions (`STORY_PARAM`/`STORY_IRR_PARAM` on 2026-07-29) without ever
getting a `coverage.json` entry, since nothing writes to that file except
the sweep script's `--record-coverage` flag.

With both Civil NX (v2.2, 07/29/2026) and Gen NX (v2.1, 07/28/2026)
connected, empty documents on both (0 nodes), manually probed the
GET-shaped subset of these plain functions directly (not through the
sweep tool, which doesn't know about them):

| Function | Endpoint | Civil | Gen |
|---|---|---|---|
| `ope.get_project_status` | `/ope/PROJECTSTATUS` | ok | ok |
| `ope.get_section_properties` | `/ope/SECTPROP` | ok (empty) | ok (empty) |
| `ope.get_story_check_parameter` | `/ope/STORY_PARAM` | 404 | ok |
| `ope.get_story_irregularity_check_parameter` | `/ope/STORY_IRR_PARAM` | 404 | ok |
| `view.get_selection` | `/view/SELECT` | ok | ok |
| `post.pre_process.get_material_table` | `/post/TABLE` (pre-process) | ok (empty) | ok (empty) |

`STORY_PARAM`/`STORY_IRR_PARAM`'s Civil 404 is now confirmed a **third**
time (previously: the 2026-07-29 sweep, then the same-day live re-check
with both products open) — solid evidence for the Gen-only restriction
that this SDK documents in the functions' own docstrings but doesn't
(and, being plain functions, can't cleanly) enforce client-side. All 6
recorded into `coverage.json`'s `live_verified` field; 310/398 total now.
`post.pre_process.get_material_table` was one spot-check standing in for
all 10 `TABLE_TYPE` values in that module (they share the same
`post.base.get_table()`/`unwrap_table()` plumbing) — the other 9 weren't
individually re-probed.

**Left deliberately untouched this pass — all mutate the model, the
document itself, or need a completed analysis first, so they get their
own explicit go-ahead rather than folding into this GET-only sweep:**

- `/doc/*` lifecycle (`OPEN`/`CLOSE`/`SAVE`/`SAVEAS`/`IMPORT`/`EXPORT`/
  `STAGAS`) — touches real files on the machine running NX; this file's own
  history has a confirmed `Program Files`-path modal-dialog trap for even
  GET-shaped calls, so a write-shaped one deserves more care, not less.
- `/ope/*` actions (`DIVIDEELEM`, `USLC`, `LINEBMLD`, `AUTOMESH`, `SSPS`,
  `EDMP`, `STOR`, `STORPROP`, `MEMB`, `GUSTFACTOR`, `LCOM-*`, `GSBG`) —
  real model mutations (mesh, load combos, story calc); both open documents
  are empty right now so there's nothing to safely exercise them against
  yet anyway.
- `/view/*` actions (`CAPTURE`, `PRECAPTURE`, `ANGLE`, `ACTIVE`, `DISPLAY`,
  `RESULTGRAPHIC`) — `CAPTURE`/`PRECAPTURE` write image files to the NX
  machine (same file-path risk class as `/doc/*`); the rest are harmless
  view-state toggles but weren't in this pass's scope.
- `/post/TABLE` (Analysis Result / Analysis Story categories) and
  `/DESIGN/*/*-ANAL` chapters — need a completed `/doc/ANAL` run first, and
  `*-ANAL` calls have a confirmed history of hanging Gen NX (see the
  `CC-ANAL`/`BC-ANAL` sections above) — short-timeout-and-poll discipline
  applies, not a plain probe.

## 2026-07-30 (later still) — a synthetic frame model, and a new crash candidate: `POST /ope/EDMP`

User authorized going further into the remaining `/ope/*`/`/view/*`/analysis
categories and building whatever model was needed ("모델 필요하면 직접
만들어서 진행해"). Built a synthetic 2-bay, 2-story steel frame on the same
empty Gen NX session (9 frame nodes + 4 unconnected quad nodes for a later
`AUTOMESH` attempt, 10 `BEAM` elements, 1 isotropic steel material, 1
`DBUSER` solid-rectangle section, base constraints, one `"DL"` load case,
two `/db/STOR` records) — all standard, previously-proven `/db/*` writes.

Ran a batch of the remaining mutating `/ope/*` actions against it:

| Action | Endpoint | Result |
|---|---|---|
| `assign_members` | `/ope/MEMB` | ok |
| `get_story_properties` | `/ope/STORPROP` | **404** (separate open question, see below) |
| `calculate_story` | `/ope/STOR` | ok — recalculated the two `/db/STOR` records' geometry-derived fields (`STORY_LEVEL`, `WIND_FLOOR_WIDTH_Y`, `WIND_CENTER_Y`, ...) from actual model geometry, overwriting the placeholder values seeded above; expected behavior for an auto-calculate action, not a bug |
| `divide_elements` | `/ope/DIVIDEELEM` | ok — split element 7 into two elements at a new midpoint node |
| `calculate_gust_factor` | `/ope/GUSTFACTOR` | ok |
| `change_property` (`TYPE="NSM"`, `AUTO=true`) | `/ope/EDMP` | 🛑 **30s read timeout, then Gen NX crashed** |
| `create_line_beam_load` | `/ope/LINEBMLD` | timed out — but this ran *after* EDMP already broke the session, so this failure doesn't mean anything about `LINEBMLD` itself; needs re-testing post-recovery |

**`POST /ope/EDMP` is a new crash candidate**, confirmed once: the call
itself read-timed-out (30s), a follow-up plain `GET /db/NODE` on the same
session also timed out, and `verify_connection()` still reported
`"connected"` throughout — the exact "modal dialog blocks every `/db/*`
call while `/mapikey/verify` keeps answering" pattern this file already
documents for other crashes. The user confirmed Gen NX showed the familiar
"[Error] Failed to disconnect the work session..." license dialog (same
one seen in the `/doc/NEW` and pre-fix `NMAS` crashes) — a full crash, not
just a slow call.

**Not yet root-caused.** Only one payload variant was tried
(`{"NODE_ELEMS": {"KEYS": [1,2,3]}, "TYPE": "NSM", "AUTO": true, "CODE":
"Korean Standard", "H_VS": 0.5}`, targeting 3 `BEAM` elements). Unlike the
`NMAS` saga, this is a single reproduction with no A/B isolation yet —
could be `EDMP` itself, the `AUTO=true` auto-calculate path specifically,
the `CODE` value, or something about the target elements. Flagged here
rather than pursued immediately; whether this gets the full NMAS-style
isolation treatment or just a documented-and-deprioritized flag (like the
`*-ANAL` hangs) is the user's call once Gen NX is back up.

**`/ope/STORPROP` (`get_story_properties`) 404'd** on its first-ever live
call, independent of the EDMP crash (it ran two calls earlier in the same
batch, before anything broke). Open question, not yet investigated:
possibly needs `calculate_story`/`/db/STOR` data in a different state,
possibly a genuine route issue, possibly a body-shape problem surfacing as
404 instead of a schema error (seen before in this project — worth
comparing against the manual's worked example rather than assuming the
docstring's `FORMAT`/`PLACE` guess is the actual cause).

## 2026-07-30 (later still) — after recovery: `LINEBMLD`/`AUTOMESH`/`LCOM-*` sorted out, then a second crash on `POST /ope/USLC`

Rebuilt the same synthetic frame (Gen NX's crash-recovery "New Project"
step discards the document, as expected) and continued through the
remaining `/ope/*` actions.

**`/ope/LINEBMLD` (`TARGET.METHOD`) sorted out**: `METHOD=0` (NODE-defined
load line) works exactly per the manual's own worked examples — confirmed
live with a `UNILOAD` on nodes `[7,8]`, echoed back correctly
(`D`/`P` padded to 4 elements: `[0.25, 0.85, 0, 0]` / `[-3, -3, 0, 0]`).
`METHOD=1` (selected elements) still fails identically a 3rd time
(`TYPE=UNILOAD` and `TYPE=CONLOAD`, both with a real, existing element in
`TARGET.ELEM`) — 3/3 `"Wrong Field"`, 0/1 success. Documented in
`ope.py`'s `LineLoadTarget` docstring as unconfirmed/likely broken; not
pursued further (no untried field found that changes the outcome).

**`/ope/AUTOMESH` needs boundary *elements*, and they must be frame-
capable (`BEAM`), not `TRUSS`**: the first attempt used `METHOD="Nodes"`
with 4 isolated, unconnected corner nodes and got a generic
`"MIDAS GEN NX second query is wrong"` — not a documented error string,
and not obviously about a missing field. Switching to `METHOD="Line
Elements"` with 4 boundary elements ringing the quad (plus adding the
`THICKNESS` the worked example includes but the Parameters table marks
merely "Optional") got further but still failed
(`"[Error] Invalid element list!"`) when those 4 boundary elements were
`TRUSS`. Rebuilding the same 4 elements as `BEAM` succeeded immediately,
generating 4 real `PLATE` elements. Reads as a genuine element-type
restriction (a `TRUSS` — no bending stiffness — plausibly can't bound a
meshed plate region) rather than a schema documentation gap; not written
up as a defect, just noted here since the manual doesn't say which line-
element types qualify.

**`/ope/LCOM-CONC`, `/ope/LCOM-STEEL`, `/ope/LCOM-SRC` all worked with a
minimal payload** (`{"OPTION": "ADD", "DGNCODE": "<per-endpoint code
string>"}` — every other field really is optional as documented), each
generating 2 real combinations (`STRENGTH`/`SERVICE`) from the model's
single `"DL"` load case. **`/ope/LCOM-GEN` (`CODE_SELECTION="CONCRETE"`)
failed with `"Wrong Field"`** on a payload built from the TypedDict's own
documented-required fields for that body
(`RS_SCALE_FACTOR:[]`, `ORTHO_EFFECT:{OPT_USE:false}`,
`ADDITIONAL_LOAD:{SPECIAL_LOAD:{OPT_USE:false},
VERTICAL_LOAD:{OPT_USE:false}}`, `CS_ANALYSIS:false`,
`PRESTRESS_LOSS:false`) — not yet investigated further, lower priority
since `LCOM-CONC` already covers the same design body successfully via
its own dedicated endpoint.

**🛑 `POST /ope/USLC` crashed Gen NX — a second, independent crash
candidate this session.** Payload: `{"POSITION": "CONC", "LCOM_LIST":
[{"TYPE": "CONC", "NAME": "cLCB1"}, {"TYPE": "CONC", "NAME": "cLCB2"}]}`,
referencing two real combinations that `LCOM-CONC` had just generated
successfully moments earlier in the same session. Same signature as the
`EDMP` crash: the call itself read-timed-out (25s), a follow-up plain
`GET /db/NODE` also timed out, `verify_connection()` still reported
`"connected"` throughout, and the user confirmed Gen NX itself was dead
("죽음") requiring the same New-Project-then-restart recovery.

**Two crash candidates from one session's `/ope/*` sweep (`EDMP`, `USLC`,
2 of 7 actions attempted) changes the risk calculus** — this isn't a
single fluke the way early `NMAS` reproductions looked, it's a live
~30% hit rate on this endpoint family so far. Deliberately **not**
continuing to blindly try the remaining untested actions (`SSPS`, `GSBG`)
without the user's explicit go-ahead each time; asked the user directly
whether to keep pushing through `/ope/*` (accepting the crash risk) or
switch to safer categories (`/view/*`, then analysis + result tables) and
leave the rest of `/ope/*` flagged-but-untested, the same way `*-ANAL` is
handled elsewhere in this file.

**`/ope/STORPROP` (`get_story_properties`) 404'd** on its first-ever live
call, independent of the EDMP crash (it ran two calls earlier in the same
batch, before anything broke). Open question, not yet investigated:
possibly needs `calculate_story`/`/db/STOR` data in a different state,
possibly a genuine route issue, possibly a body-shape problem surfacing as
404 instead of a schema error (seen before in this project — worth
comparing against the manual's worked example rather than assuming the
docstring's `FORMAT`/`PLACE` guess is the actual cause).

## 2026-07-30 (later still) — user accepted the crash risk; `SSPS`, `ANAL`, result/story tables, and both design-check `*-ANAL` families all pass

User explicitly chose to keep going despite the `EDMP`/`USLC` crashes
("계속 진행 (크래시 감수하고)"). Rebuilt the frame a third time (same
9-node/10-`BEAM` shape, no stories or quad nodes this round) and continued.

**`/ope/SSPS` worked cleanly, no crash**: `CONVERT_TO=POINT_SPRING`,
`ELEMENT.TYPE=FRAME` on two real `BEAM` elements, matching the manual's
own worked example almost exactly — generated real `/db/NSPR` point-spring
records with computed `SDR`/`Cr`/`EFFAREA`/`DK` fields.

**`/view/ANGLE`, `/view/ACTIVE`, `/view/DISPLAY` all worked, no crash** —
cosmetic view-state actions, as expected.

**`/doc/ANAL` timed out (30s) — but this was a save-confirmation dialog,
not a crash.** The call itself read-timed-out and the follow-up `GET
/db/NODE` also timed out, looking identical to the `EDMP`/`USLC` crash
signature — but the user checked Gen NX and found a plain "저장해달래"
(save-changes) prompt, not the "Failed to disconnect" crash dialog. This
is CLAUDE.md's already-documented "any confirmation dialog blocks the
whole session until dismissed" behavior, reproduced for `/doc/ANAL`
specifically for the first time in this file, and importantly: **not
every session-blocking dialog is a crash** — the two need to be told
apart by asking the user what's actually on screen, not assumed from the
timeout pattern alone. After the user saved, the session unblocked
immediately (model intact, 9 nodes) and a retried `/doc/ANAL` succeeded
in 5s.

**`/post/TABLE` (Analysis Result + Analysis Story categories) both
confirmed working** post-analysis: `get_reaction_table` and
`get_beam_force_table` (`result_1.py`) returned real per-node/per-element
rows (all zero, since the model's one `"DL"` load case never had an
actual load value assigned — expected, not a defect); `get_story_drift_table`
(`story.py`) returned a valid empty response (no lateral/seismic load to
report on). One spot-check per category, not all ~25/~16 table types.

**`/view/RESULTGRAPHIC` worked** (`CURRENT_MODE="reactionforces/moments"`)
now that real analysis results existed.

**Both design-check `*-ANAL` families tested — neither hung.** User
explicitly accepted the extra risk here too (this family's docstring
already warns of a documented Gen NX hang requiring a forced process
kill, a step beyond anything recovered from today via the graceful
New-Project dialog flow). `perform_steel_code_check` (`/DESIGN/STEEL/
KDS-41-30-2022/CODE-ANAL`, `PERFORM_TYPE=ALL`) and `perform_column_check`
(`/DESIGN/RC/KDS-41-20-2022/CC-ANAL`, same) both answered in under 2
seconds with clean, informative errors (`"failed:LoadCombination"` and
`"failed:Material, Section, LoadCombination, ElementType, Axis,
SectionType, SectionData, Rebar, Analysis, BeamData"` respectively) —
neither ever completed a full check, since the synthetic model has no
active load combination and (`CC-ANAL`'s case) no concrete/rebar data at
all. **This does not clear the historical hang risk** — the past hangs
happened on a real RC model with actual concrete/rebar data actually
reaching the design-check computation, a code path this synthetic model
never got close to. Follow-up `CC-TABLE`/`CODE-TABLE` calls also failed
cleanly (`"MIDAS GEN NX second query is wrong"`), no hang either.

**Two open questions parked, not resolved:**
- `/ope/STORPROP` 404'd a 3rd time even with real `/db/STOR` data present
  and `FORMAT="Default"` (the manual's own worked-example value) — ruling
  out both of the two leading hypotheses from the earlier attempt. Genuine
  cause still unknown; documented in `ope.py`'s `StoryPropertiesArgument`
  docstring.
- `/ope/LCOM-GEN` (`CODE_SELECTION="CONCRETE"`) still fails `"Wrong
  Field"` even with every documented-required field for that body
  present. Not pursued further since `LCOM-CONC` already covers the same
  design body successfully; documented in `generate_load_combination_general`'s
  docstring.
- A **second** `/ope/LCOM-STEEL` call (regenerating combinations on a
  fresh model iteration, this time to feed `CODE-ANAL`) failed
  (`"Set_DefaultLoadComb failed; check CheckLcom history..."`) after an
  earlier identical-shaped call had succeeded cleanly in a prior model
  iteration. Not reconciled — possibly some hidden state dependency,
  possibly unrelated to the payload at all.

Coverage after this whole multi-crash session: 328/398 live-verified
(+24 from the day's starting 304), covering `/ope/*`, `/view/*`,
`/post/TABLE`'s two analysis categories, and a first live pass at the
`*-ANAL` design-check family.

## 2026-07-30 (later still) — 🎉 `POST /db/NMAS` no longer crashes on Gen NX v2.1, build 07/30/2026 either

User reported MIDASIT shipped a Gen NX patch too and asked for the same
live re-verification already done for Civil. New build confirmed via the
About dialog: **MIDAS GEN NX 2026 (v2.1), build 07/30/2026** — one day
newer than every Gen build tested earlier this session (07/28/2026).

Mid-test wrinkle, not a defect: the session originally connected via a
saved key started answering `404 "client does not exist"` /
`verify_connection()` → `"disconnected"` — genuinely different from every
other disconnect signature seen this session (which always showed
`"connected"` while `/db/*` timed out). Turned out to be a **different
machine entirely**: the user runs Gen NX on two separate PCs (A and B)
with independent MAPI keys, and the originally-saved key was PC B's,
which had gone offline for an unrelated reason. The user supplied PC A's
key instead, which connected cleanly. `.env` updated with a note about
the two-PC setup so a future stale-key confusion is diagnosed faster.

On PC A's freshly patched session (0 nodes, scratch document): reproduced
the exact historical trigger — two nodes, two `POST /db/NMAS` calls each
omitting `rmX`/`rmY`/`rmZ`, the shape that reliably killed both products
before the fix. Both calls succeeded in 0.1s each, `verify_connection()`
stayed `"connected"` throughout, and the follow-up `GET /db/NMAS` showed
the server correctly defaulting the omitted fields to `0` itself — same
signature as Civil's confirmed fix earlier today. Test nodes/masses
cleaned up afterward; document back to empty.

**Both Civil NX (v2.2, 07/29/2026) and Gen NX (v2.1, 07/30/2026) now
confirmed fixed**, closing out the last open caveat from the Civil
confirmation ("Gen NX was not re-tested"). Still only one account/session
per product; independent reproduction (different account, or a third
session) would raise this from "strong evidence" to "settled". `NodalMass`'s
SDK-side auto-fill workaround stays in place regardless — see the earlier
Civil confirmation section's reasoning, which applies identically here
(harmless once the server also defaults correctly; still needed for
anyone on an unpatched build).

## 2026-07-30 (last) — `EDMP`/`USLC` crashes confirmed independent of NMAS's fix, filed as `MAPI-2425`/`MAPI-2426`

User asked to retry today's two `/ope/*` crashes (`EDMP`, `USLC`) on the
same Gen NX build just confirmed to fix `NMAS` (v2.1, 07/30/2026), to see
whether the same patch happened to fix them too.

**Both crashed again, on the first retry each.** `/ope/EDMP` with the
identical payload from earlier (`NODE_ELEMS.KEYS` on 3 real `BEAM`
elements, `TYPE=NSM`, `AUTO=true`) timed out at 25s; `verify_connection()`
came back `"disconnected"` this time (a different signature than earlier
today's `"connected"`-but-blocked pattern — possibly a harder crash, or
just a different failure mode of the same underlying issue). User
confirmed Gen NX had died and restarted it. `/ope/USLC` (`POSITION=CONC`,
referencing a real load combination) crashed identically on its retry
too, `"connected"`-but-blocked this time. **Conclusion: these are
independent defects from NMAS** — the patch that fixed `NMAS` did nothing
for either of them.

Side finding while rebuilding for the `USLC` retry: `/ope/LCOM-CONC` and
`/ope/LCOM-STEEL` (auto-generate load combinations), which had worked
cleanly with a minimal payload earlier the same day, now failed with
`"Set_DefaultLoadComb failed; check CheckLcom history (e.g. duplicate
LCOM names, name length, stage gate)."` on a freshly-restarted Gen NX
session with a brand new empty document — not explained, mentioned in the
`USLC` ticket as a possibly-related data point rather than claimed as
understood. Worked around by writing the combination directly via
`/db/LCOM-CONC` (the `DbResource`, not the `/ope/LCOM-CONC` generator) to
get `USLC` a real combination name to reference.

**Filed `MAPI-2425` (`/ope/EDMP`) and `MAPI-2426` (`/ope/USLC`)** under
epic MAPI-1200, both linked "relates to" `MAPI-2378` (NMAS) and to each
other, via the Atlassian MCP directly. A JQL search first ruled out an
existing duplicate — `MAPI-597` ("[OPE] Change Property") looked like a
candidate but is an unrelated, already-closed 2024 ticket about a
Confluence spec page, not a crash. Unlike `MAPI-2378`, neither new issue
claims a root cause — both are framed honestly as "reproduced twice
(pre- and post-NMAS-patch), trigger not yet isolated," asking MIDASIT to
check server-side logs rather than asserting a fix. Also noted: mid-session,
the "disconnected" `verify_connection()` reading once turned out to mean
a *different physical PC's* Gen NX had gone offline, not a crash on the
PC actually being tested — the user runs Gen NX on two machines (A/B)
with independent MAPI keys, so a stale-looking key needs checking against
"which PC" before assuming a crash.

Also worth flagging for anyone reading this file to decide what to test
next: the Gen NX session reconnected mid-troubleshooting with **710 real
nodes already loaded** (not the empty scratch document expected after a
crash-recovery New Project) — meaning at some point the user's own
real work was open in the same window this testing used. No write calls
were made against that state; testing stopped as soon as it was noticed.

## 2026-07-31 — Civil NX re-check of today's Gen-only confirmations, plus the LCOM-CONC/STEEL/SRC 404

With Civil NX v2.2 (build 07/29/2026) open on the same synthetic frame model
built earlier for the EDMP/USLC session, repeated the endpoints that had
only been spot-checked on Gen so far:

- `/ope/DIVIDEELEM`, `MEMB`, `GUSTFACTOR`, `SSPS` — all worked identically
  to Gen, same payload shapes.
- `/ope/LINEBMLD` — `TARGET.METHOD=0` confirmed working on Civil too
  (matching the manual's worked example, same as Gen); `METHOD=1` not
  re-tried here (already unconfirmed/likely broken on Gen).
- `/ope/AUTOMESH` — same element-type restriction found on Gen holds on
  Civil: 4 boundary elements as `BEAM` succeeded and generated real
  `PLATE` elements; `TRUSS` was not re-tried (already known to fail on Gen).
- `/view/ANGLE`, `ACTIVE`, `DISPLAY` — all worked identically to Gen.
- **New finding: `/ope/LCOM-CONC`, `LCOM-STEEL`, `LCOM-SRC` all 404 on
  Civil NX** with the identical minimal payload (`{OPTION, DGNCODE}`) that
  generates load combinations cleanly on Gen NX. Single reproduction per
  endpoint, on the same synthetic frame model shape used for the successful
  Gen calls earlier today. Documented in each function's docstring in
  `ope.py` (commit `3d2695e`), following the same "confirmed Gen-only, not
  enforced client-side" pattern already established for
  `STORY_PARAM`/`STORY_IRR_PARAM`.

Then continued into the items that hadn't been attempted on Civil yet at all:

- `/doc/ANAL` — ran clean, no save dialog this time (the model had already
  been saved from earlier work), matching the pre-existing 2026-07-22
  `live_verified` record for this endpoint (which already covered both
  products from `live_smoke.py`).
- `/post/TABLE` (Analysis Result category) — `get_reaction_table` and
  `get_beam_force_table` both returned real non-zero rows this time (the
  Civil model has AUTOMESH-generated plates with real self-weight, unlike
  Gen's earlier all-zero-load test) — expected, not a defect.
- `/post/TABLE` (Analysis Story category) — `get_story_drift_table` failed
  with `"there was an error creating utbl. (ex PostMode ...)"` on Civil.
  Not treated as a new defect: `/db/STOR` (Story data) was already
  confirmed Gen-only earlier in this SDK's history (`db/project.py`'s
  `Story.PRODUCTS = GEN_ONLY`), so a Story-table read having nothing to
  read on Civil is the expected consequence, not a route-level break.
  Not added to this endpoint's confirmed-products list.
- `CODE-ANAL` (steel) and `CC-ANAL` (RC column) — both re-ran cleanly on
  Civil, matching the Gen result: no hang, fast (`<2s`) informative
  "failed:..." errors listing missing prerequisites (load combination,
  material, rebar, etc.). Same caveat as the Gen finding applies: this
  doesn't clear the historically-hung code path, since the synthetic model
  still has no real concrete/rebar/load-combination data to reach it.

Civil session stayed `"connected"` throughout with no crashes. All of the
above recorded in `docs/coverage.json`, coverage steady at 398/398
implemented / 328/398 live_verified (this round only added products/method
detail to already-verified entries, no new endpoints crossed into
`live_verified` for the first time).

## 2026-07-31 (later) — a real production cable-stayed bridge on Civil NX closes 28 read-only gaps

The user loaded a real production model into the same Civil NX session
(v2.2, build 07/29/2026): 273 nodes, 278 elements (202 `TENSTR` cable-type
plus 76 `BEAM`), no analysis run yet, no design/rebar data. This is genuine
user data, not a scratch file — no write/execute call with any known crash
or hang risk was made against it; everything below is a GET-shaped POST
that only reads or reports "nothing to show yet."

**Closed 28 of the previously-unreachable `/post`/`/DESIGN` read-only
table endpoints** (coverage 328 → 356/398) by calling each with a minimal
valid argument and confirming the route + argument shape are accepted and
the error handling is clean:

- `/post/PM`, `STEELCODECHECK`, `BEAMDESIGNFORCES`, `COLUMNDESIGNFORCES`,
  `BRACEDESIGNFORCES`, `WALLDESIGNFORCES`, `STEELMEMBERDESIGNFORCES`,
  `SRCBEAMDESIGNFORCES`, `SRCCOLUMNDESIGNFORCES`,
  `COLDFORMEDSTEELMEMBERDESIGNFORCES` (`post/design.py`) — all answered
  `"Please Check/perform Analysis"` or `"there was an error creating utbl"`.
- `/DESIGN/STEEL/KDS-41-30-2022/CODE-TABLE` and `TABLE` — same "please
  perform analysis" / utbl error pattern.
- `/DESIGN/RC/KDS-41-20-2022/BD-TABLE`, `CD-TABLE`, `BRD-TABLE`,
  `WD-TABLE`, `HCD-TABLE` (`design_forces.py`) — all "please perform
  analysis".
- `/DESIGN/RC/KDS-41-20-2022/BC-TABLE`, `CC-TABLE`, `BRC-TABLE`
  (`checks.py`) initially failed `"Wrong Field"` with only `ELEMS` set —
  turned out `TABLE_TYPE` (`"MEMB"`) is required and I'd omitted it; once
  added, all three answered cleanly with "please perform analysis". Not an
  SDK defect, just an easy-to-miss required field matching `CODE-TABLE`'s
  own shape.
- `/DESIGN/RC/KDS-41-20-2022/WC-TABLE`, `TABLE` (x3, one physical route
  shared by Column/Brace/Beam Design Forces per its own docstring) — same
  pattern.
- `/DESIGN/SRC/AIK-SRC2K/BC-TABLE`, `CC-TABLE`, `TABLE` (x2, Beam/Column
  Design Forces sharing one route) — same pattern.

Session stayed `"connected"` throughout, no crashes, no hangs — but note
**none of these ever returned real populated data**, only clean
"nothing to check yet" errors, since the model has no analysis/design
results. Recorded in `coverage.json` as confirming route, argument shape,
and error-handling only; flagged for a follow-up pass once real analysis
and design results exist on a model like this.

**`/ope/STORPROP` re-confirmed 404 on Civil too** (previously only tried
on Gen), this time against real data, not a synthetic model. Consistent
with `/db/STOR` (Story) already being Gen-only, though the original Gen
404 itself was never root-caused, so "this whole route is Gen-only" stays
a plausible guess, not a confirmed fact. Noted in `StoryPropertiesArgument`'s
docstring.

**Explicitly NOT touched, and why** — all of these need either a real
file path on the NX host machine or the user's explicit go-ahead given
this is now real production data, neither of which was available/asked
for in this round:

- `/doc/OPEN`/`CLOSE`/`SAVE`/`SAVEAS`/`STAGAS`/`IMPORT`/`IMPORTMXT`/
  `EXPORT`/`EXPORTMXT` — need a safe file path from the user.
- `/view/CAPTURE`/`PRECAPTURE`, `*-REPORT` across all three design
  families, `DREULT`, `CDESIGN` — all require `EXPORT_PATH` (write a file
  on the NX machine); same blocker as `/doc/*`.
- All remaining `*-ANAL` "perform" endpoints (`BD/CD/BRD/WD/HCD-ANAL`,
  `BC/BRC/WC-ANAL` under RC-KDS, `BC-ANAL`/`CC-ANAL` under SRC) — this
  family has documented hang history (`perform_column_check`/
  `perform_wall_design`, see earlier 2026-07-25 sections); not run against
  real data without asking first.
- `/DESIGN/SRC/AIK-SRC2K/OCHECK` — iterative re-analysis/optimization,
  flagged in its own docstring as "never independently tested," at least
  as much risk as the `*-ANAL` family.
- `/DESIGN/SRC/AIK-SRC2K/DSRC` — PUT/DELETE-only config write (sets the
  active SRC design code); skipped rather than mutate a real model's
  settings without asking, even though it's likely low-impact.
- `/ope/LCOM-GEN` (still "Wrong Field" from 2026-07-30, not re-attempted:
  it's a write, and re-debugging it means adding combos to real data) and
  `/ope/GSBG` (needs a load combination with real analysis results plus a
  Bridge Group defined — this model has neither yet: `/db/STLD` shows only
  one `"Self Weight"` case, and there's no dedicated bridge-group `/db/*`
  resource in this SDK to create one via API).
- `/ope/EDMP`/`USLC` — already known Gen NX crashers (`MAPI-2425`/`2426`),
  not retried here at all (different product, and real data regardless).

## 2026-07-31 (later still) — a real modeling defect found and fixed on the bridge, then a real /doc/ANAL confirms post-analysis progression

Off to the side from SDK verification: the user spotted that the deck in
the 3D view looked like it was "standing up" instead of lying flat, and
asked me to check. Node-coordinate inspection showed the deck centerline
itself was correctly horizontal (X 0-657m, Y 5.5m constant, Z gently
curving 20.7-25.2m) with `ANGLE: 0` on every deck `BEAM` element (203-254)
— no rotation/orientation bug. The real cause turned out to be **`/db/SECT`
id 3 ("Deck"), a Box section with `H` and `B` swapped**: `vSIZE` was
`[11, 1.6, 0.04, 0.04, ...]` (11m tall, 1.6m wide) instead of the clearly
intended `[1.6, 11, ...]` (1.6m tall, 11m wide — matching the deck's real
11m Y-width exactly). Fixed live with the user's consent:

- `PUT /db/SECT` with `vSIZE[0]`/`vSIZE[1]` swapped succeeded, but **the
  `STIFF` sub-object (Area/Asy/Asz/RXX/RYY/RZZ — note: despite the `R`
  prefix these are moment-of-inertia-type values, not radii of gyration;
  the manual doesn't document this `STIFF` response shape at all for
  `/db/SECT`) was NOT recomputed by the PUT** — it stayed stale at the old
  H=11/B=1.6 numbers even after the geometry changed.
- The user opened the Section Data dialog in the Civil NX GUI and clicked
  "Calc. Section Properties", which recalculated Area/Asy/Asz/Ixx/Iyy/Izz
  correctly for the new H=1.6/B=11 shape **in the dialog only** — a
  follow-up `GET /db/SECT/3` still showed the old stale values until the
  user clicked OK to actually commit the dialog.
- After OK, `GET /db/SECT/3` confirmed the new values saved server-side
  (`AREA: 1.0016`, `RXX: 1.868`, `RYY: 0.559`, `RZZ: 12.525`,
  `CYP/CYM: 5.5`, `CZP/CZM: 0.8`, matching H=1.6/B=11 exactly).

**Takeaway for this SDK: `PUT /db/SECT` on a `SECTTYPE: "VALUE"` box
section only stores the raw dimensions — it does not auto-derive the
`STIFF` mechanical properties from them.** Anything writing `/db/SECT`
sections programmatically needs to either compute `STIFF` itself before
sending, or have a human recalculate via the GUI afterward — there's no
API-callable "recalculate now" action found in this chapter.

With the corrected section in place, the user asked to re-run analysis
and sanity-check the results. `POST /doc/ANAL` completed in 5s (no crash).
This model uses **Construction Stage Analysis** (`/db/STAG` has 8 stages,
CS0-CS7) rather than plain static load cases — `get_reaction_table`/
`get_cable_force_table`/`get_displacement_table` all returned `{"message":
""}` (empty) for ordinary `load_case_names` like `"Self Weight"` or
`"Self Weight(CS)"` until switching to **`load_case_names=["Summation(CS)"]`
with `opt_cs=True` and `stage_step=["CS7:001(last)"]`** (final stage, per
the manual's `"CS1:001(first)"`/`"CS1:002(last)"` format at
`19_POST_AnalysisResult_1.md:65`) — then all three returned real data:
symmetric reactions (844.4 tonf total, matching the bridge's mirror
symmetry exactly), all 202 cable elements in tension (none went slack/
compression after the section fix), and DZ displacement up to 2.37m
(flagged to the user as needing their own engineering judgment — cumulative
construction-stage displacement isn't directly comparable to a simple
span/400 serviceability check).

**Bonus finding while retesting `post/design.py` after the real analysis
existed**: `get_pm_interaction_diagram`'s error changed from `"Please
Check Analysis"` (pre-analysis) to `"Please Check RC Design Code"`
(post-analysis) — confirms the route correctly progresses through its
precondition chain rather than being stuck. `get_steel_code_check`
stopped erroring entirely post-analysis, now answering the `"empty"`
shape (nothing to report since no code check has been run, not a
failure). `BEAMDESIGNFORCES`/`COLUMNDESIGNFORCES`/
`STEELMEMBERDESIGNFORCES` still hit `"there was an error creating utbl"`
even post-analysis — these apparently need a load combination too, not
just an analysis result, which this model doesn't have yet (only the one
`"Self Weight"` load case exists, no `LCOM-*`).

## 2026-07-31 (later still) — 19 file-path/ANAL-family endpoints closed, then a new crash: `OCHECK`

With the user's go-ahead and a real safe path on the NX host machine
(`E:\MIDAS PROGRAM\temp`), closed 19 more endpoints on the real bridge
model (coverage 356 → 375/398):

**`/doc/*` lifecycle, verified as real round-trips, not just trusted
"command complete" responses:**

- `save_as()` to a new `.mcbx` file, then `open_project()` on that same
  path — reopened with all 273 nodes intact, confirming the write
  actually happened (per this SDK's own `save_as` docstring warning that
  a rejected path still answers "command complete").
- `close_project()` — succeeded, and a follow-up `GET /db/NODE` correctly
  answered `"The project is not opened"` (clean, not a hang) — then
  `open_project()` on the same file restored a fully working session.
- `save()` — succeeded (against the test file, not the original, since
  the open-document context had already switched via the `open_project()`
  round-trip above).
- `export_json()`/`export_mxt()` — both answered command-complete;
  **not** independently read back — see below for why `IMPORT` wasn't
  attempted, which is the same reason a round-trip verification wasn't
  either.
- `stage_as()` (`/doc/STAGAS`) — took 3 tries: `.mcbx` extension failed
  ("Please check the file name or extension"), then the post/TABLE-style
  qualified stage name `"CS7:001(last)"` failed ("Please specify the
  correct stage name"), then the plain stage name `"CS7"` (matching
  `/db/STAG`'s own `NAME` field) with a legacy `.mcb` extension succeeded.
  Both failures were **my own wrong guesses**, not a live defect — the
  manual's own worked example already shows exactly this shape
  (`STAGE_STEP: "Fase1"`, `EXPORT_PATH: "...FASE1.mcb"`). Updated
  `stage_as()`'s docstring in `doc.py` so the next person doesn't make the
  same guess from the parameter name alone.

**`/view/CAPTURE` and `PRECAPTURE`**: `capture()` with just `EXPORT_PATH`
succeeded cleanly. `precapture()` (fiber-section diagram) answered a
clean `"second query is wrong"` — this model has no fiber-modeled
sections, so the argument shape is confirmed but never produced real
data.

**Explicitly still skipped: `/doc/IMPORT`/`IMPORTMXT`.** Both are
additive/merging operations into whatever model is currently open — since
this is genuinely real production data, importing anything into it (even
a file exported from the same model) risks duplicating or corrupting
entities. These need a disposable scratch document (`/doc/NEW`) to test
safely, not this real bridge — not attempted this round.

**The `*-ANAL` "perform design check" family — 10 more endpoints, all
clean, no hang:** with the user's explicit go-ahead given the documented
hang history, ran `BD/CD/BRD/WD/HCD-ANAL` (`design_forces.py`),
`BC/BRC/WC-ANAL` (`checks.py`), and SRC's `BC-ANAL`/`CC-ANAL` — every one
answered `"Please perform analysis"` in under 1 second, no hang. Notably
this includes `WD-ANAL` (RC Wall Design Perform), the one endpoint in
this whole family with documented hang history on Gen NX 2026-06-23 — a
clean run here doesn't clear that history (this bridge has zero wall
elements, so it never got anywhere near the code path that hung before),
but it's one more data point of the endpoint behaving normally under
different conditions.

**🔴 New crash found: `POST /DESIGN/SRC/AIK-SRC2K/OCHECK`.** Called with
`ANALYSIS_OPT.ANAL_TIME=0` and `OUTPUT.MODEL_UPDATE=False` (deliberately
conservative, to avoid it silently rewriting real sections if it somehow
proceeded past validation) against a model with zero SRC-eligible
sections/materials. The client-side call timed out at 25s; a same-session
`GET /db/NODE` timed out too — the documented "connected but /db/* blocked"
signature of a native dialog holding the session. The user checked the
screen and found a **cascade of three dialogs**, distinct from every
other crash found this session (`EDMP`/`USLC` crash immediately with no
intermediate dialog):

1. `"Error Checking Result:"` listing every missing prerequisite (No
   Material/Section Shape/Section Type/Section Data/Load Combination/
   Member Type/Element Type/Design Axis/Reinforced Bar exists for
   Checking) — this is the same information every other `*-ANAL` returns
   as a clean JSON error; here it's a blocking native dialog instead.
2. `"Unacceptable model for optimal design."`
3. The familiar `"[Error] Failed to disconnect the work session due to an
   unidentified error..."` crash dialog, followed by `"Program will be
   closed due to an unexpected problem"` with an auto-recovery file path
   (`E:\MIDAS PROGRAM\temp\sdk_test_save_restore.mcb`).

After the user restarted Civil NX (re-execute → New Project → close,
per the dialog's own instructions) and reconnected with the same MAPI
key, the session recovered fully: 273 nodes intact, and `/db/SECT/3`'s
H/B fix from earlier this session (`vSIZE: [1.6, 11, ...]`) survived —
no data loss. **Not yet filed to MIDASIT Jira — needs the user's
explicit go-ahead first**, per the standing rule from the `EDMP`/`USLC`
filing earlier this session (see `MAPI-2425`/`2426`).

Coverage after this round: 375/398 implemented+verified; remaining gap is
`/doc/IMPORT`/`IMPORTMXT` (needs a scratch document), `/ope/LCOM-GEN`/
`STORPROP`/`GSBG` (unresolved or blocked on prerequisites not available
via API), `OCHECK` (now confirmed a crasher, not "verified working"),
`DSRC` (config write, skipped for consent), and the `*-REPORT`/`DREULT`/
`CDESIGN` family (still need real design results to test meaningfully,
which no `*-ANAL` on this model has produced — every one failed the
"please perform analysis"/prerequisite check, since this bridge has no
RC design code or load combination configured).

## 2026-07-31 (last) — Civil NX coverage closed out to 392/398: `*-REPORT` family, `DSRC`, `IMPORT`/`IMPORTMXT`, and a routing-level confirmation for `LCOM-*`/`STORPROP`

Closed the rest of what was tractable on Civil NX this session (375 → 392/398):

**All 12 remaining `*-REPORT` endpoints plus `DREULT`/`CDESIGN`** (Steel
`CODE-REPORT`, RC-KDS `BD/CD/BRD/WD/HCD/BC/CC/BRC/WC-REPORT`, SRC
`BC/CC-REPORT`) answered `"Please perform analysis"` cleanly with the
same `E:\MIDAS PROGRAM\temp` path — consistent with every `*-ANAL` on
this model failing the same precondition. `DREULT` answered `"It's
failed, Post Mode is not available"`; `CDESIGN` answered `"It's not
found Figure Name"` (needs a pre-existing named smart-report figure
config this model doesn't have) — both clean, route+shape confirmed, no
crash.

**`/DESIGN/SRC/AIK-SRC2K/DSRC` (config write) round-tripped cleanly**:
`PUT` with `DGNCODE="AIK-SRC2K"` succeeded, then `DELETE` reverted it —
both echoed the record back, no lasting mutation left on the real model.

**`/doc/IMPORT`/`IMPORTMXT` finally closed**, with the user's explicit
consent to `/doc/NEW` a disposable scratch document (discarding the FCM
test model from the `OCHECK` reproduction, which was no longer needed).
On the resulting empty document: `export_json()` → `import_json()` and
`export_mxt()` → `import_mxt()` both round-tripped cleanly, staying at 0
nodes throughout — no crash, no data corruption. This is the reason
these two were deliberately skipped earlier against the real bridge
model: additive/merge operations need a throwaway target, not production
data.

**`/ope/LCOM-GEN` retried with the simpler AIK-SRC2K schema** (`{OPTION,
DGNCODE: "AIK-SRC2K", RS_SCALE_FACTOR: []}`, vs the KDS:2022/CONCRETE
attempt that got "Wrong Field" on Gen 2026-07-30) — **404'd outright on
Civil**, a different and more definitive failure mode. Checked `GET
/info/ope/LCOM-GEN` and `/info/ope/LCOM-CONC` directly: **both also 404
on Civil** — the routes aren't registered on Civil NX at all, not just
failing at execution. This confirms at the routing level what was only
inferred before: **the whole `/ope/LCOM-*` family (`GEN`/`CONC`/`STEEL`/
`SRC`) is Gen-only**, closing the open question from LCOM-CONC/STEEL/
SRC's original Civil-404 finding (2026-07-30).

**`/ope/STORPROP` got the same `/info` check**: `GET /info/ope/STORPROP`
also 404s on Civil, matching the routing-level pattern above. Doesn't
explain why Gen also 404s on the same route (Gen's own `/info` was never
checked), so that half of the mystery stays open — but the Civil side is
now confirmed at the routing level rather than just inferred from a
failed POST.

**Final Civil NX tally: 392/398.** The 6 remaining are genuinely not
closeable from here:
- `/ope/EDMP`/`USLC` — confirmed Gen NX crashers (`MAPI-2425`/`2426`),
  a different product's problem to retest.
- `/ope/STORPROP`/`LCOM-GEN` — routing-confirmed 404 on Civil, but *why*
  Gen also fails (STORPROP) or exactly which field breaks (LCOM-GEN on
  Gen) is still open.
- `/ope/GSBG` — still blocked on a Bridge Group definition, which has no
  API-level way to create in this SDK's current endpoint coverage.
- `/DESIGN/SRC/AIK-SRC2K/OCHECK` — confirmed a genuine Civil NX crash,
  reproduced twice on two different bridge models (a cable-stayed bridge
  and an FCM bridge), filed as `MAPI-2429` (relates to nothing yet —
  linking left for the user to decide).

## 2026-07-31 (session end) — `GSBG` investigation on a real FCM bridge: two blockers understood, one still open

With explicit consent to "handle it freely," dug into why `/ope/GSBG`
(Bridge Girder Diagram Image Generation) has been unreachable all
session, using a real FCM (Free Cantilever Method) bridge model the user
opened (111 nodes, 106 `BEAM` elements, 17 construction stages —
`Pier1`/`Pier2`, `PierTable1`/`2`, `P1Seg1`-`12`, `P2Seg1`-`12`,
`KeySeg1`-`3`, `FSM1`/`2`, all as existing `/db/GRUP` entries).

**Corrected an earlier wrong assumption: `BRDG_GROUP` is just a plain
`/db/GRUP` name, not a GUI-wizard-only object.** `docs/manual/17_DB_Bridge.md`'s
`/db/GSBG` chapter (the DB-level sibling of `/ope/GSBG`) requires
`BODY_ELEM_GRUP_K`, an integer referencing a `/db/GRUP` group — proving
the "Bridge Girder Group" concept is exactly the general-purpose
Structure Group table this SDK already exposes as `StructureGroup`
(`db/project.py`, fully POST/PUT-capable). Split this model's 106 `BEAM`
elements into 82 horizontal (girder, ids 1-82, constant Z between
segment endpoints) vs 24 vertical (pier, ids 83-106, constant X) by node
geometry, then created a new group:

```python
StructureGroup.create({34: {"NAME": "Girder_All", "E_LIST": list(range(1, 83))}})
```

This succeeded and is now a permanent addition to this real model — worth
noting since `StructureGroup.PRODUCTS`/`METHODS` is `NO_DELETE_METHODS`,
so it can't be removed via this SDK; only through the Civil NX GUI if the
user wants it gone.

**First blocker, understood but not solvable via API alone: "post mode
is required."** Passing `BRDG_GROUP="Girder_All"` got past the
group-not-found stage into this error (matching `DREULT`'s "Post Mode is
not available" seen earlier on the cable-stayed bridge — the same
underlying gate, different wording). Ran a real `/doc/ANAL` first (46.6s
for this 17-stage FCM model, no crash), then tried `set_result_graphic()`
(`/view/RESULTGRAPHIC`, `TYPE: "CS", NAME: "Summation"`) — that itself
succeeded, but did **not** clear the "post mode" gate for `GSBG`. Only
the user manually clicking the "Post" tab in the Civil NX GUI did. No
API-only path into this mode was found this session.

**Second blocker, reproduced but not root-caused: "Final/PostCS stage is
not supported."** Once Post Mode was manually enabled, every `GSBG` call
hit this new error — and it did not change across `STAGE_LIST` values
`CS1`/`CS2`/`CS3`/`CS16`/`CS17` (the model's real final stage) or
`LC_NAME` values `"Self"`/`"Self(CS)"`/`"Summation(CS)"`. Since varying
the documented parameters had zero effect, this reads like leftover
document state — plausibly the earlier `set_result_graphic()` call's
`NAME: "Summation"` (itself a "Final/PostCS" aggregate result type)
stuck the document in a mode `GSBG` refuses to diagram from, rather than
anything wrong with the `GSBG` call's own arguments. Not confirmed before
the session ended.

**Net effect: `GSBG` went from "can't even test it" to "two of three
blockers understood, one open."** Recorded as still unverified in
`coverage.json` — a real success would need starting fresh (undo the
`Summation` result-graphic state, or open yet another session) and
confirming whether a plain single-stage `set_result_graphic()` call
avoids the "Final/PostCS" error.

## 2026-08-01 — Gen NX re-check of the 3 unresolved `/ope/*` cases (STORPROP, LCOM-GEN, OCHECK)

Connected to a fresh Gen NX session (PC A, user `sjj0507@midasit.com`) to
follow up on the endpoints left "no live_verified" in `coverage.json`,
skipping the two already-filed crashers (`EDMP`/`USLC`, `MAPI-2425`/`2426`)
and the blocked `GSBG`.

**`/ope/STORPROP` — 4th reproduction, still 404.** Same `FORMAT="Default"`,
`PLACE=4` payload that 404'd on 2026-07-30. Still fully unexplained; not
worth another blind retry without checking Gen's own `/info/ope/STORPROP`
(only Civil's has been checked, see the 2026-07-31 entry above).

**`/ope/LCOM-GEN` — new data point, still broken.** Only the KDS:2022/
CONCRETE schema had been tried on Gen before (2026-07-30, "Wrong Field").
Today's minimal AIK-SRC2K schema (`{OPTION, DGNCODE: "AIK-SRC2K",
RS_SCALE_FACTOR: []}`) reached the server (200, not 404 — confirms the
Gen route is genuinely live, unlike Civil's routing-level 404) but also
answered "Wrong Field". Both schema shapes now fail the same way on Gen;
root cause still unknown.

**`/DESIGN/SRC/AIK-SRC2K/OCHECK` — attempted, but not a real repro of the
Civil crash.** The open Gen document had **zero sections** (`/db/SECT`
empty) — not the "sections exist, none SRC-eligible" shape that crashed
Civil NX on 2026-07-31 (`MAPI-2429`). A fabricated `SECT_NO: 1` got a
clean `"Section 1 does not exist."` JSON error; a follow-up `GET /db/NODE`
confirmed the session stayed alive (0 nodes, matching the empty document).
**This does not clear Gen of the same crash risk** — it never reached the
code path that crashed Civil, since that path needs a real, existing,
non-SRC-eligible section to validate against. Re-test needed against a
real Gen model with actual section data before drawing any conclusion
either way.

**Net: no new crashes, no new working endpoints — just narrowed what's
already known.** All three remain open. Nothing filed to Jira from this
round (nothing new to report — LCOM-GEN's finding refines a symptom
already implicitly covered by `generate_load_combination_general`'s own
docstring, not a new bug).

## 2026-08-01 (later) — real Gen NX apartment model retest of OCHECK crashes; a new crash found on `KDS-41-20-2022/TABLE` (CD-TABLE), filed as `MAPI-2431`

Following up on the note above that the empty-document OCHECK attempt
didn't clear Gen of crash risk: reconnected to a fresh Gen NX session
(new MAPI key) with the user's real production "apartment" model open
(14,027 nodes, 476 sections) to retest against actual section data.

**`/DESIGN/SRC/AIK-SRC2K/OCHECK` crashed Gen NX on the real model.**
`verify_connection()` kept answering `"connected"` while every `/db/*`
call timed out, then the NX process itself died — the same signature
previously seen on Civil (`MAPI-2429`). Recovery cycle (dismiss dialogs
→ relaunch → New Project → close → reconnect with the same MAPI key)
completed with **no data loss**: post-recovery `/db/NODE`/`/db/SECT`
counts matched pre-crash exactly (14,027 / 476). This is the first
confirmation that the crash-recovery-without-data-loss pattern, well
established on Civil, also holds for Gen NX.

**Then a second, different crash: `POST /DESIGN/RC/KDS-41-20-2022/TABLE`
(Column Design Forces, `get_column_design_forces_table` /
`TABLE_TYPE_COLUMN_DESIGN_FORCES`).** Tried as the next step in the
RC/SRC design-code verification plan, on the assumption that a `TABLE`
read-back endpoint would be safe (no prior crash history for any
`*-TABLE` case) — that assumption was wrong. The very first call
produced the identical "connected but every `/db/*` call times out,
then the process dies" signature. Recovered the same way, again with
**no data loss** once the user reopened the apartment model.

To rule out leftover state from the OCHECK crash/recovery cycle as a
confound, reproduced independently: recovered to a **freshly-created,
completely empty** Gen document and issued the same `CD-TABLE` call in
isolation. Same crash signature, same recovery, same no-data-loss
outcome (trivially, since the document was empty). Two independent
reproductions (real populated model, isolated empty model) — meets this
project's bar for "confirmed," not just "unconfirmed single repro."

Filed as **MAPI-2431** (build: MIDAS Gen NX 2026 (v2.1), Build
07/30/2026), under epic `MAPI-1200`. Not linked to `MAPI-2429`/OCHECK —
different endpoint, no evidence of a shared cause. `get_brace_design_forces_table`/`get_beam_design_forces_table` share the same
underlying `TABLE` endpoint/helper and were not independently tested;
flagged as equally at risk in their docstrings until tested.

**Net for this session: two real crashes confirmed on Gen NX
(`OCHECK` via `MAPI-2429`'s Civil finding now also reproduced on Gen;
`CD-TABLE` newly found and filed as `MAPI-2431`), zero data loss across
both.** Further crash-risk testing on the real apartment model paused
per the user pending explicit re-confirmation — the working assumption
that `*-TABLE`/`*-REPORT` reads are inherently safe no longer holds and
each new candidate needs to be treated as a possible crasher until
tested.

## 2026-08-07 — patch verification: `MAPI-2425`/`MAPI-2426` fixed on both products; the predicted `get_beam_design_forces_table` risk confirmed; `MAPI-2429` closed as "not a defect"

Followed up on a fresh, previously-unseen crash found earlier the same
session (`get_beam_design_forces_table`, `POST /post/TABLE`,
`TABLE_TYPE_BEAM_DESIGN_FORCES` — hung Gen NX build 07/30/2026 on the
very first call of a `post/*` read sweep, ~4 minutes of timeouts before
the session died). The user then patched both products — About dialogs
confirmed **MIDAS GEN NX 2026 (v2.1), Build 08/06/2026** (patch v975,
see below) and **MIDAS CIVIL NX 2026 (v2.2), Build 08/06/2026** — and
asked to check whether previously-reported issues were resolved, and
whether the patch introduced anything new.

**Checked MIDASIT's internal Jira for what changed.** `MAPI-2425`
(`/ope/EDMP`) and `MAPI-2426` (`/ope/USLC`) — both filed 2026-07-30, both
originally Gen-NX-only reports — were marked **DONE** at 09:13-09:15 the
same morning the user patched, linked to a shared fix build
(`GEN_NX_US_D260806_T0910_N3547_r_b1_MR.zip`, v975). Root cause per the
vendor comment on `MAPI-2425`: `AUTO: true` internally still read
`PARAMETER` even though the manual only documents it as required when
`AUTO: false`; with `AUTO: true` and no `PARAMETER`, the code used the
missing value directly instead of guarding it, crashing the product. The
fix changes that path to return a proper error response instead of
crashing — it is **not** a requiredness change to `PARAMETER` itself, so
this SDK's existing docstring (`PARAMETER: ... required if AUTO=false` —
matching the manual exactly) needed no correction.

`MAPI-2429` (`/DESIGN/SRC/AIK-SRC2K/OCHECK` crash, filed against both
products) was closed the day before as **"결함 아님" (not a defect)** —
not because it doesn't crash, but because the endpoint itself is an
unofficial, paused-mid-development API that MIDASIT is renaming to a
`/TEMP/DESIGN/...` prefix (also affects `STEEL/KDS-41-30-2022/OCHECK`
and `SRC/AIK-SRC2K/DCHECK`). No fix timeline; still crash-prone by
design, not by accident.

**Retested `EDMP`/`USLC` live, on both products, with the exact
crash-reproduction payloads from the original reports.** Per the user's
standing permission to build disposable models for this ("모델은 안
중요해, 필요하면 더미 만들어서 테스트해도 됨"), built a minimal model on
each product from empty (`Material` "C24"/`KS01(RC)`, `Section`
400×400 `DBUSER`, two `Node`s, one `BEAM` `Element`, one `StaticLoadCase`
"DL", one `LoadCombinationConcrete` "cLCB1") and issued:

```json
POST /ope/EDMP
{"Argument": {"NODE_ELEMS": {"KEYS": [1]}, "TYPE": "NSM", "AUTO": true,
              "CODE": "Korean Standard", "H_VS": 0.5}}
```

```json
POST /ope/USLC
{"Argument": {"POSITION": "CONC",
              "LCOM_LIST": [{"TYPE": "CONC", "NAME": "cLCB1"}]}}
```

**Both products, both calls: no crash.** `EDMP` now answers
`MidasResultError("Unknown Error")` — a clean rejection, not a hang.
`USLC` now answers `{"message": "MIDAS <product> NX command complete"}`
— an actual success. `verify_connection()` confirmed healthy after every
call, on both Gen and Civil. Neither crash report was originally filed
against Civil NX (both said "Gen NX 세션 종료" only) — tested there
anyway since the fix build is shared, and it holds on Civil too.

**The `get_beam_design_forces_table` crash from earlier this session is
not a new, unfiled bug — it's the risk the 2026-08-01 entry above
already flagged and left untested.** That entry (`MAPI-2431`, Column
Design Forces) noted: *"`get_brace_design_forces_table`/
`get_beam_design_forces_table` share the same underlying `TABLE`
endpoint/helper and were not independently tested; flagged as equally at
risk."* `post/base.py`'s `get_table()` confirms this at the code level —
every `post.design.get_*_design_forces_table()` function, Beam included,
routes through the same `POST /post/TABLE` call with a different
`TABLE_TYPE`. This session's Beam crash is that prediction landing, on
build 07/30/2026 (pre-patch) — same failure signature as `MAPI-2431`
(long timeout, then every `/db/*` call fails, then the process dies).
Whether the 08/06 patch fixes this specific `TABLE_TYPE` the way it fixed
`EDMP`/`USLC` is untested — retesting it means deliberately repeating a
call already known to hang, so it stays paused pending the user's
explicit go-ahead, per "위험한 것은 마지막에."

**Net: two of three previously-reported crashes (`EDMP`/`USLC`) confirmed
fixed on both products by the same patch; the third (`OCHECK`) confirmed
not fixed and not going to be (unofficial API); `MAPI-2431`'s Column
Design Forces crash remains unresolved (IN PROGRESS) and its sibling
Beam Design Forces crash is now empirically confirmed rather than just
predicted.** No evidence of new, undocumented endpoints in this patch —
checked both `scripts/check_manual_drift.py` (`has_diff: false`) and a
7-day Jira sweep of `[MIDAS API]`-tagged issues (nothing beyond the six
already tracked here).

## 2026-08-07 (later) — `MAPI-2431` re-tested post-patch: still crashes, and MIDASIT couldn't reproduce it on their side

MIDASIT replied on `MAPI-2431` saying the same call worked fine in their
environment and asked for the model used to test it. Rather than share a
model file, re-tested two cases live on Gen NX (same patch build, v975,
build 08/06/2026) to characterize exactly when it does and doesn't crash:

**Case 1 — the currently-open real model, no design run yet: no crash.**
`POST /DESIGN/RC/KDS-41-20-2022/TABLE` with
`{"Argument": {"TABLE_NAME": "", "TABLE_TYPE": "COLUMNDESIGNFORCES"}}`
answered a clean empty `{}`, and a follow-up `verify_connection()`/
`GET /db/NODE` confirmed the session stayed healthy. This matches what
MIDASIT saw on their side.

**Case 2 — a completely blank document (`/doc/NEW`, confirmed 0 nodes via
`GET /db/NODE`): crashes, same signature as before.** The same call got no
response; `verify_connection()` then answered `"status": "disconnected"`
(notably accurate this time, not the usual false "connected") and
`GET /db/NODE` failed `404 client does not exist`. Gen NX needed a
restart.

This reconciles with the 2026-08-01 entry above, which also crashed on
both a real populated model (14,027 nodes, real section data) and an
isolated empty document — so the empty-document repro isn't new. What's
new is that **today's small real model (63 nodes) did not crash**, where
the much larger apartment model on 08-01 did. That's not enough evidence
to conclude the patch fixed anything for real models — the two "real
model" tests differ in more than just the patch (node count, whether any
design/analysis had been run, section data present or not) — but it does
mean the crash isn't purely a function of "real model vs. empty model."
The one variable that reproduces it reliably across every test so far,
pre- and post-patch, is **zero design data present** — trivially true for
a blank document, and possibly also true of the small 08-07 test model if
it turns out to have sections without any run design check. Reported both
cases back on the ticket with the exact repro steps (`/doc/NEW` then the
call above, no model file needed) since that's a strictly easier repro
path for MIDASIT than sharing a model.

Still `IN PROGRESS`, unresolved as of this entry.

## 2026-08-07 (later still) — the `TABLE`/`/post/TABLE` design-forces crash family is Gen-NX-only: full Civil NX sweep clean, plus a 43/43 `live_crud_check.py` reconfirmation

Following the `MAPI-2431` re-test above, checked whether the crash family
(everything sharing `post.design`'s `/post/TABLE` helper, and
`design.rc_kds.checks`'s sibling `/DESIGN/RC/KDS-41-20-2022/TABLE`
endpoint) is really Gen-specific, or just hadn't been tried on Civil yet.

**Civil NX, same patch build (v975-equivalent, build 08/06/2026), against
a real model (111 nodes, no design run yet):**

- `/post/TABLE`, all 8 `TABLE_TYPE` values in `post.design`
  (`BEAMDESIGNFORCES`, `COLUMNDESIGNFORCES`, `BRACEDESIGNFORCES`,
  `WALLDESIGNFORCES`, `STEELMEMBERDESIGNFORCES`, `SRCBEAMDESIGNFORCES`,
  `SRCCOLUMNDESIGNFORCES`, `COLDFORMEDSTEELMEMBERDESIGNFORCES`) — every
  single one answered a clean `200`-with-error-body `"there was an error
  creating utbl (ex PostMode ...)"`. No hang, no crash;
  `verify_connection()`/`GET /db/NODE` confirmed the session healthy after
  each call, node count unchanged (111) throughout.
- `/DESIGN/RC/KDS-41-20-2022/TABLE`, the two not yet covered
  (`BEAMDESIGNFORCES`, `BRACEDESIGNFORCES` — `COLUMNDESIGNFORCES` was
  already confirmed clean here back on 2026-07-31) — same clean
  `PostMode` error, no crash.

**Net: 11 of 11 tested combinations are clean on Civil NX; the only
confirmed crashes in this whole family remain the two already filed on
Gen NX** (`MAPI-2431`'s Column Design Forces via the `KDS-41-20-2022`
endpoint, and this session's Beam Design Forces via `/post/TABLE`, both
reproduced again post-patch). The remaining Gen-side combinations
(Brace/Wall/Steel/SRC/Cold-Formed via `/post/TABLE`, Brace via the KDS
endpoint) are still untested on Gen and are documented as "equally at
risk" rather than confirmed either way — this crash family looks
Gen-specific so far, but that's not the same claim as "safe on Gen for
the untested types."

**Separately, ran `scripts/live_crud_check.py --product civil` (all
tiers, no `--include-crashers`) against this same patch build: 43/43
resources completed a full create→read→update→read→delete→read round
trip, no failures.** This is a reconfirmation, not a new finding — all
43 cases were already `confirmed=True` as of 2026-07-29 per the script's
own tracking — but it's the first time they've all been re-run together
against the 08/06/2026 patch build, and nothing regressed. Note this
script creates its own scratch document via `/doc/NEW`, so it discarded
whatever was open beforehand (with the user's explicit go-ahead, since
that document didn't matter).

## 2026-08-07 (last) — full Civil NX `DbResource` GET sweep closes most of the read-coverage gap; `GEN_ONLY` reconfirmed unchanged

Prompted by a moment of confusion: after a run of Civil-specific findings,
it looked like Civil NX coverage might be "done." It wasn't — at the time,
only 195/399 endpoints had ever been live-verified on Civil at all (most
of this project's live sessions have skewed Gen-heavy). Ran the actual
numbers, corrected the misunderstanding, then closed as much of the real
gap as a single sweep reasonably could.

**`scripts/live_readonly_sweep.py --product civil --record-coverage`**
against build 08/06/2026 (confirmed via a Help > About screenshot: *MIDAS
CIVIL NX 2026 (v2.2), Build: 08/06/2026*) swept all 282 GET-capable
`DbResource` classes (everything in `db/*`, plus
`design.rc_kds.rebar`/`design.rc_kds.setup`/`design.steel_kds`/
`design.src_aiksrc2k`'s `DbResource`-based classes — the plain-function
`TABLE`/`ANAL`/`REPORT` endpoints in `design.rc_kds.checks` and
`doc.py`/`ope.py`/`post/*` aren't covered by this tool at all, since it
only enumerates `DbResource` subclasses). **All 282 answered ok** — no
failures, no crashes, session healthy throughout.

The script's own `--record-coverage` only writes a *new* `live_verified`
entry where none exists yet, so it undercounted: most of these 282 already
had a Gen-only `live_verified` entry from an earlier session, and the
script correctly declined to touch those (its docstring says so
explicitly — an existing entry is never overwritten). Wrote a one-off
merge script instead: for every endpoint this sweep confirmed `ok`, if its
existing `live_verified.products` didn't already include `"civil"`, add
it, append a short note, and cite this build. Matched primarily by
`(endpoint, module)`; a residual 21 entries use a wildcard module string
(`"midas_nx.db.properties.*"`) in `coverage.json` instead of the real
submodule, so those were matched by endpoint alone (checked for
uniqueness first) in a second pass. **172 endpoints gained a Civil
confirmation this way. `Verified on Civil NX` went 195/399 → 367/399.**

Separately, force-tested all 20 `GEN_ONLY`-tagged `DbResource` classes
against Civil NX (`strict_product=False`, bypassing the client-side
guard that normally blocks a product mismatch) — the same check that
originally established `GEN_ONLY` on 2026-07-29. **All 20 still 404 on
Civil**, identical to the original finding: no drift across two patch
cycles. `db/base.py`'s `GEN_ONLY` docstring now cites this reconfirmation
alongside the original evidence.

**What's left of the 32/399 still not live-verified on Civil:** almost
entirely the plain-function endpoints (`doc.py`/`ope.py`/`post/*`/
`design.rc_kds.checks`) that this sweep tool doesn't reach, several of
which overlap the Gen-only crash-risk family documented earlier this same
day (Column/Beam/Brace Design Forces and friends). Closing that remainder
needs per-module manual testing, not a single automated sweep, and was
deliberately deferred rather than rushed — see the still-open item at the
end of this file's history.

## 2026-08-10 — `BRACEDESIGNFORCES` confirmed crashing Gen NX, closing one more gap in the design-forces crash family

Continuing the Gen-side sweep of the `post.design`/`/post/TABLE` design-
forces crash family (Column and Beam already confirmed crashing, the
rest flagged "equally at risk" but untested): tried `BRACEDESIGNFORCES`
against a blank `/doc/NEW` document on Gen NX (build 08/06/2026, same
patch already confirmed crashing for Column/Beam). Same signature: no
response, then `verify_connection()` → disconnected, every `/db/*` call
→ 404. Gen NX needed a restart.

User paused the sweep here rather than continuing through the remaining
5 candidates (`WALLDESIGNFORCES`, `STEELMEMBERDESIGNFORCES`,
`SRCBEAMDESIGNFORCES`, `SRCCOLUMNDESIGNFORCES`,
`COLDFORMEDSTEELMEMBERDESIGNFORCES` via `/post/TABLE`, plus
`BRACEDESIGNFORCES` via the sibling `/DESIGN/RC/KDS-41-20-2022/TABLE`
endpoint in `design.rc_kds.checks` — still untested) — each confirmed
crash costs a full Gen NX restart, and three confirmed crashes
(Column/Beam/Brace, all via the same shared `/post/TABLE` helper) was
judged enough evidence for the pattern without burning through the rest
one restart at a time. Remaining candidates stay documented as "equally
at risk, untested" rather than confirmed.

## 2026-08-10 (later) — full Gen NX `DbResource` GET sweep, mirroring the earlier Civil sweep

After confirming Gen coverage had a much bigger gap than Civil (132/399
endpoints never live-tested on Gen at all — this project's live sessions
have skewed Civil-heavy since the FCM bridge model work), ran the same
tool used for the Civil sweep, this time against Gen:

**`scripts/live_readonly_sweep.py --product gen --record-coverage`**
against build 08/06/2026, on a blank `/doc/NEW` document (post-crash
restart from the `BRACEDESIGNFORCES` finding above): swept all 266
GET-capable `DbResource` classes applicable to Gen — **all 266 answered
ok**, no failures, no crashes, session stayed healthy throughout and
after.

Same merge-script approach as the Civil sweep (the tool's own
`--record-coverage` only adds a *new* entry, so a one-off script added
`"gen"` to existing Civil-only `live_verified.products` wherever this
sweep confirmed it): **32 endpoints gained a Gen confirmation this way.
`Verified on Gen NX` went 266/399 → 299/399.** A smaller jump than the
Civil sweep's 172, because most of the remaining gap here is
plain-function endpoints (`doc.py`/`ope.py`/`post/*`/
`design.rc_kds.checks`/`design.rc_kds.design_forces`/
`design.src_aiksrc2k`'s ANAL/TABLE/REPORT triads) this tool doesn't
reach — including the crash-risk family from earlier today, which stays
untouched by this GET-only sweep by design.

Explicitly paused here rather than continuing into those plain-function
modules: several overlap the confirmed Gen crash-risk family, and the
RC/SRC/Steel `*-ANAL` triads have their own independent Gen-hang history
(see the 2026-08-01 entries above) — closing the remainder needs
per-module manual testing with explicit go-ahead each time, not another
single automated sweep.

## 2026-08-10 (last) — non-crash-family ANAL/TABLE/REPORT/CAPTURE batch on Gen NX: 40 endpoints, no crash/hang, all recorded

Continuing the `DbResource` sweep's leftover gap: the plain-function design
chapters (`design.rc_kds.design_forces`, `design.rc_kds.checks`,
`design.steel_kds`, `design.src_aiksrc2k`, `view.py`) that the GET-only
sweep can't reach. Explicitly excluded from this batch: the confirmed/
at-risk Design-Forces crash family (`post.design`'s 8, `checks.py`'s
Column/Brace/Beam Design Forces `TABLE`, `steel_kds.py`'s
`TABLE`=`STEELMEMBERDESIGNFORCES`, `src_aiksrc2k.py`'s `TABLE`=
Beam/Column SRC Design Forces — all share the same `*DESIGNFORCES`
`TABLE_TYPE` naming convention as the confirmed Column/Brace/Beam crashes)
and `src_aiksrc2k.py`'s `OCHECK` (confirmed crashing both products,
`MAPI-2429`, already recorded separately).

Correction to the earlier "22 crash-family" figure quoted mid-session:
that overcounted by treating all 14 untested `checks.py` entries as
crash-family, when only 3 of them (Column/Brace/Beam Design Forces) are.
The other 11 (`BC`/`CC`/`BRC`/`WC`-ANAL/TABLE/REPORT, `CDESIGN`) are
unrelated check/report functions — `BC-ANAL`/`CC-ANAL` were already
re-verified clean via the QuickRebar NX production tool (2026-07-25),
and `WC-ANAL` was independently confirmed to NOT reproduce the CC-ANAL
stall. The real crash-family total across all modules is 11 Design-Forces
functions + `OCHECK`, not 22.

Ran against a blank `/doc/NEW` document (0 nodes/0 elements, same one
left over from the `DbResource` sweep), in two batches:

**Category A (29 calls, no ANAL/PERFORM prerequisite)** — `view.CAPTURE`/
`PRECAPTURE`; `design_forces.py`'s BD/CD/BRD/WD/HCD `*-TABLE`/`*-REPORT`
(10); `checks.py`'s BC/CC/BRC/WC `*-TABLE`/`*-REPORT` + `CDESIGN` (9);
`steel_kds.py`'s `CODE-TABLE`/`CODE-REPORT`/`DREULT` (3, `TABLE` skipped
as crash-family-adjacent); `src_aiksrc2k.py`'s BC/CC `*-TABLE`/`*-REPORT`
(4, `TABLE`/`OCHECK` skipped). All 29 answered cleanly with informative
refusals (`"Please perform analysis."`, `"It's not found Figure Name"`,
`"Wrong Field"`, `"Post Mode is not available"`) — no crash, no hang,
session alive after every call.

**Category B (12 `*-ANAL`/`*-PERFORM` calls, 25s timeout)**, run only
after explicit user go-ahead given the documented Gen-hang history on
this family (WC/BC/CC/BRC-ANAL, BD/CD/BRD/WD/HCD-ANAL, `CODE-ANAL`, SRC
BC/CC-ANAL — `WD-ANAL` deliberately tested last, being the one with
confirmed historical hang evidence). All 12 answered in <1s with the same
clean `"Please perform analysis."` refusal, immediately followed by a
`*-TABLE` read-back (per the established mitigation pattern) and a
`/db/NODE` session-alive check — no hang anywhere, including `WD-ANAL`.
Plausible explanation: the historical hangs were reproduced specifically
*with* real rebar/analysis data to process; against 0 elements the server
has nothing to "Convert Design Results" for and fails fast instead. This
does **not** clear the historical hang risk for real models — it's a
second data point (blank-document-is-safe), not a fix confirmation.

Recorded via a one-off merge script (same `(endpoint, module)`-matching
approach as the two `DbResource` sweeps): **38 endpoints gained a new Gen
confirmation** (2 — `CC-ANAL`, `CODE-ANAL` — already had one from an
earlier session). `Verified on Gen NX` went 299/399 → 337/399.

Remaining real gap on Gen: the crash-family (11 Design-Forces functions,
already characterized as crashing/at-risk, not "unverified"), `OCHECK`
(confirmed crashing, ditto), and `doc.py`'s 9 file-lifecycle endpoints
(`OPEN`/`CLOSE`/`SAVE`/`SAVEAS`/`STAGAS`/`IMPORT`/`IMPORTMXT`/`EXPORT`/
`EXPORTMXT` — deliberately not attempted against a session with real
state at risk) plus `ope.py`'s 3 already-investigated-and-blocked cases
(`STORPROP`/`LCOM-GEN`/`GSBG`).

**`coverage.json` correction (2026-08-11):** the 2026-08-10 batch's merge
script had recorded the Gen version as `v2.2` (copy-pasted from Civil's
version string) on all 38 entries it touched — Gen was never on v2.2.
Corrected all 38 to `MIDAS Gen NX 2026 (v2.1), build 08/06/2026`, the
build actually used that session. Caught via a fresh connection check
this session: About dialog showed **Gen NX 2026 (v2.1), build
08/11/2026** (user `sjj0507@midasit.com`).

**Connection-check tooling bug, same session:** the first pass of both
this Gen check and a following Civil check (About dialog: **Civil NX
2026 (v2.2), build 08/11/2026**) called `MidasClient(..., base_url=
"https://moa-engineers.midasit.com")` — overriding the default and
stripping the required `/gen`/`/civil` product path segment that
`build_base_url()` normally appends. `verify_connection()` still
succeeded (its URL-strip logic in `client.py` tolerates either form),
masking the bug, but every `/db/*` call landed on a route that doesn't
exist and returned a generic 404 — misread at the time as "blank
document, 0 nodes." Re-run without the `base_url` override: `Node.get()`
→ `{"message": ""}` on both products, the correct **zero-row** shape —
so both sessions genuinely are on blank documents, same conclusion as
before, but now for the right reason. No SDK code was at fault — the
bug was in the ad hoc verification script, not `client.py`.

**`OCHECK` re-tried on Civil (v2.2, build 08/11/2026) with the corrected
client**, at the user's request to re-attempt Civil's known crash
(`perform_src_optimal_design`, `docs/live_verification_notes.md`'s
2026-07-31 "New crash found" section). Same shape as Gen's 2026-08-01
attempt: a fabricated `SECT_NO: 1` against a document with zero sections
got a clean `MidasResultError` — `"Section 1 does not exist."` — and a
follow-up `Node.get()` confirmed the session stayed alive
(`{"message": ""}`). **Not a repro of the 2026-07-31 crash** — that
needed a real, existing, non-SRC-eligible section to reach the crashing
code path, which this blank document doesn't have. Narrows nothing new;
the crash risk on real Civil models with real sections stands as
documented.

**Quick full Civil-gap sweep, same session.** Of the 11 endpoints
`coverage.json` listed as not-yet-`civil`-verified, 9 turned out to
already carry a conclusive Civil finding recorded only in their
docstring/method text (not reflected in `live_verified.products` because
the finding is negative): `STORY_PARAM`/`STORY_IRR_PARAM` (confirmed
404, 3rd+ repro), `/post/TABLE` story types (confirmed error, 2 sweeps),
`STORPROP`/`LCOM-GEN`/`GSBG` (dead route or unmet precondition on every
product, not Civil-specific), `LCOM-CONC`/`LCOM-STEEL`/`LCOM-SRC`
(confirmed 404 — "the whole `/ope/LCOM-*` family's routes aren't
registered on Civil at all," per `generate_load_combination_concrete`'s
existing docstring). Retesting these would only reconfirm known dead
routes/blocked preconditions, so only the 2 genuinely untested ones were
run:

- **`/ope/STOR` (Story Calculation) — 404 on Civil**, first direct test
  against this product (`SEIS_ECC`/`WIND_ECC` both disabled, blank doc).
  Extends the story family's Gen-only pattern to cover this endpoint too.
- **`/view/RESULTGRAPHIC` — route IS registered on Civil**, unlike the
  story family: `CURRENT_MODE=reactionforces/moments` against a blank
  doc (no analysis run) got a clean `MidasResultError`, `"MIDAS CIVIL NX
  Empty Load Case Type"`. Session stayed alive. Added `civil` to its
  `live_verified.products` — same standard as the 2026-08-10 Gen batch
  (a clean, correctly-shaped rejection counts as verified request
  handling, not "no data").

Both `Node.get()`-checked alive after each call. No crash, no hang.
`docs/coverage.json` and both functions' docstrings (`ope.py`,
`view.py`) updated; `ROADMAP.md` regenerated.

**Full write round-trip + per-endpoint PUT sweep, same session, Civil NX
v2.2 build 08/11/2026.** `scripts/live_smoke.py --product civil` run
against the blank connected session: `/doc/NEW` → `UNIT` → `MATL` (C24)
→ `SECT` (600×600 DBUSER column) → 2×`NODE` → `ELEM` (beam) → `CONS`
(fixed) → `STLD` (DL) → `BODF` (self-weight) → `/doc/ANAL` →
reaction/displacement/beam-force tables, all 13 steps `ok: true`;
reaction `FZ` = 27.11 kN vs. 28.22 kN hand-calc, within the script's 5%
tolerance.

Followed by a dedicated PUT-only sweep (change → GET-verify → revert →
GET-verify per endpoint, on the 8 resources the smoke test had just
populated): `UNIT`, `MATL`, `SECT`, `NODE`, `ELEM`, `CONS`, `STLD`,
`BODF` — all 8 changed and reverted cleanly, confirmed via a follow-up
GET each time. One cosmetic-only observation: `SECT`'s `vSIZE` readback
comes back zero-padded to a fixed 10-element array
(`[0.6, 0.6, 0, 0, 0, 0, 0, 0, 0, 0]`) rather than echoing the 2-element
list that was sent — not a defect, just the server's storage shape for
a variable-length dimension array. `Node.get()` confirmed the session
alive throughout. All 8 of these endpoints were already `civil`-verified
at `level: "write"` in `coverage.json` (from earlier `create()`-only
testing) — this sweep specifically exercised `update()`/PUT, which
hadn't been individually confirmed before, so no new coverage entries,
just a stronger evidence base behind the existing ones.

## 2026-08-11 (later) — full Gen NX crash-family re-test: 15 previously-crashing/at-risk calls, 0 crashes this time

At the user's explicit request to re-test "everything that had crashed on
Gen," and after correcting an initial mis-framing (told the user this
would likely be inconclusive on a blank document like `OCHECK` — wrong:
`get_beam_design_forces_table()`'s own docstring already documented a
confirmed crash *on a blank `/doc/NEW` document*, so the risk was real,
not just theoretical). User re-confirmed proceeding anyway with the
corrected risk understanding.

**Batch 1 — 11 previously-unverified-on-Gen crash-family functions + `OCHECK`**,
called one at a time against the connected blank Gen session (0 nodes),
`Node.get()` health-checked after every single call, ready to stop
immediately on the first failure:
`checks.get_brace_design_forces_table`, `checks.get_beam_design_forces_table`,
`steel_kds.get_steel_member_design_forces_table`,
`src_aiksrc2k.get_src_beam_design_forces_table`,
`src_aiksrc2k.get_src_column_design_forces_table`,
`post.design.get_column_design_forces_table`,
`post.design.get_wall_design_forces_table`,
`post.design.get_steel_member_design_forces_table`,
`post.design.get_src_beam_design_forces_table`,
`post.design.get_src_column_design_forces_table`,
`post.design.get_cold_formed_steel_member_design_forces_table`, and
`perform_src_optimal_design` (`OCHECK`, zero-section precondition, same
non-repro shape as the existing 2026-08-01 finding). All 12 answered
cleanly (mostly empty-table responses), session alive throughout.

**Batch 2 — the 3 *already-confirmed-crashing* cases**, re-tested next
since "전부" (all) includes these: `post.design.get_brace_design_forces_table`
(`BRACEDESIGNFORCES`), `post.design.get_beam_design_forces_table`
(`BEAMDESIGNFORCES`), and `checks.get_column_design_forces_table`
(`MAPI-2431` — reproduced twice independently across different models,
re-confirmed *not fixed* as recently as 2026-08-07, the single
strongest repro in this whole family). All 3 — including MAPI-2431 —
answered cleanly this time too. Session alive after all 3.

**Total: 15 of 15 calls clean, zero crashes, zero hangs**, against Gen NX
2026 v2.1, build 08/11/2026 (previous crash confirmations were on build
08/06/2026 and earlier).

**This is not being called "fixed."** One clean pass against a
historically-confirmed crash doesn't distinguish "the vendor fixed it"
from "the crash is intermittent/non-deterministic" — and MAPI-2431's own
history already shows non-monotonic behavior (crashed on a blank
document, clean on a 63-node real model, in the same 2026-08-07 session).
Every affected docstring and `coverage.json` entry now carries today's
result as an additional data point, explicitly flagged as
"reduced-but-not-cleared," not a resolution. An independent second
re-test — ideally against real, populated model data rather than a
blank document, since that's the condition never yet cleanly tested for
most of this family — is the next real step, not a documentation
close-out.

`docs/coverage.json` (15 entries updated/extended), `ROADMAP.md`
(regenerated), and the docstrings in `post/design.py`, `checks.py`,
`steel_kds.py`, `src_aiksrc2k.py` (10 functions) all updated with
today's finding. `ruff check` and the full test suite (701 tests) both
pass.

**`DSRC` (SRC Design Code) tested on Gen, same session, after the Civil
session was closed.** Previously deferred pending consent (config-write,
no `GET` to verify state either way). `PUT {"DGNCODE": "AIK-SRC2K"}`
against Gen NX (v2.1, build 08/11/2026, blank document) succeeded,
echoed back cleanly, session stayed healthy. Not a full round trip like
the existing 2026-07-31 Civil test (PUT + DELETE) — `DELETE` wasn't
re-tried this pass. `coverage.json` gains `gen` in `live_verified.products`;
its `level` was also corrected `read` → `write` (it's a `PUT`, not a
read, regardless of which product tested it first).

## 2026-08-13 — new patch on both products: connection check only

User applied a new patch to both products and asked to confirm both
connect, with versions recorded. `verify_connection()` against fresh
`.env` MAPI keys (last-occurrence-wins for the duplicated
`MIDAS_MAPI_KEY_GEN`/`MIDAS_MAPI_KEY_CIVIL` lines) succeeded for both:

```text
GEN:   {'user': 'sjj0507@midasit.com', 'program': 'gen',   'connectionID': 'N-pAmlMjSg', 'keyVerified': True, 'status': 'connected'}
CIVIL: {'user': 'sjj0507@midasit.com', 'program': 'civil', 'connectionID': 'WjbfiHlPSw', 'keyVerified': True, 'status': 'connected'}
```

About-dialog screenshots confirm the new build:

- **MIDAS GEN NX 2026 (v2.1), build 08/12/2026** (previous: 08/11/2026)
- **MIDAS CIVIL NX 2026 (v2.2), build 08/12/2026** (previous: 08/11/2026)

Same version numbers as the prior patch, one-day-newer build only —
consistent with a routine patch rather than a version bump.

## 2026-08-13 (later) — `/db/NMAS` raw crash-trigger re-repro on Civil NX: server-side bug looks actually fixed now, not just SDK-masked

User asked whether the crash-family items flagged earlier in this file
were all resolved on Civil NX. Answer at the time: `NMAS` — SDK-safe via
the `rmX`/`rmY`/`rmZ` auto-fill workaround, previously confirmed the
*server itself* no longer crashed as of Civil NX v2.2 build 07/29/2026;
`OCHECK`/`perform_src_optimal_design` (`MAPI-2429`) — still open, closed
by MIDASIT as "not a defect" (unofficial paused-development API being
moved to `/TEMP/...`), crash risk on real models with real sections never
actually retested. User asked to proceed with `NMAS` first, then
explicitly asked for the raw repro (bypassing the SDK workaround) to
check the server's current state directly, accepting the session-death
risk that trigger has historically carried.

Against Civil NX v2.2, build 08/12/2026, on a blank connected document:

1. **SDK-safe path first** (sanity check): created `Node` 1, then
   `NodalMass.create({1: {mX:1, mY:1, mZ:1}})` (rm fields omitted from
   the call, auto-filled to `0.0` by the SDK before sending) — clean
   `201`, read back correctly, session alive. Cleaned up.
2. **Raw repro**, bypassing `NodalMass.create()` entirely via
   `client.request()` directly: created `Node` 1 and `Node` 2. Control
   call — `POST /db/NMAS` on node 1 with all six fields explicit
   (`mX/mY/mZ` + `rmX/rmY/rmZ: 0.0`) — succeeded in 0.2s. **Trigger
   call** — `POST /db/NMAS` on node 2 with `rmX`/`rmY`/`rmZ` omitted
   entirely (the exact payload shape that reproduced the crash 15+ times
   across both products pre-fix) — succeeded in **0.1s**, no timeout, no
   hang. `GET /db/NMAS` read back node 2 with `rmX: 0, rmY: 0, rmZ: 0` —
   **the server itself now applies the documented default**, rather than
   reading an uninitialized value. Follow-up `verify_connection()` and
   `Node.get()` both confirmed the session fully responsive immediately
   after. Test data (`NMAS` + both nodes) deleted, document back to
   blank, session still `connected` throughout and after.

Historically this exact omitted-fields call took 15-60s and then killed
the session; here it returned in under a second with a correct result.
That's a materially stronger signal than the 07-29 finding (which only
established "doesn't crash," not "applies the right default") —
consistent with MIDASIT having actually fixed the uninitialized-value
bug server-side, not just gotten lucky on one retest. **Not** changing
`NodalMass`'s SDK-side workaround based on this single repro on one
account/build — the class still fills `rmX`/`rmY`/`rmZ` explicitly, since
that costs nothing, remains correct regardless of server state, and this
is one data point on one build, not proof the fix is universal across
every deployed installation. Only tested on Civil this session; Gen not
re-repro'd today (its own last confirmation was 2026-07-30, build
07/30/2026).

## 2026-08-13 (last) — `OCHECK`/`MAPI-2429` re-repro'd on Civil NX with the real trigger shape: still crashes on the current patch

After the NMAS reconfirmation above, asked whether Civil's crash-family
items were "all resolved." Answer: `NMAS` yes (see above), `OCHECK`
(`perform_src_optimal_design`, `MAPI-2429`) no — MIDASIT closed it "not a
defect," no fix timeline, and the 2026-08-11 retest never actually
reached the crashing code path (zero-section document). User asked to
build a dummy model and retry properly.

**Dummy model built on Civil NX v2.2, build 08/12/2026** (blank document,
confirmed empty first): `Material.create` (C24 concrete, `KS01(RC)`),
`Section.create` (600×600 `DBUSER`, `SHAPE: "SB"` — a real, existing,
plain concrete section, i.e. **non-SRC-eligible**, the exact
precondition the 2026-07-31 finding says is needed), two `Node`s, one
`BEAM` `Element` referencing both. All four calls succeeded, session
alive.

**`perform_src_optimal_design` called against it** — `SECT_LIST:
[{SECT_NO: 1, SECT_DB: "USER"}]`, `ANALYSIS_OPT.ANAL_TIME: 0`,
`OUTPUT.MODEL_UPDATE: False` (same conservative shape as the original
2026-07-31 repro). The call timed out client-side at 30s. A follow-up
`GET /db/NODE` immediately after returned `MidasNotFoundError: 404
client does not exist` — the documented "process died after connecting"
signature. User confirmed on screen: the **"[Error] Failed to disconnect
the work session due to an unidentified error..."** dialog, identical to
2026-07-31's crash.

**Recovery**, per the dialog's own instructions (OK → re-launch → New
Project → close → reconnect with the same MAPI key): reconnected
cleanly, `verify_connection()` → `connected`, same `connectionID`.
`Node`/`Element`/`Material`/`Section` all read back empty — the dummy
model was cleared by the New Project step, not a data-loss event; it was
disposable test data built specifically for this repro, nothing of
value was lost.

**Conclusion: `MAPI-2429` is confirmed still live on the current patch
(v2.2, build 08/12/2026), not fixed and not intermittent in the way
`NMAS` briefly was.** This is a stronger data point than the 08-11
non-repro (which used the wrong precondition) and is consistent with
MIDASIT's "not a defect, no fix timeline" stance — the crash isn't
build-dependent, it's inherent to calling this unofficial,
paused-development endpoint with a real section. `docs/coverage.json`'s
`/TEMP/DESIGN/SRC/AIK-SRC2K/OCHECK` entry updated with today's repro and
build. Not re-tested on Gen this session.

## 2026-08-13 (last) — closing the 3 "typed but never live-tested" gaps from the recent manual syncs: SWIND/SSEIS USER TYPE, renamed Story Load/Weight tables, CONCURRENT_JOINT_FORCE

Earlier the same day, checking what the two most recent manual-repo sync
commits (`f4a55e7` 08-07, `76ebda9` 08-10) actually added turned up 3
items that were typed into this SDK but never independently live-tested
against the new shape: `/db/SWIND`/`/db/SSEIS`'s `"USER TYPE"` variant,
the renamed `/post/TABLE` `STORY_LOAD_{X,Y,Z}` + new `STORYWEIGHT`
fields, and the brand-new `CONCURRENT_JOINT_FORCE` table type. User asked
to test all of them, on both products, building dummy models as needed.

**Gen NX (v2.1, build 08/12/2026) — built a 2-story cantilever model**
from scratch on the blank connected session: `Unit`, `Material` (C24),
`Section` (600×600 `DBUSER`), 3 `Node`s / 2 `BEAM` `Element`s (a
0→3.2m→6.4m column), base `Constraint`, **2 real `Story` records**
(`"1F"` at 3.2m, `"RF"` at 6.4m, full field set), `StaticLoadCase`
("DL"), `SelfWeight`, then `/doc/ANAL`. Reaction sanity-checked
(54.23 kN, self-weight of the two-segment column). Every step `ok`.

- **`SWIND`/`SSEIS` `"USER TYPE"`**: POST with `STORY_WIND_PRESSURE`/
  `SEISMIC_FORCE` keyed to `"1F"`/`"RF"` succeeded (201) for both, GET
  read both back correctly — the server fills in GET-only fields
  (`ELEV`/`LOAD_H`/`LOAD_BX`/`LOAD_BY` for wind, `WEIGHT`/`ELEV` for
  seismic) on the way out, confirming those must stay client-side-omit
  on write, as the docstrings already said. `INHERENT_TORSION`'s
  corrected spelling (vs. the manual's own `"NHERENT_TORSION"` typo)
  confirmed as the one the server accepts.
- **Story Load Summary / Story Weight**: `get_story_load_summary_table("X",
  load_case_names=["DL(ST)"])` and `get_story_weight_table()` both
  returned real per-story populated rows (`"1F"`/`"RF"`, correct
  elevations, correct self-weight distribution) — closes the "renamed
  TABLE_TYPE never re-tested" gap.
- **`CONCURRENT_JOINT_FORCE`**: `additional.SET_REACTION_PARAMS =
  {NODE_KEY: 1, COMPONENT: "111111"}`, `load_case_names=["DL(ST)"]` (then
  retried with 2 load cases after adding a second `StaticLoadCase`
  "LL") — both attempts got the identical clean error `"there was an
  error creating utbl. (ex PostMode ...)"`. Not a crash, not a 404 —
  same "PostMode" precondition family as `get_wall_force_table`/`GSBG`.

**Civil NX (v2.2, build 08/12/2026) — re-confirmed `/db/STOR`/`SWIND`/
`SSEIS` still cleanly 404** (GEN_ONLY holds on the current patch too).
Built a fresh single-story-height cantilever column (same recipe, no
Story data — Civil doesn't have that endpoint) and tested
`CONCURRENT_JOINT_FORCE` there too: same request shape got a
**different** clean error, `"No data found for the specified node
key."` A follow-up retry with `NODE_KEY` sent as a string (instead of
int) got a worse, obviously-wrong-shape error (`"second query is
wrong"`), which rules out a type mismatch as the cause of the first
error — confirms the documented `int` type is correct and the node id
itself (which does have real reaction data, confirmed via
`get_reaction_table` in the same session) just isn't what this table
is looking for.

**Conclusion**: `CONCURRENT_JOINT_FORCE`'s own manual note — "typically
paired with moving-load `(MV:max)`/`(MV:min)` load cases" — reads as
literal, not just typical: a plain static-load-case reaction isn't
"extreme" over anything for this table to search, on either product.
Route and request shape are now confirmed correct on both products
(no defect found); building actual moving-load (Vehicle/Lane/MV load
case) test data to exercise the real result path is future work, not
done this session.

**Correction, same session: Gen's "PostMode" error is NOT the same gate
`GSBG` is blocked on.** User asked "Gen은 현재 postmode 맞잖아?" (Gen is
already in Post mode right now, isn't it?) and shared a screenshot
proving it — the "Post-processing Mode" toolbar toggle visibly enabled,
the analysis message log showing the completed solve, on the same
2-story column model this session built. Re-ran the exact
`CONCURRENT_JOINT_FORCE` call with Post mode confirmed already active:
**identical error, unchanged.** This decouples it from the
`GSBG`/`get_wall_force_table` "post mode is required" gate documented
2026-07-31, which *does* clear once a human manually enables Post mode
— here it didn't, so the word "PostMode" in this particular error string
is a red herring for this table specifically. Strengthens rather than
weakens the moving-load-data hypothesis above: with the generic
Post-mode explanation ruled out, "no `(MV:max)`/`(MV:min)` result to
search over" is the more likely remaining explanation for both
products' errors. `docs/coverage.json` and
`post/result_1.py`'s `get_concurrent_joint_force_table` docstring
corrected to not conflate this with the GSBG gate.

All dummy models left open on both sessions (not cleaned up) in case
useful for follow-up testing. `docs/coverage.json` updated for `/db/STOR`,
`/db/SWIND`, `/db/SSEIS`, and both `/post/TABLE` aggregate rows (ch18,
ch19); docstrings in `db/project.py`, `db/static_loads.py`,
`post/pre_process.py`, `post/result_1.py` updated to match.

## 2026-08-13 (last) — `GSBG` retest: the "post mode" gate is a reproducible fix, but the "Final/PostCS" blocker is not leftover state after all

Following the Civil-gap review above (which flagged `/ope/GSBG` as the
one genuinely open item), user opened the same real FCM bridge model
used in the original 2026-07-31 investigation and ran a full analysis,
asking to retry `GSBG`.

**First attempt, FCM bridge (111 nodes, 106 elements), Post mode not yet
manually enabled**: created a `Girder_All` `StructureGroup` covering the
82 non-pier elements (`P1Seg*`/`P2Seg*`/`PierTable*`/`KeySeg*`/`FSM*`
groups' union), then called `generate_bridge_girder_diagram` —
immediately hit the known `"post mode is required"` gate again, exactly
as before. Asked the user to manually click the "Post" tab.

**User raised a fair question before proceeding: is it okay to test
against a real production bridge?** Answered honestly — `GSBG` itself
has never crashed in any prior session (only clean JSON errors), and the
call doesn't write model data (only an output image file), so the risk
profile is lower than e.g. `OCHECK`, but not zero since this specific
combination (Post mode + a real registered Bridge Group) had never been
tried. User switched to a different, smaller real bridge model instead
(61 nodes, 52 elements, 4 construction stages `CS1`-`CS4`, groups
`SG1`/`SG2`/`SG3`) and confirmed Post mode active via the GUI.

**With Post mode confirmed active: `"post mode is required"` did not
recur.** Confirms the manual "Post" tab toggle is a real, reproducible
fix for that specific gate — not a fluke of the 2026-07-31 session.

**But `"Final/PostCS stage is not supported"` came right back**,
identically, across `STAGE_LIST=["CS1"]` (the model's first stage) with
`LC_NAME` = `"Self Weight"`, `"Self Weight(CS)"`, and `"Summation(CS)"`,
using both a fresh `Girder_All` group (all 52 elements) and the model's
own pre-existing `SG1` segment group as `BRDG_GROUP`. **This session
never called `set_result_graphic()` before hitting the error** — directly
contradicting the 2026-07-31 hypothesis that this was leftover state
from an earlier `RESULTGRAPHIC` call with a `"Summation"` load case.
That theory is now ruled out.

Tried one more thing: explicitly selecting stage `CS1` as the active
result via `set_result_graphic(CURRENT_MODE="beamdiagrams",
LOAD_CASE_COMB={"TYPE": "CS", "NAME": "CS1"})` — failed differently,
`"Can not find load case"`, meaning `CS1` alone isn't a valid
`LOAD_CASE_COMB.NAME` for that call. Didn't find the right name before
stopping (user called time on this thread — `GSBG` stays open for a
future session, not close-out material today).

Civil NX session stayed `"connected"` and responsive throughout every
attempt — no crash, no hang, on either bridge model. `docs/coverage.json`
gained `GSBG`'s first `live_verified` entry (previously had none at all,
despite the extensive 2026-07-31 investigation never having been
synced in) recording this as still-blocked, not a success.
`ope.py`'s `generate_bridge_girder_diagram` docstring updated with
today's findings.

## 2026-08-13 (last) — full `live_crud_check.py` reconfirmation on Civil NX build 08/12/2026: 43/43, no regressions

User asked whether Civil NX had ever had the full CRUD suite run against
it. Answer at the time: yes, all 43 cases confirmed since 2026-07-29,
last fully re-run together 2026-08-07 against build 08/06/2026 — but not
against either of the two patches since (08/11, 08/12). User gave
explicit go-ahead to run it now, understanding `/doc/NEW` would discard
the small 4-stage bridge model (`SG1`/`SG2`/`SG3`) open from the `GSBG`
session above (not saved, not needed further).

`scripts/live_crud_check.py --product civil` (all 6 tiers, no
`--include-crashers` — nothing is quarantined anymore): **43/43
resources completed a full create→read→update→read→delete→read round
trip, zero failures**, against Civil NX 2026 v2.2, build 08/12/2026.
Covers core (10), props (7), boundary (9), static (9, including
`/db/NMAS`), stage (4), and moving (4, AASHTO LRFD fixtures). No
regressions from the 2026-08-07 baseline. Reconfirmation, not a new
finding — same conclusion as 08-07, now current as of today's patch.

## 2026-08-13 (last) — Gen NX full verification pass, mirroring today's Civil NX session

User asked to do the same broad pass on Gen NX that Civil NX got earlier
today, "in a safe order." Plan: read-only sweep first, then the two
untested read-shaped POSTs, then the riskier `/doc/*` file-management
family (paths resolve on the NX host, `/doc/SAVEAS` has a known silent-
failure landmine), and the destructive full CRUD suite last.

**Coverage-gap check (read-only, coverage.json only):** of 363 gen-
applicable endpoints, 0 had zero live evidence, but 12 had never been
tested *on Gen specifically* (Civil-only so far): the whole `/doc/*`
file-management family (`OPEN`/`CLOSE`/`SAVE`/`SAVEAS`/`STAGAS`/
`IMPORT`/`IMPORTMXT`/`EXPORT`/`EXPORTMXT`), `/post/PM`, `/post/
STEELCODECHECK`, and the already-known-open `/ope/GSBG`.

**Full read-only sweep, Gen NX v2.1 build 08/12/2026:** 266/266 GET-
capable resources answered, zero 404s — no regressions from prior
sweeps.

**`/post/PM` and `/post/STEELCODECHECK`**, against the small analyzed
2-story concrete column (no RC design code configured): both answered
the same clean precondition errors/empty responses Civil got on 2026-
07-31 (`"Please Check RC Design Code"` for PM, `{"message": ""}` for
STEELCODECHECK). Route/shape confirmed on Gen for the first time.

**`/doc/*` file family**, path built from `verify_connection()['user']`
per `save_as()`'s own documented pattern (`C:/Users/sjj0507/Documents/
gsdk_test.mgbx`), all against the same disposable test model:

- `SAVEAS` → `OPEN` (verify) → `SAVE` → `CLOSE` → `OPEN` (reopen): all
  clean, node count (3) intact through every step. First Gen confirmation
  for all four endpoints.
- `EXPORT` (JSON) succeeded; the **`IMPORT` round trip on that same file
  failed** — `"MAINREBAR_B_FY must be > 0."` — a clean, informative
  error (not a crash), but a genuine new finding: this model's exported
  JSON apparently carries an invalid rebar default that import-side
  validation rejects. Not root-caused (SDK export gap vs. a real product
  default-value bug is still an open question). Node count unaffected by
  the failed import.
- `EXPORTMXT` succeeded; the **`IMPORTMXT` round trip succeeded too, but
  with a warning that turned out to be inaccurate**: `"[Warning] Static
  Seismic/Wind Loads Data for User Type are deleted due to changes in
  Story Data."` A follow-up `GET` on `/db/SWIND`, `/db/SSEIS`, and
  `/db/STOR` showed all three completely unchanged — nothing was
  actually deleted. **Don't take this warning's wording as ground truth
  for final state; verify with GET**, same lesson as the "a 200 doesn't
  mean success" family of findings, just inverted (a warning that
  doesn't mean failure either).
- `STAGAS` not tested — needs a construction-stage model, which this
  session's throwaway column doesn't have. Still open on Gen.

Session stayed `"connected"` and responsive throughout every step, no
crash, no hang. `docs/coverage.json` updated for `/post/PM`,
`/post/STEELCODECHECK`, and 8 of the 9 `/doc/*` endpoints (all but
`STAGAS`) with today's Gen findings; `ROADMAP.md` regenerated.

**Last step: full `scripts/live_crud_check.py --product gen` run**,
against the same patch build (v2.1, 08/12/2026), no `--include-crashers`
needed (nothing quarantined). **38/38 resources completed a full
create→read→update→read→delete→read round trip, zero failures** — core
(10), props (7), boundary (9), static (9, including `/db/NMAS`), stage
(3 of 4; `/db/CMCS` is declared Civil-only in the checker by design).
The `moving` tier (4 cases) is also Civil-only in the checker, per the
2026-07-29 finding that `/db/MVCD`'s Gen availability is per-CODE, not
unconditional — not re-litigated today. No regressions from any prior
Gen run. This closes out today's Gen NX pass at the same depth as the
Civil NX one earlier: read sweep, the 2 previously-Gen-untested
read-shaped POSTs, the `/doc/*` file family, and the full write suite,
all clean or with informative (non-crash) findings on this patch build.

## 2026-08-16 — new patch on both products: connection check only

User applied a new patch to both products and asked to confirm both
connect, with versions recorded. `verify_connection()` against fresh
`.env` MAPI keys (last-occurrence-wins for the duplicated
`MIDAS_MAPI_KEY_GEN`/`MIDAS_MAPI_KEY_CIVIL` lines) succeeded for both:

```text
GEN:   {'user': 'sjj0507@midasit.com', 'program': 'gen',   'connectionID': 'N-pAmlMjSg', 'keyVerified': True, 'status': 'connected'}
CIVIL: {'user': 'sjj0507@midasit.com', 'program': 'civil', 'connectionID': 'WjbfiHlPSw', 'keyVerified': True, 'status': 'connected'}
```

About-dialog screenshots confirm the new build:

- **MIDAS GEN NX 2026 (v2.1), build 08/14/2026** (previous: 08/12/2026)
- **MIDAS CIVIL NX 2026 (v2.2), build 08/14/2026** (previous: 08/12/2026)

Same version numbers as the prior patch, two-days-newer build only —
consistent with a routine patch rather than a version bump.

## 2026-08-16 (last) — full `live_crud_check.py` reconfirmation on both products, build 08/14/2026: 43/43 Civil, 38/38 Gen, no regressions

User asked to verify the new 08/14/2026 patch after confirming both
products connect (see the connection-check entry above). Chose the full
CRUD-suite scope over a read-only sweep or a targeted re-test of past
crash items, and explicitly authorized the `/doc/NEW` data loss ("go
go") after being warned.

Ran `scripts/live_crud_check.py` with no `--tier` filter (all tiers) on
each product in turn, Civil first:

- **Civil NX** (v2.2, build 08/14/2026): 43/43 — identical result set to
  the 08/12/2026 run (`core`/`props`/`boundary`/`static`/`stage`/`moving`
  all pass, including `/db/NMAS` clean via the auto-filled
  `rmX`/`rmY`/`rmZ` workaround).
- **Gen NX** (v2.1, build 08/14/2026): 38/38 — same as 08/12/2026 (no
  `moving` tier; those fixtures are Civil-confirmed only, per the tier's
  own docstring in the script).

No crashes, no hangs, no field/value regressions surfaced on either
product. This is a clean re-confirmation, not new coverage — same cases
as the 08-13 runs, one patch build later.

## 2026-08-16 (last) — expanding write coverage past the curated CRUD suite: batch 1 of db.project/db.boundary, 14/18 confirmed

User asked what to do next on the new 08/14/2026 patch. Given the existing
`live_crud_check.py` suite only covers a curated 43/38-endpoint subset while
174 `/db/*` endpoints across both products were still only read-verified,
picked expanding write coverage over re-chasing GSBG's open blocker or the
Gen `MAINREBAR_B_FY` import bug. User chose to start with `db.project` +
`db.boundary`'s 24 read-only endpoints (of 174 total), scoped down to a
tractable 18 for this session — deferred the 5 seismic-device endpoints
(SDVI/SDVE/SDST/SDHY/SDIS, deeply nested `COMMON` payloads) and `DRLS`
(empty-object payload, no field to round-trip) to a future batch.

Added a new `extras1` tier to `scripts/live_crud_check.py` (18 cases, 3 new
seed steps) covering: `PJCF`, `STYP`, `STYP-M1`, `TDGR`, `NPLN`, `CO_M`,
`CO_S`, `CO_T`, `CO_F`, `SPAN`, `NLLP`, `NLNK`, `NLNK-M1`, `CGLP`, `PRLS`,
`MLFC`, `PZEF`, `CLDR`. First live run (Civil NX v2.2, build 08/14/2026):
10/18, all failures fixture problems as expected on a first pass. Triaged
and fixed 4 of them:

- **`/db/PJCF`**: a fresh document already carries a Project Info record at
  id 1 (non-empty placeholder, confirmed via `ProjectInfo.items()` before
  any case ran), and POST answers "Key Already Exist" for *any* id, not
  just 1, until that record is deleted first. Same singleton family as
  UNIT/STYP, just with DELETE as the unlock instead of being GET/PUT-only.
  Added a `pjcf_unlock` seed step.
- **`/db/STYP`**: `MASS: 0` answers "Wrong Field" — valid values are only
  `1` (Lumped) or `2` (Consistent) per the manual's own enum, which the
  first payload didn't respect. Fixed to `MASS: 1`.
- **`/db/SPAN`**: `SPAN_BASE_ITEMS.length` must be `SPAN_LIST.length + 1`
  (one support point per span boundary) — a 2-items/3-list mismatch
  answered `"[Error] ... (Item:Number of Spans)"`. The manual's
  Specifications table doesn't state this relationship; only cross-checking
  against its own worked JSON example (4 items / 3 values) surfaced it.
  Fixed to 3 items / 2 values.
- **`/db/CO_F`**: keyed by a Floor Load Type (`/db/FBLD`) id, which the
  base seed model doesn't create — needed its own `fbld_seed` step. Also
  found live that CO_F's own `"NAME"` field is **read-only**, mirroring the
  linked FBLD record's name: a PUT with `NAME="FL_CRUD"` echoed back
  `"FL_SEED"` unchanged. Switched the case to probe a colour field
  (`WF_R`) instead, matching CO_M/CO_S/CO_T.

One failure did **not** resolve to a fixture problem: **`/db/NLLP`**
(General Link Properties) answers a generic `"Unknown Error"` on POST even
with the manual's own request-example payload reproduced verbatim
(`PROPERTY_NAME`/`DESC`/`APPLICATION_TYPE="ELEMENT"`/
`APPLICATION_TYPE_D="SPG"`/`TOTAL_WEIGHT`/`OPT_USE_MASS`), tried against
both a partially-seeded and a completely fresh `/doc/NEW` document, on
**both** Civil NX and Gen NX. Left as `level: read` in coverage.json —
genuinely unresolved, not swept under a workaround. This blocks `NLNK`,
`NLNK-M1`, and `CGLP` (all reference an NLLP record by name), so those
three stayed untested this round too; their coverage.json entries got a
2026-08-16 note saying so rather than being silently left stale.

Final result after fixes, re-run fresh on both products:

- **Civil NX** (v2.2, build 08/14/2026): 14/18 (`STYP-M1`/`SPAN` are
  Civil-only and both pass; `NLLP`/`NLNK`/`NLNK-M1`/`CGLP` are the 4
  failures/blocks).
- **Gen NX** (v2.1, build 08/14/2026): 12/15 (`STYP-M1`/`SPAN` correctly
  skipped as Civil-only; `NLLP`/`NLNK`/`CGLP` are the 3 failures/blocks —
  same `NLLP` root cause reproduces here too, ruling out a Civil-specific
  explanation).

All 14 passing cases flipped to `confirmed=True` in the script.
`docs/coverage.json` updated for all 14 to `level: "write"`; `/db/NLLP`,
`/db/NLNK`, `/db/NLNK-M1`, `/db/CGLP` stay `level: "read"` with a dated
note. `ROADMAP.md` regenerated. Batch 2 (the remaining ~150 read-only
`/db/*` endpoints, including the deferred seismic-device family and the
`NLLP` root cause) is open for a future session.

## 2026-08-16 (last) — write coverage batch 2: db.misc_loads in full + 3 of db.temperature_prestress, 11/12 confirmed

Continuing the write-coverage push from earlier today (batch 1: db.project
+ db.boundary, 14/18). User asked to keep going; picked db.misc_loads (all
9 of its endpoints were still read-only) plus 3 tractable
`db.temperature_prestress` endpoints (`GTMP`/`STMP`/`BTMP` — the other 7 are
tendon/prestress geometry, deferred alongside extras1's seismic-device
family).

Found a genuine shortcut: `docs/manual/11_DB_Settlement_Misc_Loads.md` ends
with an "End-to-End 워크플로우 예제" that chains all 8 core misc_loads
endpoints (`SMPT → SMLC → PLCB → LDSQ → WVLD → IELC → EFCT → INMF`) through
one consistent fixture. Adapted its payloads almost verbatim into a new
`extras2` tier (12 cases, 1 seed step) instead of re-deriving fixtures from
the Specifications tables like extras1 needed to.

First live run (Civil NX v2.2, build 08/14/2026): 10/12. Triaged the 2
failures:

- **`/db/SMPT`**: same renumbering behaviour as `/db/STLD`/`/db/FBLD` — a
  seed record requested at id 90 landed at id 1 instead, colliding with the
  case's own id-1 target ("Key Already Exist"). Fixed by moving the case to
  id 2.
- **`/db/WVLD`**: did **not** resolve to a fixture problem. The manual's own
  full canonical example, reproduced verbatim, answered `"Wrong Field"` —
  and so did a bare `{"NAME": "..."}` payload, ruling out any specific
  field. Left at `level: read`, same class of unexplained finding as
  extras1's `/db/NLLP` (possibly a licensed offshore/marine module gate,
  unconfirmed).

Re-run clean on both products after the fix:

- **Civil NX** (v2.2, build 08/14/2026): 11/12 (`PLCB`/`WVLD` are
  Civil-only; `WVLD` is the one remaining failure).
- **Gen NX** (v2.1, build 08/14/2026): 10/10 — clean pass, exit code 0.
  `PLCB`/`WVLD` correctly skipped as Civil-only.

Incidental finding: **`/db/BTMP`** (Beam Section Temperature) passed live
on **both** products, despite the manual's own prose flagging it
`"⚠️ MIDAS Civil NX 전용 기능"` (Civil-NX-only) — its Specifications table
carries no such restriction and coverage.json already listed both products.
Same documented-vs-actual-routing mismatch pattern as the ch08/ch17
moving-load family from 2026-07-29.

11/12 cases flipped to `confirmed=True`; `docs/coverage.json` updated for
all 11 to `level: "write"`, `/db/WVLD` stays `level: "read"` with a dated
note. `ROADMAP.md` regenerated. Batch 3 (properties.*, analysis_control,
dynamic_loads, design, moving_loads, construction_stage, load_combinations,
pushover, bridge, the tendon/prestress half of temperature_prestress, the
deferred seismic-device family, and root-causing `NLLP`/`WVLD`) is open for
a future session.

## 2026-08-16 (last) — write coverage batch 3: tractable subset of db.properties.*, 4-5/9 confirmed

Third write-coverage batch of the day. Picked 9 of `db.properties.*`'s
15 remaining read-only endpoints — deferred the 5 fiber/inelastic-hinge
endpoints (`IMFM`, `EPMT`, `FIMP`, `IEHC`, `IEHG`, needing real
stress-strain curve fixtures) and `FIBR` (depends on `FIMP`), same
complexity class as extras1's deferred seismic-device family.

First live run (Civil NX v2.2, build 08/14/2026): 5/9. Unlike batches 1-2,
most of the 4 failures did **not** resolve to fixture problems even after
reproducing each endpoint's own manual canonical example verbatim:

- **`/db/GRDP`** (Group Damping): tried both a minimal Specifications-table
  payload and the manual's full worked example (with `GROUP_NAME` as the
  material's numeric id `"1"`, not its name — the actual fixture bug found
  — plus the extra `STIFF_COEF_DEFAULT`/`MASS_COEF_DEFAULT`/`OPT_*_PROP_DEFAULT`
  fields the manual's example includes but its own Specifications table
  omits). Both answered `"Wrong Field"` identically.
- **`/db/TDMF`** (Time Dependent Material – User Defined): reproduced the
  manual's own 4-point `vDAY` Request Body example verbatim (not just the
  2-point one first tried) — still `"Wrong Field"`.
- **`/db/RPSC`** (Section Manager – Reinforcements): manual's own example
  reproduced — still fails.
- **`/db/STRPSSM`** (Section Manager – Stress Points, Civil-only): manual's
  own example reproduced — still fails. Noteworthy: RPSC's own worked
  example keys at id `401` and STRPSSM's at id `9003`, not a plain running
  number like every other endpoint tested today — both describe "PSC/RC
  단면" specifically, so the base seed's plain `DBUSER` rectangular column
  section may not carry a Section Manager reinforcement/stress-point slot
  at all. Left genuinely unresolved rather than guessed at further.

All 4 are the same class of finding as `/db/NLLP` (extras1) and `/db/WVLD`
(extras2) — a manual-exact payload still answering a generic error live.
Three unrelated-looking endpoints failing identically on the first try of
a brand-new tier is unusual enough (vs. extras1/2's near-clean first
passes) that it's worth flagging as a pattern to watch, not just three
independent coincidences — worth revisiting with a fresh angle rather than
more payload guessing.

Re-run clean on both products (no changes needed for the passing 5):

- **Civil NX** (v2.2, build 08/14/2026): 5/9 (`EDMP`, `PSSF`, `VSEC`,
  `VBEM`, `EWSF` pass; `GRDP`/`TDMF`/`RPSC`/`STRPSSM` are the 4 failures).
- **Gen NX** (v2.1, build 08/14/2026): 4/7 (`STRPSSM`/`EWSF` correctly
  skipped as Civil-only; `GRDP`/`TDMF`/`RPSC` reproduce the identical
  failure, ruling out a Civil-specific explanation for those three).

5 passing cases flipped to `confirmed=True`; `docs/coverage.json` updated
for `EDMP`/`PSSF`/`VSEC`/`VBEM`/`EWSF` to `level: "write"`.
`GRDP`/`TDMF`/`RPSC`/`STRPSSM` stay `level: "read"` with dated notes.
`ROADMAP.md` regenerated. Batch 4 (the deferred fiber/inelastic-hinge
family, analysis_control, dynamic_loads, design, moving_loads,
construction_stage, load_combinations, pushover, bridge, the
tendon/prestress half of temperature_prestress, and root-causing
`NLLP`/`WVLD`/`GRDP`/`TDMF`/`RPSC`/`STRPSSM`) is open for a future session.

## 2026-08-16 (last) — write coverage batch 4: db.load_combinations in full, 7-8/8 confirmed

Fourth write-coverage batch of the day. `db.load_combinations` was a clean
target: all 8 of its endpoints were still read-only, and 6 of them
(`LCOM-GEN/CONC/STEEL/SRC/STLCOMP/SEISMIC`) share one payload shape per
the module's own `LoadCombinationPayload` docstring, so the tier is mostly
one parametrized case repeated six times.

First live run (Civil NX v2.2, build 08/14/2026): 7/8 — only
`LCOM-SEISMIC` failed, with `"The Load Combination Type is not
supported"` for the same `ANAL="ST"` payload its 5 siblings all accept.

The interesting part: **re-running on Gen NX passed 8/8, including
`LCOM-SEISMIC`** with the identical payload. This is the first
same-day, same-build, same-payload case in today's batches where the two
products actually disagree rather than one being a documented
Gen/Civil-only route — Civil genuinely rejects `ANAL="ST"` for seismic
combinations while Gen accepts it. Tried the manual's own `ANAL="RS"`/
`"CS"` alternative on Civil against the base seed's plain static `"DL"`
case; both answered `"Unknown Error"` instead, because `DL` isn't
actually an RS/CS-typed case — reproducing the manual's intended usage
properly needs a real `/db/SPLC` Response Spectrum Load Case, which is
one of the `db.dynamic_loads` endpoints deferred to a future batch. Left
`LCOM-SEISMIC` at `level: read` rather than call it "confirmed" off an
asymmetric pass.

7 cases (`LCOM-GEN`, `LCOM-CONC`, `LCOM-STEEL`, `LCOM-SRC`,
`LCOM-STLCOMP`, `CUTL`, `CLWP`) flipped to `confirmed=True`;
`docs/coverage.json` updated for all 7 to `level: "write"`.
`LCOM-SEISMIC` stays `level: "read"` with a dated note explaining the
product asymmetry. `ROADMAP.md` regenerated.

Running total for today's write-coverage push (batches 1-4): 42 endpoints
flipped to `level: write`, 7 left as genuinely unresolved live findings
(`NLLP`, `WVLD`, `GRDP`, `TDMF`, `RPSC`, `STRPSSM`, `LCOM-SEISMIC`). Batch
5 (the deferred fiber/inelastic-hinge family, `db.analysis_control`,
`db.dynamic_loads` — which would also unblock `LCOM-SEISMIC` —
`db.design`, `db.moving_loads`, `db.construction_stage`'s hydration
family, `db.pushover`, `db.bridge`, and the tendon/prestress half of
`db.temperature_prestress`) is open for a future session.

## 2026-08-16 (last) — write coverage batch 5: db.dynamic_loads, new Gen NX crash found and filed as MAPI-2468

Fifth write-coverage batch of the day, and the one this session picked
specifically because it also unblocks batch 4's `LCOM-SEISMIC` finding
(needs a real `/db/SPLC` Response Spectrum Load Case). Covered 9 of
`db.dynamic_loads`'s 12 endpoints — deferred the 3 Hyper-S variants
(`THGC-M1`/`THOO-M1`/`THIS-M1`, deeply-nested required control
sub-objects).

First live run (Civil NX v2.2, build 08/14/2026): 4/9. Triaged and fixed
3 fixture issues:

- **`/db/SPFC`/`/db/THIS`/`/db/THFC`**: all three answered "Key Already
  Exist" — their seed records (requested at id 90) renumber to id 1, same
  STLD/FBLD/SMPT family, so the cases' own test records collided at the
  same id. Fixed by moving the cases to the next free id (2, or 3 where
  `/db/THFC` has two seed records ahead of it).
- **`/db/THNL`**: "Unknown Error" — its `FUNC_NAME` must reference a
  Force/Moment-type function (`iTYPE=3/4`), not the Accel-type one
  (`iTYPE=2`) already seeded for other cases; added a second,
  Force-typed seed function. This matches the manual's own explicit
  warning ("FUNC_NAME에는 Force 또는 Moment 타입의 시간이력 함수만 사용
  가능"), just missed on the first pass.

Re-run clean on Civil NX after the fixes: 8/9 (only `THMS` still fails —
see below).

**Then, running the same tier on Gen NX, the product crashed mid-run.**
`SPLC` failed normally ("Unknown Error", session still alive), `THGC`/
`THIS`/`THFC`/`THGA` all passed clean, then `THNL`'s own case showed
`create=ok read_back=ok update=FAIL` — its `PUT` failed with `404 Client
Disconnected`, and the very next case (`THSL`) got `404 client does not
exist`. The checker's own `_session_lost` guard caught it and aborted
correctly. User asked directly ("Gen NX 뭐가 죽은 것 같은데?") mid-run;
confirmed via a direct `verify_connection()` call that `status` itself
had flipped to `"disconnected"` — not just a blocked-dialog false
"connected" (the documented `verify_connection()`-can't-see-a-blocked-
session landmine). This was a genuine session death, not a masked hang.

User restarted Gen NX, then explicitly asked to reproduce the same
scenario again ("다시 한번 같은 상황 연출해봐"). **Re-ran the identical
tier on the freshly-restarted Gen NX session and the crash reproduced at
the exact same point**: `SPLC` "Unknown Error" (alive), four clean
passes, `THNL` `create=ok read_back=ok update=FAIL` with the same `404
Client Disconnected`, then the aborted follow-on call. Two independent
reproductions, same trigger, same build (v2.1, 08/14/2026) — this
project's usual "confirmed" bar.

Isolated the trigger precisely: `POST /db/THNL` succeeds and the
following `GET` echoes it back correctly, but the **next `PUT
/db/THNL`** (`{"Assign": {"1": {"ITEMS": [{...}]}}}`, only
`SCALE_FACTOR` changed from the create payload) is what kills the
session — not the `POST` itself. Civil NX's identical round trip is
completely clean.

User asked to write this up and file it in MIDASIT's internal Jira
("내용 정리하고 Jira에 올리자 이건"). Searched `project = MAPI AND (text
~ "THNL" OR text ~ "Dynamic Nodal Load")` first — no existing ticket for
this symptom (the only THNL hit, MAPI-177, is an unrelated closed 2023
delete-behavior ticket). Filed **MAPI-2468**, parented under **MAPI-2427**
("API 동작 중 프로그램 종료 이슈" — the same crash-symptom epic that
already holds MAPI-2378/NMAS, MAPI-2425/EDMP, MAPI-2426/USLC, and
MAPI-2431/CD-TABLE), priority 높음 (`id: "3"`, matching all four
precedents), with the exact reproduction payload, both reproduction
timestamps, and an open "root cause not yet identified" framing — not
linked to the other four as a shared cause, since there's no evidence of
one, same call this project made for MAPI-2431.

`live_crud_check.py`'s `/db/THNL` case is now restricted to
`products=("civil",)` rather than fully crash-quarantined, since only
Gen NX actually crashes and Civil's round trip is clean — re-enabling Gen
needs a deliberate decision once MAPI-2468 is resolved, not an assumption
that a vendor fix landed.

One more genuinely unresolved finding, same class as extras1/2/3's
`NLLP`/`WVLD`/`GRDP`/`TDMF`/`RPSC`/`STRPSSM`: **`/db/THMS`** answers
`"Wrong Field"` on both products even with the manual's own field names
and a required-fields-only payload. `db/dynamic_loads.py`'s own docstring
already flags it as "Keyed by node/group id" (unlike `THNL`'s plain node
id) — may need a real multi-support boundary/support group defined
first, not just any integer key.

Also product-asymmetric (mirroring `LCOM-SEISMIC`'s reversed case from
batch 4): **`/db/SPLC`** passes clean on Civil NX but Gen NX answers
`"Unknown Error"` on the identical payload, reproduced twice — left at
`level: read` pending investigation (possibly needs a Gen-specific modal/
eigenvalue analysis-control setup).

Final tally: 6 endpoints (`SPFC`, `THGC`, `THIS`, `THFC`, `THGA`, `THSL`)
write-confirmed on both products; `THNL` write-confirmed on Civil only
(Gen crashes, MAPI-2468 filed); `SPLC` and `THMS` stay `level: read` as
genuine unresolved findings. `docs/coverage.json` and `ROADMAP.md`
updated accordingly.

Running total for today's write-coverage push (batches 1-5): 49 endpoints
flipped to `level: write`, 9 left as genuinely unresolved live findings
(`NLLP`, `WVLD`, `GRDP`, `TDMF`, `RPSC`, `STRPSSM`, `LCOM-SEISMIC`,
`SPLC`, `THMS`), plus one new confirmed live crash (`THNL` PUT on Gen NX,
MAPI-2468). Batch 6 (the deferred fiber/inelastic-hinge family, seismic
devices, `db.analysis_control`, `db.design`, `db.moving_loads`'s
remainder, `db.construction_stage`'s hydration family, `db.pushover`,
`db.bridge`, the tendon/prestress half of `db.temperature_prestress`, the
3 deferred Hyper-S dynamic_loads variants, and root-causing the 9 unresolved
findings above) is open for a future session.

## 2026-08-16 (last) — write coverage batch 6: seismic-device family from db.boundary, 0/5 -- genuine finding, not a fixture bug

Sixth write-coverage batch of the day. Picked up the seismic-device family
(`SDVI`/`SDVE`/`SDST`/`SDHY`/`SDIS`) that batch 1 deliberately deferred out
of `extras1` for its deeply nested `COMMON` payloads. Transcribed each
payload from the manual's own POST worked examples (`05_DB_Boundary.md`,
items 16-20), not the leaner Specifications tables, per this project's
standing preference for worked examples over tables when they disagree.

First live run (Civil NX v2.2, build 08/14/2026): 0/3 (`SDHY`/`SDIS` are
Gen-only, correctly skipped). All three POSTs answered `"Wrong Field"`.
Bisected by hand rather than assuming a fixture bug outright, given this
project's own caution about varying values before field names:

- Reproduced the manual's own bare literal `SDVI` example verbatim
  (`DAMPER_TYPE=0`, `DASHPOT_TYPE=0` — Linear Elastic, not the customized
  `=2` Exponential values the case used) — still `"Wrong Field"`.
- Fetched `SDVI.info()`'s live JSON schema: field names match the manual
  exactly (`COMMON.{NAME,DESC,INPUT_METHOD,COMPANY,PRODUCT_NAME,
  TYPE_NUMBER}`, `DEVICE_TYPE`, `DAMPER_TYPE`, `DASHPOT_TYPE`, `INPUT_TYPE`,
  `ITEM[6]` — plus an undocumented `INPUT_TYPE_EXFN` and per-item `EXFN_*`
  fields for the Exponential dashpot type), ruling out a field-name typo.
- Tried a `COMMON`-only payload, a payload with `INPUT_TYPE_EXFN` added, no
  `ITEM` array, no `DEVICE_TYPE`, non-empty `COMPANY`/`PRODUCT_NAME`/
  `TYPE_NUMBER` everywhere, `INPUT_METHOD=1` (Reference DB), and a
  single-entry `ITEM` array instead of 6 — every variant still answered
  `"Wrong Field"`.
- Extended the same manual-literal-payload test to `SDVE`/`SDST` (Civil)
  and `SDHY`/`SDIS` (Gen) — all 4 failed identically, and a full `--tier
  extras6` run on Gen NX confirmed all 5 fail there too (`SDHY`/`SDIS`
  included this time, since Gen is where they're actually implemented).

Not resolved as a fixture problem on either product. Notably, `/db/NLLP`
(General Link Properties, extras1's confirmed-broken endpoint) is the
table these five devices are meant to be referenced *from*
(`APPLICATION_TYPE_D="VI"/"VE"/"ST"/"HY"/"IS"`) — two independently
confirmed-broken endpoint families in the same manual chapter raises
suspicion of something chapter-wide (a licensed isolator/damper-design
module gate not enabled on this session?) rather than five unrelated
defects, but that's unconfirmed speculation, not a finding to act on.

Left all 5 at `level: read` in `docs/coverage.json`, each with a dated
note; none of the `extras6` cases are `confirmed=True` since none have
ever passed live. `/db/DRLS` (#24, the other endpoint extras1 deferred out
of this chapter) stays deferred for an unrelated, purely mechanical reason:
its payload is `{<node id>: {}}`, an empty object with no field to
distinguish a create from an update, so it doesn't fit this checker's
create/update/probe shape at all — a different problem from the
`"Wrong Field"` finding above. `ROADMAP.md` regenerated (399/399
implemented, write-count unchanged by this batch since nothing passed).

Running total for today's write-coverage push (batches 1-6): still 49
endpoints flipped to `level: write` (batch 6 added 0), 14 left as
genuinely unresolved live findings (`NLLP`, `WVLD`, `GRDP`, `TDMF`, `RPSC`,
`STRPSSM`, `LCOM-SEISMIC`, `SPLC`, `THMS`, `SDVI`, `SDVE`, `SDST`, `SDHY`,
`SDIS`), plus the one confirmed live crash from batch 5 (`THNL` PUT on Gen
NX, MAPI-2468). Batch 7 (the deferred fiber/inelastic-hinge family,
`db.analysis_control`, `db.design`, `db.moving_loads`'s remainder,
`db.construction_stage`'s hydration family, `db.pushover`, `db.bridge`,
the tendon/prestress half of `db.temperature_prestress`, the 3 deferred
Hyper-S dynamic_loads variants, `/db/DRLS`'s empty-payload shape problem,
and root-causing the 14 unresolved findings above) is open for a future
session.

## 2026-08-17 — write coverage batch 7: standalone/frame-attachable remainder of db.static_loads, 4/5 (Civil) + 5/8 (Gen)

Seventh write-coverage batch, continuing without a fresh scope check —
picked the remaining `db.static_loads` endpoints that don't need real
plate/planar geometry beyond what the base seed model already has: `PNLD`,
`PNLA`, `FBLA`, `FMLD`, `POSP`, `EPST`, `POSL`, `EPSE`. (`PNLA` was
initially assumed to need real plate geometry and deferrable, but
`_seed_model`'s own base model already has one — element 4, nodes 5-8 — so
it came along for free.)

First live run (Civil NX v2.2, build 08/14/2026): 1/5, only `FMLD` passed
clean. Triaged the rest:

- **`/db/PNLD`**: create succeeded but read-back failed — same
  STLD/FBLD-family renumbering as extras1/extras5's seeds (the seed
  landed at id 1, not the requested 90; the case's own id 91 request
  actually landed at id 2). Fixed by pointing the case at id 2 and citing
  the seed's real id.
- **`/db/PNLA`**: `"Wrong Field"` even after fixing `PNLD_KEY` to the
  seed's real id. Bisected by removing one field at a time — the manual
  marks `LOAD_GROUP` Required, but sending *any* non-empty value for it
  answers `"Wrong Field"`; omitting the key (or sending `""`) succeeds.
  Fixed by dropping it; `db/static_loads.py`'s `PlaneLoadPayload` docstring
  now documents this.
- **`/db/POSL`**: `"Wrong Field"` on every payload, including the
  manual's own literal example. Fetched `.info()`'s live schema: Civil
  NX's actual field set is `NAME`/`SZ`/`SRF`/`SC`/`FA`/`FV`/`DAMP_RATIO`
  only — a completely different, smaller shape than the manual's
  `CODE`/`METHOD`/`EPA`/`SDS`/`SD1`/`USER_GROUP`/`IF`/`RMF`. Sending
  `CODE` at all — even as `""` — was confirmed as the specific trigger via
  per-field bisection. Checked Gen NX's own `.info()` schema for
  comparison and found it *does* match the manual (plus two undocumented
  fields, `EPGAeff`/`Kae`) — this endpoint's real contract is
  product-asymmetric, not just wrong. Split the checker's one `POSL` case
  into two, one payload per product; `SeismicLoadParamPayload` in
  `db/static_loads.py` now documents both shapes.

Re-run clean on Civil after the `PNLD`/`PNLA`/`POSL` fixes: **4/5**
(`PNLD`, `PNLA`, `FMLD`, `POSL` pass; `FBLA` is the one remaining
failure, `"Unknown Error"` on POST, not resolved as a fixture problem
despite trying the base model's plate-corner nodes and an unrelated
frame-chain node set, both winding orders, `FLOOR_DIST_TYPE` 1 and 2, and
the manual's full optional-field set).

**Gen NX** (v2.1, build 08/14/2026), same fixed cases plus the Gen-only
trio (`POSP`/`EPST`/`EPSE`): **5/8**. `POSP`'s first attempt answered
`"Unknown Error"` with a single soil layer — fixed by using the manual's
own 3-layer example, whose `HEIGHT` values sum to exactly the depth from
`GROUND_LEVEL` to `BEDROCK_LEVEL` (5+5+15=25m); a single layer that
doesn't reach that depth appears to be the trigger, the same undocumented
cross-field relationship class as `/db/SPAN`'s item-count-vs-list-length
rule from batch 1. `POSP`, `PNLD`, `PNLA`, `FMLD`, `POSL` all passed
clean after fixture fixes. `EPST` and `EPSE` both failed `"Wrong Field"`
even with field names confirmed matching their own live `/info` schema
and several bisected variants (`SEL_TYPE`, `EP_TYPE`, blank `SOIL_PROP`,
omitted `IN_PT`, `PRES_PROFILE_ITEMS`) — not resolved as fixture
problems, left `level: read` alongside `FBLA`. `EPST`/`EPSE` are untested
on Civil NX since `POSP` (which their `SOIL_PROP` references) is
Gen-only, so there's no Civil fixture to build them against — genuinely
untested there, not confirmed broken.

6 endpoints flipped to `level: write` (`PNLD`, `PNLA`, `FMLD`, `POSP`,
`POSL` — `POSL` write-confirmed on both products despite the schema
split); `FBLA`, `EPST`, `EPSE` stay `level: read` as new unresolved
findings. `docs/coverage.json` and `ROADMAP.md` updated; `pytest` (701)
and `ruff` both clean after the source-level `PlaneLoadPayload`/
`SeismicLoadParamPayload` docstring fixes.

Running total for the write-coverage push (batches 1-7): 55 endpoints
flipped to `level: write`, 17 left as genuinely unresolved live findings
(`NLLP`, `WVLD`, `GRDP`, `TDMF`, `RPSC`, `STRPSSM`, `LCOM-SEISMIC`,
`SPLC`, `THMS`, `SDVI`, `SDVE`, `SDST`, `SDHY`, `SDIS`, `FBLA`, `EPST`,
`EPSE`), plus the one confirmed live crash from batch 5 (`THNL` PUT on
Gen NX, MAPI-2468). Batch 8 (the deferred fiber/inelastic-hinge family,
`db.node_element`'s Domain feature, `db.analysis_control`, `db.design`,
`db.moving_loads`'s remainder, `db.construction_stage`'s hydration
family, `db.pushover`, `db.bridge`, the tendon/prestress half of
`db.temperature_prestress`, the 3 deferred Hyper-S dynamic_loads
variants, `/db/DRLS`'s empty-payload shape problem, and root-causing the
17 unresolved findings above) is open for a future session.

## 2026-08-17 — write coverage batch 8: tractable subset of db.analysis_control, 5/9 (Civil) + 7/9 (Gen)

Eighth write-coverage batch, continuing without a fresh scope check.
Picked 9 of `db.analysis_control`'s 21 endpoints: the singleton "control
data" tables (`ACTL`, `PDEL`, `BUCK`, `EIGV`, `HHCT`, `MVCT`, `SMCT`,
`NLCT`, `BCCT`) — each is one record at id 1, referencing only the base
seed model's own load cases, so no per-tier geometry was needed. Deferred
the 5 Hyper-S (`-M1`) variants and the 4 country-specific `MVCT`
variants (`MVCTch`/`id`/`bs`/`tr`) as before.

First live run (Civil NX v2.2, build 08/14/2026): 3/9. Triaged:

- **`/db/EIGV`**: the manual's own first worked example uses
  `TYPE: "EIGEN"` (Subspace Iteration) and answered `"FREQ_RANGE is
  required for LANCZOS."` — the server doesn't recognize `"EIGEN"` as a
  valid `TYPE` at all despite the manual and `/info`'s own schema both
  listing it; only `"LANCZOS"`/`"RITZ"` work. Fixed by switching to the
  manual's own Lanczos example.
- **`/db/BCCT`**: `vBOUNDARY`'s `vBG` entries (`"BG1"`/`"BG2"`, the
  manual's own example values) answered `"Boundary Group not found:
  BG1"` — they have to be real `/db/BNGR` boundary groups, not free-text
  labels. Fixed with a `bngr_seed` step.

Three did **not** resolve to fixture problems, each a distinct kind of
finding:

- **`/db/ACTL`**: `TOL` never persists as written on Civil NX — POST
  succeeds and reads back correctly, but a follow-up PUT changing only
  `TOL` reads back the original value every time, confirmed even after a
  full DELETE + fresh POST with a different `TOL`. On Gen NX the same
  payload fails outright with `"Wrong Field"`, including a bare
  `{ITER, TOL}`-only payload — and Gen's own `/info` schema turns out to
  differ from Civil's/the manual's (no `CLATS`, an undocumented `ACWC`
  that answers `"Wrong Key"` when sent, ruling that field out too as the
  cause). Two different symptoms, same verdict: unresolved on both.
- **`/db/NLCT`**: Civil NX answers `"LINE_SEARCH_OPTION is required when
  OPT_ENABLE_LINE_SEARCH is true."` — neither field is in the manual or
  in `/info`'s own live schema. Tried `OPT_ENABLE_LINE_SEARCH: false`
  explicitly (same error) and a guessed `LINE_SEARCH_OPTION: "AUTO"`
  alongside `true` (also unchanged). **Passes clean on Gen NX** with the
  exact same payload — product-asymmetric, so the checker now carries two
  cases, one per product.
- **`/db/HHCT`**: Civil NX's `THETA` field has the same "write doesn't
  stick" symptom as `ACTL`'s `TOL` — POST succeeds with no error body,
  but the immediate GET reads `THETA` back as `0`, not the `1` sent,
  reproduced twice. **Also passes clean on Gen NX** with the identical
  payload — another product-asymmetric split into two cases.
- **`/db/MVCT`**: fails on *both* products, with different errors
  depending on payload completeness — the manual's full example answers
  `"Unknown Error"` on both Civil and Gen, a stripped-down minimal
  payload answers `"Wrong Field"` on Civil instead. Field names match
  `/info` on both. Noted as possibly needing the full AASHTO LRFD
  moving-load fixture chain (code → lane → vehicle → case, see the
  `"moving"` tier) built first rather than being a standalone control
  table like its 8 siblings here — untested, not pulled into this tier's
  scope given the size of that prerequisite chain.

Final result after fixes, re-run clean on both products:

- **Civil NX**: 5/9 (`PDEL`, `BUCK`, `EIGV`, `SMCT`, `BCCT` pass; `ACTL`,
  `HHCT`, `MVCT`, `NLCT` are the 4 failures).
- **Gen NX**: 7/9 (same 5 plus `HHCT` and `NLCT`; `ACTL` and `MVCT` are
  the 2 failures, confirmed as genuinely both-product issues rather than
  Civil-specific).

9 endpoints flipped to `level: write` total — 5 confirmed both products
(`PDEL`, `BUCK`, `EIGV`, `SMCT`, `BCCT`), 2 confirmed Gen-only (`HHCT`,
`NLCT`, with the `level: write` reflecting the Gen NX result specifically
per this project's convention of documenting the asymmetry rather than
averaging it away). `ACTL` and `MVCT` stay `level: read` as new
unresolved findings. `docs/coverage.json` and `ROADMAP.md` updated;
`pytest` (701) and `ruff` both clean.

Running total for the write-coverage push (batches 1-8): 64 endpoints
flipped to `level: write`, 19 left as genuinely unresolved live findings
(`NLLP`, `WVLD`, `GRDP`, `TDMF`, `RPSC`, `STRPSSM`, `LCOM-SEISMIC`,
`SPLC`, `THMS`, `SDVI`, `SDVE`, `SDST`, `SDHY`, `SDIS`, `FBLA`, `EPST`,
`EPSE`, `ACTL`, `MVCT`), plus the one confirmed live crash from batch 5
(`THNL` PUT on Gen NX, MAPI-2468). Batch 9 (the deferred fiber/
inelastic-hinge family, `db.node_element`'s Domain feature, the
remaining 12 of `db.analysis_control` — 5 Hyper-S + 4 country-specific
MVCT + `MVCT` itself once its moving-load prerequisite chain is worked
out, `db.design`, `db.moving_loads`'s remainder, `db.construction_stage`'s
hydration family, `db.pushover`, `db.bridge`, the tendon/prestress half
of `db.temperature_prestress`, the 3 deferred Hyper-S dynamic_loads
variants, `/db/DRLS`'s empty-payload shape problem, and root-causing the
19 unresolved findings above) is open for a future session.

## 2026-08-17 — write coverage batch 9: db.node_element's Domain feature, 0/3 -- /db/MADO silently drops writes

Ninth write-coverage batch. Picked up `db.node_element`'s last 3
read-only endpoints: `MADO`, `SBDO`, `DOEL` (the "Domain" feature used
for 2D/plane-stress mesh assignment). Small, self-contained scope —
`SBDO`/`DOEL` both reference a `MADO` domain by name/id, so the tier
needed a `mado_seed` creating two named domains (`DM1_SEED`/`DM2_SEED`)
plus `DOEL`'s own case targeting the base seed model's existing plate
element (id 4, nodes 5-8) rather than building new geometry.

First live run (Civil NX v2.2, build 08/14/2026): 0/3, all three
`read_back` failures with `"id N missing after wrote"`. Initially looked
like the familiar STLD/FBLD-family renumbering gotcha from earlier
batches, but a manual `GET` on all three tables immediately after
`create()` came back completely empty — not renumbered, genuinely never
written. Bisected `/db/MADO` specifically since it's the root of the
dependency chain:

- `POST /db/MADO` answers `{"message": ""}` — HTTP success, no error
  body at all — but the record is absent from a follow-up `GET`, every
  time.
- Reproduced with several payload variants: `MATL`/`PROP` pointed at the
  base model's real material/section ids (1/1), `SUB_TYPE` 1 and 2,
  `TYPE` 3 (Plane Stress) instead of 4 (Plate), and — the clearest
  signal — **the manual's own literal request-body example reproduced
  verbatim** (`NAME: "DM1"`, `MATL: 0`, `PROP: 0`, `SUB_TYPE: 2`). All
  silently no-ops.
- Checked Gen NX independently: identical `{"message": ""}` /
  empty-GET result with the same literal manual payload.

Not resolved as a fixture problem on either product — a `"message": ""`
success response that doesn't persist anything is a different failure
shape than this session's usual `"Wrong Field"`/`"Unknown Error"` class,
closer to the `/doc/SAVEAS` "command complete but no file written"
pattern this project has already documented elsewhere, just on a `/db/*`
table instead of a file write.

`SBDO` and `DOEL` both fail as a direct consequence — they reference
`DM1_SEED`/`DM2_SEED` by name/id, and those domains were never actually
created — so their own field contracts remain genuinely untested, not
confirmed broken independently of `MADO`. Left all 3 at `level: read`
with dated notes making that dependency explicit; the checker's own
cases are kept (not skipped) so a future `MADO` fix can be verified to
unblock `SBDO`/`DOEL` without touching this tier's code again.

Caught and fixed one process mistake before finalizing: `MADO`'s own
case was initially marked `confirmed=True` while drafting the fixture,
before it had actually been run live — the first real run correctly
flagged it as a **regression** (a confirmed case failing) rather than an
unverified failure, which would have been a false alarm. Reverted the
premature flag before this file/`coverage.json` were touched, so nothing
downstream saw the false regression.

`docs/coverage.json` and `ROADMAP.md` updated (all 3 stay `level: read`
— this batch added 0 to the write count, a clean miss rather than a
partial one). `pytest` (701) and `ruff` both clean.

Running total for the write-coverage push (batches 1-9): still 64
endpoints at `level: write` (batch 9 added 0), 22 left as genuinely
unresolved live findings (`NLLP`, `WVLD`, `GRDP`, `TDMF`, `RPSC`,
`STRPSSM`, `LCOM-SEISMIC`, `SPLC`, `THMS`, `SDVI`, `SDVE`, `SDST`,
`SDHY`, `SDIS`, `FBLA`, `EPST`, `EPSE`, `ACTL`, `MVCT`, `MADO`, `SBDO`,
`DOEL`), plus the one confirmed live crash from batch 5 (`THNL` PUT on
Gen NX, MAPI-2468). Batch 10 (the deferred fiber/inelastic-hinge
family, the remaining 12 of `db.analysis_control`, `db.design`,
`db.moving_loads`'s remainder, `db.construction_stage`'s hydration
family, `db.pushover`, `db.bridge`, the tendon/prestress half of
`db.temperature_prestress`, the 3 deferred Hyper-S dynamic_loads
variants, `/db/DRLS`'s empty-payload shape problem, and root-causing the
22 unresolved findings above) is open for a future session.

## 2026-08-17 — write coverage batch 10: standalone subset of db.construction_stage's heat-of-hydration family, 5/7 both products

Tenth write-coverage batch. Picked 7 of `db.construction_stage`'s 10
remaining read-only endpoints — the heat-of-hydration family
(`ETFC`/`CCFC`/`HSFC`/`HAHS`/`HPCE`/`STBK`/`HSTG`), deferring `HECB` and
`HSPT` (both keyed by a construction-stage id per the manual's own note)
and `CSCS` (references a stage name via `ASTAGE`) since none of the
three have a construction stage to attach to in this tier's fixture.
The chapter's own End-to-End workflow example covers 6 of these 7
(`ETFC`→`CCFC`→`HSFC`→`HAHS`→`HECB`→`HSTG`), so most payloads were
adapted from it rather than re-derived from the Specifications tables.

First live run (Civil NX v2.2, build 08/14/2026): 4/7. Triaged:

- **`/db/HSFC`**: `"Key Already Exist"` — the case's own id (91) collided
  with `hsfc_seed`'s second record, which the seed also placed at 91.
  Fixed by moving the case to id 92.
- **`/db/HSTG`**: passed on the first try — the fixture used real
  `/db/GRUP`-family structure/boundary group names (`SG10_SEED`/
  `BG10_SEED`) from the start rather than the manual's own made-up
  group-name example, applying the `/db/BCCT` lesson from batch 8
  proactively instead of hitting the same wall twice.

Two did **not** resolve to fixture problems:

- **`/db/HAHS`**: answered `"[Error] The element no. 1 is an element
  type in which Heat Source Assignment cannot be entered."` for element
  1 (a frame/beam). Switched to element 4 (the base model's `PLATE`) —
  same error, just renumbered to element 4. Heat-of-hydration is
  normally applied to mass concrete (piers, footings) modelled as
  `SOLID` elements, which the base seed model doesn't build — most
  likely a scope gap in this fixture rather than a confirmed product
  defect, since a real `SOLID` element was never tried. Left
  unconfirmed rather than treated as a genuine finding, pending that
  test in a future session.
- **`/db/HPCE`**: answered `"Wrong Key"` — a different error class than
  this session's usual `"Wrong Field"`/`"Unknown Error"`. Bisected field
  by field: every field *except* `ITEMS` succeeds individually (each
  answering the ordinary `"Wrong Field"` for an incomplete payload), but
  adding `ITEMS` — with real frame node ids, real plate node ids, or a
  single node — always flips the error to `"Wrong Key"` instead. Live
  `/info`'s own schema confirms `ITEMS` is a plain integer array,
  matching exactly what was sent, so this isn't a documented-vs-actual
  mismatch either. Also found two undocumented fields via `/info`
  (`START_STAGE`/`END_STAGE`, both strings, absent from the manual
  entirely) and tried them both empty and omitted — no change either
  way. Genuinely unresolved, same class as `/db/FBLA`/`/db/EPST` etc.

Re-run clean on both products after the `HSFC`/`HSTG` fixes:

- **Civil NX**: 5/7 (`ETFC`, `CCFC`, `HSFC`, `STBK`, `HSTG` pass; `HAHS`
  and `HPCE` are the 2 failures).
- **Gen NX**: same 5/7 split, confirming `HAHS`/`HPCE` aren't
  Civil-specific.

5 endpoints flipped to `level: write`; `HAHS` and `HPCE` stay
`level: read` with dated notes. `docs/coverage.json` and `ROADMAP.md`
updated; `pytest` (701) and `ruff` both clean.

Running total for the write-coverage push (batches 1-10): 69 endpoints
flipped to `level: write`, 24 left as genuinely unresolved or
scope-limited live findings (`NLLP`, `WVLD`, `GRDP`, `TDMF`, `RPSC`,
`STRPSSM`, `LCOM-SEISMIC`, `SPLC`, `THMS`, `SDVI`, `SDVE`, `SDST`,
`SDHY`, `SDIS`, `FBLA`, `EPST`, `EPSE`, `ACTL`, `MVCT`, `MADO`, `SBDO`,
`DOEL`, `HAHS`, `HPCE`), plus the one confirmed live crash from batch 5
(`THNL` PUT on Gen NX, MAPI-2468). Batch 11 (the deferred fiber/
inelastic-hinge family, the remaining 12 of `db.analysis_control`,
`db.design`, `db.moving_loads`'s remainder, `db.construction_stage`'s
`HECB`/`HSPT`/`CSCS` — needs a real construction stage built first —
`db.pushover`, `db.bridge`, the tendon/prestress half of
`db.temperature_prestress`, the 3 deferred Hyper-S dynamic_loads
variants, `/db/DRLS`'s empty-payload shape problem, retesting `/db/HAHS`
against a real `SOLID` element, and root-causing the 24 unresolved
findings above) is open for a future session.

## 2026-08-17 — correction: `EIGV`/`BCCT` were never actually confirmed on Civil NX

Re-reading batch 8's own raw result files (`extras8_civil.json`, checked_at
2026-08-16T15:47:37Z) while resuming the write-coverage push turned up a
mismatch: the code and `docs/coverage.json` both claimed `/db/EIGV` and
`/db/BCCT` were "confirmed both products," but that Civil NX run — the only
one ever made for these two cases — has both failing:

- `EIGV`: `"FREQ_RANGE is required for LANCZOS."`, the *identical* error
  the batch-8 write-up already documents for the rejected `TYPE="EIGEN"`
  attempt — except this run used the fixed `TYPE="LANCZOS"` payload
  (`iFREQ`/`bMINMAX`/`FRMIN`/`FRMAX`/`bSTRUM`) that passes clean on Gen.
  Civil answers the same error anyway, meaning it wants some additional,
  undocumented field literally named `FREQ_RANGE` that `FRMIN`/`FRMAX`
  don't satisfy.
- `BCCT`: `"Boundary Group not found: BG1"` — the exact error the
  `bngr_seed` fix (creating real `/db/BNGR` groups named `BG1`/`BG2`) was
  supposed to clear, and did clear on Gen (`extras8_gen.json`, same day,
  5 minutes later, both cases `ok`). Civil rejects the same real groups
  under the same names.

No Civil retry for either case exists anywhere in this session's scratch
output (checked — `extras8_civil2.json` was never created, unlike
`extras7_civil2.json`/`extras10_civil2.json` which do exist for their
tiers' fixed re-runs). The "confirmed both products" claim was written
without actually re-running Civil after the Gen fix landed — caught this
time by cross-checking the code against its own raw evidence, per this
project's standing "verify before confirming already done" rule.

Fixed: both `Case`s split into `products=("civil",)` unconfirmed /
`products=("gen",)` confirmed=True, same pattern as `HHCT`/`NLCT`.
`docs/coverage.json`'s `method` notes for both rewritten to state
"confirmed live on Gen NX; Civil NX fails" instead of "both products."
`ROADMAP.md` regenerated (399/399 implemented, unchanged — both stay
`level: write` since Gen alone still counts, same as `HHCT`/`NLCT`; the
batch 1-10 running total of 69 write / 24 unresolved is unaffected, only
the per-endpoint accuracy). `pytest` and `ruff` both clean.

Lesson for future batches: a product-split `Case` pair should be written
(and `confirmed` set) only after *both* products have actually been run
with the final payload — not after fixing one product's error and
assuming the fix generalizes.

## 2026-08-17 — batch 11a: `/db/STCT` (last tractable gap in `db.analysis_control`)

Of the 12 `db.analysis_control` endpoints left unattempted after batch 8, 11
are Hyper-S/`-M1` variants or the four large country-specific `MVCT`
siblings (`MVCTch`/`MVCTid`/`MVCTbs`/`MVCTtr`) — all deferred as before.
`/db/STCT` (Construction Stage Analysis Control Data) was the one genuinely
tractable endpoint left, so it got its own tier (`extras11`) rather than
waiting for a bigger batch.

Needs a real construction stage to reference (`FINAL_STAGE`), so it reuses
the `stage` tier's own `stage_1` seed (`CS_SEED`) — confirmed the manual's
own worked example makes the same mistake batch 8 already found on `BCCT`
(a made-up stage name, `"CS1"`), swapped for the real one from the start.

First Civil run failed immediately: `POST /db/STCT` answered `"Key Already
Exist"`. Investigated directly (bypassing the harness) and found the real
shape of the problem — **once a real construction stage is registered,
`/db/STCT` already holds an auto-populated default record at id 1**,
before any explicit POST. Tried `DELETE`-then-`POST` to clear it first;
`DELETE` answered its own separate error: `"[Error] Construction Stage
Analysis Control Data cannot be deleted when the Construction Stage is
registered."` So this table is POST/DELETE-locked once construction
staging is in use — a real business rule, not a fixture bug.

Fell back to a manual `PUT` on the existing id-1 record instead. The `PUT`
itself succeeded and its response echoed `iITER`/`TOL` back correctly, but
a follow-up `GET` dropped both fields entirely (present in every other
respect — `FINAL_STAGE`, `CPFC`, `bCONV`/`bTRUSS`/`bBEAM`, `bCAMBER`,
`bCHANGE_CABLE`, `iNLA_TYPE`, `bINC_TDE`, `bCNS`, `TYPE`, `iITER_CR`,
`TOL_CR` all persisted). Repeated with a second `iITER` value to rule out
a one-off — same result both times.

Gen NX doesn't pre-populate a default record, so `POST` itself succeeds
there, but the identical `iITER`/`TOL` silent-drop reproduces on the very
first `GET` after create (`"wrote 30, read back None"`) — confirming the
underlying defect is symmetric across both products, only the
POST-vs-already-exists wrinkle is Civil-specific. Likely cause: the
payload combines `iINC_NLA=0` (Linear) with `iNLA_TYPE=1` (Accumulative)
per the manual's own example, and the server may treat the two
Linear-only fields as inapplicable under Accumulative mode without saying
so.

Left as a genuine, product-symmetric finding — the `Case` in `extras11`
stays unconfirmed, documenting the Civil `"Key Already Exist"` failure
directly (closest to what a real caller hits first). `docs/coverage.json`
records the fuller story (both products, both failure modes) since the
generic harness can only exercise one of them per run. `level` stays
`read`. `ROADMAP.md` regenerated (399/399 implemented, unchanged);
`pytest` (701) and `ruff` both clean.

Running total for the write-coverage push (batches 1-11a): still 69
endpoints at `level: write`; 25 now carry a dated genuinely-unresolved or
scope-limited finding (the 24 from batches 1-10 plus `STCT`), plus the one
confirmed live crash (`THNL` PUT on Gen NX, MAPI-2468).

## 2026-08-17 — batch 11b: `moving` tier confirmed on Gen NX

The `moving` tier's own header comment had been sitting there since
2026-07-30 with a note that it *should* pass on Gen unchanged — the AASHTO
LRFD codes are the ones confirmed not gated by the region-code lock, and
the same fixture already round-trips clean on Civil — but that nobody had
actually run it against a Gen session. Ran it: `core` (base model) +
`moving` against Gen NX, identical fixture (`MVCD` "AASHTO LRFD", `LLAN`
line lanes, `MVHL`/`MVHC` HL-93 truck/tandem vehicles, `MVLD` vehicle
classes) — all 4 pass clean, full create→read→update→read→delete→read.
Re-ran Civil NX afterward too, to make sure widening `products` didn't
regress anything — also clean, 14/14 both times.

Widened all 4 `Case`s from `products=("civil",)` to both, kept
`confirmed=True` (already true from the Civil confirmation).
`docs/coverage.json`'s `method` note for `LLAN`/`MVHL`/`MVHC`/`MVLD`
updated to record the Gen write-round-trip explicitly — they'd been
`level: write` already off the Civil result plus a separate GET-only Gen
sweep from 2026-08-10, so the write/read tally is unchanged; this closes
the Gen side from "route exists" to "write proven." `ROADMAP.md`
regenerated (399/399, unchanged); `pytest` (701) and `ruff` both clean.

## 2026-08-17 — batch 11c: `/db/HECB`/`/db/HSPT` (construction-stage-keyed heat-of-hydration pair)

Batch 10 deferred `HECB`/`HSPT`/`CSCS` because they need a real construction
stage id, which this session's `stage` tier now provides (`stage_1` seeds
`CS_SEED` at id 1). Added both to the `extras11` tier alongside `STCT`.
Both are keyed by construction stage *number* in the `Assign` dict, not an
element or node id — the manual says so explicitly for each ("Assign의
키(ID)는 시공단계 번호입니다") — and both worked examples use made-up
group/function names (`"BG_SURF"`, `"CC_Standard"`, `"AT_Summer"` for
`HECB`; `"BG_BASE"` for `HSPT`), same mistake class as `/db/BCCT`'s
`"BG1"`/`"BG2"`. New `hecb_seed` creates real `/db/BNGR`, `/db/CCFC`, and
`/db/ETFC` records up front instead.

- **`HSPT`** (Prescribed Temperature): passes clean on both products,
  first try. `confirmed=True`.
- **`HECB`** (Element Convection Boundary): fails on both products with
  `"[Error] The element no. 1 is an element type in which Element
  Convection Boundary cannot be entered."` — the exact same failure shape
  as `/db/HAHS` from batch 10. `ITEMS[0].ID` (documented as a plain serial
  number) lines up numerically with "element no. 1" in the error, so it's
  plausibly read as an element reference server-side despite the manual's
  description. Given `HAHS` hit the identical wall and heat-of-hydration
  boundary conditions are normally applied to mass-concrete `SOLID`
  elements (piers, footings), this reads as the same fixture scope gap —
  the base model only builds frame and plate elements, no `SOLID` — rather
  than a fresh defect. Left unconfirmed, not re-bisected past that point.

1 endpoint (`HSPT`) flipped to `level: write`; `HECB` stays `level: read`
with a dated note pointing at the `HAHS` precedent. `docs/coverage.json`
and `ROADMAP.md` updated; `pytest` (701) and `ruff` both clean.

Running total for the write-coverage push (batches 1-11c): 70 endpoints at
`level: write` (69 from batches 1-10, +1 `HSPT` here — `LLAN`/`MVHL`/
`MVHC`/`MVLD` were already `write` before batch 11b, so widening them to
Gen doesn't add to this count); 26 with a dated genuinely-unresolved or
scope-limited finding (the 25 through batch 11a plus `HECB`), plus the one
confirmed live crash (`THNL` PUT on Gen NX, MAPI-2468). `CSCS` (composite
section for construction stage) is the one endpoint left in this family,
deferred again — it references a stage-specific section change, a bigger
fixture than this batch's scope.

## 2026-08-17 — batch 12: `db.bridge` in full, clean sweep

Picked `db.bridge` next (`GSBG`/`GCMB`/`CAMB`/`ULFC`, 4 endpoints) — fully
self-contained, no fiber/hinge dependency chain, and small enough to do in
one pass. Three of the four (`GSBG`/`GCMB`/`CAMB`) are Civil-only per
`db/bridge.py`'s own docstring; `ULFC` answers on Gen too.

One seed: a real `/db/GRUP` structure group (`SG12_SEED`, plus a second
`SG12_SEED_2` so `CAMB`'s update step has something to switch to) —
`GCMB`'s `GRUP_NAME` and `CAMB`'s three group-name fields all reference
it by name, `GSBG`'s `BODY_ELEM_GRUP_K` by its numeric key (12). The
manual's own worked examples use made-up group names for both (`"CS_0"`
.. `"CS_18"` for `GCMB`, `"FSM"`/`"PSC-BN"`/`"Key-SegK1~K5"` for `CAMB`) —
same lesson as `/db/BCCT`, used real ones from the start.

First Civil run: `GCMB`/`CAMB`/`GSBG` passed clean immediately. `ULFC`
failed with `"Wrong Field"` — the fixture had omitted `POINT` since the
manual only documents it as "required if TYPE=BEAM," but a direct check
confirmed it's actually **required unconditionally**: a `TYPE="REAC"`
payload without it is rejected, `POINT=0` clears it. Corrected the
fixture and `src/midas_nx/db/bridge.py`'s `POINT` field comment to
document this. Re-ran Civil clean (14/14), then Gen (11/11, `ULFC` only —
the other three are Civil-only by design, not attempted there).

All 4 endpoints flipped to `level: write`, all `confirmed=True` — the
first batch in this whole push where every endpoint passed with no
genuinely-unresolved finding left behind. `docs/coverage.json` and
`ROADMAP.md` updated; `pytest` (701) and `ruff` both clean.

Running total for the write-coverage push (batches 1-12): 74 endpoints at
`level: write` (70 through batch 11c, +4 here); 26 with a dated
genuinely-unresolved or scope-limited finding (unchanged this batch), plus
the one confirmed live crash (`THNL` PUT on Gen NX, MAPI-2468).

### 2026-08-24 — batch 13 (`db.design` non-rebar subset), Civil NX only

Resumed batch 13 (`/db/DCON`/`DSTL`/`LENG`/`MEMB`/`DCTL`/`LTSR`/`MBTP`/
`WMAK`) after the previous session ended blocked on both NX sessions being
disconnected. This session: Civil NX 2026 v2.2 (build 08/24/2026) was
open and connected; Gen NX stayed `disconnected` throughout, so this
batch only ever ran on Civil.

First Civil run: 3 of 8 failed. Triaged and fixed all three:

- **`/db/DCON`/`/db/DSTL` (RC/Steel Design Code)** — the manual's own
  worked-example `DGNCODE` values (`"ACI318-19"`/`"ACI318M-19"`/
  `"ACI318-14"`/`"ACI318M-14"` for DCON; `"AISC(16th)-LRFD22"` for DSTL)
  all answered `"Wrong Field"` / `"[Error] Errors detected in Steel
  Design Control Data."` — on both POST and PUT, and (for DSTL) with a
  `STEEL` material present in the model, ruling out a model-state gap.
  Bisected a wider set of `DGNCODE` values directly against the live
  server: for DCON, every non-`KCI`/`Eurocode2`/`AASHTO` code tried
  (`"KDS 24 14 21 : 2021"` included) failed the same way; for DSTL,
  every code tried except `"Eurocode3-2:05"` and `"AISC-ASD89"` failed
  the same way (`KDS`/`KBC`/`CSA`/`GB`/`BS`/`AS`/`IS`/`DIN`/`SIA`/`NBR`/
  `JGJ`/`AIJ` families all rejected). Reads as a country-design-code
  license/module gate on this particular Civil NX license, not a request
  shape bug — switched the fixture to `KCI-USD12`→`KCI-USD07` (DCON) and
  `Eurocode3-2:05`→`AISC-ASD89` (DSTL), both of which round-trip clean.
- **`/db/MEMB` (Design Member Assignment)** — `AELEM: [1, 2, 3]` failed
  `"No element among selected elements is designated as a member.(Not
  Same Member Type)"`. The shared base-model fixture's element 1 runs
  vertically (node 1→2, auto-classified `COLUMN`) while elements 2-3 run
  horizontally (node 2→3→4, `BEAM`) — grouping a column with beams into
  one `AELEM` trips this check. Elements 2-3 alone share `BEAM` and
  group fine; fixture changed to `AELEM: [2, 3]`.

Re-ran Civil clean: 18/18 (10 core + 8 extras13). `docs/coverage.json`
updated for all 8 endpoints to `level: write`, `products: ["civil"]`
only — **not** `["gen", "civil"]`, since Gen was never actually run this
session; each entry's `method` says so explicitly. `Case.confirmed`
stays `False` in `scripts/live_crud_check.py` for all 8 until Gen NX
reconnects and runs the same tier — this batch is exactly the situation
the EIGV/BCCT correction (batch 11) warned about avoiding: don't infer a
second product's result from the first's. `pytest` (701) and `ruff`
both clean.

Running total for the write-coverage push (batches 1-13): 82 endpoints
at `level: write` on at least one product (74 through batch 12, +8
here, 8 of those Civil-only pending Gen); 26 with a dated
genuinely-unresolved or scope-limited finding (unchanged), plus the one
confirmed live crash (`THNL` PUT on Gen NX, MAPI-2468). **Next session:
run `--tier core,extras13` on Gen NX first** — if it passes clean, flip
all 8 `Case.confirmed=True` and add `"gen"` to each `coverage.json`
entry's `products`; if any fail, split per-product like EIGV/BCCT rather
than guessing which fields need Gen-specific handling.

### 2026-08-24 (later) — `OCHECK`/`MAPI-2429` re-repro'd on Civil NX v2.2, build 08/24/2026: still crashes

At the user's request, re-ran the crash reproduction for `MAPI-2429`
(`perform_src_optimal_design`, `/TEMP/DESIGN/SRC/AIK-SRC2K/OCHECK`) on
whatever Civil NX build happened to be open this session, to check
whether it's still live two builds after the last confirmation
(2026-08-13, build 08/12/2026).

Built the same dummy-model shape as 2026-08-13 on a fresh `/doc/NEW`
(confirmed blank first): `Material.create` (C24 concrete, `KS01(RC)`),
`Section.create` (600×600 `DBUSER`, `SHAPE: "SB"` — real,
non-SRC-eligible), two `Node`s, one `BEAM` `Element`. All four succeeded.
Called `perform_src_optimal_design` with `SECT_LIST: [{"SECT_NO": 1,
"SECT_DB": "USER"}]`, `ANALYSIS_OPT.ANAL_TIME: 0`,
`OUTPUT.MODEL_UPDATE: False` — the same conservative payload as every
prior repro.

**Crashed again**, same underlying signature but observed slightly
differently: the call itself timed out client-side (35s, no response),
and this time the immediate follow-up `GET /db/NODE` *also* timed out
(35s) rather than returning the fast `404 client does not exist` seen
2026-08-13 — `verify_connection()` afterward showed `status:
"disconnected"`. Same "session died mid-call" outcome, just a slower
symptom on this build. Recovered via the standard restart (dialog OK →
re-launch → New Project → close → reconnect with the same MAPI key);
reconnected cleanly with the same `connectionID` as before the crash.
Dummy model was disposable test data, nothing lost.

**Conclusion: `MAPI-2429` remains live on Civil NX v2.2, build
08/24/2026** — two builds after the last confirmation (08/12/2026),
still not build-dependent, still consistent with MIDASIT's "not a
defect, no fix timeline" stance from `MAPI-2429`'s own closure.
`docs/coverage.json`'s `/TEMP/DESIGN/SRC/AIK-SRC2K/OCHECK` entry updated
with today's repro and build; no Jira action needed since the ticket is
already closed on this exact finding. Not re-tested on Gen this
session.

## 2026-08-25 — checking MIDASIT's shipped fixes on Gen NX v2.1, build 08/20/2026: MAPI-2468 (THNL) and MAPI-2431 (CD-TABLE) both confirmed fixed

Followed up asking Jira status of the whole crash-family epic (MAPI-2427)
to see which tickets were closed with an actual verified fix vs. just
closed after MIDASIT shipped a patch we'd never independently retested.
Of the 6 crash tickets: `MAPI-2378`/NMAS and `MAPI-2425`/EDMP and
`MAPI-2426`/USLC already had our own confirmation comments on the
ticket; `MAPI-2429`/OCHECK is confirmed still broken (see above);
`MAPI-2431`/CD-TABLE and `MAPI-2468`/THNL had patches shipped
(2026-08-11 and 2026-08-17 respectively) but no retest from our side —
Gen NX happened to be open this session (v2.1, build 08/20/2026, newer
than both patches), so retested both.

**`MAPI-2468` (`PUT /db/THNL` killing Gen NX) — fixed.** Raw repro first
(node + `THFC_FORCE_SEED` time-history function + `THIS_SEED` load case,
then `POST`/`GET`/`PUT` on `/db/THNL` with only `SCALE_FACTOR` changed):
the `PUT` that used to kill the session now returns in ~0.2s, session
stays healthy. MIDASIT's own comment (2026-08-17) explains the root
cause: the data layer deletes the old row when a time-history key
matches, and the API layer kept referencing it post-transaction,
dereferencing invalid memory. Then re-verified properly through the
harness: lifted `scripts/live_crud_check.py`'s `Case.products=("civil",)`
restriction on the `DynamicNodalLoad` case and re-ran `--tier
core,extras5` on Gen — `/db/THNL` now `PASS`es its full round trip
(create→read→update→read→delete→read), 17/19 in the tier (the 2
pre-existing unrelated failures, `SPLC`/`THMS`, are unchanged, documented
findings, not a regression). `docs/coverage.json`'s `/db/THNL` entry and
the `DynamicNodalLoad` case's harness comment both updated; both
products now `confirmed=True`.

**`MAPI-2431` (Column/Brace/Beam Design Forces via
`/DESIGN/RC/KDS-41-20-2022/TABLE`, `midas_nx.design.rc_kds.checks`) —
fixed.** This ticket's history was the messiest of the six: crashed
twice independently (2026-08-01, real apartment model + isolated empty
doc), MIDASIT couldn't reproduce it themselves and asked for the model,
re-crashed on a blank `/doc/NEW` retest 2026-08-07, then came back clean
on the *same* blank-doc shape 2026-08-11 — which the notes at the time
explicitly flagged as "not proof, could be intermittent, needs an
independent second re-test" given the call's history of *not* even being
monotonic with data complexity (crashed blank, clean on a 63-node real
model, on the same day). Today's retest — same blank-doc shape, Gen NX
v2.1 build 08/20/2026, a different and later build than the 08-11
patch — was the second consecutive clean pass: `get_column_design_forces
_table('')`, `get_brace_design_forces_table('')`, and
`get_beam_design_forces_table('')` all returned in <0.3s with `{}` and
`{"message": ""}`-shaped empty responses, session healthy throughout.
MIDASIT's 2026-08-11 patch comment names the actual fix: guard code
added for a Design API call made with no analysis run. Between the named
root cause and two consecutive clean passes on two different post-patch
builds, this clears the "needs an independent second re-test" bar.
`docs/coverage.json`'s three `/DESIGN/RC/KDS-41-20-2022/TABLE` entries
(Column/Brace/Beam) and their docstrings in `src/midas_nx/design/rc_kds/
checks.py` updated.

**Explicitly not covered by either fix:** the sibling `/post/TABLE` code
path (`midas_nx.post.design`'s `get_column_design_forces_table`,
`get_brace_design_forces_table`, `get_beam_design_forces_table` — a
different endpoint sharing only the `TABLE_TYPE` naming convention, per
the existing "independently-crashing siblings, not one shared root
cause" note) was **not** retested this session and stays flagged
crash-risk on Gen NX. Don't read today's fixes as clearing that endpoint
too.

**Crash-family epic status after today: 5 of 6 confirmed fixed by us
(NMAS, EDMP, USLC, CD-TABLE via `rc_kds.checks`, THNL), 1 confirmed still
broken (OCHECK/MAPI-2429, MIDASIT's own "not a defect" stance), 0 left
unverified.** `MAPI-2431` and `MAPI-2468` haven't had a confirmation
comment posted back to Jira yet — that needs the user's explicit
go-ahead per this project's standing Jira-consent rule before doing so.

## 2026-08-25 (later) — batch 14: the 12 Civil-only-by-design endpoints (5 db.moving_loads, 7 db.analysis_control Hyper-S/-M1), all confirmed on Civil NX v2.2, build 08/24/2026

User asked to continue the write-coverage push on Civil NX specifically
("civil nx 검증 진행해볼래?"). Picked the clearest Civil-only target: the
12 endpoints that are Civil-only *by design* rather than by an
undocumented Gen gap — 5 from `db.moving_loads` (`CRGR`/`CJFG`/`DYLA`/
`DYFG`/`DYNF`) and 7 Hyper-S (`-M1`) variants from
`db.analysis_control` (`ACTL-M1`/`EIGV-M1`/`HHCT-M1`/`NLCT-M1`/
`STCT-M1`/`BCGD-M1`/`BCGA-M1`). Hyper-S is a Civil NX-only solver, so
these were never reachable on Gen at all — unlike most of this
project's other Civil-only findings, which are just an undocumented gap
in an otherwise-shared endpoint.

First checked whether Hyper-S needs a model-level mode switch before
these endpoints respond: `GET /db/STYP-M1` (Structure Type, Hyper-S)
answered its defaults on a completely fresh, non-Hyper-S document — no
switch needed, the `-M1` endpoints are just always reachable on Civil.

Direct ad-hoc bisection (not yet through the harness) got 8/12 working
on the first attempt (`CRGR`/`CJFG`/`DYLA`/`ACTL-M1`/`EIGV-M1`/
`HHCT-M1`/`STCT-M1`/`BCGD-M1`); 4 failed and were triaged:

- **`/db/DYFG`** — "Wrong Field" on every payload shape tried, including
  the manual's own verbatim worked examples, with `/db/MVCD.CODE` set to
  `EUROCODE` (the documented prerequisite). Bisected via `GET
  /info/db/DYFG` (schema matched the manual exactly) and by varying the
  payload systematically: sending **all six documented fields
  simultaneously**, including the ones the manual marks conditionally
  required only for the *other* `INPUT_TYPE`/`OPT_REDUCE_EFF` branch,
  fixed it. Confirmed reproducible on a fresh document. Same defect
  class as `/db/NMAS`'s `rmX`/`rmY`/`rmZ` bug, just a clean rejection
  instead of a crash. The sibling `/db/DYNF` does **not** share this —
  its conditional requiredness works as documented; it only needed a
  real element id as the `Assign` key (per the manual's own note that
  DYNF's key is an element id, not a serial number).
- **`/db/BCGA-M1`** — "Wrong Field" on `BC_SELECT` regardless of which
  manual-documented value was tried (`"CONS"`, `"MCON"`, etc). `GET
  /info/db/BCGA-M1` revealed the live server's real enum is a
  *completely different abbreviation scheme* from the manual's own
  table — `SSSF`/`ES`/`EW`/`PS`/`SP`/`PSS`/`GSS`/`SSS`/`EL`/`RL`/`GL`/
  `CGL`/`BER`/`BEO`/`PER`/`LC` vs the manual's `SECF`/`ESSF`/`EWSF`/
  `PSSF`/`WSSF`/`CONS`/`NSPR`/`GSPR`/`SSPS`/`ELNK`/`RIGD`/`NLNK`/`CGLP`/
  `FRLS`/`OFFS`/`PRLS`/`MCON`. Not a spelling-level typo like several
  earlier findings this project has documented — a real enum table
  substitution, most likely an editing artifact from a different,
  longer naming convention. Using the live values (`"SP"`/`"LC"`) fixed
  it immediately.
- **`/db/NLCT-M1`** — "Wrong Field" with `LC_SCOPE` set to a real load
  case name (`"DL"`) and `CONV_CRITERIA` all `OPT_USE: false`. The
  manual's own worked example uses the literal keyword `"ALL"` for
  `LC_SCOPE`, not a load case name — switching to `"ALL"` and giving
  `CONV_CRITERIA.DISP` a real `OPT_USE: true`/`VALUE` fixed it.
- **`/db/DYNF`** — see DYFG above; this one just needed a real element
  id, not a payload change.

With all 4 fixed, re-ran ad-hoc — 12/12 clean — then encoded the seeds
and cases properly into `scripts/live_crud_check.py` as a new
`extras14` tier and ran it **through the harness** (the actual bar for
`Case.confirmed=True`, not an ad-hoc script): first attempt surfaced 2
more issues the ad-hoc script hadn't hit, both harness/fixture bugs
rather than SDK defects:

- `/db/DYLA` needs `/db/MVCD.CODE` in `{KSCE-LSD15, AASHTO LRFD,
  PENDOT}` — a *different*, mutually exclusive requirement from
  DYFG/DYNF's `EUROCODE`. Since this harness runs all of a tier's seeds
  before any of its cases (no interleaving), a single seed can't satisfy
  both. Fixed by seeding `KSCE-LSD15` up front for `DYLA`, then adding a
  dedicated mid-list `_MvcdSwitch` case (a local `MovingLoadCode`
  subclass restricted to `GET`/`PUT` only, to update the existing
  seeded record without re-`POST`ing over it or `DELETE`ing it
  afterward) that flips the same singleton record to `EUROCODE` before
  `DYFG`/`DYNF` run.
- `/db/BCGA-M1`'s `BC_SELECT` comes back in a server-chosen order, not
  the order sent (`["SP","LC","EL"]` sent, `["SP","EL","LC"]` read back)
  — the case's probe now sorts both sides before comparing.

Re-ran: **23/23 clean** (10 core + 13 extras14 — `MVCD`'s own switch
case is a 13th row alongside the 12 real endpoints). `docs/coverage.json`
updated for all 12 endpoints (`level: write`, `products: ["civil"]`,
Gen genuinely unreachable so no "pending" caveat needed here unlike
batch 13); `src/midas_nx/db/moving_loads.py` (`RailwayDynamicFactorPayload`)
and `src/midas_nx/db/analysis_control.py`
(`AssignBoundaryCombinationHyperSPayload`) docstrings corrected.
`pytest` (701) and `ruff` both clean.

Running total for the write-coverage push: 157 endpoints at `level:
write` on at least one product (145 through the 08-25 crash-family
session, +12 here).

## 2026-08-27 — sibling manual repo's 24-chapter "전수 재검증" pass: 3 live-evidence conflicts resolved, the rest surveyed but not yet applied

The sibling manual repo (`E:\AI Study\MIDAS-API`) moved from
`fbd4f979...` (this SDK's `vendored_at_commit`) to `05eb6c08...` via a
"전수 재검증" (full re-verification) pass that re-checked all 27
chapters against MIDASIT's official pages — 24 chapters actually
changed. Far too large to reflect in one session; a general-purpose
agent surveyed all 24 diffs against the current SDK source and flagged
3 as directly contradicting something this SDK already documents as
independently live-verified. Per this project's standing rule, none of
the 3 were "corrected" from the manual's new text alone — each was
re-tested live first.

**1. `get_story_load_summary_table` (`post/pre_process.py`) — SDK was
right, manual's new correction is wrong.** The manual's 08-25 sync
(commit `05c0550`) claimed the 2026-08-06 sync had confused this table
with its sibling Story Mass Summary Table, and the real params are just
`TABLE_NAME`/`TABLE_TYPE`(`STORY_LOAD_SUMMARY_{dir}`)/`EXPORT_PATH` —
directly contradicting this SDK's own 2026-08-13 live confirmation
(`TABLE_TYPE="STORY_LOAD_{dir}"` plus `unit`/`styles`/`components`/
`load_case_names`, returning real per-story rows). Re-tested live on
Gen NX (v2.1, build 08/20/2026): `TABLE_TYPE="STORY_LOAD_X"` still
answers cleanly (`{"message": ""}` on a document with no story data,
same shape as the known-good sibling `STORY_MASS_X`); `TABLE_TYPE=
"STORY_LOAD_SUMMARY_X"` (every casing tried) consistently answers
`"there was an error creating utbl"` — an unrecognized-table-type
error. The manual's new correction is itself wrong; not applied.

**2. `get_story_properties` (`ope.py`) — manual was right, SDK had a
genuine typo.** Four historical 404s (2026-07-30 x3 Gen, 2026-07-31
Civil, 2026-08-01 Gen) were all attributed to "unexplained, possibly a
dead route." The manual's re-verification found the real URL is
`/ope/STORYPROP` (STORY+PROP), not `/ope/STORPROP` — the SDK had been
calling a URL with a missing letter the entire time. Re-tested live on
Gen NX: `POST /ope/STORPROP` still 404s; `POST /ope/STORYPROP` routes
through cleanly (200, `"There is no valid story information."` on a
document with no Story data — a domain error, not a routing error).
Also resolved a side puzzle: `GET /info/ope/STORPROP`'s 404 (taken
earlier as routing-level confirmation the route doesn't exist) turns
out to be uninformative — `GET /info/ope/STORY_IRR_PARAM` 404s too,
for an endpoint independently confirmed working via POST, so `/info/
ope/*` apparently doesn't work for any `/ope/*` endpoint, working or
not. Fixed: `get_story_properties()` now posts to `/ope/STORYPROP`;
`docs/coverage.json`'s `/ope/STORPROP` entry renamed and reconfirmed.

**3. `WallRebarItem.vSTORY_NAME` (`db/design.py`, `/db/REBW`) — SDK
was right, manual's new correction is wrong.** The manual's
re-verification claimed the field is `vSTORY_KEY` (Integer array), not
`vSTORY_NAME` (String array) — contradicting the 2026-07-29 rewrite,
which had confirmed the field three independent ways against a real
production Gen NX model (GET echo, `/info/db/REBW` schema, and a live
PUT round-trip). Re-checked `GET /info/db/REBW` live again today: the
server's own schema still names the field `vSTORY_NAME`, `items.type:
"string"` — exactly matching the existing TypedDict. The manual's new
claim is wrong on this field; not applied.

**The other 21 changed chapters were surveyed (not deep-reviewed field
by field) and are NOT yet reflected in the SDK.** Highlights worth
prioritizing next, none live-tested yet: `/db/GSTP`'s 21-value spring
matrix is documented as upper-triangular when the manual's re-check
says it's diagonal-terms-first — the manual calls this "실무에 영향이
큰 정정" (high real-world impact; wrong DOF assignment if unfixed).
`/db/NSPR`'s `DIR` enum and `SK` field are both wrong (`STIFF`/
`FUNCTION` don't exist as documented). `/db/REBC`'s entire payload
shape is confused with a different endpoint. `post/result_1.py` has
two wrong `TABLE_TYPE` constants (`BEAMFORCEBYMAX`/`BEAMFORCESIP`
should be `BEAMFORCEVBM`/`BEAMFORCESTP`). `04_DB_Properties.md` and
`05_DB_Boundary.md` carry the largest volume of under-documented
(missing, not wrong) fields — `TDME`'s `A`/`B` vs `KDS-2016`'s actual
`iCTYPE`/`DENSITY` requirement is probably the highest-value one there.
Full per-file breakdown is in this session's conversation, not
re-derived here — ask for it again if starting the next pass.

**`docs/coverage.json`'s `vendored_at_commit` stays at `fbd4f979...`,
not bumped to `05eb6c08...`** — only 3 of 24 changed chapters are
actually reflected; bumping now would falsely claim the rest are synced
too. `python scripts/check_manual_drift.py` will keep reporting
`has_diff: true` until the remaining 21 are addressed, which is
correct, not a bug. `pytest` (704) and `ruff` both clean after this
session's 3 fixes.

## 2026-08-27 (later) — working the 24-chapter drift survey's priority list: 5 more runtime-breaking bugs confirmed and fixed live on Gen NX

Continuing from the priority list the earlier survey left (GSTP, NSPR,
REBC, `post/result_1.py`'s two `TABLE_TYPE` typos, and `/db/TDME`'s
`A`/`B` vs `KDS-2016` conflict) — Gen NX was open, so each item was
live-tested before applying any fix, per this project's standing rule.

**`/db/GSTP`'s 21-value matrix order — the manual's re-verification was
right, confirmed by direct GUI inspection.** Posted a probe spring with
a unique value (11-31) at each of the 21 array indices, then had the
user open the General Spring Type dialog in Gen NX and read the 6x6
grid back. Every single cell matched the manual's new "diagonal terms
first, then off-diagonal row by row" order exactly — SDx/SDy/SDz/SRx/
SRy/SRz diagonal = indices 0-5, then row-1 off-diagonals at 6-10, row-2
at 11-14, row-3 at 15-17, row-4 at 18-19, row-5 at 20. The SDK's prior
"upper-triangular" claim (K11,K12,K13,...,K22,K23,...) put stiffness at
the wrong degrees of freedom for anyone who filled the array that way.
`GeneralSpringTypePayload` rewritten with the full index table. Note:
`scripts/live_crud_check.py`'s own `spring_types`/`GS_CRUD` fixtures
were built under the old (wrong) assumption too — harmless in practice
since neither Case's probe function actually asserts SPRING array
values (GSTP's checks NAME, NSPR's checks SDR unrelated to GSTP), but
the physical spring those fixtures create doesn't mean what its
in-code comment implies. Not worth rebuilding the fixture data itself
since no assertion depends on it; the misleading comment on the LINEAR
NSPR case was fixed.

**`/db/NSPR`'s COMP/TENS/MULTI shape — manual right, SDK had a fully
fictional field.** The old shape (`DIR` 1-4, `DV`, an `SK` array) was
confirmed live to answer `"[Error] Point Spring value has(have) been
incorrectly entered."`; `SK` doesn't exist as a field at all. The real
shape — `STIFF` (single number) for COMP/TENS, `FUNCTION` (an
`/db/MLFC` id) for MULTI, `DIR` 0-6 (six signed directions plus
Vector), `DV` only meaningful when `DIR=6` — round-tripped cleanly,
confirmed separately for `DIR=6`+`DV`, `DIR=0` with no `DV`, and
LINEAR's previously-undocumented `Cr` damping array. `PointSpringItem`
rewritten.

**`/db/REBC` — manual right, SDK's whole payload was confused with a
different endpoint.** The old shape (`CREATE_SUB_SECTION`/`ELEMS`/
`HOOK_TYPE`, a single-object `MAIN_BAR`, top-level `DO`) answered
`"Wrong Field"` on the first live attempt. The real shape (`vMAIN_BAR`
as an array of `{NAME,NUM,ROW,D0,bUSE_CORNER,NAME_CORNER}`, integer
`HOOP_TYPE` 1=Tied/2=Spiral, `bSAME_SPACE_END_CEN`,
`NUM_BAR_BC_JOINT`) round-tripped a full POST→GET→PUT→DELETE→GET cycle
— DELETE genuinely removed the record (confirmed via a follow-up GET
returning empty). Also **not POST-only** as previously documented —
the `METHODS = frozenset({"POST"})` override was removed; full CRUD
confirmed live. `ColumnRebarItem` rewritten, `ColumnMainBarSpec`
renamed to `ColumnMainBarItem` to match the array-of-objects shape.

**`post/result_1.py`'s two `TABLE_TYPE` constants were unrecognized
values, not just misspelled labels.** `TABLE_TYPE_BEAM_FORCE_BY_MAX`
(was `"BEAMFORCEBYMAX"`) and `TABLE_TYPE_BEAM_FORCE_STATIC_PRESTRESS`
(was `"BEAMFORCESIP"`) both answered `"there was an error creating
utbl"` (unrecognized table type) on Gen NX. The manual's corrected
values (`"BEAMFORCEVBM"`, `"BEAMFORCESTP"`) instead answer `"Cannot
generate table data as there is no analysis result"` — a materially
different error confirming the table type itself is now recognized;
not re-tested against a document with a real analysis run for
populated data, so `coverage.json`'s level stays `read`.

**`/db/TDME`'s `A`/`B` vs `KDS-2016` conflict — manual right, and it
explains an old open question.** Live-confirmed: `CODENAME="KDS-2016"`
with `A`/`B` answers `"[Error] Time Dependent Material(Comp. Strength)
input data contain errors."`; the same material with `iCTYPE`/
`DENSITY` instead round-trips cleanly. `CODENAME="Korean Standard"`
(a separate, differently-named code) confirmed to work with `A`/`B` as
expected. This resolves a finding already on record from an earlier
session (`KDS-2016` recognized but rejected with `A`/`B`, cause
unidentified at the time, this file's own 2026-07-2x sections) — the
missing fields were `iCTYPE`/`DENSITY`, not a naming problem.
`TimeDependentMaterialStrengthPayload` rewritten with a full
per-`CODENAME` field group table; only the `KDS-2016`/`Korean
Standard`/`ACI` groups were live-tested, the rest (`Russian`, the two
`Japan` variants, etc.) are transcribed from the manual's
re-verification and not independently confirmed.

`docs/coverage.json` updated for `/db/GSTP`/`/db/NSPR`/`/db/REBC`/
`/db/TDME` (all flipped or reconfirmed `level: write`) and the
`post/result_1.py` aggregate entry (route/type confirmed, `level`
stays `read`). Global write coverage: 158/399. Tests updated to match
(`tests/db/test_design_setup.py`'s REBC tests, `tests/post/
test_result_1.py`'s TABLE_TYPE assertions). `pytest` (704) and `ruff`
both clean. **Remaining from the priority list, not yet done**: the
`04_DB_Properties.md`/`05_DB_Boundary.md` under-documented (missing,
not wrong) fields flagged in the earlier survey — `PlasticMaterialPayload`'s
DP/MA/DM sub-objects, `InelasticMaterialKentParkParam`'s 4 missing
fields, `SectionStiffnessItem`'s J-end block, `SectionReinforcementPayload`'s
`MBAR_ITEMS`, `FiberDivisionPayload`'s wrong `FIBR_BASE_KEY` type plus
missing fields, `GroupDampingPayload`'s Rayleigh-damping branch,
`TaperedGroupPayload`'s Y-axis POLY branch, `SeismicDeviceIsolatorPayload`'s
`SDIS_DEV_TYPE` enum and nested shapes, `LinearConstraintSlave`'s
`COEFF`/`WEIGHT` split, the three badly-incomplete seismic-device
classes, `GeneralLinkPropertyPayload`'s missing fields, and
`GeneralLinkHyperSPayload`'s outdated stub — lower severity (additive
gaps, not actively-wrong values that break a live call) so deferred
rather than blocking. Still 21 of the 24 changed manual chapters not
yet reflected at all; `vendored_at_commit` stays unbumped.

## 2026-08-27 (even later) — clearing most of the deferred properties/boundary gaps, plus 9 more chapters; 12/24 chapters now reflected

Continuation of the previous entry's deferred list, worked in three
parallel passes (Gen NX live throughout; Civil NX's session key answered
`client does not exist`/404 the whole time, so every Civil-only or
Hyper-S-only item below is manual-sourced/schema-confirmed only, not
round-tripped). All three passes ran until this Claude Code account hit
its monthly spend limit mid-session and were finished by hand afterward
— noted per item below as "agent pass" vs. "finished by hand".

**`04_DB_Properties.md` (agent pass, completed in full):**
- `/db/EPMT` `PlasticMaterialPayload`: added the entirely-missing `DP`
  (Drucker-Prager → `DRUCKER`), `MA` (Masonry → `MASONRY`), `DM` (Concrete
  Damage → `CONCDMG`) branches, and corrected `HARDENING_COEF` from
  Optional to Required-when-`OPT_HARDENING`-defaults-to-0. Manual-sourced
  (article id `35808376517913`), not independently live-tested.
- `/db/FIMP` `InelasticMaterialKentParkParam`: added `EC1_METHOD`/`EC1`/
  `Z`/`STRENGTH_AFTER`. Manual-sourced only (article id `35944335180569`).
- `/db/TSGR` `TaperedGroupPayload`: added the Y-axis polynomial fields
  (`YEXP`/`YFROM`/`YDIST`).
- `/db/SECF` `SectionStiffnessItem`: added the Tapered-section J-end block
  (`W_SF`/`IPART`/`bDiffIJ`/etc.).
- `/db/RPSC` `SectionReinforcementPayload`: added the previously-missing
  required `MBAR_ITEMS` (longitudinal reinforcement) plus its sibling
  shear-reinforcement fields.
- `/db/FIBR` `FiberDivisionBaseItem.FIBR_BASE_KEY`: corrected from `bool`
  to `int` — both the manual's JSON Schema and Request Example
  (`"FIBR_BASE_KEY": 752`) show an integer key, not a boolean. Also added
  `OPT_MONITORED_FIBER`/`MONITORED_FIBER`. Manual-sourced only.
- `/db/GRDP` `GroupDampingPayload`: added the entire Element Mass &
  Stiffness Proportional / Rayleigh-damping scheme (`bExistElement` + 17
  fields, `GROUP_DAMPING_ITEMS[]`, two priority fields) that was missing
  outright — only the Strain Energy Proportional scheme was typed before.
  **Live-confirmed root cause of a standing failure**: `/db/GRDP` had been
  stuck at `level: read` since 2026-08-16 because a write attempt using
  the (at-the-time-incomplete) manual's worked example answered `"Wrong
  Field"`; retested 2026-08-27 on Gen NX with the full field set via a
  throwaway `/db/MATL` fixture — POST/GET/DELETE round trip succeeded.
  `docs/coverage.json` bumped to `level: write` (Gen only).
- `/db/TDMT` code table: 5 previously-undocumented `CODE` values added to
  the docstring (`INDIA_IRC_112_2020`/`AS_2017_AMD_2024`/
  `AS_2018_AMD_2021`/`NEWZEALAND_2022`/`CHJTG_T_D65_2015`) — purely
  documentation, `CODE` was already untyped `str`.

**`05_DB_Boundary.md`:**
- *(agent pass)* `/db/NLLP` `GeneralLinkPropertyPayload`: added
  `DIST_RATIO_DY`/`DIST_RATIO_DZ`/`COUPLED_INPUT_METHOD`, schema-confirmed
  via `GET /info/db/NLLP` on Gen NX (types match). A live POST round trip
  was attempted but every `/db/NLLP` create that session — including the
  manual's own unmodified example — answered `"Unknown Error"` while an
  unrelated `/db/GSTP` write succeeded moments earlier/later in the same
  session; treated as a session-specific anomaly, not evidence against
  the fields.
- *(agent pass)* `/db/NLNK-M1` `GeneralLinkHyperSPayload`: rewritten from
  a 3-field stub to the full `/db/NLNK`-equivalent shape
  (REF_SYSTEM/INPUT_METHOD branching + ANGLE/POINT/VECTOR value arrays)
  plus `IEHP_NAME`. Not live-verified — Hyper-S/Civil-only, Civil session
  unavailable (`GET /db/NLNK-M1` and `GET /info/db/NLNK-M1` both answered
  `client does not exist`).
- *(agent pass, live-confirmed)* `/db/SDVI` `SeismicDeviceViscousDamperItem`:
  added the six `EXFN_*`/`OPT_EXFN_CE` fields (Exponential dashpot type).
  Confirmed via a clean POST/GET/DELETE round trip on Gen NX
  (`DASHPOT_TYPE=2`); the manual's own Request Example sends all 12
  fields regardless of `DASHPOT_TYPE` and the server didn't reject the
  Exponential-only fields under Linear/Bilinear in ad-hoc testing either,
  so the SDK now sends the full set unconditionally.
- *(agent pass, live-confirmed)* `/db/SDVE` `SeismicDeviceViscoelasticDamperPayload`:
  rewritten from a 3-field stub (`COMMON`/`MATERIAL_TYPE`/`SHEAR_AREA`) to
  17 fields — the manual's Specifications table only documents those same
  3, but its own Request Example sends 14 more, confirmed real via a
  round trip.
- *(agent pass, partially live-confirmed)* `/db/SDST`
  `SeismicDeviceSteelDamperPayload`: rewritten. The manual's official
  Specifications table lists `MATERIAL_TYPE`/`MULTIPL` — fields that
  actually belong to the sibling SDVE page, apparently cross-contaminated
  in the vendor's source docs. `GET /info/db/SDST` on Gen NX confirms no
  such properties exist server-side; it lists exactly `K0`/`P1`/`ALPHA1`/
  `KB` plus 4 hysteresis-model sub-objects (`BL2`/`LY2`/`LY3`/`IK2`).
  `K0`/`P1`/`ALPHA1`/`KB`+`BL2` confirmed via a live round trip; `LY2`/
  `LY3`/`IK2` are schema-confirmed only.
- *(finished by hand, live-confirmed)* `/db/SDHY`
  `SeismicDeviceHystereticIsolatorPayload`: added `P1`/`P2`/`ALPHA1`/
  `ALPHA2`/`BETA`/`Phi`/`LAMBDA` (previously only `COMMON`/
  `SDHY_HYS_MODEL`/`MSS`/`K0` were typed). **Root-caused a standing
  `level: read` failure**: `/db/SDHY` had been stuck since 2026-08-16
  because the write attempt (using the then-incomplete manual example)
  answered `"Wrong Field"`; retested with the full field set — clean
  POST/GET/DELETE round trip on Gen NX. `docs/coverage.json` bumped to
  `level: write` (Gen only). The manual's own table also lists a
  `MULTIPL` field absent from its JSON Schema/Request Example — left out,
  same cross-contamination pattern as SDST/SDVE.
- *(finished by hand, partially live-confirmed)* `/db/SDIS`
  `SeismicDeviceIsolatorPayload`: rewritten from 3 loose `Any` fields to
  proper `LRB`/`NRB`/`SB` sub-TypedDicts, correcting five errors the
  manual repo's own 2026-08-25 re-verification found in its prior text:
  (1) `SDIS_DEV_TYPE`'s 3rd value is `"SLD"`, not `"SB"` (`"SB"` is only
  the data object's key); (2) LRB's `OPT_CONS_NONL`/`BETA`/`ALPHA`/
  `SIGMA_V` nest inside a `DX` sub-object, not siblings of `KE`/`AR`/`TR`;
  (3) LRB has two distinct stiffness fields, `KE` and `K0` — `K0` was
  missing; (4) NRB has `AR`/`TR`/`KH`/`DX`, not just `KH`; (5) SB was
  missing `QD`(Index)/`Pi_VALUE`. **Root-caused part of the same standing
  `level: read` failure as SDHY/GRDP**: retested on Gen NX — the `SLD`
  variant round-tripped cleanly (POST/GET/DELETE), confirming the fix;
  `docs/coverage.json` bumped to `level: write` (Gen only) on the
  strength of that. The `LRB` variant still answers `"Wrong Field"` even
  with the corrected shape, but `GET /info/db/SDIS` independently
  confirms the corrected LRB nesting matches the live schema exactly —
  per this project's established pattern that `"Wrong Field"` usually
  means an unrecognized *value* rather than a wrong shape, this is
  suspected to be `SDIS_HYS_MODEL="BiLinear"` not being a recognized
  literal, not a structural defect; left unresolved, flagged in the
  docstring. `NRB` untested either way.
- *(finished by hand, live-confirmed)* `/db/MCON` `LinearConstraintItem`
  / `SLAVES[]`: split into `LinearConstraintSlaveExplicit`
  (`NODE_KEY`+`COEFF`+`DOF`, when `TYPE="EX"`) and
  `LinearConstraintSlaveWeighted` (`NODE_KEY`+`WEIGHT`, when `TYPE="WD"`)
  — the old single `LinearConstraintSlave` TypedDict only had
  `NODE_KEY`+`COEFF` and was silently wrong for `TYPE="WD"` (no `WEIGHT`
  field existed at all) and incomplete for `TYPE="EX"` (missing `DOF`).
  Live-confirmed via two separate POST/GET/DELETE round trips on Gen NX
  (one per `TYPE`) using the manual's own worked example values.

**Nine smaller chapters (agent pass, all completed):**
- `02_DB_Project_Structure.md`: `/db/STYP` gained default-value
  documentation for 5 booleans + `SMASS` (manual-sourced, not
  live-tested — `/db/STYP` is new-file-only data, can't be probed without
  `/doc/NEW` against a session that might hold real work). `/db/NPLN`:
  corrected `TOL` (default `0`, was undocumented) and `COORD` (plain
  Optional default `0`, was wrongly marked conditionally-Required) — both
  **live-confirmed** on Gen NX via a POST omitting both fields, GET
  reading back the defaults, then deleting the probe record.
- `03_DB_Node_Element.md`: `SkewPayload.iMETHOD` defaults to `1` (Angle)
  when omitted — **live-confirmed** on Gen NX via a probe-node round trip.
- `09_DB_Dynamic_Loads.md`: `HyperSAnalysisCase.ANAL_METHOD` gained a 3rd
  value (`2`=Static), manual-sourced only (THIS-M1 is Hyper-S/Civil-only,
  session unavailable).
- `10_DB_Construction_Stage.md`: `/db/CSCS`
  `CompositeSectionPartInfo.WAREA` (self-weight stiffness scale factor —
  the manual's table jumps IZZ→IW but the schema/examples all show WAREA
  between them) and `OPT_UPDATE_ALL_H` added; manual-sourced only.
- `11_DB_Settlement_Misc_Loads.md`: `/db/WVLD` `WaveLoadPayload.CREST`/
  `UNIT` corrected from an unsourced guess (`"MAX"`/`"MANUAL"`) to the
  only values the manual's own Request Example actually shows
  (`"MXM"`/`"PHASE"`) — flagged as example-confirmed, not an exhaustive
  enum, since neither version of the manual's table lists literal values
  for these fields at all. `GRID_X`/`GRID_Z` comments clarified. Not
  live-tested — `/db/WVLD` is Civil-only, session unavailable.
- `12_DB_Analysis_Control.md`: `/db/STCT` `iBSC` relabeled from "Bi-Section
  Control" to "Beam Section Property Option" (Constant=0/Change with
  Tendon=1) — a different concept entirely; the old label described a
  concept actually covered by the unrelated `BSSTEP`/`ADSTEP` fields.
  `/db/STCT-M1`: `ANAL_TYPE.iINC_NLA` gained a 4th value (Geometric+
  Material Nonlinear=3) and a new `bIEMF` field; `CREEP_SHRINKAGE.TYPE`
  corrected from `"SHRINK"` to `"SHRINKAGE"` (STCT-M1 differs from legacy
  STCT's spelling); top-level gained `iBSC` (default `1`, deliberately
  different from legacy STCT's default `0`), `FRAME_OUTPUT`, `bSAVE_OCS`,
  `NONL_CONTROL`. All Hyper-S/Civil-only, manual-sourced only (session
  unavailable).
- `13_DB_Load_Combinations.md`: investigated the manual's 2026-08-26 claim
  that a phantom `NO` field should be dropped from all six `LCOM-*`
  endpoints — **live-tested and found the manual wrong**: POST/GET on
  `/db/LCOM-GEN` (Gen NX, 2026-08-27) confirms the response's `NO` field
  is real and server-populated, not a client-side artifact. No SDK change
  made; `docs/coverage.json`'s `LCOM-*` entries annotated with this
  contradiction so a future manual sync doesn't silently "fix" it away.
- `14_DB_Pushover.md`: `/db/POGD-M1` `GEO_NONL_TYPE` enum order corrected
  — this file had it as None=0/P-Delta=1/Large Displacements=2 (following
  a JSON Schema description's word order that turns out to contradict its
  own Specifications table), while `db/dynamic_loads.py`'s two
  same-concept fields already had the table's order (None=0/Large
  Displacement=1/P-Delta=2); reconciled to match those two — this file
  was the inconsistent one. `/db/PHGE` `AssignPushoverHingePropertiesPayload.TYPE`
  gained the 4th documented value, `"G-LINK"` (General Link), previously
  omitted by an unbounded "e.g." phrasing.

**Still not started** (ran out of session budget): `15_OPE.md`,
`16_VIEW.md`, `19_/20_POST_AnalysisResult...md`, `21_POST_StoryTables.md`
— none of `ope.py`/`view.py`/`post/*.py` were touched this pass. Combined
with the 3 conflicts + 5 priority items from the previous entry, **12 of
the 24 changed chapters are now reflected**; 12 remain, all previously
surveyed (see the prior entry's punch list for `15`/`16`/`19-20`/`21`'s
specific items). `vendored_at_commit` stays unbumped
(`fbd4f9796824b8967ea748f3bcd0d329fe39fb55`). `pytest` (706), `ruff`, and
`mypy` all clean after this pass.

## 2026-08-27 (yet later) — the last 4 chapters: 15_OPE, 16_VIEW, 19-20_POST result tables, 21_POST story tables; all 24 chapters now reflected

Finished by hand (no background agents this pass — still rate-limited).
All live checks on Gen NX; Civil NX remained unreachable all session.

- **`15_OPE.md` `/ope/STORY_PARAM` `StoryCheckParameterArgument.COUNTRY_CODE`**:
  corrected `"NTCS2020"` → `"NTC2020"` (no S) — the manual's 2026-08-26
  re-verification (article id `49514705474457`) found this endpoint's own
  Specifications table uses the no-S spelling, distinct from the sibling
  `StoryIrregularityCheckParameterArgument` (§11) which genuinely does use
  `"NTCS2020"`/`"NTCS2023"` (with S) — the manual explicitly flags the two
  endpoints as using different literals for the same code. Table-sourced
  only, not live-tested (needs a real story model).
- **`15_OPE.md` `/ope/MEMB` `MemberAssignmentArgument.ELEM_LIST`**: the
  manual's 2026-08-26 re-verification claimed the real key is `"AELEM"`
  (reasoning from the worked examples and the *response* body, which does
  use `AELEM`). **Live-tested on Gen NX and found the manual's claim
  backwards**: with real elements in the model, a request using
  `"ELEM_LIST"` succeeded (and its response echoed `"AELEM"`, matching the
  manual's response example — that's where the confusion came from); the
  identical request using `"AELEM"` failed with `"There is no valid
  element information."` — the server didn't recognize it as a request
  field. No SDK change; `ELEM_LIST` was already correct. Second example
  this session (after `13_DB_Load_Combinations.md`'s `NO` field) of a
  manual "correction" that doesn't survive a live test — see the Caveat
  section's underlying point, restated in `reference_midas_api_manual.md`.
- **`15_OPE.md` `/ope/AUTOMESH` `AutoMesher.METHOD`/`TYPE` (and
  `AutoMeshProperty.ELEMENT_TYPE`)**: the manual's 2026-08-26
  re-verification makes the same "table says spaced, example says
  stripped, trust the example" argument that turned out backwards for
  `StoryIrregularityCheckParameterArgument` earlier this session (see the
  2026-08-27-first entry above). Attempted to settle it live on Gen NX;
  inconclusive — a POST using only single-word values for these three
  fields (so it didn't actually exercise the disputed spacing) failed with
  a generic `"MIDAS GEN NX second query is wrong"` unrelated to spelling.
  Not pursued further. **Left unchanged at the table's spaced form**,
  explicitly not applying the manual's unverified claim — flagged in the
  docstring as needing a real multi-word-value round trip to resolve
  either way.
- **`16_VIEW.md` `/view/ACTIVE` `ActiveArgument`**: added
  `IDENTITY_TYPE="STORY"` and its companion `STORY_ACTIVE` field
  (`"FLOOR"`/`"ABOVE"`/`"BELOW"`/`"BOTH"`) — the manual's 2026-08-26
  re-verification (article id `35523395368985`) found this mode was added
  to the Specifications table/Request Example without a matching JSON
  Schema update. **Live-confirmed on Gen NX**: both a plain
  `{"ACTIVE_MODE": "All"}` and `{"ACTIVE_MODE": "Identity",
  "IDENTITY_TYPE": "STORY", "IDENTITY_LIST": ["1F"], "STORY_ACTIVE":
  "FLOOR"}` (against a document with no story data defined) answered
  `"... command complete"`.
- **`19-20_POST_AnalysisResult_*.md` `post/base.py` `get_table()`**: added
  `average_nodal_result`/`node_flag` kwargs (→ `AVERAGE_NODAL_RESULT`
  boolean, `NODE_FLAG` `{CENTER, NODES}` object). These apply to a named
  subset of ch20's 39 plate/plane-stress-and-strain/axisymmetric tables
  (not universal, and not in the ch19/ch20 common-parameters table) — the
  manual's 2026-08-26 re-verification found both fields missing from every
  affected section's own docs, not previously called out as table-scoped
  at all. Live-confirmed accepted (not rejected) on Gen NX via
  `PLATESTRESSL`: with both fields set, the call still fails on a
  fresh document, but with the same "no analysis result" error as any
  ordinary call to that table type — not a shape-rejection error.
- **`19_POST_AnalysisResult_1.md` `post/result_1.py`
  `TABLE_TYPE_BEAM_STRESS_BY_MAX = "BEAMSTRESSVBM"`**: added — missing
  entirely before (the sibling `TABLE_TYPE_BEAM_FORCE_BY_MAX` already
  existed; this max-value-basis variant of Beam Stress did not). Live-
  confirmed recognized on Gen NX (same "no analysis result yet" signal as
  above, not "unrecognized table type"). Its `ITEM_TO_DISPLAY` filter
  parameter is not exposed by `get_beam_stress_table()` — noted in both
  places, not implemented (no existing kwarg pattern fits a single-table
  extra field cleanly; deferred rather than bolted on).
- **`21_POST_StoryTables.md` `post/story.py`
  `StiffnessCalculationMethod`**: corrected both fields' documented
  default from the first enum value (`"Drift at the Center of Mass"`/`"1 /
  Story Drift Ratio"`) to what the manual's own table (re-checked against
  article id `49513107644057`) actually says: the literal string
  `"System"` — a sentinel meaning "use the document's current calculation
  setting," not one of the listed enum values. Comment-only (TypedDicts
  here are documentation, not runtime-enforced); not live-tested.

**All 24 changed manual chapters are now reflected.** `vendored_at_commit`
bumped to `05eb6c08d1af5d61db517d63eb274f7038c80caa`;
`scripts/check_manual_drift.py --manual-api-repo "E:\AI Study\MIDAS-API"`
now reports `{"has_diff": false, "commit":
"05eb6c08d1af5d61db517d63eb274f7038c80caa"}`. `pytest` (706), `ruff`, and
`mypy` all clean.

## 2026-08-27 (final) — closing the Civil-only gaps this drift work left unverified, now that a working Civil NX key is available

The user provided a fresh Civil NX MAPI key after the above; the
previously-stored one had gone stale (`verify_connection` reported
`status: "disconnected"`, and a plain `GET /db/NODE` 404'd with `client
does not exist"`) even though it decoded to the same session id — the
underlying product just hadn't been reconnected yet. Once reconnected,
went back through every item this drift pass had left as "Civil-only,
session unavailable" and closed as many as the model state allowed:

- **`/db/WVLD`** (misc_loads.py): bisected the manual's full worked
  example down to a bare `{"NAME": "WV1"}` payload — even that minimal
  form still answers the identical `"Wrong Field"` first seen 2026-08-16.
  Confirms the standing failure is unrelated to the `CREST`/`UNIT` value
  correction specifically; the entire write path is blocked (suspected
  licensed offshore/marine module gate, per the existing coverage.json
  note). `CREST`/`UNIT` remain unverified by a live round trip.
- **`/db/NLLP`** (boundary.py `GeneralLinkPropertyPayload`): reconfirmed
  the manual's own unmodified example still answers `"Unknown Error"` on
  Civil NX too (previously only confirmed on Gen) — this is a genuine
  standing cross-product failure, not the "session-specific anomaly" this
  session had speculated for the Gen-only attempt. Docstring corrected.
  The new `DIST_RATIO_DY`/`DIST_RATIO_DZ`/`COUPLED_INPUT_METHOD` fields
  stay schema-confirmed only (`GET /info/db/NLLP`).
- **`/db/NLNK-M1`** (boundary.py `GeneralLinkHyperSPayload`): schema fully
  confirmed via `GET /info/db/NLNK-M1` on Civil NX — exactly the 10 fields
  this SDK now types, confirming `IEHP_NAME` really is absent server-side.
  A live POST attempt (two real nodes, `REF_SYSTEM=0`) answered `"Unknown
  Error"`, almost certainly because `PROP_NAME` had no real `/db/NLLP`
  property to reference (see above) — this endpoint's own write path was
  never actually exercised.
- **`THIS-M1`** (dynamic_loads.py `HyperSAnalysisCase.ANAL_METHOD`):
  schema-confirmed via `GET /info/db/THIS-M1` on Civil NX — the field's
  own description literally reads "Analysis Method (Modal:0, Direct:1,
  Static:2)", independently corroborating the manual's addition of
  `Static=2`. Not round-tripped (needs a full `DAMPING`/`NONL_CTRL_PARAM`
  setup not built this session).
- **`STCT-M1`** (analysis_control.py, three classes): the most fully
  closed of the five. A plain `POST`+`GET` round trip on Civil NX
  confirmed `iBSC`/`FRAME_OUTPUT`/`bSAVE_OCS`/`NONL_CONTROL` are all real
  (server auto-assigned `iBSC: 1`, matching the documented STCT-M1-only
  default, plus a fully-populated `NONL_CONTROL` shape now recorded in
  the docstring for whoever next wants to type it out instead of `Any`).
  `TIME_DEP_CONTROL.CREEP_SHRINKAGE.TYPE="SHRINKAGE"` round-tripped
  explicitly (and a separate creation that omitted `TYPE` defaulted to
  `"BOTH"`, confirming that value too). `iINC_NLA`'s new `3` value and
  `bIEMF` are schema-confirmed only (`GET /info/db/STCT-M1`'s own field
  descriptions list both) — a live `PUT` attempt to set them failed with
  `"Wrong Field"`, but so did a `PUT` using an already-documented
  known-good value pair (`iINC_NLA=1`/`iNLA_TYPE=1`) on the same record,
  so this object is write-once in practice and the rejection isn't
  evidence against the new values specifically.

None of these needed an SDK behavior change — all were either
reconfirmations of already-documented standing failures (WVLD, NLLP) or
upgrades from "manual-sourced only" to "schema-confirmed"/"live-confirmed"
evidence for fields already added (NLNK-M1, THIS-M1, STCT-M1). `pytest`
(706), `ruff`, and `mypy` all clean; Civil NX scratch document confirmed
empty after cleanup.

## 2026-08-27 (final, really) — pushing STCT-M1/THIS-M1/NLNK-M1 past schema-only into real round trips

The user asked to actually try live-verifying the three items the
previous entry left at "schema-confirmed only" rather than settle for
that. Two came all the way through; the third stayed genuinely blocked.

- **`STCT-M1` `iINC_NLA=3`/`bIEMF` — fully closed.** The previous entry's
  "write-once, PUT rejects everything" read was a red herring: the block
  was PUT specifically, not these values. Creating a **fresh record at
  POST time** with `{"iINC_NLA": 3, "iNLA_TYPE": 1}`, and separately
  `{"iINC_NLA": 1, "iNLA_TYPE": 0, "bIEMF": true}`, both round-tripped
  exactly through GET on Civil NX. `docs/coverage.json`'s `/db/STCT-M1`
  entry updated with this evidence (level was already `write` from an
  earlier batch).
- **`THIS-M1` `ANAL_METHOD=2` (Static) — fully closed, and expanded
  further than asked.** No worked JSON example exists for THIS-M1's
  Static case in the manual (only a parameter table) — legacy `/db/THIS`
  has its own Static example under a completely different key convention
  (`COMMON.iAMETHOD`/`iISTEP`/...) that doesn't apply here and would have
  been a trap to copy from directly. Built a fresh payload from the
  §7-2 parameter table instead: `ANAL_TYPE=1`, `ANAL_METHOD=2`,
  `INC_STEP=10`, `INC_CTRL={"INC_METHOD":0,"SF":1}`, deliberately omitting
  `ENDTIME`/`TIME_INC`/`DAMPING` (documented as required by this SDK's
  existing TypedDict, but the manual's own table scopes them to
  Modal/Direct-Integration only). It round-tripped cleanly on Civil NX —
  POST, GET (server auto-filled a complete `NONL_CTRL_PARAM` including a
  nested `BOUNDARY_NL_ANAL` even though neither was sent), DELETE. This
  also surfaced that `GEOM_NL_TYPE`/`INC_STEP`/`SUBSEQ`/`INC_CTRL`/
  `TIME_PARAM` were missing from `TimeHistoryLoadCaseHyperSPayload`
  entirely (not just the `ANAL_METHOD` enum value the manual flagged) —
  added, with a note that `ENDTIME`/`TIME_INC`/`DAMPING`'s "required"
  marking is really conditional on `ANAL_METHOD` and this TypedDict
  doesn't branch on it (a known imprecision, not fixed this pass).
  `docs/coverage.json`'s `/db/THIS-M1` bumped from `read` to `write`.
- **`NLNK-M1` — stayed blocked, confirmed genuinely unblockable today.**
  Bisected `/db/NLLP` down to a single `{"PROPERTY_NAME": "..."}` field
  across four different `(APPLICATION_TYPE, APPLICATION_TYPE_D)`
  combinations — every one answers the identical `"Unknown Error"`,
  regardless of content. `/db/NLLP` writes are unconditionally broken on
  this account/session, not something a cleverer payload works around.
  This also isn't new: the legacy `GeneralLinkPayload`'s (`/db/NLNK`)
  own docstring already recorded on 2026-08-16 that its write test was
  scaffolded but never run for this exact reason. `NLNK-M1`'s docstring
  updated to cite both findings so the next person doesn't re-attempt the
  same dead end.

`pytest` (706), `ruff`, and `mypy` clean; Civil NX scratch document
confirmed empty after cleanup.

## 2026-08-27 (post-mortem) — pre-Jira due diligence: cross-checking the 4 "manual is wrong" findings against MIDASIT's live official pages, plus a dual-product re-test

Before filing anything against MIDASIT, went back to each of the 4 findings
above and fetched the actual live Zendesk article directly (per this
project's own established rule — see the vendor-report boundary note: an
internal vendored-repo citation is not the same as the actual published
text, and 4 of 7 claims in an earlier vendor-report draft turned out to be
citing the vendored copy's own transcription errors, not MIDASIT's real
pages). Used `https://support.midasuser.com/api/v2/help_center/en-us/
articles/<id>.json` (the HTML page 403s WebFetch); found article ids via
the sibling manual repo's own citations where present, and via
`.../help_center/articles/search.json?query=...&locale=en-us` where not.
Then re-ran every live test on **both** Gen NX and Civil NX (not just
whichever product happened to be handy when each was first found).

All 4 survive intact — official docs corroborate every one, sometimes
adding a plausible explanation for how the sibling manual repo's
re-verification went wrong:

1. **Story Load Summary Table** (`TABLE_TYPE`). Official article id
   `49514148775705` ("Story Load Summary", GEN NX), `updated_at`
   2026-08-05 — its own worked JSON example literally sends
   `"TABLE_TYPE": "STORY_LOAD_SUMMARY_X"`. Re-tested live just now: Gen NX
   still answers `"there was an error creating utbl"` (unrecognized) for
   that exact literal, and still accepts the undocumented
   `"STORY_LOAD_X"` cleanly. Civil NX rejects both identically (this
   table type is Gen-only, already established — not informative either
   way there). **This is now the most interesting of the 4**: it's not
   that the sibling manual repo mis-transcribed anything — they quoted
   MIDASIT's real page accurately — it's that MIDASIT's own published
   example doesn't match their own live server. Worth flagging to
   MIDASIT as exactly that (a docs/API mismatch on their end), not as a
   transcription error.
2. **`/db/REBW`'s `vSTORY_NAME`**. Official article id `49514033006745`
   ("Modify Wall Rebar Data") turned out to describe a *third*, older
   schema entirely (`VERTICAL_REBAR`/`HORIZONTAL_REBAR`/`CREATE_SUB_WALL_ID`/
   `STORY:{FROM,TO}`) — neither this SDK's `vSTORY_NAME` nor the sibling
   repo's claimed `vSTORY_KEY` appear anywhere in it, so that article is
   itself stale relative to both. The decisive check was a fresh
   `GET /info/db/REBW` on Gen NX just now: the live schema names the field
   `vSTORY_NAME` (array of strings) — matching this SDK exactly — but
   its own `description` reads **"Story Key List"**, which is almost
   certainly why the sibling repo's re-verification concluded the field
   itself must be named `vSTORY_KEY`. Civil NX 404s on this endpoint
   entirely, already documented as Gen-only (`GEN_ONLY`, confirmed twice
   2026-07-29) — expected, not a new data point.
3. **`/db/LCOM-*`'s `NO` field**. Official article id `35990806887065`
   ("Load Combinations - General", CIVIL NX+API) documents `NO` in all
   three places the sibling repo's re-verification claimed it was absent
   from: the JSON Schema (`"NO": {"description": "CombinationNumber"}`),
   the Specifications table (`Combination Number | "NO" | Integer | - |
   Read Only`), and both request/response examples. Re-tested live just
   now on **both** products (the original test was Gen-only): a fresh
   `POST /db/LCOM-GEN` that never sends `NO` gets it back on `GET` as
   `"NO": 1` on Gen NX *and* Civil NX identically.
4. **`/ope/MEMB`'s `ELEM_LIST`**. Official article id `49514964272665`
   ("Member Assignment", GEN NX) — Specifications table lists
   `"ELEM_LIST"` ("Element List", Required), and the *request* example
   sends `"ELEM_LIST": [640, 692]`; only the *response* example uses
   `"AELEM"`. This confirms exactly the mix-up already suspected: the
   sibling repo's re-verification cited the response's `AELEM` key as if
   it were the request field. Re-tested live just now on **both**
   products: `ELEM_LIST` succeeds (assigns the member) and `AELEM` is
   rejected as "no valid element information" on Gen NX *and* Civil NX
   identically.

   **Re-verified 2026-09-06** after the sibling manual repo asked for a
   re-check, claiming the article's request example carries
   `"AELEM": [1, 2]` and that `[640, 692]` was our own example value.
   Re-fetched the same article (`updated_at` 2026-07-30T05:16:25Z, the same
   revision as 8/27) and the claim does not hold: the Input JSON example
   sends `"ELEM_LIST": [640, 692]`, the Output example returns
   `"AELEM": [640, 692]`, and the Specifications table row 3 is
   `"ELEM_LIST"` / Array / `Required(*)`. Whole-body counts: `ELEM_LIST` 2
   (example + table), `AELEM` 1 (response only). **The table and the request
   example agree**; only the response differs, which the article states
   plainly. `AELEM` belongs to the neighbouring `/db/MEMB` (Design Member
   Assignment, ch24), an `"Assign"`-wrapped id-keyed record - an easy pair
   to confuse, and both are implemented here with their own key.

   Two things this re-check did produce, and both are on us:

   - **The official Specifications table row 2 spells the key
     `"SELETION_TYPE"`**, missing a C, while both request examples and the
     live server use `SELECTION_TYPE`. Our vendored copy normalised it, so
     nobody had seen it. Recorded as MD-51.
   - **The 2026-08-27 test's own record is thinner than it reads.** The
     `AELEM` rejection's HTTP status and full response body were never
     written down - only the message string - the two-keys-at-once case was
     never tried, and no build was recorded for that session;
     `docs/coverage.json`'s `/ope/MEMB` entry still describes only the
     2026-07-30 `ASSIGN_TYPE=AUTO`/`SELECTION_TYPE=ALL` probe and is still
     `level: read`. There is no case for it in `live_crud_check.py` either,
     so it cannot be re-run mechanically. Answering the rest takes a new
     live session. Reply drafted in `docs/ope_memb_elem_list_response.md` (git history, `fa1332b`).

No SDK or docs changes needed — all 4 already match the SDK's current
code; this pass only strengthens the evidence trail before any of them
go to Jira. Test fixtures (nodes/elements/STLD/LCOM-GEN records) created
on both products during this pass were all cleaned up. `pytest` (706),
`ruff`, `mypy` unaffected (no source changed this entry).

## 2026-08-27 (yet again) — the sibling manual repo reverted its own REBB/REBC/REBW re-verification, and got 2 of 3 wrong

While the above was in progress, the user reported the manual repo had
been updated again: commit `af21cd7` ("24장 REBB/REBC/REBW 오정정 되돌림")
reverts its own 8/26 re-verification for all three endpoints, saying
that pass had confused them with a different endpoint's schema and
introduced fictional fields (`vMAIN_BAR`/`vSTORY_KEY`/integer `HOOP_TYPE`
etc.). Checked each of the three independently — live schema pulls, and
for REBC a live POST comparison — rather than trusting the revert at
face value, same as every other manual claim this session:

- **`/db/REBC` — the revert is right that 8/26 was wrong, but the
  revert's own replacement is *also* wrong.** Fetched the official
  Zendesk article directly (id `49513980544793`, "Modify Column Rebar
  Data") — it documents a single-object `MAIN_BAR` (`NAME`/`NUM`/`ROW`/
  `USE_CORNER`), `DO`, and `Active Methods: POST` only, matching exactly
  what the revert restored. Live-tested both shapes on Gen NX: the
  official/reverted single-object shape answers `"Wrong Field"`
  (rejected outright); this SDK's existing array-based `vMAIN_BAR` shape
  answers `"Column Rebars has been entered in the section no. 1, which
  has not been specified"` — a domain error, meaning the shape itself
  was accepted. A fresh `GET /info/db/REBC` independently confirms the
  array shape field-for-field, plus one field this SDK didn't have yet:
  `HOOK_TYPE` (added). `GET /db/REBC` also answers cleanly, contradicting
  "POST only." **The official MIDASIT article is wrong for this
  endpoint**, not just the vendored copy — this is now the second
  confirmed case of that this session (the first was Story Load Summary
  Table, a docs/example mismatch rather than a wrong field name).
- **`/db/REBW` — unaffected.** Re-pulled the complete `GET /info/db/REBW`
  schema (every field, not just the previously-checked `vSTORY_NAME`) —
  matches this SDK exactly. Nothing to change.
- **`/db/REBB` — the revert is wrong, and so is the SDK, in different
  ways.** The revert restored a `{LAYER1, LAYER2}` object shape for
  `MAIN_BAR_TOP`/`MAIN_BAR_BOT` (matching the official article). A fresh
  `GET /info/db/REBB` schema pull shows neither that nor exactly what
  this SDK had: the live server uses an **array** of `{NAME, NUM}` items
  (no `LAYER1`/`LAYER2`, but also no `LAYER` field like this SDK's own
  `BeamMainBarLayerEntry` had inferred) — array position encodes the
  layer instead. The schema also shows no `CREATE_SUB_SECTION`/`ELEMS`
  at all, which this SDK had carried over from the REBC/REBR pattern
  without independent confirmation for REBB specifically. Removed
  `LAYER`/`CREATE_SUB_SECTION`/`ELEMS` from `BeamMainBarLayerEntry`/
  `BeamRebarItem`. **Not round-tripped with a real POST**: every attempt
  this session (with or without these fields) failed with a generic
  `"Wrong Field"` before reaching a usable target section — inconclusive
  on its own, so this fix rests on the schema pull alone, not a write
  confirmation. Interesting side note: this SDK's 2026-07-29 rewrite of
  the neighboring `WallRebarItem` docstring says REBB was checked that
  same session and "uses the manual's long-form names correctly" — that
  was before 8/26 ever touched REBB, and refers to whatever the manual
  said at the time, not necessarily this array shape; not re-derivable
  now without the 2026-07-29 session's own notes.

Net effect: of the 3 endpoints the manual repo just reverted, 1 revert
was fully correct (REBW, moot — already fine), 1 revert corrected a real
problem but replaced it with a still-wrong shape whose real source is
now identified as a bug in MIDASIT's own official docs (REBC), and 1
revert introduced a new problem where none existed (REBB, un-reverted
here based on fresh schema evidence). `pytest` (706), `ruff`, `mypy` all
clean.

## 2026-08-27 (yet again, later) — REBB: pushed for a real write round trip, concluded the write path itself is broken

The user asked to actually live-verify REBB rather than settle for
schema evidence. Built a full real target from scratch on Gen NX
specifically for this (the earlier attempts this session had no real
section/element to write against): a concrete `MATL` (C24), a `SECT`
(`SHAPE: "SB"`, the confirmed-working fixture pattern from
`scripts/live_crud_check.py`, not the shapes that had been failing all
session), a `BEAM` element using it, and a `DCON` design code — then
retried `POST /db/REBB` many different ways:

- This SDK's existing array-based shape (`vMAIN_BAR_TOP`/`BOT`, flat
  `SKIN_BAR_NAME`/`NUM`, `MAIN_BAR_DC_TOP`/`BOT`) — `"Wrong Field"`.
- Fetched the official Zendesk article's raw HTML directly and found it
  embeds a full JSON Schema block distinct from its own rendered
  Specifications table — using `LAYER1`/`LAYER2` objects, `DT`/`DB` cover
  names, and `"additionalProperties": false`. Tried that exact shape —
  `"Wrong Field"`.
- Mixed variants (`DT`/`DB` with the array shape, `DT`/`DB` with
  `LAYER1`/`LAYER2`) — `"Wrong Field"`.
- A **literally empty item** (`{"ITEMS": [{}]}`) against the real
  section — `"Wrong Field"`, identically.

The empty-item result is the deciding one: if an empty object fails the
same way as a fully-specified one, the failure can't be about which
field names or nesting are used. Ruled out the last remaining
non-content explanations too — `verify_connection()` shows a clean
`connected` status (not a blocked-modal false positive) and an unrelated
sanity `GET /db/NODE` succeeds normally in the same session, so the
client/session itself is fine. **Conclusion: `/db/REBB`'s write path is
broken on this account/session regardless of payload, the same class of
finding as `/db/NLLP` and `/db/WVLD`** (both already documented
elsewhere in this SDK as standing failures) — not a shape question this
pass can resolve by trying yet another field-name permutation.

One more thing worth keeping: **the official article's own JSON Schema
block contradicts its own Request/Response Example**, in the same
document. This SDK follows the example (which also matches the
independent `GET /info/db/REBB` schema pull from earlier this session) —
the closest thing to a tiebreaker available — but with the write path
itself down, this can't be confirmed with an actual round trip. All test
fixtures (MATL/SECT/ELEM/NODE/DCON) cleaned up after. `pytest` (706),
`ruff`, `mypy` all clean; no source changed this entry beyond the
coverage.json/docstring notes already made.

## 2026-08-30 — two documented method sets measured, both wrong (Civil NX 2026 v2.2)

Live, against an empty Civil NX document (0 nodes/elements/materials/sections,
checked first). Every write was captured and restored or deleted; nothing was
left behind.

Both findings came out of the same question — what does a documented method
actually do — and they fail in opposite directions.

### The two response shapes

The server distinguishes "this method is not served here" from "this method ran
and rejected your data", and it does not use HTTP status to do it:

| response | meaning |
| --- | --- |
| `{"message": "error status"}` | the method is not served on that endpoint |
| `{"error": {...}}` | the method ran; the payload or the model was wrong |
| the table, echoed back | it worked |

The control that establishes this: `POST /db/NODE` then `DELETE /db/NODE/1`
returns `{"NODE": {"1": {...}}}` — a served DELETE **echoes the record it
removed** — and the following GET answers `{"message": ""}`. So `error status`
is a refusal, not an empty result, and neither is an `{"error": ...}` body.
Note also that `{"message": "error status"}` carries no `error` key, so
`MidasResultError` does not fire on it: another case for the "not every failure
carries an `error` key" rule.

### `/db/STYP-M1` does not serve DELETE, though the article says it does

The official article (`56375311138201`) tags `GET, PUT, DELETE` in its own
`activeMethods` field — read from the source HTML, not inferred — and
`02_DB_Project_Structure.md` transcribes that faithfully.

All three DELETE shapes answer `{"message": "error status"}` and change
nothing:

```
DELETE /db/STYP-M1/1                    -> {"message": "error status"}
DELETE /db/STYP-M1 {"Assign": {"1": {}}} -> {"message": "error status"}
DELETE /db/STYP-M1  (no body)            -> {"message": "error status"}
```

`POST /db/STYP-M1` answers the same. The classic `/db/STYP`, which the manual
documents as GET/PUT-only, answers identically to all of them — so the two
endpoints behave the same way, and the chapter's general rule ("신규 파일 필수
데이터는 GET / PUT만 동작") holds for the Hyper-S variant too. The article is
the thing that is wrong.

Repeated later the same session with the dummy frame in place (3 nodes, 2
beams, a material, a section, a support and a load case) and with the record
first set to a deliberately non-default state — `STYPE: "XZ"`, `GRAV: 9.81`,
`TEMP: 15`, both align flags true, `MASS_TYPE: "CONSISTENT"`. A DELETE that
reset the record to defaults would have been visible against that; all three
shapes again answered `error status` and left every field untouched. So the
question the manual section leaves open — whether DELETE resets to defaults or
empties the record — has a third answer: it does neither, because it does
nothing. An empty document was not what made the first result come out that
way.

`StructureTypeHyperS` keeps `_GET_PUT_ONLY`. It was already right; it had been
right by analogy rather than measurement, which is why this was worth checking.

`GET /info/db/STYP-M1` also confirms `MASS_CONTROL` is a nested object with
`MASS_TYPE`, `MASS_POS`, `SELFWEIGHT`, `MASS_AXIS` inside it — independent
confirmation that the extractor's `2-(N)` flattening is a defect, not a
reading of the payload. And `GET /db/STYP-M1` returns a record with no
`MASS_AXIS` at all while `SELFWEIGHT` is `false`, which is the documented
condition behaving as documented.

### `/db/POLC-M1` does serve POST, though the chapter says it does not

The reverse case, and the more expensive one. `14_DB_Pushover.md` normalizes
this endpoint to GET/PUT/DELETE and warns in a `⚠️` callout that the official
article's `POST, GET, PUT, DELETE` row is an untrimmed copy of another
endpoint's template. Earlier the same day this SDK trimmed POST out of the
contract, Python and npm on the strength of that callout.

POST works:

```
POST /db/POLC-M1 {"Assign": {"1": {…LCNAME PROBE_POST…}}}
  -> {"POLC-M1": {"1": {"LCNAME": "PROBE_POST", …}}}
GET  /db/POLC-M1
  -> {"POLC-M1": {"1": {"LCNAME": "PROBE_POST", …}}}
```

Two earlier attempts had failed — first `{"error": {"message": "INCFUNC_NAME
not found."}}`, then `Load Case does not exist` — **identically under POST and
PUT**. Those were the empty model missing the objects the payload referenced,
not the method being absent; seeding `/db/STLD` with a `DEAD` load case was
enough to make the same POST succeed. A failure that reproduces identically
under a method the manual accepts is evidence about the model, not the route.

`PushoverLoadCaseHyperS` gets its full method set back, and the contract
records the disagreement under `manualDefects` with `describes: method` rather
than silently matching the manual.

### `/db/STYP-M1` is the classic `/db/STYP`, not a separate record

Measured the same session, on a 3-node 2-beam frame with a material, a section,
a fixed base and a self-weight case — an empty document cannot show any of
this, which is why the dummy model was built.

Writing either endpoint changes the other. `PUT /db/STYP-M1` with
`STYPE: "XZ", TEMP: 11` makes the classic read `STYP: 1, TEMP: 11`; `PUT
/db/STYP` with `TEMP: 22` makes the Hyper-S one read `TEMP: 22`. They are two
spellings of one model setting, which is also why neither serves POST or
DELETE: the document cannot exist without exactly one of these records.

| `/db/STYP-M1` | classic `/db/STYP` |
| --- | --- |
| `STYPE`: `3D` / `XZ` / `YZ` / `XY` / `RZ` | `STYP`: `0` / `1` / `2` / `3` / `4` |
| `MASS_CONTROL.MASS_TYPE`: `LUMPED` / `CONSISTENT` | `MASS`: `1` / `2` |
| `MASS_CONTROL.MASS_POS`: `CENTROID` / `OFFSET` | `bMASSOFFSET`: `true` / `false` |
| `MASS_CONTROL.MASS_AXIS`: `XYZ` / `XY` / `Z` | `SMASS`: `1` / `2` / `3` |
| `MASS_CONTROL.SELFWEIGHT` | `bSELFWEIGHT` |
| `GRAV`, `TEMP`, `ALIGNBEAM`, `ALIGNSLAB` | same, `b`-prefixed for the booleans |

`MASS_POS` maps the way round that reads backwards: `CENTROID` is
`bMASSOFFSET: true`. Do not "correct" it. When `MASS_TYPE` is `CONSISTENT`,
`bMASSOFFSET` is absent from the classic response entirely; when `SELFWEIGHT`
is false, so is `SMASS`.

### `STYPE` selects the model's active degrees of freedom

Same model, same supports, self-weight in −Z, one analysis per structure type.
Node 3 displacement:

| `STYPE` | DX | DY | DZ | RX | RY |
| --- | --- | --- | --- | --- | --- |
| `3D` | 0.015020 | 0.006429 | −0.021727 | −0.002223 | 0.005007 |
| `XZ` | 0.015020 | **0** | −0.017444 | **0** | 0.005007 |
| `YZ` | **0** | 0.006429 | −0.009211 | −0.002223 | **0** |
| `XY` | **0** | **0** | **0** | **0** | **0** |
| `RZ` | as `3D` | | | | |

`XZ` keeps DX/DZ/RY, `YZ` keeps DY/DZ/RX, and `XY` produces nothing at all here
because the load is along the one axis that plane has no freedom in. `DZ`
differs between `3D` and `XZ` (−0.021727 vs −0.017444) because the out-of-plane
contribution is gone, not merely hidden. So a structure type is not a display
setting: it changes the answer.

A caution learned the hard way in the same session: an earlier run of this
comparison had no supports at all, because `/db/CONS` was sent a 6-character
`CONSTRAINT` where it wants 7 (`[DX,DY,DZ,RX,RY,RZ,RW]`) and the failure was
not checked. That model still answered `{"message": "MIDAS CIVIL NX command
complete"}` for four of the five types and produced a plausible-looking
difference. Verify the fixture with a GET before reading anything into a
result.

### Conditional rules on `MASS_CONTROL`, as enforced

| sent | result |
| --- | --- |
| `MASS_TYPE: LUMPED` with no `MASS_POS` | rejected, `Wrong Field` — genuinely required |
| `MASS_TYPE: CONSISTENT`, `SELFWEIGHT: true`, `MASS_AXIS: XY` | rejected, `MASS_AXIS is XYZ if MASS_TYPE is CONSISTENT` |
| `MASS_TYPE: CONSISTENT` with `MASS_POS` sent | **accepted, and `MASS_POS` silently dropped** |
| `STYPE: "_3D"` | rejected, `Wrong Field` |
| `STYPE: "3D"` | accepted |

Two of these settle open questions. The manual documents `MASS_POS` under
`CONSISTENT` as 불가 — the server does not refuse it, it discards it, so a
caller who sends it gets no signal that it was ignored. And the chapter's `⚠️`
choosing `"3D"` over the article's `"_3D"` enum is correct: `_3D` is rejected.

### Gen NX: the same dummy frame, and where the two products differ

Everything above was Civil. Repeated on Gen NX with the same model built the
same way — 3 nodes, 2 beams, one material, one section, a fixed base and a
self-weight case — with each piece asserted by a `GET` before anything was read
out of it.

**Hyper-S is still Civil-only on this build.** `/db/STYP-M1`, `/db/POLC-M1`,
`/db/MATL-M1`, `/db/EIGV-M1` and `/db/ACTL-M1` all answer **404** on Gen, and so
do their `/info` routes. `HYPER_S_ONLY` matches reality as of 2026-08-30; that
constant is still the right place to widen if Hyper-S ever reaches Gen.

**The two products agree exactly.** Same model, same supports, same
self-weight, node 3 displacement per structure type — Gen's numbers are
identical to Civil's to the last digit, including which components are zeroed:

| `STYP` | DX | DY | DZ | RX | RY |
| --- | --- | --- | --- | --- | --- |
| `0` (3D) | 0.015020 | 0.006429 | −0.021727 | −0.002223 | 0.005007 |
| `1` (XZ) | 0.015020 | 0 | −0.017444 | 0 | 0.005007 |
| `2` (YZ) | 0 | 0.006429 | −0.009211 | −0.002223 | 0 |
| `3` (XY) | 0 | 0 | 0 | 0 | 0 |
| `4` (RZ) | as 3D | | | | |

So the degrees-of-freedom finding is a property of the setting, not of Civil.
`DELETE /db/STYP` is refused on Gen too — all three shapes, with the model
present and from a non-default state, `{"message": "error status"}`, nothing
changed.

**`bROTRIGID` is in both schemas and only one product's responses.**

```
gen    GET /db/STYP : {..., "bMASSOFFSET": true, "bROTRIGID": false, "bSELFWEIGHT": false}
civil  GET /db/STYP : {..., "bMASSOFFSET": true, "bSELFWEIGHT": false}
```

`GET /info/db/STYP` returns the *same ten keys on both products*, `bROTRIGID`
among them. Civil accepts a `PUT` carrying it — no error either way — and then
never echoes it back, whether it was sent `true` or `false`. Gen always reports
it.

That is a response-shape difference the schema does not predict, on an endpoint
neither the manual nor `/info` distinguishes by product. Code written against
Gen that reads `STYP["bROTRIGID"]` raises `KeyError` on Civil. Read it with a
default, and do not add it to a payload-shape check that runs against both.

`StructureTypePayload` documents `bROTRIGID` without qualification, which is
right for the request; the difference is in what comes back.

### What this says about normalization

The manual repo's `⚠️` callouts exist because the official docs contradict
themselves, and following them is normally right — that rule is in CLAUDE.md
and it stays. But a normalization is a judgement about a product, and this one
was reasoned from consistency with sibling endpoints rather than measured. It
was wrong, and it was wrong in the direction that removes a capability users
have.

Both of these were caught by asking the server. Neither would have been caught
by any amount of re-reading, because both surfaces agreed with the document
they were derived from.

### `/db/MVCTch` exposes the documented `BRIDGE2` branch on both products (2026-08-30)

Read-only `GET /info/db/MVCTch` against the supplied Civil NX and Gen NX
sessions returned `BRIDGE2` under `Argument.properties` on both products.
The official manual's China moving-load-control section documents it as the
object required when `iCODETYPE` is 2 or 3 (TB 10002-2017 / Q·CR
9300-2018). The Python and generated TypeScript payload surfaces had omitted
the field; it is retained as an untyped object because its `BTYPE` branches
have different members. No model data was read or changed by this check.

### `/db/MVLD` exposes Australia's documented `ASL` branch on both products (2026-08-30)

Read-only `GET /info/db/MVLD` against the same Civil NX and Gen NX sessions
returned the identical `ASL` object: `MULTIPLE_FACTOR`, both vehicle-name
members, the loaded-lane bounds, and `LINE_ITEMS`. Its nested properties were
exactly `NA_LLAN_NAMES`, `STRAD_LLAN1_NAMES`, and `STRAD_LLAN2_NAMES`, matching
the manual's Australia Heavy Load Platform table. The SDK had omitted this
top-level branch; it is now structured on both Python and generated TypeScript
surfaces. No model data was read or changed by this check.

### `/db/MVLDch` Python payload now matches its contract branch (2026-08-30)

Civil and Gen `/info/db/MVLDch` both expose the five members of the
`OPT_AUTO_OPTIMIZE=true` branch: `MIN_VEHICLE_DIST`, `LOADED_LANE_NAME`, the
two vehicle-count bounds, and `AUTO_OPTIMIZE_ITEMS`. The promoted contract and
generated TypeScript discriminated union already contained that manual-defined
branch, but Python had only the false/general-load branch. The Python payload
now carries the same documented conditional fields. No model data was read or
changed by this check.

### `/db/STCT` exposes documented Grid Model fields on both products (2026-08-30)

Civil and Gen `/info/db/STCT` both include `bSDLE` and `vSDLE`, the Grid Model
secondary-dead-load option and its load-case list. They are documented in the
Erection Load table but had been omitted from the Python and generated
TypeScript payload surfaces. Both now match the server's top-level schema. No
model data was read or changed by this check.

### The npm package's first live session (2026-08-31)

Until this date the npm package had never spoken to a MIDAS NX server. All
three live harnesses — `live_crud_check.py`, `live_readonly_sweep.py`,
`live_smoke.py` — are Python, and every npm test mocks `fetch`. Its HTTP layer,
its error mapping and its `/post/TABLE` adapter are hand-written, and a mock
agrees with whatever the author assumed.

`midas-nx@2.7.1` was installed from the public npm registry into an empty
project and run against both supplied sessions, read-only. Six checks per
product, ten passing:

| check | gen | civil |
| --- | --- | --- |
| `verifyConnection()` | `status: connected` | `status: connected` |
| `resources.db.nodeElement.node.get()` | `{"message": ""}` | `{"message": ""}` |
| `.info()` | 3 properties | 3 properties |
| `client.request("GET", "/db/STYP")` | full record | full record |
| 404 route -> `MidasNotFoundError` | `/info/db/WVLD` | `/info/db/SDIS` |
| `/post/TABLE` `NODE` (POST-shaped read) | `MidasResultError` | `MidasResultError` |

The last row is the interesting one and it is **not** a defect. Both models are
empty, so the server answers **HTTP 200 with an error body** — `there was an
error creating utbl.` The npm client detected the error inside a 200 and raised
`MidasResultError`, which is the documented hazard this project exists to
handle. The identical call from the Python SDK on the same two sessions
produced the identical exception with the identical message, so the two
surfaces agree against a real server, not merely against each other.

**What this does not establish.** No npm write has ever reached a live product:
`POST`/`PUT`/`DELETE`, and with them the `/db/NMAS` `rmX`/`rmY`/`rmZ`
`payloadDefaults` rule, remain verified by test only on the npm side. And
`unwrapTable()` was reached but never given a populated table, because the
empty model errored first — the unstable-top-level-key behaviour it exists for
is still unobserved from JavaScript.

Reproduction at the time: install `midas-nx` from the registry, call the six
checks above. No repository harness existed yet; the next entry records the
subsequent write-capable harness.

### npm public-API write and populated-table verification (2026-08-31)

The repository now has that reproducible harness at
`packages/typescript/scripts/live-crud.mjs`. It imports the built npm package
entry point (`dist/index.js`) and uses only its public `resources.db.*` and
`post.*` APIs; it does not issue raw HTTP requests or import Python. Its
payloads are read from the checked-in, language-neutral
`schema/live-cases.json` fixture emitted by `scripts/live_crud_check.py`.

On the confirmed-empty Gen NX 2026 v2.1 and Civil NX 2026 v2.2 sessions
(both build 08/26/2026), the following npm-package round trips passed on both
products:

| npm public API | check | gen | civil |
| --- | --- | --- | --- |
| `resources.db.nodeElement.node` | create, read, update, read, per-id delete, final read | pass | pass |
| `resources.db.staticLoads.nodalMass` | same CRUD cycle, with its fixture omitting `rmX`/`rmY`/`rmZ` | pass | pass |
| `resources.db.project.loadGroup` | create, read, update, read, per-id delete, final read | pass | pass |
| `resources.db.analysisControl.settlementAnalysisControlData` | same CRUD cycle for independent Boolean control data | pass | pass |
| `post.getTable("MASS_SUMMARY_X")` + `post.unwrapTable()` | seed a fixture Node and Nodal Mass, then read a populated table | pass | pass |

For Nodal Mass, the record read back after both `POST` and `PUT` contained
the generated resource's `payloadDefaults` (`rmX`, `rmY`, and `rmZ`, each
`0.0`). This is live evidence that the npm public DB resource supplies the
three omission-sensitive values before sending the request, rather than only
declaring them in metadata.

The populated `MASS_SUMMARY_X` responses had a top-level key of **`empty`**
on both products while carrying a two-row `HEAD`/`DATA` table. `unwrapTable()`
found that table by shape, as intended; treating the `empty` key as “no data”
would have discarded real result rows. The table seed used its own Node/Nodal
Mass id and both were removed with individual-id DELETE calls. Final public
`items()` reads for `/db/NODE` and `/db/NMAS` returned `{}` on both products.

This is explicitly npm-specific live evidence. `docs/coverage.json` remains
unchanged: its historical `level` field means verification through the Python
package, so an npm run must not silently widen that meaning.

One runner limitation was also made explicit rather than misreported as an
SDK regression. `/db/STLD` ignores the requested `Assign` id on a blank model
and creates the next sequential id; its Python case intentionally runs after
the base model has already allocated ids 1–2. The small npm batch does not
recreate that base model, so it rejects that case as not equivalent instead of
claiming it is npm evidence. The npm harness now tracks every id newly created
by a selected case and deletes those ids individually even when a server has
renumbered the requested record. A Gen NX probe confirmed the failing STLD
case left its server-assigned id cleaned up (`{}` afterward). No coverage level
was changed for STLD.

## Caveat — read before acting on this file

### `/db/MVLDpl` exposes all documented conditional objects on both products (2026-08-30)

Civil and Gen `GET /info/db/MVLDpl` return the same three conditional payload
objects: `DEFAULT`, `AUTO_OPTIMIZE`, and `PERMIT_LOAD`. The latter two had been
documented in the Poland moving-load table but were absent from the Python and
generated TypeScript surfaces. Their nested members also match the manual's
Vehicle S/2S, Vehicle K/Military, and permit-vehicle rows. No model data was
read or changed by this check.

### `/db/IEHC` distinguishes Civil beam fields from Gen wall fields (2026-08-30)

Both products return the eight documented beam fields, including
`BeamDivNumNyCover` and `BeamDivNumNzCover`; the earlier Python surface had
instead exposed obsolete `CoverDivNum*` names. Gen additionally returns the
nine Wall members documented as GEN-only, while Civil correctly omits them.
The live drift checker now reads the corresponding contract product gates, so
that documented product variation is not reported as a false discrepancy. No
model data was read or changed by this check.

### `/db/MATL-M1` round-trips all three documented live `P_TYPE` branches (2026-08-31)

On a fresh Civil NX scratch model, Standard (`P_TYPE=0`), Isotropic (`1`), and
Orthotropic (`2`) Hyper-S materials each passed `POST -> GET -> PUT -> GET ->
DELETE /db/MATL-M1/{id} -> GET`. The returned Standard branch includes `CODE`,
`DB`, `USER_DEFINED`, and `THERMAL_TRANS`; the two user-defined branches return
the nested `USER_DEFINED` and `THERMAL_TRANS` objects. This confirms the
0-based `P_TYPE` branches and their nested shape through writes, not merely
`/info` introspection.

The product rejected all three first attempts solely because the material names
exceeded its 16-character limit. Shorter names then passed unchanged. The
manual's Hyper-S section has no field-level Specifications table and does not
state that limit. The scratch model was reset with `/doc/NEW` after individual
per-id deletion checks completed.

### `/db/MATL-M1` is not `/db/MATL` plus Hyper-S additions (2026-08-31)

The manual's `04_DB_Properties.md` statement that the Hyper-S endpoint has the
same base material structure as `/db/MATL`, with additional Hyperelastic
support, is contradicted by Civil NX `/info` output:

```text
/db/MATL     NAME, TYPE, PARAM, DAMP_RAT, HE_COND, HE_SPEC, PLMT, P_NAME, bMASS_DENS
/db/MATL-M1  MATL_NAME, MATL_TYPE, PARAM, DAMP_RAT
```

The endpoint has different name/type wire keys and fewer top-level members;
`HE_COND` and `HE_SPEC` are on `/db/MATL`, not `/db/MATL-M1`. The two material
families also use different `PARAM[].P_TYPE` numbering and nesting, as the
write round trips above confirm. A parent-field delegation would therefore be
a wrong contract, not a useful fallback. This is a manual-structure defect to
report upstream, not an SDK source for contract transcription.

### `/db/IEHC` `WAreaSize` is a live string, not the table's integer (2026-08-30)

Gen NX `/info/db/IEHC` types only `WAreaSize` as `string`; the sibling
`WAreaSizeCover` is `integer`. The chapter's Specifications table calls
`WAreaSize` Integer, while its own Request Example sends `"WAreaSize": "AUTO"`.
The promoted contract deliberately retains the manual's Integer declaration
and records this conflict separately under `manualDefects` plus the Gen
verification record. It is not silently retyped from one live observation.

### SDST, SDIS, MVCTch and WVLD re-check on fresh scratch models (2026-08-31)

- **`/db/SDST`**: the current official BL2 payload passed `POST -> GET -> PUT
  -> GET -> DELETE /db/SDST/{id} -> GET` on both Civil NX and Gen NX. The
  stored `BL2.BETA` and updated `P1` values were read back. This replaces the
  old `Wrong Field` result, which predated the manual's SDST/SDVE correction.
- **`/db/SDIS`**: Civil again returned 404 for `/info/db/SDIS`. On Gen, the
  corrected `SDIS_DEV_TYPE="SLD"` plus `SB` payload passed the same complete
  round trip, including an updated `KV`. The official `NRB` example subsequently
  passed the same complete round trip and returned its updated `KV`; its record
  was removed individually and a final GET returned an empty table. LRB still
  returns `Wrong Field` with the official corrected `K0`/nested-`DX` shape,
  even though Gen `/info` exposes that shape. This leaves the LRB
  model-literal/precondition unresolved rather than treating it as a field-shape
  defect.
- **`/db/MVCTch`**: Civil and Gen both passed the full round trip for the
  `iCODETYPE=0` / `FREQ` branch. `FREQ.USER_F=0` fails explicitly with
  `f > 0`; `USER_F=3.0` passes. The manual's request example omits `iSLCM`
  and `iBC` even though its table calls them required. Both values can be sent
  as zero, but the server normalizes `iSLCM` out of the GET response.
- **`/db/WVLD`**: Gen remains a route and `/info` 404. Civil still returns
  `Wrong Field` for the full official example, including the live-schema
  `DRAG_COEF_X/Y/Z` and `INER_COEF_X/Y/Z` keys. It had also rejected a bare
  `NAME` payload in the earlier probe. The live evidence therefore points to
  an undocumented product precondition or module gate, not the documented
  payload spelling. Every test record was targeted by its individual-id
  delete; the scratch models contain no test records from this pass.

### `/db/NLLP` fresh-model re-check (2026-08-31)

On both empty current-build scratch documents, the manual's exact
`APPLICATION_TYPE="ELEMENT"` / `APPLICATION_TYPE_D="SPG"` request example
again returned HTTP 201 with the error body `Unknown Error`. This is the same
result as the seeded and fresh-document attempts recorded on 2026-08-16 and
the Civil re-check on 2026-08-27. The record never materialized; individual-id
cleanup and a final GET confirmed each NLLP table remained empty. The finding
therefore remains an undocumented product precondition or module gate, not an
SDK or documented-field-shape conclusion.

This is evidence from **one MIDASIT account, one product license/edition,
one point in time**, not from the manual. It is plausible some of the
20 + 7 "product-only" endpoints above are actually gated by license tier,
Civil/Gen build version, or model state rather than being permanently
unavailable for that product. **Do not change any `PRODUCTS` frozenset in
the SDK based solely on this file.** If the same restriction is
independently reproduced (different account, different session, or a
future manual revision adds an explicit product note), that's the trigger
to revisit `PRODUCTS` for the specific classes involved — cite this file's
date and findings in that future change, and re-verify before trusting it,
since MIDASIT's platform can change between now and then.

### npm public-API Gen re-check: Node and Skew (2026-08-31)

Before mutation, direct public GETs on the supplied Gen NX 2026 v2.1 build
08/26/2026 session returned the documented empty-model shape for both
`/db/NODE` and `/db/ELEM`. The built `midas-nx@2.7.3` package was then run
through `packages/typescript/scripts/live-crud.mjs`, using only the shared
`schema/live-cases.json` fixture and an author-approved `C:/temp` checkpoint:

| npm public API | result |
| --- | --- |
| `resources.db.nodeElement.node` | `POST -> GET -> PUT -> GET -> DELETE {id} -> GET` passed |
| `resources.db.nodeElement.skew` | the same cycle passed after the fixture's disposable node-2 seed |

The runner saved `C:/temp/midas-nx-live-gen-1788162734155.mgbx` before the
mutations and reported both cases as `PASS`; it verifies every target and seed
with individual-id DELETE before reporting success. A subsequent independent
GET could not run because the supplied Gen MAPI key then returned HTTP 401
(`MAPI-Key is invalid`). That is an authentication-session interruption, not
evidence about either endpoint; no coverage level changed because this remains
npm-specific evidence.

### npm public-API checkpoint and unresolved-case re-check (2026-08-31)

The npm live harness now saved a checkpoint before every mutation. The
author explicitly selected `C:/temp` as a known writable directory on the NX
machines — a directory they created themselves — after the old inference from
the authenticated MAPI account produced an invalid-path dialog. `SAVEAS`
answered `command complete` on both sessions.

**Correction, 2026-08-31 — and the repo got this wrong twice before landing
on it.** That run wrote `.mgbx` on Gen and `.mcbx` on Civil. Gen's is right.
Civil's was first "corrected" to `.mcb`, which is also wrong: `.mcb` is the
*pre-NX* Civil extension. The author, a MIDAS IT employee, gives the full set:

| | Gen | Civil |
| --- | --- | --- |
| pre-NX | `.mgb` | `.mcb` |
| **NX** | **`.mgbx`** | **`.mcbz`** |

Civil NX's own Export menu lists "MCBZ File", which settles it. Both harnesses
now write the NX pair.

Two adjacent facts, so the next person does not re-derive them. `/doc/STAGAS`
is the exception that genuinely wants the legacy `.mcb` — `.mcbx` failed there
in 2026-07 with "Please check the file name or extension". And Civil does
*tolerate* `.mcbx` for `SAVEAS`: the 2026-07 round trip wrote one and reopened
it with all 273 nodes intact (see the `/doc/*` lifecycle entry above). Being
accepted is not being native, and that tolerance is exactly what let the wrong
spelling survive a live run without complaint.

Note also that `command complete` is not evidence a file was written — this
project's own rule — so nothing establishes what the Civil `.mcbx` checkpoints
from this run actually are. They were never read back.

**Export menus differ by product** (observed 2026-08-31, both products' own
menus). Civil NX: MIDAS/Civil MCT, MXT (for FEA/GTS), AutoCAD DXF, Frame
Section for Solid and for Plate, IDEA, IFC, **MIDAS CIVIL NX JSON File**, and
**MCBZ File**. Gen NX: MGTX (for GEN NX), Batch midas Gen MGTX, MGT (for Gen),
MGT (v885 for nGen), MXT, AutoCAD DXF, Midas Drawing, Frame Section for Solid,
IDEA, IFC, and **MIDAS GEN NX JSON File** — with no MGBX entry, because that
is a save format rather than an export. So `/doc/EXPORTMXT`'s text format is
product-specific (MCT on Civil, MGT/MGTX on Gen), while `/doc/EXPORT`'s JSON
is offered by both.

Using only the built npm package's public `resources.db.*` surface, `/db/STLD`
passed `POST -> GET -> PUT -> GET -> DELETE {id} -> GET` on both products.
The runner first created its documented `DL` and `LC_SCRATCH` static-load
cases, so STLD's server-assigned sequential id matched the Python fixture;
it then removed each target and prerequisite by its individual id.

`/db/THIK` also passed the same public-API CRUD sequence on both products;
the changed `T_IN` value was observed after `PUT`, and the final per-product
`items()` call returned `{}` after the individual delete.

`/db/SKEW` requires an existing target node, so its first npm attempt against
an empty document correctly received the server's explicit “node no. 2 has
not been specified” rejection. The shared fixture now declares a disposable
node-2 seed. With that modelled prerequisite, SKEW passed the same CRUD cycle
on both products; final public `items()` calls returned `{}` for both `NODE`
and `SKEW` after the target and seed were each deleted by id.

The following shared-fixture cases remain **unconfirmed** and reproduced their
existing product rejections rather than becoming npm regressions:

- Gen `/db/SDIS` LRB case: HTTP 201 with `Wrong Field`. The fixture now uses
  the manual's corrected nested `LRB.DX` object and includes `K0`; Gen's
  `/info` exposes that exact nesting. The same response therefore remains an
  unresolved product-value/precondition result, not evidence for changing
  field names or nesting.
- Civil `/db/WVLD`: HTTP 201 with `Wrong Field` for the full fixture payload.
- Gen and Civil `/db/NLLP`: HTTP 201 with `Unknown Error` for the minimal
  `ELEMENT`/`SPG` fixture payload.

Final npm public-API `items()` calls returned `{}` for Gen `STLD`/`SDIS`/`NLLP`
and Civil `STLD`/`WVLD`/`NLLP`. No coverage level changed: that ledger still
denotes Python-package verification, while this entry records independent npm
transport and public-resource evidence.

### npm post-analysis result-table verification (2026-08-31)

Pre-process CRUD is not sufficient evidence for result APIs. The npm package
therefore now has a separate `live:analysis` runner that first refuses a
non-empty fixture scope, then builds a minimal 0.6 m square C24 cantilever
column through public resources (material, section, two nodes, beam, fixed
base, `DL`, and self weight). It saves the completed dummy model under the
author-selected `C:/temp` checkpoint directory before calling `doc.analyze()`.

On both Gen NX and Civil NX, the solved model returned populated `HEAD`/`DATA`
tables through the built npm package for `REACTIONG` (1 row), `DISPLACEMENTG`
(1 row), and `BEAMFORCE` (5 rows). All three responses used the unstable
top-level key `empty`; `post.unwrapTable()` found the table by shape rather
than treating that key as no data. The runner deleted self weight, load case,
constraint, element, both nodes, section, and material individually in reverse
creation order. Final npm public-API GETs returned `{}` for each of those seven
tables on both products.

### npm blank-model design-control re-check (2026-08-31)

With author-confirmed empty scratch documents, re-ran the shared npm fixture
for `/db/DCON` and `/db/DSTL` exclusively through the built package's public
`resources.db.*` surface. The runner saved native-format checkpoints before
each mutation: `C:/temp/midas-nx-live-gen-1788171188500.mgbx` and
`C:/temp/midas-nx-live-civil-1788171201694.mcbz`.

- `/db/DCON` completed `POST -> GET -> PUT -> GET -> DELETE {id} -> GET` on
  both Gen NX 2026 v2.1 and Civil NX 2026 v2.2 (both build 08/26/2026), using
  the manual-listed `KCI-USD12` and `KCI-USD07` codes.
- `/db/DSTL` completed the same sequence on Civil with `Eurocode3-2:05` and
  `AISC-ASD89`. On Gen's otherwise empty document, its initial POST returned
  HTTP 201 with the result error `[Error] Errors detected in Steel Design
  Control Data.(Item:)`. The same response remained after creating the
  manual's `EN05(S)` / `S450` steel material, an `H300x150` section, two beam
  elements, and a design-member record. It is therefore not an empty-model
  prerequisite. The response still does not distinguish a Gen product/license
  gate from another server-side design-control condition, so no request shape
  is inferred from it.

Final npm public-API `items()` calls returned zero records for `NODE`, `ELEM`,
`DCON`, and `DSTL` on both products. This is npm-specific transport evidence;
it does not change the Python write-coverage ledger.

The next small blank-model batch saved
`C:/temp/midas-nx-live-gen-1788171319232.mgbx` and
`C:/temp/midas-nx-live-civil-1788171326304.mcbz` before testing `/db/DCTL`
and `/db/LTSR`.

- `/db/DCTL` completed its full CRUD sequence on both products.
- `/db/LTSR`'s original fixture target id `1` was rejected on both products at
  POST with HTTP 201 and `Not Found Key`. The manual describes it as an
  element-keyed record, and id 1 is not a BEAM in the scratch fixture. A
  disposable manual-derived steel-beam model established that the actual BEAM
  id `2` completes POST, GET, PUT, GET, DELETE-by-id, GET on both products.
  The shared fixture now uses id `2` and declares its material, section, node,
  and beam prerequisites so npm can make the same empty-document test without
  copying a payload into JavaScript.

The corrected npm run saved
`C:/temp/midas-nx-live-gen-1788172728458.mgbx` and
`C:/temp/midas-nx-live-civil-1788172738478.mcbz`; `/db/LTSR` passed through
the built public package on both products. A separate Gen probe found the
manual's `KS21(S)` / `SS400` material example returns `Unknown Error`, whereas
the manual's `EN05(S)` / `S450` example round-trips. This is recorded as a
product observation, not a manual correction: the server did not explain
whether the difference is a license or supported-standard gate.

Both products again returned zero records for `NODE`, `ELEM`, `DCTL`, and
`LTSR` after the run; the modeled prerequisite runs likewise returned zero
records for `MATL`, `SECT`, `NODE`, `ELEM`, `MEMB`, and `LTSR`.

`/db/MBTP` is likewise element-keyed. Using the same official-manual-derived
material, section, nodes, and BEAM id `2`, it completed the full public npm
CRUD sequence on both products. Its shared fixture now declares those same
four seeds rather than trying to write to an empty document. The final npm
checks saved `C:/temp/midas-nx-live-gen-1788173302760.mgbx` and
`C:/temp/midas-nx-live-civil-1788173320331.mcbz`; all target and prerequisite
tables were empty after individual cleanup.

`/db/LENG` is another element-keyed design record. With the same BEAM id `2`
and four reusable prerequisites, it completed the public npm CRUD sequence on
both products. The shared fixture now uses that actual element id and declares
the same setup. Its checkpoints were
`C:/temp/midas-nx-live-gen-1788173496472.mgbx` and
`C:/temp/midas-nx-live-civil-1788173505730.mcbz`.

`/db/MEMB` needs two compatible BEAM elements rather than one. The fixture now
adds node `4` and BEAM id `3` after the reusable element-2 chain, then groups
`[2, 3]` exactly as its documented case specifies. It passed the full public
npm CRUD sequence on Gen and Civil, with checkpoints
`C:/temp/midas-nx-live-gen-1788173602613.mgbx` and
`C:/temp/midas-nx-live-civil-1788173614217.mcbz`. Individual cleanup again
left the target and all material, section, node, and element prerequisites
empty on both products.

`/db/WMAK` is also model-keyed. Its `WID_LIST: [4]` fixture now declares a
disposable material, thickness, rectangular nodes, and PLATE element `4`,
rather than relying on Python's prebuilt base model. Through the built npm
package, the full `POST -> GET -> PUT -> GET -> DELETE {id} -> GET` sequence
passed on Gen and Civil. The saved native checkpoints were
`C:/temp/midas-nx-live-gen-1788174074805.mgbx` and
`C:/temp/midas-nx-live-civil-1788174088855.mcbz`; individual cleanup removed
the WMAK target and every prerequisite.

The setup deliberately uses a PLATE only as a tested fixture prerequisite. A
separate complete manual `TYPE: "WALL"` example (including `STYPE`, `WALL`,
`W_CON`, and `W_TYPE`) succeeded on Gen but Civil NX v2.2 build 08/26/2026
returned `[Error] Unable to add/modify the element. The element type no. 5 for
the element no. 4 is not supported.` The manual's type table numbers PLATE as
5 and WALL as 6, whereas a zero-based internal type number would make WALL 5.
That numbering observation is recorded as MD-06; it does not establish that
PLATE and WALL are interchangeable, so neither contract nor SDK behaviour was
inferred from it.

`/db/SDST` originally failed in the npm harness because its fixture stopped at
the three selector fields. The manual marks `K0`, `P1`, `ALPHA1`, `KB`, and
the selected `BL2.BETA` as required; after adding its documented BL2 example
values, the built package completed the public CRUD sequence on both products.
It read back the changed `P1` value after PUT, then deleted the record by id.
The checkpoints were `C:/temp/midas-nx-live-gen-1788174337218.mgbx` and
`C:/temp/midas-nx-live-civil-1788174348471.mcbz`.

`/db/MVCT` was then exercised unchanged from the shared fixture through the
built npm public resource on both empty scratch models. Gen returned HTTP 201
with `Unknown Error` after saving
`C:/temp/midas-nx-live-gen-1788174456882.mgbx`; Civil returned the same result
after saving `C:/temp/midas-nx-live-civil-1788174467843.mcbz`. The fixture is
not changed from that result: neither response identifies a field or enum to
correct, so treating it as a payload-shape finding would be speculation.

### extras7 fixture re-check and Civil WALL response quote (2026-08-31)

With both scratch documents empty, the Python live runner re-ran `extras7` on
Gen NX and Civil NX 2026 (v2.1/v2.2, build 08/26/2026). `/db/PNLD` completed
`POST -> GET -> PUT -> GET -> DELETE {id} -> GET` on both products using its
existing manual-derived fixture and disposable seed. The earlier coverage ledger
already correctly recorded that write evidence; this run corrects the stale
fixture `confirmed` flag. The checkpoints were
`C:/temp/midas-nx-live-gen-extras7-20260831.mgbx` and
`C:/temp/midas-nx-live-civil-extras7-20260831.mcbz`.

The same run reproduced the established outcomes without changing their
fixtures: Gen `/db/FBLA` returned `Unknown Error`; Gen `/db/EPST` and
`/db/EPSE` returned `Wrong Field`; Civil `/db/FBLA` returned `Unknown Error`.
The Civil runner skipped Gen-only earth-pressure cases and reported its existing
incompatible POSL seed, while the independent PNLD case still completed and
cleaned up. These remain product/precondition findings rather than shape changes.

For MD-06, a separate Civil probe used the manual's complete `TYPE: "WALL"`
element example and returned exactly `[Error] Unable to add/modify the element.
The element type no. 5 for the element no. 4 is not supported.` It deleted every
seed record individually; the final `NODE` and `ELEM` reads were both empty.

The same PNLD fixture then passed through the built npm package's public
`resources.db.*` surface on both products. The npm runner saved
`C:/temp/midas-nx-live-gen-1788187237711.mgbx` and
`C:/temp/midas-nx-live-civil-1788187248388.mcbz` before the round trips and
reported `PASS /db/PNLD` for each. This is npm-specific evidence and therefore
does not alter `docs/coverage.json`'s Python-package write ledger.

### extras8 current-build re-check (2026-08-31)

On empty scratch documents, the Python `extras8` runner re-ran the existing
manual-derived control-data fixtures on Gen NX 2026 v2.1 and Civil NX 2026 v2.2,
both build 08/26/2026. `/db/EIGV` completed the documented LANCZOS round trip
on both products with `TYPE`, `iFREQ`, `bMINMAX`, `FRMIN`, `FRMAX`, and `bSTRUM`;
no `FREQ_RANGE` field was sent. This supersedes the older Civil failure for this
exact fixture on the current build, but does not establish a version-independent
Civil behaviour or add an undocumented field to a contract.

`/db/BCCT` likewise completed on both products when its `vBOUNDARY.vBG` values
referenced the real `BG1` and `BG2` `/db/BNGR` seed records. This supersedes the
older Civil failure for this fixture on the current build only. Both endpoints
now have current Gen-and-Civil write evidence; the runner marks their Civil
fixtures confirmed and deletes each disposable record after the test.

The unresolved observations were kept distinct: Gen rejected `/db/ACTL` with
`Wrong Field`; Civil accepted its request but read `TOL=0.0005` back as `0.001`.
Both products returned `Unknown Error` for `/db/MVCT`; Civil still failed `/db/HHCT`
by reading `THETA=0` after sending `1`, and `/db/NLCT` required
`LINE_SEARCH_OPTION` when `OPT_ENABLE_LINE_SEARCH` was true. None of those
outcomes identifies a manual-backed payload correction, so their fixtures and
contracts remain unchanged.

### extras6 fixture re-check (2026-08-31)

The existing `/db/SDST` steel-damper fixture completed its full CRUD sequence
on both empty scratch models (Gen NX v2.1 and Civil NX v2.2, build 08/26/2026).
It was already write-covered, so this only corrects its stale fixture
`confirmed` state. `/db/SDVI` and `/db/SDVE` both returned `Wrong Field` on
both products; Gen's `/db/SDHY` and `/db/SDIS` did too. Their existing fixtures
remain unconfirmed because the responses do not identify a manual-backed value
change. Each run saved its checkpoint under `C:/temp` and deleted test records
individually.

### extras13 Gen/Civil design fixture re-check (2026-09-01)

After saving the pre-existing test model to `C:/temp`, the runner created and
cleaned up fresh scratch models on Gen NX 2026 v2.1 and Civil NX 2026 v2.2,
both build 08/26/2026. `/db/DCON`, `/db/LENG`, `/db/MEMB`, `/db/DCTL`,
`/db/LTSR`, `/db/MBTP`, and `/db/WMAK` each completed
`POST -> GET -> PUT -> GET -> DELETE {id} -> GET` on both products. The
previous Civil-only coverage records are therefore now current dual-product
evidence.

`/db/DSTL` remains intentionally unconfirmed. Its existing Eurocode3-2:05 /
AISC-ASD89 fixture completed on Civil, but Gen returned exactly
`[Error] Errors detected in Steel Design Control Data.(Item:)` at POST. That
is a product/build observation, not a basis for changing its manual-backed
payload or contract. The checkpoints were
`C:/temp/midas-nx-live-gen-extras13-20260901.mgbx` and
`C:/temp/midas-nx-live-civil-extras13-20260901.mcbz`; all test records were
deleted by individual id.

The built npm package independently completed the same seven endpoints through
its public `resources.db.*` API on both products. Before every npm batch, the
harness saved the open document to `C:/temp`, called `doc.newProject()`, and
verified `/db/NODE` and `/db/ELEM` were both empty before inserting fixture
records. This caught a harness defect: it had previously saved a checkpoint but
continued in the caller's open model. The fixture now explicitly permits only
the new-document baseline records (`MATL`/`SECT`/`THIK` id 1) to be replaced by
its own individually-cleanable prerequisites; every other setup collision still
refuses to mutate. The Gen checkpoints included
`C:/temp/midas-nx-live-gen-1788189466400.mgbx` and
`C:/temp/midas-nx-live-gen-1788189527322.mgbx`; Civil used
`C:/temp/midas-nx-live-civil-1788189535828.mcbz` and
`C:/temp/midas-nx-live-civil-1788189577919.mcbz`. Follow-up reads confirmed
both products ended with zero nodes and elements.

### Civil response-spectrum load fixture re-check (2026-09-01)

`/db/SPLC` again completed `POST -> GET -> PUT -> GET -> DELETE {id} -> GET`
on Civil NX 2026 v2.2, build 08/26/2026, using the existing `SPFC_SEED`
function prerequisite. The same fixture remains unconfirmed on Gen NX: its
POST returns `Unknown Error`. The fixture is therefore recorded as two
product-specific cases (Civil confirmed; Gen unconfirmed), rather than letting
a Civil result claim a uniform cross-product result. The Civil checkpoint was
`C:/temp/midas-nx-live-civil-extras5-20260901.mcbz`.

In the same empty-scratch-model batch, `/db/SPFC`, `/db/THGC`, `/db/THFC`,
`/db/THGA`, `/db/THNL`, and `/db/THSL` completed their existing Civil cases.
`/db/THMS` returned `Wrong Field` at create; that response does not identify a
manual-backed fixture correction, so it remains unconfirmed.

### Domain feature current-build re-check (2026-09-01)

On both empty scratch models, `/db/MADO`, `/db/SBDO`, and `/db/DOEL` again
accepted their POSTs but had no requested record in the immediately following
GET. `/db/MADO` is the prerequisite: it was absent at id 92 on both Gen NX
v2.1 and Civil NX v2.2, build 08/26/2026. The `SBDO` and `DOEL` results remain
downstream observations rather than independent failures, because their
manual-shaped records reference that missing domain. No payload, contract, or
coverage level was changed. Checkpoints are
`C:/temp/midas-nx-live-gen-extras9-20260901.mgbx` and
`C:/temp/midas-nx-live-civil-extras9-20260901.mcbz`.

### Heat-source function fixture re-check (2026-09-01)

`/db/HSFC` completed its full round trip on both current builds after the
fixture created its two named prerequisite functions at ids 90 and 91, then
used independent id 92 for the test record. The previous `confirmed: false`
fixture state was stale evidence, not a product failure, and is now corrected.
`/db/HAHS` still requires a SOLID element that this deliberately minimal model
does not create; `/db/HPCE` still rejects its documented `ITEMS` array with
`Wrong Key`. Both remain unconfirmed without any inferred payload change. The
checkpoints are `C:/temp/midas-nx-live-gen-extras10-20260901.mgbx` and
`C:/temp/midas-nx-live-civil-extras10-20260901.mcbz`.

The built npm package independently completed `/db/EIGV` and `/db/SDST` through
its public `resources.db.*` surface on both products. It saved
`C:/temp/midas-nx-live-gen-1788187895868.mgbx` and
`C:/temp/midas-nx-live-civil-1788187934137.mcbz` before the checks. The npm
harness now selects the product-specific fixture when one endpoint has separate
Gen and Civil cases; previously it selected the first duplicate and incorrectly
skipped Gen `/db/EIGV`. `/db/BCCT` is deliberately not counted as npm evidence:
its Python fixture needs the tier-local `bngr_seed`, which the language-neutral
fixture does not yet serialize for the npm harness, so the public API correctly
returned `Not Found Key` without that prerequisite.

The documented PowerShell invocation with two selected paths also completed
after the harness normalized npm 12's retained cmd.exe caret quoting and its
space-split comma value. `npm run live:crud -- -- --product gen --endpoints
/db/EIGV,/db/SDST --save-dir C:/temp` saved
`C:/temp/midas-nx-live-gen-1788188480567.mgbx` and passed both endpoints.

### extras1 and extras3 current-build re-check (2026-08-31)

The existing `/db/NLLP` seed again returned `Unknown Error` on both empty
scratch models. Its dependent `/db/NLNK`, `/db/NLNK-M1` (Civil), and `/db/CGLP`
were therefore correctly reported as blocked rather than tested against a
missing prerequisite. No fixture was changed. The `extras3` re-check likewise
left `/db/TDMF` and `/db/RPSC` failing at create on both products, and
`/db/STRPSSM` failing at create on Civil. These are current-build reproductions,
not evidence for changing fields, values, or contracts. All runs saved to
`C:/temp` and left the throwaway documents empty after individual cleanup.

### Session-close scratch-state check (2026-09-01)

Before closing this batch, the two latest scratch documents were saved as
`C:/temp/midas-nx-live-gen-final-scratch-20260901.mgbx` and
`C:/temp/midas-nx-live-civil-final-scratch-20260901.mcbz`, then each product
received `/doc/NEW`. Read-only table reads afterward returned zero `/db/NODE`
records and zero `/db/ELEM` records on both products. The open documents are
therefore empty at session end.

### Both SDKs swept read-only across the whole generated surface (2026-09-01)

Every earlier npm entry exercised a handful of endpoints. This is the breadth
check - `scripts/live_readonly_sweep.py` and a JavaScript counterpart written to
match it - run on **both** language surfaces against the same two sessions on
the same day. It is **GET only**: no create/update/delete, no `/doc/*`, no
`/doc/NEW`, no `/post/TABLE`. It ran against the documents the sessions already
had open and left them untouched.

The npm subject was the **packed artifact**, not the source tree: `npm pack`
produced `midas-nx-2.7.3.tgz`, which was installed into a throwaway project with
`npm install` and imported as `midas-nx`. Only `resources.db.*` and
`resources.design.*` were called. The Python side ran the repo's own sweep plus
two probes mirroring the npm ones, without `--record-coverage`.

| check | calls per SDK | npm | PyPI |
| --- | --- | --- | --- |
| `get()` on every GET-capable resource, per declared product | 549 | 549 answered, 0 errors | 549 answered, 0 errors |
| GET on the product a single-product resource does *not* declare | 57 | 57 refused with 404 | 57 refused with 404 |
| `info()` on every GET-capable resource, per declared product | 549 | 399 schemas, 150 404s | 399 schemas, 150 404s |

**The two SDKs swept exactly the same 549 (product, endpoint) pairs** - set
equality, not just equal counts - and returned the same result for every one.
`validate_contracts.py` already checks endpoint parity statically; this is the
first time it has been checked against running products from both languages at
once. Gen swept 267 resources and Civil 282; the npm passes took 22.9s and 25.3s.

**Product gating is correct in both directions.** All 549 declared
resource/product pairs answered, so the metadata is not wider than the server,
and all 57 single-product resources 404 on the product they do not declare, so
it is not narrower either. This is the systematic version of the check that
found 32 wrongly-Civil-only endpoints in 2026-07; nothing of that kind remains.

Thirteen resources returned data on an otherwise-empty document, all
new-document defaults: `/db/CO_F`, `/db/CO_M`, `/db/CO_S`, `/db/CO_T`,
`/db/STYP` and `/db/UNIT` on both products, plus `/db/STYP-M1` on Civil only,
which is consistent with Hyper-S being Civil NX's solver. The other 536 returned
`{"message": ""}`.

**`/info` is served for `/db/*` only.** All 147 `/DESIGN/*` resource-product
pairs 404 on introspection while the endpoint itself answers a plain GET. That
is an API fact, not a URL-construction bug in either SDK - three casings were
tried by hand on Gen:

```text
GET /DESIGN/RC/KDS-41-20-2022/DCTL        -> {"message": ""}
GET /info/DESIGN/RC/KDS-41-20-2022/DCTL   -> 404
GET /info/design/RC/KDS-41-20-2022/DCTL   -> 404
GET /info/DESIGN/rc/kds-41-20-2022/dctl   -> 404
GET /info/db/NODE                         -> full JSON Schema
```

This matters beyond the harnesses. `GET /info{endpoint}` is one of the three
permitted contract sources, and for the design-code family it does not exist:
those contracts can only be checked against the manual and against recorded live
behaviour. `contracts/README.md` and `CLAUDE.md` now say so.

Three `/db/*` endpoints also lack introspection, all Civil Hyper-S:
`/db/IEHG-GL-M1`, `/db/IEHG-PSS-M1` and `/db/IEHG-TRUSS-M1`. They are the only
exceptions among 402 `/db` resource-product pairs, and both SDKs found the same
three.

Both SDKs expose `info()` on design resources, where it can only ever 404. That is a
documentation question, not a defect found here, and no SDK behaviour was
changed on the strength of this run.

Sessions were `connected` before and after, and `/db/NODE` and `/db/ELEM`
returned zero records on both products afterwards - the sweeps issued no writes,
and none of the roughly 2,300 GETs raised a modal dialog that blocked a session.
The products were MIDAS Gen NX 2026 (v2.1) and MIDAS Civil NX 2026 (v2.2); the
build string was not re-read this session, so this entry does not establish it.
No `docs/coverage.json` level changed - every endpoint swept is already recorded
at `read` or better, and `level` denotes verification through the Python package
in any case.

### LCOM-SEISMIC real response-spectrum prerequisite re-check (2026-09-01)

The earlier product asymmetry was re-tested with the manual's actual
response-spectrum shape, rather than treating a static load case as a proxy.
The Civil scratch fixture first created `/db/SPFC` `SPFC_LCOM_SEED`, then a
real `/db/SPLC` Response Spectrum Load Case `SPLC_LCOM_SEED` referring to it.
`/db/LCOM-SEISMIC` was then posted with `ANAL="RS"` and that real `LCNAME`.
Civil NX 2026 v2.2, build 08/26/2026 still answered exactly:

```text
The Load Combination Type is not supported.
```

This removes the missing-fixture explanation, but does not justify inventing
a different Civil payload: the documented RS path itself is refused on the
current server. The Civil case remains explicitly unconfirmed.

Gen NX 2026 v2.1, build 08/26/2026 independently completed the existing
documented static-member `ANAL="ST"`, `LCNAME="DL"` create -> GET -> update
-> GET -> delete sequence. `/db/LCOM-SEISMIC` therefore moves to Python write
coverage for **Gen only**; it is not a claim that Civil supports the same
operation. The built npm package's public `resources.db` entrypoint completed
the same Gen round trip after its empty-document harness created the explicitly
declared `static_load_cases` prerequisite. Both reports and checkpoints were
saved under `C:/temp`.

### Stage and extra resource re-check (2026-09-01)

`STAG`, `TMLD`, `CRPC`, and `HSPT` completed their current fixtures on both
products; Civil's `CMCS` completed as its Civil-only case. The remaining
observations reproduce known product/server behaviour and do not change a
contract: Gen accepted `STCT` but omitted the submitted `iITER` value on the
readback, Civil returned `Key Already Exist` for the same resource, and `HECB`
on both products rejected the scratch beam with the server message that the
element type cannot receive an Element Convection Boundary. Checkpoints and
reports were saved under `C:/temp`.

### Complete SDVI and SDVE Request Examples re-check (2026-09-01)

The earlier `Wrong Field` results for `/db/SDVI` and `/db/SDVE` pre-dated the
manual's 2026-08-25 Request-Example corrections. The old SDVI fixture omitted
`INPUT_TYPE_EXFN` and the six exponential-function fields in each `ITEM`; the
old SDVE fixture contained only `COMMON`, `MATERIAL_TYPE`, and `SHEAR_AREA`.
Those were incomplete test payloads, not evidence that the current documented
routes reject their documented shapes.

Using the complete current examples, both endpoints completed
`POST -> GET -> PUT -> GET -> DELETE(id) -> GET` on Gen NX 2026 v2.1 and
Civil NX 2026 v2.2, build 08/26/2026. SDVI sent all twelve documented fields
for each of six DOFs; SDVE sent the fourteen Request-Example fields from
`THICKNESS` through `KINETIC_FRIC`. Both fixtures are now confirmed and their
coverage entries are write-level on both products. The old `Wrong Field`
finding is superseded by this manual-backed rerun, not hidden by a weaker
payload.

The built npm package's public `resources.db` entries completed the same two
full CRUD cycles on each product from a fresh `/doc/NEW` document. That adds
SDVI and SDVE to the npm harness evidence without changing the Python-only
meaning of `docs/coverage.json`'s `level` field.

After this batch, each latest scratch document was saved under `C:/temp` with
its product-native extension, then `/doc/NEW` was issued. Final read-only
checks found `NODE=0` and `ELEM=0` on both Gen and Civil, so both open documents
are empty.

### Hydration SOLID-fixture re-check: HAHS and HECB (2026-09-01)

The previous HAHS and HECB failures were deliberately re-run with a real
dummy model, not the baseline frame/plate fixture.  The fixture follows the
official `/db/ELEM` manual's eight-node hexahedral `SOLID` form
(`TYPE="SOLID"`, `MATL=1`, `SECT=0`) and creates the needed nodes, element,
real structure group, boundary group, functions, and construction stage from
an empty `/doc/NEW` document.

- `/db/HAHS` used an isolated SOLID at element 50.  Both Gen and Civil
  completed `POST -> GET -> PUT -> GET -> DELETE(id) -> GET`; the heat-source
  function changed from `HSFC_SEED` to `HSFC_SEED_2` on readback.
- `/db/HECB` initially still failed when its `ITEMS[].ID` was changed to 51.
  The manual calls this value a serial number, so the final fixture retained
  `ID=1` and made the first element itself the SOLID.  With that model and a
  real activated construction stage, both products completed the same full
  CRUD cycle, including a persisted `FACE_NO` change from 1 to 2.  The earlier
  "element no. 1" response was therefore a fixture symptom, not evidence to
  reinterpret the documented field as an element id.

These runs used MIDAS Gen NX 2026 v2.1 and MIDAS Civil NX 2026 v2.2, both
build 08/26/2026.  Reports and saved scratch checkpoints are under `C:/temp`;
each product was returned to a new empty document after the run.

### Pipe-cooling SOLID-fixture re-check (2026-09-01)

`/db/HPCE` was re-tried before calling its existing `Wrong Key` result a
product defect.  Each product started from a new scratch document with the
same manual-backed 8-node hexahedral SOLID used for HAHS/HECB.  The exact
documented payload was then posted with its `ITEMS` array populated by that
SOLID's real nodes: first all 8 nodes, then the 6-node length used by the
manual Request Example.  Gen was also tried with 4 and 2 of those real nodes.

Every attempt returned the identical `Wrong Key` response on Gen NX 2026 v2.1
and Civil NX 2026 v2.2, build 08/26/2026.  This eliminates the earlier
frame/plate-node fixture as the explanation, but does not license an invented
wire shape: the manual and current `/info` both state `ITEMS` is an integer
array.  HPCE therefore remains read-level/unconfirmed pending product evidence
or corrected documentation.  The latest scratch checkpoints are under
`C:/temp`, and both sessions were reset to an empty document afterwards.

### STCT documented Linear/Independent branch re-check (2026-09-01)

The original STCT fixture put the linear-only `iITER`/`TOL` fields beside the
Accumulative stage choice (`iNLA_TYPE=1`).  The manual instead assigns those
fields to the **Linear + Independent** branch, so a fresh scratch model with a
real construction stage was tested on both products with
`iINC_NLA=0`, `iNLA_TYPE=0`, `iITER=30`, and `TOL=0.01`.

The result is the same defect on the correct branch: Gen NX POST echoes both
values but its first GET omits them; Civil NX's stage creates the locked default
record as before, and PUT echoes both values but its following GET omits them.
Thus this is not a branch-selection or dummy-model issue.  The live fixture now
uses the documented Linear/Independent combination and remains unconfirmed;
the two fields cannot currently be verified as persisted.  Both products were
MIDAS Gen NX 2026 v2.1 / Civil NX 2026 v2.2, build 08/26/2026, and were reset
to empty scratch documents afterwards.

### Seismic-device fixture completion: SDHY and SDIS (2026-09-01)

The reusable Gen-only `extras6` fixture had drifted behind the corrected
official manual: SDHY still sent only `COMMON`, `SDHY_HYS_MODEL`, `MSS`, and
`K0`, omitting the documented `P1`, `P2`, `ALPHA1`, `ALPHA2`, `BETA`, `Phi`,
and `LAMBDA` fields. It now sends the complete current Request Example.

From a new saved scratch document, the public Python resources completed all
five seismic-device cases. In particular, `/db/SDHY` persisted `K0` from 5000
to 6000 and `/db/SDIS` used the manual's successful `SDIS_DEV_TYPE="SLD"`
branch with its `SB` object, persisting `KV` from 150000 to 160000. Each did
`POST -> GET -> PUT -> GET -> DELETE(id) -> GET`; the prior LRB `Wrong Field`
finding is intentionally not hidden or reclassified by this endpoint-level
SLD success. Gen NX 2026 v2.1 build 08/26/2026 was reset to an empty document
after the run; SDHY and SDIS are Gen-only declared endpoints.

The built npm package independently repeated `/db/SDHY` and `/db/SDIS` through
the public `resources.db` API (`npm run live:crud`, not raw HTTP) on the same
Gen NX build. Both completed their full CRUD cycles from a separately saved
and newly created scratch document, which was left empty by the harness.

### Dynamic-load fixture completion: SPLC and THMS (2026-09-01)

The remaining `extras5` failures were also abbreviated fixtures, not product
findings. `/db/SPLC` had retained only five core fields even though the manual
no-damping Request Example also supplies `ANGLE`, `bDAMP`, `INTERP`,
`COMTYPE`, `bADDSIGN`, `iSIGNTYPE`, `bMODE`, and three `aUSEMODE` entries.
`/db/THMS` had sent only its X-direction function while the worked example
includes the Y/Z functions and all three arrival-time fields.

With the complete manual shapes and real `SPFC_SEED`, `THIS_SEED`, and
`THFC_SEED` prerequisites in new scratch models, both endpoints completed
`POST -> GET -> PUT -> GET -> DELETE(id) -> GET` on Gen NX and Civil NX.
SPLC persisted `SCALE` 1.0 to 1.2; THMS persisted `SCALEX` 1.0 to 1.5.
This supersedes the former Gen-only SPLC `Unknown Error` and cross-product
THMS `Wrong Field` observations. Both products were Gen NX 2026 v2.1 / Civil
NX 2026 v2.2, build 08/26/2026, and the harness returned both documents to an
empty state after each run.

### CSCS composite-section fixture boundary (2026-09-01)

`/db/CSCS` was rechecked on both products from a new scratch model with the
manual's minimum construction-stage record and the complete documented CSCS
part-information body. The request was sent with the required `Assign`
envelope. Gen NX and Civil NX both rejected the base model section at
`Item:Section Type`, which is expected: the manual says this route requires a
`COMPOSITE` section.

The only manual `COMPOSITE`/`SOD_BOX` sample available for the prerequisite
section omits the dimensions needed for a valid section; Gen NX rejects that
literal sample with `Section Dimensions has(have) been incorrectly entered.`
The missing geometry is not supplied by the `/db/CSCS` chapter, so the test
does not invent it or infer it from either SDK. CSCS therefore remains
read-level/unconfirmed pending a complete manual composite-section fixture or
new live evidence. Both products were reset to empty scratch documents after
the probe (Gen NX 2026 v2.1 and Civil NX 2026 v2.2, build 08/26/2026).

### Hyper-S `/info` schema artifact capture (2026-09-02)

Civil NX's relay reported program `civil`. Read-only `GET /info/db/...` calls
captured the complete response bodies in `schema/hyper-s-info.json`; no model
GET response body was captured and no model data was changed. The top-level
`Argument.properties` fields match the two earlier prose probes exactly:
`MATL-M1` has `MATL_NAME`, `MATL_TYPE`, `DAMP_RAT`, and `PARAM`; `EPMT-M1` has
`NAME`, `MODEL_TYPE`, `TRESCA`, `VMISES`, `MOHRCL`, `DRUCKER`, `MASONRY`, and
`CONCDMG`; `IMFM-M1` has `CONCRETE` and `STEEL`; `IEHG-BEAM-M1` has
`INEL_PROP_NAME`; and contracted `STYP-M1` has `STYPE`, `GRAV`, `TEMP`,
`ALIGNBEAM`, `ALIGNSLAB`, and `MASS_CONTROL`.

`GET /info/db/IEHG-TRUSS-M1`, `/info/db/IEHG-GL-M1`, and
`/info/db/IEHG-PSS-M1` each returned the expected 404. The split still holds:
they serve GET but expose no introspection schema, so their assumed
`INEL_PROP_NAME` shape remains labelled as sibling analogy rather than live
schema evidence.

### `/db/STYP-M1`'s contract and its `/info` schema were written from different sources and agree exactly (2026-09-02)

`schema/hyper-s-info.json` deliberately includes `/db/STYP-M1`, which is not
one of the seven uncontracted stubs. It is the one Hyper-S endpoint with a
real manual section, so its contract was derived from the Specifications
table with no reference to introspection - which makes the captured schema an
independent check on it rather than a restatement.

They agree on all ten paths, type for type:

| path | `/info` | `contracts/endpoints/db-styp-m1.yaml` |
| --- | --- | --- |
| `STYPE` | string | string |
| `GRAV` | number | number |
| `TEMP` | number | number |
| `ALIGNBEAM` | boolean | boolean |
| `ALIGNSLAB` | boolean | boolean |
| `MASS_CONTROL` | object | object |
| `MASS_CONTROL.MASS_TYPE` | string | string |
| `MASS_CONTROL.MASS_POS` | string | string |
| `MASS_CONTROL.SELFWEIGHT` | boolean | boolean |
| `MASS_CONTROL.MASS_AXIS` | string | string |

The four nested members are the point. The manual never writes the path
`MASS_CONTROL.MASS_TYPE`; it numbers those rows `2-(1)` through `2-(4)` under
a row named `MASS_CONTROL` and leaves the reader to infer the nesting. The
contract carries four notes saying exactly that, and the server's own schema
now confirms the inference was right.

That is a statement about the extractor, not just this endpoint. Rebuilding a
structure the manual addressed by numbering is the most common finding in the
whole contract set - 592 of them across 95 contracts - and this is the first
time one has been checked against a source that states the path directly.

### The `/info` schemas are malformed in two ways (2026-09-02)

Captured verbatim, so both are in `schema/hyper-s-info.json` as served:
apostrophes inside `description` strings are escaped `\'`, which is not a JSON
escape (8 occurrences), and `maxItems` is stated on an array's `items`
subschema rather than the array (4 occurrences on `/db/MATL-M1`). Registered
as **MD-12**; a contract written from this artifact must not transcribe
either.

### What the capture did not record

The session's Civil NX build string. `schema/hyper-s-info.json` carries
`"nxVersion": null` and says so rather than naming a build it does not have,
and the eight `docs/coverage.json` entries keep the `nx_versions` of the
sessions that set their level. Every other live record in this repo carries a
build; re-stamp this one on the next Civil NX session rather than inferring
it from the dates around it.

## 2026-09-02 (later) — an `/info` sweep of the 18 endpoints no contract could reach

Read-only `GET /info/db/...` for every remaining uncontracted `/db/*` resource,
on each product it declares: **27 probes, all answered.** Captured verbatim in
`schema/info-schemas.json`. No `/doc/NEW`, no write, and no GET response body
recorded, so nothing here is model data. Both sessions verified as
`sjj0507@midasit.com`; neither product's build string was recorded, and the
artifact says so rather than naming one.

Each of these endpoints was blocked by an ambiguity the manual states but does
not resolve. The server resolves most of them outright.

### `/db/TDME`: the duplicate `"SCALE"` is a wrong key, and the right one is `aDATA`

MD-13. The Specifications table gives `"SCALE"` to both "Scale Factor"
(Number) and "Function Data" (Array of `{TIME, COMP, TENS, ELAST}`), and the
vendored manual's own ⚠️ callout says there is no example to tell them apart.
There is now:

```text
SCALE   number   Scale Factor
aDATA   array    Func Data   items -> TIME, COMP, TENS, ELAST
```

Row 5 is right and row 6's key is wrong: the array is `aDATA`. Civil and Gen
return byte-identical schemas. This is the manual's error to fix, not a choice
between two documented names, and it closes MD-13.

### Three compact key rows name real, separate fields

| endpoint | the manual's one cell | what `/info` lists |
| --- | --- | --- |
| `/db/MVLDeu` | `"SCALE_FACTOR1"/"SCALE_FACTOR2"/"SCALE_FACTOR3"` | all three, each `number` |
| `/db/STCT-M1` | `bSDLE" / "vSDLE` | `bSDLE` boolean, `vSDLE` array of names |
| `/db/THIS-M1` | `FREQ1/PERIOD1` | `DAMPING.FREQ1`, `DAMPING.FREQ2`, `DAMPING.PERIOD1`, `DAMPING.PERIOD2` |

`/db/THIS-M1`'s is the most useful: the row names two of four real fields, and
they are nested under `DAMPING` rather than at the root, which the table never
says.

`/db/POGD`'s refused cell is different in kind - `AIK-G-001-2021` is a design
code name, not a wire property, and none of the endpoint's nine real
properties is called anything like it.

### `/db/REBW`'s field names, confirmed a third time and in full

`GET /info/db/REBW` returns one `ITEMS` array whose members are `ID`,
`bUSE_MODEL_THICK`, `THICK`, `DW`, `DE`, `VER_BAR`, `HOR_BAR`, `END_BAR`,
`NUM_END_BAR`, `BE_HOR_BAR`, `BE_LENGTH`, `vSTORY_NAME`. That matches the
2026-07-29 live PUT round trip exactly and adds the four the round trip never
touched. The manual's Specifications table names none of them.

`/db/PRES` and all four `/db/REB*` endpoints are the same shape: a single
`ITEMS` array with everything inside it.

### `/db/POGD` is not the same endpoint on both products

The only pair in the sweep whose two schemas differ. Same nine top-level keys,
but `NONL_OPT` and `PHOP_OPT` carry different members - Gen's `PHOP_OPT` opens
with `bCONSREBARAREA1D` and `BEAM_CORE_SIZE` (fiber-model options), Civil's
with `bASSIGNBYMEMBER` and `bTRI_SYM`. A contract for `/db/POGD` has to tag
those members by product; a single shape would be wrong on one of them.

Every other both-product endpoint returned byte-identical schemas on Gen and
Civil - eight pairs, which is also the first systematic check that `/info`
itself agrees across products.

> **Superseded in part, 2026-09-04.** "The only pair in the sweep" was accurate
> about a sweep of nine endpoints, and it is not true of the API.
> `scripts/info_baseline.py --divergence` asks the same question of all **177**
> pairs that answer `/info` on both products and finds **ten** that differ:
> `/db/ACTL`, `/db/BCCT`, `/db/EPSE`, `/db/IEHC`, `/db/POGD`, `/db/POLC`,
> `/db/POSL`, `/db/SBDO`, `/db/SPLC`, `/db/THGC`. `/db/SPLC` differs by fifteen
> fields and `/db/POGD` by twenty, so this one was not even the widest. What
> stands is the conclusion drawn from it - "a contract has to tag those members
> by product; a single shape would be wrong on one of them" - which is now done
> for nine of the ten. See MD-46.

## 2026-09-03 — `/db/TDME`'s code-name branches, tested one at a time

Both documents were confirmed empty first — `GET /db/NODE`, `/db/ELEM`,
`/db/MATL` and `/db/TDME` all answered `{"message": ""}` on Gen NX and Civil NX
— so no `/doc/NEW` was needed and none was called. Every record created was
deleted by its own id, and both tables end empty.

The manual splits `/db/TDME` into eight "전용 추가 필드" tables, one per group of
`CODENAME` values, and the extractor refuses to promote a contract from them
because nothing says what review decided about the split. This tests the split
directly. Payloads come from the section's own tables, and the `KDS-2016` case
is the manual's Request Example copied verbatim.

### The manual's Required is not the product's, and it differs per branch

| `CODENAME` | sent | result |
| --- | --- | --- |
| `CEB-FIP(2010)` | base fields only | **stored**, server filled `iCTYPE` |
| `European` | base fields only | **stored**, server filled `iCTYPE: 2` |
| `Russian` | base fields only | rejected, "input data contain errors" |
| `ACI` | base fields only | rejected, "input data contain errors" |
| `KDS-2016` | base fields only | rejected, "input data contain errors" |
| `KDS-2016` | + `iCTYPE: 1`, `DENSITY: 230` | **stored** |

Every one of those extra fields is marked **Required** in its branch table. For
`CEB-FIP(2010)` and `European` the server supplies a value instead of refusing,
and for `ACI`, `Russian` and `KDS-2016` it does refuse. That is exactly the
`documentedOptional` / `safeToOmit` split this repo keeps as two booleans: the
documentation's claim is uniform, the product's behaviour is not.

Identical on both products, checked case for case.

### Two of the documented code names belong to a different product

`Japan(hydration)` and `Japan(elastic)` — entries 16 and 17 of the chapter's own
`CODENAME` table, each with its own branch of extra fields — answer
`Wrong Field` on Gen NX **and** Civil NX. Seven spellings were tried
(`Japan(hydration)`, `Japan(elastic)`, `Japan (Hydration)`, `JAPAN(HYDRATION)`,
`Japan(Hydration)`, `Japan(Elastic)`, bare `Japan`); all seven, both products.

**The refusal is correct and the search was misdirected.** Those two codes are
**iGen's**, and this API is not talking to iGen (author, 2026-09-03). Nothing
is wrong with the product.

Two things are worth keeping from it. The chapter's code table mixes another
product's values into a list it presents as this endpoint's, with no marking —
recorded as **MD-14**, owned by the manual repo. And this file's own diagnostic
rule, `Wrong Field` = "the value is unknown, vary the value not the fields",
is true but incomplete: it points at spelling, and the answer here was not a
spelling. A value the product has never heard of and a value that belongs to a
sibling product produce the identical error, so after two or three spellings
the next question is which product the value is from, not which capitalisation.

`/info/db/TDME` lists every field those two branches require
(`TENS_STRN_FACTOR`, `bUSE`, `A`, `B`, `D`, `iCTYPE`, `iECTYPE`), so the
endpoint's schema is shared across products even where the code names are not.

### The server renumbers a posted record, and it cost a cleanup pass

`POST /db/TDME` under key `901` echoed `{"TDME": {"901": {...}}}` and then
stored the record as id `1`. The first probe's cleanup keyed off the id it had
posted, found nothing, and left eight records behind; a second pass deleted
them by the ids a `GET` actually reported. This is the same behaviour recorded
for `/db/STLD` in 2026-07-26 (a POST under key `7` produced id `3`), so it is a
`/db/*` property and not news — but a harness that deletes by the id it sent
will silently fail to clean up. Match on a field you set, then delete by the id
the table reports.

## 2026-09-03 (later) — `/db/PRES`: B-4 measured, with the error string

The last surviving claim of the vendor report's section B, tested against a
real plate. The Gen document was confirmed empty first, seeded with
`live_crud_check.py`'s own `_seed_model` — the repo's confirmed payloads, not a
hand-written model — and every record deleted by id afterwards. `/doc/NEW` was
neither needed nor called; all nine tables the seed touches read
`{"message": ""}` at the end.

Element 4 is the seed's plate. `ELEM_TYPE: "PLATE"`, `FACE_EDGE_TYPE: "FACE"`,
`EDGE_FACE: 1`, `FORCES: [-10, -10, -10, -10]`, varying only `DIRECTION`:

| `DIRECTION` | result |
| --- | --- |
| omitted | **rejected** — `[Error] Errors detected in Pressure Loads Data.(Item:Load Direction)` |
| `"NORMAL"` | **rejected** — same message |
| `"LZ"` (local z) | stored |
| `"GZ"` (global Z) | stored |

**B-4 holds, and both halves of the row are wrong for this combination.**
`DIRECTION` is marked *Optional* with default `"NORMAL"`; omitting it fails,
and the default it names is the one value this combination refuses. The
official article's footnote availability matrix already said so — Normal is
`-` for PLATE + FACE while Local x/y/z and Global X/Y/Z are `O` — so the
matrix and the product agree and only the Specifications row is out of step.

That is the whole of what survived section B's re-audit, now with a
reproduction and the exact error text rather than an inference.

### The `Assign` key is what selects the element

The first attempt sent `{"Assign": {"1": {"ITEMS": [{"ID": 4, ...}]}}}` — the
plate named in `ITEMS[].ID`, under key `1` — and was refused with
`[Error] The element no. 1 is an element type in which Pressure loads cannot be
assigned`, which is true of the seed's beam 1 and not of its plate 4. Moving
the payload to key `4` stored it.

So the server resolved the element from the `Assign` key, and `ITEMS[].ID`
echoed back. `DbResource.create()` already keys by id, so both SDKs send this
correctly; what the run corrects is the reading of the confirmed fixture, whose
`ID` field looks like the selector and is not.

## 2026-09-03 (later still) — what the manual's "Create Only" actually means

`Create Only` appears in exactly two Required cells in the whole manual, and
both are a field named `CALC_OPT`: `/db/SECT`'s `SECTTYPE: "VALUE"` branch
(default `true`) and `/db/SPFC`'s design-spectrum branch (default `false`).
The extractor does not recognise the value and emits a note instead of a
requiredness, so `/db/SECT` and `/db/SPFC` have both been sitting on it.

Measured on Gen NX against an empty document, with every record deleted by id
afterwards. `/doc/NEW` was neither needed nor called.

**The two rows say the same thing and the product means two different things
by it.** That is the finding: "Create Only" cannot be read off the manual into
a contract as one shared semantic, because the manual's own two uses of it do
not agree with each other.

### `/db/SECT` — literal, and it leaves stale stiffness behind

`CALC_OPT` is not a stored property. No GET on any of the seven sections
created here returned the key. What it does is decide whether the server
computes `SECT_I.STIFF` (`AREA`, `ASY`, `ASZ`, `RXX`...) and `SECT_I.DESIGN`
from `vSIZE`, and it decides that **only on POST**:

| POST | `STIFF` in the body | result |
| --- | --- | --- |
| `CALC_OPT` omitted | absent | computed from `vSIZE` |
| `CALC_OPT: true` | absent | computed from `vSIZE` |
| `CALC_OPT: false` | absent | **refused** - `[Error] Section input data contain errors.` |
| `CALC_OPT` omitted | present | stored verbatim |
| `CALC_OPT: true` | present | stored verbatim |
| `CALC_OPT: false` | present | stored verbatim |

So the documented default `true` is confirmed, and `false` is a real gate — it
forbids the computation, which is why it fails when there is nothing to fall
back on. But a supplied `STIFF` wins under every value, including `true`:
`AREA: 0.999` on a 0.3 m H section was stored as `0.999`.

The asymmetry that names the row is exact. **The identical body that POST
refuses is accepted as a PUT:**

```text
POST {"CALC_OPT": false, ...no STIFF}  ->  [Error] Section input data contain errors.
PUT  {"CALC_OPT": false, ...no STIFF}  ->  accepted, record keeps the STIFF it had
```

And `CALC_OPT: true` on a PUT does not compute anything:

| step | `vSIZE[0]` | `STIFF.AREA` |
| --- | --- | --- |
| POST, `CALC_OPT` omitted | 0.3 | 0.004533 (computed) |
| PUT to 0.9, `STIFF` stripped, no `CALC_OPT` | 0.9 | 0.004533 |
| PUT to 0.9, `STIFF` stripped, `CALC_OPT: true` | 0.9 | 0.004533 |
| POST a fresh section at 0.9 | 0.9 | **0.008433** |

A section deliberately corrupted to `AREA: 0.777` stayed at `0.777` through a
PUT with `CALC_OPT: true` and `STIFF` stripped.

⚠️ **Resizing a `VALUE` section through PUT leaves the model carrying the new
dimensions with the old section properties** — 200, no error, and the record
reads back looking self-consistent unless the caller knows what `AREA` should
have become. Same silent-corruption family as `/db/CONS` truncating an
8-character `CONSTRAINT` and `/db/MVHL`'s empty `VEH_DEFAULT` no-op. Deleting
and re-POSTing is the only way to recompute through the API.

### `/db/SPFC` — the same words, and "Create Only" is wrong

Here `CALC_OPT: true` is what makes the server build the 103-point `aFUNC`
spectrum from the code parameters in `STR`/`OPT`/`VAL`. Omitted or `false`
with no `aFUNC` supplied is refused:

```text
[Error] Spectrum Function Data (Name:KDS_None) contains errors.(Item:Spectrum Data)
```

Which means **the manual's own KDS(41-17-00:2019) worked example does not
run** — it omits `CALC_OPT` and supplies no `aFUNC`. Registered as MD-15.

Unlike `/db/SECT`, `CALC_OPT` is fully honoured on PUT. Starting from a record
whose `aFUNC` had been hand-set to a 2-point flat curve at `0.5`, against code
parameters that generate a peak of `0.0528`:

| PUT (`aFUNC` stripped each time) | stored `aSRA` | stored curve |
| --- | --- | --- |
| `CALC_OPT: true` | [0.22, 0.154] | **103 pts, peak 0.0528 - recomputed** |
| `CALC_OPT: false`, `aSRA` doubled | [0.44, 0.308] | 103 pts, peak 0.0528 - untouched |
| `CALC_OPT` omitted, `aSRA` doubled | [0.44, 0.308] | 103 pts, peak 0.0528 - untouched |

`true` on a PUT rebuilt the curve; `false` and omission left it alone. So the
documented default `false` is confirmed for this endpoint too, and the
`Create Only` cell is simply not true of it.

Rows two and three are the stale-derived-data shape again, in a milder form:
new code parameters can be stored against a curve they do not generate. Here,
unlike `/db/SECT`, the caller has a fix — resend with `CALC_OPT: true`.

`/db/SPFC` also renumbers a POSTed record, joining `/db/STLD` and `/db/TDME`.

## 2026-09-03 (later still) — `/db/MVHL`: the finding was real, the reading was not

`VEHICLE_LOAD_NUM` has been quoted in three places in this repo as a
documented value that is wrong live, and as a silent-data-corruption case
alongside `/db/CONS`. Measured properly on Civil NX, it is **neither**. It is
the endpoint's branch discriminator, and it does exactly what the manual's own
worked examples show.

| `VEHICLE_LOAD_NUM` | companion fields | result |
| --- | --- | --- |
| `1` | `VEHICLE_TYPE_NAME` + `STANDARD_CODE` | stored intact - standard DB vehicle |
| `2` | `USER_LOAD_TYPE` + `LOAD_ITEMS` | stored intact - all three axle loads kept |
| `2` | `VEHICLE_TYPE_NAME` + `STANDARD_CODE` | branch-1 fields discarded, user-defined Truck/Lane stored |
| `1` | no `VEHICLE_TYPE_NAME` | **refused** - `(Item:Length of Vehicular Load Type(0 ~ 40 characters))` |
| `3` | - | **refused** - `Wrong Field` |
| omitted | - | **refused** - `Wrong Field` |

Row three is the 2026-07-26 observation, reproduced exactly. What it shows is
not a product discarding a caller's data: it is **branch 2 ignoring branch 1's
fields**, which is what selecting branch 2 means. The manual has said so since
2026-07-30, when the KSCE-LSD15 article added a User Defined example carrying
`"VEHICLE_LOAD_NUM": 2` with `USER_LOAD_TYPE` and no `VEHICLE_TYPE_NAME`.

Sent properly, branch 2 is not lossy at all — `LOAD_ITEMS`' three axle loads
came back field for field.

This is the fourth finding in the same family as the retracted B-1/B-2/B-3 and
the iGen code names: a real observation, correctly recorded, with a conclusion
about the *manual* that the source did not support. The observation was made
before the branch was documented, and nobody re-read it afterwards.

### What is actually wrong is narrower, and it is requiredness

The common Specifications table marks every branch-1 and branch-2 field
without reference to the branch. Measured:

| field | table says | measured |
| --- | --- | --- |
| `VEHICLE_TYPE_NAME` | Required | required **only** when `VEHICLE_LOAD_NUM: 1` |
| `STANDARD_CODE` | Required | **not required at all** - omitted, accepted, stored without it |
| `USER_LOAD_TYPE` | Optional | ignored on input under `MVLD_CODE: 2`; the server always stored `"Truck/Lane"`, for `"Train"`, `"Lane"`, `"Truck"`, `"TruckLane"` and omission alike |

Same shape as `/db/FIMP`'s table stating child keys without their parents.
Registered as MD-16. `STANDARD_CODE` confirms by a write what
`VehiclePayload`'s docstring already recorded from a read of a real Eurocode
model: its Load Model 1 entry carries no `STANDARD_CODE` key at all.

### Two things that are not validated on write

- `STANDARD_CODE` is checked against its own enum — `"NOT-A-CODE"` answers
  `Wrong Field` — but **not against the vehicle or the moving-load code**.
  `"KS-RB"` was accepted and stored on an `MVLD_CODE: 2` (AASHTO LRFD)
  `HL-93TRK` vehicle.
- `VEHICLE_TYPE_NAME` is **not validated at all**. `"NOT-A-VEHICLE"` was
  accepted and stored verbatim. Since that name is what selects which standard
  vehicle's axle loads the analysis uses, a typo here is silent.

`/db/MVHL` renumbers a POSTed record too — keys 10-14, 20, 21 landed at ids
4-10.

## 2026-09-03 (patch) — build 09/02/2026 on both products, and a read-only sweep from each SDK

The author installed the latest patch mid-session and read the build off each
product's About dialog:

| product | version | build |
| --- | --- | --- |
| MIDAS Gen NX 2026 | v2.1 | 09/02/2026 |
| MIDAS Civil NX 2026 | v2.2 | 09/02/2026 |

**The API still does not report this.** `/mapikey/verify` answers only
`{"user", "program", "connectionID", "keyVerified", "status"}`, and
`/doc/VERSION`, `/doc/INFO`, `/version` and `/doc/ABOUT` all 404 on both
products after the patch as before it. So the About dialog remains the only
source, and a build string can only be attached to a session someone was
watching. That is why the four records written earlier today say the build is
unknown rather than citing 09/02/2026: those runs happened before this patch
was installed, and back-stamping them with a build that did not exist yet
would turn a gap into a false citation. `schema/info-schemas.json` and
`schema/hyper-s-info.json` keep `nxVersion: null` for the same reason.

Both sessions survived the patch: the `connectionID`s (`tZwG5G-fSg` for Gen,
`maTuEDSLQw` for Civil) were unchanged afterwards.

### The sweep, run from a different SDK per product

Deliberately split, so each language surface drove a real product rather than
both being checked by the one that is easier to script:

| product | driver | resources | result |
| --- | --- | --- | --- |
| Civil NX | Python, `scripts/live_readonly_sweep.py` | 282 GET-capable | **282 ok, 0 failed** |
| Gen NX | npm, the built `dist/` walked resource by resource | 268 declare gen, 267 serve GET | **267 ok, 0 failed** |

No route moved, disappeared or changed shape across the patch, on either
product or through either SDK.

On Gen, 261 tables were empty and six carried data — `/db/UNIT`, `/db/STYP`
and the four colour tables `/db/CO_F`, `/db/CO_M`, `/db/CO_S`, `/db/CO_T`.
Those are what any document has: units and a structure type are not optional,
and the colour tables are product defaults. They are not residue from this
session's earlier write probes, all of which were deleted by id and confirmed
empty before the patch went on.

The npm sweep was written for the session at first, because
`packages/typescript/scripts/` carried only `live-crud.mjs` and
`live-analysis.mjs`, both of which call `/doc/NEW` and discard unsaved work -
so the npm package had no safe harness at all. [Corrected 2026-09-20: only
`live-crud.mjs` calls `/doc/NEW`. `live-analysis.mjs` never has - `git log -S`
finds no `newProject` in it, ever. It is still unsafe against a model you care
about, because it adds a column to the open document and runs a solve before
deleting what it added, but it does not discard the document. The conclusion
this paragraph draws - that the npm package needed a GET-only harness - is
unaffected.] It has one now:
`packages/typescript/scripts/live-readonly.mjs`, `npm run live:readonly`,
committed the same day and re-run against both products to the same counts.

Having one per SDK is not duplication. Each imports its own package, so a
wrong endpoint string, a wrong product gate or a broken response unwrapping in
that package answers 404 there and nowhere else - the Python sweep cannot see
an npm defect. That the two agree exactly (282 Civil, 267 Gen) is itself the
cross-check.

## 2026-09-03 (patched build) — MD-14's two Japan code names, re-measured on 09/02/2026

The earlier `/db/TDME` probe ran before the 09/02/2026 patch was installed, so
its build was never recorded. This re-runs the narrow part of it against a
build both About dialogs name — MIDAS Gen NX 2026 (v2.1) and MIDAS Civil NX
2026 (v2.2), both build 09/02/2026 — because "we do not know which build that
was" is a weak place to leave a claim that a documented value does not work.

Both documents were confirmed empty first (`GET /db/NODE`, `/db/ELEM`,
`/db/MATL`, `/db/TDME` all `{"message": ""}`), so no `/doc/NEW` was needed or
called. The payload is `live_crud_check.py`'s confirmed `/db/TDME` case with
`CODENAME` varied and nothing else. Both tables were empty again afterwards,
each record deleted by the id a `GET` reported.

| sent | Gen NX | Civil NX |
| --- | --- | --- |
| `CEB-FIP(2010)` (control) | **stored** | **stored** |
| `Japan(hydration)`, name only | `Wrong Field` | `Wrong Field` |
| `Japan(hydration)` + `TENS_STRN_FACTOR`, `bUSE`, `A`, `B`, `D` | `Wrong Field` | `Wrong Field` |
| `Japan(elastic)`, name only | `Wrong Field` | `Wrong Field` |
| `Japan(elastic)` + `iECTYPE` | `Wrong Field` | `Wrong Field` |

**MD-14 stands, on a build that is now on the record.** The control stored on
both products in the same session, so the write path was working and the
refusal is about the value.

**One thing is new.** The earlier pass varied only the spelling — seven of
them. This pass supplied each branch's own documented companion fields as well,
and the answer did not move: still `Wrong Field`, never `[Error] ... input data
contain errors`. Those two error strings are this file's standing diagnostic
pair — the second means the value was recognised and its companions were wrong.
Getting the first with the companions present rules out the remaining reading
in which the code name is known and only its extra fields were missing. What
is left is the value itself being unknown to this API, which is what "these are
iGen's" predicts.

A live call cannot confirm *why*, and this one does not try to. That the two
codes belong to iGen is the author's knowledge (2026-09-03); what a probe can
establish is that the refusal is real, reproducible on a known build, on both
products, and not an artefact of the companion fields. It is.

## 2026-09-03 (patched build) — the three uncontractable Hyper-S endpoints, re-checked

"Uncontractable in principle" is a strong claim, and it was resting on an
`/info` capture dated 2026-09-02 — the day before the 09/02/2026 patch went on.
Re-probed on the patched build. GET only.

| | Civil NX v2.2 | Gen NX v2.1 |
| --- | --- | --- |
| `/info/db/IEHG-BEAM-M1` (control) | schema returned | 404 |
| `/info/db/MATL-M1` (control) | schema returned | 404 |
| `/info/db/IEHG-GL-M1` | **404** | 404 |
| `/info/db/IEHG-PSS-M1` | **404** | 404 |
| `/info/db/IEHG-TRUSS-M1` | **404** | 404 |
| `GET /db/IEHG-{GL,PSS,TRUSS}-M1` | `{"message": ""}` | 404 |

**Nothing moved.** The claim stands, and now on a build that is on the record.

The controls are what make that worth writing down. `/info/db/IEHG-BEAM-M1` —
the sibling in the same family, same chapter, same product — answers in the
same session, so the 404 on the other three is a property of those three
endpoints rather than of the session, the key or the build.

Two things this re-confirms rather than discovers. The routes themselves are
served on Civil: `GET /db/IEHG-GL-M1` answers `{"message": ""}`, so these are
real endpoints with no schema route, not absent ones — already recorded, and
still true. And Gen 404s on every row including both controls, which is
`HYPER_S_ONLY` behaving as `db/base.py` documents.

So the three keep no permitted source: the manual gives them a URL and a
methods line, `/info` gives nothing, and this repo does not read a request
shape out of an SDK. They stay uncontracted until one of those changes.

## 2026-09-03 (patched build) — the standing write failures, re-asked

A new build can fix things, so the failures this repo carries forward were
re-asked rather than assumed. Payloads come from `schema/live-cases.json`, the
committed fixture the harness emits; none of these six declares a `needs` seed,
so a direct probe reproduces what the harness would send. No `/doc/NEW` — the
tables were checked empty first, and a refused write changes nothing.

| endpoint | Civil NX v2.2 | Gen NX v2.1 |
| --- | --- | --- |
| `/db/NLLP` | `Unknown Error` | `Unknown Error` |
| `/db/WVLD` | `Wrong Field` | not declared for Gen |
| `/db/GRDP` | `Wrong Field` | `Wrong Field` |
| `/db/TDMF` | `Wrong Field` | `Wrong Field` |
| `/db/RPSC` | `Wrong Field` | `Wrong Field` |
| `/db/STRPSSM` | `Wrong Field` | not declared for Gen |
| `/db/REBB` (empty item) | not declared for Civil | `Wrong Field` |

**Nothing was fixed by the patch.** Every one reproduces, with the same message
as before.

**Two of these are root-caused and five are not, and the difference matters.**
`/db/NLLP` was bisected on 2026-08-31 to a single field across four
`(APPLICATION_TYPE, APPLICATION_TYPE_D)` combinations, all answering the
identical `Unknown Error`; `/db/REBB` was tested down to a literally empty item
on 2026-08-27, which cannot contain a wrong field. Those two are product-side
by elimination. `/db/WVLD`, `/db/GRDP`, `/db/TDMF`, `/db/RPSC` and
`/db/STRPSSM` are `confirmed=False` cases whose cause has never been isolated —
this repo's own rule is that an unconfirmed failure is not an SDK defect until
someone triages the fixture, and across three earlier runs most such failures
turned out to be a fixture or a wrong documented value rather than the product.
Re-running them proves the symptom survives the patch. It does not promote any
of the five to a product defect, and this entry is not evidence for that claim.

What the re-check is worth: `db-rebb-write-path-refuses-every-payload` now has
a `lastChecked` on a build that is on the record, and the five unconfirmed
cases are known to be still worth triaging rather than possibly already fixed.
## 2026-09-04 — `/db/NMAS`'s crash does not reproduce, on either product

Re-test of the 2026-07-29 root cause, at the author's explicit request and with
explicit consent that a crash was acceptable. Civil NX 2026 v2.2 and Gen NX
2026 v2.1, both build 09/02/2026 — see the build note at the end of this entry. **It did not crash.** Roughly 500
omitted-`rmX`/`rmY`/`rmZ` writes across both products, in three escalating
rounds, and neither session ever stopped answering.

Both documents were confirmed empty first — `/db/NODE`, `/db/ELEM` and
`/db/NMAS` all returned the empty-table `{"message": ""}` — so `/doc/NEW` was
never called and there was no unsaved work at risk. Every payload came from
`scripts/live_crud_check.py`'s confirmed cases rather than being hand-written.
`verify_connection()` was not used as the liveness probe, because the relay
answers `"connected"` while a modal dialog holds the product; each probe is a
`GET /db/NODE` with a 20s timeout.

| Round | What it did | Civil NX | Gen NX |
| --- | --- | --- | --- |
| 1 | control (`NodalMass.create`, `rm*` filled) then 8 omission variants on fresh nodes: all three omitted, `mX` alone, `rmZ` alone missing, `rmX` alone missing, empty record, `PUT` | alive | alive |
| 2 | 200 sequential `POST`s with `rm*` omitted, one per fresh node, probing every 50 | alive | alive |
| 3 | an eight-node frame with real `BEAM` elements and a constraint, `rm*` omitted on every connected node, then 40 `PUT`/`DELETE`/`POST` cycles | alive | alive |

Round 3 exists because round 2 did not test what it claimed to. Its element
seed failed `Key Already Exist` on nodes that round 1 had already created, so
the elements were never made and the "connected node" writes went to nodes that
did not exist — which is what the `Unknown Error` replies in that round mean.
Rebuilt on an untouched id range, the frame came up with 8 elements on Civil and
10 on Gen, and the omission still did not crash either.

**The server now applies the documented default, on both products.** The write
response is a poor witness: a full-fields `POST` echoes all six fields back, an
omitted-fields `POST` echoes back only what was sent, and reading the echo alone
suggests the record is stored without them. It is not. `GET /db/NMAS/3002` on a
record written with `rm*` omitted returns
`{"mX": 10, "mY": 10, "mZ": 10, "rmX": 0, "rmY": 0, "rmZ": 0}` — identically on
Civil and Gen. So the default is applied; the write response just does not
report it. This confirms the 2026-08-13 finding, which saw the same thing on
Civil NX v2.2 build 08/12/2026 on one installation, and extends it to Gen.

Worth naming the trap, because this session fell into it: the response body of a
write is what the server accepted, not what it stored. Only a read says what was
stored.

**One long call is worth recording.** In round 2 on Civil, one of the 200 writes
took **21.7 seconds** while every other call in the same run was ~0.1s. That is
inside the 15–60s window the crash used to present as, and it is the only trace
of the old behaviour seen all day. It did not recur, and the session answered
normally immediately afterwards. Not evidence of anything on its own; recorded
because a latency spike in exactly that range on exactly that call is not a
coincidence worth discarding either.

**The workaround stays.** `NodalMass.create()`/`.update()` still fill
`rmX`/`rmY`/`rmZ` with `0.0`, and `contracts/safety/known-product-risks.yaml`
still carries the risk. Three reasons, in order of weight: one clean session on
one build on one machine does not overturn 15+ reproductions across multiple
versions, builds, models and calling machines; the products auto-update, so an
SDK release cannot assume its users are on this build or later; and the
workaround costs a caller nothing, since it sends the values the manual already
documents as the default. This repo's own rule applies — a mitigated crash risk
is still a crash risk, and `risk` and `mitigation` are separate axes.

**The build is on the record: Civil NX 2026 v2.2 and Gen NX 2026 v2.1, both
build 09/02/2026.** The author confirmed it, and the session evidence agrees
independently. `verify_connection()` returned `connectionID` `maTuEDSLQw` for
Civil and `tZwG5G-fSg` for Gen today — the same two ids the 2026-09-03 patch
entry recorded after the author read the build off each About dialog. A
`connectionID` does not survive a product restart, so both processes have been
running continuously since that reading, which is also why no auto-update can
have slipped in between. The API still reports no version itself
(`/doc/VERSION` and `/doc/INFO` 404, as that entry documents), so this is the
strongest anchor available short of reading the dialog again, and it is a
checkable one rather than an assumption.

That makes this a build MIDASIT can be given a name for. The 2026-08-13
observation was Civil NX v2.2 build 08/12/2026 on one installation; this is
both products on 09/02/2026.

**What this does not establish.** Not that the defect is fixed: an
uninitialized-value read is exactly the kind of bug that hides when memory
happens to be zero, and the scratch documents here were about as clean as a
session gets. It establishes that it no longer reproduces on demand, which is
weaker and still worth knowing — the vendor report's A-1 can say so.

The model left behind on each product is a scratch document holding ~230 nodes,
8–10 beam elements and their nodal masses. Nothing was deleted; both documents
were empty throwaways when the run started.

## 2026-09-04 (later) — the two unresolved `/post/TABLE` spellings, compared live

POST-shaped reads only: no `/doc/NEW`, model mutation, export path or deletion.
The calls used `midas_nx.post.base.get_table()` with an empty `TABLE_NAME` and
sent each spelling of each disputed `TABLE_TYPE` against the same open document.
Both products were connected under the same continuously-running sessions
recorded above: MIDAS Gen NX 2026 v2.1 and MIDAS Civil NX 2026 v2.2, both build
09/02/2026 (`connectionID` `tZwG5G-fSg` and `maTuEDSLQw`, respectively).

| `TABLE_TYPE` sent | Gen NX body | Civil NX body |
| --- | --- | --- |
| `BEAMFORCESTP` | `{"error":{"message":"[empty] Cannot generate table data as there is no analysis result."}}` | `{"error":{"message":"[empty] Cannot generate table data as there is no analysis result."}}` |
| `BEAMFORCESIP` | `{"error":{"message":"MIDAS GEN NX there was an error creating utbl. (ex PostMode ...)"}}` | `{"error":{"message":"MIDAS CIVIL NX there was an error creating utbl. (ex PostMode ...)"}}` |
| `REACTIONSURFACESPRING` | `{"error":{"message":"MIDAS GEN NX there was an error creating utbl. (ex PostMode ...)"}}` | `{"error":{"message":"MIDAS CIVIL NX there was an error creating utbl. (ex PostMode ...)"}}` |
| `REACTIONLSURFACESPRING` | `{"error":{"message":"[empty] Cannot generate table data as there is no analysis result."}}` | `{"error":{"message":"[empty] Cannot generate table data as there is no analysis result."}}` |

The distinction is stable across products: `Cannot generate ... no analysis
result` means the product recognised the table type but the scratch document
could not provide its data; `there was an error creating utbl` is the response
for the unrecognised spelling. This independently repeats the older Gen-only
`BEAMFORCESTP` finding and settles the direction of both contradictions as
measurements: `BEAMFORCESTP` and `REACTIONLSURFACESPRING` are recognised.
Per the handoff boundary, the contracts and their `resolved` flags were not
changed here.

## 2026-09-04 (last) — the 18 existing unconfirmed CRUD cases re-run; `/db/STRPSSM` closed

Both open documents were confirmed empty before the first destructive call:
`GET /db/NODE` and `GET /db/ELEM` each returned `{"message": ""}` on Gen and
Civil. The runs then used `scripts/live_crud_check.py` in batches of at most
eight, with its own seeded throwaway model and save-before-`/doc/NEW`
checkpoint under `C:/temp`. Every payload came from the harness's contract-led
case definitions; none was composed at the prompt. The harness saved each
resulting scratch model and restored an empty document after every batch.

The products were the continuously running sessions already tied to their
About dialogs: Gen NX 2026 v2.1 and Civil NX 2026 v2.2, both build 09/02/2026
(`connectionID` `tZwG5G-fSg` and `maTuEDSLQw`).

| Endpoint | Gen NX | Civil NX | Classification |
| --- | --- | --- | --- |
| `/db/ACTL` | create refused | update completed, updated value did not read back | remains unconfirmed |
| `/db/CGLP` | blocked by prerequisite seed | blocked by prerequisite seed | remains unconfirmed |
| `/db/DOEL` | create response accepted, record absent on GET | create response accepted, record absent on GET | remains unconfirmed |
| `/db/EPSE` | create refused | product-specific case not selected | remains unconfirmed |
| `/db/EPST` | create refused | prerequisite seed refused | remains unconfirmed |
| `/db/FBLA` | create refused | create refused | remains unconfirmed |
| `/db/HPCE` | create refused | create refused | remains unconfirmed |
| `/db/MADO` | create response accepted, record absent on GET | create response accepted, record absent on GET | remains unconfirmed |
| `/db/MVCT` | create refused | create refused | remains unconfirmed |
| `/db/NLLP` | `Unknown Error` | `Unknown Error` | remains unconfirmed |
| `/db/NLNK` | blocked by NLLP seed | blocked by NLLP seed | remains unconfirmed |
| `/db/NLNK-M1` | product-specific case not selected | blocked by NLLP seed | remains unconfirmed |
| `/db/RPSC` | `Wrong Field` | `Wrong Field` | remains unconfirmed |
| `/db/SBDO` | create response accepted, record absent on GET | create response accepted, record absent on GET | remains unconfirmed |
| `/db/STCT` | create response accepted, record absent on GET | create refused against the auto-populated stage-control record | remains unconfirmed |
| `/db/STRPSSM` | not served for Gen | **full CRUD round trip passed** | promoted to write-confirmed |
| `/db/TDMF` | create refused | create refused | remains unconfirmed |
| `/db/WVLD` | product-specific case not selected | create refused | remains unconfirmed |

Two fixtures were stale against the live-corrected contracts and were repaired
before the final isolated run. `/db/RPSC` now sends longitudinal reinforcement
at `MBARS[].MBAR_ITEMS[]` while leaving `SBAR_ITEMS` at the root (MD-40); it
still returned `Wrong Field` on both products, so no conclusion beyond the
observed failure is claimed. `/db/STRPSSM` now sends `{Y, Z}` points rather
than the manual's erroneous `{PY, PZ}` spelling (MD-38). On Civil it then
passed POST, GET, PUT, GET, per-id DELETE, and deletion verification using
section id 1. This isolates the former failure to the stale point-key shape.

Result-state changes: `schema/live-cases.json` remains 167 cases and moves from
143 to **144 confirmed**; repository coverage moves from 172 write / 227 read
to **173 write / 226 read**. No other endpoint was promoted, and no failed
unconfirmed case is labelled an SDK or product defect.

## 2026-09-05 — npm public-API CRUD evidence extended from 23 to 32 DB endpoints

Ran the built npm 2.7.7 package through
`packages/typescript/scripts/live-crud.mjs`, not raw HTTP and not Python. Each
run supplied `--save-dir C:/temp`; the harness checkpointed the open document,
called `/doc/NEW`, verified NODE/ELEM were empty, used only cases emitted in
`schema/live-cases.json`, deleted each test record through the public
resource's per-id `delete()` method, saved the throwaway model separately, and
restored an empty document. Batches never exceeded eight endpoints.

The same nine previously unrecorded resources completed create, read-back,
update, updated read-back, individual delete, and deletion verification on
both MIDAS Gen NX 2026 v2.1 and MIDAS Civil NX 2026 v2.2, build 09/02/2026:

| Public npm resource endpoint | Gen | Civil |
| --- | --- | --- |
| `/db/MVCD` | pass | pass |
| `/db/TDGR` | pass | pass |
| `/db/NPLN` | pass | pass |
| `/db/ETFC` | pass | pass |
| `/db/CCFC` | pass | pass |
| `/db/HSFC` | pass | pass |
| `/db/MLFC` | pass | pass |
| `/db/CUTL` | pass | pass |
| `/db/CLWP` | pass | pass |

This is evidence for the installed-user path that generated metadata alone
cannot provide: resource discovery through `resources.db`, request wrapping,
response unwrapping, stored-value checks, PUT handling, and per-id deletion all
ran through the built package. The npm inventory therefore moves from 23 to
**32 distinct `/db` endpoints**, plus the existing four result-table
operations (36 public-API operations total). `docs/coverage.json` stays
unchanged because its current rows record product endpoint evidence rather
than which language client supplied it; adding a language-evidence dimension
would be a schema decision, not a live-run side effect.

The wider selection also exposed a harness boundary that must not be called an
SDK regression. Python's live checker constructs a common base model before
its cases; `schema/live-cases.json` currently emits explicit per-case setup but
not that common model, while the npm checker begins from a genuinely empty
document. Consequently CNLD, BMLD, CONS, ESSF, SECF, TSGR and TDMT could not
resolve their node/element/material/section preconditions; GSTP, TDME, IFGS,
THGC, THFC and SPFC likewise did not persist without the base model; and the
LCOM-GEN/LCOM-CONC fixtures referenced load case `DL`, which did not exist.
The npm script prints `REGRESS` because these cases are confirmed in the
Python-driven fixture, but this run does **not** establish a package regression:
the two harnesses did not create equivalent starting models. `/db/GRUP` was
also rejected locally before its write because it has no DELETE operation and
the npm harness deliberately refuses cases it cannot clean up. None of these
attempts is included in the 32-endpoint count. Final direct GETs returned
`{"message": ""}` for NODE and ELEM on both products, independently confirming
that both sessions were left on empty documents.

## 2026-09-05 (later) — every historical non-TEMP crash path re-checked; zero crashes

The author clarified the scope as endpoints that have **not** been moved under
`/TEMP`. Accordingly `/TEMP/DESIGN/SRC/AIK-SRC2K/OCHECK` was deliberately not
called and its standing risk was not changed. Everything else with a recorded
product-crash history was re-run against the same continuously-running Gen NX
2026 v2.1 and Civil NX 2026 v2.2 sessions, both build 09/02/2026. Every risky
call was followed by a real `GET /db/NODE`; `verify_connection()` alone was not
used as proof of liveness.

| Historical crash path | Gen NX | Civil NX |
| --- | --- | --- |
| `/post/TABLE`, all eight Design Forces `TABLE_TYPE`s | all returned `{"message": ""}`; alive after each | all returned the normal `there was an error creating utbl` no-result error; alive after each |
| `/DESIGN/RC/KDS-41-20-2022/TABLE`, Column/Brace/Beam | all returned empty dictionaries; alive after each | all returned the normal `there was an error creating utbl` no-result error; alive after each |
| `/ope/EDMP` | returned clean `Unknown Error`; alive | returned clean `Unknown Error`; alive |
| `/ope/USLC` | `command complete`; alive | `command complete`; alive |
| `PUT /db/THNL` | full create/read/update/read/delete/read round trip passed | full create/read/update/read/delete/read round trip passed |
| raw `POST /db/NMAS` with `rmX`/`rmY`/`rmZ` omitted | returned, GET stored all three as `0`; alive | returned, GET stored all three as `0`; alive |

The eight `/post/TABLE` values were `BEAMDESIGNFORCES`,
`COLUMNDESIGNFORCES`, `BRACEDESIGNFORCES`, `WALLDESIGNFORCES`,
`STEELMEMBERDESIGNFORCES`, `SRCBEAMDESIGNFORCES`,
`SRCCOLUMNDESIGNFORCES`, and `COLDFORMEDSTEELMEMBERDESIGNFORCES`. This is the
independent later-build re-test their docstrings had asked for after the single
clean 2026-08-11 pass. It establishes that none reproduces its old blank-model
crash on the current build. It does not claim that a populated, analysed and
designed production model exercises the same product path.

EDMP and USLC used the exact prior crash-reproduction setup recorded on
2026-08-07: the repository's common disposable model seed plus a real concrete
load combination. THNL used its confirmed `schema/live-cases.json` case through
`scripts/live_crud_check.py`. NMAS bypassed the SDK normalizer intentionally:
its body was derived from the shared confirmed case with only the three
rotational-mass fields removed. The old NMAS mitigation therefore remains in
both SDKs despite another clean raw call.

All modified models were checkpointed under `C:/temp` with their product-native
extensions before cleanup. Final direct NODE/ELEM reads on both products were
empty. The many `/doc/NEW` calls involved in the isolated harnesses also
returned cleanly, but this was not a large-real-model reproduction of that
endpoint's old crash and is not claimed as one.

## 2026-09-05 — Task 1 shared-model harness disagreement rechecked

Both products answered direct `GET /db/NODE` and `GET /db/ELEM` with empty
documents before this run. Gen's built npm 2.7.8 harness then replayed the
version-4 shared fixture, printing `BUILT base model (9 steps)`, for the
two cases that had disagreed in the earlier session:

| Endpoint | npm on Gen | Python on Gen, same selection |
| --- | --- | --- |
| `/db/TDMT` | `id 3 missing after POST` | full create/read/update/read/delete/read PASS |
| `/db/GSTP` | `id 3 missing after POST` | full create/read/update/read/delete/read PASS |

npm exited 1; Python exited 0. Both harnesses saved their throwaway models
under `C:/temp` and restored an empty document. Civil received no mutations
in this recheck. Product builds were not queried again in this run; no new
build-specific claim is made.

An offline comparison identifies the setup difference: Python's main loop
runs **every seed in each selected tier**, regardless of the selected cases'
`needs`. npm's `runCase` replays only the case's emitted `setup`. Both of
these cases had empty `needs` and `setup` in `schema/live-cases.json`, so
Python's props tier created TDMT records 1 and 2 before testing record 3 and
npm did not. Sharing `baseModel` closed the common prefix and nothing else;
it never established that the harnesses begin each case in the same state.

The handoff's explicit stop-on-disagreement condition was reached. This
recheck adds no npm PASS evidence and does not classify either failure as a
package defect.

**Offline follow-up, 2026-09-05, fixture version 5.** The emitter now exports
every tier seed the npm harness can replay -- a sequence of `{"Assign": ...}`
POSTs captured from the seed step's own calls -- rather than a hand-picked
three tiers. 34 of the 37 tier seeds export; the three that do not
(`pjcf_unlock`, `solid11_seed`, `stage11_seed`) read state back or delete a
record, are named in `unsupportedSeeds` with the reason, and the four cases
needing them carry `blockedSeeds` so npm refuses them instead of running them
half-seeded. Cases carrying setup went 21 to 66. A failure before the endpoint
under test is touched is now classified `BLOCK` and exits 3, the same split
the Python runner has always made, so `id 3 missing after POST` would not have
been printed as `REGRESS` under this build. **None of this is a live result.**
Whether TDMT and GSTP now agree across the two harnesses is exactly what the
next live session has to answer, and the products' builds were not queried
again here.

## 2026-09-05 — Task 1 closed live: the two harnesses now agree, and one Python-side collision surfaced

Fixture version 5, npm built from 2.7.8 sources. Both products answered
`GET /db/NODE` and `GET /db/ELEM` with empty documents before the session,
checked with each product's own MAPI key -- an earlier check in this session
read one key for both products and proved nothing, which is worth writing down
because `verify_connection()` answered `connected` either way.

### The fifteen, both harnesses, both products

`/db/TDMT`, `/db/GSTP`, `/db/CNLD`, `/db/BMLD`, `/db/CONS`, `/db/ESSF`,
`/db/SECF`, `/db/TSGR`, `/db/TDME`, `/db/IFGS`, `/db/THGC`, `/db/THFC`,
`/db/SPLC`, `/db/LCOM-GEN`, `/db/LCOM-CONC`.

| harness | Gen | Civil |
| --- | --- | --- |
| npm `live:crud` | 15 PASS | 15 PASS |
| `live_crud_check.py` | 15 PASS | 14 PASS, 1 blocked (below) |

`BUILT base model (9 steps)` printed on every npm run. **The two cases that
disagreed on 2026-09-04 -- `/db/TDMT` and `/db/GSTP` -- now pass on both
harnesses.** They failed `id 3 missing after POST` because npm replayed no tier
seed, so the records the case counts on were never created; version 5 emits
them and the symptom is gone. The remaining eleven of the original thirteen,
plus `/db/LCOM-GEN` and `/db/LCOM-CONC`, pass as well.

### `/db/SPLC` on Civil: a fixture collision, not a regression

Selecting extras4 and extras5 together on Civil answers **`POST /db/SPLC -> 201
with an error body: Key Already Exist`**. Alone, the same case passes on the
same product in the same session.

The cause is a cross-tier id collision that predates this work and had simply
never been selected together. `_extras4_seeds`' `lcom_seismic_splc` is
Civil-only and creates `/db/SPLC` id 1; extras5's Civil `/db/SPLC` case owns id
1 too. The Python runner executes **every seed step of a selected tier**
regardless of any case's `needs`, so choosing both tiers hands the case's id to
a seed. Gen never sees it because that seed does not run there.

Requesting a different id is not a fix: this load-case family renumbers a
requested `Assign` key to the next free slot (confirmed live 2026-08-16, see
`_extras5_seeds()`), so a case asking for id 2 would land at 1 when extras4 was
not selected and fail its own read-back.

What changed is the **classification**. `_run_case` now checks whether the
case's id is already present before creating it, and reports `BLOCK` (exit 3,
"fixture problem") rather than `REGRESS` (exit 1, "treat as an SDK defect").
Verified live in both directions on Civil: the two-tier selection prints
`BLOCK /db/SPLC` and exits 3, the single-case selection still prints `PASS` and
exits 0. The npm harness has refused a setup collision since it was written;
this is the same refusal on the side that had been calling it a regression.

**The underlying collision is still there and still needs a decision.** Nothing
about the endpoint is in doubt -- the shape passes on both products whenever
either tier runs alone.

## 2026-09-05 — Task 4: the seventeen re-probed on build 09/02/2026, and what the fixtures themselves say

Every recorded reason in this file is a lead rather than a conclusion, so the
seventeen `/db` endpoints that have a live case and have never passed were run
again against the current builds. **All of them still fail**, and two were
probed field by field rather than only re-run.

| endpoint | Gen, build 09/02/2026 |
| --- | --- |
| `/db/ACTL` | `Wrong Field` |
| `/db/EPSE`, `/db/EPST`, `/db/RPSC`, `/db/TDMF` | `Wrong Field` |
| `/db/HPCE` | `Wrong Key` |
| `/db/FBLA`, `/db/MVCT`, `/db/NLLP` | `Unknown Error` |
| `/db/MADO`, `/db/DOEL`, `/db/SBDO` | POST accepted, record absent on read-back |
| `/db/CGLP`, `/db/NLNK` | blocked; their `nllp_seed`/`glink_seed` fail first |

### `/db/ACTL`: both halves of the old finding reproduce

The 2026-08-16 entry recorded Gen refusing every POST and Civil never
persisting `TOL`. Both hold on build 09/02/2026, and the Gen half was narrowed:
three payloads were sent, each derived from committed sources rather than
written by hand — the fixture as committed, the fixture filtered to the fields
the contract tags for Gen, and the two fields the contract marks `required`.
**All three answer `Wrong Field`.** Civil accepts all three and reads back
correctly, then fails `read_updated`: `updated to 0.0005, read back 0.001`.

So the fixture is not the explanation on either product. `/db/ACTL` is a
product-behaviour item, not a coverage one.

### `/db/FBLA`: the obvious suspect is not the cause

Its payload carries `LOAD_ANGLE`, which no contract records. Sending the
contract's seven keys without it answers the same `Unknown Error` on both
products, so the extra key is a real fixture defect and **not** why the call
fails.

### The check that should have existed: fixtures against contracts

Chasing those two made the gap obvious. This repository compares contracts
against both SDKs, against `/info`, and against the manual, and had **nothing
comparing them against the fixtures** — the fourth artefact claiming to know an
endpoint's shape, and the one deciding what a live run actually sends.

`scripts/check_fixture_contract.py` does. **Its first three counts were all
wrong, each for its own reason, and the sequence is the finding worth keeping.**

| reported | when | what was wrong with it |
| --- | --- | --- |
| 64 contract gaps | 2026-09-05 | counted `safeToOmit: true` fields, which are *already* the record of an accepted call that omitted them |
| 81 total, 54 + 27 | 2026-09-05 | the checker read only `document["fields"]` and ignored `appliesWhen` |
| **41 + 2** | 2026-09-06 | current |

The second correction removed 38 findings and is the instructive one, because
every one of them read as a hard defect and none was:

- **A name declared in a `variant` counted as recorded nowhere.** `/db/EIGV`'s
  `FRMIN`, `FRMAX`, `iFREQ`, `bMINMAX` and `bSTRUM`, `/db/THIS`'s `DALL`,
  `/db/NBOF`'s `KEY_NODE_ITEMS`, `/db/PNLD`'s `AREALOAD`, `/db/NLCT`'s three
  and `/db/FBLA`'s `LOAD_ANGLE` are all declared in a variant of their own
  contract. The list that was written up as "21 wire names an accepted round
  trip sent that no contract records" was, almost entirely, a checker that had
  not looked in the right place.
- **A `required` field carrying an `appliesWhen` counted as missing from every
  payload**, rather than from the branch that selects it. `/db/NLNK`'s four and
  `/db/HSFC`'s two already carried their condition.

`/db/MVCT`'s `DIST` has no `appliesWhen` and is still reported, which is what
separates this from silencing the check.

What survives is **41 fixture leads across 5 endpoints** — `/db/ACTL`,
`/db/GRDP`, `/db/MVCT`, `/db/NLNK-M1`, `/db/TDMF` — and **2 contract gaps on
one confirmed endpoint**, `/db/SDIS`'s `LRB` and `NRB`.

**The generalization.** A checker that compares two artefacts is a third claim
about the shape, and it is wrong until something disagrees with it. This one
was believed for a day, written into a release note, and handed to another
agent as a task list, on nothing but its own output. A new checker's first
findings are a hypothesis; confirm a sample of them against the artefacts by
hand before reporting a count as a fact.

Both lists are held as a baseline in CI, in both directions: a new finding
fails, and so does one that disappears without being recorded. Nothing was
merged from them — a fixture is never a source for a contract.

## 2026-09-06 — chapter 08 moving-load and lane family, both products

Thirteen `/db` endpoints from chapter 08 gained a live case, replaying the
manual's own JSON examples from `scripts/fixtures/*.json` with only the model
references remapped to the seeded base model. Both documents were confirmed
empty first, with each product's own MAPI key.

| endpoint | Gen | Civil |
| --- | --- | --- |
| `/db/LLANtr`, `/db/MVHLtr` | PASS | PASS |
| `/db/MLSP`, `/db/MLSR`, `/db/MVLDtr` | PASS | PASS |
| `/db/SLAN` | PASS (under `BS`) | PASS (under `KSCE-LSD15`) |
| `/db/LLANch`, `/db/SLANch` | code unavailable | PASS |
| `/db/LLANid` | code unavailable | PASS |
| `/db/IMPF` | code unavailable | PASS |
| `/db/LLANop`, `/db/SLANop` | refused under `BS` | PASS |
| `/db/SINF` | POST accepted, record absent | POST accepted, record absent |

**Which moving-load code a product offers decides most of this table.**
`POST /db/MVCD` answers `[Error] ... (Item:Unavailable moving load code)` on Gen
for `CHINA`, `INDIA` and `KOREA`, so the lanes those codes exist for cannot be
written there at all. That is a product capability, not a payload defect, and
the cases are split per product rather than carrying a payload that fails on
one of them. `BS` is the code chapter 08 lists for the general/optimization
family on Gen, and under it `/db/SLAN` passes while `/db/LLANop` and
`/db/SLANop` are still refused.

### The tiers could not be run together, and that was the finding

Every lane tier seeds the same single-row `/db/MVCD` selector with its own
`CODE`, by POST. The first tier in a selection wins and every later one answers
`Key Already Exist`, taking its whole tier down with it: selecting four lane
tiers on Gen left one running and blocked five cases that pass individually.
`/db/MLSP`, `/db/MLSR` and `/db/MVLDtr` looked like failures for that reason
alone.

The seed now POSTs and falls back to PUT on the refusal — `/db/MVCD` declares
PUT, and the record is a selector rather than a table, so changing it is what a
second tier means. Four lane tiers selected together on Gen then pass all five
cases where one had passed before.

**It POSTs first deliberately rather than reading the record and branching.**
Reading state back would have made the seed one the npm harness cannot replay
from an emitted payload, which is how `pjcf_unlock`, `solid11_seed` and
`stage11_seed` came to be excluded — so branching would have taken all thirteen
of these cases away from npm to fix a Python-only collision. The first attempt
did exactly that and the emitter caught it.

This is the same collision class as `/db/SPLC`'s, and the second one found in
two days: a seed that owns a fixed id is a shared resource whether or not it
was written as one.

### What is not claimed

`/db/SINF` accepts its POST on both products and the record is absent on read
back, so it stays read-level and unconfirmed. `/db/MVLDbs`, `/db/MVLDch`,
`/db/MVLDeu` and `/db/MVLDid` have **no live case**; an earlier draft of this
work recorded them as write citing `live_crud_check.py`, and that citation had
no case behind it, so they are back at read.

## 2026-09-06 — moving-load controls pass; country load cases remain unresolved

The Gen NX 2026 v2.1 and Civil NX 2026 v2.2 sessions - both Build 09/02/2026,
author-confirmed 2026-09-06; the entry first recorded 08/26 and 08/27, which
nothing could have measured - were checkpointed under `C:/temp`, replaced with a
throwaway base model, and restored to an empty scratch document after each
Python and npm run. The fixtures replay the first JSON Request Body from the
vendored manual commit `7920759`; the two SDKs consumed the same emitted case
data.

`/db/MVCTbs` and `/db/MVCTtr` completed create/read/update/read/delete on both
products. `/db/MVCTid` completed the same round trip on Civil; Gen does not
offer the `INDIA` moving-load code. Their manual `iIGP` and
`INFL_GEN_POINT` branches are now represented as `appliesWhen`, so the fixture
checker no longer asks a Number/Line payload to invent the mutually exclusive
Distance value. Write coverage moved from 185 to 188 endpoints, and npm DB
evidence from 55 to 58.

The adjacent country/code-specific load cases did not earn write evidence:

| endpoint | Gen | Civil |
| --- | --- | --- |
| `/db/MVLDbs` | not run | not run |
| `/db/MVLDch` | code unavailable | `Non-existent Vehicle ... in Sub-Load Case` |
| `/db/MVLDid` | code unavailable | `Number of Sub-Load Cases` |
| `/db/MVLDeu` | `Unknown Error` | `Unknown Error` |
| `/db/MVLDpl` | `POLAND` code unavailable | POST accepted, id 1 absent on read-back |

`/db/MVLDbs` stopped at the required offline gate: its contract currently
marks the mutually exclusive `LCDATA_*` objects required at the record root,
so the manual's own `LOADMODEL="STANDER"` example appears to omit five required
sibling branches. Expressing the two-value ALL_MODE branch with the present
condition model needs a contract-shape decision; the live case was therefore
not run and the gate was not waived.

For the four attempted endpoints, the lane records were mechanical clones of
the manual's own lane Request Body with only record ids and the lane names
referenced by the target Request Body remapped. No vehicle definition was
invented. The China result confirms that its documented vehicle label is a
model reference, not a self-contained definition. India and Eurocode still
need a manual- or `/info`-backed prerequisite before their failures can be
classified further. Poland's Civil no-persistence response is retained as an
unconfirmed product observation. Python and npm returned the same outcomes.

## 2026-09-06 — Hyper-S controls: PUT-only write verification on Civil

Civil NX 2026 v2.2, Build 09/02/2026 (author-confirmed; recorded as 08/27 at
the time, which nothing could have measured) was checkpointed under `C:/temp`, replaced
with a disposable base model, and restored to an empty scratch document after
each run. The complete `/db/THGC-M1` and `/db/THOO-M1` Request Bodies were
copied from chapter 09 at the vendored manual commit `7920759`; they were not
inferred from either SDK.

Both endpoints completed PUT/read/per-id DELETE/read through Python and the
published npm surface. They deliberately have no POST step because their
declared operations are GET, PUT, and DELETE. This moves both endpoints from
read to write evidence on Civil.

The first npm attempt exposed two harness defects rather than product defects:
the harness unconditionally called POST, and its nested-object expectation used
JavaScript reference identity. The harness now selects POST and/or PUT from the
emitted case methods and compares expected arrays/objects structurally. Unit
tests cover the nested `OUT_OPT` shape that found the latter defect. The rerun
passed both endpoints and restored the empty document.

## 2026-09-06 (later) - /ope/MEMB settled by measurement, on both products

The sibling manual repo asked for a re-check of the `ELEM_LIST` vs `AELEM`
question and was right that the 2026-08-27 record was thinner than it read.
Rather than reconstruct the missing answers, the whole thing was measured
again on Gen NX and Civil NX. Both sessions were confirmed empty first with
**each product's own key** (`verify_connection()` reporting `program: "gen"`
and `program: "civil"` respectively), and **every probe got its own
`/doc/NEW` plus a verified-empty check before the throwaway model was
rebuilt**, so no probe could see another's members. The model is
`schema/live-cases.json`'s base model; elements 2 and 3 are its two collinear
horizontal beams. Probe bodies are the article's own Request Example with the
element ids remapped.

Identical on both products:

| # | sent | POST | body | `GET /db/MEMB` after |
| --- | --- | ---: | --- | --- |
| A | `ELEM_LIST: [2,3]`, `SELECTION` | 200 | `{"MEMB": {"1": {"AELEM": [2,3], "bREVERSE": false}}}` | member created |
| B | `AELEM: [2,3]`, `SELECTION` | **200** | `{"error": {"message": "There is no valid element information."}}` | `{"message": ""}` - nothing created |
| C | `ELEM_LIST: [2]` **and** `AELEM: [3]` | 200 | `{"MEMB": {"1": {"AELEM": [2], ...}}}` | member is `[2]` |
| D | `AELEM: [2,3]`, `AUTO`/`ALL` | 200 | `{"1": {"AELEM": [1]}, "2": {"AELEM": [2,3]}}` | whole model auto-assigned |
| E | **no element list**, `SELECTION` | 200 | `{"error": {"message": "There is no valid element information."}}` | `{"message": ""}` |

**B and E are identical, down to the status code and message string.** Sending
`AELEM` is indistinguishable from sending no element list at all, which is the
signature of a key the request schema does not have - not of a bad value. That
is the cleanest form this question could have been settled in, and it took a
negative control (E) that the 2026-08-27 pass never ran.

The other three answers:

- **`SELECTION_TYPE` is not the confound it looked like.** `ALL` does ignore
  the element list (D), but it ignores `ELEM_LIST` just as thoroughly. It is
  not a condition under which `AELEM` starts working.
- **Both keys at once: `ELEM_LIST` wins and `AELEM` is ignored outright** (C),
  with no conflict and no warning.
- **The rejection is HTTP 200**, not a 4xx. One more instance of the rule, now
  with the status code written down.

Two things fell out that nobody was looking for:

- **`bREVERSE` disagrees between the POST echo and the stored record.** All
  three successful probes, both products: POST answers `"bREVERSE": false` and
  an immediate `GET /db/MEMB` returns `true` for that same member. **The POST
  response body is not the stored record**, so do not assert against it.
- **`POST /doc/NEW` with no request body is HTTP 500** - `{"error":
  {"message": "Cannot read properties of null (reading 'Argument')"}}` from the
  relay - and the document is **not** reset. It needs `{"Argument": {}}`, which
  answers `200 "... command complete"` and does clear. The first run of this
  probe ignored that status and every probe after it ran on an accumulated
  model; the results were discarded and the run above replaced them. The
  failure is loud, and it was still missed by not reading it - which is the
  argument for asserting the reset rather than assuming it.

`/ope/MEMB` moves to **write** level on both products on this run: it created
design members and the members were read back. Both sessions were left on an
empty document, confirmed on `/db/NODE`, `/db/ELEM` and `/db/MEMB`.

Product build strings are not recorded: the API exposes no endpoint that
reports them, so that one field of the sibling repo's request cannot be
answered from a script.

Full reply in `docs/ope_memb_elem_list_response.md` (removed 2026-09-17; git
history at `fa1332b`).

**Follow-up the same day: the documentation half was a locale difference, and
this repository got it wrong.** The sibling repo quoted the article's request
example as `"AELEM": [1, 2]`; the reply above re-fetched the article, found
`"ELEM_LIST": [640, 692]`, and reported their citation as mistaken. Both
readings were real. Article `49514964272665`, `updated_at`
`2026-07-30T05:16:25Z` in both cases, and the **`ko` and `en-us` locales carry
different Input JSON examples** - `ko` sends `AELEM`, `en-us` sends
`ELEM_LIST`, while both Specifications tables say `ELEM_LIST`. Recorded as
MD-52.

The live run is what settles it, and it still points the same way: `ELEM_LIST`
assigns the member, `AELEM` is not read. The `ko` example is the wrong one, and
the sibling repo has already reverted its own chapter back to `ELEM_LIST`
(`0270fad`).

The lesson is not about this endpoint. **A vendored citation records a URL but
not a locale**, so two people can transcribe the same article id faithfully and
end up with different field names - and every manual-versus-article comparison
here that fetched a single locale has the same blind spot. "I re-fetched it and
you are wrong" was reported in good faith with the raw body in hand; the step
missing from it was asking why a careful person would be reading something
else.

## 2026-09-12 - seven pending write cases completed in both SDKs

Gen NX 2026 v2.1 and Civil NX 2026 v2.2, both Build 09/02/2026
(author-confirmed), were connected with their own keys and confirmed empty on
`/db/NODE` and `/db/ELEM` before the batch. Each harness checkpointed under
`C:/temp`, built its disposable dependencies, and restored an empty scratch
document after the run.

Python and the built npm package independently completed the emitted cases for
`/db/IEPI`, `/db/EXLD`, `/db/PRST`, `/db/POLC`, `/db/MATD`, and `/db/IEHC` on
both products. Civil additionally completed `/db/POLC-M1`; that endpoint is
Civil-only. The ordinary cases completed create/read/update/read/delete/read.
`/db/MATD` declares only GET and PUT, so it completed read/PUT/read and relied
on the harness's final whole-document reset for cleanup. `/db/POLC-M1` included
POST because the earlier live observation proves that the route accepts it,
despite the chapter's normalized method list.

The fixtures came from the contracts and the Request Bodies at vendored manual
commit `7920759`; neither SDK was used as a source for the other. `/db/IEHC`
uses separate Gen and Civil cases so the Gen-only wall members never leak into
the Civil payload. `/db/POLC-M1` uses the dependency-free `ACC` branch already
represented by its contract.

### `/db/MATD`: the documented material lookup is not sufficient on this build

Two manual-derived attempts were rejected identically on Gen and Civil:

- `CODENAME="EN04(RC)"`, `CODEMATLNAME="ClassB"` returned `Rebar grade lookup
  failed`.
- Omitting the strength values returned `MAINREBAR_B_FY must be > 0`.

A GET of the disposable model's material 1 returned concrete `C24` with
`CODENAME="KS01(RC)"`, `CODEMATLNAME="C24"`, and blank rebar-code/name fields.
Using that observed lookup identity together with the manual Request Body's
positive `MAINREBAR_B_FY=500000` and `SUBREBAR_B_FY=600000` passed on both
products and both SDKs. This is recorded as product evidence, not generalized
into a contract claim: the manual's implication that these strengths are
ignored does not match the live requirement, and its `EN04(RC)` / `ClassB`
example is not usable on these builds.

The first npm run also exposed a harness safety gap: it refused every endpoint
without DELETE, even when the selected case was last and a final document reset
was requested. The harness now permits that narrow `document-reset` cleanup
mode only for the final selected case with final reset enabled; unit tests cover
both the allowed and rejected orderings. The rerun passed all seven distinct
endpoints and left both products empty.

## 2026-09-14 - GRDP completed; three B-2 failures narrowed offline

The same continuously running Gen NX 2026 v2.1 and Civil NX 2026 v2.2 Build
09/02/2026 sessions were confirmed empty, checkpointed under `C:/temp`, and
restored to empty scratch documents after every Python and npm run.

The fixture/contract comparison fell from 41 findings over five endpoints to
one finding on `/db/ACTL`. `/db/GRDP` now sends every member of the vendored
manual's complete Request Body. `/db/MVCT`, `/db/TDMF`, and `/db/NLNK-M1` now
carry the branch conditions that their manual rows state explicitly (`iIGP`,
`FTYPE`, and `REF_SYSTEM`/`INPUT_METHOD`, respectively), rather than treating
all mutually exclusive branch members as simultaneously required.

`/db/GRDP` completed create/read/update/read/delete/read through both Python
and the built npm package on both products. The first complete-payload run
showed why the older probe was misleading: the POST echo retained
`STRAIN_GROUP_ITEMS.DAMPING_RATIO=0.05`, but immediate GET stored that value and
the nested group coefficients as `0` on the disposable model. The case now
probes `FREQ_MODE_1_DEFAULT`, which does persist. An attempted update from 0.1
to 0.2 was correctly rejected because it equalled `FREQ_MODE_2_DEFAULT`; using
the manual's separately stated 0.5 completed the round trip.

`/db/MVCT` initially repeated the old `Unknown Error` on both products. An
isolated prerequisite probe then showed that selecting the manual's `AASHTO
LRFD` moving-load code was sufficient; no lane, vehicle, or moving-load case
was needed. The normal Python harness and built npm public API subsequently
completed create/read/update/read/delete/read on Gen and Civil, checkpointing
under `C:/temp` and restoring both products to empty scratch documents.

The other two did not earn write evidence. `/db/TDMF` still returns `Wrong
Field` on both products even with the chapter's CREEP/CTYPE Request Body;
`/info`'s extra `ELAST` has no documented value or request semantics, so none
was invented. Civil `/db/NLNK-M1` remains blocked before its
own call because the manual NLLP seed still returns `Unknown Error`. These are
now live/product prerequisites or documentation gaps, not offline
fixture-versus-contract mismatches.

## 2026-09-14 - EPMT is write-confirmed on Gen, rejected on Civil

The fixed manual's `/db/EPMT` Von-Mises Request Body was added as a new Task A
case. The update uses the second material name printed by that same section;
no payload value was inferred. Python and the built npm public API each
completed create/read/update/read/delete/read on Gen NX 2026 v2.1 Build
09/02/2026.

Civil NX 2026 v2.2 Build 09/02/2026 returned `Wrong Field` for the identical
POST through both SDKs. Fresh `GET /info/db/EPMT` responses from Gen and Civil
declared the same field shape, including the `VM` branch members, so `/info`
does not supply a product-specific payload correction. The Civil case remains
unconfirmed and its earlier read-only evidence remains intact. Every run was
checkpointed under `C:/temp` and restored to an empty scratch document.

## 2026-09-14 - FIMP's printed Kent & Park request is internally invalid

The fixed manual's complete `/db/FIMP` Request Body was added without changing
its values. Python and the built npm public API sent it to Gen NX 2026 v2.1
and Civil NX 2026 v2.2 Build 09/02/2026. All four POSTs returned the same
specific product error:

`Epsilon_cu > 0.8 / Z + Epsilon_co`

The request prints `ECU=0.003`, `Z=100`, and `EC0=0.002`, so it does not meet
that stated relationship. The chapter's second example repeats the same three
values and supplies no compliant alternative. No replacement was invented;
the case remains unconfirmed and `/db/FIMP` remains read-only in the coverage
ledger. Every run was checkpointed under `C:/temp` and restored to an empty
scratch document.

## 2026-09-15 - Task F npm replay, extras14 first pass

The existing confirmed fixtures for `/db/ACTL-M1`, `/db/BCGD-M1`, `/db/CJFG`,
`/db/CRGR`, `/db/DYLA`, `/db/EIGV-M1`, `/db/HHCT-M1`, `/db/NLCT-M1`, and
`/db/STCT-M1` completed through the built npm package on Civil NX 2026 v2.2
Build 09/02/2026. The same selections were re-run through Python on the same
session. All models were checkpointed under `C:/temp` and reset to empty.

The first npm pass exposed two fixture-replay defects rather than endpoint
regressions. A setup resource without DELETE was rejected even for the final
case before a guaranteed document reset; the harness now permits exactly that
cleanup mode and a unit test guards the boundary. `dl14_seed` is also marked as
the live-observed renumbering seed it is. `/db/BCGA-M1` subsequently reached
its endpoint, but its Python probe sorts server-reordered `BC_SELECT` while the
language-neutral fixture cannot yet express that comparator. `/db/DYFG` and
`/db/DYNF` require the intentionally interleaved `/db/MVCD` switch to EUROCODE;
an endpoint-only selection omits that switch. These three remain out of npm
evidence until their comparison/order semantics are represented explicitly.

## 2026-09-16 - Task F npm replay, extras1 complete

All ten `extras1` endpoints completed through the built npm package and were
then re-run through Python in the same product sessions on Build 09/02/2026.
`/db/CLDR`, `/db/CO_F`, `/db/CO_M`, `/db/CO_S`, `/db/CO_T`, `/db/PRLS`,
`/db/PZEF`, and `/db/STYP` passed on Gen and Civil. `/db/SPAN` and
`/db/STYP-M1` are Civil-only and passed there. Every run was checkpointed
under `C:/temp` and restored to an empty document.

The first npm `/db/CO_F` attempt was BLOCKED before the target call because
the emitted fixture's global seed map silently let the `extras7` seed named
`fbld_seed` replace the different `extras1` seed with the same name. Python
selects seeds inside each tier and was unaffected. The `extras7` seed is now
named `fbld7_seed`, preserving both measured payloads independently; the npm
rerun then passed on both products. This was fixture identity loss, not a
product or SDK regression.

## 2026-09-16 - Task F npm replay, extras2 complete

All ten `extras2` endpoints completed through npm and Python on Build
09/02/2026. `/db/BTMP`, `/db/EFCT`, `/db/GTMP`, `/db/IELC`, `/db/INMF`,
`/db/LDSQ`, `/db/SMLC`, `/db/SMPT`, and `/db/STMP` passed on Gen and Civil;
Civil-only `/db/PLCB` passed on Civil. Each run was checkpointed under
`C:/temp` and restored to an empty document.

The first npm pass reached neither `/db/SMLC` nor the `/db/SMPT` target because
their shared `smpt_seed` asks for id 90 and the product stores it at the next
free id. This renumbering was already documented by the Python fixture from
the 2026-08-16 live run, but the emitted fixture had not preserved that fact.
Marking `smpt_seed` as renumbering made the npm replay verify the stored seed
by its name; both targets then passed on both products.

## 2026-09-16 - Task F npm replay, extras3 complete

All six `extras3` endpoints completed through npm and Python on Build
09/02/2026. `/db/EDMP`, `/db/PSSF`, `/db/VBEM`, and `/db/VSEC` passed on Gen
and Civil; Civil-only `/db/EWSF` and `/db/STRPSSM` passed on Civil. Every run
was checkpointed under `C:/temp` and restored to an empty document. No fixture,
SDK, or product disagreement surfaced in this tier.

## 2026-09-16 - Task F npm replay, boundary complete

All eight `boundary` endpoints (`/db/ELNK`, `/db/FRLS`, `/db/GSPR`,
`/db/MCON`, `/db/NSPR`, `/db/OFFS`, `/db/RIGD`, and `/db/SSPS`) completed
through npm and Python on both Gen and Civil, Build 09/02/2026. Every run was
checkpointed under `C:/temp` and restored to an empty document. No fixture,
SDK, or product disagreement surfaced in this tier.

## 2026-09-16 - Build 09/15/2026 on both products, and the published 2.8.2 checked from both registries

Gen NX and Civil NX both moved to **Build 09/15/2026** (MIDAS Gen NX 2026 v2.1,
MIDAS Civil NX 2026 v2.2), each read from its own About dialog. This is the
first time in this file's history that the two products carry the same build
date; they have been patched on separate schedules all year, so this is a
coincidence to check rather than a rule to rely on. Everything below was run
GET only, against the documents the author had open - no `/doc/NEW`, no write
of any kind.

**What was tested is the published package, not this working tree.** Both
surfaces were installed fresh from their registries into a scratch directory
(`pip install midas-nx==2.8.2`, `npm i midas-nx@2.8.2`) and the read-only
sweeps were pointed at those installs, so a result here is what a user who
installs 2.8.2 today gets. PyPI published 2026-09-15T17:13Z, npm
2026-09-15T17:08Z.

| product | surface | swept | answered | failed |
| --- | --- | --- | --- | --- |
| Gen | PyPI `midas-nx` 2.8.2 | 268 GET-capable resources | 268 | 0 |
| Gen | npm `midas-nx` 2.8.2 | 268 of 305 declared serve GET | 268 | 0 |
| Civil | PyPI `midas-nx` 2.8.2 | 283 GET-capable resources | 283 | 0 |
| Civil | npm `midas-nx` 2.8.2 | 283 of 305 declared serve GET | 283 | 0 |

The two SDKs agree exactly on both products, as they did on 2026-09-03 at 267
and 282; the extra one on each side is `DESIGN/STEEL/DSTL`, added in 2.8.2. npm
additionally reported 6 endpoints carrying data on Gen and 7 on Civil, which is
a property of the open documents, not of the build.

### `DESIGN/STEEL/DSTL` answered on both products - the ledger's last unverified endpoint

It returned `{"message": ""}`, the documented zero-row shape, on Gen and on
Civil, through both published SDKs. Its declared `products: [gen, civil]` is
therefore confirmed rather than assumed, and `docs/coverage.json` now records
it at `level: "read"`, taking live coverage to **400/400 (200 write / 200
read)**. What this does *not* do is send it a payload: the endpoint selects a
project's steel design code, and nothing has yet put a value into it.

### The patch changed one schema, identically on both products: `/db/SECT` gains `USE_HAMBLY_EQ`

`scripts/info_baseline.py --capture` per product, then `--diff` against
`schema/info-baseline.json` (captured 2026-09-03 on Build 09/02/2026), reports
exactly one difference on each side and it is the same one - 189 pairs compared
on Gen, 210 on Civil:

```
CHANGED  /db/SECT (gen)              CHANGED  /db/SECT (civil)
  + SECT_AFTER.USE_HAMBLY_EQ (bool)    + SECT_AFTER.USE_HAMBLY_EQ (bool)
  + SECT_BEFORE.USE_HAMBLY_EQ (bool)   + SECT_BEFORE.USE_HAMBLY_EQ (bool)
```

Nothing else changed, gained or disappeared, on either product. Because both
products declare it, this is not one of the ten schema divergences and needs no
per-product tag.

The new property appears **nowhere in the manual repository** - `Hambly` does
not occur in `docs/manual/*.md` at all - and therefore in no contract and
neither SDK. That is a documentation lag one day after a patch, not a defect,
so it is deliberately **not** filed in `docs/manual_defects_register.md`.

Four things say "the article has not been revised yet" rather than "this is an
internal or beta flag", and they are worth writing down because whoever decides
what to do with the property should not have to guess again:

1. **It carries a description.** `/info` gives it as
   `{"description": " Use Hambly Eq. for Ixx", "type": "boolean"}`. Ixx is the
   torsional constant. The placeholders this API really does carry - `/db/DRLS`'s
   `DUMMY`, which `infoOnly` exists for - have no description at all.
2. **Its position is the tell.** Within `SECT_BEFORE`/`SECT_AFTER`'s 57
   properties it sits at `... USE_SHEAR_DEFORM, USE_WARPING_EFFECT,
   USE_HAMBLY_EQ, SHAPE ...`, and the first two are rows **(11) Consider Shear
   Deformation** and **(12) Consider Warping Effect** of the chapter's 공통
   Specifications table - both Boolean, both default `false`, both Optional. The
   table stops at (12). This is the third checkbox of that same group sitting in
   row (13)'s empty seat, not a flag hidden somewhere unrelated.
3. **Both products declare it identically.** A beta would more plausibly reach
   one product first; this reached Gen and Civil in the same patch.
4. **The timing needs no explanation.** The manual repo's 2026-09-15 정기 점검
   sync (`a6947a7`) and the products' Build 09/15/2026 are the same day, so the
   article simply had not been revised when the build shipped.

None of that is proof, and nothing has sent the property to the server. It
argues for *holding*, which is what a beta flag would argue for too - the two
hypotheses differ in what the next sync will show, not in what to do now.

**`schema/info-baseline.json` was deliberately left at its 2026-09-03 capture.**
Both products have now been captured on the new build and the pair would make a
valid replacement, but re-baselining is not a bookkeeping step here: CI runs
`info_baseline.py --against-contracts --check`, which fails when the set of
declared-but-uncontracted properties grows, and `USE_HAMBLY_EQ` is exactly such
a property. Committing a new baseline therefore means first deciding what
`contracts/endpoints/db-sect.yaml` says about it - `/info` is a permitted
source for a `/db/*` contract, so `requirement: unstated` is available - or
waiting for the next MIDASIT manual sync to document it. That decision is the
author's; until it is made, the 2026-09-03 baseline is still the right thing to
diff against, and this section is the record of the one property that differs.

Two things these runs do not prove, both worth restating because a clean sweep
invites the opposite reading: they prove 268 and 283 routes exist, answer and
parse on the new builds, and they prove nothing whatsoever about request
shapes, because the server never saw a payload.

### A wrinkle in the diff tool, not in the product

`--diff --product <p>` filters the *fresh* capture by product but not the
baseline, so a single-product capture reads as a wall of `GONE ... (other
product)` lines - 210 of them sweeping Gen, 189 sweeping Civil - that mean only
"this capture had no such-and-such in it". They are noise, not a finding.
Reading that output requires filtering the other product out by hand. The
per-product capture is not avoidable: the MAPI keys are per product.

## 2026-09-16 (later) - every historical crash path re-run on Gen NX Build 09/15/2026: one crashed

The author asked for the crash paths to be re-tested on the new build, then
chose the full scope including the deliberately destructive ones, on a document
they confirmed disposable. Work went least-destructive first, and every risky
call was followed by a real `GET /db/NODE` - `verify_connection()` alone was
never used as proof of liveness, because it answers `connected` through the
relay while the product is gone.

| Historical crash path | Ticket | Result on Build 09/15/2026 |
| --- | --- | --- |
| `/post/TABLE`, all eight Design Forces `TABLE_TYPE`s | - | all `{"message": ""}` in <0.5s; alive after each |
| `/DESIGN/RC/KDS-41-20-2022/TABLE`, Column/Brace/Beam | MAPI-2431 | all `{}`; alive after each |
| `PUT /db/THNL` | MAPI-2468 | full create/read/update/read/delete/read round trip **PASS** |
| `/ope/EDMP` | MAPI-2425 | clean `Unknown Error`; alive |
| `/ope/USLC` | MAPI-2426 | `command complete`; alive |
| `/db/NMAS` through the SDK (normalizer on) | MAPI-2378 | full round trip **PASS** |
| raw `POST /db/NMAS` with `rmX`/`rmY`/`rmZ` omitted | MAPI-2378 | **did not reproduce** - 201 in 0.38s, GET stored all three as `0`; alive |
| `/TEMP/DESIGN/SRC/AIK-SRC2K/OCHECK` | MAPI-2429 | 🛑 **crashed** |

Nothing was hand-written. The four `/db/*` round trips ran through
`scripts/live_crud_check.py`'s own confirmed cases; `/ope/EDMP` and `/ope/USLC`
used the 2026-07-30 crash-reproduction shapes on the repository's
`BASE_MODEL_STEPS` seed plus extras4's own `/db/LCOM-CONC` record; the raw NMAS
call ran through `docs/vendor_repro_nmas.py`, which is the vendor-facing
reproduction and bypasses the SDK entirely.

**OCHECK crashed, and that is the expected result rather than a new finding.**
Same conservative argument as every prior repro, on the repository's seed rather
than a hand-built dummy this time: the call hung 24.06s and returned 404
`Client Disconnected`, the follow-up `GET /db/NODE` answered 404 `client does
not exist`, and `verify_connection()` flipped to `disconnected`. It is worth
being precise about what is new here, because it is easy to overstate: **Gen was
already confirmed crashing on the `/TEMP/` path on 2026-08-07.** What 2026-09-16
adds is the current build, and the first Gen reproduction in over a month -
`MAPI-2429` is now reproduced across four builds and both products, still
matching MIDASIT's own "not a defect, no fix timeline" closure. No Jira action
follows; the ticket is already closed on exactly this finding.

The ordering is what makes the rest of the table mean something: the product had
just answered eleven historically-crashing calls and four full write round trips
without a stumble, so it was demonstrably healthy right up to the OCHECK call.

**Two things this does not establish.** The `/post/TABLE` and RC-TABLE families
were exercised against a document with no nodes, which is the same blank-model
shape as every clean re-test since 2026-08-11 - a populated, analysed and
designed model has still never been re-tested against them. And the raw NMAS
call not reproducing is now its third consecutive clean result, but the
normalizer stays in both SDKs: a server defect that stops reproducing is not the
same as one whose fix has been stated, and the cost of keeping the mitigation is
three fields nobody has to think about.

### Civil NX, same build, same paths - all clean, OCHECK deliberately skipped

The author extended the re-test to Civil NX (v2.2, Build 09/15/2026, document
confirmed disposable) and excluded `OCHECK`: it had just been reproduced on Gen,
it is already confirmed on Civil across three builds, and crashing a second
product proves nothing the ticket does not already say.

| Historical crash path | Result on Civil, Build 09/15/2026 |
| --- | --- |
| `/post/TABLE`, all eight Design Forces `TABLE_TYPE`s | all returned the established `there was an error creating utbl (ex PostMode ...)` no-result error; alive after each |
| `/DESIGN/RC/KDS-41-20-2022/TABLE`, Column/Brace/Beam | same no-result error; alive after each |
| `PUT /db/THNL` | full round trip **PASS** |
| `/ope/EDMP` | clean `Unknown Error`; alive |
| `/ope/USLC` | `command complete`; alive |
| `/db/NMAS` through the SDK | full round trip **PASS** |
| raw `POST /db/NMAS` with the three rotational fields omitted | **did not reproduce**, twice in the same session - 201 in ~0.4s; alive |

Every modified document was checkpointed under `C:/temp` with the product's own
`.mcbz` extension and then reset with `/doc/NEW`; both products were left on
empty documents.

### A defect in the vendor-facing reproduction script, found by running it

`docs/vendor_repro_nmas.py` built every URL as `{host}/{product}{endpoint}`,
including its own `/mapikey/verify` health check. **That endpoint is served from
the host root with no product segment** - `client.py`'s `verify_connection()`
strips the segment for exactly this reason - so the script's opening "연결 확인"
line and its post-call relay probe had both been answering
`404 Not Found, Please check your request url.` on both products.

Its verdict was never wrong: the pass/fail decision reads the `/db/*` calls, not
this one. But this is the file MIDASIT is pointed at to reproduce A-1, and it
opened with a 404. Fixed by giving `call()` a `root=True` option for that one
endpoint; re-run on Civil, the check now answers 200 with the normal
`connected` body. Nothing else in the script changed, and it ships in neither
package.

### 2026-09-16 — Task I boundary: `DESIGN/STEEL/DSTL`

On a disposable empty document, `GET /DESIGN/STEEL/DSTL` answered `200` with
`{"message": ""}` on both Gen NX 2026 v2.1 and Civil NX 2026 v2.2, Build
09/15/2026. The manual's documented design-code selection was absent from that
response, so there was no observed original value to restore. No `PUT` and no
`DELETE` were sent: a write followed by a guessed revert would not be a safe
round trip. This remains a read-level confirmation and a documented live block,
not a rejection of the manual payload.

### 2026-09-16 — npm/Python replay: static fixture batch

On fresh disposable documents checkpointed below `C:/temp`, the npm package and
the Python SDK each replayed the same emitted confirmed fixtures for
`/db/ETMP`, `/db/FBLD`, `/db/LTOM`, `/db/NBOF`, `/db/NTMP`, `/db/PRES`,
`/db/PSLT`, and `/db/SDSP`. Every endpoint completed its full
create → get → update → get → delete round trip on both Gen NX 2026 v2.1 and
Civil NX 2026 v2.2, Build 09/15/2026. Each harness reset the document with
`/doc/NEW`; final `GET /db/NODE` and `GET /db/ELEM` checks were empty on both
products.

### 2026-09-16 — npm/Python replay: dynamic-load batch

On fresh disposable documents checkpointed below `C:/temp`, both SDKs completed
the same emitted fixture round trips for `/db/SPFC`, `/db/THGA`, `/db/THIS`,
`/db/THMS`, `/db/THNL`, and `/db/THSL` on Gen NX 2026 v2.1 and Civil NX 2026
v2.2, Build 09/15/2026. Every npm run and every Python run completed
create → get → update → get → delete for all six resources. Both products were
reset through `/doc/NEW` after the batch.

### 2026-09-16 — Civil-only `extras14` replay result

`/db/BCGA-M1`, `/db/DYFG`, and `/db/DYNF` are Civil-only cases, so Gen was not
called. The npm harness safely blocked `BCGA-M1` because its emitted setup
names `/db/BNGR` as individually non-cleanable; Python completed that existing
case. Both SDKs received the same current-server rejections for the other two:
`DYFG` requires the moving-load code to be Eurocode and `DYNF` is applicable
only to Moving Code EUROCODE. This is not counted as npm replay completion.
The Python harness independently reports both as current regressions; no SDK
behaviour claim is made because the two clients exposed the same server result.
The Civil document was reset to empty after each attempt.

### 2026-09-16 — npm/Python replay: analysis-control subset

`/db/BUCK` and `/db/PDEL` completed their emitted fixture round trips through
both packages on Gen NX and Civil NX, Build 09/15/2026. `/db/BCCT` also passed
on both products once it was intentionally run as a one-case npm batch: its
`/db/BNGR` prerequisite has no DELETE operation, so the final `/doc/NEW` reset
owned its cleanup. Python completed the same three endpoints on both products.

`/db/HHCT` and `/db/NLCT` passed on Gen through both SDKs but failed on Civil
through both SDKs. HHCT's POST succeeds but the expected value does not read
back; NLCT returns that `LINE_SEARCH_OPTION` is required when
`OPT_ENABLE_LINE_SEARCH` is true. Neither is counted as an npm replay success;
the identical outcomes are retained as product/fixture evidence rather than
claimed as an SDK divergence. Every run was checkpointed under `C:/temp` and
finished with a fresh document.

### 2026-09-16 — npm/Python replay: bridge batch

`/db/ULFC` completed its emitted fixture on both SDKs and both products.
Civil-only `/db/CAMB`, `/db/GCMB`, and `/db/GSBG` likewise passed through npm
and Python. Each bridge group case ran as a one-case npm batch because its
`/db/GRUP` setup cannot be individually deleted; the terminal `/doc/NEW`
reset therefore owned cleanup. Checkpoints remained under `C:/temp`, and each
product returned to an empty document.

### 2026-09-16 — npm/Python replay: static-load subset

`/db/FMLD`, `/db/PNLA`, and `/db/POSL` passed their shared fixtures through
both SDKs on Gen NX and Civil NX; Gen-only `/db/POSP` passed through both SDKs
on Gen. The first npm PNLA pass exposed a fixture omission rather than an API
failure: `/db/PNLD` is known to renumber requested key 90 to key 1. Adding its
already documented `allowRenumbering` marker to the emitted fixture made the
subsequent npm Gen and Civil replays pass. All runs used the disposable
checkpoint/reset protocol under `C:/temp`.

### 2026-09-16 — npm/Python replay: moving-load subset

`/db/LLAN`, `/db/MVHC`, and `/db/MVLD` completed their emitted AASHTO LRFD
fixtures through npm and Python on both products, Build 09/15/2026. `/db/MVHL`
also completed through Python on both products, but npm POSTs are stored under a
server-renumbered target ID rather than fixture ID 2. The npm harness can
verify known **seed** renumbering by stable name but has no equivalent target
case representation, so MVHL remains outside the npm-success count pending a
separate, tested harness design. Each product was checkpointed under `C:/temp`
and reset to an empty document.

### 2026-09-16 — npm/Python replay: construction-stage batch

`/db/STAG`, `/db/TMLD`, and `/db/CRPC` completed their emitted fixtures through
npm and Python on Gen NX and Civil NX; Civil-only `/db/CMCS` completed through
both SDKs on Civil. npm ran each as an isolated case because the shared group
setup includes resources without per-ID DELETE; the terminal `/doc/NEW` reset
owns that cleanup. Every call used the `C:/temp` checkpoint protocol and left
an empty document.

### 2026-09-16 — npm/Python replay: heat-of-hydration subset

`/db/HAHS` and `/db/STBK` completed their fixtures through npm and Python on
both products, Build 09/15/2026. HAHS used its confirmed disposable eight-node
solid model; both runs checkpointed below `C:/temp` and ended with `/doc/NEW`.

`/db/HSTG` then completed through npm and Python on both products as a separate
one-case group-seed batch under the same checkpoint/reset protocol.

### 2026-09-16 — npm/Python replay: load-combination batch

`/db/LCOM-SRC`, `/db/LCOM-STEEL`, and `/db/LCOM-STLCOMP` each completed the
same emitted fixture through npm and Python on Gen NX and Civil NX, Build
09/15/2026. All product documents were checkpointed under `C:/temp` and reset
to empty after the batch.

### 2026-09-16 — npm/Python replay: lane-optimization batch

Civil ran `/db/LLANop`, `/db/SLAN`, and `/db/SLANop` together through the npm
harness; all three completed their emitted create → get → update → get → delete
round trips. Gen then ran `/db/SLAN` as a one-case npm batch and passed. Python
replayed the same three selections on Civil and the same SLAN selection on Gen;
all passed. The runs used Build 09/15/2026, checkpointed under `C:/temp`, and
restored empty scratch documents with `/doc/NEW`.

### 2026-09-16 — npm/Python replay: boundary-group core case

`/db/BNGR` ran as a one-case batch on Gen and independently on Civil because
the resource has no per-ID DELETE operation. npm completed create → get →
update → get on both products, after which the harness checkpointed the
throwaway model and used `/doc/NEW` for cleanup. Python replayed the same
one-case selection on each product and passed. Both products were Build
09/15/2026 and were left on empty documents.

## 2026-09-17 - closing the npm/Python evidence asymmetry, and what is left of it

Both products were open on Build 09/15/2026 with empty documents, confirmed by
a read of `/db/NODE` and `/db/ELEM` on each before anything ran. Every batch
below went through the built npm package first and the Python harness second on
the same selection in the same session, checkpointed under `C:/temp`, and ended
with `/doc/NEW`.

| endpoint | npm | Python | what it closed |
| --- | --- | --- | --- |
| `/db/GRUP` | Gen, Civil | Gen, Civil | the last plain replay in the gap |
| `/db/LLANtr` | Gen | Gen | Civil-only since 2026-09-06 |
| `/db/MLSP` | Gen | Gen | same |
| `/db/MLSR` | Gen | Gen | same |
| `/db/MVHLtr` | Gen | Gen | same |
| `/db/MVLDtr` | Gen | Gen | same |
| `/db/TMAT` | Gen, Civil | Gen, Civil | never attempted through npm |
| `/db/IMPF` | Civil | Civil | same; Civil-only, needs the `KOREA` lane code |

All eight passed create → get → update → get → delete on every product listed.
The five lane and moving cases ran as one npm batch on Gen, so the `/db/MVCD`
selector seed that used to take a whole tier down with `Key Already Exist`
handled five tiers in one selection without incident.

### The asymmetry was partly a measurement artefact

`scripts/report_npm_replay_coverage.py` counted **endpoints**, and an endpoint
is not the unit the fixture works in. It now counts **confirmed cases** and
compares each case's declared products against the products the evidence
inventory records, which changed what the number means:

```
by confirmed case (177 cases over 166 endpoints)
  npm ran every declared product: 170
  npm ran only some             : 0
  npm ran none                  : 7
```

Two things only that unit can see. **Five cases were counted as done while npm
had run one product of two** - the five lane and moving rows above, Civil-only
since 2026-09-06 while Python had both. They are the asymmetry this session was
asked to close, and endpoint-level counting had hidden them behind a tick.

And **`/db/HHCT` and `/db/NLCT` were counted as undone while npm had already
replayed them.** Each carries a confirmed Gen case and an unconfirmed Civil one;
npm completed the Gen case on 2026-09-16 and the Civil case failed, which for an
unconfirmed case means triage the fixture rather than a regression. Endpoint
counting cannot record one product's result without implying the other's, so the
run went unrecorded. Their Gen evidence is now in the ledger and the inventory,
and nothing is claimed about Civil.

A first draft of the per-product comparison also reported eleven endpoints whose
inventory row named a product their confirmed case does not declare. All eleven
were the `/db/HHCT` shape - npm running an **unconfirmed** case of the same
endpoint, which is a real run and not a wrong label - and they disappeared when
the comparison was widened to every case for the endpoint. That rule is pinned
by a test.

### The seven that are left, and why none is a replay

| endpoint | why |
| --- | --- |
| `/db/PJCF` | `pjcf_unlock` reads state back and branches, so it cannot be emitted as a payload |
| `/db/HECB` | same, `stage11_seed` + `solid11_seed` |
| `/db/HSPT` | same, `stage11_seed` |
| `/db/MVHL` | the server renumbers the **target** id; npm can verify a renumbered seed by name and has no equivalent for a target |
| `/db/BCGA-M1` | its setup names `/db/BNGR`, which has no per-id DELETE, so npm blocks the case rather than leave the model dirty |
| `/db/DYFG` | the server refused both SDKs on 2026-09-16: the moving-load code must be Eurocode, and the case seeds KSCE |
| `/db/DYNF` | same refusal, same day |

Four of the seven are **harness and fixture design**, which is offline work.
`/db/DYFG` and `/db/DYNF` are the two worth looking at first and not because of
npm: they are `confirmed` cases that Python also failed, and a confirmed case
failing is this repository's definition of a regression. Whether the seed
drifted or the product changed is not yet established, and re-running the
harness will not answer it.

## 2026-09-17 (later) — the npm seed gap closed, and Task I and Task J run

Both products assumed on Build 09/15/2026, as read from their About dialogs on
2026-09-16; not re-read this time. Every write ran on
a scratch document, checkpointed under `C:/temp` first and reset with
`/doc/NEW` afterwards.

### A `/doc/NEW` with no project open blocked Gen NX

The first call of the session was a Python `/doc/NEW` against Gen NX with **no
project open** (`GET /db/NODE` had answered `The project is not opened`). It
did not answer within 60 s. Afterwards `/mapikey/verify` still said
`connected` while `GET /db/NODE` timed out - the blocked-session signature.
Civil was not called. The author then brought both products back up with an
empty document open, and everything below ran on those. What the product
showed is not recorded, so this is a symptom, not a cause: **open a document
before the first `/doc/NEW`, rather than relying on `/doc/NEW` to create one.**

### npm replayed the five confirmed cases it could not express

Fixture version 6 closes what was recorded as harness design:

- A seed step may be a per-id DELETE (`{"endpoint": ..., "delete": [ids]}`),
  which is what `DbResource.delete` sends. That exports `pjcf_unlock` and
  `solid11_seed`.
- `stage11_seed` reads `/db/STAG` only so a full Python run does not create
  stage 1 twice. It is listed in `FRESH_DOCUMENT_SEEDS`, and its create branch
  is exported; the npm harness's collision check refuses loudly if stage 1 ever
  exists. Any other seed that reads stays unexportable.
- `expected.unordered` tells npm to compare a list as a multiset, which
  `/db/BCGA-M1`'s probe already did by sorting.
- `/db/MVHL` needed no harness change. Its case targets id 2, the table
  renumbers to the next free id, and the case never declared the `vehicle`
  seed that holds id 1. Python always ran that seed with the tier; npm seeds
  only what a case declares, so its POST landed at id 1.
- The emitted setup follows `needs`, and HECB's listed the stage before the
  groups the stage names. `/db/STCT` also lacked `hecb_seed`.

| Endpoint | npm Gen | npm Civil | Python Gen | Python Civil |
| --- | --- | --- | --- | --- |
| `/db/PJCF` | PASS | PASS | PASS | PASS |
| `/db/MVHL` | PASS | PASS | PASS | PASS |
| `/db/HECB` | PASS | PASS | PASS | PASS |
| `/db/HSPT` | PASS | PASS | PASS | PASS |
| `/db/BCGA-M1` | - | PASS | - | PASS |

HECB, HSPT and BCGA-M1 each ran as their own npm invocation, because their
setup touches `/db/GRUP` or `/db/BNGR`, which have no per-id DELETE and so may
only be cleaned up by the final document reset. The Python runs printed three
seed failures that no selected case needed: `nllp_seed` and `glink_seed`
answered `Unknown Error` on both products, as recorded before, and on Civil
`mvcd_ksce_seed` answered `Key Already Exist` because the `moving` tier had
created `/db/MVCD` id 1 earlier in the same run. That one looked like the lead
for `/db/DYFG` and `/db/DYNF` and was not; see the next section.

### `/db/DYFG` and `/db/DYNF` were never a regression

They need the moving-load code to be EUROCODE, and extras14 gets there with a
*case*, not a seed: `mvcd_ksce_seed` creates `/db/MVCD` as KSCE-LSD15 for
`/db/DYLA`, then the tier's own `/db/MVCD` case PUTs EUROCODE, and only then do
DYFG and DYNF run. The 2026-09-16 runs selected `--endpoints /db/DYFG,/db/DYNF`,
which filters that switch case out, so the code stayed KSCE-LSD15 and both
SDKs were refused - correctly. Selecting the switch with them
(`--tier extras14 --endpoints /db/DYLA,/db/MVCD,/db/DYFG,/db/DYNF`) passed all
four on Civil NX, Build 09/15/2026.

npm cannot interleave a case between two others' setups, so the fixture now
declares what those two actually need: a `mvcd_eurocode` seed, the switch
case's own confirmed update payload, which the two cases name in `setup` while
`setup_replaces` keeps `mvcd_ksce_seed` from being prepended in front of it.
Python still gates them on `mvcd_ksce_seed`. npm then passed both on Civil.
`report_npm_replay_coverage.py` reports all 177 confirmed cases replayed by npm
on every product they declare.

The rule this adds: **an endpoint selection can drop a case another case depends
on, and the Python harness does not warn.** In extras14 that case is `/db/MVCD`.

### Task I: `DESIGN/STEEL/DSTL` takes a write on Gen, and Civil refuses it

On a fresh document `GET` answered `{"message": ""}` on both products.
`PUT {"Assign": {"1": {"DGNCODE": "KDS 41 30 : 2022"}}}` then:

- **Gen NX** accepted it, answered `{"DSTL": {"1": {"DGNCODE": "KDS 41 30 :
  2022"}}}`, and a following `GET` returned the same record.
- **Civil NX** answered `[Error] Errors detected in Steel Design Control
  Data.(Item:)` and a following `GET` was still `{"message": ""}`.

The manual's request shape is therefore right, on Gen. There was no original
value to put back, so the revert was the document itself: the scratch model
was saved under `C:/temp` and replaced with `/doc/NEW`, after which `GET`
answered `{"message": ""}` again. No DELETE was sent. The enum has one
documented value, so nothing was varied on Civil; the wording matches the
refusal `/db/DSTL` gave for most code names in batch 13 (2026-08-17), but what
Civil needs is not established. `docs/coverage.json` records the endpoint
at `level: "write"` for Gen alone, as the ledger does for every write verified
on one product; the Civil read of 2026-09-16 is still in its `method`.

### Task J: `USE_HAMBLY_EQ` is absent from a DB/User solid section's record

The scratch model's one section was the base model's emitted `DBUSER` solid
rectangle. `GET /db/SECT` returned no `SECT_AFTER` block at all and a
`SECT_BEFORE` without `USE_HAMBLY_EQ`, on both products. That is one section
type, created without the field, so it says only that the product does not add
the property to a record of that type. A section type that carries
`SECT_AFTER` - a composite section - is where the property would be expected,
and no confirmed fixture builds one; the probe stopped rather than write one
from memory.

## 2026-09-18 - Task G assertions made meaningful and re-confirmed

Both products were open on Build 09/15/2026. Their own MAPI keys returned empty
`/db/NODE` and `/db/ELEM` tables before the first mutation. The built npm
package ran first and the Python harness ran second, using the same emitted
fixture. Every run checkpointed under `C:/temp`, created a disposable base
model, and restored an empty scratch document afterwards.

| Endpoint | Products | Assertion that passed in both SDKs |
| --- | --- | --- |
| `/db/MATD` | Gen, Civil | `MAINREBAR_B_FY` was absent on the base material and read back as `500000` after PUT |
| `/db/IEHC` | Gen, Civil | `BEAM_LOC` read back as `1` after POST and `2` after PUT |
| `/db/POLC-M1` | Civil | `NLTYPE` read back as `PDELTA` after POST and `NONE` after PUT |

The prior checks could pass without proving their update: MATD asserted the
pre-existing material name, while IEHC and POLC-M1 sent identical create and
update payloads. These corrected payloads were marked unconfirmed before the
run and restored to confirmed only after all product/SDK combinations above
passed.

Re-deriving the standing `safeToOmit` survey changes no candidate: MATD has no
create call, while IEHC and POLC-M1 are not among its 57 candidate fields. The
result remains 21 grounded claims and 36 honestly `unverified` candidates.

### Task K: current-build core batch

The first eight-endpoint Task K batch replayed `/db/LDGR`, `/db/NODE`,
`/db/SKEW`, `/db/STLD`, `/db/CNLD`, `/db/BMLD`, `/db/CONS`, and `/db/MVCD`
through npm and Python on both Gen and Civil. All 32 endpoint/SDK/product
combinations completed the emitted create/read/update/read/delete sequence on
Build 09/15/2026.

The first npm attempt exposed a fixture-only block: the shared base model
already contains node 2 and static load cases 1 and 2, while the SKEW and STLD
cases redundantly replayed the same named seeds. npm correctly refused the two
collisions. Removing those redundant case-level setup declarations made the
fixture agree with the base model; both cases then passed through both SDKs on
both products. Every attempt checkpointed under `C:/temp` and restored an empty
scratch document.

### Task K: current-build properties batch

`/db/THIK`, `/db/ESSF`, `/db/SECF`, `/db/TSGR`, `/db/TDMT`, and `/db/TDME`
then replayed cleanly through npm and Python on both Gen and Civil, Build
09/15/2026. All 24 endpoint/SDK/product combinations passed, with checkpoints
under `C:/temp` and an empty scratch document restored after every run.

### Task K: current-build boundary batches

The boundary tier was split at the eight-endpoint limit. `/db/NSPR`,
`/db/GSTP`, `/db/GSPR`, `/db/ELNK`, `/db/RIGD`, `/db/MCON`, `/db/FRLS`, and
`/db/OFFS` passed first; `/db/SSPS` passed separately. npm and Python both
completed every case on Gen and Civil, Build 09/15/2026: 36
endpoint/SDK/product combinations in total. Each run checkpointed under
`C:/temp` and restored an empty scratch document.

### Task K: current-build properties extras3 batch

Gen replayed `/db/GRDP`, `/db/EDMP`, `/db/PSSF`, `/db/VSEC`, and `/db/VBEM`;
Civil replayed those five plus its declared `/db/STRPSSM` and `/db/EWSF`
cases. Both npm and Python passed every selection on Build 09/15/2026, for 24
endpoint/SDK/product combinations. The unsupported Gen cases were excluded
before product calls rather than misreported as failures. Every live run used
`C:/temp` checkpoints and restored an empty document.

### Task K: current-build extras2 batches

The eleven remaining extras2 cases were split into selections of eight and
three. Gen ran every case except the Civil-only `/db/PLCB`; Civil ran all
eleven. `/db/SMPT`, `/db/SMLC`, `/db/PLCB`, `/db/LDSQ`, `/db/IELC`,
`/db/IFGS`, `/db/EFCT`, `/db/INMF`, `/db/GTMP`, `/db/STMP`, and `/db/BTMP`
all passed through npm and Python on every declared product, Build 09/15/2026.
The 42 endpoint/SDK/product combinations used `C:/temp` checkpoints and ended
on empty scratch documents.

### Task K: current-build extras13 design batch

`/db/DCON`, `/db/LENG`, `/db/MEMB`, `/db/DCTL`, `/db/LTSR`, `/db/MBTP`, and
`/db/WMAK` passed through npm and Python on Gen and Civil, Build 09/15/2026.
The first npm attempt blocked five cases because their explicit design-model
setup overlapped the shared base model. The fixture now marks those known
material, section, node, element, and plate replacements explicitly instead
of weakening collision checks. The corrected fixture then passed all 28
endpoint/SDK/product combinations. Each attempt restored an empty document.

### Task K: current-build extras4 load-combination batch

`/db/LCOM-GEN`, `/db/LCOM-CONC`, `/db/CUTL`, and `/db/CLWP` passed through
both SDKs on Gen and Civil; the confirmed Gen `/db/LCOM-SEISMIC` case passed
through both SDKs on Gen. Its old case-level static-load seed was removed
because both harnesses already build the same `DL` record in the shared base
model. All 18 endpoint/SDK/product combinations passed on Build 09/15/2026,
with `C:/temp` checkpoints and empty documents restored afterwards.

### Task K: current-build extras10 hydration batch

`/db/ETFC`, `/db/CCFC`, and `/db/HSFC` passed through npm and Python on Gen
and Civil, Build 09/15/2026. All 12 endpoint/SDK/product combinations passed;
each run checkpointed under `C:/temp` and restored an empty document.

### Task K: current-build extras15 assignment batch

`/db/IEPI`, `/db/EXLD`, `/db/PRST`, and `/db/POLC` passed through npm and
Python on Gen and Civil, Build 09/15/2026. All 16 endpoint/SDK/product
combinations passed; each run checkpointed under `C:/temp` and restored an
empty document.

### Task K: current-build dynamic Hyper-S controls batch

The Civil-only `/db/THGC-M1` and `/db/THOO-M1` cases passed through npm and
Python on Civil NX 2026 v2.2, Build 09/15/2026. Both SDKs completed each
PUT/read/update/read/per-id DELETE sequence, for four endpoint/SDK/product
combinations. Both runs checkpointed under `C:/temp` and restored an empty
scratch document.

### Task K: current-build extras6 seismic-device batch

`/db/SDVI`, `/db/SDVE`, and `/db/SDST` passed through npm and Python on Gen
and Civil; the Gen-only `/db/SDHY` and `/db/SDIS` cases passed through both
SDKs on Gen. All 16 endpoint/SDK/product combinations passed on Build
09/15/2026. Every run checkpointed under `C:/temp` and restored an empty
scratch document.

### Task K: current-build extras8 analysis-control batch

`/db/EIGV`, `/db/MVCT`, and `/db/SMCT` passed through npm and Python on Gen
and Civil NX, Build 09/15/2026. All 12 endpoint/SDK/product combinations
passed; each run checkpointed under `C:/temp` and restored an empty scratch
document.

### Task K: current-build extras7 nodal-load batch

`/db/PNLD` passed through npm and Python on Gen and Civil NX, Build
09/15/2026. All four endpoint/SDK/product combinations passed, checkpointed
under `C:/temp`, and restored empty scratch documents. The Civil Python tier
also printed unrelated best-effort seed warnings for `posp_seed` and
`posl_seed`; neither is a `PNLD` prerequisite, and the selected `PNLD` case
still completed its full create/read/update/read/delete/read round trip.

### Task K: current-build extras16 material batch

The confirmed Gen-only `/db/EPMT` case passed through npm and Python on Gen NX
2026 v2.1, Build 09/15/2026. Both SDKs completed the full
create/read/update/read/delete/read round trip, checkpointed under `C:/temp`,
and restored an empty scratch document.

### Task K: current-build extras5 dynamic-load batch

`/db/SPLC`, `/db/THGC`, and `/db/THFC` passed through npm and Python on Gen
and Civil NX, Build 09/15/2026. All 12 endpoint/SDK/product combinations
completed full round trips. Keeping this selection inside `extras5` avoided
the documented cross-tier SPLC seed collision; all runs checkpointed under
`C:/temp` and restored empty scratch documents.

### Task K: current-build China and India lane batches

The Civil-only `/db/LLANch`, `/db/SLANch`, and `/db/LLANid` confirmed cases
passed through npm and Python on Civil NX 2026 v2.2, Build 09/15/2026. The
China and India code selections were kept in separate tier runs. All six
endpoint/SDK/product combinations passed, with `C:/temp` checkpoints and empty
scratch documents restored afterwards.

### Task K: current-build moving-control batches

`/db/MVCTbs` and `/db/MVCTtr` passed through npm and Python on Gen and Civil;
the Civil-only `/db/MVCTid` case also passed through both SDKs on Civil NX,
Build 09/15/2026. Each case selected its own moving-load code (`BS`, `INDIA`,
or `TRANS`) in a separate setup/cleanup sequence. All 10
endpoint/SDK/product combinations completed full round trips, checkpointed
under `C:/temp`, and restored empty scratch documents.

### Task K: current-build `/db/NMAS` replay

`/db/NMAS` passed create/read/update/read/delete/read through npm and Python on
Gen NX and Civil NX, Build 09/15/2026. The case uses NODE 3 from the shared
base model; its obsolete duplicate setup was removed because npm correctly
refuses overwriting a base-model record. Both products checkpointed under
`C:/temp` and restored an empty scratch document after the run.

### Task K: current-build extras1 completion batches

`/db/TDGR`, `/db/NPLN`, `/db/PRLS`, `/db/MLFC`, `/db/CO_M`, `/db/CO_S`,
`/db/CO_T`, `/db/STYP`, and `/db/CLDR` passed through npm and Python on Gen NX
and Civil NX, Build 09/15/2026. Civil-only `/db/STYP-M1` passed through both
SDKs on Civil NX. The four PUT-only color/type cases ran as isolated npm invocations so
the document reset, rather than a nonexistent DELETE operation, was their
cleanup. Every run checkpointed under `C:/temp` and restored an empty scratch
document. Python's extras1 diagnostic still reports the independently known
`nllp_seed`/`glink_seed` failures, but each selected case completed its own
round trip.

### MIDAS-API manual-error probes requested 2026-09-18

Targeted probes from
`MIDAS-API/docs/error_reports/live_verification_requests_20260918.md` ran on
Gen NX 2026 v2.1 and Civil NX 2026 v2.2, Build 09/15/2026. Each probe saved
the disposable document under `C:/temp`, rebuilt its documented preconditions,
and used a GET after the write rather than treating a 2xx status as success.

- `/ope/MEMB`: the documented `SELECTION_TYPE` and table typo
  `SELETION_TYPE` both selected and persisted elements 2 and 3 on Gen and
  Civil. The typo behaves as an accepted alias on this build.
- `/db/SSEIS`: Gen accepted `KDS(41-17-00: 2019)` and normalized it to
  `KDS(41-17-00:2019)`. The two example typos `IINHERENT_TORSION` and
  `NHERENT_TORSION` returned HTTP 201 but disappeared from the response; GET
  kept the real `INHERENT_TORSION` field at `false` instead of the requested
  `true`.
- `/db/TDNA`: both products accepted and persisted the official 2D and 3D
  Round/Element examples' numeric `RADIUS` values. Both products returned an
  HTTP 201 body containing `Wrong Field` for `PROFY.RADIUS=false` and for
  `PROF.RADIUS=[0,20]`; GET then returned `Not Found Key`. The two conflicting
  specification rows must be Number, not Boolean or Array.
- `/db/MATD`: Gen persisted `bSERVCHECK=true`, `dSHORTTERM=1.25`, and
  `dLONGTERM=1.5`, both separately and together. Civil echoed each field in
  its HTTP 200 PUT response but omitted all three from the following GET, so
  they are accepted-but-ignored on Civil in this build.
- `/db/SPLC`: on Gen, POST persisted
  `aACCECC_ECCEN_LIST[0].ALONG=2.5`. A following PUT echoed the requested
  value `3.5`, but GET retained `2.5`; updating ALONG is silently ignored on
  this build even though creation works.

The Jira-ready Korean response is in the manual repository at
`docs/error_reports/live_verification_feedback_20260918.md`. Raw response
captures remain only in `C:/temp/manual-feedback-*.json`; model response
bodies are deliberately not committed here.

### Task K: current-build final extras1 batch

`/db/PZEF` passed through npm and Python on Gen NX and Civil NX, while the
Civil-only `/db/SPAN` case passed through both SDKs on Civil NX, Build
09/15/2026. The npm runner required the no-DELETE `/db/PZEF` case to run last;
after correcting that ordering, all six endpoint/SDK/product combinations
completed their full case. Python's extras1 diagnostic printed the already
known, unrelated `nllp_seed` and `glink_seed` warnings, but both selected
cases passed. Each run checkpointed under `C:/temp` and restored an empty
scratch document.

### Task K: current-build final extras14 batches

The Civil-only `/db/CRGR`, `/db/CJFG`, `/db/DYLA`, `/db/ACTL-M1`,
`/db/EIGV-M1`, `/db/HHCT-M1`, `/db/NLCT-M1`, `/db/STCT-M1`, and
`/db/BCGD-M1` confirmed cases passed through npm and Python on Civil NX 2026
v2.2, Build 09/15/2026. npm ran `/db/CRGR`, `/db/CJFG`, and `/db/DYLA`
individually because their `/db/GRUP` setup has no per-ID cleanup and therefore
must be last; the earlier runner guard was a batch-order block, not an endpoint
failure. All 18 successful endpoint/SDK combinations completed their full
round trips, checkpointed under `C:/temp`, and restored empty scratch
documents.

## 2026-09-19 — Task A batches 17 and 18, first live run

Both products on Build 09/15/2026 (Gen NX 2026 v2.1, Civil NX 2026 v2.2). The
first read-only check found **no project open on either product** —
`GET /db/NODE` answered `The project is not opened` with each product's own key
while `/mapikey/verify` still said `connected` — so nothing was run until the
author opened a New Project in both. The re-check then read 0 `NODE` and 0
`ELEM` records on each, and was repeated before every run. The built npm
package ran first and the Python harness second, on Gen then Civil, same
session, same emitted fixture. Every run checkpointed under `C:/temp` and
restored an empty scratch document.

**npm and Python agreed on every endpoint and product:**

| Endpoint | Gen | Civil |
| --- | --- | --- |
| `/db/TDNT` | pass | pass |
| `/db/POGD` | `Wrong Field` | pass |
| `/db/POGD-M1` | — (Civil only) | pass |
| `/db/PHGE` | `Unknown Error` | `Unknown Error` |
| `/db/TDNA` | see below | see below |
| `/db/TDPL` | blocked by the TDNA seed | blocked by the TDNA seed |

`/db/TDNT`, `/db/POGD` (Civil) and `/db/POGD-M1` are write-level from this run;
the ledger is 204 write.

- **`/db/TDNT`** passed with the ch07 section 6 KSCE LSD15 example as written.
  That example sends none of `FT`, `FPK` or `TDMFNAME`, which the chapter's
  Specifications table marks Required without a condition. The pass is live
  evidence for the `appliesWhen` on `RM` those three fields now carry: the
  product does not require them under RM 6.
- **`/db/POGD`** is product-asymmetric: the identical payload passes on Civil
  and answers `Wrong Field` on Gen, through both SDKs. It is now one case per
  product, the pattern `/db/EPMT` already uses. `Wrong Field` usually names a
  bad *value* rather than a bad field name, so the enums in ch14's common
  control fields are where to look first.
- **`/db/PHGE`** answered `Unknown Error` on both products, with ch14's own
  two-element hinge-assignment example on the base model's elements 1 and 2.
- **`/db/TDNA`** failed in two stages, and the first one was a fixture defect.
  The ch07 section 7 example sends `TDN_GRUP: 1` and assumes tendon group 1
  exists; without it both SDKs got `[Error] Tendon Group 1 does not exist.` —
  a domain error, so the shape was accepted and the target was missing. A
  `/db/TDGR` seed built from extras1's confirmed case fixed that, and the
  retry answered, on both products and through both SDKs:

  `[Error] Errors detected in Tendon Profile Data.(Item:IS_DB_TDNA_NOTENSIONCALC : Not Registered String)`

  The item named is an internal resource-string id the product could not look
  up (`Not Registered String`), so the message itself is broken as well as the
  request refused. "No tension calc" reads as a model-state precondition — the
  base model's beams carry a DB/User solid section, not a PSC one — but that
  is a reading, not a finding. It was **not** chased by permuting fields; the
  case stays unconfirmed, and `/db/TDPL` stays blocked behind it.

## 2026-09-19 (later) — Task B on Build 09/15/2026: nothing moved

Same session as batches 17 and 18, both products still on Build 09/15/2026,
the read-only 0-record check repeated before every run. Of Task B's 22
endpoints, the 15 that were neither settled product behaviour (`/db/ACTL`,
`/db/FIMP`, `/db/STCT`) nor blocked behind `nllp_seed` (`/db/NLLP`,
`/db/NLNK`, `/db/NLNK-M1`, `/db/CGLP`) were run, because **none of the 15 had
been run on this build** — the last recorded attempts are 2026-09-04 to
2026-09-14. npm then Python, Gen then Civil. The four `lane_code_*` seeds all
POST `/db/MVCD` id 1, so each moving-load code had an invocation of its own.

**Every endpoint answered what it answered on the earlier build, word for
word, and npm and Python agreed on every one:**

| Endpoint | Gen | Civil |
| --- | --- | --- |
| `/db/EPSE`, `/db/EPST` | `Wrong Field` | — (Gen only) |
| `/db/RPSC`, `/db/TDMF` | `Wrong Field` | `Wrong Field` |
| `/db/WVLD` | — (Civil only) | `Wrong Field` |
| `/db/HPCE` | `Wrong Key` | `Wrong Key` |
| `/db/FBLA` | `Unknown Error` | `Unknown Error` |
| `/db/MVLDeu` | `Unknown Error` | `Unknown Error` |
| `/db/MADO`, `/db/SBDO`, `/db/DOEL` | POST accepted, record absent on read-back | same |
| `/db/SINF` | POST accepted, id 1 absent on read-back | same |
| `/db/MVLDpl` | — (Civil only) | POST accepted, id 1 absent on read-back |
| `/db/MVLDch` | — (Civil only) | `[Error] Moving Load Case Data (Name:MV_Case1) contains errors.(Item:Non-existent Vehicle has been defined in Sub-Load Case.)` |
| `/db/MVLDid` | — (Civil only) | `[Error] Moving Load Case Data (Name:MV_India_1) contains errors.(Item:Number of Sub-Load Cases)` |

That is a result, not an absence of one: a new build changed none of these,
so none of them is build-transient. **Do not re-run any of the 15 against this
build with an unchanged fixture** — it has now been asked.

### `fbld7_seed` was missing from `RENUMBERING_SEEDS`, so npm never tested `/db/FBLA`

npm's first pass reported `/db/FBLA` as `BLOCK — /db/FBLD: id 90 missing after
setup POST` on both products, while Python reached FBLA and got `Unknown
Error`. The two SDKs were not disagreeing about the product; they were testing
different things. `/db/FBLD` renumbers to the next free id (confirmed live
2026-08-16), and extras7's own seed docstring says so — "pnld_seed/fbld7_seed
both land at id 1, not the requested 90" — but only `pnld_seed` had been
registered. npm, which verifies every seed record by id, stopped at the seed;
Python, which does not, carried on to FBLA, whose payload names the load type
rather than its id. `fbld7_seed` is now registered, and npm reaches FBLA and
answers `Unknown Error` exactly as Python does.

### Leads, not findings

- **`/db/MVLDch` needs a vehicle.** Its sub-load case names the China class
  `CH(CJJ11)_C-CD(A/B)`, and its `needs` build the lane code and the lanes but
  no vehicle; the message says as much. No confirmed case builds a China
  vehicle — the fixture's vehicle cases are AASHTO `/db/MVHL` and
  `/db/MVHLtr` — so a seed needs a China vehicle payload from ch08, not one
  written here.
- **`/db/MVLDid`**'s `Number of Sub-Load Cases` is a domain message about a
  count, the same class as `/db/SPAN`'s item-count-vs-list-length rule.
- Of the five "accepted, then absent" endpoints, three ask for id 1 in an
  **empty** table (`/db/SBDO`, `/db/SINF`, `/db/MVLDpl`), so renumbering
  cannot explain them the way it explained FBLD: the next free id is the one
  requested, and they drop the write. `/db/MADO` (id 92, beside its seeds'
  90 and 91) and `/db/DOEL` (id 4) do not rule renumbering out on this
  evidence alone; extras9 records MADO dropping writes on both products.

### Task B, same session: `/db/MVLDch` and `/db/MVLDid` pass once they have a vehicle

Both leads from the run above were offline questions first, and both had the
same answer. A ch08 country load case's sub-load names a vehicle — despite the
key, `VEHICLE_CLASS` with `VEHICLE_TYPE: "VL"` names a `/db/MVHL` record, not
a `/db/MVHC` class — and neither case's `needs` built one.

- **India is paired by the manual itself.** Section 14's General Load Python
  example names `IN(IRC6)_ClassA`, which is section 10's India example (MVLD
  code 7, `STANDARD_CODE: "IRC:6-2000"`, standard Class A). The fixture had
  used section 14's Request Body instead, whose railway vehicle
  `IN(IRC)_(25t1)_BroadGauge-1676mm` no section documents creating. The case
  now names Class A and a seed creates it.
- **China is not paired.** Both of section 13's examples name the standard
  class `CH(CJJ11)_C-CD(A/B)`, which no section documents creating, and the
  only China vehicle section 10 documents is the user-defined `CN_UD_Lane1`
  (MVLD code 3, `VEH_CN` Truck/Lane, no `STANDARD_CODE`). The case names that
  one: a model reference remapped, as element and lane references already
  are, not a value invented.

With the vehicles seeded, **both passed a full round trip on Civil NX through
both SDKs** — create, read, update, read, per-id DELETE, read. The India
result also answers the lead the run above recorded: `Number of Sub-Load
Cases` was the missing vehicle too, not a count rule — `NUM_LOADED_LANES` was
left at the example's 2, beside one sub-load item. A sub-load whose vehicle
does not exist is evidently discarded, and the case is then refused for
having none.

Two more things this run established:

- **The country cases' update now proves a PUT.** It had equalled the create,
  so it could not fail (the Task G class). It changes `DESC` alone — the probe
  `/db/STLD`'s confirmed case uses — and both cases read back `crud updated`.
  `/db/MVLDeu` and `/db/MVLDpl` share the helper and get the same update; both
  still fail before it, as recorded above.
- **`/db/MVHL` accepted and stored both country shapes**, since npm verifies
  every seed record by id: a user-defined China vehicle with `VEH_CN` and no
  `STANDARD_CODE`, and a standard India vehicle with `STANDARD_CODE` and no
  `VEH_*` object. That matches what the SDK's own class docstring recorded
  from a real Eurocode model on 2026-07-30 — country vehicles carry their
  `VEH_*` object instead of `VEH_DEFAULT`, and not necessarily a
  `STANDARD_CODE` — and it is the first time either of these two shapes has
  been written. `/db/MVHL` was already write-level, so no count changes.

`/db/MVLDch` and `/db/MVLDid` are write-level on Civil, and the ledger is 206
write. Gen has neither code, so Gen's evidence for both stays the read.

### Task B, same session: the five `Wrong Field` cases are not bad values

The standing advice is that `Wrong Field` usually names a bad *value*, so vary
a documented enum value before any field name. None of the five contracts
declares an `enum` on a field these payloads send; the value sets live in
field descriptions. Measured against those, and against the history:

- **`/db/EPST` — every documented value set is now exhausted.** 2026-08-16
  had varied `SEL_TYPE` and `EP_TYPE`; this session varied the remaining two,
  one at a time, through the Python harness on Gen with a temporary edit that
  was reverted afterwards: `ELEM_TYPE: "PLANAR"` on the base model's plate
  element 4, and `DIR: "NORMAL"`. Both answered `Wrong Field`. EPST's failure
  is not a value its descriptions offer. `/db/EPSE` shares every one of those
  fields and fails identically; it was not probed separately.
- **`/db/WVLD` — value-independent.** A bare `{"NAME": ...}` answered `Wrong
  Field` on 2026-08-16, so no value in the payload is the cause; varying
  `THEORY`, `CHAR_TYPE` or `VERT_COORD` cannot answer anything.
- **`/db/RPSC`** — the manual's own example with its documented values fails.
  Comparing the payload with `GET /info/db/RPSC` turned up one member the
  fixture never sends, `MBARS[].MBAR_ITEMS[].PART`. The contract and ch04
  both record it, as an Integer with no default, no requiredness and no value
  in any example, so sending it means inventing one. Stopped there.
- **`/db/TDMF`** — no field it sends states a value set; the CREEP/`CTYPE`
  body was the chapter's own, and was tried on 2026-09-14.

One false lead, recorded so the next session does not follow it: every one of
the 399 `/info` schemas in `schema/info-baseline.json` roots its record at
`Argument`, `/db/NODE` included, so RPSC's `Argument` root says nothing about
its request wrapper.

### 2026-09-20 — Task P `/db/PTNS`

The final mechanically buildable `/db` case passed through the built npm
package and Python SDK on Gen NX 2026 v2.1 and Civil NX 2026 v2.2, Build
09/15/2026. Each product started from an empty document verified with its own
key. The fixture used the manual's TRUSS shape on element 5 and base-model
nodes 21-22, created the existing `PS15_SEED` prestress load case, registered
it through `/db/EXLD`, then completed PTNS create/read/update/read/delete/read.
The update changed `TENSION` from 130 to 260 and both SDKs read back the change.
Every run checkpointed under `C:/temp` and restored an empty scratch document.

### 2026-09-20 (later) - Task P's fixture stops sharing extras15's seeds

The PTNS case above borrowed extras15's `prestress_load_cases` seed by
splicing that tier's seed list into extras19's, and put its truss on the base
model's node pair 21-22. Both were wrong for the same reason: a tier's seeds
are not per-case. The runner executes every seed of a selected tier before
that tier's cases, so a selection holding extras15 and extras19 - which is
what a full re-verification is - POSTed the same /db/STLD records twice, and
/db/STLD renumbers, so the second POST would have left two load cases
answering to the name the fixture looks up. Nodes 21-22 are the pair the base
model keeps unattached so ELNK, RIGD and MCON cannot collide with a real
element; the truss attached one to them.

The fixture now builds its own nodes 51-52, its own `PS19_SEED` load case and
registers that name through `/db/EXLD`. Re-run on Build 09/15/2026 through
both SDKs: PTNS passed on Gen and Civil, and `/db/EXLD`, `/db/PRST` and
`/db/PTNS` passed together in one Gen selection, which is the combination the
old arrangement would have broken. `/db/EXLD` id 1 is still shared with
extras15's own case, which deletes it before extras19's seed re-creates it -
TIERS is ordered, so that sequence is fixed.

### 2026-09-20 (later) - review fixes, re-run on Build 09/15/2026

A code review of the untagged batch found four defects in the harnesses. Two
were only reachable live, so extras13's five design cases - the only ones whose
setup replaces a shared base-model record - were re-run on Gen and Civil
through both SDKs. All five passed on both products with no cleanup errors.

The npm harness detects what a setup step created by diffing against a
snapshot taken before the step, so an id a `replaceExisting` seed overwrote
never looked new and cleanup left it in place. The fixture's steel S450 stayed
at material 1, its H300x150 at section 1, and nodes 1-4, element 2-3 and
thickness 1 likewise, for every later case in the same invocation. Nothing has
misreported because of it - the batches this is run in are small and the
design tier sits late - but a confirmed case running against a base model
nobody rebuilt is how a healthy SDK prints REGRESS. Cleanup now restores the
base-model record.

The Python harness's read-back probe subscripts the record it is handed
(`p["ITEMS"][0]["END"]`), and only `MidasAPIError` was caught, so a record the
product returns in another shape raised `KeyError` out of the tier loop: no
report, no end-of-run checkpoint, and the product left holding the fixture's
model. An unreadable record is now a failure of that case and nothing else.

### 2026-09-21 - /db/REBW was already write level, and the ledger had lost it

Nothing new was run. Consolidating the ledger put the two records for
`/db/REBW` side by side, and they disagreed: `db-rebw-live-shape-2026-07-29`
in contracts/verification/gen-nx.yaml describes a PUT round trip against a
real production Gen NX model - wall 101's record backed up, `VER_BAR.DIST`
changed from 0.2 to 0.99, the change confirmed on a fresh read, then reverted -
while docs/coverage.json had the endpoint at read level.

The ledger's own definition settles it: write means a live call actually
mutated model data, and that PUT did. What happened is a property of the old
shape rather than of the evidence. An endpoint had one prose `method` field,
and on 2026-08-27 a read-sweep narrative about `/info/db/REBW` field names was
written into it, overwriting the write evidence that had been there since
2026-07-29. The session record kept it; the per-endpoint field could not.

`/db/REBW` is now write level on Gen, dated 2026-07-29 on build 07/28/2026,
which is the session that earned it. Published coverage moves from 207 write /
193 read to 208 / 192, and ROADMAP's version matrix gains the 2026-07-29 Gen
row that endpoint had been the only citer of.

This is also why the new ledger appends rather than edits: a record is what one
session saw, and a later session writing over it loses evidence nobody notices
is gone.

## 2026-09-21 - the vendor report re-measured on both products, and two of its claims sharpened

The author had both products open and asked for the report's items to be
checked as of today. Scope chosen by the author: the fixture replay, **not**
A-2 (its reproduction empties a table) and **not** A-7 (it needs a document
opened from `Program Files` and, if it reproduces, a human to dismiss a modal).
Both documents were empty before anything ran (`GET /db/NODE` and `/db/ELEM`
answered 0 records under each product's own key), every destructive run
checkpointed under `C:/temp`, and both products were left on empty documents.

**No build string was read this session.** The API reports none, so every one
in this file is a human reading the About dialog; the `/info` comparison below
says the *surface* matches Build 09/15/2026's and nothing stronger than that.

**The API surface has not moved.** A fresh GET-only `/info` capture of both
products diffed against `schema/info-baseline.json` shows exactly one change,
`/db/SECT` gaining `SECT_AFTER.USE_HAMBLY_EQ` and `SECT_BEFORE.USE_HAMBLY_EQ`
on both - which is the already-recorded Build 09/15/2026 delta against a
baseline captured 2026-09-03. Nothing else. That is not proof the build is
unchanged and it was not treated as one: `/db/NMAS` is the standing proof that
behaviour can change while `/info` does not, which is why the writes were run
anyway.

### Reproduced, unchanged

| item | endpoint | what happened today |
| --- | --- | --- |
| A-3 | `/db/CONS` | sent an 8-character `CONSTRAINT`, stored 7, both products |
| A-3 | `/db/MVHL` | `VEHICLE_TYPE_NAME: "NOT-A-VEHICLE"` stored verbatim, both |
| A-3 | `/db/SECF` | key naming no section: POST ok, table empty, both |
| A-3 | `/db/STCT` | Gen: `wrote 30, read back None` - `iITER` dropped |
| A-3 | `/db/SBDO`, `/db/SINF` | `id 1 missing after wrote`, both |
| A-3 | `/db/MVLDpl` | `id 1 missing after wrote`, Civil |
| - | `/db/MADO`, `/db/DOEL` | `id 92` / `id 4` missing, both - populated tables, so still not separable from a renumber |
| A-4 | seventeen calls | every refusal in the A-10 batch arrived as **HTTP 201 with an error body** |
| A-6 | `/db/TDMT` | an unrecognised `CODE` answers `Wrong Field` |
| A-8 | `/DESIGN/*`, IEHG trio | 404 on both products; `/db/*` answers |
| A-9 | `/db/POSL` | Civil `/info` declares `CODE` in 8 properties; sending `CODE: ""` answers `Wrong Field`; the same payload without it is accepted |
| A-10 | all nine + `/db/RPSC` | each answered its exact recorded message on both products |

A-10 in full, from the harness rather than by hand: `Wrong Field` for
`/db/TDMF`, `/db/RPSC`, `/db/EPST`, `/db/EPSE` and `/db/WVLD`; `Wrong Key` for
`/db/HPCE`; `Unknown Error` for `/db/FBLA`, `/db/PHGE`, `/db/MVLDeu` and
`/db/NLLP`. `/db/WVLD` is the Civil case and `/db/EPST`/`/db/EPSE` the Gen
ones, so "both products" means each on the product that declares it.

### Two claims that got sharper, one that got weaker

**`/db/SECF` is an echo, not just a silent success.** The report recorded a 200
with no error. What the product actually returns is the **whole record echoed
back** - `{"SECF": {"4": {"ITEMS": [{"ID": 1, "AREA_SF": 1.2, ...}]}}}` - while
`GET /db/SECF` answers `{"message": ""}`. That is the same signature as
`/db/CONS` and `/db/MATD`, not a weaker cousin of them, and the report's
wording is now that.

**`/db/STBK`'s `LCNAME` is weaker evidence than it was being used as.** The
claim that `/info` is not a superset of what the server accepts rested partly
on `LCNAME` being absent from `/info` while a confirmed round trip sends it.
The call does succeed on both products. But the record read back afterwards is
`{"NODE1": 1, "NODE2": 2, "DX": 0, "DY": 0.005, "DZ": 0, "GROUP_NAME": ""}` -
**no `LCNAME`**. So what is established is that the field is *tolerated*, not
that it is stored, and whether it had any effect is unmeasured. `/db/POSL` is
doing all the work in that direction and it is doing it well; `/db/STBK` is now
stated as the weaker observation it is, in the report and in CLAUDE.md.

### A first probe that answered nothing, and why it is recorded

`/db/MVHL`'s first run reported the bogus vehicle name as *not* stored, which
would have contradicted the report. It was wrong: the probe called
`_seed_model` only, and `/db/MVHL`'s case declares `needs: [mvcd, vehicle]` -
without the `/db/MVCD` selector carrying `CODE: "AASHTO LRFD"`, the POST is a
no-op for an unrelated reason. Re-run with the seed taken from the fixture, the
name stores verbatim on both products.

This is the fifth time a missing tier seed has read as a product finding. The
rule it keeps proving: a probe that skips the fixture's own `needs` is not
measuring the endpoint.

### Not measured today

A-2 and A-7 by the author's choice, above. A-5 needs the product to be killed.
`/db/STCT` on **Civil** reported `BLOCKED` rather than a result - see the
correction in the next section, because the reason recorded here first was
wrong. `/db/MATD` and `/db/SSEIS` came from
`scripts/live_manual_feedback.py`'s probes rather than the CRUD fixture and
were not re-run in the batch above. `/db/SPLC`'s round trip passes; the
`ALONG`-ignored-on-update half is not what that case measures.

## 2026-09-21 (later) - the rest of the report, on a dummy model built for it

The author asked for the remaining items to be measured with a dummy model
rather than left as debt. `scripts/live_crud_check.py`'s `_seed_model` builds
it - 10 nodes, 4 elements, 2 static load cases - and every run checkpointed
under `C:/temp` and ended on an empty document. Both products were confirmed
empty before and after.

### A-2 reproduces, and the contrast now sits in one session

Measured on both products, on a model built to be destroyed:

| call | before | after |
| --- | --- | --- |
| `DELETE /db/NODE/6` (per-id, undocumented) | NODE 10, ELEM 4 | NODE 9, ELEM 3 |
| `DELETE /db/STLD` + `{"Assign": {"1": {}}}` | STLD 2 | **STLD 0** |
| `DELETE /db/NODE` + `{"Assign": {"3": {}}}` | NODE 9, ELEM 3 | **NODE 0, ELEM 0** |

The per-id form does exactly what it should, including taking the one element
that depended on node 6. The documented body-with-ids form ignores the id and
empties the table, and on `/db/NODE` it takes every element with it - one call,
whole model. Identical on Gen and Civil.

That is the strongest form of this finding recorded so far, because the correct
behaviour and the destructive one are two calls apart in the same session on
the same model, rather than compared across sessions.

### A-3's remaining three, through their own probes

`scripts/live_manual_feedback.py --case b1` and `--case b2`, which is where
these were measured on 2026-09-18:

- **`/db/MATD`** - Gen stores `bSERVCHECK`, `dSHORTTERM` and `dLONGTERM`
  individually and together; Civil's record carries **none of the three** in
  any of the five variants, baseline included, while the PUT answers 200.
- **`/db/SPLC`** - POST stores `ALONG: 2.5`; the PUT to `3.5` answers 200 and
  **echoes 3.5**; the following GET still reads `2.5`. Gen.
- **`/db/SSEIS`** - the real `INHERENT_TORSION` round-trips to `true`. Both
  article typos, `IINHERENT_TORSION` and `NHERENT_TORSION`, vanish from the 201
  response body and leave the real field `false`.

### Correction: `/db/STCT`'s Civil block is a fixture seed, not the product

The batch earlier today recorded Civil's `/db/STCT` case as `BLOCKED` because
"Civil pre-populates the stage-control record". **That attribution was wrong**,
and the harness's own message said so: `id 1 already exists before this case
ran; a seed in this selection owns it`. A seed in `extras11` creates it.

Measured directly on a freshly seeded model, `GET /db/STCT` answers
`{"message": ""}` on **both** products - neither pre-populates it - and the PUT
is refused because there is no record to update. The 2026-08 observation of a
pre-existing record on Civil was on a model with construction staging in use,
which is also where that table becomes POST/DELETE-locked.

So the Civil half of `/db/STCT` still has not been measured, and now the
precondition is known: it needs a model with construction stages, not a bare
seed. The Gen half stands on today's `wrote 30, read back None`.

This is the second wrong attribution in one day, after `/db/MVHL`'s missing
seed. Both came from the same habit - reading a harness result without reading
what the harness said about it.

## 2026-09-21 (later still) - A-7 reproduced on Gen, and *not* on Civil, from one call

The author asked for A-7 to be measured directly: build a dummy model and save
it under `Program Files`. Both products were tried, at their request, on a
dummy `_seed_model` model with a real checkpoint written to `C:/temp` first.

Same relay, same call, same path shape, opposite results.

| | `POST /doc/SAVEAS` -> `C:/Program Files/a7-probe-<product>-<stamp>.<ext>` |
| --- | --- |
| Civil NX | `{"message": "MIDAS CIVIL NX command complete"}`, session responsive. ~~`/doc/OPEN` then succeeded~~ -- **wrong, see the correction below**: the probe read the absence of an exception, not the answer |
| Gen NX | **the HTTP call never answered** (read timeout at 60s), and the session was blocked |

The Gen dialog, photographed by the author:

> `C:/Program Files/a7-probe-gen-20260921T072357Z.mgbx 액세스가 거부되었습니다.`

That is A-7's exact signature, on the exact path, and it blocked every `/db/*`
call until the author dismissed it. Gen was responsive again immediately after.

### Two things this session establishes on its own

**`verify_connection()` answered `connected` throughout the block.** Every
`/db/NODE` call timed out while `/mapikey/verify` answered `connected` in well
under a second, twice, minutes apart. That is A-5's mechanism, observed
incidentally and more cleanly than the original crash-window measurement: the
relay serves the health check, so it cannot see a product held by a modal.

**`/doc/SAVEAS` did not answer "command complete" here.** The standing rule in
CLAUDE.md is that a save which never happened still answers like a success. For
*this* failure mode it did not answer at all - the call hung until the dialog
was dismissed, and the client gave up first. Both behaviours are real, but
the split drawn here - "a path NX dislikes answers like success, an
access-denied write hangs" - is **wrong**: Civil answered the identical
access-denied write with `command complete`. The split is by product. See the
last section of this date.

### The `GET /db/CAMB` re-check was not one

`GET /db/CAMB` on Civil then answered `{"message": ""}` without blocking, and
this was read as the 2026-07-29 "a plain GET pops the dialog" case failing to
reproduce. It was not a test of that case: it assumed a document opened from
`Program Files`, and the `/doc/OPEN` meant to provide one had failed (see the
next section). The 2026-07-29 observation, made with the product's own tutorial
file genuinely located under `Program Files`, remains the only measurement.

## 2026-09-21 (last) - A-7 settled, and the probe that got it wrong

The author checked the NX host: the Civil file was in **neither**
`C:\Program Files\` nor `%LOCALAPPDATA%\VirtualStore\`. Then they tried a Save
As from the Civil NX GUI to that folder and Windows itself refused it -
`"이 위치에 저장할 권한이 없습니다. 권한은 관리자에게 문의하십시오."`, offering
the Documents folder instead. So the account cannot write there through any
path, and **no file was ever created by either product**.

Both hypotheses above are dead. It is not elevation and it is not UAC
virtualization. Civil simply reported a success for a write that did not
happen, which is the failure shape CLAUDE.md has recorded since 2026-07-26 -
the one this session's Gen result was used to argue it was *not*.

### The probe was the defect, not the API

`/doc/OPEN` knows perfectly well. Measured on both products, on an **empty**
document (0 nodes, checked immediately before, so a node count can distinguish
"it opened" from "it did nothing"), against a file that certainly does not
exist:

```text
[civil] OPEN C:/Program Files/a7-missing-....mcbz -> {"message": "MIDAS CIVIL NX path is wrong (the file can't open)"}  nodes after: 0
[civil] OPEN C:/temp/a7-missing-....mcbz          -> {"message": "MIDAS CIVIL NX path is wrong (the file can't open)"}  nodes after: 0
[gen]   OPEN C:/Program Files/a7-missing-....mgbx -> {"message": "MIDAS GEN NX path is wrong (the file can't open)"}    nodes after: 0
[gen]   OPEN C:/temp/a7-missing-....mgbx          -> {"message": "MIDAS GEN NX path is wrong (the file can't open)"}    nodes after: 0
```

Same message in a writable directory and an unwritable one, so it is about the
missing file and not about the permission.

The earlier probe called `/doc/OPEN`, caught no exception, and **printed its
own sentence** - `"/doc/OPEN on the Program Files path SUCCEEDED - the file
exists"` - without ever printing the answer body. The product had answered
`path is wrong (the file can't open)`. HTTP 200, no `error` key, so
`MidasResultError` does not fire and nothing raises. A probe that prints a
conclusion instead of the response can only report what it already assumed.

### The full chain, every answer read

Civil, one session, document empty beforehand, seeded to 10 nodes:

```text
SAVEAS C:/temp/a7-chain-civil-<stamp>.mcbz          -> {"message": "MIDAS CIVIL NX command complete"}
SAVEAS C:/Program Files/a7-chain-civil-<stamp>.mcbz -> {"message": "MIDAS CIVIL NX command complete"}   <- byte-identical
OPEN   C:/Program Files/a7-chain-civil-<stamp>.mcbz -> {"message": "MIDAS CIVIL NX path is wrong (the file can't open)"}
OPEN   C:/temp/a7-chain-civil-<stamp>.mcbz          -> {"message": "MIDAS CIVIL NX command complete"}   nodes: 10
```

The session stayed alive after each call. So on Civil the information that the
write failed exists in the product and is absent from the `SAVEAS` response;
the very next call reports it.

### What this changes

- **`/doc/SAVEAS` has two failure shapes and they are per-product, not
  per-path.** Identical call, identical path: Civil answers `command complete`
  and writes nothing, Gen raises a modal and never answers. The 2026-07-26
  "answers like success" and the 2026-09-21 "hangs the call" observations are
  both real and are not two kinds of path.
- **"Verify a write with `/doc/OPEN`" still holds, and needs one more clause:
  read the message.** `/doc/OPEN` reports a missing file honestly, but as a 200
  body with no `error` key, so absence of an exception proves nothing.
- **Nothing was left behind on the NX host by the Program Files attempts.** The
  earlier note claiming a stray `a7-probe-civil-*.mcbz` is withdrawn. The files
  under `C:/temp` are real and are the author's to clear.

Both products were left connected, responsive, and with the dummy model open on
Civil (saved at `C:/temp`); Gen's document was left empty.

## 2026-09-22 - `/db/SPLC`'s supplementary rows, one at a time

`scripts/live_manual_feedback.py --case c1`, both products, each document
confirmed empty by GET with that product's own key first, each probe on a fresh
document seeded by `_seed_model` plus the `SPFC_B2` spectrum function, and a
checkpoint under `C:/temp` before the first `/doc/NEW` and after each probe. The
build was not re-read this session; the last one recorded is 09/15/2026 on both.
Every probe starts from section 2's no-damping Request Body with `aFUNCNAME`
pointed at `SPFC_B2`, and changes what its label says.

| probe | product | POST | read back |
| --- | --- | --- | --- |
| the example as printed | both | 201 | as sent; Gen adds `bACCECC: false`, `bAUTO`; Civil adds `CQCRATIO`, `iANGLETYPE` |
| `bACCECC: true`, rows 25-29 omitted | Gen | 201 | `bACCECC: true`, with `bACCECC_AUTO: false`, `bACCECC_CONSIDER_GL` and `bACCECC_MINIMUM_TORSION` supplied |
| `bNDP: true`, `NDP` omitted | Gen | 201 | neither `bNDP` nor `NDP` |
| `bNDP: true`, `NDP: 1.0` | Gen | 201 | neither `bNDP` nor `NDP` |
| Modal damping example (`iMDTYPE: 1`) | both | 201 | `DALL`, `aDAMPING` as sent |
| Mass & Stiffness, direct (`iMDTYPE: 2`, `iCOEF: 1`) | both | 201 | `MASSC`, `STIFFC` as sent |
| Mass & Stiffness, from modal damping (`iCOEF: 2`) | both | 201 | `iCALC`, `FP1`, `FP2`, `DR1`, `DR2` as sent |

What it settles:

- **Rows 25-29 are not required**, even with the switch on. The table marks
  them Required directly under row 24's `bACCECC` and states no condition, and
  a confirmed round trip already omitted them with `bACCECC` at its default;
  the other half is now measured as well. MD-57.
- **`NDP` is not required either**, and what the server does with `bNDP` and
  `NDP` is open: both are accepted and neither is read back, on this document.
  That may depend on a design setting the scratch model does not have; nothing
  here says which.
- **The damping tables' gates are the manual's own**, and the three examples
  that state them round-trip unchanged on both products.

The contract now carries all four supplementary tables, and `ResponseSpectrumLoadCasePayload`
is generated from it. Both documents were left empty. Response bodies stay in
the run's JSON outside the repository.

## 2026-09-22 (later) - `/db/ELEM`'s per-type rows, one at a time

`scripts/live_manual_feedback.py --case c2`, same conditions as the SPLC run
above: empty documents confirmed first, one fresh seeded document per probe,
checkpoints under `C:/temp`. Each probe is one of section 2's Request Bodies on
the seed's nodes, as printed or with one row the per-type table marks Required
left out. Plane Stress has no printed example, so it is the PLATE one with
`TYPE: "PLSTRS"`. A wall has to stand vertically; the first run put it on the
seed's flat plate corners and Gen answered `The geometry of the element no. 10
is incorrect`, so the WALL probes were re-run on Gen on the seed's frame nodes
plus one node below node 3.

| probe | Gen NX | Civil NX |
| --- | --- | --- |
| TENSTR Cable, as printed (no `NON_LEN`) | accepted | accepted |
| TENSTR Cable without `STYPE` | `Errors detected in the Element input data` | same |
| TENSTR Cable without `CABLE` | accepted; reads back `CABLE: 3`, `NON_LEN: 3.2`, no `TENS` | same |
| COMPTR Truss, as printed | accepted | accepted |
| COMPTR Truss without `STYPE` | refused, as above | same |
| PLATE without `STYPE` | accepted; reads back `STYPE: 1` | same |
| PLSTRS with and without `STYPE` | accepted; `STYPE: 1` when omitted | same |
| WALL, as printed | accepted; `W_CON` not in the response or the GET | `The element type no. 5 for the element no. 10 is not supported` |
| WALL without `STYPE` | refused, as above | not supported |
| WALL without `WALL` | `The wall ID no. 0 ... exceeded the possible range ... no. 1 to no. 9999` | not supported |
| WALL without `W_CON` | accepted, identical record | not supported |

What it settles, all of it MD-59:

- **`STYPE` selects the branch and is required where a table's element has
  more than one subtype** - TENSTR, COMPTR, WALL - and **defaults to 1** for
  PLATE and PLSTRS, where the tables also mark it Required.
- **Cable's `CABLE` and `NON_LEN` are not required.** The section's own Cable
  example omits `NON_LEN`; omitting `CABLE` gets Lu with a server-chosen
  length.
- **WALL is a Gen NX element.** Civil refuses the type outright, the chapter's
  own example included, and says nothing about it.
- **`W_CON` is accepted and never returned**, sent or not, and `/info` declares
  it on neither product.

`ElementPayload` is now generated from the contract as a union over
`(TYPE, STYPE)`. Both documents were left empty.

## 2026-09-22 (later still) - `/db/SPFC`'s design codes, and a save dialog `CALC_OPT` leaves behind

### The run that blocked both products

`scripts/live_manual_feedback.py --case c3` first sent each of section 1's
design-code Request Bodies with `CALC_OPT: true` added where the body lacks it
(MD-15: without it or an `aFUNC` the server refuses a design spectrum), one
fresh document per example. On **both** products the first example
(KDS(41-17-00:2019)) was accepted and saved to `C:/temp`, and the `/doc/NEW`
before the second **never answered**; every later call timed out. The author
confirmed a save-changes dialog on both hosts and restarted both products.

So a `CALC_OPT: true` record leaves the document modified again *after* a
`/doc/SAVEAS` - the server-built curve evidently lands later - and the next
`/doc/NEW` raises the save dialog, which blocks the whole API session. None of
the SPLC or ELEM probes earlier the same day, which save and `/doc/NEW` in the
same pattern, did this. **A harness must not `/doc/NEW` after a `CALC_OPT:
true` write without saving again first, or at all.**

### What the examples store

Re-run without `CALC_OPT`: each example carries the section's User Type
`aFUNC` curve instead, all eight in one document, and the table is read back
(this endpoint renumbers a POSTed record). Both products, identical results:

| example | result |
| --- | --- |
| KDS(41-17-00:2019), IBC2012, CH2010, JPN2000, TAIWAN(2022), IS1893(2016), NBC95 | accepted; `STR`, `OPT` and `VAL` stored where the tables put them. The server pads `aSRA` to four entries, and adds `aMSRACC` and `TL` to IBC2012's `VAL` |
| EURO2004, as printed | `Unknown Error` |

`--case c4` then varied the EURO2004 body on Gen one change at a time: `VAL.AG`
for `VAL.ag` (the `/info` spelling), `OPT` removed, and both. All four answer
`Unknown Error`. `/info` declares `SPECTYPE`, `GROUTYPE` and `NATIONALANNEX` in
`STR`, as strings, where the table puts them in `OPT`; no working EURO2004
request was found, and none was guessed. MD-60.

Both documents were left empty.

## 2026-09-22 (last) - `/db/THIS`'s four printed Request Bodies

`scripts/live_manual_feedback.py --case c5`: section 6's four bodies, as
printed, into one fresh seeded document per product, read back by name (the
endpoint renumbers). Empty documents confirmed first, both left empty after.

| body | Gen NX | Civil NX |
| --- | --- | --- |
| Linear + Modal + Transient | stored as sent, plus `bSUBSEQ: false`, `iGEOM: 0` | same |
| Nonlinear + Direct Integration | `Unknown Error` | `Wrong Field` |
| Nonlinear + Static, Load Control | `Wrong Field` | accepted; stored without `ENDTIME`, with `bCUMULATE: false` for the sent `true`, `iMSTEP: 16` for `10`, and `iTHTYPE: 1` added |
| Nonlinear + Static, Displacement Control | `Wrong Field` | accepted; `iMSTEP: 16` for `10`, `ULSM` dropped, `iTHTYPE: 1` added |

The seed model has no nonlinear properties, and a nonlinear time history on
it may simply be unanalysable; these results say the printed nonlinear bodies
do not run on a bare model, not which row is wrong, so no contract row is
corrected from them. What they do show: Civil NX takes a Static record without
`iTHTYPE` (COMMON marks it Required) and rewrites several values it was sent.
Both belong to a session with a nonlinear model before they are claimed.

## 2026-09-22 (after) - `/db/MVHL`: MVLD_CODE picks the country object

`scripts/live_manual_feedback.py --case c6` and `--case c7`, Civil NX, both
documents confirmed empty first and left empty after. Each country got its
own document with its `/db/MVCD` `CODE` from section 1's value table
selected, then section 10's printed body, read back by `VEHICLE_LOAD_NAME`
(the endpoint renumbers).

| body | `MVLD_CODE` | `STANDARD_CODE` sent | result |
| --- | --- | --- | --- |
| KSCE-LSD15 standard | 13 | `"KSCE-LSD15"` | stored as sent |
| KSCE-LSD15 user-defined Truck/Lane | 13 | none | stored as sent, `VEH_KSCE_LSD15` included |
| Canada | 8 | `"CANADA"` | stored; `VEH_CA` read back with `CENT_F` added |
| Australia | 14 | `"ROAD TRAFFIC"` | stored; `VEH_AU` read back with four more members |
| Australia, heading value | 14 | `"AUSTRALIA"` | `Wrong Field` |
| China user-defined Truck/Lane | 3 | none | stored as sent, `VEH_CN` included |
| China, under the Australia code | 3 | none | `{"message": ""}`, nothing stored |
| South Africa | 16 | `"NA"` | `Wrong Field` |
| South Africa without `STANDARD_CODE` (c7) | 16 | none | stored, but without `VEH_ZA` |
| Poland | 15 | `"PN-85/S-10030 - RoadBridge"` | `{"message": ""}`, nothing stored |
| Poland, `MVLD_CODE` 1 to 20 (c7) | 1-20 | same | `{"message": ""}` each, nothing stored |

What this settles: the `VEH_*` object follows the record's `MVLD_CODE`, not
the `STANDARD_CODE` each table's heading names. Two user-defined bodies send
no `STANDARD_CODE` and were stored with their objects; Australia's heading
value is refused where its body's `"ROAD TRAFFIC"`, the name of that table's
first group, is stored. So `STANDARD_CODE` picks a standard within a
country, and the chapter's footnote list of country names is not its value
set. A record whose `MVLD_CODE` is not the model's own code answers exactly
like a success and stores nothing - the same shape as the empty
`VEH_DEFAULT` case.

What it does not settle: why Poland's body stores nothing under any code,
and what `STANDARD_CODE` South Africa's `VEH_ZA` needs. Neither was chased by
varying values the manual does not give. `/db/MVHL`'s contract gates its six
country objects on the `MVLD_CODE` each printed body sends, with Poland's 15
marked unconfirmed (MD-61).

## 2026-09-22 (after) - `/ope/DIVIDEELEM`: the Equal row's axes hold for every method

`scripts/live_manual_feedback.py --case c8`, Civil NX and Gen NX, each body in
its own seeded document (element 1 a 3.2 m beam, element 4 a 4 m square
plate), `/db/ELEM` counted before and after. Empty documents confirmed first
with each product's own key, left empty after.

| body | both products |
| --- | --- |
| Frame Equal, printed (`NUM_X: 10`) | 4 -> 13 elements |
| Frame Unequal, `DIST_X: "2@1.0"` only | 4 -> 6 |
| Frame ParametricUnequal, `RATIO_X: "3@0.3"` only | 4 -> 7 |
| Planar ParametricUnequal, `RATIO_X` and `RATIO_Y` | 4 -> 23 |
| Planar ParametricUnequal, `RATIO_X` only | `Unknown Error`, nothing divided |
| Planar Unequal, printed (`2@2.5`, `2@3.0` on a 4 m plate) | `... second query is wrong` |

The Unequal and ParametricUnequal rows mark X, Y and Z Required with no
condition; the Equal row beside them says which axes each element type uses,
and that rule is what the product applies. The printed Planar Unequal body
failed on its distances, which overrun this plate, not on its shape. Wall and
Solid were not measured and follow the Equal row. MD-62.
