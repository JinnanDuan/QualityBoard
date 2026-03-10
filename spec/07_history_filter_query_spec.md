# History 筛选查询 Spec（方案设计）

> 本文档定义 DT 看板 History 模块的筛选查询方案，供实现时参考。

---

## 一、数据模型与执行键

### 1.1 表结构

| 表 | 说明 |
|----|------|
| `pipeline_history` | 主表，用例级执行明细 |
| `pipeline_failure_reason` | 失败原因表，记录失败用例的分析结果 |

### 1.2 执行键（唯一标识一次用例执行）

一次用例执行由以下三字段唯一确定：

| 主表字段 | 失败原因表字段 | 说明 |
|----------|----------------|------|
| `case_name` | `case_name` | 用例名称 |
| `platform` | `platform` | 平台 |
| `start_time` | `failed_batch` | 轮次（语义相同） |

**关联关系**：`(ph.case_name, ph.platform, ph.start_time)` ↔ `(pfr.case_name, pfr.platform, pfr.failed_batch)`

### 1.3 唯一索引前提（重要）

- 唯一索引 `(case_name, platform, failed_batch)` **已由人工在数据库层手动建立**
- Cursor 无需考虑索引创建，仅假设唯一执行键已存在
- 所有 EXISTS / IN 子查询均基于该唯一执行键进行关联
- 实现时直接使用该索引，不涉及 DDL 变更

---

## 二、大表注意事项（约 400 万条数据）

### 2.1 索引存储特性

在约 400 万条数据规模下：

- B+ 树索引深度通常为 3～4 层，单次查找约 3～4 次磁盘 I/O
- 唯一索引 `(case_name, platform, failed_batch)` 可显著加速 EXISTS 关联与去重
- 主表 `pipeline_history` 的 `idx_timentask`、`idx_start_time_case` 等索引对主表筛选至关重要

### 2.2 建索引前校验（人工操作）

**唯一索引建立前必须确保表中无重复数据**，否则 UNIQUE 创建会失败：

- 执行去重检查：`SELECT case_name, platform, failed_batch, COUNT(*) FROM pipeline_failure_reason GROUP BY case_name, platform, failed_batch HAVING COUNT(*) > 1`
- 若有重复，需先清理或合并后再建唯一索引

### 2.3 建索引后的影响

- **查询性能**：EXISTS 关联、跨表筛选可充分利用唯一索引，查询耗时从秒级降至毫秒级
- **写入开销**：INSERT/UPDATE 需维护索引，开销可接受，大表场景下查询收益远大于写入成本

---

## 三、查询模型：条件合并

### 3.1 核心原则

**每次筛选请求 = 基于完整条件集合的重新生成 SQL**

- 输入：用户当前选择的全部筛选条件（来自 URL 参数 / 表单）
- 输出：一条（或一组）SQL，所有条件直接组合为 AND
- 禁止：**结果集驱动** — 不允许将上一次查询结果拼进 IN 条件

### 3.2 筛选条件分类

| 分类 | 条件 | 来源表 | 说明 |
|------|------|--------|------|
| 主表条件 | start_time, subtask, case_name, main_module, case_result, case_level, analyzed, platform, code_branch | pipeline_history | 直接作用于主表 WHERE |
| 跨表条件 | failure_owner, failed_type | pipeline_failure_reason | 需通过 EXISTS 或子查询关联 |

### 3.3 条件合并示例

用户选择：`start_time=['2024-01-15'], failed_type=['bug'], platform=['Android']`

正确做法：**所有条件在一次 SQL 中合并**

```sql
SELECT * FROM pipeline_history ph
WHERE ph.start_time IN ('2024-01-15')
  AND ph.platform IN ('Android')
  AND EXISTS (
    SELECT 1 FROM pipeline_failure_reason pfr
    WHERE pfr.case_name = ph.case_name
      AND pfr.failed_batch = ph.start_time
      AND pfr.platform = ph.platform
      AND pfr.failed_type IN ('bug')
  )
```

错误做法：先查 batch 得到 case_name 列表，再在下次查询中用这些 case_name 做 IN。

---

## 四、推荐 SQL 架构

### 4.1 主查询结构

```
SELECT ph.*
FROM pipeline_history ph
WHERE
  [主表条件：start_time, subtask, case_name, main_module, case_result, case_level, analyzed, platform, code_branch]
  [跨表条件：EXISTS 子查询]
ORDER BY [sort_field] [sort_order]
LIMIT [page_size] OFFSET [offset]
```

### 4.2 跨表筛选：EXISTS 子查询（首选）

**首选方案**：使用 EXISTS 相关子查询，基于唯一执行键 `(case_name, platform, failed_batch)` 关联

```sql
EXISTS (
  SELECT 1
  FROM pipeline_failure_reason pfr
  WHERE pfr.case_name = ph.case_name
    AND pfr.failed_batch = ph.start_time
    AND pfr.platform = ph.platform
    AND [pfr.failed_type IN (用户选择) OR 未选则省略]
    AND [pfr.owner IN (用户选择) OR 未选则省略]
)
```

**要点**：

- 必须使用**执行键三字段**精确匹配，利用唯一索引
- 条件由用户选择集合生成，无中间结果集
- MySQL 5.7 可将 EXISTS 优化为 semi-join，无需物化子查询结果

### 4.3 备选：IN 子查询

当以下条件满足时，可考虑 IN 子查询作为备选：

- 子查询结果集预期较小（如 failed_type 过滤后 < 数百行）
- 实测 EXISTS 性能不佳，需对比验证

```sql
(ph.case_name, ph.start_time, ph.platform) IN (
  SELECT case_name, failed_batch, platform
  FROM pipeline_failure_reason
  WHERE failed_type IN (用户选择)
    AND (owner IN (用户选择) OR 未选则省略)
)
```

**MySQL 5.7 注意**：三字段 IN 子查询可能存在优化风险（物化、索引选择不佳），EXISTS 更稳，优先选用。

### 4.4 总数查询

与主查询共用同一套 WHERE 条件，仅将 SELECT 改为 COUNT：

```sql
SELECT COUNT(*)
FROM pipeline_history ph
WHERE [与主查询相同的条件]
```

---

## 五、跨表筛选逻辑

### 5.1 何时添加 EXISTS

仅当用户选择了 `failure_owner` 或 `failed_type` 时，才添加 EXISTS 子查询。

### 5.2 执行键匹配

EXISTS 子查询中的关联条件必须严格使用三字段，与唯一索引一致：

```sql
pfr.case_name = ph.case_name
AND pfr.failed_batch = ph.start_time   -- 注意：failed_batch 对应 start_time
AND pfr.platform = ph.platform
```

### 5.3 条件组合

- 若用户同时选了 `failed_type` 和 `failure_owner`：EXISTS 内用 AND 连接
- 若只选其一：只添加对应条件
- 若都未选：不添加 EXISTS 子查询

### 5.4 数据拼装（非筛选）

主查询返回的 `pipeline_history` 行需展示 `failure_owner`、`failed_type`。

**方案**：主查询完成后，根据当前页的 `(case_name, start_time, platform)` 批量查 `pipeline_failure_reason`，在服务层拼装。此步骤与筛选逻辑分离，不参与 WHERE 条件。

---

## 六、索引利用说明

### 6.1 主表 pipeline_history

| 索引 | 用途 |
|------|------|
| idx_timentask (start_time, subtask) | start_time 筛选、排序 |
| idx_main_module (main_module) | main_module 筛选 |
| idx_start_time_case (start_time, case_name) | start_time + case_name 筛选 |
| idx_casename_platform_batch (case_name, platform, start_time) | EXISTS 关联时主表侧 |
| idx_created_at_desc (created_at) | 默认排序 |

### 6.2 失败原因表 pipeline_failure_reason

| 索引 | 用途 |
|------|------|
| idx_pfr_failedbatch_case (failed_batch, case_name) | 现有索引，可辅助部分场景 |
| **唯一索引 (case_name, platform, failed_batch)** | 执行键，EXISTS/IN 关联的核心索引，已人工建立 |

**说明**：唯一索引已存在，实现时直接依赖。若 EXISTS 中 `failed_type`、`owner` 筛选选择性高，可结合实际执行计划评估是否需额外复合索引。

### 6.3 索引使用顺序

1. 主表：先按 start_time、platform 等主表条件过滤，缩小扫描范围
2. EXISTS：对每行候选，用 `(case_name, platform, failed_batch)` 唯一索引查找 pfr，再应用 failed_type、owner 条件

---

## 七、禁止项与检查清单

### 7.1 禁止

- 将上一次查询结果（如 case_name 列表）拼进 IN 条件
- 使用大结果集 JOIN（如 pipeline_history JOIN pipeline_failure_reason 全表）
- 跨表筛选时未使用执行键三字段精确匹配
- 在代码中创建或修改唯一索引（索引由人工维护）

### 7.2 检查清单

- [ ] 每次请求的 SQL 是否仅由用户条件集合生成？
- [ ] 跨表条件是否通过 EXISTS（或 IN 子查询）实现？
- [ ] EXISTS 子查询是否使用 `(case_name, failed_batch, platform)` 三字段精确匹配？
- [ ] 是否无任何「上一次结果驱动下一次查询」的逻辑？
- [ ] 是否假设唯一索引已存在，未涉及索引 DDL？

---

## 八、与筛选项接口的关系

- 筛选项接口 `GET /api/v1/history/options` 与列表查询**完全解耦**
- 筛选项使用单表去重查询，不参与跨表筛选
- 列表查询超时或失败时，筛选项仍可正常返回

---

## 九、版本与变更

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2025-03 | 初版：条件合并、EXISTS 跨表筛选、禁止结果集驱动 |
| 1.1 | 2025-03 | 明确唯一索引前提、大表注意事项、索引利用说明 |
