# POST Analysis Results Part 1

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
| `REACTIONG` | `POST /post/TABLE` | Global reaction | `TABLE_TYPE=REACTIONG` |
| `REACTIONL` | `POST /post/TABLE` | Local reaction | `TABLE_TYPE=REACTIONL` |
| `REACTIONSURFACESPRING` | `POST /post/TABLE` | Surface spring reaction | `TABLE_TYPE=REACTIONSURFACESPRING` |
| `DISPLACEMENTG/L` | `POST /post/TABLE` | Displacement | `TABLE_TYPE=DISPLACEMENTG/L` |
| `TRUSSFORCE` | `POST /post/TABLE` | Truss force | `TABLE_TYPE=TRUSSFORCE` |
| `TRUSSSTRESS` | `POST /post/TABLE` | Truss stress | `TABLE_TYPE=TRUSSSTRESS` |
| `CABLEFORCE` | `POST /post/TABLE` | Cable force | `TABLE_TYPE=CABLEFORCE` |
| `CABLECONFIG` | `POST /post/TABLE` | Cable configuration | `TABLE_TYPE=CABLECONFIG` |
| `CABLEEFFIENCY` | `POST /post/TABLE` | Cable efficiency | `TABLE_TYPE=CABLEEFFIENCY` |
| `BEAMFORCE` | `POST /post/TABLE` | Beam force | `TABLE_TYPE=BEAMFORCE` |
| `BEAMFORCESTP` | `POST /post/TABLE` | Beam force static prestress | `TABLE_TYPE=BEAMFORCESTP` |
| `BEAMSTRESS*` | `POST /post/TABLE` | Beam stress variants | `TABLE_TYPE=BEAMSTRESS*` |
| `CONCURRENT_JOINT_FORCE` | `POST /post/TABLE` | Concurrent joint force | `TABLE_TYPE=CONCURRENT_JOINT_FORCE` |

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

### BEAMFORCE

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
      "TO": "1 to 10"
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

### REACTIONG

```json
{
  "Argument": {
    "TABLE_NAME": "Reaction",
    "TABLE_TYPE": "REACTIONG",
    "NODE_ELEMS": {
      "KEYS": [1, 2, 3, 4]
    },
    "LOAD_CASE_NAMES": [
      "DL(ST)",
      "EQX(RS)"
    ]
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
https://github.com/Dennis5882/MIDAS-API/blob/main/docs/manual/19_POST_AnalysisResult_1.md
```

正式实现时，字段级 JSON Schema、每一个 endpoint 的 Specifications、官方 Request/Response 及 Python Example 应从该二级页同步到 `registry/`，不要人工猜字段。
