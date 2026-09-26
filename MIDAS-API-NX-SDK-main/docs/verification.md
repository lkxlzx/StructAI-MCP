# How endpoints are verified

This project distinguishes four different claims. They are not degrees of the
same thing — they answer different questions, and conflating them is how an
SDK ends up confidently sending a request shape no server accepts.

| Claim | What it proves | What it does **not** prove |
| --- | --- | --- |
| **Implemented** | The endpoint is wrapped, typed, and unit-tested against a mocked server. | That the real server accepts it. |
| **Live read** | The route exists on a real product, answers, and the response parses. | That this SDK's *request* shape is right. |
| **Live write** | A create / update / delete round trip was watched succeeding, and the change was read back. | That it behaves the same on the other product, or another build. |
| **Not verified** | — | Nothing either way. It is not "broken", it is unmeasured. |

Current counts are in
[ROADMAP.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/ROADMAP.md),
generated from `docs/coverage.json`, which records what is implemented, and
`contracts/verification/ledger.yaml`, which records what was observed live.

## Why read and write are counted separately

A GET that answers tells you the route is real. It tells you almost nothing
about whether the payload this SDK *sends* is correct, because a GET has no
payload.

Nearly every substantive defect found in this project was invisible to reads:

- `/db/REBW` — **every field name** in the specification table was wrong.
  Found by reading real populated data back from a production model and
  confirming with a live PUT round trip.
- `/db/REBC` — the documented single-object `MAIN_BAR` is refused; the server
  takes a `vMAIN_BAR` array. A POST comparison settled it: the documented
  shape answered `Wrong Field`, the other answered a *domain* error naming
  the section it could not find. "Shape refused" and "shape accepted, target
  missing" are the cheapest way to tell a wrong payload from a wrong model.
- `/db/PRES` — the specification row marks `DIRECTION` optional with a
  default of `"NORMAL"`, while the same article's own footnote matrix shows
  `NORMAL` unavailable for a `"PLATE"` + `"FACE"` pressure. Omitting the
  field is *how* the bad default gets applied, so both halves fail together.
- `/db/NMAS` — omitting the optional `rmX`/`rmY`/`rmZ` crashed both products.
  Sending them explicitly, even as their documented default of `0.0`, does
  not. Both SDKs now fill them in before sending.
- `/db/MVHL` — the specification table states branch-1 and branch-2
  requiredness with no reference to the branch, so `VEHICLE_TYPE_NAME` reads
  as always required when it is required only for `VEHICLE_LOAD_NUM: 1`.

Every one of those endpoints answered a GET perfectly well the whole time.

### Findings get retracted too

Three entries this list used to carry were removed on 2026-07-27, when every
documentation claim here was re-checked against MIDAS IT's own published
articles rather than a vendored copy of them, and a fourth followed on
2026-09-03. In each case the live observation was real and correctly
recorded; the conclusion drawn about the *documentation* was not supported by
the source once somebody read it. One of them was not even a vendor claim —
it was this SDK's own docstring.

So: a finding here is a claim about one specific article, and it is only as
good as the last time that article was read. Measuring the product is the
easy half.

## How the evidence is recorded

`contracts/verification/ledger.yaml` carries one record per live session, and
each record lists the endpoints that session covered:

```yaml
- id: ledger-write-2026-07-29-rebw
  endpoints: ["/db/REBW"]
  date: 2026-07-29
  level: write
  products: [gen]
  nxVersions: { gen: "MIDAS Gen NX 2026 (v2.1), build 07/28/2026" }
  outcome: success
  method: >-
    PUT round trip against a real production Gen NX model ...
```

**Re-verifying adds a record; it never edits one.** That is the point of the
per-session shape: an endpoint's claim is resolved from every record naming it,
so a later read cannot quietly overwrite an earlier write. Before 2026-09-21
the same fact lived in `docs/coverage.json` as a single block per endpoint, and
it did get overwritten that way. `docs/coverage.json` now records only what is
implemented and in which module.

`level` is `"write"` only when something was actually mutated — model data, or
a file on the NX host. A POST that the server refused before doing anything is
`"read"`; the HTTP verb does not decide this. `/post/TABLE` is a POST and a
read.

Product and build are recorded because they matter: the same endpoint has been
seen present on one product and 404 on the other, and behaviour has changed
between builds of the same version.

## Where the write evidence comes from

`scripts/live_crud_check.py` runs create → read → update → read → delete →
read against real resources, in dependency-ordered tiers. A case is marked
`confirmed` only after somebody has watched it pass.

It separates a **regression** (a previously-confirmed case now failing — treat
as an SDK defect, exit 1) from an **unverified failure** (a case that has
never passed, so triage the fixture first, exit 3). That distinction exists
because on the first run, *every* failure turned out to be a bad fixture or a
wrong documented value rather than an SDK bug.

## What these numbers do not claim

- Evidence comes from a small number of accounts, licence tiers and builds.
  An endpoint marked verified on Civil NX may behave differently on Gen NX,
  and vice versa.
- A verified endpoint can still break when MIDAS IT ships a product update.
  Nothing here is a continuous check — CI never touches a live product.
- Verification records what happened once, under one model state. Endpoints
  whose behaviour depends on model contents (design checks, result tables) can
  behave differently against a model with real analysis results than against
  an empty one, and the entry says which was used.

Negative results are kept, not deleted. An endpoint that 404s on one product,
or a call that crashed a session, is recorded as such — a documentation set
that only records successes is not evidence.
