# 4 个泛化 MCP Tool 定义

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

## 5. Tool annotations

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
```

## 6. 为什么不拆成更多 Tool

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

正确方式：

```text
tool selection = 4
endpoint selection = registry
schema validation = server
```
