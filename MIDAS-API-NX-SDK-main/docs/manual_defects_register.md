# Manual defects register

A running record of places where `E:\AI Study\MIDAS-API` (or the MIDASIT
official article it transcribes) disagrees with what the product actually does.

**This file collects; it does not act.** Nothing here has been applied to the
manual repository, sent to MIDASIT, or filed in Jira. Those are the author's
calls. `docs/vendor_report_triage.md` is the counterpart for findings about the
**product** rather than the documentation, and records which of them are in the
vendor report and which are held back; several findings are both, and then each
file carries its own half. Do not edit the manual repo from this repository, and do not open a Jira
issue about any of these without an explicit go-ahead.

**How to add an entry.** When live evidence contradicts the manual, append a row
here in the same commit that records the evidence in
`docs/live_verification_notes.md`. Give it the next `MD-nn` id, and say which
side owns the correction — the manual repo can rewrite its own transcription,
but only MIDASIT can fix its own article. If the disagreement also affects a
contract, the manual's claim goes under `manualDefects` and the product's
behaviour under `contracts/verification/`, separately, as
`contracts/README.md` requires.

Session baseline for every 2026-08-31 entry: MIDAS Gen NX 2026 v2.1 and MIDAS
Civil NX 2026 v2.2, both build 08/26/2026.

The 2026-09-03 entries (MD-14 through MD-17) were found on the build that
preceded the 09/02/2026 patch, which was installed part-way through that same
day. The build they ran on is not recorded, because the API does not report one
and nobody read the About dialog before the patch went on - see
docs/live_verification_notes.md. A GET-only sweep from each SDK immediately
after the patch (282 of 282 on Civil NX v2.2, 267 of 267 on Gen NX v2.1, both
build 09/02/2026) found no route changed, so nothing in these entries is
known to be patch-specific. **MD-14 has since been re-measured on the patched
build itself** and is no longer resting on an unrecorded one.

## Register

| id | found | endpoint / topic | manual says | product does | correction owned by | status |
| --- | --- | --- | --- | --- | --- | --- |
| MD-01 | 2026-08-30 | `/db/STYP-M1` `DELETE` | `02_DB_Project_Structure.md` declares GET, PUT, DELETE in three places | all three DELETE forms refused on both products, from a non-default state with a model open | **MIDASIT article** (`activeMethods`); the manual repo repeats it | open |
| MD-02 | 2026-08-30 | `/db/POLC-M1` POST | the `14_DB_Pushover.md` ⚠️ callout says POST is not served and the article's row is an untrimmed template | POST created a record that the next GET returned | **manual repo** (its own callout) | open |
| MD-03 | 2026-08-31 | `/db/MATL-M1` structure | `04_DB_Properties.md:239` — same base material structure as `/db/MATL`, plus Hyperelastic support | different top-level names (`MATL_NAME`/`MATL_TYPE`), four fields against `/db/MATL`'s nine, and the `HE_*` fields are on the parent instead | **MIDASIT article** note | open |
| MD-04 | 2026-08-31 | `/db/IEHC` `WAreaSize` | the Specifications table types it Integer | Gen `/info` types it `string`; the chapter's own Request Example sends `"AUTO"` | **manual repo** transcription | open |
| MD-05 | 2026-08-31 | model file extensions | the manual's examples still show pre-NX spellings | four extensions in two pairs: pre-NX `.mgb`/`.mcb`, NX `.mgbx`/`.mcbz`. Civil NX's own Export menu lists "MCBZ File" | **manual repo** | open |
| MD-06 | 2026-08-31 | `/db/ELEM` `TYPE: "WALL"` on Civil | `03_DB_Node_Element.md` supplies a WALL-element request example for the shared Node/Element chapter | Gen accepted the manual-shaped WALL element; Civil NX v2.2 (08/26/2026) returned the quoted unsupported-type error below | **MIDASIT product/article** (support scope must be clarified) | open |
| MD-07 | 2026-09-01 | `/db/FIMP` Kent & Park table | `04_DB_Properties.md:2103` keys the rows `"KENPAR"."FC"` and omits `CONC`/`STEEL` from Specifications entirely | the same article's Request Body nests them `CONC` > `KENPAR` > `FC`, three levels deep | **manual repo** transcription | open |
| MD-08 | 2026-09-01 | `/db/CO_S`, `/db/CO_T` Specifications | one row keyed `"W_R" ~ "HE_B"` for No. `1-9` | the same section's JSON Schema and Request Example both list nine separate colour components, as `/db/CO_M`'s table does individually | **manual repo** transcription | open |
| MD-09 | 2026-09-01 | `/DESIGN/RC/.../DCRM-*`, `/DESIGN/SRC/AIK-SRC2K/LLRF` | the JSON Schema `enum` lists 5 rebar sizes and 6 reduction factors | the same rows' descriptions say `19종 (D4 ~ D57)` and `가능값 11개`; LLRF's list carries the literal member `...(전체 11개)` | **manual repo** transcription | open |
| MD-10 | 2026-09-01 | four sections' Specifications tables | the table omits a root property the same section's JSON Schema declares | `/db/EPMT` (6 model objects) and `/db/ELEM` (`C_RAT`, `LCAXIS`) reconciled 2026-09-02; `/db/FIMP` and `/db/RCHK` still drafts. Five more turned out to be this SDK's parser, not the manual - see the detail | **manual repo** transcription (4 of the original 9) | 2 reconciled, 2 open |
| MD-11 | 2026-09-02 | nine parameter rows' Value Type | the Specifications table's Value Type cell | the same section's own JSON Schema types the property differently. Seven are integer/number width; two change the shape of the value - `/db/SBDO` `AXIS_VECTOR` (Number vs an array of numbers, and its own Request Example sends six) and `/db/MATL` `PARAM` (Object vs array) | **manual repo** transcription | `/db/SBDO` and `/db/MATL` corrected in their contracts; 7 open |
| MD-12 | 2026-09-02 | seven Hyper-S `-M1` sections, and the `/info` schema that substitutes for them | the section gives a URL, a methods line and a Zendesk link - no Specifications table and no JSON Schema, so live `/info` is the only permitted contract source | `/info` serves a full schema for four of them and 404s for three, and the schemas it serves are malformed twice over: every apostrophe in a `description` is escaped `\'`, which is not a JSON escape, and `maxItems` is stated on an array's `items` subschema instead of the array | **MIDASIT product** (`/info` output) and **MIDASIT article** (the missing section content) | open |
| MD-13 | 2026-09-02 | `/db/TDME` `"SCALE"` | the Specifications table gives the key `"SCALE"` to two different rows - "Scale Factor" (Number) and "Function Data" (Array[Object] of `{TIME, COMP, TENS, ELAST}`) | unknown; the section has no Request Example that sends either, so which row owns the name cannot be read from the chapter. The vendored manual flags this itself in a ⚠️ callout and transcribes both verbatim | **MIDASIT article** (the duplicate is in the source) | **answered 2026-09-02**: `/info` names the array `aDATA`; row 6's key is wrong |
| MD-14 | 2026-09-03 | `/db/TDME` `CODENAME` `Japan(hydration)` / `Japan(elastic)` | `04_DB_Properties.md` lists both in its `CODENAME` code table (entries 16 and 17), each with its own table of required extra fields, and marks neither as belonging to a different product | both answer `Wrong Field` on Gen NX and Civil NX - **correctly**: these two codes are iGen's, and the NX API is not talking to iGen | **manual repo** - the code table needs to say which entries are not available through this API | open; re-measured 2026-09-03 on build 09/02/2026, both products |
| MD-15 | 2026-09-03 | `Create Only`, in `/db/SECT` and `/db/SPFC` | the manual's only two `Create Only` cells, both a `CALC_OPT`, say the server honours the field on create and ignores it on modify | true of `/db/SECT` exactly; false of `/db/SPFC`, where `CALC_OPT: true` on a PUT rebuilds the spectrum. Separately, `/db/SPFC`'s KDS(41-17-00:2019) worked example is refused as printed - it omits `CALC_OPT` and supplies no `aFUNC` | **MIDASIT article** (one value used for two contracts, and an example that cannot run) | open |
| MD-16 | 2026-09-03 | `/db/MVHL` common Specifications table | `VEHICLE_TYPE_NAME` and `STANDARD_CODE` Required, `USER_LOAD_TYPE` Optional, with no reference to the branch | `VEHICLE_LOAD_NUM` selects the branch: `1` needs the type name, `2` needs neither it nor `STANDARD_CODE`, which is not required under either. `USER_LOAD_TYPE` is ignored on input. The chapter's own KSCE-LSD15 examples show the branch; the table that claims to cover every code does not mention it | **MIDASIT article** (the table), which the manual repo transcribes faithfully | open |
| MD-17 | 2026-09-03 | `/db/PRES` `DIRECTION`, and the section's own example | the Specifications row marks `DIRECTION` Optional with the default `"NORMAL"`, and the section's Python example assigns a PLATE + FACE load with that value | on a PLATE with `FACE_EDGE_TYPE: "FACE"` both the omission and `"NORMAL"` are refused with the same `(Item:Load Direction)` error. The same section's own availability matrix already marks Normal `-` for that pair, and its JSON request example sends `"LZ"` | **MIDASIT article** (the row, and one of its two examples) | open |
| MD-18 | 2026-09-03 | `/db/THGC-M1` `INIT_LOAD_TYPE` | the main Specifications table types it `Integer(enum)` and prints both options with the literal `0` - "0=비선형 정적 해석, 0=정적/시공단계 결과 가져오기" | the options are `0` and `1`; live `/info` describes the same field as "Initial Load Type (Perform NL Static:0, Import Static:1)". A duplicate literal is self-refuting rather than merely unverified - the row as printed cannot be followed at all | **manual repo** transcription (to be checked against the MIDASIT article) | open |
| MD-19 | 2026-09-03 | `/db/THGC-M1` `ITER_PARAM.LINE_SEARCH` children | the sub-parameter table marks all five Required - `OPT_USE`, `LINE_SEARCH_OPT`, `START_ITER_NO`, `MAX_LINE_SEARCH_ITER`, `LINE_SEARCH_TOL` | unmeasured. The same section's Python example sends `{"OPT_USE": False}` and omits the other four, so the chapter contradicts itself the way MD-16 describes | **manual repo** transcription | open, unmeasured |
| MD-20 | 2026-09-03 | `/db/THGC-M1` "ITER_PARAM 서브 파라미터" Key column | `NORM_CTRL`'s children are stated as a path on one row - "`DISP` → `{OPT_USE, VALUE}`", repeated for `FORCE` and `ENERGY` - and `LINE_SEARCH`'s five children follow as sibling rows marked only by a "-" in the 설명 column | read as printed the table yields a field named `{OPT_USE, VALUE}` and puts ten children beside the two parents that own them; the section's own Request Example nests all of them | **manual repo** transcription | open |
| MD-21 | 2026-09-03 | `/db/STCT-M1`, five Key cells and one table's destinations | row 5 is keyed `"bSDLE"` / `"vSDLE"`; TIME_DEP_CONTROL has `"bTTLE_ES"` / `"iTTLE_ES"`; NONL_CONTROL keys three sibling objects `"DISP"/"LOAD"/"WORK"` and states `ADVANCED`'s whole subtree as prose in one cell; the "나머지 객체" table puts each row's parent in an `Object` column and keys `"bTRUSS"` / `"bBEAM"` and `"OPT_USE"` / `"iSDOPT"` / `"SDCONST"` | each is a set of sibling properties, sent that way by the section's own Request Body; `/info` independently confirms `bSDLE` and `vSDLE` as two of sixteen root properties | **manual repo** transcription | open |
| MD-22 | 2026-09-03 | `/db/STCT-M1` `FINAL_STAGE` | the top-level Parameters table lists fourteen rows and none of them names a final-stage name | `GET /info/db/STCT-M1` declares sixteen root properties, and `FINAL_STAGE` (string, "Final Stage Name") is the one the table has no counterpart for - the field the table's own `bLAST_FINAL: false` "Other Stage" option has to be answered with | **manual repo** transcription | open |
| MD-23 | 2026-09-03 | `/db/THIS-M1` `FREQ1`/`PERIOD1` and `FREQ2`/`PERIOD2` | the `COEF_INPUT=1` damping table keys two wire properties in each of rows 3 and 5 | they are mutually exclusive, selected by `COEF_CALC` (0=Frequency, 1=Period) - the row directly above them - and each row's own description says so | **manual repo** transcription | open |
| MD-24 | 2026-09-04 | `/DESIGN/RC/KDS-41-20-2022/BRD-TABLE` and `CD-TABLE`, `ELEMS` / `SECTIONS` | both rows are marked 조건부 and no condition is stated anywhere in either section - not in the 설명 column, not in the section's own JSON Schema, which requires only `TABLE_TYPE` and carries no `if`/`then` | unknown, and deliberately left that way. The same chapter states this exact condition explicitly fifteen times elsewhere - `요소 번호 입력 (CREATE_SUB_SECTION=true 일 때 필수)`, with a matching `then: {required: ["ELEMS"]}` - so the omission is not a house style | **manual repo** transcription | superseded in part by MD-33 - the rejected paraphrase stands rejected, but the condition is stated elsewhere in the chapter and both contracts are now promoted |
| MD-25 | 2026-09-04 | `/db/MVLDeu` `OPT_COMB`, `STL_LIST`, `SUB_LOAD_LIST` | `OPT_COMB` is typed `String` in the row whose own description gives its values as `0`/`1`; `STL_LIST` and `SUB_LOAD_LIST` are typed `Array[Object]` with no member rows, their members named only inside the parent row's description | `OPT_COMB` is an integer - both Request Body examples send `"OPT_COMB": 1` unquoted; the two arrays carry exactly the members their descriptions number, and the examples send them literally | **manual repo** transcription | open |
| MD-26 | 2026-09-04 | `/db/REBR` `ID` and `ELEMS` | the 파라미터 table numbers the ITEMS item's members `(1)`-`(6)` and has a row for neither; the section's third table then lists four rows at two different levels without saying so | the section's own JSON Schema declares both on the ITEMS item and places `KEYS`/`TO`/`STRUCTURE_GROUP_NAME` inside `ELEMS`; chapter 26's REBC/REBR document the same two members as ordinary numbered rows | **manual repo** transcription | open |
| MD-27 | 2026-09-04 | `/db/RCHK`, five count fields | four 파라미터 tables type `dSUB_BARNUM`, `SUBBAR_NUM`, `SUBBAR_NUM_Y`, `SUBBAR_NUM_Z` Integer and `BAR_NUM` (under `vPOSITION`) Number; the section's own JSON Schema types the first four `number` and `BAR_NUM` `integer` - the opposite way round in every case | the schema is internally consistent, the tables are not: `BAR_NUM` is typed Integer in one table and Number in another for the same name and the same description | **manual repo** transcription | open |
| MD-28 | 2026-09-04 | `/ope/AUTOMESH` `MESH_SIZE`, `INCLUDE_INTERIOR_LINES` | rows 2-1/2-2 mark `LENGTH` and `DIV` both **Required** while each says the two cannot be used together, and type both Number where the schema says `integer`; row 1-6 declares `INCLUDE_INTERIOR_LINES` and lists none of its members | the two size fields are alternatives - each Request Example sends one; `DIV` is a count and `LENGTH` a model-unit length, so they do not resolve the same way; the missing members are the same three rows 1-5-a..c give, and the schema and second example both carry them | **manual repo** transcription | open |
| MD-29 | 2026-09-04 | `/DESIGN/RC/KDS-41-20-2022/REBB`, the whole item shape | the JSON Schema and 파라미터 tables give `MAIN_BAR_TOP`/`MAIN_BAR_BOT` as `{LAYER1, LAYER2}` objects, a `SKIN_BAR` object, and cover distances named `DT`/`DB`, and name no `bSAME_SIZE_*` field | the section's own Request Body, Response Body and Python example all send `vMAIN_BAR_TOP`/`vMAIN_BAR_BOT` arrays, flat `SKIN_BAR_NAME`/`SKIN_BAR_NUM`, `MAIN_BAR_DC_TOP`/`MAIN_BAR_DC_BOT` and three `bSAME_SIZE_*` booleans - and the section says outright to follow the examples | **manual repo** transcription | open |
| MD-30 | 2026-09-04 | `/DESIGN/RC/KDS-41-20-2022/REBR` `MAIN_BAR.NUM` | the JSON Schema writes the minimum as `"minItems": 4` on a field it types `integer` - a keyword that applies to arrays and does nothing here | the bound is 4 and the Parameters row states it in prose in the same section (철근 총 개수 (min 4)); transcribed as `minimum: 4`, and the chapter-24 sibling `/db/REBR` now carries the same | **manual repo** transcription | open |
| MD-31 | 2026-09-04 | `/DESIGN/RC/KDS-41-20-2022/TABLE` `NODE_ELEMS` | row 8 types it `Object (oneOf)` and lists none of its members | the section's JSON Schema declares `KEYS`, `TO` and `STRUCTURE_GROUP_NAME` under a `oneOf`, and the Request Body sends `{"KEYS": [915]}` | **manual repo** transcription | open |
| MD-32 | 2026-09-04 | `/DESIGN/SRC/AIK-SRC2K/OCHECK`, the route itself | section 21 prints `{base url}/DESIGN/SRC/AIK-SRC2K/OCHECK` as the Input URI and documents the endpoint like any other in the chapter | that path returns a clean 404; MIDASIT moved the route to `/TEMP/DESIGN/SRC/AIK-SRC2K/OCHECK` on 2026-08-06 to mark it unofficial with paused development, and the route that does answer ends the NX session on any model holding a section SRC design cannot use | **manual repo** transcription | open |
| MD-33 | 2026-09-04 | `/DESIGN/RC/KDS-41-20-2022/CD-TABLE` and `.../BRD-TABLE`, `ELEMS`/`SECTIONS` | both rows are marked 조건부 and neither states a condition; the sections' own JSON Schemas carry no branch keyword | the two are alternatives - exactly one of them - which chapter 26 states for the same field pair in seven of its nine BD/CD/BRD sections, in the row and in a schema `oneOf` | **manual repo** transcription | open |
| MD-34 | 2026-09-04 | `/db/REBR`, the whole item shape | each `ITEMS` entry has a single `MAIN_BAR` object, a top-level `DO`, a string `HOOP_TYPE` defaulting to `"Ties"`, and an optional `CREATE_SUB_SECTION` with `ELEMS` | `GET /info/db/REBR` declares `vMAIN_BAR`, an array whose entries each carry `D0` (a zero), an integer `HOOP_TYPE` (1=Tied, 2=Spiral), and no `CREATE_SUB_SECTION` or `ELEMS` at all - field for field the shape `/db/REBC` was found to have on 2026-08-27 | **manual repo** transcription | open |
| MD-35 | 2026-09-04 | all six `/db/LCOM-*`, four fields | the chapter's "LCOM 타입별 비교 요약" table gives five of the six an em dash under 추가 필드 and gives `LCOM-CONC` only `bES`; no Parameters row names `iSERV_TYPE`, `nLCOMTYPE` or `nSEISTYPE` anywhere | `GET /info/db/LCOM-*` declares all four on all six, on both products | **manual repo** transcription | open |
| MD-36 | 2026-09-04 | `/db/LCOM-*` and `/db/POGD`, member rows | rows written `| — | (vCOMB) ... |` and `| — | (INITLOAD) ... |` name their parent in the Description cell and leave the No. column an em dash | they are members of that array; the contracts published `ANAL`/`LCNAME`/`FACTOR` and `LC_NAME`/`LC_TYPE`/`SF` as siblings of the array containing them | **this SDK** extractor | fixed |
| MD-37 | 2026-09-04 | `/db/POGD-M1` `ANALYSIS_STOP`, four claims | `AXIAL_YIELD.BEAM`, `SUPPORT_DZ_DIR.UPLIFT`, a `WALL` in both stop groups, and a `SYMMETRIC` marked Required in `PO_HINGE_OPT.BILINEAR`/`.TRILINEAR` | `GET /info/db/POGD-M1` declares `BEAM_COLUMN` and `UPLIFTING` for the first two - and the manual is its own second witness on `BEAM_COLUMN`, which it uses four rows earlier for the same checkbox in the sibling `SHEAR_YIELD` group. `WALL` and `SYMMETRIC` it declares nowhere; both are kept, see below | **manual repo** transcription | partly fixed |
| MD-38 | 2026-09-04 | `/db/STRPSSM` `POINT1`/`POINT2` entries | each entry is `{"PY": ..., "PZ": ...}`, in the Specifications rows and the Request Example alike | `GET /info/db/STRPSSM` declares `{"Y": ..., "Z": ...}` and gives those two properties the descriptions `"PY"` and `"PZ"` - the section read the description as the key | **manual repo** transcription | open |
| MD-39 | 2026-09-04 | `/db/STOR` `STORY_AREA_ITEMS` | the section's JSON Schema, Request Example and Specifications table all give fifteen properties and stop | there is a sixteenth, an array of `{X, Y, Z}` factors. The manual documents it - in chapter 15, where `/ope/STOR`'s POST response is the same record field for field with this array added and the prose names it | **manual repo** transcription | open |
| MD-40 | 2026-09-04 | `/db/RPSC` `MBAR_ITEMS` | row 5 puts it at the root beside `SBAR_ITEMS` (row 4), the two described identically | `GET /info/db/RPSC` has `SBAR_ITEMS` at the root as documented and `MBAR_ITEMS` one level down, inside an array named `MBARS` the section never mentions. The pair really is asymmetric | **manual repo** transcription | open |
| MD-41 | 2026-09-04 | nine `/db/*` sections, fifteen fields | each section's Specifications table (and, where it has one, its JSON Schema) presents a complete field list | `GET /info` declares one to six more on each: `/db/BMLD` `ITEMS.VX/VY/VZ`, `/db/HPCE` `START_STAGE`/`END_STAGE`, `/db/PJCF`'s five model-file properties, `/db/RCHK` `BEAM.OPTION_IMJSAME`, `/db/SDVE` and `/db/SDHY` `COMMON`'s six members, `/db/STAG` `NO`, `/db/TDMF` `ELAST`, `/db/TDNT` `bRELAX`. Three of the fifteen were already known - `STAG.NO` and `TDNT.bRELAX` from real models on 2026-07-30, `HPCE`'s pair from /info on 2026-08-17 - and had reached `src/midas_nx/` but never `contracts/` | **manual repo** transcription, except `/db/SDVE` and `/db/SDHY` where the manual defers to `/db/SDVI`'s table and **this SDK**'s extractor cannot follow a cross-reference | open |
| MD-42 | 2026-09-04 | `/db/GRDP` `GROUP_DAMPING_ITEMS[]`, fifteen members | one sentence under the Specifications tables says the array overrides rows 7-18 per group using "`_DEFAULT` 접미사만 빠진 이름", then lists all fifteen - in prose, not a table row | the members are real and the manual is right about every one of them; `GET /info/db/GRDP` declares exactly those fifteen on both products. `scripts/extract_contracts.py` reads tables, so the contract shipped the array with no members and npm published `Array<JsonObject>` | **this SDK** extractor | fixed |
| MD-43 | 2026-09-04 | `/db/SLANch`, the whole record | section 8's only Parameters table is headed "Parameters - LANE_ITEMS" and gives three rows: `NODE`, `OFFSET`, `SPAN_LENGTH` | those three are members of the `LANE_ITEMS` array. The record's own eight fields appear only in the Request Example and the Python example, with no Specifications row anywhere, and `/info` declares a ninth, `SEQ`. The sibling `/db/SLAN` one section earlier tables all nine properly | **manual repo** transcription | open |
| MD-44 | 2026-09-04 | five arrays and one object across `/db/SLAN`, `/db/POLC`, `/db/ACTL-M1`, `/db/NLNK`, `/db/NLNK-M1` | each states its members somewhere other than a numbered table row - a per-code table, a per-branch table, a sub-table heading naming three children, a sentence | the members are real and the manual is right about every one of them; the extractor reads numbered table rows and read none of these | **this SDK** extractor | fixed |
| MD-45 | 2026-09-04 | `/db/LLANtr` `SPECIAL_LANE_ITEMS`, `/db/SLANop` `OPT_STRADD` and `CHINA_ITEMS` | neither section documents them | `GET /info` declares them on both endpoints. `SPECIAL_LANE_ITEMS` carries the server's own description " Used only when importing", which is the whole of what is known about when it applies; `CHINA_ITEMS` has no description at all, only its members' | **manual repo** transcription | open |
| MD-46 | 2026-09-04 | ten `/db/*` sections, 73 fields | each documents one endpoint with one Specifications table and says nothing about either product | the two products declare different records. `/db/SPLC` differs by 15 fields, `/db/POSL` by 11, `/db/POGD` by 20, `/db/SBDO` by 16, `/db/IEHC` by 9, and `/db/ACTL`, `/db/BCCT`, `/db/EPSE`, `/db/POLC`, `/db/THGC` by one to four each. Mostly it is the products' own feature sets - Gen NX has walls and fiber hinges, Civil NX has bridge seismic parameters - not a transcription slip | **manual repo** transcription | open |
| MD-47 | 2026-09-04 | `/db/TDMT` `TCODE` and `bSILICA` | section 6's "Specifications (공통 키 + CEB-FIP)" table documents two code branches, CEB-FIP and ACI, while its `CODE` value table lists 33 codes | `CODE="EUROPEAN"` is a third branch with two dedicated fields the table names nowhere. Both were read off a real PSC bridge model's C40/50 concrete on 2026-07-30 and both are declared by `GET /info/db/TDMT` on either product. The gap is wider than these two: /info declares roughly seventy fields here, spanning codes the value table lists and the field table then ignores | **manual repo** transcription | open |
| MD-48 | 2026-09-04 | `/db/MVHL` `VEH_EUROCODE`, 48 fields | section 10's Specifications table documents `VEH_DEFAULT` and no country object at all | `GET /info/db/MVHL` declares eleven more - `VEH_FR`, `VEH_CN`, `VEH_IN`, `VEH_CA`, `VEH_BS`, `VEH_EUROCODE`, `VEH_RU`, `VEH_KSCE_LSD15`, `VEH_AU`, `VEH_PL`, `VEH_ZA` - and a real Eurocode "Load Model 1" vehicle read on 2026-07-30 used `VEH_EUROCODE` instead of `VEH_DEFAULT`, omitting `STANDARD_CODE` the table marks Required. Four of the eleven have their own manual tables; `VEH_EUROCODE` has none | **manual repo** transcription | open |
| MD-49 | 2026-09-04 | `/post/TABLE` surface-spring reaction `TABLE_TYPE` | the JSON Schema and Specifications table give `REACTIONSURFACESPRING`; the Request Example alone gives `REACTIONLSURFACESPRING` | on both Gen NX and Civil NX, build 09/02/2026, `REACTIONSURFACESPRING` is refused with `there was an error creating utbl`, while `REACTIONLSURFACESPRING` is recognised and reaches the expected no-analysis-result response | **MIDASIT article** (schema and table), which this SDK followed into both packages | open upstream; corrected here |
| MD-50 | 2026-09-05 | `/db/MVCTch` `FREQ`, `BRIDGE1.BTYPE`, `BRIDGE2.BTYPE`, 9 fields | section 10 documents all of them - `FREQ`'s 25 keys across a two-Key-column table, and each `BTYPE` in the bold sentence that introduces its field table, enum included | this repo read neither. Every key in the `FREQ` table's *second* Key column was dropped whole (`SBEM_L`/`E`/`IC`/`MC`, `iARCH_TYPE`, `CABL_A`/`CABL_L`) while the first column extracted correctly, packed cells included - so it is a table shape the parser reads half of, not MD-48's packed cell. `BTYPE` is the selector deciding which of its table's fields apply, so neither object was usable without it | **this SDK** extractor | fixed here; parser deliberately unfixed (one such table in the whole manual) and guarded by a CI count |
| MD-51 | 2026-09-06 | `/ope/MEMB` `SELECTION_TYPE` | the official Specifications table's row 2 gives the key as `"SELETION_TYPE"`, missing a C | both of the same article's own Input JSON examples send `"SELECTION_TYPE"`, and that is what the server accepts. Found while re-verifying the neighbouring `ELEM_LIST` claim against the raw article (`49514964272665`, `updated_at` 2026-07-30); our vendored copy had normalised the spelling, so nothing here had ever surfaced it | **MIDASIT article** (table only) | open upstream; already correct here and in the vendored manual |
| MD-52 | 2026-09-06 | `/ope/MEMB` request example, `ko` vs `en-us` | the **same article id** `49514964272665`, with the **same `updated_at`**, serves a different Input JSON example per locale: `ko` sends `"AELEM": [1, 2]`, `en-us` sends `"ELEM_LIST": [640, 692]`. Both locales' Specifications tables say `ELEM_LIST` | live on both products, `ELEM_LIST` assigns the member and `AELEM` is not read at all - byte-identical to sending no element list - so the `ko` example is the wrong one. `AELEM` is the response key, and separately the request key of the neighbouring `/db/MEMB` | **MIDASIT article** (`ko` locale) | open upstream; the vendored manual carries the correct `ELEM_LIST` |
| MD-53 | 2026-09-12 | `/db/MATD` rebar grade example | section 9's Request Body names the grades `REBAR_CODENAME="EN04(RC)"`, `MAINREBAR_REBARNAME="ClassB"`, `SUBREBAR_REBARNAME="ClassC"` and prints the yield strengths beside them as if the named grades supplied them | both products answer `Rebar grade lookup failed` for that pair through both SDKs. Dropping the strengths instead answers `MAINREBAR_B_FY must be > 0`, so they are required input rather than a consequence of the grade. A PUT carrying the model's own `KS01(RC)`/`C24` identity with positive strengths completes on both | **MIDASIT article** example | open |
| MD-54 | 2026-09-14 | `/db/FIMP` Kent & Park example | section 28's complete Request Body prints `ECU=0.003`, `Z=100` and `EC0=0.002`, and the chapter's second example repeats the same three values | all four POSTs - two SDKs times two products - are refused with `Epsilon_cu > 0.8 / Z + Epsilon_co`. The printed values do not satisfy the product's own stated relationship, and the chapter offers no compliant alternative anywhere | **MIDASIT article** example | open |
| MD-55 | 2026-09-14 | `/db/TDMF` Creep example | section 5 prints a Creep Request Body (`FTYPE="CREEP"` with `CTYPE`) as a worked example | both products answer `Wrong Field` for it. `/info/db/TDMF` additionally declares an `ELAST` the chapter never mentions, with no documented values or request semantics, so no substitute is derivable from a permitted source | **MIDASIT article** example | open |
| MD-56 | 2026-09-14 | `/db/EPMT` on Civil NX | section 10 documents one payload with no product qualifier | Gen completes the Von-Mises Request Body end to end through both SDKs; Civil answers `Wrong Field` for the identical POST, although `GET /info/db/EPMT` declares the same field shape on both products | **MIDASIT** (article or product) | open |
| MD-57 | 2026-09-22 | `/db/SPLC` rows 25-29 and `NDP` | the accidental-eccentricity table marks `bACCECC_AUTO`, `ACCECC_PERCENT`, `bACCECC_CONSIDER_GL`, `bACCECC_MINIMUM_TORSION` and `aACCECC_ECCEN_LIST` Required, and the non-dissipative table marks `NDP` Required, each directly under the Boolean that turns its feature on and with no condition | none is required. A confirmed round trip omits all six with the switches at their defaults; on Gen NX, `bACCECC: true` without rows 25-29 is accepted and reads back with three of them supplied by the server, and `bNDP: true` without `NDP` is accepted (though neither `bNDP` nor `NDP` is read back either way) | **manual repo** as vendored; the official article (`35963719599641`) was not re-read for this, so which of the two carries it is unestablished | open |
| MD-58 | 2026-09-22 | `/db/STCT` `vSDLE` | the Erection Load table marks row 9, `vSDLE` (Grid Analysis Load, JP edition only), Required with no condition, directly under row 8's `bSDLE` (default false); the same chapter's `/db/STCT-M1` section marks the pair Optional | a record without `bSDLE` and `vSDLE` is accepted on both products - a POST on Gen NX, a PUT on the stage-created record on Civil NX (2026-08-17, re-tested 2026-09-01) - so it is not required while `bSDLE` is off. What `bSDLE: true` needs on the JP edition is unmeasured | **manual repo** as vendored; the official article (`35990281053465`) was not re-read for this | open |
| MD-59 | 2026-09-22 | `/db/ELEM` per-type tables | Plate and Plane Stress mark `STYPE` Required, Cable marks `CABLE` and `NON_LEN` Required, Wall marks `W_CON` Required, and the section lists `WALL` among ten element types with no product qualifier | all four rows are optional on both products: `STYPE` reads back 1, `CABLE` 3 and `NON_LEN` 3.2, and the section's own Cable example omits `NON_LEN`. `W_CON` is accepted and never returned, and `/info` declares it nowhere. Civil NX refuses every `WALL` record as an unsupported element type. `STYPE` is required for TENSTR, COMPTR and WALL, and `WALL` for WALL | **manual repo** as vendored; the official article (`35806934300825`) was not re-read for this | open |
| MD-60 | 2026-09-22 | `/db/SPFC` EURO2004 | the EURO2004 table places `SPECTYPE`, `GROUTYPE` and `NATIONALANNEX` in `OPT`, and its Request Body sends them there with `VAL.ag` | that body answers `Unknown Error` on both products, and so does it with `OPT` removed, with `VAL.AG`, and with both. `GET /info` declares the three in `STR` as strings. Every other design-code example in the section is stored as sent | **manual repo** as vendored; the official article was not re-read for this | open |
| MD-61 | 2026-09-22 | `/db/MVHL` country tables | each country table's heading names the `STANDARD_CODE` that selects its object - `"KSCE-LSD15"`, `"CANADA"`, `"AUSTRALIA"`, `"NA"`/`"NB"`/`"NC"` - and the China and Poland headings defer the values to the official article | the record's `MVLD_CODE` selects the object: both user-defined bodies send no `STANDARD_CODE` and store their objects, `"AUSTRALIA"` answers `Wrong Field` where the Australia body's own `"ROAD TRAFFIC"` stores, and `"NA"` answers `Wrong Field`. A record whose `MVLD_CODE` is not the model's `/db/MVCD` code answers `{"message": ""}` and stores nothing, and the Poland body stored nothing under any code | **manual repo** as vendored; the official articles were not re-read for this | open |
| MD-62 | 2026-09-22 | `/ope/DIVIDEELEM` Unequal and ParametricUnequal rows | `DIST_X/Y/Z` and `RATIO_X/Y/Z` are marked Required with no condition, beside the Equal row that states the axes per element type (Frame=X만, Planar=X,Y, Wall=X,Z, Solid=X,Y,Z) | the Equal row's axes hold for both: a Frame divides with `DIST_X` or `RATIO_X` alone, and a Planar element answers `Unknown Error` to `RATIO_X` alone and divides with X and Y; identical on both products | **manual repo** as vendored; the official article was not re-read for this | open |

## Detail

### MD-01 — `/db/STYP-M1` DELETE

The manual names DELETE in its endpoint methods and other chapter locations.
Live checks against both products refused the bare DELETE body forms and the
per-id route while a real model was open. This is a product-capability finding,
not a request-wrapper inference. Keep the endpoint's documented GET/PUT facts
separate from the disproven DELETE claim.

Recorded in the SDK as a `manualDefects` entry with `describes: method`;
`StructureTypeHyperS` keeps `_GET_PUT_ONLY`.

### MD-02 — `/db/POLC-M1` POST

The manual-repo warning is more restrictive than the product. A live POST
created a record and a following GET returned it. The proposed correction is
not to invent a payload schema: only to stop claiming that POST is absent.

No evidence establishes that the official article makes the same claim, so this
one is the manual repo's own to fix.

### MD-03 — `/db/MATL-M1` structure

The Hyper-S endpoint cannot safely inherit `/db/MATL`'s fields:

```text
/db/MATL     9 props: NAME, TYPE, PARAM, DAMP_RAT, HE_COND, HE_SPEC, PLMT, P_NAME, bMASS_DENS
/db/MATL-M1  4 props: MATL_NAME, MATL_TYPE, PARAM, DAMP_RAT
```

Beyond the different top-level names and count, `PARAM[].P_TYPE` is 0-based and
user-defined material values are nested under `USER_DEFINED`, whereas
`/db/MATL` uses a different, flatter parameter shape. The `HE_*` fields — the
ones that look like the Hyperelastic support the note claims is exclusive to
MATL-M1 — are on the parent and absent from MATL-M1.

The wording is therefore not a harmless abbreviation. It directs a reader to a
wrong wire contract, and copying the parent's fields would have produced a
contract whose every top-level name is wrong. This is the `/db/REBW` class of
defect: a section wrong about its own endpoint's field names.

### MD-04 — `/db/IEHC` `WAreaSize`

Recorded in the SDK as a `manualDefects` entry plus a Gen verification record.
The contract keeps the manual's `integer` rather than silently substituting the
live `string`, so a reader sees both claims and decides. Its sibling
`WAreaSizeCover` really is `integer` live, so this is one field, not the table.

### MD-05 — model file extensions

Four extensions, two pairs, and this repository got Civil's wrong twice before
landing on it — once as `.mcbx`, once over-corrected to `.mcb`:

| | Gen | Civil |
| --- | --- | --- |
| pre-NX | `.mgb` | `.mcb` |
| **NX** | **`.mgbx`** | **`.mcbz`** |

`/doc/STAGAS` is a real exception that wants the legacy `.mcb` and rejects
other spellings ("Please check the file name or extension"). Civil also
*tolerates* `.mcbx` for `SAVEAS` — a 2026-07 round trip wrote one and reopened
it with all 273 nodes — which is exactly why a wrong spelling survived a live
run without complaint. Being accepted is not being native.

The Export menus also differ by product in a way the manual does not state:
Civil NX offers MCT and an "MCBZ File"; Gen NX offers MGTX/MGT variants and no
MGBX. Both offer a product-named JSON export, which is `/doc/EXPORT`.

### MD-06 — `/db/ELEM` `TYPE: "WALL"` on Civil

The manual's element example uses `TYPE: "WALL"`, material 1, thickness/section
1, node order `[1, 2, 4, 3]`, `STYPE: 1`, `WALL: 1`, `W_CON: 0`, and
`W_TYPE: 0`. On a disposable rectangular model, Gen NX accepted that request.
Under the same shape and ids, Civil NX 2026 v2.2 build 08/26/2026 returned:

> `[Error] Unable to add/modify the element. The element type no. 5 for the element no. 4 is not supported.`

The manual's one-based type table says 5 is `PLATE` and 6 is `WALL`; that is
inconsistent with the server's displayed 5. A zero-based internal sequence
would label `WALL` as 5 and is therefore consistent with the message, while
the manual's displayed numbering is not. This is only a numbering observation,
not evidence deciding Civil's WALL-element support scope.

This is not a claim that a PLATE is semantically interchangeable with a WALL.
The separate `/db/WMAK` check merely established that its existing fixture
round-trips when its `WID_LIST` references an actual PLATE on both products.
No endpoint contract was changed: the evidence is insufficient to replace the
manual's element-type statement or to infer product-specific WMAK semantics.

### MD-07 - `/db/FIMP` Kent & Park parameter table

The Specifications table for the Kent & Park hysteresis model keys its rows
`"KENPAR"."FC"`, `"KENPAR"."PARTIAL_FACT"` and so on - a parent and a child,
with no row for the parent itself - while `CONC` and `STEEL` appear only in the
chapter's JSON Schema block and never in a Specifications table. The request
example in the same article shows the real shape:

```json
{"NAME": "Conc_Kent&Park", "MATL_TYPE": "CONC", "HYS_MODEL": "KPM",
 "CONC": {"KENPAR": {"FC": 30000, "PARTIAL_FACT": 1.0}}}
```

Read as a table of wire keys, the section therefore states a three-level object
as ten flat top-level fields. A contract drafted from it said exactly that, so
`/db/FIMP` is listed in `promote_contract.py`'s `NEEDS_HAND_REVIEW` and stays
on its reviewed Python fallback, whose `CONC`/`STEEL` objects are correct.

The chapter's own callout says this repository documents Kent & Park alone as
a representative of a 5,900-line article covering many concrete and steel
models. That is a deliberate, reasonable scope choice, and it is also why a
generated union over `HYS_MODEL` must never treat `"KPM"` as the only legal
value.

### MD-08 - `/db/CO_S` and `/db/CO_T` colour components

The Specifications table compresses nine keys into one row:

```text
| 1-9 | Wire Frame / Hidden Fill / Hidden Edge RGB (0-255) | `"W_R"` ~ `"HE_B"` | Integer |
```

Read as a list of literal keys that is two fields, and both SDKs published
exactly two: a caller could set the red component of the wire frame and the
blue of the hidden edge, and nothing else. The section's own JSON Schema names
all nine in order, its Request Example sends all nine, and the sibling
`/db/CO_M` lists them individually - three independent statements against the
one compressed row.

The extractor now expands an interval row only when the No. column's span and
the schema's property order agree on the count, which is transcription rather
than inference. Both contracts were re-promoted and the npm
`SectionColorPayload` carries eleven fields.

### MD-09 - sampled `enum` lists presented as complete

`26_Design_RC_KDS41202022.md:5076` declares

```json
"MAIN_REBAR": { "type": "string", "description": "주철근 규격 (전체 19종: D4 ~ D57)",
                "enum": ["D4", "D5", "D6", "D7", "D8"] }
```

The description and the enum contradict each other in the same object. Taken
as an enum it published `MAIN_REBAR: "D4" | "D5" | "D6" | "D7" | "D8"`, so an
npm caller could not name D10 or anything above it - the sizes real rebar
design uses. `/DESIGN/SRC/AIK-SRC2K/LLRF` is blunter still: its list carries
the literal member `...(전체 11개)`, which would have been a legal value.

Nine fields across four contracts were affected. A count or range the manual
states about its own list now disqualifies the list, and the field keeps its
declared scalar type, which is wide enough for every documented value.

### MD-10 - a Specifications table that is not the whole request

**Five of the original nine were this repository's parser, not the manual.**
The rows were there all along. `extract_contracts.py` split each table row on
every `|`, including GFM's escaped `\|`, which the manual uses to write
alternatives - ``None \| 50% \| 100%``. That gave the row more cells than its
header has, and a row whose cell count disagrees was discarded with no
diagnostic. Ten rows across three chapters were being deleted that way,
among them `/ope/LCOM-GEN`'s `CODE_SELECTION`, which the same section's JSON
Schema marks **required** and uses to select the whole request body.
`_split_row` now honours the escape, and the five contracts built from those
tables carry the recovered fields: `CODE_SELECTION`, `SPLICED_BARS` on the
three `DCRM-*` endpoints, and `FRAMEX`/`FRAMEY` on `DCTL`. Three further rows
(`HOOP_TYPE`, `HOOK_TYPE`, and a fourth `SPLICED_BARS`) belong to `REBC`,
`REBR` and `DCRE`, which are still drafts, so nothing promoted was missing
them.

That leaves **two promoted contracts and two drafts** genuinely built from a
table that omits a root its own JSON Schema declares. Both promoted ones are
now reconciled; both drafts are not.

| section | root(s) only the schema names | state |
| --- | --- | --- |
| `/db/EPMT` | `TRESCA`, `VMISES`, `MOHRCL`, `DRUCKER`, `MASONRY`, `CONCDMG` | **reconciled** 2026-09-02 |
| `/db/ELEM` | `C_RAT`, `LCAXIS` | **reconciled** 2026-09-02 |
| `/db/RCHK` (draft) | `BEAM`, `COLM` | open |
| `/db/FIMP` (draft) | `CONC`, `STEEL` | open - see MD-07 |

**`/db/EPMT` was the one the earlier note got wrong.** Its contract said the
six objects stayed unmerged because "the manual does not state a scalar wire
discriminator". It does: Specifications row 2 enumerates `MODEL_TYPE` as
`"TR"`/`"VM"`/`"MC"`/`"DP"`/`"MA"`/`"DM"` against the model each one selects,
and each sub-table heading names the object that model fills. All six are now
conditional `object` fields on `MODEL_TYPE`. Their *members* are still not
transcribed, and that is the honest reason: none of those sub-tables has a
Value Type column, so the manual gives no type for a single member, and the
`MASONRY` object's `BM`/`BED_JOINT`/`HEAD_JOINT`/`GEOM` structure is stated in
prose rather than as a table.

**`/db/ELEM`'s two are plain fields with nothing stated about them.** The
schema types and describes `C_RAT` (cable length ratio, number) and `LCAXIS`
(local axis, integer); no table in the section names either - not the common
keys and not any of the nine per-subtype tables, including the Cable table
`C_RAT` clearly belongs with. Both are declared with `requirement: unstated`,
which is the whole claim the manual supports.

**A second row-dropping class, found by the same measurement — open.** Once
escaped pipes stopped hiding it, counting every row in a keyed manual table
that produces no field leaves **20 rows whose cell count is one short of
their header**, because the row omits the leading No. cell. They are not one
kind of loss:

| section | rows | what is lost | state |
| --- | --- | --- | --- |
| `/db/POLC-M1` | 5 | **variant divider rows** (`INCRE_METHOD = "LOAD"인 경우`, ...) | promoted, 0 variants |
| `/db/ULFC` | 2 | **variant divider rows** (`등호(Equality) 조건 (EQ=true)`, ...) | promoted, 0 variants |
| `/ope/GUSTFACTOR` | 2 | **variant divider rows** (`STRUCTURE_TYPE = "RIGID"인 경우`) | draft |
| `/db/THIS-M1` | 11 | nested field rows prefixed `- ` (`MODE_NO`, `MAX_ITER`, ...) | draft |

No field is missing from the two promoted contracts - the rows under each
divider parsed normally. What is missing is the split: `/db/POLC-M1` and
`/db/ULFC` both carry 0 variants and 0 unmerged tables, so the npm generator
takes their flat field list as the payload and offers every branch's fields
at once - the same shape 2.7.3 and 2.7.4 corrected on six other endpoints.
`/db/THIS-M1` is the different case: eleven documented nested fields are
simply absent, and it is still a draft.

Fixing this needs a decision the escaped-pipe fix did not: a short row has to
be aligned to the header, and which column it omits is a judgment about the
table's shape rather than a mechanical un-escape. Left open deliberately.

`/db/RCHK` stays open for a structural reason rather than a judgment one: its
`BEAM` and `COLM` object headings are **bold prose**, not markdown headings,
so the parser reads their contents as free-floating tables and attaches them
to no root. Nothing is promoted from it, so nothing wrong has shipped. Its
`MEMBTYPE == "COLUMN"` / `"COLM"` object pairing is *not* a defect - the wire
value and the object key genuinely differ, and the manual states both.

Roots are the visible end of a wider pattern. Comparing every path, not just
the top level, **39 of the 337 promoted contracts and 22 of the 47 drafts**
have at least one path their section's JSON Schema declares and their table
never names. The extreme cases are whole subtrees: `/DESIGN/SRC/AIK-SRC2K/MRBD`
gives 14 of 54 paths, `/db/POGD` 9 of 73, `/view/RESULTGRAPHIC` 11 of 66.
That is measurement, not a verdict - a schema path can be a wrapper the
contract models elsewhere - but it is the number to start from. Only the root
case blocks promotion, because a missing top-level branch means the table is
not the request at all; MRBD is listed in `NEEDS_HAND_REVIEW` by name because
the tree-marker fix made it promotable while still a quarter complete.

`extract_contracts.py` now emits a review note for this, so no further contract
can be promoted from a table its own section contradicts. Reconciling the four
that remain needs someone to read each section and decide how the two
renderings relate - `/db/EPMT`'s six objects are `MODEL_TYPE` branches,
`/db/ELEM`'s two are plain optional fields, and they are not the same kind of
gap. The parser finding is the reason to check the tooling before the source:
over half of what looked like a documentation defect was this repo silently
dropping rows it could not count.

### MD-11 - a Value Type its own section's JSON Schema contradicts

A section states its request twice, and MD-08 through MD-10 are all cases
where one rendering is *less* than the other. These nine are different: the
two renderings state incompatible things about the same property, so neither
can be read as an abbreviation of the other.

| endpoint | path | table says | schema says |
| --- | --- | --- | --- |
| `/db/SBDO` | `AXIS_VECTOR` | Number | `array` of `number` |
| `/db/MATL` | `PARAM` | Object | `array` |
| `/ope/AUTOMESH` | `MESH_SIZE.LENGTH` | Number | `integer` |
| `/ope/AUTOMESH` | `MESH_SIZE.DIV` | Number | `integer` |
| `/db/RCHK` | `BEAM.vSUB_BAR.dSUB_BARNUM` | Integer | `number` |
| `/db/RCHK` | `COLM.vLAYER.vPOSITION.BAR_NUM` | Number | `integer` |
| `/db/RCHK` | `COLM.SUB_BAR.SUBBAR_NUM` | Integer | `number` |
| `/db/RCHK` | `COLM.SUB_BAR.SUBBAR_NUM_Y` | Integer | `number` |
| `/db/RCHK` | `COLM.SUB_BAR.SUBBAR_NUM_Z` | Integer | `number` |

Seven are numeric width, where either reading accepts the values the other
does and nothing a caller sends is refused by the difference. The two at the
top are not: a caller who believes the table sends a scalar where the server
wants a vector.

`/db/SBDO`'s reached users. The contract followed the table, the npm payload
followed the contract, and `SectionBoundaryDataPayload.AXIS_VECTOR` shipped
as `number` - a field whose own documented value, `[0, 0, 0, 0, 0, 0]`, does
not typecheck. Python was never wrong about it (`List[float]` since the
endpoint was added), which is the same asymmetry `/db/CO_S` had: one surface
read the schema, the other read the table, and only the contract could make
them answer the same question. Corrected 2026-09-02 with a `manualDefects`
entry; the npm type is now `Array<number>`, a breaking change for anyone
assigning a scalar.

`/db/MATL`'s reached users differently. `PARAM` was typed `Object`, which the
extractor's nesting then read as a container: read as one branch of the
request rather than of a `PARAM` entry, the three `#### PARAM - P_TYPE = n`
tables would have put `STANDARD`, `ELAST` and `ELAST_M` beside `TYPE` and
`NAME`, where no payload has ever carried them. Corrected 2026-09-02 with the
same kind of `manualDefects` entry, and the endpoint is contracted now.

`extract_contracts.py` attaches a review note wherever the two disagree, so no
further contract can be promoted from a Value Type its own section
contradicts. It deliberately transcribes neither side: choosing between them
took the Request Example and the Python SDK, and neither is a source the
extractor reads for types. The two resolutions above are transcribed in
`_MANUAL_TYPE_CORRECTIONS`, a closed list that also writes each one's
`manualDefects` entry into the contract - so a manual re-sync that reinstates
the table's claim has to argue with the record rather than silently win.

### MD-51 - a Specifications table key with a letter missing

`/ope/MEMB`'s official article states the selection-type key three times. Two
of them - both Input JSON format examples - say `"SELECTION_TYPE"`. The
Specifications table says **`"SELETION_TYPE"`**.

It has never reached anything here, because the vendored manual transcribes the
correct spelling and both SDKs send `SELECTION_TYPE`, which the server accepts.
It surfaced only because the sibling manual repo asked for a re-check of a
different claim about the same article and the raw body was read end to end.

The reason it is worth recording rather than shrugging at: **a normalised
vendored copy hides upstream typos by design**, and that is usually right - the
repo follows the normalised form on purpose. The cost is that nobody
downstream can report the original. Reading the raw article is the only way
these surface, and it is not something any check here does routinely.

### MD-52 - one article id, two locales, two different request examples

This one cost a round trip with the sibling manual repo and neither side was
misreading anything.

They quoted `/ope/MEMB`'s official request example as `"AELEM": [1, 2]`. This
repository had recorded it as `"ELEM_LIST": [640, 692]` and, on re-fetching the
article, confirmed its own reading and reported theirs as a mis-citation. Both
fetches were real. The article is `49514964272665` in both cases, `updated_at`
is `2026-07-30T05:16:25Z` in both cases, and the bodies differ:

| | `en-us` | `ko` |
| --- | --- | --- |
| Input JSON example | `"ELEM_LIST": [640, 692]` | `"AELEM": [1, 2]` |
| Output JSON example | `"AELEM": [640, 692]` | `"AELEM": [1, 2]` |
| Specifications row 3 | `"ELEM_LIST"` | `"ELEM_LIST"` |
| body counts | ELEM_LIST 2, AELEM 1 | ELEM_LIST 1, AELEM 5 |

So `en-us` is internally consistent and `ko` contradicts its own table. The
live run settles which is right: `ELEM_LIST` assigns the member on both
products, and `AELEM` produces the same HTTP 200 error as sending no element
list at all. **The `ko` example is wrong.**

Two things follow, and the second is bigger than this endpoint.

**A vendored citation must name its locale.** `docs/manual/*.md` records a
source URL but not which locale it was read in, so two people can transcribe
the same id faithfully and end up with different field names. Every
manual-versus-article comparison this repository has ever done that fetched one
locale carries the same blind spot.

**"I re-fetched the article and you are wrong" is not sound on its own.** That
is what was reported here, in good faith, with the raw body in hand. The
missing step was asking why a careful person would read something different -
which, once asked, has exactly one cheap answer to check.

## Suggested follow-up, when the author chooses to act

1. Review each finding against the current online article and manual source.
2. Correct manual-repo-owned text (MD-02, MD-04, MD-05), preserving a visible
   note where the upstream article is contradictory.
3. Escalate MD-01, MD-03, and MD-06 to MIDASIT's documentation owner; those are
   official-source issues that the manual repo can only annotate.
4. After any upstream or manual correction, re-run
   `scripts/check_manual_drift.py` before moving `vendored_at_commit`.

### MD-12 - the only source these endpoints have is itself malformed

Seven `-M1` sections in `04_DB_Properties.md` are stubs: a URL, a methods
line, a Zendesk link, and a one-line GET snippet. There is no Specifications
table and no JSON Schema, so `contracts/README.md`'s three permitted sources
reduce to one - live `/info` introspection. Three of the seven
(`/db/IEHG-TRUSS-M1`, `/db/IEHG-GL-M1`, `/db/IEHG-PSS-M1`) 404 on `/info`,
which leaves them with **no permitted source at all**; that split has now been
observed three times, most recently in `schema/hyper-s-info.json`.

The four that do answer carry two defects in the schema they return. Both are
in the captured artifact verbatim, and a contract written from it must not
transcribe either.

**Apostrophes are escaped with a backslash inside a JSON string.** Eight
`description` values across `/db/MATL-M1` and `/db/EPMT-M1`:

| endpoint | path | `description` as served |
| --- | --- | --- |
| `/db/MATL-M1` | `PARAM[].USER_DEFINED.POISN` | `" Poisson\'s ratio"` |
| `/db/MATL-M1` | `PARAM[].USER_DEFINED.POISN_M` | `" Poisson\'s ratio [xy,xz,yz]"` |
| `/db/EPMT-M1` | `MASONRY.{BM,BED_JOINT,HEAD_JOINT}.YOUNG_S_MODULUS` | `" Young\'s Modulus"` |
| `/db/EPMT-M1` | `MASONRY.{BM,BED_JOINT,HEAD_JOINT}.POSSIONS_S_RATIO` | `" Poisson\'s Ratio"` |

`\'` is valid in JavaScript and PHP string literals and is not a JSON
escape. A strict parser rejects it; a lenient one keeps the backslash, so the
text reaches a reader as `Poisson\'s ratio`. The same objects also spell the
key `POSSIONS_S_RATIO`, which is the server's own misspelling of "Poisson's"
and is the wire name regardless.

**`maxItems` is attached to the wrong schema.** Four array properties on
`/db/MATL-M1`:

```json
"ELAST_M": {"description": " Modulii of elasticity [X,Y,Z]", "type": "array",
             "items": {"type": "number", "maxItems": 3}}
```

`maxItems` constrains an array; here it sits on the `number` subschema
describing each element, where JSON Schema ignores it. The intent is
unambiguous - three components, named in the description - but as served the
bound constrains nothing. `ELAST_M`, `THERMAL_M`, `SHEAR_M` and `POISN_M` all
have it.

This is the same shape as the rule `extract_contracts.py` already learned
about the manual in 2.7.5: a bound stated for another kind of value is noted,
not transcribed. It now has to hold for `/info` too.

### MD-13 - two fields, one key, and no example to separate them

`/db/TDME`'s Specifications table:

| No. | Description | Key | Value Type |
| --- | --- | --- | --- |
| 5 | Scale Factor | `"SCALE"` | Number |
| 6 | Function Data (Array of `{TIME, COMP, TENS, ELAST}`) | `"SCALE"` | Array [Object] |

The vendored manual does not hide this - its own ⚠️ callout says the source
table repeats the key, that it looks like a typo, and that there is no example
to confirm the real name, so both rows are transcribed as they stand.

That leaves the extractor with one field named `SCALE` that is a `Number` and
also has four children, which is why `/db/TDME` refuses promotion. The note is
genuinely open: no permitted source answers it. The manual states both, and
neither the section's Request Example nor its Python example sends either row.

**One live call settled it**, the same day this was registered.
`GET /info/db/TDME` lists `SCALE` as a `number` named "Scale Factor" and a
separate `aDATA` array whose items are `{TIME, COMP, TENS, ELAST}` - the
"Function Data" row's real key. Civil and Gen return identical schemas.

So row 5 is correct and row 6's key is wrong; there was never a choice between
two documented names, only one typo standing where a different name belongs.
The contract records `aDATA` with `provenance: live_corrected` and this
defect under `manualDefects`. Captured in `schema/info-schemas.json`.

### MD-14 - a code table that mixes in another product's values

`/db/TDME`'s `CODENAME` table lists 20 values. Eighteen are accepted through
the NX API. `Japan(hydration)` and `Japan(elastic)` answer `Wrong Field` on Gen
NX and Civil NX alike, in all seven spellings tried.

**That refusal is correct.** Those two codes belong to **iGen**, a different
MIDAS product, and this API is not talking to it (author, 2026-09-03). The
product is not failing to honour its own documentation; the chapter is listing
values from a product the reader cannot reach here and saying nothing about it.

So the defect is a labelling one, and it is the manual repo's to fix: the code
table should mark which entries this API serves. As it stands, a caller reading
the table has no way to tell entry 16 from entry 15, and the only feedback is
`Wrong Field` - which this file's own diagnostic reads as "unrecognised value",
sending the reader off to try spellings. Seven were tried here before the
answer turned out not to be a spelling at all.

The extra fields those two branches require (`TENS_STRN_FACTOR`, `bUSE`, `A`,
`B`, `D`, `iCTYPE`, `iECTYPE`) are all present in `/info/db/TDME`, so the
endpoint's schema is shared across products even where the code names are not.
A contract for `/db/TDME` should therefore carry the fields and leave those two
code names out of the branch it declares for this API.

**Re-measured 2026-09-03 on build 09/02/2026**, both products, after the patch
landed - the original pass predates it and its build was never captured. The
refusal reproduces exactly, with a `CEB-FIP(2010)` control storing in the same
session to show the write path was working.

That pass added something the first did not try. The first varied only the
spelling, seven times; this one also supplied each branch's own documented
companion fields (`TENS_STRN_FACTOR`, `bUSE`, `A`, `B`, `D` for Hydration,
`iECTYPE` for Elastic). The answer stayed `Wrong Field` and never became
`[Error] ... input data contain errors` - the message a *recognised* code name
with wrong companions produces. That rules out the last reading in which the
name is known and only its extra fields were missing, and leaves the value
itself unknown to this API, which is what "these are iGen's" predicts. A live
call cannot confirm the *why*, and the probe did not try to.

> An earlier version of this entry claimed the product refuses a value its own
> documentation gives it, and held the claim back pending a re-fetch of the
> official article. The re-fetch was the right instinct and the conclusion was
> still wrong: the missing context was not in the article, it was that a second
> product exists. Recorded here because "check the source before accusing"
> would not have caught this one either.

### MD-15 - one Required value, two endpoints, two different meanings

`Create Only` appears in exactly two Required cells in the whole manual, and
both belong to a field called `CALC_OPT`:

| chapter | endpoint | row | Default |
| --- | --- | --- | --- |
| `04_DB_Properties.md:1148` | `/db/SECT` (`SECTTYPE: "VALUE"`) | Calculation Options | `true` |
| `09_DB_Dynamic_Loads.md:131` | `/db/SPFC` (KDS 41-17-00:2019) | 계산 옵션 | `false` |

Read plainly the value says: the server honours the field on create and
ignores it on modify. Measured on Gen NX on 2026-09-03, that is true of the
first row and false of the second.

`/db/SECT` matches it exactly. The identical body that POST refuses -
`CALC_OPT: false` with no `SECT_I.STIFF` to fall back on, answered
`[Error] Section input data contain errors.` - is accepted as a PUT, and a PUT
that changes `vSIZE` never recomputes `STIFF`, not even with `CALC_OPT: true`
sent explicitly.

`/db/SPFC` does not. `CALC_OPT: true` on a PUT rebuilt a spectrum that had been
hand-set to a flat two-point curve into the 103-point curve its code
parameters generate; `false` and omission both left the stale curve while
accepting new parameters.

So the defect is not that either endpoint misbehaves - each is internally
consistent - but that one Required value is being used for two different
contracts, with nothing in either cell to tell them apart. A reader who
generalises from the row they happen to meet first will be wrong about the
other one half the time.

**A second defect in the same section, found on the way.** `/db/SPFC`'s
KDS(41-17-00:2019) Request Body example omits `CALC_OPT` and supplies no
`aFUNC`. That exact body is refused:

```text
[Error] Spectrum Function Data (Name:KDS_2019_func) contains errors.(Item:Spectrum Data)
```

A design-spectrum function needs either `CALC_OPT: true`, so the server builds
the curve from `STR`/`OPT`/`VAL`, or an explicit `aFUNC`. The documented
default `false` is correct - it is the worked example that cannot run, which
is the more serious of the two because a worked example is what a reader
copies.

Both are recorded in `contracts/endpoints/db-spfc.yaml` under `manualDefects`,
and in `_MANUAL_REQUIREDNESS_CORRECTIONS` in `scripts/extract_contracts.py`
so a re-extraction carries them forward. The contract schema now accepts
`create_only` as a `requirement`, described as what the manual claims rather
than as what the product does - which is what this entry is about.

### MD-16 - a branch's requiredness stated as if there were no branch

`/db/MVHL`'s common Specifications table marks eight fields Required or
Optional without reference to `VEHICLE_LOAD_NUM`, which is the field that
decides which of them apply. Measured on Civil NX, 2026-09-03:

| No. | field | table says | measured |
| --- | --- | --- | --- |
| 4 | `VEHICLE_TYPE_NAME` | Required | required **only** under `VEHICLE_LOAD_NUM: 1`; omitting it there is refused with `(Item:Length of Vehicular Load Type(0 ~ 40 characters))` |
| 5 | `STANDARD_CODE` | Required | **not required at all** - omitted, accepted, and stored without it |
| 6 | `USER_LOAD_TYPE` | Optional | ignored on input under `MVLD_CODE: 2`; `"Train"`, `"Lane"`, `"Truck"`, `"TruckLane"` and omission all stored `"Truck/Lane"` |

Same shape as `/db/FIMP`'s table stating child keys without their parents: the
rows are not individually false so much as unqualified, and a caller reading
row 4 as an unconditional requirement writes a request the server refuses.

The chapter already contains the information. Its KSCE-LSD15 section, added
2026-07-30, carries a Standard example with `"VEHICLE_LOAD_NUM": 1` and
`VEHICLE_TYPE_NAME`, and a User Defined example with `"VEHICLE_LOAD_NUM": 2`,
`USER_LOAD_TYPE` and no type name. What is missing is any statement that this
is a branch, in the one table that presents itself as covering every code.

Row 5 also has an independent confirmation predating this: `VehiclePayload`'s
docstring records that a real production Eurocode PSC bridge model's
predefined "Load Model 1" vehicle carries no `STANDARD_CODE` key at all.

> This entry replaces a claim this repo carried for five weeks in three files:
> that `VEHICLE_LOAD_NUM` was a *documented value wrong live*, and that sending
> `2` made the product silently corrupt a standard vehicle. The observation was
> accurate and reproduces exactly; the conclusion was not. `2` selects the
> user-defined branch, and discarding branch 1's fields is that branch working.
> The observation was made 2026-07-26, four days before the manual documented
> the branch, and nobody re-read it afterwards. Fourth entry in the family that
> includes the retracted B-1/B-2/B-3 and MD-14's iGen codes - see the
> 2026-09-03 passage in `docs/live_verification_notes.md`.

### MD-17 - a row, an example and a matrix that disagree inside one section

`/db/PRES` section 10 of `06_DB_Static_Loads.md` makes three statements about
`DIRECTION` and they do not agree with each other. Measured on Gen NX,
2026-09-03, against the plate in `scripts/live_crud_check.py`'s own seed -
element 4, `ELEM_TYPE: "PLATE"`, `FACE_EDGE_TYPE: "FACE"`, `EDGE_FACE: 1`,
varying only this field:

| `DIRECTION` | result |
| --- | --- |
| omitted | **refused** - `[Error] Errors detected in Pressure Loads Data.(Item:Load Direction)` |
| `"NORMAL"` | **refused** - same message |
| `"LZ"` | stored |
| `"GZ"` | stored |

| the section says | where | agrees with the product |
| --- | --- | --- |
| Optional, default `"NORMAL"` | Specifications row (7) | **no**, in both halves |
| `"DIRECTION": "NORMAL"` on a PLATE + FACE load | Python example | **no** |
| `"DIRECTION": "LZ"` on a PLATE + FACE load | JSON request example | yes |
| Normal is `-` for PLATE + FACE | availability matrix | yes |

So the correction is not a discovery about the product - the section already
documents the product correctly, twice. Two of its four statements were written
without reference to the other two, and the Required column is the one a caller
reads first.

That both halves of row (7) are wrong matters more than either alone. A wrong
default a caller could ignore; here omitting the field is how the default gets
applied, so the row is wrong in the direction that makes following it fail.
There is also no default an SDK can substitute - which way a pressure acts is
an engineering decision - so both SDKs require the field on the wire instead
(contract rule `db-pres-direction-must-be-explicit`) and leave `"NORMAL"` alone
when a caller types it, because the matrix says it is right for the other three
`ELEM_TYPE`/`FACE_EDGE_TYPE` pairs.

This is vendor report **B-4**, which survived the 2026-09-01 re-audit that
retracted B-1, B-2, B-3 and B-7 - narrowed then, and now measured with the
error string rather than inferred.

**A separate, smaller thing in the same section.** `GET /info/db/PRES` declares
an eleventh member of `ITEMS` that the chapter never mentions: `PSLT_KEY`, an
integer referring to a `/db/PSLT` pressure load type. Both products return it
and their schemas agree. It is in the contract as `requirement: unstated` -
`/info` declares no `required` array, and reading the manual's silence as
"Optional" would be a claim nobody has made.

### MD-18 - an enum that names one literal twice

`/db/THGC-M1`'s main Specifications table types `INIT_LOAD_TYPE` as
`Integer(enum)` and names exactly two options, then prints `0` as the literal
for both:

> | 2 | 초기 하중 유형 (0=비선형 정적 해석, 0=정적/시공단계 결과 가져오기) | `INIT_LOAD_TYPE` | Integer(enum) | - | Required |

An enum cannot carry the same literal twice, so unlike most rows in this
register this one is not merely unverified - it is unusable as printed. A
caller who wants "정적/시공단계 결과 가져오기" has no value to send.

The live `/info` schema answers it. Captured 2026-09-03 during the full sweep
of `GET /info/{endpoint}` over every `/db/*` resource on both products:

> `INIT_LOAD_TYPE` | integer | Initial Load Type (Perform NL Static:0, Import Static:1)

The two options correspond to the manual's two, in the same order, so the
correction is one literal and not a new value set. That distinction is why the
contract records `provenance: live_corrected` on this field alone and keeps
`enum` sourced to the manual, which is the side that declares there is an enum
at all: `/info` states no `enum` anywhere, and this repo does not promote a
value set named in an `/info` description into one.

`TimeHistoryGlobalControlHyperSPayload` in `src/midas_nx/db/dynamic_loads.py`
already carried `1` in its trailing comment. That agreement is corroboration,
not a source - `contracts/README.md` forbids an SDK as a contract source, and
the SDK comment on its own records nobody's measurement.

### MD-19 - a switch's children marked Required, and an example that omits them

`/db/THGC-M1`'s "ITER_PARAM 서브 파라미터" table marks all five children of
`LINE_SEARCH` Required. The same section's Python example sends the object with
one key:

```python
"LINE_SEARCH": {
    "OPT_USE": False
}
```

This is MD-16's shape - requiredness stated with no reference to the switch
that governs it - and the reading that reconciles the two is that the other
four apply only when `OPT_USE` is true. **That reading is not recorded as
fact.** Nobody has put either form to a running product, so the contract keeps
the table's claim in `requirement` and leaves every `safeToOmit` on the five
`unverified`.

Measuring it is not something the read-only sweeps can do: `/db/THGC-M1` serves
GET, PUT and DELETE and no POST, so the only way to ask is a PUT that rewrites
the model's global solver settings. That belongs in a write harness against a
document confirmed disposable, not in a sweep that runs beside open work.

The three sub-parameter tables in this section are otherwise clean. All three -
`INCREMENT_STEP`, `ITER_PARAM`, `HINGE_OPT` - were merged into the object field
each names when the contract was reviewed, and the section's own request example
nests every one of them under its parent in a single payload, so none of them is
a conditional variant.

### MD-20 - a Key column that states paths instead of property names

`/db/THGC-M1`'s "ITER_PARAM 서브 파라미터" table names eighteen rows, and two of
its groups are not addressable from what the Key column prints.

| the row prints | what it means |
| --- | --- |
| `` `DISP` → `{OPT_USE, VALUE}` `` (and the same for `FORCE`, `ENERGY`) | `NORM_CTRL.DISP` is an object with two members; the cell names a path and a set, not a property |
| five rows keyed `OPT_USE`, `LINE_SEARCH_OPT`, `START_ITER_NO`, `MAX_LINE_SEARCH_ITER`, `LINE_SEARCH_TOL`, each prefixed "-" in the 설명 column only | the children of `LINE_SEARCH`, which is itself a row of the same table |

Parsed exactly as written, the table produces a field literally named
`{OPT_USE, VALUE}` and places ten children as siblings of the two parents that
own them. This is not a subtle mismatch - the resulting payload has no valid
shape at all.

The section resolves it two paragraphs later. Its Request Body example nests
every one of them:

```json
"ITER_PARAM": {
  "NORM_CTRL": {
    "DISP":   {"OPT_USE": true, "VALUE": 0.001},
    "FORCE":  {"OPT_USE": true, "VALUE": 0.001},
    "ENERGY": {"OPT_USE": true, "VALUE": 0.001}
  },
  "LINE_SEARCH": {
    "OPT_USE": true, "LINE_SEARCH_OPT": 1, "START_ITER_NO": 3,
    "MAX_LINE_SEARCH_ITER": 4, "LINE_SEARCH_TOL": 0.5
  }
}
```

Same family as MD-07 (`/db/FIMP`, rows keyed `"KENPAR"."FC"` with the parents
omitted), MD-08 (`/db/CO_S`, one row keyed `"W_R" ~ "HE_B"`) and MD-13
(`/db/TDME`, one key given to two rows): a Key cell carrying a path or a set
rather than one wire property, with the same section's own example carrying the
answer.

**What was done about it.** The section's other two sub-tables -
`INCREMENT_STEP` and `HINGE_OPT` - have this problem nowhere: each heading names
its destination object and each table is flat, so both were added to
`scripts/extract_contracts.py`'s `_STRUCTURAL_TABLE_SPLITS` and now merge with
no judgment involved. `ITER_PARAM` was deliberately left out of that registry
and its subtree hand-resolved in `contracts/endpoints/db-thgc-m1.yaml`, because
a mechanical merge of this table would encode the broken shape rather than the
documented one.

### MD-21 - one section, five multi-key cells and a table keyed outside its Key column

`/db/STCT-M1` is the densest instance of MD-20's family found so far. Six of
its supplementary tables describe one record, and five Key cells across them do
not name a single wire property:

| where | the cell prints | what it means |
| --- | --- | --- |
| top-level row 5 | `` `"bSDLE"` / `"vSDLE"` `` (Value Type `Boolean / Array [String]`) | two root properties |
| TIME_DEP_CONTROL | `` `"bTTLE_ES"` / `"iTTLE_ES"` `` | two properties of that object |
| NONL_CONTROL | `` `"DISP"`/`"LOAD"`/`"WORK"` `` | three sibling objects, each `{OPT_USE, VALUE}` |
| NONL_CONTROL | `` `"ADVANCED"` `` with its ten children and nested `LINE_SEARCH` as prose in the Description cell | an object the Key column never enumerates |
| "나머지 객체" | `` `"bTRUSS"` / `"bBEAM"` ``, and `` `"OPT_USE"` / `"iSDOPT"` / `"SDCONST"` `` | two, and three, properties |

The "나머지 객체" table has a second problem on top of the multi-key cells: it
states each row's parent in an `Object` column rather than in the key, so its
twelve rows belong to four different objects. No entry in
`scripts/extract_contracts.py`'s structural-split registry can express that -
a `StructuralTableMerge` appends a table's whole field list to each of its
targets - which is why that table and NONL_CONTROL are resolved by hand in the
contract while the other four merge mechanically.

**The top-level split has independent confirmation.** `GET /info/db/STCT-M1`,
captured 2026-09-03, declares sixteen root properties including `bSDLE`
(boolean, "Secondary Dead Load Effect") and `vSDLE` (array, "SDL Load Case
Names") as two separate entries. The section's Request Body sends them as
sibling keys, and so does the Python SDK, which had already split them.

### MD-22 - a root property the top-level table does not have

The same `/info` capture answers a second question about `/db/STCT-M1`. Its
sixteen root properties line up with the manual's fourteen rows once `bSDLE`
and `vSDLE` are counted separately - except for one:

> `FINAL_STAGE` | string | Final Stage Name

The manual's top-level Parameters table has no row for it. It is also the field
the table's own first row implies: `bLAST_FINAL` is documented as "Final Stage
Option (Last: true / Other: false)", and "Other" has to name the stage
somewhere.

Recorded in the contract as `requirement: unstated`, not `optional`. `/info`
declares no `required` array, and the manual makes no claim about this field at
all, so "Optional" would be a claim nobody has made. Same shape as MD-10.

### MD-23 - two keys in a cell, with the discriminator on the row above

`/db/THIS-M1`'s damping table, `COEF_INPUT=1` branch:

| No. | 설명 | Key | Value Type |
| --- | --- | --- | --- |
| 2 | 계산 기준 (0=Frequency, 1=Period) | `COEF_CALC` | Integer(enum) |
| 3 | 모드1 주파수(COEF_CALC=0) / 주기(COEF_CALC=1) | `` `FREQ1`/`PERIOD1` `` | Number |
| 5 | 모드2 주파수(FREQ1≠FREQ2)/주기(PERIOD1≠PERIOD2) | `` `FREQ2`/`PERIOD2` `` | Number |

Unlike the rest of this family, the answer is directly above the question:
`COEF_CALC` is row 2 of the same table, and row 3's own description states the
mapping. The contract declares four fields, each `conditional` on the
`COEF_CALC` value its row names.

`FREQ2`/`PERIOD2`'s description is less careful - "모드2 주파수(FREQ1≠FREQ2)" is
a constraint between the two modes, not a statement of which key applies - but
row 3 settles the pattern for both, and the same `COEF_CALC` governs.

> **What was not done here.** This section's other loose end is
> `BOUNDARY_NL_ANAL`, an object the manual names once - as a table heading -
> and never places. Its two members are typed; its parent is not stated
> anywhere, no Request Example nests it, and the common table has no row for
> it. A 2026-08-27 live round trip saw the server auto-fill `NONL_CTRL_PARAM`
> "including a nested BOUNDARY_NL_ANAL", which proves it exists without saying
> whether it sits directly under `NONL_CTRL_PARAM` or under its `ITER_CTRL`.
> The contract keeps it under `extraction.unmergedTables` with that reasoning
> as its `resolution`, which also stops the npm generator from publishing an
> admittedly incomplete field list as the payload type. Settling it needs a
> POST, and no confirmed fixture for this endpoint exists to build one from.

### MD-24 - 조건부 with no condition, in a chapter that states them elsewhere

`/DESIGN/RC/KDS-41-20-2022/BRD-TABLE` and `/DESIGN/RC/KDS-41-20-2022/CD-TABLE`
each mark `ELEMS` and `SECTIONS` 조건부 in the 필수 column and never say what the
condition is. `ELEMS` appears exactly twice in the whole BRD-TABLE section: once
in the JSON Schema, which lists it as a property and requires only
`TABLE_TYPE`, with no `if`/`then` anywhere; and once in the parameter row. There
is no Request Example for either endpoint that would settle it.

What makes this a defect rather than a gap is that the same chapter knows how to
write the condition. Fifteen rows in `26_Design_RC_KDS41202022.md` state it in
the cell itself:

> | (3) | 요소 번호 입력 (`CREATE_SUB_SECTION`=true 일 때 필수) | `"ELEMS"` | Object | — | 조건부 |

and back it with a matching `"then": { "required": ["ELEMS"] }` in the same
section's JSON Schema. Two sections use the same 조건부 marker with neither.

**Both contracts stay unpromoted.** This entry exists partly to stop the gap
being closed by paraphrase. The 설명 column reads "요소 지정 — KEYS/TO/
STRUCTURE_GROUP_NAME 중 하나", which describes `ELEMS`'s own internal shape -
which of its three sub-keys to use - and says nothing about when `ELEMS` itself
is required. Turning that into `condition: 요소 지정 시` produces a sentence that
is both circular and unsourced, and a first pass at these two contracts on
2026-09-04 did exactly that before it was caught. The honest state is the one
the extractor already reports: "the manual marks this conditional but does not
state the condition", which is an unresolved review note and blocks promotion,
as it should.

> **Superseded in part, 2026-09-04.** The paragraph above says the condition is
> unknown "and deliberately left that way". The first half is no longer true.
> A sweep of every 조건부 `ELEMS`/`SECTIONS` row in chapter 26 found that seven
> of the nine BD/CD/BRD sections state this exact pair as an either/or, in the
> row and in a schema `oneOf`, and that these two are the only ones that do not.
> [MD-33](#md-33---two-sections-that-drop-what-their-seven-siblings-state)
> records that and both contracts are promoted. What stands here unchanged is
> the rejection of the drafted conditions `요소 지정 시` / `단면 번호 지정 시`:
> those were paraphrases of the 설명 column, they were circular, and the note
> attached to them claimed the condition was stated in the same section, which
> it is not. The lesson below about the marker phrase stands too.

### MD-25 - a Value Type and two item shapes the same section settles

`/db/MVLDeu`'s Specifications table understates three rows, and each time the
same section carries the answer a few lines later.

| row | the table says | the section's own Request Body |
| --- | --- | --- |
| 12 `OPT_COMB` | `String`, described as "Loading Effect (Combined: `0` / Independent: `1`)" | `"OPT_COMB": 1` — unquoted, in both examples that set it |
| 11 `STL_LIST` | `Array[Object]`, members only in the description as `(1)` `"NAME1"`, `(2)` `"NAME2"` | `[{"NAME1": "LL_03", "NAME2": "LL_04"}]` |
| 13 `SUB_LOAD_LIST` | `Array[Object]`, six members named in the description | a sub-load case carrying all six, with `SLN_LIST` an array of lane names |

`OPT_COMB` is MD-11's family: a Value Type column the same section contradicts,
in this case with its own worked examples rather than a JSON Schema.

The two arrays are worth recording for a different reason. The numbering
convention in their descriptions — `(1)`, `(2)`, … followed by the quoted key —
is the same one this manual uses in rows of its own elsewhere, and which the
extractor already resolves into nested `properties` when the members get their
own rows. Here it is compressed into one cell, so nothing resolves it
automatically.

**Why that matters beyond tidiness.** Before this endpoint was contracted, the
npm package published `MovingLoadCaseEurocodeStraddlingLaneItem` and
`MovingLoadCaseEurocodeSubLoadItem` from the Python TypedDicts. A contract
transcribing the rows exactly as typed would have replaced both with
`JsonObject` and shipped a *less* precise type than the one it replaced —
caught on 2026-09-04 while reviewing the generated diff, which is the reason
that diff gets read rather than skimmed.

### MD-26 - two members a sibling chapter documents and this one does not

`/db/REBR`'s 파라미터 table presents itself as the whole ITEMS item. It numbers
six members `(1)` to `(6)`, and the section's own JSON Schema - printed
directly above it - declares eight:

| JSON Schema property | 파라미터 row |
| --- | --- |
| `CREATE_SUB_SECTION` | `(1)` |
| `ID` | **none** |
| `ELEMS` | **none** |
| `MAIN_BAR` | `(2)`, with `(2)a`/`(2)b`/`(2)c` |
| `SHEAR_BAR_END` | `(3)` |
| `SHEAR_BAR_CEN` | `(4)` |
| `DO` | `(5)` |
| `HOOP_TYPE` | `(6)` |

The section does not leave the two undocumented. Its third table is headed
"**`CREATE_SUB_SECTION == true` 일 때 — `ELEMS` (KEYS / TO /
STRUCTURE_GROUP_NAME 중 택1)**", and the JSON Schema carries the same condition
as `ELEMS`'s own description. What the table does not say is that its four rows
belong to two different levels:

| No. | Key | where it actually belongs |
| --- | --- | --- |
| `(1)` | `"ID"` | the ITEMS item, beside `CREATE_SUB_SECTION` |
| a | `"KEYS"` | inside `ELEMS` |
| b | `"TO"` | inside `ELEMS` |
| c | `"STRUCTURE_GROUP_NAME"` | inside `ELEMS` |

The `(1)` versus a/b/c numbering is the only thing distinguishing them, and no
row names `ELEMS` itself. Merged as parsed, `KEYS`/`TO`/`STRUCTURE_GROUP_NAME`
would sit beside `ID` at item level and `ELEMS` would not exist.

**Chapter 26 documents the same shape correctly.**
`/DESIGN/RC/KDS-41-20-2022/REBC` and `.../REBR` give `ID` and `ELEMS` ordinary
numbered rows in their Parameters tables, with `ELEMS`'s condition stated in
its own description cell. So this is chapter 24 leaving out what its sibling
chapter states about a near-identical payload, not a gap in what MIDASIT knows.

Same shape as MD-22: a member the table has no row for, supplied by a second
statement inside the same section. Neither SDK is affected - both already send
`ELEMS` - so this is a documentation defect only.

> **What the extractor learned here.** The `(2)a`/`(2)b`/`(2)c` numbering had
> no pattern in `scripts/extract_contracts.py`, so those rows fell to depth 0.
> That put `NAME`/`NUM`/`ROW` at the root of the request instead of inside
> `MAIN_BAR`, and left the `(3)` row after them parented on `ROW`, an Integer.
> The parenthesised number is a path segment, not a sibling marker;
> `_NUMBER_PAREN_SUBITEM` now reads it as depth 2. Nine rows in chapter 24 use
> this form and nothing else in the manual does.

### MD-27 - a table and its own schema, disagreeing five times in both directions

`/db/RCHK` states its request twice, and the two renderings disagree about
integer versus number on every field that counts rebars:

| field | 파라미터 table | JSON Schema |
| --- | --- | --- |
| `BEAM.vSUB_BAR.dSUB_BARNUM` | Integer | `number` |
| `COLM.SUB_BAR.SUBBAR_NUM` | Integer | `number` |
| `COLM.SUB_BAR.SUBBAR_NUM_Y` | Integer | `number` |
| `COLM.SUB_BAR.SUBBAR_NUM_Z` | Integer | `number` |
| `COLM.vLAYER.vPOSITION.BAR_NUM` | Number | `integer` |

The last row runs the other way, and it is the one the section settles. The
same key, with the same description (철근 개수), also appears in the 보 철근
레이어 table for `POS_TOP_LAYERS` / `POS_BOT_LAYERS`, where the table types it
**Integer** and the schema types it `integer`. So three statements say integer
and one says number, and the contract records `integer`.

The other four have no third statement. The section's POST/PUT Request Body
sends `"SUBBAR_NUM": 12` and `"dSUB_BARNUM": 2` - whole numbers, which satisfy
both readings, so the example cannot break the tie. The contract keeps the
tables' `Integer` as **the narrower of the two documented types**: every value
it admits is one the schema's reading also admits, so a caller following the
contract cannot be led into a request the other rendering would refuse. The
reverse choice has no such guarantee.

Worth stating plainly: **no published surface distinguishes the two.**
TypeScript has a single `number` type, and none of these five is a Python
TypedDict member - they live inside `RebarCheckPayload`'s nested objects,
generated from this contract. So the entry records a documentation
contradiction and the reasoning used to settle it, and changes nothing a caller
sees. Only a live POST sending a fractional count could turn it into a fact,
and none has been made.

The Hungarian prefix is not evidence either way here, and was not used as any:
`dSUB_BARNUM` carries the `d`-for-double prefix and is typed Integer by the
table, while `SUBBAR_NUM` carries no prefix and is typed the same way.

### MD-28 - two mutually exclusive Required fields, and a row that points instead of listing

`/ope/AUTOMESH` gathers three separate findings in one section.

**Both halves of a mutually exclusive pair are marked Required.**

| No. | 설명 | Key | 필수 |
| --- | --- | --- | --- |
| 2-1 | 길이 기준 (`DIV`와 동시 사용 불가) | `MESH_SIZE.LENGTH` | **Required** |
| 2-2 | 분할수 기준 (`LENGTH`와 동시 사용 불가) | `MESH_SIZE.DIV` | **Required** |

No payload can satisfy both cells, and the section's own two Request Bodies
prove it: one sends `"MESH_SIZE": { "LENGTH": 1 }` and the other
`"MESH_SIZE": { "DIV": 3 }`. Each is recorded `conditional`, carrying its own
row's phrase as the condition and **no `appliesWhen`** - the manual names no
discriminator field, because which one to send is a modelling choice, not a
branch the payload declares. `documentedOptional` stays `false`: the manual
does say Required, and that flag records the documentation.

**The same two fields are also typed both ways, and do not resolve the same
way.** The table says Number for both; the JSON Schema says `integer` for both.

- `DIV` is 분할수, a division count. `integer` is kept - the narrower of the
  two documented types, and the Request Example's `3` satisfies either reading,
  so narrowing costs nothing.
- `LENGTH` is a mesh size in model length units. Here the narrower reading
  would exclude values the row's own description admits, and no third statement
  supports it, so the table's `Number` is kept.

This is where [MD-27](#md-27---a-table-and-its-own-schema-disagreeing-five-times-in-both-directions)'s
rule stops being mechanical. There, all five contested fields were counts and
all five went the same way. The rule is not "prefer the narrower type"; it is
"prefer the narrower type **when narrowing cannot exclude a value the field's
own description admits**". A length fails that test and a count passes it.

**A row that points at another row instead of listing its members.** Row 1-6
declares `MESHER.INCLUDE_INTERIOR_LINES` and writes 구조는 1-5와 동일 where its
member rows would go. So the table names three fields fewer than the request
has: `OPT_CHECK`, `OPTION`, `VALUE`. The JSON Schema declares the identical
trio under `INCLUDE_INTERIOR_LINES`, and the second Request Body sends
`{ "OPT_CHECK": true, "OPTION": "User", "VALUE": [2] }`.

They are transcribed rather than left out, because a payload type built from
the table alone would refuse a call the manual itself prints. `VALUE`'s
condition is rooted on **this** object's `OPTION`, not on the sibling's - the
two objects have the same shape, not a shared instance. Same family as MD-22
and MD-26.

> **What the extractor learned here.** Rows 1-5-a to 1-5-c and 3-2-a/3-2-b
> write their paths relative to the object rather than the request root
> (`INCLUDE_INTERIOR_NODES.OPT_CHECK`, not
> `MESHER.INCLUDE_INTERIOR_NODES.OPT_CHECK`), so the extractor built a second
> root-level container for each and reported both as having "no row of its own".
> Both are now in `_STRUCTURAL_ROOT_MOVES`, alongside `/ope/GUSTFACTOR`, which
> shortens its paths the same way.

### MD-29 - a section that documents its request twice and says which one to believe

`/DESIGN/RC/KDS-41-20-2022/REBB` prints a JSON Schema, then four Parameters
tables, then a Request Body, a Response Body and a Python example. The two
halves do not describe the same payload:

| the schema and tables | the three examples |
| --- | --- |
| `MAIN_BAR_TOP` / `MAIN_BAR_BOT`, each `{LAYER1, LAYER2}` objects | `vMAIN_BAR_TOP` / `vMAIN_BAR_BOT`, arrays |
| `SKIN_BAR`, an object of `{NAME, NUM}` | flat `SKIN_BAR_NAME` / `SKIN_BAR_NUM` |
| `DT` / `DB` | `MAIN_BAR_DC_TOP` / `MAIN_BAR_DC_BOT` |
| — | `bSAME_SIZE_TOP_BOT`, `bSAME_SIZE_IMJ`, `bSAME_SIZE_LAYER` |
| `CREATE_SUB_SECTION`, `ELEMS`, `DT`, `DB` | not sent |

The section resolves it itself, in a callout directly above the examples:

> **예제 표기 차이:** ... 실제 전송 시에는 아래 예제 형식을 그대로 따르는 것이
> 안전합니다.

The contract follows the examples, and records the schema-and-table rendering
here. Both SDKs already did the same, with the reasoning written into
`RcBeamRebarSector`'s docstring since before this contract existed.

**Corroboration, and what it is not.** The chapter-24 sibling `/db/REBB` was
contracted from `GET /info/db/REBB` and live verification, and its shape is the
example rendering exactly - `vMAIN_BAR_TOP`, `SKIN_BAR_NAME`, `MAIN_BAR_DC_TOP`
and all three `bSAME_SIZE_*` flags, with no `LAYER1`/`LAYER2` and no `DT`/`DB`.
That raises confidence and it is **not** the source: a sibling endpoint is not
a permitted source, `/info` does not serve `/DESIGN/*` (see `CLAUDE.md`), and
every field in this contract is transcribed from chapter 26's own text.

**What is still unknown.** `vMAIN_BAR_TOP` is `[]` in every one of the three
examples, so the array's item shape is never shown by an example. The item is
recorded as `{NAME, NUM}` - the two members the manual's own layer rows give
(레이어 내 철근 규격 / 레이어 내 철근 개수). No layer-number property is
transcribed: the schema rendering carries the layer in the key and the array
rendering carries it in the position, and no row of chapter 26 names one as a
field.

`src/midas_nx/design/rc_kds/rebar.py` had inferred a `LAYER: int` there. It is
dropped, because nothing documents it. The chapter-24 sibling dropped the same
inference on 2026-08-27 against a live `/info` pull and this one was missed
then; the two now agree. This removes `LAYER` from the exported npm interface
`RcBeamMainBarLayerEntry` - a breaking removal, recorded in
`packages/typescript/CHANGELOG.md`.

> **What the extractor learned here.** The sector table was registered in
> `_STRUCTURAL_TABLE_SPLITS` and should not have been. Three of its rows key
> more than one property at once (`"LAYER1"` / `"LAYER2"`,
> `"NAME"` / `"LEG"` / `"DIST"`, `"NAME"` / `"NUM"` - the MD-20 family), and two
> unnumbered rows state the members of `LAYER1`/`LAYER2` rather than of the
> sector, so merging it produced ten flat siblings where the schema has a
> two-level tree. Only the `ELEMS` table stays registered.

### MD-30 - the right number under the wrong keyword

`/DESIGN/RC/KDS-41-20-2022/REBR`'s JSON Schema:

```json
"NUM": { "type": "integer", "description": "철근 총 개수", "minItems": 4 }
```

`minItems` constrains array length. On an integer it is inert - a JSON Schema
validator ignores it, so the schema as written places no bound at all. What the
bound is, is not in doubt: the section's Parameters row for the same field says
철근 총 개수 (min 4), and the chapter-24 sibling `/db/REBR` says 개수 (min 4) in
its row and repeats it in its schema's `description`.

Both contracts now carry `minimum: 4`, which is what all three statements mean.
Small, and worth recording for one reason: a machine reading these schemas gets
no bound, and a person reading them gets the right one.

### MD-31 - a `oneOf` in the type cell, and no member rows

`/DESIGN/RC/KDS-41-20-2022/TABLE` (manual sections 67-69, one endpoint
discriminated by `TABLE_TYPE`) types its `NODE_ELEMS` row:

| No. | 설명 | Key | Value 타입 | 필수 |
| --- | --- | --- | --- | --- |
| 8 | 노드/요소 선택 (`KEYS`/`TO`/`STRUCTURE_GROUP_NAME` 중 하나) | `"NODE_ELEMS"` | Object (oneOf) | 선택 |

`Object (oneOf)` is not a shape, and no row lists a member. The section's own
JSON Schema declares all three properties with a `oneOf` requiring exactly one,
and the Request Body and Python example both send `{"KEYS": [915]}`.

All three are transcribed, each `optional`. The `oneOf` names none of them
required on its own, and a contract has no way to write "exactly one of these",
so the manual's own 중 하나 stays in the description - the same treatment
`/db/REBR`'s and `/DESIGN/.../REBC`'s `ELEMS` already get.

> **What the promotion gate learned here.** This draft and its
> `/DESIGN/SRC/AIK-SRC2K/TABLE` sibling were also refused for "no generic
> plain-function parity surface was discovered", which was wrong: both SDKs
> have shipped these endpoints for months. Where one URL serves several
> documented tables, each SDK puts the endpoint literal in a helper -
> `_get_rc_design_forces_table` in Python, `defineDesignTable` in
> `design-tables.ts` - and gives each table a thin wrapper. Both discoveries
> read only the public function's own body, so neither saw the literal.
> `scripts/function_endpoints.py` now resolves module-private helpers to a
> fixpoint on the Python side and reads the npm factory on the other, which
> raised the discovered plain-function surface from 80 endpoints to 82.

### MD-32 - a documented URL that 404s, in front of a route that kills the session

Section 21 of chapter 27 documents `OCHECK` the way it documents everything
else: an Input URI, Active Methods, a JSON Schema, a Parameters table, a worked
example. Nothing marks it as different.

Two things are wrong with that, and they compound.

**The URL does not answer.** MIDASIT moved the route to
`/TEMP/DESIGN/SRC/AIK-SRC2K/OCHECK` on 2026-08-06, and the documented path now
cleanly 404s. The `/TEMP/` prefix is the status marker: it says this is an
unofficial API whose development is paused. A reader following the manual gets
a 404 with no hint that the endpoint exists elsewhere, or that its existence
elsewhere is a warning.

**The route that does answer ends the session.** Called against a model holding
a real section SRC design cannot use, it never responds: the client times out
after 30-35 seconds, the product raises its "Failed to disconnect the work
session" licence dialog, and the licence is held until the process is properly
restarted. Reproduced four times:

| date | product / build | outcome |
| --- | --- | --- |
| 2026-07-31 | Civil NX, old path, real production bridge model | session died |
| 2026-08-07 | Gen NX v2.1, `/TEMP/` path | identical crash |
| 2026-08-13 | Civil NX v2.2 build 08/12/2026, purpose-built dummy model | identical crash |
| 2026-08-24 | Civil NX v2.2 build 08/24/2026, same dummy model | identical crash |

The path move is not a fix, and the crash is not build-dependent.

Two controls make the precondition clear rather than assumed: the same call
against a document with **no sections** answers a clean
`Section 1 does not exist.` error and leaves the session healthy, on both
products. So the trigger is a property of the caller's model, not of the
request - which is why the contract records `mitigation: warn_only` rather than
`normalized`. There is no field an SDK could add or normalise. `/db/NMAS` is
the contrast: there, three omitted fields caused it and filling them in made
the crash unreachable.

The contract records the route the product serves, with
`source.manual.status: contradicted`, and carries a `warn` sdkRule and the
`temp-src-ocheck-ends-the-session` entry in
`contracts/safety/known-product-risks.yaml`. Both SDKs already carried the
warning on the function; nothing about the published surface changes.

### MD-33 - two sections that drop what their seven siblings state

Chapter 26's design-check endpoints all take the same either/or target
selector: give `ELEMS` **or** `SECTIONS`, not both. Nine sections form the
BD/CD/BRD family, and seven of them say so twice over - in the Parameters row
(`ELEMS`/`SECTIONS` 중 하나) and in a JSON Schema `oneOf`:

```json
"oneOf": [
  { "required": ["ELEMS"],    "not": { "required": ["SECTIONS"] } },
  { "required": ["SECTIONS"], "not": { "required": ["ELEMS"] } }
]
```

| section | row says 중 하나 | schema `oneOf` |
| --- | --- | --- |
| 39 BD-ANAL, 40 BD-TABLE, 41 BD-REPORT | yes | yes |
| 42 CD-ANAL, 44 CD-REPORT | yes | yes |
| 45 BRD-ANAL, 47 BRD-REPORT | yes | yes |
| **43 CD-TABLE** | **no** | **no** |
| **46 BRD-TABLE** | **no** | **no** |

The two outliers mark both rows 조건부 and then state no condition. What their
`ELEMS` rows do carry - 요소 지정 — `KEYS`/`TO`/`STRUCTURE_GROUP_NAME` 중 하나 -
is about what goes **inside** `ELEMS`, not about when `ELEMS` is needed. Their
schemas have `required: ["TABLE_TYPE"]` and no branch keyword at all.

Both contracts record `requirement: conditional` with the condition
`ELEMS/SECTIONS 중 하나` and **no `appliesWhen`**. The manual names no
discriminator field, because there is none: which of the two to send is the
caller's choice, not a branch the payload declares. Same shape as
[MD-28](#md-28---two-mutually-exclusive-required-fields-and-a-row-that-points-instead-of-listing)'s
`MESH_SIZE.LENGTH`/`DIV`.

> **Correcting MD-24.** These two endpoints were left unpromoted on 2026-09-03
> after a drafted condition was rejected, and
> [MD-24](#md-24----------with-no-condition-in-a-chapter-that-states-them-elsewhere) recorded why. That
> rejection was right about the specific claim: the conditions written were
> `요소 지정 시` and `단면 번호 지정 시`, per-field paraphrases of the 설명
> column that say "`ELEMS` is required when elements are specified" - circular,
> and not what the manual says. The note attached to them also claimed the
> condition was "stated elsewhere in the same section", which was false.
>
> What MD-24 got wrong was its conclusion that the manual states no condition
> here at all. It does, for this exact pair, seven times - just never inside
> these two sections. The sweep that found that had not been run. So the
> endpoints are contracted now, with a different condition from the rejected
> one and evidence that can be checked by grepping the chapter. MD-24 stands as
> a record of the invented paraphrase; it no longer stands as a reason to leave
> these two uncontracted.

### MD-34 - the third endpoint in this family the chapter describes wrongly

Chapter 24 describes `/db/REBR` the same way it describes `/db/REBC`, and the
server takes both the same way, which is not the way the chapter describes:

| the chapter | `GET /info/db/REBR` |
| --- | --- |
| `MAIN_BAR`, one object of `{NAME, NUM, ROW}` | `vMAIN_BAR`, an **array** |
| `DO` on the item, a Number | `D0` inside each array entry - a **zero**, not the letter |
| `HOOP_TYPE`, String `"Ties"` / `"Spirals"`, default `"Ties"` | `HOOP_TYPE`, **integer**, `1=Tied, 2=Spiral` |
| `CREATE_SUB_SECTION` and `ELEMS` | neither exists |

`/db/REBW` was the first endpoint in this chapter found wrong about its own
field names (2026-07-29), `/db/REBC` the second (2026-08-27). This is the
third, and the cheapest of the three to establish: `/db/REBC`'s was settled by
POSTing both candidate shapes to one live session - the documented form
answered `Wrong Field`, the array form answered a domain error naming the
missing target section - and this section makes every one of the same claims
about the sibling endpoint.

**What has not been done.** No POST comparison has been run against `/db/REBR`
itself. The contract rests on the `/info` schema plus the `/db/REBC`
precedent, and says so. `/db/REBC`'s round trip is what establishes the
*consequence* - refusal, not silent misbehaviour - and that consequence is
assumed here rather than measured.

**The chapter-26 sibling is not affected, and that is deliberate.**
`/DESIGN/RC/KDS-41-20-2022/REBR` is a different URL, and its section is
internally consistent: its JSON Schema, its Parameters table, its Request and
Response bodies and its Python example all agree on `MAIN_BAR`, a top-level
`DO` and a string `HOOP_TYPE`. `/info` does not serve `/DESIGN/*`, so there is
no permitted source that contradicts it, and a sibling endpoint's shape is not
one. Its contract is left alone. The same split already exists for `REBC`,
whose two chapters describe the same-named data differently for two different
URLs, with live evidence for only the `/db/*` one.

> **How this was found, and why it matters more than the finding.** This
> contract was written from the manual earlier the same day, promoted, and its
> generated npm diff reviewed - the review that is supposed to catch exactly
> this. It did not, and could not: the manual's shape generates a perfectly
> coherent TypeScript type. What caught it was sweeping the 2026-09-03 `/info`
> capture against every contract and asking which declared properties no
> contract records. `/db/REBR` reported two, `ITEMS.vMAIN_BAR` and
> `ITEMS.vMAIN_BAR.D0`, which is what a wrong shape looks like from that angle.
>
> Reviewing a generated diff proves the generator did what the contract says.
> It cannot prove the contract is right about the product. Only a source that
> is the product can do that, and for `/db/*` that source is `/info`.

### MD-35 - a summary table that says "no additional fields", and four of them

Chapter 13 ends with a comparison table meant to tell a reader what is
different about each of the six load-combination endpoints:

| 엔드포인트 | 추가 필드 |
| --- | --- |
| `LCOM-GEN` | — |
| `LCOM-CONC` | `bES` |
| `LCOM-STEEL` | — |
| `LCOM-SRC` | — |
| `LCOM-STLCOMP` | — |
| `LCOM-SEISMIC` | — |

`GET /info/db/LCOM-*`, captured 2026-09-03 on both products, declares the same
four extra properties on **all six**:

| property | /info type | /info description |
| --- | --- | --- |
| `bES` | boolean | E (Concrete design only) |
| `iSERV_TYPE` | integer | EC Serv Type |
| `nLCOMTYPE` | integer | EC Lcom Type |
| `nSEISTYPE` | integer | EC Seis Type |

Twelve schemas, six endpoints, two products, no exceptions. So the 추가 필드
column does not describe what the server accepts, and the three `EC` fields are
named nowhere in the chapter at all.

All four are recorded on all six contracts with `requirement: unstated` -
`/info` declares no `required` array and the manual makes no claim about them,
so `optional` would be a claim nobody has made. Same shape as MD-10 and MD-22.

`bES`'s own description still says "Concrete design only", which may well be
true of what the field *does* while being false of where it is *accepted*. That
distinction is not resolvable from a schema, and nothing here claims to resolve
it: the contracts record that the field exists on all six, not that it is
meaningful on all six.

### MD-36 - the most explicit nesting form in the manual, and the one nothing read

Two chapters mark an array member by naming its parent outright and leaving the
No. column an em dash:

```
| 7 | 조합 항목 배열      | `"vCOMB"`  | Array  | — | **Required** |
| — | (vCOMB) 해석 타입   | `"ANAL"`   | String | — | **Required** |
| — | (vCOMB) 하중케이스명 | `"LCNAME"` | String | — | **Required** |
| — | (vCOMB) 계수        | `"FACTOR"` | Number | — | **Required** |
```

This is the clearest statement of structure anywhere in the manual - the parent
is *named*, not implied by a number, by indentation, or by which row came
before. It is also the only form `scripts/extract_contracts.py` did not read,
so all 21 such rows became root fields. Seven contracts published members as
siblings of the array that contains them: `ANAL`/`LCNAME`/`FACTOR` on all six
`/db/LCOM-*`, and `LC_NAME`/`LC_TYPE`/`SF` on `/db/POGD`.

**This one is ours, not the manual's** - hence the source column. It is
recorded here anyway, because the register is where this project keeps what it
got wrong about a manual section, and because the failure mode is worth naming:
the parser had rules for four *implicit* nesting forms and none for the
explicit one.

The npm effect was visible and nobody looked: `vCOMB` was published as
`Array<JsonObject>` - an array whose item shape the contract could not state,
because the item's three members were sitting outside it. `/info` shows the
same nesting the manual does. Both SDKs' hand-written Python TypedDicts had it
right all along (`vCOMB: List[LoadCombinationItem]`), which is the tell that
should have been noticed: when a generated type is vaguer than the hand-written
one it replaced, the contract is usually wrong.

### MD-37 through MD-41 - what a schema is evidence of, and what it is not

Five findings from one change: `scripts/info_baseline.py --against-contracts`
learned to look in both directions. It had only ever asked which properties
`/info` declares that no contract records. The reverse question - which names a
contract publishes that `/info` declares nowhere - takes four endpoints across
381 contracts, and two of the four were real.

`/db/POGD-M1` is the worst of them. The manual spells the Uplifting checkbox
`UPLIFT` in six places: its JSON Schema, both `allOf` cross-field rules, the
Specifications table, the request and response examples, and the Python
sample. The server calls it `UPLIFTING`. Six agreeing statements inside one
section is not six witnesses - it is one transcription, copied. The sibling
case in the same table is the useful one: `AXIAL_YIELD.BEAM` against
`SHEAR_YIELD.BEAM_COLUMN`, the same Beam/Column checkbox spelled two ways four
rows apart, and the server using the second in both groups. **The manual
disagreeing with itself is worth more than the manual agreeing with itself.**

`/db/STRPSSM` has the clearest cause of any defect in this register.
`GET /info/db/STRPSSM` declares each stress point as `{"Y", "Z"}` and gives
those two properties the descriptions `"PY"` and `"PZ"`. The section publishes
`PY`/`PZ` as the keys. Somebody read down the description column.

**The correction that did not happen.** `WALL` and `SYMMETRIC` were removed
from `/db/POGD-M1` and then put back, and the reason is the calibration this
whole tranche turns on. `/db/STBK`'s `LCNAME` is declared by neither product's
`/info` schema, and `scripts/live_crud_check.py` runs a confirmed
create-read-update-delete round trip that sends it, on both products, and
passes. So an `/info` property list is evidence about what the server
*declares*, and that is not the same as what it *accepts*. Absence from `/info`
supports a note; it does not support deleting a field the manual documents -
and `SYMMETRIC` is one the manual marks Required and lists in its own schema's
`required` array, so removing it would have broken every caller who follows the
documentation.

What settled `/db/REBC`, and `/db/REBR` after it, was a different kind of
evidence and worth restating next to this one: a live POST comparison in which
the documented shape was refused with `Wrong Field` and the `/info` shape was
accepted. A schema absence and a refused request are not interchangeable, and
MD-34's success does not license MD-37's shortcut.

**Three of these were already in the repository.** `/db/STAG`'s `NO` and
`/db/TDNT`'s `bRELAX` were found in real production models on 2026-07-30 and
have been in `src/midas_nx/` ever since; `/db/HPCE`'s `START_STAGE`/`END_STAGE`
were found by `/info` on 2026-08-17 and written into
`docs/live_verification_notes.md`. None of them ever reached `contracts/`, and
the sweep rediscovered them from the product. That is not a discovery, it is a
migration gap - the contracts were behind their own SDK - and it is the second
thing the reverse sweep is good for.

**And three standing live failures now have a cause to test.** `/db/RPSC`,
`/db/STRPSSM` and `/db/TDMF` are three of the four endpoints whose *own* manual
worked example has been failing live on both products since 2026-08-16, left
open in `docs/live_verification_notes.md` as wanting "a fresh angle rather than
more payload guessing". MD-38 says STRPSSM's example sends `PY`/`PZ` where the
server wants `Y`/`Z`; MD-40 says RPSC's sends `MBAR_ITEMS` at the root where
the server wants it inside `MBARS`; `/db/TDMF` is missing an `ELAST` the server
declares. These are candidate causes and nothing more - confirming any of them
takes a live POST, which is the author's call to make.

### MD-42 - the fourth standing live failure, and what the sweep says about it

`/db/GRDP` is the one endpoint in this batch where the sweep's answer is that
nothing is wrong. The manual documents `GROUP_DAMPING_ITEMS`'s fifteen members
in a sentence rather than a table - it says they are rows 7 to 18 with the
`_DEFAULT` suffix taken off, plus `GROUP_TYPE`/`GROUP_NAME`, and names each one
- and `/info` declares exactly those fifteen. Manual and server agree
completely. `src/midas_nx/db/properties/damping.py` has had them since
2026-08-27; only the contract was behind, for the third time in this batch.

That matters for a question that was open. `/db/GRDP` is the fourth of the four
endpoints whose own manual worked example has failed live on both products
since 2026-08-16. MD-38, MD-40 and MD-41 give the other three a shape defect to
test. This one has none: whatever makes `/db/GRDP` answer `"Wrong Field"`, it
is not the request shape, and the note's own suspicion - the fixture naming a
material by id where the model has no such group - survives as the better
lead. **A sweep that finds nothing is a result.**

The fix needed a new mechanism rather than a `field_name` manualDefect. That
waiver turns off the extra-field check for a whole contract and asserts the
manual is wrong, and here the manual is right. `extraction.prose` records the
sentence instead: its line, its text verbatim, and the paths it documents, so
the drift check accepts exactly those fields and nothing else, and the claim
stays checkable against the chapter. The npm signature was MD-36's again, and
it is worth saying twice: `Array<JsonObject>`, an array whose items nothing
described, sitting next to a hand-written Python TypedDict that had all fifteen.

### MD-43 through MD-45 - the contracts were behind their own SDK, six times

This batch was meant to be the tail of the `/info` sweep: a few arrays whose
members no contract recorded. What it actually found is that **six of the eight
endpoints were already correct in `src/midas_nx/`** and wrong only in
`contracts/` - the file this repository calls the source of truth. The npm
package, which generates from the contract, shipped the damage; PyPI, which
does not, did not.

`/db/SLANch` is the worst of it and the clearest statement of the problem. Its
contract's entire field list was `NODE`, `OFFSET`, `SPAN_LENGTH` - the three
members of the `LANE_ITEMS` array, published at the root as though they were
the record. `TrafficSurfaceLanesChinaPayload` on npm therefore named **nothing
the record actually holds**, while `TrafficSurfaceLanesChinaPayload` in Python
had all eight documented fields plus the array. Same package name, same version
number, two registries, and one of them describing a different endpoint.

The cause is a single extractor blind spot with five faces. Each of these
sections does state its members; none states them as a numbered row in the
table the parser reads:

| endpoint | where the members are | what shipped |
| --- | --- | --- |
| `/db/SLANch` | a sub-table headed for the array, mistaken for the main table | three array members as the whole payload |
| `/db/SLAN` | a second table whose rows are design codes | `Array<JsonObject>` |
| `/db/POLC` | a second table whose rows are `LOADPATTERNTYPE` values | `Array<JsonObject>` |
| `/db/ACTL-M1` | a sub-table heading naming three children at once | two fields one level too high |
| `/db/NLNK`, `-M1` | one sentence, ending "(NLNK와 동일)" | `Array<JsonObject>` |

Two of those are now expressible. `extraction.prose` took the sentence, the
same mechanism MD-42 needed. `/db/POLC`'s branch table became a real
`appliesWhen` on `LOADPATTERNTYPE`, because that value is a field of the same
record. `/db/SLAN`'s could not: its rows are design codes, and the code is a
model-wide setting rather than a property of this payload, so the manual names
no wire discriminator and the contract records the condition in words with no
structured gate. That distinction - a condition on a sibling field versus a
condition on the world - is the one worth keeping straight.

**A generator defect fell out of the fix.** Giving `/db/NLNK`'s `POINT_VALUES`
its `{VALUE}` member turned `[JsonObject, JsonObject, JsonObject]` into a plain
`Array<...>`: the tuple rule that preserves an exactly-bounded array lived only
on the path for arrays of scalars, so an array *gained* a described item type
and *lost* its documented length in the same change. Both paths go through one
helper now. It is the second time this batch that making a type more precise
was the thing that exposed an imprecision elsewhere.

### MD-46 - `products: [civil, gen]` was never a claim about the record

A contract's `products` list says which products answer the route. It has been
read, by the generator and by everything downstream, as though it also said the
record is the same on both. For ten endpoints it is not.

`scripts/info_baseline.py --divergence` asks the question of all 177 pairs that
answer `/info` on both products. Ten differ. `docs/live_verification_notes.md`
concluded on 2026-09-03 that `/db/POGD` was "the only pair in the sweep whose
two schemas differ" and that every other both-product endpoint returned
byte-identical schemas - true of the nine endpoints that sweep covered, and the
reason the sentence is worth revisiting rather than trusting. Nine of ten were
invisible to it.

The prescription was already written down there: "A contract for `/db/POGD` has
to tag those members by product; a single shape would be wrong on one of them."
That is what this does, for all ten. 45 fields gained a `products` tag, and
eight that no contract recorded at all were added with one.

**Most of this is not a defect in the manual so much as a limit of it.** Gen NX
is a building product and Civil NX a bridge product; `/db/IEHC`'s nine Gen-only
fields are wall-discretization options and `/db/POSL`'s Civil-only pair are
bridge seismic parameters. A single Specifications table per endpoint cannot say
that, and none of these sections tries to. It is registered here because a
contract that repeats the table unqualified turns a limit of the documentation
into a false statement about the product.

**Two things the tags were not reaching.** The npm generator read the
resource-level `products` and ignored the field-level one entirely, so 53
narrowed fields - including `/db/SBDO`'s and `/db/IEHC`'s, tagged long before
this batch - reached no caller of either SDK. A Civil NX user of `/db/POGD` was
offered twenty Gen-only fiber-model options as if they were theirs. The field
doc comments now say "Gen NX only" / "Civil NX only". And `--divergence` marks
a contract that has declared its own field list incomplete, because `/db/SPLC`
carries four `unmergedTables` entries and its fifteen absent fields are a known
gap rather than a finding - the one endpoint of the ten this batch leaves open,
deliberately.

### What `/info` is evidence of, both directions, settled

Two counter-examples now bound it from opposite sides, and neither is
hypothetical.

**Declared, and refused.** `GET /info/db/POSL` declares `CODE` on *both*
products. A live test on 2026-08-16 found Civil NX answers `"Wrong Field"` for
it, "even as an empty string", along with every one of
`METHOD`/`EPA`/`SDS`/`SD1`/`USER_GROUP`/`IF`/`RMF`. So `/info` lists a property
the product will not take.

**Undeclared, and accepted.** `GET /info/db/STBK` declares no `LCNAME` on
either product. `scripts/live_crud_check.py` runs a confirmed
create-read-update-delete round trip that sends it, on both, and passes. So
`/info` omits a property the product does take.

`/info` is therefore neither a superset nor a subset of what the server
accepts. It is a schema document with its own errors - like the manual, just
produced closer to the code and, on the evidence of MD-34 and MD-38, right far
more often. That refines this morning's rule rather than overturning it: only
`/info` proves the *contract followed the product's declared schema*, and only
a round trip proves the product accepts a payload. Where the two disagree, the
round trip wins, and `/db/POSL`'s contract is the worked example - `CODE` is
tagged from the live finding, not from `/info`.

The practical form of this, for anyone changing a contract from a schema:

* `/info` declares it and the manual does not → add the field, `unstated`.
* `/info` does not declare it and the manual does → keep the field, add a note.
  Never delete on that alone (`/db/POGD-M1`'s `WALL`, MD-37).
* `/info` and the manual name it differently → the server's name, and register
  the defect (MD-34, MD-37, MD-38).
* A live round trip contradicts `/info` → the round trip wins, and say so where
  the field is declared.

**Held by CI since 2026-09-05.** Tagging all ten was a one-off pass, and a
one-off pass on 73 fields decays: a contract gaining one field on a divergent
endpoint without a `products` tag re-introduces exactly this defect, silently,
and only someone remembering to run `--divergence` would notice.
`scripts/info_baseline.py --divergence --check` now runs in CI and treats the
two failure modes differently, because they are different questions.
**`untagged` fails on one** - it is already at the floor, and any value above
zero is a false claim being published. **`absent` is a per-endpoint ceiling**
that may fall for free; all 15 sit on `/db/SPLC`, whose field list is
deliberately incomplete through `unmergedTables`. The guard was verified by
removing `/db/ACTL`'s `CLATS` tag and watching the real command exit 1 naming
that endpoint - a check whose whole job is to fail is worth seeing fail once.


### MD-47 and the check that found it - the contract was behind its own SDK, twelve more times

MD-43 through MD-45 each began the same way: a contract published fewer fields
than the Python TypedDict two directories away, and every automated gate was
green while it did. That is not bad luck. `validate_contracts.py`'s parity
check compares an endpoint's route, its verbs, its `products` list and its
executable safety rules against both SDKs, and has never compared a field
name. `/db/ELNK` published four fields beside a twelve-key TypedDict for
months on exactly that hole.

`check_field_parity` closes it. It resolves each contract's
`surface.payloadTypeName` to the Python TypedDict of that name **in the module
the endpoint's resource lives in** - the name alone is not unique, because the
RC and steel design chapters both have an `SRDF` and a `LENG` and their
payloads differ - follows nested TypedDicts through their annotations, and
fails on any wire name the SDK ships that the contract records nowhere. It
enforces one direction only. A contract naming more than a TypedDict is the
intended state: a TypedDict is documentation, npm generates its payload types
from the contract, and the contract is meant to run ahead.

It found 73 keys across twelve endpoints on its first run. Four resolved to
the name collision above and were false. The rest were real, and they split
into three kinds:

**A wrong shape, four times.** `/db/LLAN`, `/db/LLANch` and `/db/LLANid`
published a flat record. The server takes `{COMMON: {...}, LANE_ITEMS: [...]}`
and always has - the manual's Request Example, its Python example,
`scripts/live_crud_check.py`'s confirmed round trip and `GET /info` all agree,
and the second table's heading says so outright. So does the contract's own
`extraction.table`, which has recorded `Parameters – COMMON` since the draft
was made. The promotion read a heading that named a destination as though it
named the record. `/db/LLANop` is flat at the root, correctly, and had an empty
`LANE_ITEMS`.

**A second consequence, and the reason this kind of error is expensive.**
`/db/LLAN`'s ten common fields all carried `safeToOmit: true` with an
omission-evidence sentence naming the confirmed live payload. That payload
sends nine of them. The claim came from comparing the payload's top-level keys
against a field list that was flat when the payload is not, so every member of
`COMMON` read as absent. A wrong shape does not stay a shape problem; it
manufactures false claims on the axis the safety rules read.

**An empty object, five times.** `/db/MVLDbs`'s six `LCDATA_*` objects and the
design `/DESIGN/RC/KDS-41-20-2022/REBW`'s six had no members at all. Both
sections state them - MVLDbs in a second table using `SUBLOADDATA[].FIELD`
path notation and a 주요 필드 summary table, REBW in its own JSON Schema and a
하위 객체 필드 요약 table - and the parser reads numbered rows.

**A missing branch, once.** `/db/TDMT`'s `CODE="EUROPEAN"`, registered above.

**And one SDK defect, which is what the check is nominally for.**
`/db/HHCT-M1`'s `ITEM` had an `M_GENERAL` the endpoint does not have. Python
shared one item TypedDict between `/db/HHCT` and `/db/HHCT-M1`; the manual
documents `M_GENERAL` only in `/db/HHCT`'s table and `GET /info/db/HHCT-M1`
declares only `TYPE`, `CREEP_CALC_METHOD` and `M_EFF_MOD`. Both sources agree
against the SDK, so the SDK was the thing that changed - the one case in
twelve where the contract was right.

**What the drift checker had to learn.** Putting the LLAN fields back where
the heading says made `scripts/extract_contracts.py --check` report every
single member as invented: it flattens each section's tables into one
namespace, so it holds `LL_NAME` where a correct contract holds
`COMMON.LL_NAME`. Comparing those as strings passes the wrong shape and fails
the right one. `extraction.structuralTables` already existed to record that a
table's heading named its destination; the drift check simply never consulted
it. It does now, in both directions, and only for a leaf the manual's tables
actually state - so a member the manual never mentions is still reported.


### MD-48 and the second blind spot - twenty contracts nothing was checking

MD-47 closed the hole where no gate compared a field name. It left a second
one open in the same breath: `check_field_parity` skipped any contract with an
`extraction.unmergedTables` entry, on the reasoning that such a contract has
already admitted its field list is incomplete. Twenty contracts carry one. The
skip was worth 214 wire names the SDKs ship and no gate looked at - three times
the 73 the check had just found, hidden behind an admission that was true but
far too broad.

**The fix is itemisation, not a wider net.** An `unmergedTables` entry now
records `fieldNames`: the wire names its table holds, in table order. `fields`
had always given the count, and a count is exactly what cannot be used as a
waiver - it says a gap exists without saying what is in it. With the names
written down the waiver is per-name: a name the table accounts for is a
declared gap, a name in neither the contract nor any of those lists is a
defect the check reports. `scripts/extract_contracts.py` emits the list for new
drafts and `--check` verifies it still matches the table, so a chapter edit
that adds a row cannot widen a waiver in silence.

That took the blind spot from 214 names to 84, and the 84 were all real:

* **`/db/THIS-M1` published a shape the server does not take.** The manual's
  headings name two objects and the condition on each in one line - `증분 제어
  (ANAL_METHOD=2 Static 전용, INC_CTRL)`, `시간 적분 방법 (ANAL_METHOD=1 Direct
  Integration 전용, TIME_PARAM)` - and the contract kept both as record-level
  branches, offering `INC_METHOD` and `METHOD` at the root. `/info` declares
  `INC_CTRL` holding `INC_METHOD`, `SF` and a `DISP_CTRL` of its own. Same
  species as `/db/LLAN` in MD-47, found by the same check one layer deeper.
* **`/db/MVLD` had no load case.** `TYPE` selects between `DEFAULT`,
  `PERMIT_LOAD` and `AUTO_OPTIMIZE`, the section carries one worked Request
  Example per value, and the contract published `LCNAME`, `DESC`, `TYPE` and
  nothing else. Australia's `ASL` makes four.
* **Four empty objects**: `/db/SDIS` and `/db/SDST`'s `COMMON` (tabled one
  section over, in `/db/SDVI`), `/db/NLCT-M1`'s `CONV_CRITERIA` (three
  sub-objects named in a sentence above the table that gives their two
  members), `/db/SDST`'s four hysteresis objects (named in a cell).
* **`/db/MVHL`'s `VEH_EUROCODE`**, registered above.

**And a parser defect the names exposed on their own.** 64 of the recorded
names came back as things like `bSD" / "iSDOPT" / "SDCONST` or `SFI(STR)` or
`_3_LANE_FACTOR_1" ~ "_3_LANE_FACTOR_4`. A Key cell can name several
properties at once, and the table parser hands the whole cell back as one key.
While that cell only ever fed a count it was invisible; the moment the names
are written down it is the difference between a waiver accounting for three
fields and one accounting for none - which is why sixteen of `/db/STCT`'s
"missing" names were never missing at all. `_unpack_key_cell` transcribes the
three forms that occur, and only for `fieldNames`: the merged-field path still
goes through `_REVIEWED_SHARED_COMPACT_KEYS`, which demands a named review per
row, because a merged row becomes a published field and a waived one does not.
No contract *field* carries a packed name - the only non-identifier key in all
381 is `/ope/GSBG`'s `7TH_DOF_TYPE`, which is the server's own spelling.

### MD-49 - counting the manual's own statements settled one string and broke the other

Two `/post/TABLE` `TABLE_TYPE` values had the same shape of problem: the
manual states each three times and one of the three disagrees. Both
contracts declared the majority spelling and both said out loud, in a
`manualDefects` entry with `resolved: false`, that nobody had asked the
server. On 2026-09-04 both were asked, on Gen NX 2026 v2.1 and Civil NX
2026 v2.2, build 09/02/2026.

| value sent | server |
| --- | --- |
| `BEAMFORCESTP` (table + example) | recognised |
| `BEAMFORCESIP` (JSON Schema enum) | refused |
| `REACTIONSURFACESPRING` (table + JSON Schema enum) | **refused** |
| `REACTIONLSURFACESPRING` (request example alone) | **recognised** |

The probe reads a distinction this repo already relies on elsewhere:
`[empty] Cannot generate table data as there is no analysis result` is a
`TABLE_TYPE` the product knows and cannot fill, while `there was an error
creating utbl` is one it does not know. Stable across both products and
both pairs.

**The majority was right once and wrong once, and the wrong one shipped.**
Both SDKs' surface-spring reaction constant carried
`REACTIONSURFACESPRING`, a string the server refuses on both products, for as
long as the constant has existed. Every caller of that one table type got a
refusal. Corrected here: the contract takes `provenance: live_corrected`,
Python's `TABLE_TYPE_REACTION_LOCAL_SURFACE_SPRING` and npm's
`reaction.localSurfaceSpring` take the extra L, and `BEAMFORCESTP`'s entry
takes `provenance: live_verified` because it is now confirmed rather than
merely outvoted.

The reason to keep this row after fixing it is the method, not the string.
A wire value is not a majority opinion. Three documents agreeing is three
transcriptions of one source, and this pair is the measurement showing that
a 2-1 split carries no information at all about which way the server goes.
`tests/test_contracts.py::test_a_table_type_contradiction_is_settled_live_or_left_open`
now refuses to let a `describes: table_type` defect be marked resolved on
anything but a live check. The upstream typos are unfixed and remain a
vendor-report item.

### MD-50 - a table with two Key columns, and a field stated in the sentence above it

`/db/MVCTch`'s section 10 is well documented. This repo read about two thirds
of it, in two different ways, and the `/info` sweep is what said so - nine
properties the server declares that no contract recorded, on an endpoint whose
chapter states every one of them.

**The `FREQ` table has two Key/설명 column pairs side by side**, which is how a
25-key object fits on a page:

```text
| Key | 설명 | Key | 설명 |
| `"USER_F"` | f [Hz] | `"SBEM_L"`/`"SBEM_E"`/... | 단순보 L/E/Ic/mc |
| `"CBEM_A"`/`"CBEM_B"`/... | 연속보 a/b/L/E/Ic/mc | `"iARCH_TYPE"` | 아치교 형식 |
```

Everything in the first Key column extracted, **packed cells included** - the
contract has all six `CBEM_*`, all six `ARCH_*`, all five `SUSP_*`. Everything
in the second was dropped whole. That is the diagnosis: not MD-48's packed Key
cell, which this very table proves works, but a table shape the parser reads
half of. Seven keys: `SBEM_L`, `SBEM_E`, `SBEM_IC`, `SBEM_MC`, `iARCH_TYPE`,
`CABL_A`, `CABL_L`.

**Each `BRIDGE` object's `BTYPE` is stated in the bold sentence introducing its
table**, not in a row of it:

> **BRIDGE1 객체 — `"BTYPE"`(Bridge Type: `"RC"` / `"STEEL"` / `"MBRG"`(Old
> Urban Bridge) / `"TRAIN"`(Train·Subway))별 필드:**

That sentence carries the field *and its enum*, and `BTYPE` is the selector
deciding which of the table's 34 rows apply — so the object was unusable
without it, in both languages. Both are now transcribed with their enums and
recorded under `extraction.prose` with the sentence quoted, which is the same
treatment `/db/MVCT`'s Russia-code sentence got.

**What found it.** Not a review of the chapter — the `/info`-to-contract sweep,
on its small-count tail. `/db/SECT` is 995 unrecorded properties and means
nothing; `/db/MVCTch` was 9 and meant a chapter this repo half-read. That is
the shape the sweep is for, and it is now a CI ceiling rather than something
someone remembers to run.

**The parser stays unfixed, and the sweep is why.** Every table in all 27
chapters was scanned for a header row carrying two or more Key columns.
There is exactly one: this table. Teaching the extractor a second Key column
would be code written for a single table in the whole manual, and code that
runs once is code nobody maintains correctly.

What the measurement earns instead is a guard.
`scripts/report_dropped_manual_rows.py` counts a third cause now, **second
key column ignored**, standing at 3 rows - the three `FREQ` rows whose second
Key cell names a property. It runs in CI with the other two causes, so a
manual sync that introduces a second such table fails the build and someone
reads the section instead of finding out months later from an `/info` sweep.
If that count ever grows, the parser change stops being code for one table
and becomes worth writing.

### MD-53 through MD-56 - four worked examples, measured on 09/02/2026

All four were found the same way: a Task A or Task B case replayed the
chapter's own Request Body, unchanged, against Gen NX 2026 v2.1 and Civil NX
2026 v2.2, both build 09/02/2026, through **both** SDKs. Nothing here is a
fixture written from memory, and no replacement value was invented for any of
them - where the manual's example does not work, the case stays unconfirmed
and the endpoint keeps the coverage level it had earned.

**MD-53 is the one that says something about the API, not just the article.**
`/db/MATD`'s example names a rebar grade and prints the yield strengths beside
it, which reads as "these follow from the grade". They do not: omitting them
answers `MAINREBAR_B_FY must be > 0`, so they are required input, and the named
`EN04(RC)`/`ClassB` pair is not resolvable on these builds at all. What
completed was the model's own `KS01(RC)`/`C24` identity plus the example's own
positive strengths. That is recorded as product evidence and deliberately not
generalized into a contract claim - one model's material lookup is not a
schema.

**MD-54 is internally checkable without a product at all.** The section prints
`ECU=0.003`, `Z=100`, `EC0=0.002`; the product refuses the POST with
`Epsilon_cu > 0.8 / Z + Epsilon_co`, and `0.8/100 + 0.002 = 0.010` is greater
than `0.003`. The example contradicts a rule the product states in its own
error text, and the chapter's second example repeats the same three numbers.
An article's worked example is the strongest source this repository has short
of a live call - this is the case where it was wrong on its face.

**MD-55 and MD-56 are held rather than worked around.** `/db/TDMF` has an
`ELAST` in `/info` that the chapter never mentions; a value for it would have
to be invented, so it was not. `/db/EPMT` is the sharper one: `/info` declares
the same field shape on both products and only Civil refuses, which means
`/info` cannot supply the correction either. Both stay open, and both
endpoints keep exactly the evidence they earned - `/db/EPMT` is a Gen-only
write in `docs/coverage.json`, with the Civil case present and unconfirmed.
