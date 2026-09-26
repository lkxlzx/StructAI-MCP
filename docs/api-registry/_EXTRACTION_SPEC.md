# MIDAS API 抽取规范（Extraction Spec）

本文件是**所有抽取子任务的唯一契约**。产出必须逐字遵守，否则合并阶段会失败。

---

## 1. 目的

把 `MIDAS-API-main/docs/manual/*.md`（27 章、约 270 个端点）与插件/示例文档，
转成**机器可读的端点注册表**，用于填充 StructAI 的 `tool_interfaces` / `capabilities` 表，
并作为 Adapter 实现的字段级依据。

---

## 2. 输出位置与命名

```
G:\StructAI MCP\docs\api-registry\part-<分组号>.json
```

分组号由任务下发时指定（例如 `part-01.json`）。**一个子任务只写一个 JSON 文件。**
不要写 markdown 产出（除任务另行要求）。

---

## 3. JSON 结构（严格）

```json
{
  "part": "01",
  "source_files": ["docs/manual/01_DOC.md", "docs/manual/02_DB_Project_Structure.md"],
  "chapters": [
    {
      "chapter": "01",
      "title": "DOC",
      "source": "docs/manual/01_DOC.md",
      "scope_note": "原文开头对本章范围的说明（如「11개」）",
      "endpoints": [
        {
          "endpoint": "/doc/NEW",
          "methods": ["POST"],
          "wrapper": "Argument",
          "response_root_key": null,
          "category": "doc",
          "resource": "project",
          "operations": ["create"],
          "purpose": "New Project — 新建空白工程",
          "product_scope": "both",
          "methods_documented": ["POST"],
          "methods_observed": null,
          "key_fields": [],
          "request_example": "{\"Argument\": {}}",
          "notes": ""
        }
      ]
    }
  ]
}
```

### 字段规则

| 字段 | 规则 |
|---|---|
| `endpoint` | 原样照抄，**保留原始大小写**（如 `/db/NODE`、`/ope/STORY_PARAM`） |
| `methods` | 原文 Methods 行列出的方法；`/doc/*` 一律只有 `POST` |
| `wrapper` | 请求体外层键：`/db/*` 用 `"Assign"`，`/doc/*` 用 `"Argument"`，其他按原文 |
| `response_root_key` | GET 返回的最外层键（通常是大写资源名，如 `"NODE"`）；未知填 `null` |
| `category` | `doc` / `db` / `ope` / `view` / `post` / `design` 之一 |
| `resource` | **单数小写**的领域资源名，用于映射 StructAI 的 MCP resource。取值尽量收敛到：`project` `unit` `structure_type` `group` `node` `element` `material` `section` `thickness` `boundary` `spring` `link` `load` `load_case` `load_combination` `analysis` `result` `design` `view` `tendon` `construction_stage` `moving_load` `dynamic_load` `pushover` `bridge` `misc` |
| `operations` | 从 `["create","read","update","delete","execute"]` 中选；由 methods 推导（POST→create，GET→read，PUT→update，DELETE→delete，`/doc/ANAL`→execute） |
| `product_scope` | `both` / `gen` / `civil`；原文标注仅 GEN 或仅 CIVIL 的照实填，未标注填 `both` |
| `methods_documented` | 原文表格里写的方法（可能有错，照抄） |
| `methods_observed` | **留 `null`**。本仓库的实机观测结论已作废，不引用 |
| `key_fields` | 字段表，见下 |
| `request_example` | 原文 `Request Body` 的 JSON，**压成一行**。过长（>400 字符）则截断并加 `…` |
| `notes` | 原文中的 ⚠️ 注记、版本差异、必填陷阱、GET/PUT-only 限制等 |

### `key_fields` 元素

```json
{ "key": "X", "type": "number", "required": false, "default": "0", "desc": "GLOBAL X-POSITION" }
```

- `key`：原样照抄字段名（含 `iMETHOD`、`T_bLMT`、`bUseMt` 这类大小写混排）
- `type`：`number` / `integer` / `string` / `boolean` / `array` / `object`
- `required`：原文 Required 列为 **Required** 时 `true`，`Optional` 时 `false`
- `default`：原文 Default 列，字符串化；无则 `null`
- `desc`：原文 Description 列（**保留原文语言，不要翻译**）

---

## 4. 深度要求（分两档）

### A 档 —— 逐字段（核心建模与结果章）
`key_fields` 必须覆盖原文 Specifications 表的**每一行**。
适用：01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21。

### B 档 —— 端点级（设计代码与超大结果章）
`key_fields` 可为 `[]`，但每个端点的 `purpose` 必须具体（不能只写"设计"）。
适用：20, 22, 23, 24, 25, 26, 27。

---

## 5. 硬性规则

1. **只记录原文存在的内容。** 不得推测、补全、发明字段或方法。
2. **原文有错也照抄**，把疑问写进 `notes`，不要擅自更正。
3. **不要翻译** `desc`、`purpose` 里的专有名词；可以保留韩文/英文原文。
4. **端点去重**：同一端点在本章内只出现一次。若原文重复定义，合并 `key_fields` 并在 `notes` 说明。
5. **数字键**：`request_example` 里的 `"1"`、`"198"` 等 ID 键照抄。
6. **不要写 markdown 文件**，只写指定的 JSON。
7. **不得调用 shell**（沙箱禁用）。只用 `read` / `write` / `edit` / `glob` / `grep`。
8. 大文件用 `read` 的 `offset`/`limit` **分页读完**，不要只读开头就下结论。
9. 若单文件超过约 400 行，先 `grep -n '^## '` 拿到章节骨架，再逐段读。

---

## 6. 输出前自检

- [ ] JSON 可被 `json.loads` 解析（无尾逗号、无注释）
- [ ] `endpoints` 数量 ≥ 原文 `Table of Contents` 列出的端点数
- [ ] 每个 `endpoint` 都有 `purpose` 和 `methods`
- [ ] A 档任务的 `key_fields` 非空
- [ ] 文件路径与命名完全符合第 2 节
