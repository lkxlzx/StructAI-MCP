# DB resources

Every `/db/*` endpoint is a `DbResource` subclass. The base class below defines
the whole CRUD surface; each concrete resource only declares `ENDPOINT`,
`NAME`, `PRODUCTS` and `METHODS`, plus a `{ClassName}Payload` TypedDict
documenting its fields.

See [ROADMAP.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/ROADMAP.md)
for the full list of resources and their verification status.

## DbResource

::: midas_nx.db.base.DbResource

## Product gates

::: midas_nx.db.base
    options:
      members:
        - GEN_ONLY
        - CIVIL_ONLY
        - HYPER_S_ONLY
        - NO_DELETE_METHODS

## Nodes and elements

The reference implementation for the resource pattern.

::: midas_nx.db.node_element.Node

::: midas_nx.db.node_element.Element
