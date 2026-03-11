# 首页最新批次状态 + 趋势折线图功能规约（Spec）

本文档定义首页 Dashboard 的「最新批次状态」与「趋势折线图」功能规格，作为后续 AI 编程的契约。

---

## 1. 功能概述

在系统首页（Dashboard，路由 `/`）展示两大模块：

1. **最新批次状态卡片**：以卡片形式展示**最新已执行完**批次的执行概况，便于用户快速了解当前测试健康度。
2. **趋势折线图**：按 `code_branch` 分开展示，**master 分支**与 **bugfix 分支**各一张折线图，以批次为横轴展示多批次执行趋势。

**数据来源**：`pipeline_overview` 表，按 `batch` + `code_branch` 聚合。

**分支定义**：
- **master**：`code_branch = 'master'`（或等价匹配，如忽略大小写）
- **bugfix**：`code_branch` 不为 master 的均视为 bugfix（如 `xxxxBeta_bugfix` 等）

---

## 2. 最新批次状态卡片

### 2.1 展示内容

| 指标 | 展示形式 | 数据来源 |
|------|----------|----------|
| 批次 | 纯文本，突出显示 | 聚合后的 `batch` |
| 总用例数 | 数字 | `SUM(case_num)`（需转为 int，若 case_num 为 varchar 则 CAST） |
| 通过数 | 数字，绿色 | `SUM(passed_num)` |
| 失败数 | 数字，红色 | `SUM(failed_num)` |
| 通过率 | 百分比（如 95.2%） | `通过数 / 总用例数 × 100`，总用例数为 0 时显示「—」 |

**说明**：`case_num` 在 `pipeline_overview` 中为 varchar，聚合时需按 `CAST(case_num AS SIGNED)` 或等价方式求和；若部分记录 case_num 为空，按 0 处理。

### 2.2 布局与样式

- **布局**：单行横向排列，使用 Ant Design `Row` + `Col` 或 `Card` 组件的 `Grid` 布局。
- **卡片数量**：建议 4～6 个指标卡片，或 1 个大卡片内分块展示。
- **样式**：
  - 每个指标独立成块，数字类指标使用较大字号。
  - 通过数用绿色、失败数用红色，与 History 页面的 Tag 着色一致。

### 2.3 数据聚合规则

- **最新批次定义**：取**最新已执行完**的批次。即：`batch_end IS NOT NULL` 的记录中，按 `MAX(batch_end)` 降序取第一条对应的 `batch`。若同一 batch 下有多条记录（不同 subtask/platform/code_branch），需先按 batch 聚合后再取最新。
- **「已执行完」判定**：`batch_end IS NOT NULL`，表示该批次执行已结束。
- **同一 batch 下多 subtask 聚合**：
  - `总用例数`：`SUM(CAST(case_num AS SIGNED))`，空值按 0
  - `通过数`：`SUM(passed_num)`
  - `失败数`：`SUM(failed_num)`

### 2.4 空数据与异常

| 场景 | 展示策略 |
|------|----------|
| 无数据（表为空） | 显示「暂无批次数据」，卡片区域保留，数字类指标显示「—」 |
| 无已执行完批次（所有记录 batch_end 均为 NULL） | 显示「暂无批次数据」 |
| case_num 为空 | 按 0 参与 SUM，通过率显示「—」 |
| 总用例数为 0 | 通过率显示「—」 |

### 2.5 「暂无批次数据」常见原因

若最新批次状态处显示「暂无批次数据」，可能原因包括：

1. **表中无数据**：`pipeline_overview` 表为空。
2. **无已执行完批次**：所有记录的 `batch_end` 均为 NULL，表示尚无批次执行完成。需确保数据入库时 `batch_end` 有值。
3. **查询逻辑错误**：旧逻辑按 `batch_start` 取最新，若 `batch_start` 为空或子查询返回空，会导致无结果。**修正**：按 `batch_end IS NOT NULL` 且 `MAX(batch_end)` 降序取最新批次。

---

## 3. 趋势折线图

### 3.1 双图表按分支展示

- **图表数量**：**两张**折线图，按 `code_branch` 分开展示。
- **图表 1**：标题「**master 分支最近 batch 执行情况**」，置于图表上方中央，仅展示 `code_branch = 'master'` 的数据。
- **图表 2**：标题「**bugfix 分支最近 batch 执行情况**」，置于图表上方中央，展示 `code_branch` 不为 master 的数据（如 `xxxxBeta_bugfix` 等，均视为 bugfix）。
- **布局**：两张图表上下排列，图表 1 在上、图表 2 在下。
- **分支匹配规则**：`code_branch` 与 `'master'` 比较时，建议忽略首尾空格；精确匹配 `'master'` 为 master 分支，其余均为 bugfix。

### 3.2 X 轴

- **展示内容**：批次标识（`batch` 字段值）。
- **排序规则**：按 `MAX(batch_start)` 升序，即最早执行的批次在左，最近在右。
- **默认展示数量**：每张图最近 **30** 个批次。
- **可配置性**：首版不暴露用户可调的批次数量。

### 3.3 Y 轴与指标

采用 **单 Y 轴** 设计，仅展示用例数相关指标：

| 指标 | 图表类型 | 颜色建议 |
|------|----------|----------|
| 失败用例数 | 折线 | 红色 (#ff4d4f) |
| 总用例数 | 折线 | 蓝色 (#1890ff) |

**说明**：规约推荐展示「失败数」「总用例数」两条折线。

### 3.3.1 Y 轴网格线

- **要求**：**不显示** Y 轴数字对应的横向网格线（splitLine）。
- **实现**：ECharts `yAxis.splitLine.show: false`，仅保留 Y 轴刻度和数字，去掉横向参考线。

### 3.4 数据点标签（数量展示）

- **要求**：每个数据点**上方**展示对应数量值。
- **实现**：ECharts series 配置 `label: { show: true, position: 'top' }`，在折线每个点上显示数值。

### 3.5 图表类型

- **推荐**：纯折线图，展示失败用例数、总用例数两条折线，每个点上方显示数量。

### 3.6 Tooltip

悬停于某批次数据点时，Tooltip 展示：

| 字段 | 格式 |
|------|------|
| 批次 | 纯文本 |
| 执行时间 | `YYYY-MM-DD HH:mm`（取 MIN(batch_start)） |
| 总用例数 | 数字 |
| 通过数 | 数字 |
| 失败数 | 数字 |
| 通过率 | 百分比 |

### 3.7 交互

- **图例**：支持点击图例切换显示/隐藏对应折线系列。
- **点击数据点**：点击某批次的数据点，跳转到 History 页（`/history`），URL 带筛选参数 `?start_time=批次值`（可附加 `code_branch` 以保持筛选一致性），直接展示该批次的用例明细。

### 3.8 数据范围

- **默认**：每张图查询最近 30 个批次。master 与 bugfix 分别按 `code_branch` 过滤后，再按 `batch_start` 降序取前 30 个 `batch`，最后按 `batch_start` 升序排列用于 X 轴。
- **已执行完**：趋势图是否仅展示 `batch_end IS NOT NULL` 的批次？规约建议**是**，与最新批次卡片逻辑一致，仅展示已执行完的批次。

---

## 4. 可选扩展

| 扩展项 | 首版是否纳入 | 说明 |
|--------|--------------|------|
| 按平台（platform）筛选 | 否 | 首页展示全平台汇总；若后续需要，可增加筛选器 |
| 按代码分支（code_branch）筛选 | **是** | 已纳入：master / bugfix 双图表分开展示 |
| 最新批次卡片点击跳转 | **是** | 点击卡片可跳转到 History 页，带 `?start_time=批次值` 参数，与趋势图点击行为一致 |

---

## 5. 数据获取与 API 设计

### 5.1 接口列表

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 最新批次状态 | GET | `/api/v1/dashboard/latest-batch` | 返回**最新已执行完**批次的聚合数据（不区分 code_branch） |
| 批次趋势数据 | GET | `/api/v1/dashboard/batch-trend` | 返回最近 N 个批次的聚合数据，需支持 `code_branch` 过滤 |

### 5.2 请求/响应结构

**GET /api/v1/dashboard/latest-batch**

- 请求参数：无
- 响应结构：

```json
{
  "batch": "2024-03-10_09:00",
  "total_case_num": 1200,
  "passed_num": 1150,
  "failed_num": 50,
  "pass_rate": 95.83,
  "batch_start": "2024-03-10T09:00:00",
  "batch_end": "2024-03-10T09:12:30",
  "result": "failed"
}
```

- 无数据时返回 `null` 或 `{}`，由前端判断展示空状态。
- **关键**：仅查询 `batch_end IS NOT NULL` 的记录，按 `MAX(batch_end)` 降序取最新批次。

**GET /api/v1/dashboard/batch-trend**

- 请求参数：`limit`（可选，默认 30，最大 50）、`code_branch`（必填，取值 `master` 或 `bugfix`）
- 响应结构：

```json
{
  "items": [
    {
      "batch": "2024-03-10_09:00",
      "total_case_num": 1200,
      "passed_num": 1150,
      "failed_num": 50,
      "pass_rate": 95.83,
      "batch_start": "2024-03-10T09:00:00"
    }
  ]
}
```

- `items` 按 `batch_start` 升序排列（从左到右对应 X 轴）。
- `code_branch=master`：仅查 `TRIM(code_branch) = 'master'`
- `code_branch=bugfix`：仅查 `TRIM(code_branch) != 'master'` 或 `code_branch IS NULL`（空值归入 bugfix 或按业务约定）

### 5.3 聚合逻辑

**最新批次（已执行完）：**

```sql
-- 取 batch_end 不为空的最新批次
SELECT batch,
       SUM(CAST(COALESCE(case_num, '0') AS SIGNED)) AS total_case_num,
       SUM(COALESCE(passed_num, 0)) AS passed_num,
       SUM(COALESCE(failed_num, 0)) AS failed_num,
       MIN(batch_start) AS batch_start,
       MAX(batch_end) AS batch_end
FROM pipeline_overview
WHERE batch_end IS NOT NULL
  AND batch = (
    SELECT batch FROM (
      SELECT batch, MAX(batch_end) AS max_end
      FROM pipeline_overview
      WHERE batch_end IS NOT NULL
      GROUP BY batch
      ORDER BY max_end DESC
      LIMIT 1
    ) t
  )
GROUP BY batch;
```

**趋势数据（按 code_branch 过滤，仅已执行完）：**

```sql
-- code_branch = 'master' 时
SELECT batch,
       SUM(CAST(COALESCE(case_num, '0') AS SIGNED)) AS total_case_num,
       SUM(COALESCE(passed_num, 0)) AS passed_num,
       SUM(COALESCE(failed_num, 0)) AS failed_num,
       MIN(batch_start) AS batch_start,
       MAX(batch_end) AS batch_end
FROM pipeline_overview
WHERE batch_end IS NOT NULL
  AND TRIM(COALESCE(code_branch, '')) = 'master'
  AND batch IN (
    SELECT batch FROM (
      SELECT batch, MAX(batch_start) AS ms
      FROM pipeline_overview
      WHERE batch_end IS NOT NULL AND TRIM(COALESCE(code_branch, '')) = 'master'
      GROUP BY batch
      ORDER BY ms DESC
      LIMIT :limit
    ) t
  )
GROUP BY batch
ORDER BY MIN(batch_start) ASC;

-- code_branch = 'bugfix' 时：将 TRIM(COALESCE(code_branch, '')) = 'master' 改为 != 'master'
```

**说明**：MySQL 5.7 子查询需使用派生表别名；`batch_end IS NOT NULL` 确保仅统计已执行完的批次。

### 5.4 性能考虑

- **pipeline_overview 数据量级**：通常远小于 `pipeline_history`（百万级），批次级聚合后数据点数量有限（如数千条），单次查询压力较小。
- **索引建议**：`(batch_start)` 或 `(batch, batch_start)` 可加速「最近 N 批次」的筛选；若现有 `idx_batch_subtask` 已覆盖常用查询，可暂不新增索引。
- **限制**：`limit` 参数最大 50，防止单次请求返回过多数据点影响前端渲染。

---

## 6. 字段复用说明

| 聚合字段 | 最新批次卡片 | 趋势折线图（master） | 趋势折线图（bugfix） |
|----------|--------------|----------------------|----------------------|
| batch | ✓ | ✓ X 轴 | ✓ X 轴 |
| total_case_num | ✓ | ✓ 折线 + 点标签 | ✓ 折线 + 点标签 |
| passed_num | ✓ | ✓ Tooltip | ✓ Tooltip |
| failed_num | ✓ | ✓ 折线 + 点标签 | ✓ 折线 + 点标签 |
| pass_rate | ✓ | ✓ Tooltip | ✓ Tooltip |
| batch_start | — | ✓ Tooltip | ✓ Tooltip |
| batch_end | — | — | — |
| result | — | — | — |
| code_branch | — | 过滤 = master | 过滤 != master |
