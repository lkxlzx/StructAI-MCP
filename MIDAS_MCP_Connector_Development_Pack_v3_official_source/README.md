# MIDAS MCP Connector Development Pack v2

## 目录

```text
api_chapters/
  01_DOC.md
  02_DB_Project_Structure.md
  03_DB_Node_Element.md
  04_DB_Properties.md
  05_DB_Boundary.md
  06_DB_Static_Loads.md
  07_DB_Temperature_Prestress.md
  08_DB_Moving_Loads.md
  09_DB_Dynamic_Loads.md
  10_DB_Construction_Stage.md
  11_DB_Settlement_Misc_Loads.md
  12_DB_Analysis_Control.md
  13_DB_Load_Combinations.md
  14_DB_Pushover.md
  15_OPE.md
  16_VIEW.md
  17_DB_Bridge.md
  18_POST_PreProcess.md
  19_POST_AnalysisResult_1.md
  20_POST_AnalysisResult_2.md
  21_POST_StoryTables.md
  22_POST_TH_HY_Pushover.md
  23_POST_Design.md
  24_DB_Design.md
  25_Design_Steel_KDS41302022.md
  26_Design_RC_KDS41202022.md
  27_Design_SRC_AIKSRC2K.md

mcp/
  01_PROTOCOL.md
  02_ARCHITECTURE.md
  03_TOOLS.md
  04_HTTP.md
  05_TEST_MATRIX.md
  06_LLM_ROUTING.md

registry/
  registry.schema.md

examples/
  01_modeling_to_analysis.md
```

## 设计目标

- MCP 对 LLM 只暴露 4 个泛化 Tool。
- MIDAS 全部二级 API 通过内部 Endpoint Registry 映射。
- DB 使用 `Assign`。
- Action / POST 使用 `Argument`。
- POST/TABLE 通过 `TABLE_TYPE` 映射。
- POST/TEXT 通过 `TEXT_TYPE` 映射。
- 删除必须显式指定目标。
- MAPI-Key 永不暴露给模型。

## 官方源

https://support.midasuser.com/hc/en-us/articles/33016922742937-MIDAS-API-Online-Manual

## 二级同步源

https://github.com/Dennis5882/MIDAS-API/tree/main/docs/manual

> 说明：本 v2 将文档按章节/功能拆开。二级章节内的具体字段以该章节对应的官方二级页面为最终事实源；MCP 层只依赖 Registry。
