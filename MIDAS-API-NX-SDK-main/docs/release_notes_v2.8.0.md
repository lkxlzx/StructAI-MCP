# midas-nx 2.8.0

A shared PyPI/npm version release.

| surface | what actually changed |
| --- | --- |
| Python | **nothing** — `src/midas_nx/` has no commit since 2.7.9; an identical wheel goes out under a new number |
| npm | three payload types stop requiring two fields that cannot both be supplied |

Nothing is removed, no exported name moves, and no field changes type. The npm
change **widens** what type-checks; existing code that compiled still compiles.

## Fixed — two mutually exclusive fields were both marked required

`MovingLoadAnalysisControlIndiaPayload` and `MovingLoadAnalysisControlBSPayload`
make `UNUMT` and `DIST` optional; `MovingLoadAnalysisControlTransversePayload`
does the same for `NUM_UNIT_LOAD` and `DISTANCE`.

These are branches, not siblings. One is the Number/Line element, the other the
distance between points, and the influence-generation selector — `iIGP`, or
`INFL_GEN_POINT` — decides which applies. **A record carrying both is not a
thing the endpoint accepts.** Requiring both described a payload no caller could
construct, and it was not a typing nicety: it also blocked the live case for
these three endpoints from passing an offline gate that was itself wrong.

The manual states the branch in the description text of each row — "(when
iIGP=0)", "(when method 1)". It was documented all along, just not in a form
anything could read. The three contracts now carry it as `appliesWhen`, the
construct fifty other contracts already use, and the generated optionality
follows from that rather than from a hand edit.

## Nothing changed in the Python package

`src/midas_nx/` has no commit between `py-v2.7.9` and this release. Under
lockstep versioning that is still a real release for PyPI — it republishes an
identical wheel under the aligned number — and this section exists so nobody
goes looking for a behaviour change that is not there.

## Also in this release, none of it in either package

- **Five endpoints moved from read to write evidence**, run through both public
  SDKs on Gen NX 2026 v2.1 and Civil NX 2026 v2.2, both Build 09/02/2026.
  `/db/MVCTbs` and `/db/MVCTtr` completed a full round trip on both products, `/db/MVCTid` on Civil only — Gen does not offer the `INDIA`
  moving-load code — and `/db/THGC-M1` and `/db/THOO-M1` completed
  PUT/read/per-id DELETE/read on Civil. Write coverage **185 → 190**, live cases
  188 → 200, confirmed 158 → 165, npm live evidence 55 → 60.

  Four country-specific moving-load cases were added **unconfirmed**, carrying
  their verbatim errors, because that is what they earned. The China result is
  the informative one: its documented vehicle label is a reference to a model
  record, not a self-contained definition. `/db/MVLDbs` was not run at all — its
  contract marks mutually exclusive `LCDATA_*` objects required together, so the
  manual's own example fails the offline gate, and the gate was not waived to
  get around it.

- **The npm harness had two defects that no passing case could reveal.**
  `containsExpectedValue` compared with `Object.is` — reference identity for an
  object or array — so a fixture whose expected value was nested could never
  match and the assertion passed nothing. And `runCase` called POST
  unconditionally, so a resource declaring GET, PUT and DELETE and no POST could
  not be exercised from npm while Python ran it fine. Both were found by running
  the harness, not by reading it.

- **The fixture-to-contract checker reported three different counts in two days,
  and all three were the checker.** 64, then 81 split 54/27, now 41 fixture
  leads across 5 endpoints and 2 contract gaps on one. The 81 version read only
  a contract's base `fields`, so a name declared in a `variant` counted as
  recorded nowhere — `/db/EIGV`'s five, `/db/THIS`'s `DALL`, `/db/PNLD`'s
  `AREALOAD` and six more, every one of them declared in its own contract — and
  a `required` field carrying an `appliesWhen` counted as missing from every
  payload rather than from the branch that selects it.

  **The generalization is the part worth keeping.** A checker that compares two
  artefacts is itself a third claim about the shape, and it is unverified until
  something disagrees with it. This one was believed on its own output for a day
  — written into a release note and handed to another agent as a 21-item task
  list that described nothing real. A new checker's first findings are a
  hypothesis; confirm a sample by hand before reporting a count as a fact. The
  2.7.9 notes have been corrected in place rather than quietly restated.

## Validation

- Python: 1026 tests, ruff and mypy clean.
- npm: 75 tests, typecheck, generation and packed-artifact checks clean.
- Contracts: schema, SDK parity, field parity, the `/info`-to-contract sweep,
  the product-divergence guard and the fixture-to-contract check all pass.

One check is red on purpose. The sibling manual repository has an unreflected
2026-09-06 sync that the author is still verifying — it has already been
followed by one self-correcting commit — so `check_manual_drift.py` reports a
difference and one contract-to-manual test fails. Nothing in this release moves
toward it.
