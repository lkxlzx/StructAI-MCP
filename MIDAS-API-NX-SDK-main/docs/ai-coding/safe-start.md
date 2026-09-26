# Safe start: building with an AI coding assistant

You don't need to know Python or TypeScript well to use `midas-nx` — tools
like Claude Code, ChatGPT, GitHub Copilot, or similar can write the code for
you. This page is for that path. It assumes you can describe what you want in
plain language but can't fully review the code that comes back.

It applies to both packages: `midas-nx` on PyPI (Python) and `midas-nx` on
npm (JavaScript/TypeScript). Where a name differs, both are given.

!!! danger "The one thing to internalize"
    **Generated code is not verified code**, even when it runs without
    errors. `midas-nx` drives a live engineering application — a wrong call
    can discard unsaved work or corrupt a model, and a script that "worked"
    once isn't proof it's safe to run again. Treat every script an AI
    writes for you the way you'd treat a script written by a stranger: read
    what it's about to do before you run it.

## The two rules that matter most

1. **The first script should only read data.** Don't let an AI assistant's
   first attempt at your task include `create`, `update`, `delete`,
   `delete_all`/`deleteAll`, `new_project`/`newProject`,
   `open_project`/`openProject`, or `analyze` calls. Get a read-only version
   working and understood first, then extend it.
2. **AI assistants guess plausible-sounding function names.** `midas-nx` has
   changed shape across versions, and an assistant trained on old data (or
   just pattern-matching) will confidently write calls that don't exist. The
   [context pack](context-pack.md) tells it not to do this and how to check
   — use it.

## Step 1: give your assistant the context pack

Paste the [AI context pack](context-pack.md) into your chat before asking
for any code — as a system prompt if your tool supports one, otherwise as
your first message. Take the [Python](context-pack.md#python) box or the
[JavaScript and TypeScript](context-pack.md#javascript-and-typescript) one, whichever
matches the package you installed; pasting both just confuses the assistant
about which language you want. It tells the assistant the real API shape, the
error model, and the specific ways this SDK can hurt you if used carelessly
(`doc.new_project()` discarding work, `delete_all()` emptying a whole table,
timeouts not being rollbacks, and so on).

## Step 2: describe the task with this template

```text
Product: Gen NX or Civil NX
Current model state: [describe without confidential information]
Goal: [one concrete task]
Inputs: [ids, load cases, units, selections]
Expected output: [screen output, a summary, or a file]

Start with a read-only version of this. Show me a preview of anything you
plan to create, change, or delete before writing the code that does it.
```

## Step 3: review the generated code before running it

Go through this checklist. If you can't answer a line, ask the assistant to
explain it in plain language rather than skipping it.

- [ ] Does the script only *read* data (no `create`/`update`/`delete`/
      `delete_all`/`deleteAll`/`new_project`/`newProject`/`open_project`/
      `openProject`/`analyze`) — or, if it writes, did I explicitly ask for
      that after seeing a read-only version work first?
- [ ] Does it import only things that plausibly exist? (Ask the assistant to
      show `python -c "import midas_nx; print(dir(midas_nx))"` output, or
      point it at the [reference](../reference/client.md), if unsure. On npm,
      run the TypeScript compiler — a name that does not type-check does not
      exist, and that check is free.)
- [ ] Is the product (`Product.GEN` / `Product.CIVIL`, or `"gen"` / `"civil"`
      on npm) the one I actually use?
- [ ] Is my MAPI-Key absent from the code the assistant shows back to me, or
      from anything it suggests logging/printing?
- [ ] If it writes data, does it print a preview (ids, payload) *before* the
      write call runs?
- [ ] Is there no `delete_all()`/`deleteAll()` without an explicit confirm,
      and no blind `new_project()`/`newProject()` at the top of the script?
- [ ] If a call can time out, does the script avoid automatically retrying
      the same write?
- [ ] Am I running this against a test/disposable project the first time,
      not my real model?

## If something goes wrong: reporting back to the AI

Don't paste raw tracebacks or your MAPI-Key back into the chat. Strip
identifying details and use this shape instead:

```text
Installed midas-nx version:
Package: PyPI (Python) or npm (JavaScript/TypeScript)
Python or Node.js version:
Product: Gen NX / Civil NX
Operation type: read / create / update / delete
What I expected:
What happened:
Sanitized error message (no keys, no model/customer data):

Do not suggest an automatic retry. First explain how to safely check
whether the request already took effect.
```

That last line matters — a timeout is not proof the request didn't happen
(see the context pack's safety facts). Letting an assistant "just try again"
after a write timeout can double up whatever it was doing.

## Next

- [AI context pack](context-pack.md) — the copy-paste block itself
- [Destructive operations and recovery](../safety.md) — the full list of
  things that can go wrong, independent of who or what wrote the code
- [Getting started](../en/quickstart.md) — the read-only Python path, useful
  once you want to understand what the AI is actually doing
- Runnable scripts to compare the generated code against:
  [`examples/python/`](https://github.com/Dennis5882/MIDAS-API-NX-SDK/tree/main/examples/python/)
  and
  [`examples/javascript/`](https://github.com/Dennis5882/MIDAS-API-NX-SDK/tree/main/examples/javascript/)
