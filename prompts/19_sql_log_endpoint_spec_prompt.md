# 角色设定

你是本项目的运维与可观测性专家，精通 Python/FastAPI 应用的日志体系设计。你熟悉 Python logging 模块、SQLAlchemy 日志、contextvars 请求上下文传递、以及 FastAPI 中间件机制。你擅长在「开发调试便利性」与「生产环境性能/安全」之间做合理权衡。

# 任务目标

请输出一份 Markdown 格式的 **SQL 日志关联触发接口规约（Spec）**，不要写任何代码。该规约是**增量规约**，在现有 `spec/05_log_spec.md` 及已实现的日志体系基础上，补充「在 SQL 日志中展示触发该 SQL 的 API 接口」的设计方案。该规约将作为后续 AI 编程的契约。

# 输入信息

## 1. 当前实现现状

### 1.1 SQL 日志机制

- **开关**：`.env` 中 `LOG_SQL=true` 时，SQLAlchemy 的 `echo=True` 将 SQL 输出到 `sqlalchemy.engine` logger
- **输出目标**：`app.log`（与 app_file handler 一致）
- **日志格式**：`%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s] %(request_id)s %(message)s`
- **当前示例**：
  ```
  2026-03-01 18:28:22.383 [INFO] [sqlalchemy.engine.Engine] [req:2ce20b0b-3dfa-4d64-b353-f3fa6633a044] SELECT DISTINCT pipeline_history.start_time ...
  ```

### 1.2 已有能力

| 能力 | 说明 |
|------|------|
| **request_id** | 每条 SQL 日志已带 `[req:xxx]`，由 RequestIdFilter 从 contextvars 注入 |
| **access.log** | 记录 method、path、status_code、duration_ms、client_ip，同样带 request_id |
| **关联方式** | 可通过 `grep "req:xxx" app.log access.log` 串联一次请求的完整链路，在 access.log 中查到对应接口 |

### 1.3 当前缺失

- **SQL 日志行内不直接显示接口**：开发调试时需先记下 request_id，再 grep access.log 才能知道是哪个接口触发的 SQL，无法一眼看出

## 2. 期望能力

在打印 SQL 日志时，**在日志行内直接展示触发该 SQL 的 API 接口**（如 `GET /api/v1/history` 或 `POST /api/v1/failure-reason`），便于：

- 开发调试时快速定位「这条 SQL 是哪个接口产生的」
- 排查慢查询时无需二次 grep，直接根据接口路径过滤
- 与现有 request_id 机制兼容，不破坏已有串联能力

## 3. 相关技术组件（规约需考虑）

| 组件 | 路径 | 说明 |
|------|------|------|
| 请求上下文 | `backend/core/request_id.py` | contextvars 存储 request_id |
| 中间件 | `backend/middleware/request_id.py` | 生成并注入 request_id |
| 中间件 | `backend/middleware/access_log.py` | 记录 method、path 等，在响应后写入 |
| 日志 Filter | `backend/logging_config.py` RequestIdFilter | 从 contextvars 读取 request_id 注入 LogRecord |
| SQL 日志 | `sqlalchemy.engine` logger | 使用 app_file handler，经 RequestIdFilter |
| 数据库层 | `backend/core/database.py` | create_async_engine(echo=settings.LOG_SQL) |

## 4. 项目约束（规约需遵守）

- **技术栈**：Python 3.8 / FastAPI / SQLAlchemy 2.0 async / aiomysql
- **日志规范**：遵循 `docs/06_logging_guide.md`、`spec/05_log_spec.md`，不得在日志中记录密码、Token 等敏感信息
- **配置**：新增配置项通过 `.env` 读取，不得硬编码
- **向后兼容**：现有 `grep "req:xxx" app.log access.log` 的排查方式应继续可用

# 规约必须明确界定的内容

1. **需求边界**
   - 作用范围：仅 SQL 日志（`sqlalchemy.engine`）还是扩展至其他应用层日志？
   - 非 HTTP 场景：定时任务、启动阶段等无请求上下文时，接口字段如何展示（如 `-` 或 `[non-http]`）？
   - 可选开关：是否通过配置（如 `LOG_SQL_SHOW_ENDPOINT`）控制，以便生产环境在关闭 LOG_SQL 时不受影响？

2. **接口信息的获取与传递**
   - 在何处获取 method + path：中间件（请求进入时）vs 其他位置
   - 存储方式：contextvars（与 request_id 类似）vs 其他
   - 格式约定：`GET /api/v1/history`、`POST /api/v1/failure-reason` 等，是否包含 query string？

3. **日志格式变更**
   - 在现有格式中如何插入接口信息：`%(request_id)s` 之后追加 `%(endpoint)s`？或合并为 `[req:xxx][GET /api/v1/history]`？
   - 仅 SQL 日志使用新格式，还是所有 app.log 统一扩展？
   - 格式示例（规约需给出 Before/After 对比）

4. **实现层级**
   - Filter 扩展（在 RequestIdFilter 中增加 endpoint）vs 新建 EndpointFilter vs 自定义 Formatter
   - 中间件顺序：RequestIdMiddleware、AccessLogMiddleware 与「注入 endpoint 的中间件」的先后关系
   - 对 SQLAlchemy echo 输出的影响：SQLAlchemy 使用标准 logging，是否需特殊处理？

5. **性能与安全**
   - 路径中是否可能包含敏感信息（如 `/api/v1/user/12345`），是否需要脱敏或截断？
   - 额外 contextvars 与 Filter 逻辑的性能开销是否可接受？

6. **与现有脚本及文档的衔接**
   - `docs/06_logging_guide.md` 中「5. SQL 日志」章节需同步更新的内容
   - `spec/05_log_spec.md` 中需补充或修订的条款

# 格式要求

请以如下结构输出 Spec（可整体输出，作为 `spec/06_sql_log_endpoint_spec.md` 的初稿，或作为 `spec/05_log_spec.md` 的增补章节）：

```
# SQL 日志关联触发接口规约（Spec）

本文档描述在现有日志体系基础上，为 SQL 日志增加「触发接口」展示能力的设计方案。本规约为 spec/05_log_spec.md 的增量扩展。

## 1. 功能概述

[目标、适用场景、与当前方式的对比]

## 2. 需求边界

[作用范围、非 HTTP 场景、配置开关]

## 3. 接口信息的获取与传递

[获取时机、存储方式、格式约定]

## 4. 日志格式变更

[格式设计、Before/After 示例、适用范围]

## 5. 实现设计

[Filter/Formatter 选型、中间件顺序、与 SQLAlchemy 的协同]

## 6. 性能与安全

[敏感路径处理、性能考量]

## 7. 与现有文档的衔接

[06_logging_guide.md、05_log_spec.md 的同步更新点]
```

# 约束与原则

- 所有用户可见文字使用中文。
- 规约不涉及具体代码实现，仅描述架构、数据流、格式约定、配置契约等设计层面的内容。
- 需与现有 `request_id`、`access.log` 机制兼容，不破坏已有排查流程。
- 规约需明确「仅当 LOG_SQL=true 时生效」或类似的配置约束，避免生产环境误开启带来的影响。
