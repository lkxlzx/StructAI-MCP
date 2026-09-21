# DB Properties

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
| `MATL` | `CRUD /db/MATL` | Material | `Assign` |
| `MATL-M1` | `CRUD /db/MATL-M1` | Hyper-S material | `Assign` |
| `IMFM` | `CRUD /db/IMFM` | Fiber inelastic material | `Assign` |
| `IMFM-M1` | `CRUD /db/IMFM-M1` | Auto material link | `Assign` |
| `TDMF` | `CRUD /db/TDMF` | User time-dependent material | `Assign` |
| `TDMT` | `CRUD /db/TDMT` | Creep/shrinkage material | `Assign` |
| `TDME` | `CRUD /db/TDME` | Compressive strength | `Assign` |
| `EDMP` | `CRUD /db/EDMP` | Change property | `Assign` |
| `TMAT` | `CRUD /db/TMAT` | Time-dependent material link | `Assign` |
| `EPMT` | `CRUD /db/EPMT` | Plastic material | `Assign` |
| `EPMT-M1` | `CRUD /db/EPMT-M1` | Hyper-S plastic material | `Assign` |
| `SECT` | `CRUD /db/SECT` | Section properties | `Assign` |
| `THIK` | `CRUD /db/THIK` | Thickness | `Assign` |
| `TSGR` | `CRUD /db/TSGR` | Tapered group | `Assign` |
| `SECF` | `CRUD /db/SECF` | Section manager stiffness | `Assign` |
| `RPSC` | `CRUD /db/RPSC` | Section reinforcements | `Assign` |
| `STRPSSM` | `CRUD /db/STRPSSM` | Stress points | `Assign` |
| `PSSF` | `CRUD /db/PSSF` | Plate stiffness scale factor | `Assign` |
| `VBEM` | `CRUD /db/VBEM` | Virtual beam | `Assign` |
| `VSEC` | `CRUD /db/VSEC` | Virtual section | `Assign` |
| `EWSF` | `CRUD /db/EWSF` | Effective width scale factor | `Assign` |
| `IEHC` | `CRUD /db/IEHC` | Inelastic hinge control | `Assign` |
| `IEHG` | `CRUD /db/IEHG` | Inelastic hinge assignment | `Assign` |
| `IEHG-BEAM-M1` | `CRUD /db/IEHG-BEAM-M1` | Hyper-S beam hinge | `Assign` |
| `IEHG-TRUSS-M1` | `CRUD /db/IEHG-TRUSS-M1` | Hyper-S truss hinge | `Assign` |
| `IEHG-GL-M1` | `CRUD /db/IEHG-GL-M1` | Hyper-S general link hinge | `Assign` |
| `IEHG-PSS-M1` | `CRUD /db/IEHG-PSS-M1` | Hyper-S point spring hinge | `Assign` |
| `FIMP` | `CRUD /db/FIMP` | Inelastic material | `Assign` |
| `FIBR` | `CRUD /db/FIBR` | Fiber division | `Assign` |
| `GRDP` | `CRUD /db/GRDP` | Group damping | `Assign` |
| `ESSF` | `CRUD /db/ESSF` | Element stiffness scale factor | `Assign` |
| `MATD` | `CRUD /db/MATD` | Modify concrete materials | `Assign` |

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
https://github.com/Dennis5882/MIDAS-API/blob/main/docs/manual/04_DB_Properties.md
```

正式实现时，字段级 JSON Schema、每一个 endpoint 的 Specifications、官方 Request/Response 及 Python Example 应从该二级页同步到 `registry/`，不要人工猜字段。
