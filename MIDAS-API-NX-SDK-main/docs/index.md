# midas-nx

Unified Python and JavaScript/TypeScript SDKs for the **MIDAS NX Open API** —
one package name on each registry, both covering **MIDAS Civil NX** and
**MIDAS Gen NX** from the same reviewed endpoint inventory.

=== "Python"

    ```bash
    pip install midas-nx
    ```

    ```python
    from midas_nx import MidasClient, Product
    from midas_nx.db.node_element import Node

    client = MidasClient(mapi_key="YOUR-MAPI-KEY", product=Product.GEN)
    print(client.verify_connection())
    print(f"{len(Node.items(client=client))} node(s) in the current model.")
    ```

=== "JavaScript / TypeScript"

    ```bash
    npm install midas-nx
    ```

    ```js
    import { MidasClient, resources } from "midas-nx";

    const client = new MidasClient({ mapiKey: "YOUR-MAPI-KEY", product: "gen" });
    console.log(await client.verifyConnection());

    const nodes = await resources.db.nodeElement.node.items(client);
    console.log(`${Object.keys(nodes).length} node(s) in the current model.`);
    ```

**Risk level: 1 — read-only** (see [Risk levels](safety.md#risk-levels)). It
cannot create, change, or delete anything, so it's safe to run against a
real model.

!!! info "Project status"
    Built by a MIDAS IT employee, from hands-on verification against real
    Gen NX and Civil NX sessions. It is an **employee-led open-source
    project — not an officially released or supported MIDAS IT product**.

    - Problems with **this SDK** → [GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues)
    - Problems with **the products, licensing, or the Open API service** →
      MIDAS IT's official support channels
    - Questions, feedback, or getting in touch → the author, Dennis, on
      [LinkedIn](https://www.linkedin.com/in/dennis58)

!!! danger "Read this before your first write"
    This SDK drives a live engineering application. Several calls can destroy
    unsaved work, and some have crashed the product outright. A `200` response
    does not mean success. Start with
    [Destructive operations and recovery](safety.md).

## How would you like to start?

**Learn Python and use the SDK.** Install Python, then follow a guided,
read-only walkthrough that explains each step. No prior programming
experience assumed.
→ [Getting started](en/quickstart.md) (also [한국어](ko/quickstart.md), [繁體中文](zh-tw/quickstart.md))

**Already write JavaScript or TypeScript.** The same walkthrough for the npm
package — Node, a MAPI key, and a first read-only script, with full type
declarations in your editor.
→ [Getting started (npm)](npm/quickstart.md) (also [한국어](npm/quickstart-ko.md), [繁體中文](npm/quickstart-zh-tw.md))

**Build a script with an AI coding assistant.** Don't know Python well?
Give your AI assistant (Claude Code, ChatGPT, Copilot, or similar) a
verified context pack and a pre-run safety checklist, and describe your task
in plain language.
→ [Safe start: building with an AI coding assistant](ai-coding/safe-start.md)

## Learn more

| You want to… | Go to |
| --- | --- |
| Run a complete task end-to-end | [Recipes](recipes/index.md) |
| Understand what can break a model or a session | [Destructive operations and recovery](safety.md) |
| Look up a class, function or exception | [Reference](reference/client.md) |
| Know which endpoints are actually proven to work | [How endpoints are verified](verification.md) |
| Read the raw findings from real NX sessions | [Live session notes](live_verification_notes.md) |
| See per-endpoint implementation status | [ROADMAP.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/ROADMAP.md) |

## What it covers

Every endpoint documented in the
[MIDAS-API manual repo](https://github.com/Dennis5882/MIDAS-API) is wrapped:
model building (nodes, elements, materials, sections, boundaries, loads),
analysis control and result extraction, construction stages, moving loads and
bridge features, and the RC / steel / SRC design-code chapters.

Endpoints are typed with `TypedDict` payloads carrying the manual's
requiredness and defaults as per-field comments. Those TypedDicts are
**documentation, not runtime validation** — the real schemas are too
conditional for one flat model, and the official documentation has been wrong
often enough that this SDK records what was observed rather than what was
promised.

## Design in one page

- **`MidasClient` is an instance**, not global mutable state. Pass it
  explicitly, or set a default with `configure()`.
- **Errors raise**, they don't exit the process. Everything descends from
  `MidasAPIError`, and a `200` carrying an `{"error": ...}` body raises
  `MidasResultError` rather than being handed back as a result.
- **`/db/*` endpoints are classes** (`DbResource` subclasses) with
  `create` / `get` / `items` / `update` / `delete` / `delete_all`.
- **`/doc/*`, `/ope/*`, `/view/*` are plain functions**, because those wrap
  their body in `"Argument"` rather than an ID-keyed `"Assign"`.
- **Product mismatches fail before the request**: a Civil-only resource called
  from a Gen client raises `ProductMismatchError` instead of a server 404.
