# npm live-evidence inventory (scratch)

Started as a read-only extraction from `docs/live_verification_notes.md` on
2026-09-01, and has been appended to session by session since. An entry appears
only when a session record says the built npm package completed the operation.
`contracts/verification/ledger.yaml` is the authoritative live-evidence ledger
(it took that over from `docs/coverage.json` on 2026-09-21); this file is the
session record behind the npm part of it. The name says scratch because that is
how it started, on 2026-09-01, not because it can be thrown away.

**It is enforced.** `scripts/report_npm_replay_coverage.py --check` fails when
the ledger claims an npm replay this file records no session for. Run it before
writing a claim; it is not one of the steps CI runs.
That check exists because a ledger entry is a claim and this file is the
evidence: on 2026-09-16 four entries were written citing a notes section that
did not mention them, and nothing could see it. So append here in the same
commit that writes the claim - a run this file does not carry does not count.

## Completed DB endpoints

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/NODE` | 2026-08-31 | Gen, Civil |
| `/db/NMAS` | 2026-08-31 | Gen, Civil |
| `/db/LDGR` | 2026-08-31 | Gen, Civil |
| `/db/SMCT` | 2026-08-31 | Gen, Civil |
| `/db/SKEW` | 2026-08-31 | Gen, Civil (also separately re-checked on Gen) |
| `/db/STLD` | 2026-08-31 | Gen, Civil |
| `/db/THIK` | 2026-08-31 | Gen, Civil |
| `/db/DCON` | 2026-08-31 | Gen, Civil |
| `/db/DSTL` | 2026-08-31 | Civil |
| `/db/DCTL` | 2026-08-31 | Gen, Civil |
| `/db/LTSR` | 2026-08-31 | Gen, Civil |
| `/db/MBTP` | 2026-08-31 | Gen, Civil |
| `/db/LENG` | 2026-08-31 | Gen, Civil |
| `/db/MEMB` | 2026-08-31 | Gen, Civil |
| `/db/WMAK` | 2026-08-31 | Gen, Civil |
| `/db/SDST` | 2026-08-31 | Gen, Civil |
| `/db/PNLD` | 2026-08-31 | Gen, Civil |
| `/db/EIGV` | 2026-08-31 | Gen, Civil |
| `/db/LCOM-SEISMIC` | 2026-09-01 | Gen |
| `/db/SDVI` | 2026-09-01 | Gen, Civil |
| `/db/SDVE` | 2026-09-01 | Gen, Civil |
| `/db/SDHY` | 2026-09-01 | Gen |
| `/db/SDIS` | 2026-09-01 | Gen |
| `/db/MVCD` | 2026-09-05 | Gen, Civil |
| `/db/TDGR` | 2026-09-05 | Gen, Civil |
| `/db/NPLN` | 2026-09-05 | Gen, Civil |
| `/db/ETFC` | 2026-09-05 | Gen, Civil |
| `/db/CCFC` | 2026-09-05 | Gen, Civil |
| `/db/HSFC` | 2026-09-05 | Gen, Civil |
| `/db/MLFC` | 2026-09-05 | Gen, Civil |
| `/db/CUTL` | 2026-09-05 | Gen, Civil |
| `/db/CLWP` | 2026-09-05 | Gen, Civil |

| `/db/CNLD` | 2026-09-05 | Gen, Civil |
| `/db/BMLD` | 2026-09-05 | Gen, Civil |
| `/db/CONS` | 2026-09-05 | Gen, Civil |
| `/db/ESSF` | 2026-09-05 | Gen, Civil |
| `/db/SECF` | 2026-09-05 | Gen, Civil |
| `/db/TSGR` | 2026-09-05 | Gen, Civil |
| `/db/TDMT` | 2026-09-05 | Gen, Civil |
| `/db/TDME` | 2026-09-05 | Gen, Civil |
| `/db/GSTP` | 2026-09-05 | Gen, Civil |
| `/db/IFGS` | 2026-09-05 | Gen, Civil |
| `/db/THGC` | 2026-09-05 | Gen, Civil |
| `/db/THFC` | 2026-09-05 | Gen, Civil |
| `/db/SPLC` | 2026-09-05 | Gen, Civil |
| `/db/LCOM-GEN` | 2026-09-05 | Gen, Civil |
| `/db/LCOM-CONC` | 2026-09-05 | Gen, Civil |

| `/db/LLANch` | 2026-09-06 | Civil |
| `/db/SLANch` | 2026-09-06 | Civil |
| `/db/LLANid` | 2026-09-06 | Civil |
| `/db/LLANtr` | 2026-09-06 | Civil |
| `/db/MVHLtr` | 2026-09-06 | Civil |
| `/db/MLSP` | 2026-09-06 | Civil |
| `/db/MLSR` | 2026-09-06 | Civil |
| `/db/MVLDtr` | 2026-09-06 | Civil |
| `/db/MVCTbs` | 2026-09-06 | Gen, Civil |
| `/db/MVCTid` | 2026-09-06 | Civil |
| `/db/MVCTtr` | 2026-09-06 | Gen, Civil |
| `/db/THGC-M1` | 2026-09-06 | Civil |
| `/db/THOO-M1` | 2026-09-06 | Civil |
| `/db/IEPI` | 2026-09-12 | Gen, Civil |
| `/db/EXLD` | 2026-09-12 | Gen, Civil |
| `/db/PRST` | 2026-09-12 | Gen, Civil |
| `/db/POLC` | 2026-09-12 | Gen, Civil |
| `/db/MATD` | 2026-09-12 | Gen, Civil |
| `/db/IEHC` | 2026-09-12 | Gen, Civil |
| `/db/POLC-M1` | 2026-09-12 | Civil |
| `/db/GRDP` | 2026-09-14 | Gen, Civil |
| `/db/MVCT` | 2026-09-14 | Gen, Civil |
| `/db/EPMT` | 2026-09-14 | Gen |
| `/db/ACTL-M1` | 2026-09-15 | Civil |
| `/db/BCGD-M1` | 2026-09-15 | Civil |
| `/db/CJFG` | 2026-09-15 | Civil |
| `/db/CRGR` | 2026-09-15 | Civil |
| `/db/DYLA` | 2026-09-15 | Civil |
| `/db/EIGV-M1` | 2026-09-15 | Civil |
| `/db/HHCT-M1` | 2026-09-15 | Civil |
| `/db/NLCT-M1` | 2026-09-15 | Civil |
| `/db/STCT-M1` | 2026-09-15 | Civil |
| `/db/CLDR` | 2026-09-16 | Gen, Civil |
| `/db/CO_F` | 2026-09-16 | Gen, Civil |
| `/db/CO_M` | 2026-09-16 | Gen, Civil |
| `/db/CO_S` | 2026-09-16 | Gen, Civil |
| `/db/CO_T` | 2026-09-16 | Gen, Civil |
| `/db/PRLS` | 2026-09-16 | Gen, Civil |
| `/db/PZEF` | 2026-09-16 | Gen, Civil |
| `/db/SPAN` | 2026-09-16 | Civil |
| `/db/STYP` | 2026-09-16 | Gen, Civil |
| `/db/STYP-M1` | 2026-09-16 | Civil |
| `/db/BTMP` | 2026-09-16 | Gen, Civil |
| `/db/EFCT` | 2026-09-16 | Gen, Civil |
| `/db/GTMP` | 2026-09-16 | Gen, Civil |
| `/db/IELC` | 2026-09-16 | Gen, Civil |
| `/db/INMF` | 2026-09-16 | Gen, Civil |
| `/db/LDSQ` | 2026-09-16 | Gen, Civil |
| `/db/PLCB` | 2026-09-16 | Civil |
| `/db/SMLC` | 2026-09-16 | Gen, Civil |
| `/db/SMPT` | 2026-09-16 | Gen, Civil |
| `/db/STMP` | 2026-09-16 | Gen, Civil |
| `/db/EDMP` | 2026-09-16 | Gen, Civil |
| `/db/EWSF` | 2026-09-16 | Civil |
| `/db/PSSF` | 2026-09-16 | Gen, Civil |
| `/db/STRPSSM` | 2026-09-16 | Civil |
| `/db/VBEM` | 2026-09-16 | Gen, Civil |
| `/db/VSEC` | 2026-09-16 | Gen, Civil |
| `/db/ELNK` | 2026-09-16 | Gen, Civil |
| `/db/FRLS` | 2026-09-16 | Gen, Civil |
| `/db/GSPR` | 2026-09-16 | Gen, Civil |
| `/db/MCON` | 2026-09-16 | Gen, Civil |
| `/db/NSPR` | 2026-09-16 | Gen, Civil |
| `/db/OFFS` | 2026-09-16 | Gen, Civil |
| `/db/RIGD` | 2026-09-16 | Gen, Civil |
| `/db/SSPS` | 2026-09-16 | Gen, Civil |

## Completed result-table operations

| TABLE_TYPE | Date | Products |
| --- | --- | --- |
| `MASS_SUMMARY_X` | 2026-08-31 | Gen, Civil |
| `REACTIONG` | 2026-08-31 | Gen, Civil |
| `DISPLACEMENTG` | 2026-08-31 | Gen, Civil |
| `BEAMFORCE` | 2026-08-31 | Gen, Civil |

## Deliberate exclusions

- Read-only first-session checks (`/db/STYP`, `/info/db/NODE`) were successful
  transport checks, but were not described as completed npm endpoint cases.
- Explicit rejections or unresolved cases (`/db/FIMP`, `/db/SDIS` LRB,
  `/db/WVLD`, `/db/NLLP`, Gen `/db/DSTL`, and `/db/BCCT`) are not evidence of
  a completed endpoint operation.
- The 2026-09-06 country/code-specific moving-load attempts are not completed
  evidence: `/db/MVLDch` rejected a nonexistent vehicle, `/db/MVLDid` rejected
  the sub-load-case count, `/db/MVLDeu` returned `Unknown Error` on both
  products, and `/db/MVLDpl` did not persist on Civil while Gen refused the
  `POLAND` code. `/db/MVLDbs` never passed the offline fixture/contract gate.
- `/doc/NEW`, `SAVEAS`, and the model-building prerequisites are harness
  operations, not selected endpoint cases.
- The 2026-09-05 empty-document sweep selected cases whose Python fixture
  relied on that harness's common base model, which the shared JSON did not
  carry, so those npm attempts were not counted. **Resolved.** Fixture version
  5 emits the base model and every tier seed the npm harness can replay, and
  the fifteen affected endpoints were re-run on both products on 2026-09-05.
  They are counted above; see the live notes for the run.

### Current-build static batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/ETMP` | 2026-09-16 | Gen, Civil |
| `/db/FBLD` | 2026-09-16 | Gen, Civil |
| `/db/LTOM` | 2026-09-16 | Gen, Civil |
| `/db/NBOF` | 2026-09-16 | Gen, Civil |
| `/db/NTMP` | 2026-09-16 | Gen, Civil |
| `/db/PRES` | 2026-09-16 | Gen, Civil |
| `/db/PSLT` | 2026-09-16 | Gen, Civil |
| `/db/SDSP` | 2026-09-16 | Gen, Civil |

### Current-build dynamic-load batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/SPFC` | 2026-09-16 | Gen, Civil |
| `/db/THGA` | 2026-09-16 | Gen, Civil |
| `/db/THIS` | 2026-09-16 | Gen, Civil |
| `/db/THMS` | 2026-09-16 | Gen, Civil |
| `/db/THNL` | 2026-09-16 | Gen, Civil |
| `/db/THSL` | 2026-09-16 | Gen, Civil |

### Current-build analysis-control batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/BCCT` | 2026-09-16 | Gen, Civil |
| `/db/BUCK` | 2026-09-16 | Gen, Civil |
| `/db/PDEL` | 2026-09-16 | Gen, Civil |

### Current-build bridge batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/CAMB` | 2026-09-16 | Civil |
| `/db/GCMB` | 2026-09-16 | Civil |
| `/db/GSBG` | 2026-09-16 | Civil |
| `/db/ULFC` | 2026-09-16 | Gen, Civil |

### Current-build static-load batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/FMLD` | 2026-09-16 | Gen, Civil |
| `/db/PNLA` | 2026-09-16 | Gen, Civil |
| `/db/POSL` | 2026-09-16 | Gen, Civil |
| `/db/POSP` | 2026-09-16 | Gen |

### Current-build moving-load batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/LLAN` | 2026-09-16 | Gen, Civil |
| `/db/MVHC` | 2026-09-16 | Gen, Civil |
| `/db/MVLD` | 2026-09-16 | Gen, Civil |

### Current-build construction-stage batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/STAG` | 2026-09-16 | Gen, Civil |
| `/db/TMLD` | 2026-09-16 | Gen, Civil |
| `/db/CRPC` | 2026-09-16 | Gen, Civil |
| `/db/CMCS` | 2026-09-16 | Civil |

### Current-build heat-of-hydration subset

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/HAHS` | 2026-09-16 | Gen, Civil |
| `/db/STBK` | 2026-09-16 | Gen, Civil |
| `/db/HSTG` | 2026-09-16 | Gen, Civil |

### Current-build load-combination batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/LCOM-SRC` | 2026-09-16 | Gen, Civil |
| `/db/LCOM-STEEL` | 2026-09-16 | Gen, Civil |
| `/db/LCOM-STLCOMP` | 2026-09-16 | Gen, Civil |

### Current-build lane-optimization batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/LLANop` | 2026-09-16 | Civil |
| `/db/SLAN` | 2026-09-16 | Gen, Civil |
| `/db/SLANop` | 2026-09-16 | Civil |

### Current-build core group batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/BNGR` | 2026-09-16 | Gen, Civil |

### Current-build Gen-only analysis-control cases

Both endpoints carry two cases: a confirmed Gen one and an unconfirmed Civil
one. npm completed the confirmed Gen case; the Civil case failed on both SDKs
the same day, which for an unconfirmed case means triage the fixture. Only the
Gen run is recorded here, because only the Gen run happened.

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/HHCT` | 2026-09-16 | Gen |
| `/db/NLCT` | 2026-09-16 | Gen |

### 2026-09-17 — closing the product asymmetry

`/db/GRUP` was the last plain replay in the gap. The other five had a Civil row
from 2026-09-06 while their confirmed cases declare Gen too, so npm evidence was
one product short of Python's on each. Gen closes them.

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/GRUP` | 2026-09-17 | Gen, Civil |
| `/db/LLANtr` | 2026-09-17 | Gen |
| `/db/MLSP` | 2026-09-17 | Gen |
| `/db/MLSR` | 2026-09-17 | Gen |
| `/db/MVHLtr` | 2026-09-17 | Gen |
| `/db/MVLDtr` | 2026-09-17 | Gen |
| `/db/TMAT` | 2026-09-17 | Gen, Civil |
| `/db/IMPF` | 2026-09-17 | Civil |

### 2026-09-17 — seeds the fixture could not express

Fixture version 6 exports per-id DELETE seed steps and the create branch of
`stage11_seed`, and declares `/db/BCGA-M1`'s order-free comparison. Each run
below was its own harness invocation where a setup table has no DELETE.
`/db/MVHL` needed no harness change: its case had never declared the
`vehicle` seed its id depends on.

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/PJCF` | 2026-09-17 | Gen, Civil |
| `/db/HECB` | 2026-09-17 | Gen, Civil |
| `/db/HSPT` | 2026-09-17 | Gen, Civil |
| `/db/MVHL` | 2026-09-17 | Gen, Civil |
| `/db/BCGA-M1` | 2026-09-17 | Civil |
| `/db/DYFG` | 2026-09-17 | Civil |
| `/db/DYNF` | 2026-09-17 | Civil |

`/db/DYFG` and `/db/DYNF` seed the EUROCODE `/db/MVCD` record Python reaches
through extras14's switch case (`mvcd_eurocode`, `setup_replaces`).

**Count:** 162 distinct `/db` endpoints and 4 distinct result-table operations;
166 distinct npm public-API operations overall.

### 2026-09-18 - Task G meaningful update assertions

The built npm package replayed the corrected cases on Build 09/15/2026. Each
run began with empty `NODE` and `ELEM` tables, checkpointed under `C:/temp`,
and restored an empty scratch document afterwards. These are new payload
variants for endpoints already present in this inventory, not new endpoint
coverage.

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/MATD` | 2026-09-18 | Gen, Civil |
| `/db/IEHC` | 2026-09-18 | Gen, Civil |
| `/db/POLC-M1` | 2026-09-18 | Civil |

**Count:** 3 corrected cases replayed; 162 distinct `/db` endpoints and 4
distinct result-table operations remain covered overall.

### 2026-09-18 - Task K core batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/LDGR` | 2026-09-18 | Gen, Civil |
| `/db/NODE` | 2026-09-18 | Gen, Civil |
| `/db/SKEW` | 2026-09-18 | Gen, Civil |
| `/db/STLD` | 2026-09-18 | Gen, Civil |
| `/db/CNLD` | 2026-09-18 | Gen, Civil |
| `/db/BMLD` | 2026-09-18 | Gen, Civil |
| `/db/CONS` | 2026-09-18 | Gen, Civil |
| `/db/MVCD` | 2026-09-18 | Gen, Civil |

**Count:** 8 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K properties batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/THIK` | 2026-09-18 | Gen, Civil |
| `/db/ESSF` | 2026-09-18 | Gen, Civil |
| `/db/SECF` | 2026-09-18 | Gen, Civil |
| `/db/TSGR` | 2026-09-18 | Gen, Civil |
| `/db/TDMT` | 2026-09-18 | Gen, Civil |
| `/db/TDME` | 2026-09-18 | Gen, Civil |

**Count:** 6 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K boundary batches

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/NSPR` | 2026-09-18 | Gen, Civil |
| `/db/GSTP` | 2026-09-18 | Gen, Civil |
| `/db/GSPR` | 2026-09-18 | Gen, Civil |
| `/db/ELNK` | 2026-09-18 | Gen, Civil |
| `/db/RIGD` | 2026-09-18 | Gen, Civil |
| `/db/MCON` | 2026-09-18 | Gen, Civil |
| `/db/FRLS` | 2026-09-18 | Gen, Civil |
| `/db/OFFS` | 2026-09-18 | Gen, Civil |
| `/db/SSPS` | 2026-09-18 | Gen, Civil |

**Count:** 9 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K properties extras3 batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/GRDP` | 2026-09-18 | Gen, Civil |
| `/db/EDMP` | 2026-09-18 | Gen, Civil |
| `/db/STRPSSM` | 2026-09-18 | Civil |
| `/db/PSSF` | 2026-09-18 | Gen, Civil |
| `/db/VSEC` | 2026-09-18 | Gen, Civil |
| `/db/VBEM` | 2026-09-18 | Gen, Civil |
| `/db/EWSF` | 2026-09-18 | Civil |

**Count:** 7 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K final extras1 batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/SPAN` | 2026-09-18 | Civil |
| `/db/PZEF` | 2026-09-18 | Gen, Civil |

**Count:** 2 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K final extras14 batches

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/CRGR` | 2026-09-18 | Civil |
| `/db/CJFG` | 2026-09-18 | Civil |
| `/db/DYLA` | 2026-09-18 | Civil |
| `/db/ACTL-M1` | 2026-09-18 | Civil |
| `/db/EIGV-M1` | 2026-09-18 | Civil |
| `/db/HHCT-M1` | 2026-09-18 | Civil |
| `/db/NLCT-M1` | 2026-09-18 | Civil |
| `/db/STCT-M1` | 2026-09-18 | Civil |
| `/db/BCGD-M1` | 2026-09-18 | Civil |

**Count:** 9 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K dynamic Hyper-S controls batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/THGC-M1` | 2026-09-18 | Civil |
| `/db/THOO-M1` | 2026-09-18 | Civil |

**Count:** 2 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K extras6 seismic-device batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/SDVI` | 2026-09-18 | Gen, Civil |
| `/db/SDVE` | 2026-09-18 | Gen, Civil |
| `/db/SDST` | 2026-09-18 | Gen, Civil |
| `/db/SDHY` | 2026-09-18 | Gen |
| `/db/SDIS` | 2026-09-18 | Gen |

**Count:** 5 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K extras8 analysis-control batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/EIGV` | 2026-09-18 | Gen, Civil |
| `/db/MVCT` | 2026-09-18 | Gen, Civil |
| `/db/SMCT` | 2026-09-18 | Gen, Civil |

**Count:** 3 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K extras7 nodal-load batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/PNLD` | 2026-09-18 | Gen, Civil |

**Count:** 1 current-build replay; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K extras1 completion batches

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/TDGR` | 2026-09-18 | Gen, Civil |
| `/db/NPLN` | 2026-09-18 | Gen, Civil |
| `/db/PRLS` | 2026-09-18 | Gen, Civil |
| `/db/MLFC` | 2026-09-18 | Gen, Civil |
| `/db/CO_M` | 2026-09-18 | Gen, Civil |
| `/db/CO_S` | 2026-09-18 | Gen, Civil |
| `/db/CO_T` | 2026-09-18 | Gen, Civil |
| `/db/STYP` | 2026-09-18 | Gen, Civil |
| `/db/STYP-M1` | 2026-09-18 | Civil |
| `/db/CLDR` | 2026-09-18 | Gen, Civil |

**Count:** 10 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K extras16 material batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/EPMT` | 2026-09-18 | Gen |

**Count:** 1 current-build replay; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K extras5 dynamic-load batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/SPLC` | 2026-09-18 | Gen, Civil |
| `/db/THGC` | 2026-09-18 | Gen, Civil |
| `/db/THFC` | 2026-09-18 | Gen, Civil |

**Count:** 3 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K China and India lane batches

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/LLANch` | 2026-09-18 | Civil |
| `/db/SLANch` | 2026-09-18 | Civil |
| `/db/LLANid` | 2026-09-18 | Civil |

**Count:** 3 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K moving-control batches

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/MVCTbs` | 2026-09-18 | Gen, Civil |
| `/db/MVCTid` | 2026-09-18 | Civil |
| `/db/MVCTtr` | 2026-09-18 | Gen, Civil |

**Count:** 3 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K nodal-mass replay

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/NMAS` | 2026-09-18 | Gen, Civil |

**Count:** 1 current-build replay; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K extras4 load-combination batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/LCOM-GEN` | 2026-09-18 | Gen, Civil |
| `/db/LCOM-CONC` | 2026-09-18 | Gen, Civil |
| `/db/LCOM-SEISMIC` | 2026-09-18 | Gen |
| `/db/CUTL` | 2026-09-18 | Gen, Civil |
| `/db/CLWP` | 2026-09-18 | Gen, Civil |

**Count:** 5 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K extras10 hydration batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/ETFC` | 2026-09-18 | Gen, Civil |
| `/db/CCFC` | 2026-09-18 | Gen, Civil |
| `/db/HSFC` | 2026-09-18 | Gen, Civil |

**Count:** 3 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K extras15 assignment batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/IEPI` | 2026-09-18 | Gen, Civil |
| `/db/EXLD` | 2026-09-18 | Gen, Civil |
| `/db/PRST` | 2026-09-18 | Gen, Civil |
| `/db/POLC` | 2026-09-18 | Gen, Civil |

**Count:** 4 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-18 - Task K extras2 batches

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/SMPT` | 2026-09-18 | Gen, Civil |
| `/db/SMLC` | 2026-09-18 | Gen, Civil |
| `/db/PLCB` | 2026-09-18 | Civil |
| `/db/LDSQ` | 2026-09-18 | Gen, Civil |
| `/db/IELC` | 2026-09-18 | Gen, Civil |
| `/db/IFGS` | 2026-09-18 | Gen, Civil |
| `/db/EFCT` | 2026-09-18 | Gen, Civil |
| `/db/INMF` | 2026-09-18 | Gen, Civil |
| `/db/GTMP` | 2026-09-18 | Gen, Civil |
| `/db/STMP` | 2026-09-18 | Gen, Civil |
| `/db/BTMP` | 2026-09-18 | Gen, Civil |

**Count:** 11 current-build replays; 162 distinct `/db` endpoints and 4
distinct result-table operations remain covered overall.

### 2026-09-18 - Task K extras13 design batch

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/DCON` | 2026-09-18 | Gen, Civil |
| `/db/LENG` | 2026-09-18 | Gen, Civil |
| `/db/MEMB` | 2026-09-18 | Gen, Civil |
| `/db/DCTL` | 2026-09-18 | Gen, Civil |
| `/db/LTSR` | 2026-09-18 | Gen, Civil |
| `/db/MBTP` | 2026-09-18 | Gen, Civil |
| `/db/WMAK` | 2026-09-18 | Gen, Civil |

**Count:** 7 current-build replays; 162 distinct `/db` endpoints and 4 distinct
result-table operations remain covered overall.

### 2026-09-19 - Task A batches 17 and 18

The first live run of either batch. The built npm package ran first and the
Python harness second, on Gen then Civil, Build 09/15/2026, each starting from
an empty document checked with that product's own key. These are **new
endpoints** for this inventory, not re-runs.

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/TDNT` | 2026-09-19 | Gen, Civil |
| `/db/POGD` | 2026-09-19 | Civil |
| `/db/POGD-M1` | 2026-09-19 | Civil |

`/db/POGD` answered `Wrong Field` on Gen through both SDKs and is recorded for
Civil only. `/db/PHGE` and `/db/TDNA` failed on both products and `/db/TDPL`
was blocked by the TDNA seed; none of those are counted here.

**Count:** 3 new endpoints; 165 distinct `/db` endpoints and 4 distinct
result-table operations; 169 distinct npm public-API operations overall.

### 2026-09-19 - Task B moving-load country cases

The built npm package ran first and the Python harness second, on Civil NX,
Build 09/15/2026, after each case's vehicle was seeded. New endpoints for this
inventory.

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/MVLDch` | 2026-09-19 | Civil |
| `/db/MVLDid` | 2026-09-19 | Civil |

**Count:** 2 new endpoints; 167 distinct `/db` endpoints and 4 distinct
result-table operations; 171 distinct npm public-API operations overall.

### 2026-09-20 - Task P pretension load

The built npm package ran first on each empty product document. The manual's
TRUSS, prestress-load-case and EXLD prerequisites seeded `/db/PTNS`, whose
create/read/update/read/delete/read round trip passed on both products.

| Endpoint | Date | Products |
| --- | --- | --- |
| `/db/PTNS` | 2026-09-20 | Gen, Civil |

**Count:** 1 new endpoint; 168 distinct `/db` endpoints and 4 distinct
result-table operations; 172 distinct npm public-API operations overall.

Re-run 2026-09-20 after the fixture was rebuilt on its own nodes 51-52 and
`PS19_SEED` load case: npm passed `/db/PTNS` again on Gen and Civil, and
passed `/db/EXLD`, `/db/PRST` and `/db/PTNS` in one Gen selection. No new
endpoint, so the count above is unchanged.
