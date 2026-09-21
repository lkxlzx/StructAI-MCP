# OPE

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
| `PROJECTSTATUS` | `GET /ope/PROJECTSTATUS` | Project status | `none` |
| `DIVIDEELEM` | `POST /ope/DIVIDEELEM` | Divide elements | `Argument` |
| `SECTPROP` | `POST /ope/SECTPROP` | Section properties calculation | `Argument` |
| `USLC` | `POST /ope/USLC` | Using load combinations | `Argument` |
| `LINEBMLD` | `POST /ope/LINEBMLD` | Line beam load | `Argument` |
| `AUTOMESH` | `POST /ope/AUTOMESH` | Auto mesh planar area | `Argument` |
| `SSPS` | `POST /ope/SSPS` | Surface spring operation | `Argument` |
| `EDMP` | `POST /ope/EDMP` | Change property operation | `Argument` |
| `STOR` | `POST /ope/STOR` | Story calculation | `Argument` |
| `STORY_PARAM` | `POST /ope/STORY_PARAM` | Story check parameter | `Argument` |
| `STORY_IRR_PARAM` | `POST /ope/STORY_IRR_PARAM` | Story irregularity check | `Argument` |
| `STORYPROP` | `POST /ope/STORYPROP` | Story properties | `Argument` |
| `MEMB` | `POST /ope/MEMB` | Member assignment operation | `Argument` |
| `GUSTFACTOR` | `POST /ope/GUSTFACTOR` | Gust factor calculator | `Argument` |
| `LCOM-GEN` | `POST /ope/LCOM-GEN` | General combinations operation | `Argument` |
| `LCOM-CONC` | `POST /ope/LCOM-CONC` | Concrete combinations operation | `Argument` |
| `LCOM-STEEL` | `POST /ope/LCOM-STEEL` | Steel combinations operation | `Argument` |
| `LCOM-SRC` | `POST /ope/LCOM-SRC` | SRC combinations operation | `Argument` |
| `GSBG` | `POST /ope/GSBG` | Bridge girder image generation | `Argument` |

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
https://github.com/Dennis5882/MIDAS-API/blob/main/docs/manual/15_OPE.md
```

正式实现时，字段级 JSON Schema、每一个 endpoint 的 Specifications、官方 Request/Response 及 Python Example 应从该二级页同步到 `registry/`，不要人工猜字段。
