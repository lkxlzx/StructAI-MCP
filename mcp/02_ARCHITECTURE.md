# MIDAS MCP Connector Architecture

## 1. 总体架构

```text
                    ┌──────────────────────────────┐
                    │ Claude / Cursor / Agent / LLM│
                    └──────────────┬───────────────┘
                                   │
                                   │ MCP JSON-RPC 2.0
                                   ▼
                  ┌────────────────────────────────┐
                  │        MIDAS MCP Server         │
                  │                                │
                  │  Tool Layer                   │
                  │  ┌────────────┐               │
                  │  │ midas_doc  │               │
                  │  ├────────────┤               │
                  │  │ db_query   │               │
                  │  ├────────────┤               │
                  │  │ db_assign  │               │
                  │  ├────────────┤               │
                  │  │ db_delete  │               │
                  │  └────────────┘               │
                  │            │                   │
                  │            ▼                   │
                  │     Endpoint Registry          │
                  │            │                   │
                  │   ┌────────┼─────────────┐     │
                  │   │        │             │     │
                  │  DB       OPE           VIEW   │
                  │   │        │             │     │
                  │  POST     POST          POST   │
                  │  GET      GET           ...    │
                  │  PUT      ...                  │
                  │  DELETE   ...                  │
                  │            │                   │
                  │            ▼                   │
                  │       MAPI REST Client         │
                  └────────────┬───────────────────┘
                               │
                               │ HTTPS + MAPI-Key
                               ▼
                  ┌────────────────────────────────┐
                  │       MIDAS NX API Host        │
                  │    /civil or /gen Base URL     │
                  └────────────┬───────────────────┘
                               │
                               │ WebSocket
                               ▼
                    ┌─────────────────────────┐
                    │ MIDAS Civil NX / Gen NX │
                    └─────────────────────────┘
```

MIDAS 官方说明描述了 REST API → Server → WebSocket → MIDAS NX 的通信关系，并要求调用方在 REST 请求 Header 中携带 `MAPI-Key`。

## 2. 服务端模块

### 2.1 MCP Transport

负责：

- stdio
- Streamable HTTP
- initialize
- tools/list
- tools/call
- cancellation

### 2.2 Tool Router

```text
Tool name
   |
   +--> midas_doc
   +--> midas_db_query
   +--> midas_db_assign
   +--> midas_db_delete
```

### 2.3 Endpoint Registry

推荐结构：

```json
{
  "NODE": {
    "namespace": "db",
    "path": "/db/NODE",
    "methods": ["GET", "POST", "PUT", "DELETE"],
    "read_wrapper": "none",
    "write_wrapper": "Assign",
    "id_style": "string_number",
    "tool_read": "midas_db_query",
    "tool_create": "midas_db_assign",
    "tool_update": "midas_db_assign",
    "tool_delete": "midas_db_delete"
  }
}
```

POST/TABLE：

```json
{
  "POST:TABLE:BEAMFORCE": {
    "namespace": "post",
    "path": "/post/TABLE",
    "methods": ["POST"],
    "selector_field": "TABLE_TYPE",
    "selector_value": "BEAMFORCE",
    "write_wrapper": "Argument",
    "tool_create": "midas_db_assign"
  }
}
```

VIEW Capture：

```json
{
  "VIEW:CAPTURE": {
    "namespace": "view",
    "path": "/view/CAPTURE",
    "methods": ["POST"],
    "write_wrapper": "Argument"
  }
}
```

## 3. Registry 必须包含的信息

至少：

```text
endpoint_key
namespace
uri
methods
selector_field
selector_value
request_wrapper
supports_item_id
delete_strategy
response_key
product
version
source_page
risk_level
```

推荐再增加：

```text
request_schema
response_schema
sample_request
sample_response
timeout
retryable
idempotent
requires_analysis
requires_design
destructive
```

## 4. Dispatcher

伪代码：

```text
dispatch(tool, args):

  validate_tool_schema(args)

  endpoint = registry.lookup(args.endpoint)

  if endpoint == null:
      return MCP input error

  validate_method(endpoint, tool, args)

  path = endpoint.path
  body = build_body(endpoint, args)

  result = midas_http.request(
      method = endpoint.method,
      path = path,
      body = body,
      headers = {
          "MAPI-Key": secret_store.mapi_key,
          "Content-Type": "application/json"
      }
  )

  normalized = normalize_response(endpoint, result)

  return normalized
```

## 5. Endpoint Registry 与 MCP Tool 的关系

不要：

```text
505 endpoint = 505 tools
```

而要：

```text
505 endpoint
    |
    v
Endpoint Registry
    |
    +-- read
    +-- create
    +-- update
    +-- delete
    |
    v
4 MCP tools
```

## 6. State

不要把 MIDAS 当前文件状态完全藏在模型外部。

建议服务端维护：

```text
connection_id
product: civil | gen
base_url
current_project
last_save_time
analysis_status
model_revision
```

如果使用无状态 MCP HTTP，则可以把这些状态编码为显式 handle：

```json
{
  "project_handle": "midas-project-8e7..."
}
```

但对于 stdio 单进程模式，服务器内存状态是最简单的。

## 7. 并发

MIDAS GUI / model session 一般不应该被多个互斥写操作同时修改。

建议：

```text
READ GET             -> 并发安全策略较宽松
POST / PUT / DELETE  -> per-project mutex
ANAL                 -> per-project exclusive lock
VIEW                 -> 可选读锁 / GUI lock
```

例如：

```text
project A -> analysis lock
project B -> 不受 project A 锁影响
```

## 8. 安全分级

建议 Registry：

```text
READ
WRITE
DESTRUCTIVE
ANALYSIS
EXPORT
IMPORT
DESIGN
```

MCP Tool annotations：

- query: read-only=true
- assign: read-only=false
- delete: destructive=true
- doc ANAL: destructive=false, long_running=true

## 9. Retry

默认仅对：

- TCP reset
- connection reset
- 502 / 503 / 504

考虑一次有限重试。

不要自动重试：

- DELETE
- ANAL
- IMPORT
- EXPORT
- DESIGN action

除非 Registry 明确标记为 idempotent。

## 10. 进程架构

Windows EXE 推荐：

```text
midas-mcp.exe
├─ config.json
├─ logs/
├─ schemas/
├─ registry/
│  ├─ doc.json
│  ├─ db.json
│  ├─ ope.json
│  ├─ view.json
│  ├─ post.json
│  └─ design.json
└─ src/
```

这样以后 MIDAS 二级页面变动时只更新 Registry，不改 Tool 层。
