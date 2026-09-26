# midas-nx for JavaScript / TypeScript — getting started

This guide is for engineers reaching MIDAS Gen NX/Civil NX from Node.js. It
goes from installing Node to running a first read-only script, in order, so
you can follow it start to finish in one sitting.

> `midas-nx` is an employee-led open-source project, built by a MIDAS IT
> employee from hands-on product and API verification work. It is **not an
> officially released or supported MIDAS IT product** — please report problems
> with this SDK or guide on
> [GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues) rather
> than to MIDAS IT product support, which does not cover it.

> Writing Python instead? [That quickstart](../en/quickstart.md) is the same
> walkthrough for the PyPI package, and it assumes no prior programming
> experience at all.

## Before you start

- MIDAS Gen NX or Civil NX installed, with a valid license
- An internet connection — the SDK talks to MIDAS's cloud relay server
- **The product running on some machine you can reach.** It does not have to
  be the machine running your code; see [Step 5](#step-5-know-which-machine-you-are-talking-to).

## Step 1: Install Node.js

`midas-nx` requires **Node.js 18 or newer**. Check what you have:

```bash
node --version
```

If that prints something older than `v18`, or errors, install the current LTS
from https://nodejs.org/. Any installation method works — the official
installer, `nvm`, `fnm`, Homebrew, `winget`.

## Step 2: Make a project and install midas-nx

```bash
mkdir midas-scripts
cd midas-scripts
npm init -y
npm install midas-nx
```

The package has **no runtime dependencies** and does not need Python
installed. (The `midas-nx` package on PyPI is the separate Python SDK for the
same API — not a requirement of this one.)

TypeScript declarations ship with it, so your editor will autocomplete every
endpoint and payload field with no `@types/` package to add.

## Step 3: Get a MAPI key

The `MAPI-Key` is the authentication key this SDK uses to talk to MIDAS
Gen NX/Civil NX. You get it **from inside the MIDAS Gen NX (or Civil NX)
application itself**, not from npm.

1. Launch MIDAS Gen NX (or Civil NX).
2. In the top menu, open **Apps** and click **API Settings**.
3. The screen shows a **Base URL** and a **MAPI-Key**. Click the **Copy**
   button next to each to copy it.
4. Click **Connected**. If it succeeds, Status switches to **Connected** —
   that's what confirms Open API is actually active.

> Want a fresh key (e.g. you think one leaked)? Click **Refresh** next to
> it. The old key is invalidated immediately.

> ⚠️ **Treat it like a password while it's live.** Keep it in an environment
> variable rather than in the file, and don't commit it, paste it into a
> public issue, or share a screenshot that shows it. If you think a key
> leaked, click **Refresh** for a new one.

> 🌏 **No need to guess which regional server you're on.** Use the
> **Base URL** shown on that same screen — it's correct for any region,
> including China's separate server. If it differs from the SDK's default
> global relay (`moa-engineers.midasit.com`), pass
> `baseUrl: "the copied value"` to `new MidasClient({ ... })`.

## Step 4: Write and run your first script (read-only)

**Risk level: 1 — read-only** (see [Risk levels](../safety.md#risk-levels)).

Save this as `first-script.mjs` in the folder you made in step 2. The `.mjs`
extension is what lets you use `import` and top-level `await` without any
extra configuration.

```js
import { MidasClient, resources } from "midas-nx";

// Using Civil NX instead? Change this to product: "civil".
const client = new MidasClient({
  mapiKey: process.env.MIDAS_MAPI_KEY,
  product: "gen",
});

console.log(await client.verifyConnection());

const nodes = await resources.db.nodeElement.node.items(client);
console.log(`Connected. Found ${Object.keys(nodes).length} node(s) in the current model.`);
```

Put the key in the environment and run it:

```bash
# macOS / Linux
export MIDAS_MAPI_KEY="paste_the_key_you_copied_in_step_3_here"
node first-script.mjs
```

```powershell
# Windows PowerShell
$env:MIDAS_MAPI_KEY = "paste_the_key_you_copied_in_step_3_here"
node first-script.mjs
```

You should see something like:

```
{ status: 'connected', keyVerified: true }
Connected. Found 3 node(s) in the current model.
```

(The exact node count depends on whatever model you currently have open —
`0` is a perfectly normal answer if it's a blank project.)

**This script only reads data.** It cannot create, change, or delete
anything in your model, no matter which project you run it against — safe
to try against real work.

### If something goes wrong

- **`MidasConnectionError`**: check that Gen NX/Civil NX is running and Open
  API is connected. This SDK's error messages end with a `(Hint: ...)`
  telling you what to check.
- **`MidasAuthError`**: make sure the key from step 3 reached the process.
  `console.log(process.env.MIDAS_MAPI_KEY?.length)` should print a number,
  not `undefined` — a new terminal window does not keep the variable you set
  in the old one. Keys can also change when you restart the product.
- **`ERR_MODULE_NOT_FOUND`**: you are running the file from a different
  folder than the one holding `node_modules`. `cd` into the project folder
  first.
- **Behind a corporate firewall**: see
  ["Connectivity troubleshooting"](../safety.md#connectivity-troubleshooting)
  for the exact port/address info to hand to your IT team.

## Step 5: Know which machine you are talking to

Calls go through MIDAS IT's relay to the machine running MIDAS NX, which is
often **not** the machine running your script. This matters more than it
sounds:

- **Every file path resolves on the MIDAS NX machine.** Export paths,
  `doc.saveAs()`, `doc.openProject()`, report and image paths. A path that
  does not exist there raises a dialog *there* and blocks the session, while
  your HTTP call still answers like a success.
- **A blocked session is invisible to `verifyConnection()`.** While a modal
  dialog is up in the product, the relay still answers "connected" while
  every real call times out.

## Step 6: Change something (optional — this writes to your model)

Everything from here can modify a model. Read
[the safety guide](../safety.md) first; the short version is on this page.

DB endpoints hang off the `resources` tree, keyed by record id:

```js
import { MidasClient, resources } from "midas-nx";

const client = new MidasClient({ product: "gen" });
const node = resources.db.nodeElement.node;

await node.create({ 1: { X: 0, Y: 0, Z: 0 } }, client);
const nodes = await node.items(client);
await node.delete([1], client); // one DELETE request per id
```

Field names inside a payload are the official uppercase wire names, exactly
as the API manual writes them. Your editor will complete them.

Three rules worth internalizing before you write anything bigger:

1. **`doc.newProject()` discards unsaved work** in whatever document is open
   — including work unrelated to your script. Never run it unattended
   against a model that matters.
2. **`deleteAll()` empties the whole table**, which is why it demands
   `{ confirm: true }`. Use `delete(ids, client)` for specific records.
3. **A timeout is not a rollback.** The operation may still land after the
   HTTP call gives up waiting. Never auto-retry a write after a timeout —
   check the model state first.

## Next steps

- [Runnable examples](https://github.com/Dennis5882/MIDAS-API-NX-SDK/tree/main/examples/javascript/)
  — read-only first, then a model built from scratch, a load combination, and
  a wind load. Each states its risk level at the top.
- [Safety guide](../safety.md) — risk levels, and the calls that have crashed
  a product outright.
- [Letting an AI assistant write the code](../ai-coding/safe-start.md) — with
  a [context pack](../ai-coding/context-pack.md#javascript-and-typescript)
  written for the assistant rather than for you.
- [ROADMAP.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/ROADMAP.md)
  — every endpoint and how far each one has been verified against a running
  product.
