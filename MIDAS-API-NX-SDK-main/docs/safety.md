# Destructive operations and recovery

Everything on this page is observed behaviour of the MIDAS NX products and
API, recorded from real sessions — not defects in this package. The full
reproductions are in [Live session notes](live_verification_notes.md).

Read this before your first write. Several of these cost hours to diagnose the
first time.

## Risk levels

Examples and recipes across this project's docs are labeled with one of
these. If something you're reading isn't labeled (yet), assume the highest
level that could plausibly apply until you've checked.

| Level | Meaning | Examples |
| --- | --- | --- |
| 0 | Connection / local check only | Checking the installed version, `verify_connection()` |
| 1 | Read-only | `.items()`, `.get()` on any `/db/*` resource |
| 2 | Limited addition | `.create()` against a disposable test model |
| 3 | Modifies existing data | `.update()` on materials, sections, loads, ... |
| 4 | High risk | `.delete()`, `delete_all()`, `doc.new_project()`, `doc.open_project()`, `doc.save_as()`, `doc.analyze()` |

Levels 3 and 4 should always run against a copy, preview the change before
sending it, and get verified by reading the data back afterward — see
[A 200 response does not mean success](#a-200-response-does-not-mean-success)
for why the response alone isn't proof. Level 4 in particular should never
sit inside an automatic retry loop — see
[Timeouts are not rollbacks](#timeouts-are-not-rollbacks).

## A 200 response does not mean success

This is the single most important thing on the page.

- Several endpoints report a refusal with an `{"error": {...}}` body under a
  **2xx** status. This SDK raises `MidasResultError` for those; opt out with
  `MidasClient(raise_on_result_error=False)` if you want the raw body.
- Some don't even do that. `/doc/ANAL` reports a failed solve as
  `{"message": "... Analysis failed."}`, with no `error` key.
  `/doc/SAVEAS` answers `"... command complete"` for a save that never
  happened.
- Error bodies have also arrived under **201**, not just 200.

!!! tip "The rule that actually protects you"
    **Verify a write by reading it back.** Not by trusting the response, and —
    for anything file-related — not with `os.path.exists()` either (see
    [paths](#paths-resolve-on-the-nx-machine-not-yours)).

## Deleting

`delete()` is safe and precise. `delete_all()` is neither, and says so:

```python
Node.delete([4, 5])          # removes exactly nodes 4 and 5
Node.delete_all()            # raises DestructiveOperationError
Node.delete_all(confirm=True)  # empties the entire NODE table
```

`delete_all()` requires `confirm=True` and raises
`DestructiveOperationError` without it, **before sending anything** — a
mistaken call costs nothing.

!!! danger "Why the guard exists"
    The manual documents deletion as `DELETE {endpoint}` with an ID-keyed
    `{"Assign": {...}}` body. Live testing measured that call **ignoring the
    ids and clearing the whole table** — and for `/db/NODE` that takes every
    element attached to those nodes with it. One call, model gone, no undo
    through the API.

    `delete()` therefore issues one `DELETE {endpoint}/{id}` per id — an
    undocumented form that removes exactly the record asked for. Do not
    "simplify" it back into a single request.

## Paths resolve on the NX machine, not yours

Calls travel through a MIDASIT relay, so the product is frequently running on
a different PC. `EXPORT_PATH`, `/doc/SAVEAS`, `/doc/OPEN`, and every report or
image path resolve **there**.

A path that doesn't exist on that machine raises a modal dialog **on that
machine** — blocking the session — while your HTTP call still returns
something indistinguishable from success.

```python
user = client.verify_connection()["user"]   # build paths from this
```

Verify a write with `/doc/OPEN`, never `os.path.exists()`.

## A modal dialog blocks the whole session

Any dialog — a confirmation prompt, an access-denied error, a crash-recovery
notice — blocks **every** API call in that session until a human dismisses it,
not just the call that raised it.

!!! warning "`verify_connection()` cannot see this"
    While a dialog is up, `/mapikey/verify` keeps answering `"connected"`
    (the relay serves it) while every `/db/*` call times out. Treat a healthy
    connection check as "the key is valid and the process was alive a moment
    ago" — **not** as clearance to run a destructive operation. There is no
    API-visible signal for a blocked session; the only reliable check is a
    cheap real call with a short timeout.

A read can trigger one, too: a plain `GET /db/CAMB` popped an access-denied
dialog purely because the open document lived under `Program Files`, where a
standard account can't write the auxiliary file the call produces. Keep
working documents out of `Program Files`-style locations.

## Calls that have crashed the product

Some endpoints have killed a live session outright — the process dies, and the
license is held until it is restarted properly. Reported to MIDAS IT where
reproduced.

The signature is recognisable: `verify_connection()` keeps reporting
`"connected"` while every `/db/*` call times out, then the process dies and
subsequent calls raise `MidasNotFoundError` (`"client does not exist"`).

Use a short per-call timeout and read results back separately rather than
blocking on a response that may never arrive:

```python
from midas_nx.client import MidasConnectionError

try:
    perform_column_check({"PERFORM_TYPE": "ALL"}, client, timeout=25.0)
except MidasConnectionError:
    pass  # a timed-out check may still have committed its results

table = get_column_check_table({...}, client)   # read regardless
```

If you only need results an engineer already computed in the GUI, reading the
`*-TABLE` endpoint alone needs no `*-ANAL` call and carries none of this risk.

### Recovery

No data loss has been observed after these crashes, on either product, as long
as recovery is done properly:

1. Dismiss the dialogs.
2. Relaunch Gen NX / Civil NX.
3. Press **New Project**.
4. Close the application properly (this releases the license).
5. Reconnect with the same MAPI key.

Verify the model afterwards by comparing record counts to what you had before.

## Scripts that write

Two of the live scripts in this repo are safe to point at a model you care
about. The other five are not:

| Script | Safe against an open model? |
| --- | --- |
| `scripts/live_readonly_sweep.py` | ✅ GET only |
| `packages/typescript/scripts/live-readonly.mjs` | ✅ GET only, the npm equivalent |
| `scripts/live_smoke.py` | ❌ calls `/doc/NEW` — **discards unsaved work** |
| `scripts/live_crud_check.py` | ❌ calls `/doc/NEW`, then creates, updates and deletes real records |
| `packages/typescript/scripts/live-crud.mjs` | ❌ the same, from the npm package |
| `scripts/live_manual_feedback.py` | ❌ calls `/doc/NEW` once per probe while investigating a documentation defect |
| `packages/typescript/scripts/live-analysis.mjs` | ❌ no `/doc/NEW`, but it adds a column to **your** open model and runs a solve, then deletes what it added |

`/doc/NEW` has itself crashed Gen NX when the open document was a large real
model. Get the document to an empty state first, and confirm it.

Every one of the five writes a checkpoint to a directory **on the machine
running NX**, which you name with `--save-dir`. None of them guesses one: a
path that does not exist on that machine raises a dialog there and blocks the
session, while the HTTP call still answers like a success.

Since 2026-09-21 the four that call `/doc/NEW` ask in exactly the same way, and
**refuse to start** when you name nothing — the rule and the reasons are in
`scripts/harness_save_path.py`. `--save-dir` takes a directory and the file
name is derived from the product, so the NX extension (Gen `.mgbx`, Civil
`.mcbz`) cannot be got wrong. `--no-save-before` waives the checkpoint and
**not** the `/doc/NEW`. Two stated departures: `scripts/live_crud_check.py`
also accepts `--save-as` for an exact path, and `scripts/live_manual_feedback.py`
has no waiver at all, because its per-probe saves are the evidence the run
produces rather than a safety net.

## Connectivity troubleshooting

`MidasConnectionError` almost always means MIDAS Gen/Civil NX isn't running,
isn't connected via Open API, or the connection died mid-session.
`client.verify_connection()` is the fastest way to tell those apart — it
reports whether the product process is alive and whether the current
MAPI-Key is valid for it, before you burn a request timeout finding out the
hard way.

If the app is running and still won't connect, it's usually a corporate
firewall blocking outbound traffic to the MIDAS relay. Share this with your
network/security team:

| Item | Value |
| --- | --- |
| Protocol | `https`, `wss` |
| Port | `443` |
| IP | `121.157.60.1/32` (MIDAS public NAT IP) |
| URI | `https://moa-engineers.midasit.com` |

If your network does SSL inspection/interception on all outbound traffic,
`moa-engineers.midasit.com` needs to be excluded from it — several users have
hit silent connection failures caused by SSL inspection specifically,
separate from a plain firewall block. When an appliance answers in the
product's place, you'll get a `MidasServerError` reading `response body is
not JSON: '<html>...'` — that message is the giveaway that something between
you and MIDAS is intercepting the request.

## Timeouts are not rollbacks

A client-side timeout means you stopped waiting. It does not mean the server
stopped working — the operation may well complete afterwards. After any
timeout on a write, re-read the state before deciding what happened.

This SDK never retries automatically, for exactly this reason. A retried
`POST` against an endpoint that already succeeded is a second write, not a
recovery.
