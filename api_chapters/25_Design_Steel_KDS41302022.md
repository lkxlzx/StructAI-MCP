# Steel Design KDS 41 30:2022

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
| `DSTL` | `GET/PUT/DELETE /DESIGN/STEEL/DSTL` | Design code selector | `Assign` |
| `DCO` | `GET/PUT/DELETE .../DCO` | Design code option | `Assign` |
| `DCTL` | `GET/PUT/DELETE .../DCTL` | Definition of frame | `Assign` |
| `LLRF` | `GET/PUT/DELETE .../LLRF` | Live load reduction | `Assign` |
| `LCTB` | `GET/DELETE .../LCTB` | Nonlinear load contribution | `Assign` |
| `SRDF` | `GET/PUT/DELETE .../SRDF` | Strength reduction factors | `Assign` |
| `SERV` | `POST/GET/PUT/DELETE .../SERV` | Serviceability | `Assign` |
| `EQCT` | `POST/GET/PUT/DELETE .../EQCT` | Seismic combination type | `Assign` |
| `ULCT` | `POST/GET/PUT/DELETE .../ULCT` | Underground combination type | `Assign` |
| `SUEQ` | `POST/GET/PUT/DELETE .../SUEQ` | Earthquake scale-up | `Assign` |
| `CRCM` | `POST/GET/PUT/DELETE .../CRCM` | Circular combined ratio | `Assign` |
| `HCBM` | `POST/GET/PUT/DELETE .../HCBM` | Haunched beam | `Assign` |
| `LENG` | `POST/GET/PUT/DELETE .../LENG` | Unbraced length | `Assign` |
| `KFAC` | `POST/GET/PUT/DELETE .../KFAC` | Effective length K | `Assign` |
| `LTSR` | `POST/GET/PUT/DELETE .../LTSR` | Slenderness ratio | `Assign` |
| `CMFT` | `POST/GET/PUT/DELETE .../CMFT` | Moment correction | `Assign` |
| `FMAG` | `POST/GET/PUT/DELETE .../FMAG` | Moment magnifier | `Assign` |
| `CBFT` | `POST/GET/PUT/DELETE .../CBFT` | Bending coefficient | `Assign` |
| `MBTP` | `POST/GET/PUT/DELETE .../MBTP` | Member type | `Assign` |
| `SLRS` | `POST/GET/PUT/DELETE .../SLRS` | Seismic resisting system | `Assign` |
| `MLLR` | `POST/GET/PUT/DELETE .../MLLR` | Live load reduction modify | `Assign` |
| `MEMB` | `GET/PUT/DELETE .../MEMB` | Member assignment | `Assign` |
| `SMODI` | `GET/PUT/DELETE .../SMODI` | Steel material modify | `Assign` |
| `CODE-ANAL` | `POST .../CODE-ANAL` | Steel code check | `Argument` |
| `CODE-TABLE` | `POST .../CODE-TABLE` | Steel code table | `Argument` |
| `CODE-REPORT` | `POST .../CODE-REPORT` | Steel code report | `Argument` |
| `DREULT` | `POST .../DREULT` | Steel design result image | `Argument` |
| `TABLE` | `POST .../TABLE` | Steel member design forces | `TABLE_TYPE` |

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

### DSTL

```json
{
  "Assign": {
    "1": {
      "DGNCODE": "KDS 41 30 : 2022"
    }
  }
}
```

### CODE-ANAL

```json
{
  "Argument": {}
}
```

### TABLE

```json
{
  "Argument": {
    "TABLE_TYPE": "STEELMEMBERDESIGNFORCES"
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
https://github.com/Dennis5882/MIDAS-API/blob/main/docs/manual/25_Design_Steel_KDS41302022.md
```

正式实现时，字段级 JSON Schema、每一个 endpoint 的 Specifications、官方 Request/Response 及 Python Example 应从该二级页同步到 `registry/`，不要人工猜字段。
