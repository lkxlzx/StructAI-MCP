# Official MIDAS API Online Manual — 2026-09-20 Source Audit

## 权威源

https://support.midasuser.com/hc/en-us/articles/33016922742937-MIDAS-API-Online-Manual

官方页面当前显示：Created May 28, 2024；Edited July 14, 2026 10:11。

## 与旧镜像/旧章节的关键差异

### 新增 / 遗漏 DB

```text
/db/GALD   Grid Analysis Load   Civil NX JP only
/db/HHND   Heat of Hydration Result Graph
```

### OPE 正确 endpoint

```text
/ope/STORPROP
```

不要使用旧文档中的 `STORYPROP`。

### 官方当前 Analysis Result 还包含

```text
Effective Span Length
Nodal Results of RS
Element Properties at Each Stage
Beam Section Properties at Last Stage
Lack of Fit Force - Truss
Lack of Fit Force - Beam
Lack of Fit Force - Plate
Equilibrium Element Nodal Force
Initial Element Force
Resultant Force
```

### 官方当前 Time History Result 还包含 JP-only Fiber Section

```text
Estimate Yield Strength
Elastic Modulus Retention Rate
Maximum Strain of The Cell
Event Step
Average Compression Strain
```

### 官方当前 Heat of Hydration Result Table

```text
Stress Local / Global
Temperature
Displacement
Tensile Stress
Pipe Cooling Nodal Temperature
```

### 官方当前 Analysis Story Table

```text
Story Drift
Story Displacement
Story Shear (R.S.)
Story Shear Force Coefficient (R.S.)
Story Mode Shape
Story Shear Force Ratio
Story Eccentricity
Overturning Moment
Story Axial Force Sum
Story Stability Coefficient
Torsional Irregularity Check
Torsional Amplification Factor
Stiffness Irregularity Check
Capacity Irregularity Check
Criteria for Regularity in Plan
Ultimate Story Shear For Check
Weight Irregularity Check
```

## Registry 原则

最终 Registry 必须按“逻辑操作”而不是章节数量构建，并记录：

```text
key
namespace
uri
methods
selector_field
selector_value
wrapper
product
variant
source_url
source_title
```

优先级：

```text
官方主手册
  > 官方二级页面
  > 本地 Registry
  > 镜像/生成文档
```

JP-only、Hyper-S-only 必须明确登记 variant，不能假设所有 Civil/Gen API 都通用。
