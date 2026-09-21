# MCP Protocol & Communication Specification

## 1. MCP 协议定位

MCP 是 LLM Host 与外部 Tool Server 之间的协议；MIDAS API 是下游业务 REST API。

因此存在两层通信：

```text
Layer 1
LLM Host <-> MCP Server
JSON-RPC 2.0 / MCP

Layer 2
MCP Server <-> MIDAS NX Open API
HTTP/HTTPS + JSON + MAPI-Key
```

## 2. MCP 版本

生产实现建议以当前 MCP `2026-07-28` 规范为基线。

参考：

- https://modelcontextprotocol.io/
- https://blog.modelcontextprotocol.io/posts/2026-07-28/

该版本的一个重要变化是协议核心向 stateless request/response 设计演进。对于单机 EXE 型 MIDAS Connector，建议优先实现：

- stdio transport：Claude Desktop / Cursor / 本地 Agent
- Streamable HTTP：服务器化、多客户端、跨主机

## 3. stdio 建议

对于 Windows 上编译成 `.exe` 的 MIDAS MCP Server：

```text
Host
  |
  | spawn process
  v
midas-mcp.exe
  |
  +-- stdin  : MCP JSON-RPC messages
  +-- stdout : MCP JSON-RPC messages
  +-- stderr : logs only
```

严格要求：

- stdout 不输出普通日志。
- 日志写 stderr。
- MCP 响应写 stdout。
- 不在 stdout 打印 banner。
- 服务异常退出时返回进程级错误并记录 stderr。

## 4. Streamable HTTP 建议

远程部署：

```text
Claude / Agent
      |
      | HTTP POST
      v
https://host:port/mcp
      |
      v
MIDAS MCP Server
```

推荐：

- `/mcp` 作为 MCP endpoint。
- 支持 JSON response。
- 需要服务端消息时启用 SSE 能力。
- 负载均衡时保持 request header / body 的一致性。
- 使用 HTTPS。
- MAPI-Key 只保存在服务器端，不暴露给模型。

## 5. MCP initialize

典型交互：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2026-07-28",
    "capabilities": {
      "tools": {}
    },
    "clientInfo": {
      "name": "your-host",
      "version": "1.0.0"
    }
  }
}
```

服务器：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2026-07-28",
    "capabilities": {
      "tools": {}
    },
    "serverInfo": {
      "name": "midas-mcp",
      "version": "1.0.0"
    }
  }
}
```

## 6. tools/list

客户端取得 4 个 MCP Tool：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

返回核心：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "midas_doc",
        "description": "MIDAS project/document operations",
        "inputSchema": {}
      },
      {
        "name": "midas_db_query",
        "description": "Read/query MIDAS model data",
        "inputSchema": {}
      },
      {
        "name": "midas_db_assign",
        "description": "Create/update MIDAS data or invoke registered write/action endpoints",
        "inputSchema": {}
      },
      {
        "name": "midas_db_delete",
        "description": "Delete MIDAS model data",
        "inputSchema": {}
      }
    ]
  }
}
```

## 7. tools/call

客户端把模型的 Tool Call 原样传给 MCP：

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "name": "midas_db_assign",
    "arguments": {
      "endpoint": "NODE",
      "mode": "create",
      "data": {
        "1": {
          "X": 0,
          "Y": 0,
          "Z": 0
        }
      }
    }
  }
}
```

服务器内部转换为：

```http
POST /db/NODE
MAPI-Key: <server secret>
Content-Type: application/json
```

Body：

```json
{
  "Assign": {
    "1": {
      "X": 0,
      "Y": 0,
      "Z": 0
    }
  }
}
```

## 8. Tool result

成功时建议同时返回：

1. 人类/LLM 易读的 text。
2. `structuredContent`（如果 SDK / 协议版本支持并启用 outputSchema）。

建议统一结果：

```json
{
  "ok": true,
  "endpoint": "NODE",
  "method": "POST",
  "status": 200,
  "data": {
    "NODE": {
      "1": {
        "X": 0,
        "Y": 0,
        "Z": 0
      }
    }
  }
}
```

## 9. MCP 错误 vs MIDAS 错误

必须区分：

### A. MCP 参数错误

例如 `endpoint` 不在 Registry：

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "result": {
    "isError": true,
    "content": [
      {
        "type": "text",
        "text": "Unknown MIDAS endpoint: NODE_X"
      }
    ]
  }
}
```

### B. MIDAS HTTP 错误

```json
{
  "ok": false,
  "upstream": {
    "status": 401,
    "body": {
      "error": "unauthorized"
    }
  },
  "endpoint": "NODE"
}
```

不要把下游 HTTP 401/404/500 伪装成 MCP 协议错误。

## 10. Cancellation / timeout

推荐默认：

- query：10~30 s
- assign：30~60 s
- analysis：5~30 min
- result table：30~180 s

实际值可以通过配置覆盖。

分析计算属于长任务，不建议让一个 HTTP socket 无限制等待。

## 11. Trace

建议为每次 MCP Tool Call 生成：

```text
mcp_request_id
midas_request_id
tool
endpoint
http_method
duration_ms
status
```

若接入 OpenTelemetry，建议在 `_meta` / trace context 中透传 traceparent。

## 12. 不要让模型接触 MAPI-Key

错误：

```json
{
  "mapi_key": "...."
}
```

正确：

```text
LLM
  -> midas_db_assign(...)
     -> Registry
        -> Server Secret Store
           -> MAPI-Key
              -> MIDAS API
```
