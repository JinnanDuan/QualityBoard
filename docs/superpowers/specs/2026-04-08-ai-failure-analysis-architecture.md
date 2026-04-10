# AI 辅助失败原因分析 — 架构设计

- **文档类型**：架构设计（Architecture Spec）
- **关联文档**：同目录下的 `2026-04-08-ai-failure-analysis-tech-selection.md`（技术选型）
- **状态**：Draft（待评审）
- **作者**：AI 助手 × djn
- **日期**：2026-04-08

---

## 0. 文档目的与适用范围

本文档定义一个**新增的独立服务**——`ai-failure-analyzer`（下文简称 **AIFA**），以及它与既有 `dt-report` 系统之间的集成方式。目标是在不改动 `dt_infra` 数据库结构、不污染 `dt-report` 既有业务代码的前提下，为失败用例提供**AI 辅助的根因分析能力**。

本文档**只描述架构**（组件边界、数据流、契约、状态机、错误策略、部署形态、安全与观测）。所有涉及"选哪个库、哪个模型、哪个协议"的决策放在技术选型文档。

---

## 1. 背景与定位

### 1.1 业务背景
- `dt-report` 现有**"一键分析"**（`spec/11_one_click_batch_analyze_spec.md`）是**纯规则**能力：把整批失败用例批量打标为 bug 并写入责任人，**不做任何智能判断**。
- 团队的失败归因仍然高度依赖人工翻日志、看截图、查近期提交，这是"半天内处理完所有失败"目标的最大瓶颈。
- 需要一种能"读懂"日志/截图/代码历史并给出**初步归因结论**的能力。

### 1.2 功能定位
AIFA 是 **drill-down 级别** 的能力：
- **作用单位 = 单条失败用例**（不是整批）
- **作用页面 = 详细执行历史页的 Drawer**（与现有"失败归因"Tab 并列）
- **作用角色 = 所有登录用户**（与现有 Drawer 权限一致）
- **产出 = 结构化的初步归因报告**（verdict / evidence / suspect patches / next steps）
- **落地方式 = 仅在前端侧边展示，零数据库写入**

### 1.3 与既有"一键分析"的关系
| 维度 | 既有一键分析 | AIFA |
|---|---|---|
| 粒度 | 整批 | 单条 |
| 智能程度 | 0（纯规则） | LLM + 多数据源 |
| 写库 | 写 `pfr` + `ph.analyzed` | **零写库** |
| 部署 | dt-report 内嵌 | **独立服务** |
| 目标 | 快速打标、让数据流转起来 | 辅助归因、缩短人工调查时间 |

两者**互补、不替代**。一键分析解决"怎么让整批失败进入流转"，AIFA 解决"某一条失败到底是为什么"。

---

## 2. 核心设计原则

本架构的所有取舍都围绕以下原则展开，遇到冲突时优先级由上至下：

1. **与 dt_infra 数据库零耦合** —— AIFA 不连 MySQL，不知道表结构。
2. **与 dt-report 代码零耦合** —— 调用通过 HTTP + 独立契约；dt-report 侧只增加两个薄文件。
3. **降级优先于失败** —— 任何单一数据源故障返回 `partial` 报告，绝不整单崩。
4. **生产级但足够简单** —— 一个 Agent、五个 Skill、五个 Tool、一个内存 Session Store；避免过度工程。
5. **Token 成本硬约束** —— 结构化摘要在 Skill 之间流转，原始数据不透传到最终合成。
6. **未来可替换** —— LLM 厂商、代码仓库实现、Session 后端、Mongo schema 都走抽象或配置，切换不改代码。

---

## 3. 系统边界与部署拓扑

### 3.1 端到端数据流

```
┌──────────────────────── 浏览器（dt-report 前端）───────────────────────┐
│  HistoryPage → 某条失败用例 → Drawer → 「AI 归因」Tab → 点击 / 展开    │
└──────┬──────────────────────────────────────────────▲──────────────────┘
       │ ① POST /api/v1/ai/analyze                    │ ⑥ SSE 渲染
       ▼                                              │
┌──────────────── dt-report backend（现有） ─────────────────────┐
│  api/v1/ai_proxy.py  (新增薄代理，JWT + 限流 + 审计)            │
│      │                                                          │
│      │ ② 读 pipeline_history & 近 N 次历史执行                  │
│      ▼                                                          │
│  services/ai_context_builder.py  (新增，纯 dt_infra 读)         │
└──────┬──────────────────────────────────────────────────────────┘
       │ ③ POST http://ai-failure-analyzer:8080/v1/analyze (SSE)
       ▼
┌──────────────── ai-failure-analyzer（新独立服务）───────────────┐
│  FastAPI app                                                    │
│  ├── api/v1/analyze.py           入口 + SSE                     │
│  ├── agent/orchestrator.py       单 Agent 三阶段主循环          │
│  ├── agent/skills/*.py           五个 skill 模块                │
│  ├── agent/prompts/*.md          每个 skill 的 system prompt    │
│  ├── tools/*.py                  五个 tool                      │
│  ├── clients/                    mongo / http / codehub / llm   │
│  ├── sessions/                   内存 LRU Session Store         │
│  └── core/                       config / logging               │
│                                                                 │
│  ④ 外部数据源访问：                                              │
│    ├─► HTML log   (httpx → log_url)                             │
│    ├─► MongoDB    (motor → 只读用户)                            │
│    ├─► 截图       (httpx → screenshot_url, base64)              │
│    ├─► CodeHub    (httpx → REST API + token)                    │
│    └─► LLM        (httpx/openai-sdk → OpenAI 兼容端点)          │
│                                                                 │
│  ⑤ 产出 AnalyzeReport（结构化 JSON）                             │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 进程与容器边界

| 维度 | dt-report | AIFA |
|---|---|---|
| Repo 位置 | 本仓库 | 本仓库新增 `ai-failure-analyzer/` 子目录（monorepo 独立目录，非 submodule） |
| Python 虚拟环境 | 现有 | **独立** `requirements.txt` |
| Dockerfile | 现有 | **独立** `ai-failure-analyzer/Dockerfile` |
| 监听端口 | 现有 | `AIFA_PORT`（默认 `8080`） |
| 环境变量前缀 | 现有 | **全部以 `AIFA_` 开头**，与 dt-report env 严格隔离 |
| 日志目录 | 现有 `logs/` | 独立 `logs/aifa/` 或容器内 `/var/log/aifa` |
| dt_infra 访问 | 读写（遵循现有红线） | **零访问**（不连 MySQL） |
| MongoDB 访问 | 无 | 只读账号 |
| CodeHub 访问 | 无 | Service token |
| LLM API 访问 | 无 | 独立 API key |
| 生命周期 | 独立升级/重启 | 独立升级/重启 |

**关键要点**：AIFA 与 dt-report 共享的只有一个 HTTP 契约（§4），其他一切解耦。

### 3.3 dt-report 侧新增的最小改动

**严禁改动任何现有 service**。只新增两个薄文件：

1. **`backend/api/v1/ai_proxy.py`** —— 单接口 `POST /api/v1/ai/analyze`
   - 复用 `get_current_user` 做 JWT 校验
   - 调用 `ai_context_builder.build_payload(history_id)` 构造 payload
   - `httpx.AsyncClient` 转发到 AIFA
   - 透明转发 AIFA 的 SSE 响应流
   - 写一条 `sys_audit_log`（顺便推动 audit 落地）
   - 请求体：`{ history_id: int, follow_up_message?: str, session_id?: str, mode: "initial"|"follow_up" }`

2. **`backend/services/ai_context_builder.py`** —— 构造 AIFA 的请求 payload
   - 按 `history_id` 读 `pipeline_history` 主记录
   - 复用 `history_service` 的 helper 查近 N 次相同 `(case_name, platform)` 的执行记录（默认 N=20）
   - 读 `module_repo_mapping`（配置文件，见 §4.3）得到 `repo_hint`
   - 组装为 AIFA 契约定义的 JSON
   - **纯数据读取**，不做任何 AI/Prompt 相关逻辑

### 3.4 前端改动范围

- **严禁继续膨胀 `HistoryPage.tsx`**（当前已约 2010 行）
- 新增独立组件目录 `frontend/src/pages/history/components/ai_analysis/`（见 §9.1）
- 新增 API service 层：`frontend/src/services/aiAnalysisService.ts`
- Drawer 内在现有"失败归因"Tab 旁新增"**AI 归因（beta）**"Tab
- 该 Tab **懒加载**：用户切换到此 Tab 时才 mount 组件、才发 HTTP 请求

---

## 4. API 契约（dt-report ↔ AIFA）

**接口**：`POST http://ai-failure-analyzer:8080/v1/analyze`
**内容类型**：`application/json`（请求）/ `text/event-stream`（响应，SSE）
**认证**：Header `Authorization: Bearer <AIFA_INTERNAL_TOKEN>`（内部 service token，非 JWT）

### 4.1 Request Body

```json
{
  "session_id": "uuid-generated-by-frontend",
  "mode": "initial",
  "follow_up_message": "仅 mode=follow_up 时存在",
  "case_context": {
    "history_id": 123456,
    "case_name": "test_login_with_invalid_password",
    "platform": "Android",
    "main_module": "auth",
    "start_time": "202604071930",
    "case_result": "failed",
    "code_branch": "master",
    "log_url": "http://.../log/xxx.html",
    "screenshot_url": "http://.../shot/xxx.png",
    "pipeline_url": "http://jenkins/.../123",
    "reports_url": "http://.../report/xxx",
    "case_level": "P0"
  },
  "recent_executions": [
    { "start_time": "202604061930", "case_result": "passed", "code_branch": "master" },
    { "start_time": "202604051930", "case_result": "passed", "code_branch": "master" }
  ],
  "repo_hint": {
    "repo_url": "https://codehub.internal/group/project",
    "default_branch": "master",
    "path_hints": ["src/auth/", "tests/auth/"]
  }
}
```

- `recent_executions`：由 dt-report 按 `(case_name, platform)` 查近 N 条，AIFA 据此判断"首次失败 / 回归 / flaky"。
- `repo_hint`：**由 dt-report 侧维护**的 `main_module → 仓库` 映射（初期为 YAML 配置，后期可升级为字典表）。AIFA 不理解业务模块与仓库的对应关系。

### 4.2 SSE 响应事件

```
event: progress
data: {"stage": "plan", "message": "规划分析路径..."}

event: progress
data: {"stage": "log_analysis", "message": "正在分析日志..."}

event: progress
data: {"stage": "code_blame", "message": "正在检索近期提交..."}

event: report
data: { ...完整 report JSON... }
```

出错时：
```
event: error
data: {"error_code": "codehub_unauthorized", "message": "..."}
```

### 4.3 Response Schema（report 字段）

```json
{
  "session_id": "uuid",
  "status": "ok | partial | error",
  "report": {
    "verdict": "product_bug | env_issue | test_flaky | infra | unknown",
    "confidence": 0.0,
    "summary": "一句话结论",
    "evidence": [
      {
        "type": "log_excerpt | screenshot_observation | commit | history_pattern",
        "source": "mongo_log | html_log | screenshot | codehub | recent_executions",
        "snippet": "...",
        "reference": "具体指向（日志行号/commit sha/历史批次）"
      }
    ],
    "suspect_patches": [
      {
        "repo": "...",
        "sha": "...",
        "author": "...",
        "commit_time": "...",
        "touched_files": ["..."],
        "why_suspect": "AI 解释"
      }
    ],
    "suggested_next_steps": ["...", "..."],
    "data_gaps": ["Mongo 未检索到该批次日志", "..."]
  },
  "trace": {
    "skills_invoked": ["log_analysis", "code_blame", "synthesis"],
    "tool_calls": 7,
    "llm_input_tokens": 12034,
    "llm_output_tokens": 1820,
    "elapsed_ms": 18430
  }
}
```

### 4.4 契约版本化

- Schema 放在 `ai-failure-analyzer/api/v1/schemas/`
- 版本号体现在 URL 路径（`/v1/`）
- 未来升级契约走 `/v2/`，dt-report 侧 ai_proxy 可并存两版

---

## 5. Agent 状态机

单 Agent 三阶段主循环，每个阶段有严格出口条件：

```
┌──────────────────────────┐
│  incoming request        │
└──────────┬───────────────┘
           │
   ┌───────▼────────┐
   │   PLAN 阶段     │  LLM 只输出 JSON：要激活哪些 skill、顺序
   │  (1 LLM call)   │  温度=0，强制 JSON mode
   └───────┬────────┘
           │  skill_plan = ["history", "log", "screenshot", "code_blame"]
           ▼
┌────────────────────────┐
│    ACT 阶段             │  按 skill_plan 顺序逐个激活 skill
│  (每个 skill 1-N LLM)   │  每个 skill 内部可用其允许的 tool 集
└────────────┬───────────┘
             │  各 skill 产出结构化中间结果
             ▼
     ┌───────────────┐
     │ SYNTHESIZE    │  LLM 只做最终报告合成
     │ (1 LLM call)  │  输入 = 各 skill 的结构化摘要，不看 raw tool output
     └───────┬───────┘
             │
             ▼
     ┌───────────────┐
     │ 输出 Report   │
     └───────────────┘
```

**硬性约束**：
1. **Plan 是硬约束** —— 模型只能在预定义 skill 集合里选择，不能自创 skill。输出格式由 JSON mode 约束。
2. **Act 阶段 Skill 之间隔离** —— Skill A 的 tool 原始输出不进 Skill B 的上下文；Skill 间只传**结构化摘要**。这是 token 爆炸的主要防线。
3. **Synthesize 只看摘要** —— 不看原始日志文本、原始 diff、原始截图。最终合成 prompt 长度始终可控。
4. **追问（follow_up）** —— 跳过 Plan 和 Act，直接用 session 里存的中间结果 + 用户问题跑一次 Synthesize 变体。**不会触发新 tool 调用**，除非模型判定必须补查（此时重走 Plan，但限定在未用过的 skill）。

---

## 6. Skill × Tool 矩阵

### 6.1 Skill 清单（5 个）

| Skill | 目的 | 允许调用的 Tool | 产出结构化字段 |
|---|---|---|---|
| `history_skill` | 判断**偶发/回归/新失败**，看历史通过/失败模式 | _（无 tool，仅读 payload.recent_executions）_ | `pattern`（flaky/regression/new/persistent）、`last_pass_batch` |
| `log_analysis_skill` | 定位根因行、堆栈、异常关键字 | `fetch_log_html`, `query_mongo_logs` | `error_lines[]`, `stack_summary`, `keywords[]` |
| `screenshot_skill` | 识别截图中的 UI 状态（报错弹窗/空白页/toast 等） | `fetch_screenshot_b64` | `ui_state`, `visible_error_text`, `description` |
| `code_blame_skill` | 反推可能引入问题的 patch | `codehub_list_commits`, `codehub_get_commit_diff` | `suspect_patches[]`（sha/author/why_suspect） |
| `synthesis_skill` | 汇总成最终报告 | _（无 tool，输入各 skill 摘要）_ | 完整 `report` 对象 |

### 6.2 Tool 清单（5 个）

所有 Tool 都是 `async` Python 函数，通过 OpenAI function-calling 协议暴露给 LLM。

```python
# 1. HTML 日志抓取
async def fetch_log_html(log_url: str, max_chars: int = 20000) -> dict:
    """httpx GET → selectolax 提正文 → 去时间戳/ANSI → 截断"""
    # returns: {text, truncated, content_length}

# 2. MongoDB 结构化日志查询
async def query_mongo_logs(
    case_name: str, batch: str, platform: str,
    levels: list[str] = ["ERROR", "WARN"], limit: int = 200
) -> dict:
    """motor 只读查询，按 level 过滤，按 timestamp 倒序"""
    # returns: {records: [...], total}

# 3. 截图获取
async def fetch_screenshot_b64(
    screenshot_url: str, max_bytes: int = 2_000_000
) -> dict:
    """httpx GET → 校验 content-type/size → base64 编码"""
    # returns: {base64, mime, size_bytes, truncated}

# 4. CodeHub 提交列表
async def codehub_list_commits(
    repo_url: str, branch: str, since: str, until: str,
    path_filters: list[str] | None = None, limit: int = 30
) -> dict:
    """CodeHub REST API，时间窗 + 路径过滤"""
    # returns: {commits: [{sha, author, time, message, files}]}

# 5. CodeHub 单 commit diff
async def codehub_get_commit_diff(
    repo_url: str, sha: str, max_lines: int = 500
) -> dict:
    """CodeHub REST API，diff 截断"""
    # returns: {diff, truncated, files_changed}
```

### 6.3 Tool 层硬性约束

1. **全部 async** —— 不允许同步阻塞调用
2. **全部有 timeout** —— 默认 10s，可通过配置调整
3. **全部有返回截断** —— `max_chars` / `max_bytes` / `max_lines` 等硬上限，防止大日志撑爆上下文
4. **全部结构化错误** —— 不 raise，返回 `{error: "...", detail: "..."}`，让 Agent 能 graceful 处理
5. **全部幂等** —— 同参数同会话内返回相同结果；加进程内 LRU 缓存
6. **全部打审计日志** —— INFO 级别，含 `request_id / session_id / skill / tool_name / elapsed_ms / input_size / output_size`

---

## 7. Session 管理

**用途**：支持同一次分析报告之上的**追问**交互。

**存储**：内存 LRU
- `max_sessions`：默认 200（env 可配）
- `ttl_seconds`：默认 1800（30 分钟）
- 淘汰策略：LRU

**Session 内容**：
```python
class SessionState:
    session_id: str
    case_context: CaseContext         # 初次请求传入
    recent_executions: list[...]       # 初次请求传入
    plan: list[str]                    # Plan 阶段决策
    skill_summaries: dict[str, dict]   # 各 skill 的结构化摘要（不含 raw tool output）
    final_report: ReportSchema         # 最终报告
    trace: TraceRecord                 # 元信息
    created_at: datetime
    last_accessed_at: datetime
```

**单实例限制**：不做跨进程 Session 共享；单副本部署。如果未来扩副本，把 `SessionStore` 抽象为 Protocol，实现替换为 Redis。

---

## 8. 外部数据源集成与降级

### 8.1 HTML 日志

| 维度 | 细节 |
|---|---|
| 客户端 | `httpx.AsyncClient`（共享连接池） |
| 解析 | `selectolax` 提 `<body>` 纯文本 |
| 超时 | connect 3s / read 10s |
| 并发 | 全局 semaphore ≤ 4 在途 |
| 后处理 | 去时间戳前缀、ANSI 色码；按行 split 保留末 N 行（默认 800） |
| 截断阈值 | `max_chars=20000` |

**降级**：
- 连不上 → skill 产出空 `error_lines=[]`，`data_gaps` 记"HTML 日志获取失败"
- 解析不出正文 → 返回原始文本末尾 2000 字符 + WARNING
- 超大 → 截断继续 + `data_gaps` 记

### 8.2 MongoDB 结构化日志

| 维度 | 细节 |
|---|---|
| 驱动 | `motor` |
| 连接 | 启动时建立单例 `AsyncIOMotorClient`，连接池 10 |
| 账号 | **只读用户**，env `AIFA_MONGO_URI` |
| 超时 | `serverSelectionTimeoutMS=3000`, `socketTimeoutMS=8000` |
| 查询 | 只用 `find`，不用 `aggregate`/`mapReduce` |
| 字段名 | **全部走 env 配置**，避免硬编码（AIFA 不控制 Mongo schema） |

所需 env：
```
AIFA_MONGO_URI
AIFA_MONGO_DB
AIFA_MONGO_LOG_COLLECTION
AIFA_MONGO_FIELD_CASE_NAME
AIFA_MONGO_FIELD_BATCH
AIFA_MONGO_FIELD_PLATFORM
AIFA_MONGO_FIELD_LEVEL
AIFA_MONGO_FIELD_TIMESTAMP
```

**降级**：
- Mongo 连不上 → skill 跳过 Mongo 分支，仅用 HTML，`data_gaps` 记
- Mongo 查空 → 不是错误，正常返回
- Mongo 超时 → 降级到 HTML + WARNING

### 8.3 截图

| 维度 | 细节 |
|---|---|
| 客户端 | 共用 `httpx.AsyncClient` |
| 超时 | connect 3s / read 8s |
| 大小硬上限 | **2MB**（超过直接 error） |
| content-type 校验 | 必须以 `image/` 开头 |
| 编码 | base64（data URL）送给视觉模型 |

**视觉模型调用**（由 `screenshot_skill` 发起）：
```python
messages = [
  {"role": "system", "content": prompt},
  {"role": "user", "content": [
    {"type": "text", "text": "这是该用例失败时的截图..."},
    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
  ]}
]
```

**降级**：
- 图片拉取失败 → skill 产出 `{ui_state: "unknown"}`
- 图片过大 → error + `data_gaps` 记
- 视觉模型调用失败（配额/网络）→ 整个 skill 降级返回空 + WARNING

### 8.4 CodeHub

| 维度 | 细节 |
|---|---|
| 客户端 | 共用 `httpx.AsyncClient` |
| 认证 | `AIFA_CODEHUB_TOKEN`，header 形式（具体 header 名接入时确认） |
| base URL | `AIFA_CODEHUB_BASE_URL`（可配置） |
| 超时 | connect 3s / read 15s |

**操作**：
- `list_commits(repo, branch, since, until, path_filters, limit=30)`
  - 默认时间窗：`until = case.start_time`, `since = until - 7d`
  - path_filters 来自 `repo_hint.path_hints`
- `get_commit_diff(repo, sha, max_lines=500)`
  - Agent 只对 Top 3-5 commit 取 diff

**仓库抽象层**：
```python
# clients/code_repo/__init__.py
class CodeRepoClient(Protocol):
    async def list_commits(...): ...
    async def get_commit_diff(...): ...

# clients/code_repo/codehub.py
class CodeHubClient: ...       # 初期唯一实现

# 未来:
# clients/code_repo/gitlab.py
# clients/code_repo/gitea.py
```

通过 env `AIFA_CODE_REPO_PROVIDER=codehub` 决定注入哪个实现。

**降级**：
- CodeHub 连不上 → skill 跳过，报告无 `suspect_patches`，`data_gaps` 记
- 时间窗无 commit → 正常，给出"该时间窗无新增提交"
- **401（token 无效）→ fail-loud**：整个分析返回 500，提示联系管理员（这是配置错误不是暂时故障）

---

## 9. 前端集成

### 9.1 组件拆分

严禁在 `HistoryPage.tsx` 中直接写 AI 逻辑。新建独立目录：

```
frontend/src/pages/history/components/ai_analysis/
  ├── AIFailureAnalysisTab.tsx      Drawer 内 Tab 入口（轻，仅状态协调）
  ├── AnalysisTrigger.tsx           首次点击「开始分析」按钮
  ├── ProgressStream.tsx            SSE 进度展示
  ├── ReportView.tsx                结构化报告渲染
  ├── FollowUpInput.tsx             追问输入框
  ├── FollowUpHistory.tsx           追问历史列表
  └── useAIAnalysis.ts              hook：封装 SSE + session 管理 + 错误处理

frontend/src/services/aiAnalysisService.ts   API 封装
```

### 9.2 状态机

```
idle
  └── [点击开始分析] → loading
         ├── [SSE: progress]     → loading（更新进度文案）
         ├── [SSE: report]       → ready
         └── [SSE: error]        → error

ready
  ├── [输入追问 + 发送]           → follow_up_loading
  │     ├── [SSE: report]        → ready（追加新回答）
  │     └── [SSE: error]         → error（保留原报告）

error
  └── [点击重试]                  → loading（生成新 session_id）
```

### 9.3 session_id 约定

- Tab 首次 mount 时前端生成 `crypto.randomUUID()`
- 初次分析：`mode=initial, session_id`
- 追问：`mode=follow_up, session_id, follow_up_message`
- Drawer 关闭 → session_id 作废（前端 state 销毁）

### 9.4 报告渲染

`ReportView.tsx` 按结构化 schema 渲染（非裸 markdown）：
- **顶部大卡片**：`verdict` + `confidence` + `summary`
- **中部三列/折叠区**：`evidence`（按 source 分组）、`suspect_patches`（表格）、`suggested_next_steps`（列表）
- **底部警示条**：`data_gaps`（灰色提示）
- **角标**：`trace.tool_calls / elapsed_ms`（方便解释成本和调试）
- **原始 evidence snippet 允许展开**，默认折叠

### 9.5 Tab 懒加载

- 组件只在用户切到 "AI 归因" Tab 时 mount
- 首次 mount 不自动发请求；必须用户点"开始分析"按钮才发
- 这让"好奇点开 Drawer 但不想分析"的用户不产生任何 LLM 成本

---

## 10. 错误分级与响应

| 等级 | 场景 | 行为 |
|---|---|---|
| **Fatal** | LLM API key 无效、CodeHub token 无效、Agent 内部断言失败 | HTTP 500，前端展示"AI 服务异常" |
| **Partial** | 某个 skill 的数据源挂了，其他 skill 成功 | HTTP 200 + `status: "partial"` + `data_gaps` 列出缺失 |
| **Soft** | 单个 tool 调用超时、单条日志截断 | 内部 WARNING，skill 继续 |
| **User** | payload 字段缺失、session_id 不存在 | HTTP 400，明确中文 detail |

**核心原则**：**只要还有任何一个 skill 能跑，就返回 partial 而不是整单失败。**

---

## 11. 健康检查与观测

### 11.1 健康检查

`GET /healthz`：
```json
{
  "status": "ok",
  "checks": {
    "mongo": "ok",
    "codehub": "ok",
    "llm": "ok"
  }
}
```
- **Mongo**：`ismaster` ping
- **CodeHub**：轻量 API 调用（如获取 token info）
- **LLM**：**不在健康检查里调**（太贵），改为**启动时一次 warmup**

dt-report 侧可在管理员后台加一个状态卡片展示 AIFA 健康。

### 11.2 日志

- 双文件：`aifa_app.log` + `aifa_access.log`
- 沿用 dt-report 的 `dictConfig` 风格
- **Request ID**：复用 dt-report `X-Request-ID` header；没有则自生成 UUID4
- 所有 tool/LLM 调用 INFO 日志：`request_id / session_id / skill / tool_name / elapsed_ms / input_size / output_size`

### 11.3 Trace 结构

每次 analyze 请求生成一条完整 trace，写入 `trace.log`（JSONL 格式，便于未来接 ELK / ClickHouse）：

```python
class TraceRecord:
    request_id: str
    session_id: str
    case_name: str
    mode: Literal["initial", "follow_up"]
    plan: list[str]                    # 选中的 skill
    skill_timings: dict[str, int]
    tool_calls: list[ToolCallRecord]
    llm_calls: list[LLMCallRecord]     # 每次 LLM 调用的 token/耗时/模型
    total_input_tokens: int
    total_output_tokens: int
    total_elapsed_ms: int
    status: Literal["ok", "partial", "error"]
    data_gaps: list[str]
```

### 11.4 成本追踪

- **按请求**：input/output tokens × `price_per_1k_input / price_per_1k_output`（env 配置）→ 写入 trace
- **单请求硬上限**：`AIFA_MAX_TOKENS_PER_REQUEST`（默认 80000），触顶直接熔断返回 partial
- **按天聚合**：AIFA 每天 0 点打印前一天 summary（总请求数、总成本、p95 延迟、各 skill 失败率）
- **告警钩子**：预留 `CostAlertSink` Protocol；未来想接 WeLink 告警时实现注入，不动主代码

### 11.5 指标端点

`GET /metrics` 返回 JSON（不引入 prometheus-client 依赖）：
```json
{
  "requests_total": 1234,
  "requests_ok": 1180,
  "requests_partial": 42,
  "requests_error": 12,
  "tokens_input_total": 5230000,
  "tokens_output_total": 820000,
  "p50_elapsed_ms": 15400,
  "p95_elapsed_ms": 28900,
  "uptime_seconds": 86400
}
```

未来接 Prometheus 时加 `/metrics/prom` adapter，不动主接口。

### 11.6 敏感信息脱敏

AIFA 日志**不记录**完整日志文本、完整 diff、完整截图 base64。只记录摘要与哈希：

```
log_text_hash=sha256:xxxxxxx len=12345
diff_hash=sha256:yyyyyyy lines=234
screenshot_hash=sha256:zzzzzzz bytes=102400
```

排障时可对比是否为同一份内容，又不把潜在敏感代码/数据落到日志。

---

## 12. 安全

### 12.1 秘钥管理

所有秘钥通过 env 注入，**零硬编码**。完整 env 清单：

| env | 用途 |
|---|---|
| `AIFA_LLM_API_KEY` | LLM 网关 API key |
| `AIFA_LLM_BASE_URL` | OpenAI 兼容端点 |
| `AIFA_LLM_TEXT_MODEL` | 文本推理模型名 |
| `AIFA_LLM_VISION_MODEL` | 视觉模型名 |
| `AIFA_MONGO_URI` | Mongo 只读连接串 |
| `AIFA_MONGO_DB` / `AIFA_MONGO_LOG_COLLECTION` | 库/集合 |
| `AIFA_MONGO_FIELD_*` | 字段映射（见 §8.2） |
| `AIFA_CODEHUB_BASE_URL` | CodeHub API 根 |
| `AIFA_CODEHUB_TOKEN` | CodeHub service token |
| `AIFA_CODE_REPO_PROVIDER` | 代码仓库实现（`codehub`） |
| `AIFA_INTERNAL_TOKEN` | dt-report ↔ AIFA 之间的内部 token |
| `AIFA_MAX_TOKENS_PER_REQUEST` | 单请求 token 硬上限（默认 80000） |
| `AIFA_MAX_CONCURRENT_ANALYSES` | 全局并发上限（默认 8） |
| `AIFA_MAX_SESSIONS` | 内存 session 上限（默认 200） |
| `AIFA_SESSION_TTL_SECONDS` | session TTL（默认 1800） |
| `AIFA_PORT` | 监听端口（默认 8080） |
| `AIFA_LOG_LEVEL` | 日志级别 |
| `AIFA_ENV` | `development` / `production` |

### 12.2 dt-report ↔ AIFA 认证

- **不转发 JWT** —— JWT 对 AIFA 没意义
- 使用独立 **内部 service token**：`AIFA_INTERNAL_TOKEN`
- dt-report 侧 `ai_proxy` 在转发请求时添加 `Authorization: Bearer <internal_token>`
- AIFA 侧中间件校验；匹配失败直接 401
- token 仅存在于 dt-report 和 AIFA 的 env 里，**不在前端、不在浏览器、不在 URL**
- 未来升级为 mTLS 或 HMAC 签名只需改一个中间件

### 12.3 网络边界

- AIFA `8080` **只绑内网**（防火墙/安全组限制）
- 浏览器**永远不直接访问 AIFA**，所有流量必须经 dt-report 的 `ai_proxy`
- 浏览器侧的 JWT 鉴权、用户审计、速率限制都继续由 dt-report 既有中间件处理

### 12.4 速率限制

- **dt-report 侧**（在 `ai_proxy` 加）：同一用户每分钟 ≤10 次、每小时 ≤50 次 → 触顶返回 429
- **AIFA 侧**：全局并发 semaphore，默认 `AIFA_MAX_CONCURRENT_ANALYSES=8`；超过直接返回 503（不排队，避免 SSE 超时体验变差）

### 12.5 审计

- dt-report 侧 `ai_proxy` 每次调用写一条 `sys_audit_log`（顺便推动 audit 落地）
  - 字段：`user_employee_id / history_id / session_id / mode / result_status`
  - **这是唯一对 dt_infra 的写入**，符合"AIFA 不碰 dt_infra"红线
- AIFA 侧只写自己的 `trace.log`，不碰 dt_infra

### 12.6 输入净化

- `follow_up_message`：最大 2000 字符
- Mongo 查询参数：显式 escape（尽管 motor 参数化已基本免疫）
- CodeHub URL：拼接前用白名单校验域名（必须匹配 `AIFA_CODEHUB_BASE_URL` 的域）

---

## 13. 部署

### 13.1 Docker

- **独立 Dockerfile**：`ai-failure-analyzer/Dockerfile`
- 基础镜像：`python:3.11-slim`
- 运行时依赖：`httpx`, `motor`, `openai`, `selectolax`, `fastapi`, `uvicorn`, `pydantic-settings`
- **不装 Playwright**（AIFA 根本不用）
- 暴露：`AIFA_PORT`
- 启动：`uvicorn ai_failure_analyzer.main:app --host 0.0.0.0 --port ${AIFA_PORT}`

### 13.2 docker-compose 片段示例

```yaml
services:
  dt-report:
    environment:
      - AI_ANALYZER_BASE_URL=http://ai-failure-analyzer:8080
      - AI_ANALYZER_INTERNAL_TOKEN=${AIFA_INTERNAL_TOKEN}
    depends_on:
      - ai-failure-analyzer

  ai-failure-analyzer:
    build: ./ai-failure-analyzer
    environment:
      - AIFA_PORT=8080
      - AIFA_LLM_API_KEY=${AIFA_LLM_API_KEY}
      - AIFA_LLM_BASE_URL=${AIFA_LLM_BASE_URL}
      - AIFA_MONGO_URI=${AIFA_MONGO_URI}
      - AIFA_CODEHUB_BASE_URL=${AIFA_CODEHUB_BASE_URL}
      - AIFA_CODEHUB_TOKEN=${AIFA_CODEHUB_TOKEN}
      - AIFA_INTERNAL_TOKEN=${AIFA_INTERNAL_TOKEN}
      - AIFA_ENV=production
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3
    expose:
      - "8080"
```

### 13.3 发布策略

- AIFA 与 dt-report **解耦发布**：独立升级、独立回滚
- dt-report 侧 `ai_proxy` 对 AIFA 故障 **graceful degrade**：Tab 展示"AI 服务维护中"，其他功能完全不受影响

---

## 14. 非功能性目标（SLO）

| 指标 | 目标 |
|---|---|
| 单次 initial analyze p50 延迟 | ≤ 20s |
| 单次 initial analyze p95 延迟 | ≤ 40s |
| 单次 follow_up 延迟 p50 | ≤ 6s |
| 单次分析平均成本 | ≤ 0.5 元（可配置） |
| Partial 率 | ≤ 10%（超过说明数据源不稳） |
| Error 率 | ≤ 1% |
| 可用性 | 99%（AIFA 宕机不影响 dt-report 其他功能） |

---

## 15. 关键决策记录（ADR）

| # | 决策 | 理由 |
|---|---|---|
| ADR-01 | 独立服务而非 dt-report 内嵌模块 | 用户明确要求"解耦到独立进程/容器"；秘钥/成本/发布彻底隔离 |
| ADR-02 | AIFA 零访问 dt_infra，由 dt-report 推送 payload | 与数据库红线一致；AIFA 不绑定 dt_infra schema |
| ADR-03 | 单 Agent + 5 Skill + 5 Tool | 多 Agent 是过度工程；单 Agent 三阶段状态机已足够 |
| ADR-04 | Agent 三阶段 Plan → Act → Synthesize，Skill 之间只传结构化摘要 | 防 token 爆炸；可预测可观测 |
| ADR-05 | 前端 SSE 流式而非轮询 | 用户体验更好，代码增量很小 |
| ADR-06 | 交互 = 一次性为主 + 轻量追问 | 用户明确选择；追问复用 session 摘要，不重跑 tool |
| ADR-07 | 结果零数据库写入，只在侧边 Drawer 展示 | 用户明确选择；避免与现有写入流程冲突 |
| ADR-08 | 仅 5 个 Tool，严格 async/timeout/截断/结构化错误/幂等/审计 | 生产级最小集合；足够支撑当前需求 |
| ADR-09 | LLM 走 OpenAI 兼容协议，初期 GLM | 切换厂商零代码改动；初期最小配置 |
| ADR-10 | Mongo 字段名全部走 env 配置 | AIFA 不控制 Mongo schema；换源只改 env |
| ADR-11 | CodeHub 初期唯一实现，同时保留 `CodeRepoClient` Protocol | 生产级与简单的平衡；抽象成本可忽略 |
| ADR-12 | Session 存内存 LRU；抽象为 Protocol 便于未来换 Redis | 初期单实例够用，无需 Redis 依赖 |
| ADR-13 | 内部 service token 而非转发 JWT | 避免跨系统 token 语义污染 |
| ADR-14 | AIFA 只绑内网，浏览器不直连 | 鉴权/限流/审计集中在 dt-report 一处 |
| ADR-15 | dt-report 侧唯一改动 = ai_proxy + ai_context_builder 两个文件 | 不污染现有 service，顺便推动 sys_audit_log 落地 |
| ADR-16 | 单请求 token 硬上限 + 按天成本聚合 | 防止单 bug 烧光一天配额 |
| ADR-17 | Partial 优先于整单失败 | 降级优于失败，提高整体可用性 |
| ADR-18 | Prompt 作为代码走 git，不做运行时热更新 | 便于 review 和回滚 |
| ADR-19 | 前端 AI 组件独立目录，不污染 HistoryPage.tsx | HistoryPage.tsx 已 2010 行，继续塞会拖慢编辑和渲染 |
| ADR-20 | Tab 懒加载，首次 mount 不自动发请求 | 避免好奇用户产生无意义 LLM 成本 |

---

## 16. 未来演进方向

列为未纳入当前版本范围的方向，供后续迭代参考：

1. **整批分析**：从单用例扩展到整批失败的聚类归因
2. **历史 AI 报告沉淀**：将高质量报告经人工确认后写入 `pipeline_failure_reason.reason`，形成闭环（需产品层面决策，会打破 ADR-07）
3. **多厂商灰度**：通过 A/B 路由在 GLM/Kimi/MiniMax 之间对比质量
4. **Redis session**：多副本部署时替换 `SessionStore` 实现
5. **Prometheus 指标**：接统一监控平台
6. **离线评估集**：收集人工标注的失败样本作为 AIFA 质量回归测试
7. **Fine-tune / RAG**：将项目特有的错误模式沉淀为知识库

---

## 17. 验收清单（供实现阶段 self-check）

- [ ] AIFA 进程完全独立，不 import 任何 `backend.*` 模块
- [ ] AIFA 所有 env 以 `AIFA_` 开头
- [ ] AIFA 不建立任何 MySQL 连接
- [ ] 所有 5 个 tool 都是 async，都有 timeout 和截断
- [ ] 所有 5 个 tool 返回结构化错误而非 raise
- [ ] Plan 阶段输出严格受 JSON schema 约束
- [ ] Skill 之间只传结构化摘要，不传原始 tool output
- [ ] Synthesize 阶段 prompt 输入长度有硬上限
- [ ] 单请求累计 tokens 超过 `AIFA_MAX_TOKENS_PER_REQUEST` 自动熔断为 partial
- [ ] 外部数据源故障返回 partial 而非 500
- [ ] CodeHub 401 是 fail-loud（返回 500）
- [ ] LLM API key 无效是 fail-loud
- [ ] dt-report 侧只新增 `ai_proxy.py` 和 `ai_context_builder.py` 两个文件，不改现有 service
- [ ] `HistoryPage.tsx` 零改动或仅改一行挂 Tab
- [ ] 所有 AI 前端组件在独立目录 `ai_analysis/`
- [ ] Tab 懒加载
- [ ] 前端 session_id 由浏览器生成，Drawer 关闭即作废
- [ ] 内部 service token 校验中间件存在且生效
- [ ] AIFA 只绑内网
- [ ] `sys_audit_log` 有写入点（在 ai_proxy 里）
- [ ] 日志脱敏：不落原始日志/diff/截图
- [ ] Trace 每次请求生成完整记录
- [ ] `/healthz` 和 `/metrics` 端点可用
- [ ] 独立 Dockerfile，不装 Playwright
- [ ] docker-compose 示例可直接拉起
