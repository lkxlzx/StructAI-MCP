# CLAUDE.md — midas-nx

Python and JavaScript/TypeScript SDKs wrapping the **MIDAS NX Open API**, with both language
surfaces covering **Civil NX** and **Gen NX**. Published as `midas-nx` on both PyPI and npm
(separate registries, one shared version number since 2026-08-28 — see Releasing). Repo `Dennis5882/MIDAS-API-NX-SDK`, branch `main`.

## Commands

```bash
pip install -e ".[dev]"         # Python dev setup
pytest                          # Python suite; no live server needed
ruff check src tests scripts    # Python lint
mypy                            # Python static typing
python scripts/gen_roadmap.py   # regenerate ROADMAP.md from docs/coverage.json
python scripts/validate_contracts.py   # validate contracts/ and check both SDKs against it

cd packages/typescript
npm ci                          # JavaScript/TypeScript dev setup
npm run generate                # regenerate npm resources/types from contracts (3 resources fall back to Python)
npm run typecheck
npm test
npm run build
```

Before a commit, run the checks for every affected surface. CI (`.github/workflows/ci.yml`) always
runs the Python checks on 3.11/3.12/3.13/3.14 and the npm generation, typecheck, tests, package build, declaration
safety checks, and packed-artifact smoke tests on Node.js 18/22. None of these tests needs a live server.

## How the npm and PyPI packages relate

Three layers, and they answer differently. Getting one confused for another is
what produced two wrong statements in this file on 2026-09-23, both written
while tidying prose rather than measuring.

**To someone installing either one: no relationship at all.** The npm package
declares no dependencies and ships `dist/`, README, CHANGELOG and LICENSE;
0 of 751 generated npm types come from Python. The wheel depends on `requests`
and nothing else. Neither package requires the other, and an npm user never
reaches Python or PyPI.

**Deliberately tied, and reversible:** one version number across both
registries (lockstep since 2026-08-28 — a release moves both even when only
one surface changed), and one upstream, `contracts/`, of which both SDKs are
equal implementations.

**Building the npm package needs Python — all of it, not part of it.**
`prepack` is `npm run generate && …`, `generate` shells out to
`python scripts/generate_typescript_sdk.py`, and npm runs `prepack` for
`npm pack` and `npm publish` alike, so publishing rebuilds `dist/` through
Python every time; `publish-npm.yml` sets up Python 3.13 and installs the dev
extra for PyYAML because of it. The *reason* left is small — the IEHG trio's
four metadata values, 3 of 305 resources, with no permitted source to contract
— but it gates the whole step: point `PYTHON_SRC` at an empty directory and
generation dies at `DbResource itself`. A small remnant holding the gate is
still holding the gate. An already-built `dist/` runs fine without any of this.

## Sibling repos on this machine

| Path | What it is |
| --- | --- |
| `E:\AI Study\MIDAS-API` | **The API manual — source of truth for every endpoint schema.** `docs/manual/*.md` |
| `E:\AI Study\Rebar-repair` | QuickRebar NX, a production web tool on the same API. Live-evidence source; its `CLAUDE.md` has a hard-won domain-rules section |

## Where things go

- `contracts/` — the **language-neutral source of truth**, being introduced endpoint
  by endpoint. Read `contracts/README.md` before touching it. The Python and npm
  packages are equal implementations of what is written there; neither is a source
  for the other, and neither may be used as a source for a contract. Permitted
  sources are the manual repo, `docs/live_verification_notes.md`, and live
  `/info/{endpoint}` introspection. `scripts/validate_contracts.py` validates the
  contracts and then checks **both** SDKs against them — a disagreement is an SDK
  defect, never a reason to edit the contract. Two things there are easy to get
  wrong: `documentedOptional` (a claim about the docs) and `safeToOmit` (a claim
  about the product) are separate booleans and must stay that way, and `risk`
  (what the endpoint is) and `mitigation` (what the SDKs do) are separate axes —
  a mitigated crash risk is still a crash risk.
  Since 2026-09-04 that parity has a fifth check, `check_field_parity`, and it
  exists because the other four never compared a **field name**: they compare
  routes, verbs, `products` and executable rules, which is how `/db/ELNK`
  published four fields beside a twelve-key TypedDict for months with every gate
  green. It resolves `surface.payloadTypeName` to the Python TypedDict of that
  name **in the module the endpoint's resource lives in** — the name alone is
  not unique, the RC and steel design chapters both having an `SRDF` and a
  `LENG` — follows nested TypedDicts, and fails on any wire name the SDK ships
  that the contract records nowhere. **One direction only.** A contract naming
  more than a TypedDict is the intended state; the reverse is the defect. Its
  first run found 73 keys across twelve endpoints, of which exactly one was an
  SDK defect (`/db/HHCT-M1`'s `M_GENERAL`) and the rest were contracts behind
  their own SDK — including three that published a flat record the server has
  never accepted, and `/db/LLAN`, where the flat shape had also manufactured ten
  false `safeToOmit: true` claims. Fixing one takes a permitted source; a
  TypedDict is the subject the check measures, never a source. `sdkOnly` waives
  a name the server does not take.
  A contract that declares part of its field list missing does **not** get
  skipped. Fifteen did when that waiver was written (2026-09-15, down from
  twenty, and worth another 214 unchecked names); **none does now** — the last
  of those tables were merged on 2026-09-22, and the only `unmergedTables`
  entries left are `/db/TDME`'s two, both marked `excluded`, which waive
  nothing. The rule stays for the next contract that needs it.
  Each `extraction.unmergedTables` entry records `fieldNames`, so the waiver is
  per-name: a name that table accounts for is a declared gap, a name in neither
  the contract nor any of those lists is a defect. `fields` had always given the
  count, and a count cannot be a waiver — it says a gap exists without saying
  what is in it. Writing the names down also exposed a parser defect on its own
  (MD-48): a Key cell can name several properties at once — `"bSD" / "iSDOPT" /
  "SDCONST"` — and the table parser returns the whole cell as one key, invisible
  for as long as it only fed a count.
- `src/midas_nx/` — the only thing that ships in the wheel (`packages = ["src/midas_nx"]`).
  - `client.py` — `MidasClient`, `Product` enum, exception hierarchy rooted at `MidasAPIError`.
  - `db/` — `/db/*` endpoints as `DbResource` subclasses.
  - `doc.py` / `ope.py` / `view.py` — `/doc/*`-style endpoints as **plain functions** (wrapped in
    `"Argument"`, not ID-keyed `"Assign"`).
  - `post/` — everything POSTing to the shared `/post/TABLE` (a `TABLE_TYPE` string selects the
    table, so these are functions over one generic `get_table()`, not a resource per table).
  - `design/` — design-code chapters (`rc_kds/`, `steel_kds.py`, `src_aiksrc2k.py`).
- `packages/typescript/` — the npm package. Hand-written runtime adapters live directly under `src/`;
  generated resources, operations, tables, and payload types live under `src/generated/`.
  `package.json` is the npm version source; `package-lock.json` must change with it.
- `scripts/generate_typescript_sdk.py` — for a contracted `/db/*` endpoint, derives the npm
  endpoint/name/products/methods/manual-chapter surface from its contract; the three
  uncontracted resources (the IEHG trio) still use the reviewed Python fallback.
  Since 2026-09-02 a contract's optional `surface` block
  also owns the **published npm names** — `className`, `exportName`, `modulePath`,
  `payloadTypeName` — for the 302 resources that have one, and the generator raises if a name
  disagrees with the contract, so moving a Python module can no longer rename an npm export in
  silence. This replaces the older "class and module names remain compatibility anchors until
  every resource is contracted" rule, which described a finish line the design could not reach:
  there was nowhere in a contract to put a name. Run it through `npm run generate`; do not
  hand-edit `packages/typescript/src/generated/*`.
  The generator asks the contract first and the Python class second (one function,
  `_resource_identity`). **Since 2026-09-17 it does not import `midas_nx`**: class facts are
  read from the source tree by `_static_resource_classes`, the same syntax trees the payload-type
  and operation readers already parse, and `tests/test_generate_typescript_sdk.py` fails if an
  import comes back. What that removed is the need for an **importable `midas_nx`**;
  publishing still needs Python. `prepack` runs `npm run generate`, which shells out to
  `python scripts/generate_typescript_sdk.py`, and npm runs `prepack` on `npm pack` and
  `npm publish` alike - `publish-npm.yml` sets up Python 3.13 and `pip install -e ".[dev]"`
  for PyYAML because of it. This bullet claimed the opposite until 2026-09-23.
  **None of this is a dependency of the published npm package**, which declares no
  dependencies and ships `dist/` alone: nothing an npm user installs reaches Python or
  PyPI, and what is read is this repo's own source files at generation time, never an
  installed distribution. The **source tree** is still load-bearing — deleting `src/midas_nx/` breaks `npm run generate`,
  and with it `npm publish`; an already-built `dist/` still *runs*, but publishing rebuilds it
  — because the IEHG trio still takes its resource identity
  from Python classes. Its types no longer do: 0 of 751 generated npm types come from Python
  TypedDicts since 2026-09-22, when the last 14 - exported names nothing in the generated SDK
  referenced - were withdrawn at the author's request (`_PYTHON_TYPES_WITHDRAWN`). **Since 2026-09-22 the types are decided by contracts alone**: which types exist and in which
  namespace is decided by the contracts for every type they own (payload roots by
  `surface.payloadTypeName` + `modulePath`, nested and argument types by their recorded
  namespace), the resource list is contracts ∪ Python classes rather than Python classes with
  contracts laid over them, and `types.ts` is written in name order because the old order was
  Python's class order, which no contract can state. A test deletes every TypedDict a contract
  owns (597) and requires `types.ts` unchanged. `pythonModule` stays in
  `schema/typescript-resources.json` as a record only. The `/post` request objects moved the
  same day: a table contract's `requestFields.additional` nests now and its `surface.nestedTypes`
  names the story tables' `ADDITIONAL` types and `NODE_FLAG`; `UNIT`/`STYLES` hang off an
  operation `surface` with no `exportName` on `/post/TABLE`, which names types without
  publishing a generated export. An `unmergedTables` entry marked `excluded: true` is a table
  review decided, with evidence, is not part of this API (`/db/TDME`'s two iGen code tables), and
  does not stop the contract's field list becoming the payload type. Only 3 of 305 resources still take their
  identity from a Python class: the IEHG trio, which has no permitted source and so can never be
  contracted. **`scripts/report_npm_type_provenance.py` measures the type side of that rather than
  leaving it to a hand count**, and `--check` holds both it and the exported-type count as
  ceilings in CI. **Since 2026-09-22 the 70 operations and 87 table wrappers
  are listed by the contracts, not found in Python**: an operation `surface` and a
  table contract's `surface` state the export, its place, its argument or TABLE_TYPE, and the JSDoc
  (`documentation`, seeded from the docstring the generator used to render, so no published text
  changed; from then on npm's text is owned there and Python's docstring is Python's). The old
  Python walks survive only as the other half of parity tests. Operation **argument types** are
  built from the operation contract's fields too, `"Argument"` wrapper row removed. That was the
  first time a function contract's requiredness reached a published type, and it showed:
  `/view/ACTIVE`'s `N_LIST` was required in every mode because the manual's table sorts rows under
  a *mode* column the extractor did not read (it does now, `_GROUP_COLUMNS`), and `/ope/LINEBMLD`
  required both the `CURVED` coefficients and the non-`CURVED` arrays. Both are fixed from the
  manual's own words. Where the manual gives no condition to cite, the argument stays on Python
  with its reason in `_ARGUMENT_TYPES_LEFT_ON_PYTHON` rather than publishing a type that refuses a
  call the product accepts. **Since 2026-09-21 a contract can own its
  nested types too**: `surface.nestedTypes` records, per field path, the name and namespace a
  nested object is *already published under* (the namespace is part of the public name), and the
  generator builds that type from the contract subtree, including any variant union attached
  there. Before that the generator emitted a payload root from the contract with its nested
  objects inlined, and published the named interfaces for those same objects from Python —
  `total=False`, so e.g. `BeamEndOffsetItem.TYPE` was optional beside a root that required it.
  Moving 228 of them made 415 members required across 156 types and added 37, and removed none;
  that is a public-type change the npm changelog has to state. Three refusals are built in: a
  name several contracts declare with different shapes (prose aside), a path whose shape a
  variant *above* it redeclares (`/db/SECT`'s `SECT_BEFORE`), and — until 2026-09-22 — a name
  the package did not already publish. That third one read the Python tree and went with it;
  `report_npm_type_provenance.py --check` now pins the exported type count (`EXPORTED_TYPES`)
  instead, so an export is still never added as a side effect. Also since 2026-09-22, an
  object only one branch declares can be named (`/db/NLCT`'s `NEWTON_ITEMS`), an entry's
  `branch` says which variant's version of a path it is (`/db/MCON`'s two `SLAVES` shapes),
  and conditions inside a nested type are read from its own root. Filling the contracts'
  member-less objects from each section's own JSON Schema found `/db/MCON` publishing a
  `LinearConstraintItem` no request could satisfy - both `TYPE` tables' members merged into one
  required `SLAVES` element, and the branch keys placed beside `TYPE` - now one `SLAVES` shape
  per branch. Deriving the element types
  also caught an extractor defect the name-only `check_field_parity` cannot see: **a `(1)`-numbered
  nested row whose key already appeared higher in the table was dropped**, because
  `extract_contracts.py` gave such rows no parent scope. Fixed there, and the 27 members it had lost
  across eight contracts were restored verbatim from the fixed extractor's own drafts — `/db/EFCT`'s
  `COMB_LIST[].LCNAME` and `/db/STAG`'s `DACT_ELEM[].GRUP_NAME` among them, both of which `/info`
  declares on both products. What remains Python-sourced is broken down in the
  script's docstring; most of it sits under no contract-generated root at all — operation
  arguments; the 0 `unmergedTables` roots left since 2026-09-22 account for none of it.
- `scripts/contract_from_info.py` — the one path into a contract that does not start at the
  manual. Seven Hyper-S `-M1` sections state a URL, their methods and nothing else, so live
  `/info` is their only permitted source; this fills a draft's `fields` from
  `schema/hyper-s-info.json` and leaves every other decision the extractor made alone. It
  writes `requirement: unstated` throughout — `/info` declares no `required` array, and
  `optional` would be a claim nobody has made — and it will not turn a value set named in a
  `description` into an `enum` or a variant: an `/info` schema is flat and states no branch
  anywhere, so a gate has to come from the manual or a live observation. Three of the seven
  (`/db/IEHG-GL-M1`, `/db/IEHG-PSS-M1`, `/db/IEHG-TRUSS-M1`) 404 on `/info` as well, which
  leaves them with **no permitted source at all**; they cannot be contracted as things stand.
  See `docs/contract_migration_brief.md`.
- `schema/info-baseline.json` — every `GET /info{endpoint}` the products answer, both
  products, captured read-only 2026-09-03. It is the server's own schema, never model
  data. `scripts/info_baseline.py` captures it (`--capture`, GET only, safe against an
  open model), diffs a fresh capture against it (`--diff`, which is how a product
  patch's effect on the API surface gets measured), and sweeps it against every
  contract offline (`--against-contracts`). That last mode is worth running after any
  batch of contract work: it is what found MD-34, where a contract written from the
  manual, promoted, and reviewed through its generated npm diff still had a shape the
  server refuses. Reviewing a generated diff proves the generator followed the
  contract; only `/info` proves the contract followed the product. It sweeps **both
  directions** — properties `/info` declares that no contract records, and names a
  contract publishes that `/info` declares nowhere. The second list is short (4 hits
  across 384 contracts) and is where a wrong *name* shows up rather than a missing
  one, which a one-directional sweep cannot see: MD-37 and MD-38 were both found
  that way. **Read the second list weakly.** `/info` listing a property is not the
  same as the server accepting only those — `/db/STBK`'s `LCNAME` is in neither
  product's schema and `scripts/live_crud_check.py` sends it in a confirmed round
  trip that passes on both — so absence from `/info` supports a note, never deleting
  a documented field. Removing one takes what settled `/db/REBC`: a live comparison
  where the documented shape was refused and the other accepted. A contract may
  waive a property it deliberately does not publish with `infoOnly`, which exists
  for placeholders like `/db/DRLS`'s `DUMMY`, not for anything a caller might send.
  `--divergence` answers a third question: **`products: [civil, gen]` says the route
  answers on both, never that the record is the same.** Ten of the 177 both-product
  endpoints declare different schemas, so a field listed without its own `products`
  is a claim about both products that is sometimes false; tag it (MD-46).
  **`/info` is neither a superset nor a subset of what the server accepts.** It
  declares `/db/POSL`'s `CODE` on Civil NX, which refuses it live even as an empty
  string — re-measured 2026-09-21, still `Wrong Field` with it and accepted without
  it. The other direction, `/db/STBK`'s `LCNAME`, is **weaker than this bullet used
  to claim**: the call is accepted without error on both products, but the record
  read back afterwards does not carry the field, so what is established is that the
  server tolerates it, not that it stores it. `/db/POSL` carries this argument. It is a schema document with its own errors — like the manual, just
  produced closer to the code and right far more often. Where `/info` and a live
  round trip disagree, the round trip wins.
- `schema/typescript-resources.json` / `schema/typescript-coverage.json` — committed generator outputs.
  CI fails if either these schemas or `packages/typescript/src/generated/*` drift after regeneration.
- `docs/coverage.json` — the **implementation inventory**: what exists, which module wraps it,
  which manual chapter documents it. It stopped carrying live evidence on 2026-09-21.
- `contracts/verification/ledger.yaml` — the **live-evidence ledger**, and the only place an
  endpoint's verification claim is stated. One record per session; `endpoints` lists what that
  session covered. `scripts/verification_ledger.py` resolves records into one claim per endpoint
  and is what every count reads. `ROADMAP.md` is **generated from both files** — never hand-edit
  `ROADMAP.md`. A record's **`level`** is `"read"` or `"write"` and means what the session
  *achieved*: `"write"` if a live call actually mutated model data or wrote a file on the NX host,
  `"read"` for everything else that answered — *including POST-shaped reads* (`/post/TABLE`,
  `*-REPORT` calls that returned "Please perform analysis" without producing output) and including
  a write the product refused before it changed anything. The HTTP verb doesn't decide it. Reads
  and writes prove different things — a GET proves the route exists and parses, only a round trip
  proves the request shape is one the server accepts, and every field-name/enum/default defect
  found so far was invisible to reads. **Re-verifying adds a record; it never edits one**, which is
  what the old append-only `method` string in `coverage.json` got wrong twice. Until the migration
  the same fact lived in two files — 40 contracts cite only a read session for an endpoint the
  ledger holds at write level, and the two disagreed about what `level` even meant. Those 40 were
  audited on 2026-09-21 and **none is a contract defect**: a ref names the session a contract was
  promoted from, and what would make a stale one worth acting on is the later write having revealed
  something the contract misses. `check_fixture_contract.py` measures that, and not one of the 40
  appears among its confirmed-side findings. Don't re-promote them to move the number; a test holds
  the property instead, and the ceiling stays as drift detection for endpoints that turn write next.
- `docs/live_verification_notes.md` — findings from real Gen/Civil NX sessions that are *not* in the
  manual. Deliberately kept out of the typed contracts; read it before trusting any `PRODUCTS` change.
- `docs/vendor_report_ko.md` — the issue report for MIDASIT, **unsent**; `scripts/make_vendor_docx.py`
  renders it. `docs/vendor_report_triage.md` is the working file behind it: which live findings are in
  it, which are held back and *why*, and the re-verification debt on the older items. Read the triage
  before adding anything, because two of the three standing holds are traps — a documentation claim
  measured against the vendored manual rather than MIDASIT's own article is what killed four of seven
  B-items in July, and `/TEMP/.../OCHECK` is closed by MIDASIT as not-a-defect, so re-raising it is the
  author's call. `docs/manual_defects_register.md` is the same idea for findings about the
  **documentation** rather than the product. All three collect; none of them acts.
- `AGENTS.md` — the root-level entry point **for an AI agent helping someone *use* the
  SDK**, as opposed to this file, which is for maintaining the repository. It says that
  in its second line, because an agent arriving at the repo finds `CLAUDE.md` first and
  following it is the wrong path for that job. It points at the language-matched context
  pack, the four hazards most likely to bite, the existence checks that stop invented
  names, and `examples/`.
- `examples/python/` and `examples/javascript/` — four runnable scripts each, the same
  four, twinned by name and payload so the two SDKs can be read side by side. Each states
  its risk level in its first lines. They ship in neither package; the READMEs link them
  on GitHub. A resource path written here is checked against the built package before it
  goes in, not recalled.
- `PLAN.md` — the hand-maintained big-picture roadmap (`ROADMAP.md` is the generated per-endpoint
  counterpart). It is **editable, and goes stale fast**: it spent v0.11.0–v0.11.2 listing shipped
  work as pending, because releases updated the code but not the plan. When a release changes what
  §2's status table or §4's milestone table claims, update them in the same commit, along with the
  "Last updated" line. Verify against the tree before restating status — most of the 2026-07-26
  corrections were things the plan asserted were missing while the file sat in the repo.
  Since 2026-09-21 the *numbers* no longer rely on that discipline:
  `scripts/check_state_numbers.py --check` re-derives every count stated by §2, by the live
  playbook's "Where things stand" and by its gates block — live coverage, fixture size, contract
  and field totals, and how much of the npm type surface still comes from Python — from the
  artefact that owns each, and fails in CI on a disagreement, including a claim that has been
  deleted rather than updated. **This file is a scanned region too**, so a count here is held to
  the same standard. It deliberately does *not* read PLAN.md's dated header block or §4: those
  record what was true at a release, and a milestone row is correct precisely because nobody
  rewrote it. That split is what the check found on its first run — §2's fixture counts were
  stale against the fixture, and against the header four sections above them.
  A consequence worth knowing when editing any of these files: the checker cannot tell a claim
  from an illustration, so don't spell out a superseded figure in a scanned region — describe it.

## Adding an endpoint

1. Scaffold from the manual chapter:

   ```bash
   python scripts/gen_endpoint.py \
     "E:\AI Study\MIDAS-API\docs\manual\05_DB_Boundary.md" /db/CONS --class-name Constraint
   ```

   (In Git Bash, prefix with `MSYS_NO_PATHCONV=1` or the `/db/CONS` argument gets mangled into a
   Windows path.)
2. Follow `src/midas_nx/db/node_element.py` as the reference pattern. Each resource declares
   `ENDPOINT` / `NAME` / `PRODUCTS` / `METHODS`, with a `{ClassName}Payload` TypedDict directly above
   it in the same module.
3. TypedDicts are **documentation, not runtime validation** — schemas are too conditional for a
   one-size-fits-all model. Put the manual's requiredness/defaults in a trailing comment per field.
4. Add a test mirroring `tests/db/test_node_element.py` (mock HTTP via `responses`, assert the
   request shape — URL, headers, JSON body).
5. Mark it `"implemented"` in `docs/coverage.json`, then rerun `scripts/gen_roadmap.py`.
6. Run `npm run generate` from `packages/typescript/`, review the generated TypeScript diff, and add
   or update hand-written npm adapters/tests when the endpoint needs behavior beyond generated metadata.
7. **If the endpoint needs a safety rule, it belongs in a contract, not in one language.**
   Write `contracts/endpoints/<id>.yaml`, then run `python scripts/validate_contracts.py`.
   `normalize_defaults` rules flow into the npm surface automatically through
   `npm run generate`; the Python side implements them in the resource class, and the
   validator fails if the two disagree. A rule that lives only inside
   `NodalMass.create()` reaches only Python's users — that is how the npm package
   shipped for a month able to crash a live NX session.

## Staying in sync with the manual repo

`docs/coverage.json`'s `vendored_at_commit` records which upstream commit this SDK reflects.

```bash
python scripts/check_manual_drift.py --manual-api-repo "E:\AI Study\MIDAS-API"
```

It maps changed chapters to affected `midas_nx` modules. **Bump `vendored_at_commit` only after
actually reflecting the changes**, then confirm it reports `has_diff: false`.

Two things that have already caused rework:

- **The official MIDASIT docs contain typos and self-contradictions, and the manual repo
  deliberately normalizes them** — marked with `⚠️` callouts that often say outright
  "다음 동기화 때 되돌리지 마십시오". Follow the normalized form. Do **not** transcribe an official
  typo verbatim into `src/` with a `[sic]` note; that shipped `"Drfit"` and
  `"Drift on the Center of Mass"` in v0.11.1 and had to be corrected a day later. Cross-check
  against the same enum in other chapters and against each article's own request example.
  Where a contradiction is genuinely unresolved (e.g. `"X_DIR"` in a table vs `"X-DIR"` in the
  working example), declare both and document which to try first.
- **A bulk "정기 점검" sync commit is often followed within a day by self-audit `fix(manual):`
  commits** correcting its own transcription. Re-run the drift checker instead of assuming one
  sync is final.

## Live-server behaviour worth knowing

- **A 200 does not mean success.** Several endpoints return HTTP 200 with an `{"error": {...}}`
  body. Since v0.12.0 `MidasClient._send()` detects this and raises `MidasResultError`
  (opt out with `raise_on_result_error=False`) — don't add a second check per call site, and
  don't regress it: before v0.12.0 the client returned the error dict as a successful result.
- **`/post/TABLE`'s top-level response key is unstable** (seen as `"Result Table"` and `"empty"`
  as well as the `TABLE_NAME` you passed). Match on shape — find the dict carrying `HEAD`/`DATA` —
  not on a key name. `post.base.unwrap_table()` does this; use it instead of indexing by
  `TABLE_NAME`. Confirmed 2026-07-26: **`"empty"` is just the default key for a blank
  `TABLE_NAME`**, and it can carry a full table — never read it as "no data".
- **Every path belongs to the machine running NX, not the one running the script.** Calls go
  through MIDASIT's relay, so the product is often on another PC. `EXPORT_PATH`, `/doc/SAVEAS`,
  `/doc/OPEN`, report and image paths all resolve there. A path that doesn't exist on that machine
  raises a modal dialog *there* and blocks the session, while the HTTP call still answers
  `{"message": "... command complete"}` — identical to success. **The failure shape depends
  on the product, not only the path**: on 2026-09-21 the same `/doc/SAVEAS` into
  `C:\Program Files\`, which the account cannot write to at all, answered Civil NX with
  `"MIDAS CIVIL NX command complete"` — byte-identical to a real save — and wrote nothing,
  while on Gen NX it raised `"...액세스가 거부되었습니다"` and the call **never answered**,
  hanging until a human dismissed the dialog. Verify a write with `/doc/OPEN`, never
  `os.path.exists()` — **and read its message, because it does not raise**: for a missing file
  it answers HTTP 200 `{"message": "... path is wrong (the file can't open)"}` with no `error`
  key, so `MidasResultError` stays silent. A probe that treated "no exception" as "the file
  exists" is what briefly put the opposite of the truth about Civil into this file. This cost an afternoon of chasing a "broken" `/doc/SAVEAS` that was
  working fine. **Do not derive the path from `verify_connection()["user"]`** — this rule used to
  say to, and 2026-08-31 disproved it: that field is the MAPI account's email
  (`sjj0507@midasit.com`), not the NX host's Windows profile, so a path built from it does not
  exist and raises exactly the blocking dialog the rule exists to avoid. Require an explicit
  writable directory on the NX machine instead, as
  `packages/typescript/scripts/live-crud.mjs` now does (`--save-dir`, refusing to run without
  one). **Four model extensions, two pairs, easy to mix up** (author-confirmed 2026-08-31):
  pre-NX Gen `.mgb` / Civil `.mcb`; **NX Gen NX `.mgbx` / Civil NX `.mcbz`**. `/doc/SAVEAS` wants
  the NX pair; `/doc/STAGAS` wants the legacy `.mcb` and rejects other spellings outright
  ("Please check the file name or extension"). Civil also *tolerates* `.mcbx` for `SAVEAS` — a
  2026-07 round trip wrote one and reopened it with 273 nodes — but it is not the product's own
  extension and this repo got it wrong twice by assuming it was. The Export menus differ by
  product too: Civil NX offers MCT and an "MCBZ File"; Gen NX offers MGTX/MGT variants and no
  MGBX. Both offer a product-named JSON export, which is `/doc/EXPORT`.
- **`DELETE {endpoint}` with an ID-keyed `"Assign"` body empties the whole table**, ignoring the
  ids — for `/db/NODE` that takes the attached elements with it. This is what the manual documents,
  and it cost a model before it was caught. The undocumented `DELETE {endpoint}/{id}` is the one
  that deletes a single record. `DbResource.delete()` uses it as of v0.14.0; the destructive form is
  `delete_all()`. Don't "simplify" `delete()` back to one request.
- **Not every failure carries an `error` key.** `/doc/ANAL` reports a failed solve as
  `{"message": "... Analysis failed."}` and `/doc/SAVEAS` returns `"... command complete"` for a
  save that never happened. Error bodies also arrive under **201**, not just 200. When adding a
  write endpoint, verify the failure shape live rather than assuming `MidasResultError` covers it.
- **`verify_connection()` can't see a blocked session.** While a modal dialog is up, `/mapikey/verify`
  still answers `"connected"` (the relay serves it) while every `/db/*` call times out.
- **Hyper-S (`-M1`) endpoints are Civil NX only** — it's the solver MIDASIT shipped with Civil NX.
  They 404 under Gen. Use `HYPER_S_ONLY` from `db/base.py`, not `CIVIL_ONLY`: Hyper-S is expected
  to reach Gen NX eventually, and that constant is the one place to widen when it does.
- **Most of ch08/ch17 (moving-load/bridge) is *not* actually Civil NX only**, despite the manual's
  framing and this SDK's `CIVIL_ONLY` docstring having said otherwise until 2026-07-29: 32 of 47
  declared-Civil-only endpoints (`/db/LCOM-CONC` with real populated data, the rest with an empty
  table) answer on Gen NX too, route + `/info` schema both confirmed live. `GEN_ONLY` in `db/base.py`
  documents which 15 are genuinely Civil-only. That the API answers doesn't mean driving a
  bridge/moving-load feature from a Gen NX session is a sound engineering choice for a given
  project — that's the calling engineer's judgment, not something `PRODUCTS` should gate.
- **A manual chapter can be wrong about its own endpoint's field names, not just an enum value.**
  `/db/REBW` (ch24, Modify Wall Rebar) is the confirmed case: live-checked 2026-07-29 against a
  real production Gen NX model, every field name in the manual's Specifications table
  (`VERTICAL_REBAR`, `HORIZONTAL_REBAR`, `STORY: {FROM,TO}`, `CONCRETE_FACE_TO_CENTER_OF_REBAR`,
  ...) is wrong — the live server's actual GET/`.info()`/PUT contract uses `VER_BAR`, `HOR_BAR`,
  `vSTORY_NAME` (a story-name array, not a range), top-level `DW`/`DE`, etc. Confirmed via a live
  PUT round trip (change → verify → revert), not just GET. Its sibling `/db/REBB` and the
  KDS-specific `/DESIGN/RC/KDS-41-20-2022/REBW` both matched their own docs exactly, so this isn't
  a systemic rebar-family issue — treat each endpoint's manual section as independently
  fallible, and cross-check `/info/db/...` against real populated data before trusting a
  Specifications table that's never been checked against a live model with actual data in it.
  `WallRebarPayload`/`WallRebarItem` in `db/design.py` now documents the server-confirmed shape.
  **`/db/REBC` is the second confirmed case**, found 2026-08-27: the manual and MIDASIT's own
  article both give a single-object `MAIN_BAR` with a top-level `DO`, and a live POST comparison
  settled it — the documented shape answers `Wrong Field` while the server's `vMAIN_BAR` array
  with a per-entry `D0` answers a *domain* error naming the missing target section. That
  distinction between "shape refused" and "shape accepted, target missing" is the cheapest way to
  tell a wrong payload from a wrong model, and it is worth reaching for before permuting field
  names. Both endpoints, plus `/db/REBB` and `/db/FIMP`, are now contracted from `/info` with
  `provenance: live_corrected` and the manual's claim recorded under `manualDefects` — that is the
  pattern to follow when a section is wrong rather than merely stale, and
  `contracts/endpoints/db-rebw.yaml` is the worked example.
- **A GET can still pop a modal dialog if the open document lives under `Program Files`** (or any
  other path a standard account can't write to) — confirmed live 2026-07-29 with `GET /db/CAMB`
  (FCM Camber Control, a plain read): with the product's own bundled tutorial file open from
  `Program Files\...\Tutorial\`, the call still answered `{"message": ""}` but a
  `"...액세스가 거부되었습니다"` (access denied) dialog popped anyway; moving the same file to
  `Downloads` and repeating the identical call produced no dialog. This generalizes the
  crash-recovery-only `_restore.mcb`-under-`Program Files` case (vendor report A-7) into a broader
  pattern: some read-shaped commands write an auxiliary/cache file next to the document even to
  answer a GET. The 2026-09-21 attempt to re-measure this on Civil is **not evidence either way**: it
  assumed a document opened from `Program Files`, and the `/doc/OPEN` that was supposed to
  provide one had answered `path is wrong` unread. The 2026-07-29 observation stands as the only
  measurement. `scripts/live_readonly_sweep.py`'s "GET only, safe" claim still holds for *data*
  safety, but keep working documents off `Program Files`-style paths before running it.
- **Verifying against a live session: the two read-only sweeps are the safe ones.** Python's
  `scripts/live_readonly_sweep.py` and — since 2026-09-03 — npm's
  `packages/typescript/scripts/live-readonly.mjs` (`npm run live:readonly -- -- --product gen`)
  issue GET only, so either can run against a model the user has open. Prefer the one matching
  the surface you are checking: each imports its own SDK, so a wrong endpoint string or product
  gate in that package shows up as a 404 there and nowhere else. They proved equal on
  2026-09-03 (282 Civil resources, 267 Gen). A clean sweep proves routes exist and parse and
  nothing about request shapes — every field-name, enum and default defect found so far was
  invisible to a GET. **Four** harnesses call `/doc/NEW` and **discard unsaved work**:
  `scripts/live_smoke.py`, `scripts/live_crud_check.py`, since 2026-09-01
  `packages/typescript/scripts/live-crud.mjs`, and since 2026-09-19
  `scripts/live_manual_feedback.py`, which calls it once per probe rather than once per
  run. Never run one against someone's open document without asking first. The npm one
  saves a checkpoint before the `/doc/NEW` unless `--no-save-before` is passed; that flag
  removes the safety net, not the destructive call. Every one of them writes its
  checkpoints to a directory **on the NX machine** that the caller names with `--save-dir`;
  none of them guesses one, because a path that does not exist there raises a blocking dialog
  while the HTTP call still answers like a success. **Since 2026-09-21 all four ask the same
  way and refuse to start when nothing is named** — `scripts/harness_save_path.py` holds the
  rule, the reasons and the two stated departures, and `tests/test_harness_save_path.py` checks
  each harness applies it. `--save-dir` takes a directory and the file name is derived from the
  product, so the NX extension pair (Gen `.mgbx`, Civil `.mcbz`, against the pre-NX `.mgb`/
  `.mcb` that `/doc/STAGAS` wants) cannot be got wrong; `--no-save-before` waives the checkpoint
  and **not** the `/doc/NEW`. The shape is checked while arguments are parsed, not at the save,
  so a relative path costs nothing — not even a connection. The departures: `live_crud_check.py`
  also accepts `--save-as` for an exact path, and `live_manual_feedback.py` has no waiver,
  because its per-probe saves are the evidence the run produces rather than a safety net.
- **`/info/{endpoint}` introspection is served for `/db/*` only.** Swept from both SDKs
  2026-09-01: it answered for 399 of 402 `/db/*` resource-product pairs and for **none of the
  147 `/DESIGN/*` pairs**, even though those design endpoints answer a plain GET
  (`GET /DESIGN/RC/KDS-41-20-2022/DCTL` returns `{"message": ""}` while
  `GET /info/DESIGN/RC/KDS-41-20-2022/DCTL` is a 404, in every casing tried). It is an API
  fact, not a URL bug in either SDK. This narrows `contracts/README.md`'s permitted sources
  for the design-code family from three to two — the manual and recorded live behaviour — so
  a design contract can never carry `provenance: info_schema`. The three `/db/*` exceptions
  are the Civil Hyper-S trio `/db/IEHG-GL-M1`, `/db/IEHG-PSS-M1` and `/db/IEHG-TRUSS-M1`.
- **`scripts/live_crud_check.py` write coverage is tracked in the script itself.** Cases carry
  `confirmed=True` only once someone has watched them pass live (183 of 220 cases as of
  2026-09-20; the first 43 landed 2026-07-29 on Civil NX, after `/db/NMAS`'s crash was
  root-caused and worked around — see above); a failure of
  a confirmed case is a **regression** and exits 1, while a failure of an
  unconfirmed one exits 3 and means "triage the fixture first". Don't flip `confirmed` to silence
  a failure, and don't report an unconfirmed failure as an SDK defect — across three runs every
  failure resolved to a fixture, a wrong documented value, or a product bug, and the one real SDK
  defect was a wrong docstring. **Exactly one documented value has survived re-checking**, and
  this bullet claimed five until 2026-09-21. On 2026-07-27 every documentation claim was
  re-checked against the **official Zendesk articles** rather than the vendored copy, and three
  of the ones named here were retracted that day: `/db/TDMT` documents an exact 28-value
  `UNDERSCORED_UPPERCASE` enum, and the CEB-FIP spellings recorded as rejected were `/db/TDME`'s
  display strings fed to the wrong field — the two endpoints spell the same code differently,
  which `live_crud_check.py`'s `TimeDependentMaterialSeed` docstring tabulates; `"KDS2016"`
  appears in neither official article and came from a bad transcription; and `/db/SECF`'s
  "keyed by element id" was **this SDK's own docstring**, not MIDASIT's. The live findings
  behind them stand; the accusations do not. **Never cite the vendored manual as "the
  documentation" in anything sent outside** — fetch the article and quote it. What survives is
  `/db/PRES`'s `DIRECTION`, narrowed: the Specifications row marks it *Optional, default
  `"NORMAL"`* while the same article's own footnote matrix shows `NORMAL` unavailable for
  `"PLATE"` + `"FACE"`. So treat the manual's worked examples as a starting guess — and treat a
  documentation defect as unproven until the official article has been read. `/db/PRES`'s case was measured in
  full on 2026-09-03 and is worse than a wrong default: omitting the field is *how* the bad
  default gets applied, so both halves of the row fail together. Both SDKs now require
  `DIRECTION` explicitly rather than substitute anything — there is no value an SDK could pick,
  because which way a pressure acts is an engineering decision (contract rule
  `db-pres-direction-must-be-explicit`). `/db/MVHL`'s `VEHICLE_LOAD_NUM` used
  to head that list and was **retracted 2026-09-03**: it is the endpoint's branch discriminator
  (`1` standard, `2` user-defined) and behaves as documented. What is wrong there is the common
  Specifications table stating branch-1 and branch-2 requiredness with no reference to the
  branch — see MD-16.
- **`"Wrong Field"` from a `/db/*` write usually means a bad *value*, not a bad field name.**
  Confirmed on `/db/TDMT` and `/db/TDME`: an unrecognised `CODE`/`CODENAME` answers `Wrong Field`,
  while a recognised one with the wrong companion fields answers `"[Error] ... input data contain
  errors."`. A whole session went into varying fields on `/db/TDMT` before the value was suspected
  — vary the enum value first. Seed steps are per-case dependencies (`needs=`) for the same
  reason: one bad seed used to report 6 false blockages.
- **`*-ANAL` design-check calls** reproducibly hung Gen NX 2026 v2.1 (build 06/23/2026), then ran
  clean on that *same build*. Not a vendor fix; trigger unidentified. Use a short timeout and read
  the `*-TABLE` back regardless of whether the call returned. Full history in
  `docs/live_verification_notes.md`.
- Any call that can raise a **confirmation dialog** blocks the whole API session, not just that
  call, until a human dismisses it.
- **`POST /db/NMAS` used to kill both Civil NX and Gen NX — root cause found and worked around
  2026-07-29.** 15+ reproductions across both products (multiple Civil versions/builds, a real
  production model, a same-LAN-as-the-host caller, a from-scratch minimal fully-connected model)
  first ruled out every wrong explanation — not an idle timeout, not a blocking save-changes
  dialog, not model topology, not which machine the HTTP request comes from — before landing on
  the real one: **the server crashes when the optional `rmX`/`rmY`/`rmZ` fields are omitted from
  the payload, and does not crash when they're sent explicitly, even as `0.0` (their documented
  default)**. Confirmed symmetrically on both products in the same session: a full-fields call
  survives, an immediately following omitted-fields call on a different node kills that same
  session every time — reads as an uninitialized-value read server-side for those three fields
  specifically. `NodalMass.create()`/`.update()` (`db/static_loads.py`) now fill them in
  automatically before sending, so calling the class through this SDK is safe without knowing any
  of this; `live_crud_check.py`'s `/db/NMAS` case runs unquarantined now (`--include-crashers` is
  still there for any future case that needs it). Full reproduction history in
  `docs/live_verification_notes.md`; the vendor report's A-1 now leads with the root cause and
  the workaround, not just "it crashes."
- **Open a document before the first `/doc/NEW`.** On 2026-09-17 Gen NX had no project open
  (`GET /db/NODE` answered `The project is not opened`), and a `/doc/NEW` sent then did not
  answer and left the session blocked until the product was brought back up. Every harness
  assumes a document is already open; if that GET says otherwise, ask for one.
- **A `/db/SPFC` write with `CALC_OPT: true` leaves the document modified after a save.**
  On 2026-09-22 a probe saved right after one, and the next `/doc/NEW` raised a save-changes
  dialog on both products and never answered, blocking both sessions until the author
  restarted them. The server-built curve evidently lands after `/doc/SAVEAS` returns. Probes
  now give a design spectrum an explicit `aFUNC` instead; if one must send `CALC_OPT: true`,
  do not `/doc/NEW` after it without a human watching. Details in
  `docs/live_verification_notes.md`.
- **An `--endpoints` selection can drop a case another case depends on**, and
  `scripts/live_crud_check.py` does not warn. extras14's `/db/DYFG` and `/db/DYNF` need that
  tier's `/db/MVCD` case to switch the moving-load code to EUROCODE first; selected without it
  they are refused, which read as a regression on 2026-09-16 and was not one.
- **`/doc/NEW` has crashed Gen NX** when the open document was a large real model (2026-07-26,
  v2.1 build 06/23/2026) — the "Failed to disconnect the work session" license dialog, which
  always kills the app and holds the license until the process is restarted properly. Harmless
  a dozen times over against small scratch documents the same day. Never point `scripts/live_smoke.py`,
  `scripts/live_crud_check.py` or `packages/typescript/scripts/live-crud.mjs` at a session holding
  a model that matters; get the user to press New Project first and confirm the document is empty.

## Releasing

PyPI and npm use the same package name and, **as of 2026-08-28, the same version number**.
**Reversed at the author's explicit request** — this rule previously said the two version streams were
independent and that you must "not bump both versions merely to make the numbers match when only one
packaged surface changed." They are now kept in lockstep: one package name across two registries that
reports two different versions is confusing to the people the SDK is for, and that outweighs the
tidiness of a per-registry changelog.

What lockstep means in practice:

- A release bumps **both** `src/midas_nx/__init__.py`'s `__version__` and `packages/typescript/package.json`
  (plus `package-lock.json`) to the same number, and publishes **both** a `py-vX.Y.Z` and a `js-vX.Y.Z`
  GitHub Release.
- One number covers both surfaces, so it can never be right for both at once. The author picks it;
  don't bump on your own reading of semver. Whatever it says, the release notes must state plainly
  what actually changed in each surface and what actually breaks. The 2.6.0 release is the worked
  example in both directions: nothing in `src/midas_nx/` changed at all (an identical wheel went out
  under a new number), while the npm side removed exported interface members — a breaking removal
  shipped deliberately as a minor bump to keep the numbers aligned, called out at the top of the
  npm changelog so anyone using those fields is not ambushed by a number that looks safe.
- A release where one surface has no shipped change at all is still a real release for that registry —
  it republishes an identical wheel or tarball under the aligned number. Do not skip it; a skipped
  bump is how the streams drifted apart in the first place.

The unprefixed `v*` tags are historical; all new package releases use `py-v*` or `js-v*`.

### Python / PyPI

A release is warranted when **either** packaged surface changed — `src/midas_nx/` behaviour or
packaged metadata, or the npm package's source, declarations or metadata. `scripts/`, `docs/` and
`.github/` ship in neither and warrant nothing on their own. Under lockstep versioning (see above)
the Python version moves even when only the npm surface changed; re-derive from the actual diff
which surface is the reason, and say so in the release notes.

1. Commit the code changes **together with `PLAN.md`'s "Last updated" line and §2/§4 tables**,
   updated to the state this release actually leaves the repo in. This step used to be a separate,
   easy-to-skip rule stated only in "Where things go" above, disconnected from this checklist — and
   it did get skipped: the v1.0.0 bump commit (`0fb0454`, 2026-07-29) said in its own message that
   all three of PLAN.md's v1.0.0 gate criteria were met, but never touched `PLAN.md` itself, and
   that went unnoticed until the v1.1.0 release. Don't repeat that: if this release changes what
   §2's status table or §4's milestone table claims, that's part of "the code changes," not an
   optional follow-up.
2. Separate commit: `chore: bump version to vX.Y.Z` editing only `src/midas_nx/__init__.py`'s
   `__version__`. That is the **single source** — `pyproject.toml` declares `dynamic = ["version"]`
   and hatchling reads it from there. (Until v0.11.2 the bump edited `pyproject.toml` instead, which
   left `midas_nx.__version__` reporting `0.10.0` on a `0.11.2` install; `tests/test_version.py`
   now fails if the two drift apart.) Keep `PLAN.md` out of *this* commit — it belongs in step 1.
3. `git push origin main`.
4. **Publish the GitHub Release** (tag `py-vX.Y.Z`). `gh` CLI is installed and authenticated
   (`gh auth status`, `repo` scope) as of 2026-08-27 — Claude Code can run `gh release create` directly
   once the author has said so for that release; draft the release notes as a short highlights list
   (not an exhaustive per-file diff) either way. The author may still choose to publish manually via
   the web UI instead — check which one they want, don't assume.
5. That Release triggers `.github/workflows/publish.yml` (PyPI Trusted Publishing). The workflow
   explicitly ignores every release whose tag does not start with `py-v`; `release` events do not
   support path filtering.
6. Verify with unauthenticated public APIs:
   `api.github.com/repos/Dennis5882/MIDAS-API-NX-SDK/releases/latest`, the same repo's
   `actions/workflows/publish.yml/runs`, and `pypi.org/pypi/midas-nx/<version>/json`.
   PyPI's `/json` `latest` field caches — query the exact version path to confirm.

### JavaScript / TypeScript / npm

An npm release accompanies every Python release and vice versa — see the lockstep rule above. What
changed in `packages/typescript/src/`, its generated public declarations, or npm packaged metadata
decides the *notes*, and a breaking change here makes the shared number a major bump; it no longer
decides whether npm gets a release at all.

1. Update the reviewed Python model and `docs/coverage.json` first when the official API contract changed.
2. From `packages/typescript/`, run `npm run generate`, then review both `src/generated/` and the
   repository-root `schema/typescript-*.json`. Never hide generator drift by editing generated files directly.
3. Bump `package.json` and `package-lock.json` together (for example,
   `npm version X.Y.Z --no-git-tag-version`).
4. Follow `packages/typescript/RELEASING.md`: promote `CHANGELOG.md`'s `Unreleased` entries into the
   new version, run `npm run prepack`, and inspect the declarations and `npm pack --dry-run` contents.
5. Commit and push, then publish a GitHub Release with tag `js-vX.Y.Z`. That triggers
   `.github/workflows/publish-npm.yml`, which ignores non-`js-v` releases, repeats generation and
   package checks, verifies the tag against `package.json`, and publishes through npm Trusted
   Publishing (OIDC). No npm token or one-time code belongs in the repository or workflow.
6. One-time external setup: on npmjs.com, configure `midas-nx`'s GitHub Actions Trusted Publisher
   for repository `Dennis5882/MIDAS-API-NX-SDK`, workflow `publish-npm.yml`, no environment, and
   allow `npm publish`. The workflow uses Node.js 24 and `id-token: write` for this trust exchange.
7. Verify the public result with `npm view midas-nx version dist-tags --json` and a clean temporary
   install/import smoke test. The PyPI and npm workflows remain separate even when a release changes
   both language surfaces; create one `py-v*` Release and one `js-v*` Release in that case.
   When generating GitHub notes, explicitly select the previous `js-v*` tag so Python releases are
   not included in the npm comparison.

## Conventions

- **README framing**: lead with what the SDK does, then the project-status paragraph.
  **Reversed 2026-08-02, at the author's explicit request** (this rule used to say
  "the author removed all official/unofficial positioning — don't reintroduce it"):
  the root README and registry-facing package docs now *do* carry a short status paragraph, because the
  author is a MIDAS IT employee and "built by an employee, from real product
  verification" is the SDK's actual provenance and worth stating. It must convey all
  three of: built by a MIDAS IT employee from hands-on verification; **not** an
  officially released or supported MIDAS IT product; SDK issues → GitHub Issues,
  product/licensing/Open-API-service issues → MIDAS IT official support.
  Still forbidden: logos, trademark usage, any wording implying company endorsement,
  and the comparison against MIDASIT's own packages. Don't rename the project.
  Officialization talks with MIDASIT HQ are open and undecided as of 2026-08-02 — if
  they conclude, this wording is the first thing to revisit.
  The root README carries parallel Korean / 繁體中文 / 简体中文 blocks plus
  `docs/{ko,en,zh-tw}/quickstart.md`; the npm-facing guide is
  `packages/typescript/README.md`. A user-facing wording change usually means checking all of them.
- **Windows consoles are cp949.** Non-ASCII in `print()` or an uncaught traceback either crashes or
  mangles. Scripts call `sys.stdout.reconfigure(encoding="utf-8")`; user-facing exception text stays
  ASCII (hence `(Hint: ...)`, not an em-dash).
- Commit messages: imperative subject, body explaining *why*. Match `git log`.
