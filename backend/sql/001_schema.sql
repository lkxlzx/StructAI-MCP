PRAGMA foreign_keys = ON;

-- =============================================================================
-- StructAI 持久层 Schema —— SQLite 完整 DDL
-- =============================================================================
-- 来源（唯一真源）：《StructAI MCP V2.1 设计框架规范》§4
-- 上位文档：《StructAI 架构边界与融合规范 v1.0（总纲）》§4.1 / §4.2 / §4.5 / §4.7 / §4.8
-- 数据库基线：SQLite 3.x（PostgreSQL 可迁移）
--
-- 表数量：49
-- 索引数量：57（CREATE INDEX / CREATE UNIQUE INDEX，含 1 个部分索引 ux_default_model）
--
-- ---------------------------------------------------------------------------
-- 全局约定
-- ---------------------------------------------------------------------------
-- 时间（总纲 §4.5.1 / V2.1 §3.2）：
--   * 时间戳一律 UTC 存储，类型 DATETIME；
--   * created_at / updated_at 由 ORM 层（SQLAlchemy default / onupdate）维护；
--   * 本 DDL 不定义任何 CREATE TRIGGER（保持 SQLite / PostgreSQL 可迁移性）；
--   * 此处 DEFAULT CURRENT_TIMESTAMP 仅为裸 SQL 建库时的兜底，生产路径由 ORM 赋值覆盖。
-- 追加型表（V2.1 §3.3 / 裁决 C-12）：不设 updated_at ——
--   task_events / system_logs / audit_logs / user_roles / role_permissions。
-- 主键（总纲 §4.1.1）：一律 INTEGER PRIMARY KEY AUTOINCREMENT；
--   单例配置表为例外，使用 INTEGER PRIMARY KEY CHECK(id = 1)。
-- 命名（总纲 §4.6）：表名 snake_case 复数；索引名 ix_<表>_<列> / ux_<表>_<列>。
-- 加密（总纲 §4.7.1）：models.api_key_encrypted、midas_clients.api_key_encrypted、
--   midas_clients.access_token_encrypted、mcp_client_credentials.secret_hash、
--   system_configs.config_value（is_secret = 1 时）、assistant_plans.confirmation_token_hash。
--
-- ---------------------------------------------------------------------------
-- 建表顺序（拓扑排序说明）
-- ---------------------------------------------------------------------------
-- 本文件已按依赖顺序重排 V2.1 §4 的 CREATE TABLE 语句，使每一个
-- FOREIGN KEY ... REFERENCES 的目标表都先于本表建立。相对 V2.1 §4 原文的改动：
--   1) adapters 提前到 midas_clients 之前
--      （midas_clients.adapter_code → adapters.code，原文为前向引用）
--   2) assistant_sessions 提前到 assistant_files 之前
--      （assistant_files.session_id → assistant_sessions.session_id，原文为前向引用）
--   3) assistant_intents → assistant_plans → assistant_messages 的顺序，
--      使 assistant 簇的真环只保留 1 条回边（详见下方 assistant 块首注释）
--   4) reports 移到 assistant_files 之后
--      （reports.file_id → assistant_files.file_id，原文为前向引用）
-- SQLite 在 PRAGMA foreign_keys = ON 下容忍前向引用（只要执行期被引用表已存在），
-- 因此原文可直接执行；但 Alembic 自动生成迁移时必须按上述拓扑序，
-- 否则需要 use_alter / 手工拆分 op.create_table。
--
-- 幂等：全部 CREATE TABLE / CREATE INDEX 均带 IF NOT EXISTS。
-- 种子数据：见同目录 002_seed.sql（本文件为纯 DDL，不含任何数据写入语句）。
-- =============================================================================

BEGIN;

-- =========================================================
-- 1. 用户、角色、权限（5 张表）
-- =========================================================

-- users：平台用户账号，承载登录凭据、在线状态与失败锁定策略。
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    -- 所属部门（总纲 §4.2.5 补充的用户表字段）。一个用户**只属于一个部门**，
    -- 因此这里是一个纯 TEXT 标签，不建 departments 表、不建关联表；它与
    -- midas_clients.department（本文件 §5）**按值匹配**，二者共用同一词表。
    -- 可空、无默认值：NULL 表示「未分配」这一真实状态，**不等于**「任意部门」——
    -- 未分配部门的用户不能使用 visibility='department' 的实例
    -- （《MIDAS API 对接规范》§2.5.4 第 5 条：跨租户访问必须显式授予，不得假定）。
    department      TEXT,
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

-- roles：RBAC 角色字典（super_admin / engineer / analyst / visitor）。
CREATE TABLE IF NOT EXISTS roles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    code        TEXT NOT NULL UNIQUE,
    description TEXT,
    is_system   INTEGER NOT NULL DEFAULT 0,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- permissions：权限码字典，编码规范 <module>:<action>（总纲 §4.8.1）。
CREATE TABLE IF NOT EXISTS permissions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    module      TEXT NOT NULL,
    action      TEXT NOT NULL,
    description TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- user_roles：用户 ↔ 角色关联（追加型表，无 updated_at，裁决 C-12）。
CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    PRIMARY KEY(user_id, role_id),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE CASCADE
);

-- role_permissions：角色 ↔ 权限关联（追加型表，无 updated_at，裁决 C-12）。
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id       INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    PRIMARY KEY(role_id, permission_id),
    FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY(permission_id) REFERENCES permissions(id) ON DELETE CASCADE
);

-- =========================================================
-- 2. 系统配置（3 张表）
-- =========================================================

-- system_configs：键值型系统配置；is_secret = 1 时 config_value 须加密（总纲 §4.7.1）。
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

-- security_configs：安全策略单例表（V2.1 新增 rate_limit_* 三列，裁决 B-7）。
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

-- service_configs：服务运行参数单例表；log_level 归属本表（裁决 A-2）。
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
-- 3. Adapter 注册（1 张表）
-- =========================================================

-- adapters：MIDAS 系列软件 Adapter 注册表，是 capabilities / tool_interfaces 的归属根。
-- 【顺序调整】原文位于 midas_clients 之后，此处提前以满足 midas_clients.adapter_code 外键。
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
-- 4. MCP Server / Client（3 张表）
-- =========================================================

-- mcp_servers：StructAI 自身 MCP Server 实例（V2.1 新增 started_at，裁决 A-2）。
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

-- mcp_clients：接入 StructAI MCP Server 的外部 MCP Client 会话记录。
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

-- mcp_client_credentials：MCP Client 凭据（V2.1 新增，裁决 B-1）；
-- 一个 client 可持有多个凭据（轮换期并存）；secret_hash 为单向哈希（总纲 §4.7.1）。
CREATE TABLE IF NOT EXISTS mcp_client_credentials (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    mcp_client_id INTEGER NOT NULL,
    secret_hash   TEXT NOT NULL,
    secret_prefix TEXT,
    scopes_json   TEXT,
    expires_at    DATETIME,
    last_used_at  DATETIME,
    revoked_at    DATETIME,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(mcp_client_id) REFERENCES mcp_clients(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_mcp_client_credentials_client
ON mcp_client_credentials(mcp_client_id);

-- =========================================================
-- 5. MIDAS Client（1 张表）
-- =========================================================

-- midas_clients：MIDAS 软件连接配置（api_key_encrypted / access_token_encrypted 须加密）。
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
-- 6. AI Provider / Model（2 张表）
-- =========================================================

-- model_providers：LLM 服务提供方字典（openai_compatible 等）。
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

-- models：AI 模型实例配置；api_key_encrypted 须加密（总纲 §4.7.1）。
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

-- 部分唯一索引：全局最多一个未删除的默认模型（is_default = 1）。
CREATE UNIQUE INDEX IF NOT EXISTS ux_default_model
ON models(is_default)
WHERE is_default = 1 AND deleted_at IS NULL;

-- =========================================================
-- 7. MCP Tool（1 张表）
-- =========================================================

-- tools：对 LLM 暴露的稳定 MCP Tool 注册表（version 默认 '2.1'，裁决 C-5）。
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
-- 8. Schema Registry（1 张表）
-- =========================================================

-- schemas：JSON Schema 注册表；唯一键为 (schema_code, version) 以支持多版本（裁决 B-2）。
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
-- 9. MIDAS 二级 Interface（1 张表）
-- =========================================================

-- tool_interfaces：MIDAS 二级 Endpoint 映射（裁决 B-3）。
-- tool_id 允许 NULL —— 同一 Endpoint 可被多个 Tool 共享；唯一键为 (adapter_code, interface_code)。
CREATE TABLE IF NOT EXISTS tool_interfaces (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id           INTEGER,
    adapter_code      TEXT NOT NULL,
    interface_code    TEXT NOT NULL,
    method            TEXT NOT NULL,
    endpoint          TEXT NOT NULL,
    -- 请求体外层包装键：'Assign'（/db/*）、'Argument'（/doc/* 及多数 design/post 动作），
    -- NULL 表示该端点无请求体（《MIDAS API 对接规范》§3.1）。
    -- 注意：/post/* 与 /DESIGN/**/TABLE 的 URI 是共享的，靠 Argument 内的
    -- TABLE_TYPE 选择目标，因此 interface_code 必须按表类型区分，不能按 URI。
    request_wrapper   TEXT,
    -- GET 响应的最外层键（如 'NODE'）；源文档未给 GET 响应体时为 NULL（对接规范 §3.2）。
    response_root_key TEXT,
    operation         TEXT NOT NULL,
    resource          TEXT,
    -- ===== 三层分类（v1.0 修订，《总纲》§4.2.12 / 对接规范 §7.1）=====
    -- product_scope = 该端点适用于哪个 MIDAS 产品
    -- domain        = 业务域（前端一级菜单 / LLM 第一层筛选）
    -- feature       = 手册章节（前端二级菜单 / LLM 第二层筛选）
    --
    -- 三者是**列而非 metadata_json 里的字段**：它们都是过滤与分组条件
    -- （product_scope 在每次能力解析时都要过滤），索引友好是硬要求。
    --
    -- product_scope 默认 'unknown'：手册的产品标注**不可信**——对接规范 §3.5
    -- 第 15 条实测，47 条声明「Civil 专属」的端点中 32 条在 Gen NX 上也能应答。
    -- 因此「尚未实机验证」必须是一个**显式状态**，而不是假装知道。
    product_scope     TEXT NOT NULL DEFAULT 'unknown'
                      CHECK(product_scope IN ('gen','civil','designer','both','unknown')),
    -- domain 可空（未归域），且**不需要写 IS NULL OR**：SQL 的 CHECK 只在条件
    -- 求值为 FALSE 时失败，而 NULL IN (...) 求值为 NULL —— 三值逻辑下通过。
    -- 这里刻意与 ORM 的 enum_check 保持**同一种形式**：测试夹具用
    -- Base.metadata.create_all 建表（tests/conftest.py），形式不同会让
    -- 「测试用的 schema」与「本文件产出的 schema」约束不一致。
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

-- 三层分类的复合索引：能力解析要按产品过滤，前端要按 域→章 分组。
CREATE INDEX IF NOT EXISTS ix_tool_interfaces_scope
ON tool_interfaces(product_scope, domain, feature);

-- =========================================================
-- 10. Capability Registry（2 张表）
-- =========================================================

-- capabilities：能力语义注册表（resource + action 决定该 Adapter 能做什么）。
--
-- v1.0 修订两处（表为空时改，零迁移成本）：
--   * 新增 tool_id —— 此前 `Capability.tool`（MCP 工具名）在库里**没有归宿**。
--     它**不能**从 tool_interfaces.tool_id 推导：实测 /post/TABLE 的 POST 被
--     midas_execute 与 midas_query 共用（裁决 B-3 说的正是这种共用），
--     而 platform-owned 的 24 行根本没有 interface。所以它是能力自身的属性。
--   * adapter_code 改为**可空** —— 7 个 midas_task 能力是 platform-owned
--     （对接规范 §2.5.1：MIDAS 没有任务端点），没有 adapter 可指。
--     NULL 使 ux_capability 失去对它们的唯一性（SQL 里 NULL 互不相等），
--     因此补一条**部分唯一索引**只管 NULL 那一半。
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
-- 同一 capability_code 可对每个 adapter 各存一行 —— 这正是多产品扩展所需的键
-- （node.list 在 gen 与 civil 上各有一行），也是本表与 `_TABLE` 目前不一致之处。
CREATE UNIQUE INDEX IF NOT EXISTS ux_capability
ON capabilities(adapter_code, capability_code);

-- platform-owned 的能力（adapter_code IS NULL）：capability_code 全局唯一。
-- 没有它，NULL 互不相等的语义会让 `task.get` 被插入两次而无人察觉。
CREATE UNIQUE INDEX IF NOT EXISTS ux_capability_platform
ON capabilities(capability_code) WHERE adapter_code IS NULL;

CREATE INDEX IF NOT EXISTS ix_capabilities_resource_action
ON capabilities(resource, action);

CREATE INDEX IF NOT EXISTS ix_capabilities_tool
ON capabilities(tool_id);

-- capability_interfaces：Capability ↔ Interface 多对多关联（V2.1 新增，裁决 B-3）。
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
-- 11. Task（2 张表）
-- =========================================================

-- tasks：统一异步任务表。一切长任务在此登记，可查询 / 取消 / 重试 / 订阅。
--   type   = 业务任务类型（封闭枚举 14 值，V2.1 §26.2 / 裁决 A-6）
--   action = 具体动作，复用 MCP action 词表（V2.1 §6.3）
--   status = 总纲 §4.2.1 任务状态词表（带 CHECK）
--   request_id 承载总纲 §4.1.5 追溯链首端：request_id → task_id → adapter_request_id
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

-- task_events：任务事件流，供 midas_task action=events 轮询
-- （追加型表，无 updated_at，裁决 C-12）。
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
-- 12. Logs（2 张表）
-- =========================================================

-- system_logs：运行日志；adapter_request_id 承载总纲 §4.1.5 追溯链末端
-- （追加型表，无 updated_at，裁决 C-12）。
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

-- audit_logs：操作审计日志，记录 before/after 快照
-- （追加型表，无 updated_at，裁决 C-12）。
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
-- 13. Backup / Import / Export（5 张表）
-- =========================================================

-- backup_configs：备份策略单例表；storage_path 为平台自适应相对路径（裁决 C-10）。
CREATE TABLE IF NOT EXISTS backup_configs (
    id              INTEGER PRIMARY KEY CHECK(id = 1),
    enabled         INTEGER NOT NULL DEFAULT 1,
    frequency       TEXT NOT NULL DEFAULT 'daily',
    retention_count INTEGER NOT NULL DEFAULT 7,
    storage_path    TEXT NOT NULL DEFAULT './data/backups',
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- backups：备份记录（backup_id 使用 bk_ 前缀，总纲 §4.1.3）。
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

-- data_exports：数据导出记录（export_id 使用 exp_ 前缀，总纲 §4.1.3）。
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

-- data_imports：数据导入记录（import_id 使用 imp_ 前缀，总纲 §4.1.3）。
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

-- cleanup_configs：数据清理策略单例表（任务 / 日志 / 审计保留天数）。
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
-- 14. Session / API Token（1 张表）
-- =========================================================

-- sessions：登录会话与 API Token 哈希；expires_at 由 security_configs.session_timeout_minutes 派生。
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
-- 15. Project（1 张表，V2.1 新增，裁决 N-7）
-- =========================================================

-- projects：工程项目实体；assistant_sessions 与 reports 通过 project_id 归属本项目。
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

-- =========================================================
-- 16. AI 工程助手（14 张表，V2.1 新增，来源 v1.1 §98 + 总纲 §6.1）
-- =========================================================
--
-- 【建表顺序与真环说明 —— 必读】
--
-- 本簇存在一个无法用重排消除的真环，涉及三张表：
--
--     assistant_intents.message_id  →  assistant_messages(message_id)
--     assistant_messages.intent_id  →  assistant_intents(intent_id)
--     assistant_messages.plan_id    →  assistant_plans(plan_id)
--     assistant_plans.intent_id     →  assistant_intents(intent_id)
--
-- 即依赖关系为：messages 依赖 intents 与 plans；intents 依赖 messages；plans 依赖 intents。
-- 这是一个三节点环（intents → messages → plans → intents）。
--
-- 本文件采用的顺序为：
--     assistant_sessions → assistant_files → assistant_intents
--                        → assistant_plans   → assistant_messages → 其余
--
-- 该顺序把回边数量压到**最小值 1 条**：仅
--     assistant_intents.message_id → assistant_messages(message_id)
-- 是前向引用（目标表在本文件中稍后创建）。其余三条边均满足「被引用表已存在」。
-- 任何线性顺序都至少要留下 1 条回边（三节点环不可能线性化）。
--
-- SQLite：在 PRAGMA foreign_keys = ON 下，建表语句本身**不校验**被引用表是否存在
--   （外键在 DML 执行期解析），因此本顺序可直接执行；V2.1 §4 原文的顺序同样可执行。
-- Alembic：自动生成的迁移会因该回边失败或需要 use_alter，必须显式做拓扑排序，
--   并对 assistant_intents.message_id 这一条外键使用
--   `op.create_foreign_key(..., use_alter=True)`，或先建表后补外键。
--
-- 另有两处前向引用已由本文件的全局重排消除（不再位于本簇内）：
--     assistant_files.session_id → assistant_sessions(session_id)  （sessions 已提前）
--     reports.file_id            → assistant_files(file_id)        （reports 已后置，见第 17 节）
-- =========================================================

-- --- 16.1 会话（裁决 N-25：midas_client_id → midas_clients(id)）---
-- assistant_sessions：AI 工程助手会话；status 取值见总纲 §4.2.4。
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

-- --- 16.2 文件本体（裁决 N-23：files = 上传与产物文件本体）---
-- assistant_files：上传件与产物文件本体（file_id 使用 file_ 前缀，总纲 §4.1.3）。
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

-- --- 16.3 工程意图 ---
-- assistant_intents：由自然语言解析出的工程意图与缺失参数。
-- 【回边】message_id → assistant_messages(message_id) 为本簇唯一前向引用，见块首说明。
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

-- --- 16.4 执行计划（status 取值见总纲 §4.2.2）---
-- assistant_plans：可执行计划与高风险确认状态；
-- confirmation_token_hash 为一次性令牌的单向哈希（总纲 §4.7.1）。
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
    confirmation_token_hash  TEXT,
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

-- --- 16.5 对话消息 ---
-- assistant_messages：会话消息流；role 取值见总纲 §4.2.9。
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

-- --- 16.6 计划步骤（裁决 N-1：可执行形式）---
-- assistant_plan_steps：可直接翻译为 MCP 调用的步骤；status 取值见总纲 §4.2.3。
CREATE TABLE IF NOT EXISTS assistant_plan_steps (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id       TEXT NOT NULL,
    step_no       INTEGER NOT NULL,
    step_id       TEXT,
    name          TEXT,
    tool_name     TEXT,
    action        TEXT,
    resource      TEXT,
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

-- --- 16.7 产物语义记录（裁决 N-23：outputs = 关联 file + 类型 + 元数据）---
-- assistant_outputs：产物语义层，指向 assistant_files 中的文件本体。
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
-- assistant_drawing_tasks：图纸识别任务；status 为总纲 §4.2.7 词表（tasks.status 子集）。
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
-- assistant_drawing_objects：从图纸抽取出的构件对象及其到模型的映射。
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

-- --- 16.10 识图设置（单例表，补 v1.1 §76 缺表）---
-- assistant_drawing_settings：识图开关与置信度阈值（全局唯一一行）。
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
-- assistant_templates：工程模板字典（参数 Schema + 计划模板）。
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
-- assistant_examples：示例算例，引用 assistant_templates。
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

-- --- 16.13 历史记录（细粒度审计）---
-- assistant_history：AI 全链路细粒度审计；type 取值见总纲 §4.2.9。
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
-- assistant_commands：常用工程指令字典（提示词模板 + 参数 Schema）。
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
-- 17. Report（1 张表，V2.1 新增，裁决 B-5）
-- =========================================================
-- 【顺序调整】原文位于 assistant 簇之前，此处后置以满足 reports.file_id → assistant_files(file_id)。
-- reports：报告实体；status 与 backups / data_exports / data_imports 对齐（总纲 §4.2.5）。
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
-- 18. 规范知识库（2 张表，V2.1 新增，裁决 N-19）
-- =========================================================

-- code_standards：设计规范主表；category 取值见总纲 §4.2.10。
CREATE TABLE IF NOT EXISTS code_standards (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT NOT NULL UNIQUE,
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

-- code_clauses：规范条文；severity 取值见总纲 §4.2.10。
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
-- 19. 地区荷载规范参数库（1 张表，V2.1 新增，裁决 N-20）
-- =========================================================

-- load_parameter_library：地区荷载参数库；parameter_type 取值见总纲 §4.2.10。
-- standard_code 存 code_standards.code 的字符串值，按 V2.1 §5.4 不设外键。
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

COMMIT;

-- =============================================================================
-- 建表完成：49 张表 / 57 个索引。
-- 种子数据请执行 002_seed.sql（34 权限 / 4 角色 / 角色权限映射 / 5 张单例表 /
-- 4 部规范 / 3 条常用指令 / 4 个模板 / 2 个示例案例）。
-- =============================================================================
