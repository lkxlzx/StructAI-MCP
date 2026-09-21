# MIDAS API HTTP / JSON / MAPI-Key 规范

## 1. Base URL

Gen：

```text
https://moa-engineers.midasit.com:443/gen
```

Civil：

```text
https://moa-engineers.midasit.com:443/civil
```

实际部署时不要硬编码，写在 `config.json` 里，按软件分 profile：

```json
{
  "active_profile": "MIDAS CIVIL NX",
  "profiles": {
    "MIDAS GEN NX":   { "base_url": "http://localhost:3030/gen",   "mapi_key": "<key>" },
    "MIDAS CIVIL NX": { "base_url": "http://localhost:3030/civil", "mapi_key": "<key>" }
  }
}
```

用 `--profile "MIDAS CIVIL NX"`（或 `MIDAS_MCP_PROFILE`）切换产品。
`MIDAS_MAPI_KEY` / `MIDAS_BASE_URL` 环境变量优先级高于配置文件，便于临时覆盖。

## 2. Headers

```http
Content-Type: application/json
MAPI-Key: <MAPI_KEY>
```

## 3. HTTP 方法

### DOC

全部 POST：

```text
POST /doc/NEW
POST /doc/OPEN
...
POST /doc/ANAL
```

### DB

通常：

```text
GET
POST
PUT
DELETE
```

特殊：

```text
/db/UNIT
/db/STYP
```

只允许 GET / PUT。

## 4. DB Request Wrapper

创建/更新：

```json
{
  "Assign": {
    "1001": {
      "X": 0,
      "Y": 0,
      "Z": 0
    }
  }
}
```

服务器永远不要要求模型把 `Assign` 再套一层；Tool 输入只接受内部 `data`。

## 5. DB GET

全部：

```http
GET /db/NODE
```

单对象：

```http
GET /db/NODE/1001
```

## 6. DB DELETE

指定：

```http
DELETE /db/NODE/1001
```

或者 Registry 映射到：

```http
DELETE /db/NODE
```

但全量删除必须进行安全确认。

## 7. DOC Request Wrapper

### 空对象

```json
{
  "Argument": {}
}
```

### String argument

```json
{
  "Argument": "C:\\MIDAS\\MyProject.mcb"
}
```

### Object argument

```json
{
  "Argument": {
    "EXPORT_PATH": "C:\\MIDAS\\Stage1.mcb",
    "STAGE_STEP": "Stage1"
  }
}
```

## 8. OPE / VIEW / POST

多数动作采用：

```json
{
  "Argument": {
    "..."
  }
}
```

## 9. POST/TABLE

通用：

```http
POST /post/TABLE
```

典型：

```json
{
  "Argument": {
    "TABLE_NAME": "BeamForce",
    "TABLE_TYPE": "BEAMFORCE",
    "UNIT": {
      "FORCE": "KN",
      "DIST": "M"
    },
    "NODE_ELEMS": {
      "TO": "1 to 5"
    },
    "LOAD_CASE_NAMES": [
      "DL(ST)",
      "LL(CB)"
    ],
    "PARTS": [
      "Part I",
      "Part J"
    ]
  }
}
```

响应：

```json
{
  "BeamForce": {
    "FORCE": "KN",
    "DIST": "M",
    "HEAD": [
      "Index",
      "Element",
      "Load",
      "Part",
      "Fx",
      "Fy",
      "Fz",
      "Mx",
      "My",
      "Mz"
    ],
    "DATA": [
      ["1", "1", "DL(ST)", "I", "0", "0", "10", "0", "20", "0"]
    ]
  }
}
```

## 10. POST/TEXT

```http
POST /post/TEXT
```

例如时间历史节点位移：

```json
{
  "Argument": {
    "TEXT_TYPE": "TH_DISP",
    "TH_CASE_NAME": ["EQ1"],
    "NODE_ELEMS": {
      "KEYS": [1, 2, 3]
    },
    "STEP": {
      "FROM": 0,
      "TO": 10,
      "STEPS": 100
    }
  }
}
```

注意：

某些二级页的 JSON Schema 文字曾出现 `TABLE_TYPE` 与正文 Request Example 不一致的情况；对于 POST/TEXT，应以二级页请求示例实际使用的 `TEXT_TYPE` 为准。

## 11. DESIGN API

设计代码接口通常：

```text
/DESIGN/RC/...
/DESIGN/STEEL/...
/DESIGN/SRC/...
```

配置型接口使用：

```json
{
  "Assign": {
    "1": {
      "DGNCODE": "..."
    }
  }
}
```

动作接口使用：

```json
{
  "Argument": {
    "..."
  }
}
```

## 12. 认证与连接异常

建议错误归一化：

```json
{
  "ok": false,
  "category": "AUTH",
  "http_status": 401,
  "endpoint": "NODE",
  "message": "MIDAS API rejected MAPI-Key"
}
```

## 13. 不允许的行为

服务器不得：

- 把 MAPI-Key 返回给 LLM。
- 让模型直接控制任意 URL。
- 允许 `endpoint` 直接包含 `http://`、`https://`。
- 允许 `../` 路径逃逸。
- 未经 Registry 注册就转发请求。
- 把任意用户输入拼成下游 URL。

## 14. Endpoint path 构造

正确：

```text
registry.endpoint.path
```

错误：

```text
"/db/" + user_input
```

必须先：

```text
user_input -> registry lookup -> trusted path
```
