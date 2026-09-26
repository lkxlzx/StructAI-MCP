# midas-nx 2.7.7

A shared PyPI/npm version release. **The largest breaking npm release the
contract work has produced**, and the patch number does not say so — the
version is kept aligned across the two registries rather than derived from
semver, so read this file rather than the digits.

`src/midas_nx/` ships two corrected resource labels and nothing else
behavioural. Its TypedDicts move with the contracts, and one of them renames an
importable name; see "Python surface" below.

## Read this first — npm breaking changes

| What | Scale | Why |
| --- | --- | --- |
| `Assign` is no longer a payload member | 60 payload types | `DbResource.create()`/`.update()` build the envelope from the `ItemMap` you pass; supplying it produced `{"Assign": {"1": {"Assign": …}}}` on the wire |
| `BraceMainBarSpec` renamed `BraceMainBarItem` | 1 exported interface | `/db/REBR` takes `vMAIN_BAR`, an array; the single-object `MAIN_BAR` with a top-level `DO` is a shape `GET /info/db/REBR` declares nowhere |
| Records that change shape | 18 | Each published a nesting the server refuses — the npm changelog lists them one by one |
| `ITEM.M_GENERAL` removed | `HeatOfHydrationAnalysisControlHyperSPayload` | `/db/HHCT-M1` has no such field; the TypedDict shared an item type with `/db/HHCT`, which does |
| `LAYER` removed | `RcBeamMainBarLayerEntry` | This SDK's own inference; no statement in chapter 26 names it |

**Nothing that worked on the wire stops working.** Every removal is a field the
server does not take or a nesting it does not accept. If your build breaks, the
type was describing a request that would have been rejected.

Additive in the same release: 72 field doc comments now say "Gen NX only." or
"Civil NX only."; four fields appear on all six `/db/LCOM-*` payloads; and
`VehiclePayload`, `MovingLoadCasePayload`, `TrafficLineLanesOptimizationPayload`
and six others gain members their objects never had.

## The check that compares field names

The contract validator had four parity checks and none of them compared a
**field name**. They compare routes, verbs, `products` and executable rules,
which is how `/db/ELNK` published four fields beside a twelve-key TypedDict for
months with every gate green.

`check_field_parity` resolves a contract's `surface.payloadTypeName` to the
Python TypedDict of that name **in the module the endpoint's resource lives
in** — the name alone is not unique, the RC and steel design chapters both
having an `SRDF` and a `LENG` — follows nested TypedDicts, and fails on any
wire name an SDK ships that no contract records. **One direction only.** A
contract naming more than a TypedDict is the intended state; the reverse is the
defect.

Its first run found **73 keys across twelve endpoints**:

- **One was an SDK defect.** `/db/HHCT-M1`'s `ITEM.M_GENERAL`, which neither
  the manual's table nor `GET /info/db/HHCT-M1` gives that endpoint.
- **Eleven were contracts behind their own SDK**, three of which published a
  flat record the server has never accepted (`/db/LLAN`, `/db/LLANch`,
  `/db/LLANid`) and a fourth that put a nested object's members at the root
  (`/db/THIS-M1`). In every case the contract's own `extraction.table` had
  recorded the destination-naming heading since the day the draft was made —
  the promotion read a heading that named a *destination* as though it named
  the record.

`/db/LLAN` is the expensive one, and not for its own sake. Its flat shape
manufactured **ten false `safeToOmit: true` claims**, because promotion
compares a confirmed live payload's top-level keys against the contract's field
list, and a flat list makes every nested member look like a top-level key
somebody had proven omissible. A wrong shape does not stay a shape problem — it
manufactures false claims on the axis the safety rules read. The
omission-safety count went *down* this release, from 128 proven safe to 119,
and that is the correction.

## The blind spot behind it

The check skipped any contract declaring part of its field list missing.
Twenty do. That was another **214 unchecked names** — three times what the
first run found.

`extraction.unmergedTables` entries now record `fieldNames`, so the waiver is
per-name rather than per-contract: a name that table accounts for is a declared
gap, a name in neither the contract nor any of those lists is a defect.
`fields` had always given the count, and **a count cannot be a waiver** — it
says a gap exists without saying what is in it. The extractor emits the names
into new drafts and `--check` verifies they still equal what the table holds,
so a row added upstream cannot widen a waiver in silence.

214 → 84 → 0. The 84 closed as two endpoints whose record the server would
refuse (`/db/THIS-M1`, and `/db/MVLD`, which published `LCNAME`, `DESC` and
`TYPE` and nothing to carry the load), four empty objects, and `/db/MVHL`'s
48-field `VEH_EUROCODE`.

Writing the names down exposed a parser defect of its own. **A Key cell can
name several properties at once** — `"bSD" / "iSDOPT" / "SDCONST"`,
`SFI(STR)`, `"_3_LANE_FACTOR_1" ~ "_3_LANE_FACTOR_4"` — and the table parser
returns the whole cell as one key. 64 occurrences, invisible for as long as
that cell only fed a *count*. `_unpack_key_cell` transcribes the three forms
that occur and applies **only to `fieldNames`**; merged rows still go through
`_REVIEWED_SHARED_COMPACT_KEYS`, which demands a named review per row, because
a merged row becomes a published field and an exempted one does not. Registered
as MD-48.

## `/info` is committed, and swept both ways

`schema/info-baseline.json` holds every `GET /info{endpoint}` both products
answer, captured read-only. `scripts/info_baseline.py --against-contracts`
sweeps it against all 381 contracts **in both directions**. The reverse
direction — names a contract publishes that `/info` declares nowhere — is
short (4 hits) and is where a wrong *name* shows up rather than a missing one:
MD-37 and MD-38 were both found that way.

**Read the reverse list weakly.** `/db/STBK` ships an `LCNAME` no `/info`
schema declares and a confirmed round trip sends it successfully on both
products, while `/db/POSL`'s `CODE` is declared on Civil NX and refused live
even as an empty string. `/info` is neither a superset nor a subset of what the
server accepts — it is a schema document with its own errors, like the manual,
just produced closer to the code and right far more often. Where `/info` and a
live round trip disagree, the round trip wins.

The sweep also settled a claim the contracts had been making without evidence:
**`products: [civil, gen]` says the route answers on both, never that the
record is the same.** Ten of the 177 both-product endpoints declare different
schemas — `/db/SPLC` by 15 fields, `/db/POGD` by 20, `/db/SBDO` by 16. Mostly
it is the two products' own feature sets (Gen NX has walls and fiber hinges,
Civil NX has bridge seismic parameters) rather than a transcription slip, so a
field listed without its own `products` was a claim about both products that
was sometimes false. Tagged, and recorded as MD-46.

## Python surface

Two resource labels in `db/design.py` follow their manual sections:
`RebarCheckInput.NAME` is now `"Rebar Input for Checking - Beam/Column"` and
`BraceRebar.NAME` (`/db/REBR`) is `"Modify Brace Rebar Data"`. **That is the
whole behavioural change.**

TypedDicts are documentation rather than runtime validation, so the shape
corrections above do not change what any call sends. Two are worth knowing if
you import the types directly:

- `midas_nx.db.design.BraceMainBarSpec` is renamed `BraceMainBarItem`.
- `HeatOfHydrationAnalysisControlHyperSPayload.ITEM` now points at a new
  `CreepShrinkageItemHyperS`, which is `CreepShrinkageItem` without
  `M_GENERAL`. `/db/HHCT` is unaffected.

## `/db/NMAS`'s crash does not reproduce

Re-tested on build 09/02/2026 on both products: the omitted-`rmX`/`rmY`/`rmZ`
payload that killed 15+ sessions now survives. The workaround in
`NodalMass.create()`/`.update()` **stays**. Nothing on the record says this was
fixed deliberately, and the failure mode reads as an uninitialized-value read —
the kind that stops reproducing without being gone.

## Counts

- Contracts **358 → 381** of 399 endpoints; `surface` blocks 289 → 301; drafts
  awaiting review 26 → 3.
- 4,916 fields: 119 proven safe to omit, 8 proven unsafe, 4,789 unverified.
- Manual defects register **MD-17 → MD-48**.
- 294 contracts now compared against a Python payload type by name; 17 waive
  part of the comparison through `unmergedTables`, 6 name a type Python does
  not define, 0 are ambiguous.
- npm: 764 payload types, 282 of them from contracts; 723 exported interfaces.

## Validation

- Python: 996 tests, ruff and mypy clean.
- npm: 60 tests, typecheck, generation and packed-artifact checks clean.
- Contracts: schema, SDK parity, field parity and manual-drift checks pass.
