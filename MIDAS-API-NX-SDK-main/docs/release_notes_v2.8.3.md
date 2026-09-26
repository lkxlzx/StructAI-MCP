# midas-nx 2.8.3

A shared PyPI/npm version release. **One npm type narrows, and that is the only
change in either package.**

| surface | what actually changed |
| --- | --- |
| Python | nothing — `src/midas_nx/` is identical to 2.8.2, so PyPI republishes the same code under the aligned number |
| npm | `SteelDesignCodeSelectionPayload.DGNCODE` is now required and typed as the literal `"KDS 41 30 : 2022"` |

## Changed on npm — `SteelDesignCodeSelectionPayload` narrows

> **Breaking for this one type, despite the patch number.** Code that omitted
> `DGNCODE`, or passed any other string, no longer typechecks. Nothing changes
> at runtime: the request an SDK sends is the same.

```diff
 export interface SteelDesignCodeSelectionPayload {
-  DGNCODE?: string;
+  DGNCODE: "KDS 41 30 : 2022";
 }
```

`DESIGN/STEEL/DSTL` (`steelDesignCodeSelection`, added in 2.8.2) now has a
contract, so its payload type is generated from the manual's field table
instead of the Python fallback. The fallback types every member as an optional
`string`, so it said less than the manual does. The manual lists exactly one
design code and marks the field required. The new type matches
`RcDesignCodeSelectionPayload`, its RC counterpart. No exported name was added,
removed or renamed; npm exports the same 765 type names as in 2.8.2.

The value has now been sent to a product. On Build 09/15/2026 the endpoint
behaved differently on the two products:

- **Gen NX** accepted `{"DGNCODE": "KDS 41 30 : 2022"}` and returned the
  stored record.
- **Civil NX** refused the same request with
  `[Error] Errors detected in Steel Design Control Data.` A Civil model
  appears to need something else first, and what that is has not been
  established.

## Also in this release, none of it in either package

- **Building the npm package no longer needs a working Python install.** The
  generator used to import `midas_nx` to list the resource classes; it now
  reads the same facts from the source files. Before the import was removed,
  both methods gave the same answer for all 305 resources. A test now fails if
  the import comes back. The Python source tree is still needed to generate
  the package.
- **Every npm function export is now named by a contract.** Contracts can name
  the npm export for each operation of a function endpoint (`/doc/*`, `/ope/*`,
  `/view/*`, the design calls). `/post/PM` and `/post/STEELCODECHECK` were
  contracted, which completes all 70 operations. Contracts went from 381 to
  384 endpoints, and the generated TypeScript for these operations did not
  change.
- **The npm package has now replayed all 177 confirmed live test cases**, on
  every product each case covers, and so has Python, on Gen NX 2026 v2.1 and
  Civil NX 2026 v2.2, Build 09/15/2026. npm live evidence went from 113 to 162
  `/db` endpoints.
  - Five cases could not be replayed before because their setup steps deleted
    or read data. The shared test fixture can now describe those steps.
  - `/db/DYFG` and `/db/DYNF` had looked like a regression. They were not: they
    had been run without the test case that sets the moving-load code to
    Eurocode first.
- **Live coverage is 201 write / 199 read of 400 endpoints**, because
  `DESIGN/STEEL/DSTL` now has write evidence on Gen.

## Validation

- Python: 1081 tests; ruff and mypy report no issues.
- npm: 83 tests; typecheck, generation and packed-artifact checks pass.
- Contracts: schema, SDK parity, field parity, manual drift, the
  `/info`-to-contract sweep and the npm replay-evidence check all pass.
