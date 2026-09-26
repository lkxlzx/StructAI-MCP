# midas-nx 2.7.3

A shared PyPI/npm version release. **The npm package changes; the Python one
does not.**

`src/midas_nx/` has not changed since 2.7.2 — an identical wheel goes out under
a new number, because the two registries move together. The reason for this
release is on the npm side, and it breaks a type. 2.6.0 is the earlier worked
example of the same situation.

## Read this first — npm breaking change

`FloorLoadPayload` (`/db/FBLA`) was a flat interface with every member
optional. It is now a **discriminated union**, and three members are required:

```ts
// before
interface FloorLoadPayload {
  FLOOR_LOAD_TYPE_NAME?: string;
  FLOOR_DIST_TYPE?: number;
  NODES?: Array<number>;
  LOAD_ANGLE?: number;
  OPT_ALLOW_POLYGON_TYPE_UNIT_AREA?: boolean;
  // ...every branch's fields at once
}

// after
type FloorLoadPayload = {
  FLOOR_LOAD_TYPE_NAME: string;   // now required
  FLOOR_DIST_TYPE: number;        // now required
  NODES: Array<number>;           // now required
  // ...
} & (
  { FLOOR_DIST_TYPE: 1; LOAD_ANGLE?: number; /* shared fields */ } |
  { FLOOR_DIST_TYPE: 2; OPT_ALLOW_POLYGON_TYPE_UNIT_AREA?: boolean; /* shared fields */ }
);
```

Three things this affects:

- Code that omitted `FLOOR_LOAD_TYPE_NAME`, `FLOOR_DIST_TYPE` or `NODES` now
  fails typechecking. The manual marks all three Required; the old declaration
  was wrong about that.
- Code that `extends FloorLoadPayload` or relies on declaration merging breaks:
  it is a `type` now, not an `interface`.
- Code that set `LOAD_ANGLE` together with `OPT_ALLOW_POLYGON_TYPE_UNIT_AREA`
  no longer typechecks — the manual documents them under different
  `FLOOR_DIST_TYPE` values, and the old flat interface offered every branch's
  fields at once regardless.

No runtime behaviour changed, and no general runtime payload validation was
added. This is the declaration moving towards the published manual.

## Contracts

The last two of the four schema decisions land here, and neither introduces a
construct the schema had no precedent for.

**D3 — conditional variants.** `variant.when` becomes an array of
`{path, equals | in}` conditions combined with AND: exactly the shape a field's
`appliesWhen` already had. One change covers a nested discriminator
(`STR.SPEC_CODE`), a two-level selector, and a table the manual gives several
values for. `in` carries two or more literals, is mutually exclusive with
`equals`, and every value in it is written in the manual rather than inferred
from an enum. The 21 existing variants moved to the array form.

Where a manual states one table for several values *and* separate tables for
each — `/db/FBLA`'s `= 1`, `= 2`, and `= 1 or 2` — the third is the shared
table, not a third branch. The contract transcribes the overlap and generation
folds those fields into each branch it covers, so no two union members match the
same discriminator.

Still deliberately unresolved: two tables claiming the *same single* value.
`/db/NLNK` splits `REF_SYSTEM=1` into Angle/3Points/Vector and `/db/HSFC`
splits `TYPE="FUNC"` by whether concrete data is used. Both second selectors are
real; neither is written down as a wire field, so those stay unmerged.

**D4 — arguments that are not a field list.** `request.itemSchema` gains
`scalar` (with a required `scalarType`) and `empty`. Nine `/doc/*` sections
carry a JSON Schema and no Specifications table, and that was never a parsing
gap: `/doc/OPEN` and `/doc/SAVEAS` take a bare path string; `/doc/NEW`,
`/doc/CLOSE` and `/doc/SAVE` take `{}`. An empty `fields` list is the correct
transcription, so promotion and the manual-drift check stop reading it as a
failure when the request declares it.

**Promoted contracts 309 → 319** — `/db/FBLA` and all nine `/doc/*` endpoints.
319 endpoints, 3,010 fields, 65 drafts still awaiting review. 252 of the 304 npm
resources take their facts from a contract, leaving 52 on the reviewed Python
fallback.

With D1 and D2 in 2.7.2, all four contract-schema decisions are now closed.

## Validation

- Python: 877 tests, ruff and mypy clean.
- npm: 55 tests, typecheck, generation and packed-artifact checks clean.
- Contracts: schema, SDK parity and manual-drift checks pass.
