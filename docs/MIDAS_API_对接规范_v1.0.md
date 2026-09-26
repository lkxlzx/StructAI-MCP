# MIDAS NX Open API 对接规范 v1.0

**文档性质：** 适配层依据（StructAI MCP V2.1 §12–§22 的事实来源）
**依据来源：** `MIDAS-API-main/`（GitHub `Dennis5882/MIDAS-API`，212 文件 / 4.03 MB）
**从属关系：** 本文件是《StructAI 架构边界与融合规范 v1.0（总纲）》的下位文档，
用于**修正**《StructAI MCP V2.1 设计框架规范》中关于 MIDAS 事实的假设。
**冲突优先级：** 本文件在**「MIDAS 是什么样」**这一问题上高于 V2.1；
在**「StructAI 内部如何建模」**上仍以总纲与 V2.1 为准。

---

# 1. 为什么要写这份文件

V2.1 的 §12–§22（Adapter / Capability / Interface）是在**没有接触真实 MIDAS API** 的情况下写的，
其中关于连接方式、认证、端点命名、载荷结构的假设**与事实不符**。本文件逐条给出事实与修正。

---

# 2. 连接与认证

## 2.1 两种接入方式（v1.0.1 订正）

> **订正：** 本规范早期版本写「MIDAS NX Open API **不是本地 REST 服务**，而是云端中继」——
> **这是错的。** MIDAS Gen NX 与 MIDAS Civil NX **都提供本地 REST 接口**。
> 该错误源于只读了仓库 `README.md`（它只描述云端中继），
> 而**实机验证证明本地接口完全可用**（§11：建模 + 分析 + 取结果全程走本地）。

### 方式一：本地接口（同机调用）

```text
[调用方] ──HTTP──▶ http://localhost:3030/{gen|civil}    ← 由 MIDAS 应用进程自己提供
```

| 项 | 值 |
|---|---|
| Base URL | `http://localhost:3030/gen`（Civil 为 `/civil`） |
| 监听进程 | **`GenNX.exe` 自身**（实测 PID 40796，非独立服务） |
| 绑定地址 | **仅 `::1`（IPv6 回环）** |
| 认证头 | `MAPI-Key` |
| 健康检查 | `GET http://localhost:3030/mapikey/verify` |

#### 实测的监听地址（单机单版本的一次观测）

```text
Get-NetTCPConnection -LocalPort 3030
  State   LocalAddress   LocalPort   OwningProcess
  Listen  ::1            3030        40796          ← 仅此一条
```

裸 TCP 连接（不经 HTTP、不经代理、不经 DNS 解析）：

```text
::1:3030          → 连接成功
127.0.0.1:3030    → 拒绝连接
<LAN-IP>:3030     → 拒绝连接
<主机名>:3030     → 拒绝连接
```

> ### ⚠️ 这不是「MIDAS 不支持 IPv4」
>
> 准确的表述是：**它的本地 API 监听器绑定在 IPv6 回环地址 `::1` 上。**
> Windows 对显式绑定的 IPv6 地址默认 `IPV6_V6ONLY=1`，因此 IPv4 回环
> `127.0.0.1` 不会被映射到该监听器。这是**绑定地址的选择，不是协议能力问题**。
>
> 佐证：同机上其他进程正常使用 IPv4（`0.0.0.0:1947`、
> 双栈的 `::` + `0.0.0.0:135` 等），协议栈本身完好。
>
> **本结论仅为单机、单版本、单配置下的一次观测**，以下均**未验证**：
> - 是否随 Gen NX 版本变化
> - 是否可通过产品设置更改监听地址（§10 已登记）
> - MIDAS Civil NX 是否相同
>
> 因此**不得**据此推断 MIDAS 的协议能力或写死任何 IPv4/IPv6 假设。

**实践建议：配置里写 `localhost`，不要写 `127.0.0.1`。**
本机 `getaddrinfo("localhost")` 的顺序是 `[AF_INET6 ::1, AF_INET 127.0.0.1]`，
`localhost` 会先命中 `::1`，因此无论绑定的是 `::1` 还是 `127.0.0.1` 都能连通，
是最稳的写法。

### 方式二：云端中继（跨机调用）

```text
[调用方] ──REST(HTTPS)──▶ [MIDAS 云: moa-engineers.midasit.com] ──WebSocket──▶ [MIDAS Gen/Civil NX]
    ▲                                                                                │
    └────────────────────────── JSON 结果 ◀──────────────────────────────────────────┘
```

| 项 | 值 |
|---|---|
| Base URL（Gen） | `https://moa-engineers.midasit.com:443/gen` |
| Base URL（Civil） | `https://moa-engineers.midasit.com:443/civil` |
| 网络要求 | `https` + `wss`，端口 `443`，MIDAS 公网 NAT `121.157.60.1/32` |
| SSL 拦截 | 企业代理若做 SSL Inspection，必须排除该域名，否则连接被拒 |

### 为什么两者都存在

**因为本地接口只绑回环。** 跨机调用没有别的路，只能走云端中继——
**中继不是多余的，它正是为「调用方不在 MIDAS 那台机器上」而存在的。**

| 场景 | 该用哪种 |
|---|---|
| 脚本与 MIDAS 同机 | **本地接口** —— 零外部依赖、无防火墙/SSL 问题、延迟最低 |
| 调用方在另一台机器 | **云端中继**，或 §2.6 的方案乙 |
| 局域网多部门平台 | **见 §2.6（关键决策）** |

**共同前提：MIDAS Gen/Civil NX 必须处于运行状态。** 产品没开，两种方式都失败。

### 认证头（两种方式相同）

| 项 | 值 |
|---|---|
| 认证头 | **`MAPI-Key: <key>`** —— 明确**不是** `Authorization: Bearer` |
| Content-Type | `application/json` |
| MAPI-Key 来源 | 在 MIDAS Gen/Civil NX **应用内**（Open API / Apps 菜单）签发，可随时重发 |

## 2.2 连接健康检查

```http
# 本地接口（调用方与 MIDAS 同机）
GET http://localhost:3030/mapikey/verify

# 云端中继（调用方在另一台机器）
GET https://moa-engineers.midasit.com:443/mapikey/verify

MAPI-Key: <key>
```

注意：路径**不含** `/gen` 或 `/civil`（产品路径要去掉）。

```json
{
  "user": "User_ID",
  "program": "civil",
  "connectionID": "Connection_ID",
  "keyVerified": true,
  "status": "connected"
}
```

| 键 | 含义 |
|---|---|
| `status` | 产品-服务器连接状态 |
| `keyVerified` | MAPI-Key 是否有效 |
| `user` | 产品内登录的用户 ID |
| `program` | 已连接产品（`gen` / `civil`） |
| `connectionID` | 标识客户端的易失 ID |

## 2.3 错误码（连接层）

| HTTP | 原因 | 处置 |
|---|---|---|
| 401 | Key 错误/缺失 | 校验 `MAPI-Key` 头 |
| 403 | 权限不足 | 校验 Key 权限/产品授权 |
| 连接失败/超时 | **本地产品未运行** | 提示用户启动 MIDAS |
| 404 | Base URL 错 | 校验 `/gen` 或 `/civil` 路径 |

## 2.4 对 V2.1 的修正

| V2.1 原文 | 修正 |
|---|---|
| `midas_clients.api_url` 示例 `http://192.168.1.100:8080` | 语义改为**含产品段的完整 Base URL**：本地为 `http://localhost:3030/gen`，云端中继为 `https://moa-engineers.midasit.com:443/gen`（§2.1）。**无需改 DDL**——产品段由 `software` / `adapter_code` 决定并体现在 URL 中 |
| `api_key_encrypted` + `access_token_encrypted` | MIDAS NX **只有 MAPI-Key**，无 token 概念。`access_token_encrypted` 保留给未来非 MIDAS 软件（CSI/ANSYS），对 MIDAS 适配器**不使用** |
| `health_check()` | 实现为 `GET /mapikey/verify`，而非探活 Base URL |
| `verify_tls` | 保留。企业 SSL 拦截场景下需配合代理排除规则 |

---

## 2.5 会话与并发模型（回答「多用户 / 多客户端 / 并发」）

### 2.5.1 手册里没有并发章节

对 `MIDAS-API-main` 全文检索 `동시 / concurrent / multi-user / multi-client / queue / 대기열`：
**94 处命中全部是结构工程概念**（`CONCURRENT_JOINT_FORCE` 同时节点力、`/db/CRGR`
Concurrent Reaction Group、`bCONCURRENT` 板同时力等），
**没有一处是关于 API 并发、多用户或调用配额的**。

**结论：MIDAS 官方文档未定义 API 层的并发能力或限制。**

### 2.5.2 真正的并发约束来自产品形态（实机验证）

MIDAS NX 是一个 **GUI 单实例应用**，其 API 由应用进程自身提供（本地接口，见 §2.1）。
无论走本地还是云端中继，最终都作用于**同一个 GUI 会话**。由此产生三条硬约束：

| # | 事实 | 后果 |
|---|---|---|
| 1 | **任何会弹出确认对话框的调用，会阻塞整个 API 会话**，不只是那一次调用，直到有人在 NX 那台机器上点掉对话框 | 并发调用会互相拖死 |
| 2 | 会话被对话框阻塞时，**`/mapikey/verify` 仍然回答 `connected`**（中继在应答），而所有 `/db/*` 调用超时 | 健康检查**无法**发现阻塞 |
| 3 | 文件路径在 **NX 所在机器**上解析；路径不存在会在**那边**弹对话框并阻塞会话，而 HTTP 调用照常返回类似成功的信息 | 一次错误路径可锁死整条通道 |

### 2.5.3 多客户端 / 多用户模型（部署形态）

**平台是局域网内多用户共用的服务，每个部门接入自己的 MIDAS 实例。**

```text
部门 A 用户 ─┐
部门 B 用户 ─┼─▶ StructAI MCP 平台（局域网服务器，多人并发）
部门 C 用户 ─┘        │
                      ├── MAPI-Key A → 部门 A 的 MIDAS Gen NX 实例
                      ├── MAPI-Key B → 部门 B 的 MIDAS Civil NX 实例
                      └── MAPI-Key C → 部门 C 的 MIDAS Gen NX 实例
```

**两个正交的并发维度必须分清：**

| 维度 | 并发性 | 约束 |
|---|---|---|
| **平台 ↔ 用户** | **多用户并发** | 平台必须能同时服务多个部门的请求；任务池需要真实并发 |
| **平台 ↔ 某个 MIDAS 实例** | **串行** | 该实例是单 GUI 应用，任何弹框会阻塞整条通道（§2.5.2） |

README 的表述（하나의 클라이언트가 여러 `MAPI-Key`를 가지면…）描述的是
**调用方持有多个 Key 的能力**，不是用户模型；用户模型由部署形态决定。

**`midas_clients` 因此是「多租户注册表」**：
每一行 = 某个部门/用户注册的一个 MIDAS 实例，`MAPI-Key` 属于**实例**而非用户。

### 2.5.4 对 StructAI 的强制要求

> **平台层并发 N（服务多用户），但每个 `midas_client_id` 并发恒为 1。**

落到设计上：

1. **Task Engine 采用「全局工作池 + 按客户端串行队列」**：
   全局并发 N 服务多部门，但**同一 `midas_client_id` 任何时刻只允许一个在途请求**。
   V2.1 §26 的「并发限制」需按此细化。
2. **健康检查不能只用 `/mapikey/verify`** —— 它看不见阻塞。
   应增加一次轻量 `GET /db/UNIT` 之类的真实数据调用作为活性探针。
3. **所有会弹对话框的调用（文件读写、路径相关、`/doc/NEW`）必须串行且带超时**，
   超时后**不得自动重试**（见 §3.5 第 5 条）。
4. `midas_clients` 已有 `timeout_seconds`；**增加 `max_concurrency` 列并固定为 1**，
   把这条约束写进数据而不是代码注释。
5. **🔴 `midas_clients` 缺归属字段 —— DDL 缺陷，多部门接入前必须补**

   现有 `midas_clients` 表（V2.1 §4）**没有任何归属或可见性字段**。
   在「多部门各自接入自己的 MIDAS 实例」的部署下，这意味着：

   ```text
   A 部门用户可以查询 / 操作 / 甚至删除 B 部门注册的 MIDAS 实例
   → 跨租户越权，且无法按部门计量与审计
   ```

   需补：

   | 新增列 | 类型 | 说明 |
   |---|---|---|
   | `owner_id` | INTEGER FK `users(id)` | 注册该实例的用户；也是 `visibility='private'` 规则的匹配键 |
   | `department` | TEXT | 所属部门的**标签**，同时也是 `visibility='department'` 规则的**匹配键** —— 与 `users.department`（总纲 §4.2.5 补充）**按值**比较。二者共用同一套词表、均非外键（不建 `departments` 表）。**不是**仅供展示/分组的字段：它决定谁能用这个实例。`NULL` = 未登记部门标签，此时该实例**无人可用**（比较无法命中；§2.5.4 要求失败关闭，绝不假定「同一部门」） |
   | `visibility` | TEXT CHECK(`private`/`department`/`public`) | 可见范围；默认 `private` |
   | `max_concurrency` | INTEGER NOT NULL DEFAULT 1 | 固定 1（见第 4 条） |

   并在权限模型中加入 **「实例归属校验」**：
   `midas_client_id` 的使用必须先通过 `owner_id` / `visibility` 判定，
   与 `assistant:*`、`tool:*` 权限**叠加**生效，而不是替代。

   > **实现约束（裁决）：** 总纲 §4.8.2 的权限码是**封闭集合**，
   > 因此实例归属校验**不得引入新的权限码**，必须实现为
   > **既有权限码之上的数据范围过滤（data-scope filter）**。
   > 即：先判 `assistant:*` / `tool:*`，再按 `owner_id` / `visibility`
   > 收窄可操作的 `midas_client_id` 集合。

   > **规则两侧的落库位置：** 实例一侧是 `midas_clients.department`（上表），
   > **主体一侧是 `users.department`** —— 总纲 §4.2.5 补充规定「一个用户只属于
   > 一个部门」，两者**按值匹配**、共用同一套标签词表、均非外键。
   > 未分配部门的用户**不能**使用 `visibility='department'` 的实例（失败关闭）。
   > 该列是 v1.0 修订新增的：在此之前主体一侧**没有任何落库位置**，只能从
   > 「用户自己注册过的实例」反推，而部门的实例是**管理员注册一次**的，
   > 于是部门成员会被本部门实例拒绝 —— 该推导已删除。

## 2.6 局域网多部门部署：三条路径（关键决策）

### 约束

平台的部署形态是：**局域网服务器上一个平台，多个部门各自接入自己的 MIDAS**。
但实测表明 **MIDAS 本地接口绑定在回环地址上**（本机为 `::1`，见 §2.1），所以：

```text
平台（LAN 服务器） ──✗──▶ http://<部门PC>:3030/gen      不可达
```

### 三条路径

| 路径 | 做法 | 优点 | 代价 |
|---|---|---|---|
| **甲：云端中继** | 平台调 `moa-engineers.midasit.com`；各部门的 MIDAS 通过 WebSocket 外连 | 与网络拓扑无关；无需在部门 PC 装东西 | **依赖公网**；需防火墙放行 + SSL 拦截排除；流量绕行境外；延迟高 |
| **乙：部门侧本地转发器** | 在每个部门 PC 上跑一个我们的轻量转发进程，监听 LAN 地址并把请求转到 `localhost:3030` | **纯局域网**、无公网依赖、延迟最低、可离线；且**绕开 IPv6-only 限制** | 需在每台部门 PC 部署一个组件 |
| **丙：改 MIDAS 监听地址** | 若 MIDAS 有配置项可把 3030 绑到 `0.0.0.0` | 最简洁 | **未验证**——需确认 MIDAS 是否提供该设置；若无则不可行 |

### 建议

**甲为兜底，乙为主推。**

- **乙**最符合「局域网多部门平台」的形态：不依赖公网、不受 SSL 拦截影响、延迟低，
  而且转发器可以自行决定监听地址族，不受 MIDAS 绑定选择的限制。
  代价是要在部门 PC 上装一个小组件——但这对工程软件环境是常规操作。
- **甲**保留为跨网/异地部门的兜底通道，不需要在对方机器上装东西。
- **丙**值得先花十分钟确认：如果 MIDAS 原生支持改监听地址，方案会简单得多。

**需你确认：** MIDAS Gen/Civil NX 的设置里，有没有「API 监听地址 / 端口」之类的配置项？
（这决定丙是否可行，也影响乙的必要性。）

# 3. 请求与响应约定

## 3.1 两种包装键

| 端点族 | 请求外层键 | 说明 |
|---|---|---|
| `/db/*` | **`"Assign"`** | 编号键（ID）→ 数据对象 |
| `/doc/*` | **`"Argument"`** | 仅 `POST`；空参用 `{}` |

```jsonc
// /db/*
{"Assign": {"1": {"X": 0, "Y": 0, "Z": 0}, "2": {"X": 6, "Y": 0, "Z": 0}}}

// /doc/*
{"Argument": {"EXPORT_PATH": "C:\\out\\model.json"}}
```

## 3.2 读取响应

`GET` 返回的顶层键是**资源名（通常大写）**，不是 `Assign`：

```jsonc
// GET /db/NODE
{"NODE": {"1": {"X": 0, "Y": 0, "Z": 0}, "2": {"X": 6, "Y": 0, "Z": 0}}}
```

**由此产生三条 Adapter 硬规则：**

1. **解包**：读取响应时，须按端点的 `response_root_key` 取出内层对象
2. **回写复用**：把响应顶层键改名为 `Assign` 即可直接 `PUT`——这是官方推荐的
   schema 发现法（手册查不到字段时，在 GUI 里建好再 `GET`）
3. **空表不是空对象** ⚠️ —— **实机验证（见 §11）**

### 3.2.1 三种响应形态（必须全部处理）

`GET /db/*` 实测只有三种形态：

| # | 形态 | 含义 | 示例（实测） |
|---|---|---|---|
| 1 | `{"<RESOURCE>": {...}}` | **有数据** | `{"UNIT":{"1":{"FORCE":"KN","DIST":"M",...}}}` |
| 2 | `{"message":""}` | **表为空** | `GET /db/NODE` → `{"message":""}` |
| 3 | `{"error":{...}}` | **失败**（HTTP 可能仍是 200/201） | 见 §3.5 第 2 条 |

> **这是最容易写错的一条。** 空表**不会**返回 `{"NODE": {}}`，
> 而是返回 `{"message":""}`。因此：
>
> - **禁止**用 `response[root_key]` 直接取值——空表时 `root_key` 根本不存在
> - 必须按**形态匹配**：先看有无 `error`，再看有无 `message`，最后才按
>   `response_root_key` 取数据
> - `{"message":""}` 是**成功且无数据**，不是错误；而
>   `{"message":"... Analysis failed."}` 是失败（§3.5 第 7 条）——
>   **两者靠 message 是否为空来区分**
>
> 实测覆盖：`/db/NODE` `/db/ELEM` `/db/MATL` `/db/SECT` `/db/CONS`
> `/db/STLD` `/db/GRUP` `/db/BODF` `/db/LCOM-GEN` 九个端点，
> 空模型下**全部**返回 `{"message":""}`。

## 3.3 新文件限制（按端点区分）

**单位、结构类型等「新文件必需数据」只能用 `GET` / `PUT`，`POST` 不生效。**

这是**端点级**属性，Adapter 必须逐端点知道。归属：写入 `tool_interfaces.metadata_json`
的 `new_file_get_put_only` 标志。

## 3.4 文档自身矛盾（照录，不擅自更正）

| 位置 | 矛盾 |
|---|---|
| `/doc/new` vs `/doc/save` | 前者传 `{}`，官方 Python 示例中后者**不传 body**；与「`/doc/*` 统一用 `Argument` 包装」不一致 |
| `/db/CONS` 的 `CONSTRAINT` | README 示例 `"1111000"`，官方示例 `"1111111"`；**7 位**，而 MIDAS 常规为 6 自由度（Dx Dy Dz Rx Ry Rz）。第 7 位含义待确认 |
| `/doc/EXPORT` 的 `Argument` | 对象形式 `{"Argument": {"EXPORT_PATH": "..."}}` 会被拒但仍返回 200；**必须传裸字符串** `{"Argument": "C:\\..."}` |

> 最后一条是**已复现的实机现象**（见 `MIDAS-API-main/docs/error_reports/`），
> 属「2xx 错误体」类，Adapter 不能只看状态码。

---

## 3.5 危险语义与防呆清单（实机验证）

> 以下每一条都是**在真实 Gen NX / Civil NX 会话上复现过的**产品行为，不是推测。
> Adapter 与守卫层必须逐条实现。

| # | 危险行为 | 必须实现的防护 |
|---|---|---|
| **1** | **`DELETE {endpoint}` 带 ID 键的 `Assign` 体会清空整张表**，完全忽略传入的 id。对 `/db/NODE` 会连带删掉挂在其上的单元。**未文档化的 `DELETE {endpoint}/{id}` 才是删单条。** | 单条删除**只允许**走 `DELETE /db/XXX/{id}`；`Assign` 形式必须从 API 中移除或加显式二次确认 |
| **2** | **HTTP 200 不代表成功。** 多个端点返回 200 + `{"error": {...}}`。错误体**也会以 201 返回**。 | `is_error_body()` 必须同时检查 200 与 201 的 body，不能只看状态码（§7.4） |
| **3** | **`POST /db/NMAS` 会杀死 MIDAS NX**：当可选字段 `rmX`/`rmY`/`rmZ` 被省略时服务端崩溃。显式传（哪怕 `0.0`）则正常。 | Adapter 在写 `/db/NMAS` 前**强制补全这三个字段**；此类「必填兜底」应作为契约规则存在 |
| **4** | **`/doc/NEW` 丢弃未保存的工作**，包括与本次调用无关的文档。 | 高风险操作，纳入 §72 确认清单；调用前先探测是否有未保存改动 |
| **5** | **超时不等于回滚。** 写操作可能在 HTTP 放弃后仍然落地。 | **禁止对写操作自动重试**；超时后必须先读回模型状态 |
| **6** | **所有路径在 NX 所在机器上解析**，常常不是跑我们服务的那台。路径不存在会在那边弹模态对话框并阻塞会话，而 HTTP 仍返回类似成功的信息。 | 路径必须由调用方显式提供且可校验；**禁止从 `verify_connection()["user"]` 推导路径**（那是 MAPI 账号邮箱，不是 NX 主机的 Windows 账户） |
| **7** | **失败不一定带 `error` 键。** `/doc/ANAL` 求解失败返回 `{"message": "... Analysis failed."}`；`/doc/SAVEAS` 对根本没发生的保存返回 `"... command complete"`。 | 错误识别需覆盖 message 文本模式，不能只认 `error` |
| **8** | **`/post/TABLE` 的顶层响应键不稳定** —— 见过 `"Result Table"`、`"empty"`，也可能就是传入的 `TABLE_NAME`。**且 `"empty"` 可以承载一张完整的表。** | 必须**按形状匹配**（找带 `HEAD`/`DATA` 的字典），禁止按键名取值；禁止把 `"empty"` 读作「无数据」 |
| **9** | **手册可能把某个端点自己的字段名写错**，不只是枚举值。已确认两例：`/db/REBW`、`/db/REBC` 的手册 Specifications 表**每一个字段名都是错的**。 | 关键端点上线前必须用 `/info/db/...` 或实机 PUT 往返核对；`/info` 与实机冲突时以实机为准 |
| **10** | **`"Wrong Field"` 通常意味着值错，不是字段名错。** | 排障顺序：先换枚举值，再怀疑字段名 |
| **11** | ~~首次 `/doc/NEW` 之前必须先有打开的文档，否则可能不响应并阻塞会话。~~ **已实测推翻**：在「没有打开任何项目」的状态下直接 `POST /doc/NEW {}`，**立即返回** `200 {"message":"MIDAS GEN NX command complete"}`，无阻塞、无对话框。 | `/doc/NEW` 是「项目未打开」的**恢复入口**，不是需要前置条件的高危调用（见 §11.5.12）。它真正的高风险在另一面：**会丢弃未保存的工作**（第 4 条），调用前仍应确认无未保存改动 |
| **12** | **`/db/PRES` 的 `DIRECTION`**：手册标为可选、默认 `"NORMAL"`，但同一文章的脚注矩阵显示 `PLATE`+`FACE` 下 `NORMAL` 不可用。**省略该字段正是错误默认值被套用的方式。** | 强制要求显式传 `DIRECTION`，不代为选择（压力作用方向是工程决策） |
| **13** | **一个 GET 也可能弹对话框**：若打开的文档位于 `Program Files` 之类标准账户不可写的路径，读取类命令也会弹「拒绝访问」并阻塞。 | 工作文档禁止放在受保护路径；守卫层应探测文档路径 |
| **14** | **Hyper-S（`-M1`）端点是 Civil NX 专属**，在 Gen NX 下 404。 | 用 `HYPER_S_ONLY` 标记（而非 `CIVIL_ONLY`），因为 Hyper-S 预期将来会到 Gen |
| **15** | **手册对 ch08/ch17 的「Civil 专属」标注不可靠**：47 个声明 Civil 专属的端点中，**32 个在 Gen NX 上也能应答**（路由与 `/info` schema 均已实机确认）。 | 不要用 `product_scope` 做工程可行性门控；是否该在 Gen 上驱动桥梁/移动荷载功能是**工程师的判断** |

## 3.6 路径大小写不敏感，但响应根键始终是大写（实机验证）

### 事实

请求路径**完全大小写不敏感**，实测全部返回 `200` 且结果相同：

```text
/gen/db/NODE      → 200 {"NODE":{"1":{"X":0,...},"2":{...}}}
/gen/db/node      → 200 {"NODE":{"1":{"X":0,...},"2":{...}}}   ← 相同
/gen/db/Node      → 200 {"NODE":...}
/gen/db/nOdE      → 200 {"NODE":...}
/gen/db/lcom-gen  → 200 {"message":""}        （/db/LCOM-GEN）
/gen/info/db/node → 200 （同 /info/db/NODE）
/gen/db/node/1    → 200 {"NODE":{"1":{...}}}  （per-id DELETE/GET 形式）
/gen/doc/anal     → 200 （同 /doc/ANAL）
```

**但响应根键始终是规范的大写资源名** —— 即使请求用小写，
`GET /db/node` 返回的仍然是 `{"NODE": {...}}`。

### 这条事实有一个真实的坑

**若 `tool_interfaces.endpoint` 存的是小写、而解包按小写根键精确匹配，就会失配**：

```python
root_key = "node"                      # 由小写 endpoint 推导
if root_key in response:               # {"NODE": {...}} → False
    return response[root_key]
return response                        # ← 错误地落到「无根键」分支，
                                       #    把整个 {"NODE": {...}} 当成数据
```

后果是**静默的**：不报错，但返回的数据结构多了一层，下游全部错位。

### 强制要求

> **根键匹配必须大小写不敏感**（或统一转大写后比较）。
> 本项目的 `unwrap_response()` 与 `normalize_upstream()` 均已按此实现，
> 并有回归测试 `test_root_key_lookup_is_case_insensitive`。

### 建议

`tool_interfaces.endpoint` **统一以规范大写形式入库**（如 `/db/NODE`、`/db/LCOM-GEN`），
把大小写差异挡在注册表层；大小写不敏感匹配只作为**兜底**，不作为主路径。

# 4. 载荷形状分类（Adapter 最易低估处）

`Assign` 的值**不是统一结构**。官方示例已暴露至少四类：

| 类型 | 示例端点 | 形状 |
|---|---|---|
| **A. 扁平字段** | `/db/NODE` | `{"X":0,"Y":0,"Z":0}` |
| **B. 容器 + ITEMS 数组** | `/db/CONS` | `{"ITEMS":[{"ID":1,"CONSTRAINT":"1111111"}]}` |
| **C. 嵌套参数数组** | `/db/MATL` | `{"TYPE":"CONC","NAME":"C32","PARAM":[{"P_TYPE":1,"STANDARD":"AS17(RC)","DB":"C32"}]}` |
| **D. 多层嵌套** | `/db/SECT` | `{"SECTTYPE":"DBUSER","SECT_BEFORE":{"SHAPE":"SB","DATATYPE":2,"SECT_I":{"vSIZE":[0.6,0.6]}}}` |

**结论：** `tool_interfaces.request_schema_json` **必须是真 schema**，不能是占位符。
手抄约 270 个端点的字段结构不现实，唯一可行的规模化路径是 §5 的自省端点。

---

### 4.1 `Assign` 外层键的语义随端点而异（实机教训）

**这是最容易踩的坑**：`Assign` 的外层键**并不总是**「该端点的主实体号」。

| 端点 | 外层键含义 | 内层结构 |
|---|---|---|
| `/db/NODE` | 节点号 | 坐标字段 |
| `/db/ELEM` | 单元号 | 单元字段 |
| **`/db/CNLD`** | **节点号** | `ITEMS[]` = 该节点上的各工况荷载；`ITEMS[].ID` 只是**序号** |
| `/db/CONS` | 约束组号 | `ITEMS[]` = 各节点及其约束 |
| `/db/STLD` | 工况号 | 工况字段 |

`/db/CNLD` 尤其危险：外层键是节点号，内层却还有一个**看起来像节点号的**
`ITEMS[].ID`（手册参数表：`Serial Number / Integer / 0 / Optional`）。

**误用的后果是荷载静默地加到错误的节点上**——分析照常返回
`command complete`，但结果全错（本项目实际踩过：荷载落在固定端，
表现为反力正确、内力与位移全零）。完整案例见 §11.6。

**因此 `tool_interfaces.metadata_json` 必须记录 `outer_key_means`**，
取值 `node` / `element` / `load_case` / `group` / `self`，
把这条语义变成**数据**，而不是散落在 Adapter 代码里的注释。

# 5. Schema 自省（本规范最重要的一条）

在 `baseURL` 与 `db` 之间插入 `info`，服务器会**直接返回该资源各 Key 的说明与 Value 类型**：

```http
GET https://moa-engineers.midasit.com:443/civil/info/db/node
MAPI-Key: <key>
```

```text
普通端点：{base url}/db/NODE
自省端点：{base url}/info/db/NODE
```

### 5.0.1 自省响应的包装键固定为 `Argument`（实机验证）

`/info` 返回的 schema **不以资源名为键**，而是**固定包在 `Argument` 下**：

```jsonc
// GET /gen/info/db/NODE
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "Argument": {                       // ← 固定，不是 "NODE"
    "type": "object",
    "properties": { "X": {...}, "Y": {...}, "Z": {...} }
  }
}
```

实测 7 个资源（`NODE`/`ELEM`/`MATL`/`SECT`/`CONS`/`UNIT`/`STLD`）
**顶层键一律是 `['$schema', 'Argument']`**。解析自省结果时必须取
`payload["Argument"]["properties"]`。

**并且 `/info` 的 schema 是扁平且不完整的**——它不声明 `required`、
不表达分支。实测字段数远少于手册：`MATL` 只有 **9** 个属性、
`SECT` **11** 个、`CONS` 只有 1 个（`ITEMS`）、`STLD` **4** 个。
所以 `/info` 适合**校验字段名是否存在**，不足以单独重建完整载荷结构，
仍需与手册/契约合并。

**工程含义：**

- `capabilities` / `tool_interfaces` 的 `request_schema_json` **可由活 API 自动生成**，
  不必依赖手册转录，且天然与用户实际安装的软件版本一致
- 新增 MIDAS 版本或产品时，重新跑一次自省即可刷新注册表
- 应作为**离线构建步骤**（`build_introspect.py`）而非运行时行为

> 这是 V2.1 §16「Capability Resolver」在实现层唯一可规模化的依据来源。

## 5.1 自省的适用范围（**重要限制**）

**`/info/{endpoint}` 只为 `/db/*` 提供，对设计代码端点一律 404。**

| 范围 | 结果 |
|---|---|
| `/db/*` 资源-产品对 | **402 对中 399 对可用** |
| `/DESIGN/*` 对 | **147 对中 0 对可用**（尽管这些端点本身的普通 GET 正常应答） |

三个例外（连 `/info` 也 404）：`/db/IEHG-GL-M1`、`/db/IEHG-PSS-M1`、`/db/IEHG-TRUSS-M1`
（Civil Hyper-S 三兄弟）。

**推论：** 自省能覆盖 `/db/*`（约 231 个端点），
但 **122 个设计代码端点的 schema 只能来自手册或实机记录**。
所以「用 `/info` 全自动生成注册表」**只对数据层成立**，设计层仍需人工/契约来源。

### 5.1.1 实机覆盖率（Gen NX，229 个 `/db/*` 端点全量扫描）

| 结果 | 数量 |
|---|---|
| `/info` 应答 | **193**（84%） |
| `/info` 404 | **36** |

36 个失败项的分类很干净：

| 类别 | 数量 | 端点 |
|---|---|---|
| **Hyper-S（`-M1`）** | **21** | `ACTL-M1` `BCGA-M1` `BCGD-M1` `EIGV-M1` `EPMT-M1` `HHCT-M1` `IEHG-BEAM-M1` `IEHG-GL-M1` `IEHG-PSS-M1` `IEHG-TRUSS-M1` `IMFM-M1` `MATL-M1` `NLCT-M1` `NLNK-M1` `POGD-M1` `POLC-M1` `STCT-M1` `STYP-M1` `THGC-M1` `THIS-M1` `THOO-M1` |
| 桥梁专用 | 5 | `CAMB` `GCMB` `GSBG` `SPAN` `PLCB` |
| 移动荷载动力系数 | 5 | `CJFG` `CRGR` `DYFG` `DYLA` `DYNF` |
| 其他 | 5 | `CMCS` `EWSF` `RCHK` `STRPSSM` `WVLD` |

**规律：全部 21 个 `-M1`（Hyper-S）端点在 Gen NX 下 `/info` 一律 404**——
与「Hyper-S 是 Civil NX 专属」一致（在 Gen 上这些端点本身也不可用）。
故本表是 **Gen NX 视角**；Civil NX 下的覆盖率会更高。

### 5.1.2 `/info` 的字段丰富度差异极大（重要）

| 属性数 | 端点数 |
|---|---|
| **1** | **49** |
| 2–5 | 47 |
| 6–15 | 74 |
| 16–40 | 20 |
| 41+ | 3（`TDMT` 72、`STCT` 63、`THIS` 39） |

**49 个端点只返回 1 个属性**（通常就是一个 `ITEMS` 容器），
例如 `BMLD` `CNLD` `CONS` `DRLS` `EXLD` `RCHK`。

**结论：`/info` 可用于「校验字段名是否存在」，不足以重建完整载荷结构。**
这 49 个浅端点（以及全部 design 端点）的 schema 必须来自手册或 SDK 契约。

> 这直接决定了注册表的构建策略：
> **`/info` 做校验与补全，手册 / SDK 契约做主体。**

## 5.2 自省自身也有缺陷

服务端返回的 schema 并非无错。已登记的两类：

1. 撇号用反斜杠转义（不是合法 JSON 转义）
2. `maxItems` 写在数组的 `items` 子 schema 上，而 JSON Schema 会忽略它

**并且 `/info` 既不保证是服务器接受集合的超集，也不保证是子集**：
`/db/POSL` 的 `CODE` 在 Civil NX 的 `/info` 里声明，实机却拒收（即使传空字符串）；
反过来 `/db/STBK` 的 `LCNAME` 两个产品的 `/info` 都没有，实机却接受。
**`/info` 与实机冲突时，以实机往返为准。**

---

# 6. 端点规模与分类

手册 27 章，约 **270 个端点**，分六大类：

| 类别 | 前缀 | 逻辑端点数 | 唯一 URI 数 | 性质 |
|---|---|---|---|---|
| 数据 | `/db/*` | 229 | 229 | 模型、属性、边界、荷载、分析控制、组合、设计参数 |
| 设计代码 | design | 135 | 125 | KDS 41 30:2022（钢）、KDS 41 20:2022（RC）、AIK-SRC2K（SRC） |
| 后处理 | `/post/*` | 98 | **2** | 结果表；**URI 只有 `/post/TABLE` 与 `/post/TEXT`** |
| 操作 | `/ope/*` | 20 | 19 | GUI 操作与预计算，**不落 DB** |
| 视图 | `/view/*` | 12 | 7 | 视图控制与**图像捕获（写文件）** |
| 文档 | `/doc/*` | 11 | 11 | 新建/打开/保存/另存/导入/导出/分析，**仅 POST** |
| **合计** | | **505** | **392** | |

> **数量口径说明：** 上表取自 `docs/api-registry/midas_api_registry.json`
> 的实测统计（505 条逻辑端点记录，392 个唯一 URI）。
> 本规范早期版本引用的「约 270 个端点」来自手册 `INDEX.md` 各章自述的
> 「N개」声明，那是**章节自报数**，与逐条抽取的结果不一致。
> **以注册表为准**；手册自述数仅作交叉参考。
>
> 与兄弟 SDK 的 **384 个契约**也不等：SDK 的 `contracts/` 只覆盖
> `/post/*` 中的 3 个，且 design 族的组织方式不同。
> **三者不可混用为构建目标数**，需先对账。

## 6.1 元素类型与节点数约束

| `TYPE` | 节点数 |
|---|---|
| `BEAM` `TRUSS` `TENSTR` `COMPTR` | 2 |
| `PLATE` `PLSTRS` `PLSTRN` `AXISYM` | 3–4 |
| `WALL` | 4（仅四边形） |
| `SOLID` | 4 / 6 / 8（四面体/楔形/六面体） |

## 6.2 单位系统

`/db/UNIT` 四维：`DIST` / `FORCE` / `HEAT` / `TEMPER`。

---

# 7. 对 V2.1 的修正清单

## 7.1 数据库（`tool_interfaces` 需加两列）

| 新增列 | 类型 | 说明 |
|---|---|---|
| `request_wrapper` | `TEXT` | `'Assign'` / `'Argument'` / NULL |
| `response_root_key` | `TEXT` | 如 `'NODE'` / `'ELEM'`；无则 NULL |

`metadata_json` 承载端点级怪癖：

```json
{
  "new_file_get_put_only": true,
  "source_chapter": "03_DB_Node_Element",
  "outer_key_means": "node|element|load_case|group|self"
}
```

### 7.1.1 订正：`product_scope` 提升为**列**，并新增 `domain` / `feature`

本规范早期版本把 `product_scope` 放在 `metadata_json` 里：

```json
{ "product_scope": "both|gen|civil" }
```

**该写法已废弃**（总纲 §4.2.11 裁决）。原因：`product_scope` 在**每次能力解析**时
都要参与过滤，而 JSON 字段无法有效索引；`domain`/`feature` 同理，它们是前端的
分组依据。三者改为**列**，并加复合索引 `ix_tool_interfaces_scope`。

同时把 `product_scope` 的取值从 3 值扩为 **5 值**，并新增第三产品：

```
product_scope   gen / civil / designer / both / unknown      默认 unknown
domain          8 值（封闭）      ← 前端一级菜单 / LLM 第一层筛选
feature         27 值（封闭）     ← 手册章节 / 前端二级菜单 / LLM 第二层筛选
```

权威取值表与 `feature → domain` 映射见**总纲 §4.2.11**；本节只记数据库形态。

**为什么必须有 `unknown`（本规范实测所得）：**

> §3.5 第 15 条已证明：手册对 ch08/ch17 的「Civil 专属」标注**不可靠** ——
> 47 个声明 Civil 专属的端点中，**32 个在 Gen NX 上也能应答**。

所以手册的产品标注**不能作为 `product_scope` 的取值来源**，只能作为线索。
真实取值必须**逐端点对实机探测**得到；在探测之前，该端点就是 `unknown`。

**`unknown` 的默认行为（总纲 §4.2.11 裁决）：乐观放行 + `unverified` 警告。**
不适用产品的能力以 `CAPABILITY_NOT_SUPPORTED`（422，总纲 §4.4 封闭集合内）
拒绝，**不新增错误码**；产品过滤与 §4.8.2 的权限检查**叠加**生效。

> **`metadata_json` 保留 `source_chapter`** —— 它是**溯源**信息（读出来给人看），
> 不是过滤条件；而 `feature` 是同一件事的**可查询形态**。两者并存是有意的：
> 前者记录来源，后者供查询。抽取管线应同时写入。

**`midas_clients` 需另加 4 列** —— 见 §2.5.4 第 5 条（多租户归属）：
`owner_id` / `department` / `visibility` / `max_concurrency`。

> **订正：** 本规范早期版本此处曾写「**不改动** `midas_clients`」，
> 与 §2.5.4 第 5 条直接冲突。**以 §2.5.4 为准**——
> 多部门共用平台时，缺归属字段会导致跨租户越权。
> 该 4 列已落入 V2.1 §4、`backend/sql/001_schema.sql` 与
> `backend/app/models/midas.py`，并已实机验证建表通过。

**不改动**：`access_token_encrypted`（保留给未来非 MIDAS 软件；
MIDAS NX 只用 `MAPI-Key`，无 token 概念，见 §2.1）。

## 7.2 `interface_code` 约定（不改结构，明确规则）

一个 `interface_code` 对应**一个（端点, 方法）对**：

```text
node.create  → POST   /db/NODE
node.read    → GET    /db/NODE
node.update  → PUT    /db/NODE
node.delete  → DELETE /db/NODE
```

与 V2.1 §17 的 `interface_code: "node.create"` 示例一致，无需改表。

## 7.3 Adapter Protocol 需新增能力

| 方法 | 用途 |
|---|---|
| `introspect(resource) -> dict` | 调 `/info/db/<RES>`，返回服务器声明的字段与类型 |
| `health_check()` 改造 | 调 `/mapikey/verify`，返回 `status`/`keyVerified`/`program`/`connectionID` |
| `unwrap(response, root_key)` | 按 `response_root_key` 取出内层数据 |
| `wrap(payload, wrapper)` | 按 `request_wrapper` 包装为 `Assign` / `Argument` |

## 7.4 2xx 错误体必须识别

`is_error_body()` 至少识别以下标记（官方文档已确认会出现）：

```text
"MIDAS GEN NX path is wrong"
"the file can't open"
"Analysis is not allowed"
"no analysis result"
```

**禁止仅凭 HTTP 状态码判定成功。**

## 7.5 MCP resource 枚举粒度（**已裁决：以真实接口为准**）

V2.1 的 MCP resource 枚举只有 9 个（`node`/`element`/`material`/`section`/`load`/
`boundary`/`group`/`coordinate_system`/`property`），而真实 API 的分布是：

| 粗资源 | 真实端点数 | 例子 |
|---|---|---|
| `property` | **32** | `/db/MATL` `/db/SECT` `/db/THIK` `/db/TDF*` `/db/IEH*` `/db/FIBR` … |
| `boundary` | **24** | `/db/CONS` `/db/NSPR` `/db/GSPR` `/db/ELNK` `/db/RIGD` `/db/SDVI` … |
| `load` | **21** | `/db/STLD` `/db/BMDL` `/db/FBLD`+`/db/FBLA` `/db/PRES` `/db/SWIND` `/db/SSEIS` … |

**问题：** LLM 传 `resource=load` 时，由谁决定落到 `/db/BMLD` 还是 `/db/FBLD`？
当前设计没有归属方。

**两个候选方案：**

| 方案 | 做法 | 代价 |
|---|---|---|
| **甲：扩枚举** | 把 MCP resource 扩到接近真实的粒度（如 `beam_load`/`floor_load`/`pressure_load`） | Tool Schema 变复杂，但 LLM 一次选对 |
| **乙：Capability 细分** | 保持 9 个粗资源，在 Capability 层按参数二次选择（如按荷载类型字段路由） | Schema 稳定，但二次选择逻辑需明确归属且易错 |

### 裁决

> **「我 V2.1 里定的 9 个资源，真实接口为准」** —— 采纳**方案甲：扩枚举**。

理由：真实差异是**语义差异**（梁荷载与楼面荷载不是一回事），
不是同一概念的实现细节；让 LLM 一次选对，胜过在 Capability 层做易错的二次路由。

### 依据：注册表实测的 resource 分布（26 个）

| resource | 条数 | resource | 条数 |
|---|---|---|---|
| `design` | 148 | `load_combination` | 11 |
| `result` | 96 | `project` | 11 |
| `load` | 39 | `load_case` | 9 |
| `moving_load` | 29 | `bridge` | 7 |
| `misc` | 24 | `construction_stage` | 7 |
| `dynamic_load` | 17 | `view` | 7 |
| `boundary` | 14 | `pushover` | 6 |
| `material` | 13 | `tendon` | 6 |
| `section` | 13 | `spring` | 5 |
| `analysis` | 12 | `node` | 2 |
| `element` | 12 | `structure_type` | 2 |
| `link` | 11 | `thickness` | 2 |
| | | `group` / `unit` | 1 / 1 |

### 落实要求

1. **枚举以上表为基线**，由 V2.1 §7–§8 落笔（枚举归 V2.1 所有，
   见总纲所有权矩阵 #3；本规范只给裁决与依据）。
2. **`design`(148) 与 `result`(96) 是聚合桶，不再细拆枚举值。**
   二者的具体判别交给 `interface_code`：
   - `result` → 按 `TABLE_TYPE` 区分（如 `result.reaction`、`result.story_drift`）
   - `design` → 按设计代码族 + 动作区分（如 `design.rc.beam_design_forces`、
     `design.steel.code_check`）
3. **版本影响**：这是 MCP Tool Schema 的**破坏性变更**，按 V2.1 §31.3
   需升版本号（`tool.version` `2.1` → `2.2`）。因尚未发布，无兼容负担。
4. **`coordinate_system` 与 `property` 两个旧枚举值应删除**：
   真实 API 中不存在对应资源，前者落在 `/db/SKEW`（归 `node`），
   后者实际是 `material`/`section`/`thickness` 等具体资源的旧称。

---

# 8. 对 v1.2 的修正清单

| 位置 | 现状 | 修正 |
|---|---|---|
| §9.2 创建 MIDAS 客户端 | `api_url: "http://192.168.1.100:8080"` | 改为 `http://localhost:3030/gen`（本地）或 `https://moa-engineers.midasit.com:443/gen`（云端） |
| §9.6 测试连接 | 未指明实现 | 明确调 `/mapikey/verify`，返回 `keyVerified`/`program`/`connectionID` |
| §40–§43 模型 REST | `/api/v1/midas/model/nodes` | 我方 REST 路径可保留，但**必须注明下游映射到 `/db/NODE`** |
| §45 计算 | `/api/v1/midas/analysis/run` | 下游为 `POST /doc/ANAL` |
| §9.7 连接 | `POST /clients/{id}/connect` | 语义为「校验 MAPI-Key + 确认本地产品在运行」，非建立 TCP 连接 |

---

# 9. 无法复用的 MIDAS 原生能力（重要成本项）

MIDAS 提供 **61 个 Plug-in**，覆盖各国规范荷载生成、人工地震波、反应谱、配筋、荷载组合、
结果导出、格式转换等。**但它们无法被服务端调用：**

```text
技术栈：TypeScript + React（moaui 组件库）+ PyScript（浏览器端 Python 3.11.2）
打包：  构建成 ZIP → 在产品 MyWork 标签页上传
运行：  内嵌于 MIDAS GUI，需人工在界面操作
数据访问：MidasAPI(Product.CIVIL, "KR").dbRead("NODE") / dbWrite(...)
```

MIDAS 提供的 npm 库：`@midasit-dev/cra-template-moaui`、`moaui-components-v1`、`moaui-lab`。

**结论：**

1. 原生 Plug-in **没有服务端入口**，我们的 MCP 层调不到
2. 因此 v1.2 §81（荷载生成）、§82（规范检查）、§85（优化）**必须自研**
3. 这 61 个 Plug-in 的价值是：**功能参照**（工程师期望什么）+ **端点规格来源**（它们内部调哪些 `/db/*`）

## 9.1 已完成的验证（回答「官方能否走通 REST 入口」）

**结论：走不通。** 三条独立证据：

| 证据 | 内容 |
|---|---|
| ① 手册零覆盖 | 对 `docs/manual/`（27 章、约 270 端点）全文检索 `plug-in` / `PLUGIN` / `/plugin` → **0 处匹配**。JSON Manual 里没有任何 Plug-in 端点 |
| ② 技术栈 | Plug-in 是 TypeScript + React + **PyScript（浏览器端 Python 3.11.2）**，打包 ZIP 后在产品 MyWork 标签页上传，**内嵌于 GUI 运行** |
| ③ 数据访问方式 | 通过 `MidasAPI(Product.CIVIL, "KR").dbRead("NODE")` 这类**产品内包装器**调用，与外部 REST 调用者是两条路 |

**需要你决策：** 各国规范算法（风/雪/地震/温度，多国代码）自研成本很高。
可选策略：

- 只做中国规范（GB 50009 / 50011 / 50017），其余不支持
- 只做「参数录入 + 组合生成」，规范系数由工程师手工输入
- 长期投入，逐步覆盖

## 9.2 替代路径：`midas-nx` SDK（MIT）

**`Dennis5882/MIDAS-API-NX-SDK`** 提供了另一条路，且质量很高：

| 项 | 内容 |
|---|---|
| 包名 | `midas-nx`（PyPI **与** npm 同名同版本号，lockstep 发布） |
| 许可 | **MIT** —— 可自由使用/修改/商用 |
| 作者 | MIDAS IT 在职员工，基于**实机验证**开发；**非 MIDAS IT 官方支持产品** |
| 覆盖 | Civil NX + Gen NX，来自同一份「reviewed endpoint inventory」 |
| 契约 | **`contracts/endpoints/*.yaml` —— 384 个机器可读端点契约** |
| 默认风险 | Risk level 1（只读），`MidasClient` 默认可安全跑在真实模型上 |
| 文档站 | `https://dennis5882.github.io/MIDAS-API-NX-SDK/` |

### 契约目录构成（384 个）

```text
db      222
design  122
ope      19
doc      11
view      7
post      3
```

### 为什么它比手册更适合做注册表来源

每个契约按字段记录 **`provenance`**：

```text
manual          从手册章节转录
live_verified   手册的说法已在运行中的产品上核对过
live_corrected  手册是错的，实机检查替换了它（错处记入 manualDefects）
info_schema     取自 GET /info{endpoint}
```

**并且明确禁止以 SDK 源码为契约来源** —— 因为「从实现推导的契约无法发现实现本身是错的」。
这正是我们要的：**一份不以某个实现为准、而以产品和手册为准的端点事实表**。

契约还区分两组容易混淆的布尔量，对我们的高风险门控直接可用：

- `documentedOptional`（关于**文档**的声明） vs `safeToOmit`（关于**产品**的声明）
- `risk`（这个端点**是什么**） vs `mitigation`（SDK **做了什么**）——
  被缓解的崩溃风险**仍然是崩溃风险**

**建议：** `tool_interfaces.request_schema_json` 与 `capabilities` 的填充
**以 SDK 的 `contracts/endpoints/*.yaml` 为主来源**，
我方的 `docs/api-registry/part-*.json` 作为交叉校验（两者都源自同一手册，可互为独立转录）。
但注意：SDK 只覆盖 **3 个 `/post/*` 契约**，所以结果表（约 90 个端点）仍需我方抽取补足。

---

# 10. 待确认项

| # | 待确认 | 影响 |
|---|---|---|
| 1 | ~~`/db/CONS` 的 `CONSTRAINT` 第 7 位含义~~ | ✅ **已实机解决**：`/info/db/CONS` 的字段描述为 `(DX,DY,DZ,RX,RY,RZ,RW)` —— **7 位 = 三平动 + 三转动 + RW**（第 7 位是绕局部轴的转动/翘曲自由度）。README 的 `"1111000"` 与示例的 `"1111111"` 都是 7 位，不矛盾 |
| 2 | `/doc/save` 是否接受空 body | Adapter 参数构造 |
| 3 | `/info/db/<RES>` 对全部 270 个端点是否都可用 | Schema 自省方案的可行性 |
| 4 | `moa-engineers.midasit.com` 之外是否有区域替代服务器及其地址 | 部署与容灾 |
| 4b | **MIDAS 是否提供「API 监听地址 / 端口」配置项**（能否把 3030 从 `::1` 改绑到 LAN 或 `0.0.0.0`） | 决定 §2.6 方案丙是否可行 |
| 4c | 本地 API 的绑定地址是否随 Gen/Civil NX 版本或设置变化 | §2.1 的观测仅单机单版本，不应写死假设 |
| 5 | `/post/*` 结果表是否需要 `POST` 触发而非 `GET` | 结果读取实现 |
| 6 | 粗资源 vs 扩枚举（§7.5） | Tool Schema 稳定性 |

---

# 11. 实机验证记录

## 11.1 被测环境

### 11.1.1 第一轮：本机 Gen NX（只读）

| 项 | 值 |
|---|---|
| 产品 | **MIDAS Gen NX**（`/mapikey/verify` 返回 `"program":"gen"`） |
| Base URL | `http://localhost:3030/gen` |
| 验证端点根 | `http://localhost:3030` |
| 探测方式 | **纯 GET，只读**（未执行任何写操作、`/doc/NEW` 或 `DELETE`） |
| 模型状态 | 项目已打开，**模型为空**（`/ope/PROJECTSTATUS` 各计数均为 0） |

### 11.1.2 第二轮：三个产品并列（含云端中继）

> 为多产品路由框架（总纲 §4.9）验收而建立。**三个产品同时连通**，
> 这是「同一平台连接不同用户的不同产品」的实测基础。

| 产品 | 接入方式 | Base URL | `program` 回显 | 实测 |
|---|---|---|---|---|
| **MIDAS Gen NX** | 本机回环 | `http://localhost:3030/gen` | `gen` | `healthy` |
| **MIDAS Civil NX** | 云端中继 | `https://moa-engineers.midasit.cn:443/civil` | `civil` | `healthy` |
| **MIDAS Civil Designer** | 云端中继 | `https://moa-engineers.midasit.cn:443/cdn` | `cdn` | `healthy` |

三者均 `keyVerified: true`、`status: "connected"`，延迟 250–630 ms。

> **第三产品**：`product_scope` 的取值集合（总纲 §4.2.11）因此从
> `gen / civil / both / unknown` 扩为 **`gen / civil / designer / both / unknown`**。
>
> **URL 段与分类名不同**：云端 URL 的路径段是 **`cdn`**（MIDAS 的 API 要求），
> 而 `product_scope` 标为 **`designer`**（给人看的分类）。两者是不同轴——
> 前者是 wire 细节，后者是能力分类——映射由
> `app.core.constants.PRODUCT_SCOPE_BY_PRODUCT` 显式给出，不靠推断。
> 适配器 code 由产品值派生（`f"midas_{product.value}"`），故 Designer 的
> 适配器 code 是 **`midas_cdn`**。

## 11.2 已验证为真的结论

| 结论 | 证据 |
|---|---|
| `/mapikey/verify` 在**主机根**，不含产品段 | 根路径 → `200`；`/gen/mapikey/verify` → **404** |
| `/info` **只覆盖 `/db/*`**，设计代码端点 404 | `/info/db/NODE` → 200；`/info/DESIGN/RC/KDS-41-20-2022/DCTL` → **404**（证实 §5.1） |
| GET 响应的资源名根键 | `/db/UNIT` → `{"UNIT":{...}}`；`/db/PJCF` → `{"PJCF":{...}}`；`/db/STYP` → `{"STYP":{...}}` |
| **空表返回 `{"message":""}`** | 9 个端点一致（见 §3.2.1） |
| `/info` 包装键固定为 `Argument` | 7 个资源顶层键一律 `['$schema','Argument']`（见 §5.0.1） |
| `CONSTRAINT` 是 **7 位** | `/info/db/CONS` 描述 `(DX,DY,DZ,RX,RY,RZ,RW)` |

## 11.3 实测数据样本

```jsonc
// GET /gen/db/UNIT —— 单位系统已设置
{"UNIT":{"1":{"FORCE":"KN","DIST":"M","HEAT":"KJ","TEMPER":"C"}}}

// GET /gen/db/PJCF —— 项目信息
{"PJCF":{"1":{"USER":"JSK","ADDRESS":"JSK"}}}

// GET /gen/db/STYP —— 结构类型
{"STYP":{"1":{"STYP":0,"MASS":1,"GRAV":9.806,"TEMP":0,
              "bALIGNBEAM":false,"bALIGNSLAB":false,
              "bMASSOFFSET":true,"bROTRIGID":false,"bSELFWEIGHT":false}}}

// GET /gen/ope/PROJECTSTATUS —— 各计数为 0（空模型）
{"PROJECTSTATUS":{"DATA":[["结构类型","1","0"],["节点","0","0"],["单元","0","0"], ...]}}
```

## 11.4 与文档不符之处（需注意）

| 项 | 文档说法 | 实测 |
|---|---|---|
| `/mapikey/verify` 的 `user` / `connectionID` | 官方示例给出 `"User_ID"` 与一个连接 ID | **本机回环实测均为空字符串** `""`。`keyVerified`/`status`/`program` 正常。**因此不可依赖 `user` 字段**（SDK 亦独立发现它其实是 MAPI 账号邮箱，而非 NX 主机账户） |
| `/info` 的字段完整度 | 官方称返回该资源的 Key 与类型 | 实测**扁平且不完整**（`MATL` 仅 9 属性、`CONS` 仅 1 个 `ITEMS`），不含 `required`、不表达分支 |

> **订正（第二轮实测）：上面第一行的「均为空字符串」只对**本机回环**成立。**
> **云端中继两者都有值**：
>
> | 接入方式 | `user` | `connectionID` |
> |---|---|---|
> | 本机 `localhost:3030` | `""` | `""` |
> | 云端 `moa-engineers.midasit.cn` | `"erwe"` | `"t-NXqIsmTw"`（Civil）/ `"CZXg8vJZQw"`（Designer） |
>
> 因此结论应改为：**本地接入为空、云端接入有值**。「不得依赖 `user`」的理由
> （它无法用来推导 NX 主机的 Windows 账户或路径，§3.5 第 6 条）在两种接入下
> **都仍然成立**——有值也不代表它描述的是 NX 主机账户。

## 11.5 写操作验证（第二轮，已获授权）

### 11.5.1 🔴 `DELETE` 语义 —— 已实机确认

```
DELETE /gen/db/NODE/2                      → 200 {"NODE":{"2":{...}}}      只剩 1、3   ✅ 按 id 删单条
DELETE /gen/db/NODE  {"Assign":{"1":null}} → 200 {"NODE":{"1":..,"3":..}}  → 全空      🔴 清空整表
```

第二条的响应**回显了两条记录**（1 和 3），而请求里只有 id 1 ——
这是它**忽略 id、操作整表**的直接证据。
**Adapter 的单条删除只能走 `DELETE {endpoint}/{id}`。**

### 11.5.2 🔴 `/doc/EXPORT` 必须传裸字符串 —— 已实机确认

```
{"Argument": {"EXPORT_PATH": p}} → 200 {"message":"... path is wrong (the file can't open)"}  文件未写出
{"Argument": p}                  → 200 {"message":"... command complete"}                    写出 2769 字节
```

对象形式被拒却返回 **200**，且错误信息伪装成路径问题。**只看状态码必然误判。**

### 11.5.3 `POST` 是「仅创建」，不是 upsert

```
POST /gen/db/CNLD  （键已存在） → 400 {"error":{"message":"Key Already Exist"}}
```

更新必须用 `PUT`。Adapter 的 `upsert` 需自行实现「先 PUT / 先 POST」的次序。

### 11.5.4 `POST` 成功返回 201，并回显创建的记录

6 次建模 POST 全部返回 `201`。

### 11.5.5 ⚠️ 读回形态 ≠ 写入形态

服务端会补默认值并**归一化数组长度**：

| 表 | 写入 | 读回 |
|---|---|---|
| `/db/ELEM` | `"NODE": [1, 2]` | `"NODE": [1,2,0,0,0,0,0,0]`（补齐到 8）+ `"STYPE": 0` |
| `/db/MATL` | `{TYPE, NAME, PARAM}` | 追加 `HE_SPEC` `HE_COND` `PLMT` `P_NAME` `bMASS_DENS` `DAMP_RAT`；`PARAM[]` 内追加 `CODE` `bELAST` `ELAST` |
| `/db/CONS` | `{ID, CONSTRAINT}` | 追加 `GROUP_NAME: ""` |
| `/db/STLD` | `{NAME, TYPE, DESC}` | 追加 `NO: 1` |

**推论：不能用「读回结果」反推最小写入载荷**，两者必须分别建模。

### 11.5.6 `/post/TABLE` 的真实行为

| 发现 | 证据 |
|---|---|
| **`COMPONENTS` 是必需的** | 省略时返回 `200 {"message":""}`；带上后立刻返回数据 |
| **响应根键 = 传入的 `TABLE_NAME`** | 传 `"D"` → `{"D":{...}}`；传 `"Displacement"` → `{"Displacement":{...}}` |
| 结果表里工况名带 `(ST)` 后缀 | `["LC1(ST)"]` 命中；`["LC1"]` 返回空 |
| 错误 `TABLE_TYPE` → 400 + 错误体 | `there was an error creating utbl. (ex PostMode ...)` |
| **错误信息被服务端自己截断** | 上面那条 message 里的 `...` 是服务端截断，不是显示截断 |

### 11.5.7 `/doc/ANAL` 的两种请求体

```jsonc
POST /doc/ANAL   {}                                   // 一般分析 —— 裸空对象
POST /doc/ANAL   {"Argument": {"TYPE": "Pushover"}}   // 推覆分析
```

### 11.5.8 `/doc/ANAL` 会真正校验模型

移除支承后再分析：

```
400 {"error":{"message":"[错误] 边界条件 没有定义。"}}
```

所以 `{"message":"... command complete"}` 确实意味着**求解成功**，不是静默失败。

### 11.5.9 ⚠️ 错误信息是本地化的

上面那条是**中文**。**Adapter 不能只匹配英文字符串**，
错误识别必须覆盖中/英，或改用非文本判据。

### 11.5.10 两个意外好用的只读端点

| 端点 | 用途 | 实测 |
|---|---|---|
| `GET /ope/SECTPROP` | **截面属性计算结果** | `面积 0.360 m²`、`Iyy/Izz 0.0108 m⁴`——可直接校验截面定义 |
| `GET /ope/PROJECTSTATUS` | **模型清单**（中文标签） | 逐项计数，可作建模完成度断言 |

> `POST /ope/SECTPROP` 返回 `400 {"error":{"message":"Unknown Error"}}`——**它是 GET**。

---

### 11.5.11 ⚠️ 同一个 `/doc/ANAL`，两种模型问题、两种失败形态

实机对比（同一个 Gen NX 实例）：

| 模型问题 | 应答 | 形态 |
|---|---|---|
| **没有边界条件** | `400 {"error":{"message":"[错误] 边界条件 没有定义。"}}` | 4xx + `error` 键 + **中文** |
| **模型为空（无单元）** | `200 {"message":"MIDAS GEN NX Analysis is not allowed."}` | **2xx** + 无 `error` 键 + **英文** |

**两条都要防**：

- 只看状态码 → 空模型会被判成「分析成功」，随后取结果才报
  `400 [D] Cannot generate table data as there is no analysis result.`
- 只看 `error` 键 → 漏掉空模型这一路
- 只匹配英文 → 漏掉边界条件那一路；只匹配中文 → 漏掉空模型那一路

**因此 §3.5 第 2/7 条的分层判据是必需的**，而不是「保险起见多查一层」：
本项目的适配器正是靠它把上面第二条判成了 `MIDAS_CALCULATION_ERROR`，
任务记录里保留了完整的 `error_message`（实测见 §11.7 的任务持久化验收）。

> **推论**：`command complete` 之外的所有 `message` 都必须当作可疑信号，
> 无论状态码是 200 还是 400。

### 11.5.12 ⚠️ 「项目未打开」是一个**独立状态**，且可由 API 自行恢复

实测：把实例里的项目关掉后，**任何数据调用**都会失败，而失败形态与以往记录的都不同：

```
GET  /gen/db/UNIT   -> 400 {"error":{"message":"The project is not opened"}}
```

要点：

- **它不是连接问题。** HTTP 通了、`MAPI-Key` 有效、`/mapikey/verify` 正常 ——
  缺的是**模型**。总纲 §4.4.6 的 `MODEL_UNAVAILABLE`（503 模型不可用）才是它的语义；
  泛化的 `MIDAS_API_ERROR`（502 上游错误）虽然不算错，但对调用方**毫无可操作性**：
  前者告诉它「去新建/打开一个模型」，后者只告诉它「上游出错了」。
  适配器的文本标记表已按此归类（`project is not opened` → `MODEL_UNAVAILABLE`）。
- **它是可恢复的，且恢复手段就在 API 里**：

  ```
  POST /gen/doc/NEW   {}          -> 200 {"message":"MIDAS GEN NX command complete"}
  GET  /gen/db/UNIT               -> 200 {"UNIT":{"1":{...}}}      # 已恢复
  GET  /gen/ope/PROJECTSTATUS     -> 全部计数为 0                   # 全新空项目
  ```

  `/doc/NEW` 在无项目状态下**立即返回**，不会阻塞会话 —— 这与 §3.5 第 11 条
  原先的记载相反，该条已订正。
- **但它会丢弃未保存的工作**（§3.5 第 4 条，高风险操作）。所以「未打开项目」
  可以自动恢复，「有未保存改动」不可以 —— 两者必须区分对待。
- `/ope/PROJECTSTATUS` 是**判断该状态的廉价探针**：它返回各类对象的计数，
  在项目未打开时会失败，在项目打开时给出节点/单元/材料/荷载工况等数量。
  比读一张具体的表更适合做「会话里到底有没有模型」的判据。

> **对活性探针的影响**：§2.5.4 规定用真实数据调用（`/db/UNIT`）探测被阻塞的会话，
> 这条依然成立 —— 本次正是它发现了「项目未打开」。但排障时要多分一类：
> **探针失败可能是会话被阻塞，也可能只是没有打开项目**，两者的处置完全不同。
### 11.5.13 🔴 `/doc/SAVE` 对「从未保存过」的文档会弹「另存为」，并阻塞整条会话

**事故记录（本项目实测）**：在 `/doc/NEW` 新建的空项目上调用 `POST /doc/SAVE`，
NX 无处可写，于是**弹出「另存为」模态对话框**。后果不是「这次调用失败」，而是：

```
GET /gen/db/UNIT          -> curl 000（超时，无任何响应）
GET /gen/ope/PROJECTSTATUS-> curl 000
GET /mapikey/verify       -> curl 000     ← 连不碰文档的端点也超时
```

**整条 API 会话被冻结，只能人工在 NX 主机上关闭对话框。** 一次 pytest 运行因此
挂起数分钟，且没有任何超时能救——服务端根本没在处理请求。

要点：

- 这是 §3.5 第 6 / 13 条那类陷阱的**第三种触发方式**。前两种是「路径不存在」和
  「路径受保护（Program Files）」，这一种是**根本没给路径**，由上游自己弹窗去问。
- **它无法被自动检测或自动恢复。** 超时后重试只会继续撞在同一个对话框上；唯一的
  处置是人工介入。所以它必须**在发出请求之前**被拦下。
- 因此 `doc_save()` 现在要求显式 `confirm=True`，与 `/doc/NEW` 同一形状。
  **已知保存路径时应改用 `/doc/SAVEAS` 带显式路径**——那种形式永远不需要问。
- 判据：`/doc/SAVE` 只在**文档已保存过**时安全。新建项目、`/doc/NEW` 之后、
  或任何不确定文档来源的场景，都不满足这个前提。

> **推论（对活性探针）**：§2.5.4 的 `/db/UNIT` 探针确实能发现会话被冻结——本次正是
> 它发现的。但要注意它的**盲区**：探针自己也会超时，此时「会话被阻塞」与「实例
> 没开项目」与「服务没起来」三者都表现为超时，必须结合 `/mapikey/verify`
> 是否也超时来区分（本次连它都超时，故判定为会话级冻结）。
### 11.5.14 ⚠️ 服务端**无法**区分「会话冻结」与「网络黑洞」——不要假装能

§11.5.13 记录了模态对话框冻结整条会话的事故，随后我们给适配器加了会话诊断。
但把诊断放到**不可达主机**上实测时，它给出了与冻结**完全相同**的判定，并建议
「派人去 NX 主机上关对话框」——**而真实原因是网络不通。补救措施是错的，这比没有
诊断更糟。**

实测（本机，httpx 0.28.1）：

| 目标 | 原始 TCP 连接 | HTTP 层异常 | 耗时 |
|---|---|---|---|
| 真实实例 | 成功 | HTTP 200 | 0.21s |
| 端口关闭 | **失败**（ConnectionRefused） | `ConnectError` | 2.33s |
| `192.0.2.1`（RFC 5737） | 成功 | `RemoteProtocolError` | 0.27s |
| `198.51.100.1`（RFC 5737） | 成功 | `RemoteProtocolError` | 0.26s |
| `203.0.113.1`（RFC 5737） | 成功 | `RemoteProtocolError` | 0.24s |
| `10.255.255.1`（黑洞） | 成功 | **`ReadTimeout`** | 5.19s |

两条结论：

1. **黑洞目标抛的是 `ReadTimeout`，不是 `ConnectTimeout`。** 所以
   `phase == "read"` 只说明「请求发出去了、没等到响应」，而**网络路径死掉也是这个样子**。
2. **原始 TCP 探测救不了这个区分。** RFC 5737 地址保证不可路由，可 TCP 连接却在
   **0.00 秒「成功」** —— 这台机器上有中间层（代理 / 防火墙 / 安全软件）接受了所有
   出站连接。所以「TCP 连上了 ⇒ 对面有东西在监听」在本环境下**是假的**。

**因此：从服务端看，`session_frozen` 与「网络黑洞」是真正不可区分的。** 诊断必须
报告**观测到的事实**，并列出候选原因，而不是断言其中之一。

可证明与不可证明的分界：

| 观测 | 判定 | 是否已证实 |
|---|---|---|
| `verify` 在**连接阶段**失败 | `service_down` | ✅ 没有任何东西接受连接 |
| `verify` 正常 + `unit` 报「项目未打开」 | `no_project` | ✅ 会话在应答 |
| `verify` 正常 + `unit` 读超时 | `document_frozen` | ✅ `/mapikey/verify` 成功即证明会话在应答，故阻塞在文档层 |
| **两个探针都读超时** | `session_unresponsive` | ❌ **不可区分**：模态对话框 或 网络黑洞 |
| `401` | `auth_failed` | ✅ |

`session_unresponsive` 仍然给出**有用的两半**：`requires_human = True`、
`retry_helps = False` —— 两种候选都需要人工、且**都不会因为重试而好转**。
但它的 `remedy` 必须给出**判别步骤**（先看 NX 主机上有没有对话框，再从服务所在机器
确认网络可达性），而**不得**断言对话框就是原因。

> **一般教训**：当观测不足以支撑结论时，正确的做法是把状态命名为**观测到的现象**
> （`session_unresponsive`）并列出候选，而不是命名成我们**猜测的原因**
> （`session_frozen`）。后者会在错误的那一半情况下给出错误且有害的处置建议。
### 11.5.15 🔴 三产品并列时「静默走错产品」——路由方向必须是「实例 → 适配器 → 能力」

**背景。** 为验收多产品路由框架（总纲 §4.9），同时注册 Gen / Civil NX / Civil Designer
三个实例（§11.1.2），观察同一能力 `midas_query target=node action=list` 的落点。

**实测（修复前）：**

| 注册情况 | 调用 | 结果 |
|---|---|---|
| 只 Gen | 不指定 adapter | `success=True` |
| **只 Civil** | 不指定 adapter | **`ADAPTER_NOT_FOUND`**（去找 `midas_gen`） |
| **只 Designer** | 不指定 adapter | **`ADAPTER_NOT_FOUND`** |
| **三个都注册** | **不指定 adapter** | **`success=True` —— 静默走了 Gen** |
| 三个都注册 | `adapter=midas_civil` | `CAPABILITY_NOT_SUPPORTED` |

**根因**：`adapter.code` 是**产品派生**的（`f"midas_{product.value}"`），而全部
155 个非平台能力把 `adapter_code` **硬编码为 `'midas_gen'`**，且能力表**只按 `code` 键控**。

**第四行是最危险的一条**：调用方以为在操作 Civil，实际读写了 **Gen 的模型**，
而且 `success=True` —— **没有任何提示**。报错会被发现，静默走错不会。

**修复后（实测验收）：**

| 注册情况 | 调用 | 结果 |
|---|---|---|
| 只 Gen | 不指定 | `success=True` |
| 只 Civil | 不指定 | `CAPABILITY_NOT_SUPPORTED`（适配器**已找到**，缺 civil 能力行） |
| 只 Designer | 不指定 | 同上 |
| **三个都注册** | **不指定** | **`VALIDATION_ERROR`（歧义，拒绝并列出可选项）** |
| 三个都注册 | `adapter=midas_civil` | `success=True` |

**URL 级证明**（HTTP 传输层记录器，每次调用只触达自己的产品）：

```
adapter=midas_gen     -> GET http://localhost:3030/gen/db/NODE
adapter=midas_civil   -> GET https://moa-engineers.midasit.cn/civil/db/NODE
adapter=midas_cdn     -> GET https://moa-engineers.midasit.cn/cdn/db/NODE
```

**三条可复用的结论：**

1. **路由方向只能是「实例 → 适配器 → 能力」。** 反向（能力决定实例）在本项目
   产生了「静默走错产品」这一**数据损坏路径**。
2. **歧义必须拒绝，不得猜测。** 可用实例 `>1` 且调用方未指定时，猜测的代价是
   静默改错模型，拒绝的代价只是一次明确的报错。
3. **「每个适配器只触达自己的 URL」必须被测量，不能靠推断。** 回归的表现是
   「返回另一个产品的数据且 `success=True`」——只看信封抓不到，必须断言 URL。

> 完整方案见 `docs/多产品多租户路由框架_v1.0.md`；裁决见总纲 §4.9。
## 11.6 ✅ 已解决：位移为零是建模错误，不是 MIDAS 异常

### 根因：`/db/CNLD` 的 `Assign` 外层键才是节点号

手册写得很明确（`06_DB_Static_Loads.md`）：

```python
cnld_data = {
    "Assign": {
        "8": {                 # ← 外层键 = 节点号
            "ITEMS": [{"ID": 1, # ← ID 是「序号」，Optional，默认 0
                       "LCNAME": "LL", "FZ": -50.0, ...}]}}}
```

参数表原文：`| (1) | Serial Number | "ID" | Integer | 0 | Optional |`

**我写成了外层键 `1` + `ITEMS[].ID = 2`，于是荷载加到了节点 1（固定端）。**
这一条同时解释了当时观察到的**全部四个现象**：

| 现象 | 解释 |
|---|---|
| 反力 FX = −10000 kN（正确） | 荷载直接进了支座 |
| **反力 MY = 0** | 力臂为 0——荷载就在固定节点上 |
| 单元内力全零 | 荷载不经过单元 |
| 位移全零 | 荷载加在已被约束的自由度上 |

**关键诊断判据**：固定端悬臂受侧向力，**弯矩反力不可能为零**。
我第一次查反力时只要了 `MZ`，而这个悬臂的弯矩是绕 Y 的（`MY`），
漏掉了这条判据。补上 `MY` 后立刻定位——**这是本次排障的转折点**。

### 修正后的端到端验证（全部精确吻合）

```jsonc
{"Assign": {"2": {"ITEMS": [{"ID": 1, "LCNAME": "LC1", "GROUP_NAME": "",
                             "FX": 10000.0, "FY": 0, "FZ": 0,
                             "MX": 0, "MY": 0, "MZ": 0}]}}}
```

| 量 | 解析解 | 实测 | |
|---|---|---|---|
| 顶点位移 DX | 335.999 mm | **3.359993e+02 mm** | ✅ |
| 顶点转角 RY | 0.157497 rad | **1.574997e-01 rad** | ✅ |
| 柱底弯矩 MY | 32000 kN·m | **3.200000e+07**（kN·mm） | ✅ |
| 单元剪力（沿全长） | 10000 kN | **1.000000e+04** | ✅ |
| 弯矩图 I→1/4→2/4→3/4→J | 32000→24000→16000→8000→0 | **3.2e7→2.4e7→1.6e7→8.0e6→0** | ✅ |

> **结论：API 建模 → 运行分析 → 取结果 全链路可用，
> 数值与闭式解在 6 位有效数字上一致。**
> 之前记为「未决异常」的问题已完全澄清。

### 由此得到的最重要规律：`Assign` 外层键的语义随端点而异

**这是最容易踩的坑，也是本规范 §4 所说的「载荷形状异构」的最隐蔽形态。**

| 端点 | 外层键含义 | 内层结构 |
|---|---|---|
| `/db/NODE` | 节点号 | 坐标字段 |
| `/db/ELEM` | 单元号 | 单元字段 |
| **`/db/CNLD`** | **节点号** | `ITEMS[]` = **该节点上的各工况荷载**；`ID` 只是序号 |
| `/db/CONS` | 约束组号 | `ITEMS[]` = 各节点及其约束 |
| `/db/STLD` | 工况号 | 工况字段 |

**「外层键 = 该端点的主实体号」这个直觉，在 `CNLD` 上会把人带偏**：
外层键是节点号，而内层又有一个看起来像 ID 的 `ITEMS[].ID`。
**Adapter 必须逐端点保存并校验外层键语义，不能假设统一。**

> **建议**：`tool_interfaces.metadata_json` 增加一个字段
> `"outer_key_means": "node" | "element" | "load_case" | "group" | "self"`，
> 把这条语义变成数据，而不是散落在 Adapter 代码里的注释。

### 顺带确认：手册的 DELETE 示例是危险的

手册的 CNLD 示例用 `DELETE /db/CNLD {"Assign": {"8": {}}}` 删节点 8 的荷载。
但 §11.5.1 已实机证明**带 `Assign` 体的 DELETE 会清空整表**——
**照抄这个示例会误删全部节点荷载。** 正确做法是 `DELETE /db/CNLD/8`。

### 方法论教训（写给后续排障）

1. **先看反力的完整六分量**，不要只取自己以为需要的那几个——
   我漏掉 `MY` 直接导致多花了数轮。
2. **力学自洽性是最好的判据**：反力正确而内力全零，在静定结构里是不可能的。
   出现这种组合时，第一嫌疑是**荷载加错了位置**，而不是软件 bug。
3. **手册的参数表要逐行读**，尤其是 `ID` 这类看起来显然的字段——
   它的 Description 只有 `" ID"`，真正的语义（Serial Number）写在参数表的 Description 列里。

# 附录 A — 端点总表

由 `docs/api-registry/merge_registry.py` 合并 `part-*.json` 后生成：

- `docs/api-registry/midas_api_registry.json` —— 机器可读注册表
- `docs/api-registry/ENDPOINT_INDEX.md` —— 人读端点表

**注意：** 该注册表字段名逐字取自 MIDAS 官方 JSON Manual，**不含实机观测结论**。

# 附录 B — 依据文件

| 文件 | 用途 |
|---|---|
| `MIDAS-API-main/README.md` | 架构、端点概览、快速开始 |
| `MIDAS-API-main/docs/AUTHENTICATION.md` | 认证、`/mapikey/verify`、防火墙、`/info/db` 自省 |
| `MIDAS-API-main/docs/manual/INDEX.md` | 27 章全端点索引 |
| `MIDAS-API-main/docs/manual/01..27_*.md` | 逐端点 JSON Schema |
| `MIDAS-API-main/docs/plugin/INDEX.md` | 61 个原生 Plug-in 目录 |
| `MIDAS-API-main/docs/plugin/guide/03,04` | Plug-in 技术栈与开发方式 |
| `MIDAS-API-main/examples/python/*.py` | 官方调用范式与载荷形状实例 |
