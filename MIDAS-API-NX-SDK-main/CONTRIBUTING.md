# Contributing to midas-nx

Thanks for looking. This is an employee-led open-source project, not an
officially supported MIDAS IT product — see the README for what that means for
support expectations.

## Where to report what

| Problem | Where |
| --- | --- |
| SDK bug, wrong payload shape, missing endpoint, docs | [GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues) |
| Security vulnerability in this package | [SECURITY.md](./SECURITY.md) — privately, not a public issue |
| MIDAS Gen NX / Civil NX product, licensing, Open API service | MIDAS IT official support channels |

If a call fails, say which **product and build** (Help → About) — behaviour
differs between Gen NX and Civil NX, and between builds of the same version.

## Setup

```bash
pip install -e ".[dev]"
cd packages/typescript
npm install
```

Three checks must pass before any commit. CI runs exactly these:

```bash
pytest                        # ~1160 tests, no live server needed
ruff check src tests scripts
mypy

cd packages/typescript
npm run generate              # derives npm resources/types from contracts/
npm run typecheck
npm test
```

Generated TypeScript files and `schema/typescript-coverage.json` are committed.
The generator fails if any row in `docs/coverage.json` is not represented in
the npm SDK, and CI fails if generated output has drifted. When the official
manual changes, update `contracts/` first — it is the source of truth both
SDKs implement — then the reviewed Python model and the coverage ledger, and
regenerate both language surfaces in the same change.

`npm run generate` reads the contracts for everything it can: since
2026-09-22 no generated type's shape comes from a Python `TypedDict`. It
still parses `src/midas_nx/` for three endpoints with no permitted source
(the IEHG trio), which is why it needs the Python source tree present, and
why `npm publish` does too — `prepack` runs generation before packing.

The test suite mocks HTTP with `responses`. **Nothing in it touches a real
MIDAS NX session**, and it must stay that way — tests have to run in CI, where
no product is installed.

## Adding or changing an endpoint

`CLAUDE.md` has the full loop; the short version:

1. Scaffold from the manual chapter in the sibling
   [MIDAS-API](https://github.com/Dennis5882/MIDAS-API) repo via
   `scripts/gen_endpoint.py`.
2. Follow `src/midas_nx/db/node_element.py` as the reference pattern:
   `ENDPOINT` / `NAME` / `PRODUCTS` / `METHODS`, with a `{ClassName}Payload`
   TypedDict directly above the class.
3. TypedDicts are **documentation, not runtime validation** — the real schemas
   are too conditional for one flat model. Put the manual's
   requiredness/default in a trailing comment per field rather than trying to
   encode it in the type.
4. Add a test mirroring `tests/db/test_node_element.py` — assert the request
   shape (URL, headers, JSON body).
5. Mark it `"implemented"` in `docs/coverage.json`, then re-run
   `python scripts/gen_roadmap.py`. **Never hand-edit `ROADMAP.md`** — it is
   generated.

## Two things that will get a PR sent back

**Don't encode a manual claim as verified fact.** The official documentation
has been wrong about field names, enum values, and defaults — repeatedly, and
in ways only a live round trip caught. If the manual says it but nobody has
seen it work, write it as the manual's claim, not as confirmed behaviour.

**Don't weaken a safety guard to make something pass.** `delete()` issues one
request per id on purpose; `delete_all()` requires `confirm=True` on purpose.
Both exist because the documented alternative was measured destroying an
entire table. Same for `MidasResultError`: a 200 response carrying an
`{"error": ...}` body is a failure, and turning that check off to get a green
test is not a fix.

## Live verification

Scripts under `scripts/` that talk to a real product are **not** run by CI and
should not be run casually:

- `scripts/live_readonly_sweep.py` — GET only. Safe against a model you have
  open.
- `scripts/live_smoke.py` — calls `/doc/NEW` and **discards unsaved work**.
- `scripts/live_crud_check.py` — creates, updates and deletes real records.

Never point the last two at a session holding a model that matters. Some calls
have crashed the product outright; `docs/live_verification_notes.md` records
which, and is worth reading before your first live run.

If you do verify something live, record the product, build, date and what you
actually observed — including a negative result. Don't upgrade an endpoint's
`live_verified` entry in `docs/coverage.json` on the strength of a call that
merely didn't error.

A `live_verified` entry looks like this, and **`level` is required**:

```json
"live_verified": {
  "date": "2026-08-02",
  "products": ["gen"],
  "level": "write",
  "method": "scripts/live_crud_check.py (full CRUD round trip)",
  "nx_versions": { "gen": "MIDAS Gen NX 2026 (v2.1), build 07/30/2026" }
}
```

`level` is `"write"` only if the call **actually mutated** something — model
data, or a file on the NX host — and that was confirmed. Everything else is
`"read"`, including POST-shaped reads like `/post/TABLE` and report calls that
returned "Please perform analysis" without producing output. The HTTP verb
does not decide this; what the server actually did decides it. ROADMAP.md
counts the two separately, and will warn if an entry has no `level`.

## Versioning and compatibility

[Semantic Versioning](https://semver.org/). The public API is everything
exported from `midas_nx` plus the documented resource classes and endpoint
functions — not private helpers (`_`-prefixed), and not the exact wording of
an exception message.

**Python:** 3.11+. v2.1.0 dropped 3.9–3.11 together, because 3.9 was past its
own EOL and three dependency floors were stuck behind it; 3.10 and 3.11 went
with it although nothing in the code needed 3.12. 3.11 came back in 2.9.0 after
the whole suite was run on it. 3.10 stayed out: it reaches EOL in October 2026,
and `requests`, `pytest` and `mypy` all floor at 3.10 today, so the next
dependency bump would force it out again. Every version in the classifier list
is tested in CI. Dropping one is a minor bump at least, announced in the
release notes.

**MIDAS NX:** there is no single "supported version" — the same endpoint can
behave differently across products and builds. What a release claims is what
was actually observed, recorded per endpoint in `docs/coverage.json` and
narratively in `docs/live_verification_notes.md`. A product-side change can
therefore break a working call without any release here.

**Deprecation:** the normal path is deprecate in one minor release
(`DeprecationWarning`, still functional, replacement named in the message and
release notes), remove in the next major.

**The exception is safety.** A default that can destroy a user's model is not
kept working for a deprecation cycle just because SemVer would prefer it —
during that cycle the hazard stays armed, which is the thing being fixed.
Such a change ships immediately, is called out at the top of the release
notes, and the fix is always a one-line edit at the call site.

This has happened once, and is the precedent: `delete_all()` now requires
`confirm=True`, and raises `DestructiveOperationError` without it — before
sending anything, so a mistaken call costs nothing.

```python
Node.delete_all()                  # before
Node.delete_all(confirm=True)      # now
```

## Commits

Imperative subject, body explaining *why*. Match `git log`.
