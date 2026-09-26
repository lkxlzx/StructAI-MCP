# midas-nx 2.9.0

A shared PyPI/npm version release. **Python 3.11 is supported again, and the
package is now tested through 3.14.** No code changes in either package.

| surface | what actually changed |
| --- | --- |
| Python | `requires-python` moves from `>=3.12` to `>=3.11`; classifiers list 3.11, 3.12, 3.13 and 3.14. `src/midas_nx/` itself is identical to 2.8.4 |
| npm | nothing — the same tarball content republishes under the aligned number |

## Python 3.11 works, and always did

The `>=3.12` floor was never a property of the code. Measured with `vermin`,
`src/midas_nx`'s real minimum is **3.8**: no PEP 695 type parameters, no
`@override`, no `itertools.batched`, no `typing_extensions`, and no
`sys.version_info` gates anywhere.

v2.1.0 dropped 3.9, 3.10 and 3.11 in a single move, and the reason was 3.9:
it was nine months past its own EOL and three Dependabot floor bumps
(`requests`, `mypy`, `pytest`) were stuck behind it. 3.10 and 3.11 went along
with it.

3.11 comes back measured rather than assumed — the full suite (1,090 tests)
passes on 3.11.15. The same run passes on **3.14.5**, a version `>=3.12`
already allowed but which nothing tested or advertised, so 3.14 joins the
classifiers too.

The CI matrix is now **3.11, 3.12, 3.13, 3.14**, which keeps the rule that
every classifier is a version CI actually runs.

## Why not 3.10

`requests`, `pytest` and `mypy` all still floor at 3.10 today, so nothing
technical blocks it. It stays out on timing: **3.10 reaches end of life in
October 2026**, weeks from this release, and any one of those three raising
its floor would force it straight back out. Adding a version and dropping it
again within weeks is the churn v2.1.0 existed to end.

If you are on 3.10 or older, `pip install midas-nx` will refuse the package
rather than install something untested.

## Documentation

The three quickstarts (`ko`, `en`, `zh-tw`) walked beginners through finding
3.12 or 3.13 specifically on python.org, including a step about using the "All
releases" link when the download button offered something newer. They now say
to take the latest release, and that an existing 3.11-or-newer install needs
nothing. `CONTRIBUTING.md` records why 3.10 is excluded so the question does
not have to be re-derived.

## Nothing else changed

No behaviour, no field, no type. `src/midas_nx/` and the npm `dist/` are what
2.8.4 shipped; this release moves packaging metadata and the versions CI
proves.
