# UT 门禁记录查询 API（GET 列表）实现规约

本文档为 **`GET /api/v1/ut-gate-runs`** 的**实现级**规约，供后端与「UT门禁历史」前端联调对照。上位需求见 **`spec/15_ut_gate_jenkins_report_spec.md`**（§6.2、§8）；表结构与字段含义见 **§5** 及 **`database/V1.1.2__create_ut_gate_run.sql`**；单条记录 JSON 形状与 **`spec/16_ut_gate_report_post_api_spec.md` §6** 的 **`UtGateRunItem`** 对齐。

**本文档范围**：**分页列表** `GET /api/v1/ut-gate-runs`。**不包含** `GET /api/v1/ut-gate-runs/stats`（见 **§11**）；**不包含** Jenkins `POST`（见 **`spec/16_ut_gate_report_post_api_spec.md`**）。

---

## 1. 接口概要

| 项目 | 规约 |
|------|------|
| 方法 / 路径 | **`GET /api/v1/ut-gate-runs`** |
| FastAPI `tags` | **`["UT门禁上报"]`**（与 POST 同路由模块时可复用，或 **`["UT门禁历史"]`**，实现时二选一保持 OpenAPI 分组清晰） |
| 鉴权 | 见 **§3** |
| 响应包装 | **`PageResponse[UtGateRunItem]`**（与 `backend/schemas/common.py` 一致：`items`, `total`, `page`, `page_size`） |

---

## 2. 关联与约束

- **分层**：`Schema`（`UtGateRunQuery` 等）→ `Service`（`select` + 动态 `where` + 分页 + count）→ `API`（`Depends(get_db)`、`response_model=PageResponse[UtGateRunItem]`）。
- **Python**：类型标注使用 `Optional[X]`（Python 3.8）；**禁止** `X | None`。
- **查询策略**：**默认禁止 JOIN**（项目规则）；本接口仅查 **`ut_gate_run`** 单表。
- **日志**：列表接口**不在每条查询后打 INFO**（见项目日志规范）；**可**在参数明显非法时 **WARNING**；未预期异常 **ERROR** + `logger.exception()`。
- **ORM → Schema**：`UtGateRunItem.model_validate(row)`，`model_config = {"from_attributes": True}`。

---

## 3. 认证与权限

### 3.1 与集成 Token、浏览器的关系

- **`UT_GATE_INTEGRATION_TOKEN` / `Authorization: Bearer`**：用于 **Jenkins → `POST /api/v1/ut-gate-runs`**（见 **`spec/16`**）。**浏览器不得持有该 Token。**
- **本 `GET` 接口**：使用现有用户登录态 **`Depends(get_current_user)`**（JWT），与 **`/api/v1/history`** 等列表接口一致；由后端直接读库，**不要求**再用集成 Token「代调」第二跳。

### 3.2 「全员可见」（已确认）

- 凡 **已登录** 用户（`user` / `admin` 等现有角色）均可调用本接口；**不得**因非管理员返回 **403**（除非未登录 **401**）。
- 与主 spec §6.2、§9 一致：菜单与数据对登录用户开放，**不**做额外 RBAC 裁剪。

### 3.3 失败响应

| HTTP | 场景 |
|------|------|
| **401** | 未登录或 JWT 无效 |
| **422** | 查询参数校验失败（时间格式、互斥参数、非法 `sort_order` 等） |
| **500** | 数据库或其它未预期异常；`logger.exception()`，响应 **detail** 简短中文 |

---

## 4. 查询参数（Query）

继承 **`PageRequest`**：`page`（默认 `1`）、`page_size`（默认 `20`，**建议上限** `100`，与项目其它列表一致）。

| 参数名 | 必填 | 类型 | 说明 |
|--------|------|------|------|
| `start_time` | 否 | `string` | **闭区间左端**，作用于 **`reported_at`**（见 §4.1）。 |
| `end_time` | 否 | `string` | **闭区间右端**，作用于 **`reported_at`**。 |
| `is_intercepted` | 否 | `boolean` | 为 `true` / `false` 时仅返回对应行；**省略**则不过滤。 |
| `mr_url` | 否 | `string` | **精确匹配**：`TRIM(mr_url 参数)` 与列 **`mr_url`** 相等；**不**使用 `LIKE`。 |
| `mr_url_contains` | 否 | `string` | **子串匹配**：`mr_url IS NOT NULL AND mr_url LIKE '%…%'`；**转义**字面量 `%`、`_`、`!`（与 `history_service._like_substring` 语义一致，防通配符注入）。最大长度 **200**（与 History 子串参数一致）。 |
| `job_name_contains` | 否 | `string` | **`job_name`** 子串匹配，同上转义规则；最大长度 **200**。 |
| `sort_field` | 否 | `string` | 允许值：`reported_at`（默认）、`created_at`、`id`。其它值 → **422**。 |
| `sort_order` | 否 | `string` | `asc` / `desc`（大小写不敏感），默认 **`desc`**。其它值 → **422**。 |

### 4.1 时间参数语义（固化）

- 筛选列固定为 **`reported_at`**（门禁结束上报时间，与主 spec §5.2、§8.1 列表语义一致）。
- **`start_time` / `end_time`** 与主 spec §6.2 命名对齐；**语义**为本接口上的 **`reported_at` 范围**，**不是** Jenkins `JOB_NAME` 的 `start_time`。
- **格式**（二选一，实现须统一解析）：
  1. **ISO 8601** 日期时间字符串（推荐带时区；若无时区则按服务器本地或统一按 **UTC** 解析，**须在实现 PR 中写死一种**）；或  
  2. **`YYYY-MM-DD`**：视为该日 **00:00:00**～**23:59:59** 的本地日界（仅当 `start_time`、`end_time` **均为**日期格式时适用；与 ISO 混用规则在实现中 **422** 或按文档写死）。
- **闭区间**：`reported_at >= 解析(start_time)` 且 `reported_at <= 解析(end_time)`；若只传一端则只施加一端条件。
- **`start_time` 晚于 `end_time`** → **422**。

### 4.2 `mr_url` 与 `mr_url_contains` 互斥

- 若 **`mr_url` 与 `mr_url_contains` 同时非空**（去空白后）→ **422**，`detail` 说明二者互斥。
- 若均为空，则不对 `mr_url` 列加条件。

### 4.3 多条件组合

- 所有条件 **AND** 关系。

---

## 5. 排序与分页

- **默认排序**：`reported_at DESC`，`id DESC`（第二排序键保证稳定顺序，**建议**写入 Service）。
- **`sort_field` + `sort_order`** 覆盖第一排序键；**第二键**仍为 **`id DESC`**（推荐）。

### 5.1 计数

- `total` 使用 **`select(func.count()).select_from(与列表相同 where 条件的子查询/别名)`** 或与项目现有 `history_service` 等一致的 **count 语句**，**禁止**对大结果集仅 `LIMIT` 后数行当 `total`。

---

## 6. 响应体

- 顶层：`PageResponse[UtGateRunItem]`。
- **`UtGateRunItem`** 字段与 **`spec/16` §6**、表 **`ut_gate_run`** 一致；若 POST 已定义该 Schema，**GET 直接复用**，避免两套模型漂移。

### 6.1 日期时间序列化

- 与 **`spec/16` §6.2** 及项目现有列表 API 一致（推荐 **ISO 8601** 字符串）。

### 6.2 大整数 `id`

- JSON **number** 与 POST 一致；若前端需字符串化，在 **前端类型** 或 **二期** 扩展字段中处理，**本期**不强制改 Schema。

---

## 7. 索引与性能

- 已有索引：`idx_created_at`、`idx_mr_url_created`、`idx_is_intercepted_created`、`idx_job_build`（见 `V1.1.2` DDL）。
- **`reported_at` 范围 + `ORDER BY reported_at`**：若线上执行计划不佳，**二期**可加 **`idx_reported_at`**（须新迁移，**禁止** ALTER 保护表；仅允许**新增**迁移加索引）。

---

## 8. 路由与模块组织

- 与 **`POST /api/v1/ut-gate-runs`** 同属 **`backend/api/v1/ut_gate_run.py`**（推荐），或拆文件但 **同一 `prefix="/ut-gate-runs"`** 的 `APIRouter`。
- 在 **`backend/api/router.py`** 已 `include_router` 的前提下，仅新增 **`GET`** 处理函数即可。

---

## 9. OpenAPI

- 为各 Query 参数补充 **description**（中文）：尤其说明 **`start_time`/`end_time` 绑定 `reported_at`**，避免与 History 的「批次 start_time」混淆。

---

## 10. 错误与校验小结

| 场景 | HTTP |
|------|--------|
| 未登录 | **401** |
| 互斥参数、`sort_field`/`sort_order` 非法、时间解析失败、start>end | **422** |
| 数据库异常 | **500** |

---

## 11. `GET /api/v1/ut-gate-runs/stats`（非本期必做）

主 spec §6.2 已列出 **stats** 接口（按日/周聚合 `is_intercepted`、可选 `job_name`）。**主 spec §8.2** 明确 **本期前端不做图表**。

| 项 | 规约 |
|----|------|
| **本期实现** | **可不实现** stats；若实现，**不得**被「UT门禁历史」列表页 **v1** 强依赖。 |
| **鉴权** | 与列表 **GET** 相同：**`get_current_user`**。 |
| **二期** | 与 ECharts 或看板汇总一并对接时再固化请求/响应字段表。 |

若本期跳过 stats，**OpenAPI** 可不登记该路径，直至二期 spec 更新。

---

## 12. 实现检查清单

- [x] `UtGateRunQuery`（或等价）继承 `PageRequest`，含 §4 字段与校验器  
- [x] `list_ut_gate_runs(db, query) -> Tuple[List[UtGateRun], int]`（与项目 Service 签名风格一致）  
- [x] `GET` 路由：`Depends(get_current_user)`、`response_model=PageResponse[UtGateRunItem]`  
- [x] `mr_url_contains` / `job_name_contains` 与 History 一致的 **LIKE 转义**  
- [x] 单测：Schema（互斥、时间、排序）、OpenAPI 含 `GET`（DB 联测可后续补）  

---

## 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-05-07 | 初稿：`GET` 列表、鉴权、筛选、排序、分页、`stats` 非必做说明 |
| v1.1 | 2026-05-07 | 后端已按 §12 实现列表接口；§12 勾选同步 |
