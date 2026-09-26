# Post / result extraction

`/post/TABLE` (ch18-23) extracts pre-process summaries, analysis results,
story tables, and design forces. Every table type shares one HTTP endpoint —
a `TABLE_TYPE` string selects which table comes back — and one response
shape (`{FORCE, DIST, HEAD, DATA}`), so `post/base.py` provides the shared
plumbing once rather than a class per table.

See [ROADMAP.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/ROADMAP.md)
for the full list of table types.

## Shared plumbing

::: midas_nx.post.base

## Example table getters

::: midas_nx.post.result_1
    options:
      members:
        - get_reaction_table
        - get_displacement_table

::: midas_nx.post.pre_process
    options:
      members:
        - get_element_weight_table

::: midas_nx.post.story
    options:
      members:
        - get_story_drift_table
