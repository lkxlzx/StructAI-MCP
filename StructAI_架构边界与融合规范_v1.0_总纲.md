# StructAI 架构边界与融合规范 v1.0（总纲）

**文档性质：** 架构总纲 / 唯一裁决源  
**所属平台：** StructAI  
**适用范围：** 全部 StructAI 子系统  
**生效版本：** 与《StructAI MCP V2.1 设计框架规范》《StructAI 管理器 API 接口设计规范 v1.2》配套使用

---

# 0. 本规范的定位

## 0.1 三件套关系

StructAI 的设计由**三份文档**构成，各管一层，互不重定义：

| 文档 | 管什么 | 性质 |
|---|---|---|
| **本规范（总纲）** | 层次划分、所有权边界、跨层统一约定、冲突裁决、实施排期 | 裁决源 |
| **《StructAI MCP V2.1 设计框架规范》** | 持久层 DDL、MCP 4 Tool 契约、Adapter / Capability / Interface 契约、错误码注册表、状态词表 | 设计框架 |
| **《StructAI 管理器 API 接口设计规范 v1.2》** | `/api/v1/*` REST/SSE 接口、页面取数映射、UI 展示状态 | 接口契约 |

## 0.2 冲突优先级

```text
本规范（总纲）
     ↓ 高于
V2.1 设计框架规范
     ↓ 高于
v1.2 接口设计规范
```

**任何跨文档矛盾，一律以本规范第 5 章「冲突裁决表」为准。** 三份文档中未列入裁决表的分歧，按第 3 章「所有权矩阵」判定归属，由所有者一方定稿。

## 0.3 唯一真源原则

> **每一个表、字段、枚举、错误码、ID 前缀、权限码，全局只允许有一个所有者。**

非所有者文档**只能引用，不得重定义**。引用方式：

```text
参见《V2.1 设计框架规范》§x.y
```

禁止出现「A 文档定义了一套、B 文档又定义了一套」的情况——这正是 V2.0 与 v1.1 产生 40 余处矛盾的根因。

---

# 1. 两份原始文档的性质辨析

融合前必须先承认一个事实：**V2.0 与 v1.1 不是版本迭代关系，而是两个不同层次的东西。**

| | V2.0 文档 | v1.1 文档 |
|---|---|---|
| **它是什么** | **设计框架** | **UI 原型还原的 API** |
| **回答什么问题** | 系统怎么运转 | 页面怎么取数 |
| **管什么层** | 持久层 + 智能编排层 + 适配层 | 表现层契约 |
| **服务对象** | 后端框架、LLM Agent、MIDAS 软件 | Vue 前端、管理端运维 |
| **内容主体** | 28 张表 DDL、4 个 MCP Tool JSON Schema、Adapter Protocol | 101 节 REST/SSE 接口、页面映射 |
| **是否关心 UI** | 不关心 | 全部围绕 UI 原型 |

## 1.1 因此产生的两类错误

把「框架」和「UI API」当成同一层来写，必然产生两类越界：

**类型一：UI API 文档越界定义了框架的东西**

```text
v1.1 §98  列出 13 张 assistant_* 表       ← 表结构属于框架层
v1.1 §96  定义助手状态机                  ← 状态词表属于框架层
v1.1 §20.1 用 ?type=calculate 过滤        ← 任务语义属于框架层
v1.1 §50  另立一套错误码                  ← 错误码注册表属于框架层
```

**类型二：框架文档缺失 UI API 新增的层**

```text
v1.1 §65-§101 新增 AI 工程助手完整模块
V2.0 全文出现「assistant」0 次
     ↓
数据层完全不知道 AI 层存在 → 13 张表无处安放
```

## 1.2 融合的正确做法

```text
不是「合并成一份」
而是「划清边界 + 对齐交叉处」
```

具体三步：

1. **定所有权**——每个关注点指定唯一所有者（第 3 章）
2. **定约定**——跨层共用的 ID / 状态 / 错误码 / 时间 / 命名，统一到本规范（第 4 章）
3. **逐条裁决**——现有 40 余处矛盾逐条给出结论（第 5 章）

---

# 2. 七层架构模型

## 2.1 分层

```text
┌──────────────────────────────────────────────────────────────┐
│ L1  表现层         UI 原型（Vue）                             │
│                    首页 / MIDAS客户端 / MCP服务器 / 工具与接口 │
│                    任务监控 / 日志中心 / 系统设置 / AI工程助手 │
│                    所有者：v1.2 §54 §95                        │
└───────────────────────────┬──────────────────────────────────┘
                            │ REST / SSE
┌───────────────────────────▼──────────────────────────────────┐
│ L2  管理接口层     /api/v1/*                                  │
│                    REST 门面 · SSE 流 · 统一信封 · 分页        │
│                    所有者：v1.2                                │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│ L3  领域服务层     Service Layer（共享，无对外契约）           │
│                    AuthService / ModelService / TaskService   │
│                    ToolService / ReportService / ...          │
│                    所有者：V2.1（结构）                        │
│                    ★ REST 与 MCP 两条路径在此汇合              │
└──────────┬────────────────────────────────┬──────────────────┘
           │                                │
┌──────────▼──────────────┐   ┌─────────────▼──────────────────┐
│ L4a 智能编排层          │   │ L4b 管理编排层                  │
│  AI 工程助手            │   │  MCP 4 Tools                    │
│  意图→校验→计划→确认    │   │  midas_query / midas_model      │
│  所有者：v1.2 §62-§91   │   │  midas_execute / midas_task     │
│  （接口）               │   │  所有者：V2.1 §7-§11            │
│  V2.1（数据与状态）     │   │                                 │
└──────────┬──────────────┘   └─────────────┬──────────────────┘
           └────────────────┬───────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ L5  适配层         Capability Resolver                        │
│                    Adapter Registry                           │
│                    Tool Interface Mapping                     │
│                    所有者：V2.1 §12-§22                        │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ L6  集成层         MIDAS Gen / Civil / FEA NX / CSI / ...     │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ L7  持久层         SQLite（PostgreSQL 可迁移）                 │
│                    49 张表                                     │
│                    所有者：V2.1 §4                             │
└──────────────────────────────────────────────────────────────┘
```

## 2.2 横切关注点

以下能力跨越所有层，**注册表式内容统一由 V2.1 拥有，接口表现由 v1.2 拥有**：

| 横切能力 | 内容所有者 | 接口所有者 |
|---|---|---|
| 认证 / RBAC | V2.1（权限码种子） | v1.2（接口鉴权要求） |
| 错误码 | **本规范 §4.4**（注册表） | v1.2（引用） |
| 状态词表 | **本规范 §4.2**（词表） | v1.2（引用 + UI 映射） |
| ID 命名 | **本规范 §4.1** | 两者引用 |
| 任务引擎 | V2.1 | v1.2（REST 门面） |
| 审计日志 | V2.1（表） | v1.2（查询接口） |
| 统一信封 | **本规范 §4.3** | v1.2（实现） |
| 加密与密钥 | V2.1 §30 | v1.2（回显规范） |

## 2.3 两条数据流（关键）

融合后必须同时成立，且**在 L3 汇合**：

**路径 A — 管理端 / 运维（人操作）**

```text
运维人员
  → UI 页面
  → /api/v1/*        （v1.2 REST 门面）
  → Service Layer
  → Adapter
  → MIDAS
```

**路径 B — AI 工程助手（LLM 编排）**

```text
自然语言 / 图纸
  → /api/v1/assistant/*   （v1.2 AI 门面）
  → 意图解析 → 参数校验 → Execution Plan → 高风险确认
  → MCP 4 Tools           （V2.1 契约）
  → Capability Resolver
  → Adapter Registry
  → Adapter
  → MIDAS
```

**路径 C — 外部 LLM Agent（直连 MCP）**

```text
外部 AI Agent
  → POST /mcp            （MCP Protocol Endpoint）
  → MCP 4 Tools
  → Capability Resolver → Adapter → MIDAS
```

三条路径**共用 L3 与 L5**，禁止各自实现一套业务逻辑。

---

# 3. 所有权矩阵

> 本表是三份文档的边界法。任何新增内容必须先在本表登记归属。

| # | 关注点 | 唯一所有者 | 其他文档如何引用 |
|---|---|---|---|
| 1 | 表结构 / DDL / 索引 / 外键 | **V2.1 §4** | v1.2 只引用表名与字段名 |
| 2 | 表数量与数据字典 | **V2.1** | v1.2 不得列出表清单 |
| 3 | MCP Tool 名称与 JSON Schema | **V2.1 §7-§11** | v1.2 §37 §92 引用 |
| 4 | MCP 返回信封 | **V2.1 §11** | v1.2 不适用 |
| 5 | Capability 语义与编码 | **V2.1 §16** | v1.2 §16 引用 |
| 6 | Tool Interface / Endpoint 映射 | **V2.1 §17** | v1.2 §13 §14 引用 |
| 7 | Adapter Protocol 与元数据 | **V2.1 §13 §15** | v1.2 §10 引用 |
| 8 | Adapter 生命周期与状态 | **V2.1 §14** | v1.2 §9 §10 引用 |
| 9 | **任务状态词表** | **本规范 §4.2.1** | V2.1 收录、v1.2 引用 |
| 10 | **执行计划状态词表** | **本规范 §4.2.2** | V2.1 收录、v1.2 引用 |
| 11 | **错误码注册表** | **本规范 §4.4** | V2.1 收录、v1.2 引用 |
| 12 | **ID 命名规范** | **本规范 §4.1** | V2.1 收录、v1.2 引用 |
| 13 | **统一响应信封（REST）** | **本规范 §4.3** | v1.2 实现 |
| 14 | 时间与量纲约定 | **本规范 §4.5** | 两者引用 |
| 15 | 命名与大小写约定 | **本规范 §4.6** | 两者引用 |
| 16 | 加密字段清单与回显规范 | **本规范 §4.7** | V2.1 §30、v1.2 §9.3 |
| 17 | 权限码清单 | **本规范 §4.8** | V2.1 种子数据、v1.2 鉴权声明 |
| 18 | REST 路径与请求/响应体 | **v1.2** | V2.1 不定义 REST 路径 |
| 19 | 页面与 API 映射 | **v1.2 §54 §95** | — |
| 20 | SSE 事件名与载荷 | **v1.2 §21 §22.3 §71** | V2.1 §26 只声明能力 |
| 21 | **UI 展示状态机** | **v1.2 §93** | V2.1 不落库 |
| 22 | 实施排期与优先级 | **本规范 §7** | 两份文档删除各自的优先级章节 |
| 23 | 验收标准 | **本规范 §8** | 两份文档删除各自的验收章节 |
| 24 | 工程规范知识库内容 | **V2.1**（表） | v1.2 §79 引用 |

## 3.1 越界判定规则

出现以下情况即判定为**越界**，必须回退到所有者文档：

```text
v1.2 中出现 CREATE TABLE / 字段定义        → 越界，移入 V2.1
v1.2 中出现 MCP Tool 的 action/resource 枚举 → 越界，移入 V2.1
v1.2 中出现新的错误码字符串                 → 越界，移入 §4.4
v1.2 中出现新的任务状态取值                 → 越界，移入 §4.2
V2.1 中出现 /api/v1/... 的具体请求体        → 越界，移入 v1.2
V2.1 中出现页面名称或 UI 交互描述           → 越界，移入 v1.2
V2.1 中出现新的 ID 前缀                     → 越界，移入 §4.1
```

---

# 4. 跨层统一约定

> 本章是**全局唯一真源**。V2.1 与 v1.2 必须逐字收录，不得改写。

## 4.1 ID 命名规范

### 4.1.1 数据库主键

```text
一律 INTEGER PRIMARY KEY AUTOINCREMENT
```

### 4.1.2 业务 ID 总则

```text
<前缀>_<yyyymmdd>_<6位十进制序号>
```

示例：`req_20260925_000001`

### 4.1.3 前缀清单（封闭集合）

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
| `proj_` | 项目 ID | `projects.project_id` | §4.1（v1.0.1 补齐） |
| `out_` | AI 产物 ID | `assistant_outputs.output_id` | §4.1（v1.0.1 补齐） |
| `hist_` | AI 历史记录 ID | `assistant_history.history_id` | §4.1（v1.0.1 补齐） |

### 4.1.4 关键裁决：取消任务子类型前缀

> **原文档中的 `task_ai_xxx` / `task_calc_001` / `analysis_xxx` / `optimization_xxx` / `export_xxx` / `report_xxx` / `model_import_xxx` / `drawing_xxx` 全部废止。**

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

### 4.1.5 追溯链

```text
request_id  →  task_id  →  adapter_request_id
```

三者必须能从任一端互相查到。`tasks` 表保存 `request_id`，`system_logs` 保存 `adapter_request_id`。

### 4.1.6 外键类型规则（v1.0.1 补齐）

外键列的 SQL 类型**由被引用表是否拥有业务 ID 列决定**，不得随意混用：

| 被引用表 | 有无业务 ID 列 | 外键列类型 | 典型外键 |
|---|---|---|---|
| `users` | 无 | **INTEGER** → `users.id` | `tasks.requested_by`、`audit_logs.user_id` |
| `models` | 无 | **INTEGER** → `models.id` | `tasks.model_id`、`assistant_sessions.model_id` |
| `midas_clients` | 无 | **INTEGER** → `midas_clients.id` | `tasks.midas_client_id`、`assistant_sessions.midas_client_id` |
| `model_providers` | 无 | **INTEGER** → `model_providers.id` | `models.provider_id` |
| `projects` | 有 `project_id` | **TEXT** → `projects.project_id` | `reports.project_id`、`assistant_sessions.project_id` |
| `assistant_files` | 有 `file_id` | **TEXT** → `assistant_files.file_id` | `reports.file_id`、`assistant_outputs.file_id` |
| `tasks` | 有 `task_id` | **TEXT** → `tasks.task_id` | `assistant_plans.task_id` |
| `assistant_sessions` | 有 `session_id` | **TEXT** → `assistant_sessions.session_id` | `assistant_messages.session_id` |
| `tools` | 有 `name` | **TEXT** → `tools.name` | `tasks.tool_name` |
| `adapters` | 有 `code` | **TEXT** → `adapters.code` | `tasks.adapter_code` |

> **修订说明：** 本规则为 v1.0 发布后补齐。§5.4 的裁决 N-6 曾笼统写成
> 「`project_id`、`file_id` 一律 INTEGER」，与 V2.1 §4 的实际 DDL 冲突
> （`projects.project_id`、`assistant_files.file_id` 均为 `TEXT UNIQUE` 业务 ID）。
> **经裁决：以 V2.1 §4 的 DDL 为准**（依据 §3 所有权矩阵第 1 行），
> N-6 的 INTEGER 要求**仅适用于 `model_id` 与 `midas_client_id`**。

## 4.2 状态词表

### 4.2.1 任务状态（`tasks.status`）

```text
queued      已入队
running     执行中
success     成功
failed      失败
cancelled   已取消
retrying    重试中
```

所有者：本规范。落库位置：`tasks.status`（带 CHECK 约束）。MCP `midas_task` 的 `status` 枚举与此**完全一致**。

### 4.2.2 执行计划状态（`assistant_plans.status`）

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

所有者：本规范。落库位置：`assistant_plans.status`（带 CHECK 约束）。

> **裁决**：v1.1 §71 的 `awaiting_confirmation` 采用本词表原样；v1.1 §96 的 `WAITING_CONFIRMATION` 改为引用本词表。

### 4.2.3 计划步骤状态（`assistant_plan_steps.status`）

```text
pending     待执行
running     执行中
completed   已完成
failed      失败
skipped     已跳过（依赖失败或人工跳过）
```

### 4.2.4 会话状态（`assistant_sessions.status`）

```text
active      活跃
archived    已归档
```

### 4.2.5 其他既有状态列（沿用 V2.1，并补 CHECK 约束）

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

> **补充（v1.0 修订）：用户表新增部门列 `users.department`。** `users` 表新增
> `department TEXT`（可空、无默认值），语义为「用户所属部门」。规则：
> **一个用户只属于一个部门**；`users.department` 与 `midas_clients.department`
> （V2.1 §4 同名字段）**按值匹配**——二者共用同一套部门标签，**不是外键**，因此
> 不新增 `departments` 表、也不新增用户↔部门关联表；**未分配部门的用户不能使用
> `visibility='department'` 的实例**，必须 fail closed，绝不「视为同一部门」。
> `NULL` 表示「未分配」这一真实状态，**不等于**「任意部门」。
> `midas_clients.visibility` 的取值与可见性规则由《MIDAS API 对接规范》§2.5.4
> 第 5 条拥有（`department` 实例可由部门标签匹配的主体使用）；本列是该规则中
> 「主体部门」一侧的落库位置。已存在的数据库由 `app.db.init_db` 的幂等补列步骤
> 一次性补齐并回填。

### 4.2.6 UI 展示状态机（v1.2 拥有，不落库）

v1.1 §96 的助手状态机：

```text
IDLE → UNDERSTANDING → PLANNING → VALIDATING → WAITING_CONFIRMATION
     → EXECUTING → VERIFYING → COMPLETED
异常：FAILED / CANCELLED / TIMEOUT
```

**裁决：这是前端展示状态机，由 v1.2 拥有，不落库。** 它必须由 `assistant_plans.status` + `assistant_plan_steps.status` + `tasks.status` 三者**派生**得出，映射关系由 v1.2 定义：

| UI 展示状态 | 派生自 |
|---|---|
| `IDLE` | 无进行中计划 |
| `UNDERSTANDING` | `assistant_intents` 生成中 |
| `PLANNING` | `plans.status = draft` |
| `VALIDATING` | `plans.status = validating` |
| `WAITING_CONFIRMATION` | `plans.status = awaiting_confirmation` |
| `EXECUTING` | `plans.status = executing` |
| `VERIFYING` | `plans.status = verifying` |
| `COMPLETED` | `plans.status = completed` |
| `FAILED` | `plans.status = failed` |
| `CANCELLED` | `plans.status = cancelled` |
| `TIMEOUT` | `plans.status = failed` 且 `error_code = TASK_TIMEOUT` |

### 4.2.7 识图任务状态（`assistant_drawing_tasks.status`）

```text
queued / running / success / failed / cancelled
```

即 §4.2.1 任务状态词表的**子集**。识图任务本身也是 `tasks` 表中的一条记录，此处仅冗余缓存其运行态。

### 4.2.8 项目状态（`projects.status`）

```text
active / archived
```

与 §4.2.4 会话状态同词表。

### 4.2.9 AI 模块辅助枚举

```text
assistant_messages.role          user / assistant / system
assistant_plans.risk_level       low / medium / high
assistant_plan_steps.status      （见 §4.2.3）
assistant_files.purpose          upload / output / temp
assistant_outputs.output_type    report / drawing / model_file / result
assistant_history.type           chat / intent / plan / execute / drawing / report
reports.report_type              calculation / analysis / design / check / custom
reports.status                   processing / success / failed
```

### 4.2.10 规范知识库与荷载参数枚举

```text
code_standards.category              national / industry / local / enterprise / international
code_clauses.severity                info / warning / error
load_parameter_library.parameter_type  wind / snow / seismic / temperature / live / dead / crane
```

> **补充说明（v1.0 修订）：** §4.2.7–§4.2.10 为 v1.0 首次发布后补齐。
> 原 V2.1 构建过程中发现总纲 §4.2 未覆盖这些表的取值，已在 V2.1 中按本规范精神临时定义并标注。
> 现正式收录于此，V2.1 与 v1.2 应以本节为唯一真源。

### 4.2.11 能力三层分类（`tool_interfaces`）

**背景。** `tool_interfaces` 从 32 个端点扩展到三个产品的全部接口（约 1,373 个条目 /
约 683 个唯一 URI）后，出现两个本规范此前无法回答的问题：

1. **同一个端点在不同产品上是否可用？** 连 Gen NX 却看到 Civil 专属端点，
   调用后只会得到 MIDAS 的 404 —— 而正确行为是「该能力不适用于本产品」。
2. **LLM 如何在上千个端点中定位？** 从 683 个里选一个不可行。

因此 `tool_interfaces` 新增三列，构成**严格三层**分类：

```text
product_scope          gen / civil / designer / both / unknown
  └── domain           8 个     ← 前端一级菜单；LLM 第一层筛选
        └── feature    27 个     ← 前端二级菜单；LLM 第二层筛选
              └── capability    端点
```

**三列均为封闭集合，且必须是「列」而非 `metadata_json` 里的字段** ——
`product_scope` 在**每次能力解析**时都要过滤，`domain`/`feature` 是前端的分组依据，
索引友好是硬要求。`metadata_json` 仅保留溯源与端点级怪癖
（`source_chapter` / `outer_key_means` / `new_file_get_put_only`）。

#### `product_scope`（封闭 5 值）

```text
gen / civil / designer / both / unknown        默认 unknown
```

| 取值 | 含义 |
|---|---|
| `gen` / `civil` / `designer` | 仅该产品可用 |
| `both` | 两个或以上产品均可用 |
| **`unknown`** | **尚未对实机验证** |

> **裁决：`unknown` 是**一等状态**，不是占位符。**
> 《对接规范》§3.5 第 15 条实测：手册声明「Civil 专属」的 47 个端点中，
> **32 个在 Gen NX 上也能应答**。手册的产品标注**不可信**，
> 因此「尚未验证」必须可表达，而不是假装知道。
>
> **`unknown` 的默认行为（裁决）：乐观放行 + `unverified` 警告。**
> 即：`unknown` 的能力**可见、可调用**，但信封 `warnings` 中带一条
> 「该端点的产品适用范围尚未实机验证」。理由：1,373 条逐条验证需要时间，
> 在验证完成前把大量能力隐藏起来，比带警告放行更糟。实机验证后收敛为
> `gen`/`civil`/`designer`/`both`。

#### `domain`（封闭 8 值）

```text
project / model / load / analysis / result / design / view / operation
```

#### `feature`（封闭 27 值）

手册章节，一一对应 `api_chapters/01..27`：

```text
doc                        db_project_structure       db_node_element
db_properties              db_boundary                db_static_loads
db_temperature_prestress   db_moving_loads            db_dynamic_loads
db_construction_stage      db_settlement_misc_loads   db_analysis_control
db_load_combinations       db_pushover                ope
view                       db_bridge                  post_pre_process
post_analysis_result_1     post_analysis_result_2     post_story_tables
post_th_hy_pushover        post_design                db_design
design_steel_kds41302022   design_rc_kds41202022      design_src_aiksrc2k
```

#### `feature` → `domain` 的映射（严格全函数）

每个 `feature` **恰好属于一个** `domain`，**不得**出现未归域或一对多：

| domain | features | 数量 |
|---|---|---|
| `project` | `doc`, `db_project_structure` | 2 |
| `model` | `db_node_element`, `db_properties`, `db_boundary`, `db_bridge` | 4 |
| `load` | `db_static_loads`, `db_temperature_prestress`, `db_moving_loads`, `db_dynamic_loads`, `db_construction_stage`, `db_settlement_misc_loads` | 6 |
| `analysis` | `db_analysis_control`, `db_load_combinations`, `db_pushover` | 3 |
| `result` | `post_pre_process`, `post_analysis_result_1`, `post_analysis_result_2`, `post_story_tables`, `post_th_hy_pushover` | 5 |
| `design` | `post_design`, `db_design`, `design_steel_kds41302022`, `design_rc_kds41202022`, `design_src_aiksrc2k` | 5 |
| `view` | `view` | 1 |
| `operation` | `ope` | 1 |
| | **合计** | **27** |

> 映射表的权威实现在 `app/core/constants.py` 的 `CAPABILITY_FEATURE_DOMAIN`，
> 与两个枚举放在一起，使「新增章节却忘记归域」不可能悄悄发生。

#### 约束与落库

- `product_scope`：`TEXT NOT NULL DEFAULT 'unknown'` + `CHECK`（封闭 5 值）
- `domain`：`TEXT` 可空（未归域）+ `CHECK`（封闭 8 值）
- `feature`：`TEXT` 可空
- 复合索引 `ix_tool_interfaces_scope(product_scope, domain, feature)`

> **可空列的 CHECK 写法：不得写 `IS NULL OR`。**
> SQL 的 `CHECK` 仅在条件求值为 **FALSE** 时失败，而 `NULL IN (...)` 求值为
> `NULL`，三值逻辑下**通过**。因此 `CHECK(domain IN (...))` 本身即允许 NULL。
> 两条建表路径必须用**同一种形式**：SQLite 走 `sql/001_schema.sql`，
> PostgreSQL 走 `Base.metadata.create_all`（即 ORM 的 `enum_check`），
> 形式不同会产生**两个部署路径约束不一致**的静默分歧。

> **产品过滤是数据范围过滤，不新增权限码。**
> 与 §4.8.2 的权限检查**叠加**生效，而非替代 —— 与《对接规范》§2.5.4 第 5 条
> 对实例归属的处理同理。不适用产品的能力以 **`CAPABILITY_NOT_SUPPORTED`（422）**
> 拒绝；该码已在 §4.4 封闭集合内，**不新增错误码**。

### 4.2.12 能力注册表的键控（`capabilities`）

为多产品扩展（Gen / Civil NX / Civil Designer）做准备时，发现 `capabilities`
表有三处无法表达的事。**三处均在表仍为空时修正，迁移成本为零。**

#### 一、`tool_id` —— 能力归属哪个 MCP 工具

**裁决：新增 `capabilities.tool_id INTEGER NOT NULL` → `tools.id`。**

此前 `Capability.tool`（`midas_query` / `midas_model` / `midas_execute` /
`midas_task`）**在数据库里没有归宿**。它**不能**从 `tool_interfaces.tool_id` 推导：

- 实测 `/post/TABLE` 的 POST 端点被 `midas_execute` **与** `midas_query` **共用**
  —— 这正是裁决 B-3 引入 `capability_interfaces` 多对多所要表达的情形；
- platform-owned 的能力（`midas_task` 的 7 个）**没有 interface**，无从推导。

因此「由哪个工具暴露」是**能力自身**的属性，落在 `capabilities` 上。

> 附带实测：`(resource, action)` 组合在现有 162 行中**唯一决定** `tool`（0 冲突）。
> 但那是**数据的巧合，不是 schema 的保证** —— 依赖它会重复本项目已犯过的
> 「用约定代替约束」的错误（`tasks.requested_by` 无写入方、MCP 与 REST 的归属
> 过滤分歧，皆属此类）。故取显式列，不取推导。

#### 二、`adapter_code` 可空 —— platform-owned 能力

**裁决：`capabilities.adapter_code` 改为**可空**。**

`midas_task` 的 7 个能力是 platform-owned（《对接规范》§2.5.1：MIDAS 没有任务
端点），**没有 adapter 可指**。原 `NOT NULL` 使它们**根本无法落库** ——
DB 驱动的能力表会静默丢掉整个 `midas_task` 工具。

#### 三、`capability_code` 按 adapter 唯一 —— 多产品的前提

**裁决：`ux_capability(adapter_code, capability_code)` 保持不变，并补部分唯一索引
`ux_capability_platform(capability_code) WHERE adapter_code IS NULL`。**

- **同一 `capability_code` 可按 adapter 各存一行**：`node.list` 在 gen / civil /
  designer 上各一行，互不覆盖。这是多产品扩展**必需**的键。
- 但 `adapter_code` 可空后，SQL 中 **NULL 互不相等**，复合唯一索引**管不住**
  platform-owned 那一半 —— `(NULL, 'task.get')` 可被插入两次而无人察觉。
  部分唯一索引补上这一半（SQLite 与 PostgreSQL 均支持部分索引）。

> **⚠️ 代码侧待修（已知偏离）：** `app/mcp/capabilities.py` 的 `_TABLE` 目前**只按
> `code` 键控**，且 `CapabilityResolver` 在调用方指定的 adapter 与能力的
> `adapter_code` 不一致时直接以 `CAPABILITY_NOT_SUPPORTED` 拒绝
> （`capability.py` §16.2）。这意味着**当前代码结构上无法表达「同一能力属于多个
> 产品」** —— 给 civil 再加一行 `node.list` 会覆盖 gen 那行。
>
> 该项是**阶段 3（能力表入库）的前置条件**，需将 `_TABLE` 改为按
> `(adapter_code, code)` 键控，并相应调整解析与查询接口。**本规范先行记录该
> 偏离**，以免实现落后于 schema 而无人察觉。

## 4.3 统一响应信封

### 4.3.1 REST 信封（v1.2 全部接口适用）

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {},
  "request_id": "req_20260925_000001",
  "timestamp": "2026-09-25T08:30:00+08:00"
}
```

失败：

```json
{
  "success": false,
  "code": "CAPABILITY_NOT_SUPPORTED",
  "message": "当前 MIDAS Adapter 不支持该操作",
  "details": {
    "adapter": "midas_gen",
    "resource": "node",
    "action": "create"
  },
  "data": null,
  "request_id": "req_20260925_000002",
  "timestamp": "2026-09-25T08:30:01+08:00"
}
```

**强制规则：**

- 所有 `application/json` 响应**必须**包含 `success` / `code` / `message` / `request_id` / `timestamp`
- 业务数据一律放在 `data` 中，**禁止顶层裸字段**
- 分页统一为 `data.items` + `data.pagination`
- 业务错误一律用 HTTP 200 + `success: false` 或对应 4xx/5xx + 同一信封

**唯一允许的例外（必须在 v1.2 中显式标注）：**

| 例外 | 原因 |
|---|---|
| SSE 流（`*/stream`） | `text/event-stream`，非 JSON |
| 文件下载（`*/download`、`/files/{id}`） | 二进制流 |
| 健康探针（`/health/ready`、`/health/live`） | 容器编排要求裸状态码 |
| OpenAPI（`/openapi.json`、`/docs`） | 框架生成 |

> 说明：`/health`（聚合健康检查）**不属于例外**，必须使用标准信封。

### 4.3.2 MCP 信封（V2.1 的 4 个 Tool 适用）

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

**两种信封不得混用。** v1.2 §17 的 `POST /tools/{name}/test` 是 REST 接口，必须使用 REST 信封，`latency_ms` 放入 `data`。

## 4.4 错误码注册表（唯一）

> 全部错误码在此定义。V2.1 与 v1.2 只能引用，**不得新增**。

### 4.4.1 认证与授权

| code | HTTP | 说明 |
|---|---|---|
| `AUTH_REQUIRED` | 401 | 未提供凭证 |
| `AUTH_INVALID` | 401 | 凭证无效（含旧名 `AUTH_FAILED`） |
| `AUTH_EXPIRED` | 401 | 凭证过期 |
| `PERMISSION_DENIED` | 403 | 权限不足 |
| `CONFIRMATION_INVALID` | 403 | 高风险确认令牌无效或过期 |

### 4.4.2 请求与资源

| code | HTTP | 说明 |
|---|---|---|
| `VALIDATION_ERROR` | 422 | 参数校验失败（含旧名 `VALIDATION_FAILED`） |
| `RESOURCE_NOT_FOUND` | 404 | 资源不存在 |
| `RESOURCE_CONFLICT` | 409 | 资源冲突 |
| `RATE_LIMITED` | 429 | 请求过于频繁 |

### 4.4.3 MCP 层

| code | HTTP | 说明 |
|---|---|---|
| `MCP_SERVER_ERROR` | 500 | MCP Server 内部错误 |
| `MCP_CLIENT_ERROR` | 502 | MCP Client 协议错误 |

### 4.4.4 Adapter 与能力

| code | HTTP | 说明 |
|---|---|---|
| `ADAPTER_NOT_FOUND` | 404 | Adapter 未注册 |
| `ADAPTER_UNAVAILABLE` | 503 | Adapter 不可用 |
| `CLIENT_NOT_CONNECTED` | 409 | MIDAS Client 未连接 |
| `CAPABILITY_NOT_SUPPORTED` | 422 | 当前软件/版本不支持该能力 |
| `INTERFACE_NOT_FOUND` | 404 | 二级 Interface 未映射 |

### 4.4.5 MIDAS 上游

| code | HTTP | 说明 |
|---|---|---|
| `MIDAS_CONNECTION_FAILED` | 502 | 连接失败 |
| `MIDAS_AUTH_FAILED` | 502 | 上游认证失败 |
| `MIDAS_API_ERROR` | 502 | 上游返回错误 |
| `MIDAS_CALCULATION_ERROR` | 502 | 计算失败 |

### 4.4.6 任务

| code | HTTP | 说明 |
|---|---|---|
| `TASK_NOT_FOUND` | 404 | 任务不存在 |
| `TASK_ALREADY_RUNNING` | 409 | 任务已在运行 |
| `TASK_CANCEL_FAILED` | 409 | 取消失败 |
| `TASK_TIMEOUT` | 504 | 任务超时（含旧名 `TIMEOUT`） |

### 4.4.7 AI 工程助手

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

### 4.4.8 AI 模型

| code | HTTP | 说明 |
|---|---|---|
| `MODEL_UNAVAILABLE` | 503 | 模型不可用 |
| `MODEL_TIMEOUT` | 504 | 模型超时 |
| `MODEL_API_ERROR` | 502 | 模型接口错误 |

### 4.4.9 数据与系统

| code | HTTP | 说明 |
|---|---|---|
| `DATABASE_ERROR` | 500 | 数据库错误 |
| `BACKUP_FAILED` | 500 | 备份失败 |
| `RESTORE_FAILED` | 500 | 恢复失败 |
| `IMPORT_VALIDATION_FAILED` | 422 | 导入文件校验失败 |
| `INTERNAL_ERROR` | 500 | 未归类内部错误 |
| `NOT_IMPLEMENTED` | 501 | 能力已定义未实现 |

### 4.4.10 旧名别名映射（迁移期兼容）

| 旧名 | 出处 | 归一为 |
|---|---|---|
| `AUTH_FAILED` | V2.0 §20 | `AUTH_INVALID` |
| `VALIDATION_FAILED` | V2.0 §20 | `VALIDATION_ERROR` |
| `TIMEOUT` | V2.0 §20 | `TASK_TIMEOUT` / `MODEL_TIMEOUT` |
| `INVALID_REQUEST` | V2.0 §20 | `VALIDATION_ERROR` |
| `MCP_*` 以外未列出者 | — | `INTERNAL_ERROR` |

## 4.5 时间与量纲约定

### 4.5.1 时间

```text
存储：UTC，DATETIME 类型
传输：ISO 8601 带时区偏移，默认 +08:00
```

- `created_at` / `updated_at` 由 **ORM 层**（SQLAlchemy `default` / `onupdate`）维护
- **不依赖数据库触发器**（保持 SQLite / PostgreSQL 可迁移性）
- API 输出时统一转换为配置时区（默认 `Asia/Shanghai`）
- 禁止在 DDL 中依赖 `CURRENT_TIMESTAMP` 作为唯一时间来源

### 4.5.2 数值量纲

| 类别 | 单位 | 说明 |
|---|---|---|
| 长度 / 坐标 | m | 模型坐标、跨度、高度 |
| 截面尺寸 | mm | H 型钢高宽、板厚 |
| 力 | kN | 集中力 |
| 分布荷载 | kN/m、kN/m² | 线荷载、面荷载 |
| 应力 | MPa（N/mm²） | 强度、容许应力 |
| 位移 | mm | 节点位移 |
| 质量 | kg / t | 钢材重量 |
| 进度 | 0–100 REAL | 百分比 |
| 置信度 | 0.0–1.0 REAL | 识图置信度 |

> 每个数值字段必须在 V2.1 的字段注释中标注单位。

## 4.6 命名与大小写约定

| 对象 | 规则 | 示例 |
|---|---|---|
| 表名 | snake_case，复数 | `tool_interfaces` |
| 字段名 | snake_case | `api_key_encrypted` |
| 索引名 | `ix_<表>_<列>` / `ux_<表>_<列>` | `ix_tasks_status` |
| REST 路径段 | kebab-case | `/audit-logs`、`/model-providers`、`/code-check`、`/dimension-check` |
| REST 资源 | **复数** | `/nodes`、`/elements`、`/materials` |
| MCP resource | **单数** | `node`、`element` |
| MCP action | 动词 | `create`、`list` |
| 权限码 | `module:action` | `model:read` |
| JSON 字段 | snake_case | `api_key_masked` |

### 4.6.1 单复数转换责任

```text
MCP 层：单数  node
REST 层：复数  nodes
     ↓
转换由 v1.2 的 Service 层入口 / Adapter Mapper 承担
禁止在数据库中存储两套资源名
```

## 4.7 加密与敏感字段

### 4.7.1 必须加密的字段（封闭清单）

```text
models.api_key_encrypted
midas_clients.api_key_encrypted
midas_clients.access_token_encrypted
mcp_client_credentials.secret_hash        （单向哈希）
system_configs.config_value               （当 is_secret = 1 时）
assistant_plans.confirmation_token_hash   （单向哈希）
```

算法：`AES-256-GCM`；主密钥：环境变量 `STRUCTAI_MASTER_KEY`。

### 4.7.2 回显规范（唯一）

敏感字段**一律**按以下结构回显，禁止返回明文：

```json
{
  "api_key_configured": true,
  "api_key_masked": "********"
}
```

字段名前缀按实际字段替换（`api_key_` / `access_token_` / `secret_`）。

> **裁决**：V2.0 §30 的 `{configured, masked}` 废止，统一采用 v1.1 §9.3 的带前缀形式。

## 4.8 权限码清单

### 4.8.1 编码规范

```text
<module>:<action>
```

### 4.8.2 完整清单（封闭集合）

| 模块 | 权限码 |
|---|---|
| system | `system:read` `system:write` `system:audit` ★新增 |
| model | `model:read` `model:create` `model:update` `model:delete` `model:test` |
| user | `user:read` `user:create` `user:update` `user:delete` |
| role | `role:read` `role:write` |
| task | `task:read` `task:cancel` `task:retry` ★新增 |
| tool | `tool:read` `tool:execute` |
| data | `data:read` `data:backup` `data:restore` `data:export` `data:import` `data:cleanup` |
| assistant | `assistant:read` `assistant:chat` `assistant:plan` `assistant:confirm` `assistant:execute` `assistant:drawing` `assistant:modeling` `assistant:optimize` `assistant:report` ★全部新增 |
| audit | 复用 `system:audit` |

### 4.8.3 默认角色映射

| 角色 | 权限 |
|---|---|
| `super_admin` | 全部 |
| `engineer` | `model:*` `tool:*` `task:*` `assistant:*` `system:read` `data:read` |
| `analyst` | `model:read` `tool:read` `task:read` `assistant:read` `assistant:chat` `data:read` |
| `visitor` | `model:read` `tool:read` `task:read` `data:read` |

### 4.8.4 高风险权限约束

```text
data:restore        → 仅 super_admin
system:write        → 仅 super_admin
user:delete         → 仅 super_admin
assistant:execute   → engineer 及以上，且必须通过 §5 高风险确认流程
```

> **裁决**：v1.1 §72 把「恢复数据库」列为 AI 可确认的高风险操作，与「`data:restore` 仅 super_admin」冲突。
> **结论**：AI 助手**不得**触发 `data:restore`。§72 清单中「恢复数据库」**移除**，改由运维页面人工操作。

## 4.9 多产品多租户路由

> 完整方案见 `docs/多产品多租户路由框架_v1.0.md`；本节只记**裁决**。

### 4.9.1 路由方向（唯一）

**裁决：路由链一律为「实例 → 适配器 → 能力」，禁止反向。**

```
调用方 → midas_client_id → midas_clients.adapter_code → 该适配器下的 (resource, action)
```

**禁止**由能力反推适配器。原实现把 `capabilities.adapter_code` 硬编码为 `'midas_gen'`，
后果经实机确证（Gen / Civil NX / Civil Designer 三实例）：

| 场景 | 原行为 | 应有行为 |
|---|---|---|
| 只部署 Civil NX | 每个能力 `ADAPTER_NOT_FOUND` | 自动选中 Civil |
| 只部署 Civil Designer | 同上 | 自动选中 Designer |
| 三个都注册，不指定实例 | **`success=True`，静默走 Gen** | **拒绝** |

> **第三行是数据混乱的直接来源**：调用方以为在操作 Civil，实际改了 Gen 的模型，
> 且**没有任何提示**。故本裁决为**实现阻断级**。

### 4.9.2 四道闸

| 闸 | 规则 | 失败码（§4.4 封闭集合） |
|---|---|---|
| **1. 歧义即拒绝** | 可用实例 `>1` 且调用方未指定 → **拒绝，不得猜测** | `VALIDATION_ERROR` |
| 2. 数据范围 | 用户只能使用其有权使用的实例（§4.8.2 之上的数据范围过滤） | `PERMISSION_DENIED` |
| 3. 能力可用性 | 目标适配器下无该 `(resource, action)` | `CAPABILITY_NOT_SUPPORTED` |
| 4. 产品范围 | `product_scope` 不允许（§4.2.11） | `CAPABILITY_NOT_SUPPORTED` |

**闸 1 的实例选择规则（完整）：**

| 可用实例数 | 调用方指定 | 行为 |
|---|---|---|
| 0 | — | `CLIENT_NOT_CONNECTED` |
| 1 | 否 | 自动选中（唯一，无歧义） |
| 1 | 是，但不匹配 | `PERMISSION_DENIED` |
| **>1** | **否** | **`VALIDATION_ERROR`（歧义，必须显式指定）** |
| >1 | 是 | 校验在可用集内 → 用它 |

> **裁决：闸 1 是硬约束。** 「宁可让调用方多传一个参数，也不能让它改错模型」——
> 猜测的代价是**静默的数据损坏**，而拒绝的代价只是一次明确的报错。
> 平台拥有的工具（`midas_task`）不参与选实例：MIDAS 无任务端点
> （《对接规范》§2.5.1），其能力 `adapter_code` 为 `NULL`。

### 4.9.3 能力表的键控

与 §4.2.12 一致：`capabilities` 与内存能力表均按 **`(adapter_code, capability_code)`** 键控。

**裁决：不存在「按 code 单独键控」的形式。** 同一 `capability_code` 在每个适配器下各有一行
（`node.list` 在 gen / civil / cdn 各一行），按 code 单独键控会让后一行**静默覆盖**前一行——
这正是 §4.9.1 那条「静默走 Gen」的成因。

因此枚举全部能力**只能**用有序集合（`capability_rows()`），**不得**用 code 为键的字典。

### 4.9.4 不新增错误码

§4.9.2 用到的四个码**全部已在 §4.4 封闭集合内**，本框架不新增任何错误码、
不新增 ID 前缀、不新增权限码。

---

# 5. 冲突裁决表

> 编号规则：`A-` 上一轮报告的 A 级问题；`B-` B 级；`C-` C 级；`N-` v1.1 新增内容引入的新问题。

## 5.1 A 级（实现阻断级）

| 编号 | 冲突描述 | 裁决 | 落地方 |
|---|---|---|---|
| A-1 | MCP 状态接口双路径：V2.0 `/mcp/server/status` vs v1.1 `/mcp/server` | **采用 `/api/v1/mcp/server`** | v1.2 保持；V2.1 §27 删除 `/status` |
| A-2 | `mcp_servers` 缺 `started_at`、`log_level`，但接口返回/接收 | `mcp_servers` **新增 `started_at DATETIME`**；`log_level` **归属 `service_configs`**，`PUT /mcp/server` 收到后写入 `service_configs` | V2.1 §4；v1.2 §7.2 加注 |
| A-3 | 两套不兼容错误码 | **统一到 §4.4 注册表**，旧名走别名映射 | 两者 |
| A-4 | `system:audit` 权限码缺失 | **新增 `system:audit`** 及全部 `assistant:*` | V2.1 种子数据 |
| A-5 | 统一信封被大量示例违反 | **REST 信封强制**，例外仅限 §4.3.1 四类 | v1.2 全量修正 |
| A-6 | `tasks.type` 与 `tasks.action` 语义未定义 | `type` = **业务任务类型**（封闭枚举，见 §5.4）；`action` = **具体动作**（引用 MCP action 词表） | V2.1 §4 + 本规范 §5.4 |
| A-7 | Adapter 的 `QueryRequest`/`ModelRequest`/`ExecuteRequest` 未定义，Protocol 无 `metadata()` | **定义三个 dataclass（均继承 `AdapterRequest`）**；Protocol **新增 `metadata()` 方法** | V2.1 §13 §18 §19 |

## 5.2 B 级（模型缺口）

| 编号 | 问题 | 裁决 | 落地方 |
|---|---|---|---|
| B-1 | MCP Client 无凭据存储 | **新增表 `mcp_client_credentials`** | V2.1 §4 |
| B-2 | `schemas.schema_code` UNIQUE 阻止多版本 | 改为 **UNIQUE(`schema_code`, `version`)** | V2.1 §4 |
| B-3 | 同一 Endpoint 无法挂给两个 Tool | `tool_interfaces` 唯一键改为 **UNIQUE(`adapter_code`, `interface_code`)**，并**允许 `capabilities` 与 `tool_interfaces` 多对多**（新增关联表 `capability_interfaces`） | V2.1 §4 |
| B-4 | `query`/`data` 自由对象绕过 `additionalProperties:false` | **收紧**：`midas_query.query` 按 target 用 `oneOf` 分资源子 Schema；`midas_model.data` 按 resource 用 `oneOf`；`midas_execute.data` 保留开放但**强制经 Capability 的 `request_schema_json` 二次校验** | V2.1 §7-§9 |
| B-5 | 无报告实体 | **新增表 `reports`** | V2.1 §4 |
| B-6 | `updated_at` 永不更新 | **ORM 层 `onupdate` 维护**，不用触发器 | §4.5.1 |
| B-7 | Rate Limit 无配置字段 | `security_configs` **新增** `rate_limit_enabled` / `rate_limit_per_minute` / `rate_limit_burst` | V2.1 §4 |
| B-8 | `system_configs.is_secret` 加密方案未定义 | 纳入 §4.7.1 加密清单 | §4.7 |
| B-9 | MCP 侧无订阅能力 | **明确为轮询模型**：`midas_task action=events` 轮询。MCP 不提供 push。实时推送仅由 v1.2 的 SSE 提供 | V2.1 §7 加注 |
| B-10 | `status` 列 CHECK 约束不一致 | 全部状态列**补齐 CHECK**，取值见 §4.2 | V2.1 §4 |
| B-11 | `tasks.tool_name`/`adapter_code` 无外键 | **补齐外键** | V2.1 §4 |
| B-12 | 缺索引 | `system_logs` 增 `(task_id)`、`(module, timestamp)`；`audit_logs` 增 `(user_id)`、`(resource_type, resource_id)` | V2.1 §4 |
| B-13 | 时区口径未定义 | 统一按 §4.5.1 | §4.5 |

## 5.3 C 级（文档一致性）

| 编号 | 问题 | 裁决 |
|---|---|---|
| C-1 | V2.0 §2 表格漏 `count` | V2.1 §2 补 `count` |
| C-2 | V2.0 §2 写 `log`，schema 是 `logs` | 统一为 **`logs`** |
| C-3 | 密钥回显字段名两套 | 统一为 **`api_key_configured` / `api_key_masked`**（§4.7.2） |
| C-4 | `task_id` 命名四套 | 统一为 **`task_` 前缀 + `tasks.type` 区分**（§4.1.4） |
| C-5 | MCP v2 与 REST v1 版本轴未对齐 | 明确：**MCP Tool Schema 版本**（`tool.version=2.1`）与 **REST API 版本**（`/api/v1`）是两条独立轴，无映射关系；MCP 大版本升级不影响 REST |
| C-6 | 单复数不一致 | 按 §4.6.1 分工 |
| C-7 | `target=capabilities` 与 `action=capabilities` 语义重叠 | **保留 `target=capabilities` + `action=list`**；`action=capabilities` **从枚举移除** |
| C-8 | §18.4 硬编码 `deepseek-v4-flash` | 改为占位符 `<model_code>` |
| C-9 | token 7200s 与 session_timeout 30min 关系未说明 | `expires_in` 由 `security_configs.session_timeout_minutes × 60` 计算；示例改为 1800 |
| C-10 | 备份默认路径是 Linux 路径 | V2.1 改为**平台自适应**：默认 `./data/backups`（相对工作目录） |
| C-11 | `AdapterResult` 缺 `field` 导入 | V2.1 补 `from dataclasses import dataclass, field` |
| C-12 | 部分表无 `updated_at` | **明确例外**：追加型表（`task_events`/`system_logs`/`audit_logs`/`user_roles`/`role_permissions`）不设 `updated_at` |
| C-13 | §29 缺 `api_auth_required` | v1.2 补齐 |

## 5.4 N 级（v1.1 新增内容引入）

> **编号说明：** 「问题」列中的 `§x` 指 **v1.1 原编号**（描述问题发生的位置）；
> 「落地方」列中的 `§x` 指 **v1.2 交付版编号**。两套编号不同，因为 v1.2 已按本规范 §6.6 删除了 4 个越界章节并重新编号。

| 编号 | 问题 | 裁决 | 落地方 |
|---|---|---|---|
| N-1 | **Execution Plan 不可执行**：`operation: create_nodes` / `run_analysis` 无法翻译为 MCP 调用 | **重定义 plan step 结构**为可执行形式：`{step_no, name, tool, action, resource, params, depends_on}`。示例改为 `{"tool":"midas_model","action":"create","resource":"node"}`、`{"tool":"midas_execute","action":"analysis","resource":"model"}` | v1.2 §67；V2.1 §4 表结构 |
| N-2 | `/assistant/analysis/run` 与 `/midas/analysis/run` 重复；`/assistant/reports` 与 `/reports` 重复 | **双门面并存是允许的**（AI 门面 / 运维门面），但必须：① 共享同一 Service ② 请求体字段名完全一致 ③ 响应体同构。**`/api/v1/reports` 与 `/api/v1/midas/analysis/run` 标记为运维门面**，字段名以 AI 门面为准统一 | v1.2 §45 §47 加注并对齐字段（§84 同步对齐） |
| N-3 | `confirmation_token` 无处签发 | **`POST /assistant/plans` 的响应必须返回 `plan_id` + `confirmation_token`**；`GET /plans/{id}` 在 `awaiting_confirmation` 时也返回。令牌**一次性**、有效期 10 分钟、绑定 `plan_id` + `user_id` | v1.2 §67 §68 §69 |
| N-4 | 无法加载历史对话 | **新增 `GET /api/v1/assistant/sessions/{session_id}/messages`**（分页） | v1.2 §64.2 |
| N-5 | `stream: true` 与 JSON 响应矛盾 | **定义**：`stream=true` 时该接口返回 `text/event-stream`，事件为 `message.delta` / `intent.ready` / `plan.ready` / `done`；`stream=false` 时返回标准信封 JSON | v1.2 §64.1 |
| N-6 | `model_id` 类型自相矛盾（整数 vs 字符串） | **按外键目标表是否有业务 ID 列决定**（见 §4.1.6）：`model_id`→`models.id`、`midas_client_id`→`midas_clients.id` 为 **INTEGER**；`project_id`→`projects.project_id`、`file_id`→`assistant_files.file_id` 为 **TEXT 业务 ID**。v1.1 的 `"model_xxx"` 字符串形式废止，改为整数 | v1.2 全量修正；类型以 V2.1 §4 为准 |
| N-7 | `project_id` 无实体 | **新增表 `projects`** | V2.1 §4 |
| N-8 | §70 缺响应体 | 补响应：`{plan_id, status, risk_level, requires_confirmation, confirmation_token, steps[]}` | v1.2 §67 |
| N-9 | 三套状态词表互不兼容 | 统一到 §4.2；UI 状态机改为派生（§4.2.6） | 两者 |
| N-10 | AI 任务无取消入口 | **新增 `POST /api/v1/assistant/plans/{plan_id}/cancel`**；并明确 AI 任务即 `tasks` 表记录，可用通用 `/tasks/{task_id}/cancel` | v1.2 §70.1 |
| N-11 | 异步策略不一致（§81/§82 无 task_id） | **§81 荷载生成、§82 规范检查改为异步**，返回 `task_id`。凡可能超过 3 秒的操作一律进 Task Engine | v1.2 §78 §79 |
| N-12 | AI 模块无 RBAC 定义 | 引入 `assistant:*` 权限码（§4.8.2），51 个接口逐条标注所需权限 | v1.2 §62.2 及各 AI 章节 |
| N-13 | §98 越界定义表，且 `mcp_clients` 应为 `midas_clients` | **§98 整节删除**，改为「参见《V2.1 设计框架规范》§4」 | v1.2 §0.4（登记）／V2.1 §4（表结构） |
| N-14 | §47 与 §87 报告字段名不一致 | 统一为 **`report_type` + `include[]`** | v1.2 §47 §84 |
| N-15 | §94 文件类型 PDF 重复 | 去重 | v1.2 §91 |
| N-16 | §63 验收无 AI 条目 | 验收标准整体上移至本规范 §8 | 两者 |
| N-17 | §62/§63/§64 仍写 V1.0 | 改为 v1.2 / 上移 | v1.2 |
| N-18 | §30.1 `table_count: 28` 已失真 | 改为 **49** | v1.2 §30.1 |
| N-19 | 规范知识库（§82）在 V2.0 属 P3，但 v1.1 列为核心 | **提升为核心能力**，新增 `code_standards` / `code_clauses` 表；排期见 §7 | V2.1 §4 |
| N-20 | 荷载生成（§81）需要地区规范参数库 | 新增 `load_parameter_library` 表 | V2.1 §4 |
| N-21 | §69 `normalized_parameters` 示例为空 | 补实际归一化示例 | v1.2 §66 |
| N-22 | §68.1 返回 `missing_parameters` 但无补全接口 | 复用 §67 消息接口补全（AI 追问），文档注明 | v1.2 §65 |
| N-23 | `assistant_files` 与 `assistant_outputs` 边界不清 | `files` = **上传与产物文件本体**；`outputs` = **产物语义记录**（关联 file + 类型 + 元数据） | V2.1 §4 |
| N-24 | §75 支持 DWG 但未提转换链路 | v1.2 §72 加注：DWG 需经转换服务转为 DXF/中间格式后识别 | v1.2 §72（含 §72.2 转换接口） |
| N-25 | 助手会话与 MIDAS Client 关联字段错误 | `assistant_sessions.midas_client_id` → FK `midas_clients(id)` | V2.1 §4 |

---

# 6. 补缺清单

## 6.1 新增表（20 项 / 21 张）

| # | 表名 | 用途 | 来源 |
|---|---|---|---|
| 1 | `assistant_sessions` | AI 会话 | v1.1 §98 |
| 2 | `assistant_messages` | 对话消息 | v1.1 §98 |
| 3 | `assistant_intents` | 工程意图 | v1.1 §98 |
| 4 | `assistant_plans` | 执行计划 | v1.1 §98 |
| 5 | `assistant_plan_steps` | 计划步骤（含可执行字段） | v1.1 §98 + N-1 |
| 6 | `assistant_files` | 文件本体 | v1.1 §98 |
| 7 | `assistant_outputs` | 产物语义记录 | v1.1 §98 + N-23 |
| 8 | `assistant_drawing_tasks` | 识图任务 | v1.1 §98 |
| 9 | `assistant_drawing_objects` | 识图对象 | v1.1 §98 |
| 10 | `assistant_drawing_settings` | 识图设置 | **补 v1.1 §76 缺表** |
| 11 | `assistant_templates` | 工程模板 | v1.1 §98 |
| 12 | `assistant_examples` | 示例案例 | v1.1 §98 |
| 13 | `assistant_history` | 历史记录（细粒度审计） | v1.1 §98 |
| 14 | `assistant_commands` | 常用工程指令 | v1.1 §98 |
| 15 | `reports` | 报告实体 | B-5 |
| 16 | `projects` | 项目实体 | N-7 |
| 17 | `mcp_client_credentials` | MCP Client 凭据 | B-1 |
| 18 | `capability_interfaces` | Capability ↔ Interface 多对多 | B-3 |
| 19 | `code_standards` / `code_clauses` | 规范知识库 | N-19 |
| 20 | `load_parameter_library` | 地区荷载规范参数库 | N-20 |

> 说明：第 19 项含两张表，故实际新增 **21 张**。合并后总数：

```text
28（原）+ 21（新）= 49 张
```

**最终表数量：49。** v1.2 §30.1 的 `table_count` 应填 `49`。

## 6.2 既有表的结构调整

| 表 | 调整 |
|---|---|
| `mcp_servers` | 新增 `started_at DATETIME` |
| `security_configs` | 新增 `rate_limit_enabled` / `rate_limit_per_minute` / `rate_limit_burst` |
| `schemas` | 唯一键改为 `(schema_code, version)` |
| `tool_interfaces` | 唯一键改为 `(adapter_code, interface_code)`；`tool_id` 允许 NULL |
| `tasks` | 补齐 `tool_name` → `tools(name)`、`adapter_code` → `adapters(code)` 外键；`type` 加 CHECK |
| `models` | `status` 加 CHECK |
| `midas_clients` | `status` 加 CHECK |
| `mcp_servers` | `status` 加 CHECK |
| `adapters` | `status` 加 CHECK |
| `tasks` | `status` 加 CHECK |
| `system_logs` | 新增索引 `(task_id)`、`(module, timestamp)` |
| `audit_logs` | 新增索引 `(user_id)`、`(resource_type, resource_id)` |
| `tasks` | 新增 `request_id TEXT` — 承载 §4.1.5 的 `request_id → task_id → adapter_request_id` 追溯链 |
| `system_logs` | 新增 `adapter_request_id TEXT` — 承载 §4.1.5 追溯链的末端 |
| `users` | 新增 `department TEXT` — 用户所属部门；与 `midas_clients.department` 按值匹配（规则见 §4.2.5 补充） |

## 6.3 新增权限码

```text
system:audit
task:retry
assistant:read  assistant:chat  assistant:plan  assistant:confirm
assistant:execute  assistant:drawing  assistant:modeling
assistant:optimize  assistant:report
```

## 6.4 新增错误码

见 §4.4.7（AI 工程助手，8 条）与 §4.4.9（`IMPORT_VALIDATION_FAILED`、`NOT_IMPLEMENTED`）。

## 6.5 新增接口（v1.2）

| 接口 | 用途 |
|---|---|
| `GET /api/v1/assistant/sessions/{session_id}/messages` | 加载历史对话（N-4） |
| `POST /api/v1/assistant/plans/{plan_id}/cancel` | 取消计划执行（N-10） |
| `GET /api/v1/assistant/templates/categories` | 模板分类 |
| `POST /api/v1/assistant/files/{id}/convert` | 图纸格式转换（N-24） |

## 6.6 删除的内容

| 位置 | 删除项 | 理由 |
|---|---|---|
| V2.0 §33 | 优先级 P0–P3 | 上移至本规范 §7 |
| V2.0 §34 | 验收标准 | 上移至本规范 §8 |
| v1.1 §62 | 实施顺序 | 上移至本规范 §7 |
| v1.1 §63 | 验收标准 | 上移至本规范 §8 |
| v1.1 §98 | 数据库实体清单 | 越界，改引用 V2.1 §4 |
| v1.1 §50 | 独立错误码清单 | 越界，改引用本规范 §4.4 |
| v1.1 §96 | 状态机定义 | 改为 UI 派生状态（§4.2.6） |
| v1.1 §72 清单 | 「恢复数据库」 | 与 `data:restore` 仅 super_admin 冲突（§4.8.4） |

---

# 7. 融合后的实施排期

> 本章合并 V2.0 的 P0–P3 与 v1.1 §62 的 ①–⑬，并纳入 AI 工程助手。
> **原则：先地基、再框架、后门面、最后智能。**

## Phase 0 — 地基（P0）

```text
0.1  SQLite DDL（49 张表）+ 种子数据
0.2  SQLAlchemy 2.x Models + Alembic 迁移
0.3  Repository 层（SQLite / PostgreSQL 双支持）
0.4  统一信封 / 错误码 / Request ID 中间件
0.5  时间与量纲约定落地（ORM onupdate、时区转换）
0.6  加密模块（AES-256-GCM + STRUCTAI_MASTER_KEY）
```

**验收：** 49 张表可建可迁；信封与错误码单测通过；密钥字段往返加解密正确。

## Phase 1 — 框架（P0）

```text
1.1  FastAPI 基础框架 + 依赖注入
1.2  JWT / RBAC（含 assistant:* 权限码）
1.3  审计日志中间件
1.4  MIDAS Client 管理 + 连接测试
1.5  Adapter Base + Protocol + Registry
1.6  Capability Registry + Resolver
1.7  Interface Registry（tool_interfaces + capability_interfaces）
1.8  Task Engine（队列 / 并发 / 超时 / 重试 / 取消 / 进度）
1.9  MCP Server + 4 Tool + Tool Dispatcher
1.10 Mock Adapter（用于全链路自测）
```

**验收：** 4 个 MCP Tool 可被 MCP Client 调用；Mock Adapter 下全链路通；任务可查询/取消/重试。

## Phase 2 — 管理端 API 与 UI 还原

```text
2.1  REST API 全量（v1.2 §5-§54）
2.2  SSE（任务流 / 日志流）
2.3  Vue UI 对接（原型 12 个页面）
2.4  数据管理（备份 / 恢复 / 导入 / 导出 / 清理）
2.5  系统设置（基础 / 服务 / 安全 / 模型 / 用户权限）
```

**验收：** 原型全部页面通过 REST 取数，无前端硬编码业务状态。

> 对应 v1.1 §62 的 ⑨⑩⑪。

## Phase 3 — MIDAS Gen 适配

```text
3.1  MIDAS Gen Adapter（client / mapper / capabilities / interfaces）
3.2  模型 CRUD（节点/单元/材料/截面/边界/组）
3.3  荷载
3.4  计算任务
3.5  结果查询
3.6  Capability Matrix 实测校准
```

**验收：** MIDAS Gen 真实连接下完成建模 → 计算 → 取结果闭环。

## Phase 4 — AI 工程助手（核心业务层）

```text
4.1  assistant_* 数据层落地（14 张表）
4.2  AI 会话与消息（含 GET messages）
4.3  意图解析（§68）
4.4  参数与规范校验（§69）+ code_standards / code_clauses
4.5  Execution Plan 生成与可执行化（N-1）
4.6  高风险确认流程（N-3）
4.7  计划执行 → Task Engine → MCP 4 Tools
4.8  执行过程查询与 SSE
4.9  结果解释（§84）
4.10 报告生成（§87）+ reports 表
4.11 图形输出（§88）
4.12 历史案例 / 历史记录（§91 §92）
4.13 工程模板 / 示例案例 / 常用指令（§89 §90 §93）
```

**验收：** 自然语言 → 意图 → 计划 → 确认 → 执行 → 结果 → 计算书，全链路可追溯。

> **本 Phase 是 StructAI 区别于普通 MCP 管理器的核心。**

## Phase 5 — 智能识图与智能建模

```text
5.1  图纸上传与格式转换（PDF / DXF / PNG / JPG；DWG 经转换）
5.2  识图任务与对象抽取（§75 §77）
5.3  尺寸一致性检查（§78）
5.4  识图结果转模型（§79）
5.5  快速向导建模（§80.2）
5.6  自然语言建模（§80.1）
5.7  模型预览（§80.3）
5.8  荷载生成 + load_parameter_library（§81）
5.9  规范检查（§82）
```

## Phase 6 — 优化与多软件

```text
6.1  结构优化（§85 §86）
6.2  MIDAS Civil Adapter
6.3  MIDAS FEA NX Adapter
6.4  批量导入导出
6.5  完整能力矩阵
```

## Phase 7 — 生态扩展

```text
7.1  CSI / SAP2000 / ETABS / ANSYS Adapter
7.2  自动配筋 / 钢材优化
7.3  规范知识库扩展
7.4  多轮工程对话与迭代优化
```

## 7.1 与原排期的对照

| 原 V2.0 | 原 v1.1 §62 | 新排期 |
|---|---|---|
| P0 | ①–⑧ | Phase 0 + Phase 1 |
| P1 | ⑨–⑫ | Phase 2 + Phase 3 |
| P2（含报告生成） | — | Phase 4（报告生成提前至核心） |
| P3（AI 自动建模 / 工程规则校验 / 规范知识库 / 自动优化） | — | **Phase 4 + Phase 5 + Phase 6（大幅提前）** |
| — | ⑬ 测试与审计 | 贯穿各 Phase |

> **关键变更：** 原 V2.0 把「AI 自动建模 / 工程规则校验 / 规范知识库 / 自动优化」放在最后一档 P3。
> v1.1 把 AI 工程助手定义为核心业务模块。
> **裁决：采纳 v1.1 的定位，AI 助手提升至 Phase 4–5**，因为这些能力才是 StructAI 的产品差异点；MIDAS Gen 适配（Phase 3）必须先完成，作为 AI 的执行基础。

---

# 8. 统一验收标准

## 8.1 数据层

- [ ] 49 张表全部建立，含索引、外键、CHECK 约束
- [ ] 追加型表的 `updated_at` 例外已在文档标注
- [ ] 所有状态列取值与 §4.2 词表一致
- [ ] 加密字段按 §4.7 落地，库中无明文
- [ ] `schemas` 支持同码多版本
- [ ] `tool_interfaces` 支持一接口多 Tool

## 8.2 框架层

- [ ] 4 个 MCP Tool 可被外部 Agent 调用
- [ ] MCP 信封符合 §4.3.2
- [ ] Adapter Protocol 完整（含 `metadata()`）
- [ ] `QueryRequest` / `ModelRequest` / `ExecuteRequest` 已定义
- [ ] Capability Resolver 全链路可追溯
- [ ] 错误码全部来自 §4.4，无自定义

## 8.3 接口层

- [ ] `/api/v1/*` 全部返回 REST 信封，例外仅 4 类
- [ ] 分页统一 `data.items` + `data.pagination`
- [ ] 所有 `model_id` / `project_id` / `midas_client_id` 为整数
- [ ] 所有 `task_id` 使用 `task_` 前缀
- [ ] 51 个 AI 接口逐条标注所需权限码
- [ ] SSE 事件名与载荷已定义

## 8.4 任务与追踪

- [ ] 所有长任务进 Task Engine，返回 `task_id`
- [ ] `request_id → task_id → adapter_request_id` 可互相追溯
- [ ] 任务可查询 / 取消 / 重试 / 查看事件

## 8.5 AI 工程助手

- [ ] 自然语言 → 意图 → 参数 → 计划 全链路
- [ ] Execution Plan 可直接翻译为 MCP 调用
- [ ] 高风险确认令牌一次性、有有效期
- [ ] 历史对话可加载
- [ ] AI 输出绑定真实计算结果，禁止编造
- [ ] 规范检查可追溯到具体条文
- [ ] 识图结果可转模型且经过校验

## 8.6 安全

- [ ] JWT / RBAC / TLS / Rate Limit / Audit 全部启用
- [ ] AI 不得绕过 RBAC / Capability / 校验 / 确认
- [ ] AI 不得触发 `data:restore`
- [ ] 敏感字段回显符合 §4.7.2

## 8.7 架构

- [ ] REST 与 MCP 共享 Service Layer，无重复业务逻辑
- [ ] 三份文档无重复定义（按 §3 越界规则自检）
- [ ] 新增 MIDAS 软件只需新增 Adapter + Capability + Interface，不改 MCP Tool Schema

---

# 9. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | — | 首次发布。融合 V2.0 设计框架与 v1.1 管理端 API；建立七层模型、所有权矩阵、跨层统一约定；裁决 40 项冲突；补 21 张表；重排 8 个 Phase |

---

# 10. 附录：三份文档的引用约定

## 10.1 V2.1 设计框架规范必须包含

```text
§0  文档定位（引用本规范）
§4  完整 DDL（49 张表）+ 种子数据
§6  MCP Tool JSON Schema 总规范
§7-§11  4 个 Tool 完整 Schema
§12-§22 Adapter / Capability / Interface
§23-§24 Canonical Model
§25 事务与安全
§26 Task Engine
§28 REST 与 MCP 的关系
§29 权限模型
§30 加密
§31 版本策略
附录 A  错误码注册表（收录本规范 §4.4）
附录 B  状态词表（收录本规范 §4.2）
附录 C  ID 命名规范（收录本规范 §4.1）
```

## 10.2 v1.2 接口设计规范必须包含

```text
§0  文档定位与边界（含 §0.4 越界内容处置登记）
§2-§4  API 基础规范 / HTTP 通用规范（含 §3.2 信封、§3.3 四类例外）/ HTTP 状态码
§5  认证
§6-§61  管理端接口（含统一信封修正）
§62 AI 工程助手 API（§62.2 RBAC 权限表）
§63-§91  AI 工程助手接口（含 RBAC 标注）
§92 AI Assistant 与 MCP 4 Tool 的关系
§93 AI Assistant 状态机（UI 展示状态，派生，不落库）
§94 AI Assistant 安全边界
§95 前端 AI 工程助手页面与 API 映射（含权限列）
§96 完整 StructAI API 模块
§97 最终 StructAI 核心业务闭环
附录  错误码引用表（指向本规范 §4.4）
```

## 10.3 禁止事项

三份文档中**均不得**出现：

```text
重复定义表结构
重复定义错误码
重复定义状态词表
重复定义 ID 前缀
重复定义权限码
重复定义实施排期
重复定义验收标准
```

任何一处出现，即视为违反本规范 §0.3「唯一真源原则」。
