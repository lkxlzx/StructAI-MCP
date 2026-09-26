## Fixed

- **`post.result_1.get_concurrent_joint_force_table()` (added in v2.3.0)
  was missing `node_elems`, `components`, `opt_cs`, and `stage_step`.**
  Its docstring claimed the manual doesn't document these for this table
  type — it does: `19_POST_AnalysisResult_1.md`'s common 10-item
  parameter table explicitly applies to all 13 tables in the chapter,
  and this table's own note says `ADDITIONAL` is added *on top of* those
  10 items, not in place of them. `COMPONENTS` in particular drives
  which "Elem./Component" column blocks the response repeats. Without
  these four parameters, a caller had no way to scope the query to
  specific nodes/elements, filter displayed components, or select a
  construction-stage step — every sibling function in the same module
  exposes all four. All four are now exposed and forwarded to
  `get_table()`; the docstring no longer denies they apply.

## Docs

- `ROADMAP.md` regenerated: a v2.3.0 commit corrected a
  `docs/coverage.json` date (`2026-08-07` → `2026-08-10`) after
  `ROADMAP.md` had already been generated from the pre-fix state,
  leaving the committed file stale.

## How this was found

A `/code-review` pass against v2.3.0's commit, cross-checking its new
function against the manual source directly rather than trusting the
commit's own docstring claims. Two independent verification passes
(the review's own manual re-read, plus a background re-run of
`scripts/gen_roadmap.py` against the committed `coverage.json`)
confirmed both findings before any fix was applied.
