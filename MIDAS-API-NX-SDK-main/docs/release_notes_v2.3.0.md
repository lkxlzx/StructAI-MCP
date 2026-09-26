## Added

- New endpoint: `post.result_1.get_concurrent_joint_force_table()`
  (`TABLE_TYPE=CONCURRENT_JOINT_FORCE` via `POST /post/TABLE`). For the
  reaction node/component named in its `additional` argument
  (`SET_REACTION_PARAMS.NODE_KEY`/`COMPONENT`), finds each named load
  case's extreme (max/min) reaction instant and reports every other named
  load case's joint force at that same instant — typically paired with
  moving-load `(MV:max)`/`(MV:min)` load cases. Previously undocumented in
  the manual; not yet live-tested.
- `db.static_loads.StaticWindLoadPayload`/`StaticSeismicLoadPayload`
  (`/db/SWIND`/`/db/SSEIS`) each gain fields for a `WIND_CODE`/
  `SEIS_CODE = "USER TYPE"` variant that inputs story-level wind
  pressure/seismic force directly (`STORY_WIND_PRESSURE`/
  `SEISMIC_FORCE`) instead of using the KDS calculation
  (`PARAMETERS`). Purely additive — the existing KDS-code call shape is
  unchanged.

## Docs

- `/ope/GSBG` (Bridge Girder Diagram Image Export) is now documented a
  second time, at `docs/manual/17_DB_Bridge.md` #5 — this is the same
  endpoint already implemented here as
  `ope.generate_bridge_girder_diagram()` (sourced from `15_OPE.md` #19),
  field-for-field identical. No code change; both `ope.py` and
  `db/bridge.py` now cross-reference the duplicate documentation so it
  isn't mistaken for a second endpoint later.

## How this was found

`scripts/check_manual_drift.py` flagged real, non-cosmetic drift against
the vendored manual repo's 2026-08-10 sync commit (`76ebda9`), which
itself confirmed against the official site that three articles (Static
Wind/Seismic Load, Bridge Girder Diagrams, Concurrent Joint Force Table)
had genuinely new content, not just timestamp churn.
`docs/coverage.json`'s `vendored_at_commit` is now current with that sync,
and `check_manual_drift.py` reports `has_diff: false`.
