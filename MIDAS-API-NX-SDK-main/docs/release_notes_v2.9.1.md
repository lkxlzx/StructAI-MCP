# midas-nx 2.9.1

A shared PyPI/npm version release. **npm's payload and operation-argument
types now follow the contracts all the way down, which makes 551 members
required across 216 types. Nothing changes at runtime, and Python is
unchanged.**

| surface | what actually changed |
| --- | --- |
| Python | nothing. `src/midas_nx/` is identical to 2.9.0; PyPI republishes it under the aligned number |
| npm | `types.ts` only. No exported name is added, removed or renamed (765 before and after) and no member is removed; 551 members become required across 216 types, and 39 members are added across 11 types. The generated JavaScript is unchanged |

## Breaking at the type level, in a patch release

The version number is a patch bump by the author's choice, to keep the two
registries aligned. **Read it as breaking for the types listed below**: code
that builds one of those objects without a member the contract requires stops
compiling. No request an SDK sends changes, and code that already sent those
members keeps compiling.

The counts are taken against `js-v2.9.0`'s declarations. A member is a named
type's own property, inherited ones included, so a member that moved from a
base interface into the type itself is neither added nor removed.

## Changed on npm - nested types come from the contracts

Every npm payload built from a contract already inlined its nested objects in
the contract's shape. The **named** interfaces for those same objects were
still generated from the Python package's TypedDicts, where every member is
optional, so one object was published twice with two shapes:

```diff
-  export interface BeamEndOffsetItem extends DbBaseTypes.ItemGroupFields {
-    TYPE?: string;
+  export interface BeamEndOffsetItem {
+    /** Serial Number */
+    ID?: number;
+    /** Load Group Name */
+    GROUP_NAME?: string;
+    /** Reference CS · "GLOBAL" / "ELEMENT" */
+    TYPE: string;
```

`BeamEndOffsetPayload.ITEMS[].TYPE` was already required; now the item type
agrees with it. 228 nested types moved:

- **415 members become required** across 156 types. Any value that satisfied
  the containing payload type already satisfied these.
- **37 members are added** across 10 types, where the manual documents a field
  the TypedDict lacked.
- **29 types no longer `extends` a shared base** such as
  `DbBaseTypes.ItemGroupFields`; they declare the same members themselves.
- **4 become `type` aliases instead of `interface`s**, because the contract
  branches inside them: `LinearConstraintItem`, `PressureLoadItem`,
  `RcBeamRebarItem` and `RcBraceRebarItem`. A type alias of a union cannot be
  `extends`-ed or `implements`-ed.

## Changed on npm - operation arguments come from the contracts

The argument types of `operations.*` (`/ope`, `/view`, and the design-code
`*-ANAL`, `*-TABLE` and `*-REPORT` calls) are now generated from their
operation contracts: 44 argument types and 44 objects nested in them.

- **136 members become required** across 60 types, each checked against its
  manual row: the report calls' `REPORT_TYPE`/`EXPORT_PATH`/`OUTPUT_NAME`, the
  table calls' `TABLE_TYPE`, `/ope/AUTOMESH`'s settings objects, and so on.
- **Members the manual requires in only one branch stay optional**, with the
  condition in their JSDoc. `{ ACTIVE_MODE: "All" }` still type-checks, because
  `/view/ACTIVE`'s `N_LIST`/`E_LIST` apply only to mode `"Active"`:

  ```ts
  export interface ActiveArgument {
    ACTIVE_MODE: string;
    /** 노드 번호 목록 Applies when ACTIVE_MODE = "Active". */
    N_LIST?: Array<number>;
  ```

  The same holds for `/view/CAPTURE`'s `FIGURE_NAME` and for `/ope/LINEBMLD`'s
  per-`TYPE` load values.
- **2 members are added**: `PRI_SORT_WID` and `EXPORT_PATH` on
  `RcWallDesignTableArgument`.
- **`LoadCombinationSteelArgument` declares its members itself** instead of
  extending `_LoadCombinationSteelSrcKdsArgument`, and its `OPTION` and
  `DGNCODE` become required, as the manual states.
- **Left as they were, on purpose:** `DivideElementsArgument`, whose manual
  marks every axis of a division Required without saying which axes a frame
  uses, so the type would refuse a valid frame division;
  `SrcMemberCheckTableArgument`, whose two manual sections disagree; the two
  load-combination union arguments; and `ResultGraphicArgument`.

## Fixed on npm - eight payloads regain nested members

The tool that drafts contracts from the manual dropped a nested row numbered
`(1)`, `(2)` whenever a field of the same name appeared earlier in the table.
27 documented members are restored across eight payload types, among them
`InitialForceControlDataPayload`'s `COMB_LIST[].LCNAME` (`/db/EFCT`) and
`ConstructionStagePayload`'s `DACT_ELEM[].GRUP_NAME` (`/db/STAG`), both
required and both declared by the product's own `/info` schema on Civil NX and
Gen NX. The full list is in the
[npm changelog](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/packages/typescript/CHANGELOG.md).

## Not in either package

Listed so the release is not mistaken for the sum of the work since 2.9.0:

- Live evidence now has one home, `contracts/verification/ledger.yaml`, with
  one meaning for a `read` or `write` level.
- Every harness that calls `/doc/NEW` asks for its save directory the same way
  and refuses to start without one.
- The counts that `PLAN.md` and `CLAUDE.md` state about the repository are
  re-derived in CI, and so is how much of npm generation still reads the
  Python source tree: 478 types when that was first measured, 162 now.
- A product finding is settled: a `/doc/SAVEAS` into a folder the NX host
  cannot write to answers Civil NX exactly as a successful save does and
  writes nothing, while on Gen NX it raises a dialog and the call never
  answers. Confirm a save with `/doc/OPEN` and read its message.
