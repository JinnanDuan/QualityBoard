# Q
实际生产中，pipeline_history的数据量比较大，能达到400w以上。其中的case_name字段的基数也比较大，能达到几千条。很多查询会比较慢。请考虑一下，应该用哪些手段来避免这些问题。

# A

基于当前表结构和查询方式，整理了一份针对 `pipeline_history`（400w+ 行、`case_name` 基数几千）的优化建议。

---

## 一、当前瓶颈分析

### 1. `get_history_options`（筛选选项接口）

- 对 `pipeline_history` 做 9 次 `SELECT DISTINCT`，每次扫 400w 行
- `case_name` 基数大，`DISTINCT` 成本高
- 每次打开历史页都会触发，是主要慢点之一

### 2. `list_history`（分页列表）

- `COUNT(*)` 在 400w 行上做聚合，即使有 WHERE 仍可能很慢
- 默认 `ORDER BY created_at DESC`，深分页（如 page=1000）的 `OFFSET` 成本高
- 多条件组合时，现有索引不一定能覆盖

### 3. 现有索引

```25:29:database/V1.0.1__create_pipeline_history.sql
  KEY `idx_timentask` (`start_time`,`subtask`),
  KEY `idx_main_module` (`main_module`) USING BTREE,
  KEY `idx_start_time_case` (`start_time`,`case_name`) USING BTREE,
  KEY `idx_casename_platform_batch` (`case_name`,`platform`,`start_time`) USING BTREE,
  KEY `idx_created_at_desc` (`created_at`) USING BTREE
```

---

## 二、优化手段（按优先级）

### 1. 筛选选项：`case_name` 从 `pipeline_cases` 取（优先做）

`pipeline_cases` 是用例主表，行数远小于 400w，`case_name` 去重成本低：

```sql
-- pipeline_cases 有 idx_case_name，且数据量小
SELECT DISTINCT case_name FROM pipeline_cases WHERE case_name IS NOT NULL AND case_name != '' ORDER BY case_name;
```

- 修改 `get_history_options` 中 `case_name` 的来源为 `pipeline_cases`
- 其他字段（start_time、subtask、main_module 等）仍从 `pipeline_history` 取

### 2. 筛选选项：加缓存（改动小、收益大）

- `start_time`、`subtask`、`main_module`、`case_level`、`platform`、`code_branch` 等变化不频繁
- 用 Redis 或内存缓存，TTL 5–15 分钟
- 新数据写入后，可主动失效或接受短时延迟

### 3. `case_name` 改为远程搜索（避免一次加载几千条）

- 不再一次性返回全部 `case_name`
- 前端 Select 使用 `showSearch` + `filterOption={false}`，输入时调用后端搜索接口
- 后端：`WHERE case_name LIKE %keyword%` 或全文索引，限制返回条数（如 50 条）
- 大幅减少单次查询的数据量和网络传输

### 4. 新建汇总表缓存筛选选项（不违反「禁止 ALTER」）

新建表，定时任务从 `pipeline_history` 汇总各字段去重值：

```sql
-- V1.x.x__create_history_filter_cache.sql
CREATE TABLE history_filter_cache (
  id int(11) NOT NULL AUTO_INCREMENT,
  field_name varchar(50) NOT NULL COMMENT 'start_time/subtask/case_name/main_module/...',
  field_value varchar(255) NOT NULL,
  updated_at datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_field_value (field_name, field_value)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- 定时（如每小时）从 `pipeline_history` 更新
- `get_history_options` 改为查该表，数据量小，查询快

### 5. 分页：用游标替代 OFFSET

- 深分页时 `OFFSET 20000 LIMIT 20` 需要扫描 20020 行
- 改为基于 `(created_at, id)` 的游标分页，例如：

```python
# 下一页：WHERE (created_at, id) < (last_created_at, last_id) ORDER BY created_at DESC, id DESC LIMIT 20
```

- 需要 API 支持 `cursor` 参数，前端配合改造

### 6. COUNT 优化

- 对总行数要求不严格时，可用近似值（如 `EXPLAIN` 的 rows 或统计表）
- 或限制最大页码（如最多 100 页），避免对超大结果集做精确 COUNT

### 7. 索引补充（需放宽「禁止 ALTER」规则）

当前规则禁止对已有表做 ALTER。若允许，可考虑：

| 索引 | 用途 |
|------|------|
| `(start_time, created_at)` | 按批次 + 时间排序 |
| `(case_result, analyzed, created_at)` | 失败/未分析用例筛选 |
| `(main_module, start_time)` | 按主模块 + 批次查询 |

需评估实际慢查询的 `WHERE` / `ORDER BY` 组合后再定索引。

### 8. 读写分离

- 历史查询、报表类接口走只读从库
- 主库专注写入和强一致性读

### 9. 分区（同样需 ALTER）

- 按 `start_time` 或 `created_at` 做 RANGE 分区，缩小单次扫描范围
- 需要 ALTER TABLE，同样受当前规则限制

---

## 三、建议实施顺序

| 优先级 | 措施 | 是否需 ALTER | 预期收益 |
|--------|------|--------------|----------|
| 1 | `case_name` 从 `pipeline_cases` 取 | 否 | 明显降低 case_name 去重耗时 |
| 2 | 筛选选项加缓存 | 否 | 显著减少对 `pipeline_history` 的 DISTINCT 查询 |
| 3 | `case_name` 改为远程搜索 | 否 | 避免一次加载几千条，体验更好 |
| 4 | 新建 `history_filter_cache` 汇总表 | 否 | 彻底减轻 options 接口压力 |
| 5 | 游标分页 | 否 | 改善深分页性能 |
| 6 | 索引补充 / 分区 | 是 | 需评估后决定是否放宽规则 |

建议先做 1、2、3，改动小且不涉及表结构变更；若仍不够，再考虑 4、5，最后再评估 6 及索引/分区方案。