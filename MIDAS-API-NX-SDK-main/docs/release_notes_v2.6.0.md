# midas-nx 2.6.0

The first release under **one shared version number** across both registries. PyPI
and npm had drifted to 2.3.5 and 2.4.0, which is confusing for a single package
name, so from here they move together. `CLAUDE.md`'s Releasing section was
reversed to match — it previously required the two streams to stay independent.

One number cannot be right for both surfaces at once, so here is what each
actually got.

## Python / PyPI

**Nothing in `src/midas_nx/` changed.** 2.6.0 is byte-for-byte the same package
as 2.3.5 apart from its version metadata, republished under the aligned number.
There is no Python API change to look for, and nothing to migrate.

## JavaScript / TypeScript / npm

### Breaking, despite the minor bump

`DbResourceMetadata.pythonModule`, and `OperationMetadata.pythonModule` /
`pythonFunction`, are gone. **If your code reads any of those it will stop
compiling on this upgrade**, even though a minor bump does not normally warn
you. The number was chosen to keep the registries aligned; this note is the
warning the number does not give.

The npm package was shipping the PyPI package's module paths
(`"midas_nx.db.static_loads"`) to JavaScript users — nothing a caller could act
on, and a standing signal that one language surface was generated from the
other. `DbResourceMetadata` gains an optional `manualChapter` instead, naming
the official manual chapter that documents the endpoint.

### Added

- `tableTypes` — every `TABLE_TYPE` value from the new table contracts, as a
  named constant. The npm package previously named only whichever value a table
  wrapper defaulted to, so variants like `REACTIONL` and
  `REACTIONSURFACESPRING` were reachable only by someone who already knew they
  existed. Python has always named them.

### Changed

- Payload types for 38 endpoints are generated from `contracts/` rather than
  from the Python `TypedDict`s. They are more accurate, not merely differently
  sourced: the `TypedDict`s are all `total=False`, so every field they produced
  was optional regardless of what the manual said. `/db/RIGD`'s `DOF` and
  `S_NODE` are now correctly required, and its `ITEMS` array carries its real
  element shape instead of four sibling keys no payload has.

## Repository — the language-neutral contracts

Neither registry ships `contracts/`, but it is what the two releases above came
out of, and it is where the endpoint's shape and safety rules now live.

- **39 endpoint contracts and 3 result-table contracts.** `/post/TABLE` is
  modelled as two layers, because 89 tables share one route: the request shape
  is contracted once, and each table adds only its `TABLE_TYPE` values, response
  columns, and the shared fields it ignores.
- **266 fields carry an omission-safety answer**: 59 proven safe from payloads a
  running product actually accepted without them, 5 proven unsafe, and 202
  honestly `unverified`. The manual saying "Optional" is not evidence — that is
  what `documentedOptional` already records, and `/db/NMAS` is the endpoint
  where believing it ends the session.
- **Two contradictions inside the official manual are recorded unresolved**
  rather than settled by guess: `REACTIONSURFACESPRING` versus
  `REACTIONLSURFACESPRING`, and `BEAMFORCESTP` versus `BEAMFORCESIP`. Each
  contract declares the majority spelling and says outright that nobody has
  asked the server which it accepts.

CI now validates the contracts, checks them against the official manual for
drift, and checks **both** SDKs against them. A disagreement is reported as an
SDK defect, never as a reason to edit the contract. It has already caught: the
npm package able to crash a live NX session on `/db/NMAS`; `/db/GRUP` claiming a
DELETE it does not serve; `/db/RIGD` and `/db/OFFS` flattening an array; and
seven endpoints wrongly marked Civil-only.

## Install

```bash
pip install midas-nx==2.6.0
npm install midas-nx@2.6.0
```
