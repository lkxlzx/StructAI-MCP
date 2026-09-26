# midas-nx 2.8.1

A shared PyPI/npm version release.

| surface | what actually changed |
| --- | --- |
| Python | **comments only** — three TypedDict field comments now name the branch that governs the requiredness they state. No function, class, annotation or constant changed |
| npm | three payload types moved onto their contracts and now carry real requiredness — **16 members became required**; three others stopped requiring fields that cannot all apply at once |

No exported name is added, removed or renamed: 741 exported payload types
before, 741 after.

## Breaking on npm — 16 members that were optional are now required

**This is a patch number carrying a type narrowing.** Existing code that
compiled may stop compiling. Nothing about the wire format changed and no
runtime behaviour moved; what changed is that three payload types stopped
being derived from a Python TypedDict and started being derived from their
contract, and a contract states which members the manual marks Required.

| payload type | now required |
| --- | --- |
| `TimeHistoryLoadCaseHyperSPayload` | `NAME`, `ANAL_CASE`, `ENDTIME`, `TIME_INC`, `OUTPUT_STEP`, `DAMPING`, `INIT_METHOD`, `KEEP_LOAD`, `CUM_DVA`, `SUBSEQ`, `USE_INIT_LOAD` |
| `NonlinearAnalysisControlHyperSPayload` | `NONLINEAR_TYPE`, `ITER_METHOD`, `CONV_CRITERIA`, `LOAD_STEPS` |
| `AdditionalImpactFactorPayload` | `ITEMS` |

The generator emits a Python-fallback type as entirely optional, because a
TypedDict says nothing about requiredness that a generator can read. So these
three types had been **claiming less than the manual says** — a caller could
build a `TimeHistoryLoadCaseHyperSPayload` with no `NAME` and type-check
clean, then get an error from the server. If your code was already sending
what the endpoint needs, it still compiles. If it did not, the compiler now
says so at the point where the fix is cheap.

`TimeHistoryLoadCaseHyperSPayload` is also emitted as a `type` alias rather
than an `interface` now, in common with the other 18 contract-generated
payload types. Declaration merging against it no longer works; nothing else
about using it changes.

## Fixed on npm — three more payloads stop requiring what cannot coexist

Same defect class as 2.8.0's, found in three more places, and documented in
the manual all along as prose inside a row rather than as anything machine
readable:

| payload type | now optional | because |
| --- | --- | --- |
| `MovingLoadAnalysisControlPayload` | `iIGPN`, `DIST`, `RGN`, `DGN`, `FGN`, `LGN` | `iIGP` selects one of the first two; each group name applies only when its own `bRG`/`bDG`/`bFG`/`bLG` is true |
| `GeneralLinkHyperSPayload` | `BETA_ANGLE`, `INPUT_METHOD`, `ANGLE_VALUES`, `POINT_VALUES`, `VECTOR_VALUES` | `REF_SYSTEM` picks the element or global system, then `INPUT_METHOD` picks Angle, 3 Points or Vector |
| `TimeDependentMaterialFunctionPayload` | `CTYPE`, `RELAXATION` | `FTYPE` selects Creep or Relaxation; the manual numbers both rows `6` and qualifies them "(Creep only)" / "(Relax only)" |

Each condition is now `appliesWhen` in the contract, and the generated JSDoc
says it — `Required when REF_SYSTEM = 1 and INPUT_METHOD = 0`. The conditions
were transcribed from the section's own table at the vendored manual commit,
including the case where the neighbouring `/db/NLNK` section states different
requiredness for the same field names. Reading the wrong one of those two
tables would have been invisible to every gate in the repository.

## Added on npm — members the merged manual tables declare

`PointSpringPayload`, `NonlinearAnalysisControlHyperSPayload`,
`TimeHistoryLoadCaseHyperSPayload` and `AdditionalImpactFactorPayload` gain 53
members between them, nearly all nested inside objects those types already
had. They come from 21 manual tables whose contents the contracts had recorded
as *missing* rather than as fields — a declared gap, honestly marked, and now
closed from the manual and `/info`.

## Nothing changed in the Python package

`src/midas_nx/` has one commit since 2.8.0 and it edits three trailing
comments: `UNUMT`, `DIST`, `NUM_UNIT_LOAD` and `DISTANCE` said `required`
without the branch that governs it, which is the same defect the npm types
carried. The annotations are untouched — a TypedDict here is documentation and
the contract is the source.

## Also in this release, none of it in either package

- **Nine endpoints moved from read to write evidence**, each completed through
  both SDKs on Gen NX 2026 v2.1 and Civil NX 2026 v2.2, both Build 09/02/2026:
  `/db/IEPI`, `/db/EXLD`, `/db/PRST`, `/db/POLC`, `/db/MATD`, `/db/IEHC`,
  `/db/POLC-M1` (Civil-only), `/db/MVCT` and `/db/EPMT` (Gen write; Civil
  refuses the identical POST). Write coverage **191 → 200**, confirmed cases
  165 → 177, npm live evidence 60 → 70 endpoints.

- **`/db/MVCT`'s two-month-old `Unknown Error` was explained.** An isolated
  probe established the prerequisite: selecting the manual's `AASHTO LRFD`
  moving-load code is enough. No lane, vehicle or moving-load case is needed —
  which is the opposite of what a reasonable reading of the chapter suggests.

- **The fixture-to-contract checker went from 41 leads to 1.** `/db/GRDP`'s 28
  were a fixture sending less than the manual's own Request Body; the other 12
  were three contracts stating a branch member's requiredness without its
  branch. What is left is `/db/ACTL`, which is settled product behaviour.

- **Four official worked examples were measured and do not work** (MD-53
  through MD-56): `/db/MATD`'s rebar grade pair is not resolvable and the yield
  strengths it prints beside them are required input, not a consequence;
  `/db/FIMP`'s Kent & Park example fails the product's own printed inequality —
  `0.8/100 + 0.002 = 0.010`, against a stated `ECU` of `0.003`; `/db/TDMF`'s
  Creep body answers `Wrong Field`; and `/db/EPMT`'s payload works on Gen and
  is refused on Civil while `/info` declares the same shape on both. **No
  replacement value was invented for any of them** — each case stays
  unconfirmed and each endpoint keeps the level it earned.

- **`safeToOmit` can no longer outrun its evidence.** 21 fields were promoted
  from recorded live omissions and 36 were deliberately left `unverified`, with
  the reason per field. `/db/NMAS`'s `rmX`/`rmY`/`rmZ` appear in that candidate
  list and omitting them crashes both products — they stay `false`. The
  derivation now requires the confirmed case to have satisfied every
  `appliesWhen` predicate and to have run on a product the field applies to.

- **21 unmerged extraction tables were merged**, 93 → 72 tables and 602 → 482
  waived field names, which is where most of this release's npm members came
  from.

## Validation

- Python: 1061 tests, ruff and mypy clean.
- npm: 77 tests, typecheck, generation and packed-artifact checks clean.
- Contracts: schema, SDK parity, field parity, the `/info`-to-contract sweep,
  the product-divergence guard and the fixture-to-contract check all pass.

One check is red on purpose, as it was for 2.8.0. The sibling manual
repository has an unreflected 2026-09-06 sync that the author is still
verifying, so `check_manual_drift.py` reports a difference and one
contract-to-manual test fails. Nothing in this release moves toward it; every
manual row cited above was read at the vendored commit `7920759`.
