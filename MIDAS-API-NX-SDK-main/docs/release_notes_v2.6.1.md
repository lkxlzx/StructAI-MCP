# midas-nx 2.6.1

This is a shared PyPI/npm version release. The Python package is republished
without a runtime API change so both registries remain on the same version.

## JavaScript / TypeScript / npm

### Fixed

- Every generated operation now carries the reviewed Gen NX/Civil NX product
  availability from `docs/coverage.json`.
- A Civil client now rejects Gen-only Story operations such as
  `/ope/STORY_PARAM` and `/ope/STORY_IRR_PARAM` locally with
  `ProductMismatchError`, rather than making a request that Civil NX rejects
  with HTTP 404.
- The operation wrappers report that mismatch as an async Promise rejection,
  matching their public TypeScript signature.

## Validation

- Real Civil NX: 282 supported DB GET resources answered successfully.
- Real Civil NX: npm SDK created and analyzed a minimal cantilever model, then
  read reaction, displacement, and beam-force tables successfully.
- The saved validation model was reopened and its model data and reaction table
  were read again.

## Install

```bash
pip install midas-nx==2.6.1
npm install midas-nx@2.6.1
```
