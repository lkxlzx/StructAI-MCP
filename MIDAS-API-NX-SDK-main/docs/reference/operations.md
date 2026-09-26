# Operation functions

`/ope/*` (ch15) wraps its body in `"Argument"` — the same convention as
`midas_nx.doc`. Most ch15 endpoints have deeply-nested, highly-optional
bodies, so each function takes one `TypedDict` `argument` parameter rather
than several named keyword arguments.

::: midas_nx.ope
    options:
      members:
        - divide_elements
        - auto_mesh
        - convert_surface_spring
        - calculate_story
