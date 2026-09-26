# Project Plan

High-level architecture, phased roadmap, and milestone plan for `midas-nx`.
For the itemized per-endpoint checklist see the auto-generated
[ROADMAP.md](./ROADMAP.md); this document is the hand-maintained "big picture"
that ROADMAP.md doesn't capture.

> Last updated: 2026-09-23 — **2.9.3 released** (`js-v2.9.3`, `py-v2.9.3`).
> **Nothing executable changed on either side**: `src/midas_nx/` and
> `packages/typescript/src/` are identical to 2.9.2. It publishes the author
> credit (`Dennis`) and a LinkedIn contact into both registries' metadata,
> and the npm README rewritten around getting a first read-only script
> running - it had never said what a MAPI key is or linked the safety guide.
> Also in it, shipped in neither package: `examples/javascript/` with the two
> examples that come first, a TypeScript half for the AI context pack, and three
> retracted findings removed from the published `docs/verification.md`. See
> `docs/release_notes_v2.9.3.md`.
>
> Earlier — 2.9.2 released (`js-v2.9.2`, `py-v2.9.2`).
> npm's generated types now come from the contracts alone: every supplementary
> manual table is merged (or, for `/db/TDME`'s two iGen tables, excluded), the
> arguments held on Python are generated, and 14 exports nothing in the package
> referenced are withdrawn (765 → 751). Against `js-v2.9.1`, **202 members
> become required across 74 types**, 105 are added across 11 and 11 removed
> across 3. Nothing changes at runtime; a patch number by the author's choice,
> breaking at the type level. `src/midas_nx/` is identical to 2.9.1.
>
> Earlier — 2.9.1 released (`js-v2.9.1`, `py-v2.9.1`).
> npm's nested payload types and 44 operation-argument types (with 44 nested
> in them) are now generated from the contracts, so **551 members become
> required across 216 types** and 39 are added across 11, measured against
> `js-v2.9.0`; no export is added, removed or renamed, no member is removed,
> and nothing changes at runtime. A patch number by the author's choice, and
> breaking at the type level. The contracts also list the 70 npm operations
> and 87 table wrappers now, and Python-sourced npm types fall 478 → 162.
> `src/midas_nx/` is identical to 2.9.0. See `docs/release_notes_v2.9.1.md`.
>
> Earlier — 2026-09-21, **no release; nothing packaged changed.** The
> numbers this file states are measured now: `scripts/check_state_numbers.py
> --check` re-derives every count in §2, in the live playbook's state and
> gates blocks and in CLAUDE.md from the artefact that owns it, and fails CI on
> a disagreement or on a claim deleted rather than updated. Its first run found
> §2's fixture counts stale against the fixture itself, and §1 still calling
> the ledger fold pending a day after it landed. Also: the 40 contracts citing
> a read session for a write-level endpoint were audited and none is a contract
> defect, so that decision is closed rather than queued;
> `scripts/report_npm_type_provenance.py` turns "npm generation still reads the
> Python source tree" into a CI ceiling and shows the remainder is almost
> entirely nested objects, one generator capability rather than hundreds of
> gaps; the vendor report is at v1.4, still unsent; and the two live-harness
> guards that keep a failed probe or a guessed save path from costing a whole
> run are now tested.
>
> Earlier — 2026-09-20 (later), **2.9.0 released** (`js-v2.9.0`,
> `py-v2.9.0`): `requires-python` moves from `>=3.12` back to `>=3.11`, and the
> classifiers and CI matrix now span **3.11 through 3.14**. No code changed in
> either package. The floor was never a property of the code — `vermin` puts
> `src/midas_nx`'s real minimum at 3.8 — and v2.1.0 had dropped 3.11 alongside
> 3.9, which was the version actually blocking dependency bumps. 3.11 returns
> measured: 1,090 tests pass on 3.11.15 and on 3.14.5. 3.10 stays out because it
> reaches EOL in October 2026 and `requests`, `pytest` and `mypy` all floor
> there today.
>
> Earlier — 2026-09-20, **2.8.4 released** (`js-v2.8.4`, `py-v2.8.4`):
> `TendonPropertyPayload`'s `FT`, `FPK` and `TDMFNAME` relax from required to
> optional, each carrying the `RM` condition that makes it required, because
> `/db/TDNT` requires them per relaxation model and the type claimed they were
> always needed. Nothing that typechecked against 2.8.3 breaks, and
> `src/midas_nx/` changes only a comment. Also since 2.8.3, none of it shipped:
> live coverage is **208 write / 192 read** (`/db/TDNT`, `/db/POGD` on Civil,
> `/db/POGD-M1`, `/db/MVLDch`, `/db/MVLDid` and `/db/PTNS` earned write
> evidence on Build 09/15/2026); the live fixture is **220 cases over 196
> endpoints, 183 confirmed**, every one replayed by npm on each declared
> product; each of the 40 `/db` endpoints still below write level has a
> recorded reason in `docs/live_verification_playbook.md`, which replaced the
> Codex handoff when that work ended.
>
> Earlier — 2026-09-17, **2.8.3 published** to npm then PyPI (`js-v2.8.3`, `py-v2.8.3`): one npm type narrows
> (`SteelDesignCodeSelectionPayload.DGNCODE` becomes the required literal
> `"KDS 41 30 : 2022"`, because `DESIGN/STEEL/DSTL` is now contracted) and
> `src/midas_nx/` is unchanged. Also since 2.8.2, none of it shipped: npm
> generation **no longer imports `midas_nx`**; all 70 npm operations are named by
> a contract (`/post/PM` and `/post/STEELCODECHECK` contracted, 381 → 384);
> **npm has replayed all 177 confirmed live cases** on every declared product
> (fixture version 6 — per-id DELETE seed steps; `/db/DYFG`/`/db/DYNF` turned out
> to be a selection artefact, not a regression), npm evidence 113 → 162; and
> `DESIGN/STEEL/DSTL` took a PUT on Gen while Civil refused it, so live coverage
> is **201 write / 199 read**.
>
> Earlier — 2026-09-16 (later), **the published 2.8.2 was swept against both
> products on Build 09/15/2026**, each surface installed from its registry:
> 268/268 GET-capable resources answer on Gen and 283/283 on Civil, through PyPI
> and npm alike. That run took `DESIGN/STEEL/DSTL` from the ledger's one
> unverified endpoint to read level on **both** products, so live coverage is now
> **400/400 (200 write / 200 read)**. `/info` moved by exactly one property in the
> patch, identically on both — `/db/SECT` gained `USE_HAMBLY_EQ` on
> `SECT_BEFORE`/`SECT_AFTER`, which the manual documents nowhere yet;
> `schema/info-baseline.json` is deliberately still the 2026-09-03 capture until
> that property has somewhere to live.
>
> Earlier the same day — **2.8.2 published** to PyPI and npm, additive on both:
> `DESIGN/STEEL/DSTL` (the steel design-code selector, not `/db/DSTL`), three
> `/db/MATD` members, `bPJ` on the curved tendon profile, and a corrected
> three-state `OPT_CS` description. The manual repo is reflected through
> `a6947a7` and **CI is fully green** for the first time since 2026-09-06;
> reflecting it moved 108 manual anchors across 59 contracts where the drift
> check had named 11. npm live evidence 70 → 113 `/db` endpoints.
>
> Earlier — 2026-09-15, **2.8.1 published** to PyPI and npm. The npm surface
> carries a **breaking narrowing in a patch number**: three payload types moved
> off the Python fallback onto their contracts, so 16 members that had been
> optional are now required — the fallback emits everything optional, which
> means those types had been claiming *less* than the manual says. Three other
> payload types stop requiring fields that cannot all apply at once, the same
> defect 2.8.0 fixed elsewhere. `src/midas_nx/` changes three trailing comments
> and nothing else. Nine endpoints earned write evidence, taking coverage
> **191 → 200** and npm live evidence **60 → 70**.
>
> **The fixture-to-contract checker went from 41 leads to 1**, and the split is
> the lesson: 28 were a fixture sending less than the manual's own Request Body,
> and 12 were three contracts stating a branch member's requiredness without
> its branch. Same shape as MD-16. What remains is `/db/ACTL`, settled product
> behaviour.
>
> **Four official worked examples were measured and do not work** (MD-53
> through MD-56). `/db/FIMP`'s is checkable without a product at all: the
> printed `ECU=0.003` fails the inequality the product states in its own error
> text, `0.8/100 + 0.002 = 0.010`. No replacement value was invented for any of
> the four; each case stays unconfirmed.
>
> Earlier, and still worth keeping:
>
> **The finding worth keeping is about a checker, not an endpoint.**
> `check_fixture_contract.py` reported 64, then 81 split 54/27, then 41/2 — and
> all three corrections were defects in the thing doing the counting. The 81
> version read only a contract's base `fields`, so a name declared in a
> `variant` counted as recorded nowhere and a `required` field carrying an
> `appliesWhen` counted as missing from every payload. 38 of the 81 were
> phantom, and before that was found the number had reached this file, the live
> notes, a published GitHub Release body, and a 21-item task list handed to
> another agent that described nothing real. **A checker comparing two artefacts
> is itself a third claim about the shape**; confirm a sample of its findings by
> hand before reporting a count as a fact.
>
> Earlier in the same day: the live harness seam closed 09-05, and chapter 08's
> moving-load and lane family gained thirteen live cases, taking write coverage
> **173 → 185**. Both harnesses agree on all of them.
>
> The finding worth keeping from that batch is a **second seed collision in two
> days**. Every lane tier seeds the same single-row `/db/MVCD` code selector by
> POST, so the first tier in a selection won and every later one answered `Key
> Already Exist`, blocking five cases that pass individually. The seed now
> POSTs and falls back to PUT — deliberately, rather than reading the record
> and branching, because a seed that reads state back is one the npm harness
> cannot replay, and the first attempt at this fix silently took all thirteen
> cases away from npm until the emitter caught it. **A seed owning a fixed id
> is a shared resource whether or not it was written as one.** A one-value
> fix in both packages, and the value is one the server was refusing.
> `/post/TABLE`'s surface-spring reaction type is `REACTIONLSURFACESPRING`,
> with an L that the Specifications table and the JSON Schema enum both drop.
> Only the section's request example has it. The contract had followed the
> other two on the reasoning that two sources beat one, and **both products
> refuse the majority spelling** — so every caller of that one table type got
> an error instead of a table, in both languages, for as long as the constant
> has existed. Nothing is removed and no name moves; calls that failed start
> working.
>
> **A wire value is not a majority opinion**, and this release is the
> measurement. The same live run asked the other `/post/TABLE` contradiction
> — `BEAMFORCESTP` against the schema enum's `BEAMFORCESIP` — and there the
> identical 2-1 reading was right. Three documents agreeing is three
> transcriptions of one source, so a 2-1 split carries no information at all
> about which way the server goes. Both contracts had said so honestly, with
> `resolved: false` and "nobody has asked the server"; the answer took one
> call each.
> `tests/test_contracts.py::test_a_table_type_contradiction_is_settled_live_or_left_open`
> now refuses to let a `describes: table_type` defect be marked resolved on
> anything but a live check. Result-table contradictions 2 → 0.
>
> **Every non-`/TEMP` crash path was re-checked on build 09/02/2026, and none
> reproduces.** Eight Design Forces `TABLE_TYPE`s, the three
> `/DESIGN/RC/KDS-41-20-2022/TABLE` variants, `/ope/EDMP`, `/ope/USLC`,
> `PUT /db/THNL`, and a raw `/db/NMAS` with `rmX`/`rmY`/`rmZ` omitted, on both
> products. Every risky call was followed by a real `GET /db/NODE` rather than
> `verify_connection()`, which answers "connected" through the relay while a
> modal dialog holds the session and therefore cannot tell a live session from
> a blocked one. **Nothing is cleared.** The design-forces docstrings record
> the independent second blank-document pass they had asked for and say in the
> same breath that a populated, analysed, designed model was not exercised;
> the NMAS mitigation stays, because an uninitialized read is exactly the
> defect that hides when the memory happens to be zero.
>
> **`/db/STRPSSM` moved read → write**, and the reason is worth keeping: the
> fixture had been failing `Wrong Field` since 2026-08-16 under a recorded
> guess that it needed a genuine PSC/RC section. It needed `Y`/`Z` — the
> manual's `PY`/`PZ` were `/info`'s *descriptions*, taken for the keys (MD-38).
> 172 → 173 write, 227 → 226 read.
>
> **The `/info` sweep is a standing check now.** `info_baseline.py
> --against-contracts --check` holds a per-endpoint ceiling and runs in CI, so
> a count going down passes and a new or growing difference fails. Keyed per
> endpoint deliberately: a single total would let one contract lose a property
> while another gains one, and the value of that sweep is in the small numbers
> — a count of one or two is what a missing table row looks like, while
> `/db/SECT`'s 995 is the section-property tree and means nothing.
>
> npm live evidence 23 → 32 `/db` endpoints on both products, which also
> exposed a gap worth naming: `schema/live-cases.json` emits each case's own
> setup but not the common base model Python's harness builds first, so the
> npm harness cannot run thirteen confirmed cases and prints `REGRESS` for
> them. That is a hole in the file's claim to be the language-neutral source,
> not a package regression.
>
> **Closed 2026-09-05, in two passes, and the second one was the real hole.**
> Sharing the base model closed only the common prefix: Python's runner
> executes **every seed step of a selected tier** whatever the cases' `needs`
> say, while npm replays only what the fixture emitted for that case. Fixture
> **version 5** exports every tier seed npm can replay — 34 of 37, the boundary
> being a sequence of `{"Assign": ...}` POSTs captured from the seed step's own
> calls — and names the other three in `unsupportedSeeds` **with the reason**,
> so the four cases needing them are refused rather than run half-seeded. Cases
> carrying setup 21 → 66. Confirmed live on both products: all fifteen affected
> endpoints PASS on both harnesses, and npm live evidence is **47 `/db`
> endpoints**.
>
> Both harnesses now also **read a result the same way**. A failure before the
> endpoint under test is touched is `BLOCK` and exit 3 — "triage the fixture"
> — not `REGRESS` and exit 1. npm never had that class, and Python had it only
> for a seed step that threw: a pre-existing cross-tier id collision on Civil
> (`/db/SPLC`, whose id extras4's Civil-only seed occupies) reported as a
> regression on a shape both products accept. Two harnesses reading one fixture
> must also read one result, or comparing them measures the harnesses.

---

## 1. Architecture map

The repository maintains two packaged language surfaces, and is migrating to a language-neutral
contract as the source of truth for both. Historically Python was the reviewed implementation *and*
the endpoint-metadata source for npm generation — which is how the npm package shipped a month after
`/db/NMAS`'s crash workaround without it: the generator carries metadata and docstrings, and that
workaround was behaviour inside a method. `contracts/` now holds endpoint shape and safety rules as
facts about the API, sourced from the manual repo, live verification records and `/info`
introspection — never from either SDK. Both surfaces still share `docs/coverage.json`, which since
2026-09-21 is the implementation inventory and nothing else: the live evidence it used to carry
per endpoint moved into `contracts/verification/ledger.yaml`, one record per session, resolved
into per-endpoint claims by `scripts/verification_ledger.py`. That fold is done.

```text
contracts/                        language-neutral source of truth (see contracts/README.md)
├── schema/                       JSON Schema for an endpoint contract
├── endpoints/                    one YAML per endpoint — 384 endpoint contracts so far
├── safety/                       cross-endpoint client rules + known product defects
└── verification/                 ledger.yaml — the live-evidence ledger, one record per
                                  session; {gen,civil}-nx.yaml — dated findings contracts cite
src/midas_nx/                     Python package (PyPI: midas-nx)
packages/typescript/              JavaScript/TypeScript package (npm: midas-nx)
├── src/generated/                generated resources, operations, tables, payload types
├── src/{client,db-resource,...}  hand-written runtime and safety behavior
└── tests/                        Vitest unit and public-type coverage
scripts/generate_typescript_sdk.py
scripts/validate_contracts.py     validates contracts, then checks both SDKs against them
schema/typescript-*.json          committed cross-language generation ledgers
```

### Python package

```text
midas_nx/
├── client.py            MidasClient — instance-based HTTP + auth, typed errors,
│                        Product.GEN|CIVIL selection, strict_product guard.
│                        Also: configure()/MidasAPI() low-level free-function API,
│                        .verify_connection() (/mapikey/verify health check).
├── doc.py               /doc/*, /ope/*, /view/* lifecycle — plain functions,
│                        wrapped in "Argument" (not ID-keyed "Assign").
└── db/
    ├── base.py          DbResource — .create/.get/.update/.delete/.info()/
    │                    .items() classmethods (.info() = /info/db/... schema
    │                    introspection, independent of METHODS/CRUD;
    │                    .items() = ID-keyed GET-response unwrap, v0.11.0),
    │                    METHODS/PRODUCTS guards, shared NO_DELETE_METHODS +
    │                    ItemGroupFields TypedDict.
    ├── project.py       ch 02  Project structure, groups, colors, story
    ├── node_element.py  ch 03  Node/Element/Skew/Domain
    ├── properties/      ch 04  material · section · thickness · hinge · damping
    ├── boundary.py      ch 05  constraints · springs · links · seismic devices
    ├── static_loads.py  ch 06  static/earth-pressure/wind/seismic loads
    ├── temperature_prestress.py  ch 07  temperature loads · tendons · prestress
    ├── dynamic_loads.py ch 09  response spectrum · time history
    ├── construction_stage.py     ch 10  stages · composite sections · hydration
    ├── misc_loads.py    ch 11  settlement · wave loads · initial forces
    ├── analysis_control.py       ch 12  main/P-Delta/buckling/eigenvalue/
    │                    nonlinear/construction-stage/moving-load control
    ├── load_combinations.py      ch 13  LCOM-* combinations · cutting lines
    ├── pushover.py       ch 14  pushover global control · load cases
    ├── moving_loads.py   ch 08  traffic lanes · vehicles · moving load cases
    │                    (country variants) · dynamic factors (civil-only)
    ├── bridge.py         ch 17  girder diagrams · camber control · cable
    │                    unknown-load-factor constraints (civil-only)
    └── design.py         ch 24  pre-design-calc input: RC/steel code select,
                         rebar-check input, unbraced length, design member
                         assignment, frame def, slenderness limits, rebar overrides
├── ope.py                ch 15  GUI/preprocessing operations (element divide,
│                        auto-mesh, LCOM-* auto-generation, gust factor, ...)
│                        — plain functions, one TypedDict argument each.
├── view.py               ch 16  model view control (selection, capture,
│                        viewpoint, active target, display, result graphics)
│                        — plain functions, one TypedDict argument each.
├── design/               DESIGN/<STEEL|RC|SRC>/<code>/<ENDPOINT> — a
│                        different namespace from /db/*; mixes DbResource-style
│                        config/member-CRUD endpoints with plain POST-action
│                        functions (design-execution/table/report/image) that
│                        reuse post/base.py's NodeElemsSelector/TableUnit/
│                        TableStyles.
│   ├── steel_kds.py       ch 25  Steel design code KDS 41 30:2022 setup,
│   │                    per-member design parameters, material overrides,
│   │                    design-execution/result-table/report/image (27/27)
│   ├── rc_kds/            ch 26  RC design code KDS 41 20:2022 (69/69 ✦✦,
│   │   │                largest chapter in the project — split into 4 files,
│   │   │                mirrors db/properties/'s subpackage-per-oversized-
│   │   │                chapter precedent):
│   │   ├── setup.py       design code/frame/load-combination setup, seismic
│   │   │                params, per-member design params (19)
│   │   ├── rebar.py       moment/torsion/rebar-ratio params, wall/rebar-
│   │   │                design-criteria, beam/column/wall/brace rebar
│   │   │                overrides (19)
│   │   ├── design_forces.py  design-execution/table/report per member type:
│   │   │                beam/column/brace/wall/haunched-beam (15)
│   │   └── checks.py      code-check/table/report per member type, plus
│   │                    comprehensive design result and column/brace/beam
│   │                    design-forces tables — the latter 3 share one real
│   │                    HTTP endpoint (TABLE) selected by Argument.TABLE_TYPE,
│   │                    mirroring post/design.py's shared-helper pattern (16)
│   └── src_aiksrc2k.py    ch 27  SRC design code AIK-SRC2K setup, per-member
│                        design parameters, check-execution/result-table/
│                        report, optimal design, material/section overrides
│                        (27/27, single self-contained file — no cross-chapter
│                        TypedDict reuse with steel_kds.py/rc_kds/*, per this
│                        subtree's established convention)
└── post/                 POST /post/* result extraction — plain functions,
    │                    wrapped in "Argument" (same convention as doc.py).
    ├── base.py           get_table() — shared /post/TABLE plumbing (one
    │                    endpoint, TABLE_TYPE selects the table; no
    │                    DbResource-per-type since there's one real endpoint).
    ├── pre_process.py    ch 18  element weight · mass/load summary · material ·
    │                    section · supports · story mass/load/weight (10 types)
    ├── result_1.py       ch 19-20  reaction/displacement/truss/cable/beam/
    │                    plate/plane/solid/link/mode-shape/tendon results (50 types)
    ├── story.py          ch 21  story drift/displacement/shear/eccentricity/
    │                    irregularity-check tables (17 types)
    └── design.py         ch 23  P-M diagram · steel code check · design
                         forces (RC/steel/SRC/cold-formed) (10 endpoints)
```

**`ope.py`/`view.py` convention**: like `doc.py`, bodies are wrapped in a plain
`"Argument"` key (not ID-keyed `"Assign"`). But unlike `doc.py`'s few-named-
kwargs style, most ch15/16 endpoints have deeply-nested, highly-optional
bodies (10+ levels in places, e.g. `/view/DISPLAY`'s ~90 boolean toggles), so
each POST function takes one `TypedDict` `argument` parameter instead —
mirroring the `db/*.py` payload-typing style but at the whole-body level.

**Design invariants** (keep these as new chapters land):
- One `DbResource` subclass per endpoint; `TypedDict` payloads document schema
  (no runtime validation — schemas are too conditional).
- Deeply-conditional sub-objects fall back to `Any` (see `SectBefore.SECT_I`);
  only the common envelope is fully typed.
- Every endpoint gets a `responses`-mocked test asserting request shape.
- Coverage tracked in `docs/coverage.json`; `ROADMAP.md` regenerated from it.

---

## 2. Current status (endpoint table as of 2026-07-29; package surfaces updated 2026-08-27)

| Area | Chapters | Endpoints | State |
|---|---|---|---|
| Lifecycle | 01 | 11/11 | ✅ done |
| Core modeling | 02, 03 | 21/21 | ✅ done |
| Properties | 04 | 32/32 | ✅ done |
| Boundary | 05 | 24/24 | ✅ done |
| Static loads | 06 | 21/21 | ✅ done |
| **Phase 1 — analyzable model** | 07, 09, 10, 11 | **47/47** | ✅ done |
| **Phase 2 — analysis control + results out** | 12–14, 18–21, 23 | **48/48 rows** | ✅ done |
| **Phase 3 — operations & view** | 15, 16 | **26/26** | ✅ done |
| **Phase 4 — civil bridge specialization** | 08, 17 | **32/32** | ✅ done |
| **Phase 5a — design setup + steel code** | 24, 25 | **40/40** | ✅ done |
| **Phase 5b — RC design code** | 26 | **70/70** | ✅ done |
| **Phase 5c — SRC design code** | 27 | **27/27** | ✅ done |
| **Total** | | **400/400 (100%)** | 390/398 published through v0.11.2, the last 8 landed 2026-07-29; `+1` on 2026-08-07 — `DESIGN/RC/DRC` (RC design code selection), a chapter-26 endpoint newly documented in the manual repo's 2026-08-06 sync (MAPI-1365); `+1` on 2026-09-16 — `DESIGN/STEEL/DSTL`, its chapter-25 steel counterpart, documented in the 2026-09-06 sync. Not the same endpoint as `/db/DSTL`, which shares the name |

> The last 8 rows (STYP-M1, MATL-M1, IMFM-M1, EPMT-M1, IEHG-{BEAM,TRUSS,GL,
> PSS}-M1) had no JSON Schema in the manual repo to transcribe from — this
> was v1.0.0 gate item (a). Resolved 2026-07-29 by deriving their payload
> TypedDicts from live `GET /info/db/...` server introspection instead
> (confirmed for 5 of 8; the other 3 — IEHG-TRUSS/GL/PSS-M1 — have no
> `/info` route at all, so their shape is assumed by sibling analogy to
> IEHG-BEAM-M1, not independently confirmed). Documented in-module as
> server-derived, not manual-transcribed. Every documented endpoint across
> all 27 chapters is now implemented.

Non-endpoint status as of **v2.0.0** (these are the axes Phases 6-8 move, and
they're the ones worth re-checking before planning a release):

| Axis | Artifact | State |
|---|---|---|
| Tests | 1164 Python tests + 90 Vitest tests, mocked/local only | ✅ green, all of it. The contract-to-manual test that had failed on purpose since 2026-09-06 passes again: the manual repo's syncs through `a6947a7` (2026-09-15) were reflected 2026-09-16 |
| CI | `.github/workflows/ci.yml` — Python checks on 3.11/3.12/3.13/3.14 plus npm generation/typecheck/tests/package smoke on Node.js 18/22, push+PR | ✅ running |
| Static typing | mypy over `src/midas_nx`, config in `pyproject.toml`, own CI job | ✅ clean across all 41 modules |
| Packaging verification | `package` CI job + `scripts/wheel_smoke_test.py` — builds the wheel, installs it into a clean venv, asserts `py.typed` shipped, `__version__` matches the distribution, and the `delete_all()` guard is armed | ✅ running |
| TypeScript/npm SDK | `packages/typescript/` — ESM + CommonJS + declarations, Node.js 18+, Vitest/typecheck/build and packed-artifact smoke tests | ✅ npm `midas-nx` 2.9.3 published 2026-09-23; `js-v*` OIDC workflow and npm Trusted Publisher registration completed 2026-08-27. Versions have moved in lockstep with PyPI since 2.6.0 |
| Cross-language generation | `scripts/generate_typescript_sdk.py`, `schema/typescript-{resources,coverage}.json`, `packages/typescript/src/generated/` | ✅ generated outputs committed; CI rejects drift. ⚠️ CI was red on `main` 2026-08-27 (`dcb98e0`..`21034f3`) because the committed npm surface had gone stale against its own generator — **py-v2.3.5 was tagged while it was red**. Fixed in `f303fd7`; the drift gate works, nobody read it |
| Language-neutral contracts | `contracts/` + `scripts/{extract,promote,validate}_contract*.py`, own CI job | 🚧 **384 endpoints + 87 result tables**, 5,576 fields, every npm operation named by a contract, with **3** drafts awaiting review (`extract_contracts.py --report`, not raw ignored draft files). Drafted from the manual by `extract_contracts.py`, promoted by `promote_contract.py`. Validates schema, cross-references, safety-rule coverage, manual drift, and **parity against both SDKs** — a disagreement is an SDK defect, not a reason to edit the contract. It has caught: npm able to crash a live NX session on `/db/NMAS`; `/db/GRUP` claiming a DELETE it does not serve; `/db/RIGD`/`/db/OFFS` flattening an `ITEMS` array; 7 endpoints wrongly called Civil-only; and — since the fifth check, `check_field_parity`, started comparing **field names** on 2026-09-04 — twelve contracts that had fallen behind their own SDK, three of them publishing a flat record the server has never accepted |
| Fixture ↔ contract agreement | `scripts/check_fixture_contract.py --check`, own CI step | ✅ **1 fixture lead on 1 endpoint** and **3 contract gaps on 2 `confirmed` endpoints**, down from 41 leads across 5. The fourth artefact claiming to know an endpoint's shape was the one nothing checked, and what it found split two ways: `/db/GRDP`'s 28 were a fixture sending less than the manual's own Request Body, and 12 more were three contracts stating a branch member's requiredness without its branch — `/db/MVCT`, `/db/NLNK-M1` and `/db/TDMF`, all three now carrying `appliesWhen`, which is what 2.8.1 shipped to npm. What is left is `/db/ACTL`, settled product behaviour. It first reported 81 and then 64; both were its own defects, corrected 2026-09-06 — it had read only a contract's base `fields`, so a name declared in a `variant` and a `required` field carrying an `appliesWhen` both counted as defects. Held in CI in both directions; nothing merged, because a fixture is never a source for a contract |
| Omission safety | `safeToOmit` in every contract field | 🚧 146 proven safe from confirmed live payloads, 8 proven unsafe, **5,422 honestly unverified** (5,576 fields, 2026-09-22). The proven-safe count went *down* in 2.7.7: `/db/LLAN`'s contract published a flat record, so promotion compared a confirmed live payload's top-level keys against a flat field list and manufactured ten `safeToOmit: true` claims nobody had earned. The manual saying "Optional" is not evidence — that is what `documentedOptional` records, and `/db/NMAS` is where believing it kills the session |
| Destructive-op safety | `delete()` per-id URL; `delete_all(confirm=True)` required, else `DestructiveOperationError` before sending | ✅ guarded |
| Docs site | MkDocs Material + mkdocstrings (`mkdocs.yml`), built `--strict` on every PR | ✅ live at `dennis5882.github.io/MIDAS-API-NX-SDK/` (confirmed 2026-08-04 — this row had drifted stale, saying "GitHub Pages not yet enabled" after it already was) |
| Stated numbers | `scripts/check_state_numbers.py --check`, own CI step | ✅ every number this plan's §2, the live playbook's state block and its gates block state about the repository are re-derived from the artefact that owns each and compared; a pattern no document states any more fails too, so deleting the sentence is not a way to pass. Its first run found §2's fixture counts stale against the fixture itself — and against this file's own header four sections above. It deliberately reads neither that dated header nor §4, because a milestone row is correct precisely because nobody rewrote it |
| npm type provenance | `scripts/report_npm_type_provenance.py --check`, own CI step | ✅ **0 of 751 generated npm types still come from the Python source tree**, held as a ceiling that can fall but not rise. Since 2026-09-21/22 contracts own nested payload types (`surface.nestedTypes`), the operation and table-wrapper lists (operation `surface` and table `surface`), operation argument types with their nested types, each table's own request objects (`requestFields.additional`), and where every contract-built type is placed - Python supplies nothing for a type a contract owns. Nothing is left (the 0 `unmergedTables` roots left since 2026-09-22 add nothing): the last 14 were exported names nothing in the generated SDK referenced, withdrawn at the author's request and listed in the generator's `_PYTHON_TYPES_WITHDRAWN`. The Python source tree is still read for the IEHG trio's resource identity, which has no permitted source to contract - the provenance script's docstring records how it got there. That read is generation-time and local to this repo: the generator imports nothing, and the published npm package declares no dependencies and ships `dist/` alone, so no npm user reaches Python or PyPI |
| Manual drift | `manual-drift-check.yml` (`cron: 0 3 * * 3`) + `scripts/check_manual_drift.py` | ✅ running |
| Schema drift (live) | `scripts/check_drift.py` (`/info/db/...` vs TypedDict) | ✅ local dev tool |
| Scaffolding | `scripts/gen_endpoint.py` | ✅ in the documented add-an-endpoint loop |
| Response handling | 200-with-`error` body, non-JSON body, empty-table shapes, failed-analysis message | ✅ hardened in v0.12.0/v0.14.0 |
| Write verification | `scripts/live_crud_check.py` and `packages/typescript/scripts/live-crud.mjs`, both replaying `schema/live-cases.json` v6 — create/read/update/delete round trips, **183 of 220 cases confirmed, and npm has replayed all 183** on every product each declares (2026-09-18). v6 added per-id DELETE seed steps, so no seed is unexportable any more | ✅ `/db/STRPSSM` joined the confirmed set on Civil NX 2026 v2.2 after replacing the stale manual `PY`/`PZ` point keys with live `/info`'s `Y`/`Z`. `/db/NMAS` used to crash **both** products, root-caused 2026-07-29 (omitted `rmX`/`rmY`/`rmZ`) and worked around in `NodalMass.create()`/`.update()` |
| Version metadata | `__init__.py` `__version__` (hatchling `dynamic`) + `tests/test_version.py` + a tag↔`__version__` check in `publish.yml` | ✅ single source, enforced at release |
| Live verification | `scripts/live_smoke.py` (write round trip), `scripts/live_readonly_sweep.py` (GET breadth) | ✅ 400/400 recorded in `contracts/verification/ledger.yaml`, split by `level`: **208 write / 192 read** as of 2026-09-21 — `DESIGN/STEEL/DSTL` answered at read level on both products on 2026-09-16, then took the documented PUT on Gen NX on 2026-09-17 while Civil NX refused it, so its entry is write on Gen. Write level means a call changed model data or wrote a host file; read includes route/schema checks and POST-shaped reads. The build baseline is Gen NX 2026 v2.1 and Civil NX 2026 v2.2, both **Build 09/15/2026**, each read from its own About dialog and author-confirmed 2026-09-16. Five entries dated 2026-09-06 had recorded 08/26 and 08/27 and were corrected: **the API reports no build anywhere**, so every such string is a human reading the About dialog and one that was not read is not a measurement. |
| Onboarding docs | `docs/{ko,en,zh-tw}/quickstart.md` and `docs/npm/quickstart{,-ko,-zh-tw}.md`, `docs/ai-coding/`, `AGENTS.md`, `docs/index.md`, `docs/safety.md` risk levels, `docs/recipes/`, `docs/ko/python-basics.md`, `examples/{python,javascript}/` | ✅ first example read-only + AI-assistant path (v2.1.2); recipe pilot + ko minimal-Python primer + real-session-verified MAPI key step (2026-08-04). 2026-09-23 closed the npm side, which had none of it: its own quickstart in three languages (the Python one opens with "Install Python"), a TypeScript context pack, Python/TypeScript tabs on the recipes, four JavaScript examples against Python's four, and `AGENTS.md` so an arriving agent does not read `CLAUDE.md` as a user guide; ⚠️ still text-only, no screenshots |
| Practitioner layer | Excel round-trip, `recipes`/`easy`, opt-in validation | ❌ not started |

### Write-verification priority

All 399 implemented endpoints answer a live GET or write; **207 have had a
write round trip proven** against a real server, as of 2026-09-20 (see the
"Live verification" row above — this count has grown across many sessions
since the `scripts/live_crud_check.py` tiers below were first built, not in
one pass). Answering a GET says an endpoint exists; only a round trip says
the SDK's write shape is the one the server accepts. The tiers below were
the original push that closed that gap, ordered by what a real modelling
script reaches for rather than by manual chapter — kept here as the
still-accurate origin story, not a live count:

| Tier | Covers | Why here |
|---|---|---|
| `core` | groups, nodes, elements, load cases, nodal/beam loads, constraints | the original 10; the regression baseline, proven on Gen since 2026-07-26 |
| `props` | THIK, ESSF, SECF, TSGR, TDMT/TDME/TMAT | every model picks a thickness and a stiffness factor; creep/shrinkage gates PSC and construction stages |
| `boundary` | NSPR, GSTP/GSPR, ELNK, RIGD, MCON, FRLS, OFFS, SSPS | springs and links are the boundary conditions scripts actually write; CONS alone isn't a model |
| `static` | SDSP, NMAS, LTOM, NBOF, FBLD, PSLT, PRES + ch07 ETMP/NTMP | the ch06 remainder, plus the two temperature loads that behave like static loads |
| `stage` | STAG, TMLD, CRPC, CMCS | needs groups by name and a stage id to attach to, so it comes after both |
| `moving` | LLAN, MVHL, MVHC, MVLD (Civil) | last: Civil-only, and the longest prerequisite chain (code → lane → vehicle → case) |

What the live runs settled (see `docs/live_verification_notes.md` for the
evidence): the `boundary` tier passed 9/9 first time, `stage` 4/4 and `moving`
4/4 after fixture fixes, and three defects surfaced that no mocked test could
have caught — `/db/SECF` is keyed by section id and the SDK's docstring said
element id; `/db/MVHL` accepts a `VEHICLE_TYPE_NAME` no standard vehicle has
and stores it verbatim; and `/db/TDMT` and
`/db/TDME` spell the same code differently
(`CODE: "CEB_FIP_2010"`/`"KDS_2016"` vs. `CODENAME: "CEB-FIP(2010)"`/
`"KDS-2016"`) — both documented correctly by the official articles, but easy
to cross-feed and get a false "Wrong Field". One product defect looked severe
enough to gate permanently: **`POST /db/NMAS` crashed both Civil NX and Gen
NX** across 15+ reproductions (multiple Civil versions/builds, a real
production model, a from-scratch minimal model, both products) — until
2026-07-29's root-cause session found it only happens when the optional
`rmX`/`rmY`/`rmZ` fields are omitted, and doesn't when they're sent
explicitly (even as `0.0`, their documented default). `NodalMass.create()`/
`.update()` now fill them in automatically, so the case runs unquarantined
and confirmed. Two more documented-value defects
turned up: `/db/PRES`'s documented default `DIRECTION` of `"NORMAL"` is
rejected on a plate face and omitting the field fails the same way (though
the official article's own footnote already documents this — see the B-4
narrowing in `docs/live_verification_notes.md`); and `/db/CMCS`'s `PRODUCTS`
was corrected to Civil-only after three independent sessions all 404'd it
under Gen despite the manual listing both.

Two rules make the fixtures trustworthy, because on the first Civil run every
failure was a bad fixture rather than an SDK defect. Seeded records go in at
the lowest free key and their case takes the *next* one, so key-honouring
tables (`/db/NODE`) and renumbering tables (`/db/STLD`) land on the same id
either way; and nothing a case deletes is another case's prerequisite. The
report separates a **regression** (a case confirmed live that broke — an SDK
defect suspect, exit 1) from an **unverified failure** (a case that has never
passed, so triage the payload first, exit 3) from a **blocked** case (its
tier's seed failed). A case is only marked `confirmed=True` after it has been
watched passing.

Velocity reference: the 02–06 build added 76 endpoints in one pass; Phase 1
(07/09/10/11) added another 47 in a second pass; Phase 2 (12–14, 18–21, 23)
added 48 rows (~118 real functions/classes) in a third pass; Phase 3 (15, 16)
added 26 endpoints (131 real functions/classes across ope.py + view.py) in a
fourth pass; Phase 4 (08, 17) added 32 endpoints (90 real classes across
moving_loads.py + bridge.py) in a fifth pass; Phase 5a (24, 25) added 40
endpoints (122 real classes/functions across db/design.py + design/steel_kds.py)
in a sixth pass; Phase 5b (26) added 69 endpoints (173 real classes/functions
across design/rc_kds/'s 4 files) in a seventh pass; Phase 5c (27) added 27
endpoints (~68 real classes/functions across design/src_aiksrc2k.py) in an
eighth and final pass — all eight followed the same fixed
transcribe→type→test→mark-coverage loop (see §5), with Phase 2's ch19-20/ch21,
Phase 3's ch15/ch16, Phase 4's ch08, Phase 5a's ch24+ch25 (in parallel), Phase
5b's ch26 (split 4 ways in parallel — the first time a single chapter itself
needed splitting across multiple agents), and Phase 5c's ch27 (small enough,
at 7,148 manual lines, to fit back into a single background-agent pass like
ch25) each delegated to background agents following that same established
pattern.

---

## 3. Phased roadmap

Phases are ordered by (a) unlocking a complete analyzable model first, then
(b) getting results back out, then (c) specialization. Sizing is by documented
rows; ✦ marks chapters whose real endpoint count far exceeds their row count.

### Phase 1 ✅ — Complete the analyzable model  ·  47/47 endpoints  ·  v0.2.0
Everything needed to define a full model that MIDAS can actually run.
- ch 07 Temperature / Prestress (12/12)
- ch 09 Dynamic Loads (12/12)
- ch 10 Construction Stage (14/14)
- ch 11 Settlement / Misc Loads (9/9)

### Phase 2 ✅ — Analysis control + results out  ·  48/48 rows ✦  ·  v0.3.0
Configure the run and read results back — the payoff phase.
- ch 12 Analysis Control (21/21)
- ch 13 Load Combinations (8/8)
- ch 14 Pushover (6/6)
- ch 18–21 POST result/story tables (4 aggregate rows ✦ → 87 real functions:
  10 pre-process + 50 analysis-result + 17 story table types)
- ch 23 POST Design forces (10/10)

### Phase 3 ✅ — Operations & view  ·  26/26 endpoints  ·  v0.4.0
- ch 15 OPE operations (19/19)
- ch 16 VIEW select/capture/display (7/7)

### Phase 4 ✅ — Civil bridge specialization  ·  32/32 endpoints (civil-only)  ·  v0.5.0
- ch 08 Moving Loads (28/28, civil-only)
- ch 17 Bridge diagrams/cable/camber (4/4, civil-only)

### Phase 5 — Design code checks  ·  ~136 real endpoints ✦  ·  split by code
The largest chunk — split into per-code sub-phases (confirmed necessary after
measuring source density: ch26 alone is 13,363 manual lines / 69 endpoints,
3x any chapter built so far), each its own release rather than one big bang.

- **Phase 5a ✅ — Design setup + Steel code  ·  40/40 endpoints  ·  v0.6.0**
  - ch 24 DB Design setup (13/13)
  - ch 25 Steel KDS 41 30:2022 (27/27 ✦)
- **Phase 5b ✅ — RC design code  ·  69/69 endpoints ✦  ·  v0.7.0**
  - ch 26 RC KDS 41 20:2022 (69/69) — largest single chapter in the project
    (13,363 manual lines); split into 4 parallel background-agent passes by
    natural endpoint-group boundary (setup items 1-19, rebar/member items
    20-38, design-execution items 39-53, checks+tables items 54-69), each
    writing to its own file under a new `design/rc_kds/` subpackage. No
    cross-chapter TypedDict reuse with ch25 materialized in practice — RC's
    field sets differ enough per-endpoint (even for same-named endpoints
    like DCO/MBTP/MLLR/HCBM) that local-per-chapter shapes stayed the right
    call; `design/base.py` remains unbuilt.
- **Phase 5c ✅ — SRC design code  ·  27/27 endpoints ✦  ·  v0.8.0**
  - ch 27 SRC AIK-SRC2K (27) — same DCO/DCTL/LLRF/... setup + check-triplet
    structure as ch25/26; at 7,148 manual lines it was close in size to
    ch25 (6,199 lines/27 endpoints), so it fit in a single background-agent
    pass rather than ch26's four-way split. Kept fully self-contained (no
    cross-chapter TypedDict reuse with steel_kds.py/rc_kds/*), matching
    Phase 5b's finding that same-named endpoints (DCTL/MBTP/...) still
    differ enough field-for-field across codes that local shapes are the
    right call.
- **v0.9.0 ✅ — Live Gen/Civil NX verification + PyPI discoverability**
  — no new chapter work; extensive live-session verification against real
  Gen NX / Civil NX (see docs/live_verification_notes.md — confirmed a
  reproducible Gen NX application defect in the RC-KDS "perform design
  check" family, confirmed the full Civil analyze→results chain including
  moving loads) plus PyPI-page improvements (`py.typed` marker, classifiers,
  keywords, project URLs, README install/use-cases/multilingual intro).
- **v0.9.1 ✅ — Live-manual schema sync**
  — no new chapter work; the vendored manual's `/ope/GSBG` article changed
  schema between 2026-07-12 (the "확인 필요"/unconfirmed draft this was
  originally transcribed from) and 2026-07-14 (`LC_TYPE` dropped,
  `BATCH_LIST` changed from an object array to a plain string array).
  Updated `BridgeGirderDiagramArgument` + its tests to match; no other
  endpoint affected by that manual update.
- **v0.10.0 ✅ — Connection/introspection helpers**
  — `MidasClient.verify_connection()` (`/mapikey/verify` health check) and
  `DbResource.info()` (`/info/db/...` schema introspection, a fallback for
  fields/endpoints this SDK hasn't wrapped yet). Source: the manual repo's
  docs/AUTHENTICATION.md (a cross-cutting auth/ops guide, not a per-chapter
  manual page) — not tracked in docs/coverage.json/ROADMAP.md for that
  reason, so the 390/398 count is unchanged. Also ported the manual repo's
  simple-beam load-combination tutorial to `examples/python/`, and added a
  README Troubleshooting section (connection errors, firewall/SSL-inspection
  allowlist).
- **v0.11.0 ✅ — Phase 6 tooling** (see Phase 6 below for the itemized list):
  CI, weekly manual-drift job, drift/scaffolding/smoke scripts,
  `DbResource.items()`, error hints, ko/en/zh-tw guides.
- **v0.11.1 ✅ — Manual-sync correctness fix**
  — the vendored manual's `DCRM-WALL` changed schema (breaking); added the
  Wall Force result table and the story tables' `ADDITIONAL` params.
- **v0.11.2 ✅ — Enum/spelling correction + README framing**
  — corrected `STORY_DRIFT_METHOD` enum values and direction-key spelling
  (v0.11.1 had transcribed an official-doc typo verbatim; the manual repo
  normalizes those deliberately — this is the incident behind CLAUDE.md's
  "don't transcribe a `[sic]` typo" rule). Also re-verified the `*-ANAL`
  hang on a current build and rewrote `docs/live_verification_notes.md`
  accordingly (same build, not a vendor fix — trigger still unidentified),
  and dropped the official/unofficial framing and trademark line from the
  README.
- **v0.12.0 ✅ — Client correctness** (out-of-band, from a review of
  `src/midas_nx/` rather than of the phase plan — the first release driven by
  auditing the SDK's own behaviour instead of the manual):
  - HTTP 200 carrying an `{"error": {...}}` body now raises `MidasResultError`
    instead of being returned as a successful result. This is the repo's own
    top documented live-server gotcha; it was described in three docstrings
    and handled in none. Opt out with `raise_on_result_error=False`.
  - A non-JSON response (proxy/SSL-inspection appliance answering in the
    product's place) raised a raw `JSONDecodeError` straight past
    `except MidasAPIError`; it now maps into the hierarchy, keeping the
    status-based class so a 401 login page still carries the MAPI-Key hint.
  - `DbResource.items()` raised `AttributeError` on the `{"message": ""}`
    zero-row shape recorded in `live_verification_notes.md`; it now returns
    `{}` and picks the table by value type rather than by position.
  - `post.base.unwrap_table()` — the `/post/TABLE` counterpart to
    `DbResource.items()`, finding the `HEAD`/`DATA` dict by shape. The
    unstable top-level key was documented as a hazard with no helper to
    handle it, and `get_table()`'s own docstring contradicted the finding.
  - `__version__` is now the single source (`dynamic = ["version"]`), with
    `tests/test_version.py` guarding it. It had reported `0.10.0` since
    v0.11.0 because the release step edited only `pyproject.toml`.
- **v0.14.0 ✅ — Write verification, and a table-destroying `delete()`**
  — first session with write permission on a real Civil NX. The new
  `scripts/live_crud_check.py` (create → read → update → delete per resource)
  found `DbResource.delete([id])` **emptying the entire table**, elements
  included, because the manual's documented ID-keyed DELETE body is ignored by
  the server. The undocumented per-id URL works; `delete()` now uses it and
  the old behaviour is named `delete_all()`. Also: `doc.analyze()` raises on
  `{"message": "... Analysis failed."}`, which carries no `error` key and so
  slipped past v0.12.0's check. Ten resources now pass a full round trip. Full
  findings — including `/doc/SAVEAS` returning success for a save that never
  happened, and `verify_connection()` being unable to see a blocked session —
  in `docs/live_verification_notes.md`.
- **v0.13.0 ✅ — Hyper-S is Civil-only + live verification at 295/390**
  — `scripts/live_readonly_sweep.py` (A1, see Phase 6) swept both products
  against real sessions on 2026-07-26 and found the SDK offering the 13
  Hyper-S (`-M1`) endpoints to Gen clients: they answer under Civil NX and
  404 under Gen NX, 21/21 including the 8 unimplemented stubs. Hyper-S is the
  solver MIDASIT shipped with Civil NX, so `PRODUCTS` was simply wrong.
  Corrected via a `HYPER_S_ONLY` constant — deliberately separate from
  `CIVIL_ONLY`, because Hyper-S is expected to reach Gen NX eventually and
  that day this should be one line, not 13. Guarded by
  `tests/db/test_hyper_s_products.py`. A Gen client now raises
  `ProductMismatchError` instead of issuing a request that can only 404.

### Phase 6 ✅ (mostly) — Trust & maintenance foundation  ·  v0.11.0-v0.11.2
Endpoint coverage (Phases 1-5) is done; before layering practitioner features
on top, harden the ground it stands on. **v0.11.0 shipped this phase's tooling
in one pass** (commits `afdcaaf`, `9e837ec`, `6b7fe8c`, `f55fac1`); what's
listed as ⏳ below is the remainder, re-scoped 2026-07-26 against the tree as
it actually is.

**Shipped:**
- **CI: test/lint pipeline ✅** — `.github/workflows/ci.yml` runs `pytest` +
  `ruff check src tests` on every push to `main` and every PR, across Python
  3.9 and 3.13. Prerequisite for the manual-drift job; both are live.
- **D1 ✅ — vendoring pipeline wired into CI.** `manual-drift-check.yml`
  (`cron: '0 3 * * 3'`, `issues: write`) checks out the sibling manual repo,
  runs `scripts/check_manual_drift.py` against `coverage.json`'s
  `vendored_at_commit`, and opens/updates an issue with the affected
  `midas_nx` modules. Deliberately pure-diff, no AI in the workflow.
- **D2 ✅ (moved up from Phase 8) — live schema drift checker.**
  `scripts/check_drift.py` diffs every `DbResource`'s TypedDict field names
  against what the live server reports via `/info/db/...` (`DbResource.info()`).
  Needs a running NX session, so it's a local dev tool, not a CI job — that
  split is the point, not a shortfall.
- **D3 ✅ (moved up from Phase 8) — endpoint scaffolding.**
  `scripts/gen_endpoint.py` generates the TypedDict + `DbResource` + test
  boilerplate from a manual chapter; it's now step 1 of the documented
  add-an-endpoint loop in `CLAUDE.md`. Human review stays mandatory.
- **A1, partial ✅ — live verification formalized.** `live_verified` is a real
  per-endpoint field in `coverage.json`, `ROADMAP.md` prints the verification
  rate and the Gen/Civil build table, and `scripts/live_smoke.py` makes the
  next session a rerun rather than a one-off. See ⏳ below for the gap.
- **C2 ✅ — friendlier error messages.** `MidasAuthError.HINT` (MAPI key
  location) and `MidasConnectionError.HINT` (NX process / API-server check)
  in `src/midas_nx/client.py`, ASCII-only per the cp949 console constraint.
- **C1, partial ✅ — multilingual getting-started guides.**
  `docs/{ko,en,zh-tw}/quickstart.md`, linked from the README.
- **B3 ✅ (moved up from Phase 7) — GET response unwrap.**
  `DbResource.items()` in `db/base.py`, available on every subclass.

**Remaining (⏳ — this is what v0.13.0 is for; v0.12.0 was cut for the
client-correctness fixes above instead):**
- **A1 ✅ done 2026-07-26 — both products swept and recorded.**
  `scripts/live_readonly_sweep.py` is committed (GET-only, safe against an open
  model) and its results are recorded per endpoint: `live_verified` went from
  **10/390 to 295/390**. Gen reproduced 2026-07-22 exactly (253 swept, 233 OK,
  the same 20 404s) on a real 710-node analyzed model rather than a blank one,
  which removes model state as an explanation; Civil reproduced exactly too
  (293/273/20). D4's version matrix now has both halves. The old "526
  endpoints" figure in this plan was wrong in both directions — 546 tested /
  506 OK across both products are the real numbers. **What's left on this axis
  is write coverage**, not read: POST/PUT/DELETE is still only exercised by
  `live_smoke.py`'s ~10-endpoint round trip.
- **C1 remainder — a screenshot-driven, zero-python-experience walkthrough.**
  The three quickstarts are still text-only (211/202/188 lines as of v2.1.2,
  up from 129/147/89 — the read-only-first rewrite added content but not
  images; 0 images). The missing piece is the NX-side half: where the MAPI
  key lives, what "API connected" looks like in the GUI, what a failed
  connection looks like. One complete path with pictures beats a
  feature-complete doc site.
- **D4, pulled forward from Phase 8 — per-endpoint version matrix.**
  `coverage.json` already carries `nx_versions` *inside* each `live_verified`
  block and `ROADMAP.md` prints one global build table. Promoting that to a
  real compatibility matrix is now a small step, and it's a natural companion
  to the A1 widening above — do them in the same pass.

> **D6 is dead, not deferred.** It existed to back the README's "covers roughly
> a third of the documented API surface" comparison against MIDASIT's own
> packages. That prose was removed in `4f050f7`/`a1b7026`, and `CLAUDE.md` now
> forbids reintroducing official/unofficial positioning or the comparison.
> There is no claim left to substantiate — don't rebuild the table.

### Phase 7 — Practitioner efficiency
- **B2 — Excel round-trip**, `midas-nx[excel]` extra (keep pandas/openpyxl out
  of the core dependency — `requests`-only import stays a hard invariant).
  `from_excel`/`to_excel` for node/element/load tables and result reports;
  `to_dataframe()` folds in as the pandas primitive underneath.
- **C3 — scenario examples** (2 to start): analyze → extract results → Excel
  summary report; construction-stage bulk model edit. Each example doubles as
  live-verification evidence (Phase 6 A1) and onboarding material (C1).
  `examples/python/` currently holds three single-purpose scripts
  (`quickstart.py`, `kds_wind_load.py`, `simple_beam_load_combination.py`);
  what C3 wants is end-to-end *workflows*, a different thing.

> B3 shipped early, in v0.11.0 — see Phase 6.

### Phase 8 — High-level workflow layer
Deliberately last: picking the wrong recipe scenarios is the most expensive
mistake in this axis, so it waits on user feedback from Phases 6-7's examples
and README traffic, not just code readiness.
- **B1 — `midas_nx.recipes` (or `.easy`)**: workflow-level functions
  (`create_frame(...)`, `apply_load_combos_kds(...)`, `extract_member_forces(...)`)
  returning practitioner-ready dict/DataFrame shapes, ID/endpoint-key unwrapping
  built in. Low-level layer (current `db.*`/`design.*`) stays untouched
  underneath — this is additive, not a replacement.
- **B4 — opt-in runtime validation**, two-staged: `typing_extensions.Required[]`
  first, opt-in full validation second. Default `strict=True` in the new
  recipes layer; low-level layer keeps today's no-validation behavior.

> **Recipe/engineering-task layer inputs (reviewed 2026-08-04):**
> `docs/planning/onboarding_plan_active.md` §11 (a per-recipe doc standard —
> risk level, product, verification status, full runnable code) and
> `docs/planning/documentation_maintenance_architecture_plan.md` §6-7 (removed
> 2026-09-17; in git history at `fa1332b`) (an
> engineering-task index generated as navigation over `coverage.json`, not
> copied API text) both propose shapes for this layer for whenever B1 starts.
> The architecture plan's larger ask — a `coverage.json` schema v2 with
> `observations[]` and a 12-state discrepancy FSM tracking MIDASIT dev-team
> ticket review — was judged disproportionate to solo-maintainer scale and
> deferred as an idea, not adopted; only its two verified bugs (a dead
> Troubleshooting link in the ko quickstart, unsanitized production-model
> detail/local paths in public `coverage.json` free text) were fixed, both
> in v2.1.2. **B1 itself (a new `midas_nx.recipes` code module) is still
> deliberately not started** — it's new public API surface with no usage
> feedback yet (v2.1.2 shipped days before this note). What *did* start
> 2026-08-04: a small pilot of the doc-only recipe format from §11 above —
> `docs/recipes/{index,inspect-project,read-nodes-and-elements,get-results}.md`,
> three read-only (risk level 1) recipes built entirely on the existing
> `db.*`/`post.*` API, no new SDK code. This is architecturally a different,
> much lower-commitment thing than B1: it's navigation and worked examples
> over what already ships, not a new versioned API surface, so it doesn't
> need to wait on the same feedback gate. `mkdocs build --strict` passing
> with the new `Recipes` nav section; import statements in all three spot-
> checked against the installed package.

> D2 (schema drift checker), D3 (endpoint scaffolding) and D4 (version matrix)
> all moved out of this phase: D2/D3 shipped in v0.11.0, and D4 is now folded
> into Phase 6's A1 remainder since `coverage.json` already records
> `nx_versions` per live-verified endpoint. See Phase 6.

### v1.0.0 — public API freeze
Gate: (a) the 8 undocumented Hyper-S `-M1` stubs resolved; (b) live
verification covering the core paths; (c) the manual-diff pipeline having
caught and survived a real upstream change. Matches D5 from the 2026-07-21
roadmap review: 1.0 means "frozen public surface + live-verified core paths +
a running change-detection pipeline," not just "endpoint count is high."

Status after 2026-07-29:

- **(a) is now resolved.** Went with option 1 (the author's explicit choice,
  "1번으로 해서 진행"): implemented all 8 stubs (`StructureTypeHyperS`,
  `MaterialHyperS`, `InelasticFiberMaterialLinkHyperS`, `PlasticMaterialHyperS`,
  `InelasticHingePropertyHyperS{Beam,Truss,GeneralLink,Pss}`) with payload
  TypedDicts derived from live `GET /info/db/...` introspection rather than a
  manual Specifications table, documented in-module as server-derived. 5 of 8
  have a directly-confirmed `/info` schema (`STYP-M1`, `MATL-M1`, `IMFM-M1`,
  `EPMT-M1`, `IEHG-BEAM-M1`); the other 3 (`IEHG-TRUSS-M1`, `IEHG-GL-M1`,
  `IEHG-PSS-M1`) have no `/info` route at all (404, even though GET works),
  so their single-field shape is assumed by sibling analogy to `IEHG-BEAM-M1`
  and flagged as such, not independently confirmed. Two Hyper-S variants
  (`MATL-M1`, `IMFM-M1`) turned out to have a genuinely different wire shape
  from their non-Hyper-S sibling (0-indexed `P_TYPE` vs 1-indexed; nested
  `CONCRETE`/`STEEL` sub-objects with different field names vs flat fields) —
  not just a product gate on an identical schema. Coverage is now 398/398
  (100%); `docs/coverage.json`/`ROADMAP.md`/`tests/db/test_hyper_s_products.py`
  (13→21) updated; 680 tests passing. This is a genuine `src/` addition
  (new classes, new client behavior), so it adds to the pending version-bump
  case, see the project memory.
- **(b) is now met, not half-met.** `scripts/live_crud_check.py` covers 43
  resources across 6 tiers with a full create→read→update→read→delete→read
  round trip: **43/43 confirmed on Civil NX**, **38/43 confirmed on Gen**
  (the other 5 are genuinely Civil-only — `/db/CMCS` and the 4-case moving
  chain — not untested). `/db/NMAS`, the one case that used to gate this
  permanently (crashed both products), was root-caused and fixed 2026-07-29.
  Read paths: 303/398 recorded across both products (the +8 being today's
  Hyper-S stubs), unchanged elsewhere and re-confirmed live the same day with
  zero regressions.
- **(c) is met, and reinforced again today** — not by the automated
  `manual-drift-check.yml` pipeline this time, but by the same live-check
  discipline catching a real, severe manual/server mismatch by hand
  (`/db/REBW`'s entire field-name schema, see `docs/live_verification_notes.md`
  and vendor report B-4). Worth flagging as a new consideration for 1.0,
  not yet in this gate's original three criteria: REBW was only caught
  because someone happened to read real populated data back against a real
  model. There is no way to know how many other endpoints carry the same
  kind of undiscovered manual/server mismatch without doing that same
  check broadly — a case for a wider live drift audit before declaring the
  public surface frozen, not just an endpoint-count or route-existence
  check. Not resolved; a call for the author.

**All three original gate criteria are now met.** The only open item is the
newly-surfaced (c)-adjacent question above (wider live drift audit before
freezing) — a call for the author, not a blocker by the gate's original text.

**v1.0.0 shipped 2026-07-29** on this basis (GitHub Release + `publish.yml` +
PyPI all confirmed live that day). The wider-live-drift-audit question above
was left open by choice, not resolved — and it caught something the same
day: **v1.1.0 (2026-08-02) broke the freeze**, removing `sect_position` from
`get_table()`/`get_wall_force_table()` (and `parts` from the latter) after
MIDASIT confirmed (Jira MAPI-2012) Wall Force never actually supported
either field — this SDK's fields were an inferred guess, not confirmed
against the product. "Frozen" here has always meant "no *known* reason left
to break it," not "provably will never break" — the open audit question is
exactly why that's the honest framing rather than a stronger guarantee.

### Cross-cutting / backlog (any time)

- ~~Resolve the undocumented Hyper-S stubs~~ — done 2026-07-29, see the
  v1.0.0 gate above.
- Extend write verification further. `scripts/live_crud_check.py` now covers
  43 resources across 6 tiers on both products (43/43 Civil, 38/43 Gen — see
  the v1.0.0 gate above), but the design-chapter (`ch24-27`) and `post/`
  write families still aren't covered by it at all. `/db/REBW`'s 2026-07-29
  discovery (whole field-name schema wrong, only found by reading real
  populated data back) is a concrete argument for extending this checker —
  or some equivalent live-data spot-check — into those chapters before 1.0.
- **Doc-site backlog triage (2026-08-04)**, cross-checking
  `docs/planning/documentation_maintenance_architecture_plan.md` (removed
  2026-09-17; in git history at `fa1332b`) §6.1's
  three-tier nav proposal against what's actually on the MkDocs site:
  - **Done this pass**: tier 3 (developer Reference) had two whole chapter
    families — `post/*` (ch18-23 result extraction) and `design/*` (ch24-27
    RC/steel/SRC code checks) — with no Reference page at all, unlike every
    other module. Not an architecture gap, just missed when `reference/`
    was built; added `docs/reference/post.md` and `docs/reference/design.md`
    (curated examples + a ROADMAP.md pointer, matching `reference/db.md`'s
    existing style — not an exhaustive per-endpoint dump), wired into
    `mkdocs.yml` nav, `mkdocs build --strict` passing.
  - **Also done this pass**: `docs/ko/ai-coding/safe-start.md` — a Korean
    translation of the AI-assisted-coding safe-start page (architecture
    plan §0.3 P1's "한국어 AI 안전 시작 페이지"), wired into `mkdocs.yml`
    nav next to the English original (same "language sub-list" pattern as
    Getting started), and `docs/ko/quickstart.md`'s existing cross-link
    repointed at it. `context-pack.md` deliberately stays English-only,
    single-source, per that same plan's own reasoning (AI-facing content
    that must track the SDK exactly — one canonical version, not N to keep
    in sync). `mkdocs build --strict` passing after both additions.
  - **Tier 2, corrected 2026-08-06** (two days after the 2026-08-04 triage
    below, not the same day): the author's actual ask on re-discussion
    wasn't "write 10 categories of new recipe content" (that's still
    declined, see below) but "reorganize what already exists under the
    10-category taxonomy so engineers can find it" — a navigation-only
    change, exactly what architecture-plan §6.2 describes ("기능별 페이지는
    색인으로 제한"). Done: `docs/recipes/index.md`'s flat 3-row table
    replaced with a 10-row task table (model setup → geometry → properties
    → boundary → loads → analysis → results order); rows without a recipe
    yet say so plainly ("*none yet*") and link straight to the relevant
    `midas_nx` module / Reference page / ROADMAP.md chapter instead of
    leaving a dead end. No new tutorial content was written — this doesn't
    touch the feedback gate below at all.
  - **Writing new recipe content for the 7 empty categories is still
    declined**: the 3-recipe pilot has no usage feedback yet, and doing
    that now would reverse the "wait for feedback" call with no new
    evidence to justify it.
  - **Tier 3 completed 2026-08-06**: split `reference/doc-ope-view.md` (one
    page covering three unrelated module families) into
    `reference/document.md`, `reference/operations.md`,
    `reference/view.md` — matching §6.1's "Operation Functions"/"View
    Functions" as separate Reference entries. Unlike the tier-2 item
    above, this was low-risk to do immediately: purely organizational, no
    new public API surface, nothing gated on user feedback. No inbound
    links to the old page existed outside `mkdocs.yml` itself.
    `mkdocs build --strict` passing with the 3-way split.
- **Quickstart Step 3 corrected from a real session (2026-08-04).** The
  three quickstarts' "get a MAPI key" step had been describing a menu path
  ("find the Open API menu... choose Issue API Key") never confirmed
  against an actual running Gen NX/Civil NX session. The author walked
  through the real screen: top menu **Apps → API Settings**, which shows
  both **Base URL** and **MAPI-Key** with **Copy** buttons, a **Refresh**
  button to reissue the key, and a **Connected** button whose success
  flips Status to **Connected**. Rewrote Step 3 in all three languages to
  match, and simplified the 🌏 China-server note in the process: since the
  product's own API Settings screen shows the correct Base URL directly,
  there's no need to guess a region from a URL pattern — copy what's
  shown. This is the same category of gap as the Phase 6 C1 remainder
  below (text-only quickstarts describing NX-side UI without having seen
  it) but narrower in scope — one step, not a full screenshot pass.
- **Confirmed 2026-08-07 (was a watch item as of yesterday):
  `/DESIGN/SRC/AIK-SRC2K/OCHECK` moved to `/TEMP/DESIGN/SRC/AIK-SRC2K/OCHECK`,
  and the move is not a fix.** Per MIDASIT's reply on `MAPI-2429` (the
  `OCHECK` crash, closed as "결함 아님"): this optimal-design endpoint is
  an unofficial API paused mid-development with no resume date, and
  MIDASIT moved it under a `/TEMP/` prefix specifically to mark it as
  unofficial. Live-tested same day: the old path now cleanly 404s (no
  longer routed at all), and the new `/TEMP/` path reproduces the exact
  same crash on Gen NX against a session with real non-SRC sections.
  `design/src_aiksrc2k.py`'s `perform_src_optimal_design()` now points at
  the new path and its docstring documents the crash under the new path
  too — this was the only one of the endpoints named in MIDASIT's comment
  actually implemented in this SDK (`DCHECK` and steel's own `OCHECK`
  were never wrapped here, nothing to update for those).

---

## 4. Release milestones

| Version | Milestone | Gate |
|---|---|---|
| v0.1.0 ✅ | Core DB modeling (ch 01–06) | published |
| v0.2.0 ✅ | Full analyzable model (Phase 1) | published |
| v0.3.0 ✅ | Analysis control + result extraction (Phase 2) | published |
| v0.4.0 ✅ | Operations & view (Phase 3) | published |
| v0.5.0 ✅ | Civil bridge features (Phase 4) | published |
| v0.6.0 ✅ | Design setup + Steel code (Phase 5a) | published |
| v0.7.0 ✅ | RC design code (Phase 5b) | published |
| v0.8.0 ✅ | SRC design code (Phase 5c) | published |
| v0.9.0 ✅ | Live Gen/Civil NX verification + PyPI discoverability (py.typed, classifiers, README) | published |
| v0.9.1 ✅ | Live-manual schema sync (`/ope/GSBG` → 2026-07-14 schema) | published |
| v0.10.0 ✅ | Connection/introspection helpers (`verify_connection()`, `DbResource.info()`) + beam example + troubleshooting docs | published |
| v0.11.0 ✅ | Phase 6 tooling — CI (`ci.yml`), weekly manual-drift job (D1), drift/scaffolding/smoke scripts (D2/D3/A1), `DbResource.items()` (B3), error hints (C2), ko/en/zh-tw guides (C1 pt. 1) | published |
| v0.11.1 ✅ | Manual-sync fix — `DCRM-WALL` breaking schema change, Wall Force table, story-table `ADDITIONAL` params | published |
| v0.11.2 ✅ | `STORY_DRIFT_METHOD` enum + direction-key spelling correction; `*-ANAL` re-verification writeup; README framing cleanup | published |
| v0.12.0 ✅ | Client correctness — `MidasResultError` for 200-with-`error` bodies, non-JSON responses kept inside the exception hierarchy, `items()` empty-shape fix, `post.base.unwrap_table()`, `__version__` single-sourced | published |
| v0.13.0 ✅ | Hyper-S corrected to Civil-only (`HYPER_S_ONLY`), A1 live sweep complete across both products (295/390), D4 matrix has both halves | published |
| v0.14.0 ✅ | `delete()` no longer empties the table (per-id URL) + `delete_all()`, `analyze()` raises on a failed solve, `scripts/live_crud_check.py` | published |
| ~~v0.15.0~~ | Never shipped as its own release — the planned bundle (53 PRODUCTS corrections, `/db/REBW` schema rewrite, `STORY_IRR_PARAM` enum fix, 8 Hyper-S `-M1` stubs) landed directly in v1.0.0 instead (`5b7fc3c`, `05977a5`), same day the freeze gate closed | superseded by v1.0.0 |
| v1.0.0 ✅ | Public API freeze: all three gate criteria met 2026-07-29 (Hyper-S stub decision resolved, core paths live-verified, manual-diff pipeline survived a real change) — only the wider-live-drift-audit question (surfaced by the REBW find) left open by choice | published — GitHub Release + `publish.yml` + PyPI confirmed live 2026-07-29 |
| v1.1.0 ✅ | First post-freeze breaking change: `get_table()`/`get_wall_force_table()` drop `sect_position`/`parts` per MIDASIT's confirmation (Jira MAPI-2012) Wall Force never supported them; plus the open drift-audit question above catching a real drift on the first sync since the freeze (`STORY_DRIFT_METHOD` "on" vs "at", `VEH_KSCE_LSD15`/`MVLD_CODE=13`) | published 2026-08-02 |
| v2.0.0 ✅ | External-review response. **Breaking:** `delete_all()` requires `confirm=True`. Adds per-request `timeout=`, mypy (clean, 41 modules) + the full 3.9–3.13 CI matrix + a built-wheel smoke test, a read/write split in the live-verification numbers (63 write / 329 read), a MkDocs site with a generated API reference, `SECURITY.md`/`CONTRIBUTING.md` with an explicit SemVer + deprecation policy, absolute README links that survive PyPI, and the employee-led project-status statement | published 2026-08-02 |
| v2.0.1 ✅ | Packaged-metadata-only: README trimmed to a lightweight multilingual (en/ko/zh-tw/zh-cn) landing page, developer-level content consolidated onto the MkDocs site instead of duplicated | published 2026-08-02 |
| v2.1.0 ✅ | Drops Python 3.9/3.10/3.11 support (`requires-python = ">=3.12"`); 3.9 was already 9 months past its own EOL, and three Dependabot floor bumps (requests/mypy/pytest) were stuck behind it | published 2026-08-02 |
| v2.1.1 ✅ | Re-applies the requests/mypy/pytest floor bumps closed for blocking on Python 3.9, now that v2.1.0 dropped it | published 2026-08-02 |
| v2.1.2 ✅ | Packaged-metadata-only: beginner onboarding rewrite — read-only first example everywhere, new `docs/ai-coding/` AI-assistant safety pack, two-path doc-site entry, risk-level (0-4) badges in `docs/safety.md` | published 2026-08-04 |
| v2.1.3 ✅ | Fixes `MidasClient._send()` raising `AttributeError` instead of a `MidasAPIError` subclass when a non-2xx error body's `error` field is a non-dict; two stale-docstring corrections found in the same review pass | published 2026-08-04 |
| v2.2.0 ✅ | Manual-driven sync (398→399 endpoints): Story Load Summary Table's `TABLE_TYPE` renamed (**breaking**), Story Load/Weight Tables gain unit/styles/components/load_case_names, Wall Design Forces gains `story_names`, new `DESIGN/RC/DRC` endpoint (`RcDesignCodeSelection`) | published 2026-08-07 |
| v2.2.1 ✅ | `perform_src_optimal_design()` (`OCHECK`) follows MIDASIT's `/TEMP/DESIGN/SRC/AIK-SRC2K/OCHECK` path move (MAPI-2429, unofficial/paused API) — old path now 404s; new path still crashes the session live-confirmed, docstring warns upfront | published 2026-08-07 |
| v2.3.0 ✅ | Manual-driven sync (`76ebda9`): new endpoint `get_concurrent_joint_force_table()` (`CONCURRENT_JOINT_FORCE`), `SWIND`/`SSEIS` gain a `"USER TYPE"` schema variant (additive, non-breaking); `/ope/GSBG`'s new second listing in ch17 confirmed to be the same already-implemented endpoint, no code change needed | published 2026-08-10 |
| v2.3.1 ✅ | `/code-review` fix: `get_concurrent_joint_force_table()` (v2.3.0) was missing `node_elems`/`components`/`opt_cs`/`stage_step` and its docstring wrongly denied the manual documents them for this table — added and corrected; `ROADMAP.md` regenerated to match a v2.3.0 date fix | published 2026-08-10 |
| v2.3.2 ✅ | `BRACEDESIGNFORCES` confirmed crashing Gen NX (docstring update), a full Gen NX `DbResource` GET sweep (32 new confirmations), and a manual 38-endpoint non-crash-family design-chapter batch (view/RC/steel/SRC ANAL-TABLE-REPORT, incl. `WD-ANAL`) — all clean. `Verified on Gen NX`: 266/399 → 337/399 | published 2026-08-10 |
| v2.3.5 ✅ | Full close-out of the sibling manual repo's 24-chapter re-verification drift (`vendored_at_commit` current, `has_diff: false`); root-caused 3 long-standing "Wrong Field" write stalls (`GRDP`/`SDHY`/`SDIS`) to missing fields, not server bugs; caught 6 cases of the manual repo's own re-verification being newly wrong, 2 traced further to stale MIDASIT official docs. Write coverage 158→162/399 | published 2026-08-27 |
| npm v2.3.2 ✅ | Initial typed JavaScript/TypeScript SDK generated from the reviewed Python endpoint inventory, with shared Civil NX/Gen NX coverage | published to npm 2026-08-26 |
| npm v2.3.3 ✅ | Safety and result-table typing hardening; declaration checks and packed npm artifact smoke tests added to CI | published to npm 2026-08-26 |
| npm v2.3.4 ✅ | Package-local changelog, npm release checklist, and the independent `js-v*` trusted-publishing route | published to npm 2026-08-27 |
| npm v2.4.0 ✅ | Fixes `db.staticLoads.nodalMass` sending payloads that could end a live NX session; adds `DbResourceMetadata.payloadDefaults`, generated from the new `contracts/` source of truth | published to npm 2026-08-27 |
| **2.6.0** ✅ | First release under one shared version number. Python: no `src/midas_nx/` change at all — an identical wheel under the aligned number. npm: `pythonModule`/`pythonFunction` removed from the shipped metadata, payload types for 38 endpoints generated from `contracts/` instead of from Python `TypedDict`s, and `tableTypes` added. Repo: `/post/TABLE` modelled as endpoint + table, 39 endpoint contracts and 3 table contracts promoted | published 2026-08-28 as `py-v2.6.0` and `js-v2.6.0` |
| **2.6.1** ✅ | npm operation wrappers now enforce the reviewed Gen NX/Civil NX product availability before sending a request; validated against a real Civil NX session with full DB GET coverage and a model -> analysis -> result-table round trip. Python republished unchanged to preserve the shared version | published 2026-08-28 as `py-v2.6.1` and `js-v2.6.1` |
| **2.7.0** ✅ | npm: `/db/BODF` generated from a reviewed contract, so `selfWeight` requires `LCNAME` and types `FV` as exactly three numbers; contracted fixed-length arrays now generate tuples rather than unbounded arrays. Python republished unchanged | published 2026-08-28 as `py-v2.7.0` and `js-v2.7.0` |
| **2.7.1** ✅ | Catches both packages up to three same-day manual revisions. Python: 27 resource labels corrected to the manual's English, `/db/POLC-M1` regains POST after a live call disproved the chapter, `/ope/GSBG` **now raises** on contradictory `BATCH` payloads, and 11 chapter-02 docstring references follow the manual's renumbering. npm: 400 lines of new result-table wrappers, contract-generated payload types, and four payload interfaces re-declared as type aliases. Repo: `--check` gained label, method and section-heading comparisons, each of which found real drift; 31 `safeToOmit: true` claims retracted after the evidence behind them turned out to be a request that never ran | published 2026-08-30 as `py-v2.7.1` and `js-v2.7.1` |
| **2.9.3** ✅ | **Nothing executable changed on either side** - `src/midas_nx/` and `packages/typescript/src/` are identical to 2.9.2, so both registries get a byte-identical build under a new number. What it publishes is metadata and the page people read first: the author credit (`Dennis`) and a LinkedIn contact on PyPI and npm, and the npm README restructured around reaching a first read-only script - it had never said what a MAPI key is or where to get one, never linked the documentation site or the safety guide, and opened its API section with `create()`/`delete()` and no warning. Its status paragraph is now in Korean, Traditional Chinese and Simplified Chinese too. Also in it, shipped in neither package: `examples/javascript/` carrying the read-only and model-building examples payload for payload against their Python namesakes (the other two Python examples have no JS twin yet), a TypeScript half for the AI context pack (`docs/ai-coding/` had described Python only), and three retracted findings removed from the published `docs/verification.md` - `/db/TDMT` and `/db/SECF` retracted 2026-07-27, `/db/MVHL` 2026-09-03 | published 2026-09-23 as `js-v2.9.3` then `py-v2.9.3` |
| **2.9.2** ✅ | **npm types come from the contracts alone; nothing changes at runtime, and Python is unchanged.** Every supplementary manual table a contract declared unmerged is merged - `/db/ELEM` and `/db/MVHL` become unions (MVHL's country object measured live to follow `MVLD_CODE`, not the headings' `STANDARD_CODE`), and `/db/MVLD`, `/db/MVLDpl`, `/db/SPFC`, `/db/THIS` and `/view/RESULTGRAPHIC` among others are generated - and the arguments held on Python are built from their contracts, `/ope/DIVIDEELEM`'s after a live axis measurement. 14 exports nothing referenced are withdrawn (765 → 751). Against `js-v2.9.1`: 202 members required across 74 types, 105 added across 11, 11 removed across 3 (`/db/FIBR`'s misplaced `R`/`G`/`B` among them) - breaking at the type level under a patch number the author chose | published 2026-09-22 as `js-v2.9.2` then `py-v2.9.2` |
| **2.9.1** ✅ | **npm types follow the contracts all the way down; nothing changes at runtime, and Python is unchanged.** Nested payload types (228) and operation-argument types (44, plus 44 nested) are generated from the contracts instead of Python TypedDicts: 551 members become required across 216 types and 39 are added across 11, against `js-v2.9.0`, with no export or member removed — breaking at the type level under a patch number the author chose. 27 nested members the contract extractor had dropped are restored across eight payloads, and `/view/ACTIVE`, `/view/CAPTURE` and `/ope/LINEBMLD` keep their branch-only members optional. Also in it, none of it shipped: one live-evidence ledger, one save-path rule for every `/doc/NEW` harness, stated counts re-derived in CI, and A-7 settled per product | published 2026-09-22 as `js-v2.9.1` then `py-v2.9.1` |
| **2.9.0** ✅ | **Python 3.11 is supported again; no code changed.** `requires-python` `>=3.12` → `>=3.11`, classifiers and the CI matrix span 3.11-3.14, and 1,090 tests pass on 3.11.15 and 3.14.5. The floor was never a property of the code (vermin: real minimum 3.8); v2.1.0 dropped 3.11 alongside the 3.9 that was actually blocking dependency bumps. 3.10 stays out: EOL October 2026, and requests/pytest/mypy all floor there today. The three quickstarts stop sending beginners to hunt for a specific version | published 2026-09-20 as `js-v2.9.0` then `py-v2.9.0` |
| **2.8.4** ✅ | **Three members of one npm type relax; Python is unchanged.** `TendonPropertyPayload`'s `FT`, `FPK` and `TDMFNAME` become optional with their `RM` conditions in JSDoc, so `/db/TDNT`'s per-relaxation-model requiredness is stated instead of flattened — nothing that compiled against 2.8.3 breaks, and the only Python edit is a comment. Also in it, none of it shipped: live coverage 201 → 207 write (TDNT, POGD on Civil, POGD-M1, MVLDch, MVLDid, PTNS), the fixture reaches 220 cases with 183 confirmed and npm replaying every one, and the Codex handoff becomes `docs/live_verification_playbook.md` | published 2026-09-20 as `js-v2.8.4` then `py-v2.8.4` |
| **2.8.3** ✅ | **One npm type narrows; Python is unchanged.** `SteelDesignCodeSelectionPayload.DGNCODE` becomes the required literal `"KDS 41 30 : 2022"` now that `DESIGN/STEEL/DSTL` is contracted — breaking for that type, no runtime change — and Gen NX accepted that value live while Civil NX refused it. Also in it, none of it shipped: npm generation stops importing `midas_nx`; contracts name all 70 npm operations (381 → 384 endpoints); npm replays all 177 confirmed live cases, evidence 113 → 162, with `/db/DYFG`/`/db/DYNF` resolved as a selection artefact; live coverage 201 write / 199 read | published 2026-09-17 as `js-v2.8.3` then `py-v2.8.3` |
| **2.8.2** ✅ | Additive on both surfaces. **`DESIGN/STEEL/DSTL`** joins both SDKs as `SteelDesignCodeSelection` — the steel counterpart of `DESIGN/RC/DRC`, and not `/db/DSTL`, which shares the name; documented by the manual and not yet called live, so it has no contract. npm also gains `bSERVCHECK`/`dSHORTTERM`/`dLONGTERM` on `MaterialModifyConcretePayload` and `bPJ` on `TendonProfilePayload`'s CURVE shape, and both SDKs document `OPT_CS` as three states — omitting it keeps the current view, `false` switches to the final stage. Also in it, none of it shipped: the manual reflected through `a6947a7` with CI green again, 108 anchors moved across 59 contracts where the check had named 11; npm live evidence 70 → 113 and a global seed-name collision found by the npm replay; `upload-artifact` and `setup-node` to v7, with npm published before PyPI to prove the new OIDC path first | published 2026-09-16 as `js-v2.8.2` then `py-v2.8.2` |
| **2.8.1** ✅ | **A breaking narrowing in a patch number, and it makes the types honest.** `TimeHistoryLoadCaseHyperSPayload`, `NonlinearAnalysisControlHyperSPayload` and `AdditionalImpactFactorPayload` moved off the Python fallback onto their contracts, so 16 members that were optional are now required - the fallback emits every member optional because a TypedDict states no requiredness a generator can read, which means those three had been claiming *less* than the manual. No exported name moves: 741 payload types before and after. Three others widen the way 2.8.0 did - `MovingLoadAnalysisControlPayload`, `GeneralLinkHyperSPayload` and `TimeDependentMaterialFunctionPayload` stop requiring branch members their own selector excludes - and 53 members arrive from 21 merged manual tables. Python changes three trailing comments. Also in it, none of it shipped: nine endpoints earned write evidence through both SDKs (191 -> 200, npm evidence 60 -> 70); `/db/MVCT`'s two-month `Unknown Error` resolved to one prerequisite, the `AASHTO LRFD` code selection; the fixture-to-contract checker fell 41 leads -> 1; four official worked examples measured and refused, registered MD-53 through MD-56 with no invented replacement | published 2026-09-15 as `py-v2.8.1` and `js-v2.8.1` |
| **2.8.0** ✅ | Three moving-load control payload types stop requiring `UNUMT`/`DIST` (and `NUM_UNIT_LOAD`/`DISTANCE`) together. They are branches selected by `iIGP` / `INFL_GEN_POINT`, so a record carrying both is not a thing the endpoint accepts — the manual said so in each row's description text and nothing could read it. The three contracts now carry `appliesWhen` and the npm optionality follows; **nothing in `src/midas_nx/` changed at all**, so PyPI republishes an identical wheel under the aligned number. Also in it, none of it shipped: five endpoints moved read → write (`/db/MVCTbs`, `/db/MVCTtr` both products; `/db/MVCTid` Civil only; `/db/THGC-M1`, `/db/THOO-M1` Civil, PUT-only), write coverage 185 → 190 and npm evidence 55 → 60; two npm harness defects that no passing case could reveal (`Object.is` on nested objects, an unconditional POST); and **the fixture checker's own three wrong counts** — 64, 81, then 41/2 — of which the 81 had already reached a release note and a task list for another agent. | published 2026-09-06 as `py-v2.8.0` and `js-v2.8.0` |
| **2.7.9** ✅ | Additive on npm, documentation-only on PyPI. **Thirty-five `MAPI-xxxx` references left the packaged surfaces**: they sat in docstrings across eight `src/midas_nx` modules, so every PyPI install carried MIDAS IT's internal ticket ids, and seven reached the npm package through generated wrappers. The rule against naming that tracker had been enforced for release notes; the packages are more public than a release note and had been missed. Every finding stays word for word. npm additionally gains members the server declares: `SPECIAL_LANE_ITEMS` on four lane payload types plus `OPT_STRADD`, and nine fields on `MovingLoadAnalysisControlChinaPayload` — seven from a `FREQ` table with **two Key/설명 column pairs side by side** that the parser reads only half of, and two `BTYPE` selectors stated in the **bold sentence introducing** their table rather than in a row of it (MD-50). Also in it, none of it shipped: chapter 08's lane and moving-load family live-verified on both products (write 173 → 185, npm evidence 47 → 55); a second seed collision found and fixed; fixtures checked against contracts for the first time; the 602 waived names measured against `/info`. | published 2026-09-06 as `py-v2.7.9` and `js-v2.7.9` |
| **2.7.8** ✅ | A one-value fix in both packages, and the value is one the server was refusing. `/post/TABLE`'s surface-spring reaction type is `REACTIONLSURFACESPRING`; the Specifications table and the JSON Schema enum both drop the L and only the request example has it, so the contract took the majority and **both products refuse it**. Every caller of that table type got an error instead of a table, in both languages, for as long as the constant has existed. The same live run confirmed `BEAMFORCESTP`, where the identical 2-1 reading was right — which is the finding worth keeping: **a wire value is not a majority opinion**, and three documents agreeing is three transcriptions of one source. A `describes: table_type` defect can now be marked resolved only on a live check; result-table contradictions 2 → 0. Also in it, none of it shipped: every non-`/TEMP` crash path re-checked on build 09/02/2026 with a real `GET /db/NODE` as the liveness proof and **nothing cleared**; `/db/STRPSSM` read → write once `PY`/`PZ` turned out to be `/info`'s descriptions rather than its keys (172 → 173 write); the `/info`-to-contract sweep wired into CI as a per-endpoint ceiling; npm live evidence 23 → 32 endpoints. | published 2026-09-05 as `py-v2.7.8` and `js-v2.7.8` |
| **2.7.7** ✅ | Gives the contracts a check that compares **field names**, which the four parity checks that came before never did: `check_field_parity` resolves a contract's `surface.payloadTypeName` to the Python TypedDict of that name in the endpoint's own module and fails on any wire name an SDK ships that no contract records. Its first run found 73 keys across twelve endpoints; **exactly one was an SDK defect** (`/db/HHCT-M1`'s `ITEM.M_GENERAL`), the rest contracts behind their own SDK, three of them publishing a flat record the server has never accepted — and `/db/LLAN`'s wrong shape had also manufactured ten false `safeToOmit: true` claims. Itemising the `unmergedTables` waiver by `fieldNames` closed another 214 unchecked names and exposed a parser defect of its own (MD-48: a Key cell can name several properties at once). `schema/info-baseline.json` — every `GET /info{endpoint}` both products answer — is committed and swept against every contract in both directions. **The largest breaking npm release so far, despite the patch number**: sixty payload types lose the `Assign` envelope the client builds for you, `BraceMainBarSpec` is renamed `BraceMainBarItem`, and eighteen records change shape, every one of them a shape the server refuses. Python ships two corrected labels and nothing else behavioural. Contracts 358 → 381 of 399, `surface` blocks 289 → 301, manual defects MD-17 → MD-48. | published 2026-09-04 as `py-v2.7.7` and `js-v2.7.7` |
| **2.7.6** ✅ | Empties `promote_contract.py`'s hand-review gate: the six endpoints held out of the source of truth because transcribing their manual sections would have put something false into it are all contracted. Three take their fields from the server (`/db/REBW`, `/db/REBC`, `/db/REBB`), and for the first two MIDASIT's own articles carry the same wrong shapes, so the vendored chapters transcribe their source faithfully. **Breaking in both surfaces, despite the patch number**, which is kept aligned rather than semver-derived: `create()`/`update()` now refuse a `/db/MVHL` empty `VEH_DEFAULT` and a `/db/PRES` item with no `DIRECTION` — the second because omitting the field is *how* its documented default gets applied, and that default is the one value a plate face refuses. Four shipped npm type defects found while contracting: a variant's branch attached to the payload root instead of the object holding its gate (`/db/SWIND`'s `WIND_SPEED` was a top-level member, not a `PARAMETERS` one); a multi-value branch table dropped when it overlapped no other; 53 rows dropped from `└`-nested tables, two of them required; and a changelog entry claiming two payload types were contract-generated when they were not. Contracts 342 → 358, `surface` blocks 273 → 289, drafts 42 → 26. | published 2026-09-03 as `py-v2.7.6` and `js-v2.7.6` |
| **2.7.5** ✅ | The first release since 2.6.0 where both packaged surfaces change. Python: `RebarDesignCriteria` and `RebarDesignCriteriaByWallMember` take their manual sections' labels, which their three `DCRM-*` siblings already had. **npm breaking**: `AXIS_VECTOR` is `Array<number>` — the Specifications table typed it `Number` while the section's own schema and Request Example send six, so its documented value was a type error — and six payloads become contract-driven with required members. The larger fix goes the other way: **49 fields the manual requires only inside one branch** were typed required of every payload, so `ConvectionCoefficientFunctionPayload` demanded `COEF` and `SCALE_FACTOR` together and no caller could satisfy it. Contracts 337 → 342, `surface` blocks 0 → 273, drafts 47 → 42; MD-11 records the nine Value Types a section contradicts. | prepared 2026-09-02 |
| **2.7.4** ✅ | npm only again; Python republished unchanged. **npm breaking**: `StaticSeismicLoadPayload`, `StaticWindLoadPayload` and `TendonProfilePayload` become discriminated unions with fifteen newly required members. The other direction matters more — three shipped defects made *documented* values untypeable: `/db/CO_S` offered two of nine colour components because the manual keys them `"W_R" ~ "HE_B"`, rebar sizes stopped at D8 against a description reading `19종 (D4 ~ D57)`, and a variant union outlawed every discriminator value no manual table covered. Contracts 319 → 337; `/db/FIMP` un-promoted for declaring a three-level object as ten flat fields. | published 2026-09-02 |
| **2.7.3** ✅ | D3 and D4, the last two contract-schema decisions. `variant.when` takes the `appliesWhen` shape — an ANDed array of `{path, equals|in}` — so a nested discriminator, a two-level selector and a table the manual gives several values for are all expressible; `request.itemSchema` gains `scalar` and `empty` for the nine `/doc/*` arguments that are a bare string or `{}` rather than a field list. Promoted 309 → 319. **npm breaking**: `FloorLoadPayload` is now a discriminated union with three required members. Python's packaged surface is unchanged. | published 2026-08-31 as `py-v2.7.3` and `js-v2.7.3` |
| **2.7.2** ✅ | Contract-migration progress and the 2026-08-31 live-verification batch: Python payload documentation gained verified moving-load, analysis-control and inelastic-hinge members; npm generated types gained reviewed manual shapes for 30 newly promoted endpoint contracts (279 to 309), taking contract-owned npm resource facts to 251 of 304. The live harness now makes safe, verified checkpoints before dependent cases and records scratch-model evidence separately from manual facts. | published 2026-08-31 |
| v0.16.0/Phase 7 (not started) | Excel round-trip extra (B2), 2 scenario examples (C3) | `pip install midas-nx[excel]` works, examples run against a live session |
| v0.17.0+/Phase 8 (not started) | `recipes`/`easy` high-level layer (B1) once scenarios are validated from Phase 7 feedback, opt-in validation (B4) | |

Python releases use `py-v*` GitHub Releases and `publish.yml` to reach PyPI. npm releases use `js-v*`
GitHub Releases and `publish-npm.yml` with npm Trusted Publishing (OIDC). Both workflows check the tag
prefix and package version directly because `release` events cannot use path filters. The registries
share the `midas-nx` name and move in lockstep on one version number.

> Numbering note (2026-07-21): the original Phase 1-5 numbering above was
> chapter/endpoint-coverage-driven and ended at v0.10.0. Phase 6-8 (this
> section) reflect a 2026-07-21 roadmap review's four-axis reprioritization
> (reliability, practitioner efficiency, non-developer accessibility,
> maintenance architecture) — version numbers from v0.14.0 on are provisional
> until each release's actual scope is locked at cut time. v0.12.0 and v0.13.0
> are the mechanism working as intended: both were out-of-band releases driven
> by what live testing turned up, and the phase work shifted down rather than
> the releases being forced into the plan's shape. **Phase headings deliberately
> carry no version number** — only this table does, so a re-cut edits one place.
>
> Version-bump note (rewritten 2026-08-30): this used to say to bump each
> package only when its own surface changed. That has been wrong since
> 2026-08-28 — the two registries share **one** version number, so a release
> moves both and publishes both a `py-v*` and a `js-v*` Release even when one
> surface has no shipped change. What the diff still decides is the **notes**:
> re-derive from it which surface is the reason, and say so. `scripts/`,
> repository docs, `.github/` and this file ship in neither package and warrant
> no release on their own (`CLAUDE.md` § Releasing).
>
> Staleness note (2026-07-26): this plan spent v0.11.0-v0.11.2 describing
> already-shipped work as pending — most of Phase 6, plus D2/D3 sitting in
> Phase 8 while their scripts were already in the repo and in `CLAUDE.md`'s
> documented workflow. **Re-check §2's non-endpoint status table against the
> tree before planning a release**, and update the "Last updated" line in the
> same commit that changes anything below it.

---

## 5. Working rhythm (per endpoint)

Unchanged from the 02–06 build — the loop that produced the current velocity,
now with step 1 scaffolded (see `CLAUDE.md` § Adding an endpoint for the
canonical version):

1. Scaffold from the manual chapter with `scripts/gen_endpoint.py`, then
   correct it against the vendored manual by hand — the scaffolder gives a
   first draft, not a finished module.
2. Add `DbResource` subclass + `TypedDict` payload in the chapter module.
3. Add a `responses`-mocked test mirroring `tests/db/test_node_element.py`.
4. Mark `"implemented"` in `docs/coverage.json`, re-run `scripts/gen_roadmap.py`.
5. Run `pytest`, `ruff check src tests scripts`, and `mypy`.
6. From `packages/typescript/`, run `npm run generate`, review the generated
   surface and schemas, then run `npm run typecheck` and `npm test`. CI also
   builds and smoke-tests the packed artifact on Node.js 18 and 22.
