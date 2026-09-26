# Live verification playbook

How a live write-verification session is run on this repo, what is left to
verify, and why each remaining endpoint sits where it does.

This replaces `docs/codex_handoff_prompt.md`, deleted 2026-09-20 when the
author stopped handing mechanical batches to Codex. Everything here was
written for that file and is kept because it is about the work, not about who
does it; its task assignments and division-of-labour framing are gone. Earlier
versions are in git history (`a9da9a0` and before).

`docs/live_verification_notes.md` remains the evidence record — what ran, on
which build, with verbatim errors. This file is the procedure and the
scoreboard.

## Where things stand (measured 2026-09-20)

- **Both products are on Build 09/15/2026** (Gen NX 2026 v2.1, Civil NX 2026
  v2.2).
- **2.8.4 is published on PyPI and npm** (2026-09-20). It shipped the
  `/db/TDNT` relaxation — `FT`, `FPK` and `TDMFNAME` optional, each with its
  `appliesWhen` condition in JSDoc. Nothing in either packaged surface has
  changed since.
- **Coverage: 400/400 implemented, 208 write / 192 read.** Of the 225 `/db`
  endpoints, 186 are write-level and 39 are not.
- **Fixture (`schema/live-cases.json`, version 6):** 220 cases over 196
  endpoints; 183 confirmed over 172 endpoints; 9 base-model steps; 77 named
  seeds; 0 unsupported.
- **npm has replayed all 183 confirmed cases** on every product each declares.
  Keep that gap at 0: every new confirmed case goes through both harnesses.
- **Contracts: 384 endpoints + 87 result tables.** The three drafts left, the
  IEHG trio, have no permitted source; that is final.

## Gates

Run these before starting and before committing. If a number differs,
something moved — the command wins over this file. The last one enforces that
for the section above: it re-derives what "Where things stand" claims and fails
if the file and the repository disagree.

```bash
python -m pytest -q                       # 1126 passed
ruff check src tests scripts && mypy      # clean
python scripts/validate_contracts.py      # OK - contracts valid
python scripts/check_manual_drift.py --manual-api-repo "E:\AI Study\MIDAS-API"
                                          # has_diff: false
MSYS_NO_PATHCONV=1 python scripts/extract_contracts.py \
  --manual-api-repo "E:\AI Study\MIDAS-API" --check    # OK - no drift
python scripts/info_baseline.py --against-contracts --check   # OK
python scripts/info_baseline.py --divergence --check          # OK
python scripts/report_dropped_manual_rows.py \
  --manual-api-repo "E:\AI Study\MIDAS-API" --check    # exit 0
python scripts/live_crud_check.py --check-cases        # silent; exit 0
python scripts/check_fixture_contract.py --check       # 1 fixture lead over 1
                                          # endpoint, 3 contract gaps over 2
python scripts/report_npm_replay_coverage.py --check   # 183 cases over 172
                                          # endpoints; every product: 183
python scripts/check_verification_lag.py --check       # 40, ceiling 40
python scripts/verification_ledger.py                  # 397 endpoints:
                                          # 189 read, 208 write
python scripts/report_unmerged_tables.py --check       # exit 0
python scripts/check_state_numbers.py --check          # OK; it checks this
                                          # block's own numbers too
cd packages/typescript && npm run generate && npm run typecheck && npm test
                                          # no drift; 90 tests
```

The manual repo is vendored at `e64a682`. If the drift or extraction check goes
red, a sync landed upstream: deciding what a chapter's new text means is real
work, and a line reference that no longer resolves can mean a table moved or
that it changed.

## The recurring task: re-verify on a new build

**Live. Destructive: `/doc/NEW`.** Every confirmed case was replayed on Build
09/15/2026 on 2026-09-18, so this is dormant until a newer build ships. A
confirmed case failing on a new build is a **regression**, which is what this
exists to catch before a user does.

When a build ships, this command names the scope — set `BUILD` to the **old**
build and it lists every confirmed-case endpoint not yet re-run on anything
newer. Do not hand-count.

```bash
PYTHONIOENCODING=utf-8 python - <<'PY'
import json, sys
sys.path.insert(0, "scripts")
from verification_ledger import load_records

BUILD = "09/15/2026"   # replace with the NEW build's string
cases = json.load(open("schema/live-cases.json", encoding="utf-8"))["cases"]
seen = set()
for record in load_records():
    nx = json.dumps(record.get("nxVersions") or {})
    if BUILD in nx or BUILD in (record.get("method") or ""):
        seen.update(record.get("endpoints") or [])
todo = sorted({c["endpoint"] for c in cases
               if c["confirmed"] and c["endpoint"] not in seen})
print(len(todo)); print(" ".join(todo))
PY
```

It asks which confirmed-case endpoints have no ledger record citing that
build. A record mentioning the build for another reason drops out of the
list; that errs toward doing less, never toward a false claim. With
`BUILD = "09/15/2026"` it prints 0 today.

Batch by tier (`--tier`), at most 8 endpoints per selection, through **both**
harnesses on **both** products in the same session. **Before calling a batch
done, re-run the scope command**; if it did not drop by the number just run,
the ledger append is what is missing.

## Running a live batch

1. **Ask before the first product call of a session.** Then confirm each
   document is open and empty with **that product's own key**: `GET /db/NODE`
   and `GET /db/ELEM` return no records. If `GET /db/NODE` says
   `The project is not opened`, ask for a document — do not send `/doc/NEW`.
2. In Git Bash, `export MSYS_NO_PATHCONV=1` first, or `/db/PTNS` arrives as
   `C:/Program Files/Git/db/PTNS` and the harness exits 2 before any product
   call.
3. npm: from `packages/typescript`, `npm run live:crud -- -- --product gen
   --endpoints /db/A,/db/B --save-dir C:/temp` (PowerShell takes two `--`, Bash
   one), with `MIDAS_MAPI_KEY` set to that product's key.
4. Python, same selection, same session: `python scripts/live_crud_check.py
   --product gen --endpoints /db/A,/db/B --save-dir C:/temp
   --out <report>.json`. `--save-dir` derives the file name, so the extension
   cannot be got wrong; `--save-as C:/temp/<name>.mgbx` still takes an exact
   path if you want one (`.mcbz` on Civil). The Python harness refuses to run
   (exit 2) when `schema/live-cases.json` has drifted from the script; re-emit,
   never hand-edit the fixture.
5. Repeat both for `civil`.
6. A `BLOCK` (exit 3) means a seed failed and says nothing about the endpoint.
   A confirmed case failing is a regression: report it verbatim, do not change
   the fixture to make it pass, and do not flip `confirmed`.

Selection traps, each of which has cost a session:

- **A case whose setup touches a table with no per-id DELETE** — `/db/GRUP`,
  `/db/BNGR` — may only be the **last** endpoint of an npm invocation, because
  the document reset is its cleanup. Give each such case its own invocation.
- **An `--endpoints` selection can drop a case another case depends on**, and
  the Python harness does not warn. `extras14`'s `/db/DYFG` and `/db/DYNF` need
  that tier's `/db/MVCD` case; select them together.
- **Selecting `moving` and `extras14` together** makes `mvcd_ksce_seed` answer
  `Key Already Exist`.
- **A seed on a table that renumbers** (STLD, FBLD, …) must be listed in
  `RENUMBERING_SEEDS`, or npm refuses its setup as a collision. `SeedStep` has
  no flag for it; the set is the only place.
- **A seed that replaces a base-model record is cleaned up by restoring it**,
  not by deleting it. extras13's five design cases are the only ones that do
  this: they overwrite material 1, section 1, nodes 1-4, element 2-3 and
  thickness 1. Until 2026-09-20 the npm harness left the fixture's versions in
  place for the rest of the invocation, because it detects what a step created
  by diffing against a snapshot taken before the step's own delete. If a new
  seed needs `replaceExisting`, check that the base model can supply the
  record back — `replacedBaseModelRecord` refuses a PUT step, which the
  document supplies rather than the fixture.
- **A failing read-back probe is a failure of that case, not of the run.** A
  probe subscripts the record it is handed (`p["ITEMS"][0]["END"]`), so a
  record the product returns in another shape used to raise `KeyError` past
  the report, the end-of-run checkpoint and the document restore. Both are
  caught now; a `FAIL` naming a probe means the shape, not the SDK.
- **A tier's seeds are not per-case.** The Python runner executes every seed of
  a selected tier before that tier's cases, so a tier that splices another
  tier's seed list POSTs those records twice whenever both are selected — a
  full re-verification does exactly that. Give a new tier its own seeds, even
  when an existing one looks identical; extras19 was built the other way on
  2026-09-20 and rebuilt the same day (live notes).

## Recording a run — three places, every time

A run that reaches only some of these did not happen as far as any count is
concerned. This mistake has been made twice: on 2026-09-17 one endpoint and on
2026-09-18 eleven were recorded in the evidence files and never reached the
ledger, and the second session reported its task complete.

1. **The fixture** — `confirmed=True` per product that passed, then
   `--emit-cases`.
2. **The ledger**, `contracts/verification/ledger.yaml` — see below.
3. **The evidence files** — `docs/live_verification_notes.md` (what ran, on
   which build, verbatim errors) and `docs/npm_live_evidence_scratch.md` (one
   row per npm success: date, products, Count line).
   `report_npm_replay_coverage.py --check` fails if a ledger record's `method`
   says `npm replayed the same emitted fixture` and the scratch file has no
   row.

Then `python scripts/gen_roadmap.py` and commit `ROADMAP.md` with the batch.

**A run adds a record. It never edits one.**

```yaml
  - id: ledger-write-2026-09-21
    endpoints: ["/db/PTNS"]
    date: "2026-09-21"
    level: write            # what the session ACHIEVED, not what it tried
    products: [gen, civil]  # only the products it achieved that on
    nxVersions:
      gen: MIDAS Gen NX 2026 (v2.1), build 09/15/2026
      civil: MIDAS Civil NX 2026 (v2.2), build 09/15/2026
    outcome: success
    method: >-
      What was actually done, including whether npm replayed the same
      emitted fixture.
```

`scripts/verification_ledger.py` resolves the records into one claim per
endpoint: **write if any record achieved a write**, and the earliest record at
that level supplies the date and build, because that is the session that
established the claim. So a re-verification is a new record and the original
claim keeps its date -- which is what the old append-only `method` string kept
getting wrong. A read that follows a write does not demote anything, and a
promotion from read to write is just a write record.

Two things the ledger will not do for you:

- **`level` is what a session achieved.** A write the product refused before
  it changed anything is `read`. Recording a refused write as `write` is how
  the old contract records came to claim `/db/NLLP` and `/db/TDMF` at write
  level while their own `finding` said the write was refused.
- **Nothing is deleted or rewritten.** A record is what one session saw, and a
  later session cannot change that. If a record is wrong about what happened,
  correct it in place with a dated note, the way the live notes do.

Run `python scripts/verification_ledger.py` to see the resolved totals, and
`python scripts/gen_roadmap.py` to publish them.

## What is left, and why

Each `/db` endpoint below write level is here with its reason. **Read its entry
in `docs/live_verification_notes.md` before touching it**: re-running an
unchanged fixture on an unchanged build answers nothing, and on 2026-09-19 all
15 runnable cases in the first table were re-run and every answer matched the
earlier build word for word.

### 23 endpoints with a case that has never passed

| endpoint | last answer / reason | blocker |
| --- | --- | --- |
| `/db/EPST`, `/db/EPSE` | `Wrong Field` | every documented value set on EPST varied (`SEL_TYPE`, `EP_TYPE`, `ELEM_TYPE`, `DIR`); EPSE shares its fields |
| `/db/WVLD` | `Wrong Field` | refuses even a bare `NAME` — not a value |
| `/db/TDMF` | `Wrong Field` | sends no field with a value set to vary |
| `/db/RPSC` | `Wrong Field` | `/info` lists `MBARS[].MBAR_ITEMS[].PART`, which the fixture never sends; no source states a value |
| `/db/HPCE` | `Wrong Key` | product finding |
| `/db/FBLA`, `/db/MVLDeu`, `/db/PHGE` | `Unknown Error` | product finding |
| `/db/MADO`, `/db/SBDO`, `/db/DOEL`, `/db/SINF`, `/db/MVLDpl` | POST accepted, record not stored | product finding |
| `/db/ACTL` | Gen refuses every payload; Civil accepts and drops `TOL` | settled product behaviour |
| `/db/STCT` | drops `iITER`/`TOL` on both products | settled product behaviour |
| `/db/FIMP` | printed `ECU=0.003` violates the product's `Epsilon_cu > 0.8 / Z + Epsilon_co` | no compliant value documented |
| `/db/NLLP` | `nllp_seed` answers `Unknown Error` on both | — |
| `/db/NLNK`, `/db/NLNK-M1`, `/db/CGLP` | blocked by `nllp_seed` | NLLP |
| `/db/TDNA` | `Errors detected in Tendon Profile Data.(Item:IS_DB_TDNA_NOTENSIONCALC : Not Registered String)` | a model precondition; permuting fields is not the answer |
| `/db/TDPL` | blocked by the TDNA seed | TDNA |

### 17 endpoints with no case

| endpoint | what stands in the way |
| --- | --- |
| `/db/IMFM`, `/db/IMFM-M1` | every name field is a **FIMP** property name (`Fiber Model Property Name`); blocked by `/db/FIMP` |
| `/db/FIBR` | a fiber division needs FIMP materials; blocked by `/db/FIMP` |
| `/db/IEHG` | `FIBER_NAME` names a FIBR division (blocked), and `PROP_NAME` an inelastic hinge property that no endpoint creates |
| `/db/IEHG-BEAM-M1` | `INEL_PROP_NAME` names an inelastic hinge property that no endpoint creates |
| `/db/EPMT-M1` | contract is `/info`-only: no value stated anywhere, so any payload would be hand-written |
| `/db/CSCS` | needs a `COMPOSITE` section; the manual's only sample omits its dimensions and Gen refuses it (live notes, 2026-09-01) |
| `/db/TDCS` | needs CSCS and the TDNA seed; both blocked |
| `/db/DRLS` | Gen-only; `/info` carries a `DUMMY` placeholder the contract waives — needs a representation decision |
| `/db/RCHK`, `/db/REBB`, `/db/REBR`, `/db/REBW` | ch24 design rebar; REBW's manual section is known wrong about its own field names, and each needs a designed RC member |
| `/db/MVLDbs` | contract marks mutually exclusive `LCDATA_*` objects required together, and `ALL_MODE`'s two-value condition needs a shape decision |
| `/db/IEHG-GL-M1`, `/db/IEHG-PSS-M1`, `/db/IEHG-TRUSS-M1` | no manual schema and `/info` 404s — **never** build a fixture |

### Unconfirmed cases on endpoints already at write level

They move no count. None is actionable unless its cause changes.

| case | product | recorded cause |
| --- | --- | --- |
| `/db/LLANch`, `/db/SLANch`, `/db/LLANid`, `/db/IMPF` | gen | `Unavailable moving load code` for the code these lanes need |
| `/db/LLANop`, `/db/SLANop` | gen | refused under `BS`, the code ch08 gives Gen for this family |
| `/db/LCOM-SEISMIC` | civil | documented `ANAL="RS"` answers `The Load Combination Type is not supported.` |
| `/db/HHCT` | civil | POST accepted, expected value not read back |
| `/db/NLCT` | civil | `LINE_SEARCH_OPTION` required when `OPT_ENABLE_LINE_SEARCH` is true; the contract records no value for it |
| `/db/DSTL` | gen | `Errors detected in Steel Design Control Data.` |
| `/db/EPMT` | civil | `Wrong Field` for the request Gen accepts |
| `/db/POGD` | gen | `Wrong Field` for the payload Civil accepts |

`check_fixture_contract.py`'s one lead, `/db/ACTL` sending `CLATS` on Gen, is
covered above.

### The unmerged tables

`docs/unmerged_tables_against_info.md` is down to `/db/TDME`'s two tables,
which review marked `excluded` with evidence rather than merged: they are iGen
code tables this API refuses. Every other table it used to list was merged
between 2026-09-21 and 2026-09-22, several after a live measurement. The
report and its CI check stay as drift detection for the next contract that
declares one - not as a queue to rescan.

## Open decisions

- **Contract `verification` refs lag the ledger.** 40 contracts cite only a
  read session for an endpoint the ledger holds at write level (TDNT, POGD,
  MVLDch, MVLDid and PTNS among them). It read 48 until the checker stopped
  matching the word "write" in the block and started resolving the ref: eight
  contracts cite a write session whose id does not spell it. The fold
  landed on 2026-09-21 and fixed the *source* of the disagreement -- there is
  one ledger now, `contracts/verification/ledger.yaml` -- but a contract's
  `verification.records[].ref` still points at the session it was promoted
  from, and that is not hand-edited: it records provenance, and editing it to
  match a later claim would forge one. `scripts/check_verification_lag.py`
  holds the count as a ceiling so it can fall but not grow. Re-promoting a
  contract is what moves it. **Audited 2026-09-21: not one of the 40 is a
  contract defect, so this is closed as a decision.** A stale citation would
  matter if the later write had revealed something the contract does not
  record; `check_fixture_contract.py` measures that on every `confirmed` case,
  and none of the 40 is among its three confirmed-side findings (39 have a
  confirmed case; `/ope/MEMB` is write-confirmed through the 2026-09-18 manual
  probes instead). `tests/test_check_verification_lag.py` keeps the two sets
  disjoint, so if one ever crosses over it stops being bookkeeping and that
  contract wants re-promoting from a permitted source. Do not churn the 40 to
  drive the number down.
- **`/db/SPLC`'s `NDP` requiredness** — nested under the Optional `bNDP` switch
  with no wire rule, so neither an `appliesWhen` nor a `safeToOmit` is
  grounded.
- **`/db/SPLC`'s cross-tier id collision** — extras4's `lcom_seismic_splc` and
  extras5's Civil case both own id 1, and the family renumbers, so a different
  id does not fix it. It reports `BLOCK`, honestly.
- **`/db/SPLC`'s `aACCECC_ECCEN_LIST[].ALONG`** is created but never updated
  (recorded in the contract's PUT `notes`).
- **`/db/THIS-M1`'s 20 `/info` properties with no manual row** — the ceiling in
  `info_baseline.py` holds the number.
- **`/db/SECT`'s `USE_HAMBLY_EQ`** — added by Build 09/15/2026 on both
  products, documented nowhere. Not contracted, and
  `schema/info-baseline.json` must not be re-captured: CI fails when the
  uncontracted set grows. At the next manual sync, check whether
  `04_DB_Properties.md`'s 공통 Specifications table grows a row.
- **`/db/MVLDbs`'s contract shape**, and the ch24 rebar family above.

## Live-session rules

`CLAUDE.md` carries the full set; these are the ones a live session trips over.

- **`.env` holds `MIDAS_MAPI_KEY_GEN` and `MIDAS_MAPI_KEY_CIVIL`**, no plain
  `MIDAS_MAPI_KEY`. Never print either. A mismatched key still answers
  `connected` and returns 0 records, so check each product with its own key.
- **`verify_connection()` cannot prove a session is alive.** It answers
  `connected` while a modal dialog holds the product; use a real `GET /db/NODE`.
- **Paths belong to the NX machine.** `--save-dir` is required and never
  inferred from `verify_connection()["user"]`, which is an email. All four
  destructive harnesses ask the same way and refuse to start without an answer
  (`scripts/harness_save_path.py`); the shape is checked while arguments are
  parsed, so a relative path costs nothing, not even a connection.
  `C:/temp` exists; the author manages it — do not clean it.
- **A GET can pop a modal dialog** if the open document lives under
  `Program Files`.
- **Four harnesses call `/doc/NEW` and discard unsaved work**:
  `scripts/live_smoke.py`, `scripts/live_crud_check.py`,
  `packages/typescript/scripts/live-crud.mjs` and
  `scripts/live_manual_feedback.py`, which calls it once per probe rather than
  once per run. Never against a document the author has not confirmed empty.
  Each takes the checkpoint directory from the caller and none guesses one.
  `--no-save-before` waives the checkpoint, not the `/doc/NEW`, and
  `live_manual_feedback.py` does not offer it: its per-probe saves are the
  run's evidence.
- **Assert a reset, do not assume it.** `/doc/NEW` without `{"Argument": {}}` is
  HTTP 500 and resets nothing.
- **Never call `/TEMP/DESIGN/SRC/AIK-SRC2K/OCHECK`**: it crashes Gen, MIDASIT
  has closed it as unsupported, and each call costs a restart and a held
  licence.
- **Never hand-write a live payload.** Use the fixture, a contract or a manual
  example.

## Repository rules this work keeps running into

Beyond what `CLAUDE.md` already states:

- **`appliesWhen`'s `in` needs at least two values**; use `equals` for one.
- **`contracts/` mixes CRLF and LF.** Edit those files as bytes; a deletion
  count on an insert-only change means corrupted line endings. The ledger and
  `docs/coverage.json` are machine-written, so append a record or re-run the
  generator rather than hand-editing either.
- **Never commit a GET response body** — it is the author's model contents.
- **Never put `MAPI-xxxx` or MIDASIT's internal tracker in anything that
  ships**, release notes included. The manual repo names one; it does not come
  across.
- **A wire value is not a majority opinion.** Three documents agreeing can be
  three transcriptions of one typo; only a live check settles one.
