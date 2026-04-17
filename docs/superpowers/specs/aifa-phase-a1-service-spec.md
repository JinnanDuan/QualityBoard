# AIFA Phase A1 — 服务骨架阶段规格说明

- **文档类型**：阶段规格（Phase Spec，仅描述 **A1** 交付范围）
- **关联文档**（单一事实来源优先级）：
  1. `2026-04-08-ai-failure-analysis-architecture.md`（组件边界、**dt-report ↔ AIFA 契约**、错误策略；冲突时以架构为准）
  2. `2026-04-08-ai-failure-analysis-tech-selection.md`（Python 3.11、FastAPI、OpenAI SDK、日志等）
  3. `2026-04-14-ai-failure-analysis-implementation-plan.md`（分期 ID 与依赖关系）
- **对应分期**：实现计划 **A1** — 正式 **AIFA（`ai-failure-analyzer`）服务骨架**：FastAPI、`POST /v1/analyze`、内部 Service Token、`GET /healthz`；**单轮 LLM、无 Tool**。
- **状态**：Draft
- **日期**：2026-04-16

---

## 0. 文档目的

本文档回答：**A1 合并时必须具备哪些行为、接口、配置与验收标准**；不重复架构全文，只固化 **A1 范围内的「必须 / 可选 / 禁止」**。

**A1 不包含**：dt-report 侧 `ai_proxy` / `ai_context_builder`（**A2**）、SSE 进度事件的丰富度与 `report` 全字段契约的终态收紧（**A3**）、接受/拒绝写库（**A4**）、按 `history_id` 限流（**A5**）、Mongo / 外链拉取 / CodeHub 等 Tool（**Phase B**）。

---

## 1. 与架构、实现计划的对齐说明

| 主题 | 架构要求 | A1 落地方式 |
|------|----------|-------------|
| 服务形态 | 独立进程、仓库内 `ai-failure-analyzer/` 子目录 | 新增独立目录与独立依赖清单；**不与** `backend/` 混部署 |
| `POST /v1/analyze` | 请求 `application/json`；响应 **`text/event-stream`（SSE）** | A1 **必须**采用 SSE；允许 **最少条数** 的 `progress`（例如 1 条）再发 `report` |
| 认证 | `Authorization: Bearer <AIFA_INTERNAL_TOKEN>` | A1 **必须**实现；`/v1/*` 受保护，`/healthz` 豁免 |
| 契约字段 | §4.1 请求体、`report` §4.3 | A1：**请求体**按架构字段做 Pydantic 校验，**未传字段**可缺省/可空；**响应** `report` 提供 **最小可用子集**（见 §5.3），其余数组可为空 |
| 单轮无 Tool | 五 Skill / Tool 矩阵属后续 | A1 **禁止**实现 Mongo、httpx 拉截图/报告、CodeHub；仅基于 **请求 JSON 文本** 调单轮 LLM（或 Mock） |
| 健康检查 | §11.1 `GET /healthz` | A1：**进程可用** + 可选 `checks`；**不要求** Mongo / CodeHub / LLM 远程探测（可标 `skipped` / `not_configured`） |
| `spec_change` / `flaky` | §4.3 无对比证据不得强判 | A1：服务端在合成/后处理阶段 **无成功侧截图相关有效输入** 时，**不得**输出 `spec_change` / `flaky`，应降级为 **`unknown`** 并可在 `data_gaps` 中说明 |

实现计划将「**SSE 进度丰富度 + report 与 §4.3 完全对齐**」记在 **A3**：A1 完成后，A3 可在 **不改动传输层协议** 的前提下增补事件与字段校验；**A1 不得**采用「仅 `application/json` 整包返回、无 SSE」形态，以免与架构 §4 冲突。

---

## 2. 交付物清单（A1 DoD）

以下全部满足，视为 **A1 完成**：

1. **可启动服务**：本地或容器内可通过 Uvicorn 启动（启动命令与端口由实现文档或 README 说明；默认端口可与架构示例 **8080** 对齐）。
2. **`GET /healthz`**：返回 HTTP 200 与 JSON body，至少包含整体 `status`（如 `ok`）；依赖检查可为 **简化**（见 §6）。
3. **`POST /v1/analyze`**：
   - 校验 `Authorization: Bearer`；错误返回 **401**（与架构 §10 对 token 配置错误的 fail-loud 一致）。
   - 校验请求体 JSON（结构对齐架构 §4.1，字段允许大量可选）。
   - 响应为 **SSE**：至少包含 `event: progress`（可 1 条）与 `event: report`；异常路径 `event: error`（见 §5.2）。
4. **LLM 配置**：模型调用的 **Base URL（或等价）** 与 **API Key** **必须**从**环境变量**读取，禁止写入仓库；支持 **Mock 模式**（见 §7）以便 CI 无密钥运行。
5. **单轮分析**：无 Tool、无多阶段 Agent；可将 `case_context` / `recent_executions` 等 **安全截断** 后拼入 prompt。
6. **自动化测试**：至少覆盖「无 token / 错误 token → 401」「健康检查 200」「Mock LLM 下 analyze 返回合法 SSE 且最终 `report` 可解析」。

---

## 3. 代码与工程布局（规范性要求）

以下内容供实现时遵循（A1 合并时目录名可微调，但须保持 **版本在 URL、Schema 独立文件**）：

- 根目录：`ai-failure-analyzer/`（与架构 §3 一致）。
- **Python 3.8+**（实现与 `pyproject.toml` 一致；技术选型 §2.1 仍推荐 3.11，与「环境仅 3.8」可并存）；**FastAPI + Uvicorn + Pydantic v2**（技术选型 §2.2）。
- 建议结构：`main` 挂载路由；`api/v1/analyze.py`；`api/v1/schemas/`（请求/响应模型）；`core/config.py`（环境变量）；`core/security.py`（Bearer 校验）；`services/analyze_service.py`（单轮 LLM 编排）。
- **独立** `requirements.txt`（或 `pyproject.toml`），**不**合并进 `backend/requirements.txt`。
- **可选**：`Dockerfile`（与 dt-report 对齐：`ubuntu:20.04` + `docker/sources.list` + apt 安装 `python3`/`venv`（focal 为 3.8.x）；构建上下文为**仓库根目录**）、`.env.example`（仅键名与说明，无真实密钥）。

---

## 4. 端点规格

### 4.1 `GET /healthz`

- **鉴权**：无需 Bearer。
- **响应**：`application/json`。
- **A1 最小 body 示例**：

```json
{
  "status": "ok",
  "checks": {
    "process": "ok",
    "mongo": "skipped",
    "codehub": "skipped",
    "llm": "not_configured"
  }
}
```

- **`checks.llm` 语义建议**：
  - `not_configured`：未配置调用真实 LLM 所需变量且未开启 Mock；
  - `ok`：已配置为 Mock 或已配置密钥且（可选）启动阶段 warmup 成功；
  - 具体枚举实现阶段可细化，但须 **人类可读、稳定**。

A1 **不要求**对 Mongo、CodeHub、LLM 供应商做**周期性**远程健康探测；架构 §11.1 完整 checks 可在 **B 阶段** 或运维迭代中补齐。

### 4.2 `POST /v1/analyze`

- **路径**：`/v1/analyze`（版本前缀与架构 §4 一致）。
- **鉴权**：**必须**携带 `Authorization: Bearer <token>`；与 `AIFA_INTERNAL_TOKEN` 比对（建议使用 `secrets.compare_digest` 防计时侧信道）。
- **请求头**：接受 `Content-Type: application/json`；若转发链存在 `X-Request-ID`，**应记录**；若无则服务端生成 UUID4。
- **请求体**：结构对齐架构 **§4.1**（`session_id`、`mode`、`case_context`、`recent_executions`、`repo_hint` 等）；字段 **大部分可选**，**不得**要求 AIFA 访问 MySQL 补数据（架构 §4.1 末段）。
- **成功响应**：`Content-Type: text/event-stream`；`Cache-Control: no-cache`；`Connection` 等按 SSE 常规实践。
- **HTTP 状态码**：
  - 流式成功：**200**（即使业务 `report.status` 为 `partial` / `error`，仍由 SSE `report` 或 `error` 事件表达，与架构「partial 仍 200」方向一致；若 A1 简化为「LLM 失败则发 `event: error` 后结束」，须在实现中固定并写入测试）。
  - 未授权：**401**。
  - 请求体非法：**400**（可选用 FastAPI 校验错误体；是否通过 SSE 返回由实现二选一，但须在 README 说明；**推荐** JSON 400 以便客户端区分「协议错误」与「分析失败」）。

---

## 5. SSE 与 `report` 最小契约（A1）

### 5.1 事件类型（A1 最小集）

与架构 **§4.2** 对齐，A1 **至少**支持：

| `event` | 说明 |
|---------|------|
| `progress` | `data` 为 JSON：`{"stage": string, "message": string}`；`stage` 可枚举简化，如 `llm_single` |
| `report` | `data` 为 **完整一层** JSON：含 `session_id`、`status`、`report`、`trace`（见 §5.3） |
| `error` | `data` 为 JSON：`{"error_code": string, "message": string}`（与架构 §4.2 形态一致） |

**不要求** A1 实现 `progress` 与真实 Plan/Act 阶段一一对应（属 **A3 / B2**）。

### 5.2 `event: error` 触发条件（A1 建议）

至少包含：**内部 token 校验失败**（此类也可在进流前直接 HTTP 401，不进入 SSE）、**请求体验证失败**、**LLM 调用不可恢复失败**（如 401/403、连接拒绝）。  
**不要求** A1 实现架构 §10 全部 Soft/Partial 分级；但 **禁止**在日志中打印 API Key 或完整 Bearer。

### 5.3 `event: report` 的 JSON 最小字段（A1）

顶层对象 **必须**包含（命名与架构 §4.3 **一致**，便于 A3 收紧）：

| 字段 | 类型 | A1 要求 |
|------|------|---------|
| `session_id` | string | 与请求一致或回显请求值 |
| `status` | `"ok" \| "partial" \| "error"` | 单轮成功且解析成功 → 通常 `ok`；解析降级 → `partial` 或 `error` 由实现定义并测准 |
| `report` | object | 见下表 |
| `trace` | object | 至少含 `llm_input_tokens`、`llm_output_tokens`、`elapsed_ms`（整数；未知可为 `0`）；`skills_invoked` 可为 `["llm_single"]` 等 |

**`report` 子对象（A1 最小）**：

| 字段 | A1 要求 |
|------|---------|
| `failure_category` | 必须有；取值 `bug \| spec_change \| flaky \| env \| unknown`；**无足够对比证据时禁止** `spec_change` / `flaky`（见 §1 表） |
| `summary` | 建议有（短句） |
| `detailed_reason` | 建议有（长文本占位亦可，但须为字符串） |
| `confidence` | 建议有（0～1 浮点） |
| `data_gaps` | 建议有（字符串数组，可为空） |
| `evidence` | 可有；允许空数组 `[]` |
| `stage_timeline` | 可有；允许单元素或空数组 |
| `verdict`、`rationale_summary`、`suspect_patches`、`suggested_next_steps` | **可选**；A1 可为空或省略 |

**LLM 输出解析策略（A1）**：推荐 **强制模型输出 JSON**（与 `report` 最小子集同构的片段），服务端校验 + 缺省填充；解析失败时 `status`/`report` 与 `event: error` 的组合方式由实现固定并测试覆盖。

---

## 6. 环境变量与配置（A1 必须）

以下变量名 **为建议命名**，实现阶段可统一前缀为 `AIFA_*`，但须在 **`.env.example` 与 README** 中列出全部键。

| 变量 | 必填 | 说明 |
|------|------|------|
| `AIFA_INTERNAL_TOKEN` | 生产必填 | dt-report（或脚本）调用 AIFA 时使用的 **内部 Service Token**；**禁止**出现在前端或仓库明文 |
| `AIFA_LLM_BASE_URL` | 调真实 LLM 时必填 | 兼容 OpenAI 兼容协议的 **API Base**；Mock 模式下可忽略 |
| `AIFA_LLM_API_KEY` | 调真实 LLM 时必填 | **禁止**日志明文打印；Mock 模式下可忽略 |
| `AIFA_LLM_MODEL` | 建议 | 模型名；缺省值由实现文档约定 |
| `AIFA_LLM_MOCK` | 可选 | 例如 `1` / `true` 时 **不发起外网调用**，返回固定或可配置 fixture，供 CI |
| `AIFA_PORT` | 可选 | 监听端口，默认建议 `8080` |

**可选后续变量**（可在 A1 README 预留说明，实现可延后）：`AIFA_MAX_TOKENS_PER_REQUEST`、温度、单请求超时等（架构 §11.4 / 技术选型）。

---

## 7. 安全与合规（A1）

- **密钥**：仅环境变量 / 容器注入；日志、trace、异常栈中 **脱敏**。
- **网络**：假定仅内网可达；**不在** A1 实现浏览器直连 CORS 生产配置（若本地调试需要 CORS，须默认关闭或限制 origin）。
- **请求体**：对嵌入请求的大段文本做 **长度上限**（具体字节数实现阶段定义），超限返回 **400** 或 `partial` + `data_gaps`（二选一并文档化）。

---

## 8. 日志（A1 最小）

与技术选型「标准库 logging + 不冗余」方向一致：

- 使用 `logging.getLogger(__name__)`。
- **INFO**：分析请求完成（含 `request_id`、`session_id`、`elapsed_ms`、token 统计摘要）；**不在**循环内逐条刷屏。
- **WARNING**：可恢复错误（如 LLM 超时重试策略若 A1 未做则可为单次失败）。
- **ERROR**：未预期异常使用 `logger.exception`。
- **禁止**：打印完整请求体中的敏感 URL 参数、Bearer、API Key。

---

## 9. 测试与验收

| 用例 | 期望 |
|------|------|
| 无 `Authorization` 调用 `/v1/analyze` | 401 |
| 错误 Bearer | 401 |
| `GET /healthz` | 200 + JSON |
| `AIFA_LLM_MOCK` 开启时 `POST /v1/analyze` | 200，SSE 可解析，最终 `report.failure_category` 合法且满足 §1 降级规则 |
| 请求体缺少 `session_id` 等必填项 | 400（若 A1 将 `session_id` 列为必填） |

**手动验收**：`curl`/`httpx` 示例命令写入 README；示例中使用占位 token。

---

## 10. 明确非目标（A1 禁止范围）

- 不实现 **dt-report** 任何路由、代理、写库。
- 不实现 **Mongo**、**httpx 拉取截图/报告**、**CodeHub**、多 Skill、Plan/Act/Synthesize、追问 session 持久化。
- 不实现 **`/metrics`**、完整 JSONL **trace 文件**、成本按天聚合（架构 §11.3–11.5；可列在后续阶段）。
- 不修改 **MySQL** 表结构或 `database/` 迁移（AIFA **零 MySQL**）。

---

## 11. 维护约定

- A1 实现合并后：在 `2026-04-14-ai-failure-analysis-implementation-plan.md` 的 A1 行更新状态（打勾或「已完成」）可选。
- 若本规格与架构正文冲突：**以架构为准**，并修订本文件 revision。

### 修订记录

| 日期 | 变更 |
|------|------|
| 2026-04-16 | 初稿：A1 范围、DoD、SSE 最小集、环境变量、健康检查、非目标 |
| 2026-04-16 | 文件名定为 `aifa-phase-a1-service-spec.md`（无日期前缀）；实现计划增加引用 |
| 2026-04-16 | 仓库根目录新增 `ai-failure-analyzer/` 实现 A1（与本文档 DoD 对齐） |
| 2026-04-17 | AIFA `Dockerfile` 改为与 dt-report 同基础镜像，镜像内 deadsnakes 安装 Python 3.11；构建自仓库根目录 |
| 2026-04-17 | 源码与依赖声明兼容 **Python 3.8+**（与 3.10+ 行为一致），便于与 dt-report 同版本 Python |
| 2026-04-17 | AIFA `Dockerfile` 与 dt-report 一致改为仅 **apt 安装 python3**（3.8），去掉 deadsnakes/PPA |
