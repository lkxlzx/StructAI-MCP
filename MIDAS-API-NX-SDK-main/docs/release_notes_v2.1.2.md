Packaged-metadata-only release. No `src/midas_nx/` behaviour changed.

## Changed

- **The first example everywhere is now read-only.** `README.md`,
  `docs/index.md`, and all three `docs/{en,ko,zh-tw}/quickstart.md` guides
  led with a script that called `doc.new_project()`, which discards unsaved
  work in whatever document is currently open in Gen NX/Civil NX — and has
  crashed Gen NX outright when that document was a large real model. The
  first example everywhere is now `verify_connection()` + `Node.items()`,
  which cannot change anything. The original model-building script moved to
  an explicit, warning-labeled "Step 5 (optional)" in each quickstart, and
  `examples/python/quickstart.py` gained a warning docstring plus a new
  read-only sibling, `examples/python/verify_and_read.py`. Quickstart also
  gained a short note on handling the MAPI-Key it has users paste into a
  script (don't commit it, don't share screenshots of it).
- **New `docs/ai-coding/` section** for users who plan to have an AI
  assistant write the Python instead of learning it themselves — a path the
  quickstarts already pointed to in "Next steps" but gave no supporting
  material for. `context-pack.md` is a copy-pasteable block covering the
  real API shape, the error hierarchy, and this SDK's specific ways of
  hurting you if used carelessly; `safe-start.md` explains how to use it,
  with a task-description template, a pre-run review checklist, and a
  sanitized error-follow-up template.
- **`docs/index.md`'s "Where to go" table split into two entry paths.** The
  six-row table with no priority order is now a "How would you like to
  start?" choice between learning Python and building with an AI assistant,
  with the remaining reference links kept in a smaller table below. README's
  "Learn more" table gained the same AI-assisted-coding link.
- **New Risk levels table (0-4) in `docs/safety.md`**, with level badges
  added to every example the three changes above touch. Notably, the
  quickstart's Step 5 demo — which just adds one column — is level 4 (high
  risk) purely because it calls `doc.new_project()`, independent of how
  small what it builds is.
- Three superseded/reference onboarding-planning drafts archived under
  `docs/planning/` (excluded from the mkdocs build) instead of left at the
  repo root.

## Why a version bump for a docs change

`pyproject.toml` declares `readme = "README.md"`, so the README is packaged
metadata, not just a repo file — this is the one category of doc change this
project's release policy treats as bump-worthy on its own (same reasoning as
v2.0.1).
