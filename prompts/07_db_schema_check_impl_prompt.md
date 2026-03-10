# 数据库表结构一致性校验 — 实现 Prompt

请严格按照 `spec/07_db_schema_check_spec.md` 实现「系统启动时数据库表结构一致性校验」功能。

---

## 一、必读文档

1. **功能规约**：`spec/07_db_schema_check_spec.md`（全文精读，所有实现必须符合该 spec）
2. **项目规则**：`.cursor/rules/project.mdc`（技术栈、数据库红线、分层契约）
3. **日志规范**：`docs/06_logging_guide.md`

---

## 二、实现清单

### 1. 配置层

- 在 `backend/core/config.py` 中新增：
  - `DB_SCHEMA_CHECK_ENABLED: bool = True`
  - `DB_SCHEMA_CHECK_FAIL_FAST: bool = True`
- 使用 `_parse_bool` 或 `field_validator` 解析 env 中的布尔值（参考 `LOG_SQL`、`LDAP_USE_NETBIOS`）
- 在 `.env.example` 中新增上述两项及注释

### 2. Service 层

新建 `backend/services/schema_check_service.py`，实现：

| 函数/职责 | 说明 |
|----------|------|
| `parse_ddl_file(path) -> dict` | 解析单个 DDL 文件，提取表名、字段列表（名、类型、NULL/NOT NULL、DEFAULT）、主键、索引。可使用正则或 `sqlparse` |
| `get_expected_schema() -> dict` | 按 spec 第 9 节的表-DDL 映射，读取 `database/` 下 10 个 DDL 文件，返回「表名 -> 期望结构」的字典 |
| `get_actual_schema(db_name, engine) -> dict` | 通过 `information_schema` 查询实际表结构，返回「表名 -> 实际结构」的字典。需使用 `text()` 执行原生 SQL，可用 `engine.connect()` 或注入 `AsyncSession` |
| `compare_schemas(expected, actual) -> List[dict]` | 逐表、逐字段比较，返回差异列表。每条差异为 `{"type": "表缺失"|"字段缺失"|"字段多余"|"类型不同"|"可空性不同"|..., "table": str, "field": str|None, "detail": str}` |
| `run_schema_check() -> Tuple[bool, List[dict]]` | 主入口：获取期望结构 → 获取实际结构 → 比较 → 返回 (是否一致, 差异列表) |

**类型等价规则**（spec 4.3）：`int` 与 `int(11)` 等价，`tinyint(1)` 与 `boolean` 等价。

**DATABASE_URL 解析**：从 `settings.DATABASE_URL` 解析出数据库名（如 `mysql+aiomysql://user:pass@host:port/dt_infra` → `dt_infra`）。注意 URL 中可能含 `?charset=utf8mb4`，需正确解析。

### 3. 启动钩子

修改 `backend/main.py`：

- 添加 `lifespan` 上下文管理器（FastAPI 0.115 支持 `lifespan` 参数）
- 在 startup 阶段：
  1. 若 `DB_SCHEMA_CHECK_ENABLED=false`，跳过校验
  2. 否则调用 `run_schema_check()`
  3. 若存在差异且 `DB_SCHEMA_CHECK_FAIL_FAST=true`：将差异报告输出到 stderr、写入 logger.error，然后 `raise SystemExit(1)` 或 `sys.exit(1)` 使进程退出
  4. 若存在差异且 `DB_SCHEMA_CHECK_FAIL_FAST=false`：写入 logger.warning，继续启动
  5. 若一致：`logger.info("DB Schema Check 通过，10 张表结构一致")`

**注意**：lifespan 中需要获取数据库连接。可使用 `engine = create_async_engine(settings.DATABASE_URL)` 创建临时引擎，或复用 `backend.core.database.engine`。校验为只读操作，不修改数据库。

### 4. 差异报告格式

严格按 spec 5.2 的输出示例：

```
[DB Schema Check] 校验失败，发现 N 处不一致：

[表缺失] sys_audit_log: 数据库中不存在该表
[字段缺失] 表 pipeline_overview, 字段 platform: DDL 中定义但数据库中不存在
[类型不同] 表 ums_email, 字段 employee_id: DDL=varchar(20), 实际=varchar(50)

请执行 database/V1.0.9__create_sys_audit_log.sql 等迁移脚本，或联系 DBA 同步表结构。
```

### 5. 异常处理

按 spec 第 6 节：

- 数据库连接失败 → `logger.exception`，启动失败
- DDL 文件缺失或解析失败 → `logger.error` / `logger.exception`，启动失败
- 不在日志中输出密码、连接串等敏感信息

---

## 三、实现约束

1. **Python 3.8**：类型标注使用 `Optional[X]`，禁止 `X | None`
2. **只读校验**：不执行任何 `ALTER`、`DROP`、`CREATE`
3. **项目根目录**：`database/` 路径为 `Path(__file__).resolve().parent.parent.parent / "database"`
4. **依赖**：若使用 `sqlparse`，需加入 `backend/requirements.txt` 并锁定版本；若用正则解析 DDL，可不新增依赖

---

## 四、校验粒度（实现优先级）

- **P0（必须）**：表是否存在、字段是否存在
- **P1（必须）**：字段类型、是否可空（含 int/int(11) 等价处理）
- **P2（可选）**：默认值、主键、索引 — 首版可暂不实现，在代码中留 TODO

---

## 五、验证方式

实现完成后：

1. 正常库：启动应成功，日志有 `DB Schema Check 通过`
2. 缺表：删除某表后启动，应 fail-fast，控制台和日志有明确差异报告
3. 改字段：手动 ALTER 某字段类型后启动，应检测到「类型不同」
4. `DB_SCHEMA_CHECK_ENABLED=false`：应跳过校验，正常启动
5. `DB_SCHEMA_CHECK_FAIL_FAST=false`：有差异时仅 WARNING，不退出
