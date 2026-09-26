# For AI agents

You are probably here because someone asked you to write code against
`midas-nx`. Read this first; it is short.

**`CLAUDE.md` in this directory is not for you.** It is the maintainer's
guide to the repository itself — contracts, generators, release process. If
you are helping someone *use* the SDK, following it will send you the wrong
way.

## The one thing to internalize

This SDK drives a live engineering application. **Generated code is not
verified code**, even when it runs without errors. A wrong call can discard
someone's unsaved work or end their MIDAS NX session, and an HTTP `200` does
not always mean the request succeeded.

Write and run a **read-only** version of the task first. Only then extend it.

## Load the context pack before writing any code

[`docs/ai-coding/context-pack.md`](docs/ai-coding/context-pack.md) is written
for you, not for the user. It has the real API shape, the error model, and
the specific ways this SDK can hurt someone. Take the box that matches the
package in use:

| package | install | pack | human quickstart |
| --- | --- | --- | --- |
| Python (PyPI) | `pip install midas-nx` | [Python](docs/ai-coding/context-pack.md#python) | [docs/en/quickstart.md](docs/en/quickstart.md) |
| JavaScript / TypeScript (npm) | `npm install midas-nx` | [JavaScript and TypeScript](docs/ai-coding/context-pack.md#javascript-and-typescript) | [docs/npm/quickstart.md](docs/npm/quickstart.md) |

Paste one, not both.

## Do not guess names

`midas-nx` has changed shape across versions, and a plausible-sounding
function name is usually a name that does not exist. Check instead:

```bash
python -c "import midas_nx; print(midas_nx.__version__)"   # Python
npm list midas-nx                                          # npm
```

On npm the package ships full TypeScript declarations, so `tsc --noEmit` is a
free existence check — a name that does not type-check is not real.
[`ROADMAP.md`](ROADMAP.md) lists every endpoint and how far each one has been
verified against a running product.

## The four facts most likely to bite

1. **`doc.new_project()` / `doc.newProject()` discards unsaved work** in
   whatever document is open — including work unrelated to the script.
2. **`delete_all()` / `deleteAll()` empties the whole table**, which is why it
   demands an explicit confirmation. Use `delete(ids)` for specific records.
3. **A timeout is not a rollback.** The operation may still land after the
   HTTP call gives up. Never auto-retry a write after a timeout; check the
   model state first.
4. **Every file path resolves on the machine running MIDAS NX**, which is
   often not the machine running the script. A path that does not exist there
   raises a dialog *there* and blocks the session while the call answers like
   a success.

[`docs/safety.md`](docs/safety.md) has the full list and the risk levels.

## Examples to copy from rather than invent

- [`examples/python/`](examples/python/) — four, from a read-only check to a
  load combination and a KDS wind load.
- [`examples/javascript/`](examples/javascript/) — the same four, as `.mjs`.

Each states its risk level at the top. Start from the read-only one.

## If you are working on this repository rather than with the SDK

Then `CLAUDE.md` is the right document, and the rule that matters most is
that `contracts/` is the source of truth: a disagreement between a contract
and either SDK is an SDK defect, never a reason to edit the contract.
