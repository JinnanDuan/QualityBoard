# 数据库表结构一致性校验 — P2 完善 Prompt

在现有 `backend/services/schema_check_service.py` 基础上，按 `spec/07_db_schema_check_spec.md` 第 4.4 节及 5.2 节，**补充实现 P2 校验**：默认值、主键、索引。

---

## 一、必读文档

1. **功能规约**：`spec/07_db_schema_check_spec.md`（重点：2.2 校验粒度、4.4 P2 校验实现细节、5.2 不一致时的提示要求）
2. **现有实现**：`backend/services/schema_check_service.py`（在现有逻辑上扩展，勿破坏 P0/P1）

---

## 二、变更清单

### 1. DDL 解析扩展（`_parse_ddl_file`）

在现有字段解析基础上，**新增提取**：

| 提取项 | DDL 格式 | 输出结构 |
|--------|----------|----------|
| 字段 DEFAULT | `DEFAULT xxx`、`ON UPDATE CURRENT_TIMESTAMP` | 每列增加 `default` 字段，归一化后取值见 spec 4.4.1 |
| 主键 | `PRIMARY KEY (\`col1\`[, \`col2\`...])` | 返回 `primary_key: [col1, col2, ...]`（按顺序） |
| 索引 | `KEY \`idx_name\` (\`col1\`[, \`col2\`...])`、`UNIQUE KEY \`idx_name\` (...)` | 返回 `indexes: [{name, columns: [...], unique: bool}, ...]` |

**默认值归一化**（spec 4.4.1）：

- `DEFAULT NULL` → `NULL`
- `DEFAULT ''` → `''`
- `DEFAULT 0` / `DEFAULT '0'` → `0`
- `DEFAULT CURRENT_TIMESTAMP` → `CURRENT_TIMESTAMP`
- `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` → `CURRENT_TIMESTAMP ON UPDATE`
- 无 DEFAULT → `None`（表示无默认值）

**索引解析**：用正则匹配 `PRIMARY KEY`、`KEY \`xxx\``、`UNIQUE KEY \`xxx\`` 行，提取括号内列名列表。不解析 `FOREIGN KEY`、`CONSTRAINT`。

### 2. 期望结构扩展（`get_expected_schema`）

`get_expected_schema` 返回的每表结构由 `{columns}` 扩展为：

```python
{
    "columns": [...],           # 每列增加 default 字段
    "primary_key": ["id"],      # 主键列列表
    "indexes": [                # 非主键索引
        {"name": "idx_xxx", "columns": ["a", "b"], "unique": False},
        ...
    ]
}
```

### 3. 实际结构扩展（`get_actual_schema`）

**COLUMNS 查询**：增加 `COLUMN_DEFAULT`、`EXTRA`，用于默认值比较。

**主键**：从 `COLUMNS` 中 `COLUMN_KEY='PRI'` 的列按 `ORDINAL_POSITION` 排序；或从 `STATISTICS` 中 `INDEX_NAME='PRIMARY'` 按 `SEQ_IN_INDEX` 排序。

**索引**：查询 `information_schema.STATISTICS`，按 `INDEX_NAME` 分组，排除 `PRIMARY`，得到 `{name, columns: [...], unique: NON_UNIQUE==0}`。

每表结构扩展为：

```python
{
    "columns": [...],           # 每列增加 default, extra
    "primary_key": ["id"],
    "indexes": [{"name": "idx_xxx", "columns": ["a", "b"], "unique": False}, ...]
}
```

### 4. 比较逻辑扩展（`compare_schemas`）

在现有 P0/P1 比较后，**新增**：

| 差异类型 | 触发条件 | detail 示例 |
|----------|----------|-------------|
| 默认值不同 | 期望 default 与实际 COLUMN_DEFAULT/EXTRA 归一化后不一致 | `DDL=CURRENT_TIMESTAMP, 实际=NULL` |
| 主键缺失 | DDL 有主键，实际无 | `DDL 定义主键(id)，数据库中无主键` |
| 主键不同 | 主键列或顺序不同 | `DDL 主键=id, 实际主键=other_id` |
| 索引缺失 | DDL 索引在 actual.indexes 中不存在 | `DDL 中定义但数据库中不存在` |
| 索引多余 | 实际索引在 DDL 中未定义（可选，仅告警） | `数据库中存在但 DDL 未定义` |
| 索引列不同 | 索引名相同但列或顺序不同 | `DDL=(batch,subtask), 实际=(batch)` |
| 索引唯一性不同 | 索引名相同但 unique 不同 | `DDL=UNIQUE, 实际=普通索引` |

**默认值比较**：MySQL 返回的 `COLUMN_DEFAULT` 可能带引号（如 `'0'`、`'CURRENT_TIMESTAMP'`），需 strip 引号后与归一化期望值比较。`EXTRA` 含 `on update CURRENT_TIMESTAMP` 时，与 `CURRENT_TIMESTAMP ON UPDATE` 对应。

### 5. 差异报告扩展（`format_diff_report`）

在 `type_labels` 中增加 P2 类型：

```python
"默认值不同": "[默认值不同]",
"主键缺失": "[主键缺失]",
"主键不同": "[主键不同]",
"索引缺失": "[索引缺失]",
"索引多余": "[索引多余]",
"索引列不同": "[索引列不同]",
"索引唯一性不同": "[索引唯一性不同]",
```

输出格式按 spec 5.2 表格，如：`[索引缺失] 表 pipeline_overview, 索引 idx_batch_subtask: DDL 中定义但数据库中不存在`。

---

## 三、实现约束

1. **Python 3.8**：类型标注使用 `Optional[X]`，禁止 `X | None`
2. **不新增依赖**：继续用正则解析 DDL，不引入 sqlparse
3. **向后兼容**：P0/P1 行为不变，仅扩展 P2
4. **表缺失时**：该表的主键、索引校验跳过（已计入「表缺失」）

---

## 四、验证方式

1. 正常库：启动成功，日志有「DB Schema Check 通过」
2. 删除某索引后启动：应检测到「索引缺失」
3. 修改某字段 DEFAULT 后启动：应检测到「默认值不同」
4. 修改主键列后启动：应检测到「主键不同」或「主键缺失」
