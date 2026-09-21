# DB Settlement / Misc Loads

> Source: MIDAS API Online Manual  
> Official manual: https://support.midasuser.com/hc/en-us/articles/33016922742937-MIDAS-API-Online-Manual  
> Mirror/index: https://github.com/Dennis5882/MIDAS-API/tree/main/docs/manual

## Scope

本章单独对应 MIDAS API 的一个二级功能章节。接口保持“**二级页面 → Registry → 4 个 MCP Tool**”映射，不把每个 MIDAS endpoint 暴露成独立 MCP Tool。

### Base URL

```text
https://moa-engineers.midasit.com:443/gen
https://moa-engineers.midasit.com:443/civil
```

### HTTP Headers

```http
Content-Type: application/json
MAPI-Key: <MAPI_KEY>
```


## Endpoint Registry

| Endpoint | URI / Methods | 功能 | Request wrapper |
|---|---|---|---|
| `SMPT` | `CRUD /db/SMPT` | Settlement group | `Assign` |
| `SMLC` | `CRUD /db/SMLC` | Settlement load cases | `Assign` |
| `PLCB` | `CRUD /db/PLCB` | Pre-composite section | `Assign` |
| `LDSQ` | `CRUD /db/LDSQ` | Load sequence nonlinear | `Assign` |
| `WVLD` | `CRUD /db/WVLD` | Wave loads | `Assign` |
| `IELC` | `CRUD /db/IELC` | Ignore elements for load cases | `Assign` |
| `IFGS` | `CRUD /db/IFGS` | Large displacement initial force | `Assign` |
| `EFCT` | `CRUD /db/EFCT` | Small displacement initial force control | `Assign` |
| `INMF` | `CRUD /db/INMF` | Initial element force | `Assign` |

## MCP 映射规则

```text
GET     -> midas_db_query
POST    -> midas_db_assign
PUT     -> midas_db_assign
DELETE  -> midas_db_delete

DOC command -> midas_doc
```


## 通用 Request 模板

### DB Assign

```json
{
  "Assign": {
    "1": {
      "...": "二级页面字段"
    }
  }
}
```

### GET

```http
GET /db/<ENDPOINT>
```

### GET single

```http
GET /db/<ENDPOINT>/1
```

### DELETE

```http
DELETE /db/<ENDPOINT>/1
```


## Complete core examples

### Generic endpoint example

```json
{
  "Assign": {
    "1": {
      "...": "replace with exact secondary-page fields"
    }
  }
}
```

For action endpoints:

```json
{
  "Argument": {
    "...": "replace with exact secondary-page fields"
  }
}
```


## Response conventions

### DB response

```json
{
  "<ENDPOINT>": {
    "1": {
      "...": "..."
    }
  }
}
```

### POST/TABLE response

```json
{
  "Example": {
    "FORCE": "kN",
    "DIST": "m",
    "HEAD": ["Index", "..."],
    "DATA": [["1", "..."]]
  }
}
```


## Registry / validation notes

1. endpoint key 必须来自 Registry，不接受任意 URL。
2. `Assign` 与 `Argument` 必须由 Registry 决定，LLM 不直接决定 wrapper。
3. POST/TABLE 以 `TABLE_TYPE` 区分逻辑端点。
4. POST/TEXT 以 `TEXT_TYPE` 区分逻辑端点。
5. DELETE 必须有明确目标 ID。
6. 长耗时 ANAL 必须使用独立 timeout / project lock。


## 二级页面完整源文件

本章对应的原始同步文件：

```text
https://github.com/Dennis5882/MIDAS-API/blob/main/docs/manual/11_DB_Settlement_Misc_Loads.md
```

正式实现时，字段级 JSON Schema、每一个 endpoint 的 Specifications、官方 Request/Response 及 Python Example 应从该二级页同步到 `registry/`，不要人工猜字段。
