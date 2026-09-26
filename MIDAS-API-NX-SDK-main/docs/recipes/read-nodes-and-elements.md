# Read nodes and elements

- **Audience**: Python beginners, AI-assisted coding beginners, common
- **SDK**: `midas-nx`, on PyPI or npm — the code below is given for both
  (check your version with `python -c "import midas_nx; print(midas_nx.__version__)"`
  or `npm list midas-nx`)
- **Product**: Gen NX or Civil NX
- **Risk level**: 1 — read-only (see [Risk levels](../safety.md#risk-levels))
- **Time**: a few minutes
- **Precondition**: Gen NX or Civil NX running, a project with some
  geometry open, a valid MAPI-Key
- **Changes the model?**: no
- **Live verification**: `Node`/`Element` are live-verified at write level
  on both Gen NX and Civil NX (`docs/coverage.json`) — a write round trip
  is a stronger guarantee than a read, since it proves the SDK's own
  create/update shape is one the server accepts, not just that `GET` works

## What you get

The model's geometry as plain Python dicts you can filter, print, or feed
into your own logic — nodes above a given elevation, elements using a
specific section, or just a full dump to eyeball while you're learning the
shape of the data.

## Before you run this

- [ ] Gen NX or Civil NX is open with a project that has some nodes and
  elements in it (an empty model will just print nothing, which isn't a
  bug)
- [ ] You have a MAPI-Key from that session

## Inputs

- `mapi_key`, `product` — same as [Inspect a project](inspect-project.md)
- Nothing else — this recipe reads everything and filters client-side

## Full code

=== "Python"

    ```python
    from midas_nx import MidasClient, Product
    from midas_nx.db.node_element import Node, Element

    client = MidasClient(mapi_key="paste-your-mapi-key-here", product=Product.GEN)

    nodes = Node.items(client=client)
    elements = Element.items(client=client)

    # Every node above Z = 3.0
    high_nodes = {nid: n for nid, n in nodes.items() if n["Z"] > 3.0}
    print(f"{len(high_nodes)} node(s) above Z=3.0:")
    for nid, n in high_nodes.items():
        print(f"  #{nid}: ({n['X']}, {n['Y']}, {n['Z']})")

    # Every beam element
    beams = {eid: e for eid, e in elements.items() if e["TYPE"] == "BEAM"}
    print(f"{len(beams)} beam element(s):")
    for eid, e in beams.items():
        print(f"  #{eid}: nodes {e['NODE']}, material {e['MATL']}, section {e['SECT']}")
    ```

=== "JavaScript / TypeScript"

    ```js
    import { MidasClient, resources } from "midas-nx";

    const client = new MidasClient({ mapiKey: "paste-your-mapi-key-here", product: "gen" });
    const { node, element } = resources.db.nodeElement;

    const nodes = await node.items(client);
    const elements = await element.items(client);

    // Every node above Z = 3.0
    const highNodes = Object.entries(nodes).filter(([, n]) => n.Z > 3.0);
    console.log(`${highNodes.length} node(s) above Z=3.0:`);
    for (const [nid, n] of highNodes) {
      console.log(`  #${nid}: (${n.X}, ${n.Y}, ${n.Z})`);
    }

    // Every beam element
    const beams = Object.entries(elements).filter(([, e]) => e.TYPE === "BEAM");
    console.log(`${beams.length} beam element(s):`);
    for (const [eid, e] of beams) {
      console.log(`  #${eid}: nodes ${e.NODE}, material ${e.MATL}, section ${e.SECT}`);
    }
    ```


## What the code does

- `Node.items()` / `Element.items()` each fetch the entire table with one
  `GET` and return `{id: {field: value, ...}, ...}`.
- The filtering (`if n["Z"] > 3.0`, `if e["TYPE"] == "BEAM"`) happens in
  Python after the data is back — there's no server-side query, so this
  scales fine for typical model sizes but fetches the whole table every
  call.
- `n["Z"]`/`e["TYPE"]` etc. are the raw field names `/db/NODE`/`/db/ELEM`
  return — see [DB resources](../reference/db.md) for the full field list.

## Expected output

```text
2 node(s) above Z=3.0:
  #2: (0, 0, 3.2)
  #4: (5, 0, 3.2)
1 beam element(s):
  #1: nodes [1, 2], material 1, section 1
```

Exact numbers depend on your model. `0` for either count is a normal
result for a model with no matching geometry, not an error.

## Verify the result

Cross-check a couple of printed IDs against what you see in the Gen
NX/Civil NX model view (or against a known-good node/element table export)
to confirm the field values line up with what you expect.

## Common errors

- **`MidasConnectionError` / `MidasAuthError`** — same causes as in
  [Inspect a project](inspect-project.md).
- **`KeyError`** on a field like `n["Z"]` — you're on a product/model
  where that field is genuinely absent (e.g. a 2D-only element type
  without every 3D field). Print one raw entry
  (`print(next(iter(nodes.values())))`) to see the actual keys before
  assuming a field name.

## Timeout and retry

Both calls here are reads — safe to just re-run the script if either
times out.

## Recovery

Not applicable — this recipe cannot modify the model.

## Related reference

- [DB resources](../reference/db.md)
- [ROADMAP.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/ROADMAP.md) — full field lists per resource

## Ask an AI to adapt this

```text
Using this exact script as a starting point, filter elements to only
[TRUSS / PLATE / a specific SECT id] instead of BEAM. Keep it strictly
read-only — no create, update, delete, or analyze calls.
```
