"""Validated MIDAS knowledge surfaced to the model as MCP resources.

Every entry here was confirmed against a live Gen NX instance (the crash guard,
the (ST)/(CB) suffix rule, P-Delta location, rebar grade spaces, …).  They are
exposed as ``midas://knowledge/*`` resources and distilled into the tool result
text so the model is told the rule *at the moment it is relevant*, not only in
a doc it must remember to read.
"""
from __future__ import annotations

PITFALLS: list[dict] = [
    {"area": "boundary", "trap": "boundary/load records keyed on node/element ids",
     "symptom": "MIDAS crashes (every later request 502s) when a missing id is referenced",
     "fix": "the connector refuses the write unless the referenced id exists (crash guard)"},
    {"area": "analysis", "trap": "EIGV.TYPE=EIGEN with a rigid diaphragm",
     "symptom": "'Analysis is not allowed.' and all analysis is blocked until the record is deleted",
     "fix": "TYPE must be LANCZOS"},
    {"area": "load", "trap": "MATL PARAM.P_TYPE=1",
     "symptom": "accepted but POISN/THERMAL/DEN/MASS silently zero",
     "fix": "P_TYPE must be 2, and POISN/THERMAL/DEN/MASS supplied"},
    {"area": "result", "trap": "LOAD_CASE_NAMES without (ST)/(CB) suffix",
     "symptom": "POST/TABLE returns 0 rows, no error",
     "fix": "load cases need '(ST)', combinations '(CB)'"},
    {"area": "analysis", "trap": "P-Delta requested in ACTL",
     "symptom": "ACTL has no second-order fields",
     "fix": "P-Delta lives in DB:PDEL (ITER/TOL/PDEL_CASES)"},
    {"area": "result", "trap": "reading storey results without (ST) suffix",
     "symptom": "0 rows",
     "fix": "append '(ST)'"},
    {"area": "design", "trap": "rebar grade without a space (ClassB)",
     "symptom": "'Rebar grade lookup failed'",
     "fix": "use 'Class A'/'Class B'/'Class C' (space), or GB grades HRB400/HRB335"},
    {"area": "design", "trap": "switching design code without deleting DCON",
     "symptom": "'Key Already Exist' and old checks reused",
     "fix": "DELETE /db/DCON/1 before changing DGNCODE"},
    {"area": "geometry", "trap": "rectangular section SHAPE='SR'",
     "symptom": "interpreted as a solid round/other shape",
     "fix": "rect uses 'SB', pipe uses 'P', solid round 'SR'"},
    {"area": "geometry", "trap": "H-section SHAPE='DB'/'H2'/'I'",
     "symptom": "'cross-section size input error'",
     "fix": "use SHAPE='H' with vSIZE [H,B,tw,tf]"},
    {"area": "result", "trap": "'Unknown Error' when reading result tables",
     "symptom": "bare Unknown Error, not 'no analysis result'",
     "fix": "any model change invalidates results; re-run /doc/ANAL before reading"},
    {"area": "geometry", "trap": "space/planar truss",
     "symptom": "mechanism/I divergent analysis (10^18 displacements)",
     "fix": "use BEAM elements"},
    {"area": "delete", "trap": "sending DELETE with a body on /db/LCOM-GEN",
     "symptom": "200 returned and the ENTIRE combination collection is wiped, whatever id the body named",
     "fix": "never send a body-form delete; the connector only uses DELETE <uri>/<id> and verifies by read-back"},
    {"area": "delete", "trap": "expecting DELETE <uri>/<id> to work everywhere",
     "symptom": "LCOM-GEN answers 'Unknown Error' for the path form",
     "fix": "that endpoint has no per-id delete; the connector reports the failure rather than falling back to a collection-wide delete"},
    {"area": "geometry", "trap": "typo in a field name on /db/NODE",
     "symptom": "201 and an EMPTY node is created; the same typo gives 'Wrong Field' elsewhere",
     "fix": "read the record back after creating it; node creation is the most forgiving endpoint"},
    {"area": "result", "trap": "trusting the DELETE status code",
     "symptom": "HTTP 200 for an id that never existed, so a no-op delete looks successful",
     "fix": "the connector reads the id back after DELETE and only reports success when it is gone"},
    {"area": "file", "trap": "passing an object argument to /doc/EXPORT (or IMPORT/OPEN)",
     "symptom": "200 with 'MIDAS GEN NX path is wrong (the file can't open)'",
     "fix": "these commands take a bare string path; the connector unwraps EXPORT_PATH/FILE_PATH for you"},
    {"area": "load", "trap": "CNLD item written with a CMD/FV vector",
     "symptom": "HTTP 400 '[错误] 荷载值输入有错误。' (load value input error)",
     "fix": "CNLD items use explicit components FX/FY/FZ/MX/MY/MZ; key must equal the node number"},
    {"area": "load", "trap": "BMLD items reusing the same per-element ID",
     "symptom": "later load silently overwrites earlier for that element",
     "fix": "ID is the load number within the element (1,2,3…), not the element number"},
    {"area": "file", "trap": "EXPORT_PATH using forward slashes",
     "symptom": "'second query is wrong' or read timeout",
     "fix": "use Windows backslashes"},
    {"area": "file", "trap": "/doc/SAVEAS and repeated NEW",
     "symptom": "modal dialog that blocks the whole API channel",
     "fix": "use /doc/SAVE; clear the model in place instead of NEW"},
    {"area": "units", "trap": "kg as point load",
     "symptom": "wrong scale",
     "fix": "default units kN-m; 1000 kg -> FZ = -9.81 kN"},
    {"area": "units", "trap": "reading result numbers without checking /db/UNIT first",
     "symptom": "moments and deflections off by powers of 1000 (mm vs m models)",
     "fix": "read DB:UNIT before interpreting any result; a mm model scales moment by 1e3"},
    {"area": "storey", "trap": "confusing /db/STOR with /ope/STORYPROP",
     "symptom": "old docs spelled it STORPROP; /db/STOR needs all 15 fields or answers a bare 'Wrong Field'",
     "fix": "the storey property endpoint is OPE:STORYPROP (POST); it answers 'no valid story information' when stores are absent. /db/STOR is the storey definition and is not a stub - a partial record is what fails"},
    {"area": "load", "trap": "posting a /db collection with an 'Argument' wrapper",
     "symptom": "HTTP 400 'Wrong Field' on DB:LCOM-GEN (and LCOM-CONC/LCOM-STEEL/LCOM-SRC, STOR, EDMP, SSPS)",
     "fix": "every /db endpoint takes 'Assign'; verified live - Assign -> 201, Argument -> 400. The registry wrapper is authoritative; the connector strips any wrapper the model supplies"},
    {"area": "analysis", "trap": "treating a DOC:ANAL HTTP 400 that carries [警告] as a failed analysis",
     "symptom": "HTTP 400 '[警告] 强制位移在 反应谱分析中设为零。' yet POST/TABLE still returns real DEAD(ST) and EQ_X(RS) rows",
     "fix": "a [警告] body is a WARNING, not a rejection: the analysis runs and the results are readable. The connector reports it as ok with a 'warning' field. Confirm by reading a result table before believing any failure"},
    {"area": "write", "trap": "re-POSTing a key that already exists",
     "symptom": "HTTP 400 'Key Already Exist' - the record is NOT overwritten and the old value silently survives; a setting you believed you changed (e.g. EIGV.iFREQ) stays stale and every later result reflects the old value",
     "fix": "treat a create as write-once: read the record back after every write and assert the value you asked for. To change an existing record use mode='update' (PUT). The connector reports this as category ALREADY_EXISTS rather than a generic rejection, so it is never mistaken for success"},
    {"area": "analysis", "trap": "trusting an eigenvalue request without checking the readback",
     "symptom": "POST /post/TABLE EIGENVALUEMODE returns only 3 modes although 20 were requested; the EIGENVALUE ANALYSIS sub-table has 3 rows and the modal participation tables have 3 rows",
     "fix": "the computed mode count is DB:EIGV.iFREQ, not the MODES list in the table request. Read DB:EIGV back and confirm iFREQ before running /doc/ANAL; widening MODES alone changes nothing"},
    {"area": "result", "trap": "reading an eigenvalue table by a guessed response key",
     "symptom": "KeyError on the table name: the response root key follows the request's TABLE_NAME, so {\"TABLE_NAME\":\"EigenvalueMode\"} answers under 'EigenvalueMode', not 'EIGENVALUEMODE'",
     "fix": "use the first key of the response object, or send TABLE_NAME equal to TABLE_TYPE. The mode summary (frequencies, periods, participation masses/factors, direction factors) is not in the top-level DATA but in the response's SUB_TABLES array; each entry is a single-key object whose inner HEAD/DATA hold the rows"},
    {"area": "result", "trap": "concluding 'this build has no modal/eigenvalue summary' from the top-level table",
     "symptom": "POST:TABLE:EIGENVALUEMODE answers 200 with HEAD ['Index','Node','Mode','UX','UY','UZ','RX','RY','RZ'] and 1960 per-node mode-shape rows; nothing in DATA looks like a frequency or a period, so a caller that reads only DATA reports the summary as unavailable - and a caller that then searches for a separate MODAL/FREQUENCY/EIGENVALUE endpoint gets 'unknown MIDAS endpoint' and treats that as confirmation",
     "fix": "the summary is in the SAME reply, under SUB_TABLES: 'EIGENVALUE ANALYSIS' (ModeNo, Frequency(rad/sec), Frequency(cycle/sec), Period(sec), Tolerance), 'MODAL PARTICIPATION MASSES PRINTOUT (1)'/'(2)', 'MODAL PARTICIPATION FACTOR PRINTOUT' and 'MODAL DIRECTION FACTOR PRINTOUT'. Verified live on Gen NX 2027: 20 modes, mode 1 = 2.6350 Hz / 0.3795 s, cumulative participation 99.48 % X / 97.50 % Y / 92.34 % Z. Never decide a result is absent because the primary table is empty or does not look like it - SUB_TABLES is a first-class result source, and the connector parses it into result_summary.modal_result automatically"},
    {"area": "result", "trap": "reading only the top-level table and dropping the SUB_TABLES that came with it",
     "symptom": "the summary tables MIDAS appends (eigenvalue, participation, direction factor, buckling) are silently ignored, so a report can claim 'no modal results' while they were returned in the same response",
     "fix": "a POST/TABLE reply's SUB_TABLES is a list of single-key {name: {HEAD, DATA}} objects, read from the endpoint that was already asked - never by searching for a second endpoint. The connector attaches result_summary.sub_tables / modal_result / buckling_result to every POST:TABLE result, and a midas_db_query search for modal wording returns a 'route' pointing at POST:TABLE:EIGENVALUEMODE"},
    {"area": "analysis", "trap": "setting SPLC.aUSEMODE with bMODE left false",
     "symptom": "the write returns HTTP 200 but aUSEMODE comes back empty, so the response-spectrum case has no modes to combine",
     "fix": "bMODE must be true for aUSEMODE to be stored; set bMODE=true and read the mode list back before running ANAL"},
    {"area": "analysis", "trap": "running eigenvalue, response-spectrum and buckling analyses in one /doc/ANAL",
     "symptom": "HTTP 400 '[错误] 不能同时执行 特征值分析和 屈曲分析。' / '[错误] 不能同时执行 反应谱分析和 屈曲分析。' / '[错误] 不能同时执行 P-Delta分析和 屈曲分析。' - the analysis does not run at all",
     "fix": "buckling is mutually exclusive with eigenvalue, response-spectrum AND P-Delta on Gen NX 2027. Delete DB:BUCK before a run that needs the others, and delete DB:EIGV/DB:SPLC/DB:PDEL before the buckling run; re-create and re-run afterwards. P-Delta coexists with eigenvalue and response spectrum (it only emits a [警告] about the forced-displacement DOFs)"},
    {"area": "analysis", "trap": "asking for P-Delta in ACTL",
     "symptom": "ACTL has no second-order field",
     "fix": "P-Delta lives in DB:PDEL (ITER/TOL/PDEL_CASES)"},
    {"area": "design", "trap": "expecting the steel code check to run off DB:MATL alone",
     "symptom": "CODE-ANAL answers HTTP 400 'failed:SectionType, LoadCombination' however complete the model looks; DB:LCOM-STEEL (the design module's own combination set) is empty while DB:LCOM-GEN is full, and SMODI reports FY 0.0",
     "fix": "the KDS steel module keeps its own inputs: DSTL selects the code, SMODI holds Fy/Fu (DB:MATL.PARAM carries only E/nu/alpha/density - there is no yield field there at all), DCTL defines the frame, SRDF the reduction factors, LENG the unbraced lengths, and DB:LCOM-STEEL the design combinations. Set all of them and read each back. If CODE-ANAL still reports 'SectionType, LoadCombination' the module's section-classification input has no exposed endpoint on this build: record UNSUPPORTED with the verbatim response rather than reporting a ratio"},
    {"area": "design", "trap": "registering design members by name of element type",
     "symptom": "MEMB answers 'Please Select the connected element.' or '所选单元中没有单元被指定为构件.(特性不同)' (member properties differ) for some element lists but HTTP 200 for others",
     "fix": "MEMB accepts TRUSS and BEAM elements alike - one member per element always works. What it rejects is an element list that is not a connected path, or one whose members differ in section/type. Register members in connected runs of a single section, or one member per element"},
    {"area": "design", "trap": "mixing the DSTL code and the route code",
     "symptom": "404 when a GB code is used as a route path segment",
     "fix": "DSTL: GB50017-17 etc.; route codes JAPAN-ROAD-II-H14 etc."},
    {"area": "stage", "trap": "STAG ACT_LOAD naming a load CASE",
     "symptom": "HTTP 400 with a bare 'Unknown Error' (no detail at all), even though every field name matches /info/db/STAG",
     "fix": "ACT_LOAD.LOAD_NAME names a LOAD GROUP (DB:LDGR), not a load case. Create DB:LDGR records with the same names as the load cases the stages activate, then reference those. Verified live: LOAD_NAME='LG1' -> 201, LOAD_NAME='DEAD' (a load case) -> 400 'Unknown Error'"},
    {"area": "stage", "trap": "STAG ACT_LOAD.DAY given as a JSON number",
     "symptom": "HTTP 400 '[错误] 施工阶段 荷载组输入错误(项目:加载时间)' (load group input error, item: load time)",
     "fix": "DAY is a STRING: 'FIRST', 'LAST', or a numeric string of days. DAY=1 (number) -> 400; DAY='1' is the same rejected case only because the referenced group was invalid; DAY='FIRST'/'LAST' -> 201. The manual's example '5.000000' shows the numeric-string form"},
    {"area": "stage", "trap": "STAG ACT_BNGR.POS given a boolean or 'FIRST'",
     "symptom": "HTTP 400 'Wrong Field' on an otherwise valid stage",
     "fix": "POS is a string enum 'DEFORMED' / 'ORIGINAL' (manual ch10). 'FIRST'/'0'/'1'/true all give 'Wrong Field'; 'DEFORMED' -> 201"},
    {"area": "stage", "trap": "defining DB:STAG but never activating a boundary group",
     "symptom": "every later /doc/ANAL answers HTTP 400 '[错误] 边界条件 没有定义。' (boundary conditions are not defined) although DB:CONS is fully populated, and the message names no endpoint or id",
     "fix": "the mere PRESENCE of DB:STAG switches /doc/ANAL into construction-stage mode. The stage analysis needs the supports addressed as a boundary GROUP, not just as DB:CONS records: create DB:BNGR (NAME/AUTOTYPE), set GROUP_NAME on each DB:CONS item to that group, and list it in the first stage's ACT_BNGR. Delete DB:STAG (and DB:STCT) to leave construction-stage mode again"},
    {"area": "stage", "trap": "defining DB:STAG without DB:STCT",
     "symptom": "the stages are stored but /doc/ANAL runs no stage analysis",
     "fix": "DB:STCT is the stage-analysis control record; set it (FINAL_STAGE names the last stage, or bLAST_FINAL=true) together with the stages"},
    {"area": "stage", "trap": "a support whose node is not in the FIRST stage's activated structure group",
     "symptom": "the construction-stage analysis DELETES that support's DB:CONS record, and the reaction comes back from only the remaining supports (a global moment residual appears where the linear run balanced exactly)",
     "fix": "the stage analysis activates boundary conditions only at nodes belonging to the structure groups activated in that stage, and it rewrites DB:CONS to match. Either include every support node in the first stage's DB:GRUP N_LIST, or expect the later supports to be inactive until their stage. Verified live: 8 supports in DB:CONS -> 4 after ANAL, and the 4 that survived were exactly the nodes in the first stage's group; adding all 98 nodes to that group made all 8 survive"},
    {"area": "stage", "trap": "expecting DB:GRUP N_LIST / E_LIST to be assignable like other records",
     "symptom": "PUT /db/GRUP returns 200 but the list only ever grows - a shorter list does not remove members, and DELETE /db/GRUP answers 'does not support DELETE'",
     "fix": "the GRUP node/element lists are merge-only; there is no way to shrink one through the API, and re-POSTing the key answers 'Key Already Exist'. Build the lists correctly the first time. Consequence: once a node is added to a group it stays, so a group used for a stage partition cannot be re-partitioned"},
    {"area": "post", "trap": "asking a POST/TABLE for a combination by its bare name",
     "symptom": "HTTP 200, and the table comes back with the load cases only - the combination rows are SILENTLY absent, so a report can claim 'no combination results' when the combination was solved all along",
     "fix": "a combination must be requested as '<NAME>(CB)' and a load case as '<NAME>(ST)'. Verified live on POST/TABLE:TRUSSFORCE: ['ULS-01','SLS-01'] -> 0 rows; ['ULS-01(CB)','SLS-01(CB)'] -> 914 rows. MIDAS answers each combination as three envelopes whose row labels carry the bare name plus '(all)'/'(max)'/'(min)', so match returned labels on their base name"},
    {"area": "post", "trap": "reading the self-weight contribution to a load balance from the nodal loads only",
     "symptom": "the DEAD case shows a large residual moment (thousands of kN.m) although the force sum is exact",
     "fix": "the MIDAS native self-weight is a BODY load: it acts at each element's centre of gravity, so it contributes its own moment about the origin. Add that couple, derived from POST/TABLE:ELEMENTWEIGHT (per-element 'Total Weight' x element midpoint, M = sum(-cy*w, cx*w, 0)), to the applied six-vector. Verified live: residual MX/MY 5586/-6994 kN.m -> 0.0075/-0.0094"},
    {"area": "post", "trap": "assuming the supports can always react a load's torque",
     "symptom": "a case with a net moment about the vertical axis leaves a residual MZ equal to the applied torque, looking like a modelling error",
     "fix": "check DB:CONS first. When every constraint ends in 0000 for RX/RY/RZ, no support restrains rotation directly; a pin-jointed grid then resists torque only through the lever arm of its in-plane forces, and a pure torque couple applied at a single node has no such arm. Report it as a property of the support system, not as a numerical failure"},
    {"area": "load", "trap": "believing STYP.bSELFWEIGHT adds the self-weight as a static load",
     "symptom": "the dead-load balance is short by the entire self-weight, or a second DB:BODF record is added to compensate and the weight is then counted twice",
     "fix": "on Gen NX 2027 STYP.bSELFWEIGHT is Convert-Self-Weight-to-Mass: it only feeds the mass matrix for dynamic analysis and adds no static load. The static self-weight comes from exactly one DB:BODF record (LCNAME + FV vector). Verified live on the portal frame: one BODF record with FV=[0,0,-1] reproduced the POST/TABLE:ELEMENTWEIGHT total to 1.3e-5 kN"},
    {"area": "result", "trap": "reading a plane-frame model's unused DOFs as missing or broken data",
     "symptom": "UY/RX/RZ come back 0.000 for every node in every combination, which looks like a dead result column or a wrong DOF mapping",
     "fix": "read DB:STYP first: 1 is the X-Z plane (only DX/DZ/RY active), 2 is Y-Z (DY/DZ/RX), 3 is X-Y (DX/DY/RZ), 0 is full 3-D. The zero rows are the model's own DOF definition, not missing data. Map result columns by the names the reply's own HEAD carries and never translate a DOF name across conventions"},
    {"area": "post", "trap": "matching a result table's columns by literal header text or by position",
     "symptom": "POST/TABLE:ELEMENTWEIGHT reads as unparseable, or a value is silently taken from the wrong column: its HEAD is ['Index','Element','Total Weight',...], the field is 'Total Weight' WITH a space, so a parser that looks for 'TotalWeight' or indexes DATA[i][2] drifts as soon as MIDAS inserts or reorders a column",
     "fix": "index every row by its own HEAD, normalised (case-folded, separators stripped): take the column whose normalised name is 'totalweight', and take the element id from the column normalised to 'element'/'elem', not from a fixed position. Verified live: the same reply yields 3.67757/7.95423/7.95423/3.67757 kN for elements 1-4"},
    {"area": "post", "trap": "checking a load balance with the reaction MOMENT components",
     "symptom": "the moment residual stays large (tens of kN.m) on a model that balances exactly, and each wind case shows a residual equal to the applied overturning moment",
     "fix": "when DB:CONS ends in 0000 for RX/RY/RZ the supports are hinges and the reaction moments are released - they read exactly 0 and carry no information. Take moments about the origin from the reaction FORCES instead: for an X-Z plane frame M = sum(z*FX - x*FZ). Verified live: the false 101.98 kN.m residual became 1e-5, and both wind cases exactly 0"},
    {"area": "post", "trap": "reconciling the dead load without a sign convention",
     "symptom": "the self-weight back-calculated from the support reactions comes out with the wrong sign or magnitude and looks inconsistent with POST/TABLE:ELEMENTWEIGHT",
     "fix": "for an X-Z plane frame the implied self-weight is -(sum(FZ) + every other applied FZ): the roof load acts downward too, so it is ADDED back. Verified live: sum(FZ)=+33.4616 kN with a -10.1980 kN roof load gives 23.2636 kN against ELEMENTWEIGHT 23.2636 kN, residual 1.3e-5"},
    {"area": "post", "trap": "labelling a governing combination from a different component than the value",
     "symptom": "every element's 'governing combination' comes back as the first combination in the list although the values differ; on a plane frame the in-plane moment is M2 (Moment-y) and M3 is identically 0, so a peak taken over M3 degenerates to the first row",
     "fix": "derive the label and the value from the SAME component set: peak |M2| and |M3| together for the value, then report the combination that produced that value. Verified live: elements read COMB1/COMB1/COMB1/COMB1 before the fix and COMB3/COMB3/COMB2/COMB2 after"},
    {"area": "report", "trap": "printing a self-consistency check instead of gating on it",
     "symptom": "a report prints a load-balance residual and still exits 0 with every check PASS, so a model whose weight, equilibrium or governing combination is wrong is reported as verified",
     "fix": "a numerical self-check is a gate, not a paragraph: it belongs in the same PASS/FAIL list as the endpoint checks and in the process exit code. The connector supplies the numbers (result_summary, ELEMENTWEIGHT, REACTIONG); the caller must assert them, and a check that cannot fail is not a check"},
    {"area": "write", "trap": "an id snapshot taken once and reused for the whole session",
     "symptom": "'<EP> keys records on NODE ids that do not exist' is raised for nodes created earlier in the same session, so a correct write looks like a modelling error",
     "fix": "fixed in the connector: the per-family id snapshot now expires after a few seconds and is dropped by every write that changes it - DB: assign and delete (a partially failed delete included), DOC:NEW/OPEN/CLOSE/IMPORT/IMPORTMXT, and the OPE:AUTOMESH / OPE:DIVIDEELEM actions that mint nodes and elements. A failed read is no longer cached either. So if the message still appears, the id really is missing: re-read DB:NODE. The snapshot exists so the crash guard does not re-read NODE/ELEM on every write, and it expires because the model can also be edited by hand in the MIDAS GUI"},
    {"area": "file", "trap": "moving a driver into the package and still launching it "
     "by file path",
     "symptom": "the child MCP server dies instantly, the parent raises 'MCP server "
     "closed its output', and the server's stderr log holds 'ImportError: attempted "
     "relative import with no known parent package'",
     "fix": "launch every in-package entry point as a MODULE - subprocess with "
     "[sys.executable, '-m', 'midas_mcp.frame', '--server'] and PYTHONPATH pointing "
     "at src. A file path hands the interpreter a top-level script, and a module "
     "that uses relative imports has no parent package in that mode. Verified live: "
     "the same driver completed 18/18 once switched from a path to -m"},
    {"area": "report", "trap": "a report that states its own tool list and artifact "
     "directory from literals",
     "symptom": "the header names 4 tools after a 5th was added, and points at "
     "artifacts/PORTAL-FRAME-TEST-001/ while the run wrote to the --out-dir it was "
     "given - so the report sends the reader to another run's files",
     "fix": "anything in a report that describes the run must come from the run: read "
     "the tool list from the tools.json the run itself captured, and derive the "
     "artifact directory from the live out_dir. A hardcoded header is a claim about "
     "a run that has already changed"},
    {"area": "report", "trap": "deciding 'did it work' from a state file the failed "
     "run never overwrote",
     "symptom": "a run that refuses at the preflight leaves the PREVIOUS run's "
     "state.json and report.md in place, so the machine-readable verdict says "
     "ok/SUCCESS and hands back the previous model's report as this run's answer",
     "fix": "drop the state file AND the rendered report when a run starts, and write "
     "a verdict on EVERY exit path including the refusal; then gate the verdict's "
     "report on the analysis value, so only the paths that actually rendered one "
     "(SUCCESS/FAILED) can quote a report.md. Dropping state.json alone is not "
     "enough: the report is read back from its own file, so a refusal still quoted "
     "the previous run's 200-line report - caught only by reading the refused run's "
     "--json output, not by its exit code. Also make ok require analysis==SUCCESS, "
     "a non-empty criterion list and a non-empty self-check list: all([]) is true, "
     "so a run that died before the checks existed is otherwise indistinguishable "
     "from a clean one. Verified live: the refusal now answers {ok: false, "
     "analysis: REFUSED, note: ..., report: ''}"},
    {"area": "delete", "trap": "believing a per-id 'still present' immediately after "
     "DELETE",
     "symptom": "clearing a document prints '4 of 4 delete(s) failed; 0 deleted.' for "
     "DB:LCOM-GEN, yet the collection reads empty a moment later and the preflight "
     "that follows sees a clean document",
     "fix": "MIDAS can answer 200 to a DELETE it applies slightly later. Judge a clear "
     "by the read-back AFTER every collection has been asked to empty, not by the "
     "per-id verification; a driver that judges by the per-id result prints a failure "
     "on every successful clear and trains the reader to ignore the word FAILED"},
    {"area": "write", "trap": "a spec-driven run that silently ignores a mistyped key",
     "symptom": "the model is built without the load or the geometry the caller "
     "described, and every check still passes because the checks only see the model "
     "that was built",
     "fix": "refuse unknown spec keys by name and list the known ones, and derive every "
     "secondary quantity from the spec - slope, element lengths, and the legacy "
     "per-load scalars - resetting them FIRST, so a spec that drops a load cannot "
     "leave the previous run's value behind and have the report quote it"},
    {"area": "report", "trap": "a parameterised run whose report still describes the "
     "model the driver was built against",
     "symptom": "the spec changes the span, the sections or the supports and the "
     "analysis is correct, but the report's model table still reads '20 m', '5', "
     "'N1/N5', 'COLUMN_H400X200X8X12' - and the pre-solve stability check passes or "
     "fails against node ids ('1', '5') that the spec never named",
     "fix": "every label in the report and in the checks must be derived from the "
     "installed model rather than written as text: geometry and counts from the model, "
     "section names and dimensions from the section records, support ids from the "
     "spec's own node list, the pinned/fixed wording from the CONSTRAINT string "
     "itself, the units from the response's DIST/FORCE, and the '8 extremes' count "
     "from the number of peaks. Where a value genuinely cannot be derived - a "
     "structure code this driver has not verified - print the raw code instead of a "
     "familiar plane name. A literal is a claim about a run that has already changed"},
    {"area": "file", "trap": "running 'python -m midas_mcp.frame' from a source "
     "checkout that has no src on the path",
     "symptom": "ModuleNotFoundError: No module named 'midas_mcp' - while the same "
     "checkout's unittest run passes, because the first test module discovered "
     "happens to insert <root>/src into sys.path and every later module inherits it",
     "fix": "install once with 'pip install -e .' or set PYTHONPATH=src for the "
     "command; a tool that spawns the driver must export it itself, because only the "
     "environment is inherited, never the parent's sys.path. Verified live: the "
     "one-shot run only started once PYTHONPATH pointed at src"},
    {"area": "report", "trap": "reading the frame verdict from the top level of the "
     "'midas_frame_run' answer",
     "symptom": "the reply's 'ok' is there but 'analysis', 'criteria', 'verifications' "
     "and 'steps' all read as missing, and the 'report' looks misplaced - the shape "
     "does not match the CLI's '--json' verdict, so a caller concludes the tool "
     "failed when it simply answered in its own envelope",
     "fix": "the tool always answers {ok, endpoint, method, status, category, message, "
     "report, data}: 'report' is the rendered report at the TOP level and the verdict "
     "of the same shape as --json is nested under 'data'. Read ok/report from the "
     "envelope and the counts from data. A refusal is a normal answer in that shape - "
     "ok false, category MODEL_NOT_EMPTY, report empty - not a transport error, so a "
     "client that only accepts a JSON-RPC 'result' envelope will see nothing at all"},
]

RECIPES: dict[str, dict] = {
    "modal-rs": {
        "title": "Eigen + response-spectrum workflow",
        "steps": [
            "set EIGV.TYPE=LANCZOS and an explicit mode count",
            "define SPLC with one aUSEMODE entry per mode",
            "add the spectrum function (SPFC, aFUNC as g multiples)",
            "run /doc/ANAL once to produce static + modal + RS results together",
            "read periods from POST:TABLE:EIGENVALUEMODE and its SUB_TABLES",
        ],
        "note": "EIGV and SPLC must coexist or ANAL answers 'Analysis is not allowed.'",
    },
    "steel-frame": {
        "title": "steel portal frame: model, analyse, then prove the results",
        "steps": [
            "declare the model's plane first - DB:STYP 1=X-Z, 2=Y-Z, 3=X-Y, 0=3-D - "
            "and read it back: it defines which DOFs are live, so the result columns "
            "can be mapped without guessing DOF names",
            "DB:UNIT -> DB:MATL (PARAM.P_TYPE=2 with E/POISN/DEN) -> DB:SECT "
            "(SHAPE='H', vSIZE [H,B,tw,tf] in metres) -> DB:NODE -> DB:ELEM (TYPE='BEAM')",
            "DB:CONS with an explicit constraint string: 1110000 is DX/DY/DZ fixed and "
            "RX/RY/RZ free. Do not release the beam-column moment connections - it is "
            "a rigid frame and those connections are the frame's whole behaviour",
            "DB:STLD load cases, then the self-weight as exactly ONE DB:BODF record "
            "(LCNAME + FV=[0,0,-1]). STYP.bSELFWEIGHT adds no static load, so setting "
            "it here as well double-counts the weight",
            "DB:BMLD beam loads, keyed per element with a per-element ITEMS id",
            "DB:LCOM-GEN combinations (iTYPE 0=Add, 1=Envelope, 2=ABS, 3=SRSS)",
            "DB:EIGV TYPE=LANCZOS with an explicit iFREQ, then read iFREQ back BEFORE "
            "running DOC:ANAL - widening the table request changes nothing",
            "DOC:ANAL once. A [警告] body is a warning, not a rejection: confirm by "
            "reading a result table rather than believing the status code",
            "read results with '<NAME>(ST)' for cases and '<NAME>(CB)' for "
            "combinations; each combination answers as (all)/(max)/(min) envelopes",
            "prove the run with the 'load-balance' recipe before quoting any extreme "
            "value, and put that proof in the PASS/FAIL list",
            "for the steel check use DESIGN:STEEL:*:CODE-ANAL then *:CODE-TABLE; the "
            "/post/TABLE design-force endpoints return empty on this build",
        ],
        "note": "any model edit invalidates results; re-run /doc/ANAL before reading. "
                "Every reported extreme must name the element/node AND the combination, "
                "and the combination must come from the same component as the value. "
                "For a single-bay steel portal frame do not do this by hand at all - "
                "the 'one-shot' recipe runs this whole list in one call.",
    },
    "load-balance": {
        "title": "prove a load case by equilibrium before quoting results",
        "steps": [
            "read DB:UNIT first - every number below is in those units",
            "read POST/TABLE:REACTIONG for the case ('<NAME>(ST)') or the combination "
            "('<NAME>(CB)') and sum the reaction FORCES. Do NOT use the reaction "
            "moments: with constraints ending in 0000 for RX/RY/RZ the supports are "
            "hinges and those components read exactly 0",
            "for an X-Z plane frame take moments about the origin from the forces: "
            "M = sum(z*FX - x*FZ)",
            "build the applied six-vector from the loads you wrote, plus the "
            "self-weight couple: POST/TABLE:ELEMENTWEIGHT gives per-element "
            "'Total Weight' w acting at the element centroid, so add "
            "M = sum(-cy*w, cx*w, 0)",
            "residual = sum(reactions) + applied, per component. Assert it - do not "
            "print it",
            "for the DEAD case also reconcile the weight itself: implied self-weight "
            "= -(sum(FZ) + every other applied FZ) must equal the ELEMENTWEIGHT total",
        ],
        "note": "verified live on a single-storey steel portal frame: force and moment "
                "residuals 1e-5, both wind cases exactly 0, and the DEAD self-weight "
                "reconciled to 1.3e-5 kN. A check that cannot fail is not a check.",
    },
    "rc-section": {
        "title": "RC member + rebar",
        "steps": [
            "rect sections use SHAPE='SB' with SECT_I.vSIZE [H,B] in meters",
            "concrete PARAM.STANDARD 'GB(RC)' + DB 'C30' for Chinese code",
            "MATD rebar grades carry a space ('Class A'), set MAINREBAR_B_FY (N/m^2)",
            "DCON key '1'; DELETE /db/DCON/1 before switching DGNCODE",
        ],
        "note": "accepted DGNCODE set is narrow (ACI318, KCI-USD, GB50010-02, BS8110-97).",
    },
    "one-shot": {
        "title": "one call: spec -> model -> analysis -> verified report",
        "steps": [
            "reach for this FIRST. A steel portal frame end to end - build, "
            "analyse, self-verify, report - is one call: the midas_frame_run "
            "tool, or `python -m midas_mcp.frame --spec specs/portal-frame.json`",
            "pass the model as a spec: an object, or spec_path for a file. "
            "Omitted keys keep the validated 20 m span / 6 m eave / 8 m ridge "
            "frame; an unknown key is refused by name, never ignored",
            "read the verdict, not the log. --json prints one line: {ok, "
            "analysis, criteria, verifications, steps, failed, note, report}. ok "
            "is true only for analysis==SUCCESS with a non-empty criterion list, "
            "no failed criterion, and self-consistency checks that ran and passed",
            "a refused run answers analysis=REFUSED with a note and an empty "
            "report: the live MIDAS document was not empty. Pass clear=true / "
            "--clear, or clear it in the GUI",
            "the report is the answer. report.md lands in out_dir beside "
            "state.json, the raw res_*.json responses and the mcp_audit.jsonl / "
            "http_audit.jsonl trail",
        ],
        "note": "verified live: 18/18 steps, 13/13 criteria, 4/4 self-consistency "
                "checks, analysis SUCCESS, exit 0, about 5 minutes. Drive "
                "midas_db_assign by hand only when the model is not a steel "
                "portal frame.",
    },
}


def pitfalls_markdown() -> str:
    lines = ["# MIDAS knowledge: validated pitfalls\n"]
    for i, p in enumerate(PITFALLS, 1):
        lines.append(f"## {i}. {p['area']} — {p['trap']}\n")
        lines.append(f"- symptom: {p['symptom']}\n- fix: {p['fix']}\n")
    return "\n".join(lines)


def recipe_markdown(name: str) -> str:
    r = RECIPES[name]
    lines = [f"# MIDAS recipe: {r['title']}\n"]
    for i, s in enumerate(r["steps"], 1):
        lines.append(f"{i}. {s}")
    if r.get("note"):
        lines.append(f"\n> note: {r['note']}")
    return "\n".join(lines)


def routing_markdown() -> str:
    return (
        "# MIDAS routing rules\n"
        "- for a steel portal frame the whole job is ONE call: the midas_frame_run "
        "tool, or `python -m midas_mcp.frame --spec specs/portal-frame.json`. It "
        "builds, analyses, self-verifies and returns the report - read "
        "midas://recipes/one-shot before driving the steps below by hand\n"
        "- use midas_db_query for reads and to discover endpoints (search)\n"
        "- use midas_db_assign for writes/actions; mode create=POST, update=PUT\n"
        "- use midas_db_delete with explicit target_ids; never 'delete all' implicitly\n"
        "- use midas_doc for NEW/SAVE/ANAL; CALL /doc/ANAL only after the model is ready and never auto-retry it\n"
        "- read results only after a successful ANAL; re-run ANAL after any model change\n"
        "- modal/eigen questions (frequency, period, participation mass, mode shape) are answered by POST:TABLE:EIGENVALUEMODE; buckling by POST:TABLE:BUCKLINGMODE. Their summaries are in the reply's SUB_TABLES, parsed into result_summary.modal_result / .buckling_result\n"
        "- never conclude a result is absent because the primary table is empty; check SUB_TABLES first\n"
        "- the recipes midas://recipes/steel-frame and midas://recipes/load-balance "
        "are the worked sequences for a frame: build order first, then the "
        "equilibrium proof. Read 'load-balance' before reporting any extreme value\n"
        "- a self-consistency check (equilibrium residual, self-weight "
        "reconciliation) is a gate, not a paragraph: put it in the same PASS/FAIL "
        "list as the endpoint checks and in the exit code\n"
        "- the MAPI-Key is server-side only; it never appears in tool results\n"
    )