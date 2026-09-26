# midas-nx 2.7.0

This is a shared PyPI/npm version release. The Python package is republished
without a runtime API change so both registries remain on the same version.

## JavaScript / TypeScript / npm

### Added

- `/db/BODF` (Self-Weight) now uses a reviewed language-neutral contract for
  its generated npm payload.

### Changed

- `resources.db.staticLoads.selfWeight` now requires `LCNAME` and types `FV`
  as exactly three numbers, matching the documented self-weight factors for the
  X, Y, and Z directions.
- Fixed-length arrays in reviewed endpoint contracts generate TypeScript tuples
  instead of unrestricted arrays.

### Compatibility

Existing TypeScript calls that omit `LCNAME` or pass a non-three-value `FV`
array to `/db/BODF` must be updated. This is a type-level correction to the
documented wire shape; it does not change the Python runtime API.

## Validation

- Python: 773 tests, ruff, and mypy passed.
- Contracts: schema/parity validation and manual-drift validation passed.
- npm: generation, typecheck, tests, build, and packed-artifact inspection
  passed.

## Install

```bash
pip install midas-nx==2.7.0
npm install midas-nx@2.7.0
```
