# 失败原因继承功能规约（Spec）

本文档在 `spec/02_history_fields_spec.md`、`spec/03_history_failure_reason_spec.md`、`spec/04_failure_process_spec.md` 基础上，补充「失败原因继承」的交互与数据变更规约。

---

## 1. 功能概述

### 1.1 功能目标

从历史执行记录将已标注的失败原因继承到目标用例，减少重复标注工作。支持两种继承维度：**批次维度**（按历史批次匹配 `case_name + platform` 逐条继承）、**用例维度**（选择一条具体历史执行记录，将其失败原因批量应用到勾选用例）。

### 1.2 适用场景

- 轮次 A 已对失败用例设置失败原因，轮次 B 执行结束后希望复用
- 多条用例失败原因相同，希望从某条历史记录一次性复制到当前勾选用例

### 1.3 作用范围

- **页面**：详细执行历史页面
- **对象**：`case_result = 'failed'` 或 `'error'` 的执行记录（与「处理」按钮一致，passed 不可勾选）

---

## 2. 与勾选的联动

### 2.1 按钮可用条件

| 勾选状态 | 按钮状态 | 说明 |
|----------|----------|------|
| 未勾选任何记录 | **禁用** | 必须勾选才能操作 |
| 勾选 1 条 failed/error | 可用 | 弹窗可选择「批次维度」或「用例维度」 |
| 勾选多条 failed/error，且为同一批次 | 可用 | 弹窗可选择「批次维度」或「用例维度」 |
| 勾选多条 failed/error，且跨多个批次 | 可用 | 弹窗**仅**显示「用例维度」 |
| 勾选的全部为 passed | 禁用 | 与「处理」按钮逻辑一致 |

### 2.2 继承维度说明

| 维度 | 源选择 | 目标范围 | 匹配/应用逻辑 |
|------|--------|----------|---------------|
| **批次维度** | 选择历史批次 | 当前筛选批次下**所有** failed/error 用例 | 按 `(case_name, platform)` 在源批次 `pipeline_failure_reason` 中匹配，有则继承 |
| **用例维度** | 源用例名（必填）+ 源平台（可选）+ 源批次（可选）确定唯一源记录 | 当前**勾选**的用例 | 将源记录的失败原因（failed_type、owner、reason、analyzer 等）**原样复制**到每条勾选用例 |

### 2.3 弹窗选项展示规则

| 勾选情况 | 弹窗可选维度 |
|----------|--------------|
| 勾选 1 条 failed/error | 批次维度、用例维度 |
| 勾选多条 failed/error 且同一批次 | 批次维度、用例维度 |
| 勾选多条 failed/error 且跨批次 | 仅用例维度 |

---

## 3. 入口与按钮

### 3.1 按钮位置

- 「继承失败原因」按钮放置在**表格上方工具栏**，与「处理」按钮并列
- 位于筛选控件右侧，与「刷新」等操作按钮保持视觉层级一致

### 3.2 按钮状态

| 状态 | 条件 | 表现 |
|------|------|------|
| 可用 | 勾选至少 1 条 failed/error 记录 | 可点击，触发弹窗 |
| 禁用 | 未勾选，或勾选的全部为 passed | 置灰，不可点击 |
| 加载中 | 继承请求进行中 | 显示 loading 状态 |

---

## 4. 继承弹窗

### 4.1 布局与结构

| 属性 | 规约 |
|------|------|
| 标题 | 「继承失败原因」 |
| 宽度 | 建议 520px～600px |
| 字段顺序 | 继承维度（Radio）→ 源选择（根据维度切换） |
| 底部按钮 | 左侧「取消」，右侧「确定」 |

### 4.2 继承维度选择

| 字段 | 控件类型 | 必填 | 选项 | 说明 |
|------|----------|------|------|------|
| 继承维度 | Radio 单选 | 是 | 批次维度、用例维度 | 跨批次勾选时仅显示「用例维度」 |

### 4.3 批次维度：源批次选择

| 字段 | 控件类型 | 必填 | 选项来源 | 说明 |
|------|----------|------|----------|------|
| 源批次 | 下拉单选 Select（可搜索） | 是 | `pipeline_history.start_time` 去重，仅 20 开头批次，排除当前批次，按时间倒序 | 选择要继承的历史轮次 |

- 当前筛选批次：勾选用例所在批次的 `start_time`（单条时即该条；多条同批次时即该批次；跨批次时无「当前批次」，不展示批次维度）

### 4.4 用例维度：源选择（筛选 → 选择）

用例维度下，用户先通过三字段**筛选**，再点击「查询」获取匹配记录列表，**从列表中选择一条**后执行继承。

| 步骤 | 控件 | 必填 | 说明 |
|------|------|------|------|
| 1. 筛选 | 源用例名、源平台、源批次 | 用例名必填 | 三字段用于缩小范围，选项来自 `GET /inherit-source-options` |
| 2. 查询 | 「查询」按钮 | - | 调用 `GET /inherit-source-records`，展示匹配的源记录列表 |
| 3. 选择 | 单选列表（平台、批次、失败类型、原因摘要） | 是 | 用户从查询结果中选择一条记录 |
| 4. 确定 | 「确定」按钮 | - | 提交 `source_pfr_id` 执行继承 |

### 4.5 校验规则

- 继承维度必选
- 批次维度：源批次必选，且不能与当前筛选批次相同
- 用例维度：源用例名必选；源平台、源批次可选；须先查询并选择一条源记录

### 4.6 确定/取消行为

| 操作 | 行为 |
|------|------|
| 取消 | 关闭弹窗，不发起请求 |
| 确定 | 1）前端校验；2）校验通过后调用后端 API；3）成功则关闭弹窗、刷新表格、展示成功提示（含继承数量）；4）失败则展示错误信息，弹窗不关闭 |

---

## 5. 继承逻辑

### 5.1 批次维度继承流程

1. 目标范围：当前筛选批次下 **failed/error 且未分析**（`analyzed = 0` 或 `NULL`）的用例；**已分析**（`analyzed = 1`）的不参与继承。
2. 对每条目标用例 `(case_name, platform)`，在源批次 `pipeline_failure_reason` 中查找 `failed_batch = 源批次` 且 `case_name`、`platform` 匹配的记录。
3. 若找到：**仅 INSERT** 目标 `pipeline_failure_reason`（在「未分析必无 pfr」不变量下成立）；若未找到：跳过。

### 5.2 用例维度继承流程

1. 目标范围：当前**勾选**的 failed/error 用例中，**仅 `analyzed = 0` 或 `NULL`** 的记录；已分析记录跳过并计入跳过数。
2. 源：用户从筛选结果中选择一条记录，提交 `source_pfr_id`（`pipeline_failure_reason.id`）。
3. 将源记录的失败原因（failed_type、owner、reason、analyzer、created_at）**原样复制**到每条可继承目标，**仅 INSERT** `pipeline_failure_reason`。

### 5.3 写入字段（两种维度通用）

| 字段 | 继承策略 |
|------|----------|
| failed_type | 直接复制 |
| owner | 直接复制 |
| reason | 直接复制 |
| analyzer | 直接复制（保留源分析人） |
| created_at | 直接复制（保留源分析时间） |
| updated_at | 数据库默认 `ON UPDATE CURRENT_TIMESTAMP` |
| failed_batch | 目标记录的 start_time |
| platform | 目标记录的 platform |
| case_name | 目标记录的 case_name |
| recover_batch | 不继承，置空 |
| dts_num | 不继承，置空 |

### 5.4 pipeline_history.analyzed

- 继承成功后，对应目标记录的 `pipeline_history.analyzed` 置为 `1`

### 5.5 INSERT 与不变量

- **继承**路径下：仅对未分析目标执行，在「仅手动标注或继承会将 `analyzed` 置 1 且此时才有 pfr」不变量下，目标侧**只执行 INSERT**，不对已有 pfr 做 UPDATE。
- **手动标注**（分析处理）仍按原规约：已存在 pfr 则 UPDATE，否则 INSERT。

### 5.6 平台一致性

- **批次维度**：按 `(case_name, platform)` 匹配，源与目标 platform 必须相同
- **用例维度**：不校验 platform，源记录的失败原因可应用到任意 platform 的勾选用例（如将 oh 的失败原因复制到 android 用例）

---

## 6. 边界与异常

### 6.1 边界情况

| 场景 | 处理 |
|------|------|
| 目标已分析（`analyzed = 1`） | 不参与继承（批次维度查询即排除；用例维度跳过并计入 skipped） |
| 批次维度：源批次无该用例的 pfr | 跳过，不写入 |
| 并发：同一目标批次或同一勾选集合上另有继承在执行 | 返回 503，提示稍后重试（MySQL `GET_LOCK`） |
| 目标用例非 failed/error | 不参与继承（勾选时已限制为 failed/error） |
| 批次维度：源批次 = 当前筛选批次 | 前端/后端校验，提示「源批次不能与当前批次相同」 |
| 用例维度：未选择源记录（source_pfr_id 为空） | 前端校验，提示「请从查询结果中选择一条源记录」 |
| 用例维度：source_pfr_id 对应记录不存在 | 返回 400，提示「源记录不存在或已删除」 |
| 部分成功、部分失败 | 事务内执行，失败则整体回滚，返回错误信息 |

### 6.2 提交失败

- 网络错误、超时：提示「网络异常，请稍后重试」
- 业务错误：展示后端返回的 `message` 或 `detail`
- 弹窗保持打开，允许用户修改后重试

### 6.3 提交成功后

- 刷新表格数据，使 `analyzed`、`failure_owner`、`failed_type` 等列立即更新
- 若 Drawer 正在展示已继承记录，内容应同步更新

---

## 7. API 设计

### 7.1 请求

| 属性 | 规约 |
|------|------|
| 方法 | `POST` |
| 路径 | `/api/v1/history/inherit-failure-reason` |
| 请求体 | 见下表 |

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| inherit_mode | string | 是 | `"batch"` 或 `"case"` |
| source_batch | string | 条件 | 批次维度时必填，源批次 start_time |
| target_batch | string | 条件 | 批次维度时必填，当前筛选批次 start_time |
| source_pfr_id | int | 条件 | 用例维度时必填，用户从筛选结果中选择的 `pipeline_failure_reason.id` |
| history_ids | array[int] | 条件 | 用例维度时必填，勾选的 `pipeline_history.id` 列表；批次维度时不传 |

**说明**：用例维度下，用户先通过三字段筛选并查询，从结果中选择一条记录后提交 `source_pfr_id`。

### 7.2 响应

- **成功**：`200`，body 示例：

```json
{
  "success": true,
  "inherited_count": 15,
  "skipped_count": 3,
  "message": "继承成功，共继承 15 条"
}
```

- **失败**：`4xx`/`5xx`，body 包含 `message` 或 `detail`

### 7.3 后端校验

- **批次维度**：校验 `source_batch` 与 `target_batch` 不同；校验两者均存在；`target_batch` 下所有 failed/error 作为目标
- **用例维度**：
  - 校验 `source_pfr_id` 必填
  - 按 `source_pfr_id` 查询 `pipeline_failure_reason`，不存在则返回 400「源记录不存在或已删除」
  - 校验 `history_ids` 中每条记录存在且 `case_result` 为 failed/error

---

## 8. 日志规范

- 继承成功：`INFO` 级别，记录「继承失败原因：维度={inherit_mode}，继承数量={count}，操作人={operator}」
- 继承失败：`WARNING` 或 `ERROR` 级别，记录错误原因及 traceback

---

## 9. 数据流示意

```
用户勾选 failed/error 用例 → 点击「继承失败原因」→ 弹窗选择维度 + 源
    → 批次维度：选源批次 → 确定
    → 用例维度：选源用例名（必填）+ 源平台（可选）+ 源批次（可选）
        → 点击「查询」→ GET /inherit-source-records → 展示匹配记录列表
        → 用户从列表中选择一条 → 确定
    → 前端校验 → POST /api/v1/history/inherit-failure-reason
    → 后端：
        批次维度：取 target_batch 下所有 failed/error → 按 (case_name, platform) 查 source_batch 的 pfr → 匹配则继承
        用例维度：按 source_pfr_id 查 pfr → 对 history_ids 原样复制
    → INSERT/UPDATE pipeline_failure_reason，更新 pipeline_history.analyzed = 1
    → 返回成功 → 前端刷新表格 → 关闭弹窗 → 成功提示
```

## 10. 用例维度接口（补充）

### 10.1 选项接口 `GET /history/inherit-source-options`

三字段下拉的选项来源，支持级联筛选：

| 字段 | 选项接口 | 说明 |
|------|----------|------|
| 源用例名 | 有 pfr 的 `case_name` 去重 | 必填，初始加载全部 |
| 源平台 | 有 pfr 的 `platform` 去重 | 可选，可传入 `case_name` 缩小范围 |
| 源批次 | 有 pfr 的 `failed_batch` 去重 | 可选，可传入 `case_name`、`platform` 缩小范围 |

查询参数：`case_name`、`platform`（可选）。返回 `{ case_names: [], platforms: [], batches: [] }`。

### 10.2 筛选记录接口 `GET /history/inherit-source-records`

根据三字段筛选，返回匹配的源记录列表，供用户选择：

- 查询参数：`case_name`（必填）、`platform`（可选）、`batch`（可选）
- 返回：`{ records: [{ id, case_name, platform, failed_batch, failed_type, owner, reason }, ...] }`

## 11. 性能与超时（补充）

- **后端**：继承仅 INSERT pfr，采用 **批量 INSERT**（分块）及 **`pipeline_history.analyzed` 批量 UPDATE**（按 id 分块）；不再对 pfr 逐条 SELECT/UPDATE。
- **并发**：使用 MySQL **`GET_LOCK`**（批次维度按目标批次、用例维度按勾选 id 集合哈希）避免同一目标上并发继承。
- **前端**：`POST /inherit-failure-reason` 请求超时单独设为 **60 秒**（与列表等接口默认 15 秒区分）。
