# 详细执行历史页面 - 跟踪人与失败原因字段规约（扩展 Spec）

本文档在 `spec/02_history_fields_spec.md` 基础上，补充 `pipeline_failure_reason` 关联字段的展示与筛选规约。

---

## 1. 数据获取策略（实现参考）

### 1.1 方案对比

| 维度 | 方案 A：SQL JOIN | 方案 B：分步查询 + 应用层合并 |
|------|------------------|------------------------------|
| **实现方式** | Service 层使用 `LEFT JOIN pipeline_failure_reason ON (ph.case_name = pfr.case_name AND ph.start_time = pfr.failed_batch AND ph.platform = pfr.platform)` | 先查 `pipeline_history` 分页结果，再根据结果集中的 `(case_name, start_time, platform)` 批量查 `pipeline_failure_reason`，应用层合并 |
| **分页** | 天然支持，一次查询即得完整分页数据 | 分页逻辑不变，但需在合并后保证分页边界正确（主表分页，关联数据按主表 ID 映射） |
| **性能** | 单次 SQL，数据库优化 JOIN；无匹配时 LEFT JOIN 返回 null | 两次查询；需避免 N+1，批量 IN 条件如 `(case_name, failed_batch, platform) IN ((...), (...), ...)` 或按 id 批量查 |
| **代码复杂度** | 较低，ORM 一次查询，Schema 扩展关联字段即可 | 较高，需维护批量查询逻辑、结果映射、空值填充 |
| **空值处理** | 无匹配时 `failure_owner`、`failed_type` 为 null，前端统一展示「—」 | 同上，应用层合并时对无匹配记录填充 null |
| **扩展性** | 若后续需展示 `reason`、`analyzer` 等更多字段，仅扩展 SELECT 即可 | 需同步扩展批量查询与合并逻辑 |

### 1.2 推荐方案及理由

**推荐采用方案 A：SQL JOIN。**

理由：
1. **分页一致性**：分页基于 `pipeline_history`，JOIN 方式天然保证每条主表记录对应 0 或 1 条关联记录，无需额外处理分页边界。
2. **实现简单**：一次查询即可返回完整数据，Schema 与 Service 层改动集中、易维护。
3. **性能可接受**：关联条件 `(case_name, start_time, platform)` 在 `pipeline_history` 上已有索引 `idx_casename_platform_batch`，`pipeline_failure_reason` 有 `idx_pfr_failedbatch_case`，JOIN 效率可接受；且失败记录占比通常低于全部记录，关联表数据量相对可控。
4. **扩展友好**：后续若需展示 `reason`、`analyzer` 等字段，仅扩展 SELECT 列表即可。

方案 B 适用于：主表与关联表数据量极大、JOIN 成为瓶颈，或关联表在异构数据源等场景。当前单库、表规模可控，优先选用 JOIN。

---

## 2. 表格列扩展

在现有表格列清单中，新增以下两列。建议插入位置：在「执行结果」列之后、「用例级别」之前，便于用户快速定位失败用例的归因信息。

| 字段名 | 列标题 | dataIndex | 列宽 | 渲染方式 |
|--------|--------|-----------|------|----------|
| failure_owner | 跟踪人 | failure_owner | 100 | 纯文本，无值时显示「—」 |
| failed_type | 失败原因 | failed_type | 140 | 纯文本，ellipsis 省略，无值时显示「—」 |

**说明：**
- `failure_owner`、`failed_type` 与主表 `owner` 区分命名，避免与「用例开发责任人」混淆。
- 两列仅在有关联 `pipeline_failure_reason` 记录时有值；passed 用例或尚未录入失败原因时，统一显示「—」。
- `failed_type` 列宽 140px，内容过长时 ellipsis 省略，悬停可考虑 Tooltip 展示完整内容（可选，由实现阶段决定）。

---

## 3. Drawer 扩展

### 3.1 新增「失败归因区」

在 Drawer 中新增 **失败归因区**，置于「基本信息区」与「外部链接区」之间。该区仅当 `case_result = 'failed'` 或 `case_result = 'error'` 时展示；当 `case_result` 为 passed 等其他值时，整个失败归因区不渲染。

| 字段名 | 展示名称 | 展示形式 |
|--------|----------|----------|
| failure_owner | 跟踪人 | 纯文本，无关联记录时显示「—」 |
| failed_type | 失败原因 | 纯文本，无关联记录时显示「—」 |
| reason | 详细原因 | 长文本，无关联记录或内容为空时显示「—」 |
| failure_analyzer | 分析人 | 纯文本，无关联记录时显示「—」 |
| analyzed_at | 分析时间 | 纯文本，展示为「YYYY-MM-DD HH:mm:ss」，无关联记录或时间为空时显示「—」 |

**说明：**
- 失败归因区与基本信息区中的「用例开发责任人」明确区分：前者为 `pipeline_failure_reason.owner`（失败跟踪人），后者为列表接口响应中的 `owner` 字段，由 `main_module` 关联 `ums_module_owner`（必要时补 `ums_email`）拼接姓名+工号，**不是**直接读取 `pipeline_history.owner` 列。
- 展示顺序固定为：**跟踪人 → 失败原因 → 详细原因 → 分析人 → 分析时间**。
- `reason` 对应 `pipeline_failure_reason.reason` 字段，用于展示详细失败原因。前端展示需保留原始文本中的换行和缩进（建议使用 `white-space: pre-wrap`），空值时统一展示为「—」。
- 详细原因区域默认采用固定高度（约等于 3 行文本）+ 内部滚动的方式展示，当内容超出高度时允许纵向滚动查看全部内容。
- 详细原因区域应提供「展开 / 收起」能力：收起时使用固定高度预览（约 3 行），展开时放宽高度限制，便于查看更多内容；再次收起时恢复到预览高度。
- `failure_analyzer` 来自 `pipeline_failure_reason.analyzer`，表示失败原因分析人。
- `analyzed_at` 为分析时间字段（具体字段名可与实现对齐），建议展示格式为「YYYY-MM-DD HH:mm:ss」，无值时统一展示为「—」。

---

## 4. 筛选扩展

### 4.1 纳入筛选

将「跟踪人」「失败原因」纳入筛选条件，便于按失败归因维度快速定位记录。

| 字段名 | 筛选控件类型 | 是否必选 | 默认值策略 | 选项来源 | 备注 |
|--------|--------------|----------|------------|----------|------|
| failure_owner | 下拉单选 | 否 | 空（查全部） | 从 `pipeline_failure_reason.owner` 去重 | 支持多选时可考虑，本次建议单选 |
| failed_type | 下拉单选 | 否 | 空（查全部） | 从 `pipeline_failure_reason.failed_type` 去重 | 同上 |

### 4.2 联动关系

- **展示策略**：筛选控件**始终展示**，不随「执行结果」筛选变化而隐藏。当用户选择「跟踪人」或「失败原因」时，后端需在 `pipeline_failure_reason` 上施加 EXISTS 子查询或 JOIN 条件；若无匹配的 `pipeline_history` 记录，则结果集为空，属预期行为。
- **与主表筛选关系**：两个筛选与主表筛选（如 `case_result`、`platform` 等）为 AND 关系，可组合使用。例如：`case_result=failed` + `failure_owner=张三` 表示「失败且跟踪人为张三」的记录。
- **URL 同步**：筛选条件需同步到 URL 查询参数，支持 deeplink。

### 4.3 后端实现要点

筛选需支持对 `pipeline_failure_reason` 的关联查询，可采用：
- **JOIN 方式**：在 WHERE 中增加 `AND pfr.owner = :failure_owner`、`AND pfr.failed_type = :failed_type`（参数有值时生效）；
- **EXISTS 子查询**：`EXISTS (SELECT 1 FROM pipeline_failure_reason pfr WHERE ... AND pfr.owner = :failure_owner)`。

选项接口：需提供「跟踪人」「失败原因」的去重选项接口，可从 `pipeline_failure_reason` 表 `SELECT DISTINCT owner`、`SELECT DISTINCT failed_type` 获取，排除空值。

---

## 5. 空值策略

当某条 `pipeline_history` 记录**无对应** `pipeline_failure_reason` 时（如 passed 用例、或 failed 但尚未录入失败原因），统一采用以下策略：

| 场景 | failure_owner | failed_type |
|------|---------------|-------------|
| 无关联记录 | 显示「—」 | 显示「—」 |
| 有关联记录但字段为空 | 显示「—」 | 显示「—」 |
| 有关联记录且字段有值 | 显示实际值 | 显示实际值 |

**说明：** 前端与后端约定：`failure_owner`、`failed_type` 为 `null` 或空字符串时，统一渲染为「—」，不区分「无记录」与「记录存在但字段为空」。

---

## 6. 字段复用说明（增量）

在 `spec/02_history_fields_spec.md` 的「字段复用说明」基础上，新增以下两行：

| 字段 | 表格列 | Drawer | 筛选 |
|------|--------|--------|------|
| failure_owner | ✓ | ✓ 失败归因区 | ✓ |
| failed_type | ✓ | ✓ 失败归因区 | ✓ |
| failure_analyzer | — | ✓ 失败归因区 | — |

**数据来源说明：** 以上两字段均来自 `pipeline_failure_reason` 表，通过 `(case_name, start_time, platform)` 与 `(case_name, failed_batch, platform)` 关联 `pipeline_history`。关联关系为 0 或 1。
