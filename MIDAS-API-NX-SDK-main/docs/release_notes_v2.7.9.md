# midas-nx 2.7.9

A shared PyPI/npm version release. **Additive on npm, documentation-only on
PyPI.** Nothing is removed, no exported name moves, and no type changes shape.

| surface | what actually changed |
| --- | --- |
| Python | **docstrings only** — no function, class or constant changed |
| npm | five payload types gain members the server declares, plus the same docstring change |

## Removed — MIDAS IT's internal ticket ids are no longer shipped

Thirty-five `MAPI-xxxx` references sat in docstrings across eight modules of
`src/midas_nx`, so **every PyPI install carried the vendor's internal Jira
ids**, and seven of them reached the npm package too through the generated
operation and table wrappers.

This repository has always forbidden naming that tracker in release notes. The
packaged surfaces are more public than a release note, and had been missed.

**Every finding stays, word for word.** Only the id goes: "reported to MIDASIT
(`MAPI-xxxx`)" becomes "reported to MIDASIT", "root-caused MAPI-xxxx as"
becomes "root-caused it as", and every dated confirmation keeps its date. The
crash histories, the re-test records, and the "reduced but not cleared"
judgements are all still there.

## Added — npm payload members the server declares

None of these is new behaviour; each is a field the products accept that the
contracts did not record.

- `TrafficLineLanePayload`, `TrafficLineLanesChinaPayload`,
  `TrafficLineLanesIndiaPayload` and `TrafficLineLanesOptimizationPayload` gain
  **`SPECIAL_LANE_ITEMS`**, an array all four declare and the manual documents
  on none. Its members differ per endpoint (7, 6, 5 and 8). The server's own
  description — "Used only when importing" — is the whole of what is known
  about when it applies, so no rule is generated from it.
  `TrafficLineLanesOptimizationPayload` also gains the root `OPT_STRADD`.
- `MovingLoadAnalysisControlChinaPayload` gains **nine fields the manual
  documents and this repository could not read**: `FREQ`'s `SBEM_L`, `SBEM_E`,
  `SBEM_IC`, `SBEM_MC`, `iARCH_TYPE`, `CABL_A` and `CABL_L`, plus a `BTYPE` on
  each of `BRIDGE1` and `BRIDGE2` with the enum each accepts.

Two separate causes, and the diagnosis is the part worth keeping. `FREQ`'s
table has **two Key/설명 column pairs side by side** and the parser reads only
the first — the first column's packed cells extracted correctly, so this is
*not* the packed-Key-cell defect the repository already knows about. Each
`BTYPE` is stated in the **bold sentence introducing** its table rather than in
a row of it, enum included, and it is the selector deciding which of that
table's fields apply — so neither object was usable without it. Recorded as
MD-50.

## Also in this release, none of it in either package

- **Chapter 08's lane and moving-load family is live-verified on both
  products.** Thirteen `/db` endpoints gained a live case replaying the
  manual's own JSON examples: write coverage **173 → 185**, confirmed cases
  144 → 158, npm live evidence 47 → 55 endpoints. Which moving-load code a
  product offers decides most of that table — `POST /db/MVCD` answers
  "Unavailable moving load code" on Gen NX for `CHINA`, `INDIA` and `KOREA`,
  so the lanes those codes exist for cannot be written there at all. That is a
  product capability, not a payload defect, and the cases are split per product
  rather than carrying a payload that fails on one of them.

- **A second seed collision, found two days after the first.** Every lane tier
  seeds the same single-row `/db/MVCD` selector by POST, so the first tier in a
  selection won and every later one answered `Key Already Exist`, taking its
  whole tier with it — three endpoints looked like failures for that reason
  alone. The fix POSTs and falls back to PUT, **deliberately rather than
  reading the record and branching**: a seed that reads state back cannot be
  replayed from an emitted payload, so branching would have taken all thirteen
  cases away from the npm harness to fix a Python-only problem. The first
  attempt did exactly that, silently, and the emitter caught it.

- **Fixtures are now checked against contracts.** Contracts were compared
  against both SDKs, against `/info` and against the manual; nothing compared
  them against the fixtures, which decide what a live run actually sends.
  `scripts/check_fixture_contract.py` splits its findings by whether the case
  has ever passed live: where the payload is the suspect, and where the product
  accepted the payload so the contract is what is behind.

  **Correction, 2026-09-06.** This section first said 81 findings, 54 and 27.
  Those counts were the checker's own defect, not the repository's state: it
  read only a contract's base `fields`, so a name declared in a `variant` and a
  `required` field carrying an `appliesWhen` condition both counted as defects.
  38 of the 81 came off when it was fixed. The real numbers are **41 fixture
  leads across 5 endpoints and 2 contract gaps on one**.

- **The 602 waived field names were measured** against `/info`. 533 of the 534
  it can speak to are declared, so "does a second source exist" was the wrong
  question; "does it agree on shape" is the right one, and 53 of the 93 tables
  have a single `/info` object holding all of their names.

## Validation

- Python: 1024 tests, ruff and mypy clean.
- npm: 70 tests, typecheck, generation and packed-artifact checks clean.
- Contracts: schema, SDK parity, field parity, manual drift, the
  `/info`-to-contract sweep, the product-divergence guard and the new
  fixture-to-contract check all pass.
