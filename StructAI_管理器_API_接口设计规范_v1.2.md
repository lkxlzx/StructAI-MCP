# StructAI 管理器 API 接口设计规范 v1.2

**文档版本：** v1.2  
**API 版本：** `/api/v1`  
**协议：** HTTP/HTTPS + JSON  
**实时接口：** SSE（`text/event-stream`）  
**MCP 协议：** MCP Streamable HTTP / SSE（按实际客户端兼容情况启用）  
**默认服务端口：** 8765

---

# 0. 文档定位与边界

## 0.1 本文档是什么

本文档是 **UI 原型还原的 API 契约**。

它回答的问题是：**页面怎么取数、怎么写数。**

本文档**拥有**以下内容：

| # | 本文档拥有的内容 | 主要章节 |
|---|---|---|
| 1 | REST 路径（`/api/v1/*`） | §2、§5-§53、§62-§91 |
| 2 | 请求体 / 响应体字段 | 全部接口章节 |
| 3 | 前端页面与 API 的映射 | §54、§95 |
| 4 | SSE 事件名与事件载荷 | §21、§22.3、§71 |
| 5 | UI 展示状态机（派生，不落库） | §93 |
| 6 | 接口级鉴权声明（引用权限码） | §62 及各接口章节 |

## 0.2 本文档不是什么（边界）

本文档**不拥有**以下内容，任何情况下**只引用，不重定义**：

| 不属于本文档的内容 | 唯一所有者 | 本文档的引用方式 |
|---|---|---|
| 表结构 / DDL / 索引 / 外键 / 表数量 | 《StructAI MCP V2.1 设计框架规范》§4 | 只引用表名与字段名 |
| MCP 4 Tool 名称与 JSON Schema | 《StructAI MCP V2.1 设计框架规范》§7-§11 | §37、§39、§92 引用 |
| Capability / Interface / Adapter 契约 | 《StructAI MCP V2.1 设计框架规范》§12-§22 | §10、§13、§14、§16 引用 |
| 错误码注册表 | 《StructAI 架构边界与融合规范 v1.0（总纲）》§4.4 | §49、§50 与附录引用 |
| 状态词表（任务 / 计划 / 步骤 / 会话 / 其他状态列） | 《总纲》§4.2 | 全部接口章节引用 |
| ID 前缀与命名规范 | 《总纲》§4.1 | 全部接口章节引用 |
| 权限码清单 | 《总纲》§4.8 | §23、§26、§62 引用 |
| 统一响应信封（REST） | 《总纲》§4.3.1 | §3.2 实现，全量示例遵循 |
| 时间与量纲约定 | 《总纲》§4.5 | 全部示例遵循 |
| 加密字段清单与回显规范 | 《总纲》§4.7 | §9.3 引用 |
| 实施排期与优先级 | 《总纲》§7 | 本文档不含 |
| 验收标准 | 《总纲》§8 | 本文档不含 |

## 0.3 冲突优先级

```text
《StructAI 架构边界与融合规范 v1.0（总纲）》
     ↓ 高于
《StructAI MCP V2.1 设计框架规范》
     ↓ 高于
本文档《StructAI 管理器 API 接口设计规范 v1.2》
```

> **任何跨文档矛盾，一律以《总纲》第 5 章「冲突裁决表」为准，且《总纲》整体优先于本文档。**
> 本文档内部若出现与《总纲》不一致的表述，以《总纲》为准，本文档必须回改。

## 0.4 越界内容的处置（相对 v1.1 的删除项）

v1.1 中以下内容属于框架层或裁决层，本文档已整体删除，改为指针：

| v1.1 位置 | 原内容 | 处置 |
|---|---|---|
| v1.1 §62 | 实施顺序（①-⑬） | **删除**。实施排期由《总纲》§7 拥有。 |
| v1.1 §63 | 验收标准 | **删除**。验收标准由《总纲》§8 拥有。 |
| v1.1 §98 | 数据库核心实体清单（13 张 `assistant_*` 表 + 8 张关联表） | **删除整节**。表结构参见《StructAI MCP V2.1 设计框架规范》§4；最终 schema 为 **49 张表**。 |
| v1.1 §50 | 手写错误码清单 | **删除清单**。错误码注册表由《总纲》§4.4 拥有，见本文档 §50 与附录。 |
| v1.1 §96 | 助手状态机定义 | **保留为 UI 展示状态机**，改为由落库状态派生，见本文档 §93。 |

> 上述删除项的处置依据见《总纲》§6.6「删除的内容」与 §3.1「越界判定规则」。

## 0.5 三份文档的分工

```text
《总纲》            →  层次划分 / 所有权 / 统一约定 / 冲突裁决 / 排期 / 验收
《V2.1 设计框架规范》 →  49 张表 DDL / MCP 4 Tool Schema / Adapter·Capability·Interface 契约
本文档 v1.2        →  /api/v1/* REST·SSE 接口 / 页面取数映射 / UI 展示状态
```

---

# 1. 文档目的

本文档定义 StructAI 管理器（MIDAS MCP 管理器）Web 管理端、StructAI、MCP Server、MIDAS Adapter 之间的 REST API、实时接口、认证授权、错误处理、任务管理以及**接口层请求/响应数据结构**规范。

> 注意：本文档中的「数据结构」仅指**接口层的请求体与响应体字段**，不包含数据库表结构。表结构由《StructAI MCP V2.1 设计框架规范》§4 拥有。

目标是让前端 UI、后端服务和 MCP Connector 按统一接口开发，避免前端直接依赖数据库或 MIDAS 原始 API。

核心原则：

```text
Web UI
   ↓ REST/SSE
API Gateway（/api/v1）
   ↓
Service Layer          ← REST 与 MCP 在此汇合
   ↓
MCP / Task / Adapter
   ↓
MIDAS Software
```

前端永远不直接访问：

```text
SQLite
MIDAS API
Adapter
```

---

# 2. API 基础规范

## 2.1 Base URL

```text
/api/v1
```

开发环境：

```text
http://127.0.0.1:8765/api/v1
```

局域网：

```text
http://<server-ip>:8765/api/v1
```

生产环境建议：

```text
https://mcp.example.com/api/v1
```

## 2.2 路径命名约定

路径段命名（kebab-case）、REST 资源复数、MCP resource 单数等约定，由《总纲》§4.6 拥有，本文档全部接口遵循。

```text
REST 路径段      kebab-case     /audit-logs  /model-providers  /code-check  /dimension-check
REST 资源        复数           /nodes  /elements  /materials
MCP resource     单数           node  element
JSON 字段        snake_case     api_key_masked
```

单复数转换由 Service 层入口 / Adapter Mapper 承担，转换责任见《总纲》§4.6.1。

## 2.3 内容类型

```http
Content-Type: application/json
```

文件上传使用：

```text
multipart/form-data
```

文件下载返回二进制流（属于 §3.3 的例外）。

---

# 3. HTTP 通用规范

## 3.1 方法

支持：

```text
GET
POST
PUT
PATCH
DELETE
```

## 3.2 统一响应信封

信封结构由《总纲》§4.3.1 拥有，本文档按其实现。

成功：

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

**强制规则（本文档全量示例与实现必须满足）：**

- 所有 `application/json` 响应**必须**包含 `success` / `code` / `message` / `request_id` / `timestamp`
- 业务数据一律放在 `data` 中，**禁止顶层裸字段**
- 分页统一为 `data.items` + `data.pagination`（见 §51）
- 业务错误一律用 HTTP 200 + `success: false`，或对应 4xx/5xx + 同一信封
- 异步受理返回 `data.status` 与 `data.task_id`

## 3.3 唯一允许的例外（封闭清单）

全文档**仅**以下四类响应可以不使用统一信封，且必须在对应章节显式标注：

| # | 例外 | 涉及接口 | 原因 |
|---|---|---|---|
| 1 | SSE 流 | `*/stream`（§21、§22.3、§64.1、§71） | `text/event-stream`，非 JSON |
| 2 | 文件下载 | `*/download`、`/assistant/files/{id}`（§30.4、§91） | 二进制流 |
| 3 | 健康探针 | `/api/v1/health/ready`、`/api/v1/health/live`（§35、§36） | 容器编排要求裸状态码 |
| 4 | OpenAPI | `/openapi.json`、`/docs`、`/redoc`（§59） | 框架生成 |

> **注意：`/api/v1/health`（聚合健康检查，§34）不属于例外，必须使用标准信封。**
> 依据：《总纲》§4.3.1。

---

# 4. HTTP 状态码

| HTTP | 含义 |
|---|---|
| 200 | 成功 |
| 201 | 创建成功 |
| 202 | 异步任务已接受 |
| 204 | 删除成功，无返回内容 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 409 | 资源冲突 |
| 422 | 参数验证失败 |
| 429 | 请求过于频繁 |
| 500 | 服务内部错误 |
| 502 | MIDAS/Adapter 上游错误 |
| 503 | 服务不可用 |
| 504 | 上游超时 |

> 每个错误码对应的推荐 HTTP 状态，由《总纲》§4.4 注册表给出；本文档不另立对应关系。

---

# 5. 认证

## 5.1 登录

```http
POST /api/v1/auth/login
```

请求：

```json
{
  "username": "admin",
  "password": "********"
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "access_token": "eyJ...",
    "token_type": "Bearer",
    "expires_in": 1800,
    "user": {
      "id": 1,
      "username": "admin",
      "name": "系统管理员",
      "roles": [
        "super_admin"
      ]
    }
  },
  "request_id": "req_20260925_000001",
  "timestamp": "2026-09-25T08:30:00+08:00"
}
```

> **`expires_in` 说明（C-9）**：`expires_in` 由 `security_configs.session_timeout_minutes × 60` 计算得出，不是硬编码常量。
> 示例中 `session_timeout_minutes = 30`，故 `expires_in = 1800`。修改 §29 安全设置后，新签发的 Token 立即采用新值。

后续请求：

```http
Authorization: Bearer <access_token>
```

## 5.2 当前用户

```http
GET /api/v1/auth/me
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "id": 1,
    "username": "admin",
    "name": "系统管理员",
    "roles": [
      "super_admin"
    ],
    "permissions": [
      "system:read",
      "system:write",
      "system:audit",
      "assistant:read",
      "assistant:chat"
    ]
  },
  "request_id": "req_20260925_000002",
  "timestamp": "2026-09-25T08:30:05+08:00"
}
```

> `permissions` 的完整取值集合由《总纲》§4.8.2 拥有。

## 5.3 退出登录

```http
POST /api/v1/auth/logout
```

## 5.4 刷新 Token

```http
POST /api/v1/auth/refresh
```

返回同 §5.1，`expires_in` 重新按 `security_configs.session_timeout_minutes` 计算。

---

# 6. 首页 Dashboard API

对应原型：

```text
首页
MCP 状态
MIDAS 客户端
模型
任务
系统运行状态
```

## 6.1 首页总览

```http
GET /api/v1/dashboard/overview
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "mcp": {
      "status": "running",
      "port": 8765,
      "connected_clients": 2,
      "active_tasks": 1
    },
    "midas": {
      "total": 3,
      "connected": 2
    },
    "models": {
      "total": 6,
      "available": 5
    },
    "tasks": {
      "running": 1,
      "queued": 3,
      "failed": 0
    },
    "system": {
      "cpu_percent": 23.4,
      "memory_percent": 48.2,
      "disk_percent": 61.7
    }
  },
  "request_id": "req_20260925_000003",
  "timestamp": "2026-09-25T08:31:00+08:00"
}
```

> `mcp.status` 取值来自 `mcp_servers.status`，`tasks.*` 计数基于 `tasks.status`。状态取值由《总纲》§4.2.5 拥有。

---

# 7. MCP Server API

对应：

```text
MCP服务器页面
```

## 7.1 获取 Server 状态

```http
GET /api/v1/mcp/server
```

> **A-1 裁决**：MCP Server 状态的**唯一合法路径**是 `GET /api/v1/mcp/server`。
> `GET /api/v1/mcp/server/status` **不是合法路径**，前端与客户端不得调用。
> 依据：《总纲》§5.1 A-1。

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "id": 1,
    "name": "StructAI MCP Server",
    "host": "0.0.0.0",
    "port": 8765,
    "protocol_version": "2024-11-05",
    "transport": "streamable_http",
    "status": "running",
    "enabled": true,
    "started_at": "2026-09-25T08:00:00+08:00"
  },
  "request_id": "req_20260925_000004",
  "timestamp": "2026-09-25T08:31:10+08:00"
}
```

> **A-2 裁决**：`started_at` 由 `mcp_servers.started_at` 提供，是 `mcp_servers` 表的新增字段，由《V2.1 设计框架规范》§4 拥有。
> `status` 取值见《总纲》§4.2.5（`stopped / starting / running / stopping / error`）。

## 7.2 修改 Server 配置

```http
PUT /api/v1/mcp/server
```

请求：

```json
{
  "host": "0.0.0.0",
  "port": 8765,
  "transport": "streamable_http",
  "log_level": "INFO"
}
```

> **A-2 裁决**：`log_level` **不写入 `mcp_servers`**。本接口收到 `log_level` 后，写入 `service_configs`（其读写接口为 §28）。
> 即：`PUT /api/v1/mcp/server` 的 `log_level` 字段与 `PUT /api/v1/settings/service` 的 `log_level` 字段指向**同一份配置**。
> 依据：《总纲》§5.1 A-2。

## 7.3 启动

```http
POST /api/v1/mcp/server/start
```

## 7.4 停止

```http
POST /api/v1/mcp/server/stop
```

## 7.5 重启

```http
POST /api/v1/mcp/server/restart
```

---

# 8. MCP Client API

## 8.1 Client列表

```http
GET /api/v1/mcp/clients
```

支持：

```text
?page=1&page_size=20
&status=connected
&keyword=xxx
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "items": [
      {
        "id": 1,
        "client_name": "claude-desktop",
        "status": "connected",
        "connected_at": "2026-09-25T08:10:00+08:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 1,
      "total_pages": 1
    }
  },
  "request_id": "req_20260925_000005",
  "timestamp": "2026-09-25T08:32:00+08:00"
}
```

> `mcp_clients.status` 取值见《总纲》§4.2.5（`disconnected / connected`）。
> MCP Client 凭据存储于 `mcp_client_credentials`，字段与哈希算法由《V2.1 设计框架规范》§4 拥有。

## 8.2 Client详情

```http
GET /api/v1/mcp/clients/{id}
```

## 8.3 断开 Client

```http
POST /api/v1/mcp/clients/{id}/disconnect
```

---

# 9. MIDAS 客户端 API

对应原型：

```text
MIDAS客户端
```

## 9.1 列表

```http
GET /api/v1/midas/clients
```

过滤：

```text
?software=MIDAS%20Gen
&status=connected
&page=1
&page_size=20
```

## 9.2 创建

```http
POST /api/v1/midas/clients
```

请求：

```json
{
  "name": "MIDAS Gen 主客户端",
  "software": "MIDAS Gen",
  "version": "2026",
  "adapter_code": "midas_gen",
  "api_url": "http://192.168.1.100:8080",
  "api_key": "********",
  "timeout_seconds": 60,
  "proxy_enabled": false
}
```

注意：

API Key 只能在 TLS/本机安全环境中提交，数据库必须加密保存（加密字段清单见《总纲》§4.7.1）。

## 9.3 详情

```http
GET /api/v1/midas/clients/{id}
```

敏感字段返回：

```json
{
  "api_key_configured": true,
  "api_key_masked": "********"
}
```

不得返回明文 Key。

> **说明**：上面是**字段片段（fragment）**，不是完整响应。它在实际响应中位于统一信封的 `data` 内，完整形态如下：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "id": 1,
    "name": "MIDAS Gen 主客户端",
    "software": "MIDAS Gen",
    "status": "connected",
    "api_key_configured": true,
    "api_key_masked": "********",
    "access_token_configured": true,
    "access_token_masked": "********"
  },
  "request_id": "req_20260925_000065",
  "timestamp": "2026-09-25T08:32:30+08:00"
}
```

> **C-3 裁决（全局约定）**：`api_key_configured` / `api_key_masked` 是**全局唯一的**敏感字段回显形式，适用于所有包含加密字段的资源（`midas_clients`、`models`、`mcp_client_credentials`、`system_configs` 等）。
> 字段名前缀按实际字段替换（`api_key_` / `access_token_` / `secret_`）。依据：《总纲》§4.7.2。

## 9.4 修改

```http
PUT /api/v1/midas/clients/{id}
```

## 9.5 删除

```http
DELETE /api/v1/midas/clients/{id}
```

## 9.6 测试连接

```http
POST /api/v1/midas/clients/{id}/test
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "connected": true,
    "latency_ms": 42,
    "software": "MIDAS Gen",
    "version": "2026"
  },
  "request_id": "req_20260925_000006",
  "timestamp": "2026-09-25T08:33:00+08:00"
}
```

## 9.7 连接

```http
POST /api/v1/midas/clients/{id}/connect
```

## 9.8 断开

```http
POST /api/v1/midas/clients/{id}/disconnect
```

---

# 10. Adapter API

> Adapter Protocol、Adapter 元数据与生命周期状态由《StructAI MCP V2.1 设计框架规范》§13、§14、§15 拥有。本节仅定义查询接口。

## 10.1 Adapter列表

```http
GET /api/v1/adapters
```

## 10.2 Adapter详情

```http
GET /api/v1/adapters/{code}
```

## 10.3 Adapter能力

```http
GET /api/v1/adapters/{code}/capabilities
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "adapter": "midas_gen",
    "capabilities": [
      {
        "code": "node.create",
        "resource": "node",
        "action": "create",
        "enabled": true
      },
      {
        "code": "element.create",
        "resource": "element",
        "action": "create",
        "enabled": true
      },
      {
        "code": "analysis.run",
        "resource": "analysis",
        "action": "run",
        "enabled": true
      }
    ]
  },
  "request_id": "req_20260925_000007",
  "timestamp": "2026-09-25T08:34:00+08:00"
}
```

> Capability 的语义与编码规则由《V2.1 设计框架规范》§16 拥有。

---

# 11. 工具 API

对应原型：

```text
工具与接口
```

## 11.1 Tool列表

```http
GET /api/v1/tools
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "items": [
      {
        "name": "midas_query",
        "display_name": "MIDAS查询",
        "version": "2.1",
        "enabled": true
      },
      {
        "name": "midas_model",
        "display_name": "MIDAS模型",
        "version": "2.1",
        "enabled": true
      },
      {
        "name": "midas_execute",
        "display_name": "MIDAS执行",
        "version": "2.1",
        "enabled": true
      },
      {
        "name": "midas_task",
        "display_name": "MIDAS任务",
        "version": "2.1",
        "enabled": true
      }
    ]
  },
  "request_id": "req_20260925_000008",
  "timestamp": "2026-09-25T08:35:00+08:00"
}
```

> 4 个 Tool 的名称与 JSON Schema 由《V2.1 设计框架规范》§7-§11 拥有。`version` 为 MCP Tool Schema 版本（`2.1`），与 REST 的 `/api/v1` 是两条独立版本轴，见 §60。

---

# 12. Tool 详情

```http
GET /api/v1/tools/{tool_name}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "name": "midas_model",
    "version": "2.1",
    "description": "MIDAS模型统一操作工具",
    "input_schema": {},
    "output_schema": {},
    "enabled": true
  },
  "request_id": "req_20260925_000009",
  "timestamp": "2026-09-25T08:35:10+08:00"
}
```

> `input_schema` / `output_schema` 的完整内容由《V2.1 设计框架规范》§7-§11 拥有；本接口**原样转发**其 Schema，不在本文档中重定义。

---

# 13. Tool接口列表

```http
GET /api/v1/tools/{tool_name}/interfaces
```

支持：

```text
?adapter=midas_gen
&resource=node
&action=create
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "items": [
      {
        "id": 1,
        "interface_code": "node.create",
        "adapter_code": "midas_gen",
        "tool_name": "midas_model",
        "resource": "node",
        "action": "create"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 1,
      "total_pages": 1
    }
  },
  "request_id": "req_20260925_000010",
  "timestamp": "2026-09-25T08:36:00+08:00"
}
```

> Tool ↔ Interface 的映射规则由《V2.1 设计框架规范》§17 拥有。同一 Interface 可挂给多个 Tool（`tool_interfaces` 唯一键为 `(adapter_code, interface_code)`）。

---

# 14. Interface 详情

```http
GET /api/v1/interfaces/{id}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "id": 1,
    "interface_code": "node.create",
    "adapter_code": "midas_gen",
    "method": "POST",
    "endpoint": "/api/model/nodes",
    "operation": "create",
    "resource": "node",
    "request_schema": {},
    "response_schema": {}
  },
  "request_id": "req_20260925_000011",
  "timestamp": "2026-09-25T08:36:10+08:00"
}
```

> `request_schema` / `response_schema` 由《V2.1 设计框架规范》§17 拥有。

---

# 15. Schema API

> Schema 的版本与唯一键规则（`UNIQUE(schema_code, version)`）由《V2.1 设计框架规范》§4 拥有。

## 15.1 Schema列表

```http
GET /api/v1/schemas
```

## 15.2 Schema详情

```http
GET /api/v1/schemas/{schema_code}
```

支持指定版本：

```text
?version=2.1
```

## 15.3 Schema验证

```http
POST /api/v1/schemas/{schema_code}/validate
```

请求：

```json
{
  "data": {
    "x": 0,
    "y": 0,
    "z": 3.6
  }
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "valid": true,
    "errors": []
  },
  "request_id": "req_20260925_000012",
  "timestamp": "2026-09-25T08:37:00+08:00"
}
```

---

# 16. Capability Matrix API

对应原型：

```text
接口能力矩阵
```

```http
GET /api/v1/capabilities/matrix
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "adapters": [
      "midas_gen",
      "midas_civil"
    ],
    "resources": [
      "node",
      "element",
      "material",
      "section",
      "load",
      "analysis"
    ],
    "matrix": [
      {
        "adapter": "midas_gen",
        "node.create": true,
        "node.read": true,
        "element.create": true,
        "analysis.run": true
      }
    ]
  },
  "request_id": "req_20260925_000013",
  "timestamp": "2026-09-25T08:38:00+08:00"
}
```

> Capability 语义、编码与 Capability ↔ Interface 多对多关系由《V2.1 设计框架规范》§16 与 §17 拥有。

---

# 17. Tool测试 API

对应：

```text
工具接口测试
```

```http
POST /api/v1/tools/{tool_name}/test
```

请求：

```json
{
  "adapter": "midas_gen",
  "input": {
    "target": "node",
    "action": "list",
    "page": 1,
    "page_size": 10
  }
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "latency_ms": 35,
    "tool": "midas_query",
    "result": {
      "items": [],
      "pagination": {
        "page": 1,
        "page_size": 10,
        "total": 0,
        "total_pages": 0
      }
    },
    "warnings": []
  },
  "request_id": "req_20260925_000014",
  "timestamp": "2026-09-25T08:39:00+08:00"
}
```

> **A-5 裁决**：本接口是 **REST 接口**，必须使用 REST 信封；`latency_ms` 必须放在 `data` 内，不得置于顶层。
> MCP 信封（`tool` / `status` / `warnings` / `errors`）仅适用于 MCP Protocol Endpoint，两种信封**不得混用**。依据：《总纲》§4.3.2。

---

# 18. 模型管理 API

对应原型：

```text
系统设置 → 模型设置
```

## 18.1 Provider

```http
GET /api/v1/model-providers
POST /api/v1/model-providers
PUT /api/v1/model-providers/{id}
DELETE /api/v1/model-providers/{id}
```

## 18.2 Model

```http
GET /api/v1/models
POST /api/v1/models
GET /api/v1/models/{id}
PUT /api/v1/models/{id}
DELETE /api/v1/models/{id}
```

> `models.id` 为 **INTEGER** 主键。所有引用模型的字段（`model_id`）一律使用该整数，见 §62 与《总纲》§4.1.1、§5.4 N-6。

## 18.3 设置默认模型

```http
POST /api/v1/models/{id}/default
```

## 18.4 测试模型

```http
POST /api/v1/models/{id}/test
```

请求：

```json
{
  "message": "请生成一个简单的钢柱建模计划"
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "model": "<model_code>",
    "latency_ms": 843,
    "response": "..."
  },
  "request_id": "req_20260925_000015",
  "timestamp": "2026-09-25T08:40:00+08:00"
}
```

> **C-8 裁决**：`data.model` 为**占位符** `<model_code>`，取值来自被测试模型记录自身的 `model_code` 字段，禁止在文档或代码中硬编码具体模型名。

---

# 19. 模型参数 API

```http
GET /api/v1/models/{id}/parameters
PUT /api/v1/models/{id}/parameters
```

参数：

```json
{
  "temperature": 0.7,
  "top_p": 0.9,
  "max_output_tokens": 4096,
  "stream_enabled": true,
  "tool_calling_enabled": true,
  "json_output_enabled": true,
  "max_retries": 3
}
```

---

# 20. 任务 API

对应：

```text
任务监控
```

> **C-4 裁决**：一切异步任务的 ID 一律使用 `task_` 前缀，形式为 `task_<yyyymmdd>_<6位序号>`（示例 `task_20260925_000001`）。
> 子类型由 `tasks.type` 区分，**不得**使用 `task_calc_*` / `task_ai_*` / `analysis_*` / `optimization_*` / `export_*` / `report_*` / `model_import_*` / `drawing_*` 等前缀。依据：《总纲》§4.1.4。

## 20.1 任务列表

```http
GET /api/v1/tasks
```

参数：

```text
?page=1
&page_size=20
&status=running
&type=calculate
&action=analysis
&adapter=midas_gen
&keyword=xxx
```

**`type` 与 `action` 的区别（A-6 裁决）：**

```text
type    = 业务任务类型（封闭枚举，所有者：《V2.1 设计框架规范》§4 的 tasks.type CHECK 约束）
action  = 具体动作（引用 MCP action 词表：create / list / read / update / delete / run / ...）
```

- `type` 回答「这是哪一类业务任务」，例如 `calculate`、`drawing_recognize`、`report`、`export`（示例取自《总纲》§4.1.4）
- `action` 回答「这一任务在做什么动作」，与 MCP Tool 的 `action` 词表同源
- 二者是**两个独立维度**，可以叠加过滤，例如「所有计算类任务中执行分析动作的」= `?type=calculate&action=analysis`
- **`type` 的完整允许取值以《V2.1 设计框架规范》§4 为准，本文档不重定义、不新增**

> 原 v1.1 的 `?type=calculate` 只表达了业务类型，缺少动作维度，且未说明取值来源。本版按 A-6 拆分为 `type` + `action` 两个参数。

## 20.2 任务详情

```http
GET /api/v1/tasks/{task_id}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "task_id": "task_20260925_000001",
    "type": "calculate",
    "action": "analysis",
    "status": "running",
    "progress": 45,
    "tool_name": "midas_execute",
    "adapter_code": "midas_gen",
    "request_id": "req_20260925_000001",
    "created_at": "2026-09-25T08:41:00+08:00",
    "started_at": "2026-09-25T08:41:02+08:00",
    "finished_at": null
  },
  "request_id": "req_20260925_000016",
  "timestamp": "2026-09-25T08:41:30+08:00"
}
```

> `status` 取值见《总纲》§4.2.1（`queued / running / success / failed / cancelled / retrying`）。
> `progress` 单位为百分比（0–100 REAL），见《总纲》§4.5.2。

## 20.3 创建任务

一般情况下由 Tool 执行自动创建。

如果管理端需要：

```http
POST /api/v1/tasks
```

## 20.4 取消

```http
POST /api/v1/tasks/{task_id}/cancel
```

## 20.5 重试

```http
POST /api/v1/tasks/{task_id}/retry
```

> 需 `task:retry` 权限，权限码由《总纲》§4.8.2 拥有。

## 20.6 任务结果

```http
GET /api/v1/tasks/{task_id}/result
```

## 20.7 任务事件

```http
GET /api/v1/tasks/{task_id}/events
```

---

# 21. 任务实时 SSE

```http
GET /api/v1/tasks/{task_id}/stream
```

> **例外 1（SSE 流）**：本接口返回 `text/event-stream`，不使用统一信封。

事件：

```text
event: task.started
data: {"task_id":"task_20260925_000001","type":"calculate","action":"analysis"}

event: task.progress
data: {"task_id":"task_20260925_000001","progress":25}

event: task.progress
data: {"task_id":"task_20260925_000001","progress":75}

event: task.completed
data: {"task_id":"task_20260925_000001","status":"success","progress":100}
```

事件名与载荷：

| 事件名 | 载荷字段 | 触发时机 |
|---|---|---|
| `task.started` | `task_id` `type` `action` | 任务进入 `running` |
| `task.progress` | `task_id` `progress` | 进度变化 |
| `task.completed` | `task_id` `status` `progress` | 任务进入 `success` / `failed` / `cancelled` |
| `task.retrying` | `task_id` `retry_count` | 任务进入 `retrying` |

前端：

```javascript
const source = new EventSource(
  `/api/v1/tasks/${taskId}/stream`
);

source.addEventListener("task.progress", event => {
    const data = JSON.parse(event.data);
    updateProgress(data.progress);
});
```

---

# 22. 日志中心 API

## 22.1 日志列表

```http
GET /api/v1/logs
```

支持：

```text
?level=ERROR
&module=adapter
&task_id=task_20260925_000001
&keyword=timeout
&start_time=...
&end_time=...
&page=1
&page_size=50
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "items": [
      {
        "id": 1001,
        "timestamp": "2026-09-25T08:41:05+08:00",
        "level": "ERROR",
        "module": "adapter",
        "task_id": "task_20260925_000001",
        "adapter_request_id": "adapter_20260925_000001",
        "message": "upstream timeout"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 50,
      "total": 1,
      "total_pages": 1
    }
  },
  "request_id": "req_20260925_000017",
  "timestamp": "2026-09-25T08:42:00+08:00"
}
```

## 22.2 日志详情

```http
GET /api/v1/logs/{id}
```

## 22.3 日志 SSE

```http
GET /api/v1/logs/stream
```

> **例外 1（SSE 流）**：本接口返回 `text/event-stream`，不使用统一信封。

事件：

```text
event: log.appended
data: {"id":1002,"timestamp":"2026-09-25T08:42:10+08:00","level":"INFO","module":"task","message":"task progress 80%"}
```

---

# 23. 审计日志 API

```http
GET /api/v1/audit-logs
```

仅允许：

```text
super_admin
```

或具有：

```text
system:audit
```

权限的角色访问。

> **权限归属说明**：`system:audit` 权限码定义于《总纲》§4.8.2（模块 `system`），审计模块**复用**该权限码，不另立 `audit:*` 权限。
> `audit_logs` 表结构与索引由《V2.1 设计框架规范》§4 拥有。

---

# 24. 用户管理 API

对应：

```text
用户与权限
```

## 24.1 用户列表

```http
GET /api/v1/users
```

## 24.2 创建用户

```http
POST /api/v1/users
```

请求：

```json
{
  "username": "zhangsan",
  "name": "张三",
  "email": "zhangsan@company.com",
  "password": "********",
  "roles": [
    "engineer"
  ]
}
```

## 24.3 用户详情

```http
GET /api/v1/users/{id}
```

## 24.4 修改

```http
PUT /api/v1/users/{id}
```

## 24.5 删除

```http
DELETE /api/v1/users/{id}
```

## 24.6 禁用

```http
POST /api/v1/users/{id}/disable
```

## 24.7 启用

```http
POST /api/v1/users/{id}/enable
```

## 24.8 重置密码

```http
POST /api/v1/users/{id}/reset-password
```

> `users.status` 取值见《总纲》§4.2.5（`enabled / disabled / locked`）。

---

# 25. 角色 API

```http
GET /api/v1/roles
POST /api/v1/roles
GET /api/v1/roles/{id}
PUT /api/v1/roles/{id}
DELETE /api/v1/roles/{id}
```

> 默认角色与权限映射（`super_admin` / `engineer` / `analyst` / `visitor`）由《总纲》§4.8.3 拥有。

---

# 26. 权限 API

```http
GET /api/v1/permissions
GET /api/v1/roles/{id}/permissions
PUT /api/v1/roles/{id}/permissions
```

**权限码的完整清单（封闭集合）由《总纲》§4.8.2 拥有，本文档不重定义。**

本文档涉及的权限码均为该清单的一部分：

```text
system:read    system:write    system:audit        ← system:audit 为新增
task:read      task:cancel     task:retry          ← task:retry 为新增

assistant:read      assistant:chat       assistant:plan
assistant:confirm   assistant:execute    assistant:drawing
assistant:modeling  assistant:optimize   assistant:report
```

> 上述 `system:audit` 与全部 `assistant:*` 权限码均属《总纲》§4.8.2 定义的封闭清单；`GET /api/v1/permissions` 返回的集合必须与该清单**逐字一致**。

---

# 27. 系统基础设置 API

对应：

```text
系统设置 → 基础设置
```

```http
GET /api/v1/settings
PUT /api/v1/settings
```

请求：

```json
{
  "system_name": "StructAI MCP 管理器",
  "language": "zh-CN",
  "timezone": "Asia/Shanghai",
  "theme": "light"
}
```

> `timezone` 决定 API 输出时间的时区偏移（默认 `Asia/Shanghai`），见《总纲》§4.5.1。

---

# 28. 服务配置 API

```http
GET /api/v1/settings/service
PUT /api/v1/settings/service
```

例如：

```json
{
  "host": "0.0.0.0",
  "port": 8765,
  "workers": 2,
  "log_level": "INFO",
  "cors_enabled": true,
  "auto_start": true
}
```

修改端口后建议：

```text
保存
  ↓
提示需要重启
  ↓
POST /api/v1/mcp/server/restart
```

> 本节的 `service_configs` 是 `log_level` 的**唯一落库位置**；§7.2 的 `PUT /api/v1/mcp/server` 收到 `log_level` 后也写入此处（A-2）。

---

# 29. 安全设置 API

```http
GET /api/v1/settings/security
PUT /api/v1/settings/security
```

请求：

```json
{
  "captcha_enabled": false,
  "api_auth_required": true,
  "password_min_length": 8,
  "password_complexity": true,
  "max_login_attempts": 5,
  "lock_minutes": 30,
  "session_timeout_minutes": 30,
  "login_log_enabled": true,
  "rate_limit_enabled": true,
  "rate_limit_per_minute": 120,
  "rate_limit_burst": 20
}
```

> **C-13 裁决**：`api_auth_required` 为必填字段，补齐 v1.1 的缺失。
> `rate_limit_*` 三个字段对应 `security_configs` 新增列（《总纲》§5.2 B-7）。
> `session_timeout_minutes` 是 §5.1 登录响应 `expires_in` 的计算依据（C-9）。

---

# 30. 数据管理 API

对应：

```text
数据管理
```

> **归属说明**：数据库 schema（表结构、表数量、索引、外键）由《StructAI MCP V2.1 设计框架规范》§4 拥有。
> 最终 schema 为 **49 张表**。本文档只引用，不列出表清单。

## 30.1 数据库信息

```http
GET /api/v1/data/info
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "database_size": 1336934400,
    "table_count": 49,
    "health": "healthy",
    "last_backup_at": "2026-09-21T02:30:00+08:00"
  },
  "request_id": "req_20260925_000018",
  "timestamp": "2026-09-25T08:43:00+08:00"
}
```

> **N-18 裁决**：`table_count` 由 `28` 更正为 **`49`**（原 28 张 + 新增 21 张，见《总纲》§6.1）。
> `database_size` 单位为**字节**。

## 30.2 立即备份

```http
POST /api/v1/data/backups
```

## 30.3 备份列表

```http
GET /api/v1/data/backups
```

> `backups.backup_id` 使用 `bk_` 前缀；`backups.status` 取值见《总纲》§4.2.5（`processing / success / failed`）。

## 30.4 下载备份

```http
GET /api/v1/data/backups/{id}/download
```

> **例外 2（文件下载）**：本接口返回二进制流，不使用统一信封。

## 30.5 恢复备份

```http
POST /api/v1/data/backups/{id}/restore
```

恢复属于高风险操作。

必须：

```text
RBAC（data:restore，仅 super_admin）
+
审计
+
二次确认
+
当前数据库自动备份
```

> **`data:restore` 仅 `super_admin` 可用**，依据《总纲》§4.8.4。
> **AI 工程助手不得调用本接口**，见 §69 与 §94。

---

# 31. 数据导出

```http
POST /api/v1/data/export
```

请求：

```json
{
  "scope": [
    "system_configs",
    "users",
    "models",
    "tools",
    "tasks"
  ],
  "format": "json"
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "status": "queued",
    "task_id": "task_20260925_000005"
  },
  "request_id": "req_20260925_000019",
  "timestamp": "2026-09-25T08:44:00+08:00"
}
```

> **C-4 裁决**：导出任务 ID 为 `task_20260925_000005`，其 `tasks.type` 为导出类业务类型（取值见《V2.1 设计框架规范》§4）。
> 原 v1.1 的 `export_xxx` 前缀**已废止**（《总纲》§4.1.4）。
> `data_exports.export_id` 使用 `exp_` 前缀，是**导出记录**的业务 ID，与 `task_id` 是两个不同的标识。

---

# 32. 数据导入

```http
POST /api/v1/data/import
```

使用：

```text
multipart/form-data
```

请求字段：

```text
file
scope
overwrite
```

导入前必须：

```text
文件校验
 ↓
Schema 校验
 ↓
数据预览
 ↓
冲突检测
 ↓
用户确认
 ↓
事务导入
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "status": "queued",
    "task_id": "task_20260925_000006",
    "import_id": "imp_20260925_000001"
  },
  "request_id": "req_20260925_000020",
  "timestamp": "2026-09-25T08:45:00+08:00"
}
```

> 导入文件校验失败返回 `IMPORT_VALIDATION_FAILED`，错误码定义见《总纲》§4.4.9。

---

# 33. 数据清理

```http
POST /api/v1/data/cleanup
```

请求：

```json
{
  "task_logs": true,
  "system_logs": true,
  "audit_logs": false,
  "temporary_files": true
}
```

接口必须返回清理统计：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "deleted": {
      "task_logs": 18234,
      "system_logs": 9312,
      "temporary_files": 42
    }
  },
  "request_id": "req_20260925_000021",
  "timestamp": "2026-09-25T08:46:00+08:00"
}
```

---

# 34. 系统健康检查

```http
GET /api/v1/health
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "status": "healthy",
    "database": "healthy",
    "mcp_server": "running",
    "adapter": "healthy",
    "disk": "healthy"
  },
  "request_id": "req_20260925_000022",
  "timestamp": "2026-09-25T08:47:00+08:00"
}
```

> **注意：聚合健康检查 `/api/v1/health` 不属于信封例外**，必须使用标准信封。依据：《总纲》§4.3.1。

---

# 35. 就绪检查

用于 Docker/Kubernetes：

```http
GET /api/v1/health/ready
```

未准备完成：

```text
503
```

> **例外 3（健康探针）**：本接口按容器编排要求返回**裸状态码**，不使用统一信封。依据：《总纲》§4.3.1。

---

# 36. 存活检查

```http
GET /api/v1/health/live
```

正常：

```text
200
```

> **例外 3（健康探针）**：本接口按容器编排要求返回**裸状态码**，不使用统一信封。依据：《总纲》§4.3.1。

---

# 37. MCP Protocol Endpoint

REST 管理 API 与 MCP Protocol Endpoint 必须分离。

建议：

```text
/api/v1/*
```

用于管理。

MCP：

```text
/mcp
```

例如：

```text
http://127.0.0.1:8765/mcp
```

MCP Client 连接：

```text
POST /mcp
```

MCP 内部暴露：

```text
midas_query
midas_model
midas_execute
midas_task
```

> **归属说明**：4 个 MCP Tool 的名称、`action` / `resource` 枚举与完整 JSON Schema 由《StructAI MCP V2.1 设计框架规范》§7-§11 拥有。
> 本节**只声明 Tool 名称清单**，不重述其 Schema。MCP 侧的返回信封（`tool` / `status` / `warnings` / `errors`）由《V2.1 设计框架规范》§11 拥有，与本文档 §3.2 的 REST 信封**不得混用**。

---

# 38. MCP Tool Dispatcher

内部流程：

```text
MCP Request
    ↓
Authentication
    ↓
RBAC
    ↓
Tool Validation
    ↓
Capability Resolver
    ↓
Adapter Registry
    ↓
Interface Mapping
    ↓
Adapter
    ↓
MIDAS API
    ↓
Normalize Result
    ↓
MCP Response
```

> Dispatcher 的输入校验规则（`additionalProperties: false`、`oneOf` 分资源子 Schema、Capability `request_schema_json` 二次校验）由《V2.1 设计框架规范》§7-§9 与 §16 拥有。

---

# 39. MCP Tool 与 REST 的对应关系

| MCP Tool | REST 管理接口 |
|---|---|
| `midas_query` | `/api/v1/midas/*` |
| `midas_model` | `/api/v1/midas/model/*` |
| `midas_execute` | `/api/v1/midas/execute` |
| `midas_task` | `/api/v1/tasks/*` |

注意：

REST API 是管理与调试接口。

MCP Tool 是给 AI Agent 的稳定执行接口。

二者共享 Service Layer。

> **归属说明**：上表仅是「MCP Tool ↔ REST 门面」的**路由对照**。每个 Tool 的 `action` / `resource` 枚举与参数 Schema 由《StructAI MCP V2.1 设计框架规范》§7-§11 拥有，本文档不重述。
> 三条数据流（运维路径、AI 助手路径、外部 Agent 直连 MCP）在 Service Layer 汇合，见《总纲》§2.3。

---

# 40. MIDAS 模型 REST API

为了 Web UI 调试，也可以提供：

```http
GET /api/v1/midas/model/{resource}
```

例如：

```http
GET /api/v1/midas/model/nodes
GET /api/v1/midas/model/elements
GET /api/v1/midas/model/materials
GET /api/v1/midas/model/sections
GET /api/v1/midas/model/loads
```

但这些接口最终必须调用：

```text
ModelService
```

而不是直接调用 MIDAS Adapter。

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "items": [
      {
        "id": 1001,
        "x": 0.0,
        "y": 0.0,
        "z": 0.0
      },
      {
        "id": 1002,
        "x": 6.0,
        "y": 0.0,
        "z": 0.0
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 2,
      "total_pages": 1
    }
  },
  "request_id": "req_20260925_000023",
  "timestamp": "2026-09-25T08:48:00+08:00"
}
```

> REST 路径资源名为**复数**（`nodes`），MCP resource 为**单数**（`node`），转换责任见《总纲》§4.6.1。
> 坐标单位为 **m**，见《总纲》§4.5.2。

---

# 41. 模型创建

```http
POST /api/v1/midas/model/nodes
```

请求：

```json
{
  "nodes": [
    {
      "id": 1001,
      "x": 0,
      "y": 0,
      "z": 0
    },
    {
      "id": 1002,
      "x": 6,
      "y": 0,
      "z": 0
    }
  ],
  "validate": true,
  "transactional": true
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "created": 2,
    "failed": 0,
    "ids": [
      1001,
      1002
    ]
  },
  "request_id": "req_20260925_000024",
  "timestamp": "2026-09-25T08:49:00+08:00"
}
```

---

# 42. 模型修改

```http
PATCH /api/v1/midas/model/nodes/{id}
```

请求：

```json
{
  "x": 6,
  "y": 0,
  "z": 3.6
}
```

---

# 43. 模型删除

```http
DELETE /api/v1/midas/model/nodes/{id}
```

高风险操作建议：

```json
{
  "confirm": true
}
```

---

# 44. 模型校验

```http
POST /api/v1/midas/model/validate
```

请求：

```json
{
  "model_id": 1,
  "scope": [
    "nodes",
    "elements",
    "loads"
  ]
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "valid": false,
    "errors": [
      {
        "code": "NODE_NOT_FOUND",
        "message": "单元 1002 引用了不存在的节点"
      }
    ],
    "warnings": [
      {
        "code": "LOAD_LOW",
        "message": "当前荷载低于配置规范建议值"
      }
    ]
  },
  "request_id": "req_20260925_000025",
  "timestamp": "2026-09-25T08:50:00+08:00"
}
```

> **注意**：`data.errors[].code` / `data.warnings[].code` 是**模型校验业务问题码**，与《总纲》§4.4 的**接口错误码**是两套不同用途的编码；接口级错误仍使用 `code` 字段（顶层信封）。

---

# 45. 计算 API

```http
POST /api/v1/midas/analysis/run
```

请求：

```json
{
  "model_id": 1,
  "analysis_type": "static",
  "options": {
    "async": true,
    "timeout_seconds": 3600
  }
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "status": "queued",
    "task_id": "task_20260925_000001"
  },
  "request_id": "req_20260925_000026",
  "timestamp": "2026-09-25T08:51:00+08:00"
}
```

> **C-4 裁决**：原 `task_calc_001` 已废止，改为 `task_20260925_000001`，其 `tasks.type` 为 `calculate`（示例取自《总纲》§4.1.4），子类型由 `tasks.type` 区分，不体现在 ID 前缀上。

> **N-2 裁决（运维门面 vs AI 门面）**：
>
> ```text
> 运维门面（本接口）      POST /api/v1/midas/analysis/run
> AI 门面                 POST /api/v1/assistant/analysis/run     （见 §80）
> ```
>
> - 两者**共享同一个 Service Layer**（AnalysisService），禁止各自实现一套业务逻辑
> - 两者请求体与响应体的**字段名必须完全一致**（`model_id` / `analysis_type` / `cases` / `options` / `async`）
> - 两者响应体**同构**：均返回 `data.status` + `data.task_id`
> - 差异仅在于鉴权门面与调用来源：运维门面由管理端调用，AI 门面由 AI 工程助手调用
>
> 依据：《总纲》§5.4 N-2。

---

# 46. 计算结果

```http
GET /api/v1/midas/results
```

例如：

```text
?type=displacement
&node_id=1001
&load_case=LC1
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "model_id": 1,
    "node_id": 1001,
    "load_case": "LC1",
    "ux": 0.001,
    "uy": -0.003,
    "uz": -0.012
  },
  "request_id": "req_20260925_000027",
  "timestamp": "2026-09-25T08:52:00+08:00"
}
```

> 位移单位为 **mm**，见《总纲》§4.5.2。

---

# 47. 报告 API

```http
POST /api/v1/reports
```

请求：

```json
{
  "project_id": 1,
  "model_id": 1,
  "report_type": "structural_calculation",
  "format": "pdf",
  "include": [
    "project_info",
    "model",
    "materials",
    "loads",
    "load_combinations",
    "analysis",
    "design",
    "warnings",
    "results"
  ]
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "status": "queued",
    "task_id": "task_20260925_000007",
    "report_id": "rpt_20260925_000001"
  },
  "request_id": "req_20260925_000028",
  "timestamp": "2026-09-25T08:53:00+08:00"
}
```

> **C-4 裁决**：原 `report_xxx` 已废止，改为 `task_20260925_000007`（`tasks.type` 为报告类业务类型）。
> `report_id` 使用 `rpt_` 前缀，是 `reports` 表的业务 ID，与 `task_id` 是两个不同的标识。
> **N-6 裁决**：`project_id`、`model_id` 一律为 **INTEGER**，对应 `projects.id`、`models.id`。

> **N-2 / N-14 裁决（报告字段统一）**：
>
> ```text
> 运维门面（本接口）      POST /api/v1/reports
> AI 门面                 POST /api/v1/assistant/reports     （见 §84）
> ```
>
> - 两者**共享同一个 Service Layer**（ReportService），禁止各自实现一套业务逻辑
> - **报告请求字段在运维门面与 AI 门面中完全一致**，统一为：
>
> ```text
> report_type     报告类型（原 v1.1 §47 的 type、§87 的 report_type 统一为 report_type）
> include[]       报告包含章节（原 v1.1 §47 的 sections、§87 的 include 统一为 include[]）
> format          输出格式
> project_id      项目 ID（INTEGER）
> model_id        模型 ID（INTEGER）
> ```
>
> - **原 v1.1 §47 的 `type` 与 `sections` 字段名废止**，一律使用 `report_type` + `include[]`
> - 响应体同构：均返回 `data.status` + `data.task_id` + `data.report_id`
>
> 依据：《总纲》§5.4 N-2、N-14。

---

# 48. 请求追踪

每一次 API 请求必须生成：

```text
request_id
```

格式遵循《总纲》§4.1.2：

```text
<前缀>_<yyyymmdd>_<6位十进制序号>
```

例如：

```text
req_20260925_000001
```

如果触发任务：

```text
request_id
    ↓
task_id
    ↓
adapter_request_id
```

方便完整追踪。

> 三者必须能从任一端互相查到：`tasks` 表保存 `request_id`，`system_logs` 保存 `adapter_request_id`。依据：《总纲》§4.1.5。
> **注意**：`request_id` 的格式是 `req_20260925_000001`，v1.1 中的 `req_20260925_083012_8F32` 形式**已废止**。

---

# 49. 错误结构

统一：

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
  "request_id": "req_20260925_000029",
  "timestamp": "2026-09-25T08:54:00+08:00"
}
```

> 失败响应同样必须包含 `success` / `code` / `message` / `request_id` / `timestamp`；`details` 与 `data` 为可选字段。

---

# 50. 错误码（引用总纲）

**错误码注册表由《StructAI 架构边界与融合规范 v1.0（总纲）》§4.4 唯一拥有。**

本文档**不定义、不新增**任何错误码；全部接口返回的 `code` 必须来自该注册表。

```text
唯一真源： 《总纲》§4.4 错误码注册表
本文档角色：引用者
```

注册表分类索引见本文档 **附录 错误码引用表**。

## 50.1 旧名别名映射（迁移期兼容）

以下映射表逐字收录自《总纲》§4.4.10，实现方在迁移期必须按此归一：

| 旧名 | 出处 | 归一为 |
|---|---|---|
| `AUTH_FAILED` | V2.0 §20 | `AUTH_INVALID` |
| `VALIDATION_FAILED` | V2.0 §20 | `VALIDATION_ERROR` |
| `TIMEOUT` | V2.0 §20 | `TASK_TIMEOUT` / `MODEL_TIMEOUT` |
| `INVALID_REQUEST` | V2.0 §20 | `VALIDATION_ERROR` |
| `MCP_*` 以外未列出者 | — | `INTERNAL_ERROR` |

> 迁移期结束后，旧名不再对外返回；服务端可在日志中记录旧名到新名的归一动作。

---

# 51. 分页规范

统一：

```text
?page=1&page_size=20
```

响应（位于统一信封的 `data` 内）：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 128,
      "total_pages": 7
    }
  },
  "request_id": "req_20260925_000030",
  "timestamp": "2026-09-25T08:55:00+08:00"
}
```

最大：

```text
page_size <= 500
```

> 分页结构统一为 `data.items` + `data.pagination`，禁止顶层裸 `items`。依据：《总纲》§4.3.1。

---

# 52. 排序

统一：

```text
?sort_by=created_at
&sort_order=desc
```

后端必须使用白名单字段，禁止直接拼接用户输入 SQL。

---

# 53. 搜索

统一：

```text
?keyword=deepseek
```

支持：

```text
模型名
用户名
任务ID
接口名称
Adapter名称
日志内容
```

---

# 54. 前端页面与 API 映射

## 首页

```text
GET /dashboard/overview
GET /health
```

## MIDAS客户端

```text
GET    /midas/clients
POST   /midas/clients
PUT    /midas/clients/{id}
DELETE /midas/clients/{id}
POST   /midas/clients/{id}/test
POST   /midas/clients/{id}/connect
POST   /midas/clients/{id}/disconnect
```

## MCP服务器

```text
GET  /mcp/server
PUT  /mcp/server
POST /mcp/server/start
POST /mcp/server/stop
POST /mcp/server/restart
```

> 状态接口只有 `GET /mcp/server`；`/mcp/server/status` **不是合法路径**（A-1）。

## 工具与接口

```text
GET  /tools
GET  /tools/{name}
GET  /tools/{name}/interfaces
GET  /interfaces/{id}
GET  /capabilities/matrix
POST /tools/{name}/test
```

## 任务监控

```text
GET  /tasks
GET  /tasks/{id}
POST /tasks/{id}/cancel
POST /tasks/{id}/retry
GET  /tasks/{id}/result
GET  /tasks/{id}/events
GET  /tasks/{id}/stream
```

## 日志中心

```text
GET /logs
GET /logs/{id}
GET /logs/stream
GET /audit-logs
```

## 系统设置

```text
GET/PUT /settings
GET/PUT /settings/service
GET/PUT /settings/security
```

## 模型设置

```text
GET/POST       /model-providers
GET/PUT/DELETE /model-providers/{id}

GET/POST       /models
GET/PUT/DELETE /models/{id}
POST           /models/{id}/default
POST           /models/{id}/test
GET/PUT        /models/{id}/parameters
```

## 用户与权限

```text
GET/POST       /users
GET/PUT/DELETE /users/{id}
POST           /users/{id}/enable
POST           /users/{id}/disable
POST           /users/{id}/reset-password

GET/POST       /roles
GET/PUT/DELETE /roles/{id}

GET            /permissions
GET            /roles/{id}/permissions
PUT            /roles/{id}/permissions
```

## 数据管理

```text
GET  /data/info
GET  /data/backups
POST /data/backups
GET  /data/backups/{id}/download
POST /data/backups/{id}/restore
POST /data/export
POST /data/import
POST /data/cleanup
```

## AI 工程助手

见 §95。

---

# 55. 推荐 FastAPI 项目结构

```text
backend/
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py
│   │       ├── dashboard.py
│   │       ├── mcp.py
│   │       ├── midas.py
│   │       ├── adapters.py
│   │       ├── tools.py
│   │       ├── schemas.py
│   │       ├── capabilities.py
│   │       ├── models.py
│   │       ├── tasks.py
│   │       ├── logs.py
│   │       ├── users.py
│   │       ├── roles.py
│   │       ├── settings.py
│   │       ├── data.py
│   │       ├── health.py
│   │       └── assistant/
│   │           ├── sessions.py
│   │           ├── messages.py
│   │           ├── intent.py
│   │           ├── plans.py
│   │           ├── drawing.py
│   │           ├── modeling.py
│   │           ├── loads.py
│   │           ├── code_check.py
│   │           ├── analysis.py
│   │           ├── optimization.py
│   │           ├── reports.py
│   │           ├── templates.py
│   │           ├── examples.py
│   │           ├── history.py
│   │           └── files.py
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── midas_service.py
│   │   ├── tool_service.py
│   │   ├── task_service.py
│   │   ├── model_service.py
│   │   ├── backup_service.py
│   │   ├── audit_service.py
│   │   ├── assistant_service.py
│   │   ├── plan_service.py
│   │   ├── drawing_service.py
│   │   └── report_service.py
│   │
│   ├── adapters/
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── midas_gen/
│   │   ├── midas_civil/
│   │   └── midas_fea/
│   │
│   ├── mcp/
│   │   ├── server.py
│   │   ├── dispatcher.py
│   │   ├── tools/
│   │   │   ├── query.py
│   │   │   ├── model.py
│   │   │   ├── execute.py
│   │   │   └── task.py
│   │   └── capability.py
│   │
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   ├── core/
│   └── workers/
│
├── migrations/
├── tests/
├── requirements.txt
└── Dockerfile
```

---

# 56. API 开发原则

## 原则 1：前后端彻底解耦

Vue 不允许：

```text
直接 SQL
直接 MIDAS API
直接 Adapter
```

## 原则 2：Service Layer 复用

REST：

```text
REST → Service → Adapter
```

MCP：

```text
MCP → Service → Adapter
```

> 运维门面与 AI 门面（N-2）也必须复用同一个 Service，禁止各自实现一套业务逻辑。

## 原则 3：异步操作统一 Task

任何：

```text
计算
导入
导出
备份
恢复
报告生成
大型模型操作
```

都应该进入 Task Engine。

> **量化判据**：凡**可能超过约 3 秒**的操作，一律进入 Task Engine 并返回 `task_id`（N-11）。
> 因此 §78 荷载生成与 §79 规范检查在本版中改为**异步**。

## 原则 4：所有写操作审计

至少记录：

```text
user_id
request_id
action
resource
before
after
result
ip
timestamp
```

## 原则 5：响应信封唯一

任何 `application/json` 响应必须使用 §3.2 的统一信封，例外仅 §3.3 的四类。

## 原则 6：契约不重复定义

表结构、MCP Tool Schema、错误码、状态词表、ID 前缀、权限码一律引用所有者文档，禁止在本文档中重定义（《总纲》§0.3）。

---

# 57. API 安全要求

必须启用：

```text
JWT
RBAC
TLS
Request ID
Rate Limit
Audit Log
Secret Encryption
Input Validation
```

禁止：

```text
SQL Injection
任意 Endpoint 调用
任意 URL 代理
明文 API Key
明文密码日志
前端保存 MIDAS Secret
```

---

# 58. Docker 部署

建议：

```yaml
services:

  midas-mcp:
    build: .
    container_name: structai-mcp
    restart: unless-stopped

    ports:
      - "8765:8765"

    volumes:
      - ./data:/opt/midas-mcp/data
      - ./backups:/opt/midas-mcp/backups
      - ./logs:/opt/midas-mcp/logs

    environment:
      TZ: Asia/Shanghai
      STRUCTAI_MASTER_KEY: ${STRUCTAI_MASTER_KEY}
```

SQLite：

```text
/opt/midas-mcp/data/structai.db
```

> 备份默认目录为 `./data/backups`（相对工作目录，平台自适应），见《总纲》§5.3 C-10。
> `STRUCTAI_MASTER_KEY` 是 AES-256-GCM 主密钥，见《总纲》§4.7.1。

---

# 59. OpenAPI

FastAPI 自动生成：

```text
/openapi.json
/docs
/redoc
```

建议生产环境根据安全要求决定是否公开 `/docs`。

> **例外 4（OpenAPI）**：上述三个端点由框架生成，不使用统一信封。依据：《总纲》§4.3.1。

---

# 60. API 版本策略

当前：

```text
/api/v1
```

未来：

```text
/api/v2
```

V1 不因 MIDAS API 变化而直接破坏。

MIDAS 软件差异由：

```text
Adapter
Capability
Interface Registry
```

处理。

> **版本轴说明（C-5）**：本文档涉及**两条相互独立的版本轴**，二者**无映射关系**：
>
> ```text
> REST API 版本轴         /api/v1 → /api/v2        （本文档拥有）
> MCP Tool Schema 版本轴  tool.version = 2.1       （《V2.1 设计框架规范》拥有）
> ```
>
> MCP Tool Schema 的大版本升级（例如 2.1 → 3.0）**不影响** `/api/v1` 的存在与语义；反之 `/api/v1` → `/api/v2` 也不强制变更 Tool Schema 版本。

---

# 61. 最终架构

```text
                    ┌─────────────────────┐
                    │     StructAI UI     │
                    └──────────┬──────────┘
                               │ REST / SSE
                               ▼
                    ┌─────────────────────┐
                    │    FastAPI API      │
                    ├─────────────────────┤
                    │ Auth / RBAC         │
                    │ Dashboard           │
                    │ Settings            │
                    │ Models              │
                    │ Tasks               │
                    │ Logs                │
                    │ Data                │
                    │ Assistant (AI)      │
                    └──────────┬──────────┘
                               │
                         Service Layer
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
          MCP Dispatcher                Task Engine
                │                             │
        ┌───────┴────────┐                    │
        │                │                    │
        ▼                ▼                    ▼
  Capability       Adapter Registry       Task DB
  Resolver               │
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       MIDAS Gen      MIDAS Civil     MIDAS FEA
       Adapter         Adapter        Adapter
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                    MIDAS Software
```

> 分层模型（L1 表现层 / L2 管理接口层 / L3 领域服务层 / L4 智能编排层 / L5 适配层 / L6 集成层 / L7 持久层）由《总纲》§2.1 拥有。

---

# 62. AI 工程助手 API（StructAI 核心模块）

> **重要：AI 工程助手是 StructAI 的一级核心业务模块，不应仅作为普通聊天页面处理。**
>
> 其定位是：
>
> ```text
> 用户自然语言 / 图纸
>        ↓
> AI工程助手
>        ↓
> 工程意图识别
>        ↓
> 参数提取与规范校验
>        ↓
> Execution Plan
>        ↓
> 高风险操作确认
>        ↓
> Task Engine
>        ↓
> MIDAS Adapter / MCP
>        ↓
> 模型 / 荷载 / 分析 / 设计
>        ↓
> 结果校验
>        ↓
> 计算书 / 图纸 / 模型文件 / 结果
> ```
>
> AI 工程助手不是简单的 LLM Chat，而是 StructAI 的工程智能编排入口。

## 62.1 AI 工程助手页面

前端路由：

```text
/#/ai
```

API 前缀：

```text
/api/v1/assistant
```

页面包含：

```text
AI智能对话
工程模板
示例案例
历史案例
历史记录
智能识图
智能建模
模型视图
计算/验算结果
计算书预览
模型信息
执行过程
常用工程指令
```

## 62.2 AI 模块所需权限（RBAC 标注，N-12）

AI 模块的全部接口**必须逐条鉴权**。权限码取自《总纲》§4.8.2 的封闭清单，本文档不新增权限码。

下表按 **AI 子模块 → 所需权限** 给出统一要求；各接口章节不再重复标注。

| AI 子模块 | 章节 | 所需权限 |
|---|---|---|
| 会话管理（创建 / 列表 / 详情 / 删除） | §63 | `assistant:read` |
| 对话消息（发送 / 历史加载） | §64 | `assistant:chat` |
| 工程意图解析 | §65 | `assistant:chat` |
| 参数与规范校验 | §66 | `assistant:plan` |
| Execution Plan 创建 / 查询 | §67 §68 | `assistant:plan` |
| 高风险确认 | §69 | `assistant:confirm` |
| 计划执行 / 计划取消 | §70 | `assistant:execute` |
| 执行过程（步骤 / SSE） | §71 | `assistant:read` |
| 智能识图（创建任务 / 设置 / 结果 / 尺寸检查） | §72 §73 §74 §75 | `assistant:drawing` |
| 图纸格式转换 | §72.2 | `assistant:drawing` |
| 识图结果转模型 | §76 | `assistant:modeling` |
| 智能建模（自然语言 / 快速向导 / 预览） | §77 | `assistant:modeling` |
| 荷载生成 | §78 | `assistant:modeling` |
| 规范检查 | §79 | `assistant:modeling` |
| AI 分析计算 | §80 | `assistant:execute` |
| 结果解释 | §81 | `assistant:report` |
| 结构优化（运行 / 结果） | §82 §83 | `assistant:optimize` |
| 计算书生成 | §84 | `assistant:report` |
| 图形输出 | §85 | `assistant:report` |
| 工程模板（查询） | §86 | `assistant:read` |
| 工程模板（使用 / 运行） | §86.5 | `assistant:modeling` |
| 示例案例（查询） | §87 | `assistant:read` |
| 示例案例（运行） | §87.4 | `assistant:modeling` |
| 历史案例（查询 / 打开 / 导出 / 删除） | §88 | `assistant:read` |
| 历史案例（再次运行） | §88.3 | `assistant:plan` |
| 历史记录（查询 / 详情） | §89 | `assistant:read` |
| 常用工程指令 | §90 | `assistant:read` |
| 文件管理（查询 / 下载） | §91 | `assistant:read` |
| 文件管理（上传 / 删除） | §91 | `assistant:read` + （图纸类另需 `assistant:drawing`） |

**高风险权限约束（引用《总纲》§4.8.4）：**

```text
assistant:execute   → engineer 及以上，且必须通过 §69 高风险确认流程
data:restore        → 仅 super_admin（AI 助手不得触发，见 §69 / §94）
```

> 默认角色映射（`super_admin` 全部；`engineer` 含 `assistant:*`；`analyst` 仅 `assistant:read` + `assistant:chat`；`visitor` 不含任何 `assistant:*`）由《总纲》§4.8.3 拥有。

---

# 63. AI Assistant Session API

AI 工程助手以 Session 为核心。

> 所需权限：`assistant:read`（§62.2）。

## 63.1 创建会话

```http
POST /api/v1/assistant/sessions
```

请求：

```json
{
  "title": "钢结构厂房建模",
  "model_id": 1,
  "midas_client_id": 1,
  "project_id": null
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "session_id": "asst_20260925_000001",
    "title": "钢结构厂房建模",
    "model_id": 1,
    "midas_client_id": 1,
    "project_id": null,
    "status": "active",
    "created_at": "2026-09-25T09:00:00+08:00"
  },
  "request_id": "req_20260925_000031",
  "timestamp": "2026-09-25T09:00:00+08:00"
}
```

> **N-6 裁决**：`model_id`、`midas_client_id`、`project_id` 一律为 **INTEGER**（对应 `models.id` / `midas_clients.id` / `projects.id`）。
> `session_id` 使用 `asst_` 前缀，是**字符串业务 ID**（《总纲》§4.1.3）。
> `status` 取值见《总纲》§4.2.4（`active / archived`）。

## 63.2 会话列表

```http
GET /api/v1/assistant/sessions
```

参数：

```text
?page=1
&page_size=20
&keyword=钢结构
&status=active
```

## 63.3 会话详情

```http
GET /api/v1/assistant/sessions/{session_id}
```

## 63.4 删除会话

```http
DELETE /api/v1/assistant/sessions/{session_id}
```

---

# 64. AI 对话 API

> 所需权限：`assistant:chat`（§62.2）。

## 64.1 发送工程需求

```http
POST /api/v1/assistant/sessions/{session_id}/messages
```

请求：

```json
{
  "content": "建立一个跨度30米、长度60米、檐口高度10米的钢结构厂房模型，采用H型钢门式刚架。",
  "mode": "engineering",
  "stream": true,
  "auto_execute": false
}
```

系统处理：

```text
自然语言
 ↓
工程意图
 ↓
实体提取
 ↓
参数提取
 ↓
规范校验
 ↓
Execution Plan
```

### 64.1.1 两种响应模式（N-5）

本接口由请求字段 `stream` 决定响应形态，**二者互斥**：

```text
stream = false  →  Content-Type: application/json  →  返回 §3.2 标准信封
stream = true   →  Content-Type: text/event-stream →  返回 SSE 事件流（例外 1）
```

**`stream = false`（标准信封）：**

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "message_id": "msg_20260925_000001",
    "intent_id": "intent_20260925_000001",
    "status": "planning",
    "requires_confirmation": true
  },
  "request_id": "req_20260925_000032",
  "timestamp": "2026-09-25T09:01:00+08:00"
}
```

**`stream = true`（SSE 流，例外 1，不使用信封）：**

```text
event: message.delta
data: {"message_id":"msg_20260925_000001","delta":"正在解析工程需求……"}

event: message.delta
data: {"message_id":"msg_20260925_000001","delta":"已识别为门式刚架钢结构厂房。"}

event: intent.ready
data: {"intent_id":"intent_20260925_000001","intent":"create_structural_model","missing_parameters":["building_length","frame_spacing"]}

event: plan.ready
data: {"plan_id":"plan_20260925_000001","status":"awaiting_confirmation","risk_level":"medium","requires_confirmation":true}

event: done
data: {"message_id":"msg_20260925_000001","status":"awaiting_confirmation"}
```

SSE 事件名与载荷（封闭清单）：

| 事件名 | 载荷字段 | 说明 |
|---|---|---|
| `message.delta` | `message_id` `delta` | LLM 增量文本，可多次出现 |
| `intent.ready` | `intent_id` `intent` `missing_parameters` | 意图解析完成 |
| `plan.ready` | `plan_id` `status` `risk_level` `requires_confirmation` | 执行计划生成完成 |
| `done` | `message_id` `status` | 本次请求结束（正常或异常均发送） |

> `status` 取值来自 `assistant_plans.status`，见《总纲》§4.2.2。
> 依据：《总纲》§5.4 N-5。

### 64.1.2 前端示例

```javascript
const es = new EventSource(
  `/api/v1/assistant/sessions/${sessionId}/messages?stream=true`
);

es.addEventListener("message.delta", e => {
    appendDelta(JSON.parse(e.data).delta);
});

es.addEventListener("plan.ready", e => {
    showPlan(JSON.parse(e.data));
    es.close();
});
```

## 64.2 加载历史对话（N-4）

```http
GET /api/v1/assistant/sessions/{session_id}/messages
```

参数：

```text
?page=1
&page_size=50
&order=asc
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "items": [
      {
        "message_id": "msg_20260925_000001",
        "session_id": "asst_20260925_000001",
        "role": "user",
        "content": "建立一个跨度30米、长度60米、檐口高度10米的钢结构厂房模型，采用H型钢门式刚架。",
        "intent_id": null,
        "created_at": "2026-09-25T09:01:00+08:00"
      },
      {
        "message_id": "msg_20260925_000002",
        "session_id": "asst_20260925_000001",
        "role": "assistant",
        "content": "已识别为门式刚架钢结构厂房，正在生成执行计划。",
        "intent_id": "intent_20260925_000001",
        "created_at": "2026-09-25T09:01:04+08:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 50,
      "total": 2,
      "total_pages": 1
    }
  },
  "request_id": "req_20260925_000033",
  "timestamp": "2026-09-25T09:02:00+08:00"
}
```

> **N-4 裁决**：本接口为 v1.2 新增，用于加载历史对话；分页结构遵循 §51。
> `message_id` 使用 `msg_` 前缀（《总纲》§4.1.3），消息本体存储于 `assistant_messages`（表结构见《V2.1 设计框架规范》§4）。

---

# 65. AI 工程意图 API

> 所需权限：`assistant:chat`（§62.2）。

## 65.1 意图解析

```http
POST /api/v1/assistant/intent/parse
```

请求：

```json
{
  "session_id": "asst_20260925_000001",
  "content": "建立一个跨度30米的钢结构厂房，檐口高度10米"
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "intent_id": "intent_20260925_000001",
    "intent": "create_structural_model",
    "discipline": "steel_structure",
    "entities": {
      "span": {
        "value": 30,
        "unit": "m"
      },
      "eave_height": {
        "value": 10,
        "unit": "m"
      }
    },
    "missing_parameters": [
      "building_length",
      "frame_spacing"
    ],
    "warnings": []
  },
  "request_id": "req_20260925_000034",
  "timestamp": "2026-09-25T09:03:00+08:00"
}
```

> **N-22 裁决（缺失参数如何补全）**：`data.missing_parameters` 列出的关键参数**不通过独立接口补全**，而是由 AI 助手通过 **§64.1 消息接口**发起**追问**（生成一条 `role = assistant` 的追问消息），用户在**同一会话**中回答后，系统重新解析并更新意图。
>
> 补全闭环：
>
> ```text
> §65 intent/parse  返回 missing_parameters
>      ↓
> §64.1 消息接口    AI 追问（assistant 消息）
>      ↓
> §64.1 消息接口    用户回答（user 消息）
>      ↓
> §65 intent/parse  重新解析，missing_parameters 收敛
>      ↓
> §66 validate      参数校验
>      ↓
> §67 plans         生成执行计划
> ```
>
> 当 `missing_parameters` 非空时，不得进入 §67 生成可执行计划；参数缺失对应的错误码为 `PARAMETER_INCOMPLETE`（《总纲》§4.4.7）。
> 依据：《总纲》§5.4 N-22。

---

# 66. 参数校验 API

> 所需权限：`assistant:plan`（§62.2）。

AI 提取参数后必须经过独立 Validation Service。

```http
POST /api/v1/assistant/validate
```

请求：

```json
{
  "discipline": "steel_structure",
  "model_type": "portal_frame",
  "parameters": {
    "span": 30,
    "length": 60,
    "eave_height": 10,
    "frame_spacing": 6
  }
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "valid": true,
    "errors": [],
    "warnings": [
      {
        "code": "CODE_LOAD_CHECK",
        "message": "需要进一步确定基本风压及雪荷载参数"
      }
    ],
    "normalized_parameters": {
      "span": {
        "value": 30.0,
        "unit": "m"
      },
      "length": {
        "value": 60.0,
        "unit": "m"
      },
      "eave_height": {
        "value": 10.0,
        "unit": "m"
      },
      "frame_spacing": {
        "value": 6.0,
        "unit": "m"
      },
      "roof_slope": {
        "value": 0.05,
        "unit": "ratio"
      },
      "steel_grade": {
        "value": "Q355",
        "unit": null
      }
    }
  },
  "request_id": "req_20260925_000035",
  "timestamp": "2026-09-25T09:04:00+08:00"
}
```

> **N-21 裁决**：`normalized_parameters` 不再是空对象，而是**归一化后的真实参数体**。
> 归一化规则：
>
> - 所有带量纲的参数一律转为 `{ "value": <number>, "unit": "<单位>" }` 结构
> - 长度类单位统一为 **m**，截面尺寸统一为 **mm**（《总纲》§4.5.2）
> - 无量纲参数（如 `steel_grade`）的 `unit` 为 `null`
> - 未在请求中给出、但可由规范推导的参数（如 `roof_slope`）在此补齐
>
> 依据：《总纲》§5.4 N-21。

---

# 67. AI Execution Plan

> 所需权限：`assistant:plan`（§62.2）。

AI 不允许直接从 LLM 输出调用任意 MIDAS API。

必须生成中间执行计划：

```http
POST /api/v1/assistant/plans
```

## 67.1 步骤结构（N-1 重定义）

**每个步骤必须可被翻译为一次合法的 MCP Tool 调用。**

步骤结构：

```json
{
  "step_no": 1,
  "step_id": "step_1",
  "name": "创建节点",
  "tool": "midas_model",
  "action": "create",
  "resource": "node",
  "params": { "...": "..." },
  "depends_on": []
}
```

> **说明**：上面是**步骤结构片段（schema fragment）**，不是完整响应。
> 它在实际响应中位于统一信封的 `data.steps[]` 内；完整响应体见 §67.3，完整可执行示例见 §67.2。

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `step_no` | INTEGER | 步骤序号，从 1 开始 |
| `step_id` | string | 步骤标识，形如 `step_1` |
| `name` | string | 面向 UI 展示的步骤名 |
| `tool` | string | MCP Tool 名，取自 `midas_query` / `midas_model` / `midas_execute` / `midas_task` |
| `action` | string | MCP action（动词），取值来自《V2.1 设计框架规范》§7-§11 |
| `resource` | string | MCP resource（**单数**），取值来自《V2.1 设计框架规范》§7-§11 |
| `params` | object | 该次 Tool 调用的参数体，须满足对应 Tool 的 `input_schema` |
| `depends_on` | string[] | 依赖的 `step_id` 列表，空数组表示无依赖 |

> **N-1 裁决**：v1.1 的 `"operation": "create_nodes" / "create_elements" / "apply_loads" / "run_analysis"` **全部废止**——这些值无法翻译成任何合法的 MCP 调用。
> 新结构由 `tool` + `action` + `resource` + `params` 四元组构成，可**直接**翻译为 MCP 调用。
> `depends_on` 表达步骤之间的**执行顺序**；执行器按 `depends_on` 做**拓扑排序**解析，不依赖数组顺序。
> `action` / `resource` 的合法取值由《V2.1 设计框架规范》§7-§11 拥有，本文档不重定义。

## 67.2 完整可执行示例（4 步）

请求：

```http
POST /api/v1/assistant/plans
```

```json
{
  "session_id": "asst_20260925_000001",
  "intent": "create_structural_model",
  "steps": [
    {
      "step_no": 1,
      "step_id": "step_1",
      "name": "创建节点",
      "tool": "midas_model",
      "action": "create",
      "resource": "node",
      "params": {
        "nodes": [
          { "id": 1001, "x": 0, "y": 0, "z": 0 },
          { "id": 1002, "x": 6, "y": 0, "z": 0 }
        ]
      },
      "depends_on": []
    },
    {
      "step_no": 2,
      "step_id": "step_2",
      "name": "创建单元",
      "tool": "midas_model",
      "action": "create",
      "resource": "element",
      "params": {
        "elements": [
          { "id": 2001, "type": "beam", "node_ids": [1001, 1002] }
        ]
      },
      "depends_on": ["step_1"]
    },
    {
      "step_no": 3,
      "step_id": "step_3",
      "name": "施加荷载",
      "tool": "midas_model",
      "action": "create",
      "resource": "load",
      "params": {
        "load_case": "DL",
        "loads": [
          { "type": "beam", "element_id": 2001, "direction": "GZ", "value": -5.0, "unit": "kN/m" }
        ]
      },
      "depends_on": ["step_2"]
    },
    {
      "step_no": 4,
      "step_id": "step_4",
      "name": "运行结构分析",
      "tool": "midas_execute",
      "action": "analysis",
      "resource": "model",
      "params": {
        "analysis_type": "static",
        "cases": ["DL", "LL", "WL"]
      },
      "depends_on": ["step_3"]
    }
  ]
}
```

> **关键点**：运行分析使用 `midas_execute`（`action = analysis`，`resource = model`），**不是** `midas_task`。
> `midas_task` 用于**查询 / 订阅已存在任务**，不用于发起分析。
> 依据：《总纲》§5.4 N-1。

## 67.3 响应体（N-3 / N-8）

响应必须返回 `plan_id` 与 `confirmation_token`：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "plan_id": "plan_20260925_000001",
    "status": "awaiting_confirmation",
    "risk_level": "medium",
    "requires_confirmation": true,
    "confirmation_token": "confirm_20260925_000001",
    "steps": [
      {
        "step_no": 1,
        "step_id": "step_1",
        "name": "创建节点",
        "tool": "midas_model",
        "action": "create",
        "resource": "node",
        "status": "pending",
        "depends_on": []
      },
      {
        "step_no": 2,
        "step_id": "step_2",
        "name": "创建单元",
        "tool": "midas_model",
        "action": "create",
        "resource": "element",
        "status": "pending",
        "depends_on": ["step_1"]
      },
      {
        "step_no": 3,
        "step_id": "step_3",
        "name": "施加荷载",
        "tool": "midas_model",
        "action": "create",
        "resource": "load",
        "status": "pending",
        "depends_on": ["step_2"]
      },
      {
        "step_no": 4,
        "step_id": "step_4",
        "name": "运行结构分析",
        "tool": "midas_execute",
        "action": "analysis",
        "resource": "model",
        "status": "pending",
        "depends_on": ["step_3"]
      }
    ]
  },
  "request_id": "req_20260925_000036",
  "timestamp": "2026-09-25T09:05:00+08:00"
}
```

> **N-3 / N-8 裁决**：
> - `plan_id` 使用 `plan_` 前缀（《总纲》§4.1.3）
> - `confirmation_token` 使用 `confirm_` 前缀，由本接口**签发**
> - `status` 取值见《总纲》§4.2.2（`assistant_plans.status`）
> - 步骤 `status` 取值见《总纲》§4.2.3（`assistant_plan_steps.status`）
> - `risk_level` 取值由风险分级策略决定，用于决定 `requires_confirmation` 是否为 `true`

## 67.4 确认令牌规则

```text
confirmation_token  →  一次性（single-use）
                    →  有效期 10 分钟
                    →  绑定 plan_id + user_id
```

- 令牌**明文只返回一次**，落库的是 `assistant_plans.confirmation_token_hash`（单向哈希，见《总纲》§4.7.1）
- 超时或已使用 → 返回 `CONFIRMATION_INVALID`（403，见《总纲》§4.4.1）
- 令牌与 `plan_id` 或 `user_id` 不匹配 → 同样返回 `CONFIRMATION_INVALID`

---

# 68. Execution Plan 查询

> 所需权限：`assistant:plan`（§62.2）。

```http
GET /api/v1/assistant/plans/{plan_id}
```

返回（`status = awaiting_confirmation` 时**必须**返回 `confirmation_token`）：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "plan_id": "plan_20260925_000001",
    "session_id": "asst_20260925_000001",
    "intent": "create_structural_model",
    "status": "awaiting_confirmation",
    "risk_level": "medium",
    "requires_confirmation": true,
    "confirmation_token": "confirm_20260925_000001",
    "steps": [
      {
        "step_no": 1,
        "step_id": "step_1",
        "name": "创建节点",
        "tool": "midas_model",
        "action": "create",
        "resource": "node",
        "status": "pending",
        "depends_on": []
      },
      {
        "step_no": 2,
        "step_id": "step_2",
        "name": "创建单元",
        "tool": "midas_model",
        "action": "create",
        "resource": "element",
        "status": "pending",
        "depends_on": ["step_1"]
      },
      {
        "step_no": 3,
        "step_id": "step_3",
        "name": "施加荷载",
        "tool": "midas_model",
        "action": "create",
        "resource": "load",
        "status": "pending",
        "depends_on": ["step_2"]
      },
      {
        "step_no": 4,
        "step_id": "step_4",
        "name": "运行结构分析",
        "tool": "midas_execute",
        "action": "analysis",
        "resource": "model",
        "status": "pending",
        "depends_on": ["step_3"]
      }
    ]
  },
  "request_id": "req_20260925_000037",
  "timestamp": "2026-09-25T09:06:00+08:00"
}
```

> **N-3 裁决**：当 `data.status = awaiting_confirmation` 时，本接口**必须**返回 `confirmation_token`，以便前端在刷新页面后仍可完成确认。
> 令牌重新签发的规则：仅当原令牌已过期且计划仍未确认时，重新签发新令牌；同一计划**同一时刻只有一个有效令牌**。
> 当 `data.status` 为其他取值时，`confirmation_token` 字段为 `null`。

---

# 69. AI 高风险确认

> 所需权限：`assistant:confirm`（§62.2）。

以下操作原则上必须确认：

```text
删除模型
批量删除构件
覆盖现有模型
修改大量模型数据
运行正式计算
导入大型模型
发布计算结果
```

> **裁决（《总纲》§4.8.4）**：v1.1 §72 清单中的「**恢复数据库**」**已移除**。
> 理由：`data:restore` 权限**仅 `super_admin`** 可用，与「AI 可确认的高风险操作」冲突。
> **AI 工程助手不得触发 `data:restore`**；数据库恢复只能由运维人员在数据管理页面（§30.5）人工操作。

接口：

```http
POST /api/v1/assistant/plans/{plan_id}/confirm
```

请求：

```json
{
  "confirmed": true,
  "confirmation_token": "confirm_20260925_000001"
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "plan_id": "plan_20260925_000001",
    "status": "approved",
    "confirmed_at": "2026-09-25T09:07:00+08:00"
  },
  "request_id": "req_20260925_000038",
  "timestamp": "2026-09-25T09:07:00+08:00"
}
```

> 确认成功后 `assistant_plans.status` 由 `awaiting_confirmation` 变为 `approved`（《总纲》§4.2.2）。
> `confirmation_token` 校验失败（无效 / 过期 / 已使用 / 不匹配）返回 `CONFIRMATION_INVALID`（403）。

---

# 70. AI 执行

> 所需权限：`assistant:execute`（§62.2）。
> 注意：`assistant:execute` 需 engineer 及以上角色，且必须已通过 §69 确认流程（《总纲》§4.8.4）。

```http
POST /api/v1/assistant/plans/{plan_id}/execute
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "plan_id": "plan_20260925_000001",
    "status": "executing",
    "task_id": "task_20260925_000010"
  },
  "request_id": "req_20260925_000039",
  "timestamp": "2026-09-25T09:08:00+08:00"
}
```

> **C-4 裁决**：原 `task_ai_xxx` 已废止，改为 `task_20260925_000010`（`task_` 前缀 + `tasks.type` 区分，见《总纲》§4.1.4）。
> **计划状态**：`assistant_plans.status` 由 `approved` 变为 `executing`（《总纲》§4.2.2）。
> 未经确认即调用本接口 → 返回 `PLAN_NOT_CONFIRMED`（409，见《总纲》§4.4.7）。

之后统一进入：

```text
Task Engine
```

## 70.1 取消计划执行（N-10）

```http
POST /api/v1/assistant/plans/{plan_id}/cancel
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "plan_id": "plan_20260925_000001",
    "status": "cancelled",
    "task_id": "task_20260925_000010",
    "cancelled_at": "2026-09-25T09:09:00+08:00"
  },
  "request_id": "req_20260925_000040",
  "timestamp": "2026-09-25T09:09:00+08:00"
}
```

> **N-10 裁决**：本接口为 v1.2 新增。
> **AI 任务即 `tasks` 表记录**，因此底层的 `task_id` **也可以**通过通用任务取消接口取消：
>
> ```http
> POST /api/v1/tasks/{task_id}/cancel     ← 见 §20.4
> ```
>
> 两个入口的语义完全一致，均把 `tasks.status` 置为 `cancelled`、把 `assistant_plans.status` 置为 `cancelled`。
> 取消失败（例如任务已进入不可中断阶段）返回 `TASK_CANCEL_FAILED`（409，见《总纲》§4.4.6）。
> 依据：《总纲》§5.4 N-10。

---

# 71. AI 执行过程

> 所需权限：`assistant:read`（§62.2）。

对应原型中的：

```text
AI执行步骤
执行过程
```

## 71.1 执行步骤

```http
GET /api/v1/assistant/tasks/{task_id}/steps
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "task_id": "task_20260925_000010",
    "plan_id": "plan_20260925_000001",
    "status": "running",
    "progress": 40,
    "steps": [
      {
        "step_no": 1,
        "step_id": "step_1",
        "name": "创建节点",
        "tool": "midas_model",
        "action": "create",
        "resource": "node",
        "status": "completed",
        "progress": 100,
        "depends_on": []
      },
      {
        "step_no": 2,
        "step_id": "step_2",
        "name": "创建单元",
        "tool": "midas_model",
        "action": "create",
        "resource": "element",
        "status": "running",
        "progress": 65,
        "depends_on": ["step_1"]
      },
      {
        "step_no": 3,
        "step_id": "step_3",
        "name": "施加荷载",
        "tool": "midas_model",
        "action": "create",
        "resource": "load",
        "status": "pending",
        "progress": 0,
        "depends_on": ["step_2"]
      },
      {
        "step_no": 4,
        "step_id": "step_4",
        "name": "运行结构分析",
        "tool": "midas_execute",
        "action": "analysis",
        "resource": "model",
        "status": "pending",
        "progress": 0,
        "depends_on": ["step_3"]
      }
    ]
  },
  "request_id": "req_20260925_000041",
  "timestamp": "2026-09-25T09:10:00+08:00"
}
```

> `data.status` 为 `tasks.status`（《总纲》§4.2.1），步骤 `status` 为 `assistant_plan_steps.status`（《总纲》§4.2.3）。
> `progress` 为百分比（0–100）。

## 71.2 实时执行流

```http
GET /api/v1/assistant/tasks/{task_id}/stream
```

> **例外 1（SSE 流）**：本接口返回 `text/event-stream`，不使用统一信封。

事件：

```text
event: step.started
data: {"task_id":"task_20260925_000010","step_id":"step_2","step_no":2}

event: step.progress
data: {"task_id":"task_20260925_000010","step_id":"step_2","progress":65}

event: step.completed
data: {"task_id":"task_20260925_000010","step_id":"step_2","status":"completed"}

event: plan.completed
data: {"task_id":"task_20260925_000010","plan_id":"plan_20260925_000001","status":"completed"}
```

| 事件名 | 载荷字段 | 说明 |
|---|---|---|
| `step.started` | `task_id` `step_id` `step_no` | 步骤开始执行 |
| `step.progress` | `task_id` `step_id` `progress` | 步骤进度变化 |
| `step.completed` | `task_id` `step_id` `status` | 步骤结束（`completed` / `failed` / `skipped`） |
| `plan.completed` | `task_id` `plan_id` `status` | 整个计划结束 |

---

# 72. AI 智能识图

> 所需权限：`assistant:drawing`（§62.2）。

AI 工程助手必须支持：

```text
PDF
DWG
DXF
PNG
JPG
```

识别对象包括：

```text
轴网
轴线
柱
梁
墙
板
支撑
桁架
门式刚架
基础
构件编号
尺寸
标高
材料
截面
荷载
节点
连接
```

> **N-24 裁决（DWG 转换链路）**：**DWG 是二进制封闭格式，识别引擎不能直接解析。**
> DWG 必须先经**格式转换步骤**转为 DXF 或中间格式，再进行识别：
>
> ```text
> DWG 上传
>   ↓
> POST /api/v1/assistant/files/{id}/convert     （§72.2）
>   ↓
> DXF / 中间格式
>   ↓
> POST /api/v1/assistant/drawing/recognize      （§72.1）
> ```
>
> 若用户直接对 DWG 发起识图，服务端必须**自动**触发转换；转换失败返回 `DRAWING_UNSUPPORTED`（422，见《总纲》§4.4.7）。
> 依据：《总纲》§5.4 N-24。

## 72.1 创建识图任务

```http
POST /api/v1/assistant/drawing/recognize
```

使用：

```text
multipart/form-data
```

字段：

```text
file
discipline
recognition_profile
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "task_id": "task_20260925_000003",
    "drawing_id": "draw_20260925_000001",
    "status": "queued"
  },
  "request_id": "req_20260925_000042",
  "timestamp": "2026-09-25T09:11:00+08:00"
}
```

> **C-4 裁决**：原 `drawing_xxx` 已废止。识图是异步任务，其任务 ID 为 `task_20260925_000003`（`tasks.type` 为 `drawing_recognize`，示例取自《总纲》§4.1.4）。
> `drawing_id` 使用 `draw_` 前缀，是 `assistant_drawing_tasks.drawing_id` 的业务 ID（《总纲》§4.1.3），与 `task_id` 是两个不同的标识。

## 72.2 图纸格式转换

```http
POST /api/v1/assistant/files/{id}/convert
```

> `{id}` 为 `file_` 前缀的文件业务 ID（`assistant_files.file_id`，**字符串**）。
> `file_id` 是业务 ID，不是数据库整数主键，见《总纲》§4.1.3。

请求：

```json
{
  "target_format": "dxf",
  "options": {
    "version": "2018"
  }
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "source_file_id": "file_20260925_000001",
    "target_file_id": "file_20260925_000002",
    "target_format": "dxf",
    "status": "success"
  },
  "request_id": "req_20260925_000043",
  "timestamp": "2026-09-25T09:12:00+08:00"
}
```

> 转换耗时可能超过 3 秒时，本接口应改为进入 Task Engine 并返回 `task_id`（见 §56 原则 3、N-11）。

---

# 73. 识图设置

> 所需权限：`assistant:drawing`（§62.2）。

```http
GET /api/v1/assistant/drawing/settings
PUT /api/v1/assistant/drawing/settings
```

示例：

```json
{
  "recognize_axis": true,
  "recognize_dimensions": true,
  "recognize_elevation": true,
  "recognize_members": true,
  "recognize_materials": true,
  "recognize_loads": true,
  "confidence_threshold": 0.85
}
```

> `confidence_threshold` 为 0.0–1.0 的 REAL（《总纲》§4.5.2）。低于该阈值时返回 `RECOGNITION_LOW_CONFIDENCE`（422）。
> 设置持久化位置为 `assistant_drawing_settings`（表结构见《V2.1 设计框架规范》§4）。

---

# 74. 识图结果

> 所需权限：`assistant:drawing`（§62.2）。

```http
GET /api/v1/assistant/drawing/tasks/{task_id}/result
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "task_id": "task_20260925_000003",
    "drawing_id": "draw_20260925_000001",
    "status": "success",
    "objects": [
      {
        "type": "column",
        "id": "C1",
        "bbox": [120, 220, 160, 500],
        "confidence": 0.96,
        "properties": {
          "section": "H400x200x8x13"
        }
      }
    ],
    "dimensions": [],
    "axes": [],
    "elevations": [],
    "warnings": []
  },
  "request_id": "req_20260925_000044",
  "timestamp": "2026-09-25T09:13:00+08:00"
}
```

> 识别对象落库于 `assistant_drawing_objects`（表结构见《V2.1 设计框架规范》§4）。
> `confidence` 为 0.0–1.0 REAL（《总纲》§4.5.2）。

---

# 75. 尺寸检查

> 所需权限：`assistant:drawing`（§62.2）。

```http
POST /api/v1/assistant/drawing/{drawing_id}/dimension-check
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "drawing_id": "draw_20260925_000001",
    "valid": false,
    "issues": [
      {
        "type": "dimension_conflict",
        "description": "轴网尺寸与局部标注不一致",
        "severity": "warning"
      }
    ]
  },
  "request_id": "req_20260925_000045",
  "timestamp": "2026-09-25T09:14:00+08:00"
}
```

---

# 76. 识图结果转模型

> 所需权限：`assistant:modeling`（§62.2）。

```http
POST /api/v1/assistant/drawing/{drawing_id}/to-model
```

请求：

```json
{
  "midas_client_id": 1,
  "model_name": "图纸识别模型",
  "validate_before_create": true
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "task_id": "task_20260925_000004",
    "drawing_id": "draw_20260925_000001",
    "status": "queued"
  },
  "request_id": "req_20260925_000046",
  "timestamp": "2026-09-25T09:15:00+08:00"
}
```

> **C-4 裁决**：原 `model_import_xxx` 已废止，改为 `task_20260925_000004`（`task_` 前缀 + `tasks.type` 区分）。
> **N-6 裁决**：`midas_client_id` 为 **INTEGER**。

---

# 77. AI 智能建模

> 所需权限：`assistant:modeling`（§62.2）。

AI 工程助手提供三种建模方式：

```text
① 图纸识别建模     → §72 → §76
② 快速向导建模     → §77.2
③ 自然语言 AI 建模 → §77.1
```

## 77.1 自然语言建模

```http
POST /api/v1/assistant/modeling/natural-language
```

请求：

```json
{
  "session_id": "asst_20260925_000001",
  "model_id": 1,
  "prompt": "建立30米跨度、60米长度、10米檐高的钢结构厂房"
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "plan_id": "plan_20260925_000002",
    "status": "awaiting_confirmation",
    "requires_confirmation": true
  },
  "request_id": "req_20260925_000047",
  "timestamp": "2026-09-25T09:16:00+08:00"
}
```

> 本接口内部走「意图 → 校验 → 计划」链路，最终产出 §67 定义的可执行 Execution Plan。

## 77.2 快速建模

```http
POST /api/v1/assistant/modeling/wizard
```

请求：

```json
{
  "type": "steel_portal_frame",
  "model_id": 1,
  "parameters": {
    "span": 30,
    "length": 60,
    "eave_height": 10,
    "frame_spacing": 6
  }
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "plan_id": "plan_20260925_000003",
    "status": "awaiting_confirmation",
    "requires_confirmation": true
  },
  "request_id": "req_20260925_000048",
  "timestamp": "2026-09-25T09:17:00+08:00"
}
```

## 77.3 模型预览

```http
GET /api/v1/assistant/modeling/{model_id}/preview
```

支持：

```text
3D
平面
立面
剖面
节点
```

> 路径参数 `{model_id}` 为 **INTEGER**（`models.id`）。

---

# 78. AI 荷载生成

> 所需权限：`assistant:modeling`（§62.2）。

```http
POST /api/v1/assistant/loads/generate
```

请求：

```json
{
  "model_id": 1,
  "location": {
    "province": "四川省",
    "city": "成都市"
  },
  "building_type": "steel_factory",
  "code": "GB50009"
}
```

返回（**异步**）：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "status": "queued",
    "task_id": "task_20260925_000011"
  },
  "request_id": "req_20260925_000049",
  "timestamp": "2026-09-25T09:18:00+08:00"
}
```

> **N-11 裁决**：本接口**改为异步**。荷载生成需查询地区规范参数库（`load_parameter_library`）并可能耗时超过 3 秒，因此必须进入 Task Engine 并返回 `task_id`。
> **通用判据：凡可能超过约 3 秒的操作，一律进入 Task Engine。** 依据：《总纲》§5.4 N-11。
> **N-6 裁决**：`model_id` 为 **INTEGER**（原 `"model_xxx"` 字符串形式废止）。

系统根据配置的规范、项目所在地及输入资料生成候选：

```text
恒载
活载
风荷载
雪荷载
地震作用
温度作用
吊车荷载
```

任务完成后，通过 `GET /api/v1/tasks/{task_id}/result` 取结果。结果体中若地勘资料缺失，必须明确标识：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "task_id": "task_20260925_000011",
    "status": "success",
    "loads": [],
    "source": "default/code_based",
    "requires_engineer_confirmation": true
  },
  "request_id": "req_20260925_000050",
  "timestamp": "2026-09-25T09:18:30+08:00"
}
```

> **AI 生成的荷载必须标注来源**（`source`）与是否需要工程师确认（`requires_engineer_confirmation`），禁止无来源的编造荷载。

---

# 79. AI 规范检查

> 所需权限：`assistant:modeling`（§62.2）。

```http
POST /api/v1/assistant/code-check
```

请求：

```json
{
  "model_id": 1,
  "code_set": [
    "GB50017",
    "GB50009",
    "GB50011"
  ]
}
```

返回（**异步**）：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "status": "queued",
    "task_id": "task_20260925_000012"
  },
  "request_id": "req_20260925_000051",
  "timestamp": "2026-09-25T09:19:00+08:00"
}
```

> **N-11 裁决**：本接口**改为异步**，必须返回 `task_id`。依据：《总纲》§5.4 N-11。
> **N-6 裁决**：`model_id` 为 **INTEGER**。

任务完成后取结果：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "task_id": "task_20260925_000012",
    "status": "success",
    "issues": [
      {
        "code": "SECTION_RATIO",
        "severity": "warning",
        "member_id": "G1",
        "message": "构件参数需要进一步验算",
        "clause_ref": "GB50017-2017 7.2.1"
      }
    ]
  },
  "request_id": "req_20260925_000052",
  "timestamp": "2026-09-25T09:19:30+08:00"
}
```

> AI 可以发现问题，但最终工程判断必须保留**可追溯的规范条文**（`clause_ref`，指向 `code_clauses`）、计算依据和人工确认状态。
> 规范知识库缺少所需条文时返回 `CODE_STANDARD_MISSING`（422，见《总纲》§4.4.7）。

---

# 80. AI 分析计算

> 所需权限：`assistant:execute`（§62.2）。

```http
POST /api/v1/assistant/analysis/run
```

请求：

```json
{
  "model_id": 1,
  "analysis_type": "static",
  "cases": [
    "DL",
    "LL",
    "WL"
  ],
  "async": true
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "status": "queued",
    "task_id": "task_20260925_000013"
  },
  "request_id": "req_20260925_000053",
  "timestamp": "2026-09-25T09:20:00+08:00"
}
```

> **C-4 裁决**：原 `analysis_xxx` 已废止，改为 `task_20260925_000013`。
> **N-6 裁决**：`model_id` 为 **INTEGER**。
> **N-2 裁决**：本接口是**AI 门面**，与**运维门面** `POST /api/v1/midas/analysis/run`（§45）共享同一个 Service Layer，且请求体/响应体字段名**完全一致**。

---

# 81. AI 结果解释

> 所需权限：`assistant:report`（§62.2）。

```http
POST /api/v1/assistant/results/explain
```

请求：

```json
{
  "task_id": "task_20260925_000013",
  "model_id": 1,
  "scope": {
    "members": ["G1", "G2"]
  }
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "summary": "检测到部分构件组合工况下利用率较高。",
    "findings": [],
    "evidence": {
      "analysis_cases": [],
      "result_ids": []
    }
  },
  "request_id": "req_20260925_000054",
  "timestamp": "2026-09-25T09:21:00+08:00"
}
```

> **N-6 裁决**：`model_id` 为 **INTEGER**。
> **C-4 裁决**：原 `analysis_id: "analysis_xxx"` 改为 `task_id: "task_20260925_000013"`——分析计算本身就是一个任务，其标识即 `task_id`。
> AI 输出必须绑定实际计算结果（`evidence`），**禁止凭模型语言自行编造计算结果**。

---

# 82. AI 优化

> 所需权限：`assistant:optimize`（§62.2）。

```http
POST /api/v1/assistant/optimization/run
```

请求：

```json
{
  "model_id": 1,
  "objective": [
    "steel_weight_minimize"
  ],
  "constraints": {
    "strength": true,
    "stability": true,
    "serviceability": true
  }
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "status": "queued",
    "task_id": "task_20260925_000014"
  },
  "request_id": "req_20260925_000055",
  "timestamp": "2026-09-25T09:22:00+08:00"
}
```

> **C-4 裁决**：原 `optimization_xxx` 已废止，改为 `task_20260925_000014`。
> **N-6 裁决**：`model_id` 为 **INTEGER**。

---

# 83. 优化结果

> 所需权限：`assistant:optimize`（§62.2）。

```http
GET /api/v1/assistant/optimization/{task_id}/result
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "task_id": "task_20260925_000014",
    "model_id": 1,
    "before": {
      "steel_weight": 125.6
    },
    "after": {
      "steel_weight": 118.2
    },
    "changes": [],
    "verification": {
      "passed": true
    }
  },
  "request_id": "req_20260925_000056",
  "timestamp": "2026-09-25T09:23:00+08:00"
}
```

结果必须保留：

```text
原模型
优化模型
修改项
计算依据
验算结果
```

> 质量单位为 **kg / t**（《总纲》§4.5.2）。
> **N-6 裁决**：`model_id` 为 **INTEGER**。

---

# 84. AI 计算书

> 所需权限：`assistant:report`（§62.2）。

```http
POST /api/v1/assistant/reports
```

请求：

```json
{
  "project_id": 1,
  "model_id": 1,
  "report_type": "structural_calculation",
  "format": "pdf",
  "include": [
    "project_info",
    "model",
    "materials",
    "loads",
    "load_combinations",
    "analysis",
    "design",
    "warnings",
    "results"
  ]
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "status": "queued",
    "task_id": "task_20260925_000015",
    "report_id": "rpt_20260925_000002"
  },
  "request_id": "req_20260925_000057",
  "timestamp": "2026-09-25T09:24:00+08:00"
}
```

支持：

```text
PDF
DOCX
```

> **N-6 裁决**：`project_id`、`model_id` 一律为 **INTEGER**（原 `"project_xxx"` / `"model_xxx"` 字符串形式废止）。
> **N-2 / N-14 裁决**：本接口是**AI 门面**，与**运维门面** `POST /api/v1/reports`（§47）共享同一个 Service Layer（ReportService），且报告请求字段**完全一致**：
>
> ```text
> report_type     报告类型（统一字段名）
> include[]       报告包含章节（统一字段名，原 sections 废止）
> format          输出格式
> project_id      项目 ID（INTEGER）
> model_id        模型 ID（INTEGER）
> ```
>
> 响应体同构：均返回 `data.status` + `data.task_id` + `data.report_id`。
> 依据：《总纲》§5.4 N-2、N-14。

---

# 85. AI 图形输出

> 所需权限：`assistant:report`（§62.2）。

```http
POST /api/v1/assistant/drawings/generate
```

请求：

```json
{
  "model_id": 1,
  "task_id": "task_20260925_000013",
  "drawing_types": [
    "plan",
    "elevation",
    "section",
    "joint",
    "deformation",
    "stress",
    "internal_force"
  ],
  "output_format": "png"
}
```

支持：

```text
平面图
立面图
剖面图
节点图
变形图
应力图
内力图
```

输出：

```text
PNG
SVG
PDF
DXF
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "status": "success",
    "model_id": 1,
    "files": [
      {
        "file_id": "file_20260925_000010",
        "drawing_type": "plan",
        "format": "png",
        "download_url": "/api/v1/assistant/files/file_20260925_000010/download"
      }
    ]
  },
  "request_id": "req_20260925_000058",
  "timestamp": "2026-09-25T09:25:00+08:00"
}
```

> **N-6 裁决**：`model_id` 为 **INTEGER**。
> 图形产物文件本体记录于 `assistant_files`，语义记录于 `assistant_outputs`（边界见《总纲》§5.4 N-23）。
> 下载接口返回二进制流，属 §3.3 例外 2。

---

# 86. AI 工程模板

> 所需权限：查询 `assistant:read`；使用/运行 `assistant:modeling`（§62.2）。

对应：

```text
/#/ai/templates
```

## 86.1 模板分类

```http
GET /api/v1/assistant/templates/categories
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "items": [
      {
        "category_code": "steel_structure",
        "category_name": "钢结构",
        "template_count": 8
      },
      {
        "category_code": "concrete_structure",
        "category_name": "混凝土结构",
        "template_count": 6
      },
      {
        "category_code": "bridge",
        "category_name": "桥梁",
        "template_count": 4
      },
      {
        "category_code": "retaining",
        "category_name": "支护",
        "template_count": 3
      },
      {
        "category_code": "foundation",
        "category_name": "基础",
        "template_count": 5
      },
      {
        "category_code": "geotechnical",
        "category_name": "岩土",
        "template_count": 2
      },
      {
        "category_code": "building_structure",
        "category_name": "建筑结构",
        "template_count": 4
      },
      {
        "category_code": "equipment_foundation",
        "category_name": "设备基础",
        "template_count": 2
      }
    ]
  },
  "request_id": "req_20260925_000059",
  "timestamp": "2026-09-25T09:26:00+08:00"
}
```

> 本接口为 v1.2 新增，用于驱动模板页的左侧分类树；分类来源为 `assistant_templates.category_code`。

## 86.2 模板列表

```http
GET /api/v1/assistant/templates
```

参数：

```text
?category_code=steel_structure
&page=1
&page_size=20
&keyword=厂房
```

## 86.3 模板详情

```http
GET /api/v1/assistant/templates/{id}
```

## 86.4 模板参数

```http
GET /api/v1/assistant/templates/{id}/schema
```

## 86.5 使用模板

```http
POST /api/v1/assistant/templates/{id}/run
```

请求：

```json
{
  "session_id": "asst_20260925_000001",
  "model_id": 1,
  "parameters": {
    "span": 30,
    "length": 60,
    "eave_height": 10,
    "frame_spacing": 6
  }
}
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "plan_id": "plan_20260925_000004",
    "status": "awaiting_confirmation",
    "requires_confirmation": true
  },
  "request_id": "req_20260925_000060",
  "timestamp": "2026-09-25T09:27:00+08:00"
}
```

> **N-6 裁决**：`model_id` 为 **INTEGER**。

---

# 87. AI 示例案例

> 所需权限：查询 `assistant:read`；运行 `assistant:modeling`（§62.2）。

对应：

```text
/#/ai/examples
```

示例案例与历史案例必须严格区分。

示例案例：

```text
官方预置
可运行
有固定步骤
可查看说明
可直接使用
```

## 87.1 示例列表

```http
GET /api/v1/assistant/examples
```

## 87.2 示例详情

```http
GET /api/v1/assistant/examples/{id}
```

## 87.3 查看步骤

```http
GET /api/v1/assistant/examples/{id}/steps
```

返回的步骤结构与本示例对应的 Execution Plan 步骤结构一致（`step_no` / `step_id` / `name` / `tool` / `action` / `resource` / `params` / `depends_on`），见 §67.1。

## 87.4 运行案例

```http
POST /api/v1/assistant/examples/{id}/run
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "plan_id": "plan_20260925_000005",
    "status": "awaiting_confirmation",
    "requires_confirmation": true
  },
  "request_id": "req_20260925_000061",
  "timestamp": "2026-09-25T09:28:00+08:00"
}
```

---

# 88. AI 历史案例

> 所需权限：查询 / 打开 / 导出 / 删除 `assistant:read`；再次运行 `assistant:plan`（§62.2）。

对应：

```text
/#/ai/history
```

历史案例是用户过去实际运行产生的工程记录。

## 88.1 历史案例列表

```http
GET /api/v1/assistant/history/cases
```

## 88.2 案例详情

```http
GET /api/v1/assistant/history/cases/{id}
```

## 88.3 再次运行

```http
POST /api/v1/assistant/history/cases/{id}/rerun
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "plan_id": "plan_20260925_000006",
    "status": "awaiting_confirmation",
    "requires_confirmation": true
  },
  "request_id": "req_20260925_000062",
  "timestamp": "2026-09-25T09:29:00+08:00"
}
```

## 88.4 打开模型

```http
GET /api/v1/assistant/history/cases/{id}/model
```

## 88.5 导出结果

```http
POST /api/v1/assistant/history/cases/{id}/export
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "status": "queued",
    "task_id": "task_20260925_000016"
  },
  "request_id": "req_20260925_000063",
  "timestamp": "2026-09-25T09:30:00+08:00"
}
```

## 88.6 删除历史案例

```http
DELETE /api/v1/assistant/history/cases/{id}
```

---

# 89. AI 历史记录

> 所需权限：`assistant:read`（§62.2）。

历史记录比历史案例粒度更细，主要用于审计和追踪。

```http
GET /api/v1/assistant/history
```

过滤：

```text
keyword
type
status
date_from
date_to
user_id
```

详情：

```http
GET /api/v1/assistant/history/{id}
```

包含：

```text
用户输入
AI回复
工程意图
参数
Execution Plan
Tool调用
Task
Adapter请求
MIDAS响应
生成文件
错误
执行日志
```

> 历史记录数据来源于 `assistant_history`（细粒度审计）以及 `request_id → task_id → adapter_request_id` 追溯链（《总纲》§4.1.5）。

---

# 90. AI 常用工程指令

> 所需权限：`assistant:read`（§62.2）。

```http
GET /api/v1/assistant/commands
```

返回：

```json
{
  "success": true,
  "code": "OK",
  "message": "操作成功",
  "data": {
    "items": [
      {
        "code": "create_model",
        "name": "创建结构模型",
        "prompt_template": "建立一个{type}结构"
      },
      {
        "code": "check_model",
        "name": "模型检查",
        "prompt_template": "检查当前模型"
      },
      {
        "code": "run_analysis",
        "name": "运行分析",
        "prompt_template": "运行当前模型分析"
      }
    ]
  },
  "request_id": "req_20260925_000064",
  "timestamp": "2026-09-25T09:31:00+08:00"
}
```

> 指令定义来源于 `assistant_commands`（表结构见《V2.1 设计框架规范》§4）。

---

# 91. AI 文件管理

> 所需权限：查询 / 下载 `assistant:read`；上传 / 删除 `assistant:read`（图纸类文件另需 `assistant:drawing`）（§62.2）。

```http
POST   /api/v1/assistant/files
GET    /api/v1/assistant/files/{id}
GET    /api/v1/assistant/files/{id}/download
DELETE /api/v1/assistant/files/{id}
POST   /api/v1/assistant/files/{id}/convert
```

> `{id}` 为 `file_` 前缀的文件业务 ID（**字符串**，见《总纲》§4.1.3）。
> `GET /api/v1/assistant/files/{id}/download` 返回二进制流，属 §3.3 例外 2。
> `POST /api/v1/assistant/files/{id}/convert` 的完整定义见 **§72.2**（图纸格式转换）。

文件类型（**已去重**）：

```text
PDF
DWG
DXF
PNG
JPG
MGT
MCT
JSON
DOCX
SVG
```

> **N-15 裁决**：v1.1 的文件类型清单中 `PDF` 出现两次，已去重。依据：《总纲》§5.4 N-15。
> `MGT` / `MCT` 是 MIDAS Gen / Civil 的原生模型文件格式。

---

# 92. AI Assistant 与 MCP 4 Tool 的关系

AI 工程助手不直接调用 MIDAS 原始 API。

完整链路：

```text
AI Engineering Assistant
          │
          ▼
 Engineering Intent
          │
          ▼
 Parameter Validation
          │
          ▼
 Execution Plan
          │
          ▼
 ┌───────────────────────────┐
 │       MCP 4 Tools         │
 │                           │
 │ midas_query               │
 │ midas_model               │
 │ midas_execute             │
 │ midas_task                │
 └─────────────┬─────────────┘
               │
               ▼
        Capability Resolver
               │
               ▼
        Adapter Registry
               │
               ▼
         MIDAS Adapter
               │
               ▼
          MIDAS Software
```

> **归属说明**：4 个 MCP Tool 的 `action` / `resource` 枚举、参数 Schema、返回信封与错误结构由《StructAI MCP V2.1 设计框架规范》§7-§11 拥有。
> 本文档**不重述**这些 Schema；§67.1 的步骤结构只是**引用** `tool` + `action` + `resource` 三元组，其合法取值以《V2.1 设计框架规范》为准。
> AI 门面与 MCP 之间的唯一契约是：**Execution Plan 的每一步必须能翻译为一次合法的 MCP Tool 调用**。

---

# 93. AI Assistant 状态机（UI 展示状态，派生）

## 93.1 状态机

```text
IDLE
 ↓
UNDERSTANDING
 ↓
PLANNING
 ↓
VALIDATING
 ↓
WAITING_CONFIRMATION
 ↓
EXECUTING
 ↓
VERIFYING
 ↓
COMPLETED
```

异常：

```text
FAILED
CANCELLED
TIMEOUT
```

## 93.2 派生规则（关键裁决）

> **本状态机是前端展示状态机，由本文档拥有，且【不落库】。**
>
> 它**不写入任何数据库表**，必须由以下三个落库状态**实时派生**得出：
>
> ```text
> assistant_plans.status          （《总纲》§4.2.2）
> assistant_plan_steps.status     （《总纲》§4.2.3）
> tasks.status                    （《总纲》§4.2.1）
> ```

派生映射表：

| UI 展示状态 | 派生自 |
|---|---|
| `IDLE` | 无进行中计划 |
| `UNDERSTANDING` | `assistant_intents` 生成中 |
| `PLANNING` | `assistant_plans.status = draft` |
| `VALIDATING` | `assistant_plans.status = validating` |
| `WAITING_CONFIRMATION` | `assistant_plans.status = awaiting_confirmation` |
| `EXECUTING` | `assistant_plans.status = executing` |
| `VERIFYING` | `assistant_plans.status = verifying` |
| `COMPLETED` | `assistant_plans.status = completed` |
| `FAILED` | `assistant_plans.status = failed` |
| `CANCELLED` | `assistant_plans.status = cancelled` |
| `TIMEOUT` | `assistant_plans.status = failed` 且 `error_code = TASK_TIMEOUT` |

> **裁决说明**：
> - 原 v1.1 §96 的 `WAITING_CONFIRMATION` 大写形式保留为 **UI 展示状态**，其落库对应值为 `assistant_plans.status = awaiting_confirmation`（《总纲》§4.2.2）
> - 前端**不得**自行维护该状态变量并写入后端；任何时刻都必须由上述三个落库状态重新计算
> - 步骤级进度（`EXECUTING` 阶段）由 `assistant_plan_steps.status` 与 `tasks.status` 共同决定
> - 依据：《总纲》§4.2.6 与 §3 所有权矩阵第 21 项

## 93.3 前端派生示例

```javascript
function deriveUiState(plan, steps, task) {
  if (!plan) return "IDLE";
  switch (plan.status) {
    case "draft":                  return "PLANNING";
    case "validating":             return "VALIDATING";
    case "awaiting_confirmation":  return "WAITING_CONFIRMATION";
    case "approved":
    case "executing":              return "EXECUTING";
    case "verifying":              return "VERIFYING";
    case "completed":              return "COMPLETED";
    case "cancelled":              return "CANCELLED";
    case "rejected":               return "FAILED";
    case "failed":
      return plan.error_code === "TASK_TIMEOUT" ? "TIMEOUT" : "FAILED";
    default:                       return "IDLE";
  }
}
```

> `UNDERSTANDING` 由 `assistant_intents` 生成中（尚未产生 plan）这一条件派生。

---

# 94. AI Assistant 安全边界

> 所需权限：各接口按 §62.2 标注；本节的约束**高于**任何接口的默认行为。

AI 不允许：

```text
任意调用 HTTP URL
任意执行 Shell
任意执行 SQL
绕过 RBAC
绕过 Capability
绕过参数校验
绕过高风险确认
直接写 MIDAS API
```

所有执行必须：

```text
AI
 ↓
Intent
 ↓
Validation
 ↓
Plan
 ↓
RBAC
 ↓
Confirmation
 ↓
MCP Tool
 ↓
Capability
 ↓
Adapter
```

## 94.1 高风险权限约束

```text
data:restore        →  仅 super_admin
system:write        →  仅 super_admin
user:delete         →  仅 super_admin
assistant:execute   →  engineer 及以上，且必须通过 §69 高风险确认流程
```

> **AI 工程助手不得触发 `data:restore`。**
> 理由：该权限**仅 `super_admin`** 可用（《总纲》§4.8.4），而 AI 助手的高风险确认流程面向 `engineer` 及以上角色，二者冲突。
> 因此 §69 的高风险操作清单中**已移除「恢复数据库」**；数据库恢复只能由运维人员在 §30.5 人工操作。
> 依据：《总纲》§4.8.4。

## 94.2 数据与输出约束

```text
AI 不得绕过 RBAC、Capability、参数校验、高风险确认
AI 不得编造计算结果（必须绑定 evidence）
AI 不得编造规范条文（必须绑定 clause_ref）
AI 不得编造荷载来源（必须标注 source）
AI 不得返回明文密钥（回显遵循《总纲》§4.7.2）
```

---

# 95. 前端 AI 工程助手页面与 API 映射

| 页面/区域 | API | 章节 | 所需权限 |
|---|---|---|---|
| AI智能对话 | `/assistant/sessions` | §63 | `assistant:read` |
| 消息发送 | `/assistant/sessions/{id}/messages` | §64.1 | `assistant:chat` |
| 历史消息 | `/assistant/sessions/{id}/messages`（GET） | §64.2 | `assistant:chat` |
| 工程意图 | `/assistant/intent/parse` | §65 | `assistant:chat` |
| 参数检查 | `/assistant/validate` | §66 | `assistant:plan` |
| 执行计划 | `/assistant/plans` | §67 | `assistant:plan` |
| 执行计划查询 | `/assistant/plans/{id}` | §68 | `assistant:plan` |
| 执行确认 | `/assistant/plans/{id}/confirm` | §69 | `assistant:confirm` |
| AI执行 | `/assistant/plans/{id}/execute` | §70 | `assistant:execute` |
| 取消执行 | `/assistant/plans/{id}/cancel` | §70.1 | `assistant:execute` |
| 执行步骤 | `/assistant/tasks/{id}/steps` | §71.1 | `assistant:read` |
| 实时执行 | `/assistant/tasks/{id}/stream` | §71.2 | `assistant:read` |
| 智能识图 | `/assistant/drawing/recognize` | §72.1 | `assistant:drawing` |
| 图纸格式转换 | `/assistant/files/{id}/convert` | §72.2 | `assistant:drawing` |
| 识图设置 | `/assistant/drawing/settings` | §73 | `assistant:drawing` |
| 识图结果 | `/assistant/drawing/tasks/{id}/result` | §74 | `assistant:drawing` |
| 尺寸检查 | `/assistant/drawing/{id}/dimension-check` | §75 | `assistant:drawing` |
| 识图建模 | `/assistant/drawing/{id}/to-model` | §76 | `assistant:modeling` |
| AI建模 | `/assistant/modeling/*` | §77 | `assistant:modeling` |
| 荷载生成 | `/assistant/loads/generate` | §78 | `assistant:modeling` |
| 规范检查 | `/assistant/code-check` | §79 | `assistant:modeling` |
| AI分析 | `/assistant/analysis/run` | §80 | `assistant:execute` |
| 结果解释 | `/assistant/results/explain` | §81 | `assistant:report` |
| AI优化 | `/assistant/optimization/*` | §82 §83 | `assistant:optimize` |
| 计算书 | `/assistant/reports` | §84 | `assistant:report` |
| 图形生成 | `/assistant/drawings/generate` | §85 | `assistant:report` |
| 工程模板 | `/assistant/templates/*` | §86 | `assistant:read`（运行：`assistant:modeling`） |
| 示例案例 | `/assistant/examples/*` | §87 | `assistant:read`（运行：`assistant:modeling`） |
| 历史案例 | `/assistant/history/cases/*` | §88 | `assistant:read`（再次运行：`assistant:plan`） |
| 历史记录 | `/assistant/history/*` | §89 | `assistant:read` |
| 常用指令 | `/assistant/commands` | §90 | `assistant:read` |
| 文件管理 | `/assistant/files/*` | §91 | `assistant:read` |

---

# 96. 完整 StructAI API 模块

补充 AI 工程助手后，整个 API 体系应正式调整为：

```text
/api/v1
│
├── auth
├── dashboard
│
├── assistant                ← AI工程助手核心
│   ├── sessions
│   │   └── {session_id}/messages
│   ├── intent
│   ├── validate
│   ├── plans
│   │   ├── {plan_id}
│   │   ├── {plan_id}/confirm
│   │   ├── {plan_id}/execute
│   │   └── {plan_id}/cancel
│   ├── tasks
│   │   ├── {task_id}/steps
│   │   └── {task_id}/stream
│   ├── drawing
│   ├── modeling
│   ├── loads
│   ├── code-check
│   ├── analysis
│   ├── results
│   ├── optimization
│   ├── reports
│   ├── drawings
│   ├── templates
│   │   └── categories
│   ├── examples
│   ├── history
│   ├── commands
│   └── files
│       └── {id}/convert
│
├── midas
├── mcp
├── adapters
├── tools
├── interfaces
├── schemas
├── capabilities
├── model-providers
├── models
├── tasks
├── logs
├── audit-logs
├── users
├── roles
├── permissions
├── settings
├── data
├── reports
└── health
```

> 本结构是 **REST 门面**的模块清单。MCP Protocol Endpoint（`/mcp`）独立于 `/api/v1`，见 §37。

---

# 97. 最终 StructAI 核心业务闭环

```text
                 ┌───────────────────┐
                 │ AI 工程助手        │
                 └─────────┬─────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
          自然语言                    工程图纸
              │                         │
              ▼                         ▼
         意图解析                    智能识图
              │                         │
              └────────────┬────────────┘
                           ▼
                     参数结构化
                           │
                           ▼
                     参数/规范校验
                           │
                           ▼
                    Execution Plan
                           │
                    高风险确认
                           │
                           ▼
                       Task
                           │
                           ▼
                    MCP 4 Tools
                           │
                           ▼
                  Capability Resolver
                           │
                           ▼
                    Adapter Registry
                           │
                           ▼
                    MIDAS Software
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
           建模          荷载/计算       设计/验算
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                       结果校验
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
          结果解释       图形输出       计算书
                           │
                           ▼
                       历史案例
```

这部分是 StructAI 区别于普通「MCP 管理器」的核心业务层。

> 闭环中每一步的接口落点见 §95；每一步的落库状态见《总纲》§4.2；每一步的排期见《总纲》§7。

---

# 附录 错误码引用表

> **本文档不定义错误码。**
> 错误码注册表由《StructAI 架构边界与融合规范 v1.0（总纲）》**§4.4** 唯一拥有。
> 本附录只提供**注册表位置索引**，供实现方按类查找，**不复制错误码清单**。

| 分类 | 注册表位置 | 典型使用场景（本文档章节） |
|---|---|---|
| 认证与授权 | 《总纲》§4.4.1 | §5 认证、§23 审计日志、§62.2 权限、§69 高风险确认 |
| 请求与资源 | 《总纲》§4.4.2 | 全部接口的参数校验、资源查找、限流 |
| MCP 层 | 《总纲》§4.4.3 | §37 MCP Protocol Endpoint、§38 Dispatcher |
| Adapter 与能力 | 《总纲》§4.4.4 | §10 Adapter、§14 Interface、§16 Capability Matrix、§17 Tool 测试 |
| MIDAS 上游 | 《总纲》§4.4.5 | §9 MIDAS 客户端、§41-§46 模型与计算 |
| 任务 | 《总纲》§4.4.6 | §20 任务、§21 SSE、§70.1 计划取消 |
| AI 工程助手 | 《总纲》§4.4.7 | §65 意图、§66 参数校验、§67-§70 计划与执行、§72 识图、§79 规范检查 |
| AI 模型 | 《总纲》§4.4.8 | §18 模型管理、§19 模型参数、§64 对话 |
| 数据与系统 | 《总纲》§4.4.9 | §30 数据管理、§32 导入、§33 清理、§34 健康检查 |
| 旧名别名映射 | 《总纲》§4.4.10 | 见本文档 §50.1（逐字收录） |

**引用约束：**

```text
本文档全部接口返回的 code 字段，取值必须存在于《总纲》§4.4 注册表。
实现方不得新增错误码。
新增错误码必须先登记到《总纲》§4.4，再由本文档引用。
```

---

**（文档结束）**





