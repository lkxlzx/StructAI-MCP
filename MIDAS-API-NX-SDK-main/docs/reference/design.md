# Design code chapters

RC / steel / SRC design-code chapters (ch24-27) live under `midas_nx.design`
— a different namespace from `/db/*`, mixing `DbResource`-style
config/member-CRUD endpoints with plain POST-action functions
(design-execution/table/report/image) that reuse `post/base.py`'s
`NodeElemsSelector`/`TableUnit`/`TableStyles`.

See [ROADMAP.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/ROADMAP.md)
for the full per-chapter endpoint list.

## Steel KDS 41 30:2022 (ch25)

::: midas_nx.design.steel_kds
    options:
      members:
        - SteelDesignCodeOption
        - perform_steel_code_check
        - get_steel_code_check_table

## RC KDS 41 20:2022 (ch26)

`design/rc_kds/` splits the largest chapter in the project into four files by
natural endpoint-group boundary — `setup.py`, `rebar.py`, `design_forces.py`,
`checks.py` — following the same `DbResource`-class / plain-function split as
`steel_kds.py`.

## SRC AIK-SRC2K (ch27)

`design/src_aiksrc2k.py` mirrors the same DCO/DCTL/LLRF/... setup +
check-triplet structure, kept fully self-contained (no cross-chapter
`TypedDict` reuse with `steel_kds.py`/`rc_kds/*`).
