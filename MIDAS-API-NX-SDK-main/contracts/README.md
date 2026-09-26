# `contracts/` — the language-neutral source of truth

Everything in this directory describes the **MIDAS NX Open API itself**, not any
SDK that wraps it. The Python package and the npm package are two equal
implementations of what is written here. Neither one outranks the other, and
neither one is a source for the other.

## Why this exists

`POST /db/NMAS` crashes MIDAS NX when the optional `rmX`/`rmY`/`rmZ` fields are
omitted. That was root-caused on **2026-07-29** and worked around in
`NodalMass.create()` the same day. The npm package shipped on **2026-08-26** — a
month later, generated from that same Python source — **without the workaround**,
so any caller reaching `/db/NMAS` through it could still hang and kill a live NX
session.

That was not carelessness. The generator carried metadata and docstrings across;
the workaround was *behaviour* inside a method, and behaviour had nowhere to
live. A safety rule that exists only inside one implementation reaches only that
implementation's users.

So the rule moved here, where it is a fact about the endpoint rather than a
property of one language binding, and
[`scripts/validate_contracts.py`](../scripts/validate_contracts.py) fails CI when
an implementation does not honour it.

## Permitted sources

| Source | Use it for |
| --- | --- |
| [`Dennis5882/MIDAS-API`](https://github.com/Dennis5882/MIDAS-API) `docs/manual/*.md` | Field names, types, defaults, requiredness, enums, methods |
| `docs/live_verification_notes.md` | What a real Gen NX / Civil NX session actually did |
| `GET /info{endpoint}` | The server's own schema, for endpoints the manual describes poorly — **`/db/*` only**, see below |

`/info` does not exist for every endpoint. Swept from both SDKs on 2026-09-01,
it answered for 399 of 402 `/db/*` resource-product pairs and for **none of the
147 `/DESIGN/*` pairs**, while the design endpoints themselves answer a plain
GET. The three `/db/*` exceptions are the Civil Hyper-S trio `/db/IEHG-GL-M1`,
`/db/IEHG-PSS-M1` and `/db/IEHG-TRUSS-M1`. So a design-code contract has two
permitted sources, not three, and `provenance: info_schema` is not available to
it — do not read a 404 there as a reason to fall back on an SDK.

**Forbidden as a source: `src/midas_nx/` and `packages/typescript/src/`.** Not
because they are untrustworthy — much of what is recorded here was learned while
building them — but because a contract derived from an implementation cannot
detect that implementation being wrong. `validate_contracts.py` reads both SDKs,
and it reads them as *subjects under test*: when a contract and an SDK disagree,
the finding is an SDK defect. Fixing it by editing the contract defeats the whole
arrangement.

Every field records where it came from in `provenance`:

- `manual` — transcribed from the manual chapter
- `live_verified` — the manual's claim was checked against a running product
- `live_corrected` — the manual was wrong and a live check replaced it (record
  the mismatch under `manualDefects` so a manual re-sync cannot quietly restore
  the error)
- `info_schema` — taken from `GET /info{endpoint}`

There is deliberately no value meaning "read off an SDK". Do not guess a field or
a behaviour into existence: if the manual does not describe it and nobody has
observed it, it does not belong in a contract.

`info_schema` was unused until 2026-09-02, when four Hyper-S contracts were
written from `schema/hyper-s-info.json` by
[`scripts/contract_from_info.py`](../scripts/contract_from_info.py). Those four
sections state a URL, their methods and nothing else, so `/info` is not a
preference there but the only source there is. Reading it comes with two rules
the script enforces, because a source nobody can cross-check is the one that
most needs them:

- **Silence is not permission.** `/info` declares no `required` array, so every
  field is `unstated`. Not `optional` — that is a claim about documentation
  that no document makes.
- **A value set in a `description` is not an `enum`, and never a variant.** An
  `/info` schema is flat and states no branch anywhere, so a discriminator read
  out of prose would be an inference about the endpoint dressed as a fact about
  the capture. `/db/MATL`'s contract, drafted from the manual's identical
  prose, keeps its values in the description too. A gate has to come from the
  manual or a live observation.

Two defects in the served schemas are registered as **MD-12**: apostrophes
escaped with a backslash, which is not a JSON escape, and `maxItems` stated on
an array's `items` subschema where JSON Schema ignores it. The first is
repaired in the prose, the second recorded and not transcribed.

## The names the packages publish

Everything else in a contract records what the product and the manual say.
`surface` records what the **packages called it**:

```yaml
surface:
  className: Node
  exportName: node
  modulePath: [db, nodeElement]
  payloadTypeName: NodePayload
```

It exists because those four were the last facts about an endpoint that lived
only in a Python class and the file it happened to sit in. Moving a Python
module renamed an npm export with nothing to object, which is the one thing
`contracts/` is supposed to make impossible.

Three things to know:

- **It renamed nothing.** Every value was seeded from the generator's own
  committed output on 2026-09-02, so the two published APIs are byte-identical
  across that change. These are public API anchors on both registries; changing
  one is a breaking change, and now it is a breaking change you have to make on
  purpose.
- **It is optional, and its absence means the Python fallback.** 302 of the 305
  npm resources have one; the 3 without a contracted surface keep taking their
  names from Python, exactly as they already do for `name` and `products`.
  All three are the IEHG trio, which has no permitted source at all and so can
  never be contracted. `/DESIGN/STEEL/DSTL` was the fourth until it was promoted
  on 2026-09-16. `payloadTypeName` is separately optional: `/db/DRLS` is typed
  `JsonObject` and has no payload type of its own, so having no name there is a
  fact, not a gap.
- **The generator refuses a disagreement**, as it does for every other contract
  fact. `className`/`exportName`/`modulePath` are checked as resources load;
  `payloadTypeName` is checked after generation picks it, because a legacy
  TypedDict shared by endpoints with different contracts gets renamed on the way
  through.

### Nested types: `surface.nestedTypes`

A payload root has had a contract-owned name since 2026-09-02, but the objects
inside it did not. The generator built the root from the contract, inlining
every nested object, and then published the **named** interface for each of
those objects a second time from the Python TypedDict - with Python's field
list and Python's `total=False`. One object, two public shapes:
`DbBoundaryTypes.BeamEndOffsetItem.TYPE` was optional beside a `/db/OFFS` root
whose `ITEMS` element required it.

```yaml
surface:
  className: BeamEndOffset
  exportName: beamEndOffset
  modulePath: [db, boundary]
  payloadTypeName: BeamEndOffsetPayload
  nestedTypes:
    - {path: ITEMS, name: BeamEndOffsetItem, namespace: DbBoundaryTypes}
```

`path` is the field inside `fields` (an array's entry names its element type);
`name` and `namespace` are what the package **already publishes** - the
namespace is part of the public name, because every namespace is re-exported
at the package root. The generator then builds that type from the contract
subtree, variant unions attached there included. Seeded on 2026-09-21 from the
committed output, so recording an entry renames nothing; it does change the
type's *shape* to the contract's, which is the point.

It refuses three things rather than guess:

- a name several contracts declare with different shapes once descriptions are
  set aside - `BAR_SECTOR_I` and `BAR_SECTOR_J` may say which end they are, but
  not have different members;
- a path whose shape a variant **above** it redeclares, as each `SECTTYPE`
  branch of `/db/SECT` redeclares `SECT_BEFORE` - there is no single subtree;
- (until 2026-09-22) a name the package did not already publish. That check
  read the Python tree, and went when placement moved to the contracts; the
  exported type count pinned in `scripts/report_npm_type_provenance.py` is its
  replacement, so recording a name still cannot add an export unnoticed.

Three things added on 2026-09-22 widened what can be declared without
loosening any of those:

- **An object only a branch declares** is found in that branch. `/db/NLCT`'s
  `NEWTON_ITEMS` exists only when `ITERATION_METHOD` is `"NEWTON"`, so it is a
  field of a variant, not of the base; several branches declaring the same path
  must agree on its shape, and a path the base declares too is still a
  redeclaration and refused.
- **`branch`** on an entry names which variant's version of a path it is, for
  the case where branches genuinely differ and each version has its own
  published name: `/db/MCON`'s `ITEMS.SLAVES` is `LinearConstraintSlaveExplicit`
  under `TYPE: EX` and `LinearConstraintSlaveWeighted` under `TYPE: WD`. It must
  equal one variant's `when` exactly.
- **Conditions inside a nested type are stated from its own root.**
  `HaunchPartSelector` is `PART_A`, `PART_B` and `PART_C` of `/DESIGN/.../HCBM`
  alike, and `PART_A.INPUT_METHOD` is wrong for two of them; the generator
  rewrites an `appliesWhen` path that starts inside the object before comparing
  or rendering. Member order does not count as a difference either.

Where a manual section's Parameters table names an object without its child
rows - `/DESIGN/.../CDESIGN`'s `RESULT_GRAPHIC.DISPLAY_MEMBERS`, the RC wall
calls' `SELECTIONS` - the members come from the same section's JSON Schema, with
the line cited under `extraction.prose`; that is what lets `extract --check`
tell a reviewed fill from drift.

The namespace an entry states is where the type is written. Since 2026-09-22
nothing about a contract-built type's placement comes from Python: a payload
root goes in the namespace its `modulePath` names, and deleting the TypedDict a
contract has taken over leaves `types.ts` unchanged.

A contract carrying `unmergedTables` may not declare any: its payload is not
generated from the contract, so there is no subtree to build from.

### A function endpoint's surface lives on the operation

A `/db/*` resource publishes **one** npm export carrying every method, so its
names belong to the endpoint. A function endpoint - `/doc/*`, `/ope/*`,
`/view/*`, the design-code calls - publishes **one export per method**, so its
names belong to the operation:

```yaml
operations:
  - method: GET
    surface:
      exportName: getStoryParameters
      modulePath: [ope]
  - method: POST
    surface:
      exportName: setStoryParameters
      modulePath: [ope]
      argumentTypeName: StoryParameterArgument
```

`/ope/STORY_PARAM` above is the case that forces the shape: one endpoint, two
exports, different names and different arguments. A single top-level `surface`
could not have said it.

Two fields beyond the resource block's, and both earn their place. `argumentTypeName`
is unqualified because the namespace is derived from `modulePath` - the
generator builds both from the same module parts, so storing the namespace
would only create something that could disagree. It takes a list where an
operation publishes a union, which two `/ope` load-combination calls do. And
`takesArgument: false` marks a POST whose caller passes nothing - the SDK sends
the empty `{"Argument": {}}` the contract's `request` records - which generates a
different npm operation kind from one whose argument is merely untyped; that
distinction is invisible in the type name, so it needs a field of its own.

Added 2026-09-17 and seeded from the generator's own committed output, so it
renamed nothing: 68 of the 70 operations were named by their contract, the
generated TypeScript was byte-identical, and the generator raises on any
disagreement between the contract and the Python function it is generated
beside. The other two, `/post/PM` and `/post/STEELCODECHECK`, got contracts the
same day, so all 70 are now named by one. They had none because chapter 23 is a
`/post/TABLE` chapter and the extractor skipped it whole; it now reads a section
in those chapters whose `Input URI` is a route of its own, and still skips the
shared-table ones.

Until 2026-09-22 this section closed by saying the generator could not create
anything - only *correct* facts about something Python already declared, so a
contract for an endpoint with no `DbResource` subclass was skipped outright.
**That is no longer true.** The resource list is contracts ∪ Python classes,
the 70 operations and 87 table wrappers are listed by the contracts rather than
found in Python, and no generated type's shape comes from a TypedDict. What still reads the Python source tree is the IEHG
trio's resource identity - three endpoints with no permitted source, so there
is nothing to invert them to. That is why `npm run generate` still needs the
source tree present even though it needs no importable install (since
2026-09-17 the class facts are read from source, not imported), and why
deleting `src/midas_nx/` breaks generation - measured 2026-09-23, it fails at
`DbResource itself` - and with it `npm pack` and `npm publish`, both of which
run `prepack` and so re-run the generator. An already-built `dist/` still runs.
None of it reaches the published npm package, which declares no dependencies
and ships `dist/` alone.

## Unknown message shapes

`request.wrapper` and `response.wrapper` describe only shapes supported by the
permitted sources. Use `unknown` for a response when the manual establishes the
route and method but says nothing about the response body. It is not shorthand
for `table`, `message`, or an empty body, and it must not be narrowed from an
SDK implementation. This matters for several non-`/db` design-resource DELETE
examples: the manual shows a bodiless `requests.delete(...)` call but does not
state its deletion scope or response.

## Explicit payload variants

Use `variants` only when every additional manual table names the same wire
discriminator and an exact value, such as ``TYPE = "EIGEN"``. Each variant
retains its source table and line, and its fields are not merged into the common
field list. A heading like “LINEAR only” does not establish the selector value;
it remains in `extraction.unmergedTables` until the manual states enough to
model it without inference.

`when` is an array of conditions combined with logical AND - the same shape a
field's `appliesWhen` uses, so one construct covers a nested discriminator
(`STR.SPEC_CODE`), a two-level selector, and the multi-value case below.

Since 2026-09-22 an operation `surface` is also **the list**: the generator
reads the 70 npm operations from the contracts instead of finding Python
functions that call `_post`/`_get`, and each surface carries two more keys:

- `documentation` - the JSDoc npm publishes on the export. Seeded from the
  Python docstring the generator used to render, so no published text changed;
  from then on it is npm's text, owned here, and the docstring is Python's.
- `nestedTypes` - as at the top level, for objects inside the **argument**.
  Paths are inside `fields` with the `"Argument"` wrapper row removed, which is
  how the argument type itself is now built: `argumentTypeName` names a type
  the generator builds from this contract's fields. An argument named by
  several contracts must come out the same from each, and a contract with
  `unmergedTables`, a union argument, or an entry in the generator's
  `_ARGUMENT_TYPES_LEFT_ON_PYTHON` (each with its reason) stays on Python.

Building argument types was the first time a function contract's
*requiredness* reached a published type, so it was read against the manual
row by row before shipping. Two rows needed a condition the manual states and
the contract had lost - `/view/ACTIVE` sorts its rows under a mode column, and
`/ope/LINEBMLD`'s load coefficients are `CURVED`-only or `CURVED`-excluded. A
`requirement: required` with `appliesWhen` is how "required in this branch"
is written; the generated type makes it optional and says when it is needed.

Table contracts (`contracts/tables/*.yaml`) gained a `surface` the same day,
for the same reason: `exportName`, `modulePath`, the default `tableType` (a
prefix for a `directional` wrapper), `factory`, `optionNames` and
`documentation`, seeded from what the generator used to find in Python.

A table's **own request fields** - the ones only some tables honour - go in
`requestFields.additional`, and since 2026-09-22 an entry may nest
(`properties`, `items`, `enum`, `appliesWhen`, like an endpoint field). The
story tables' `ADDITIONAL` objects and the plate/solid tables' `NODE_FLAG` are
written there from the manual, and `surface.nestedTypes` on the table names
the npm types built from them (`ADDITIONAL` -> `PostStoryTypes.StoryDriftAdditional`).
A row naming two keys - `LCOMS[].NAME` / `LCOMS[].FACTOR` - is two fields. The
shared request objects, `UNIT` and `STYLES`, belong to `/post/TABLE` itself:
its POST operation carries a `surface` with `nestedTypes` and **no
`exportName`**, which is how an operation says it names types but publishes no
generated export (npm's `post.getTable` is written by hand).

One shared name did not move. `PostStoryTypes.StorySetAngle` is the `SET_ANGLE`
object of four story tables, and the manual makes its `ANGLE` required in two
and optional in two; one published type cannot follow both, so it stays on
Python and each table's own `ADDITIONAL` type inlines the version it documents.

### `in`: one table, several documented values

A condition takes either `equals` (one literal) or `in` (two or more), never
both. `in` transcribes a heading naming several values for the *same* table -
`/db/FBLA`'s `FLOOR_DIST_TYPE = 1 or 2`, `LOAD_MODEL=2/3`. It is never a guess
at the rest of an enum: every value in it is written in the manual.

Such a table is the manual's **shared** table, not a further branch. `/db/FBLA`
documents one table for `= 1`, one for `= 2`, and one for `= 1 or 2`; the third
applies to both. So every value an `in` names must already have a single-value
branch of its own, and TypeScript generation folds the shared fields into each
branch it covers rather than emitting a union member that would match the same
discriminator twice.

What `in` deliberately does **not** solve: two tables claiming the *same* single
value. `/db/NLNK` splits `REF_SYSTEM=1` into Angle/3Points/Vector and `/db/HSFC`
splits `TYPE="FUNC"` by whether concrete data is used - in both the second
selector is real but the manual never names it as a wire field. Those stay
unmerged. A discriminator that is not written down cannot be transcribed.

The same rule catches a heading that names only **half** of the gate.
`/db/ELEM` heads five tables `STYPE: 1` through `STYPE: 3` across four element
types, so `STYPE: 1` heads both a tension-only truss and a compression-only
truss; the discriminator is the pair with `TYPE`, whose wire values the chapter
puts in a footnoted code table rather than in the headings. A repeated value is
the evidence, so the extractor leaves every table gated on a repeated field
unmerged, and `validate_contracts.py` refuses any contract - hand-written
included - whose variants claim one condition twice.

**An unmerged table no longer blocks the contract.** The manual is not perfect
and neither is the product, so a contract that says "these fields, and one table
I could not model" is more useful than no contract at all. Record each such
table under `extraction.unmergedTables` with a `resolution` - "the manual names
no wire discriminator; left unmerged" is a legitimate one, the point is to say
so rather than to have solved it. `promote_contract.py --resolution` writes it,
because drafts are regenerated build output and cannot be hand-edited.

What such a contract may **not** do is narrow a published type. While any
`unmergedTables` entry is present the npm generator ignores this contract's
field list and keeps the reviewed fallback payload, so promoting an incomplete
contract never breaks a caller who sets a field from the table nobody merged.
Everything else - products, methods, risk, `sdkRules` - is owned by the contract
as usual.

## One route, several manual sections

An endpoint can be documented more than once. The RC and SRC design chapters
describe `/DESIGN/RC/KDS-41-20-2022/TABLE` and `/DESIGN/SRC/AIK-SRC2K/TABLE`
once per result table — five sections for two routes — and each of those
sections says outright that it shares a URI with its siblings and is told apart
*only* by `Argument.TABLE_TYPE`. Chapter 17 likewise repeats chapter 15's
`/ope/GSBG` on purpose, for readers of the bridge chapter.

One route is one contract. `scripts/extract_contracts.py` folds such sections
when — and only when — the manual's own claim holds: their field tables agree
everywhere, or agree everywhere except one field. The folded field keeps every
value the sections named, as an `enum` where the chapter gave one, and keeps
each section's description joined, because each section calls *its* value fixed
and "one of three" is a thing the manual never says. `extraction.mergedSections`
lists every section that went in, so the fold stays reviewable against the
chapter rather than being taken on trust.

Anything wider is refused, and the emit run says which sections it refused.
`/ope/GSBG`'s two chapters transcribe one endpoint differently — one writes
`Required (BATCH=true)` inline, the other uses the bold variant headers — and
averaging them would publish a request shape neither chapter states. Splitting a
shared route the other way, into one id per section, is equally wrong: it would
invent routes the manual does not describe.

Response columns are not part of the fold. They belong to a table contract under
`contracts/tables/`, keyed by `TABLE_TYPE`. All five design-force tables are
already contracted there against `/post/TABLE`, which chapter 23 documents as
serving the same `TABLE_TYPE` values through the shared result-table route.

## Arguments that are not a field list

`request.itemSchema` says what the argument carries: `fields` (this contract's
field list), `scalar` (one primitive - name it in `scalarType`), `empty` (an
object the manual documents as carrying nothing), or `none` (no body).

Nine `/doc/*` sections have a JSON Schema and no Specifications table, and that
is documentation rather than a gap: `/doc/OPEN` and `/doc/SAVEAS` take a bare
path string; `/doc/NEW`, `/doc/CLOSE` and `/doc/SAVE` take `{}`. An empty
`fields` list is the correct transcription for those, so promotion and the
manual-drift check both accept it when the request says so explicitly.

`scalar` and `empty` are claims about the documentation, not escape hatches. A
body the permitted sources do not describe is still `none`.

## `documentedOptional` versus `safeToOmit`

These are modelled separately, and the distinction is the single most important
thing in this schema.

- `documentedOptional` is a statement about **the documentation**.
- `safeToOmit` is a statement about **the product**.

`/db/NMAS`'s `rmX` is `documentedOptional: true` and `safeToOmit: false`. The
manual is correct that the field is optional, and following the manual kills the
session. Collapsing the two into one boolean loses exactly the case that hurts
people — the caller who read the documentation and did what it said.

`safeToOmit` has three values, and `unverified` is not a lesser one:

| Value | Means | Requires |
| --- | --- | --- |
| `true` | A live call omitted it and succeeded | `omissionEvidence` citing that call |
| `false` | Someone omitted it and something broke | `omissionEffect`, plus an `sdkRule` if the field is also documentedOptional |
| `unverified` | Nobody has omitted it against a running product | nothing |

Most fields are `unverified`, and saying so is the point. "The manual says
Optional" is **not** evidence for `true` — that is what `documentedOptional`
already records, and treating it as an answer is precisely the reasoning
`/db/NMAS` punishes. The first two contracts written by hand got this wrong and
were corrected: their coordinates and translational masses now read `unverified`,
because `scripts/live_crud_check.py`'s confirmed payloads send all of them.

Where evidence does exist, it is mechanical: 116 cases in that checker are marked
`confirmed=True`, meaning someone watched that exact payload complete a live
round trip. A documented field absent from such a payload was omitted and the
call still worked. `scripts/extract_contracts.py` reads those payloads and fills
in `safeToOmit: true` with the case cited — 437 fields across 72 endpoints.

## Documented defaults

`documentedDefault` carries only a literal wire value that the manual states
unambiguously. When a Default cell contains prose such as `System`, `Auto`, or
`ADD, REPLACE`, keep `documentedDefault: null` and preserve the exact manual
cell in `documentedDefaultNote`. The note records the manual's wording; it is
not a claim about the server and is never evidence that a field is safe to
omit. A same-section JSON Schema `default` may replace the note only when it
states the identical literal value.

## Unstated manual columns

`requirement: unstated` and `documentedOptional: null` mean the manual did not
state whether the field is required. They must occur together: `null` is not a
third optionality state and says nothing about whether omitting the field works.
Likewise, `type: unstated` records a missing Value Type cell instead of guessing
`string`. A same-section JSON Schema can still supply either fact when the
manual explicitly gives it there; otherwise the absence remains part of the
contract.

## Risk and mitigation are separate axes

`risk` describes the endpoint. `mitigation` describes what the SDKs do about it.

`/db/NMAS`'s POST stays `risk: product_crash_risk` with
`mitigation: normalized`: the server defect is real and present on shipped
builds, while the SDK rule makes the crashing payload unreachable. Downgrading
the risk because it has been mitigated would erase the reason the rule exists,
and the next person to read the contract would delete the rule as ceremony.

Mitigations, in rough order of how much they cost the caller:

| `mitigation` | Meaning |
| --- | --- |
| `normalized` | The SDK fixes the payload silently. The caller needs to know nothing. |
| `confirmation_required` | The call is refused without an explicit confirmation flag. |
| `opt_in_required` | The call is refused unless the caller opts into a known hazard. |
| `warn_only` | Documented loudly; no behaviour change. |
| `none` | Nothing is done. |

Prefer `normalized` where a correct payload is knowable. Requiring a caller to
opt into a hazard the SDK could simply have avoided is a worse outcome, not a
safer one.

## Layout

```
contracts/
  README.md                          this file
  schema/
    endpoint-contract.schema.json    JSON Schema for contracts/endpoints/*.yaml
  endpoints/
    db-node.yaml                     one file per endpoint; file name == `id`
    db-nmas.yaml
    db-grup.yaml  db-rigd.yaml  db-offs.yaml  db-co-m.yaml
  drafts/                            git-ignored; `draft: true`, not contracts
  safety/
    known-product-risks.yaml         cross-endpoint client rules + product defects
  verification/
    gen-nx.yaml                      dated, build-specific live findings
    civil-nx.yaml
```

Verification records are split per product on purpose. Product support is an
observed fact rather than a manual claim, and the two products diverge: `/db/REBW`
answers on Gen only, the Hyper-S (`-M1`) family on Civil only, and 32 of 47
endpoints the manual frames as Civil-only answer on Gen too. A single shared
record cannot carry a per-product date and build.

## Working on a contract

```bash
pip install -e ".[dev]"          # brings in pyyaml + jsonschema
python scripts/validate_contracts.py
python scripts/validate_contracts.py --no-parity   # schema + refs only
pytest tests/test_contracts.py
```

`validate_contracts.py` checks, in order: schema conformance; that every
`riskRef` and verification `ref` resolves; that `product_crash_risk` operations
carry a mitigation, a rule and a risk reference; that unsafe-to-omit optional
fields are covered by a rule; that a normalization value equals the field's
documented default (a rule may make a default explicit, never invent one); and
that the endpoint, products, methods and normalization rules each contract
declares match both SDKs.

## Adding a contract for an endpoint

Start from a machine-drafted transcription rather than retyping a table:

```bash
python scripts/extract_contracts.py                       # what is parseable
python scripts/extract_contracts.py --emit /db/STLD       # draft one endpoint
python scripts/promote_contract.py db-stld                # promote a reviewed draft
python scripts/promote_contract.py --all --dry-run        # what would qualify
python scripts/extract_contracts.py --check               # promoted vs. manual
```

`promote_contract.py` refuses more than it accepts, on purpose. It will not
promote a draft that still carries review notes, one whose section has
conditional variant tables nobody has merged, one whose methods the manual never
states, contains a key row that still names more than one wire property, or is
one of the eight endpoints whose documented payload has already been
measured wrong live - putting the manual's version of `/db/SECF`'s key into the
source of truth would be worse than having no contract for it. Run
`python scripts/promote_contract.py --all --dry-run` for the current measured
set rather than relying on a copied count.

`--emit` writes to `contracts/drafts/`, which is **git-ignored and ignored by the
validator**. Every draft carries `draft: true`, which the schema forbids, so a
file moved into `contracts/endpoints/` without being read fails CI with one
unambiguous message rather than passing as fact.

Of the 4,927 fields the extractor can read, 1,114 (22%) carry a review note
— no Default column, an enum whose values live elsewhere in the chapter, a row
naming two keys at once, a condition the manual gestures at but never states.
Those notes travel into the draft. Clear them; don't delete them.

Then:

1. Read the endpoint's chapter in the manual repo yourself. The draft is a
   starting point, not a review. Fields keep `provenance: manual`.
2. Check `docs/live_verification_notes.md` for anything observed about it. Where
   live behaviour contradicts the manual, the contract records live behaviour,
   `manualDefects` records the mismatch, and the field's `provenance` becomes
   `live_corrected`.
3. Set `verification.status` honestly. `manual_only` means transcribed but never
   called — it is not a lesser state, it is the truthful one.
4. Add `sdkRules` for anything a caller could reasonably do that breaks the
   product.
5. Run `npm run generate` from `packages/typescript/` and
   `python scripts/validate_contracts.py`. Both SDKs must satisfy the contract
   before it lands.

## Migration status

Three hundred and thirty-seven endpoints and eighty-seven result tables are contracted. The remaining ledger lives in `docs/coverage.json`
(399 endpoints) and is being migrated incrementally, so an endpoint without a
contract is expected rather than a defect. What is *not* optional is that a
contract, once written, is honoured by both SDKs.

What the extractor can currently reach, per `scripts/extract_contracts.py`:

| | |
| --- | --- |
| Endpoints found across chapters 01-17 and 24-27 | 384 |
| ...with a parameter table it can parse | 368 |
| Fields transcribed across parsed tables | 4,927, of which 375 nested |
| ...carrying a review note that has to be cleared before promotion | 1,114 (22%) |
| Promoted so far | 342 endpoints + 87 tables |
| Drafts awaiting review | 47 |
| Payload types the npm SDK now takes from contracts | 258 of 750 |
| DB resources the npm SDK now takes from contracts | 273 of 304 |
| Contracts carrying explicit conditional variants | 14 |
| Supplementary tables merged as an explicit variant | 78 |
| ...merged structurally or by `appliesWhen` | 74 |
| ...left unmerged, across 24 sections | 101 |
| Enum fields whose complete value list is not stated | 20 |
| Arrays whose element type is not stated | 5 |
| Unrecognised Value Type cells | 15 |
| Sections belonging to the shared `/post/TABLE` family | 89 |

The 89 `/post/TABLE` sections (chapters 18-23) are one endpoint selected by a
`TABLE_TYPE` string, with response `HEAD` columns instead of a request payload.
They need a two-layer contract — endpoint plus table — which the schema does not
model yet, so the extractor reports them rather than flattening them into
endpoint contracts.

Still to come: that two-layer model. The reversal of Python-to-npm generation
that stood here landed 2026-09-21/22, bar the IEHG trio, which has no permitted
source to reverse it to. **Folding `docs/coverage.json` into
`contracts/verification/` landed 2026-09-21**: live evidence is now `contracts/verification/ledger.yaml`,
resolved by `scripts/verification_ledger.py`, and `docs/coverage.json` keeps
only the implementation inventory. The per-product files here still carry the
session findings a contract cites for provenance.
