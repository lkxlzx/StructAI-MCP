# midas-nx 2.7.1

A shared PyPI/npm version release. Both packages change this time.

The sibling manual repository was revised three times on 2026-08-30 — a new
endpoint section, a chapter-wide label unification, and a set of naming
corrections — and this release carries all of it into both surfaces. Two
findings came out of live Gen NX and Civil NX sessions rather than the
documentation.

## Read this first

Two changes can affect working code even though this is a patch release.

- **`/ope/GSBG` now raises on contradictory `BATCH` payloads.** Calling
  `generate_bridge_girder_diagram()` with `BATCH=True` together with
  `BRDG_GROUP`, `COMPONENTS`, `COMBINED_COMP` or `7TH_DOF_TYPE`, or with
  `BATCH=False` together with `BATCH_LIST`, now raises `MidasRequestError`
  before the request is sent. Such a call previously went to the server as
  written.
- **Four npm payload interfaces are now type aliases.**
  `EigenvalueAnalysisControlPayload`, `EigenvalueAnalysisControlHyperSPayload`,
  `NonlinearAnalysisControlDataPayload` and `SkewPayload` keep their names,
  namespaces and members, but are declared with `type` rather than `interface`.
  Code that assigns or reads them is unaffected; code that `extends` one or
  relies on declaration merging is not.

## Python / PyPI

### Fixed

- `/db/POLC-M1` serves `POST` again. The manual chapter states GET/PUT/DELETE
  and dismisses the official article's POST row as an untrimmed template; a
  live call on Civil NX 2026 v2.2 created a Pushover Load Case that read back
  on the following GET. The chapter's correction is the thing that was wrong.
- 27 resource labels now match the manual's English name. Eight had become
  Korean when the manual labelled its design chapters that way; the rest were
  SDK paraphrases — `Modify Beam Rebar` is `Modify Beam Rebar Data`,
  `Effective Length Factor` is `Effective Length Factor (K)`.
- Eleven docstrings in `db/project.py` cited the wrong manual section number.
  Inserting `/db/STYP-M1` at chapter 02's fourth position moved every section
  below it down one, so a reader following `#4 — /db/GRUP` landed on a
  different endpoint's table.

### Added

- `/ope/GSBG` rejects the two contradictory `BATCH` shapes described above.
- `StructureTypeHyperS` documents what a live session established: it is the
  same model record as `/db/STYP`, writing either changes the other, and
  `STYPE` selects the model's active degrees of freedom rather than being a
  display setting. `DELETE` is refused whatever the official article declares.
- `StructureTypePayload.bROTRIGID` records that Gen NX returns the field and
  Civil NX never does, though `/info/db/STYP` lists it identically on both.
  Read it with a default rather than by subscript.

## JavaScript / TypeScript / npm

### Added

- Result-table wrappers for the analysis, story and design-force tables, from
  reviewed table contracts.

### Changed

- Payload types for the newly contracted endpoints are generated from
  `contracts/` instead of from Python `TypedDict`s.
- Resource metadata follows the manual's corrected labels and `/db/POLC-M1`'s
  restored method set.
- The four payload interfaces noted at the top are now type aliases.

## Repository

Not shipped in either package, but it is why the above was found.

- `scripts/extract_contracts.py --check` now compares the endpoint label, the
  method set and the section heading against the manual. Each comparison found
  real drift on its first run: 114 stale labels, one wrong method set, and 103
  section strings left behind by the manual's renumbering. Every one had been
  invisible because both SDKs agreed with each other, and no gate asked whether
  they still agreed with the source.
- The extractor no longer reads a chapter's closing comparison table, or a
  normalisation callout quoting the form it rejects, as a method declaration.
- 31 fields across four contracts claimed `safeToOmit: true` on the strength of
  a live payload that was never sent — `live_crud_check.py` writes an empty
  create payload for records the product creates itself, and every field is
  absent from an empty payload. They are back to `unverified`.

## Validation

- Python: 845 tests, ruff and mypy clean.
- npm: 55 tests across 11 files, typecheck clean, no generation drift.
- Contracts: schema, parity against both SDKs, and manual-drift checks pass.
- Live: Gen NX 2026 and Civil NX 2026 v2.2, on scratch documents only.
