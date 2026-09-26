# StructAI MCP V2.1 设计框架规范

**文档版本：** V2.1  
**定位：** StructAI 工程智能设计平台的 MIDAS MCP 中间层标准（设计框架层）  
**数据库基线：** SQLite 3.x，ORM 推荐 SQLAlchemy 2.x  
**接口框架：** FastAPI  
**MCP：** Model Context Protocol  
**核心目标：** 用稳定的 4 个通用 MCP Tool 抽象不同 MIDAS 系列软件和大量二级 API，避免将数百个 Endpoint 直接暴露给 LLM。

---

# 0. 文档定位

## 0.1 从属关系

本文件是 **《StructAI 架构边界与融合规范 v1.0（总纲）》** 的下位文档。

```text
《StructAI 架构边界与融合规范 v1.0（总纲）》   ← 裁决源
        ↓ 高于
《StructAI MCP V2.1 设计框架规范》（本文件）      ← 设计框架
        ↓ 高于
《StructAI 管理器 API 接口设计规范 v1.2》         ← 接口契约
```

**任何冲突，一律以总纲第 5 章「冲突裁决表」为准。** 本文件与总纲不一致之处，以总纲为准；本文件必须回改。

## 0.2 本文件拥有的内容

```text
持久层 DDL、索引、外键、CHECK 约束、种子数据（总纲所有权矩阵 #1 #2 #24）
MCP Tool 名称与 JSON Schema（#3）
MCP 返回信封（#4）
Capability 语义与编码（#5）
Tool Interface / Endpoint 映射（#6）
Adapter Protocol 与元数据（#7）
Adapter 生命周期与状态（#8）
AI 工程助手的数据与状态（总纲 §2.1 L4a 标注）
```

## 0.3 本文件不得定义的内容

按总纲 §3.1「越界判定规则」，本文件**禁止**出现：

```text
/api/v1/... 的具体请求体与响应体       → 归 v1.2
页面名称、UI 交互、UI 展示状态机        → 归 v1.2
新的错误码字符串                        → 归总纲 §4.4
新的任务状态取值                        → 归总纲 §4.2
新的 ID 前缀                            → 归总纲 §4.1
新的权限码                              → 归总纲 §4.8
实施排期与优先级                        → 归总纲 §7
验收标准                                → 归总纲 §8
SSE 事件名与载荷                        → 归 v1.2（本文件只声明能力）
```

> **说明：** 本文件在描述 REST 相关能力时，只允许出现「能力声明」与「归属指向」，不得给出可实现的路径契约。

## 0.4 唯一真源原则

> **每一个表、字段、枚举、错误码、ID 前缀、权限码，全局只允许有一个所有者。**

本文件对总纲统一约定的部分采用**收录**（逐字复制）方式，并在附录标题中标注「收录自总纲 §x.y」。收录内容若与总纲不符，以总纲为准。

## 0.5 与 V2.0 的关系

本文件是 V2.0 的修订版。V2.0 原文保留，不再维护。主要变化：

```text
28 张表            → 49 张表（新增 21 张）
§33 实施优先级     → 删除，指向总纲 §7
§34 验收标准       → 删除，指向总纲 §8
§20 手写错误码表   → 删除，指向总纲 §4.4
REST 路径残留      → 删除，指向 v1.2
```

---

# 1. V2.1 总体架构

## 1.1 架构图

```text
                    ┌─────────────────────────────┐
                    │          StructAI           │
                    │ AI Engineering Assistant    │
                    └──────────────┬──────────────┘
                                   │ MCP
                                   ▼
                    ┌─────────────────────────────┐
                    │       StructAI MCP V2.1     │
                    │                             │
                    │  ① midas_query              │
                    │  ② midas_model              │
                    │  ③ midas_execute            │
                    │  ④ midas_task               │
                    └──────────────┬──────────────┘
                                   │
                       Adapter Registry
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
       ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
       │ MIDAS Gen    │    │ MIDAS Civil  │    │ MIDAS FEA NX │
       │ Adapter      │    │ Adapter      │    │ Adapter      │
       └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
              │                    │                    │
              └────────────────────┼────────────────────┘
                                   ▼
                         MIDAS Local/Remote API
```

## 1.2 在七层模型中的位置

按总纲 §2.1，本文件覆盖 L3（结构）、L4b（MCP 4 Tools）、L5（适配层）、L7（持久层）：

```text
L3  领域服务层     Service Layer（REST 与 MCP 在此汇合）
L4a 智能编排层     AI 工程助手 —— 接口归 v1.2，数据与状态归本文件
L4b 管理编排层     MCP 4 Tools —— 本文件 §7-§11
L5  适配层         Capability Resolver / Adapter Registry —— 本文件 §12-§22
L6  集成层         MIDAS Gen / Civil / FEA NX / CSI / ...
L7  持久层         SQLite 49 张表 —— 本文件 §4
```

## 1.3 八条核心原则（V2.1 修订）

1. **LLM 只看到 4 个稳定工具。**
2. **具体 MIDAS Endpoint 不进入 LLM Tool 列表。**
3. **Endpoint、Schema、能力映射全部存数据库。**
4. **Adapter 负责软件差异、认证、协议、字段转换和错误归一化。**
5. **StructAI 负责工程语义；MCP 层负责工具编排与软件连接。**
6. **所有长任务必须具备 `task_id`，可查询、取消、重试、查看事件；MCP 侧进度获取为轮询模型（`midas_task action=events`），MCP 不提供 push/subscribe。**
7. **API Key、Token 等敏感数据只允许密文保存**；加密字段清单以总纲 §4.7.1 为封闭集合，本文件不得增删。
8. **SQLite 是默认部署方案，数据库访问层必须保持 PostgreSQL 可迁移性**：时间戳统一 UTC 存储，`updated_at` 由 ORM 层 `onupdate` 维护，**任何地方不定义数据库触发器**。

> 说明：原 V2.0 第 8 条仅提「PostgreSQL 可迁移性」。V2.1 补入「无触发器」与「UTC」两条硬约束，理由见总纲 §4.5.1 与裁决 B-6 / B-13。

## 1.4 三条数据流

```text
路径 A  管理端运维     UI → /api/v1/* → Service Layer → Adapter → MIDAS
路径 B  AI 工程助手    /api/v1/assistant/* → 意图/校验/计划/确认 → MCP 4 Tools → Capability Resolver → Adapter → MIDAS
路径 C  外部 Agent     POST /mcp → MCP 4 Tools → Capability Resolver → Adapter → MIDAS
```

三条路径**共用 L3 与 L5**，禁止各自实现一套业务逻辑。

---

# 2. 四个 MCP Tool 的职责边界

| Tool | 职责 | 典型操作 |
|---|---|---|
| `midas_query` | 查询软件状态、模型资源、能力、对象、结果 | `list` / `get` / `search` / `count` / `inspect` |
| `midas_model` | 对结构模型进行 CRUD 和校验 | `node` / `element` / `material` / `section` / `load` / `boundary` / `group` |
| `midas_execute` | 执行明确的 MIDAS 动作/命令 | `import` / `export` / `calculate` / `save` / `run` / `command` |
| `midas_task` | 管理异步任务生命周期 | `get` / `list` / `cancel` / `retry` / `logs` / `result` |

> **修订（裁决 C-1 / C-2）：** `midas_query` 的典型操作补入 `count`；`midas_task` 的典型操作统一为 `logs`（V2.0 §2 误写 `log`，与 §10 的 schema 枚举不一致）。枚举以 §7-§10 的 JSON Schema 为唯一真源。

严格禁止：

```text
不要把：
GET /some/midas/endpoint/001
GET /some/midas/endpoint/002
...
```

直接作为 MCP Tool 暴露给模型。

应采用：

```text
MCP Tool
   ↓
Intent / action
   ↓
Capability Registry
   ↓
Adapter
   ↓
Concrete Endpoint
```

---

# 3. 数据库设计原则

## 3.1 命名

- 表名：snake_case、复数
- 主键：`INTEGER PRIMARY KEY AUTOINCREMENT`（总纲 §4.1.1 强制）
- 时间：UTC，`DATETIME` 类型
- JSON：SQLite 使用 `TEXT` 保存 JSON
- 布尔：INTEGER 0/1
- 密钥：绝不明文保存
- 删除：优先软删除（`deleted_at`）
- 所有核心业务表带 `created_at`、`updated_at`

## 3.2 时间约定（总纲 §4.5.1）

```text
存储：UTC，DATETIME 类型
传输：ISO 8601 带时区偏移，默认 +08:00
```

- `created_at` / `updated_at` 由 **ORM 层**（SQLAlchemy `default` / `onupdate`）维护
- **不依赖数据库触发器**（保持 SQLite / PostgreSQL 可迁移性）
- API 输出时统一转换为配置时区（默认 `Asia/Shanghai`）
- 禁止在 DDL 中依赖 `CURRENT_TIMESTAMP` 作为唯一时间来源

> DDL 中的 `DEFAULT CURRENT_TIMESTAMP` 仅为**裸 SQL 建库时的兜底**，生产路径由 ORM 赋值覆盖。

## 3.3 追加型表例外（裁决 C-12）

以下追加型表**不设 `updated_at`**：

```text
task_events
system_logs
audit_logs
user_roles
role_permissions
```

## 3.4 核心领域

```text
身份与权限
系统配置
MCP Server / Client
MIDAS Client
Adapter / Capability / Interface / Schema
模型 Provider / AI Model
Task / Task Event
Log / Audit
Backup / Import / Export
Project / Report
AI 工程助手（assistant_*）
规范知识库 / 荷载参数库
```

## 3.5 表数量

```text
28（V2.0 原）+ 21（V2.1 新增）= 49 张
```

> **最终表数量：49。** 与总纲 §6.1 一致。

---

# 4. SQLite 完整 DDL

> 以下 DDL 为 V2.1 基线，共 **49 张表**。
> 生产代码推荐由 Alembic 管理迁移；SQLite/PostgreSQL 差异由 Repository/ORM 层处理。
>
> **时间约定：** 全部时间戳以 UTC 存储。`updated_at` 由 **ORM 层 `onupdate`** 维护，
> **不依赖数据库触发器** —— 因此本 DDL 中**不定义任何 `CREATE TRIGGER`**，
> 这与总纲 §4.5.1 及裁决 B-6 一致。
>
> **状态约定：** 全部状态列的 CHECK 取值来自总纲 §4.2，本文件不新增取值。

```sql
PRAGMA foreign_keys = ON;

BEGIN;

-- =========================================================
-- 1. 用户、角色、权限
-- =========================================================

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    password_hash   TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'enabled'
                    CHECK(status IN ('enabled','disabled','locked')),
    is_online       INTEGER NOT NULL DEFAULT 0,
    last_login_at   DATETIME,
    last_login_ip   TEXT,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    DATETIME,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      DATETIME
);

CREATE TABLE IF NOT EXISTS roles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    code        TEXT NOT NULL UNIQUE,
    description TEXT,
    is_system   INTEGER NOT NULL DEFAULT 0,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS permissions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    module      TEXT NOT NULL,
    action      TEXT NOT NULL,
    description TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 追加型表：无 updated_at（裁决 C-12）
CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    PRIMARY KEY(user_id, role_id),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE CASCADE
);

-- 追加型表：无 updated_at（裁决 C-12）
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id       INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    PRIMARY KEY(role_id, permission_id),
    FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY(permission_id) REFERENCES permissions(id) ON DELETE CASCADE
);

-- =========================================================
-- 2. 系统配置
-- =========================================================

CREATE TABLE IF NOT EXISTS system_configs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key  TEXT NOT NULL UNIQUE,
    config_value TEXT,
    value_type  TEXT NOT NULL DEFAULT 'string'
                CHECK(value_type IN ('string','integer','float','boolean','json')),
    is_secret   INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    updated_by  INTEGER,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(updated_by) REFERENCES users(id) ON DELETE SET NULL
);

-- V2.1 新增 rate_limit_* 三列（裁决 B-7）
CREATE TABLE IF NOT EXISTS security_configs (
    id                     INTEGER PRIMARY KEY CHECK(id = 1),
    captcha_enabled        INTEGER NOT NULL DEFAULT 0,
    password_min_length    INTEGER NOT NULL DEFAULT 8,
    password_complexity    INTEGER NOT NULL DEFAULT 1,
    max_login_attempts     INTEGER NOT NULL DEFAULT 5,
    lock_minutes           INTEGER NOT NULL DEFAULT 30,
    session_timeout_minutes INTEGER NOT NULL DEFAULT 30,
    login_log_enabled      INTEGER NOT NULL DEFAULT 1,
    api_auth_required      INTEGER NOT NULL DEFAULT 1,
    rate_limit_enabled     INTEGER NOT NULL DEFAULT 1,
    rate_limit_per_minute  INTEGER NOT NULL DEFAULT 120,
    rate_limit_burst       INTEGER NOT NULL DEFAULT 30,
    updated_at             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS service_configs (
    id          INTEGER PRIMARY KEY CHECK(id = 1),
    host        TEXT NOT NULL DEFAULT '0.0.0.0',
    port        INTEGER NOT NULL DEFAULT 8765,
    workers     INTEGER NOT NULL DEFAULT 2,
    log_level   TEXT NOT NULL DEFAULT 'INFO',
    cors_enabled INTEGER NOT NULL DEFAULT 1,
    auto_start  INTEGER NOT NULL DEFAULT 1,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 3. MCP Server / Client
-- =========================================================

-- V2.1 新增 started_at（裁决 A-2）；status 补 CHECK（裁决 B-10）
CREATE TABLE IF NOT EXISTS mcp_servers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    host           TEXT NOT NULL DEFAULT '0.0.0.0',
    port           INTEGER NOT NULL DEFAULT 8765,
    protocol_version TEXT NOT NULL DEFAULT '2024-11-05',
    transport      TEXT NOT NULL DEFAULT 'streamable_http',
    status         TEXT NOT NULL DEFAULT 'stopped'
                   CHECK(status IN ('stopped','starting','running','stopping','error')),
    enabled        INTEGER NOT NULL DEFAULT 1,
    started_at     DATETIME,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mcp_clients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    client_id       TEXT NOT NULL UNIQUE,
    client_type     TEXT,
    remote_addr     TEXT,
    protocol_version TEXT,
    status          TEXT NOT NULL DEFAULT 'disconnected'
                    CHECK(status IN ('disconnected','connected')),
    last_seen_at    DATETIME,
    metadata_json   TEXT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- V2.1 新增（B-1）：MCP Client 凭据存储。
-- 一个 mcp_client 可持有多个凭据（轮换期并存），故按 client 一对多建模。
CREATE TABLE IF NOT EXISTS mcp_client_credentials (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    mcp_client_id INTEGER NOT NULL,
    secret_hash   TEXT NOT NULL,                  -- 单向哈希，见总纲 §4.7.1
    secret_prefix TEXT,                           -- 仅用于回显识别，不含密钥本体
    scopes_json   TEXT,                           -- 该凭据被授予的权限码子集
    expires_at    DATETIME,
    last_used_at  DATETIME,
    revoked_at    DATETIME,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(mcp_client_id) REFERENCES mcp_clients(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_mcp_client_credentials_client
ON mcp_client_credentials(mcp_client_id);

-- =========================================================
-- 4. MIDAS Client
-- =========================================================

-- status 补 CHECK（裁决 B-10）
CREATE TABLE IF NOT EXISTS midas_clients (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    -- 多租户归属（《MIDAS API 对接规范》§2.5.4 第 5 条）：
    -- 平台为局域网内多部门共用，每个部门接入自己的 MIDAS 实例。
    owner_id            INTEGER,
    department          TEXT,
    visibility          TEXT NOT NULL DEFAULT 'private'
                        CHECK(visibility IN ('private','department','public')),
    software            TEXT NOT NULL,
    version             TEXT,
    adapter_code        TEXT NOT NULL,
    -- 含产品段的完整 Base URL，如 https://moa-engineers.midasit.com:443/gen
    -- （对接规范 §2.1：MIDAS NX 为云端中继，非本地 REST）
    api_url             TEXT NOT NULL,
    api_key_encrypted   TEXT,
    access_token_encrypted TEXT,
    timeout_seconds     INTEGER NOT NULL DEFAULT 60,
    -- 单实例并发恒为 1（对接规范 §2.5.2：GUI 单实例，弹框会阻塞整条通道）
    max_concurrency     INTEGER NOT NULL DEFAULT 1
                        CHECK(max_concurrency = 1),
    proxy_enabled       INTEGER NOT NULL DEFAULT 0,
    proxy_url           TEXT,
    verify_tls          INTEGER NOT NULL DEFAULT 1,
    enabled             INTEGER NOT NULL DEFAULT 1,
    status              TEXT NOT NULL DEFAULT 'disconnected'
                        CHECK(status IN ('disconnected','connecting','connected','error')),
    last_connected_at   DATETIME,
    last_error          TEXT,
    metadata_json       TEXT,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(adapter_code) REFERENCES adapters(code),
    FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_midas_clients_adapter
ON midas_clients(adapter_code);

CREATE INDEX IF NOT EXISTS ix_midas_clients_status
ON midas_clients(status);

CREATE INDEX IF NOT EXISTS ix_midas_clients_owner
ON midas_clients(owner_id);

-- =========================================================
-- 5. Adapter 注册
-- =========================================================

-- status 补 CHECK（裁决 B-10）
CREATE TABLE IF NOT EXISTS adapters (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    software        TEXT NOT NULL,
    version_range   TEXT,
    implementation  TEXT NOT NULL,
    protocol        TEXT,
    capabilities_json TEXT,
    status          TEXT NOT NULL DEFAULT 'enabled'
                    CHECK(status IN ('enabled','disabled','error')),
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 6. AI Provider / Model
-- =========================================================

CREATE TABLE IF NOT EXISTS model_providers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    code          TEXT NOT NULL UNIQUE,
    base_url      TEXT,
    provider_type TEXT NOT NULL DEFAULT 'openai_compatible',
    enabled       INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- status 补 CHECK（裁决 B-10）；max_retries 对齐（空白修正）
CREATE TABLE IF NOT EXISTS models (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id           INTEGER NOT NULL,
    name                  TEXT NOT NULL,
    model_code            TEXT NOT NULL,
    model_type            TEXT NOT NULL DEFAULT 'chat',
    context_length        INTEGER,
    max_output_tokens     INTEGER,
    api_url               TEXT,
    api_key_encrypted     TEXT,
    timeout_seconds       INTEGER NOT NULL DEFAULT 60,
    proxy_enabled         INTEGER NOT NULL DEFAULT 0,
    proxy_url             TEXT,
    temperature           REAL NOT NULL DEFAULT 0.7,
    top_p                 REAL NOT NULL DEFAULT 0.9,
    stream_enabled        INTEGER NOT NULL DEFAULT 1,
    tool_calling_enabled  INTEGER NOT NULL DEFAULT 1,
    json_output_enabled   INTEGER NOT NULL DEFAULT 1,
    retry_enabled         INTEGER NOT NULL DEFAULT 1,
    max_retries           INTEGER NOT NULL DEFAULT 3,
    status                TEXT NOT NULL DEFAULT 'unavailable'
                          CHECK(status IN ('available','unavailable','error')),
    is_default            INTEGER NOT NULL DEFAULT 0,
    last_test_at          DATETIME,
    last_test_status      TEXT,
    last_test_latency_ms  INTEGER,
    metadata_json         TEXT,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at            DATETIME,
    FOREIGN KEY(provider_id) REFERENCES model_providers(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_models_provider_code
ON models(provider_id, model_code);

CREATE UNIQUE INDEX IF NOT EXISTS ux_default_model
ON models(is_default)
WHERE is_default = 1 AND deleted_at IS NULL;

-- =========================================================
-- 7. MCP Tool
-- =========================================================

-- version 默认值改为 '2.1'（裁决 C-5）
CREATE TABLE IF NOT EXISTS tools (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    description     TEXT,
    version         TEXT NOT NULL DEFAULT '2.1',
    tool_type       TEXT NOT NULL DEFAULT 'generalized',
    input_schema_json TEXT NOT NULL,
    output_schema_json TEXT,
    enabled         INTEGER NOT NULL DEFAULT 1,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 8. MIDAS 二级 Interface
-- =========================================================

-- V2.1 变更（裁决 B-3）：
--   tool_id 允许 NULL —— 同一个二级 Interface 可被多个 Tool 共享
--   （例如同一 Endpoint 同时服务于 midas_query 与 midas_model），
--   共享关系由 capability_interfaces 与 capabilities 表达，
--   唯一键为 (adapter_code, interface_code)，不再由 tool_id 参与。
--
-- V2.1 增补（对接规范 §7.1）：新增 request_wrapper / response_root_key 两列，
--   承载 /db/* 与 /doc/* 的请求包装键与 GET 响应外层资源键（见 §17.3）。
CREATE TABLE IF NOT EXISTS tool_interfaces (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id           INTEGER,
    adapter_code      TEXT NOT NULL,
    interface_code    TEXT NOT NULL,
    method            TEXT NOT NULL,
    -- 对接规范 §3.5 第 8 条：/post/* 族的 URI 统一为共享的 /post/TABLE，
    -- 具体结果表由 Argument 对象中的 TABLE_TYPE 值选择；
    -- /DESIGN/**/TABLE 同理（URI 共享，靠 TABLE_TYPE 区分）。
    -- 因此 interface_code 必须按「表类型」判别，不能按 URI 判别（见 §17.4）。
    endpoint          TEXT NOT NULL,
    -- 对接规范 §3.1：请求外层包装键。
    --   'Assign'   → /db/*（编号键 ID → 数据对象）
    --   'Argument' → /doc/* 与多数 design / post 动作
    --   NULL       → 端点不接收请求体
    request_wrapper     TEXT,
    -- 对接规范 §3.2：GET 响应的最外层资源键（如 'NODE'），解包时据此取内层对象；
    -- 来源文档未记载 GET body 时为 NULL。
    response_root_key   TEXT,
    operation         TEXT NOT NULL,
    resource          TEXT,
    -- V2.1 增补（总纲 §4.2.11）：能力三层分类。
    --   product_scope = 该端点适用于哪个 MIDAS 产品
    --   domain        = 业务域（前端一级菜单 / LLM 第一层筛选）
    --   feature       = 手册章节（前端二级菜单 / LLM 第二层筛选）
    -- 三者为**列而非 metadata_json 字段**：product_scope 在每次能力解析时都要
    -- 过滤，domain/feature 是前端分组依据，索引友好是硬要求。
    --
    -- product_scope 默认 'unknown' 是一等状态：手册的产品标注不可信
    -- （对接规范 §3.5 第 15 条：47 条声明 Civil 专属的端点中 32 条在 Gen 上
    -- 也能应答），因此「尚未实机验证」必须可表达。unknown 的能力**乐观放行**，
    -- 但信封 warnings 带 unverified 提示（总纲 §4.2.11 裁决）。
    product_scope     TEXT NOT NULL DEFAULT 'unknown'
                      CHECK(product_scope IN ('gen','civil','designer','both','unknown')),
    -- domain 可空（未归域）。**不写 IS NULL OR**：CHECK 仅在 FALSE 时失败，
    -- 而 NULL IN (...) 求值为 NULL，三值逻辑下通过。刻意与 ORM 的 enum_check
    -- 同形，否则 SQLite（本 DDL）与 PostgreSQL（create_all）约束不一致。
    domain            TEXT
                      CHECK(domain IN (
                          'project','model','load','analysis',
                          'result','design','view','operation'
                      )),
    feature           TEXT,
    request_schema_json TEXT,
    response_schema_json TEXT,
    enabled           INTEGER NOT NULL DEFAULT 1,
    timeout_seconds   INTEGER NOT NULL DEFAULT 60,
    async_supported   INTEGER NOT NULL DEFAULT 0,
    metadata_json     TEXT,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(tool_id) REFERENCES tools(id) ON DELETE SET NULL,
    FOREIGN KEY(adapter_code) REFERENCES adapters(code)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_tool_interface
ON tool_interfaces(adapter_code, interface_code);

CREATE INDEX IF NOT EXISTS ix_tool_interfaces_tool
ON tool_interfaces(tool_id);

-- 总纲 §4.2.11：三层分类的复合索引。能力解析按产品过滤，前端按 域→章 分组，
-- 一个索引同时服务两者。
CREATE INDEX IF NOT EXISTS ix_tool_interfaces_scope
ON tool_interfaces(product_scope, domain, feature);

-- =========================================================
-- 9. Schema Registry
-- =========================================================

-- V2.1 变更（裁决 B-2）：schema_code 不再全局唯一，
-- 改为 (schema_code, version) 复合唯一，以支持同一 Schema 多版本并存。
CREATE TABLE IF NOT EXISTS schemas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    schema_code    TEXT NOT NULL,
    name           TEXT NOT NULL,
    version        TEXT NOT NULL,
    schema_type    TEXT NOT NULL,
    schema_json    TEXT NOT NULL,
    description    TEXT,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_schemas_code_version
ON schemas(schema_code, version);

CREATE INDEX IF NOT EXISTS ix_schemas_type
ON schemas(schema_type);

-- =========================================================
-- 10. Capability Registry
-- =========================================================

-- v1.0 修订两处（在表仍为空时改，零迁移成本）：
--   * 新增 tool_id —— `Capability.tool`（MCP 工具名）此前在库里**没有归宿**。
--     它**不能**从 tool_interfaces.tool_id 推导：实测 /post/TABLE 的 POST 被
--     midas_execute 与 midas_query 共用（B-3 引入 capability_interfaces 正是
--     为了这种共用），而 platform-owned 的能力根本没有 interface。
--     因此 tool 是**能力自身**的属性。
--   * adapter_code 改为**可空** —— midas_task 的 7 个能力是 platform-owned
--     （对接规范 §2.5.1），没有 adapter 可指。
CREATE TABLE IF NOT EXISTS capabilities (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id          INTEGER NOT NULL,
    adapter_code     TEXT,
    capability_code  TEXT NOT NULL,
    resource         TEXT NOT NULL,
    action           TEXT NOT NULL,
    description      TEXT,
    interface_id     INTEGER,
    enabled          INTEGER NOT NULL DEFAULT 1,
    constraints_json TEXT,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(tool_id) REFERENCES tools(id),
    FOREIGN KEY(adapter_code) REFERENCES adapters(code),
    FOREIGN KEY(interface_id) REFERENCES tool_interfaces(id)
);

-- 有 adapter 的能力：(adapter_code, capability_code) 唯一。
-- **同一 capability_code 可对每个 adapter 各存一行** —— 这正是多产品扩展所需的
-- 键（node.list 在 gen / civil / designer 上各一行）。注意：代码里的 `_TABLE`
-- 目前只按 `code` 键控，无法表达这一点，是阶段 2 暴露的待修项。
CREATE UNIQUE INDEX IF NOT EXISTS ux_capability
ON capabilities(adapter_code, capability_code);

-- platform-owned 的能力（adapter_code IS NULL）：capability_code 全局唯一。
-- SQL 里 NULL 互不相等，所以上面那条复合唯一索引**管不住**这一半；
-- 没有本索引，`task.get` 可以被插入两次而无人察觉。
CREATE UNIQUE INDEX IF NOT EXISTS ux_capability_platform
ON capabilities(capability_code) WHERE adapter_code IS NULL;

CREATE INDEX IF NOT EXISTS ix_capabilities_resource_action
ON capabilities(resource, action);

CREATE INDEX IF NOT EXISTS ix_capabilities_tool
ON capabilities(tool_id);

-- V2.1 新增（B-3）：Capability ↔ Interface 多对多关联表。
-- 一个能力可能由多个 Interface 组合实现；一个 Interface 可被多个能力复用。
CREATE TABLE IF NOT EXISTS capability_interfaces (
    capability_id INTEGER NOT NULL,
    interface_id  INTEGER NOT NULL,
    PRIMARY KEY(capability_id, interface_id),
    FOREIGN KEY(capability_id) REFERENCES capabilities(id) ON DELETE CASCADE,
    FOREIGN KEY(interface_id) REFERENCES tool_interfaces(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_capability_interfaces_interface
ON capability_interfaces(interface_id);

-- =========================================================
-- 11. Task
-- =========================================================

-- V2.1 变更：
--   status 补 CHECK（裁决 B-10）
--   type   补 CHECK（裁决 A-6，业务任务类型封闭枚举）
--   tool_name → tools(name)、adapter_code → adapters(code) 补外键（裁决 B-11）
--
-- tasks.type   = 业务任务类型（封闭枚举，见 §26.2）
-- tasks.action = 具体动作，复用 MCP action 词表（见 §6.3）
CREATE TABLE IF NOT EXISTS tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id           TEXT NOT NULL UNIQUE,
    parent_task_id    TEXT,
    type              TEXT NOT NULL
                      CHECK(type IN (
                          'calculate','analysis','report','export','import',
                          'backup','restore','cleanup','drawing_recognize',
                          'model_import','optimization','code_check',
                          'load_generate','ai_plan_execute'
                      )),
    action            TEXT NOT NULL,
    resource          TEXT,
    tool_name         TEXT,
    adapter_code      TEXT,
    midas_client_id   INTEGER,
    model_id          INTEGER,
    requested_by      INTEGER,
    status            TEXT NOT NULL DEFAULT 'queued'
                      CHECK(status IN ('queued','running','success','failed','cancelled','retrying')),
    progress          REAL NOT NULL DEFAULT 0,
    priority          INTEGER NOT NULL DEFAULT 5,
    input_json        TEXT,
    result_json       TEXT,
    error_code        TEXT,
    error_message     TEXT,
    retry_count       INTEGER NOT NULL DEFAULT 0,
    max_retries       INTEGER NOT NULL DEFAULT 3,
    request_id        TEXT,
    queued_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at        DATETIME,
    finished_at       DATETIME,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(parent_task_id) REFERENCES tasks(task_id) ON DELETE SET NULL,
    FOREIGN KEY(tool_name) REFERENCES tools(name) ON DELETE SET NULL,
    FOREIGN KEY(adapter_code) REFERENCES adapters(code) ON DELETE SET NULL,
    FOREIGN KEY(midas_client_id) REFERENCES midas_clients(id) ON DELETE SET NULL,
    FOREIGN KEY(model_id) REFERENCES models(id) ON DELETE SET NULL,
    FOREIGN KEY(requested_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS ix_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS ix_tasks_adapter ON tasks(adapter_code);
CREATE INDEX IF NOT EXISTS ix_tasks_type ON tasks(type);
CREATE INDEX IF NOT EXISTS ix_tasks_tool ON tasks(tool_name);
CREATE INDEX IF NOT EXISTS ix_tasks_request_id ON tasks(request_id);

-- 追加型表：无 updated_at（裁决 C-12）
CREATE TABLE IF NOT EXISTS task_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    progress    REAL,
    message     TEXT,
    payload_json TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_task_events_task
ON task_events(task_id, created_at);

-- =========================================================
-- 12. Logs
-- =========================================================

-- 追加型表：无 updated_at（裁决 C-12）
CREATE TABLE IF NOT EXISTS system_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    level       TEXT NOT NULL,
    module      TEXT NOT NULL,
    action      TEXT,
    message     TEXT NOT NULL,
    task_id     TEXT,
    adapter_request_id TEXT,
    user_id     INTEGER,
    request_id  TEXT,
    metadata_json TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE SET NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_system_logs_time
ON system_logs(timestamp);

CREATE INDEX IF NOT EXISTS ix_system_logs_level
ON system_logs(level);

CREATE INDEX IF NOT EXISTS ix_system_logs_module
ON system_logs(module);

-- V2.1 新增索引（裁决 B-12）
CREATE INDEX IF NOT EXISTS ix_system_logs_task
ON system_logs(task_id);

CREATE INDEX IF NOT EXISTS ix_system_logs_module_time
ON system_logs(module, timestamp);

-- 追加型表：无 updated_at（裁决 C-12）
CREATE TABLE IF NOT EXISTS audit_logs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER,
    action         TEXT NOT NULL,
    resource_type  TEXT,
    resource_id    TEXT,
    method         TEXT,
    path           TEXT,
    ip_address     TEXT,
    request_id     TEXT,
    before_json    TEXT,
    after_json     TEXT,
    result         TEXT,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_audit_logs_time
ON audit_logs(created_at);

-- V2.1 新增索引（裁决 B-12）
CREATE INDEX IF NOT EXISTS ix_audit_logs_user
ON audit_logs(user_id);

CREATE INDEX IF NOT EXISTS ix_audit_logs_resource
ON audit_logs(resource_type, resource_id);

-- =========================================================
-- 13. Backup / Import / Export
-- =========================================================

-- V2.1 变更（裁决 C-10）：storage_path 改为平台自适应相对路径，
-- 相对「进程工作目录」，Windows / Linux / Docker 均成立。
CREATE TABLE IF NOT EXISTS backup_configs (
    id              INTEGER PRIMARY KEY CHECK(id = 1),
    enabled         INTEGER NOT NULL DEFAULT 1,
    frequency       TEXT NOT NULL DEFAULT 'daily',
    retention_count INTEGER NOT NULL DEFAULT 7,
    storage_path    TEXT NOT NULL DEFAULT './data/backups',
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- status 补 CHECK（裁决 B-10）
CREATE TABLE IF NOT EXISTS backups (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_id    TEXT NOT NULL UNIQUE,
    type         TEXT NOT NULL DEFAULT 'automatic',
    file_path    TEXT NOT NULL,
    file_size    INTEGER,
    checksum     TEXT,
    status       TEXT NOT NULL DEFAULT 'processing'
                 CHECK(status IN ('processing','success','failed')),
    error_message TEXT,
    created_by   INTEGER,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at  DATETIME,
    FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);

-- status 补 CHECK（裁决 B-10）
CREATE TABLE IF NOT EXISTS data_exports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    export_id    TEXT NOT NULL UNIQUE,
    scope_json   TEXT NOT NULL,
    format       TEXT NOT NULL DEFAULT 'json',
    file_path    TEXT,
    file_size    INTEGER,
    status       TEXT NOT NULL DEFAULT 'processing'
                 CHECK(status IN ('processing','success','failed')),
    error_message TEXT,
    created_by   INTEGER,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at  DATETIME,
    FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);

-- status 补 CHECK（裁决 B-10）
CREATE TABLE IF NOT EXISTS data_imports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id    TEXT NOT NULL UNIQUE,
    file_path    TEXT NOT NULL,
    scope_json   TEXT,
    status       TEXT NOT NULL DEFAULT 'processing'
                 CHECK(status IN ('processing','success','failed')),
    error_message TEXT,
    created_by   INTEGER,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at  DATETIME,
    FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS cleanup_configs (
    id                INTEGER PRIMARY KEY CHECK(id = 1),
    task_retention_days INTEGER NOT NULL DEFAULT 30,
    log_retention_days  INTEGER NOT NULL DEFAULT 60,
    audit_retention_days INTEGER NOT NULL DEFAULT 180,
    cleanup_deleted_users INTEGER NOT NULL DEFAULT 0,
    cleanup_temp_files INTEGER NOT NULL DEFAULT 1,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 14. Session / API Token
-- =========================================================

CREATE TABLE IF NOT EXISTS sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL UNIQUE,
    user_id       INTEGER NOT NULL,
    token_hash    TEXT NOT NULL,
    ip_address    TEXT,
    user_agent    TEXT,
    expires_at    DATETIME NOT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at    DATETIME,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_sessions_user
ON sessions(user_id);

-- =========================================================
-- 15. Project / Report（V2.1 新增：N-7、B-5）
-- =========================================================

CREATE TABLE IF NOT EXISTS projects (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    code          TEXT NOT NULL UNIQUE,
    description   TEXT,
    owner_id      INTEGER,
    status        TEXT NOT NULL DEFAULT 'active'
                  CHECK(status IN ('active','archived')),
    metadata_json TEXT,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at    DATETIME,
    FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_projects_owner
ON projects(owner_id);

-- status 取值与 backups / data_exports / data_imports 对齐（总纲 §4.2.5）
CREATE TABLE IF NOT EXISTS reports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id     TEXT NOT NULL UNIQUE,
    task_id       TEXT,
    project_id    TEXT,
    model_id      INTEGER,
    report_type   TEXT NOT NULL DEFAULT 'calculation'
                  CHECK(report_type IN ('calculation','analysis','design','check','custom')),
    format        TEXT NOT NULL DEFAULT 'pdf',
    include_json  TEXT,
    file_id       TEXT,
    status        TEXT NOT NULL DEFAULT 'processing'
                  CHECK(status IN ('processing','success','failed')),
    error_message TEXT,
    created_by    INTEGER,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at   DATETIME,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE SET NULL,
    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE SET NULL,
    FOREIGN KEY(model_id) REFERENCES models(id) ON DELETE SET NULL,
    FOREIGN KEY(file_id) REFERENCES assistant_files(file_id) ON DELETE SET NULL,
    FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_reports_task ON reports(task_id);
CREATE INDEX IF NOT EXISTS ix_reports_project ON reports(project_id);
CREATE INDEX IF NOT EXISTS ix_reports_status ON reports(status);

-- =========================================================
-- 16. AI 工程助手（V2.1 新增 14 张表，来源 v1.1 §98 + 总纲 §6.1）
-- =========================================================

-- --- 16.1 文件本体（裁决 N-23：files = 上传与产物文件本体） ---
CREATE TABLE IF NOT EXISTS assistant_files (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id      TEXT NOT NULL UNIQUE,
    session_id   TEXT,
    task_id      TEXT,
    file_name    TEXT NOT NULL,
    file_type    TEXT,
    mime_type    TEXT,
    file_size    INTEGER,
    storage_path TEXT NOT NULL,
    checksum     TEXT,
    purpose      TEXT NOT NULL DEFAULT 'upload'
                 CHECK(purpose IN ('upload','output','temp')),
    source       TEXT,
    created_by   INTEGER,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at   DATETIME,
    FOREIGN KEY(session_id) REFERENCES assistant_sessions(session_id) ON DELETE SET NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE SET NULL,
    FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_assistant_files_session
ON assistant_files(session_id);

CREATE INDEX IF NOT EXISTS ix_assistant_files_task
ON assistant_files(task_id);

-- --- 16.2 会话（裁决 N-25：midas_client_id → midas_clients(id)） ---
CREATE TABLE IF NOT EXISTS assistant_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL UNIQUE,
    user_id         INTEGER NOT NULL,
    title           TEXT,
    model_id        INTEGER,
    midas_client_id INTEGER,
    project_id      TEXT,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK(status IN ('active','archived')),
    last_message_at DATETIME,
    message_count   INTEGER NOT NULL DEFAULT 0,
    metadata_json   TEXT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      DATETIME,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(model_id) REFERENCES models(id) ON DELETE SET NULL,
    FOREIGN KEY(midas_client_id) REFERENCES midas_clients(id) ON DELETE SET NULL,
    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_assistant_sessions_user
ON assistant_sessions(user_id);

CREATE INDEX IF NOT EXISTS ix_assistant_sessions_status
ON assistant_sessions(status);

-- --- 16.3 对话消息 ---
CREATE TABLE IF NOT EXISTS assistant_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id   TEXT NOT NULL UNIQUE,
    session_id   TEXT NOT NULL,
    role         TEXT NOT NULL
                 CHECK(role IN ('user','assistant','system')),
    content      TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'text',
    intent_id    TEXT,
    plan_id      TEXT,
    model_code   TEXT,
    tokens_in    INTEGER,
    tokens_out   INTEGER,
    latency_ms   INTEGER,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES assistant_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY(intent_id) REFERENCES assistant_intents(intent_id) ON DELETE SET NULL,
    FOREIGN KEY(plan_id) REFERENCES assistant_plans(plan_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_assistant_messages_session
ON assistant_messages(session_id, created_at);

-- --- 16.4 工程意图 ---
CREATE TABLE IF NOT EXISTS assistant_intents (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    intent_id               TEXT NOT NULL UNIQUE,
    session_id              TEXT NOT NULL,
    message_id              TEXT,
    intent                  TEXT NOT NULL,
    discipline              TEXT,
    entities_json           TEXT,
    missing_parameters_json TEXT,
    warnings_json           TEXT,
    confidence              REAL,
    created_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES assistant_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY(message_id) REFERENCES assistant_messages(message_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_assistant_intents_session
ON assistant_intents(session_id);

-- --- 16.5 执行计划（status 取值见总纲 §4.2.2） ---
CREATE TABLE IF NOT EXISTS assistant_plans (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id                  TEXT NOT NULL UNIQUE,
    session_id               TEXT NOT NULL,
    intent_id                TEXT,
    title                    TEXT,
    status                   TEXT NOT NULL DEFAULT 'draft'
                             CHECK(status IN (
                                 'draft','validating','awaiting_confirmation','approved',
                                 'rejected','executing','verifying','completed',
                                 'failed','cancelled'
                             )),
    risk_level               TEXT NOT NULL DEFAULT 'low'
                             CHECK(risk_level IN ('low','medium','high')),
    requires_confirmation    INTEGER NOT NULL DEFAULT 0,
    confirmation_token_hash  TEXT,                -- 单向哈希，见总纲 §4.7.1
    confirmation_expires_at  DATETIME,
    confirmed_by             INTEGER,
    confirmed_at             DATETIME,
    task_id                  TEXT,
    steps_total              INTEGER NOT NULL DEFAULT 0,
    steps_done               INTEGER NOT NULL DEFAULT 0,
    error_code               TEXT,
    created_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES assistant_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY(intent_id) REFERENCES assistant_intents(intent_id) ON DELETE SET NULL,
    FOREIGN KEY(confirmed_by) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_assistant_plans_session
ON assistant_plans(session_id);

CREATE INDEX IF NOT EXISTS ix_assistant_plans_status
ON assistant_plans(status);

CREATE INDEX IF NOT EXISTS ix_assistant_plans_task
ON assistant_plans(task_id);

-- --- 16.6 计划步骤（裁决 N-1：可执行形式） ---
CREATE TABLE IF NOT EXISTS assistant_plan_steps (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id       TEXT NOT NULL,
    step_no       INTEGER NOT NULL,
    step_id       TEXT,
    name          TEXT,
    tool_name     TEXT,                       -- midas_query / midas_model / midas_execute / midas_task
    action        TEXT,                       -- 复用 MCP action 词表（§6.3）
    resource      TEXT,                       -- 复用 MCP resource 词表（单数，总纲 §4.6.1）
    params_json   TEXT,
    depends_on_json TEXT,
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK(status IN ('pending','running','completed','failed','skipped')),
    progress      REAL NOT NULL DEFAULT 0,
    task_id       TEXT,
    result_json   TEXT,
    error_code    TEXT,
    error_message TEXT,
    started_at    DATETIME,
    finished_at   DATETIME,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(plan_id) REFERENCES assistant_plans(plan_id) ON DELETE CASCADE,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE SET NULL,
    UNIQUE(plan_id, step_no)
);

CREATE INDEX IF NOT EXISTS ix_assistant_plan_steps_status
ON assistant_plan_steps(status);

CREATE INDEX IF NOT EXISTS ix_assistant_plan_steps_task
ON assistant_plan_steps(task_id);

-- --- 16.7 产物语义记录（裁决 N-23：outputs = 关联 file + 类型 + 元数据） ---
CREATE TABLE IF NOT EXISTS assistant_outputs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    output_id     TEXT NOT NULL UNIQUE,
    session_id    TEXT,
    task_id       TEXT,
    plan_id       TEXT,
    output_type   TEXT NOT NULL DEFAULT 'result'
                  CHECK(output_type IN ('report','drawing','model_file','result')),
    format        TEXT,
    file_id       TEXT,
    title         TEXT,
    metadata_json TEXT,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES assistant_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE SET NULL,
    FOREIGN KEY(plan_id) REFERENCES assistant_plans(plan_id) ON DELETE SET NULL,
    FOREIGN KEY(file_id) REFERENCES assistant_files(file_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_assistant_outputs_session
ON assistant_outputs(session_id);

CREATE INDEX IF NOT EXISTS ix_assistant_outputs_task
ON assistant_outputs(task_id);

-- --- 16.8 识图任务 ---
CREATE TABLE IF NOT EXISTS assistant_drawing_tasks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    drawing_id          TEXT NOT NULL UNIQUE,
    task_id             TEXT,
    session_id          TEXT,
    file_id             TEXT,
    discipline          TEXT,
    recognition_profile TEXT,
    status              TEXT NOT NULL DEFAULT 'queued'
                        CHECK(status IN ('queued','running','success','failed','cancelled')),
    progress            REAL NOT NULL DEFAULT 0,
    confidence_avg      REAL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at         DATETIME,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE SET NULL,
    FOREIGN KEY(session_id) REFERENCES assistant_sessions(session_id) ON DELETE SET NULL,
    FOREIGN KEY(file_id) REFERENCES assistant_files(file_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_assistant_drawing_tasks_task
ON assistant_drawing_tasks(task_id);

CREATE INDEX IF NOT EXISTS ix_assistant_drawing_tasks_status
ON assistant_drawing_tasks(status);

-- --- 16.9 识图对象 ---
CREATE TABLE IF NOT EXISTS assistant_drawing_objects (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    drawing_id        TEXT NOT NULL,
    object_type       TEXT NOT NULL,
    object_ref        TEXT NOT NULL,
    bbox_json         TEXT,
    confidence        REAL,
    properties_json   TEXT,
    mapped_node_id    TEXT,
    mapped_element_id TEXT,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(drawing_id) REFERENCES assistant_drawing_tasks(drawing_id) ON DELETE CASCADE,
    UNIQUE(drawing_id, object_ref)
);

CREATE INDEX IF NOT EXISTS ix_assistant_drawing_objects_type
ON assistant_drawing_objects(object_type);

-- --- 16.10 识图设置（单例表，补 v1.1 §76 缺表） ---
CREATE TABLE IF NOT EXISTS assistant_drawing_settings (
    id                    INTEGER PRIMARY KEY CHECK(id = 1),
    recognize_axis        INTEGER NOT NULL DEFAULT 1,
    recognize_dimensions  INTEGER NOT NULL DEFAULT 1,
    recognize_elevation   INTEGER NOT NULL DEFAULT 1,
    recognize_members     INTEGER NOT NULL DEFAULT 1,
    recognize_materials   INTEGER NOT NULL DEFAULT 1,
    recognize_loads       INTEGER NOT NULL DEFAULT 1,
    confidence_threshold  REAL NOT NULL DEFAULT 0.85,
    updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- --- 16.11 工程模板 ---
CREATE TABLE IF NOT EXISTS assistant_templates (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    template_code      TEXT NOT NULL UNIQUE,
    name               TEXT NOT NULL,
    category           TEXT,
    discipline         TEXT,
    description        TEXT,
    param_schema_json  TEXT,
    plan_template_json TEXT,
    is_system          INTEGER NOT NULL DEFAULT 0,
    sort_order         INTEGER NOT NULL DEFAULT 0,
    enabled            INTEGER NOT NULL DEFAULT 1,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_assistant_templates_category
ON assistant_templates(category, sort_order);

-- --- 16.12 示例案例 ---
CREATE TABLE IF NOT EXISTS assistant_examples (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    example_code  TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    category      TEXT,
    description   TEXT,
    template_id   INTEGER,
    steps_json    TEXT,
    run_config_json TEXT,
    is_system     INTEGER NOT NULL DEFAULT 0,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    enabled       INTEGER NOT NULL DEFAULT 1,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(template_id) REFERENCES assistant_templates(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_assistant_examples_category
ON assistant_examples(category, sort_order);

-- --- 16.13 历史记录（细粒度审计） ---
CREATE TABLE IF NOT EXISTS assistant_history (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    history_id             TEXT NOT NULL UNIQUE,
    session_id             TEXT,
    user_id                INTEGER,
    message_id             TEXT,
    plan_id                TEXT,
    task_id                TEXT,
    type                   TEXT NOT NULL DEFAULT 'chat'
                           CHECK(type IN ('chat','intent','plan','execute','drawing','report')),
    status                 TEXT,
    input_json             TEXT,
    ai_reply_json          TEXT,
    intent_json            TEXT,
    plan_json              TEXT,
    tool_calls_json        TEXT,
    adapter_requests_json  TEXT,
    midas_responses_json   TEXT,
    output_files_json      TEXT,
    errors_json            TEXT,
    log_json               TEXT,
    duration_ms            INTEGER,
    created_at             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES assistant_sessions(session_id) ON DELETE SET NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY(message_id) REFERENCES assistant_messages(message_id) ON DELETE SET NULL,
    FOREIGN KEY(plan_id) REFERENCES assistant_plans(plan_id) ON DELETE SET NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_assistant_history_session
ON assistant_history(session_id, created_at);

CREATE INDEX IF NOT EXISTS ix_assistant_history_user
ON assistant_history(user_id);

CREATE INDEX IF NOT EXISTS ix_assistant_history_task
ON assistant_history(task_id);

-- --- 16.14 常用工程指令 ---
CREATE TABLE IF NOT EXISTS assistant_commands (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    command_code      TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    category          TEXT,
    prompt_template   TEXT NOT NULL,
    param_schema_json TEXT,
    sort_order        INTEGER NOT NULL DEFAULT 0,
    enabled           INTEGER NOT NULL DEFAULT 1,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_assistant_commands_category
ON assistant_commands(category, sort_order);

-- =========================================================
-- 17. 规范知识库（V2.1 新增：N-19）
-- =========================================================

CREATE TABLE IF NOT EXISTS code_standards (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT NOT NULL UNIQUE,          -- 例如 'GB50017'
    name       TEXT NOT NULL,
    full_name  TEXT,
    version    TEXT,
    category   TEXT NOT NULL DEFAULT 'national'
               CHECK(category IN ('national','industry','local','enterprise','international')),
    country    TEXT NOT NULL DEFAULT 'CN',
    enabled    INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_code_standards_category
ON code_standards(category);

CREATE TABLE IF NOT EXISTS code_clauses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_id INTEGER NOT NULL,
    clause_no   TEXT NOT NULL,
    title       TEXT,
    content     TEXT NOT NULL,
    category    TEXT,
    tags_json   TEXT,
    severity    TEXT NOT NULL DEFAULT 'info'
                CHECK(severity IN ('info','warning','error')),
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(standard_id) REFERENCES code_standards(id) ON DELETE CASCADE,
    UNIQUE(standard_id, clause_no)
);

CREATE INDEX IF NOT EXISTS ix_code_clauses_standard_clause
ON code_clauses(standard_id, clause_no);

-- =========================================================
-- 18. 地区荷载规范参数库（V2.1 新增：N-20）
-- =========================================================

CREATE TABLE IF NOT EXISTS load_parameter_library (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_code  TEXT NOT NULL,
    region_code    TEXT NOT NULL,
    region_name    TEXT,
    parameter_type TEXT NOT NULL
                   CHECK(parameter_type IN (
                       'wind','snow','seismic','temperature','live','dead','crane'
                   )),
    values_json    TEXT NOT NULL,
    source         TEXT,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(standard_code, region_code, parameter_type)
);

CREATE INDEX IF NOT EXISTS ix_load_parameter_library_type_region
ON load_parameter_library(parameter_type, region_code);

-- =========================================================
-- 19. 初始化种子数据
-- =========================================================

-- 19.1 权限码（封闭集合，逐字来自总纲 §4.8.2）
INSERT OR IGNORE INTO permissions(code,name,module,action)
VALUES
('system:read','查看系统设置','system','read'),
('system:write','修改系统设置','system','write'),
('system:audit','查看审计日志','system','audit'),
('model:read','查看模型','model','read'),
('model:create','创建模型','model','create'),
('model:update','修改模型','model','update'),
('model:delete','删除模型','model','delete'),
('model:test','测试模型','model','test'),
('user:read','查看用户','user','read'),
('user:create','创建用户','user','create'),
('user:update','修改用户','user','update'),
('user:delete','删除用户','user','delete'),
('role:read','查看角色','role','read'),
('role:write','修改角色权限','role','write'),
('task:read','查看任务','task','read'),
('task:cancel','取消任务','task','cancel'),
('task:retry','重试任务','task','retry'),
('tool:read','查看工具','tool','read'),
('tool:execute','执行工具','tool','execute'),
('data:read','查看数据','data','read'),
('data:backup','备份数据','data','backup'),
('data:restore','恢复数据','data','restore'),
('data:export','导出数据','data','export'),
('data:import','导入数据','data','import'),
('data:cleanup','清理数据','data','cleanup'),
('assistant:read','查看 AI 助手','assistant','read'),
('assistant:chat','与 AI 助手对话','assistant','chat'),
('assistant:plan','生成执行计划','assistant','plan'),
('assistant:confirm','确认高风险计划','assistant','confirm'),
('assistant:execute','执行计划','assistant','execute'),
('assistant:drawing','智能识图','assistant','drawing'),
('assistant:modeling','智能建模','assistant','modeling'),
('assistant:optimize','结构优化','assistant','optimize'),
('assistant:report','生成报告','assistant','report');

-- 19.2 默认角色
INSERT OR IGNORE INTO roles(name,code,description,is_system)
VALUES
('超级管理员','super_admin','拥有系统全部权限',1),
('工程师','engineer','可访问 MIDAS、模型和任务功能',1),
('分析师','analyst','可访问模型分析与结果',1),
('访客','visitor','只读权限',1);

-- 19.3 角色 → 权限映射（实现总纲 §4.8.3，全部幂等）
-- super_admin = 全部
INSERT OR IGNORE INTO role_permissions(role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'super_admin';

-- engineer = model:* + tool:* + task:* + assistant:* + system:read + data:read
INSERT OR IGNORE INTO role_permissions(role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'engineer'
  AND (   p.code LIKE 'model:%'
       OR p.code LIKE 'tool:%'
       OR p.code LIKE 'task:%'
       OR p.code LIKE 'assistant:%'
       OR p.code IN ('system:read','data:read'));

-- analyst = model:read + tool:read + task:read + assistant:read + assistant:chat + data:read
INSERT OR IGNORE INTO role_permissions(role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'analyst'
  AND p.code IN (
      'model:read','tool:read','task:read',
      'assistant:read','assistant:chat','data:read'
  );

-- visitor = model:read + tool:read + task:read + data:read
INSERT OR IGNORE INTO role_permissions(role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'visitor'
  AND p.code IN ('model:read','tool:read','task:read','data:read');

-- 19.4 单例配置表初始化
INSERT OR IGNORE INTO security_configs(id) VALUES (1);
INSERT OR IGNORE INTO service_configs(id) VALUES (1);
INSERT OR IGNORE INTO backup_configs(id) VALUES (1);
INSERT OR IGNORE INTO cleanup_configs(id) VALUES (1);
INSERT OR IGNORE INTO assistant_drawing_settings(id) VALUES (1);

-- 19.5 常用工程指令
INSERT OR IGNORE INTO assistant_commands
    (command_code,name,category,prompt_template,param_schema_json,sort_order,enabled)
VALUES
('create_model','快速建模','modeling',
 '按以下参数建立一个 {{structure_type}} 结构模型：{{parameters}}',
 '{"type":"object","additionalProperties":false,"properties":{"structure_type":{"type":"string"},"parameters":{"type":"object"}},"required":["structure_type","parameters"]}',
 10,1),
('check_model','模型检查','checking',
 '对当前模型执行完整性与规范检查，列出问题清单与依据条文。',
 '{"type":"object","additionalProperties":false,"properties":{"standard_codes":{"type":"array","items":{"type":"string"}}},"required":[]}',
 20,1),
('run_analysis','执行分析','analysis',
 '对当前模型执行 {{analysis_type}} 分析并给出结果摘要。',
 '{"type":"object","additionalProperties":false,"properties":{"analysis_type":{"type":"string","enum":["static","modal","buckling","response_spectrum"]}},"required":["analysis_type"]}',
 30,1);

-- 19.6 工程模板
INSERT OR IGNORE INTO assistant_templates
    (template_code,name,category,discipline,description,param_schema_json,plan_template_json,is_system,sort_order,enabled)
VALUES
('steel_portal_frame','钢框架','structure','steel',
 '多层钢框架快速建模模板',
 '{"type":"object","additionalProperties":false,"properties":{"span_x":{"type":"number"},"span_y":{"type":"number"},"bays_x":{"type":"integer"},"bays_y":{"type":"integer"},"stories":{"type":"integer"},"story_height":{"type":"number"}}}',
 '{"steps":[{"step_no":1,"name":"创建轴网","tool_name":"midas_model","action":"create","resource":"node"},{"step_no":2,"name":"创建单元","tool_name":"midas_model","action":"create","resource":"element"}]}',
 1,10,1),
('concrete_frame','混凝土框架','structure','concrete',
 '现浇混凝土框架快速建模模板',
 '{"type":"object","additionalProperties":false,"properties":{"bays_x":{"type":"integer"},"bays_y":{"type":"integer"},"stories":{"type":"integer"},"story_height":{"type":"number"},"concrete_grade":{"type":"string"}}}',
 '{"steps":[{"step_no":1,"name":"创建轴网","tool_name":"midas_model","action":"create","resource":"node"},{"step_no":2,"name":"创建梁柱单元","tool_name":"midas_model","action":"create","resource":"element"}]}',
 1,20,1),
('bridge','桥梁','structure','bridge',
 '常规梁桥快速建模模板',
 '{"type":"object","additionalProperties":false,"properties":{"span_length":{"type":"number"},"spans":{"type":"integer"},"deck_width":{"type":"number"}}}',
 '{"steps":[{"step_no":1,"name":"创建桥面轴网","tool_name":"midas_model","action":"create","resource":"node"},{"step_no":2,"name":"创建主梁","tool_name":"midas_model","action":"create","resource":"element"}]}',
 1,30,1),
('foundation','基础','structure','geotechnical',
 '独立基础与筏板基础建模模板',
 '{"type":"object","additionalProperties":false,"properties":{"foundation_type":{"type":"string","enum":["isolated","raft","pile"]},"plan_size_x":{"type":"number"},"plan_size_y":{"type":"number"}}}',
 '{"steps":[{"step_no":1,"name":"创建基础节点","tool_name":"midas_model","action":"create","resource":"node"},{"step_no":2,"name":"创建边界条件","tool_name":"midas_model","action":"create","resource":"boundary"}]}',
 1,40,1);

-- 19.7 示例案例
INSERT OR IGNORE INTO assistant_examples
    (example_code,name,category,description,template_id,steps_json,run_config_json,is_system,sort_order,enabled)
VALUES
('ex_steel_frame_3story','三层钢框架算例','structure',
 '三层三跨钢框架，恒载+活载+风荷载，静力分析并输出计算书',
 (SELECT id FROM assistant_templates WHERE template_code='steel_portal_frame'),
 '{"steps":[{"step_no":1,"tool_name":"midas_model","action":"create","resource":"node"},{"step_no":2,"tool_name":"midas_model","action":"create","resource":"element"},{"step_no":3,"tool_name":"midas_execute","action":"analysis","resource":"model"}]}',
 '{"analysis_type":"static","generate_report":true}',
 1,10,1),
('ex_concrete_frame_2story','两层混凝土框架算例','structure',
 '两层两跨混凝土框架，静力分析与配筋结果输出',
 (SELECT id FROM assistant_templates WHERE template_code='concrete_frame'),
 '{"steps":[{"step_no":1,"tool_name":"midas_model","action":"create","resource":"node"},{"step_no":2,"tool_name":"midas_model","action":"create","resource":"element"},{"step_no":3,"tool_name":"midas_execute","action":"analysis","resource":"model"}]}',
 '{"analysis_type":"static","generate_report":true}',
 1,20,1);

-- 19.8 规范知识库种子
INSERT OR IGNORE INTO code_standards(code,name,full_name,version,category,country,enabled)
VALUES
('GB50017','钢结构设计标准','钢结构设计标准','2017','national','CN',1),
('GB50009','建筑结构荷载规范','建筑结构荷载规范','2012','national','CN',1),
('GB50011','建筑抗震设计规范','建筑抗震设计规范','2010','national','CN',1),
('GB50007','建筑地基基础设计规范','建筑地基基础设计规范','2011','national','CN',1);

COMMIT;
```

> **建表顺序说明：** 上文 `reports`（§4-15）的 `file_id` 引用 `assistant_files`（§4-16.1），
> `assistant_files` 又引用 `assistant_sessions`（§4-16.2），均属**前向引用**。
> SQLite 在 `PRAGMA foreign_keys = ON` 下允许前向引用，只要**执行期**被引用表已存在即可；
> 若使用 Alembic 迁移，请按 §4 的依赖顺序（`assistant_sessions` → `assistant_files` → 其余）
> 重排为无前向引用的建表序列。

---

# 5. 数据库关键关系

## 5.1 总览

```text
users
 ├── user_roles ── roles ── role_permissions ── permissions
 │
 ├── sessions
 ├── tasks ── task_events
 ├── audit_logs
 ├── system_logs
 ├── backups / data_exports / data_imports
 ├── projects ── reports
 └── assistant_sessions / assistant_history

mcp_clients
 └── mcp_client_credentials

midas_clients
 └── adapter_code ── adapters
                        │
                        ├── capabilities ── capability_interfaces ── tool_interfaces
                        │                                                  │
                        │                                                  └── tools
                        └── midas_clients

model_providers
 └── models
       ├── tasks
       └── assistant_sessions

schemas ── (schema_code, version) 被 tool_interfaces.request_schema_json 引用
```

## 5.2 AI 工程助手簇

```text
assistant_sessions
 ├── assistant_messages ── assistant_intents ── assistant_plans
 │                                                  ├── assistant_plan_steps
 │                                                  └── task_id ── tasks
 ├── assistant_files
 ├── assistant_outputs
 ├── assistant_drawing_tasks ── assistant_drawing_objects
 ├── assistant_history
 └── assistant_plans ── reports

assistant_drawing_settings   （单例，独立）
assistant_templates ── assistant_examples
assistant_commands           （独立，指令字典）
```

## 5.3 项目与报告

```text
projects
 ├── assistant_sessions.project_id
 └── reports.project_id

tasks
 └── reports.task_id

models
 └── reports.model_id

assistant_files
 └── reports.file_id
```

## 5.4 规范知识库与荷载参数库

```text
code_standards
 └── code_clauses            （(standard_id, clause_no) 唯一）

load_parameter_library       （(standard_code, region_code, parameter_type) 唯一）
```

> `load_parameter_library.standard_code` 存的是 `code_standards.code` 的**字符串值**，
> 不设外键，以便在规范库尚未录入时先行导入地区参数。

## 5.5 追溯链（总纲 §4.1.5）

```text
request_id  →  task_id  →  adapter_request_id
```

| 环节 | 落库位置 |
|---|---|
| `request_id` | `tasks.request_id`、`system_logs.request_id`、`audit_logs.request_id` |
| `task_id` | `tasks.task_id`、`task_events.task_id`、`system_logs.task_id`、`assistant_plans.task_id`、`assistant_plan_steps.task_id`、`assistant_outputs.task_id`、`assistant_history.task_id`、`reports.task_id` |
| `adapter_request_id` | `system_logs.adapter_request_id` |

---

# 6. MCP Tool JSON Schema 总规范

## 6.1 强制规则

以下 4 个 Tool 是 V2.1 对 LLM 暴露的稳定接口。所有 Tool 都必须：

- `additionalProperties: false`（**强制**）
- 明确 `required`
- 对 `action` / `resource` 使用 `enum`
- 不允许 LLM 直接传 URL
- 不允许 LLM 传 API Key
- 不允许 LLM 指定任意数据库 SQL
- 不允许 LLM 绕过 Capability Registry
- 长任务返回 `task_id`

## 6.2 additionalProperties 的适用范围（裁决 B-4）

> **`additionalProperties: false` 必须在每一个 Tool Schema 的每一层出现**，
> 包括顶层对象、`options`、以及 `oneOf` 分支内的每一个子 Schema。

**唯一的例外通道：** 嵌套的自由形态对象（free-form object）**仅允许**出现在
「由 Capability 的 `request_schema_json` 执行二次校验」的位置：

| Tool | 自由形态字段 | 二次校验责任方 |
|---|---|---|
| `midas_query` | 无（全部 `oneOf` 分资源收紧） | — |
| `midas_model` | 无（全部 `oneOf` 分资源收紧） | — |
| `midas_execute` | `data`（保留开放） | 解析出的 Capability 的 `request_schema_json` |
| `midas_task` | 无 | — |

```text
midas_execute.data
      ↓
CapabilityResolver.resolve(adapter, tool, action, resource)
      ↓
capability.request_schema_json
      ↓
二次校验失败 → VALIDATION_ERROR（总纲 §4.4.2）
```

**禁止**在任何 Tool 中把「未定义的自由对象」直接透传给 Adapter。

## 6.3 动作与资源词表

**MCP action 词表（动词，总纲 §4.6）：**

```text
get / list / search / count / inspect      （查询类，midas_query）
create / read / update / delete / upsert / validate   （模型类，midas_model）
connect / disconnect / open_project / save_project / close_project
import / export / calculate / analysis / generate_report
validate_model / sync / command            （执行类，midas_execute）
cancel / retry / result / events / logs    （任务类，midas_task）
```

**MCP resource 词表（单数，总纲 §4.6.1）：**

```text
server / client / capabilities / model / node / element / material / section
load / boundary / group / analysis / result / project
coordinate_system / property / report / file / command
```

> **裁决 C-7：** `capabilities` **只作为 `target` 取值**保留，
> `action=capabilities` 从 `midas_query.action` 枚举中**移除**。
> 查询能力清单统一写作 `{"target":"capabilities","action":"list"}`。

## 6.4 版本标记

每个 Tool Schema 的 `$id` 使用：

```text
structai://mcp/v2.1/tools/<tool_name>
```

`tools.version` 落库值为 `"2.1"`。

---

# 7. Tool ① midas_query

## 7.1 用途

查询：

- MIDAS 软件状态
- 当前连接
- 软件能力
- 模型对象
- 节点 / 单元 / 材料 / 截面
- 荷载 / 边界 / 组
- 计算结果
- 项目

## 7.2 JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "structai://mcp/v2.1/tools/midas_query",
  "title": "StructAI MIDAS Query",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "target",
    "action"
  ],
  "properties": {
    "target": {
      "type": "string",
      "enum": [
        "server",
        "client",
        "capabilities",
        "model",
        "node",
        "element",
        "material",
        "section",
        "load",
        "boundary",
        "group",
        "analysis",
        "result",
        "project"
      ]
    },
    "action": {
      "type": "string",
      "enum": [
        "get",
        "list",
        "search",
        "count",
        "inspect"
      ]
    },
    "id": {
      "type": ["string", "integer", "null"]
    },
    "query": {
      "type": ["object", "null"],
      "oneOf": [
        {
          "title": "server filter",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "name": { "type": "string" },
            "status": {
              "type": "string",
              "enum": ["stopped", "starting", "running", "stopping", "error"]
            },
            "transport": { "type": "string" }
          }
        },
        {
          "title": "client filter",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "software": { "type": "string" },
            "version": { "type": "string" },
            "adapter": { "type": "string" },
            "status": {
              "type": "string",
              "enum": ["disconnected", "connecting", "connected", "error"]
            },
            "enabled": { "type": "boolean" }
          }
        },
        {
          "title": "capabilities filter",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "adapter": { "type": "string" },
            "resource": { "type": "string" },
            "action": { "type": "string" },
            "enabled": { "type": "boolean" },
            "software": { "type": "string" },
            "version": { "type": "string" }
          }
        },
        {
          "title": "model filter",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "name": { "type": "string" },
            "path": { "type": "string" },
            "unit_system": { "type": "string" },
            "include_summary": { "type": "boolean", "default": true }
          }
        },
        {
          "title": "node filter",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "ids": { "type": "array", "items": { "type": ["string", "integer"] } },
            "group": { "type": "string" },
            "x_min": { "type": "number" },
            "x_max": { "type": "number" },
            "y_min": { "type": "number" },
            "y_max": { "type": "number" },
            "z_min": { "type": "number" },
            "z_max": { "type": "number" },
            "name_like": { "type": "string" }
          }
        },
        {
          "title": "element filter",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "ids": { "type": "array", "items": { "type": ["string", "integer"] } },
            "group": { "type": "string" },
            "element_type": {
              "type": "string",
              "enum": ["beam", "truss", "cable", "plate", "solid", "wall", "other"]
            },
            "material": { "type": "string" },
            "section": { "type": "string" },
            "node_id": { "type": ["string", "integer"] }
          }
        },
        {
          "title": "material filter",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "ids": { "type": "array", "items": { "type": ["string", "integer"] } },
            "name": { "type": "string" },
            "grade": { "type": "string" },
            "material_type": {
              "type": "string",
              "enum": ["steel", "concrete", "composite", "timber", "other"]
            }
          }
        },
        {
          "title": "section filter",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "ids": { "type": "array", "items": { "type": ["string", "integer"] } },
            "name": { "type": "string" },
            "shape": {
              "type": "string",
              "enum": ["H", "BOX", "PIPE", "T", "L", "C", "RECT", "CIRCLE", "other"]
            },
            "material": { "type": "string" }
          }
        },
        {
          "title": "load filter",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "load_case": { "type": "string" },
            "load_type": {
              "type": "string",
              "enum": ["static", "wind", "snow", "seismic", "temperature", "moving", "other"]
            },
            "group": { "type": "string" },
            "node_id": { "type": ["string", "integer"] },
            "element_id": { "type": ["string", "integer"] }
          }
        },
        {
          "title": "boundary filter",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "group": { "type": "string" },
            "boundary_type": {
              "type": "string",
              "enum": ["support", "spring", "constraint", "release", "other"]
            },
            "node_id": { "type": ["string", "integer"] }
          }
        },
        {
          "title": "group filter",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "name": { "type": "string" },
            "group_type": {
              "type": "string",
              "enum": ["node", "element", "load", "boundary", "mixed", "other"]
            },
            "parent": { "type": "string" }
          }
        },
        {
          "title": "analysis filter",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "analysis_type": {
              "type": "string",
              "enum": ["static", "modal", "buckling", "response_spectrum", "time_history", "other"]
            },
            "load_case": { "type": "string" },
            "load_combination": { "type": "string" },
            "include_cases": { "type": "boolean", "default": true }
          }
        },
        {
          "title": "result filter",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "result_type": {
              "type": "string",
              "enum": ["displacement", "reaction", "force", "stress", "mode", "story_drift", "other"]
            },
            "load_combination": { "type": "string" },
            "load_case": { "type": "string" },
            "node_ids": { "type": "array", "items": { "type": ["string", "integer"] } },
            "element_ids": { "type": "array", "items": { "type": ["string", "integer"] } },
            "component": { "type": "string" },
            "envelope": { "type": "boolean", "default": false },
            "top_n": { "type": "integer", "minimum": 1, "maximum": 500 }
          }
        },
        {
          "title": "project filter",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "name": { "type": "string" },
            "code": { "type": "string" },
            "status": { "type": "string", "enum": ["active", "archived"] },
            "owner_id": { "type": "integer" }
          }
        }
      ]
    },
    "fields": {
      "type": ["array", "null"],
      "items": {
        "type": "string"
      }
    },
    "page": {
      "type": "integer",
      "minimum": 1,
      "default": 1
    },
    "page_size": {
      "type": "integer",
      "minimum": 1,
      "maximum": 500,
      "default": 100
    },
    "client_id": {
      "type": ["integer", "null"]
    },
    "adapter": {
      "type": ["string", "null"]
    },
    "include_metadata": {
      "type": "boolean",
      "default": false
    }
  }
}
```

> **收紧说明（裁决 B-4）：** V2.0 的 `query` 是 `additionalProperties: true` 的自由对象，
> 使 `additionalProperties: false` 的顶层约束形同虚设。
> V2.1 改为按 `target` 分资源的 `oneOf`，**每个分支均为 `additionalProperties: false`**。
> 调用方必须保证 `query` 的形状与 `target` 匹配，否则返回 `VALIDATION_ERROR`。

## 7.3 示例

```json
{
  "target": "node",
  "action": "list",
  "query": {
    "group": "W2",
    "z_min": 0,
    "z_max": 20
  },
  "page": 1,
  "page_size": 100
}
```

```json
{
  "target": "node",
  "action": "count",
  "query": { "group": "W2" }
}
```

```json
{
  "target": "capabilities",
  "action": "list",
  "adapter": "midas_gen"
}
```

## 7.4 进度获取（裁决 B-9）

> **MCP 没有 push / subscribe 语义。** 本 Tool 与整个 MCP 层**不提供订阅能力**。
> 长任务的进度与事件**只能通过轮询**获得：
>
> ```text
> midas_task  action=events   （带 since 游标，见 §10）
> midas_task  action=get      （取 status / progress 快照）
> ```
>
> 真正的服务端实时推送（SSE）由 **v1.2 的 REST/SSE 层**提供，本文件不定义其路径与事件载荷。

---

# 8. Tool ② midas_model

## 8.1 用途

对 MIDAS 模型进行统一 CRUD 和校验。

支持：

```text
node
element
material
section
load
boundary
group
coordinate_system
property
```

## 8.2 JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "structai://mcp/v2.1/tools/midas_model",
  "title": "StructAI MIDAS Model",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "action",
    "resource"
  ],
  "properties": {
    "action": {
      "type": "string",
      "enum": [
        "create",
        "read",
        "update",
        "delete",
        "upsert",
        "validate"
      ]
    },
    "resource": {
      "type": "string",
      "enum": [
        "node",
        "element",
        "material",
        "section",
        "load",
        "boundary",
        "group",
        "coordinate_system",
        "property"
      ]
    },
    "id": {
      "type": ["string", "integer", "null"]
    },
    "ids": {
      "type": ["array", "null"],
      "items": {
        "type": ["string", "integer"]
      }
    },
    "data": {
      "type": ["object", "array", "null"],
      "oneOf": [
        {
          "title": "node object",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "id": { "type": ["string", "integer"] },
            "name": { "type": "string" },
            "x": { "type": "number" },
            "y": { "type": "number" },
            "z": { "type": "number" },
            "group": { "type": "string" }
          },
          "required": ["x", "y", "z"]
        },
        {
          "title": "node array",
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "id": { "type": ["string", "integer"] },
              "name": { "type": "string" },
              "x": { "type": "number" },
              "y": { "type": "number" },
              "z": { "type": "number" },
              "group": { "type": "string" }
            },
            "required": ["x", "y", "z"]
          }
        },
        {
          "title": "element object",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "id": { "type": ["string", "integer"] },
            "name": { "type": "string" },
            "type": {
              "type": "string",
              "enum": ["beam", "truss", "cable", "plate", "solid", "wall", "other"]
            },
            "nodes": {
              "oneOf": [
                { "type": "integer" },
                { "type": "array", "items": { "type": "integer" }, "minItems": 2 }
              ]
            },
            "material": { "type": "string" },
            "section": { "type": "string" },
            "group": { "type": "string" }
          },
          "required": ["type", "nodes"]
        },
        {
          "title": "element array",
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "id": { "type": ["string", "integer"] },
              "name": { "type": "string" },
              "type": {
                "type": "string",
                "enum": ["beam", "truss", "cable", "plate", "solid", "wall", "other"]
              },
              "nodes": {
                "oneOf": [
                  { "type": "integer" },
                  { "type": "array", "items": { "type": "integer" }, "minItems": 2 }
                ]
              },
              "material": { "type": "string" },
              "section": { "type": "string" },
              "group": { "type": "string" }
            },
            "required": ["type", "nodes"]
          }
        },
        {
          "title": "material object",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "id": { "type": ["string", "integer"] },
            "name": { "type": "string" },
            "material_type": {
              "type": "string",
              "enum": ["steel", "concrete", "composite", "timber", "other"]
            },
            "grade": { "type": "string" },
            "elastic_modulus": { "type": "number" },
            "poisson_ratio": { "type": "number" },
            "density": { "type": "number" },
            "standard_code": { "type": "string" }
          },
          "required": ["material_type"]
        },
        {
          "title": "material array",
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "id": { "type": ["string", "integer"] },
              "name": { "type": "string" },
              "material_type": {
                "type": "string",
                "enum": ["steel", "concrete", "composite", "timber", "other"]
              },
              "grade": { "type": "string" },
              "elastic_modulus": { "type": "number" },
              "poisson_ratio": { "type": "number" },
              "density": { "type": "number" },
              "standard_code": { "type": "string" }
            },
            "required": ["material_type"]
          }
        },
        {
          "title": "section object",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "id": { "type": ["string", "integer"] },
            "name": { "type": "string" },
            "shape": {
              "type": "string",
              "enum": ["H", "BOX", "PIPE", "T", "L", "C", "RECT", "CIRCLE", "other"]
            },
            "material": { "type": "string" },
            "height": { "type": "number" },
            "width": { "type": "number" },
            "web_thickness": { "type": "number" },
            "flange_thickness": { "type": "number" },
            "diameter": { "type": "number" }
          },
          "required": ["shape"]
        },
        {
          "title": "section array",
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "id": { "type": ["string", "integer"] },
              "name": { "type": "string" },
              "shape": {
                "type": "string",
                "enum": ["H", "BOX", "PIPE", "T", "L", "C", "RECT", "CIRCLE", "other"]
              },
              "material": { "type": "string" },
              "height": { "type": "number" },
              "width": { "type": "number" },
              "web_thickness": { "type": "number" },
              "flange_thickness": { "type": "number" },
              "diameter": { "type": "number" }
            },
            "required": ["shape"]
          }
        },
        {
          "title": "load object",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "id": { "type": ["string", "integer"] },
            "name": { "type": "string" },
            "load_case": { "type": "string" },
            "load_type": {
              "type": "string",
              "enum": ["static", "wind", "snow", "seismic", "temperature", "moving", "other"]
            },
            "target_type": { "type": "string", "enum": ["node", "element"] },
            "target_id": { "type": ["string", "integer"] },
            "direction": { "type": "string" },
            "magnitude": { "type": "number" },
            "unit": { "type": "string" },
            "group": { "type": "string" }
          },
          "required": ["load_case", "load_type"]
        },
        {
          "title": "load array",
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "id": { "type": ["string", "integer"] },
              "name": { "type": "string" },
              "load_case": { "type": "string" },
              "load_type": {
                "type": "string",
                "enum": ["static", "wind", "snow", "seismic", "temperature", "moving", "other"]
              },
              "target_type": { "type": "string", "enum": ["node", "element"] },
              "target_id": { "type": ["string", "integer"] },
              "direction": { "type": "string" },
              "magnitude": { "type": "number" },
              "unit": { "type": "string" },
              "group": { "type": "string" }
            },
            "required": ["load_case", "load_type"]
          }
        },
        {
          "title": "boundary object",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "id": { "type": ["string", "integer"] },
            "name": { "type": "string" },
            "boundary_type": {
              "type": "string",
              "enum": ["support", "spring", "constraint", "release", "other"]
            },
            "node_id": { "type": ["string", "integer"] },
            "dof": { "type": "array", "items": { "type": "string" } },
            "stiffness": { "type": "number" },
            "group": { "type": "string" }
          },
          "required": ["boundary_type", "node_id"]
        },
        {
          "title": "boundary array",
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "id": { "type": ["string", "integer"] },
              "name": { "type": "string" },
              "boundary_type": {
                "type": "string",
                "enum": ["support", "spring", "constraint", "release", "other"]
              },
              "node_id": { "type": ["string", "integer"] },
              "dof": { "type": "array", "items": { "type": "string" } },
              "stiffness": { "type": "number" },
              "group": { "type": "string" }
            },
            "required": ["boundary_type", "node_id"]
          }
        },
        {
          "title": "group object",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "id": { "type": ["string", "integer"] },
            "name": { "type": "string" },
            "group_type": {
              "type": "string",
              "enum": ["node", "element", "load", "boundary", "mixed", "other"]
            },
            "parent": { "type": "string" },
            "members": { "type": "array", "items": { "type": ["string", "integer"] } }
          },
          "required": ["name", "group_type"]
        },
        {
          "title": "group array",
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "id": { "type": ["string", "integer"] },
              "name": { "type": "string" },
              "group_type": {
                "type": "string",
                "enum": ["node", "element", "load", "boundary", "mixed", "other"]
              },
              "parent": { "type": "string" },
              "members": { "type": "array", "items": { "type": ["string", "integer"] } }
            },
            "required": ["name", "group_type"]
          }
        },
        {
          "title": "coordinate_system object",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "id": { "type": ["string", "integer"] },
            "name": { "type": "string" },
            "origin": { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3 },
            "rotation": { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3 },
            "cs_type": { "type": "string", "enum": ["cartesian", "cylindrical", "spherical"] }
          },
          "required": ["cs_type"]
        },
        {
          "title": "coordinate_system array",
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "id": { "type": ["string", "integer"] },
              "name": { "type": "string" },
              "origin": { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3 },
              "rotation": { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3 },
              "cs_type": { "type": "string", "enum": ["cartesian", "cylindrical", "spherical"] }
            },
            "required": ["cs_type"]
          }
        },
        {
          "title": "property object",
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "id": { "type": ["string", "integer"] },
            "name": { "type": "string" },
            "property_type": {
              "type": "string",
              "enum": ["thickness", "rigid_link", "elastic_link", "mass", "other"]
            },
            "target_type": { "type": "string", "enum": ["node", "element"] },
            "target_id": { "type": ["string", "integer"] },
            "value": { "type": "number" },
            "unit": { "type": "string" }
          },
          "required": ["property_type"]
        },
        {
          "title": "property array",
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "id": { "type": ["string", "integer"] },
              "name": { "type": "string" },
              "property_type": {
                "type": "string",
                "enum": ["thickness", "rigid_link", "elastic_link", "mass", "other"]
              },
              "target_type": { "type": "string", "enum": ["node", "element"] },
              "target_id": { "type": ["string", "integer"] },
              "value": { "type": "number" },
              "unit": { "type": "string" }
            },
            "required": ["property_type"]
          }
        }
      ]
    },
    "options": {
      "type": ["object", "null"],
      "properties": {
        "validate_before_write": {
          "type": "boolean",
          "default": true
        },
        "validate_after_write": {
          "type": "boolean",
          "default": true
        },
        "transactional": {
          "type": "boolean",
          "default": true
        },
        "dry_run": {
          "type": "boolean",
          "default": false
        }
      },
      "additionalProperties": false
    },
    "client_id": {
      "type": ["integer", "null"]
    },
    "adapter": {
      "type": ["string", "null"]
    }
  }
}
```

> **收紧说明（裁决 B-4）：** V2.0 的 `data` 是无约束的 `["object","array","null"]`。
> V2.1 改为**按 `resource` 的 `oneOf`**：每个资源给出「单对象形式」与「数组形式」两支，
> 两支均 `additionalProperties: false`。调用方必须使 `data` 的形状与 `resource` 一致。
>
> **单位约定（总纲 §4.5.2）：** 坐标 `x/y/z` 单位 m；截面尺寸 `height/width/*_thickness/diameter` 单位 mm；
> 集中力 `magnitude` 单位 kN；线荷载 kN/m；面荷载 kN/m²；弹性模量 MPa；密度 kg/m³。

## 8.3 示例

### 创建节点

```json
{
  "action": "create",
  "resource": "node",
  "data": {
    "name": "N1001",
    "x": 0,
    "y": 0,
    "z": 3.6
  },
  "options": {
    "validate_before_write": true,
    "transactional": true
  }
}
```

> 该示例在新 Schema 下仍然合法：`data` 命中 `oneOf` 的 `node object` 分支
> （`additionalProperties: false` 允许 `name`/`x`/`y`/`z`），`options` 亦合法。

### 批量创建单元

```json
{
  "action": "create",
  "resource": "element",
  "data": [
    {
      "id": 1,
      "type": "beam",
      "nodes": [1001, 1002],
      "section": "H400x200x8x12",
      "material": "Q355"
    },
    {
      "id": 2,
      "type": "beam",
      "nodes": [1002, 1003],
      "section": "H400x200x8x12",
      "material": "Q355"
    }
  ]
}
```

> 该示例命中 `oneOf` 的 `element array` 分支。注意 `oneOf` 要求**恰好匹配一支**：
> 由于 `element object` 分支的 `type` 是 `"object"`，数组不会误命中该分支。

---

# 9. Tool ③ midas_execute

## 9.1 用途

执行需要 Adapter 映射的明确软件动作。

例如：

```text
import
export
save
calculate
analysis
generate_report
command
sync
```

## 9.2 JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "structai://mcp/v2.1/tools/midas_execute",
  "title": "StructAI MIDAS Execute",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "action"
  ],
  "properties": {
    "action": {
      "type": "string",
      "enum": [
        "connect",
        "disconnect",
        "open_project",
        "save_project",
        "close_project",
        "import",
        "export",
        "calculate",
        "analysis",
        "generate_report",
        "validate_model",
        "sync",
        "command"
      ]
    },
    "resource": {
      "type": ["string", "null"],
      "enum": [
        "project",
        "model",
        "load",
        "result",
        "report",
        "file",
        "command",
        null
      ]
    },
    "data": {
      "type": ["object", "null"],
      "additionalProperties": true
    },
    "options": {
      "type": ["object", "null"],
      "properties": {
        "async": {
          "type": "boolean",
          "default": true
        },
        "wait": {
          "type": "boolean",
          "default": false
        },
        "timeout_seconds": {
          "type": "integer",
          "minimum": 1,
          "maximum": 86400,
          "default": 300
        },
        "dry_run": {
          "type": "boolean",
          "default": false
        },
        "force": {
          "type": "boolean",
          "default": false
        }
      },
      "additionalProperties": false
    },
    "client_id": {
      "type": ["integer", "null"]
    },
    "adapter": {
      "type": ["string", "null"]
    }
  }
}
```

## 9.3 data 的二次校验（裁决 B-4，强制）

> **`midas_execute.data` 是本文件唯一保留开放形态的字段，但绝不是「免校验通道」。**
>
> 所有 `data` 载荷在到达 Adapter **之前**，必须按以下链路重新校验一次：
>
> ```text
> midas_execute(action, resource, data)
>       ↓
> CapabilityResolver.resolve(adapter_code, tool="midas_execute", action, resource)
>       ↓
> capability.request_schema_json        ← tool_interfaces.request_schema_json 的归集视图
>       ↓
> 二次校验（JSON Schema Draft 2020-12）
>       ↓
> 通过 → Adapter.execute(ExecuteRequest) ／ 失败 → VALIDATION_ERROR
> ```
>
> 规则：
>
> 1. `data` 的字段集**必须**由被解析出的 Capability 的 `request_schema_json` 定义；
> 2. 校验失败**一律**返回 `VALIDATION_ERROR`（总纲 §4.4.2），不得降级为 `MIDAS_API_ERROR`；
> 3. 若解析不到 Capability，返回 `CAPABILITY_NOT_SUPPORTED`（总纲 §4.4.4），
>    **不得**把 `data` 原样透传给 MIDAS；
> 4. Adapter 内部**必须**再次执行本地校验（防御性），不得假定上游已校验。
>
> 换言之：`additionalProperties: true` 在 MCP Tool 层是**过渡形态**，
> 真实的字段约束登记在 `tool_interfaces.request_schema_json` 中。

## 9.4 计算示例

```json
{
  "action": "calculate",
  "resource": "model",
  "options": {
    "async": true,
    "wait": false,
    "timeout_seconds": 3600
  }
}
```

返回：

```json
{
  "success": true,
  "request_id": "req_20260925_000001",
  "tool": "midas_execute",
  "status": "queued",
  "data": null,
  "task_id": "task_20260925_000001",
  "warnings": [],
  "errors": []
}
```

> 返回信封见 §11，与总纲 §4.3.2 一致。V2.0 示例中缺失的
> `request_id` / `tool` / `data` / `warnings` / `errors` 已补齐。

---

# 10. Tool ④ midas_task

## 10.1 用途

统一管理异步任务。

## 10.2 JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "structai://mcp/v2.1/tools/midas_task",
  "title": "StructAI MIDAS Task",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "action"
  ],
  "properties": {
    "action": {
      "type": "string",
      "enum": [
        "get",
        "list",
        "cancel",
        "retry",
        "result",
        "events",
        "logs"
      ]
    },
    "task_id": {
      "type": ["string", "null"]
    },
    "type": {
      "type": ["string", "null"],
      "enum": [
        "calculate",
        "analysis",
        "report",
        "export",
        "import",
        "backup",
        "restore",
        "cleanup",
        "drawing_recognize",
        "model_import",
        "optimization",
        "code_check",
        "load_generate",
        "ai_plan_execute",
        null
      ]
    },
    "status": {
      "type": ["string", "null"],
      "enum": [
        "queued",
        "running",
        "success",
        "failed",
        "cancelled",
        "retrying",
        null
      ]
    },
    "since": {
      "type": ["string", "null"]
    },
    "page": {
      "type": "integer",
      "minimum": 1,
      "default": 1
    },
    "page_size": {
      "type": "integer",
      "minimum": 1,
      "maximum": 500,
      "default": 50
    },
    "include_result": {
      "type": "boolean",
      "default": false
    },
    "include_events": {
      "type": "boolean",
      "default": false
    }
  }
}
```

> **`type` 过滤字段为 V2.1 新增**，取值与 `tasks.type` 的 CHECK 约束（裁决 A-6）逐字一致。
> **`since` 为 V2.1 新增**，用于 `action=events` 的增量轮询游标。

## 10.3 轮询模型（裁决 B-9）

> **本 Tool 是轮询（poll-based）模型。**
>
> ```text
> MCP 层能力：get / list / cancel / retry / result / events / logs
> MCP 层不具备：subscribe / push / stream / websocket
> ```
>
> 调用方获取进度的标准姿势：
>
> ```text
> 1. midas_execute  → 返回 task_id
> 2. 循环 midas_task action=events, task_id, since=<上次游标>
> 3. 终态（success / failed / cancelled）时 midas_task action=result
> ```
>
> **推送投递只由 REST/SSE 层提供**，其路径、事件名与载荷**由 v1.2 拥有**，
> 本文件不定义、不承诺、不引用具体事件名。

## 10.4 示例

### 查询任务

```json
{
  "action": "get",
  "task_id": "task_20260925_000001",
  "include_result": true,
  "include_events": true
}
```

### 取消任务

```json
{
  "action": "cancel",
  "task_id": "task_20260925_000001"
}
```

### 轮询事件

```json
{
  "action": "events",
  "task_id": "task_20260925_000001",
  "since": "2026-09-25T08:30:05Z",
  "page_size": 200
}
```

### 按业务类型筛选

```json
{
  "action": "list",
  "type": "drawing_recognize",
  "status": "running",
  "page": 1,
  "page_size": 50
}
```

---

# 11. Tool 统一返回结构

所有 4 个 Tool **统一**使用总纲 §4.3.2 的 MCP 信封：

同步：

```json
{
  "success": true,
  "request_id": "req_20260925_000001",
  "tool": "midas_model",
  "status": "success",
  "data": {},
  "task_id": null,
  "warnings": [],
  "errors": []
}
```

异步：

```json
{
  "success": true,
  "request_id": "req_20260925_000002",
  "tool": "midas_execute",
  "status": "queued",
  "data": null,
  "task_id": "task_20260925_000001",
  "warnings": [],
  "errors": []
}
```

失败：

```json
{
  "success": false,
  "request_id": "req_20260925_000003",
  "tool": "midas_model",
  "status": "failed",
  "data": null,
  "task_id": null,
  "warnings": [],
  "errors": [
    {
      "code": "CAPABILITY_NOT_SUPPORTED",
      "message": "当前 MIDAS Adapter 不支持该操作",
      "details": {
        "adapter": "midas_gen",
        "resource": "node",
        "action": "create"
      }
    }
  ]
}
```

**字段约束：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `success` | boolean | 必填 |
| `request_id` | string | 必填，`req_` 前缀（总纲 §4.1.3） |
| `tool` | string | 必填，4 个 Tool 名之一 |
| `status` | string | 必填，取 `tasks.status` 词表或 `success` |
| `data` | object / null | 必填（可为 null），业务数据一律在此，禁止顶层裸字段 |
| `task_id` | string / null | 异步任务必填，`task_` 前缀 |
| `warnings` | array | 必填，可为空数组 |
| `errors` | array | 必填，可为空数组；元素含 `code` / `message` / `details` |

> **两种信封不得混用（总纲 §4.3.2）：** REST 路径（含 `POST /tools/{name}/test`）必须使用 REST 信封，
> `latency_ms` 放入 `data`；MCP Tool 调用必须使用本节的 MCP 信封。

---

# 12. Adapter 接口规范

Adapter 是 V2.1 最重要的扩展机制。

原则：

```text
MCP Tool
   ↓
CapabilityResolver
   ↓
AdapterRegistry
   ↓
MidasAdapter
   ↓
MIDAS API
```

不同 MIDAS 软件只能通过 Adapter 接入。

---

# 13. Adapter 基础接口

推荐 Python Protocol：

```python
from typing import Protocol, Any, AsyncIterator

class MidasAdapter(Protocol):

    @property
    def code(self) -> str:
        ...

    @property
    def software(self) -> str:
        ...

    @property
    def version(self) -> str:
        ...

    # V2.1 新增（裁决 A-7）：§15 要求 Adapter 提供元数据，
    # 但 V2.0 的 Protocol 没有任何访问器，导致 AdapterMetadata 无法被框架读取。
    async def metadata(self) -> "AdapterMetadata":
        ...

    async def connect(
        self,
        client: "MidasClientConfig"
    ) -> "AdapterResult":
        ...

    async def disconnect(self) -> "AdapterResult":
        ...

    # 对接规范 §2.2 / §7.3：health_check 调 GET /mapikey/verify，
    # 路径位于**主机根**（不带 /gen 或 /civil 产品段），
    # 返回 status / keyVerified / program / connectionID。
    #
    # 注意（对接规范 §2.5.2）：会话被模态对话框阻塞时，
    # /mapikey/verify 仍然回答 connected（中继在应答），而所有 /db/* 调用超时，
    # 因此健康检查**无法**发现阻塞；必须追加一次轻量真实数据探针
    # GET /db/UNIT，两者都通过才可判定通道可用。
    async def health_check(self) -> "AdapterResult":
        ...

    # 对接规范 §5 / §7.3：调 GET /info/db/<RES>，
    # 返回服务器声明的字段与类型，用于生成 request_schema_json。
    #
    # 限制（对接规范 §5.1）：/info 只为 /db/* 提供，对设计代码端点一律 404
    # （/DESIGN/* 共 147 对中 0 对可用），
    # 因此调用方必须能回退到注册表（tool_interfaces.request_schema_json）。
    async def introspect(self, resource: str) -> "AdapterResult":
        ...

    async def capabilities(self) -> list["Capability"]:
        ...

    async def query(
        self,
        request: "QueryRequest"
    ) -> "AdapterResult":
        ...

    async def model(
        self,
        request: "ModelRequest"
    ) -> "AdapterResult":
        ...

    async def execute(
        self,
        request: "ExecuteRequest"
    ) -> "AdapterResult":
        ...

    async def get_task(
        self,
        task_id: str
    ) -> "AdapterResult":
        ...

    async def cancel_task(
        self,
        task_id: str
    ) -> "AdapterResult":
        ...

    async def retry_task(
        self,
        task_id: str
    ) -> "AdapterResult":
        ...

    # 对接规范 §3.1 / §3.2 / §7.3：每个调用都必须经过的两次变换。
    # wrap：按 tool_interfaces.request_wrapper 包装为 {"Assign": ...} / {"Argument": ...}
    # unwrap：按 tool_interfaces.response_root_key 取出内层数据
    def wrap(self, payload: Any, wrapper: str | None) -> dict:
        ...

    def unwrap(self, response: Any, root_key: str | None) -> Any:
        ...
```

**关于 `metadata()`（裁决 A-7）：**

```text
§15  规定 Adapter 必须提供 AdapterMetadata
§13  V2.0 Protocol 缺少访问器  → 元数据不可达
      ↓
V2.1 新增 async def metadata(self) -> "AdapterMetadata"
```

- `metadata()` **不得**发起网络请求，必须是纯本地返回
- `code` / `software` / `version` 三个 property 与 `metadata()` 的同名字段必须一致
- Adapter 注册时（§21 `register`）框架调用一次 `metadata()` 并缓存

**V2.1 新增的四个成员（依据对接规范 §7.3）：**

| 成员 | 上游调用 | 说明 |
|---|---|---|
| `introspect(resource)` | `GET /info/db/<RES>` | 返回服务器声明的字段与类型；**只为 `/db/*` 提供**，设计代码端点一律 404（对接规范 §5.1），调用方必须回退到注册表 |
| `health_check()` | `GET /mapikey/verify`（**主机根**，不带 `/gen` 或 `/civil` 产品段） | 返回 `status` / `keyVerified` / `program` / `connectionID`；**无法**发现被模态对话框阻塞的会话（对接规范 §2.5.2），须追加轻量 `GET /db/UNIT` 探针 |
| `wrap(payload, wrapper)` | — | 按 `request_wrapper` 包装为 `Assign` / `Argument` |
| `unwrap(response, root_key)` | — | 按 `response_root_key` 取出内层数据 |

> `introspect()` 与 `health_check()` 都是**网络调用**；`wrap()` / `unwrap()` 是**纯函数**，不发起请求。

---

# 14. Adapter 生命周期

```text
REGISTERED
    ↓
INITIALIZING
    ↓
READY
    ↓
CONNECTING
    ↓
CONNECTED
    ↓
BUSY
    ↓
CONNECTED
    ↓
DISCONNECTING
    ↓
READY
```

异常：

```text
CONNECTED
    ↓
ERROR
    ↓
RECONNECTING
    ↓
CONNECTED
```

**与数据库状态列的对应关系（总纲 §4.2.5）：**

| 生命周期状态 | `adapters.status` | `midas_clients.status` |
|---|---|---|
| `REGISTERED` / `INITIALIZING` | `disabled` | `disconnected` |
| `READY` | `enabled` | `disconnected` |
| `CONNECTING` | `enabled` | `connecting` |
| `CONNECTED` / `BUSY` | `enabled` | `connected` |
| `ERROR` / `RECONNECTING` | `error` | `error` |
| `DISCONNECTING` | `enabled` | `disconnected` |

> 生命周期状态是**进程内状态机**，不落库；落库的只有上表右侧两个状态列。

---

# 15. Adapter 必须提供的元数据

```python
@dataclass
class AdapterMetadata:
    code: str
    name: str
    software: str
    version_range: str
    protocol: str

    supports_query: bool
    supports_model: bool
    supports_execute: bool
    supports_async_task: bool

    capabilities: list[str]
```

例如：

```json
{
  "code": "midas_gen",
  "name": "MIDAS Gen Adapter",
  "software": "MIDAS Gen",
  "version_range": ">=2024",
  "protocol": "http",
  "supports_query": true,
  "supports_model": true,
  "supports_execute": true,
  "supports_async_task": true,
  "capabilities": [
    "node",
    "element",
    "material",
    "section",
    "load",
    "boundary",
    "analysis",
    "result"
  ]
}
```

**落库映射：**

| `AdapterMetadata` 字段 | 落库位置 |
|---|---|
| `code` | `adapters.code` |
| `name` | `adapters.name` |
| `software` | `adapters.software` |
| `version_range` | `adapters.version_range` |
| `protocol` | `adapters.protocol` |
| `capabilities` | `adapters.capabilities_json` |
| `supports_query` / `supports_model` / `supports_execute` / `supports_async_task` | `adapters.capabilities_json` 内的布尔位 |
| — | `adapters.implementation`（模块路径） |
| — | `adapters.status`（见 §14 映射） |

> `metadata()` 的返回必须能被上述映射**无损**写入 `adapters` 表；
> 若 `metadata().code` 与数据库中已注册的 `adapters.code` 不一致，注册失败并返回 `ADAPTER_NOT_FOUND`。

---

# 16. Capability Resolver

MCP 层不能直接调用 Endpoint。

必须经过：

```python
class CapabilityResolver:

    async def resolve(
        self,
        adapter_code: str,
        tool: str,
        action: str,
        resource: str
    ) -> "Capability":
        ...
```

例如：

```text
midas_model
action=create
resource=node

        ↓

adapter = midas_gen

        ↓

capability = node.create

        ↓

interface = MIDAS Gen / node / create

        ↓

POST /...
```

## 16.1 解析表结构支撑

解析从**调用方选定的 MCP 工具**开始，逐层向下到 adapter：

| 解析环节 | 落库表 |
|---|---|
| 定位 Tool | `capabilities.tool_id` → `tools.id`（v1.0 修订新增） |
| 定位能力 | `capabilities(adapter_code, capability_code)`，唯一键 `ux_capability` |
| 能力 → Interface | `capability_interfaces`（多对多，裁决 B-3） |
| Interface 明细 | `tool_interfaces`，唯一键 `ux_tool_interface(adapter_code, interface_code)` |
| 请求 Schema 二次校验 | `tool_interfaces.request_schema_json` / `capabilities.constraints_json` |
| 定位 Adapter | `adapters.code` / `adapters.status` |

> **为什么 `tool_id` 落在 `capabilities` 而不在 `tool_interfaces`。**
> `tool_interfaces.tool_id` 存在但**不足以**推导能力归属：实测 `/post/TABLE` 的
> POST 被 `midas_execute` 与 `midas_query` **共用**（裁决 B-3 引入
> `capability_interfaces` 正是为了这种共用），且 platform-owned 的能力没有
> interface。所以「这个能力由哪个工具暴露」是**能力自身**的属性。
>
> **`adapter_code` 可空**（v1.0 修订）：`midas_task` 的 7 个能力是
> platform-owned（对接规范 §2.5.1 —— MIDAS 没有任务端点），没有 adapter 可指。
> 可空使 `ux_capability` 失去对它们的约束力（SQL 中 NULL 互不相等），
> 因此补部分唯一索引 `ux_capability_platform`。
>
> **同一 `capability_code` 可按 adapter 各存一行** —— `node.list` 在 gen / civil /
> designer 上各一行，互不覆盖。这是多产品扩展所需的键。
> ⚠️ 代码中的 `_TABLE` 目前只按 `code` 键控，**尚不能表达这一点**；将其改为按
> `(adapter_code, code)` 键控是阶段 3（能力表入库）的前置项。

## 16.2 解析失败的错误码

| 情形 | 错误码（总纲 §4.4） |
|---|---|
| Adapter 未注册 | `ADAPTER_NOT_FOUND` |
| Adapter 不可用 | `ADAPTER_UNAVAILABLE` |
| MIDAS Client 未连接 | `CLIENT_NOT_CONNECTED` |
| 软件/版本不支持该能力 | `CAPABILITY_NOT_SUPPORTED` |
| 二级 Interface 未映射 | `INTERFACE_NOT_FOUND` |

> 解析失败时**禁止**回退到「直连 Endpoint」或「跳过能力校验」。

---

# 17. Endpoint Mapping

数据库中的：

```text
tool_interfaces
```

负责保存：

```json
{
  "adapter_code": "midas_gen",
  "interface_code": "node.create",
  "method": "POST",
  "endpoint": "/db/NODE",
  "operation": "create",
  "resource": "node",
  "request_wrapper": "Assign",
  "response_root_key": "NODE"
}
```

> **V2.1 修正（依据《MIDAS NX Open API 对接规范》§7.1 / §7.2）：**
> V2.0 示例中的 `"endpoint": "/api/model/nodes"` **不是 MIDAS 的真实端点**，已替换为真实端点 `/db/NODE`，
> 并补入 `request_wrapper` / `response_root_key` 两列（见 §4 的 `tool_interfaces` DDL）。
> 全部端点取自 `docs/api-registry/ENDPOINT_INDEX.md`（392 端点注册表）。

这样未来 MIDAS API 地址变化，只改 Adapter/Interface Registry，不修改 LLM Tool Schema。

## 17.1 一接口多 Tool（裁决 B-3）

```text
V2.0：tool_interfaces.tool_id NOT NULL
      → 同一 Endpoint 无法同时服务 midas_query 与 midas_model

V2.1：tool_id 允许 NULL
      → 唯一键改为 (adapter_code, interface_code)
      → 归属关系改由 capabilities + capability_interfaces 表达
```

示例：

```text
tool_interfaces
  id=41  tool_id=NULL  adapter_code=midas_gen  interface_code=node.read
                          method=GET  endpoint=/db/NODE

capabilities
  id=101 adapter_code=midas_gen capability_code=node.list  resource=node action=list
  id=102 adapter_code=midas_gen capability_code=node.get   resource=node action=get

capability_interfaces
  (101, 41)   ← node.list 复用同一个 node.read Interface
  (102, 41)   ← node.get  复用同一个 node.read Interface
```

## 17.2 单复数转换（总纲 §4.6.1）

```text
MCP 层：单数  node
REST 层：复数  nodes
      ↓
转换由 Service 层入口 / Adapter Mapper 承担
禁止在数据库中存储两套资源名
```

`tool_interfaces.resource` 一律存 **MCP 单数**形式。

## 17.3 请求包装与响应解包（对接规范 §3.1 / §3.2）

`tool_interfaces` 的两个新列决定每次调用必须经过的**两次变换**：

| 列 | 取值 | 说明 |
|---|---|---|
| `request_wrapper` | `'Assign'` | `/db/*` 族：编号键（ID）→ 数据对象 |
| | `'Argument'` | `/doc/*` 与多数 design / post 动作；空参用 `{}` |
| | `NULL` | 端点不接收请求体 |
| `response_root_key` | 如 `'NODE'` | GET 响应最外层资源键，据此取出内层对象 |
| | `NULL` | 来源文档未记载 GET body |

```python
payload = wrap(payload, request_wrapper)       # → {"Assign": {...}} / {"Argument": {...}}
data    = unwrap(response, response_root_key)  # ← 必须先判形态，见下
```

**⚠️ 禁止直接写 `response[response_root_key]`。**
`GET /db/*` 实测只有**三种形态**（对接规范 §3.2.1）：

| 形态 | 含义 | 处置 |
|---|---|---|
| `{"<RESOURCE>": {...}}` | 有数据 | 取 `response[root_key]` |
| `{"message": ""}` | **成功且表为空** | 返回空集——**不是错误** |
| `{"error": {...}}` | 失败（HTTP 可能仍为 200 / 201） | 走 §20.4 归一化 |

```python
def unwrap(response, root_key):
    if "error" in response:                  # 1) 结构化失败信号优先
        raise MidasApiError(response["error"])
    if "message" in response:                # 2) {"message":""} = 成功无数据
        if response["message"]:
            raise MidasApiError(response["message"])
        return {}
    if root_key and root_key in response:    # 3) 正常取数据
        return response[root_key]
    return response                          # 4) 无根键端点，原样返回
```

**空表不会返回 `{"NODE": {}}`，而是 `{"message": ""}`** —— 9 个端点实测一致。
直接 `response[root_key]` 会在空模型上抛 `KeyError`。

- **读响应的顶层键是资源名，不是 `Assign`**（`GET /db/NODE` → `{"NODE": {...}}`）
- **回写复用：** 把 GET 响应的顶层键改名为 `Assign` 即可直接 `PUT`——
  这是手册查不到字段时的官方 schema 发现法（对接规范 §3.2）
- 端点是否只接受 `GET` / `PUT`（新文件必需数据如单位、结构类型，`POST` 不生效）
  是**端点级**属性，登记在 `metadata_json.new_file_get_put_only`（对接规范 §3.3）
- **`Assign` 外层键的语义随端点而异**（对接规范 §4.1）：`/db/CNLD` 的外层键是**节点号**，
  而内层 `ITEMS[].ID` 只是**序号**。登记在 `metadata_json.outer_key_means`
  （`node` / `element` / `load_case` / `group` / `self`），写入前**校验目标实体存在**

## 17.4 interface_code 约定

**一个 `interface_code` 对应一个 `(端点, 方法)` 对：**

```text
node.create  → POST   /db/NODE
node.read    → GET    /db/NODE
node.update  → PUT    /db/NODE
node.delete  → DELETE /db/NODE
```

**例外（必须编码表判别符）：** 当一个 URI 承载多个逻辑端点时，
`interface_code` 必须把判别符编进去，否则注册表无法区分：

```text
/post/TABLE              → result.reaction
                           result.displacement
                           design.rc.beam_design_forces
/DESIGN/**/TABLE         → design.rc.beam_design_forces
                           design.src.column_design_forces
                           ...
```

理由：`/post/*` 与 `/DESIGN/**/TABLE` 的 URI 是共享的，
真正的选择发生在 `Argument` 对象内的 `TABLE_TYPE` 值上（对接规范 §3.5 第 8 条）。

## 17.5 MIDAS 端点语义陷阱（对接规范 §3.5）

> 以下语义**已在真实 Gen NX / Civil NX 会话上复现**，不是推测。
> Adapter 与守卫层必须逐条实现。

| # | 陷阱 | Adapter 必须做的防护 |
|---|---|---|
| 1 | **`DELETE {endpoint}` 带 ID 键的 `Assign` 体会清空整张表**，完全忽略传入的 id（对 `/db/NODE` 还会连带删掉挂在其上的单元）。单条删除只有**未文档化**的 `DELETE {endpoint}/{id}`。 | 单条删除**只允许**暴露 `DELETE {endpoint}/{id}` 形式；`Assign` 形式的批量 `DELETE` 必须从 Interface 注册表中移除，或强制显式二次确认。 |
| 2 | `POST /db/NMAS` 在省略可选字段 `rmX` / `rmY` / `rmZ` 时**会杀死 MIDAS NX**。 | Adapter 在写 `/db/NMAS` 前**强制补全**这三个字段（哪怕值为 `0.0`）。此类「必填兜底」作为契约规则存在，不依赖调用方。 |
| 3 | `/doc/NEW` **丢弃未保存的工作**，包括与本次调用无关的文档。 | 高风险操作，纳入 §25.2 确认清单；调用前先探测是否有未保存改动。 |
| 4 | **所有文件路径在运行 MIDAS NX 的那台机器上解析**，常常不是跑本平台的那台。路径不存在会在那边弹模态对话框并阻塞会话，而 HTTP 仍返回类似成功的信息。 | 路径必须由调用方显式提供且可校验；**禁止**从 `health_check()["user"]` 推导路径（那是 MAPI 账号邮箱，不是 NX 主机的 Windows 账户）。 |
| 5 | `/post/TABLE` 的顶层响应键**不稳定**——见过 `"Result Table"`、`"empty"`，也可能就是调用方传入的 `TABLE_NAME`；且 **`"empty"` 可以承载一张完整的表**。 | 必须**按形状匹配**（找带 `HEAD` / `DATA` 的字典），**禁止**按键名取值；**禁止**把 `"empty"` 读作「无数据」。 |
| 6 | 手册可能**把某个端点自己的字段名写错**，不只是枚举值。已确认两例：`/db/REBW`、`/db/REBC`。 | 关键端点上线前必须用 `GET /info/db/<RES>` 或实机 `PUT` 往返核对；`/info` 与实机冲突时**以实机为准**（对接规范 §5.2）。 |
| 7 | Hyper-S（`-M1`）端点是 **Civil NX 专属**，在 Gen NX 下 404；但手册 ch08 / ch17 的「Civil 专属」标注**不可靠**——47 个声明 Civil 专属的端点中 **32 个在 Gen NX 上也能应答**（路由与 `/info` schema 均已实机确认）。 | 用 `HYPER_S_ONLY`（而非 `CIVIL_ONLY`）标记 `-M1` 端点；`tool_interfaces.metadata_json.product_scope`（对接规范 §7.1）**不得**用作工程可行性门控——是否该在 Gen 上驱动桥梁 / 移动荷载功能，是**工程师的判断**。 |
| 8 | **`Assign` 外层键的语义随端点而异。** `/db/CNLD` 的外层键是**节点号**，而内层 `ITEMS[].ID` 只是**序号**（手册参数表：`Serial Number / Integer / 0 / Optional`）。误用会把荷载**静默地加到错误的节点上**——分析照常返回 `command complete`，但反力、内力、位移全错。 | 逐端点在 `tool_interfaces.metadata_json.outer_key_means` 记录外层键语义（`node` / `element` / `load_case` / `group` / `self`）；写入前**校验目标实体存在**。实机案例与完整排障过程见对接规范 §11.6。 |
| 9 | **`POST` 是「仅创建」，不是 upsert。** 键已存在时返回 `400 {"error":{"message":"Key Already Exist"}}`。 | `upsert` 动作必须由 Adapter 自行实现（先 `PUT`，失败再 `POST`，或反之），**不得依赖上游幂等**。 |
| 10 | **读回形态 ≠ 写入形态。** 服务端会补默认值并**归一化数组长度**：`/db/ELEM` 的 `NODE:[1,2]` 读回为 `[1,2,0,0,0,0,0,0]` 并补 `STYPE`；`/db/MATL` 追加 6 个字段；`/db/STLD` 追加 `NO`；`/db/CONS` 追加 `GROUP_NAME`。 | **禁止用读回结果反推最小写入载荷**；写入模板与读回解析必须分别建模。校验「写入是否生效」时比对**关键字段**，而非整体相等。 |
| 11 | **`/post/TABLE` 的 `COMPONENTS` 是必需的。** 省略时返回 `200 {"message":""}`，看起来像「无结果」，实则请求不完整。 | `/post/*` 的 Interface 必须携带默认 `COMPONENTS` 模板；并把「合法空结果」与「请求缺参数」在守卫层区分开。 |

> **实机补充（Gen NX，对接规范 §11.5）：**
>
> - 第 5 条的「不稳定」已确认：根键**就是调用方传入的 `TABLE_NAME`**——传 `"D"` 得到 `{"D":{...}}`，传 `"Displacement"` 得到 `{"Displacement":{...}}`
> - 结果表中的工况名带 `(ST)` 后缀：`LOAD_CASE_NAMES: ["LC1(ST)"]` 才命中，`["LC1"]` 返回空表
> - 错误的 `TABLE_TYPE` 返回 `400` + 错误体，且**服务端会把错误信息截断**
> - `/doc/ANAL` 的**一般分析用裸 `{}`**，`{"Argument": {}}` 是推覆分析形态；且它会**真正校验模型**（无边界条件时返回 `400 [错误] 边界条件 没有定义。`）

---

# 18. Adapter 请求模型

## 18.1 基类（V2.0 原样保留）

```python
@dataclass
class AdapterRequest:
    request_id: str
    client_id: int
    action: str
    resource: str | None
    payload: dict | list | None
    options: dict
    timeout_seconds: int
```

## 18.2 三个子类（V2.1 新增，裁决 A-7）

> V2.0 的 Protocol（§13）把 `query()` / `model()` / `execute()` 的入参分别标注为
> `QueryRequest` / `ModelRequest` / `ExecuteRequest`，但这三个类型**从未被定义**。
> V2.1 补齐，三者**均继承 `AdapterRequest`**。

```python
@dataclass
class QueryRequest(AdapterRequest):
    target: str
    action: str
    query: dict | None = None
    page: int = 1
    page_size: int = 100
```

```python
@dataclass
class ModelRequest(AdapterRequest):
    resource: str
    action: str
    data: dict | list | None = None
    options: dict = field(default_factory=dict)
```

```python
@dataclass
class ExecuteRequest(AdapterRequest):
    action: str
    resource: str | None = None
    data: dict | None = None
    options: dict = field(default_factory=dict)
```

## 18.3 字段说明

**`QueryRequest`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `target` | str | 对应 `midas_query.target`（server / client / capabilities / node / …） |
| `action` | str | 覆盖基类，取值 `get` / `list` / `search` / `count` / `inspect` |
| `query` | dict / None | 已通过 §7.2 `oneOf` 校验的过滤条件 |
| `page` | int | 页码，≥ 1 |
| `page_size` | int | 每页条数，1–500 |

**`ModelRequest`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `resource` | str | 覆盖基类，MCP 单数资源名 |
| `action` | str | 覆盖基类，`create` / `read` / `update` / `delete` / `upsert` / `validate` |
| `data` | dict / list / None | 已通过 §8.2 `oneOf` 校验的载荷 |
| `options` | dict | `validate_before_write` / `validate_after_write` / `transactional` / `dry_run` |

**`ExecuteRequest`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `action` | str | 覆盖基类，`connect` / `import` / `export` / `calculate` / `analysis` / … |
| `resource` | str / None | 覆盖基类 |
| `data` | dict / None | 已通过 Capability `request_schema_json` **二次校验**（§9.3） |
| `options` | dict | `async` / `wait` / `timeout_seconds` / `dry_run` / `force` |

## 18.4 继承与基类字段

三个子类**同时**拥有基类字段，语义如下：

| 基类字段 | 在子类中的含义 |
|---|---|
| `request_id` | 本次 MCP 调用的 `req_` 追踪 ID（总纲 §4.1.3） |
| `client_id` | `midas_clients.id`（INTEGER，裁决 N-6） |
| `payload` | **原始**未归一化载荷；子类的结构化字段是其解析结果 |
| `options` | 通用选项；子类的 `options` 为**同名覆盖**，语义相同 |
| `timeout_seconds` | Adapter 级超时，来自 `tool_interfaces.timeout_seconds` 或调用方 `options` |

> **约定：** 子类中重复声明的 `action` / `resource` / `options` 是对基类字段的
> **重新声明（覆盖）**，用于收紧类型与默认值，不引入第二套语义。

## 18.5 构造示例

```python
QueryRequest(
    request_id="req_20260925_000001",
    client_id=3,
    action="list",
    resource=None,
    payload=None,
    options={},
    timeout_seconds=60,
    target="node",
    query={"group": "W2", "z_min": 0, "z_max": 20},
    page=1,
    page_size=100,
)
```

```python
ModelRequest(
    request_id="req_20260925_000002",
    client_id=3,
    action="create",
    resource="node",
    payload=None,
    options={"validate_before_write": True, "transactional": True},
    timeout_seconds=60,
    data={"name": "N1001", "x": 0, "y": 0, "z": 3.6},
)
```

```python
ExecuteRequest(
    request_id="req_20260925_000003",
    client_id=3,
    action="calculate",
    resource="model",
    payload=None,
    options={"async": True, "wait": False, "timeout_seconds": 3600},
    timeout_seconds=3600,
    data=None,
)
```

---

# 19. Adapter 返回模型

```python
from dataclasses import dataclass, field


@dataclass
class AdapterResult:
    success: bool
    status: str

    data: Any = None

    task_id: str | None = None

    error_code: str | None = None
    error_message: str | None = None

    warnings: list[str] = field(default_factory=list)

    raw_status: int | None = None
    raw_response: Any = None

    latency_ms: int | None = None
```

> **V2.1 修正（裁决 C-11）：** V2.0 §19 直接使用 `field(default_factory=list)` 却
> 没有导入 `field`，代码不可运行。V2.1 补入 `from dataclasses import dataclass, field`。

**字段约束：**

| 字段 | 说明 |
|---|---|
| `status` | 取值来自 `tasks.status` 词表（总纲 §4.2.1），**不得**自定义 |
| `task_id` | 异步任务必须返回，`task_` 前缀 |
| `error_code` | 必须来自总纲 §4.4 注册表，**不得**新增 |
| `raw_status` / `raw_response` | 上游原始返回，仅用于日志与排障，**禁止**直接回传 LLM |
| `latency_ms` | Adapter 侧耗时；MCP 信封中该值放入 `data`，REST 信封中同样放入 `data` |

---

# 20. Adapter 错误归一化

## 20.1 归一化原则

不同 MIDAS 软件可能返回：

```text
HTTP 400
HTTP 500
software error
timeout
connection refused
invalid model
calculation failed
```

Adapter **必须**把这些异构结果归一化为总纲 §4.4 注册表中的**标准错误码**，
并写入 `AdapterResult.error_code`。

> **唯一真源：** 错误码注册表由 **《StructAI 架构边界与融合规范 v1.0（总纲）》§4.4** 拥有。
> 本文件**不复制、不扩充**该表，只做收录与引用。完整清单见 **附录 A**。
> V2.0 §20 的手写错误码清单（含 `AUTH_FAILED` / `VALIDATION_FAILED` / `INVALID_REQUEST` / `TIMEOUT` 等旧名）
> **已删除**，统一走下面的别名映射。

归一化示例：

```json
{
  "success": false,
  "status": "failed",
  "error_code": "CAPABILITY_NOT_SUPPORTED",
  "error_message": "当前 MIDAS 版本不支持该操作"
}
```

## 20.2 旧名别名映射（收录自总纲 §4.4.10）

> 迁移期兼容用。新代码**禁止**再产生左侧旧名。

| 旧名 | 出处 | 归一为 |
|---|---|---|
| `AUTH_FAILED` | V2.0 §20 | `AUTH_INVALID` |
| `VALIDATION_FAILED` | V2.0 §20 | `VALIDATION_ERROR` |
| `TIMEOUT` | V2.0 §20 | `TASK_TIMEOUT` / `MODEL_TIMEOUT` |
| `INVALID_REQUEST` | V2.0 §20 | `VALIDATION_ERROR` |
| `MCP_*` 以外未列出者 | — | `INTERNAL_ERROR` |

## 20.3 Adapter 归一化实现要求

```text
1. Adapter 内部维护一张「上游错误 → 标准错误码」映射表
2. 映射表覆盖不到的上游错误 → INTERNAL_ERROR（不得自造错误码）
3. 网络层超时 → TASK_TIMEOUT（任务态）或 MODEL_TIMEOUT（模型调用态）
4. 认证失败 → MIDAS_AUTH_FAILED（上游认证）/ AUTH_INVALID（本平台认证）
5. 归一化后必须同时填充 error_code 与 error_message
6. error_message 禁止包含密钥、Token、内网地址
```

## 20.4 2xx 错误体识别（对接规范 §3.5 第 2 条 / §7.4）

**HTTP 200 与 201 都可能承载错误体。**

```text
HTTP 200 + {"error": {...}}     ← 多个端点如此
HTTP 201 + {"error": {...}}     ← 错误体也会以 201 返回
HTTP 200 + {"message": "... Analysis failed."}   ← 失败不一定带 error 键
```

**仅检查 HTTP 状态码不足以判定成功。** `is_error_body()` 必须同时检查 200 与 201 的 body，
至少把下列 message 标记判为失败：

```text
"MIDAS GEN NX path is wrong"
"the file can't open"
"Analysis is not allowed"
"no analysis result"
"... Analysis failed."
```

- 失败**不一定带 `error` 键**：`/doc/ANAL` 求解失败返回 `{"message": "... Analysis failed."}`；
  `/doc/SAVEAS` 对根本没发生的保存返回 `"... command complete"`（对接规范 §3.5 第 7 条）
- 另有「参数形式被拒但仍返回 200」的已复现现象：`/doc/EXPORT` 的 `Argument` 必须传裸字符串，
  传对象形式会被拒却仍返回 200（对接规范 §3.4）

### 20.4.1 错误信息是本地化的，且可能被截断（实机确认）

```text
400 {"error":{"message":"[错误] 边界条件 没有定义。"}}          ← 中文
400 {"error":{"message":"MIDAS GEN NX there was an error creating utbl. (ex PostMode ...)"}}
                                                               ← 英文，且 "..." 是服务端自己截断的
```

两条硬约束：

1. **不得只匹配英文字符串**——message 的语言随产品的语言设置变化。
   上面的中文错误就是同一产品在中文界面下返回的。
2. **不得依赖 message 做精确分类**——服务端会截断错误信息，
   `(ex PostMode ...)` 里的省略号来自服务端本身，不是本平台的显示截断。

**因此判据必须有层次：**

| 优先级 | 判据 | 说明 |
|---|---|---|
| 1（主） | 结构化信号：有无 `error` 键、HTTP 状态码 | 与语言无关，最可靠 |
| 2 | `message` 是否为空 | 区分「成功无数据」与「失败」 |
| 3（兜底） | message 文本模式 | 仅作粗归类，且需中英双语 |

> 文本模式匹配**只能作为兜底**，且不得作为唯一的成功/失败判据。

> 因此错误识别必须覆盖 `error` 键、message 文本模式与端点级怪癖三条路径，
> 归一化后仍按 §20.1 映射到总纲 §4.4 的标准错误码（上游错误 → `MIDAS_API_ERROR`）。

---

# 21. Adapter Registry

```python
class AdapterRegistry:

    def register(self, adapter: MidasAdapter) -> None:
        ...

    def unregister(self, code: str) -> None:
        ...

    def get(self, code: str) -> MidasAdapter:
        ...

    def list(self) -> list[MidasAdapter]:
        ...

    def resolve(
        self,
        software: str,
        version: str | None = None
    ) -> MidasAdapter:
        ...
```

**V2.1 补充约定：**

```text
register(adapter)
    → await adapter.metadata()          （裁决 A-7，注册时读取一次并缓存）
    → 校验 metadata().code 与 adapters.code 一致
    → 写回 adapters 表（name / software / version_range / protocol /
                        capabilities_json / status）
    → 若 code 未在 adapters 表登记 → 返回 ADAPTER_NOT_FOUND，拒绝注册
```

- `resolve(software, version)` 按 `adapters.software` + `adapters.version_range` 匹配，
  多个候选时取 `status='enabled'` 且版本范围最精确者
- 无候选 → `ADAPTER_NOT_FOUND`
- 候选存在但 `status='disabled'` → `ADAPTER_UNAVAILABLE`

## 21.1 选实例（多产品路由，总纲 §4.9）

> **裁决（总纲 §4.9.1）：路由链一律为「实例 → 适配器 → 能力」，禁止反向。**
> 本节规定**唯一**允许决定「这次调用去哪个实例」的地方。

```
select_adapter_code(registry, tool, requested) -> str | None
```

| 已注册适配器 | 调用方指定 | 结果 |
|---|---|---|
| 平台拥有的工具（`midas_task`） | （忽略） | `None`（不选实例） |
| 任意 | 已注册的 code | 该 code |
| 任意 | 未注册的 code | `ADAPTER_NOT_FOUND` |
| 恰好 1 个 | 否 | 该适配器（唯一，无歧义） |
| **0 个** | 否 | `CLIENT_NOT_CONNECTED` |
| **>1 个** | **否** | **`VALIDATION_ERROR`（歧义，拒绝）** |

**`>1` 且未指定必须拒绝，这是硬约束**（总纲 §4.9.2 闸 1）。原实现会回退到
`capabilities.adapter_code`（硬编码 `midas_gen`），实机确证：三产品都注册时，
不带 `adapter` 的调用**成功返回 Gen 的数据**——调用方以为在操作 Civil。
猜测的代价是静默的数据损坏，拒绝的代价只是一次明确的报错。

**与 §16 的衔接**：本函数产出 `adapter_code`，随后交给
`CapabilityResolver.resolve(adapter_code, tool, action, resource)`，
后者在**该适配器内**解析能力。能力解析因此只能回答「这个实例支持不支持这个能力」，
不可能再反推实例。

**能力表的键控必须与之一致**（总纲 §4.2.12 / §4.9.3）：
按 `(adapter_code, capability_code)`，同一 `capability_code` 在每个适配器下各一行。
枚举全部能力只能用有序集合，**不得**用 code 为键的字典——后者会让后一行静默覆盖前一行。

---

# 22. V2.1 推荐 Adapter 目录

```text
backend/app/adapters/
│
├── base.py
├── registry.py
├── errors.py
├── models.py
│
├── midas_gen/
│   ├── adapter.py
│   ├── client.py
│   ├── mapper.py
│   ├── capabilities.py
│   └── interfaces.py
│
├── midas_civil/
│   ├── adapter.py
│   ├── client.py
│   ├── mapper.py
│   ├── capabilities.py
│   └── interfaces.py
│
├── midas_fea/
│   ├── adapter.py
│   ├── client.py
│   ├── mapper.py
│   ├── capabilities.py
│   └── interfaces.py
│
└── mock/
    └── adapter.py
```

> `mock/adapter.py` 是**全链路自测的必备件**（对应总纲 §7 Phase 1.10），
> 必须在 Phase 1 完成，用于在真实 MIDAS 未接入时验证 4 个 Tool 的完整链路。

---

# 23. 工程语义层与 Adapter 分离

StructAI 不能直接把工程语义写进 MIDAS Adapter。

正确架构：

```text
StructAI Engineering Model
        │
        ▼
Canonical Structural Model
        │
        ▼
MCP
        │
        ▼
MIDAS Adapter
        │
        ▼
MIDAS-specific Model
```

例如 StructAI：

```json
{
  "element_type": "beam",
  "material": {
    "grade": "Q355"
  },
  "section": {
    "type": "H",
    "height": 400,
    "width": 200
  }
}
```

Adapter 再转换成 MIDAS Gen 所要求的字段。

**分层职责：**

| 层 | 负责 | 不负责 |
|---|---|---|
| 工程语义层（StructAI） | 工程概念、规范条文、参数校验、模板 | 任何 MIDAS 专有字段名 |
| Canonical Model | 跨软件统一的中间表示 | 任何软件的私有扩展 |
| MCP Tool 层 | 4 个稳定工具契约、Capability 解析 | 字段级转换 |
| Adapter 层 | 字段映射、协议、认证、错误归一化 | 工程规则判断 |

> **禁止：** 在 Adapter 中出现 `GB50017`、`荷载组合系数`、`抗震等级` 等**工程规则**判断；
> 这些属于工程语义层。Adapter 只做「Canonical → MIDAS」的机械转换。

---

# 24. Canonical Model 建议

StructAI 内部统一：

```text
Project
 ├── Node
 ├── Element
 ├── Material
 ├── Section
 ├── Boundary
 ├── Load
 ├── LoadCase
 ├── LoadCombination
 ├── Group
 └── Analysis
```

这样：

```text
StructAI → MIDAS Gen
StructAI → MIDAS Civil
StructAI → MIDAS FEA NX
StructAI → CSI
```

未来都可以通过不同 Adapter 实现。

**与 MCP resource 词表的对应：**

| Canonical 实体 | MCP resource（单数） |
|---|---|
| Project | `project` |
| Node | `node` |
| Element | `element` |
| Material | `material` |
| Section | `section` |
| Boundary | `boundary` |
| Load / LoadCase / LoadCombination | `load` |
| Group | `group` |
| Analysis | `analysis` |

> `LoadCase` 与 `LoadCombination` 在 MCP 层归入 `load` 资源的 `load_case` / `load_combination` 过滤字段，
> **不新增 MCP resource**（总纲 §4.6 的 resource 词表为封闭集合）。

**单位（总纲 §4.5.2，强制）：**

| 类别 | 单位 |
|---|---|
| 长度 / 坐标 | m |
| 截面尺寸 | mm |
| 力 | kN |
| 分布荷载 | kN/m、kN/m² |
| 应力 | MPa |
| 位移 | mm |
| 质量 | kg / t |
| 进度 | 0–100 REAL |
| 置信度 | 0.0–1.0 REAL |

---

# 25. 事务与安全

## 25.1 midas_model 写操作选项

`midas_model` 写操作必须支持：

```text
validate_before_write
transactional
dry_run
validate_after_write
```

推荐默认：

```json
{
  "validate_before_write": true,
  "transactional": true,
  "dry_run": false,
  "validate_after_write": true
}
```

## 25.2 高风险操作

```text
delete
calculate
overwrite
import
close_project
```

应由策略层决定是否需要二次确认。

**V2.1 补充（与总纲 §4.8.4 对齐）：**

```text
1. AI 助手路径（L4a）触发高风险操作时，必须经过 assistant_plans 的高风险确认流程：
     risk_level = high  →  requires_confirmation = 1
                        →  签发一次性 confirmation_token（哈希落
                            assistant_plans.confirmation_token_hash，有效期 10 分钟，
                            绑定 plan_id + user_id）
                        →  未确认即执行 → PLAN_NOT_CONFIRMED
2. 运维路径（L2 REST）由 v1.2 的鉴权声明约束，本文件不定义。
3. AI 助手不得触发 data:restore（总纲 §4.8.4 裁决）。
```

## 25.3 事务边界

```text
单次 MCP Tool 调用 = 一个 Service 层事务单元
    ├── 数据库写入（tasks / assistant_* / audit_logs）
    └── Adapter 调用（不参与数据库事务）

Adapter 侧事务由 Adapter 自行管理（MIDAS 侧事务）
数据库侧回滚不影响已发出的 Adapter 请求
    → 因此必须依赖 task_events + system_logs 做补偿追踪
```

## 25.4 加密字段（总纲 §4.7.1，封闭清单）

见 §30。

---

# 26. Task Engine

## 26.1 状态流转

所有可能超过几秒的操作进入任务系统：

```text
queued
  ↓
running
  ↓
success

queued
  ↓
running
  ↓
failed
  ↓
retrying
  ↓
running
```

或者：

```text
running → cancelled
```

> 状态取值与 `tasks.status` 的 CHECK 约束**逐字一致**（总纲 §4.2.1）。

## 26.2 tasks.type 业务任务类型（裁决 A-6）

> **`tasks.type` 是业务任务类型，取值封闭，共 14 个：**

```text
calculate            结构计算
analysis             分析（模态 / 屈曲 / 反应谱等）
report               报告生成
export               数据导出
import               数据导入
backup               备份
restore              恢复
cleanup              清理
drawing_recognize    图纸识别
model_import         模型导入
optimization         结构优化
code_check           规范检查
load_generate        荷载生成
ai_plan_execute      AI 执行计划
```

> **`tasks.action` 是具体动作**，复用 MCP action 词表（§6.3），
> 例如 `calculate` / `create` / `list` / `cancel`。
>
> **二者语义分工：**
>
> ```text
> type   = 这个任务「是什么业务」     → calculate / drawing_recognize / report ...
> action = 这个任务「做了哪个动作」   → create / list / calculate / cancel ...
> ```
>
> 示例：
>
> ```text
> task_20260925_000001   type=calculate           action=calculate   resource=model
> task_20260925_000002   type=drawing_recognize   action=import      resource=file
> task_20260925_000003   type=report              action=generate_report  resource=report
> task_20260925_000004   type=export              action=export      resource=result
> ```
>
> **ID 约定（总纲 §4.1.4）：** 一切异步任务 ID 一律 `task_` 前缀，
> 子类型由 `tasks.type` 区分；原 `task_ai_xxx` / `analysis_xxx` / `drawing_xxx` 等前缀**全部废止**。

## 26.3 Task Engine 职责

```text
- 排队
- 并发限制
- 超时
- 重试
- 取消
- 进度
- 日志
- 结果
- 事件（供轮询，见 §10.3）
- SSE 推送能力声明（实现归 v1.2）
```

**落库对应：**

| 职责 | 落库位置 |
|---|---|
| 排队 / 并发 | `tasks.status='queued'`、`tasks.priority` |
| 超时 | `tasks.finished_at`、`tasks.error_code='TASK_TIMEOUT'` |
| 重试 | `tasks.retry_count`、`tasks.max_retries`、`tasks.status='retrying'` |
| 取消 | `tasks.status='cancelled'` |
| 进度 | `tasks.progress`（0–100 REAL） |
| 日志 | `system_logs`（含 `task_id`、`adapter_request_id`） |
| 结果 | `tasks.result_json` |
| 事件 | `task_events`（`event_type` / `progress` / `message` / `payload_json`） |

## 26.4 追溯

```text
request_id  →  task_id  →  adapter_request_id
```

三者必须能从任一端互相查到（总纲 §4.1.5）。落库位置见 §5.5。

## 26.5 并发模型与写操作重试禁令（对接规范 §2.5.2 / §2.5.4）

```text
全局工作池并发      = N   （平台层：局域网内多部门/多用户并发）
每个 midas_client_id 并发 = 1   （实例层：硬约束，恒等于 1）
```

> **平台层并发 N，但每个 `midas_client_id` 并发恒为 1。**

理由：MIDAS NX 是**单实例 GUI 应用**，云端中继只是通道。
任何会弹出确认对话框的调用（文件读写、路径相关、`/doc/NEW`）
会阻塞**整条 API 会话**，而不只是那一次调用——并发调用会互相拖死（对接规范 §2.5.2）。

落实方式：

| 项 | 要求 |
|---|---|
| 队列结构 | **全局工作池 + 按 `midas_client_id` 串行队列**；同一 `midas_client_id` 任何时刻只允许一个在途请求 |
| 约束落点 | `midas_clients.max_concurrency` 固定为 1（`CHECK(max_concurrency = 1)`，见 §4），把约束写进数据而不是代码注释 |
| 对话框风险调用 | `/doc/NEW`、文件读写、路径相关端点：**串行 + 带超时** |
| 健康检查 | 不能只用 `/mapikey/verify`（它看不见阻塞），须加轻量 `GET /db/UNIT` 真实数据探针（见 §13） |

**写操作超时后禁止自动重试：**

```text
超时 ≠ 回滚
写操作可能在 HTTP 放弃后仍然在 MIDAS 侧落地
      ↓
禁止对写操作自动重试；超时后必须先读回模型状态，再决定后续动作
```

> 依据：对接规范 §3.5 第 5 条。
> `tasks.retry_count` / `tasks.max_retries` 只对**可安全重放的读操作**或**明确幂等的任务**生效；
> 写类任务超时一律置 `failed`（`error_code = 'TASK_TIMEOUT'`）并等待人工判定，
> **不得**由 Task Engine 自动重投。

---

# 27. 前端实时接口

> **边界声明：** 本节只做**能力声明**与**归属指向**。
> `/api/v1/*` 的完整契约（请求体、响应体、事件名、载荷）由 **《StructAI 管理器 API 接口设计规范 v1.2》** 拥有，
> 本文件不定义、不复制。

## 27.1 MCP 状态

```text
能力：查询 MCP Server 运行状态
归属：v1.2
规范路径：GET /api/v1/mcp/server
```

> **裁决 A-1：** V2.0 §27 的 `GET /api/v1/mcp/server/status` **已删除**。
> 规范路径为 `GET /api/v1/mcp/server`，由 v1.2 保持。

## 27.2 实时流（两条，归属 v1.2）

```text
能力：任务实时状态
路径：GET /api/v1/tasks/{task_id}/stream
归属：v1.2

能力：日志实时流
路径：GET /api/v1/logs/stream
归属：v1.2
```

> 这两条路径保留，因为它们是 **REST/SSE 层**的接口，不是 MCP Tool。
> 本文件只声明「MCP 侧不提供 push（裁决 B-9），实时推送由这两条 SSE 承担」。

## 27.3 传输选型

建议 SSE 优先于 WebSocket，因为：

- 任务 / 日志主要是单向服务器推送
- 前端实现简单
- Docker / 反向代理兼容性较好
- 不需要维持复杂双向协议

真正需要双向交互时再增加 WebSocket。

> **MCP 侧不存在上述选型问题：** MCP 是请求-响应模型，进度获取一律轮询（§10.3）。

---

# 28. REST API 与 MCP 的关系

```text
Vue
 │
 │ REST
 ▼
FastAPI
 │
 ├── /api/v1/settings
 ├── /api/v1/tasks
 ├── /api/v1/logs
 └── /api/v1/midas
 │
 ▼
Service Layer
 │
 ▼
Adapter
```

而 LLM：

```text
LLM
 │
 │ MCP
 ▼
MCP Server
 │
 ▼
Tool Dispatcher
 │
 ▼
Capability Resolver
 │
 ▼
Adapter
```

**两条路径最终共享同一个 Service Layer。**

这样避免：

```text
REST 一套业务逻辑
MCP 又一套业务逻辑
```

导致长期维护分裂。

## 28.1 汇合点（总纲 §2.1 L3）

```text
                     Service Layer（唯一业务逻辑）
                    ┌──────────────┴──────────────┐
              REST 门面                      MCP Tool 门面
          （v1.2 拥有契约）                （本文件 §7-§11 拥有契约）
```

**强制规则：**

```text
1. 同一业务能力在两条路径上必须调用同一个 Service 方法
2. Service 层不感知调用来源（REST 或 MCP），来源由门面层注入
3. 门面层只做：入参适配、信封适配、权限校验入口
4. 禁止在 MCP Tool 内直接访问 Repository 或 Adapter
```

## 28.2 双门面并存（总纲 N-2）

AI 门面与运维门面**允许并存**，但必须：

```text
① 共享同一 Service
② 请求体字段名完全一致
③ 响应体同构
```

> 具体接口清单与字段对齐由 v1.2 拥有，本文件不列举。

---

# 29. API 权限与 MCP 权限

MCP Client 不能默认拥有超级管理员权限。

```text
MCP Client
  ↓
Authentication
  ↓
User / Service Account
  ↓
RBAC
  ↓
Tool Permission
  ↓
Capability Permission
  ↓
Adapter
```

例如：

```text
tool:execute
+
model:read
+
model:update
```

才能执行模型修改。

而：

```text
data:restore
```

应该默认只有：

```text
super_admin
```

## 29.1 MCP Client 凭据（裁决 B-1）

```text
mcp_clients
  └── mcp_client_credentials
         ├── secret_hash      单向哈希（总纲 §4.7.1）
         ├── secret_prefix    仅用于回显识别
         ├── scopes_json      该凭据被授予的权限码子集
         ├── expires_at       过期时间
         └── revoked_at       吊销时间
```

**规则：**

```text
1. 一个 MCP Client 可持有多个凭据（轮换期并存）
2. 凭据本体只在签发时返回一次，之后仅存哈希
3. scopes_json 是权限码的「子集约束」：
     实际权限 = RBAC 角色权限 ∩ scopes_json
4. revoked_at 非空或 expires_at 已过 → AUTH_EXPIRED / AUTH_INVALID
5. 凭据校验失败不得回退到匿名访问
```

## 29.2 权限码清单

完整清单为封闭集合，见总纲 §4.8.2，落库为 `permissions` 表种子数据（§4-19.1）。

默认角色映射见总纲 §4.8.3，落库为 `role_permissions` 种子数据（§4-19.3）。

高风险权限约束（总纲 §4.8.4）：

```text
data:restore        → 仅 super_admin
system:write        → 仅 super_admin
user:delete         → 仅 super_admin
assistant:execute   → engineer 及以上，且必须通过 §25.2 高风险确认流程
```

---

# 30. API Key 与 Secret

## 30.1 必须加密的字段（收录自总纲 §4.7.1，封闭清单）

```text
models.api_key_encrypted
midas_clients.api_key_encrypted
midas_clients.access_token_encrypted
mcp_client_credentials.secret_hash        （单向哈希）
system_configs.config_value               （当 is_secret = 1 时）
assistant_plans.confirmation_token_hash   （单向哈希）
```

推荐算法：

```text
AES-256-GCM
```

环境变量：

```text
STRUCTAI_MASTER_KEY
```

数据库只保存密文。

> **V2.1 修正（裁决 C-3 / B-8）：** V2.0 §30 只列了前三个字段，遗漏
> `mcp_client_credentials.secret_hash`、`system_configs.config_value`（`is_secret=1` 时）、
> `assistant_plans.confirmation_token_hash`。V2.1 与总纲 §4.7.1 对齐。
>
> **哈希 vs 加密：**
>
> | 字段 | 方式 | 可否解密 |
> |---|---|---|
> | `*_encrypted` | AES-256-GCM 可逆加密 | 可（运行时需要明文） |
> | `secret_hash` / `confirmation_token_hash` | 单向哈希 | **不可** |

## 30.2 回显规范（收录自总纲 §4.7.2）

敏感字段**一律**按以下结构回显，禁止返回明文：

```json
{
  "api_key_configured": true,
  "api_key_masked": "********"
}
```

字段名前缀按实际字段替换（`api_key_` / `access_token_` / `secret_`）。

> **裁决 C-3：** V2.0 §30 的 `{"configured": true, "masked": "********"}` **废止**，
> 统一采用带前缀的 `api_key_configured` / `api_key_masked` 形式。

**前缀替换对照：**

| 实际字段 | 回显字段 |
|---|---|
| `api_key_encrypted` | `api_key_configured` / `api_key_masked` |
| `access_token_encrypted` | `access_token_configured` / `access_token_masked` |
| `secret_hash` | `secret_configured` / `secret_masked` |
| `confirmation_token_hash` | **不回显**（一次性令牌，签发时返回一次） |

**规则：**

```text
1. 回显结构由 v1.2 在响应体中实现（总纲 §4.7 为唯一真源）
2. MCP Tool 的返回信封中同样禁止出现明文密钥
3. masked 值统一为固定长度星号，不泄露真实长度
```

---

# 31. 版本策略

## 31.1 MCP Tool Schema 版本

```text
tool.version = "2.1"
```

`$id` 形式：

```text
structai://mcp/v2.1/tools/midas_query
structai://mcp/v2.1/tools/midas_model
structai://mcp/v2.1/tools/midas_execute
structai://mcp/v2.1/tools/midas_task
```

Tool 名称保持稳定：

```text
midas_query
midas_model
midas_execute
midas_task
```

未来 V3 不建议直接修改 V2.1 Schema，而是：

```text
/v2.1/tools/...
/v3/tools/...
```

或者：

```text
tool.version = "3.0"
```

旧客户端继续使用 V2.1。

## 31.2 两条版本轴相互独立（裁决 C-5）

> **MCP Tool Schema 版本轴** 与 **REST API 版本轴** 是**两条独立轴，无映射关系**。
>
> ```text
> MCP Tool Schema：  v2  →  v2.1  →  v3        （本文件拥有）
> REST API：         /api/v1  →  /api/v2         （v1.2 拥有）
>                        ↑
>                  二者之间没有任何对应、换算或同步要求
> ```
>
> 结论：
>
> ```text
> 1. MCP 大版本升级（如 v2.1 → v3）不影响 REST 的 /api/v1
> 2. REST 大版本升级（/api/v1 → /api/v2）不影响 MCP Tool Schema
> 3. 不得出现「MCP v3 对应 REST v2」之类的映射表
> 4. 不得用 REST 版本号命名 MCP Schema 路径，反之亦然
> ```

## 31.3 兼容性规则

```text
新增可选字段        → 兼容，不升版本
新增 enum 取值      → 需评估；MCP Tool 的 action/resource 枚举为封闭集合，
                      新增取值属于不兼容变更，必须升小版本
删除 / 改名         → 不兼容，必须升大版本
收紧 additionalProperties → 不兼容（V2.0 → V2.1 属此类）
```

> **V2.0 → V2.1 的不兼容点（必须通知既有 MCP Client）：**
>
> ```text
> 1. midas_query.action 移除 'capabilities'（裁决 C-7）
> 2. midas_query.query 收紧为 oneOf（裁决 B-4）
> 3. midas_model.data 收紧为 oneOf（裁决 B-4）
> 4. midas_task 新增 type / since（本文件 §10.2）
> ```

---

# 32. V2.1 最终接口边界

```text
                    StructAI
                       │
                AI Engineering
                   Assistant
                       │
                       ▼
              ┌────────────────┐
              │   MCP V2.1     │
              ├────────────────┤
              │ midas_query    │
              │ midas_model    │
              │ midas_execute  │
              │ midas_task     │
              └───────┬────────┘
                      │
             Capability Resolver
                      │
                Adapter Registry
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
    MIDAS Gen     MIDAS Civil    MIDAS FEA
      Adapter       Adapter       Adapter
        │             │             │
        └─────────────┼─────────────┘
                      ▼
                 MIDAS API
```

## 32.1 边界一览

| 边界 | 本文件拥有 | 指向 |
|---|---|---|
| 持久层（49 张表） | ✅ §4 | — |
| MCP 4 Tool 契约 | ✅ §7-§11 | — |
| Adapter / Capability / Interface | ✅ §12-§22 | — |
| Canonical Model | ✅ §23-§24 | — |
| 错误码注册表 | ❌ | 总纲 §4.4 / 本文件附录 A（收录） |
| 状态词表 | ❌ | 总纲 §4.2 / 本文件附录 B（收录） |
| ID 命名规范 | ❌ | 总纲 §4.1 / 本文件附录 C（收录） |
| 权限码清单 | ❌ | 总纲 §4.8（本文件仅落种子数据） |
| REST 路径与请求/响应体 | ❌ | v1.2 |
| SSE 事件名与载荷 | ❌ | v1.2 |
| UI 展示状态机 | ❌ | v1.2 §96（派生） |
| 实施排期 | ❌ | 总纲 §7 |
| 验收标准 | ❌ | 总纲 §8 |

## 32.2 核心抽象

```text
4 个 Tool = 给 AI 的稳定接口
Capability = AI 可执行能力
Interface = 软件具体 Endpoint
Adapter = 软件差异适配
Task = 长任务生命周期
Database = 全部配置、权限、能力和运行状态的持久化中心
```

因此以后增加：

```text
MIDAS Gen
MIDAS Civil
MIDAS FEA NX
CSI
SAP2000
ETABS
ANSYS
```

都不需要修改 StructAI 的 AI Tool Schema，只需要增加新的 Adapter + Capability + Interface Mapping。

这就是 V2.1 的核心扩展能力。

## 32.3 后续章节归属

> **原 V2.0 §33「实施优先级」与 §34「验收标准」已删除**，
> 统一上移至 **《StructAI 架构边界与融合规范 v1.0（总纲）》§7 实施排期** 与 **§8 统一验收标准**。
> 本文件不再重复定义，以避免违反总纲 §0.3「唯一真源原则」。
>
> 原 V2.0 §35「最终结论」的内容已并入本节 §32.1 / §32.2。

---

# 附录 A 错误码注册表（收录）

> **唯一真源：** 《StructAI 架构边界与融合规范 v1.0（总纲）》**§4.4**。
> 本附录为**收录副本**，仅供本文件内部查阅；任何差异以总纲 §4.4 为准。
> 本文件**不得**新增、改名或删除任何错误码。

## A.1 认证与授权（总纲 §4.4.1）

| code | HTTP | 说明 |
|---|---|---|
| `AUTH_REQUIRED` | 401 | 未提供凭证 |
| `AUTH_INVALID` | 401 | 凭证无效（含旧名 `AUTH_FAILED`） |
| `AUTH_EXPIRED` | 401 | 凭证过期 |
| `PERMISSION_DENIED` | 403 | 权限不足 |
| `CONFIRMATION_INVALID` | 403 | 高风险确认令牌无效或过期 |

## A.2 请求与资源（总纲 §4.4.2）

| code | HTTP | 说明 |
|---|---|---|
| `VALIDATION_ERROR` | 422 | 参数校验失败（含旧名 `VALIDATION_FAILED`） |
| `RESOURCE_NOT_FOUND` | 404 | 资源不存在 |
| `RESOURCE_CONFLICT` | 409 | 资源冲突 |
| `RATE_LIMITED` | 429 | 请求过于频繁 |

## A.3 MCP 层（总纲 §4.4.3）

| code | HTTP | 说明 |
|---|---|---|
| `MCP_SERVER_ERROR` | 500 | MCP Server 内部错误 |
| `MCP_CLIENT_ERROR` | 502 | MCP Client 协议错误 |

## A.4 Adapter 与能力（总纲 §4.4.4）

| code | HTTP | 说明 |
|---|---|---|
| `ADAPTER_NOT_FOUND` | 404 | Adapter 未注册 |
| `ADAPTER_UNAVAILABLE` | 503 | Adapter 不可用 |
| `CLIENT_NOT_CONNECTED` | 409 | MIDAS Client 未连接 |
| `CAPABILITY_NOT_SUPPORTED` | 422 | 当前软件/版本不支持该能力 |
| `INTERFACE_NOT_FOUND` | 404 | 二级 Interface 未映射 |

## A.5 MIDAS 上游（总纲 §4.4.5）

| code | HTTP | 说明 |
|---|---|---|
| `MIDAS_CONNECTION_FAILED` | 502 | 连接失败 |
| `MIDAS_AUTH_FAILED` | 502 | 上游认证失败 |
| `MIDAS_API_ERROR` | 502 | 上游返回错误 |
| `MIDAS_CALCULATION_ERROR` | 502 | 计算失败 |

## A.6 任务（总纲 §4.4.6）

| code | HTTP | 说明 |
|---|---|---|
| `TASK_NOT_FOUND` | 404 | 任务不存在 |
| `TASK_ALREADY_RUNNING` | 409 | 任务已在运行 |
| `TASK_CANCEL_FAILED` | 409 | 取消失败 |
| `TASK_TIMEOUT` | 504 | 任务超时（含旧名 `TIMEOUT`） |

## A.7 AI 工程助手（总纲 §4.4.7）

| code | HTTP | 说明 |
|---|---|---|
| `INTENT_UNRESOLVED` | 422 | 意图无法识别 |
| `PARAMETER_INCOMPLETE` | 422 | 关键参数缺失 |
| `PARAMETER_INVALID` | 422 | 参数超出规范允许范围 |
| `PLAN_NOT_CONFIRMED` | 409 | 计划未经确认即请求执行 |
| `PLAN_STEP_FAILED` | 500 | 计划步骤执行失败 |
| `DRAWING_UNSUPPORTED` | 422 | 图纸格式不支持 |
| `RECOGNITION_LOW_CONFIDENCE` | 422 | 识别置信度低于阈值 |
| `CODE_STANDARD_MISSING` | 422 | 规范知识库缺少所需条文 |

## A.8 AI 模型（总纲 §4.4.8）

| code | HTTP | 说明 |
|---|---|---|
| `MODEL_UNAVAILABLE` | 503 | 模型不可用 |
| `MODEL_TIMEOUT` | 504 | 模型超时 |
| `MODEL_API_ERROR` | 502 | 模型接口错误 |

## A.9 数据与系统（总纲 §4.4.9）

| code | HTTP | 说明 |
|---|---|---|
| `DATABASE_ERROR` | 500 | 数据库错误 |
| `BACKUP_FAILED` | 500 | 备份失败 |
| `RESTORE_FAILED` | 500 | 恢复失败 |
| `IMPORT_VALIDATION_FAILED` | 422 | 导入文件校验失败 |
| `INTERNAL_ERROR` | 500 | 未归类内部错误 |
| `NOT_IMPLEMENTED` | 501 | 能力已定义未实现 |

## A.10 旧名别名映射（收录自总纲 §4.4.10）

| 旧名 | 出处 | 归一为 |
|---|---|---|
| `AUTH_FAILED` | V2.0 §20 | `AUTH_INVALID` |
| `VALIDATION_FAILED` | V2.0 §20 | `VALIDATION_ERROR` |
| `TIMEOUT` | V2.0 §20 | `TASK_TIMEOUT` / `MODEL_TIMEOUT` |
| `INVALID_REQUEST` | V2.0 §20 | `VALIDATION_ERROR` |
| `MCP_*` 以外未列出者 | — | `INTERNAL_ERROR` |

> **V2.0 §20 的手写错误码清单已在本文件 §20 中删除**，统一由本附录替代。

---

# 附录 B 状态词表（收录）

> **唯一真源：** 《StructAI 架构边界与融合规范 v1.0（总纲）》**§4.2**。
> 本附录为**收录副本**；任何差异以总纲 §4.2 为准。
> 本文件**不得**新增或修改任何状态取值。

## B.1 任务状态 `tasks.status`（总纲 §4.2.1）

```text
queued      已入队
running     执行中
success     成功
failed      失败
cancelled   已取消
retrying    重试中
```

落库位置：`tasks.status`（带 CHECK 约束）。
MCP `midas_task` 的 `status` 枚举与此**完全一致**。

## B.2 执行计划状态 `assistant_plans.status`（总纲 §4.2.2）

```text
draft                   草稿（AI 正在生成步骤）
validating              参数校验中
awaiting_confirmation   等待人工确认
approved                已确认，待执行
rejected                已拒绝
executing               执行中
verifying               结果校验中
completed               已完成
failed                  失败
cancelled               已取消
```

落库位置：`assistant_plans.status`（带 CHECK 约束）。

## B.3 计划步骤状态 `assistant_plan_steps.status`（总纲 §4.2.3）

```text
pending     待执行
running     执行中
completed   已完成
failed      失败
skipped     已跳过（依赖失败或人工跳过）
```

## B.4 会话状态 `assistant_sessions.status`（总纲 §4.2.4）

```text
active      活跃
archived    已归档
```

## B.5 其他既有状态列（总纲 §4.2.5）

```text
users.status              enabled / disabled / locked
midas_clients.status      disconnected / connecting / connected / error
mcp_servers.status        stopped / starting / running / stopping / error
mcp_clients.status        disconnected / connected
adapters.status           enabled / disabled / error
models.status             available / unavailable / error
backups.status            processing / success / failed
data_exports.status       processing / success / failed
data_imports.status       processing / success / failed
```

> 全部已在 §4 的 DDL 中补 `CHECK` 约束（裁决 B-10）。

## B.6 UI 展示状态机（总纲 §4.2.6，v1.2 拥有，不落库）

```text
IDLE → UNDERSTANDING → PLANNING → VALIDATING → WAITING_CONFIRMATION
     → EXECUTING → VERIFYING → COMPLETED
异常：FAILED / CANCELLED / TIMEOUT
```

> 这是**前端展示状态机**，由 v1.2 拥有，**不落库**。
> 它由 `assistant_plans.status` + `assistant_plan_steps.status` + `tasks.status` 三者**派生**得出，
> 映射关系由 v1.2 定义。本文件不实现、不映射。

---

# 附录 C ID 命名规范（收录）

> **唯一真源：** 《StructAI 架构边界与融合规范 v1.0（总纲）》**§4.1**。
> 本附录为**收录副本**；任何差异以总纲 §4.1 为准。
> 本文件**不得**新增任何 ID 前缀。

## C.1 数据库主键（总纲 §4.1.1）

```text
一律 INTEGER PRIMARY KEY AUTOINCREMENT
```

## C.2 业务 ID 总则（总纲 §4.1.2）

```text
<前缀>_<yyyymmdd>_<6位十进制序号>
```

示例：`req_20260925_000001`

## C.3 前缀清单（封闭集合，总纲 §4.1.3）

| 前缀 | 实体 | 所属表 | 所有者 |
|---|---|---|---|
| `req_` | 请求追踪 ID | 不落库（日志/响应） | §4.1 |
| `task_` | **任务 ID（唯一任务前缀）** | `tasks.task_id` | §4.1 |
| `adapter_` | Adapter 请求 ID | 日志 | §4.1 |
| `asst_` | AI 会话 ID | `assistant_sessions.session_id` | §4.1 |
| `msg_` | AI 消息 ID | `assistant_messages.message_id` | §4.1 |
| `intent_` | 意图 ID | `assistant_intents.intent_id` | §4.1 |
| `plan_` | 执行计划 ID | `assistant_plans.plan_id` | §4.1 |
| `confirm_` | 确认令牌 ID | `assistant_plans` | §4.1 |
| `file_` | 文件 ID | `assistant_files.file_id` | §4.1 |
| `draw_` | 识图任务 ID | `assistant_drawing_tasks.drawing_id` | §4.1 |
| `rpt_` | 报告 ID | `reports.report_id` | §4.1 |
| `bk_` | 备份 ID | `backups.backup_id` | §4.1 |
| `exp_` | 导出 ID | `data_exports.export_id` | §4.1 |
| `imp_` | 导入 ID | `data_imports.import_id` | §4.1 |

## C.4 关键裁决：取消任务子类型前缀（总纲 §4.1.4）

> **原文档中的 `task_ai_xxx` / `task_calc_001` / `analysis_xxx` / `optimization_xxx` /
> `export_xxx` / `report_xxx` / `model_import_xxx` / `drawing_xxx` 全部废止。**

**一切异步任务的 ID 一律使用 `task_` 前缀**，子类型由 `tasks.type` 字段区分：

```text
task_20260925_000001   type=calculate
task_20260925_000002   type=drawing_recognize
task_20260925_000003   type=report
task_20260925_000004   type=export
```

理由：

- 所有长任务统一进 `tasks` 表，统一可查询、取消、重试、订阅
- 避免前端为每种任务写一套路由
- `GET /api/v1/tasks/{task_id}` 对任何任务都成立

## C.5 追溯链（总纲 §4.1.5）

```text
request_id  →  task_id  →  adapter_request_id
```

三者必须能从任一端互相查到。`tasks` 表保存 `request_id`，
`system_logs` 保存 `adapter_request_id`。

## C.6 本文件中的前缀落点速查

| 前缀 | §4 DDL 中的列 |
|---|---|
| `task_` | `tasks.task_id` |
| `asst_` | `assistant_sessions.session_id` |
| `msg_` | `assistant_messages.message_id` |
| `intent_` | `assistant_intents.intent_id` |
| `plan_` | `assistant_plans.plan_id` |
| `file_` | `assistant_files.file_id` |
| `draw_` | `assistant_drawing_tasks.drawing_id` |
| `rpt_` | `reports.report_id` |
| `bk_` | `backups.backup_id` |
| `exp_` | `data_exports.export_id` |
| `imp_` | `data_imports.import_id` |

> `req_` 与 `adapter_` **不落主键列**，分别落于
> `tasks.request_id` / `system_logs.request_id` / `audit_logs.request_id`
> 与 `system_logs.adapter_request_id`。
> `confirm_` 为一次性确认令牌 ID，仅哈希落 `assistant_plans.confirmation_token_hash`，不落明文列。

---

**（全文完）**

**文档版本：** V2.1  
**上位文档：** 《StructAI 架构边界与融合规范 v1.0（总纲）》  
**配套文档：** 《StructAI 管理器 API 接口设计规范 v1.2》  
**数据库基线：** SQLite 3.x（PostgreSQL 可迁移）  
**表数量：** 49

