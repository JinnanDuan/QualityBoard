# 日志使用指南

面向开发者与 AI 的日志配置、添加、查看说明。详细规约见 [spec/05_log_spec.md](../spec/05_log_spec.md)。

---

## 1. 日志架构

| 文件 | 内容 |
|------|------|
| **app.log** | 应用层日志：业务打点、异常堆栈、SQL（可选）、uvicorn 内部日志 |
| **access.log** | 访问日志：method、path、status_code、duration_ms、client_ip |

- 异常/错误统一写入 **app.log**
- 日志格式：`时间戳 [级别] [模块名] [req:request_id] 消息`
- 支持 RotatingFileHandler 轮转（app.log 10MB×5 份，access.log 10MB×3 份）

---

## 2. 配置

在 `.env` 中配置（参考 `.env.example`）：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| ENV | development / production | development |
| LOG_LEVEL | DEBUG / INFO / WARNING / ERROR | 随 ENV |
| LOG_DIR | 日志目录，空则项目根目录 | 空 |
| LOG_SQL | 为 true 时在 app.log 打印所有 SQL | false |

---

## 3. 添加日志

在业务代码中：

```python
import logging

logger = logging.getLogger(__name__)

logger.info("操作成功 key=%s", value)
logger.warning("可恢复异常: %s", reason)
logger.error("错误: %s", err)
logger.exception("未捕获异常")  # 自动附带完整 traceback
```

- 只要文件位于 `backend/` 目录下（如 `backend/services/xxx.py`），`__name__` 会自动是 `backend.*`，日志会写入 app.log
- 避免在日志中传入密码、Token 等敏感信息（SensitiveDataFilter 会脱敏，但不保证覆盖所有情况）

---

## 4. 查看日志

```bash
# 实时查看应用层日志
tail -f app.log

# 实时查看访问日志
tail -f access.log

# 按 request_id 串联一次请求的完整链路
grep "req:abc-123" app.log access.log

# 按级别过滤
grep "\[ERROR\]" app.log
```

---

## 5. SQL 日志

调试时在 `.env` 中设置 `LOG_SQL=true`，重启服务后所有 MySQL SQL 会写入 app.log。

生产环境建议关闭，避免日志膨胀和敏感信息泄露。

---

## 6. 其他说明

- **request_id**：每次 HTTP 请求自动生成 UUID，贯穿该请求的所有日志，响应头返回 `X-Request-ID`
- **敏感信息过滤**：Formatter 层对 password、token、Authorization 等做脱敏
- **启动方式**：`./scripts/start.sh` 调用 `python -m backend.run`，日志由 Python logging 写入，不生成 nohup.out
