# StructAI — Persistence Layer (Phase 0)

This package is the **L7 persistence layer** of the StructAI platform: the 49
tables defined by 《StructAI MCP V2.1 设计框架规范》§4, expressed twice —

* `sql/001_schema.sql` — the raw SQLite DDL, verbatim from V2.1 §4;
* `app/models/*.py` — the SQLAlchemy 2.0 declarative equivalent, used for
  PostgreSQL, for Alembic autogenerate and for ORM access.

Cross-layer conventions (enums, ID prefixes, error codes, encryption rules,
permission codes, naming, time) are **owned by 《StructAI 架构边界与融合规范
v1.0（总纲）》§4** and are implemented once, in `app/core/`.

> **Out of scope for now:** the UI and the REST/SSE layer (`/api/v1/*`, owned by
> 《StructAI 管理器 API 接口设计规范 v1.2》). This package stops at the data
> layer plus the Phase 0 groundwork (信封/错误码/加密 primitives).

---

## Layout

```text
backend/
├── alembic.ini                  Alembic config (URL injected from Settings)
├── migrations/
│   ├── env.py                   wired to Base.metadata + Settings.database_url
│   ├── script.py.mako
│   └── versions/                no baseline revision — see sql/001_schema.sql
├── requirements.txt
├── sql/
│   ├── 001_schema.sql           49 tables (V2.1 §4)
│   └── 002_seed.sql             reference data (idempotent)
└── app/
    ├── core/
    │   ├── constants.py         总纲 §4.1 prefixes, §4.2 enums, §4.8 permissions
    │   ├── errors.py            总纲 §4.4 error registry + AppError
    │   ├── ids.py               总纲 §4.1.2 <prefix>_<yyyymmdd>_<000001>
    │   ├── crypto.py            总纲 §4.7 AES-256-GCM + secret hashing
    │   └── config.py            pydantic-settings
    ├── db/
    │   ├── base.py              Base + mixins + naming conventions
    │   ├── session.py           engine / SessionLocal / session_scope
    │   └── init_db.py           create_schema + seed_data
    └── models/                  49 models in 12 modules
```

---

## Setup

```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate
# POSIX:    source .venv/bin/activate
pip install -r requirements.txt
```

### Master key (required)

`总纲 §4.7.1` requires AES-256-GCM with a master key from the environment. Any
encrypted column raises `RuntimeError` until it is set. Use a long random value
and keep it out of version control — losing it makes every stored ciphertext
unrecoverable.

```powershell
# Windows (current session)
$env:STRUCTAI_MASTER_KEY = "<a long random passphrase>"
```

```bash
# POSIX
export STRUCTAI_MASTER_KEY="<a long random passphrase>"
```

Optional overrides (see `app/core/config.py`): `DATABASE_URL`
(default `sqlite:///./data/structai.db`), `TIMEZONE` (default `Asia/Shanghai`),
`API_HOST`, `API_PORT` (8765), `LOG_LEVEL`, `SQL_ECHO`, `RATE_LIMIT_*`.

---

## Initialise the database

```bash
python -m app.db.init_db
```

That runs, in order:

1. **`create_schema()`** — executes every `sql/*.sql` in lexical order
   (`001_schema.sql`, then `002_seed.sql`) on SQLite. On any other dialect, or
   when the scripts are absent, it falls back to `Base.metadata.create_all`.
2. **`seed_data()`** — idempotent ORM upsert of the 34 permission codes
   (总纲 §4.8.2), the 4 default roles (§4.8.3), the role→permission links and the
   5 singleton config rows. Safe to re-run; existing rows are refreshed, not
   duplicated.

The SQLite file is created automatically (default `./data/structai.db`) with
`PRAGMA foreign_keys=ON` and `journal_mode=WAL` applied to every connection.

### Migrations

The baseline schema is **not** an Alembic revision — it is `sql/001_schema.sql`.
Use Alembic only for changes made after that baseline:

```bash
alembic revision --autogenerate -m "add ..."   # run from backend/
alembic upgrade head
```

`migrations/env.py` reads the URL from `get_settings().database_url` and sets
`render_as_batch=True`, which SQLite needs because it cannot `ALTER TABLE` in
most cases.

---

## Conventions you must keep when extending

| Concern | Rule | Owner |
|---|---|---|
| Table names | `snake_case`, plural | 总纲 §4.6 |
| Index / constraint names | `ix_` / `ux_` / `ck_` / `fk_` / `pk_` | 总纲 §4.6 |
| Timestamps | UTC, ORM `default` / `onupdate`, **no triggers** | 总纲 §4.5.1 |
| Append-only tables | `task_events`, `system_logs`, `audit_logs`, `user_roles`, `role_permissions` have **no** `updated_at` | 总纲 §5.3 C-12 |
| Booleans | `INTEGER` 0/1, never a native `BOOLEAN` column | V2.1 §3.1 |
| Numeric columns | state the unit in a comment (m / mm / kN / kN/m / MPa / kg / 0-100 / 0.0-1.0) | 总纲 §4.5.2 |
| Business IDs | `<prefix>_<yyyymmdd>_<6 digits>`, prefix from the closed set | 总纲 §4.1.2/§4.1.3 |
| Secrets | AES-256-GCM at rest, `********` on echo, never plaintext | 总纲 §4.7 |
| Error codes | only from `app.core.errors.ErrorCode` | 总纲 §4.4 |

Adding a CHECK constraint? Build it from the enum so the two cannot drift:

```python
from app.db.base import enum_check
from app.core.constants import TaskStatus

__table_args__ = (enum_check("status", TaskStatus),)   # -> ck_<table>_status
```

Adding a business ID column? Use the generator:

```python
from app.core.ids import new_id
task_id = new_id("task")        # task_20260925_000001
```

---

## Quick self-check

```bash
python -c "import app.models as m; print(m.TABLE_COUNT)"   # -> 49
```

`TABLE_COUNT` is derived from `Base.metadata.tables`, so it fails loudly if a
model is dropped or a module stops being imported.
