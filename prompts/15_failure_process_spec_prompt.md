# 角色设定

你是本项目的产品设计专家，精通数据看板类页面的信息架构与交互设计。你擅长在「列表操作」「批量选择」「弹窗表单」之间合理分配交互流程，兼顾操作效率与数据一致性。你熟悉多表关联场景下的数据写入与更新设计。

# 任务目标

请输出一份 Markdown 格式的 **失败记录标注功能规约（Spec）**，不要写任何代码。该规约是**增量规约**，在现有 `spec/02_history_fields_spec.md`、`spec/03_history_failure_reason_spec.md` 基础上，补充「失败记录标注」的完整交互流程与数据变更设计。该规约将作为后续 AI 编程的契约。

# 输入信息

## 1. 现有规约（必读）

请先阅读以下文件，了解当前页面结构：

- `spec/02_history_fields_spec.md`：表格列、Drawer 分区、筛选字段
- `spec/03_history_failure_reason_spec.md`：跟踪人、失败原因等关联字段的展示与筛选

本次输出是在上述规约基础上的**扩展**，需保持与现有字段命名、格式、分区结构一致。

## 2. 相关数据表结构

### pipeline_history（执行记录主表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int(11) PK | 自增主键 |
| start_time | varchar(50) | 轮次（等同于 batch） |
| subtask | varchar(100) | 组别 |
| case_name | varchar(255) | 用例名称 |
| case_result | varchar(50) | 本轮执行结果 |
| main_module | varchar(100) | 测试用例主模块 |
| platform | varchar(255) | 平台名称 |
| analyzed | tinyint(1) | 是否给失败用例分配了失败原因（1=是，0=否） |
| ... | ... | 其他字段 |

### pipeline_failure_reason（失败归因表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int(11) PK | 自增主键 |
| case_name | varchar(255) | 用例名称 |
| failed_batch | varchar(200) | 失败轮次（对应 pipeline_history.start_time） |
| platform | varchar(255) | 用例平台 |
| owner | varchar(100) | 失败用例跟踪人 |
| failed_type | varchar(100) | 失败原因分类 |
| reason | text | 详细失败原因 |
| ... | ... | 其他字段 |

**匹配关系：** `(case_name, failed_batch, platform)` 与 `(case_name, start_time, platform)` 一一对应。

### case_failed_type（失败类型字典表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| failed_reason_type | varchar(255) | 失败原因分类（选项来源） |
| owner | varchar(255) | 该失败类型的默认跟踪人 |

### ums_email（员工表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| employee_id | varchar(20) | 工号（跟踪人下拉备选来源） |
| name | varchar(50) | 姓名 |
| ... | ... | 其他字段 |

### ums_module_owner（模块负责人表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| module | varchar(40) | 主模块（选项来源） |
| owner | varchar(20) | 负责人工号（对应 ums_email.employee_id） |

## 3. 功能需求要点

1. **作用范围**：针对详细执行历史页面的任意条执行记录进行标注处理。
2. **选择方式**：支持执行记录多选、单选或全选。
3. **入口按钮**：找一个合适的地方放置按钮，按钮名称为「处理」。
4. **弹窗触发**：点击「处理」按钮后出现对话框。
5. **对话框内容**（以下均为必填）：
   - **5.1 失败类型**：下拉选择，选项来自 `case_failed_type.failed_reason_type`。
   - **5.2 跟踪人**：自动分配默认跟踪人，默认值来自 `case_failed_type.owner`（与所选失败类型对应）；支持下拉自定义更改，备选数据来自 `ums_email.employee_id`。
   - **5.3 详细原因**：文本框输入。
   - **5.4 模块（条件显示）**：仅当失败类型选择为 `bug` 时显示。默认值为该失败用例所属主模块（`pipeline_history.main_module`），默认跟踪人是`pipeline_history.owner`（main_module对应的），支持下拉自定义更改，备选数据来自 `ums_module_owner.module`，此时默认跟踪人改为 `ums_module_owner.owner`（与所选模块对应）。
6. **对话框操作**：提供「确定」「取消」按钮。
7. **取消行为**：点击取消，对话框关闭，不进行任何数据变更。
8. **确定行为**：进行以下数据变更：
   - **8.1** `pipeline_history.analyzed`：将所选记录的 `analyzed` 置为 1。
   - **8.2** `pipeline_failure_reason.owner`：更新或插入，匹配 `(case_name, failed_batch, platform)`。
   - **8.3** `pipeline_failure_reason.reason`：同上匹配关系。
   - **8.4** `pipeline_failure_reason.failed_type`：同上匹配关系。

**注意：** 当 `pipeline_failure_reason` 中不存在对应记录时，需执行 **INSERT**；已存在时执行 **UPDATE**。匹配键为 `(case_name, failed_batch, platform)`，其中 `failed_batch` 对应 `pipeline_history.start_time`。

# 规约必须明确界定的内容

1. **选择交互**
   - 表格是否支持行勾选（Checkbox）？勾选与「处理」按钮的联动逻辑。
   - 是否支持「全选当前页」「全选全部」？若支持，需说明与分页的关系。
   - 是否仅允许对 `case_result = 'failed'` 的记录进行标注？若勾选了 passed 记录，如何处理（禁用、过滤、提示）？

2. **按钮位置与状态**
   - 「处理」按钮的放置位置（表格上方工具栏、操作列、批量操作区等）。
   - 未选中任何记录时，按钮是否禁用或隐藏？
   - 选中记录后，按钮的可用状态。

3. **对话框布局与字段**
   - 对话框标题、宽度、是否支持拖拽。
   - 失败类型、跟踪人、详细原因、模块（条件显示）的控件类型、标签、占位符、校验规则。
   - 失败类型切换为 `bug` 时，模块字段的显示/隐藏逻辑及默认值、跟踪人默认值的联动更新逻辑。
   - 模块切换时，跟踪人默认值的联动更新逻辑。

4. **数据变更流程**
   - 确定时的前端校验（必填项、格式等）。
   - 后端 API 设计：请求体结构（选中的记录标识、失败类型、跟踪人、详细原因、模块）、响应结构。
   - 批量处理逻辑：多条记录是否共用同一套表单值？若共用，需说明；若每条独立，需说明交互方式（如逐条弹窗或表格内联编辑）。
   - `pipeline_failure_reason` 的 INSERT/UPDATE 判断逻辑，以及 `analyzer`、`created_at`、`updated_at` 等字段的写入策略。

5. **边界与异常**
   - 所选记录中，若部分已有 `pipeline_failure_reason` 记录、部分没有，如何处理？
   - 提交失败时的错误提示与重试策略。
   - 提交成功后，表格数据刷新策略（局部更新 vs 重新拉取）。

6. **与现有规约的衔接**
   - 标注完成后，「跟踪人」「失败原因」等字段的展示是否立即更新？需与 `spec/03_history_failure_reason_spec.md` 中的表格列、Drawer 展示保持一致。

# 格式要求

请以如下结构输出 Spec（可整体输出，作为 `spec/04_failure_process_spec.md` 的初稿）：

```
# 失败记录标注功能规约（Spec）

本文档在 `spec/02_history_fields_spec.md`、`spec/03_history_failure_reason_spec.md` 基础上，补充失败记录标注的交互与数据变更规约。

## 1. 功能概述

[简要描述功能目标、适用场景]

## 2. 选择交互

[表格勾选、全选、筛选规则、passed/failed 限制]

## 3. 入口与按钮

[按钮位置、可用状态、与选择的联动]

## 4. 标注对话框

### 4.1 布局与结构

[标题、尺寸、字段顺序]

### 4.2 字段定义

| 字段 | 控件类型 | 必填 | 默认值逻辑 | 备选数据来源 | 联动逻辑 |
| 失败类型 | ... | ... | ... | ... | ... |
| 跟踪人 | ... | ... | ... | ... | ... |
| 详细原因 | ... | ... | ... | ... | ... |
| 模块 | ... | ... | ... | ... | 仅 failure_type=bug 时显示 |

### 4.3 确定/取消行为

[取消：关闭无操作；确定：校验、提交、刷新]

## 5. 数据变更规约

### 5.1 pipeline_history

[analyzed 字段更新规则，匹配条件]

### 5.2 pipeline_failure_reason

[INSERT/UPDATE 判断、匹配键、字段写入清单]

### 5.3 批量处理策略

[多条记录共用表单 or 逐条处理，API 设计要点]

## 6. 边界与异常

[无记录、部分有记录、提交失败、刷新策略]

## 7. 与现有规约的衔接

[标注后表格/Drawer 展示的更新说明]
```

# 约束与原则

- 所有用户可见文字使用中文。
- 规约需与现有 spec 的表格结构、Drawer 分区、字段命名保持风格一致。
- 不涉及具体代码实现，仅描述交互流程、数据流、API 契约层面的规约。
- 若 `case_failed_type` 中 `failed_reason_type = 'bug'` 的精确匹配存在歧义（如大小写、前后空格），需在规约中明确匹配规则。
