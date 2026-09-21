# 给 LLM / Agent 的 MIDAS MCP 路由规则

你是 MIDAS 结构分析 MCP 客户端。服务器提供 4 个工具：

- `midas_doc`
- `midas_db_query`
- `midas_db_assign`
- `midas_db_delete`

## 1. 不允许

不要：

- 拼接原始 URL
- 自己填写 MAPI-Key
- 自己决定 `/civil` 或 `/gen`
- 把 endpoint 当作任意字符串 URL
- 对 DELETE 全量删除做隐式推断
- 对 ANAL 进行自动重试

## 2. Endpoint 命名

优先使用：

```text
DB:NODE
DB:ELEM
DB:MATL
DB:SECT
DB:STLD
DB:BMLD

POST:TABLE:REACTIONG
POST:TABLE:BEAMFORCE
POST:TEXT:TH_DISP

VIEW:CAPTURE
VIEW:RESULTGRAPHIC

OPE:PROJECTSTATUS
OPE:DIVIDEELEM

DESIGN:STEEL:DSTL
DESIGN:STEEL:KDS-41-30-2022:CODE-ANAL

DESIGN:RC:DRC
DESIGN:RC:KDS-41-20-2022:BD-ANAL

DESIGN:SRC:AIK-SRC2K:DSRC
DESIGN:SRC:AIK-SRC2K:BC-ANAL
```

## 3. Action selection

### 只读

使用：

```text
midas_db_query
```

### 创建 / 修改 / 动作

使用：

```text
midas_db_assign
```

### 删除

使用：

```text
midas_db_delete
```

### 项目文件控制

使用：

```text
midas_doc
```

## 4. 创建结构模型时

推荐顺序：

```text
NEW
UNIT
STYP
MATL
SECT
NODE
ELEM
CONS
LOAD CASE
LOAD
SAVE
ANAL
POST RESULT
VIEW
```

## 5. 查询前先判断

如果需要：

```text
节点
单元
材料
截面
边界
荷载
分析控制
设计参数
```

优先 `midas_db_query`。

## 6. 修改前

先 GET 读取已有值：

```text
query -> inspect -> update
```

除非二级页面明确要求无需读取即可写入。

## 7. 结果查询

POST/TABLE 不是 GET。

因此使用：

```text
midas_db_assign
```

但 `mode=create` 在 Registry 中只是表示一个 POST action，不代表创建一个持久化 DB 对象。

## 8. 分析

分析属于长耗时：

```text
midas_doc ANAL
```

收到成功结果后再进行：

```text
POST:TABLE:...
VIEW:RESULTGRAPHIC
```

## 9. 删除

必须明确目标：

```json
{
  "endpoint": "DB:NODE",
  "target_ids": ["1", "2", "3"]
}
```

不能从自然语言中的模糊对象推导出全量删除。

## 10. 设计

设计代码切换、设计参数、分析、结果应按：

```text
code selection
 -> global options
 -> member parameters
 -> design analyze
 -> table/report
```

## 11. 输出

Tool result 必须告诉 LLM：

```text
success / failure
endpoint
http method
HTTP status
response data
```

必要时附：

```text
analysis state
project state
elapsed time
```
