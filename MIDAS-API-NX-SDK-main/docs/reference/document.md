# Document lifecycle

`/doc/*` wraps its body in `"Argument"` rather than an ID-keyed `"Assign"`,
so these are plain functions rather than resource classes.

!!! danger "Most of the destructive surface is here"
    `/doc/NEW` discards unsaved work. `/doc/OPEN` replaces the open document.
    Every path resolves on the machine running NX, not the one running your
    script. See [Destructive operations and recovery](../safety.md).

::: midas_nx.doc
