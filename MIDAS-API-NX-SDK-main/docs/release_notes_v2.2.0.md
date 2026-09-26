## Changed (breaking)

- `post.pre_process.get_story_load_summary_table()`'s `TABLE_TYPE` values
  renamed: `STORY_LOAD_SUMMARY_X/Y/Z` → `STORY_LOAD_X/Y/Z`, matching
  `STORY_MASS`'s naming convention. Both renames were requested together
  against MIDASIT; the `STORY_MASS` half was already applied in an earlier
  manual sync, this release closes the remaining `STORY_LOAD` half. Code
  that calls `get_story_load_summary_table()`
  through this SDK needs no changes — the function's own `direction`
  parameter already builds the string internally. Code that passed the old
  `TABLE_TYPE` string directly to the server (bypassing this function) will
  now get rejected instead of a result.

## Added

- `get_story_load_summary_table()` gains `unit`, `styles`, `components`,
  and `load_case_names` parameters.
- `get_story_weight_table()` gains `unit`, `styles`, and `components`
  parameters (its `TABLE_TYPE`, `"STORYWEIGHT"`, is unchanged).
- `post.design.get_wall_design_forces_table()` gains a `story_names`
  parameter, restricting results to specific stories (the original request
  against MIDASIT used the key `"STORY"`, but the shipped param is
  `"STORY_NAMES"`, matching ch20/ch21's naming).
- New endpoint: `design.rc_kds.setup.RcDesignCodeSelection`
  (`/DESIGN/RC/DRC`, GET/PUT/DELETE) — selects the active RC design code.
  Its GET response nests under the key `"DCON"` (neither the endpoint name
  nor the sibling `DCO` option endpoint's name), per the manual itself;
  `DbResource.items()`'s existing shape-based unwrapping already handles
  this without any special-casing.

## How this was found

`scripts/check_manual_drift.py` flagged real, non-cosmetic drift against
the vendored manual repo's 2026-08-06 sync commit, which itself filtered
32 flagged updates down to 4 confirmed real changes across three files
(`18_POST_PreProcess.md`, `23_POST_Design.md`,
`26_Design_RC_KDS41202022.md`). Cross-checking with MIDASIT confirmed all
three changes are the actual shipment of long-standing requests rather
than new asks. `docs/coverage.json`'s `vendored_at_commit` is now current
with that sync
(`f4a55e7`), and `check_manual_drift.py` reports `has_diff: false`.
Endpoint count: 398 → 399.
