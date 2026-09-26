# midas-nx 2.9.2

A shared PyPI/npm version release. **npm's generated types now come entirely
from the contracts, and the supplementary manual tables every contract used
to declare unmerged are merged. Nothing changes at runtime, and Python is
unchanged.**

| surface | what actually changed |
| --- | --- |
| Python | nothing. `src/midas_nx/` is identical to 2.9.1; PyPI republishes it under the aligned number |
| npm | `types.ts` only. 14 type exports are removed and none is added or renamed (765 → 751); 202 members become required across 74 types, 105 are added across 11 types, and 11 are removed across 3 types. The generated JavaScript is unchanged |

## Breaking at the type level, in a patch release

The version number is a patch bump by the author's choice, to keep the two
registries aligned. **Read it as breaking for TypeScript users**: code that
imports one of the 14 removed names, builds one of the changed objects without
a member the contract now requires, or sets one of the 11 removed members
stops compiling. No request an SDK sends changes.

Counts are taken against `js-v2.9.1`'s declarations. A member is a named
type's own property, inherited ones included.

## Removed on npm - 14 type exports nothing in the package used

Each was exported while no operation, resource or other generated type
referenced it: wherever the object is actually sent, the payload or argument
that carries it is generated from its contract and declares the shape inline.
Several did not match what the API takes. If you imported one, use the member
type of the payload that carries it, for example
`DbPropertiesSectionTypes.SectionPayload["SECT_BEFORE"]`. The full list, by
namespace, is in the
[npm changelog](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/packages/typescript/CHANGELOG.md).
The Python TypedDicts of the same names stay.

## Changed on npm - the supplementary tables are merged

Until this release a contract whose manual section had tables the extractor
could not place declared them `unmergedTables`, and its npm payload stayed on
the Python fallback, where every member is optional. Those tables are all
merged now, several after a live measurement - except `/db/TDME`'s two
iGen-only code tables, which review marked excluded because this API refuses
their codes:

- **`/db/ELEM`** is a union over `TYPE` and `STYPE`, one branch per element
  table, with `MATL`, `SECT` and `NODE` required.
- **`/db/MVHL`** is a union over `MVLD_CODE`. The country object (`VEH_CA`,
  `VEH_AU`, `VEH_ZA`, `VEH_CN`, `VEH_PL`, `VEH_KSCE_LSD15`) follows the
  record's `MVLD_CODE`, not the `STANDARD_CODE` the manual's headings name -
  measured on Civil NX, where the Australia heading's `"AUSTRALIA"` is refused
  and its example's `"ROAD TRAFFIC"` stored.
- **`/db/MVLD`**, **`/db/MVLDpl`**, **`/db/SPFC`**, **`/db/THIS`**,
  **`/db/SPLC`**, **`/db/STCT`**, **`/db/EPMT`**, **`/db/THIK`**,
  **`/db/TDME`**, **`/db/CSCS`** and **`/db/SDIS`** are generated from their
  contracts, each member documented with the mode or code it applies to.
- **`setResultGraphic`**'s argument and its 21 nested types come from the
  contract, with the section's ten `TYPE_OF_DISPLAY` tables merged.

## Changed on npm - the arguments that were held on Python

- **`divideElements`**: the Y and Z members of the Unequal and Parametric
  options apply only to the element types that divide along them - measured
  on both products: a Frame divides with X alone, a Planar element refuses X
  alone.
- **The load-combination unions**: an operation contract can now say which
  union part its field list builds, so `LoadCombinationGeneralKdsArgument`,
  `LoadCombinationSrcKdsArgument` and the shared
  `LoadCombinationAikSrc2kArgument` are generated.
  `LoadCombinationSrcKdsArgument` no longer extends a base interface.
- **`SrcMemberCheckTableArgument`** requires `TABLE_TYPE`.

## Fixed on npm

- **`/db/FIBR`**: `R`, `G` and `B` were declared at the record root beside
  `FIMP_COLOR`; they are inside each `FIMP_COLOR` element, as the manual, its
  example and `/info` all place them.
- **`/db/MCON`**: `LinearConstraintItem` takes the shape the manual gives it.

## Not shipped, recorded in the repository

- `/db/MVHL`, `/ope/DIVIDEELEM` and the other probes run for this release are
  in `docs/live_verification_notes.md`; the manual defects they found are
  MD-57 to MD-62 in `docs/manual_defects_register.md`.
- The contract extractor reads a table that repeats its parent row, a labelled
  child number such as `(1) R/G/B`, and a value set split across a section's
  tables.
