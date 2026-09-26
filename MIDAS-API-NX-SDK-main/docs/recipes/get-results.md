# Extract a result table

- **Audience**: Python beginners, AI-assisted coding beginners, common
- **SDK**: `midas-nx`, on PyPI or npm — the code below is given for both
  (check your version with `python -c "import midas_nx; print(midas_nx.__version__)"`
  or `npm list midas-nx`)
- **Product**: Gen NX or Civil NX
- **Risk level**: 1 — read-only (see [Risk levels](../safety.md#risk-levels))
- **Time**: a few minutes
- **Precondition**: the open project has already been analyzed (`ANALYSIS
  RESULT EXISTS` — see [Common errors](#common-errors) below if it hasn't)
- **Changes the model?**: no
- **Live verification**: `POST /post/TABLE`'s analysis-result table family
  (~25 table types, including Reaction) is live-verified at read level on
  both Gen NX and Civil NX (`docs/coverage.json`) — this is one entry
  covering the whole family, not this specific reaction call in isolation

## What you get

Reaction forces from an already-analyzed model, pulled out as plain rows
you can print, sum, or hand to `pandas`/`csv` yourself — the same pattern
applies to any of the other ~25 table types this SDK wraps (displacement,
member forces, mode shapes, story drift, ...).

## Before you run this

- [ ] The project has been analyzed at least once in this session (`Analyze`
  → wait for it to finish) — a call before that returns an empty table, not
  an error
- [ ] You know at least one load case or combination name defined in the
  model (check in the GUI, or via `midas_nx.db.static_loads` if you built
  it yourself)

## Inputs

- `mapi_key`, `product` — same as [Inspect a project](inspect-project.md)
- `load_case_names` — a list like `["DL(ST)"]`; the exact spelling has to
  match a load case/combination that exists in the model, with the
  `(ST)`/`(CB)`/`(CS)` type suffix the manual documents

## Full code

=== "Python"

    ```python
    from midas_nx import MidasClient, Product
    from midas_nx.post.result_1 import get_reaction_table
    from midas_nx.post.base import unwrap_table

    client = MidasClient(mapi_key="paste-your-mapi-key-here", product=Product.GEN)

    raw = get_reaction_table(load_case_names=["DL(ST)"], client=client)
    table = unwrap_table(raw)

    rows = table.get("DATA", [])
    print(f"{len(rows)} reaction row(s), columns: {table.get('HEAD')}")
    for row in rows:
        print(row)
    ```

=== "JavaScript / TypeScript"

    ```js
    import { MidasClient, tables, unwrapTable } from "midas-nx";

    const client = new MidasClient({ mapiKey: "paste-your-mapi-key-here", product: "gen" });

    const raw = await tables.result1.getReactionTable({
      loadCaseNames: ["DL(ST)"],
      client,
    });
    const table = unwrapTable(raw);

    const rows = table.DATA ?? [];
    console.log(`${rows.length} reaction row(s), columns: ${table.HEAD}`);
    for (const row of rows) {
      console.log(row);
    }
    ```


## What the code does

- `get_reaction_table()` calls `POST /post/TABLE` with `TABLE_TYPE:
  "REACTIONG"` (global reaction) and the load case filter.
- The endpoint's top-level response key is unstable — it's been seen as
  the table name you passed, `"Result Table"`, and `"empty"` across
  sessions — so `unwrap_table()` finds the actual `{HEAD, DATA}` table by
  shape instead of indexing by key. Always use it rather than reading the
  response directly.
- `table["HEAD"]` is the column-name list, `table["DATA"]` is a list of
  rows (each a list of strings, in `HEAD` order).

## Expected output

```text
1 reaction row(s), columns: ['Node', 'Fx(kN)', 'Fy(kN)', 'Fz(kN)', 'Mx(kN*m)', 'My(kN*m)', 'Mz(kN*m)']
['1', '0', '0', '-10', '0', '0', '0']
```

Column names and row count depend on your model's supports and load cases.
**`0` rows is the normal result if the model hasn't been analyzed yet** —
see the precondition above — not a sign something is broken.

## Verify the result

Compare a row or two against the same load case's reaction table in the
Gen NX/Civil NX results view (Results → Reaction). The values should match
exactly, not just be in the right ballpark.

## Common errors

- **Empty `DATA` with no exception** — either the model hasn't been
  analyzed, or `load_case_names` doesn't match any case/combination that
  exists. Re-check the exact spelling (including the `(ST)`/`(CB)`/`(CS)`
  suffix) in the GUI.
- **`MidasResultError`** — a `200` response carrying an `{"error": ...}`
  body, e.g. `"Please perform analysis"`. This SDK raises rather than
  handing that back as a normal result — see
  [A 200 response does not mean success](../safety.md).
- **`MidasConnectionError` / `MidasAuthError`** — same causes as in
  [Inspect a project](inspect-project.md).

## Timeout and retry

This is a read — safe to just re-run the script if it times out. It does
*not* trigger analysis itself, so a timeout here can't leave a half-run
solve behind.

## Recovery

Not applicable — this recipe cannot modify the model.

## Related reference

- [Post and result extraction](../reference/post.md)
- [A 200 response does not mean success](../safety.md)

## Ask an AI to adapt this

```text
Using this exact script as a starting point, extract [displacement /
member force / story drift] instead of reaction, for the same load case.
Keep it strictly read-only — no create, update, delete, or analyze calls.
```
