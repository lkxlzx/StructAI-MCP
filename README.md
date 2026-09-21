# MIDAS NX MCP Connector

Zero-dependency (stdlib only) MCP server for MIDAS Gen / Civil NX.  Exposes the
MIDAS NX Open API to an LLM host through **exactly four tools**, backed by an
offline-generated **Endpoint Registry** and safety guards that encode the hard-won
live-testing pitfalls.

```text
LLM host  <--JSON-RPC/stdio-->  midas-mcp  <--HTTP + MAPI-Key-->  MIDAS Gen/Civil NX
```

## Requirements

- Python 3.9+ (tested on 3.14). No third-party packages.
- A running MIDAS Gen NX / Civil NX with the Open API enabled and a MAPI-Key.

## Quick start

Credentials live in a JSON config file, grouped into per-product **profiles**,
so MIDAS Gen NX, Civil NX and a cloud endpoint each keep their own URL + key:

```bash
# 1) create config.json next to the project (it is gitignored)
cp config.example.json config.json     # then fill in the keys
```

```json
{
  "active_profile": "MIDAS GEN NX",
  "profiles": {
    "MIDAS GEN NX":   { "base_url": "http://localhost:3030/gen",   "mapi_key": "<key>" },
    "MIDAS CIVIL NX": { "base_url": "http://localhost:3030/civil", "mapi_key": "<key>" }
  }
}
```

```bash
python -m midas_mcp                                # stdio, active profile
python -m midas_mcp --profile "MIDAS CIVIL NX"      # switch product
python -m midas_mcp --list-profiles                 # what is configured
python -m midas_mcp --show-config                   # resolved settings (key redacted)
python -m midas_mcp --transport http --port 8100    # Streamable HTTP on 127.0.0.1
```

`config.json` is discovered automatically (cwd, then project root, then the
user config dir); `--config <path>` or `MIDAS_MCP_CONFIG` overrides it.
Environment variables still win over the file, so a one-off or CI run needs no
edits: `MIDAS_MAPI_KEY="ci key" python -m midas_mcp --profile "MIDAS CIVIL NX"`.
The key is never accepted on the command line.

## The four tools

| Tool | Purpose | Maps to |
|---|---|---|
| `midas_doc` | project control + analysis | `POST /doc/<CMD>`, e.g. `NEW/SAVE/ANAL` |
| `midas_db_query` | read data; search endpoints; schema introspection | `GET /db/X` (or `/info/db/X`) |
| `midas_db_assign` | create/update data; run POST actions | `POST`/`PUT`, wrapper by registry |
| `midas_db_delete` | delete specific ids | `DELETE /db/X/<id>` |

Every MIDAS endpoint is addressed by a registry **key** (`DB:NODE`,
`POST:TABLE:REACTIONG`, `DESIGN:RC:KDS-41-20-2022:DCO`), never by a raw URL the
model supplies.  The registry carries `{uri, methods, wrapper, selector, notes}`
per endpoint (see `registry/registry.json`, ~590 endpoints).

## Guard rails (validated on live Gen NX)

- **Crash guard.** Boundary/load records keyed on node/element ids (`CONS`,
  `CNLD`, `BMLD`, `NSPR`, `SSPS`, `ELNK`, `RIGD`, …) are **refused locally**
  unless the referenced id exists.  Assigning a missing id crashes MIDAS
  (everything after it returns 502); we never let that happen.
- **Delete safety.** An empty `target_ids` is rejected — it never means "delete
  all".  Bulk delete requires `delete_all=true` *and* `MIDAS_MCP_ALLOW_BULK_DELETE=1`.
- **Payload corrections.** `EIGV.TYPE` is forced to `LANCZOS`; `MATL PARAM.P_TYPE`
  is forced to `2` (P_TYPE 1 silently zeroes POISN/THERMAL/DEN/MASS); file paths
  are converted to Windows backslashes (`EXPORT_PATH`, which fails on forward
  slashes).
- **Retry policy.** Only idempotent `GET` retries transient statuses
  (502/503/504).  `ANAL`, DELETE, IMPORT/EXPORT and design actions are never
  auto-retried.
- **Success by body, not status.** MIDAS returns `Wrong Field` error bodies with
  an HTTP 2xx; the connector classifies success from the body.
- **No wrapper injection.** `Assign`/`Argument` are chosen server-side from the
  registry; the model cannot twist the request shape.

## MIDAS knowledge surfaced as resources

- `midas://knowledge/pitfalls` — the validated pitfall table
- `midas://knowledge/routing` — tool/ordering rules (also inlined into
  `initialize.instructions`)
- `midas://registry/index` — full endpoint key list by namespace
  `midas://recipes/modal-rs`, `midas://recipes/steel-frame`,
  `midas://recipes/load-balance`, `midas://recipes/rc-section` — end-to-end
  worked sequences. `load-balance` is the equilibrium proof to run before
  quoting any extreme value.

## Development

```bash
# offline unit + protocol conformance tests (no network)
python -m unittest discover -s tests -p 'test_*.py'

# live tests against a running MIDAS (reads config.json; see Configuration below)
MIDAS_MCP_LIVE=1 python -m unittest tests.test_live_gen -v

# regenerate the registry from the vendored docs (docs/manual, pinned commit)
python build/build_registry.py

# probe every GET endpoint in the registry against the live MIDAS
python build/verify_live.py                    # config.json is auto-discovered
python build/verify_live.py --profile "MIDAS CIVIL NX"
```

The registry is generated from two sources: the v2 dev pack
(`api_chapters/*.md`, uniform Endpoint Registry tables) and the vendored
upstream manual (`docs/manual/*.md`, 505 endpoint sections across nine
formats).  Upstream wins on URI/methods; local wins on key naming/wrapper.
`build/build_registry.py --check` fails if the documented chapter counts drift.
Live probe results are folded back into each endpoint's `notes` so callers know
what this Gen build actually serves (e.g. `/db/RCHK`, `/db/DCON` design reads
are unavailable).

## Registering with a host

With `config.json` in place the host command needs no secrets in it at all.

Claude Code:

```bash
claude mcp add midas -- python -c "import sys; sys.path.insert(0,'src'); from midas_mcp.__main__ import main; main()"
# a different product:
claude mcp add midas-civil -- python -c "import sys; sys.path.insert(0,'src'); from midas_mcp.__main__ import main; main()" -- --profile "MIDAS CIVIL NX"
```

Claude Desktop `claude_desktop_config.json` — one server entry per profile:

```json
{
  "mcpServers": {
    "midas-gen": {
      "command": "python",
      "args": ["-m", "midas_mcp", "--profile", "MIDAS GEN NX"],
      "env": { "PYTHONPATH": "G:/StructAI MCP/src" }
    },
    "midas-civil": {
      "command": "python",
      "args": ["-m", "midas_mcp", "--profile", "MIDAS CIVIL NX"],
      "env": { "PYTHONPATH": "G:/StructAI MCP/src" }
    }
  }
}
```

(Adjust `PYTHONPATH`/working dir so `midas_mcp` is importable.  Set
`MIDAS_MCP_CONFIG` in `env` only if the file is not in the auto-discovered
locations.)

## Configuration reference

### Precedence

Highest wins:

1. Environment variables (`MIDAS_MAPI_KEY`, `MIDAS_BASE_URL`, `MIDAS_MCP_*`)
2. The selected profile block in the config file
3. The config file's top level (shared settings)
4. Built-in defaults

Profile selection: `--profile` > `MIDAS_MCP_PROFILE` > `active_profile` in the
file > the only profile when exactly one is defined.  Config file lookup:
`--config` > `MIDAS_MCP_CONFIG` > `./config.json` > `<project root>/config.json`
> `%APPDATA%\midas-mcp\config.json` (or `~/.config/midas-mcp/config.json`).

### Config file

```json
{
  "active_profile": "MIDAS GEN NX",
  "profiles": {
    "MIDAS GEN NX":   { "base_url": "http://localhost:3030/gen",   "mapi_key": "<key>" },
    "MIDAS CIVIL NX": { "base_url": "http://localhost:3030/civil", "mapi_key": "<key>",
                        "timeouts": { "analysis": 3600 } }
  },
  "timeouts": { "query": 30, "assign": 60, "analysis": 1800, "table": 180 },
  "allow_bulk_delete": false,
  "log_level": "warning",
  "max_workers": 8
}
```

A profile may override `base_url`, `mapi_key`, `timeouts`, `registry_dir`,
`allow_bulk_delete`, `log_level` and `max_workers`.  A flat file with just
top-level `base_url` + `mapi_key` still works.  `config.json` is gitignored —
never commit it.

### Environment variables

| Env var | Meaning | Default |
|---|---|---|
| `MIDAS_MAPI_KEY` | API key override (beats the config file) | profile value |
| `MIDAS_BASE_URL` | base URL override | profile value |
| `MIDAS_MCP_PROFILE` | profile to use | `active_profile` |
| `MIDAS_MCP_CONFIG` | config file path | auto-discovered |
| `MIDAS_MCP_TIMEOUT_QUERY/ASSIGN/ANALYSIS/TABLE` | per-class timeouts (s) | 30/60/1800/180 |
| `MIDAS_MCP_ALLOW_BULK_DELETE` | allow `delete_all` (1/true) | `false` |
| `MIDAS_MCP_LOG_LEVEL` | python logging level | `warning` |
| `MIDAS_MCP_MAX_WORKERS` | tool-call thread pool | `8` |

## API verification (live, 2026-09-21)

`docs/API_VERIFICATION_2026-09-21.md` records a full cross-check of the
registry against a running Gen NX build. Headline results:

- **0 method mismatches** across 379 endpoints once two doc under-reports were
  corrected (`DB:REBC` and `DESIGN:SRC:AIK-SRC2K:DSRC` both serve GET, which
  the manual omits).
- **0 schema field mismatches** across the 24 DB endpoints whose schema the
  server exposes at `GET /info/db/<NAME>`.
- **38 endpoints are not served by the Gen build.** They are *kept and marked*
  (`variant`: `Hyper-S-only` / `other-product` / `JP-only`) rather than removed,
  since Civil NX, Civil Designer or the Hyper-S solver do expose them.
  Run `build/verify_api.py` to refresh the evidence.
- An end-to-end cantilever built from an empty document reproduces the closed
  form to 0.02% (δ = PL³/3EI, M = P·L, V = P), pinned by `tests/live_workflow.py`.

## Variant-aware registration (v3 audit)

Per the official-source audit (`MIDAS_MCP_Connector_Development_Pack_v3_official_source`),
every endpoint is registered with a `product` and `variant` marker so callers
never assume an endpoint is universal across Civil/Gen:

- `-M1` endpoints are annotated `Hyper-S-only`.
- `DB:GALD` is `JP-only` (Civil NX Japan edition).
- `DB:HHND` (Heat of Hydration Result Graph) and `DB:GALD` are injected from
  the audit (they were absent from the vendored manuals) and live-probed.
- **Storey properties are `/ope/STORYPROP`** (STORY+PROP), not the old
  `STORPROP` spelling. It is POST-only; "no valid story information" is the
  expected empty answer until storeys exist. `/db/STOR` is a no-op stub on the
  tested Gen build.

## Limitations on the tested Gen NX build

- `/db/RCHK` (rebar layout) and the `/post/TABLE` design-force endpoints
  (`STEELMEMBERDESIGNFORCES`, `COLUMNDESIGNFORCES`, `BEAMDESIGNFORCES`) are not
  served — see the endpoint notes in the registry.
- Hyper-S (`-M1`) endpoints are Gen-version-specific.
- `accepts_analysis` results invalidate on any model change; run `/doc/ANAL`
  again before reading result tables.

## License

Proprietary and confidential - internal use only. See [LICENSE](LICENSE).
No licence is granted for redistribution or third-party use.

Note that this repository also carries MIDAS GEN NX / MIDAS CIVIL NX API
documentation (`api_chapters/`, `docs/manual/`, `docs/reference/`, `mcp/`).
That material belongs to MIDAS IT and is not covered by the notice above.