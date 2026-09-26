## ⚠️ Breaking

### `delete_all()` requires `confirm=True`

```python
Node.delete_all()                 # now raises DestructiveOperationError
Node.delete_all(confirm=True)     # proceeds
```

`delete_all()` empties an entire table — for `/db/NODE` that removes every
element attached to those nodes as well — and there is no undo through the
API. It was the one destructive call in the SDK with no guard on it, and the
products raise no confirmation dialog on the API path.

The guard runs **before the request is built**, so a mistaken call costs
nothing. Only the literal `True` is accepted; a truthy value is not enough.
The new `DestructiveOperationError` descends from `MidasAPIError`, so existing
`except MidasAPIError` handlers still catch it.

This shipped without a deprecation cycle on purpose: during that cycle the
hazard would stay armed, which is the thing being fixed. The migration is one
keyword. See the deprecation policy in `CONTRIBUTING.md`.

`delete(ids)` is unchanged and remains the way to remove specific records.

## Added

- **Per-request timeouts.** `request()`, `post_argument()`, `get_result()` and
  `verify_connection()` accept `timeout=`, overriding the client default for
  that call only. A `(connect, read)` tuple works. This makes the documented
  workaround for the hanging `*-ANAL` design-check family expressible: give up
  waiting quickly, then read the matching `*-TABLE` back.
- **A documentation site** (MkDocs Material), with an API reference generated
  from the docstrings — where this project's live-verification warnings
  already live, so they are now searchable rather than only visible in an
  editor tooltip. New pages: *Destructive operations and recovery*, and *How
  endpoints are verified*.
- **`SECURITY.md`** (private reporting; product vulnerabilities are explicitly
  out of scope for this repo's public tracker) and **`CONTRIBUTING.md`**
  (setup, the endpoint loop, live-verification safety rules, and an explicit
  SemVer/deprecation policy).

## Changed

- **Live-verification numbers are split into read and write.** The old
  "392/398 live-verified" conflated two claims that prove different things.
  `ROADMAP.md` now reports **63 write / 329 read / 6 unverified**, with a
  per-product breakdown, and each `live_verified` entry in
  `docs/coverage.json` carries a `level`.

  A GET that answers proves the route exists and the response parses. It says
  nothing about whether the payload this SDK *sends* is one the server
  accepts — and nearly every substantive defect found in this project was
  invisible to reads (`/db/REBW`'s field names, `/db/TDMT`'s enum,
  `/db/SECF`'s key, `/db/PRES`'s default, `/db/MVHL`'s silent downgrade).
  Nothing was reclassified upward and no record was deleted.

- **Project status is now stated up front.** The README, PyPI summary and the
  three quickstart guides say that this is built by a MIDAS IT employee from
  hands-on verification, that it is **not an officially released or supported
  MIDAS IT product**, and where each kind of problem should go.

- `verify_connection()` documents that it **cannot detect a dialog-blocked
  session** — it keeps answering `"connected"` while every `/db/*` call times
  out. It is a key-validity check, not clearance to run a destructive
  operation.

## Fixed

- **`get_table()`'s `additional` / `set_calculation_method` were typed
  `dict[str, Any]`**, which every `TypedDict` caller in `post/story.py` is
  deliberately not assignable to — ten call sites that could not type-check.
  Now `Mapping[str, Any]`. Found by mypy on its first run.
- All 12 relative links in the README were broken on PyPI, which renders it
  outside the repository. Now absolute, with every target verified to exist.
  The same bug in the three quickstart guides was caught by building the docs
  in `--strict` mode.
- `Development Status` classifier was still `4 - Beta` at v1.1.0.
- The real e-mail address and connection ID in a test fixture are now example
  values.

## Infrastructure

- **mypy** over `src/midas_nx`, clean across all 41 modules, with its own CI
  job. Deliberately not `--strict`: the payload TypedDicts document a heavily
  conditional external schema rather than model it.
- **The full 3.9 / 3.10 / 3.11 / 3.12 / 3.13 matrix** now runs, rather than
  only the two ends of the range the classifiers claim.
- **A packaging job** builds the wheel, installs it into a clean virtualenv
  and runs `scripts/wheel_smoke_test.py` from outside the source tree,
  asserting that `py.typed` shipped, that `__version__` matches the installed
  distribution, that subpackages import, and that the `delete_all()` guard is
  armed in the built artifact.
- `publish.yml` now runs ruff, mypy, pytest, `twine check` and the wheel smoke
  test *before* publishing, and fails if the release tag doesn't match
  `__version__`. PyPI attestations are enabled.
- GitHub Actions pinned to commit SHAs, with Dependabot to keep the pins
  fresh. `pypa/gh-action-pypi-publish` deliberately stays on `release/v1`.

## Not done, deliberately

The review that prompted this release also proposed an optional runtime
validation layer. It is not implemented, and the reasoning is recorded rather
than left implicit:

- Product and HTTP-method validation already exist (`DbResource._check`).
- Required-key validation would duplicate the static types across 682 schemas.
- **An enum validator built from the manual would reject payloads that
  actually work.** The documented enum values have repeatedly been wrong live
  — `/db/TDMT` wants `"European"`, not any CEB-FIP spelling the manual lists.

Automatic retries were also proposed. There is no retry logic in this package
at all, and that is the correct behaviour for an API where a timeout is not a
rollback: a retried `POST` against an endpoint that already succeeded is a
second write.

`Required`/`NotRequired` beyond the core resources is deferred. When it lands
it will follow live CRUD confirmation, not the manual's requiredness column.

## Docs deployment

The documentation site builds and is gated in CI, but is **not yet
deployed** — GitHub Pages has to be enabled once (Settings → Pages → Source:
GitHub Actions). Until then the `Documentation` URL still points at the
README rather than publishing a 404 to PyPI.
