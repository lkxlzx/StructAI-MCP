# DB Moving Loads

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
| `MVCD` | `CRUD /db/MVCD` | Moving-load code | `Assign` |
| `LLAN` | `CRUD /db/LLAN` | Traffic line lanes | `Assign` |
| `LLANch` | `CRUD /db/LLANch` | Traffic line lanes China | `Assign` |
| `LLANid` | `CRUD /db/LLANid` | Traffic line lanes India | `Assign` |
| `LLANtr` | `CRUD /db/LLANtr` | Traffic line lanes transverse | `Assign` |
| `LLANop` | `CRUD /db/LLANop` | Lane optimization | `Assign` |
| `SLAN` | `CRUD /db/SLAN` | Traffic surface lanes | `Assign` |
| `SLANch` | `CRUD /db/SLANch` | Traffic surface lanes China | `Assign` |
| `SLANop` | `CRUD /db/SLANop` | Surface lane optimization | `Assign` |
| `MVHL` | `CRUD /db/MVHL` | Vehicles | `Assign` |
| `MVHLtr` | `CRUD /db/MVHLtr` | Vehicles transverse | `Assign` |
| `MVLD` | `CRUD /db/MVLD` | Moving load cases | `Assign` |
| `MVLDch` | `CRUD /db/MVLDch` | Moving load cases China | `Assign` |
| `MVLDid` | `CRUD /db/MVLDid` | Moving load cases India | `Assign` |
| `MVLDbs` | `CRUD /db/MVLDbs` | Moving load cases BS | `Assign` |
| `MVLDeu` | `CRUD /db/MVLDeu` | Moving load cases Eurocode | `Assign` |
| `MVLDpl` | `CRUD /db/MVLDpl` | Moving load cases Poland | `Assign` |
| `MVLDtr` | `CRUD /db/MVLDtr` | Moving load cases transverse | `Assign` |
| `CRGR` | `CRUD /db/CRGR` | Concurrent reaction group | `Assign` |
| `CJFG` | `CRUD /db/CJFG` | Concurrent joint force group | `Assign` |
| `MVHC` | `CRUD /db/MVHC` | Vehicle classes | `Assign` |
| `SINF` | `CRUD /db/SINF` | Influence-surface plate elements | `Assign` |
| `MLSP` | `CRUD /db/MLSP` | Lane support interior pier moments | `Assign` |
| `MLSR` | `CRUD /db/MLSR` | Lane support interior pier reactions | `Assign` |
| `DYLA` | `CRUD /db/DYLA` | Dynamic load allowance | `Assign` |
| `IMPF` | `CRUD /db/IMPF` | Additional impact factor | `Assign` |
| `DYFG` | `CRUD /db/DYFG` | Railway dynamic factor | `Assign` |
| `DYNF` | `CRUD /db/DYNF` | Railway dynamic factor by element | `Assign` |

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

### MVCD

```json
{
  "Assign": {
    "1": {
      "CODE": "KSCE-LSD15"
    }
  }
}
```

### LLAN

```json
{
  "Assign": {
    "1": {
      "COMMON": {
        "LL_NAME": "LL_01",
        "LOAD_DIST": "LANE",
        "GROUP_NAME": "",
        "SKEW_START": 0,
        "SKEW_END": 0,
        "MOVING": "FORWARD",
        "WHEEL_SPACE": 1.8,
        "WIDTH": 3,
        "OPT_AUTO_LANE": true,
        "ALLOW_WIDTH": 3
      },
      "LANE_ITEMS": [
        { "ELEM": 1, "ECC": -1.5 },
        { "ELEM": 2, "ECC": -1.5 },
        { "ELEM": 3, "ECC": -1.5 }
      ]
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
https://github.com/Dennis5882/MIDAS-API/blob/main/docs/manual/08_DB_Moving_Loads.md
```

正式实现时，字段级 JSON Schema、每一个 endpoint 的 Specifications、官方 Request/Response 及 Python Example 应从该二级页同步到 `registry/`，不要人工猜字段。
