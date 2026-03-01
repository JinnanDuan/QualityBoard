# 日志体系改进规约（Spec）

本文档描述 dt-report 项目从当前简陋日志方式升级到可运维、可排查的完整日志体系的设计方案。

---

## 1. 功能概述

### 1.1 目标

将 dt-report 的日志体系从「仅 uvicorn 输出重定向」升级为具备以下能力的完整体系：

- **可分级**：支持 DEBUG/INFO/WARNING/ERROR 按需过滤
- **可追踪**：每次请求具备 request_id，便于串联完整调用链
- **可运维**：日志轮转、统一文本格式，便于 tail/grep 查看
- **可排查**：应用层业务打点、异常堆栈统一记录、访问日志含响应时间等

### 1.2 适用场景

| 场景 | 需求 |
|------|------|
| 开发调试 | 控制台彩色输出、DEBUG 级别、便于本地排查 |
| 生产运维 | 文件文本输出、INFO 级别、便于 tail/grep 查看 |
| 问题排查 | request_id 串联、异常堆栈完整、访问日志含耗时与状态码 |

### 1.3 与现有方式的对比

| 维度 | 现有方式 | 改进后 |
|------|----------|--------|
| 来源 | 仅 uvicorn stdout/stderr 重定向 | Python logging 统一接管，uvicorn 接入同一配置 |
| 内容 | 仅 HTTP 访问行 | 访问日志 + 应用层业务日志 + 异常堆栈 |
| 格式 | 非结构化文本 | 统一可读文本格式 |
| 追踪 | 无 | request_id 贯穿请求全链路 |
| 轮转 | 无，app.log 持续追加 | 按大小或按天轮转，保留历史 |

---

## 2. 日志架构

### 2.1 输出目标与职责划分

采用 **双文件分离** 策略：

| 文件 | 职责 | 内容 |
|------|------|------|
| `app.log` | 应用层日志 | 业务打点（登录、失败标注、数据库操作等）、异常堆栈、INFO/WARNING/ERROR |
| `access.log` | 访问日志 | 每次 HTTP 请求的路径、方法、状态码、响应时间、User-Agent 等 |

**不单独拆分 error.log**：ERROR 级别日志同时写入 `app.log`，通过日志级别字段区分。若后续有单独错误告警需求，可再扩展。

**文件位置**：默认项目根目录，与现有 `app.log` 保持一致；`access.log` 新增于同目录。可通过配置扩展为 `logs/` 子目录（如 `logs/app.log`、`logs/access.log`）。

### 2.2 与 uvicorn 的集成方式

- **不再使用** `>> app.log 2>&1` 重定向：uvicorn 与 FastAPI 的日志统一由 Python logging 管理。
- **使用 `--log-config`**：将 logging 配置文件路径传给 uvicorn，使 uvicorn 的 access 日志、error 日志均走同一套配置。
- **配置文件形式**：采用 **Python 字典**（dictConfig），便于与 `.env` 配合，支持按环境变量切换级别。
- **加载时机**：应用启动时（`main.py` 或独立 `logging_config.py`）加载配置，再通过 `uvicorn.run(..., log_config=...)` 或 `--log-config` 传入。

### 2.3 环境差异

| 环境 | 判定方式 | 输出目标 | 格式 | 默认级别 |
|------|----------|----------|------|----------|
| 开发 | `ENV=development` 或未设置 | 控制台 + app.log（可选） | 可读文本，含颜色 | DEBUG |
| 生产 | `ENV=production` | app.log + access.log | 可读文本 | INFO |

- **开发环境**：控制台输出便于本地调试；`app.log` 可配置为不输出或仅 ERROR。
- **生产环境**：仅文件输出，统一使用可读文本格式，便于 `tail -f`、`grep` 直接查看。

---

## 3. 日志级别与配置

### 3.1 默认级别

| 环境 | 根 logger | uvicorn.access | uvicorn.error | 应用 logger（backend.*） |
|------|-----------|----------------|---------------|--------------------------|
| 开发 | DEBUG | INFO | INFO | DEBUG |
| 生产 | INFO | INFO | WARNING | INFO |

- **uvicorn.access**：访问日志，生产环境保持 INFO，避免过多噪音。
- **uvicorn.error**：uvicorn 内部错误，生产环境 WARNING 及以上。
- **应用 logger**：业务模块（如 `backend.services.*`、`backend.api.*`）按环境切换 DEBUG/INFO。

### 3.2 配置文件形式与加载方式

- **形式**：Python 代码中的 `dictConfig`，在应用启动时加载。
- **加载**：应用启动时读取，根据 `ENV` 或 `LOG_LEVEL` 环境变量选择对应配置。
- **覆盖**：支持通过 `.env` 中的 `LOG_LEVEL` 等覆盖默认值，不得在代码中硬编码。

### 3.3 与 uvicorn 的协同

- uvicorn 通过 `--log-config <path>` 加载同一份 logging 配置。
- 确保 uvicorn 的 logger 名称（`uvicorn`、`uvicorn.access`、`uvicorn.error`）在配置中有明确定义，避免重复输出或丢失。

---

## 4. 日志格式

### 4.1 统一文本格式

开发与生产环境均使用 **可读文本格式**，便于 `tail -f`、`grep` 直接查看，无需额外解析工具。

### 4.2 格式示例与必含字段

**应用层日志示例**：
```
2025-02-21 10:30:45.123 [INFO] [backend.services.history] [req:abc-123] [GET /api/v1/history?page=1] 查询执行历史，page=1
```

**访问日志示例**：
```
2025-02-21 10:30:45.456 [INFO] [access] [req:abc-123] GET /api/v1/history?page=1 200 45ms 127.0.0.1
```

**必含字段**：

| 字段 | 说明 |
|------|------|
| timestamp | 时间戳，格式 `YYYY-MM-DD HH:mm:ss.SSS` |
| level | 日志级别：DEBUG/INFO/WARNING/ERROR |
| logger | 模块名（如 `backend.services.history_service`） |
| message | 主消息内容 |
| request_id | 可选，有请求上下文时以 `[req:xxx]` 形式展示 |
| endpoint | 可选，有请求上下文时以 `[METHOD /path]` 形式展示 |

**可选扩展**：业务自定义键值对可追加在 message 之后。

### 4.3 时间戳格式与时区

- **格式**：`YYYY-MM-DD HH:mm:ss.SSS`（本地时间）
- **时区**：默认使用系统本地时区（东八区部署环境为 `+08:00`）。

---

## 5. 请求追踪

### 5.1 request_id 生成与传递

- **生成**：请求进入时，由中间件生成 UUID4 作为 `request_id`。
- **传递**：通过 `contextvars`（`contextvars.ContextVar`）在请求生命周期内传递，确保同一请求内所有 logger 调用均可获取。
- **响应头**：在 HTTP 响应头中返回 `X-Request-ID`，便于前端或网关关联。

### 5.2 日志中注入 request_id 与 endpoint

- 使用 **Filter** 或 **Formatter 的 `extra` 机制**：从 `contextvars` 读取 `request_id`、`endpoint`，注入到每条日志记录的 `extra` 中。
- 若当前无请求上下文（如定时任务、启动阶段），`request_id`、`endpoint` 可为空或 `-`。

### 5.3 访问日志字段清单

每次 HTTP 请求完成后，由中间件或 uvicorn 的 access 日志记录以下字段：

| 字段 | 说明 |
|------|------|
| method | HTTP 方法（GET/POST 等） |
| path | 请求路径（含 query，如 `/api/v1/history?page=1`） |
| status_code | HTTP 状态码 |
| duration_ms | 响应耗时（毫秒） |
| client_ip | 客户端 IP |
| user_agent | User-Agent（可选，可截断过长内容） |
| request_id | 本次请求的 request_id |

**敏感路径**：对 `/api/v1/auth/login` 等路径，请求体不记录或仅记录「已登录/登录失败」等摘要，不记录密码（见第 8 节）。

---

## 6. 应用层日志

### 6.1 关键业务打点清单

| 模块/场景 | 打点位置 | 级别 | 内容摘要 |
|----------|----------|------|----------|
| 认证 | 登录成功 | INFO | 用户标识、登录方式 |
| 认证 | 登录失败 | WARNING | 原因（密码错误/用户不存在等），不记录密码 |
| 失败标注 | 失败标注提交 | INFO | 记录数、失败类型、跟踪人（脱敏） |
| 失败标注 | 失败标注提交失败 | ERROR | 原因、异常摘要 |
| 数据库 | 连接异常 | ERROR | 异常类型、连接信息（不含密码） |
| 数据库 | 连接池耗尽 | WARNING | 当前等待数 |
| API 入口 | 请求开始（可选） | DEBUG | 路径、方法 |
| API 异常 | 未捕获异常 | ERROR | 完整 traceback、request_id |

**说明**：打点位置为「规约」层面，具体实现时在对应 Service、API 或中间件中插入。

### 6.2 各级别适用场景

| 级别 | 适用场景 |
|------|----------|
| DEBUG | 开发调试、入参/出参摘要、SQL 语句（若开启） |
| INFO | 正常业务流程、关键操作成功（登录、标注提交、数据变更） |
| WARNING | 可恢复的异常、登录失败、参数校验失败、业务规则违反 |
| ERROR | 未捕获异常、数据库连接失败、外部服务调用失败 |

### 6.3 异常堆栈记录方式

- **ERROR 级别**：记录完整 traceback，便于排查。
- **格式**：在 message 之后追加换行，输出完整 traceback 文本。
- **避免**：不在 WARNING 中记录完整堆栈，仅记录异常类型与简要消息。

---

## 7. 日志轮转

### 7.1 轮转策略

采用 **Python 内置 RotatingFileHandler**（按大小轮转）：

- **触发条件**：单文件达到 10MB 时轮转。
- **保留份数**：保留 5 个历史文件（即 `app.log`、`app.log.1` … `app.log.5`）。
- **轮转后**：新日志继续写入 `app.log`，旧内容移至 `app.log.1`，依次滚动。

**备选**：若需按天轮转，可使用 `TimedRotatingFileHandler`，保留 7 天；或使用系统 `logrotate` 对 `app.log`、`access.log` 做外部轮转。规约优先采用 RotatingFileHandler，与 Python 配置一体化，减少外部依赖。

### 7.2 保留策略

| 文件 | 单文件大小上限 | 保留份数 | 总占用约 |
|------|----------------|----------|----------|
| app.log | 10MB | 5 | 50MB |
| access.log | 10MB | 3 | 30MB |

### 7.3 轮转后文件命名

- **RotatingFileHandler 默认**：`app.log`、`app.log.1`、`app.log.2` …
- **TimedRotatingFileHandler**：`app.log`、`app.log.2025-02-20`、`app.log.2025-02-19` …

---

## 8. 敏感信息过滤

### 8.1 需脱敏的字段类型

| 类型 | 示例 | 说明 |
|------|------|------|
| 密码 | 请求体中的 `password`、`pwd` | 登录、修改密码等 |
| Token | `Authorization: Bearer xxx`、`token`、`access_token` | JWT、API Key |
| 数据库连接串 | `DATABASE_URL` 中的密码部分 | 仅在日志中引用时脱敏 |
| 其他 | 根据业务扩展 | 如身份证、手机号等（若未来涉及） |

### 8.2 脱敏方式

- **密码、Token**：完全替换为 `***`，不保留任何原文。
- **Authorization Header**：整体替换为 `***`，或仅保留 `Bearer` 前缀 + `***`。
- **数据库 URL**：若需记录连接信息（如仅主机名），密码部分替换为 `***`。

### 8.3 实现位置

- **Formatter 层**：自定义 Formatter，在输出前对 `message` 或 `extra` 中的敏感键进行替换。
- **中间件层**：记录访问日志时，对请求头、请求体进行预处理，剔除或脱敏后再传入 logger。
- **业务层**：打日志时避免直接传入密码、Token，仅传「已提交」「登录失败」等摘要。

---

## 9. 与现有脚本及文档的衔接

### 9.1 scripts/start.sh 变更

- **移除** `>> "$LOG_FILE" 2>&1` 重定向：日志由 Python logging 写入文件，无需 shell 重定向。
- **保留** `LOG_FILE` 变量：可用于脚本内「提示用户日志位置」或 `tail -f` 示例，实际路径与 logging 配置一致（如 `app.log`）。
- **可选**：若采用 `logs/` 目录，需在启动前 `mkdir -p logs`，确保目录存在。

### 9.2 scripts/stop.sh / restart.sh

- **无变更**：仅依赖 PID 文件终止进程，与日志输出方式无关。

### 9.3 文档同步点

| 文档 | 需同步内容 |
|------|------------|
| `docs/03_deployment_guide.md` | 6.3 节「日志文件为 app.log」→ 补充 access.log、轮转说明、`logs/` 目录（若采用）；「查看实时日志」示例可增加 `tail -f logs/app.log`（若路径变更） |
| `docs/04_project_structure.md` | 根目录 `app.log` 说明 → 补充 access.log、logs/ 目录（若采用）；`scripts/start.sh` 说明 → 移除「重定向到 app.log」，改为「由 Python logging 写入」 |
| `README.md` | 若存在日志相关说明，需与上述保持一致 |
| `.gitignore` | 已包含 `*.log`，若采用 `logs/` 目录，可增加 `logs/` 或保持 `*.log` 覆盖 |

---

## 10. 配置契约摘要

为便于后续实现，规约约定以下配置项（通过 `.env` 或环境变量覆盖，不硬编码）：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| ENV | 环境：development / production | development |
| LOG_LEVEL | 根 logger 级别 | 随 ENV |
| LOG_DIR | 日志目录（空则项目根目录） | 空 |
| LOG_APP_MAX_BYTES | app.log 单文件最大字节 | 10485760（10MB） |
| LOG_APP_BACKUP_COUNT | app.log 保留份数 | 5 |
| LOG_ACCESS_MAX_BYTES | access.log 单文件最大字节 | 10485760 |
| LOG_ACCESS_BACKUP_COUNT | access.log 保留份数 | 3 |
