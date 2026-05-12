# UT 门禁结果上报 API（POST）实现规约

本文档为 **`POST /api/v1/ut-gate-runs`** 的**实现级**规约，供后端开发、联调与 Jenkins 脚本对照。上位需求、业务语义、表结构字段含义见 **`spec/15_ut_gate_jenkins_report_spec.md`**；数据库 DDL 见 **`database/V1.1.2__create_ut_gate_run.sql`**。

**本文档范围**：仅 **写入（上报）** 接口；**不包含** `GET` 列表/统计、前端页面（**`GET` 见 `spec/17_ut_gate_runs_get_api_spec.md`**）。

---

## 1. 接口概要

| 项目 | 规约 |
|------|------|
| 方法 / 路径 | **`POST /api/v1/ut-gate-runs`** |
| Content-Type | **`application/json`**（UTF-8） |
| FastAPI `tags` | **`["UT门禁上报"]`**（或等价中文标签，与项目其它路由风格一致） |
| 鉴权 | 见 **§3** |

---

## 2. 关联与约束

- **分层**：`Schema`（请求/响应体校验）→ `Service`（幂等、INSERT）→ `API`（路由、依赖注入）。禁止在路由函数内手写 SQL 大块逻辑。
- **Python**：类型标注使用 `Optional[X]`（Python 3.8）；**禁止** `X | None`。
- **日志**：遵循 `docs/06_logging_guide.md`；**禁止**在日志中输出 Token 或 `Authorization` 头全文。
- **ORM**：写入目标表 **`ut_gate_run`**，模型 **`UtGateRun`**（`backend/models/ut_gate_run.py`），字段与 DDL **逐列一致**。

---

## 3. 认证与安全

### 3.1 方式（本期定稿）

- 请求头 **`Authorization: Bearer <token>`**。
- **`<token>`** 与服务器配置项一致；部署时由运维配置 **QualityBoard `.env`**，与 **Jenkins Credentials** 注入的变量**共用同一密钥值**（Jenkins 侧变量名可为 `QUALITYBOARD_UT_REPORT_TOKEN` 等，**不在本文档强制 Jenkins 变量名**，仅要求请求头格式正确）。

### 3.2 服务端配置项（建议）

| 环境变量 / Settings 字段 | 说明 |
|---------------------------|------|
| **`UT_GATE_INTEGRATION_TOKEN`**（建议命名；实现时写入 `backend/core/config.py`） | 非空字符串时启用校验：与 `Authorization` 中 Bearer 值**按常量时间比较**（或框架推荐方式），相等则通过。 |
| **未配置或为空** | **实现二选一须在 PR 描述中写明**：**(A)** 拒绝所有上报（`401`/`503` + 明确 `detail`）；**(B)** 仅开发环境放行（**禁止**生产默认可匿名写入）。**推荐 (A)**，避免误部署空 Token。 |

### 3.3 失败响应

| HTTP | 场景 |
|------|------|
| **401** | 缺失 `Authorization`、非 `Bearer`、Token 不匹配或配置未启用有效 Token。 |
| **403** | 本期可与 **401** 合并实现（统一 **401** 即可），**不**单独引入 RBAC。 |

---

## 4. 请求体（JSON）

### 4.1 字段总表

所有键名 **蛇形命名（snake_case）**，与表字段、前端后续对接一致。

| JSON 键 | 必填 | 类型 | 长度 / 范围 | 映射列 | 说明 |
|---------|------|------|---------------|--------|------|
| `idempotency_key` | **是** | `string` | `1～128` | `idempotency_key` | 同 §5.2 主 spec；**禁止**仅空白字符。 |
| `job_name` | **是** | `string` | `1～256` | `job_name` | Jenkins `JOB_NAME` 等，与主 spec 一致。 |
| `build_number` | **是** | `integer` | `≥ 0` 且与 DB **`INT UNSIGNED`** 一致 | `build_number` | 超出 unsigned 范围则 **422**。 |
| `is_intercepted` | **是** | `boolean` | — | `is_intercepted` | **`true`/`false`**；服务端落库为 `1`/`0`（tinyint）。 |
| `ut_exit_code` | 否 | `integer` 或省略 / `null` | 与 MySQL **`INT`** 一致 | `ut_exit_code` | 建议 Jenkins 始终上报；缺省则 **`NULL`**。 |
| `build_url` | 否 | `string` 或 `null` | `≤ 1024` | `build_url` | 通常 `BUILD_URL`。 |
| `jenkins_base_url` | 否 | `string` 或 `null` | `≤ 512` | `jenkins_base_url` | 由 `BUILD_URL` 解析；缺省 **`NULL`**。 |
| `mr_url` | 否 | `string` 或 `null` | `≤ 1024` | `mr_url` | **仅当** Jenkins **`codehubMergeRequestUrl`** 非空时等于该值；否则省略或 **`null`**。 |

**禁止**出现的键（本期）：`error_message`、`git_remote_url`、`git_commit_sha`、`mr_id`、`summary_line` 等未在 **`ut_gate_run`** 表定义的字段；若客户端传入，**建议**服务端 **忽略**（不报错）或 **422**——实现时选一种并在 OpenAPI 说明中写死；**推荐忽略未知键**（Pydantic 默认 `extra="ignore"`）。

### 4.2 服务端校验规则

1. **Content-Type** 非 JSON 或 body 非法 JSON → **400**（可由框架抛出，**detail** 中文简述即可）。
2. **必填缺失 / 类型错误 / 超长度** → **422**（Pydantic `RequestValidationError` 统一处理时，对外仍应为可读中文或结构化 `detail`，与项目现有全局异常处理一致）。
3. **`idempotency_key` / `job_name` 去首尾空白**后若为空 → **422**。
4. **`mr_url` / `build_url` / `jenkins_base_url`**：可选 **去首尾空白**；全空白视为 **`null`**。
5. **不在服务端重算 `is_intercepted`**：以请求体为准（与主 spec §6.3「以 Jenkins 脚本解析结果为准」一致）。

### 4.3 请求示例

```json
{
  "idempotency_key": "my-job-123",
  "job_name": "folder/my-job",
  "build_number": 123,
  "is_intercepted": false,
  "ut_exit_code": 101,
  "build_url": "https://jenkins.example.com/job/folder/job/my-job/123/",
  "jenkins_base_url": "https://jenkins.example.com",
  "mr_url": "https://codehub.example.com/group/project/-/merge_requests/4647"
}
```

---

## 5. 幂等语义（本期固化）

以 **`idempotency_key`** 对应 **`UNIQUE KEY uk_idempotency`**。

### 5.1 比较字段集（客户端可写、参与幂等比较）

以下字段若与库中已有行**全部相同**，视为**同一语义重复上报**：

`job_name`, `build_number`, `build_url`, `jenkins_base_url`, `mr_url`, `is_intercepted`, `ut_exit_code`

**不参与比较**：`id`, `created_at`, `updated_at`, `reported_at`（由库或服务端维护）。

### 5.2 行为

| 条件 | HTTP | 响应体 |
|------|------|--------|
| `idempotency_key` **不存在** | **201 Created** | 新建行，返回 **完整记录**（见 **§6**），含生成的 `id` 与时间字段。 |
| `idempotency_key` **已存在**，且 §5.1 字段与已存行 **逐项相等**（`NULL` 与缺失均与 **`NULL`** 等价） | **200 OK** | 返回 **当前库中该行完整记录**（**不**修改 `updated_at`/`reported_at` 亦可，**不**再 INSERT）。 |
| `idempotency_key` **已存在**，且 §5.1 中 **任一项不等** | **409 Conflict** | `detail` 中文说明「幂等键已存在且请求内容不一致」；**不**改库中已有行。 |

> 说明：主 spec §6.1 中「200 或 409 二选一」本期按上表 **同时采用**：重复且一致 → **200**；冲突 → **409**。

---

## 6. 成功响应体（201 / 200）

### 6.1 格式

- **与表字段一致**的 **JSON 对象**（蛇形命名），至少包含：

`id`, `created_at`, `updated_at`, `reported_at`, `jenkins_base_url`, `job_name`, `build_number`, `build_url`, `mr_url`, `idempotency_key`, `is_intercepted`, `ut_exit_code`

### 6.2 类型与序列化

| 字段 | JSON 类型 | 说明 |
|------|-------------|------|
| `id` | `number` | 大整数；前端若用 JS 需注意精度，本期列表可用字符串化策略 **留待 GET spec**。 |
| `is_intercepted` | `boolean` | 由 ORM `tinyint` 映射为 `true`/`false`。 |
| `ut_exit_code` | `number` 或 `null` | |
| `*_at` | `string`（ISO 8601） | 与时区策略一致：推荐 **UTC** 带 `Z` 或显式 offset，与项目其它 API 一致。 |
| 可空字符串列 | `string` 或 `null` | |

### 6.3 Pydantic 响应模型

- 须设置 **`model_config = {"from_attributes": True}`**（与项目 Schema 契约一致）。

---

## 7. 错误响应与 HTTP 表

| HTTP | 场景 |
|------|------|
| **400** | Body 非合法 JSON。 |
| **401** | 鉴权失败（见 §3）。 |
| **409** | 幂等键冲突且载荷不一致（§5.2）。 |
| **422** | 参数校验失败（§4.2）。 |
| **500** | 未预期异常；**必须** `logger.exception()`，**detail** 对用户简短中文，**不**返回栈信息。 |

**Jenkins 侧**：主 spec 约定 4xx/5xx **不改变**门禁退出码；与本文档无关但联调时需知晓。

---

## 8. 服务端写库规则

| 列 | 规则 |
|----|------|
| `id` | 自增，插入后返回。 |
| `created_at` / `updated_at` | 以 **数据库默认值 / ON UPDATE** 为准；**不在应用层覆盖**（除非项目统一用 `server_default` 已对齐）。 |
| `reported_at` | **插入时**写 **`NOW()`**（或服务端等价 UTC）；**幂等 200** 时**不更新**该列。 |

**事务**：单条 INSERT 或「SELECT by key + 比较 + INSERT/返回」须在**同一事务**内完成，避免并发双插；并发下第二条应命中唯一键异常后转为「读已有行 + 比较」分支（实现细节由 Service 层处理）。

---

## 9. 日志

| 级别 | 时机 | 内容 |
|------|------|------|
| **INFO** | **201** 或 **200**（幂等命中）成功落库/返回 | **`idempotency_key`、`job_name`、`build_number`**；可含 **`id`**；**不含** Token。 |
| **WARNING** | **401**、**422**、**409** | 原因简述（**不**打完整 body）。 |
| **ERROR** | **500** | `logger.exception()`，**不**记录敏感信息。 |

---

## 10. 路由注册与 OpenAPI

- 在 `backend/api/v1/` 新增模块（如 **`ut_gate_run.py`**），`router = APIRouter(prefix="/ut-gate-runs", tags=["UT门禁上报"])`。
- 在 `backend/main.py`（或统一 `api/v1/__init__.py`）**include_router**，前缀与现有 **`/api/v1`** 拼接后为 **`/api/v1/ut-gate-runs`**。
- OpenAPI 中本接口 **description** 可简短引用本文档路径。

---

## 11. 非目标（本期）

- **GET** / 分页 / 筛选：见后续专项或主 spec §6.2。
- **限流**：主 spec §9 建议按 IP/Token QPS；可在首版 **TODO** 或二期实现；**不阻塞** POST 首版合入。
- **双 Token 过渡期**：主 spec 为可选；首版单 Token 即可。

---

## 12. 实现检查清单

- [x] `Settings` 增加 **`UT_GATE_INTEGRATION_TOKEN`**（或最终命名）及 `.env.example` 说明  
- [x] 依赖：`verify_ut_gate_integration_token`（或等价）仅作用于本路由  
- [x] `UtGateRunCreate` / `UtGateRunItem` Schema（命名以代码为准，字段与 §4、§6 一致）  
- [x] `create_ut_gate_run`（或等价）`async` Service：`INSERT` / 幂等分支 / 事务与唯一键冲突处理  
- [x] 路由：`POST`、`response_model`、**201** 与 **200** 用 `JSONResponse`/`Response` 区分状态码（FastAPI 默认单 `response_model` 时需显式处理多状态码）  
- [x] 单元测试：幂等比较逻辑、OpenAPI 路径登记（**鉴权 / 422 / 201 / 200 / 409** 的 HTTP 联测可在有 MySQL 的 CI 或本地库上补全）  

---

## 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-05-07 | 初稿：`POST /api/v1/ut-gate-runs`、鉴权、请求/响应、幂等 200/409、日志与检查清单 |
| v1.1 | 2026-05-07 | 后端已按 §12 落地；§12 勾选同步；补充联测说明 |
| v1.2 | 2026-05-07 | 文首范围补充 **`GET` 见 `spec/17_ut_gate_runs_get_api_spec.md`** |
