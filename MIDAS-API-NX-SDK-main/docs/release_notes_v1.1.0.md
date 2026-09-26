## Manual sync

The sibling `MIDAS-API` manual repo had drifted 3 commits since this SDK last
vendored it. `docs/coverage.json`'s `vendored_at_commit` is now current.

## ⚠️ Breaking

### Wall Force no longer accepts `sect_position`/`parts`

`get_table()` drops its `sect_position` parameter entirely, and
`get_wall_force_table()` drops both `sect_position` and `parts` — the server
never supported either field. If you were passing either argument to
`get_wall_force_table()`, remove it.

## Fixed

- **`STORY_DRIFT_METHOD`'s first enum value, for Story Stability Coefficient
  specifically, is `"Drift on the Center of Mass"`, not `"...at..."`.**
  Unlike Stiffness Irregularity Check (#13) and Weight Irregularity Check
  (#17), which do use `"at"`, this table's product screen genuinely says
  `"on"`.

## Added

- **`VehicleKsceLsd15Params`** (`db/moving_loads.py`) — the `VEH_KSCE_LSD15`
  schema KSCE-LSD15 vehicles actually use instead of `VEH_DEFAULT`. Also
  documents that `MVLD_CODE` should be `13` for this shape, not `1`.
- **`ADDITIONAL.SET_ANGLE`** on Ultimate Story Shear Force Check (`post/story.py`
  `get_ultimate_story_shear_force_check_table()`) — newly documented,
  previously undocumented entirely. Optional, defaults to `ANGLE=0`.

## Maintenance

- Fixed a bug in `scripts/check_manual_drift.py`: ledger entries whose
  `chapter_file` spans multiple chapters (e.g. `"19_....md / 20_....md"`)
  never matched an individual changed filename, producing a false
  "not yet implemented" report.
- `PLAN.md` synced to the current release state; the release checklist in
  `CLAUDE.md` now folds the `PLAN.md` update into the same commit as the
  code changes.
