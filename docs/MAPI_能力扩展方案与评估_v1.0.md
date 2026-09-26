# 用 `G:\MAPI` 拓展 StructAI MCP 能力 —— 方案与评估报告

> 版本 v1.0 · 结论先行 · 所有数字均为实测

---

## 摘要

| 维度 | 结论 |
|---|---|
| **可行性** | **高**。手册结构清晰，目标表 `tool_interfaces` 已存在且列完全够用 |
| **数据库** | **不是障碍**。扩展后约 1,400 行 + 最多 40 MB schema，SQLite 余量约 1600× |
| **真正的障碍** | **三个，全是架构问题**（见下） |
| **建议** | 分四阶段推进，**先做阶段 1（抽取管线）**——它不依赖任何未定决策 |

**三个架构障碍：**

1. **能力表是手写的 Python 字面量**（`app/mcp/capabilities.py` 的 `_TABLE`）。32 个端点可以手写，683 个不行。
2. **LLM 面对的 resource 词表会从 21 涨到约 600**，而它必须从中选一个。
3. **并非所有端点都能塞进现有 4 工具的 `(action, resource)` 模型**，`DESIGN/*` 族是典型。

---

## 一、现状盘点

### 1.1 两边各有什么

| | StructAI MCP（现在） | `G:\MAPI`（可提供） |
|---|---|---|
| 形态 | 可运行平台 | **文档工程**（4 本 markdown + 生成脚本） |
| 端点覆盖 | **32 个唯一端点** / 162 个能力行 | **1,373 个条目 / 约 683 个唯一 URI** |
| 产品 | Gen + Civil | **Gen 881 / Civil NX 454 / Civil Designer 38** |
| Schema | **0 行有 `request_schema_json`** | 手册内 **626 处 JSON Schema**、2,535 个 `json` 围栏 |
| 手册体量 | — | **16.9 MB**（Gen 11.8 / Civil NX 4.9 / Designer 0.2） |

### 1.2 端点按路径族的分布

| 族 | Gen | Civil NX | Designer | 说明 |
|---|---|---|---|---|
| `db` | 468 | 226 | 13 | 模型数据 CRUD |
| `post` | 163 | 151 | 1 | 结果表 |
| **`design`** | **146** | — | — | 设计/验算（KDS、AASHTO…） |
| `view` | 42 | 47 | 4 | 视图 |
| `ope` / `oprt` | 23 | 20 | 6 | 操作 |
| `doc` | 22 | 10 | 14 | 文档 |
| `rating` | 4 | — | — | 评定 |
| *(uri 缺失)* | 13 | — | — | 需人工补 |

---

## 二、可行性评估（逐项）

| # | 需要什么 | 手册里有吗 | 结论 |
|---|---|---|---|
| 1 | 端点清单（uri + methods） | ✅ `inventory.json` 已有 1,373 条 | **直接可用** |
| 2 | `interface_code` | ⚠️ `inventory.json` 的 `code` **大量为 null** | 需生成（见 §3.1） |
| 3 | `request_schema_json` | ✅ 626 处 JSON Schema + 2,535 个 json 围栏 | **可抽取** |
| 4 | `method` | ✅ `methods[]` 数组 | 直接可用（一 URI 多行） |
| 5 | `operation` | ❌ 无结构化字段 | 需按 method + 语义派生 |
| 6 | `request_wrapper` | ❌ 无 | 需按**族规则**派生（`/db/*`→`Assign`，`/doc/*`→`Argument`） |
| 7 | `response_root_key` | ❌ 无 | 同上 |
| 8 | 数据库容量 | — | ✅ **无问题**（余量 1600×） |
| 9 | **LLM 检索** | ❌ | ❗ **真问题**，见 §3.4 |

### 2.1 手册的自述结构（抽取依据）

Gen 手册前言明确写道：

> 接口定义分为三部分……**中文部分**（`## JSON数据手册`）是接口定义的**主干**，给出 `接口代码`、`Input URI`、`Active Methods`、`Input JSON format` 与请求体示例。

即每个接口有**固定五段结构**，实测计数：`Input URI` **861** 处、`JSON Schema` **626** 处。**这是可机械抽取的。**

---

## 三、方案

### 阶段 1：抽取管线（MAPI → 结构化清单）**← 建议先做这一步**

**产物**：`tools/extract_interfaces.py` → `interfaces.json`（约 1,400 行 × 12 字段）

**步骤**：

| 步 | 输入 | 处理 | 输出字段 |
|---|---|---|---|
| 1 | `inventory.json` | 作为**骨架**（uri + methods 已有） | `endpoint`, `method` |
| 2 | 手册正文 | 定位 `接口代码` | `interface_code` |
| 3 | 手册正文 | 抽 `Input JSON format` 的 json 围栏 | `request_schema_json` |
| 4 | 路径 + method | 派生 | `operation`, `resource` |
| 5 | **族规则表** | `/db/*`→`Assign`；`/doc/*`→`Argument`；`/post/TABLE`→调用方 `TABLE_NAME` | `request_wrapper`, `response_root_key` |
| 6 | 实机 | 与 `/info/db/*` 对账 | 校验标记 |

**关于第 4 步（`interface_code` 生成）**——`inventory.json` 里大量为 null，建议规则：

```
{product}.{family}.{path_tail}         例：gen.design.rc.kds4120.rebb
```
规范化：小写、`-`→`_`、`/`→`.`，并保证 `(adapter_code, interface_code)` 唯一（裁决 B-3）。

**关于第 5 步**——`request_wrapper` / `response_root_key` **不是手册里的字段**，而是本项目实机验证得出的族规则（对接规范 §3.1–§3.2）。派生是**确定性**的，不依赖手册。

**验收**：抽取结果与实机 `/info/db/*` 对账，**不一致的以实机为准**（对接规范 §3.5 第 9 条）。

---

### 阶段 2：能力表改为数据库驱动 **← 架构关键**

**现状**：`capability_table()` 返回模块级 `_TABLE`——**import 时构建的手写字典**。

**目标**：改为从 `tool_interfaces` 读取。该表**已经存在**且列完全够用：

```
interface_code · method · endpoint · request_wrapper · response_root_key
operation · resource · request_schema_json · response_schema_json
timeout_seconds · async_supported · metadata_json
唯一约束 (adapter_code, interface_code)   ← 裁决 B-3
外键 → tools.id / adapters.code
```

**但当前没有任何代码读它**——这是规范与实现的偏离：V2.1 §16.1 的设计意图是"权威行在数据库"，而代码把手写字典当权威。

**做法**：
1. 现有 162 行作为**种子**导出，与新行合并
2. `capability_table()` 改为读库 + 进程内缓存
3. 保留手写表作为**测试夹具**（离线测试不依赖数据库）

**风险**：这是**核心路径改动**。现有 387 个测试全部依赖手写表。建议**双轨过渡**：数据库优先、手写表兜底，跑通后再删。

---

### 阶段 3：MCP 工具映射与命名 **← 最难的一步**

**问题**：现在是 `(tool, action, resource)` 三元组，resource 词表 **21 个**：

```
analysis · boundary · capabilities · client · command · element · file ·
group · load · load_case · material · model · node · project · report ·
result · section · server · structure_type · task · unit
```

扩展到 683 个端点后，`db` 族一项就有 707 个条目、`design` 族 146 个。**resource 会涨到约 600**，而 LLM 必须从中选一个。

**具体难点**：`DESIGN/RC/KDS-41-20-2022/REBB` 这样的路径**不是简单名词**，是四级路径。扁平词表装不下。

**三个可选做法**：

| 做法 | 说明 | 代价 |
|---|---|---|
| **A. 分层 resource** | `design.rc.kds4120.rebb`，`midas_query` 支持前缀匹配 | 需改 capability 解析 |
| **B. 保持扁平 + 强制发现** | LLM 必须先 `midas_query target=capabilities action=search` 再调用 | 多一轮交互，但**已有能力**（见下） |
| **C. 按族聚合** | 一个 resource 代表一族（`design_rc`），具体接口用参数指定 | 语义最弱，LLM 易错 |

**好消息**：**发现机制已经存在**——`midas_query` 已有 `capabilities.search` / `list` / `get` / `count`。所以做法 B 的**基础设施是现成的**，只需把新端点灌进去并强化搜索质量。

**建议**：**B 为主 + A 为辅**（对 `design`/`rating` 这类深路径用分层命名，其余保持扁平）。

---

### 阶段 4：检索层 **← 真正的瓶颈**

**问题**：32 个端点时，整张能力表可以塞进 LLM 上下文；**1,373 个条目塞不进去**。

**这是上下文问题，换数据库解决不了。**

**三种检索实现与数据库的关系**：

| 方式 | SQLite | PostgreSQL |
|---|---|---|
| 关键字/全文（标题、路径、描述） | **FTS5**，够用 | `tsvector`+GIN，更强（中文分词、权重） |
| 结构化过滤（method/resource/product） | 普通索引，够用 | 同样够用 |
| **语义检索（向量）** | ❌ 无内建 | ✅ `pgvector` |

**只有第三行是 PostgreSQL 的真正入口。** 建议：**先做前两行**（SQLite 够用），向量检索**等有实测需求再说**。

---

## 四、风险评估

| 风险 | 等级 | 说明与对策 |
|---|---|---|
| **核心路径改动** | 🔴 高 | 阶段 2 触及所有工具调用。**对策**：双轨过渡 + 现有 387 测试作为回归网 |
| **`interface_code` 冲突** | 🟡 中 | 1,373 条生成代码可能撞车（尤其 `post/TABLE` 承载几百张表）。**对策**：唯一约束 + 抽取时检测 |
| **手册质量参差** | 🟡 中 | 13 条 Gen 条目 **uri 为 null**；两处手册字段名错误已知（对接规范 §3.5 第 9 条）。**对策**：以实机 `/info` 为准 |
| **Schema 抽取失败** | 🟡 中 | 626 处 JSON Schema 格式未必统一。**对策**：抽不到就留 null，**不阻塞**（表允许空） |
| **`DESIGN/*` 语义错配** | 🟡 中 | 设计验算不是 CRUD。**对策**：阶段 3 单独设计 |
| **工作量低估** | 🟡 中 | 见 §5 |
| **法律** | 🟢 低 | `MIDAS-API-main` 无 LICENSE（已由你确认接受） |

---

## 五、工作量估算

| 阶段 | 内容 | 估量 | 依赖 |
|---|---|---|---|
| 1 | 抽取管线 | **中**（1 个脚本 + 对账） | 无 —— **可立即开始** |
| 2 | 能力表入库 | **中**（核心路径改动 + 回归） | 阶段 1 |
| 3 | 工具映射与命名 | **大**（需设计决策） | 阶段 2 |
| 4 | 检索层 | **大**（需选型） | 阶段 3 |

**阶段 1 与 2 是确定无疑要做的；阶段 3 需要你参与设计决策；阶段 4 取决于检索选型。**

---

## 六、建议

### 立即做（不依赖任何未定决策）

**阶段 1：抽取管线。** 输入输出都明确，验收标准客观（与实机 `/info` 对账）。做完就能回答"手册里到底能抽出多少可用的接口定义"这个**当前无人知道**的问题。

### 然后做

**阶段 2：能力表入库。** 这是"32 → 683"能否成立的**技术前提**。不做这一步，扩展方案无从落地。

### 需要你决策后再做

- **阶段 3 的命名策略**：分层 vs 扁平 vs 聚合
- **阶段 4 的检索选型**：全文（SQLite 够）vs 语义（那时才考虑 PG）

### 明确不建议

**不要为了这次扩展先迁 PostgreSQL。** 数据量余量 1600×，而真正的瓶颈（LLM 上下文）**换库解决不了**。若将来要 PG，理由会是"我们要做向量检索"，而不是"端点变多了"。

---

## 附：本次评估用到的实测数据

```
inventory.json        0.3 MB   civilnx 454 / designer 38 / gen 881 条
唯一 URI              228 / 37 / 418          合计约 683
手册体量              16.9 MB  Gen 410,728 行 / Civil NX 157,103 行
结构标记              Input URI 861 · JSON Schema 626 · json 围栏 2,535
StructAI 现状         162 能力行 / 32 唯一端点 / 21 个 resource
tool_interfaces       17 列，唯一约束 (adapter_code, interface_code)
SQLite 实测吞吐       3513 写/秒 · 2729 混合读写/秒
扩展后估算            约 1,400 行 · schema 2.7–40 MB · 总计 < 100 MB
```
