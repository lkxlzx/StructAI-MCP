# RC Design KDS 41 20:2022

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
| `DRC` | `GET/PUT/DELETE /DESIGN/RC/DRC` | Design code selector | `Assign` |
| `DCO` | `GET/PUT/DELETE .../DCO` | Design code option | `Assign` |
| `DCTL` | `GET/PUT/DELETE .../DCTL` | Definition of frame | `Assign` |
| `LLRF` | `GET/PUT/DELETE .../LLRF` | Live load reduction | `Assign` |
| `LCTB` | `GET/DELETE .../LCTB` | Nonlinear load contribution | `Assign` |
| `SRDF` | `GET/PUT/DELETE .../SRDF` | Strength reduction | `Assign` |
| `EQCT` | `POST/GET/PUT/DELETE .../EQCT` | Seismic combination | `Assign` |
| `ULCT` | `POST/GET/PUT/DELETE .../ULCT` | Underground combination | `Assign` |
| `SUEQ` | `POST/GET/PUT/DELETE .../SUEQ` | Earthquake scale-up | `Assign` |
| `SDGN` | `POST/GET/PUT/DELETE .../SDGN` | Seismic design type | `Assign` |
| `SCOL` | `POST/GET/PUT/DELETE .../SCOL` | Seismic column type | `Assign` |
| `MBTP` | `POST/GET/PUT/DELETE .../MBTP` | Member type | `Assign` |
| `MEMB` | `GET/PUT/DELETE .../MEMB` | Member assignment | `Assign` |
| `MATD` | `GET/PUT/DELETE .../MATD` | Concrete material | `Assign` |
| `LENG` | `POST/GET/PUT/DELETE .../LENG` | Unbraced length | `Assign` |
| `KFAC` | `POST/GET/PUT/DELETE .../KFAC` | Effective length | `Assign` |
| `CMFT` | `POST/GET/PUT/DELETE .../CMFT` | Moment correction | `Assign` |
| `FMAG` | `POST/GET/PUT/DELETE .../FMAG` | Moment magnifier | `Assign` |
| `MLLR` | `POST/GET/PUT/DELETE .../MLLR` | Live load reduction | `Assign` |
| `HCBM` | `POST/GET/PUT/DELETE .../HCBM` | Haunched beam | `Assign` |
| `MRFT` | `POST/GET/PUT/DELETE .../MRFT` | Moment redistribution | `Assign` |
| `TRFT` | `POST/GET/PUT/DELETE .../TRFT` | Torsion reduction | `Assign` |
| `MCMB` | `POST/GET/PUT/DELETE .../MCMB` | Beam moment method | `Assign` |
| `DFBA` | `POST/GET/PUT/DELETE .../DFBA` | Beam design force | `Assign` |
| `PMDM` | `POST/GET/DELETE/PUT .../PMDM` | P-M calculation method | `Assign` |
| `WMAK` | `POST/GET/PUT/DELETE .../WMAK` | Wall mark | `Assign` |
| `BEMW` | `POST/GET/PUT/DELETE .../BEMW` | Boundary element method | `Assign` |
| `REXC` | `POST/GET/PUT/DELETE .../REXC` | Rebar exposure | `Assign` |
| `LMRR` | `GET/PUT/DELETE .../LMRR` | Max rebar ratio | `Assign` |
| `DCRM-*` | `POST/GET/PUT/DELETE .../DCRM-*` | Member rebar criteria | `Assign` |
| `DCRE` | `POST/GET/PUT/DELETE .../DCRE` | Rebar design criteria | `Assign` |
| `DCREM` | `POST/GET/PUT/DELETE .../DCREM` | Joint beam rebar equalization | `Assign` |
| `REBB` | `POST/GET/PUT/DELETE .../REBB` | Beam rebar | `Assign` |
| `REBC` | `POST/GET/PUT/DELETE .../REBC` | Column rebar | `Assign` |
| `REBW` | `POST/PUT/DELETE/GET .../REBW` | Wall rebar | `Assign` |
| `REBR` | `POST/GET/PUT/DELETE .../REBR` | Brace rebar | `Assign` |
| `BD-ANAL` | `POST .../BD-ANAL` | RC beam design | `Argument` |
| `BD-TABLE` | `POST .../BD-TABLE` | RC beam design table | `Argument` |
| `BD-REPORT` | `POST .../BD-REPORT` | RC beam report | `Argument` |
| `CD-ANAL` | `POST .../CD-ANAL` | RC column design | `Argument` |
| `CD-TABLE` | `POST .../CD-TABLE` | RC column table | `Argument` |
| `CD-REPORT` | `POST .../CD-REPORT` | RC column report | `Argument` |
| `BRD-ANAL` | `POST .../BRD-ANAL` | RC brace design | `Argument` |
| `BRD-TABLE` | `POST .../BRD-TABLE` | RC brace table | `Argument` |
| `BRD-REPORT` | `POST .../BRD-REPORT` | RC brace report | `Argument` |
| `WD-ANAL` | `POST .../WD-ANAL` | RC wall design | `Argument` |
| `WD-TABLE` | `POST .../WD-TABLE` | RC wall table | `Argument` |
| `WD-REPORT` | `POST .../WD-REPORT` | RC wall report | `Argument` |
| `HCD-ANAL` | `POST .../HCD-ANAL` | RC haunched beam design | `Argument` |
| `HCD-TABLE` | `POST .../HCD-TABLE` | RC haunched table | `Argument` |
| `HCD-REPORT` | `POST .../HCD-REPORT` | RC haunched report | `Argument` |
| `BC-ANAL` | `POST .../BC-ANAL` | RC beam check | `Argument` |
| `BC-TABLE` | `POST .../BC-TABLE` | RC beam check table | `Argument` |
| `BC-REPORT` | `POST .../BC-REPORT` | RC beam check report | `Argument` |
| `CC-ANAL` | `POST .../CC-ANAL` | RC column check | `Argument` |
| `CC-TABLE` | `POST .../CC-TABLE` | RC column check table | `Argument` |
| `CC-REPORT` | `POST .../CC-REPORT` | RC column check report | `Argument` |
| `BRC-ANAL` | `POST .../BRC-ANAL` | RC brace check | `Argument` |
| `BRC-TABLE` | `POST .../BRC-TABLE` | RC brace check table | `Argument` |
| `BRC-REPORT` | `POST .../BRC-REPORT` | RC brace check report | `Argument` |
| `WC-ANAL` | `POST .../WC-ANAL` | RC wall check | `Argument` |
| `WC-TABLE` | `POST .../WC-TABLE` | RC wall check table | `Argument` |
| `WC-REPORT` | `POST .../WC-REPORT` | RC wall check report | `Argument` |
| `CDESIGN` | `POST .../CDESIGN` | RC overall design result | `Argument` |
| `TABLE:Column` | `POST .../TABLE` | Column design forces | `TABLE_TYPE` |
| `TABLE:Brace` | `POST .../TABLE` | Brace design forces | `TABLE_TYPE` |
| `TABLE:Beam` | `POST .../TABLE` | Beam design forces | `TABLE_TYPE` |

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

### DRC

```json
{
  "Assign": {
    "1": {
      "DGNCODE": "KDS 41 20 : 2022"
    }
  }
}
```

### DCO

```json
{
  "Assign": {
    "1": {
      "DESIGN_CD": "KDS 41 20 : 2022",
      "SEISMIC_PROV": false
    }
  }
}
```

### BD-ANAL

```json
{
  "Argument": {}
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
https://github.com/Dennis5882/MIDAS-API/blob/main/docs/manual/26_Design_RC_KDS41202022.md
```

正式实现时，字段级 JSON Schema、每一个 endpoint 的 Specifications、官方 Request/Response 及 Python Example 应从该二级页同步到 `registry/`，不要人工猜字段。
