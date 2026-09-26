## ⚠️ Breaking

### Dropped Python 3.9, 3.10, and 3.11

`requires-python` is now `>=3.12`. Installing on 3.9–3.11 will fail; there is
no compatible release for those interpreters going forward.

Python 3.9 reached its own upstream end-of-life on 2025-10-31. This surfaced
indirectly: three open Dependabot PRs (bumping the floor versions of
`requests`, `mypy`, and `pytest`) were all failing the same CI job the same
way — `pip install -e ".[dev]"` on the Python 3.9 matrix entry — because each
of those newer dependency versions had itself already dropped 3.9 support.
Checking why led to the EOL date, which made continuing to support 3.9 a cost
with no corresponding benefit.

3.12 was chosen over the newest release (3.14) specifically to stay clear of
any version not yet past its own EOL, while unblocking all three stuck PRs.

Per the versioning policy in `CONTRIBUTING.md`, dropping a supported Python
version is a minor bump with no deprecation cycle required — unlike the
general public-API breaking-change rule, which requires one release's warning
first.

## Changed

- CI matrix: `["3.9", "3.10", "3.11", "3.12", "3.13"]` → `["3.12", "3.13"]`.
- `[tool.mypy]`/`[tool.ruff]`'s `python_version`/`target-version` now match
  the new floor (`3.12`), and the comment explaining the old
  3.9-vs-mypy's-3.10-minimum gap is gone — that gap no longer exists.
- `pyproject.toml` classifiers: removed the 3.9/3.10/3.11 entries.
