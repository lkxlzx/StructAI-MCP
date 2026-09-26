# Inspect a project

- **Audience**: Python beginners, AI-assisted coding beginners, common
- **SDK**: `midas-nx`, on PyPI or npm — the code below is given for both
  (check your version with `python -c "import midas_nx; print(midas_nx.__version__)"`
  or `npm list midas-nx`)
- **Product**: Gen NX or Civil NX
- **Risk level**: 1 — read-only (see [Risk levels](../safety.md#risk-levels))
- **Time**: under a minute
- **Precondition**: Gen NX or Civil NX running, a project open, a valid
  MAPI-Key
- **Changes the model?**: no
- **Live verification**: `Node`/`Element` are live-verified at write level
  on both Gen NX and Civil NX (`docs/coverage.json`); `verify_connection()`
  is `/mapikey/verify`, used throughout this SDK's own live sessions but
  not itemized in `docs/coverage.json` (it's a cross-cutting health check,
  not a per-chapter endpoint)

## What you get

A one-screen answer to "is this thing even connected, and what's in the
model" — the first thing worth checking before writing anything more
involved, and a template for any script that needs to fail fast if the
connection is bad.

## Before you run this

- [ ] Gen NX or Civil NX is open with a project loaded (even an empty one)
- [ ] You have a MAPI-Key from that session (see step 3 of the
  [Python](../en/quickstart.md#step-3-get-a-mapi-key) or
  [npm](../npm/quickstart.md#step-3-get-a-mapi-key) quickstart)
- [ ] You're not pasting the key into a shared chat or committing it to git

## Inputs

- `mapi_key` — from the running product
- `product` — `Product.GEN` or `Product.CIVIL`, matching what's actually
  open

## Full code

=== "Python"

    ```python
    from midas_nx import MidasClient, Product
    from midas_nx.db.node_element import Node, Element

    client = MidasClient(mapi_key="paste-your-mapi-key-here", product=Product.GEN)

    status = client.verify_connection()
    print(f"Connection: {status['status']} (key verified: {status['keyVerified']})")

    nodes = Node.items(client=client)
    elements = Element.items(client=client)
    print(f"Model: {len(nodes)} node(s), {len(elements)} element(s).")
    ```

=== "JavaScript / TypeScript"

    ```js
    import { MidasClient, resources } from "midas-nx";

    const client = new MidasClient({ mapiKey: "paste-your-mapi-key-here", product: "gen" });
    const { node, element } = resources.db.nodeElement;

    const status = await client.verifyConnection();
    console.log(`Connection: ${status.status} (key verified: ${status.keyVerified})`);

    const nodes = await node.items(client);
    const elements = await element.items(client);
    console.log(`Model: ${Object.keys(nodes).length} node(s), ${Object.keys(elements).length} element(s).`);
    ```


## What the code does

- `verify_connection()` hits `/mapikey/verify` — confirms the product
  process is alive and this key is valid for it, without touching model
  data.
- `Node.items()` / `Element.items()` each do one `GET` against `/db/NODE`
  and `/db/ELEM` and return every row as a dict keyed by ID.
- Nothing here can create, modify, or delete data — the whole script is
  reads.

## Expected output

```text
Connection: connected (key verified: True)
Model: 3 node(s), 2 element(s).
```

Numbers depend on what's actually open — `0` for both on a blank project
is a normal result, not an error.

## Verify the result

There's nothing to verify beyond "did it print the numbers you expect for
the model you have open" — this recipe doesn't change anything, so there's
no before/after state to compare.

## Common errors

- **`MidasConnectionError`** — the product isn't running, or Open API
  isn't connected. The exception message ends with `(Hint: ...)`.
- **`MidasAuthError`** — the MAPI-Key is wrong or stale (it resets each
  time the product restarts).
- **`status: "disconnected"` with no exception** — `verify_connection()`
  returns this as a normal result rather than raising, since it's a valid
  response shape. Re-check the product before calling anything else.

## Timeout and retry

All three calls here are reads. If one times out, it's safe to just run
the script again — nothing was written, so there's no risk of double
application.

## Recovery

Not applicable — this recipe cannot modify the model.

## Related reference

- [`MidasClient.verify_connection()`](../reference/client.md)
- [DB resources](../reference/db.md)

## Ask an AI to adapt this

```text
Using this exact script as a starting point, add a read-only check for
[material / section / load case] counts too. Keep it strictly read-only —
no create, update, delete, or analyze calls.
```
