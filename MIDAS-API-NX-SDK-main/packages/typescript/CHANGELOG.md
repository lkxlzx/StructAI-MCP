# Changelog

This file records changes to the JavaScript/TypeScript package published on
npm as `midas-nx`. Python package history is tracked separately in the
repository's `docs/release_notes_v*.md` files and `py-v*` GitHub Releases.

## Unreleased

### Documentation

- The README's MAPI-key and quickstart links now point at an npm quickstart
  (English, Korean, Traditional Chinese) instead of the Python one, which
  opened with "Step 1: Install Python".
- `examples/javascript/` gains the load-combination and KDS wind-load
  examples, so it matches `examples/python/` at four.

## 2.9.3 - 2026-09-23

> **Nothing executable changed.** `dist/` is identical to 2.9.2 - no
> behaviour, no types, no API surface. This release publishes the package
> metadata and the README, which is the page npmjs.com shows.

### Documentation

- README states that the package has no runtime dependencies and needs no
  Python installation. No code change.
- `author` is now `Dennis` with a LinkedIn URL, and the README points there
  for questions and feedback. GitHub Issues stays the place for SDK bugs.
- The README now says what you need before installing (a running product, a
  MAPI key and where to get one, Node 18), labels its first example
  read-only, links the documentation site, safety guide, quickstart, AI
  context pack and runnable examples, and carries the project-status
  paragraph in Korean, Traditional Chinese and Simplified Chinese. The
  maintainer-only release checklist link is gone.

## 2.9.2 - 2026-09-22

> **Breaking at the type level; nothing changes at runtime.** Measured against
> `js-v2.9.1`'s declarations: **14 type exports are removed** (listed below)
> and none is added or renamed (765 → 751); **202 members become required
> across 74 types**; 105 members are added across 11 types; and 11 members are
> removed across 3 types - `/db/MCON`'s `LinearConstraintItem` loses four it
> should never have had, `/db/TDME` four that only a code this API refuses
> could use, and `/db/FIBR`'s payload the `R`, `G` and `B` it declared at the
> wrong level. Four payloads become type aliases over a union. A member is a
> named type's own property, inherited ones included.

### Removed - 14 type exports nothing in the package used

These names were exported but referenced by no operation, resource or other
type in the package: wherever the object is actually sent, the payload or
argument carrying it is generated from its contract and declares the shape
inline. Several did not match what the API takes. If you imported one,
use the member type of the payload that carries it instead, for example
`DbPropertiesSectionTypes.SectionPayload["SECT_BEFORE"]`.

- `DbBaseTypes`: `ItemGroupFields`, `InitialLoadCaseItem`, `OptUseToleranceValue`
- `DbConstructionStageTypes`: `LoadGroupDayItem`
- `DbLoadCombinationsTypes`: `LoadCombinationPayload`
- `DbProjectTypes`: `_ColorPayload`
- `DbPropertiesMaterialTypes`: `InelasticMaterialKentParkParam`
- `DbPropertiesSectionTypes`: `SectBefore`
- `DesignRcKdsRebarTypes`: `ColumnBraceRebarDesignCriteriaItem`
- `DesignRcKdsChecksTypes`: `RcDesignForcesArgument`
- `DesignSrcAiksrc2kTypes`: `SrcDesignForcesArgument`
- `OpeTypes`: `AllowableStressLine`, `_LoadCombinationSteelSrcKdsArgument`
- `PostStoryTypes`: `StorySetAngle`

### Fixed - `/db/FIBR`'s colour members

`FiberDivisionPayload` published `R`, `G` and `B` at the record root and
typed `FIMP_COLOR` as six `JsonObject`s. The manual's row, its Request Example
and `/info` on both products all put the three inside each `FIMP_COLOR`
element, which is where they are now; **the three root members are removed**
- the server does not read colours there. `FiberDivisionColor` is the element
type.

### Changed - `/ope` and design arguments that were held on Python

- `divideElements`: `DivideElementsArgument` and its ten nested types come
  from the contract. `DIVIDE`, its `ELEM_TYPE`, `DIV_METHOD` and `OPTION`, and
  each option's X-axis member (`NUM_X`, `DIST_X`, `RATIO_X`) plus
  `PARALLEL_OPTION` and `BY_NODE_OPTION`'s members become **required**. The Y
  and Z members stay optional and say in JSDoc which `ELEM_TYPE` needs them
  (Y: Planar, Solid; Z: Wall, Solid) - measured on both products 2026-09-22,
  where a Frame divides with X alone and a Planar element refuses X alone.
- `generateLoadCombinationGeneral`'s KDS part,
  `LoadCombinationGeneralKdsArgument`, requires `OPTION`
  (`"ADD" | "REPLACE"`) and `CODE_SELECTION`.
- `generateLoadCombinationSrc`'s KDS part, `LoadCombinationSrcKdsArgument`,
  no longer extends `_LoadCombinationSteelSrcKdsArgument`; it declares the
  same seven members itself, with `OPTION` required as `"ADD" | "REPLACE"`
  and `DGNCODE` as `"KDS 41 SRC : 2022"`. The AIK-SRC2K part both operations
  share, `LoadCombinationAikSrc2kArgument`, requires `OPTION` and narrows
  `DGNCODE` to `"AIK-SRC2K"`; `RS_SCALE_FACTOR` stays optional, as the
  manual's shared table gives it for LCOM-SRC, with JSDoc saying LCOM-GEN
  requires it.
- `SrcMemberCheckTableArgument` requires `TABLE_TYPE`.

### Changed - `setResultGraphic`'s argument is generated from its contract

`ResultGraphicArgument` and its 21 nested types came from Python. The
section's ten `TYPE_OF_DISPLAY` detail tables are merged now, which makes
**6 members required across 5 types**, as the manual marks them:
`CuttingDiagramDisplay.CUTTING_NAME`, `CuttingPlaneDisplay.PLANE_NAME`,
`MirroredDisplay.MIRROR_BY_1`, `MirrorBy`'s `DIRECTION` and `OFFSET`, and
`IsoSurfaceValueMode.VALUE`. `COMPONENTS` and `TYPE_OF_DISPLAY`'s
`UNDEFORMED`, `YIELD_POINT` and `MODE_SHAPE` narrow from
`Record<string, unknown>` to `JsonObject`. Every member keeps its name.

### Changed - `/db/MVLD` is generated from its contract

`MovingLoadCasePayload` and its seven object types came from Python, all
optional. **31 members become required across the eight**: `LCNAME` and
`TYPE`, `DEFAULT`'s `COMB_OPTION` and `SUB_LOAD_DATAS`, and every row of
`SUB_LOAD_DATAS`, `PERMIT_LOAD`, `AUTO_OPTIMIZE`, `OPTIMIZE_ITEMS`, `ASL`
and `ASL.LINE_ITEMS`. `DEFAULT`, `PERMIT_LOAD` and `AUTO_OPTIMIZE` stay
optional, each documented for its `TYPE`. **Added**: `LOAD_MODEL`,
`LOAD_COMB_TYPE` and `FATIGUE` in `MovingLoadCaseDefault`, and `LOAD_MODEL`
and `FATIGUE` in `MovingLoadCaseAutoOptimize` (Australia, and Russia for
`LOAD_COMB_TYPE`). The Korea, Australia and Russia rows are chosen by the
model's `/db/MVCD` code, which no field of the record states, so they stay
optional with their country in JSDoc - as do `SCALE_FACTORS` and
`LANE_FACTOR_TYPE`, which Russia does not carry.

### Changed - `/db/MVHL` is a union over `MVLD_CODE`

`VehiclePayload` was a Python interface with everything optional and only
`VEH_DEFAULT`, `VEH_EUROCODE` and `VEH_KSCE_LSD15`. It is now a **type alias**: the
common members, where `MVLD_CODE`, `VEHICLE_LOAD_NAME` and
`VEHICLE_LOAD_NUM` are **required**, intersected with one branch per country
table - `VEH_KSCE_LSD15` (`MVLD_CODE: 13`), and the **added** `VEH_CA` (8),
`VEH_AU` (14), `VEH_ZA` (16), `VEH_CN` (3) and `VEH_PL` (15) - and a last
member for every other code, which forbids all six. `LOAD_ITEMS2` is added
at the root. `VEH_DEFAULT` stays optional, documented for codes 1, 2 and 6.
`VehicleKsceLsd15Params` requires `LENGTH_LANE` and `POINT_ITEMS`, and
`VehicleKsceLsd15PointItem` and `VehicleLoadItem` require `POINT_LOAD` and
`POINT_DIST`.

The branch key is `MVLD_CODE`, not the `STANDARD_CODE` the section's headings
name. Measured on Civil NX 2026-09-22: every printed country body stored
with its own `MVLD_CODE`, the two user-defined ones with no `STANDARD_CODE`
at all, while Australia's heading value `"AUSTRALIA"` and South Africa's
`"NA"` are refused. Rows the tables group under standard or user-defined
vehicles carry that `VEHICLE_LOAD_NUM` in JSDoc. The Poland body stored
nothing, so the code 15 is the section's and not yet confirmed.

### Changed - `/db/THIS` is generated from its contract

`TimeHistoryLoadCasePayload` held only `COMMON`, and `TimeHistoryLoadCaseCommon`
ten optional members. **47 members are added** across the two: `COMMON`
gains the per-mode rows (`iGEOM`, `iISTEP`, the ORDER and INIT load
options), and the record root gains the Newmark, iteration-control,
increment-control and damping members. Each carries the
`COMMON.iATYPE`/`COMMON.iAMETHOD` mode, and any inner switch, it applies to
in JSDoc. `COMMON` becomes required, as do its `NAME`, `iATYPE`,
`iAMETHOD`, `ENDTIME`, `iOUT` and `INITMETHOD`. `iTHTYPE` is required only for
Modal and Direct Integration: the section's own Static examples omit it, and
Civil NX accepts them (measured 2026-09-22).

### Changed - `/db/SPFC` is generated from its contract

`ResponseSpectrumFunctionPayload` had no design-code members at all. **`STR`,
`OPT` and `VAL` are added**, each with the members the section's code tables
give, every member carrying the `STR.SPEC_CODE` values it applies to in
JSDoc (`VAL.PERIOD`, for one, is required under every tabled code). `NAME`,
`iTYPE`, `SCALE` and `GRAV` become required, as do `aFUNC`'s `PERIOD` and
`VALUE`. The EURO2004 members are declared in `STR` as strings, where `/info`
puts them; the section's own EURO2004 example is refused on both products
(measured 2026-09-22), so no shape for that code is claimed.

### Changed - `/db/MVLDpl` is generated from its contract

`MovingLoadCasePolandPayload` and its five object types came from Python,
all optional. The payload is now a union on the section's two switches -
`AUTO_OPTIMIZE` required with `bAUTO_OPTIMIZE: true`, `PERMIT_LOAD` with
`bPERMIT_LOAD: true` - and `DEFAULT` applies when both are off, which is
how the section's own Optimization example leaves it out. 17 members become
required across 6 types (`LCNAME`, `LOAD_MODEL`, the rows both `LOAD_MODEL`
groups share, and each `OPTIMIZE_ITEMS` and `PERMIT_LOAD` row); rows only
one group states are required only for that `LOAD_MODEL`, in JSDoc. Both
`COMB_OPTION`s narrow to `"COMBINED" | "INDEPENDENT"` and `VEHICLE_TYPE` to
`"VL" | "VC"`.

### Changed - `/db/ELEM` is a union over `TYPE` and `STYPE`

`ElementPayload` was a six-member Python interface with everything optional.
It is now a **type alias**: the common members, where `MATL`, `SECT` and
`NODE` are **required**, intersected with one branch per table the manual
gives - Tension-only Truss/Hook/Cable (`TYPE: "TENSTR"` with `STYPE` 1-3),
Compression-only Truss/Gap (`"COMPTR"`, 1-2), `"WALL"`, `"PLATE"` and
`"PLSTRS"` - and a last member for every other type that forbids the
branch-only keys. 10 members are added: `TENS`, `T_LIMIT`, `T_bLMT`,
`NON_LEN`, `CABLE`, `WALL`, `W_CON`, `W_TYPE`, and the schema-only `C_RAT`
and `LCAXIS`. Using a branch's members now takes its literal `TYPE`, and
its `STYPE` where the branch names one; a record built with `TYPE: string`
has to be narrowed first. `STYPE` stays optional for PLATE and PLSTRS, and
`CABLE`/`NON_LEN` for Cable, although the tables mark them Required: both
products accept records without them (measured 2026-09-22). The Wall members
are tagged Gen NX only - Civil NX refuses the element type.

### Changed - `/db/STCT` is generated from its contract

`ConstructionStageAnalysisControlDataPayload` came from Python because the
contract had left the erection-load table unmerged. It is merged at record
root, where `/info` places it on both products. `FINAL_STAGE` becomes
required, and `vEREC`'s elements now require their `LTYPECC`, `EREC` and
`vLCNAME`, as the table's numbered rows do: the payload spells that element
inline rather than as `ErectionLoadItem`, which `/db/STCT-M1`'s section
documents with all three optional. `vSDLE` stays optional although its row
says Required: both products accept a record without it (Gen NX a POST,
Civil NX a PUT), and the JP-edition feature it belongs to is not measured.

### Changed - `/db/SPLC` is generated from its contract

`ResponseSpectrumLoadCasePayload` listed the main table only; the contract had
left the two damping tables and the two GEN NX-only tables unmerged. All four
are merged now, and **20 members are added**: `DALL` and `aDAMPING` (Modal,
`iMDTYPE: 1`) and `iCOEF`, `bMASSP`, `bSTIFFP`, `MASSC`, `STIFFC`, `iCALC`,
`FP1`, `FP2`, `DR1`, `DR2` (Mass & Stiffness, `iMDTYPE: 2`), each with its
`bDAMP`/`iMDTYPE`/`iCOEF` condition in JSDoc, and the Gen NX-only `bACCECC`
block and `bNDP`/`NDP`. `NAME`, `SCALE`, `PMFT` and `aFUNCNAME` become
required. The manual marks the eccentricity rows and `NDP` Required with no
condition; they are **optional** here, because Gen NX accepts a record with
the switch on and every one of them left out (measured 2026-09-22).

### Changed - `/db/EPMT` is generated from its contract

`PlasticMaterialPayload` typed its six model objects `unknown`, because the
contract had left the tables describing them unmerged: none has a Value Type
column. They are merged now, with the manual's requiredness, defaults, value
sets and conditions and `/info`'s types, which both products declare alike.
`NAME` and `MODEL_TYPE` become required; `TRESCA`, `VMISES`, `MOHRCL`,
`DRUCKER`, `MASONRY` and `CONCDMG` stay optional, each required only for its
own `MODEL_TYPE`, and gain their members - `HARDENING_COEF` required when
`OPT_HARDENING` is `0` and `BACK_STRESS_COEF` when `HARDENING_TYPE` is
`"MIX"` (both left optional in the type, the condition in JSDoc), Masonry's
`BM`/`BED_JOINT`/`HEAD_JOINT`/`GEOM` all required.

### Changed - `/db/THIK` is generated from its contract

`ThicknessPayload` was a Python TypedDict listing only the Value thickness.
The manual's first table is headed `TYPE: "VALUE"` and its second
`STYPE: "DB"`, and both are now read that way: `bINOUT`, `T_IN`, `T_OUT`,
`OFFSET` and `O_VALUE` apply when `TYPE` is `"VALUE"` (`T_OUT` also needs
`bINOUT: true`), and the Stiffened DB members `STYPE`, `RIB_POS` and
`SECTION` are **added**, required when `TYPE` is `"STIFFENED"` (and `STYPE`
is `"DB"`). `NAME` and `TYPE` become required. Everything else stays optional
with its condition in JSDoc - a draft that read the first table as the whole
record would have required `T_IN` and `T_OUT` of every stiffened plate.

### Changed - `/db/TDME` is generated from its contract

`TimeDependentMaterialStrengthPayload` becomes the contract's discriminated
union over `TYPE` and `CODENAME`: 12 members are required in the branch
they belong to. **It loses `TENS_STRN_FACTOR`, `bUSE`, `D` and `iECTYPE`**,
which exist only for the manual's two Japan code tables. Those codes belong
to iGen, a different MIDAS product; every spelling of them answers
`Wrong Field` on Gen NX and Civil NX (measured 2026-09-03, both products), so
no request that uses these four members can succeed. The contract had already
excluded the two tables; the npm type now follows it.

### Changed - `/db/CSCS` is generated from its contract

`CompositeSectionConstructionStagePayload` and `CompositeSectionPartInfo` were
Python TypedDicts because the contract had left the section's second table
unmerged. The chapter says where those rows go - each `vPARTINFO` entry - and
they are merged there. The table has no Required column, so its nine members
(`CY`...`CZJ`, and the three `STIFF_USER` objects with the 21 members the
chapter lists for each) are optional. The payload's own
required rows now reach the type: `SEC`, `ASTAGE`, `TYPE`, `vPARTINFO`, and
each part's `PART` and `MTYPE`.

### Changed - `/db/SDIS` is generated from its contract

`SeismicDeviceIsolatorPayload` and its four object types were Python
TypedDicts, because the contract had left the LRB, NRB and SB tables
unmerged. They are merged now, as the manual's main table places them, and
each object is **required only for its own `SDIS_DEV_TYPE`** (`"LRB"`,
`"NRB"`, `"SLD"`), which is what the rows say; the contract had required all
three at once. 21 members become required across 4 types - the record's
`COMMON`, `SDIS_DEV_TYPE`, `MSS`, `TAU_K`, `TAU_Q`, `KV` and each object's
own required rows - and `LRB`, `NRB`, `SB` stay optional with their condition
in JSDoc.

### Changed - 48 more named types come from the contracts

Named types for objects that sit inside one branch of a payload
(`/db/NLCT`'s `NEWTON_ITEMS`, `/db/EIGV`'s `vRITZ`, the Chinese moving-load
case's sub-load and optimisation items), objects a contract had declared
without members (the RC and steel design-result graphics, the RC wall calls'
`SELECTIONS`, the RC report calls' `DETAIL_POSITIONS`, `/db/SDSP`'s
`VALUES`, the Eurocode moving-load case's `OPTIMIZE_LIST`,
`/db/HHCT-M1`'s `CONVERGENCE.DISP` and `LOAD`), and nine `/view/DISPLAY`
options are now generated from the contracts. The members each gains come from
the manual - where its Parameters table names an object without child rows,
from the same section's JSON Schema - or, for three `OPTIMIZE_LIST` types the
manual leaves unstated, from the product's own `/info` schema.

- **46 members become required** across 17 types, each the requiredness the
  containing payload or argument already published inline.
- **10 members narrow from `string` to the values the manual lists**, such as
  `HaunchPartSelector.INPUT_METHOD` (`"KEYS" | "TO"`, in both the RC and steel
  namespaces) and the steel design-result graphic's `COLOR_TYPE`, `POSITION`
  and `MAXMIN`.
- The same objects inside the payload and argument types, which were
  `JsonObject` wherever a contract declared them without members, now carry
  those members.
- `ConvergenceCriterionCheck.VALUE` and the corresponding
  `HeatOfHydrationAnalysisControlHyperSPayload` members become optional, with
  "Required when OPT_CHECK = true" in their JSDoc, as the manual's row says;
  `/ope/AUTOMESH`'s `INCLUDE_INTERIOR_NODES.VALUE` gains the "OPTION = User"
  condition its sibling already had.
- Conditions in the JSDoc of a named nested type are stated from that type's
  own root (`Required when TYPE = "LINEAR"`, not `ITEMS.TYPE`).

### Fixed - `/db/MCON`'s linear constraint could not be typed correctly

The manual gives `SLAVES[]` two shapes: `{NODE_KEY, COEFF, DOF}` when `TYPE` is
`"EX"` and `{NODE_KEY, WEIGHT}` when it is `"WD"`. The contract had merged both
tables into one `SLAVES` element requiring all four keys, which neither type
accepts, and its branches placed the same keys beside `TYPE` instead of inside
`SLAVES`. `LinearConstraintItem` (and `LinearConstraintPayload`) now require
the right members inside `SLAVES` for each `TYPE`, and no longer list
`NODE_KEY`, `COEFF`, `DOF` or `WEIGHT` on the item itself, where the server
does not read them. `LinearConstraintSlaveExplicit` and
`LinearConstraintSlaveWeighted` describe the two element shapes.

### Changed - the `/post` request types come from the table contracts

The types for a result table's request objects - each story table's
`ADDITIONAL`, `NODE_FLAG`, `UNIT` and `STYLES` - were generated from the
Python package's TypedDicts, where every member is optional and every value a
plain `string`. 24 of them are now generated from the table contracts, which
record these objects from the manual:

- **8 members become required** across 7 types, where the manual marks them
  Required: `SET_ANGLE` on `StoryShearForceRatioAdditional` and
  `CapacityIrregularityAdditional`, `SELECT_IRREGULAR_ENDS` on
  `IrregularEndsAdditional` and `USER_DEFINE` on `SelectIrregularEnds`,
  `SET_CALCULATION_METHOD` on `StiffnessIrregularityAdditional`, and
  `SET_REACTION_PARAMS` with its `NODE_KEY` and `COMPONENT` on the Concurrent
  Joint Force types. `SELECT_NODES`, required only when `USER_DEFINE` is
  `true`, stays optional and says so in its JSDoc.
- **9 members narrow from `string` to the values the manual lists**:
  `TableStyles.FORMAT`, `OverturningMomentParams.DEFINE_RF`, `FIX_USER_CHECK`
  on both Beta types, `STORY_DRIFT_METHOD` on four types and
  `StiffnessCalculationMethod.STORY_STIFFNESS_METHOD`.
- **2 members gain a shape**, which narrows them too: `StoryDriftCalculationMethod`'s
  `DRIFT_OF_A_VERTICAL_LINE_ON_SELECTED_NODE` and
  `AVERAGE_DRIFT_OF_VERTICAL_LINES_ON_SELECTED_NODES` were `unknown` and are
  now `{ X_DIR?, Y_DIR?, COMBINED? }`, a node id and a node-id array
  respectively.
- `PostStoryTypes.StorySetAngle` is unchanged: four tables share it and the
  manual makes `ANGLE` required in two of them and optional in the others.

### Changed - declaration order in the generated types

`types.ts` (and so `dist/index.d.ts`) now lists each namespace's types in
name order. Every declaration is textually identical to 2.9.1's - 765 before
and after - and nothing else in the package changes. The old order was the
order of classes in the Python source, which is what the generator no longer
reads to place a type a contract owns.

## 2.9.1 - 2026-09-22

> **Breaking at the type level; nothing changes at runtime.** No exported name
> is added, removed or renamed - 765 exported type names before and after - and
> no member is removed. But **551 members go from optional to required across
> 216 types** - 415 across 156 payload-side types and 136 across 60
> operation-argument types - so code that builds one of those objects without a
> member the contract requires stops compiling. The generated JavaScript, the
> operations and the table wrappers are otherwise unchanged. The shared
> version number is a patch bump by the author's choice; read it as breaking
> for these types.
>
> Counted against `js-v2.9.0`'s declarations: a member is a named type's own
> property, inherited ones included, so a member that moved from a base
> interface into the type itself is neither added nor removed.

### Changed - 228 nested types now come from the contracts

Every payload built from a contract already inlined its nested objects in the
contract's shape. The **named** interfaces for those same objects - the element
of an `ITEMS` array, a `COMMON` block - were still generated from the Python
package's TypedDicts, which declare every member optional. So one object was
published twice with two shapes: `DbBoundaryTypes.BeamEndOffsetItem.TYPE` was
optional while `BeamEndOffsetPayload.ITEMS[].TYPE` beside it was required.

Contracts now record the names these types are already published under, and
228 of them are generated from the contract instead:

- **415 members become required** across 156 types, matching the payload that
  contains them. Any value that satisfied the containing payload type already
  satisfied these.
- **37 members are added** across 10 types, where the contract documents a
  field the Python TypedDict did not - `BeamLoadItem`'s eccentricity and
  additional-load members, `LinearConstraintItem`'s, and `KEYS`/`TO`/
  `STRUCTURE_GROUP_NAME` on `RcBeamRebarItem` and `RcBraceRebarItem` among
  them.
- **29 types no longer `extends` a shared base** such as
  `DbBaseTypes.ItemGroupFields`; the same members are declared inline, so the
  shape is unchanged for a caller.
- **4 become `type` aliases instead of `interface`s**, because the contract
  branches inside them: `DbBoundaryTypes.LinearConstraintItem`,
  `DbStaticLoadsTypes.PressureLoadItem`, `DesignRcKdsRebarTypes.RcBeamRebarItem`
  and `DesignRcKdsRebarTypes.RcBraceRebarItem`. `PressureLoadItem` now requires
  `FORCES` for `FACE_EDGE_TYPE` `"FACE"`/`"PRES"` and `EDGE_LOADS` for
  `"EDGE"`, as `PressureLoadPayload` already did. A type alias of a union cannot
  be `extends`-ed or `implements`-ed.

### Changed - operation argument types now come from the contracts

The argument types of `operations.*` - `/ope`, `/view` and the design-code
`*-ANAL`/`*-TABLE`/`*-REPORT` calls - were generated from the Python package's
TypedDicts, where every member is optional. 44 of them, and the 44 named
objects nested in them, are now generated from the same operation contracts
the SDK's other checks already read:

- **136 members become required** across 60 types, each checked against its
  manual row: the report calls' `REPORT_TYPE`/`EXPORT_PATH`/`OUTPUT_NAME`, the
  table calls' `TABLE_TYPE`, `/ope/AUTOMESH`'s four settings objects, and so on.
- **Members the manual requires only in one branch stay optional**, with the
  condition in their JSDoc: `/view/ACTIVE`'s `N_LIST`/`E_LIST` (mode
  `"Active"`) and `IDENTITY_TYPE`/`IDENTITY_LIST` (mode `"Identity"`), so
  `{ ACTIVE_MODE: "All" }` still type-checks; `/view/CAPTURE`'s `FIGURE_NAME`,
  whose presence is what selects a Smart Report capture; and `/ope/LINEBMLD`'s
  load `D`/`P` (every `TYPE` but `CURVED`) and `A`/`B`/`C` (`CURVED` only).
- **2 members are added**, `PRI_SORT_WID` and `EXPORT_PATH` on
  `RcWallDesignTableArgument`, where the manual documents a field the
  TypedDict lacked.
- **`LoadCombinationSteelArgument` no longer `extends`
  `_LoadCombinationSteelSrcKdsArgument`**; it declares the same members itself,
  and `OPTION` and `DGNCODE` become required as the manual states.
- **Unchanged, on purpose:** `DivideElementsArgument` (`/ope/DIVIDEELEM`),
  whose manual marks every axis of an unequal or parametric division Required
  without saying which axes a frame uses, so publishing it would refuse a valid
  frame division; `SrcMemberCheckTableArgument`, whose two manual sections
  disagree; the load-combination union arguments; and `ResultGraphicArgument`.

### Fixed - eight payloads regain nested members the manual documents

The tool that drafts contracts from the manual dropped a nested row numbered
`(1)`, `(2)` whenever a field of the same name appeared earlier in the same
table - a root `LCNAME` two rows above hid `COMB_LIST[].LCNAME`. 27 documented
members were missing from eight contracts, and so from these payload types:

- `InitialForceControlDataPayload` (`/db/EFCT`): `COMB_LIST[].LCNAME`, required.
- `ConstructionStagePayload` (`/db/STAG`): `DACT_ELEM[].GRUP_NAME`, required.
- `ConstructionStageForHydrationPayload` (`/db/HSTG`): `DACT_LOAD[].LOAD_NAME`
  and `DAY`, both optional.
- `NonlinearAnalysisControlDataPayload` (`/db/NLCT`): eleven members of
  `NEWTON_ITEMS`, `ARCLEN_ITEMS` and `DISPCT_ITEMS`, nine of them required in
  their iteration-method branch.
- `TendonProfilePayload` (`/db/TDNA`): nine `PROFZ` members of the 2D spline
  and round branches, `PT` required in each.
- `StaticSeismicLoadPayload` (`/db/SSEIS`, required) and `StaticWindLoadPayload`
  (`/db/SWIND`, optional): `ADDITIONAL_LOAD[].STORY_NAME` in the user-type
  branch.
- `BeamSectionTemperaturePayload` (`/db/BTMP`): `ITEMS[].vSECTTMP[].REF`,
  optional.

The two checked against the product's `/info` schema (`/db/EFCT`, `/db/STAG`)
declare these members on Civil NX and Gen NX. The live payloads this project
has confirmed against the product are unaffected: none of them conflicts with a
restored member.

## 2.9.0 - 2026-09-20

No change to this package. The shared version number moves because the Python
package now supports Python 3.11 again and is tested through 3.14; npm
republishes the same tarball content under the aligned number.

## 2.8.4 - 2026-09-20

> **Not breaking.** No exported name is added, removed or renamed - 765
> exported type names before and after - and three members of one type widen
> from required to optional. Code that compiled against 2.8.3 still compiles.
> Nothing changes at runtime.

### Changed - `TendonPropertyPayload` states when three members are required

`/db/TDNT` requires `FT`, `FPK` and `TDMFNAME` per relaxation model, not
always. `RM` selects the model, and the manual states each dependency in prose:
`FT` applies to six of the `RM` values, `FPK` to five, and `TDMFNAME` only to
the user-defined model `RM = 100`. The type said all three were always
required, which the SDK's own live payload - the manual's KSCE LSD15 example,
which sets none of them - did not satisfy.

The contract now records each dependency as an `appliesWhen` condition, so the
member is optional and its condition appears in the JSDoc:

```diff
-  /** Relaxation Factor xi (TB05/TB10092/Q-CR/AS/JTJ/JTG) */
-  FT: number;
+  /** Relaxation Factor xi ... Required when RM is 2 or 3 or 10 or 11 or 12 or 13. */
+  FT?: number;
-  FPK: number;
+  /** ... Required when RM is 2 or 3 or 10 or 12 or 13. */
+  FPK?: number;
-  TDMFNAME: string;
+  /** ... Required when RM = 100. */
+  TDMFNAME?: string;
```

## 2.8.3 - 2026-09-17

> **Breaking for one type, in a patch number.** No exported name is added,
> removed or renamed - 765 exported type names before and after - but one
> member narrows. Nothing changes at runtime.

### Changed - `SteelDesignCodeSelectionPayload` narrows

> **Breaking for this one type.** Code that omitted `DGNCODE`, or passed any
> string other than the manual's single value, no longer typechecks. Nothing
> changes at runtime.

`DESIGN/STEEL/DSTL` now has a contract, so its payload type is generated from
that rather than from the Python fallback. `DGNCODE` becomes required and is
typed as the literal `"KDS 41 30 : 2022"`, the only value the manual lists -
the same shape `RcDesignCodeSelectionPayload` has had since its own contract.
The fallback had emitted every member as an optional `string`, which claimed
less than the manual says.

## 2.8.2 - 2026-09-16

> Additive. No exported name is removed or renamed and no member narrows - 741
> exported payload types before, 742 after.

### Added - `steelDesignCodeSelection`, for `DESIGN/STEEL/DSTL`

- Selects the project's steel design code (today the manual lists one value,
  `"KDS 41 30 : 2022"`). GET, PUT and DELETE. The steel counterpart of
  `rcDesignCodeSelection`.
- **Not `steelDesignCode`**, which is `/db/DSTL`: same name, different URI and
  schema. Nothing about that resource changed.
- Not yet called against a product, and therefore generated from the reviewed
  Python class rather than a contract until it has been.

### Added - members the manual now documents

- `MaterialModifyConcretePayload` gains `bSERVCHECK`, `dSHORTTERM` and
  `dLONGTERM`. The official JSON Schema and live `/info` on both products
  declare them; requiredness is unstated because the article's table and
  example say nothing about them.
- `TendonProfilePayload`'s `CURVE` shape gains `bPJ`, which its `ELEMENT` and
  `STRAIGHT` shapes already had.

### Clarified - `constructionStage` (`OPT_CS`) has three states

- `true` switches the view to Construction Stage, `false` switches it to PostCS
  (the final stage), and leaving it undefined keeps the current view. The
  package already left it out unless set, so no request changes; the option's
  documentation now says so.

## 2.8.1 - 2026-09-15

> **Breaking for TypeScript callers: 16 members that were optional are now
> required.** No exported name is added, removed or renamed — 741 payload
> types before and after — and nothing about the wire format or runtime
> behaviour changed. Three payload types stopped being derived from a Python
> TypedDict and started being derived from their contract, and a contract
> states which members the manual marks Required.

### Breaking - three payload types now state the requiredness the manual does

- `TimeHistoryLoadCaseHyperSPayload` requires `NAME`, `ANAL_CASE`, `ENDTIME`,
  `TIME_INC`, `OUTPUT_STEP`, `DAMPING`, `INIT_METHOD`, `KEEP_LOAD`, `CUM_DVA`,
  `SUBSEQ` and `USE_INIT_LOAD`.
- `NonlinearAnalysisControlHyperSPayload` requires `NONLINEAR_TYPE`,
  `ITER_METHOD`, `CONV_CRITERIA` and `LOAD_STEPS`.
- `AdditionalImpactFactorPayload` requires `ITEMS`.

- The generator emits a Python-fallback type as entirely optional, because a
  TypedDict says nothing about requiredness that a generator can read. These
  three had therefore been claiming **less** than the manual says: a
  `TimeHistoryLoadCaseHyperSPayload` with no `NAME` type-checked clean and then
  failed at the server. Code already sending what the endpoint needs still
  compiles.

- `TimeHistoryLoadCaseHyperSPayload` is now a `type` alias rather than an
  `interface`, in common with the other contract-generated payload types.
  Declaration merging against it no longer works; nothing else changes.

### Fixed - three more payloads stop requiring what cannot coexist

- `MovingLoadAnalysisControlPayload` makes `iIGPN`, `DIST`, `RGN`, `DGN`,
  `FGN` and `LGN` optional: `iIGP` selects one of the first two, and each group
  name applies only when its own `bRG`/`bDG`/`bFG`/`bLG` is true.
- `GeneralLinkHyperSPayload` makes `BETA_ANGLE`, `INPUT_METHOD`,
  `ANGLE_VALUES`, `POINT_VALUES` and `VECTOR_VALUES` optional: `REF_SYSTEM`
  picks the element or global system, then `INPUT_METHOD` picks Angle, 3 Points
  or Vector.
- `TimeDependentMaterialFunctionPayload` makes `CTYPE` and `RELAXATION`
  optional: `FTYPE` selects Creep or Relaxation, and the manual numbers both
  rows `6` while qualifying them "(Creep only)" and "(Relax only)".

- Each condition is now `appliesWhen` in the contract and the generated JSDoc
  says it - `Required when REF_SYSTEM = 1 and INPUT_METHOD = 0`. Same defect
  class as 2.8.0's, found in three more places.

### Added - members the merged manual tables declare

- `PointSpringPayload`, `NonlinearAnalysisControlHyperSPayload`,
  `TimeHistoryLoadCaseHyperSPayload` and `AdditionalImpactFactorPayload` gain
  53 members between them, nearly all nested inside objects those types already
  had. They come from 21 manual tables the contracts had recorded as a declared
  gap rather than as fields.

## 2.8.0 - 2026-09-06

> Three payload types stop requiring two fields that cannot both be supplied.
> **Nothing is removed, no exported name moves, and no field changes type** -
> this widens what type-checks rather than narrowing it.

### Fixed - two mutually exclusive fields were both marked required

- `MovingLoadAnalysisControlIndiaPayload` and
  `MovingLoadAnalysisControlBSPayload` make `UNUMT` and `DIST` optional;
  `MovingLoadAnalysisControlTransversePayload` does the same for
  `NUM_UNIT_LOAD` and `DISTANCE`.

- These are branches, not siblings. One is the Number/Line element, the other
  the distance between points, and the influence-generation selector
  (`iIGP`, or `INFL_GEN_POINT`) decides which of the two applies. **A record
  carrying both is not a thing the endpoint accepts**, so requiring both
  described a payload no caller could construct.

- The manual states the branch in the description text of each row - "(when
  iIGP=0)", "(when method 1)" - so it was documented all along, just not in a
  form the generator could read. The three contracts now carry it as
  `appliesWhen`, which is where the generated optionality comes from. Existing
  code that sets both fields still compiles; nothing that used to type-check
  stops.

### Changed - the live harness runs against the resource it was given

Not shipped in the package; these are `scripts/` in this repository.

- `containsExpectedValue` compared with `Object.is`, which is reference
  identity for an object or array, so a fixture whose expected value was a
  nested object could never match a live response - the assertion passed
  nothing at all. It now compares structurally, with a unit test on the nested
  shape that exposed it.

- `runCase` called POST unconditionally, so a resource declaring GET, PUT and
  DELETE and no POST could not be exercised from this package while Python ran
  it fine. It now selects POST and/or PUT from the intersection of the emitted
  case's methods and the resource's own, and refuses a case offering neither
  rather than silently doing nothing.

## 2.7.9 - 2026-09-06

> Additive only. Four lane payload types and one moving-load control type
> gain members the server declares, and seven doc comments drop the vendor's
> internal ticket ids. **Nothing is removed and no exported name moves.**

### Added — the `/info` sweep's small-count tail, and what it was pointing at

- `TrafficLineLanePayload`, `TrafficLineLanesChinaPayload`,
  `TrafficLineLanesIndiaPayload` and `TrafficLineLanesOptimizationPayload`
  gain `SPECIAL_LANE_ITEMS`, an array the server declares on all four and the
  manual documents on none. Its members differ per endpoint (7, 6, 5 and 8
  respectively). The server's own description — "Used only when importing" —
  is the whole of what is known about when it applies, and no rule is
  generated from it. `TrafficLineLanesOptimizationPayload` also gains the
  root `OPT_STRADD`. Same finding as `/db/LLANtr`'s in 2.7.7, reaching its
  four siblings.

- `MovingLoadAnalysisControlChinaPayload` gains nine fields its **manual
  documents and this repo could not read** — the `FREQ` object's `SBEM_L`,
  `SBEM_E`, `SBEM_IC`, `SBEM_MC`, `iARCH_TYPE`, `CABL_A` and `CABL_L`, plus a
  `BTYPE` on each of `BRIDGE1` and `BRIDGE2` with the enum each accepts
  (`"RC" | "STEEL" | "MBRG" | "TRAIN"` and
  `"RAILWAY" | "RAILBRG" | "RAILCUL"`).

- Two separate causes, and the diagnosis matters because one of them looks
  like a defect this repo already fixed. `FREQ`'s table has **two Key/설명
  column pairs side by side** and the parser reads only the first — the
  first column's packed cells extracted correctly, so this is not MD-48's
  packed Key cell. Each `BTYPE` is stated in the **bold sentence introducing**
  its table rather than in a row of it, enum included; it is the selector
  deciding which of that table's fields apply, so neither object was usable
  without it. See MD-50.

- The seven `FREQ` keys are typed `unknown`, like the eighteen siblings from
  the same table: it is a Key/설명 table and states no Value Type. Taking
  `/info`'s `number` for all 25 is a separate change with its own evidence.

### Changed — doc comments no longer carry MIDAS IT's internal ticket ids

- Seven doc comments in `operations` and `tables` named `MAPI-xxxx` issues
  from the vendor's own tracker, generated from the Python docstrings they
  mirror. Every finding they record stays word for word; only the ticket id
  is gone. Nothing else about those wrappers moves.

## 2.7.8 - 2026-09-05

> A one-value fix, and the value is one the server was refusing. Nothing is
> removed, no exported name moves, and no type changes shape. If you call
> the surface-spring reaction table, your calls start working.

### Fixed — `tables.reaction.localSurfaceSpring` sent a string the server refuses

- The value is `REACTIONLSURFACESPRING`, with an L that `/post/TABLE`'s
  Specifications table and its JSON Schema enum both drop. Only the
  section's request example has it, and the contract had followed the other
  two on the reasoning that two sources beat one. **Both products refuse the
  majority spelling**, so every call through this one table type came back
  as an error rather than a table.
- Settled live on 2026-09-04, Gen NX 2026 v2.1 and Civil NX 2026 v2.2, both
  build 09/02/2026, by sending each spelling against the same document:
  `there was an error creating utbl` is a `TABLE_TYPE` the product does not
  know, `[empty] Cannot generate table data as there is no analysis result`
  is one it knows and cannot fill. The same run confirmed `BEAMFORCESTP`,
  where the identical majority reading happened to be right. See MD-49.
- No exported name changes and nothing else about the wrapper moves. If you
  were passing the constant, your calls start working.

## 2.7.7 - 2026-09-04

> **The largest breaking release so far, and the number does not say so.**
> The version is kept aligned with PyPI rather than derived from semver, so
> read this section rather than the digits. Sixty payload types lose a member
> (`Assign`, which the client builds for you and never wanted from you), one
> exported interface is renamed (`BraceMainBarSpec` -> `BraceMainBarItem`), and
> eighteen more records change shape or drop a name, because the shape they
> published is one the server refuses. Every removal below is a field the
> server does not take or a nesting it does not accept; nothing that worked on
> the wire stops working. If your build breaks, the type was describing a
> request that would have been rejected.

### Changed — `SeismicDeviceSteelDamperPayload` is generated from its contract

- **Breaking.** `/db/SDST`'s contract declared its field list incomplete, so
  the generator fell back to the reviewed Python model for this type. The one
  table it was missing — `SDST_HYS_MODEL` 별 하위 객체 — is now merged, so the
  type comes from the contract: `COMMON`, `DIR`, `SDST_HYS_MODEL`, `K0`, `P1`,
  `ALPHA1` and `KB` are required, as the manual marks them, where the fallback
  made every field optional. `COMMON` gained its six members and each
  hysteresis object its own, with "Applies when `SDST_HYS_MODEL` = …" on the
  four branches.

### Added — five more records gained members their objects never had

- `TimeHistoryLoadCaseHyperSPayload` gained `INC_CTRL` and `TIME_PARAM`. The
  contract had kept both tables as record-level branches, which put
  `INC_METHOD` and `METHOD` at the root; the manual's headings name the objects
  ("증분 제어 (ANAL_METHOD=2 Static 전용, `INC_CTRL`)") and `GET
  /info/db/THIS-M1` declares them, `INC_CTRL` holding a `DISP_CTRL` of its own.
- `NonlinearAnalysisControlHyperSPayload`'s `CONV_CRITERIA` gained `DISP`,
  `LOAD` and `WORK`, each with `OPT_USE` and `VALUE`.
- `SeismicDeviceIsolatorPayload`'s and `SeismicDeviceSteelDamperPayload`'s
  `COMMON` gained its six members, from `/db/SDVI`'s table one section over.
- `MovingLoadCasePayload` gained `DEFAULT`, `PERMIT_LOAD`, `AUTO_OPTIMIZE` and
  `ASL` — the four objects `TYPE` selects between, which the contract had
  published none of, leaving a load-case type with nothing to carry the load.
- `VehiclePayload` gained `VEH_EUROCODE` with 48 members, from `/info` and the
  2026-07-30 live reading of a real Eurocode Load Model 1 vehicle. Its three
  load-model branch arrays are deliberately still untyped. See MD-48.

### Changed — the four traffic-line-lane payloads take `COMMON` and `LANE_ITEMS`

- **Breaking.** `TrafficLineLanePayload`, `TrafficLineLanesChinaPayload` and
  `TrafficLineLanesIndiaPayload` published a flat record: the ten common lane
  properties at the root for `/db/LLAN`, the five lane-item members at the root
  for the other two. The server takes neither. All three records are
  `{ COMMON: {...}, LANE_ITEMS: [...] }` — the manual's Request Example, its
  Python example, `scripts/live_crud_check.py`'s confirmed round trip and
  `GET /info` all agree, and the contracts' own `extraction.table` had recorded
  the headings `Parameters – COMMON` and `Parameters – LANE_ITEMS` since the
  day they were drafted. `TrafficLineLanesOptimizationPayload` keeps its flat
  root, which is right for that endpoint, and gains the six members its
  `LANE_ITEMS` never had.
- Anyone whose calls worked was already sending the nested shape and passing an
  object the type did not describe; the type now describes it. Anyone following
  the type was getting a rejection from the server.

### Added — five endpoints gained the members their objects never had

- `MovingLoadCaseBsPayload`'s six `LCDATA_*` objects were typed as bare objects
  with nothing inside. They now carry what the manual states, including the
  `SUBLOADDATA` array and its straddling-lane pairs. The manual's own callout
  says its summary table lists principal fields rather than every field, and
  the contract records that.
- `ModifyWallRebarDataPayload`'s `STORY`, `VERTICAL_REBAR`, `HORIZONTAL_REBAR`,
  `END_REBAR`, `BE_HORIZONTAL_REBAR` and `CONCRETE_FACE_TO_CENTER_OF_REBAR`
  gained their members, from the section's own JSON Schema and its sub-object
  summary table.
- `MovingLoadAnalysisControlPayload` gained the eight Russia-code fields the
  manual states in a sentence after its table.
- `TimeDependentMaterialCreepShrinkagePayload` gained `TCODE` and `bSILICA`,
  the `CODE="EUROPEAN"` branch confirmed live on 2026-07-30 and declared by
  `/info` on both products. See MD-47.
- `ElasticLinkPayload` gained the eight fields each `LINK` type adds, with
  per-type "Applies when" documentation. `DIR` carries no enum: the two link
  types that use it document two different ranges.

### Removed — `HeatOfHydrationAnalysisControlHyperSPayload.ITEM.M_GENERAL`

- **Breaking.** `/db/HHCT-M1`'s `ITEM` has no `M_GENERAL`. The Python TypedDict
  shared one item type with `/db/HHCT`, which does have it; the manual
  documents it only in `/db/HHCT`'s table and `GET /info/db/HHCT-M1` declares
  only `TYPE`, `CREEP_CALC_METHOD` and `M_EFF_MOD`. `/db/HHCT` is unaffected.

### Fixed — two payloads named fields the server does not

- `SectionStressPointsPayload`'s `POINT1`/`POINT2` entries are `{Y, Z}`, not
  `{PY, PZ}`. `GET /info/db/STRPSSM` declares `Y` and `Z` and gives them the
  descriptions `"PY"` and `"PZ"` — the manual section took the description for
  the key. `POINT2` also gains its item shape, which it never had: the manual
  states the pair once, under `POINT1`, and sends both arrays the same way.

- `PushoverGlobalControlHyperSPayload`'s `ANALYSIS_STOP.AXIAL_YIELD.BEAM` is
  `BEAM_COLUMN`, and `.SUPPORT_DZ_DIR.UPLIFT` is `UPLIFTING`. The manual
  spells the second `UPLIFT` in six places; the first it spells both ways, four
  rows apart, in sibling groups describing the same checkbox — and the server
  uses `BEAM_COLUMN` in both. Nothing was removed from this type: `WALL` and
  `SYMMETRIC` are not in `/info` either and are kept, because `/db/STBK` ships
  an `LCNAME` no `/info` schema declares and a confirmed live round trip sends
  it successfully on both products. See MD-37, MD-38.

### Changed — `SectionReinforcementPayload.MBAR_ITEMS` moved into `MBARS`

- **Breaking.** `/db/RPSC`'s longitudinal reinforcement is
  `MBARS: Array<{ MBAR_ITEMS: [...] }>`, not a root `MBAR_ITEMS`. `SBAR_ITEMS`
  stays at the root, where the manual puts it and where the server has it. The
  pair genuinely is asymmetric and the manual's table reads as though that had
  been tidied away. The item members are unchanged — only the depth. See MD-40.

### Added — payload fields now say which product declares them

- 72 field doc comments gained "Gen NX only." or "Civil NX only.". Contracts
  have carried a per-field `products` list for a while — `/db/SBDO`'s and
  `/db/IEHC`'s since before this release — and the generator ignored it,
  reading only the resource-level list. A Civil NX caller of
  `PushoverGlobalControlPayload` was offered twenty Gen-only fiber-model
  options as if they were theirs.

- The tags themselves come from comparing both products' `/info` schemas across
  all 177 endpoints that answer on both. Ten declare different records:
  `/db/ACTL`, `/db/BCCT`, `/db/EPSE`, `/db/IEHC`, `/db/POGD`, `/db/POLC`,
  `/db/POSL`, `/db/SBDO`, `/db/SPLC` and `/db/THGC`. Mostly this is the two
  products' own feature sets rather than a documentation slip — Gen NX has
  walls and fiber hinges, Civil NX has bridge seismic parameters. See MD-46.

- Eight of those fields were in no contract at all and are new to the types:
  `AnalysisControlPayload.ACWC`, `TimeHistoryGlobalControlPayload`'s
  `bCONV_WALL_STIFF`, `SeismicEarthPressurePayload`'s `LOAD_TYPE` and `WIDTH`,
  and `SeismicLoadParamPayload`'s `DAMP_RATIO`, `SRF`, `EPGAeff` and `Kae`.
  Additive.

### Fixed — `TrafficSurfaceLanesChinaPayload` described the wrong thing entirely

- **Breaking.** It had three members: `NODE`, `OFFSET`, `SPAN_LENGTH`. Those
  are the members of the `LANE_ITEMS` array, not of the record. The type now
  has `NAME`, `WIDTH`, `WHEEL_SPACE`, `SKEW_START`, `SKEW_END`, `bOPTIMIZE`,
  `ALLOW_WIDTH`, `MV_DIR`, `SEQ` and `LANE_ITEMS`, which is what `/db/SLANch`
  takes. `/db/SLANch`'s manual section has exactly one Parameters table and it
  describes the array; the record's own fields appear only in its examples, so
  the contract generator took the sub-table for the whole thing. The Python
  `TrafficSurfaceLanesChinaPayload` has been correct throughout. See MD-43.

### Fixed — five arrays and one object had no item shape

- `SurfaceLaneItem` (`/db/SLAN` `LANE_ITEMS`) gains its nine members, seven of
  them carrying the design-code condition the manual states in words. No
  structured gate is generated: the code is a model-wide setting, not a field
  of this payload, so there is nothing to gate on.
- `PushoverLoadCasePayload.LOADPATTERN` gains `LCNAME`, `DIR`, `MODE` and `SF`,
  three of them documented as applying for a given `LOADPATTERNTYPE` — that one
  *is* a field of the record, so the condition is rendered.
- `GeneralLinkPayload` and `GeneralLinkHyperSPayload`'s `ANGLE_VALUES`,
  `POINT_VALUES` and `VECTOR_VALUES` gain their `{VALUE}` member.
- `MainControlDataHyperSPayload`'s `TCELEM.CONVERGENCE` gains the `DISPL`,
  `LOAD` and `WORK` level it was missing. Its `OPT_USE`/`VALUE` sat one level
  too high — `{OPT_USE, VALUE}` where the server wants
  `{DISPL: {...}, LOAD: {...}, WORK: {...}}`. **Breaking** for anyone who wrote
  the shorter shape, which the server would not have accepted. See MD-44.

### Fixed — an exactly-bounded array lost its tuple type when its items gained one

- `GeneralLinkPayload.POINT_VALUES` and `.VECTOR_VALUES` are fixed-length
  tuples again. The generator's rule for preserving `minItems == maxItems` ran
  only on arrays of scalars, so describing an array's item type silently
  dropped the manual's stated length in the same change.

### Added — `/db/LLANtr` and `/db/SLANop` fields the manual does not document

- `TrafficLineLanesTransversePayload.SPECIAL_LANE_ITEMS`
  (`Array<{ELEMS, FACTOR}>`), described by the server as "Used only when
  importing" — which is all that is known about when it applies.
- `TrafficSurfaceLanesOptimizationPayload.OPT_STRADD` (BS straddling lane) and
  `CHINA_ITEMS` (`Array<{NODE_KEY, OFFSET, SPAN_LENGTH, SPAN_START}>`). See
  MD-45.

### Fixed — `GroupDampingPayload.GROUP_DAMPING_ITEMS` had no item type

- It was `Array<JsonObject>`. It is now an array of fifteen described members
  — `GROUP_TYPE`, `GROUP_NAME`, and the twelve Rayleigh fields that mirror the
  payload's own `*_DEFAULT` roots without the suffix. The manual states all
  fifteen, in a sentence rather than a table row, which is why the contract
  generator could not see them; `GET /info/db/GRDP` declares the same fifteen.
  The Python `GroupDampingRayleighItem` has had them since 2.4.0. See MD-42.

### Added — fields the server declares and the manual does not

- `StoryPayload.STORY_AREA_ITEMS` (`Array<{X, Y, Z}>`). Documented in the
  manual, in another chapter: `/ope/STOR`'s POST response is `/db/STOR`'s
  record field for field with this array added. See MD-39.

- `SeismicDeviceViscoelasticDamperPayload.COMMON` and
  `SeismicDeviceHystereticIsolatorPayload.COMMON` were `JsonObject` and now
  carry their six members. Both sections describe the object by pointing at
  `/db/SDVI`'s table rather than repeating it, and a cross-reference is the one
  thing the contract extractor cannot follow. The Python TypedDicts have had
  these all along.

- `RebarCheckInputPayload.BEAM.OPTION_IMJSAME`; `BeamLoadPayload.ITEMS`'s
  `VX`/`VY`/`VZ`; `TimeDependentMaterialFunctionPayload.ELAST`;
  `PipeCoolingPayload.START_STAGE`/`END_STAGE`; `ProjectInfoPayload`'s five
  model-file properties (`FILE_NAME`, `DIR`, `FILE_SIZE`, `CREATED`,
  `MODIFIED`); `ConstructionStagePayload.NO`;
  `TendonPropertyPayload.bRELAX`. All additive.

### Fixed — `/db/REBR`'s payload type was the shape the server refuses

- `BraceRebarPayload` and the exported `BraceMainBarSpec` described a single
  `MAIN_BAR` object with a top-level `DO`, a string `HOOP_TYPE`, and
  `CREATE_SUB_SECTION`/`ELEMS`. `GET /info/db/REBR` declares none of that. The
  type is now `vMAIN_BAR`, an array whose entries each carry `D0` (a zero, not
  the letter), with an integer `HOOP_TYPE` and no sub-section fields.

- `BraceMainBarSpec` is renamed `BraceMainBarItem` and loses nothing but the
  wrong nesting. This is the same correction `/db/REBC` received in 2.5.0, for
  the same reason and with the same evidence: chapter 24 describes both
  endpoints identically and the server takes both identically, which is not how
  the chapter describes them.

### Fixed — `vCOMB` and `INITLOAD` members were published outside their array

- All six `LoadCombination*Payload` types declared `ANAL`, `LCNAME` and
  `FACTOR` as siblings of `vCOMB`, which was therefore typed
  `Array<JsonObject>` — an array whose items nothing described. `vCOMB` is now
  `Array<{ANAL, LCNAME, FACTOR}>`. `PushoverAnalysisControlDataPayload`'s
  `INITLOAD` gains its `{LC_NAME, LC_TYPE, SF}` items the same way.

- The manual states this nesting outright (`| — | (vCOMB) 해석 타입 | "ANAL" |`)
  and the contract generator did not read that form. The Python TypedDicts had
  it right, so this aligns the npm types with what `midas-nx` on PyPI already
  published.

### Added — four fields on every `/db/LCOM-*` payload

- `bES`, `iSERV_TYPE`, `nLCOMTYPE` and `nSEISTYPE` are optional members of all
  six load-combination payload types. `GET /info/db/LCOM-*` declares them on
  every endpoint and both products; the manual's comparison table says five of
  the six have no additional fields at all. Additive — no existing code breaks.

### Removed — the `Assign` envelope is no longer a member of 60 payload types

- **This is a fix, not a narrowing.** `DbResource.create()` and `.update()`
  build the `{"Assign": {"<id>": ...}}` envelope themselves, from the keys of
  the `ItemMap` you pass. The manual's Parameters tables open with a row for
  that envelope, and the contract generator was emitting it as a payload
  member — so 60 interfaces demanded an `Assign` that, if you supplied it,
  produced `{"Assign": {"1": {"Assign": ...}}}` on the wire.

- Two shapes were affected and both are gone: `Assign: JsonObject` sitting
  beside the real fields (56 types, such as `EffectiveLengthFactorPayload`,
  whose `Ky`/`Kz`/`Kt` are the record), and `Assign` carrying the record as its
  own members (4 types, such as `RebarDesignCriteriaPayload`), whose members are
  now the payload's own.

- If you were satisfying the compiler with a dummy `Assign: {}`, delete it. If
  you were reaching through `payload.Assign.ITEMS`, drop the `Assign` step.
  Nothing else about these types changed. The endpoints generated from Python
  TypedDicts — the same design endpoints under `/DESIGN/SRC/AIK-SRC2K/`, for
  instance — never had the member, so the two families now agree.

### Changed — eleven more endpoints take their payload type from a contract

- `/db/REBR`, `/db/RCHK`, `/ope/AUTOMESH`, `/ope/MEMB`, `/ope/SECTPROP`,
  `/ope/PROJECTSTATUS`, `/DESIGN/RC/KDS-41-20-2022/REBB`, `.../REBR`,
  `.../CD-TABLE`, `.../BRD-TABLE` and `/TEMP/DESIGN/SRC/AIK-SRC2K/OCHECK` now
  generate their payload types from
  `contracts/endpoints/`. As with earlier contract takeovers, members the
  manual marks Required become required, and nested objects that were opaque
  aliases are spelled out:

  - `BraceRebarPayload` gains the full `ITEMS` item — `MAIN_BAR`,
    `SHEAR_BAR_END`/`SHEAR_BAR_CEN`, `ELEMS` and `ID`. Previously it was
    `{ ITEMS?: Array<BraceRebarItem> }`.
  - `RebarCheckInputPayload`'s `BEAM` and `COLM` were `BeamCheckRebar` /
    `ColumnCheckRebar` references and are now inlined with their full subtrees.
    Both interfaces are still exported and unchanged.
  - `MemberAssignmentPayload`'s `ELEM_LIST` is `Array<number>`; the manual's
    table typed it only `Array`.
  - `SectionPropertiesPayload` and `ProjectStatusPayload` type their `DATA`
    rows as `Array<Array<string>>`. The values arrive as strings, quoted, in
    the manual's own Response JSON — including the numeric ones.

  - `AutoMeshPlanarAreaPayload`'s `MESHER.INCLUDE_INTERIOR_LINES` gains the
    three members the manual's table points at instead of listing, and
    `MESH_SIZE.DIV` is documented as the alternative to `LENGTH` rather than
    required alongside it.
  - The `CD-TABLE` and `BRD-TABLE` payloads document `ELEMS` and `SECTIONS` as
    alternatives — give one or the other.

### Added — a warning on `/TEMP/DESIGN/SRC/AIK-SRC2K/OCHECK`

- The SRC optimal-design endpoint now carries a contract `warn` rule and a
  named entry in the repository's known-product-risks list. Nothing about the
  npm function changes — it already carried the warning in its own
  documentation — but the risk is now stated in the language-neutral source
  both packages are generated from, so it cannot be lost in one of them. The
  endpoint ends the NX session when the open model holds a section SRC design
  cannot use, and MIDASIT has classified it as an unofficial API with paused
  development.

### Removed — `LAYER` from `RcBeamMainBarLayerEntry`

- `/DESIGN/RC/KDS-41-20-2022/REBB`'s main-bar array item is `{ NAME, NUM }`.
  The `LAYER` member was this SDK's own inference and no statement in the
  manual chapter names it; the chapter-24 sibling dropped the same inference in
  2.5.0 against a live schema pull, and this one was missed then. The two now
  agree. `ModifyBeamRebarDataPayload` also takes its whole shape from the
  contract, which follows that section's worked examples — as both SDKs
  already did.

### Changed — `TimeHistoryGlobalControlHyperSPayload` now comes from a contract

- `/db/THGC-M1`'s payload type is generated from
  `contracts/endpoints/db-thgc-m1.yaml` rather than from the Python TypedDict.
  Three consequences, in order of how likely they are to reach you:

  - **`ITER_PARAM` was `unknown` and is now a typed object.** Its convergence
    norms (`NORM_CTRL.DISP`/`FORCE`/`ENERGY`, each `{OPT_USE, VALUE}`) and its
    line-search options are spelled out. Code that assembled this object
    untyped keeps working; code that assigned an arbitrary value to it no
    longer compiles.
  - **`GEO_NONL_TYPE`, `INIT_LOAD_TYPE` and `ITER_PARAM` are required**, as the
    manual marks them. A partial payload will now be flagged by the compiler.
  - `INCREMENT_STEP` and `HINGE_OPT` are inlined in the payload rather than
    referencing the exported `HyperSIncrementStep` / `HyperSHingeOption`
    interfaces. Both interfaces are still exported and unchanged; nothing was
    removed.

### Changed — `/db/MVLDeu` and `/db/POGD` payload types now come from contracts

- `MovingLoadCaseEurocodePayload` and `PushoverAnalysisControlDataPayload` are
  generated from `contracts/endpoints/` instead of the Python TypedDict, and
  gain the members the manual marks Required — `LCNAME` and `TYPE_LOADMODEL`
  on the first, among others.

- `STL_LIST` and `SUB_LOAD_LIST` are now inline object types rather than
  references to the exported `MovingLoadCaseEurocodeStraddlingLaneItem` and
  `MovingLoadCaseEurocodeSubLoadItem` interfaces. The members are unchanged and
  both interfaces are still exported; nothing was removed.

- `MovingLoadCasePermitPayload` and `TimeHistoryLoadCasePayload` are
  **unchanged** even though `/db/MVLDpl` and `/db/THIS` are now contracted:
  both contracts carry manual tables they could not place, and a contract with
  an unresolved table deliberately does not narrow the published type.

### Changed — two more Hyper-S payload types now come from contracts

- `ConstructionStageAnalysisControlDataHyperSPayload` (`/db/STCT-M1`) and
  `PushoverAnalysisControlDataHyperSPayload` (`/db/POGD-M1`) are generated from
  `contracts/endpoints/` instead of the Python TypedDict. Both gain required
  members where the manual marks them Required — `ANAL_TYPE` and `ITER_CTRL`
  respectively, among others — so a partial object will now be flagged by the
  compiler.

  `/db/STCT-M1` also fills in what was previously `NONL_CONTROL: unknown`: its
  `iLSTEP`, `INTOUT`, `ADVANCED` (with a nested `LINE_SEARCH`) and the three
  `DISP`/`LOAD`/`WORK` convergence criteria are typed, and the payload gains
  `FINAL_STAGE`, a root property live `/info` declares that the manual's
  Parameters table never listed.

  `TimeHistoryLoadCaseHyperSPayload` (`/db/THIS-M1`) is **unchanged**. That
  endpoint is now contracted too, but its contract records one manual table it
  could not place, and a contract carrying an unresolved table deliberately
  does not narrow the published type — an incomplete field list is not a
  better type than the one you had.

### Fixed — `INIT_LOAD_TYPE`'s second value is 1, not 0

- The manual prints `0` as the literal for **both** of this field's two
  options. Live `GET /info/db/THGC-M1` gives `Perform NL Static:0, Import
  Static:1`, and the contract and both SDKs now document `1`. This is a
  documentation fix in the types and comments — no request the SDK sends
  changes. Recorded as MD-18 in `docs/manual_defects_register.md`.

## 2.7.6 - 2026-09-03

> **Breaking, despite the patch number.** The version is kept aligned with
> PyPI, so read this section rather than the number. Two `create()`/`update()`
> calls now throw where they previously sent a request, and several payload
> types moved fields into the object the server actually reads them from.
> Nothing here changes a request the SDK sends on your behalf — it changes
> which requests it will send at all, and where the types say fields belong.

### Changed — seven payload types are now generated from contracts

- `SectionPayload`, `PressureLoadPayload`, `WallRebarPayload`,
  `ColumnRebarPayload`, `BeamRebarPayload`,
  `InelasticMaterialPropertyPayload` and `SrcBeamSectionDataPayload` now come
  from `contracts/endpoints/` rather than from the Python TypedDict. For the first two that means a **discriminated union**
  over the field the manual actually branches on, with the fields the manual
  marks Required no longer optional.

  `SectionPayload` branches on `SECTTYPE` (`DBUSER`, `VALUE`, `SRC`, `PSC`),
  and each branch carries its own `SECT_BEFORE`. `CALC_OPT` has not been
  removed — it moved into the `VALUE` branch, which is the only one the manual
  documents it for. `PressureLoadPayload` branches on `FACE_EDGE_TYPE` inside
  each `ITEMS` entry: `FORCES` for `"FACE"`/`"PRES"`, `EDGE_LOADS` for
  `"EDGE"`. It also gains `PSLT_KEY`, a `/db/PSLT` reference both products'
  `/info` schema declares and the manual chapter never mentions.

  Code that built one of these as a partial object will now need the required
  members and the discriminant. The compiler points at each one, and the
  branches match what the endpoints already accepted — this narrows the type to
  what the server takes, it does not change any request the SDK sends.

  The three rebar payloads are plainer: `ITEMS` becomes required and its entry
  type is inlined rather than referring to the exported `WallRebarItem` /
  `ColumnRebarItem` / `BeamRebarItem` interface, all of which stay exported and
  unchanged. No field is renamed. These are the endpoints whose manual sections
  document schemas the product does not implement — including in MIDASIT's own
  articles, not just the vendored copy — and this package already shipped the
  server-confirmed names, corrected in 2026-07 and 2026-08.
  `ColumnRebarPayload` also gains `HOOK_TYPE`, the one field of `/db/REBC`
  where the manual survived the comparison intact.

  `InelasticMaterialPropertyPayload` grows the most: 171 members it did not
  declare before. `/db/FIMP` carries seventeen hysteresis-model objects under
  `CONC` and `STEEL`, and the manual documents one of them — its own callout
  says so, pointing at a 5900-line source article it does not transcribe. The
  rest come from the server's own `/info` schema, which both products serve
  identically. Nothing that was there is removed.

  `VehiclePayload` and `TimeDependentMaterialStrengthPayload` were listed here
  in an earlier draft of this entry and are **not** affected. Their contracts
  carry `extraction.unmergedTables` — the manual names no wire discriminator
  for one of their tables — and a contract that admits its field list is
  partial is deliberately not allowed to narrow a published type. Both remain
  the Python-derived interfaces they were.

### Added — `/db/MVHL` refuses an empty `VEH_DEFAULT`

- `vehicles.create()` and `.update()` now throw `MidasRequestError` when
  `VEH_DEFAULT` is sent as `{}`. The server accepts that body, answers
  `{"message": ""}` with no error object, and stores nothing, so the only
  previous signal was a later `get()` showing no vehicle. Omitting
  `VEH_DEFAULT` entirely is unaffected — nine of the documented
  `STANDARD_CODE` values carry their own object instead.

### Added — `/db/PRES` requires an explicit `DIRECTION`

- `pressureLoad.create()` and `.update()` now throw `MidasRequestError` when an
  entry of `ITEMS` omits `DIRECTION`. The manual marks that field Optional with
  the default `"NORMAL"`, and on a `PLATE` with `FACE_EDGE_TYPE: "FACE"` — the
  commonest pressure load there is — the server applies that default and then
  refuses the record, with the same error it gives for `"NORMAL"` sent
  explicitly. There is no default the SDK could substitute: which way a
  pressure acts is an engineering decision, so you are asked rather than
  guessed for.

  Sending `"NORMAL"` yourself is unaffected. The section's own availability
  matrix marks it valid for the other three `ELEM_TYPE`/`FACE_EDGE_TYPE`
  pairs, and refusing a value you typed would overrule that.

  A record with no `ITEMS` at all is left alone — that is a different request,
  not a missing field.

### Fixed — three payload types were missing fields their manual documents

- **`SrcBeamSectionDataPayload`, `SrcModifyMaterialPayload` and
  `SrcColumnSectionDataPayload` dropped fields the manual states.** The generator
  reads the manual's parameter tables through an extractor that suppresses a
  repeated key inside the same numbered scope — `CONCRETE.CODE` and
  `REBAR.CODE` are different fields that share a last token. A table that
  nests with `└` depth markers instead of a No. column has no numbered scope,
  so the check collapsed to the bare key and dropped every repeat anywhere in
  the table.

  A rebar table is nothing but repeats. `/DESIGN/SRC/AIK-SRC2K/MRBD` published
  14 of the 54 paths its own JSON Schema declares: `NAME` and `NUM` recur under
  `LAYER1` and `LAYER2`, under `TOP` and `BOT`, and under all three of
  `BAR_SECTOR_I`/`_M`/`_J`, and only the first of each survived. `MATD` lost
  `CONCRETE.CODE` — a **required** field — along with `CONCRETE.STANDARD_CODE`,
  `.NAME`, `.GRADE` and `REINFORCEMENT.CODE`/`.STANDARD_CODE`; `MCRD` lost
  `SHEAR_BAR.NAME`. 53 rows across the chapter in total, and none anywhere
  else. Nothing that was published is removed.

### Changed — `srcBeamSectionData.metadata.name`

- Now `"Modify SRC Beam Section Data"`, the manual's own section label, which
  this package had shortened to `"SRC Beam Section Data"`. Display metadata
  only: the export, the endpoint and the payload type are unchanged.

### Fixed — branch fields that were published at the top level

- **`StaticWindLoadPayload`, `StaticSeismicLoadPayload` and
  `LinearConstraintPayload` declared a whole conditional branch in the wrong
  object.** A manual branch table gates on one field and adds siblings of it,
  so the branch belongs wherever that field lives. The generator attached every
  branch to the payload root instead.

  `/db/SWIND` is the clearest case: `INPUT_METHOD`, `WIND_SPEED`,
  `EXP_CATEGORY`, `ROOF_HEIGHT` and the rest were published as top-level
  members, while the section's own worked examples send all of them inside
  `PARAMETERS` — which is also where the contract declares the `INPUT_METHOD`
  they branch on. `/db/SSEIS` had the same shape with `PERIOD_METHOD` and the
  period fields; `/db/MCON`'s `TYPE` branch belongs inside an `ITEMS` entry.

  `ModifyColumnRebarDataPayload` loses `KEYS`, `TO` and `STRUCTURE_GROUP_NAME`
  from its root for a related reason: the manual states them once, under a
  heading naming both a condition and a parent object, and the contract had
  recorded that one table twice - correctly inside `ELEMS`, and again as a
  root-level branch. The `ELEMS` copy is the one that survives.

  This is the same defect as the field-level nesting fix below, one level up:
  a caller following the published type put the fields where the server does
  not look. The members move rather than disappear, and the compiler will point
  at each one.

- **A branch table naming several values was dropped instead of emitted.** A
  multi-value condition was read as the manual's *shared supplement* table —
  `/db/FBLA` states one for `FLOOR_DIST_TYPE = 1 or 2` beside its `= 1` and
  `= 2` tables — and folded into the branches it covers. When it covers none of
  them it is an ordinary branch that happens to span two values, and folding
  discarded it: `/db/PRES`'s `FACE_EDGE_TYPE = "FACE" or "PRES"` branch took
  `FORCES` with it. Overlap now decides which kind a table is.

### Fixed — nested fields that were published at the top level

- **`BeamSectionTemperaturePayload`, `StaticWindLoadPayload` and
  `HeatOfHydrationAnalysisControlHyperSPayload` had members in the wrong
  place.** The manual marks a third level of nesting with a bare letter or
  roman numeral in its No. column (`a`, `b`, `c` / `i`, `ii`, `iii`), and the
  extractor only knew the parenthesised `(1)` form, so 183 rows across 18
  manual sections were read as top-level fields of the request.

  `/db/BTMP` is the clearest case: `TYPE`, `VAL_B`, `VAL_H1`, `VAL_H2`,
  `VAL_T1`, `VAL_T2`, `ELAST`, `THERMAL`, `OPT_B`, `OPT_H1` and `OPT_H2` were
  declared at the top level of the payload. The section's own Request Example
  sends them inside `ITEMS[].vSECTTMP[]`, three levels down. A caller
  following the published type put them where the server does not look.

  `/db/SWIND` lost a field outright: `TOPOGRAPHIC_EFFECT` and `FORCE_COEF`
  both document their own `OPT_USE`, and flattened to the root the second
  overwrote the first. Both are now declared, each inside its own object,
  along with the thirteen `VIBRATION_PARAMS` members.

  If you were constructing one of these payloads against the old shape, the
  members move rather than disappear — the compiler will point at each one.

### Changed


- **Four Hyper-S payload types come from a contract instead of a Python
  `TypedDict`.** `MaterialHyperSPayload`, `PlasticMaterialHyperSPayload`,
  `InelasticFiberMaterialLinkHyperSPayload` and
  `InelasticHingePropertyHyperSPayload` now inline their members and carry the
  server's own field descriptions as doc comments, which they had none of
  before. The named interfaces they used to reference
  (`MaterialHyperSParam`, `PlasticMaterialHyperSMasonry`,
  `InelasticFiberMaterialLinkHyperSConcrete` and the rest) are still exported
  and unchanged; the payloads no longer point at them.

  Their manual sections state no request at all — a URL, a methods line and a
  link — so these four are the first contracts sourced from live
  `GET /info/db/...` introspection rather than the manual. Every member is
  optional, because `/info` declares no `required` array and `optional` would
  be a claim nobody has made.

- **Fifteen resource labels take the manual's en dash.** `db.*.name` for the
  six `LCOM-*` load combinations, the five `SD*` seismic devices,
  `/db/MVCTch`, `/db/RPSC`, `/db/SECF` and `/db/TDMT` read
  `"Load Combinations – General"` rather than `"Load Combinations - General"`
  and so on. The npm package had been publishing the en dash for thirteen of
  them while the Python package published a hyphen; both now read what their
  manual section reads.

- **Three more endpoints are contract-driven**: `/db/HHCT`, `/db/SECF` and
  `/db/TDMT`. `/db/TDMT` and `/db/SECF` had been held back by a review gate
  quoting findings that were retracted on 2026-07-27, when the vendor report's
  claims were re-checked against MIDASIT's own articles.

- **Two resource labels follow their manual sections.**
  `db.properties.material.inelasticFiberMaterialLinkHyperS.name` is now
  `"Inelastic Material Link for Auto Generation (Hyper-S)"` and
  `db.properties.hinge.inelasticHingePropertyHyperSBeam.name`
  `"Assign Inelastic Hinges - Beam (Hyper-S)"`. Both had been derived from
  their parent endpoint's label; the first named a different feature, since
  `/db/IMFM-M1` is a material link and `/db/IMFM` is fiber-model properties.

## 2.7.5 - 2026-09-02

### Compatibility — breaking

- **`SectionBoundaryDataPayload.AXIS_VECTOR` is `Array<number>`, not
  `number`.** `/db/SBDO`'s Specifications table types it `Number`; the same
  section's JSON Schema types it an array of numbers and its own Request
  Example sends `[0, 0, 0, 0, 0, 0]`. The contract followed the table and npm
  followed the contract, so the field's own documented value did not
  typecheck. Python has always had `List[float]`. Assigning a scalar now
  fails; send the vector.
- **Three KDS rebar payloads are contract-driven and require their members.**
  `RebarDesignCriteriaPayload` (`/DESIGN/RC/KDS-41-20-2022/DCRE`),
  `RebarDesignCriteriaByWallMemberPayload` (`DCRM-WALL`) and
  `ModifyColumnRebarDataPayload` (`REBC`) now state the manual's requiredness,
  descriptions and enums - `SPLICED_BARS` (`"None" | "50%" | "100%"`),
  `MATERIAL` (nine grades), `END_REBAR_METHOD` (`1`-`4`), `HOOP_TYPE`,
  `HOOK_TYPE`. Their member shapes are inline, so `DcreBeamCriteria`,
  `DcreColumnBraceCriteria`, `DcreWallCriteria`,
  `RebarDesignCriteriaByWallMemberItem` and `RcColumnRebarItem` are still
  exported but no longer what the payload refers to. Rebar *size* fields stay
  plain `string`: chapter 26 says in each section that it prints only the first
  5 of 19, so there is no enum to publish.
- **Two resource labels follow the manual.**
  `rebarDesignCriteria.name` is `"Design Criteria for Rebar"` and
  `rebarDesignCriteriaByWallMember.name` is
  `"Design Criteria for Rebars by Wall Member"`, matching their manual sections
  and their three `DCRM-*` siblings, which already read that way. The Python
  classes' `NAME` changed with them.
- **`MaterialPayload` requires `TYPE`, `NAME` and `PARAM`.** `/db/MATL` is now
  contracted, and its manual states all three Required. `PARAM` is also
  `Array<...>`, not `Array<MaterialParam>`: the Specifications table types it
  `Object` while the same section's JSON Schema says `array` and every Request
  Example in the section sends `[{...}]`. Each entry now carries the manual's
  own descriptions and, in its doc comment, which `P_TYPE` requires it.
- **`SectionReinforcementPayload` requires its five members.**
  `OPT_MBAR_J`, `OPT_SBAR_J`, `OPT_CRACKED`, `SBAR_ITEMS` and `MBAR_ITEMS`
  are required, as `/db/RPSC`'s table states, and the two item arrays now
  carry their fields inline with the manual's descriptions and its
  requiredness (`IJ`, `NAME`, `REF_Y`, `REF_Z`, `NUM` are required within
  `MBAR_ITEMS`). The exported `SectionReinforcementShearItem` and
  `SectionReinforcementLongitudinalItem` interfaces are unchanged and still
  exported, but the payload no longer refers to them, so a value annotated
  with one of those names no longer widens to the payload's member type.

### Changed

- `sectionReinforcement.name` is `"Section Manager – Reinforcements"`, the
  manual's own section label, where it was `"Section Manager - Reinforcements"`
  before. `/db/RPSC` is now contracted, and a contract's `surface` block owns
  what npm publishes; the hyphen came from the Python class the resource used
  to be described by.

### Fixed

- Five documented fields were missing from the generated declarations:
  `SPLICED_BARS` on `RebarDesignCriteriaBy{Beam,Column,Brace}MemberPayload`
  (`"None" | "50%" | "100%"`, default `"50%"`) and `FRAMEX`/`FRAMEY` on
  `SrcDefinitionOfFramePayload`. The manual documents each of them in a
  Specifications row whose Description cell writes alternatives with GFM's
  escaped pipe (`None \| 50% \| 100%`); the contract extractor split those
  rows on every `|`, got more cells than the header has, and dropped the row.
  All five are optional, so nothing that compiled before stops compiling.
- **49 fields the manual requires only inside one branch are optional again.**
  A `requirement: required` carrying an `appliesWhen` is a branch's
  requirement, not the payload's, and typing it unconditionally required made
  `ConvectionCoefficientFunctionPayload` demand `COEF` (only under
  `TYPE: "CONST"`) together with `SCALE_FACTOR` and `ITEM` (only under
  `TYPE: "USER"`) - no caller could satisfy the type without sending fields
  their own branch does not have, and `InelasticMaterialPropertyPayload` asked
  for all six plasticity models at once. The condition moved into the doc
  comment (`Required when TYPE = "CONST".`). Nothing that constructed a payload
  before stops compiling; code that *reads* one of these fields may now need a
  guard under `strictNullChecks`. Affects `/db/CCFC`, `/db/EPMT`, `/db/ETFC`,
  `/db/HSFC`, `/db/MVLDid`, `/db/NLNK`, `/db/THFC` and `/ope/GSBG`.
- `/db/RPSC`'s two reinforcement item arrays no longer nest each item's
  fields under the first one. The manual numbers those supplementary tables
  `(1)`-`(n)` with no parent row of their own, and the extractor read the
  first row as the parent of its own siblings: `OPT_DR`, a boolean, held the
  twenty fields after it. The section's Request Example writes them side by
  side. `/db/MATL` and `/db/RCHK` had the same shape and are not yet
  contracted.

## 2.7.4 - 2026-09-02

### Compatibility — breaking

Three payload types were flat `interface`s with every member optional and are
now **discriminated unions**, the same change `FloorLoadPayload` went through
in 2.7.3. The version number is a patch; this section is the reason to read it
anyway.

| Type | Endpoint | Discriminator |
| --- | --- | --- |
| `StaticSeismicLoadPayload` | `/db/SSEIS` | `PERIOD_METHOD`, `SEIS_CODE` |
| `StaticWindLoadPayload` | `/db/SWIND` | `INPUT_METHOD`, `WIND_CODE` |
| `TendonProfilePayload` | `/db/TDNA` | `SHAPE`, `INPUT` + `CURVE` |

Three things this affects:

- **Fifteen members became required.** `SEIS_CODE`, `SCALE_FACTOR_X`,
  `SCALE_FACTOR_Y` and `PARAMETERS` on the seismic payload; `WIND_CODE` and
  the same three on the wind one; `NAME`, `TDN_PROP`, `ELEM`, `INPUT`,
  `CURVE`, `LENG_OPT` and `SHAPE` on the tendon profile. The manual marks all
  fifteen Required; the old declarations were wrong about that.
- **They are `type`s now, not `interface`s.** Code that `extends` one, or
  relies on declaration merging, no longer compiles.
- **Branch fields no longer combine with any discriminator value.**
  `STORY_WIND_PRESSURE` is documented under `WIND_CODE: "USER TYPE"` and
  `SEISMIC_FORCE` under `SEIS_CODE: "USER TYPE"`; the flat interfaces offered
  every branch's fields at once regardless.

No runtime behaviour changed, and no runtime payload validation was added.
This is the declaration moving towards the published manual.

### Fixed

- `SectionColorPayload` (`/db/CO_S`, `/db/CO_T`) offered two of the nine
  documented colour components. The manual compresses them into one row keyed
  `"W_R" ~ "HE_B"`, which was read as two literal keys, so `W_G`, `W_B`,
  `HF_R`, `HF_G`, `HF_B`, `HE_R` and `HE_G` could not be set. All eleven
  fields are now declared.
- Rebar size and bar-count fields no longer reject documented values.
  `RebarDesignCriteriaBy{Beam,Column,Brace}MemberPayload` typed `MAIN_REBAR`,
  `STIRRUPS`, `SIDE_BAR` and `TIES_SPIRALS` as `"D4" | "D5" | "D6" | "D7" |
  "D8"` and the leg counts as `2 | 3 | 4 | 5 | 6`, while the same rows are
  described as `19종 (D4 ~ D57)` and `2 ~ 20` - so every bar size from D10 up
  was untypeable. `SrcLiveLoadReductionFactorPayload` went further and
  accepted the literal string `...(전체 11개)`. Fourteen fields across
  four endpoints - nine distinct names - widen to their declared scalar
  type; a list the manual's own
  description outsizes is no longer read as an enum.
- A discriminated payload no longer rejects the documented values the manual
  gives no table for. `FloorLoadPayload` accepted only `FLOOR_DIST_TYPE` 1 and
  2 while `/db/FBLA` documents 1 to 4, so Polygon-Centroid and Polygon-Length
  were untypeable; `SkewPayload` lost `iMETHOD: 1` (Angle) and
  `MovingLoadCaseBsPayload` lost every load model but `"STANDER"`. Each union
  now carries a trailing member for the remaining values, which still denies
  the other branches' fields, so setting `LOAD_ANGLE` under `FLOOR_DIST_TYPE:
  3` remains an error. A union stays closed only where the contract proves it:
  a declared `enum` the branches cover exactly, or both values of a boolean.
  This widens 10 of the 13 generated union payloads; the remaining three -
  `NodalBodyForcePayload`, `MovingLoadCaseChinaPayload` and
  `EigenvalueAnalysisControlHyperSPayload` - stay closed because the
  contract proves they are. Code that relied on
  exhaustiveness narrowing over one of those discriminators needs a default
  case; nothing that compiled before stops compiling.

### Changed

- Generated payload declarations use 18 more reviewed endpoint contracts
  (319 to 337, counted from what 2.7.3 shipped). `/db/SSEIS`, `/db/SWIND` and
  `/db/TDNA` become discriminated unions on `PERIOD_METHOD`/`SEIS_CODE`,
  `INPUT_METHOD`/`WIND_CODE` and `SHAPE`/`INPUT`+`CURVE`; `/db/ELEM` and
  `/db/MVLD` keep their reviewed fallback payloads, because each has manual
  tables no discriminator could merge. **253 of the 750 generated payload
  types** now come from a contract, and 268 of the 304 resources have one.
  The 2.7.2 and 2.7.3 entries stated that first count against the resource
  count, which is the wrong denominator - resources sharing one payload type
  name collapse into a single type.
- `/db/FIMP` stays on its reviewed fallback. Its manual table keys rows
  `"KENPAR"."FC"` and omits the `CONC`/`STEEL` parents, so a contract drafted
  from it declared a three-level object as ten flat top-level fields.

## 2.7.3 - 2026-08-31

### Compatibility — breaking

- `FloorLoadPayload` (`/db/FBLA`) was a flat `interface` with every member
  optional and is now a **discriminated union** on `FLOOR_DIST_TYPE`, with
  `FLOOR_LOAD_TYPE_NAME`, `FLOOR_DIST_TYPE` and `NODES` required. Omitting one
  of those three, `extends`-ing the payload, or setting fields the manual
  documents under different `FLOOR_DIST_TYPE` values now fails typechecking.
  No runtime behaviour changed and no runtime validation was added.

### Changed

- Generated payload declarations use 10 more reviewed endpoint contracts
  (309 → 319): `/db/FBLA` and the nine `/doc/*` endpoints. 252 of the 304
  generated resources now take their facts from a contract rather than the
  reviewed Python fallback.
- Conditional variants are generated from the contract's `when` conditions,
  which now carry a dotted path and may name several documented values. A table
  the manual shares between branches contributes its fields to each of them
  rather than forming a union member that would match the same discriminator
  twice.

## 2.7.2 - 2026-08-31

### Changed

- Generated payload declarations now use **30 additional reviewed endpoint
  contracts** (279 to 309 since 2.7.1), including their documented nested
  shapes, requirements and enum values. 251 of the 304 generated resources now
  take their facts from a contract rather than the reviewed Python fallback.
- Resource metadata retains the manual's labels and punctuation for the
  reviewed analysis-control and seismic-device resources.
- Adds maintainer-only live CRUD and analysis harnesses that make a verified
  checkpoint before dependent scratch-model cases.

### Compatibility

- The newly contracted payload declarations are more specific. Existing
  TypeScript calls that supplied incomplete or incorrectly shaped payloads may
  now fail typechecking; no general runtime payload validation was added.

## 2.7.1 - 2026-08-30

### Added

- Result-table wrappers for the analysis, story and design-force tables,
  generated from reviewed table contracts.

### Changed

- Payload types for the newly contracted endpoints are generated from
  `contracts/` rather than from the reviewed Python model.
- Resource metadata follows three same-day manual revisions: corrected English
  labels for the design chapters, and `/db/POLC-M1` regaining `POST` after a
  live Civil NX call disproved the chapter that denies it.

### Compatibility

- `EigenvalueAnalysisControlPayload`,
  `EigenvalueAnalysisControlHyperSPayload`,
  `NonlinearAnalysisControlDataPayload` and `SkewPayload` are now declared as
  type aliases rather than interfaces. Names, namespaces and members are
  unchanged, so assigning and reading them is unaffected; code that `extends`
  one of them, or relies on declaration merging, needs updating.
- `resources.db.pushover.pushoverLoadCaseHyperS` accepts `create()` again.

## 2.7.0 - 2026-08-28

### Added

- `/db/BODF` (Self-Weight) now has a reviewed language-neutral contract. Its
  generated npm payload requires `LCNAME` and documents the self-weight factor
  vector.

### Changed

- Contracted fixed-length arrays now generate TypeScript tuples. This preserves
  documented array lengths at compile time rather than widening every vector to
  `Array<number>`.

### Compatibility

- `resources.db.staticLoads.selfWeight` now requires `LCNAME`, and its `FV`
  value must contain exactly three numbers. This corrects the published type to
  the documented request shape; existing TypeScript calls that omitted the load
  case name or supplied a non-three-value vector need updating.

## 2.6.1 - 2026-08-28

### Fixed

- Generated operation wrappers now carry the reviewed Gen NX/Civil NX product
  support from `docs/coverage.json`. Calling a Gen-only operation such as
  `operations.ope.getStoryCheckParameter()` with a Civil client now rejects
  with `ProductMismatchError` before sending a request that would return 404.
- Product-mismatch failures from operation wrappers are Promise rejections,
  consistent with their declared async API.

## 2.6.0 - 2026-08-28

### Breaking

> Released as a **minor** bump, at the author's decision, to keep the npm and
> PyPI version numbers aligned. If your code reads `metadata.pythonModule` or an
> operation's `pythonModule`/`pythonFunction`, it will stop compiling on this
> upgrade even though the number does not say so.

- `DbResourceMetadata.pythonModule` and `OperationMetadata.pythonModule` /
  `pythonFunction` are gone. The npm package was shipping the PyPI package's
  module paths (`"midas_nx.db.static_loads"`) to JavaScript users - nothing a
  caller could act on, and a standing advertisement that one language surface
  was generated from the other. `DbResourceMetadata` gains an optional
  `manualChapter` instead, naming the official manual chapter that documents the
  endpoint.

### Added

- `tableTypes` - every `TABLE_TYPE` value from `contracts/tables/*.yaml` as a
  named constant. Previously the npm package named only whichever value a table
  wrapper defaulted to, so variants like `REACTIONL` and
  `REACTIONSURFACESPRING` were reachable only by a caller who already knew they
  existed. The Python package has always named them.

### Changed

- Payload types for contracted endpoints are generated from `contracts/`
  rather than from the Python `TypedDict`s. This makes them more accurate, not
  merely differently sourced: the `TypedDict`s are all `total=False`, so every
  field they produced was optional regardless of what the manual said. Six
  endpoints so far - `/db/RIGD`'s `DOF` and `S_NODE` are now correctly required,
  and its `ITEMS` array carries its real element shape.

## 2.4.0 - 2026-08-27

### Fixed

- **`db.staticLoads.nodalMass` could crash a live MIDAS NX session.** Creating or
  updating a nodal mass without `rmX`/`rmY`/`rmZ` sent the payload to the product
  unchanged. Omitting those three fields has been observed to hang the call and
  end the NX session across both Gen NX and Civil NX; the Python package has
  filled them with their documented default of `0` since 2026-07-29, and this
  package shipped without that protection. `create()` and `update()` now apply the
  same defaults, without overriding any value the caller supplied.

### Added

- `DbResourceMetadata.payloadDefaults`, generated from the new language-neutral
  endpoint contracts in `contracts/`, so an endpoint's safety rules reach both the
  npm and PyPI packages instead of only whichever one they were written in. CI
  fails when either package stops honouring a contract.

## 2.3.4 - 2026-08-27

### Added

- Package-local changelog and an npm release checklist for the independent
  `js-v*` release stream.

### Changed

- Added separate npm trusted-publishing automation for `js-v*` GitHub
  Releases, independent from the Python `py-v*` release stream.

## 2.3.3 - 2026-08-26

### Changed

- Hardened destructive-operation safeguards and kept per-ID deletion
  deliberately sequential.
- Expanded result-table option types and generated operation/table typings.
- Propagated live-verification safety warnings into the published TypeScript
  declarations and added CI checks for those warnings.
- Added packed-artifact smoke tests for both CommonJS and ESM consumers on
  Node.js 18 and 22.

## 2.3.2 - 2026-08-26

### Added

- Initial typed JavaScript/TypeScript SDK for MIDAS Civil NX and MIDAS Gen NX.
- Generated DB resources, operations, result-table wrappers, and payload types
  from the reviewed Python endpoint inventory.
- ESM, CommonJS, and TypeScript declaration outputs.
- Client, document, operation, table, error, and safety APIs with Vitest and
  TypeScript validation.
