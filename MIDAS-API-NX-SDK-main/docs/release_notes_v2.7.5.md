# midas-nx 2.7.5

A shared PyPI/npm version release. **Both surfaces change**, which is new: the
last three releases moved the number for npm's sake alone.

Python's change is two words. npm's is the largest type correction the contract
work has produced so far, and one of them is a type no caller could satisfy.

## Read this first — npm breaking changes

| Type | Endpoint | What changed |
| --- | --- | --- |
| `SectionBoundaryDataPayload` | `/db/SBDO` | `AXIS_VECTOR` is `Array<number>`, not `number` |
| `MaterialPayload` | `/db/MATL` | `TYPE`, `NAME`, `PARAM` required; `PARAM` entries carry the manual's fields inline |
| `SectionReinforcementPayload` | `/db/RPSC` | five members required; item fields inline |
| `RebarDesignCriteriaPayload` | `/DESIGN/RC/…/DCRE` | contract-driven; members required, enums declared |
| `RebarDesignCriteriaByWallMemberPayload` | `/DESIGN/RC/…/DCRM-WALL` | contract-driven |
| `ModifyColumnRebarDataPayload` | `/DESIGN/RC/…/REBC` | contract-driven |

`DcreBeamCriteria`, `DcreColumnBraceCriteria`, `DcreWallCriteria`,
`RebarDesignCriteriaByWallMemberItem`, `RcColumnRebarItem`,
`SectionReinforcementShearItem` and `SectionReinforcementLongitudinalItem` are
still exported and unchanged, but the payloads no longer refer to them.

Two resource labels follow their manual sections and their already-contracted
siblings: `rebarDesignCriteria.name` is now `"Design Criteria for Rebar"` and
`rebarDesignCriteriaByWallMember.name` `"Design Criteria for Rebars by Wall
Member"`. **That is the whole of the Python change** — the two classes' `NAME`
attributes moved with them.

## A type nobody could satisfy

`ConvectionCoefficientFunctionPayload` required `COEF`, which `/db/CCFC`
documents only under `TYPE: "CONST"`, *and* `SCALE_FACTOR` and `ITEM`, which it
documents only under `TYPE: "USER"`. No caller could satisfy that type without
sending fields their own branch does not have.
`InelasticMaterialPropertyPayload` asked for all six plasticity models at once.

**49 fields across nine contracts were in that state.** A `requirement:
required` carrying an `appliesWhen` is a branch's requirement, not the
payload's, and the generator read only the first half. The condition now lives
in the doc comment — `Required when TYPE = "CONST".` — which is where a
requiredness TypeScript cannot express belongs. Affects `/db/CCFC`,
`/db/EPMT`, `/db/ETFC`, `/db/HSFC`, `/db/MVLDid`, `/db/NLNK`, `/db/THFC` and
`/ope/GSBG`. Nothing that constructed a payload before stops compiling; code
that *reads* one of these fields may now need a guard under `strictNullChecks`.

## A field whose documented value did not typecheck

`/db/SBDO`'s Specifications table types `AXIS_VECTOR` `Number`. The same
section's JSON Schema types it an array of numbers, and the section's own
Request Example sends `[0, 0, 0, 0, 0, 0]`. The contract followed the table and
npm followed the contract, so the field's own documented value was a type
error. Python has had `List[float]` since the endpoint was added — the same
asymmetry `/db/CO_S` had in 2.7.4, where one surface read the schema and the
other read the table.

Nine parameter rows in the whole manual carry a Value Type their own section
contradicts. Seven are integer/number width, where nothing a caller sends is
refused by the difference. Two change the shape of the value: this one and
`/db/MATL`'s `PARAM` (`Object` against `array`, with every Request Example in
the section sending `[{...}]`). Both are corrected with a `manualDefects`
entry and recorded as **MD-11**; `extract_contracts.py` now refuses to promote
any further contract from a Value Type its own section contradicts.

## What found them: reading the schema against the assembled request

2.7.4's method was that a manual section states its request twice, and where
the two disagree the table is the lossy one. This release found where that
comparison could not happen at all.

A row's path is only correct once its table has been placed. `Assign` is
message transport, so chapter 26's `WALL` table row is at
`Assign.WALL.HORIZONTAL_REBAR` in the assembled request and a root row named
`HORIZONTAL_REBAR` while parsing — where it also collides with the
`MATERIAL_BY_DIAMETER_INPUT` member of the same name. The two spellings never
met, so the KDS rebar sections were transcribed without a single enum, default
or requiredness their own JSON Schema states. `/DESIGN/RC/…/DCRE` published
`SPLICED_BARS` three times: once with no enum and twice with one, decided by
nothing but which of the three rows happened to be compressed.

The schema is now read twice — once per table while parsing, for the tables
that never get merged, and once against the finished paths. It only fills
blanks, so the second reading cannot overrule the first.

Reaching those fields exposed three defects of this repo's own making:

- **A supplementary table numbering every row `(1)`–`(5)` has no parent row**,
  and recording the first at depth zero made it the parent of its own
  siblings. `/db/RCHK`'s `LAYER`, an integer, held `dD` and `BAR_NUM`;
  `/db/RPSC`'s boolean `OPT_DR` held the twenty fields after it; `/db/MATL`'s
  `STANDARD` held `CODE`, `DB` and `bELAST`. All three sections' Request
  Examples write those fields side by side, and so does the Python SDK.
- **A branch table whose heading names its object** — `#### PARAM — P_TYPE = 1`
  — describes a `PARAM` entry, not the request. Merged at the root it became an
  endpoint-level branch and the generator built
  `MaterialPayload & {P_TYPE: 1; STANDARD: string; …}`.
- **A field two branch tables both document** applies under both values.
  `appliesWhen` entries are ANDed, so a second entry would be a contradiction
  rather than a widening, while keeping the first alone said an orthotropic
  material may not carry a density. `/db/MATL`'s `DEN` and `MASS` now read
  `P_TYPE is 2 or 3`.

A compact key row is also split where the section's own schema names every key
in it — 11 of the 89 refused rows across the whole manual, all in `DCRE` and
`REBB`. The other 78 include every `/db/STCT`, `/db/MVLDeu`, `/db/MVHL` and
`/db/THIS-M1` row, whose schemas declare none of those keys, so
`FREQ1`/`PERIOD1` — one field the manual names two ways — stays refused without
needing a rule of its own.

## Contracts now own the names npm publishes

A contract's new `surface` block records `className`, `exportName`,
`modulePath` and `payloadTypeName`, and the generator asks the contract before
it asks a Python class. **273 of the 304 npm resources** have one; the
generator raises if a name disagrees, so moving a Python module can no longer
rename an npm export in silence. It raised once in this release, and it was
right to: the disagreement was Python's.

This replaces the older "class and module names remain compatibility anchors
until every resource is contracted" rule, which described a finish line the
design could not reach — there was nowhere in a contract to put a name.

**Promoted 337 → 342**, 1,296 operations, 42 drafts still awaiting review.
258 of the 750 generated npm payload types come from a contract. The five new
ones are `/db/MATL`, `/db/RPSC`, `/DESIGN/RC/KDS-41-20-2022/DCRE`, `DCRM-WALL`
and `REBC`.

Promotion also learned to tell a conclusion from a gap. It refuses a draft
carrying an unresolved `# NOTE:`, and made one exception by substring for the
nesting wording — which left the sampled-enum conclusion blocking three
contracts as though someone still had to decide it. Nobody does: that note says
in its own text that no enum is transcribed, and chapter 26 states in every
section that it prints 5 of the 19 rebar sizes. The extractor now marks settled
findings `# RESOLVED:` and the gate is one rule with no string matching.

## Live verification

Unchanged from 2.7.4: **399/399 recorded, 172 write / 227 read**. No live
session was run for this release.

## Validation

- Python: 941 tests, ruff and mypy clean.
- npm: 55 tests, typecheck, generation and packed-artifact checks clean.
- Contracts: schema, SDK parity and manual-drift checks pass.
