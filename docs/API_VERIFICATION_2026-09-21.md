# MIDAS NX Open API — 实机复核报告

- **日期**：2026-09-21
- **被测实例**：MIDAS Gen NX V9.8.0，`http://localhost:3030/gen`（MAPI-Key 有效）
- **复核对象**：`registry/registry.json`（595 条逻辑端点）对拍
  - 官方源镜像 `docs/manual/`（pinned commit `e64a682`）
  - 本地 v2 章节 `api_chapters/`
  - v3 官方源审计 `MIDAS_MCP_Connector_Development_Pack_v3_official_source`
- **方法**：`build/verify_api.py`（逐端点逐方法空体探针 + `/info/db/<X>` schema 自省）、`build/verify_live.py`（GET 全量探针）、`tests/live_workflow.py`（端到端建模→分析→读数）

> 原则：**先验证有问题，再修，再记录**。本报告只收录已复现的现象；未能复现的推测一律不写。

---

## 1. 结论摘要

| 复核项 | 规模 | 结果 |
|---|---|---|
| DB 端点方法矩阵 | 231 | **0 处不符**（修正 1 处后） |
| OPE/VIEW/DESIGN 方法矩阵 | 148 | **0 处不符**（修正 1 处后） |
| 服务端 schema vs 文档字段名 | 24 | **0 处不符**（完全一致） |
| 本 build 未提供的端点 | 38 | 已保留并逐条标注产品归属，**未删除** |
| 端到端数值正确性 | 1 组 | 与解析解**精确吻合** |

---

## 2. 已复现并修复的问题

### 2.1 `DELETE` 对不存在的 id 返回 200（静默假成功）

```
DELETE /db/STLD/900   -> 200 {"STLD":{"31":{...}}}   # 实际记录 id 是 31，900 不存在
```
STLD 的 id 由 MIDAS 自行分配，删除一个不存在的 id 得到的是 **HTTP 200**，而非 404/400。仅凭状态码会把"什么都没删"报告成成功。

**修复**：`dispatch.tool_db_delete` 删除后**回读校验**——GET 该 id，仅当 400/`Not Found Key` 才计入 `deleted`；仍在则报 `MIDAS answered 200 to DELETE but the record is still present.`；端点不支持回读时记入 `unverified`。

### 2.2 多目标删除只删了第一个（连接器自身缺陷）

```
target_ids: ["710001","710002"]  ->  只有 710001 被删，710002 静默保留
```
旧实现只取 `ids[0]` 拼路径。**修复**：逐个删除并汇总 `deleted` / `failed`。

> 这条与 2.1 叠加曾造成误导性排障：删除"成功"后重建同名记录报 `Key Already Exist`。

### 2.3 `/doc/EXPORT` 等文件类命令要**裸字符串** Argument

```
{"Argument": {"EXPORT_PATH": "C:\\...\\a.json"}}  -> 200 {"message":"MIDAS GEN NX path is wrong (the file can't open)"}
{"Argument": "C:\\...\\a.json"}                   -> 200 {"message":"MIDAS GEN NX command complete"}   # 文件已写出
```
对象形式被拒却仍返回 **200**，属"2xx 错误体"类。

**修复**：对 `OPEN/SAVEAS/IMPORT/IMPORTMXT/EXPORT/EXPORTMXT` 自动解包 `EXPORT_PATH/FILE_PATH/EXPORT_FILE/PATH` 为字符串并转反斜杠；`is_error_body` 增加 `path is wrong`、`can't open`、`Analysis is not allowed`、`no analysis result` 四个标记。

### 2.4 文档少写的方法（实测可用但文档未列）

| 端点 | 文档 | 实测 | 处置 |
|---|---|---|---|
| `DB:REBC` | POST-only（`24_DB_Design.md` 第 40 行明确警告） | **GET 也返回 200** | 注册表改为 `POST,GET` |
| `DESIGN:SRC:AIK-SRC2K:DSRC` | PUT、DELETE | **GET 也返回 200**（`{"DSRC":{}}`） | 注册表改为 `GET,PUT,DELETE` |

若照文档做守卫，这两个"其实能读"的调用会被错误拒绝，故以实测为准并在注册表 note 中留证。

### 2.5 `There is no valid story information` 被当成硬错误

`/ope/STORYPROP`（POST）在无楼层时返回 `{"error":{"message":"There is no valid story information."}}`。这是**合法的空状态**，不是失败。

**修复**：`normalize.is_soft_empty` + 返回 `soft_empty: true` 的成功信封，并附提示（`STORYPROP` 是正确拼写，`STORPROP` 是旧文档写法；`/db/STOR` 在本 build 是空操作 stub）。

---

## 3. 保留并标注：本 build 未提供的端点（不删除）

按"可能属于其他软件（MIDAS CIVIL NX / Civil Designer）"的前提，**38 个端点全部保留**，`variant` 字段逐条标注：

| variant | 数量 | 说明 |
|---|---|---|
| `Hyper-S-only` | 21 | 全部 `-M1` 后缀（`EIGV-M1`、`MATL-M1`、`ACTL-M1` …），Hyper-S(MEC) 求解器专用 |
| `other-product` | 17 | 归属 Civil NX / 设计模块（见下表） |
| `JP-only` | 1 | `DB:GALD`（Civil NX 日本版） |

`other-product` 明细：

| 端点 | 归属 | 端点 | 归属 |
|---|---|---|---|
| `DB:CAMB` | Civil NX — FCM 预拱度 | `DB:WVLD` | Civil NX — 波浪荷载 |
| `DB:CMCS` | Civil NX — 施工阶段预拱度 | `DB:DYLA` | Civil NX — 铁路动力允许值 |
| `DB:GCMB` | Civil NX — 通用预拱度 | `DB:DYFG` | Civil NX — 铁路动力系数 |
| `DB:GSBG` | Civil NX — 桥梁梁格图 | `DB:DYNF` | Civil NX — 单元铁路动力系数 |
| `DB:SPAN` | Civil NX — 跨径信息 | `DB:CJFG` | Civil NX — 并发节点力组 |
| `DB:PLCB` | Civil NX — 组合前截面 | `DB:CRGR` | Civil NX — 并发反力组 |
| `DB:RCHK` | 设计/校核模块 | `OPE:GSBG` | Civil NX — 桥格图生成 |
| `DESIGN:SRC:AIK-SRC2K:OCHECK` | 设计模块 — SRC 超强校核 | `DB:EWSF` / `DB:STRPSSM` | 未归类 |

每条带两行 note：`HTTP 404 on the live Gen NX probe (…)` + `belongs to … Kept in the registry - do not remove.`

---

## 4. 端到端数值复核（解析解对拍）

`tests/live_workflow.py` 在**空文档**上从零构建并自清理：材料(P_TYPE=2) → H 型截面 → 节点 → 单元 → 支座 → 工况 → 节点荷载 → `ANAL` → 读结果 → 截图。

模型：悬臂，L=5 m，P=10 kN（FZ），H500×200×10×16，E=205 GPa，单位 KN/M。

| 量 | 解析解 | 实测 | 偏差 |
|---|---|---|---|
| 端部位移 δ=PL³/3EI | 0.004416 m | **−0.004415 m** | 0.02% |
| 根部弯矩 M=P·L | 50.0 kN·m | **−50.000** | 0 |
| 竖向反力 | 10.0 kN | **10.000** | 0 |

> 早期一次同项测试得到 0.05 kN·m，原因是该模型单位系统为 **mm**（`UNIT.DIST` 读回 `MM`）；改为显式 KN/M 后完全吻合。**读数前先确认 `UNIT`。**

---

## 5. 明确澄清：这两个不是文档缺陷

复核中发现两处**初判为文档问题、实为自身错误**，特此更正，避免污染后续判断：

1. **`/db/CNLD` 字段名**：文档 `06_DB_Static_Loads.md` 第 222 行起**明确写明** `FX/FY/FZ/MX/MY/MZ`，与 `GET /info/db/CNLD` 一致。此前误用 BMLD 的 `CMD/FV` 向量是**本连接器实现的错误**（已加注册表 note 与知识库条目，防止再犯），**非文档错误**。
2. **`/ope/STORYPROP` vs `STORPROP`**：官方镜像与 v3 审计**一致**指向 `STORYPROP`；实测 POST 有效。旧写法 `STORPROP` 才是不存在的一方。

---

## 6. 复核工具（可重复执行）

```bash
# 逐端点逐方法空体探针（默认不探 DELETE；--probe-delete 用不存在的 id 探）
MIDAS_MAPI_KEY=... python build/verify_api.py --namespace db --schemas
MIDAS_MAPI_KEY=... python build/verify_api.py --namespace ope view design

# GET 全量探针（产出 live_probe.json，被注册表构建回读）
MIDAS_MAPI_KEY=... python build/verify_live.py

# 重建注册表（会合并上述两份探针结果、产品归属与方法修正）
python build/build_registry.py

# 端到端（会真的跑 ANAL；自建自清）
MIDAS_MAPI_KEY=... python tests/live_workflow.py
```

产物：`registry/api_verify.json`、`registry/live_probe.json`、`registry/build_report.json`、`registry/error_shapes.json`。

---

## 8. 遗留项复核（同一天追加）

### 8.1 `/info/db` 覆盖规律 — 实为 195/231

此前报告"仅 24/231 有 schema"是**提取 bug**（`request()` 只读 400 字节，多数 schema 被截断）。修正后：

- **`/info/db/<NAME>` 覆盖所有在服务的 db 端点（195/231）**；
- 无 `/info` 的 36 个 == 全部标记为"本 build 不提供"的端点 —— 二者完全相关；
- **顶层字段对拍 50 个有文档的端点：15 处差异，逐条实测后归类如下。**

**已实测澄清的差异：**

| 端点 | 结论 | 证据 |
|---|---|---|
| `DB:ELEM.W_CON` | **文档正确**，服务端 schema 未列出但实测接受 | A-B 对照：加 `W_CON` 照常 201 |
| `DB:SBDO` | 文档字段名 `MEMB_TYPE_CIVIL/STR_UCS` 与服务端 `MEMBER_TYPE/…` 不符 | 两种写法均实测 `Wrong Field`（需完整 payload 复测） |
| `DB:LCOM-GEN/CONC/SRC/STEEL/SEISMIC/STLCOMP` | 服务端多 `bES/iSERV_TYPE/nSEISTYPE`（文档未列，实测接受） | 加字段照常 201 并回读 |
| `DB:STOR` | **更正**：`STORY_AREA_ITEMS` 为可选第 16 字段 | 15 字段 + 它照常 201 |
| `DB:PJCF/TDME/TDMT/TDMF/THIK/EPMT` | 服务端附加只读/管理字段（`CREATED/DIR/…`），不影响写入 | GET 正常 |

**关键更正（推翻此前报告）：**
- **`/db/STOR` 不是空操作 stub** —— 15 字段给全即成功（此前只给 2 个字段）。该笔记已改。
- 有楼层后 `/ope/STORYPROP` 返回真实 Storey 结果（Weight/Elev./Loaded H/Bx/By）。

### 8.2 错误体分类器：从白名单改为结构化判定

`build/fuzz_error_shapes.py` 对 60 个端点 × 2 种畸形载荷（未知字段名 / 类型错误）扫描：

- 120 次探针：95×400、24×404、**1×201**；
- 那 1 次 201 是 `POST /db/NODE` 带未知字段名 —— **静默创建空节点**（`{"NODE":{"995001":{}}}`），同一 typo 在别处报 `Wrong Field`。已写入注册表 note（"读回校验"）；
- 分类器旧白名单在这语料上 **0 漏判**，但纯白名单对"从未见过的新措辞"必然漏。

**改为结构化判定**（`normalize.is_error_body`）：
1. 顶层 `error` 对象 → 拒绝；
2. 非空 `message` 且非完成语（`command complete` 等）→ 拒绝；
3. 其余回退到白名单。

验证：14 个已知用例全过，含 `[错误] 材料 995001 不存在。`（中文裸串）与"全新措辞"用例。

### 8.3 危险删除语义（LCOM-GEN）

**实测确认**：`DELETE /db/LCOM-GEN/<id>` → 400 `Unknown Error`；而 `DELETE /db/LCOM-GEN` 带 `{"Assign":{"2":{}}}` → **200 并清空整个集合**（3 条组合全没，无论 body 写的哪个 id）。

已写入注册表 note + 知识库 + 删除测试（连接器只走路径式 + 回读校验）。

### 8.4 EWSF / STRPSSM 归属明确

- `DB:EWSF` = Effective Width Scale Factor（`04_DB_Properties.md` §21）；
- `DB:STRPSSM` = Section Manager - Stress Points（§17）。

两者**有文档、本 build 不提供**，不再是"未归类"。

### 8.5 复核后最终状态

- 离线 52 测试 + 实时 7 测试全绿；
- 模型清空为全空（无残留）；
- `build/verify_api.py` 改为**合并写入**（按命名空间多次运行不再互相覆盖）。

---
