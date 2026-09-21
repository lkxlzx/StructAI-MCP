# POST Story Tables

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
| `STORY_DRIFT_X/Y/COMB` | `POST /post/TABLE` | Story drift | `TABLE_TYPE=STORY_DRIFT_*` |
| `STORY_DISPLACEMENT_X/Y/COMB` | `POST /post/TABLE` | Story displacement | `TABLE_TYPE=STORY_DISPLACEMENT_*` |
| `STORY_SHEAR_FOR_RS` | `POST /post/TABLE` | Story shear force RS | `TABLE_TYPE=STORY_SHEAR_FOR_RS` |
| `STORY_SHEAR_FORCE_COEFFICIENT` | `POST /post/TABLE` | Story shear coefficient | `TABLE_TYPE=STORY_SHEAR_FORCE_COEFFICIENT` |
| `STORY_MODE_SHAPE` | `POST /post/TABLE` | Story mode shape | `TABLE_TYPE=STORY_MODE_SHAPE` |
| `STORY_SHEAR_FORCE_RATIO` | `POST /post/TABLE` | Story shear force ratio | `TABLE_TYPE=STORY_SHEAR_FORCE_RATIO` |
| `STORY_ECNTRICITY` | `POST /post/TABLE` | Story eccentricity | `TABLE_TYPE=STORY_ECNTRICITY` |
| `OVERTURNING_MOMENT` | `POST /post/TABLE` | Overturning moment | `TABLE_TYPE=OVERTURNING_MOMENT` |
| `STORY_AXIAL_FORCE_SUM` | `POST /post/TABLE` | Story axial force sum | `TABLE_TYPE=STORY_AXIAL_FORCE_SUM` |
| `STORY_STABILITY_COEFFICIENT_X/Y` | `POST /post/TABLE` | Story stability coefficient | `TABLE_TYPE=STORY_STABILITY_COEFFICIENT_*` |
| `TORSIONAL_IRREGULARITY_X/Y` | `POST /post/TABLE` | Torsional irregularity | `TABLE_TYPE=TORSIONAL_IRREGULARITY_*` |
| `TORSIONAL_AMPLIFICATION_FACTOR_X/Y` | `POST /post/TABLE` | Torsional amplification | `TABLE_TYPE=TORSIONAL_AMPLIFICATION_FACTOR_*` |
| `STIFFNESS_IRREGULARITY_X/Y` | `POST /post/TABLE` | Soft story | `TABLE_TYPE=STIFFNESS_IRREGULARITY_*` |
| `CAPACITY_IRREGULARITY` | `POST /post/TABLE` | Weak story | `TABLE_TYPE=CAPACITY_IRREGULARITY` |
| `CRITERIA_FOR_REGULARITY_IN_PLAN` | `POST /post/TABLE` | Plan regularity | `TABLE_TYPE=CRITERIA_FOR_REGULARITY_IN_PLAN` |
| `ULTIMATE_STORY_SHEAR_FORCE_CHECK` | `POST /post/TABLE` | Ultimate story shear check | `TABLE_TYPE=ULTIMATE_STORY_SHEAR_FORCE_CHECK` |
| `WEIGHT_IRREGULARITY_X/Y` | `POST /post/TABLE` | Weight irregularity | `TABLE_TYPE=WEIGHT_IRREGULARITY_*` |

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

### STORY_DRIFT_COMB

```json
{
  "Argument": {
    "TABLE_TYPE": "STORY_DRIFT_COMB",
    "LOAD_CASE_NAMES": [
      "RX(RS)",
      "RY(RS)"
    ],
    "STYLES": {
      "FORMAT": "Fixed",
      "PLACE": 4
    }
  }
}
```

`ADDITIONAL` 可进一步配置 Method 1/2、Beta、P-Delta vertical load combinations、选定节点垂线等计算方式。


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
https://github.com/Dennis5882/MIDAS-API/blob/main/docs/manual/21_POST_StoryTables.md
```

正式实现时，字段级 JSON Schema、每一个 endpoint 的 Specifications、官方 Request/Response 及 Python Example 应从该二级页同步到 `registry/`，不要人工猜字段。
