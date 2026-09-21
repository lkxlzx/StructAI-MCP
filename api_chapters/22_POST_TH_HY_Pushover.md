# POST Time History / Hydration / Pushover

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
| `TH_DISP / TH_VELOCITY / TH_ACCEL` | `POST /post/TEXT` | TH node results | `TEXT_TYPE` |
| `TH_ELEMENT_*` | `POST /post/TEXT` | TH truss/beam/plane/solid | `TEXT_TYPE` |
| `TH_PLATE_*` | `POST /post/TEXT` | TH plate | `TEXT_TYPE` |
| `TH_WALL_*` | `POST /post/TEXT` | TH wall | `TEXT_TYPE` |
| `TH_GENERAL_LINK_*` | `POST /post/TEXT` | TH general link | `TEXT_TYPE` |
| `PO_DISP` | `POST /post/TEXT` | Pushover displacement | `TEXT_TYPE` |
| `PO_ELEMENT_*` | `POST /post/TEXT` | Pushover element | `TEXT_TYPE` |
| `PO_WALL_*` | `POST /post/TEXT` | Pushover wall | `TEXT_TYPE` |
| `PO_GENERAL_LINK_*` | `POST /post/TEXT` | Pushover general link | `TEXT_TYPE` |
| `PO_ELASTIC_LINK_*` | `POST /post/TEXT` | Pushover elastic link | `TEXT_TYPE` |
| `HINGE_*` | `POST /post/TABLE` | Inelastic hinge results | `TABLE_TYPE` |
| `HY_*` | `POST /view/RESULTGRAPHIC` | Hydration graphics | `Argument` |
| `THRE / THRG / THRI / THRS` | `CRUD /db/THR*` | Smart graph definitions | `Assign` |

## MCP 映射规则

```text
GET     -> midas_db_query
POST    -> midas_db_assign
PUT     -> midas_db_assign
DELETE  -> midas_db_delete

DOC command -> midas_doc
```


## 通用 Request 模板

### POST/TABLE

```json
{
  "Argument": {
    "TABLE_NAME": "Example",
    "TABLE_TYPE": "<registered type>",
    "EXPORT_PATH": "C:\\MIDAS\\Result\\Output.JSON"
  }
}
```

### POST/TEXT

```json
{
  "Argument": {
    "TEXT_TYPE": "<registered text type>",
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


## Complete core examples

### Time History displacement

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

### Pushover displacement

```json
{
  "Argument": {
    "TEXT_TYPE": "PO_DISP",
    "PO_CASE_NAME": ["PO1"],
    "NODE_ELEMS": {
      "KEYS": [1001]
    },
    "STEP": {
      "FROM": 0,
      "TO": 100,
      "STEPS": 20
    }
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
https://github.com/Dennis5882/MIDAS-API/blob/main/docs/manual/22_POST_TH_HY_Pushover.md
```

正式实现时，字段级 JSON Schema、每一个 endpoint 的 Specifications、官方 Request/Response 及 Python Example 应从该二级页同步到 `registry/`，不要人工猜字段。
