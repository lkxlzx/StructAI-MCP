# midas-nx 2.7.4

A shared PyPI/npm version release. **The npm package changes; the Python one
does not.**

`src/midas_nx/` has not changed since 2.7.3 — an identical wheel goes out under
a new number, because the two registries move together. The reason for this
release is on the npm side, and it both breaks types and un-breaks several
others. 2.7.3 and 2.6.0 are the earlier worked examples of the same situation.

## Read this first — npm breaking change

Three payload types were flat interfaces with every member optional and are now
**discriminated unions**, exactly what happened to `FloorLoadPayload` in 2.7.3:

| Type | Endpoint | Discriminator |
| --- | --- | --- |
| `StaticSeismicLoadPayload` | `/db/SSEIS` | `PERIOD_METHOD`, `SEIS_CODE` |
| `StaticWindLoadPayload` | `/db/SWIND` | `INPUT_METHOD`, `WIND_CODE` |
| `TendonProfilePayload` | `/db/TDNA` | `SHAPE`, `INPUT` + `CURVE` |

Fifteen members became required across the three, they are `type`s rather than
`interface`s so `extends` and declaration merging break, and a field the manual
documents under one discriminator value no longer typechecks under another.
The number is a patch; the breakage is real, and this section is why.

## The other direction — types that had been outlawing documented values

Three defects went the opposite way, and all three were shipped. Each was found
by comparing what a manual section states **twice** — once as a Specifications
table, once as a JSON Schema — rather than reading either alone.

**`/db/CO_S` and `/db/CO_T` offered two of nine colour components.** The manual
compresses them into one row keyed `"W_R" ~ "HE_B"` for No. `1-9`. Read as a
list of literal keys that is two fields, and both SDKs published two: a caller
could set the wire frame's red and the hidden edge's blue, and nothing else.
The section's own JSON Schema names all nine in order, its request example sends
all nine, and the sibling `/db/CO_M` lists them individually.
`SectionColorPayload` now declares all eleven fields.

**Rebar sizes stopped at D8.** `/DESIGN/RC/KDS-41-20-2022/DCRM-BEAM` declares
`MAIN_REBAR` with description "19종 (D4 ~ D57)" and `enum: ["D4" … "D8"]` in the
same object. Adopted as an enum it typed away every bar size from D10 up — the
sizes rebar design actually uses. `SrcLiveLoadReductionFactorPayload` was
blunter still: `...(전체 11개)` was a legal value. Fourteen fields across four
endpoints, nine distinct names, widen to their declared scalar type.

**A union rejected discriminator values the manual documents.**
`FloorLoadPayload` accepted only `FLOOR_DIST_TYPE` 1 and 2 while `/db/FBLA`
documents 1 to 4; `SkewPayload` lost `iMETHOD: 1` (Angle), whose fields are all
in the base table; `MovingLoadCaseBsPayload` lost every load model but
`"STANDER"`. A union is now closed only where the contract proves it — a
declared `enum` the branches cover exactly, or both values of a boolean — and
otherwise carries a trailing member for the rest. It still denies the other
branches' fields, so `LOAD_ANGLE` under `FLOOR_DIST_TYPE: 3` remains an error.
10 of the 13 union payloads carry one; the other three are proven closed.

## Contracts

**Promoted 319 → 337**, 3,160 fields, 47 drafts still awaiting review. 253 of
the 750 generated npm payload types now come from a contract, and 268 of the
304 resources have one.

Three extraction rules were added, each because it had already produced a wrong
contract:

- **A variant value may not select two field sets.** `/db/ELEM` was promoted
  with `STYPE: 1` twice and `STYPE: 2` twice — the manual heads those tables
  "Tension only — Truss (STYPE: 1)" and "Compression only — Truss (STYPE: 1)",
  so the gate is the pair with `TYPE`, whose values live in a footnoted code
  table. A repeated value is now evidence the heading names half the gate, and
  `validate_contracts.py` refuses the shape outright.
- **A key range is not a key list.** `"W_R" ~ "HE_B"` expands only when the No.
  column's span and the section's JSON Schema property order agree on the count.
- **A list the manual's own description outsizes is not an enum.**

`/db/FIMP` was un-promoted. Its table keys rows `"KENPAR"."FC"` and never lists
the `CONC`/`STEEL` parents, so a contract drafted from it declared a three-level
object as ten flat top-level fields — replacing a correct payload with a wrong
one. A section whose JSON Schema names a root its table never mentions now
blocks promotion; nine sections are in that position, recorded as MD-10.

## Live verification

**399/399 recorded, 172 write / 227 read** (165 write at 2.7.3). Seven endpoints
moved read → write: `/db/HAHS`, `/db/HECB`, `/db/LCOM-SEISMIC`, `/db/SDVE`,
`/db/SDVI`, `/db/SPLC` and `/db/THMS`.

Four of them are worth noting for what their earlier failures were not.
`/db/SPLC` answered a Gen-only `Unknown Error`, `/db/THMS` never round-tripped,
and `/db/SDVE` and `/db/SDVI` answered `Wrong Field` on both products. All four
were **abbreviated fixtures** — a payload missing fields the manual's own
Request Example sends — not product behaviour.

`/db/HPCE` and `/db/CSCS` deliberately stayed read-level — the first returns the
same `Wrong Key` for every node-count tried, the second needs a COMPOSITE
section the manual's own sample cannot build. Neither was given an invented
wire shape to make it pass.

## Validation

- Python: 919 tests, ruff and mypy clean.
- npm: 55 tests, typecheck, generation and packed-artifact checks clean.
- Contracts: schema, SDK parity and manual-drift checks pass.
