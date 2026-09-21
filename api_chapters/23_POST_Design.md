# POST Design Tables

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
| `PM` | `POST /post/PM` | P-M interaction diagram | `Argument` |
| `STEELCODECHECK` | `POST /post/STEELCODECHECK` | Steel code check | `Argument` |
| `BEAMDESIGNFORCES` | `POST /post/TABLE` | Concrete beam design forces | `TABLE_TYPE` |
| `COLUMNDESIGNFORCES` | `POST /post/TABLE` | Concrete column design forces | `TABLE_TYPE` |
| `BRACEDESIGNFORCES` | `POST /post/TABLE` | Concrete brace design forces | `TABLE_TYPE` |
| `WALLDESIGNFORCES` | `POST /post/TABLE` | Concrete wall design forces | `TABLE_TYPE` |
| `STEELMEMBERDESIGNFORCES` | `POST /post/TABLE` | Steel member design forces | `TABLE_TYPE` |
| `SRCBEAMDESIGNFORCES` | `POST /post/TABLE` | SRC beam design forces | `TABLE_TYPE` |
| `SRCCOLUMNDESIGNFORCES` | `POST /post/TABLE` | SRC column design forces | `TABLE_TYPE` |
| `COLDFORMEDSTEELMEMBERDESIGNFORCES` | `POST /post/TABLE` | Cold-formed steel forces | `TABLE_TYPE` |

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

### Steel code check

```json
{
  "Argument": {}
}
```

### Concrete beam design forces

```json
{
  "Argument": {
    "TABLE_NAME": "BeamDesign",
    "TABLE_TYPE": "BEAMDESIGNFORCES",
    "NODE_ELEMS": {
      "KEYS": [1, 2, 3]
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
https://github.com/Dennis5882/MIDAS-API/blob/main/docs/manual/23_POST_Design.md
```

正式实现时，字段级 JSON Schema、每一个 endpoint 的 Specifications、官方 Request/Response 及 Python Example 应从该二级页同步到 `registry/`，不要人工猜字段。
