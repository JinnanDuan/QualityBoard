# 数据库表结构一致性校验功能规约 (DB Schema Check Spec)

## 1. 功能目标

在每次 FastAPI 后端启动时，自动校验当前数据库中的表结构是否与代码仓库 `database/` 目录下的 SQL DDL 文件定义一致。若不一致，**必须明确提示存在不一致，并具体指出不一致的位置**，避免运行时出现 ORM 与数据库结构不匹配导致的错误。

---

## 2. 功能范围

### 2.1 需校验的表清单

| 序号 | 表名 | DDL 文件 | 说明 |
|------|------|----------|------|
| 1 | pipeline_overview | V1.0.2__create_pipeline_overview.sql | 流水线概览 |
| 2 | pipeline_history | V1.0.1__create_pipeline_history.sql | 流水线历史 |
| 3 | pipeline_failure_reason | V1.0.3__create_pipeline_failure_reason.sql | 失败归因 |
| 4 | pipeline_cases | V1.0.4__create_pipeline_cases.sql | 用例主数据 |
| 5 | ums_email | V1.0.5__create_ums_email.sql | 员工信息 |
| 6 | ums_module_owner | V1.0.6__create_ums_module_owner.sql | 模块-责任人映射 |
| 7 | case_failed_type | V1.0.7__create_case_failed_type.sql | 失败原因类型字典 |
| 8 | case_offline_type | V1.0.8__create_case_offline_type.sql | 下线原因类型字典 |
| 9 | sys_audit_log | V1.0.9__create_sys_audit_log.sql | 系统审计日志 |
| 10 | report_snapshot | V1.1.0__create_report_snapshot.sql | 报告快照 |

> 注：`V1.0.0__init_dt_infra_database.sql` 仅包含 `CREATE DATABASE`，不定义表结构，不参与表级校验。

### 2.2 校验粒度与优先级

| 优先级 | 校验维度 | 说明 |
|--------|----------|------|
| P0 | 表是否存在 | 期望的 10 张表在数据库中是否都存在；数据库是否存在多余表（可选，仅告警） |
| P0 | 字段是否存在 | 每张表的字段是否缺失或多余 |
| P1 | 字段类型 | 字段的 MySQL 数据类型是否一致（需处理 `int` vs `int(11)` 等等价形式） |
| P1 | 是否可空 | `NULL` / `NOT NULL` 是否一致 |
| P2 | 默认值 | `DEFAULT` 是否一致（`CURRENT_TIMESTAMP`、`ON UPDATE` 等需归一化比较） |
| P2 | 主键 | `PRIMARY KEY` 是否一致 |
| P2 | 索引 | `KEY`、`UNIQUE KEY` 名称及包含列是否一致 |

> **实现要求**：P0、P1、P2 均需完整实现。

---

## 3. 触发时机

### 3.1 执行阶段

在 FastAPI 应用 **lifespan 的 startup 阶段** 执行，即在接收任何 HTTP 请求之前完成校验。

```python
# 伪代码示意
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await run_schema_check()  # 在此执行
    yield
    # shutdown
```

> 使用 FastAPI 的 `lifespan` 参数（或 `on_event("startup")`，视 FastAPI 版本而定），确保在校验完成前不对外提供服务。

### 3.2 配置开关

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `DB_SCHEMA_CHECK_ENABLED` | bool | `true` | 为 `false` 时跳过启动时校验 |
| `DB_SCHEMA_CHECK_FAIL_FAST` | bool | `true` | 为 `true` 时发现不一致则启动失败；为 `false` 时仅记录告警并继续启动 |

> 开发/调试时可临时关闭或改为仅告警，生产环境建议开启且 fail-fast。

---

## 4. 校验逻辑

### 4.1 期望结构的获取方式

**方案：解析 `database/` 下的 DDL 文件**

- 按表名与 DDL 文件映射关系（见 2.1）读取对应 `V*.sql` 文件
- 解析其中的 `CREATE TABLE` 语句，提取：
  - **P0/P1**：表名、字段列表（名、类型、NULL/NOT NULL）
  - **P2**：字段 DEFAULT（含 `ON UPDATE CURRENT_TIMESTAMP`）、`PRIMARY KEY (...)`、`KEY \`name\` (...)`、`UNIQUE KEY \`name\` (...)`
- 不依赖 ORM 反推：ORM 可能与 SQL 存在细微差异，SQL 是唯一真理（见 `database/README.md`）

**解析实现建议**：

- 使用正则或轻量 SQL 解析库（如 `sqlparse`）解析 `CREATE TABLE`
- 或维护一份「表结构清单」JSON/YAML，由 CI 或脚本从 DDL 生成，运行时读取（需保证与 DDL 同步）

### 4.2 实际结构的获取方式

**方案：查询 MySQL `information_schema`**

```sql
-- 表是否存在
SELECT TABLE_NAME FROM information_schema.TABLES
WHERE TABLE_SCHEMA = :db_name AND TABLE_NAME = :table_name;

-- 字段信息
SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_KEY
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = :db_name AND TABLE_NAME = :table_name
ORDER BY ORDINAL_POSITION;

-- 索引信息
SELECT INDEX_NAME, COLUMN_NAME, NON_UNIQUE
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = :db_name AND TABLE_NAME = :table_name
ORDER BY INDEX_NAME, SEQ_IN_INDEX;
```

> `TABLE_SCHEMA` 从 `DATABASE_URL` 解析得到（如 `dt_infra`）。

### 4.3 比较策略（P0、P1）

| 差异类型 | 处理方式 |
|----------|----------|
| `int` vs `int(11)` | 视为等价，不报错 |
| `varchar(20)` vs `varchar(20)` | 完全一致 |
| `datetime` vs `datetime` | 完全一致 |
| `tinyint(1)` vs `boolean` | MySQL 中 `boolean` 即 `tinyint(1)`，视为等价 |
| 字符集/排序规则 | 可选校验，默认 `utf8mb4` / `utf8mb4_unicode_ci` |

### 4.4 P2 校验实现细节

#### 4.4.1 默认值（DEFAULT）

**DDL 解析**：从字段定义中提取 `DEFAULT xxx`、`ON UPDATE CURRENT_TIMESTAMP`。

**归一化规则**：

| DDL 写法 | 归一化后 | 说明 |
|----------|----------|------|
| `DEFAULT NULL` | `NULL` | 空值 |
| `DEFAULT ''` | `''` | 空字符串 |
| `DEFAULT 0` / `DEFAULT '0'` | `0` | 数值或字符串 0 |
| `DEFAULT CURRENT_TIMESTAMP` | `CURRENT_TIMESTAMP` | 创建时间 |
| `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` | `CURRENT_TIMESTAMP ON UPDATE` | 创建+更新时间 |
| 无 DEFAULT | `NULL`（表示无默认值） | |

**比较**：归一化后的期望值与 `information_schema.COLUMNS` 的 `COLUMN_DEFAULT`、`EXTRA`（含 `on update CURRENT_TIMESTAMP`）比对。MySQL 返回的默认值可能带引号（如 `'0'`），需统一处理。

#### 4.4.2 主键（PRIMARY KEY）

**DDL 解析**：从 `PRIMARY KEY (\`col1\`[, \`col2\`...])` 提取主键列列表（按顺序）。

**实际结构**：`information_schema.COLUMNS` 中 `COLUMN_KEY='PRI'` 的列，按 `ORDINAL_POSITION` 排序；或 `information_schema.STATISTICS` 中 `INDEX_NAME='PRIMARY'` 的列，按 `SEQ_IN_INDEX` 排序。

**比较**：主键列名及顺序必须完全一致。差异类型：主键缺失、主键列不同、主键列顺序不同。

#### 4.4.3 索引（KEY、UNIQUE KEY）

**DDL 解析**：从 `KEY \`idx_name\` (\`col1\`[, \`col2\`...])`、`UNIQUE KEY \`idx_name\` (\`col1\`...)` 提取：索引名、列列表（按顺序）、是否唯一。

**实际结构**：查询 `information_schema.STATISTICS`，按 `INDEX_NAME`、`SEQ_IN_INDEX` 聚合，得到每个索引的列列表；`NON_UNIQUE=0` 表示唯一索引。

**比较**：

| 差异类型 | 说明 |
|----------|------|
| 索引缺失 | DDL 中定义的索引在数据库中不存在 |
| 索引多余 | 数据库中存在但 DDL 未定义的索引（可选告警） |
| 索引列不同 | 索引名相同但包含的列或顺序不同 |
| 唯一性不同 | DDL 为 UNIQUE KEY，实际为普通 KEY，或反之 |

> 注：`PRIMARY` 主键索引单独按 4.4.2 校验，不在此处重复。`FOREIGN KEY`、`CONSTRAINT` 不参与校验。

---

## 5. 不一致时的行为

### 5.1 行为策略

| 配置 | 发现不一致时 |
|------|--------------|
| `DB_SCHEMA_CHECK_FAIL_FAST=true` | 记录完整差异报告 → 启动失败（进程退出，返回非 0） |
| `DB_SCHEMA_CHECK_FAIL_FAST=false` | 记录完整差异报告 → 日志 WARNING → 继续启动 |

### 5.2 不一致时的提示要求（必须满足）

**必须明确提示「存在不一致」**，并**明确指出不一致的具体位置**：

| 差异类型 | 输出示例 |
|----------|----------|
| 表缺失 | `[表缺失] pipeline_overview: 数据库中不存在该表` |
| 表多余 | `[表多余] xxx_table: 数据库中存在但 DDL 未定义（可选告警）` |
| 字段缺失 | `[字段缺失] 表 pipeline_overview, 字段 batch: DDL 中定义但数据库中不存在` |
| 字段多余 | `[字段多余] 表 pipeline_overview, 字段 extra_col: 数据库中存在但 DDL 未定义` |
| 类型不同 | `[类型不同] 表 pipeline_overview, 字段 id: DDL=int(11), 实际=bigint(20)` |
| 可空性不同 | `[可空性不同] 表 ums_email, 字段 name: DDL=NOT NULL, 实际=NULL` |
| 默认值不同 | `[默认值不同] 表 pipeline_overview, 字段 created_at: DDL=CURRENT_TIMESTAMP, 实际=NULL` |
| 主键不同 | `[主键不同] 表 pipeline_overview: DDL 主键=id, 实际主键=other_id` |
| 主键缺失 | `[主键缺失] 表 pipeline_overview: DDL 定义主键(id)，数据库中无主键` |
| 索引缺失 | `[索引缺失] 表 pipeline_overview, 索引 idx_batch_subtask: DDL 中定义但数据库中不存在` |
| 索引多余 | `[索引多余] 表 pipeline_overview, 索引 idx_extra: 数据库中存在但 DDL 未定义` |
| 索引列不同 | `[索引列不同] 表 pipeline_overview, 索引 idx_batch_subtask: DDL=(batch,subtask), 实际=(batch)` |
| 索引唯一性不同 | `[索引唯一性不同] 表 ums_email, 索引 email: DDL=UNIQUE, 实际=普通索引` |

### 5.3 输出格式

- **日志**：写入 `app.log`，使用 `logger.error` 或 `logger.warning`，每条差异一行或结构化多行
- **控制台**：启动失败时，将差异报告输出到 stderr，便于运维直接查看
- **结构化**：差异列表可序列化为 JSON 或表格文本，便于人工排查和脚本解析

**示例输出（控制台 / 日志）：**

```
[DB Schema Check] 校验失败，发现 5 处不一致：

[表缺失] sys_audit_log: 数据库中不存在该表
[字段缺失] 表 pipeline_overview, 字段 platform: DDL 中定义但数据库中不存在
[类型不同] 表 ums_email, 字段 employee_id: DDL=varchar(20), 实际=varchar(50)
[索引缺失] 表 pipeline_overview, 索引 idx_batch_subtask: DDL 中定义但数据库中不存在
[默认值不同] 表 pipeline_overview, 字段 created_at: DDL=CURRENT_TIMESTAMP, 实际=NULL

请执行 database/V1.0.9__create_sys_audit_log.sql 等迁移脚本，或联系 DBA 同步表结构。
```

### 5.4 可选：管理端接口 / CLI

| 方式 | 说明 |
|------|------|
| `GET /api/v1/admin/schema-check` | 管理员接口，手动触发校验并返回差异报告（JSON） |
| CLI 脚本 | `python -m backend.cli schema_check` 独立执行校验，便于 CI 或运维脚本调用 |

> 非必须，可在后续迭代中实现。

---

## 6. 异常与边界

| 场景 | 处理策略 |
|------|----------|
| 数据库连接失败 | 视为严重错误：记录 `logger.exception`，启动失败，不继续校验 |
| 表不存在 | 按「表缺失」记录差异，计入不一致总数 |
| 部分表缺失 | 逐表校验，汇总所有差异后一次性输出 |
| 部分字段不一致 | 逐字段校验，汇总所有差异后一次性输出 |
| `DB_SCHEMA_CHECK_ENABLED=false` | 跳过校验，直接进入正常启动流程 |
| DDL 文件缺失 | 视为配置错误：记录 `logger.error`，启动失败 |
| DDL 解析失败 | 视为配置错误：记录 `logger.exception`，启动失败 |

---

## 7. 实现约束

### 7.1 项目规则遵守

- 不修改已有 8 张表结构，不调用 `Base.metadata.create_all()`
- 不执行任何 `ALTER TABLE`、`DROP TABLE` 等 DDL
- 仅做**只读校验**，不改变数据库状态

### 7.2 分层与代码组织

| 层级 | 位置 | 职责 |
|------|------|------|
| Service | `backend/services/schema_check_service.py` | 解析 DDL、查询 information_schema、比较逻辑、生成差异报告 |
| 启动钩子 | `backend/main.py` 或 `backend/startup.py` | lifespan 中调用 schema_check_service，根据配置决定是否 fail-fast |

> 无需新增 Model、Schema、API（除非实现管理端接口）。

### 7.3 日志规范

- 校验通过：`logger.info("DB Schema Check 通过，10 张表结构一致")`
- 校验失败：`logger.error` 或 `logger.warning`，输出完整差异报告
- 连接/解析异常：`logger.exception` 记录完整 traceback
- 不在日志中输出数据库密码、连接串等敏感信息

详见 `docs/06_logging_guide.md`。

---

## 8. 配置项汇总

在 `backend/core/config.py` 和 `.env.example` 中新增：

```python
# 数据库表结构一致性校验
DB_SCHEMA_CHECK_ENABLED: bool = True   # 是否启用启动时校验
DB_SCHEMA_CHECK_FAIL_FAST: bool = True  # 不一致时是否启动失败
```

```bash
# .env.example
DB_SCHEMA_CHECK_ENABLED=true
DB_SCHEMA_CHECK_FAIL_FAST=true
```

---

## 9. 附：表与 DDL 文件映射（实现参考）

```
pipeline_overview       -> database/V1.0.2__create_pipeline_overview.sql
pipeline_history       -> database/V1.0.1__create_pipeline_history.sql
pipeline_failure_reason -> database/V1.0.3__create_pipeline_failure_reason.sql
pipeline_cases         -> database/V1.0.4__create_pipeline_cases.sql
ums_email              -> database/V1.0.5__create_ums_email.sql
ums_module_owner       -> database/V1.0.6__create_ums_module_owner.sql
case_failed_type       -> database/V1.0.7__create_case_failed_type.sql
case_offline_type      -> database/V1.0.8__create_case_offline_type.sql
sys_audit_log          -> database/V1.0.9__create_sys_audit_log.sql
report_snapshot        -> database/V1.1.0__create_report_snapshot.sql
```
