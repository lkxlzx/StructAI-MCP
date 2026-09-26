# midas-nx 2.8.2

A shared PyPI/npm version release. **Additive on both surfaces; nothing breaks.**

| surface | what actually changed |
| --- | --- |
| Python | one new endpoint, `DESIGN/STEEL/DSTL`, and a corrected description of `opt_cs` |
| npm | the same endpoint, three new `MaterialModifyConcretePayload` members, `bPJ` on the curved tendon profile, and the same `OPT_CS` description |

No exported name is removed or renamed and no member narrows: npm goes from 741
exported payload types to 742, the one addition being the new endpoint's.

## Added — `DESIGN/STEEL/DSTL`, the steel design-code selector

`SteelDesignCodeSelection` in Python, `steelDesignCodeSelection` in npm. It
selects which steel design code a project uses — today the manual lists one
value, `"KDS 41 30 : 2022"` — and it is the steel counterpart of
`DESIGN/RC/DRC`, which the SDKs have carried since 2.2.0. GET, PUT and DELETE;
no POST.

**It is not `/db/DSTL`.** That endpoint already existed as `SteelDesignCode`,
shares the name, and has a different URI and schema; the manual says so
explicitly and a test pins the two URIs apart. If you were using `/db/DSTL`,
nothing about it changed.

The endpoint was documented by the manual and has **not yet been called against
a product** — it is the one of 400 endpoints with no live evidence. It has no
contract for the same reason: this repository promotes a contract only once
something has answered live, so npm generates this resource from the Python
class until then.

## Added on npm — members the manual now documents

- `MaterialModifyConcretePayload` gains `bSERVCHECK`, `dSHORTTERM` and
  `dLONGTERM`. The official JSON Schema and live `/info` on both products
  declare them; the article's table and example do not, so their
  requiredness is recorded as unstated and nothing is claimed about when they
  apply.
- `TendonProfilePayload`'s `CURVE` shape gains `bPJ` (Projection), which its
  `ELEMENT` and `STRAIGHT` shapes already had and every one of the manual's four
  curved-tendon examples sends.

## Clarified — `OPT_CS` has three states, and omitting it is not `false`

The manual now documents what the analysis-result tables do with it: `true`
switches the view to Construction Stage and returns CS results, `false` switches
it to PostCS — the final stage — and returns Post results, and **leaving it out
keeps the current view mode**.

Both SDKs already left it out unless you set it, so no request changes. What
changed is the documentation in both, and the contract, which no longer records
`false` as a default: an SDK that filled that default in would switch the
caller's view as a side effect of reading a table. The manual's own Default
column still says `false`, contradicting its own description, and the behaviour
has not been checked live.

## Also in this release, none of it in either package

- **The manual repository is reflected through its 2026-09-15 sync, and CI is
  fully green for the first time since 2026-09-06.** The sync had been held for
  ten days while it was verified. Reflecting it moved **108 manual line anchors
  across 59 contracts** — the drift check named eleven of them, because it reads
  `unmergedTables` and not the variant, missing-column, structural-table and
  source anchors that cite the same lines. They were moved from a line-by-line
  mapping of the two manual versions rather than one by one.

- **43 more endpoints replayed through the npm package**, taking npm live
  evidence from 70 to 113 `/db` endpoints, with the Python harness re-run on the
  same selections on Gen NX 2026 v2.1 and Civil NX 2026 v2.2, both Build
  09/02/2026. That replay found a harness defect Python could never have shown:
  seed names are global in the shared fixture, so two tiers each defining a
  `fbld_seed` with **different** records collapsed to one, and npm replayed the
  wrong seed for one of them. Emitting a fixture now fails on a duplicate name
  with a different payload.

- **Two GitHub Actions moved a major version**: `actions/upload-artifact` to v7
  and `actions/setup-node` to v7. The second stops exporting a placeholder
  `NODE_AUTH_TOKEN`, which is the npm Trusted Publishing path this repository
  publishes through — so this release was published to npm before PyPI, to
  confirm that path before the shared number went out on both.

## Validation

- Python: 1067 tests, ruff and mypy clean.
- npm: 78 tests, typecheck, generation and packed-artifact checks clean,
  including a smoke test against the packed tarball.
- Contracts: schema, SDK parity, field parity, manual drift, the
  `/info`-to-contract sweep, the product-divergence guard and the
  fixture-to-contract check all pass. Nothing is red.
