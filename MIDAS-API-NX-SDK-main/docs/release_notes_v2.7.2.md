# midas-nx 2.7.2

A shared PyPI/npm version release. Both packages change in this release.

This version combines the 2026-08-31 manual-contract migration work with
scratch-model checks against MIDAS Gen NX 2026 v2.1 and MIDAS Civil NX 2026
v2.2, both build 08/26/2026.

## Read this first

The TypeScript declarations are more specific for the newly contracted
resources. Code that previously passed an incomplete or incorrectly shaped
payload can now fail TypeScript checking, even though the request runtime has
not added general runtime schema validation. This is a correction towards the
published manual, not a change to the server protocol.

## Python / PyPI

### Changed

- Moving-load payload documentation now includes the verified Australia, China
  and Poland nested shapes, and analysis-control documentation includes the
  `BRIDGE2`, `bSDLE` and `vSDLE` members found in the current manual/live
  review.
- Inelastic-hinge payload documentation now distinguishes the Gen-only wall
  members from the common beam members, including the manual's documented
  `WAreaSize` type/example inconsistency.
- Document save/export guidance now records the verified NX-native extensions
  and cautions that an MAPI account name is not necessarily the Windows profile
  directory.

## JavaScript / TypeScript / npm

### Changed

- Generated payload declarations now use **30 additional reviewed endpoint
  contracts** (279 → 309 since 2.7.1). Their nested objects, documented
  requirements and enum values reach TypeScript callers without the Python
  package as a source: 251 of the 304 npm resources now have their facts owned
  by a contract, leaving 53 on the reviewed Python fallback.
- Generated resource labels retain the manual's punctuation and naming,
  including the en dash used by several analysis-control and seismic-device
  labels.
- The package includes safe live CRUD and analysis harnesses for maintainers;
  they create verified checkpoints before dependent scratch-model cases.

## Repository and verification

- Contract extraction now preserves a manual default that is not a literal
  wire value as documentation rather than guessing a JSON value. It also
  preserves genuinely unstated type and requirement columns instead of
  inventing `string` or optional fields.
- Live evidence, manual evidence and known manual contradictions remain
  separate records. The migration added reviewed contracts while leaving
  undecidable conditional variants unpromoted.
- `docs/manual_defects_register.md` replaces a dated one-off report. It is a
  running list of places the documentation and the product disagree, each with
  the side that owns the correction — the manual repository's own transcription
  or MIDASIT's official article. It collects only; nothing has been sent
  anywhere.
- The four model file extensions are recorded correctly for the first time:
  pre-NX `.mgb`/`.mcb`, NX `.mgbx`/`.mcbz`. This repository had Civil's wrong
  twice, partly because Civil accepts `.mcbx` for `SAVEAS` without complaint.

## Validation

- Python: 876 tests, ruff and mypy clean.
- npm: 55 tests, typecheck, generation and packed-artifact dry run clean.
- Contracts: 309 endpoints, 2,933 fields, schema, SDK parity and manual-drift
  checks pass.

