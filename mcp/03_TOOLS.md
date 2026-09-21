# 5 个 MCP Tool 定义

## 1. `midas_doc`

### Purpose

项目文档管理和分析动作。

### JSON Schema

```json
{
  "type": "object",
  "properties": {
    "command": {
      "type": "string",
      "enum": [
        "NEW",
        "OPEN",
        "CLOSE",
        "SAVE",
        "SAVEAS",
        "STAGAS",
        "IMPORT",
        "IMPORTMXT",
        "EXPORT",
        "EXPORTMXT",
        "ANAL"
      ],
      "description": "所执行的项目管理动作或计算指令"
    },
    "argument": {
      "type": "object",
      "default": {},
      "description": "传递给操作的具体参数；无参数时传入 {}"
    }
  },
  "required": ["command"]
}
```

### 服务器映射

| command | MIDAS URI | method |
|---|---|---|
| NEW | `/doc/NEW` | POST |
| OPEN | `/doc/OPEN` | POST |
| CLOSE | `/doc/CLOSE` | POST |
| SAVE | `/doc/SAVE` | POST |
| SAVEAS | `/doc/SAVEAS` | POST |
| STAGAS | `/doc/STAGAS` | POST |
| IMPORT | `/doc/IMPORT` | POST |
| IMPORTMXT | `/doc/IMPORTMXT` | POST |
| EXPORT | `/doc/EXPORT` | POST |
| EXPORTMXT | `/doc/EXPORTMXT` | POST |
| ANAL | `/doc/ANAL` | POST |

## 2. `midas_db_query`

```json
{
  "type": "object",
  "properties": {
    "endpoint": {
      "type": "string",
      "description": "Endpoint Registry key，例如 NODE、ELEM、MATL、SECT、STLD、POST:TABLE:BEAMFORCE、DESIGN:RC:KDS-41-20-2022:DCO"
    },
    "item_id": {
      "type": "string",
      "description": "可选。读取单个对象 ID。留空读取该端点全量数据。"
    }
  },
  "required": ["endpoint"]
}
```

### Query mapping

默认 DB：

```text
item_id absent
GET /db/NODE

item_id = "1003"
GET /db/NODE/1003
```

对于没有 item-id 语义的查询型 endpoint：

```text
GET /ope/PROJECTSTATUS
GET /DESIGN/RC/DRC
```

Registry 忽略 `item_id`。

## 3. `midas_db_assign`

### 用户提供的基础 Schema

```json
{
  "type": "object",
  "properties": {
    "endpoint": {
      "type": "string",
      "description": "目标端点标识"
    },
    "mode": {
      "type": "string",
      "enum": ["create", "update"],
      "description": "create -> POST；update -> PUT"
    },
    "data": {
      "type": "object",
      "description": "数据字典。顶级键是实体 ID 字符串"
    }
  },
  "required": ["endpoint", "mode", "data"]
}
```

### 推荐内部扩展

不一定暴露给 LLM；可以只作为 Registry 内部动作：

```json
{
  "transport": {
    "wrapper": "Assign | Argument | Raw",
    "selector": {
      "field": "TABLE_TYPE",
      "value": "BEAMFORCE"
    }
  }
}
```

这样可以保持 LLM tool schema 很小。

### DB create

输入：

```json
{
  "endpoint": "NODE",
  "mode": "create",
  "data": {
    "1": {
      "X": 0,
      "Y": 0,
      "Z": 0
    },
    "2": {
      "X": 6,
      "Y": 0,
      "Z": 0
    }
  }
}
```

下游：

```http
POST /db/NODE
```

```json
{
  "Assign": {
    "1": {
      "X": 0,
      "Y": 0,
      "Z": 0
    },
    "2": {
      "X": 6,
      "Y": 0,
      "Z": 0
    }
  }
}
```

### DB update

输入：

```json
{
  "endpoint": "NODE",
  "mode": "update",
  "data": {
    "2": {
      "X": 7,
      "Y": 0,
      "Z": 0
    }
  }
}
```

下游：

```http
PUT /db/NODE
```

## 4. `midas_db_delete`

```json
{
  "type": "object",
  "properties": {
    "endpoint": {
      "type": "string",
      "description": "Endpoint Registry key"
    },
    "target_ids": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "待删除的 ID 字符串列表"
    }
  },
  "required": ["endpoint", "target_ids"]
}
```

### 安全规则

强烈建议：

```text
target_ids = []
```

不要自动解释为“删除全部”。

如要开放全量删除，最好在未来 Schema 中加：

```json
"delete_all": {
  "type": "boolean",
  "default": false
}
```

并要求：

```text
delete_all = true
```

才发送 `DELETE /db/{endpoint}` 无 ID 形式。

## 5. `midas_frame_run`

### Purpose

钢门式刚架的**一次性入口**。给一个 spec，它一次做完 建模 → 分析 → 自洽校验 → 中文报告，
并把同一份报告作为工具结果返回。

### JSON Schema

```json
{
  "name": "midas_frame_run",
  "inputSchema": {
    "type": "object",
    "properties": {
      "spec": {"type": "object",
               "description": "模型 spec; 省略的键沿用已验证默认值, 未知键按名拒绝"},
      "spec_path": {"type": "string",
                    "description": "spec JSON 文件, 例如 specs/portal-frame.json"},
      "out_dir": {"type": "string",
                  "description": "report.md / state.json / 审计轨迹的目录"},
      "clear": {"type": "boolean", "default": false,
                "description": "先删除本驱动自己使用的 DB 集合"}
    }
  }
}
```

### 返回值

工具结果就是 `report` 全文（不截断 —— 截断的报告读起来仍像完整的，却恰好藏掉被引用的数字）。
`data` 里是机器可读裁决：

```json
{"ok": true, "analysis": "SUCCESS", "criteria": [], "verifications": [],
 "steps": [], "failed": [], "note": null, "exit_code": 0}
```

`ok` 很难拿到：需要 `analysis == "SUCCESS"`、判据列表非空且无失败项、自洽校验真的跑过并全过。
`analysis == "REFUSED"` 表示活文档非空、本次拒绝建模，此时**不返回任何报告**，
`category` 为 `MODEL_NOT_EMPTY`。

### 实现

不是第二份实现，而是 `python -m midas_mcp.frame --json` 的包装：驱动把报告打到 stdout，
而服务器进程的 stdout 是 JSON-RPC 流，所以必须是子进程。凭据经环境变量传给子进程，
从不上命令行。报告里描述本次运行的内容（工具清单、工件目录）都从运行本身读回，不写死。

实测 (Gen NX 2027): 18/18 步, 13/13 判据, 4/4 自洽校验, `ANALYSIS = SUCCESS`, 约 5 分钟。

## 6. Tool annotations

建议：

```text
midas_doc
  destructive_hint = false
  read_only_hint = false

midas_db_query
  destructive_hint = false
  read_only_hint = true
  idempotent_hint = true

midas_db_assign
  destructive_hint = false
  read_only_hint = false

midas_db_delete
  destructive_hint = true
  read_only_hint = false

midas_frame_run
  destructive_hint = true
  read_only_hint = false
  idempotent_hint = false
```

## 7. 为什么不拆成更多 Tool

不要创建：

```text
create_node
update_node
create_beam
create_section
assign_load
run_analysis
export_table
capture_view
...
```

这样会让模型工具选择空间随 MIDAS 版本扩张。

`midas_frame_run` 是唯一有意加上的专用工具：它不是又一个 MIDAS 端点，而是把已经验证过的
整条流程（建模 → 分析 → 自洽校验 → 报告）固化成一个入口，让同类提示词一次跑通。
它内部仍然只用上面那 4 个泛化工具能表达的东西。

正确方式：

```text
tool selection = 5 (4 个泛化 + 1 个一次性流程)
endpoint selection = registry
schema validation = server
```
