# 角色设定
你是本项目的产品设计专家，精通数据看板类页面的信息架构与交互设计。你擅长在「列表展示」「详情弹窗」「筛选条件」之间合理分配字段，兼顾信息密度与可读性。你熟悉多表关联场景下的数据展示与查询设计。

# 任务目标
请输出一份 Markdown 格式的 **详细执行历史页面字段规约扩展（Spec）**，不要写任何代码。该规约是**增量规约**，在现有 `spec/02_history_fields_spec.md` 基础上，补充「跟踪人」与「失败原因」两个关联字段的展示与筛选设计。该规约将作为后续 AI 编程的契约。

# 输入信息

## 1. 现有规约（必读）
请先阅读 `spec/02_history_fields_spec.md`，了解当前表格列、Drawer 分区、筛选字段的完整定义。本次输出是在该规约基础上的**扩展**，需保持与现有字段的命名、格式、分区结构一致。

## 2. 新增数据源：pipeline_failure_reason 表

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int(11) PK | 自增主键 |
| case_name | varchar(255) | 用例名称 |
| failed_batch | varchar(200) | 失败轮次 |
| owner | varchar(100) | **失败用例跟踪人**（注意：与 pipeline_history.owner「用例开发责任人」语义不同） |
| failed_type | varchar(100) | **失败原因分类** |
| reason | text | 详细失败原因 |
| platform | varchar(255) | 用例平台 |
| analyzer | varchar(255) | 失败原因分析人 |
| dts_num | varchar(255) | dts 单号 |
| recover_batch | varchar(200) | 恢复轮次 |
| created_at / updated_at | datetime | 创建/更新时间 |

## 3. 表关联关系

`pipeline_history` 与 `pipeline_failure_reason` 描述同一条执行记录时，满足以下三元组相等：

| pipeline_history 字段 | pipeline_failure_reason 字段 | 说明 |
|----------------------|-----------------------------|------|
| case_name | case_name | 用例名称 |
| start_time | failed_batch | 轮次/批次标识 |
| platform | platform | 平台名称 |

即：`(case_name, start_time, platform)` 与 `(case_name, failed_batch, platform)` 一一对应时，表示同一条执行记录。

**业务语义：** 仅当 `pipeline_history.case_result = 'failed'` 时，才可能有对应的 `pipeline_failure_reason` 记录；passed 用例通常无关联记录。关联关系为 **0 或 1**（一条执行记录最多对应一条失败原因记录）。

## 4. 本次需规约的字段

| 来源表 | 字段名 | 业务含义 | 本次规约目标 |
|--------|--------|----------|--------------|
| pipeline_failure_reason | owner | 失败用例跟踪人 | 在详细执行历史表格中展示 |
| pipeline_failure_reason | failed_type | 失败原因分类 | 在详细执行历史表格中展示 |

**命名区分：** 为避免与 `pipeline_history.owner`（用例开发责任人）混淆，规约中需明确区分：
- `pipeline_history.owner` → 展示为「用例开发责任人」
- `pipeline_failure_reason.owner` → 展示为「跟踪人」或「失败跟踪人」

## 5. 数据获取方式（供规约参考）

需求方提出：是否可以不使用 JOIN 方式查询，而采用其他方式（如分两次查询、应用层合并等）。

请你在规约中**单独增加一节「数据获取策略」**，对以下两种方案进行对比分析，并给出推荐方案及理由：

- **方案 A：SQL JOIN**  
  在 Service 层使用 `LEFT JOIN pipeline_failure_reason`，一次查询返回主表 + 关联字段。需考虑：无匹配记录时 owner、failed_type 为 null 的展示策略。

- **方案 B：分步查询 + 应用层合并**  
  先查询 `pipeline_history` 分页结果，再根据结果集中的 `(case_name, start_time, platform)` 批量查询 `pipeline_failure_reason`，在应用层合并到每条记录。需考虑：N+1 避免、批量查询的 IN 条件构建。

规约需明确：**推荐采用哪种方案**，并简要说明对分页、性能、代码复杂度的影响。该节作为实现阶段的参考，不约束最终实现，但需给出清晰建议。

# 规约必须明确界定的内容

1. **表格列扩展**  
   在现有表格列清单中，新增「跟踪人」「失败原因」两列。需说明：列标题、dataIndex（建议使用 `failure_owner`、`failed_type` 等与主表字段区分的命名）、列宽、渲染方式（纯文本 / Tag / 空值展示策略）。

2. **Drawer 扩展**  
   是否在 Drawer 中展示这两个字段？若展示，放在哪个分区（建议：新增「失败归因区」或并入「基本信息区」）？需说明展示形式及空值策略。

3. **筛选扩展**  
   是否将「跟踪人」「失败原因」纳入筛选条件？若纳入，需说明：筛选控件类型、选项来源（如从 `pipeline_failure_reason` 去重）、与主表筛选的联动关系（例如：仅当 case_result=failed 时，这两个筛选才生效，或始终展示但无匹配时为空）。

4. **空值策略**  
   当某条 `pipeline_history` 记录无对应 `pipeline_failure_reason` 时（如 passed 用例、或尚未录入失败原因），跟踪人、失败原因应如何展示？建议：显示「—」或「暂无」，需在规约中明确。

5. **字段复用说明表更新**  
   在现有「字段复用说明」表中，新增这两列的：表格列 ✓/—、Drawer ✓/—、筛选 ✓/—。

# 格式要求

请以如下结构输出 Spec（可整体输出，作为 `spec/03_history_failure_reason_spec.md` 的初稿）：

```
# 详细执行历史页面 - 跟踪人与失败原因字段规约（扩展 Spec）

本文档在 `spec/02_history_fields_spec.md` 基础上，补充 pipeline_failure_reason 关联字段的展示与筛选规约。

## 1. 数据获取策略（实现参考）

[方案 A vs 方案 B 对比分析，推荐方案及理由]

## 2. 表格列扩展

| 字段名 | 列标题 | dataIndex | 列宽 | 渲染方式 |
| failure_owner | 跟踪人 | ... | ... | ... |
| failed_type | 失败原因 | ... | ... | ... |

## 3. Drawer 扩展

[若需在 Drawer 中展示，说明分区与展示形式]

## 4. 筛选扩展

[若需纳入筛选，说明控件类型、选项来源、联动关系]

## 5. 空值策略

[无关联记录时的展示规则]

## 6. 字段复用说明（增量）

| 字段 | 表格列 | Drawer | 筛选 |
| failure_owner | ✓/— | ✓/— | ✓/— |
| failed_type | ✓/— | ✓/— | ✓/— |
```

# 约束与原则

- 表格列不宜过多，若现有列已较多，可评估「跟踪人」「失败原因」是否更适合仅在 Drawer 中展示，或采用「表格简化 + Drawer 详情」的折中方案。
- 筛选条件若涉及关联表，需考虑后端 API 的查询能力（如对 pipeline_failure_reason 的 EXISTS 子查询或 JOIN 条件）。
- 所有用户可见文字使用中文。
- 规约需与 `spec/02_history_fields_spec.md` 的表格结构、Drawer 分区、筛选清单保持风格一致，便于后续合并或引用。
