# SQL 日志关联触发接口规约（Spec）

本文档描述在现有日志体系基础上，为 SQL 日志增加「触发接口」展示能力的设计方案。本规约为 `spec/05_log_spec.md` 的增量扩展。

---

## 1. 功能概述

### 1.1 目标

在 SQL 日志行内**直接展示触发该 SQL 的 API 接口**（如 `GET /api/v1/history`），使开发调试时无需二次 grep，即可一眼看出「这条 SQL 是哪个接口产生的」。

### 1.2 适用场景

| 场景 | 需求 |
|------|------|
| 开发调试 | 开启 LOG_SQL 后，tail -f app.log 时直接根据接口路径定位问题 SQL |
| 慢查询排查 | 按接口路径过滤 SQL 日志，快速定位某接口的数据库调用 |
| 问题复现 | 结合 request_id、endpoint，完整串联一次请求的 SQL 执行链 |

### 1.3 与当前方式的对比

| 维度 | 当前方式 | 本规约改进后 |
|------|----------|--------------|
| SQL 日志内容 | 仅含 request_id、SQL 语句 | 增加 `[GET /api/v1/history]` 等接口标识 |
| 关联接口 | 需 `grep "req:xxx" access.log` 二次查询 | 日志行内直接展示，无需二次 grep |
| request_id | 保留 | 保留，不破坏现有串联能力 |

---

## 2. 需求边界

### 2.1 作用范围

- **主要受益**：`sqlalchemy.engine` 产生的 SQL 日志（由 LOG_SQL 控制是否输出）
- **扩展范围**：所有写入 `app.log` 的日志（经 app_file handler）均可带上 endpoint，包括 backend.*、uvicorn、sqlalchemy.engine 等
- **不涉及**：`access.log` 已有 method、path，无需变更

采用「统一扩展」策略：在请求上下文中注入 endpoint 后，所有经 RequestIdFilter 的日志均可选择展示。实现时通过扩展 Filter 注入 `record.endpoint`，Formatter 中增加 `%(endpoint)s` 占位符即可。这样 SQL 日志、业务日志、uvicorn 日志在 HTTP 请求场景下均能展示触发接口。

### 2.2 非 HTTP 场景

定时任务、应用启动阶段、后台线程等无请求上下文时：

- `endpoint` 展示为 `-`（与 request_id 无上下文时的约定一致）
- 不影响现有日志输出，仅 endpoint 字段为空占位

### 2.3 配置约束

- **不新增独立开关**：endpoint 展示与 `LOG_SQL` 解耦。endpoint 是请求上下文的通用能力，只要在 HTTP 请求内产生的日志都会带上。
- **生效条件**：当 `LOG_SQL=true` 时，SQL 会输出，此时 endpoint 会一并展示；当 `LOG_SQL=false` 时，SQL 不输出，endpoint 能力对 SQL 无影响，但对其他 app.log 日志仍生效。
- **生产环境**：生产环境通常 `LOG_SQL=false`，SQL 不打印，故无额外日志膨胀；若生产临时开启 LOG_SQL 排查问题，endpoint 可帮助快速定位接口。

---

## 3. 接口信息的获取与传递

### 3.1 获取时机

在 **RequestIdMiddleware** 的 `dispatch` 入口处获取。该中间件最先执行（最后 add_middleware），在 `call_next` 之前即可拿到 `request.method`、`request.url.path`、`request.query_params`。

### 3.2 存储方式

采用 **contextvars**，与 request_id 一致：

- 在 `backend/core/request_id.py` 同级或同模块中增加 `request_endpoint_var: ContextVar[Optional[str]]`
- 提供 `get_request_endpoint()`、`set_request_endpoint()`、`clear_request_endpoint()`
- 在 RequestIdMiddleware 的 `try/finally` 中，与 request_id 同步：入口 `set`，出口 `clear`

### 3.3 格式约定

| 要素 | 约定 |
|------|------|
| 格式 | `{METHOD} {path}`，如 `GET /api/v1/history`、`POST /api/v1/failure-reason` |
| path | 包含 path + query string，与 access.log 一致，便于精确关联 |
| 长度 | 建议单行不超过 256 字符，超出部分截断并加 `...`，避免超长 query 撑爆日志 |
| 大小写 | METHOD 使用大写（GET、POST、PUT、DELETE 等） |

**示例**：

- `GET /api/v1/history`
- `GET /api/v1/history?page=1&pageSize=20`
- `POST /api/v1/failure-reason`

---

## 4. 日志格式变更

### 4.1 格式设计

在现有格式的 `%(request_id)s` 之后追加 `%(endpoint)s`：

**当前格式**：
```
%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s] %(request_id)s %(message)s
```

**变更后格式**：
```
%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s] %(request_id)s %(endpoint)s %(message)s
```

其中 `%(endpoint)s` 有请求上下文时为 `[GET /api/v1/history]` 形式，无上下文时为 `-`。

### 4.2 Before/After 示例

**Before**：
```
2026-03-01 18:28:22.383 [INFO] [sqlalchemy.engine.Engine] [req:2ce20b0b-3dfa-4d64-b353-f3fa6633a044] SELECT DISTINCT pipeline_history.start_time FROM pipeline_history WHERE ...
```

**After**：
```
2026-03-01 18:28:22.383 [INFO] [sqlalchemy.engine.Engine] [req:2ce20b0b-3dfa-4d64-b353-f3fa6633a044] [GET /api/v1/history?page=1] SELECT DISTINCT pipeline_history.start_time FROM pipeline_history WHERE ...
```

**非 HTTP 场景**：
```
2026-03-01 18:30:00.000 [INFO] [backend.services.xxx] - - 定时任务执行完成
```

### 4.3 适用范围

- **default formatter**（app_file、console 使用）：增加 `%(endpoint)s`
- **access formatter**：不增加 endpoint（access.log 的 message 本身已是 method + path，无需重复）
- 所有使用 default formatter 的 logger（uvicorn、uvicorn.error、backend、sqlalchemy.engine、root）均自动获得 endpoint 展示能力

---

## 5. 实现设计

### 5.1 Filter/Formatter 选型

**方案**：扩展 **RequestIdFilter**，在注入 `record.request_id` 的同时注入 `record.endpoint`。

- **理由**：request_id 与 endpoint 同属请求上下文，逻辑集中，避免新增 Filter 链
- **备选**：若希望职责更清晰，可新建 `RequestContextFilter` 统一注入 request_id、endpoint，并逐步迁移 RequestIdFilter 的职责

**Formatter**：在 default formatter 的 format 字符串中增加 `%(endpoint)s` 占位符。需确保 LogRecord 在 format 前已具备 `endpoint` 属性，否则需在 Filter 中为无 endpoint 场景设置 `record.endpoint = "-"`。

### 5.2 中间件顺序

当前顺序（main.py 中 add_middleware 的调用顺序）：

1. CORSMiddleware
2. AccessLogMiddleware
3. RequestIdMiddleware（最后添加，最先执行）

**无需新增中间件**。在 RequestIdMiddleware 的 `dispatch` 中，与 `set_request_id(rid)` 同时调用 `set_request_endpoint(...)`，在 `finally` 中与 `clear_request_id()` 同时调用 `clear_request_endpoint()`。

**注意**：RequestIdMiddleware 先于 AccessLogMiddleware 执行，因此 RequestIdMiddleware 执行时，request 对象已就绪，可正确获取 method、path、query。

### 5.3 与 SQLAlchemy 的协同

- SQLAlchemy 的 `echo=True` 将 SQL 输出到 `sqlalchemy.engine` logger
- 该 logger 使用 app_file handler，经 RequestIdFilter（及 SensitiveDataFilter）
- 只要 RequestIdFilter 注入 `record.endpoint`，Formatter 使用 `%(endpoint)s`，SQL 日志即可自动带上 endpoint
- **无需对 SQLAlchemy 做任何特殊配置**，其使用标准 Python logging，与现有机制完全兼容

---

## 6. 性能与安全

### 6.1 敏感路径处理

- **path 与 query**：与 access.log 一致，记录完整 path 及 query string。当前 access.log 已记录 `GET /api/v1/history?page=1` 等，未对 path/query 做脱敏。
- **潜在风险**：query 中可能含 `token=xxx`、`key=xxx` 等敏感参数。若业务存在此类接口，建议：
  - 在 endpoint 组装时，对已知敏感 query 参数做脱敏（如替换为 `***`）
  - 或对 endpoint 总长度做截断（如 256 字符），减少敏感信息暴露面
- **规约建议**：首版实现与 access.log 保持一致，不做额外脱敏；若后续发现敏感路径，在 SensitiveDataFilter 或专门逻辑中扩展对 `record.endpoint` 的脱敏。

### 6.2 性能考量

- **contextvars**：读写开销极小，与 request_id 相同，可忽略
- **Filter 扩展**：在 RequestIdFilter 中增加一次 `get_request_endpoint()` 调用及 `record.endpoint` 赋值，开销可接受
- **字符串组装**：`f"{method} {path}"` 在请求入口执行一次，对整体延迟影响可忽略

---

## 7. 与现有文档的衔接

### 7.1 docs/06_logging_guide.md

| 章节 | 需同步内容 |
|------|------------|
| **1. 日志架构** | 表格中 app.log 说明增加「含 endpoint（触发接口）」 |
| **2. 配置** | 无需新增配置项，保持现有 LOG_SQL 等说明 |
| **4. 查看日志** | 增加示例：`grep "GET /api/v1/history" app.log` 按接口过滤 SQL |
| **5. SQL 日志** | 补充：开启 LOG_SQL 后，SQL 日志行内会展示触发接口（如 `[GET /api/v1/history]`） |

### 7.2 spec/05_log_spec.md

| 章节 | 需同步内容 |
|------|------------|
| **4. 日志格式** | 4.2 节「必含字段」表格增加 `endpoint`：可选，有请求上下文时以 `[METHOD /path]` 形式展示 |
| **4. 日志格式** | 4.2 节「应用层日志示例」更新为含 endpoint 的格式 |
| **5. 请求追踪** | 5.2 节「日志中注入 request_id」扩展为「注入 request_id 与 endpoint」 |
| **10. 配置契约摘要** | 无需新增配置项 |

### 7.3 .env.example

无需新增配置项。若未来增加 `LOG_SQL_SHOW_ENDPOINT` 等开关，再补充说明。

---

## 8. 配置契约摘要（本规约涉及）

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| LOG_SQL | 为 true 时在 app.log 打印所有 SQL；此时 SQL 日志会同时展示 endpoint | false |

本规约不新增配置项，endpoint 展示随请求上下文自动生效。
