# midas-nx 2.7.8

A shared PyPI/npm version release. **One value changes in both packages, and it
is a value the server was refusing.** Nothing is removed, no exported name
moves, and no type changes shape.

## The fix

`/post/TABLE`'s surface-spring reaction type is **`REACTIONLSURFACESPRING`**,
with an L.

| surface | was | is |
| --- | --- | --- |
| Python | `TABLE_TYPE_REACTION_LOCAL_SURFACE_SPRING = "REACTIONSURFACESPRING"` | `"REACTIONLSURFACESPRING"` |
| npm | `tables.reaction.localSurfaceSpring` | same name, corrected value |
| contract | `contracts/tables/post-reaction.yaml`, `provenance: manual` | `provenance: live_corrected` |

The manual states this string three times and one of the three disagrees: the
Specifications table and the JSON Schema enum drop the L, the section's own
request example keeps it. The contract took the majority and both SDKs shipped
it, so **every caller of that one table type got an error instead of a table**,
in both languages, for as long as the constant has existed.

If you call it, your calls start working. If you never did, nothing about this
release reaches you.

## Why it was wrong, and why that is the part worth keeping

Both of `/post/TABLE`'s spelling contradictions had been declared by majority,
and both contracts said so honestly — a `manualDefects` entry carrying
`resolved: false` and, in as many words, *nobody has asked the server*. On
2026-09-04 both were asked, on Gen NX 2026 v2.1 and Civil NX 2026 v2.2, both
build 09/02/2026, by sending each spelling against the same document:

| value sent | where the manual states it | server |
| --- | --- | --- |
| `BEAMFORCESTP` | Specifications table + request example | recognised |
| `BEAMFORCESIP` | JSON Schema enum | refused |
| `REACTIONSURFACESPRING` | Specifications table + JSON Schema enum | **refused** |
| `REACTIONLSURFACESPRING` | request example alone | **recognised** |

The probe reads a distinction this repo already relies on elsewhere: `[empty]
Cannot generate table data as there is no analysis result` is a `TABLE_TYPE` the
product knows and cannot fill, while `there was an error creating utbl` is one
it does not know. Stable across both products and both pairs.

**The identical reasoning was right once and wrong once.** That is the finding.
A wire value is not a majority opinion — three documents agreeing is three
transcriptions of one source, so a 2-1 split carries no information at all about
which way the server goes. `BEAMFORCESTP`'s contract entry now takes
`provenance: live_verified`, because it is confirmed rather than merely
outvoted.

`tests/test_contracts.py::test_a_table_type_contradiction_is_settled_live_or_left_open`
replaces a test that had asserted both contradictions were still open. That was
never the rule worth enforcing; the rule is that a `describes: table_type`
defect may be marked resolved **only** on evidence of a live check. Every other
kind — a column the docs omit, a field a revision dropped — is still settled by
reading the source, and an unresolved defect of any kind must still say what is
unknown. `validate_contracts.py` now reports **0 unresolved manual
contradictions**, down from 2.

The upstream typos are unfixed and remain a vendor-report item. Recorded as
MD-49.

## Also in this release, none of it in the wheel

- **Every non-`/TEMP` crash path was re-checked on build 09/02/2026, and none
  reproduces.** Eight Design Forces `TABLE_TYPE`s, the three
  `/DESIGN/RC/KDS-41-20-2022/TABLE` variants, `/ope/EDMP`, `/ope/USLC`,
  `PUT /db/THNL`, and a raw `/db/NMAS` with `rmX`/`rmY`/`rmZ` omitted, on both
  products. Every risky call was followed by a real `GET /db/NODE` rather than
  `verify_connection()`, which answers `"connected"` through the relay while a
  modal dialog holds the session and therefore cannot tell a live session from
  a blocked one.

  **Nothing is cleared.** The design-forces docstrings — which do ship — record
  the independent second blank-document pass they had asked for, and say in the
  same breath that a populated, analysed, designed model was not exercised. The
  `/db/NMAS` mitigation stays despite a second clean raw call: an uninitialized
  read is exactly the defect that hides when the memory happens to be zero, and
  these were near-empty scratch documents.

- **`/db/STRPSSM` moved read → write.** Its fixture had been failing `Wrong
  Field` since 2026-08-16 under a recorded guess that it needed a genuine PSC/RC
  section rather than the seed's plain rectangular one. It needed `Y` and `Z`:
  the manual's `PY`/`PZ` are `/info`'s *descriptions*, taken for the keys
  (MD-38). 172 → 173 write, 227 → 226 read; confirmed live cases 143 → 144.

- **The `/info`-to-contract sweep runs in CI.** `scripts/info_baseline.py
  --against-contracts --check` holds a per-endpoint ceiling: a count going down
  passes, a new or growing difference fails. Per endpoint deliberately — one
  total would let a contract lose a property while another gains one, and the
  value of that sweep is in the small numbers. A count of one or two is what a
  missing table row looks like; `/db/SECT`'s 995 is the section-property tree
  and means nothing.

- **npm live evidence 23 → 32 `/db` endpoints**, both products, through the
  built package rather than raw HTTP. It also exposed a gap worth naming:
  `schema/live-cases.json` emits each case's own setup but not the common base
  model Python's harness builds first, so the npm harness cannot resolve
  preconditions for thirteen confirmed cases and prints `REGRESS` for them.
  That is a hole in that file's claim to be the language-neutral source both
  harnesses read — not a package regression, and it is not recorded as one.

## Validation

- Python: 999 tests, ruff and mypy clean.
- npm: 60 tests, typecheck, generation and packed-artifact checks clean.
- Contracts: schema, SDK parity, field parity, manual-drift and the new
  `/info`-to-contract check all pass.
