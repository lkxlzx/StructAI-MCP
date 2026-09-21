# DOC

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
| `NEW` | `POST /doc/NEW` | 新建项目 | `{}` |
| `OPEN` | `POST /doc/OPEN` | 打开项目 | `String file path` |
| `CLOSE` | `POST /doc/CLOSE` | 关闭项目 | `{}` |
| `SAVE` | `POST /doc/SAVE` | 保存 | `{}` |
| `SAVEAS` | `POST /doc/SAVEAS` | 另存为 | `String file path` |
| `STAGAS` | `POST /doc/STAGAS` | 当前施工阶段另存为 | `{EXPORT_PATH,STAGE_STEP}` |
| `IMPORT` | `POST /doc/IMPORT` | 导入 JSON | `String file path` |
| `IMPORTMXT` | `POST /doc/IMPORTMXT` | 导入 MCT/MGT | `String file path` |
| `EXPORT` | `POST /doc/EXPORT` | 导出 JSON | `String file path` |
| `EXPORTMXT` | `POST /doc/EXPORTMXT` | 导出 MCT/MGT | `String file path` |
| `ANAL` | `POST /doc/ANAL` | 执行分析 | `{} / action object` |

## MCP 映射规则

```text
GET     -> midas_db_query
POST    -> midas_db_assign
PUT     -> midas_db_assign
DELETE  -> midas_db_delete

DOC command -> midas_doc
```


## 通用 Request 模板

### Empty Argument

```json
{
  "Argument": {}
}
```

### String Argument

```json
{
  "Argument": "C:\\MIDAS\\project.mcb"
}
```

### Object Argument

```json
{
  "Argument": {
    "...": "二级页面定义字段"
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
https://github.com/Dennis5882/MIDAS-API/blob/main/docs/manual/01_DOC.md
```

正式实现时，字段级 JSON Schema、每一个 endpoint 的 Specifications、官方 Request/Response 及 Python Example 应从该二级页同步到 `registry/`，不要人工猜字段。
