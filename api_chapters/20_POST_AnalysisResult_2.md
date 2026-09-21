# POST Analysis Results Part 2

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
| `PLATEFORCE*` | `POST /post/TABLE` | Plate force variants | `TABLE_TYPE=PLATEFORCE*` |
| `PLATESTRESS*` | `POST /post/TABLE` | Plate stress variants | `TABLE_TYPE=PLATESTRESS*` |
| `PLATESTRAIN*` | `POST /post/TABLE` | Plate strain variants | `TABLE_TYPE=PLATESTRAIN*` |
| `PLANESTRESS*` | `POST /post/TABLE` | Plane stress force/stress | `TABLE_TYPE=PLANESTRESS*` |
| `PLANESTRAIN*` | `POST /post/TABLE` | Plane strain force/stress | `TABLE_TYPE=PLANESTRAIN*` |
| `AXISYMMETRIC*` | `POST /post/TABLE` | Axisymmetric results | `TABLE_TYPE=AXISYMMETRIC*` |
| `SOLID*` | `POST /post/TABLE` | Solid force/stress/strain | `TABLE_TYPE=SOLID*` |
| `ELASTICLINK*` | `POST /post/TABLE` | Elastic link | `TABLE_TYPE=ELASTICLINK*` |
| `GENERAL_LINK_*` | `POST /post/TABLE` | General link | `TABLE_TYPE=GENERAL_LINK_*` |
| `EIGENVALUEMODE` | `POST /post/TABLE` | Vibration mode | `TABLE_TYPE=EIGENVALUEMODE` |
| `PARTICIPATIONVECTORMODE` | `POST /post/TABLE` | Participation vector | `TABLE_TYPE=PARTICIPATIONVECTORMODE` |
| `BUCKLINGMODE` | `POST /post/TABLE` | Buckling mode | `TABLE_TYPE=BUCKLINGMODE` |
| `TNDN_*` | `POST /post/TABLE` | Tendon tables | `TABLE_TYPE=TNDN_*` |
| `COMPSECTBEAM*` | `POST /post/TABLE` | Composite section result | `TABLE_TYPE=COMPSECTBEAM*` |
| `SELF_CONST_BEAM_*` | `POST /post/TABLE` | Self-constraint force/stress | `TABLE_TYPE=SELF_CONST_BEAM_*` |
| `WALL_FORCE_MOMENT` | `POST /post/TABLE` | Wall force | `TABLE_TYPE=WALL_FORCE_MOMENT` |

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
https://github.com/Dennis5882/MIDAS-API/blob/main/docs/manual/20_POST_AnalysisResult_2.md
```

正式实现时，字段级 JSON Schema、每一个 endpoint 的 Specifications、官方 Request/Response 及 Python Example 应从该二级页同步到 `registry/`，不要人工猜字段。
