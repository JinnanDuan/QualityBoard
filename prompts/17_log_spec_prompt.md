# 角色设定

你是本项目的运维与可观测性专家，精通 Python/FastAPI 应用的日志体系设计。你熟悉 Python logging 模块、uvicorn 日志配置、结构化日志（JSON）、请求追踪（request_id）以及日志轮转（logrotate / RotatingFileHandler）等实践。你擅长在「开发调试」「生产运维」「问题排查」之间平衡日志粒度与性能开销。

# 任务目标

请输出一份 Markdown 格式的 **日志体系改进规约（Spec）**，不要写任何代码。该规约是**独立规约**，描述 dt-report 项目从当前简陋日志方式升级到可运维、可排查的完整日志体系的设计方案。该规约将作为后续 AI 编程的契约。

# 输入信息

## 1. 当前日志现状

### 1.1 来源与输出

- **来源**：只有 uvicorn 的 stdout/stderr 被重定向到 `app.log`
- **启动方式**：`scripts/start.sh` 中通过 `nohup uvicorn ... >> app.log 2>&1` 启动
- **内容**：主要是 HTTP 访问日志，例如：`INFO: 127.0.0.1:xxx - "GET /api/v1/history HTTP/1.1" 200 OK`

### 1.2 已知问题

| 能力 | 说明 |
|------|------|
| **应用层日志** | 业务逻辑（登录、失败标注、数据库异常等）没有显式打日志 |
| **日志级别** | 未配置 DEBUG/INFO/WARNING/ERROR，难以按级别过滤 |
| **时间戳** | uvicorn 默认格式里时间信息不够清晰 |
| **请求追踪** | 无 request_id，无法串联一次请求的完整链路 |
| **错误详情** | 异常堆栈依赖 uvicorn 输出，格式不统一 |
| **日志轮转** | `app.log` 持续追加，无按大小/时间切割，易占满磁盘 |
| **访问日志格式** | 缺少响应时间、User-Agent、请求体大小等 |
| **敏感信息过滤** | 未对密码、token 等做脱敏 |

## 2. 可考虑的改进方向（供规约参考）

1. **配置 Python logging**：在 `backend/main.py` 或单独配置文件中设置 logging，使用 `--log-config` 传给 uvicorn
2. **增加应用层日志**：在关键业务（登录、失败标注、数据库操作等）处打 `logger.info` / `logger.error`
3. **接入 logrotate**：对 `app.log` 做按大小或按天轮转
4. **统一日志格式**：如 JSON，便于后续接入 ELK、Loki 等
5. **增加中间件**：记录请求 ID、耗时、状态码等，并写入日志

## 3. 项目技术栈约束（规约需遵守）

- **后端**：Python 3.8 / FastAPI / uvicorn
- **部署**：单端口模式，通过 `scripts/start.sh` / `stop.sh` / `restart.sh` 管理启停
- **日志文件**：当前约定为项目根目录 `app.log`，规约可扩展为多文件或目录结构

# 规约必须明确界定的内容

1. **日志架构**
   - 日志输出目标：单文件 vs 多文件（如 access.log / app.log / error.log 分离）
   - 与 uvicorn 的关系：是否继续重定向 stdout/stderr，还是完全由 Python logging 接管
   - 开发环境 vs 生产环境的差异（如控制台彩色输出 vs 文件 JSON 输出）

2. **日志级别与配置**
   - 默认级别（DEBUG/INFO/WARNING/ERROR）及按模块/按环境的覆盖规则
   - 日志配置文件的形式（Python 代码 / YAML / JSON）及加载方式
   - uvicorn 的 `--log-config` 如何与自定义 logging 配置协同

3. **日志格式**
   - 文本格式 vs JSON 格式的选用场景
   - 必须包含的字段：时间戳、级别、模块名、消息、以及（可选）request_id、trace_id
   - 时间戳的格式与时区约定

4. **请求追踪**
   - request_id 的生成方式（UUID）及传递方式（中间件、上下文变量）
   - 在日志中如何注入 request_id（Formatter 自定义字段 / 上下文变量）
   - 访问日志中需记录的字段：路径、方法、状态码、响应时间、User-Agent、请求体大小等

5. **应用层日志**
   - 需打日志的关键业务点清单（如：登录成功/失败、失败标注提交、数据库连接异常、API 入参/出参摘要等）
   - 各级别（INFO/WARNING/ERROR）的适用场景
   - 异常堆栈的记录方式（完整 traceback vs 精简信息）

6. **日志轮转**
   - 轮转策略：按大小（RotatingFileHandler）vs 按时间（TimedRotatingFileHandler）vs 外部 logrotate
   - 保留份数 / 保留天数
   - 轮转后文件的命名规则（如 app.log.1, app.log.2025-02-21）

7. **敏感信息过滤**
   - 需脱敏的字段类型：密码、token、Authorization header、请求体中的敏感字段
   - 脱敏方式：完全替换为 `***` vs 部分掩码
   - 在何处实现：Formatter 过滤 vs 中间件预处理

8. **与现有脚本的衔接**
   - `scripts/start.sh` 是否需要修改（如不再重定向到 app.log，或改为启动前检查日志目录）
   - `scripts/stop.sh` / `restart.sh` 是否受影响
   - 文档（如 `docs/03_deployment_guide.md`、`docs/04_project_structure.md`）中需同步更新的描述

# 格式要求

请以如下结构输出 Spec（可整体输出，作为 `spec/05_log_spec.md` 的初稿）：

```
# 日志体系改进规约（Spec）

本文档描述 dt-report 项目从当前简陋日志方式升级到可运维、可排查的完整日志体系的设计方案。

## 1. 功能概述

[目标、适用场景、与现有方式的对比]

## 2. 日志架构

### 2.1 输出目标与职责划分

[单文件/多文件、access vs app vs error 的职责]

### 2.2 与 uvicorn 的集成方式

[stdout 重定向策略、--log-config 使用方式]

### 2.3 环境差异

[开发 vs 生产的格式、级别、输出目标]

## 3. 日志级别与配置

[默认级别、配置文件形式、加载方式]

## 4. 日志格式

[文本/JSON 选用、必含字段、时间戳格式]

## 5. 请求追踪

[request_id 生成与传递、访问日志字段清单]

## 6. 应用层日志

[关键业务打点清单、级别适用场景、异常记录方式]

## 7. 日志轮转

[轮转策略、保留策略、文件命名]

## 8. 敏感信息过滤

[脱敏字段、脱敏方式、实现位置]

## 9. 与现有脚本及文档的衔接

[start.sh / stop.sh / restart.sh 变更、文档同步点]
```

# 约束与原则

- 所有用户可见文字使用中文。
- 规约不涉及具体代码实现，仅描述架构、配置契约、打点位置、格式约定等设计层面的内容。
- 需考虑项目规则：不得在代码中硬编码数据库连接信息，日志相关配置应支持通过 `.env` 或配置文件覆盖。
- 规约需与 `scripts/` 下的启停脚本、`docs/` 下的部署与结构文档保持可衔接，并在规约中明确需同步更新的文档位置。
