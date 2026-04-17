# AI 辅助失败原因分析 — 架构设计

- **文档类型**：架构设计（Architecture Spec）
- **关联文档**：
  - `2026-04-08-ai-failure-analysis-tech-selection.md`（技术选型）
  - `2026-04-14-ai-failure-analysis-implementation-plan.md`（**实现计划与分期、穿刺范围**）
- **状态**：Draft（待评审，2026-04-14 已按产品讨论修订）
- **作者**：AI 助手 × djn
- **日期**：2026-04-08（初稿）；**修订**：2026-04-14（与测试/开发讨论结论收口）

### 修订记录（2026-04-14）

- **输出与落库**：明确「分析过程 + 完整结论」默认**不落业务库**；用户**一键确认**后，仅将 **失败归类** + **详细失败原因（结论）** 写入 `pipeline_failure_reason`（与「分析处理」「一键分析」对齐，见 §1.4、§9.4、§12.5）。
- **失败归类**：`bug` / `spec_change` / `flaky` / `env`；其中 **规格变更**、**用例不稳定** 依赖与**最近一次成功批次**截图的对比；对比策略与降级见 §1.4、§8.3。
- **历史成功数据**：由 **dt-report** 查得「最近一次成功批次」，在约定 URL 形态下**仅替换 batch** 生成成功侧 **截图 / 测试报告 HTML** 等资源入口（**不含日志 URL**）；**AIFA 不连 MySQL**。
- **截图与测试报告**：`screenshot_index_url`、`reports_url` 及成功侧对应 URL **通过契约传给 AIFA**，由 **AIFA 使用 httpx 直接拉取**（目录/索引页为 HTML 时可在 **AIFA 内**用 `selectolax` 等解析出子链后再拉图片，见 §8.3）；**不由 dt-report 强制展开**为直链（若 dt-report 预展开为 `*_urls[]` 可作为可选优化，非必选）。
- **限流**：**同一 `history_id` 在 1 分钟内最多触发 10 次**分析请求（§12.4）；与模型能力无强绑定，主要为成本与防滥用。
- **详细分析过程**：以 **结构化 evidence + 阶段时间线** 为主，**短论证摘要**为辅且限长；不默认暴露完整 CoT（§4.3、§9.4）。
- **异步任务（二期）**：支持批量勾选、后台排队、进度、重试、取消；**单次 dt-report → AIFA 的 HTTP/SSE 调用超时 3 分钟**；每条任务独立结果入口（§9.6）。
- **附加文件上传**：列为**二期 / 优化项**，当前版本不做（§16）。
- **日志 vs 其它 URL**：契约 **不传 `log_url`**，文本日志仅 **Mongo**（`query_mongo_logs`，§8.1）；**截图、测试报告 HTML** 的 URL **写入契约**，由 **AIFA httpx 拉取**（§8.3、§6.2）。

---

## 0. 文档目的与适用范围

本文档定义一个**新增的独立服务**——`ai-failure-analyzer`（下文简称 **AIFA**），以及它与既有 `dt-report` 系统之间的集成方式。目标是在**不改动既有表结构红线**（见项目数据库规范）、**不污染** `dt-report` 既有业务逻辑的前提下，为失败用例提供**AI 辅助的根因分析能力**；分析**草稿**与过程默认不落业务库，**经用户确认**后可写入既有 `pipeline_failure_reason` 字段。

本文档**只描述架构**（组件边界、数据流、契约、状态机、错误策略、部署形态、安全与观测）。所有涉及"选哪个库、哪个模型、哪个协议"的决策放在技术选型文档。

---

## 1. 背景与定位

### 1.1 业务背景
- `dt-report` 现有**"一键分析"**（`spec/11_one_click_batch_analyze_spec.md`）是**纯规则**能力：把整批失败用例批量打标为 bug 并写入责任人，**不做任何智能判断**。
- 团队的失败归因仍然高度依赖人工翻日志、看截图、查近期提交，这是"半天内处理完所有失败"目标的最大瓶颈。
- 需要一种能"读懂"日志/截图/代码历史并给出**初步归因结论**的能力。

### 1.2 功能定位
AIFA 是 **drill-down 级别** 的能力（**一期：单条**为主）：
- **作用单位 = 单条失败用例**（一期入口：详细执行历史 Drawer；二期见 §9.6 批量排队）
- **作用页面 = 详细执行历史页的 Drawer**（与现有「失败归因」Tab 并列）
- **作用角色 = 所有登录用户**（与现有 Drawer 权限一致）
- **产出**（见 §1.4）：① **详细分析过程**（可观测、有依据）；② **结论**（详细失败原因）；③ **失败归类**；④ 可选 **一键写入** `pipeline_failure_reason`（仅 **失败归类** + **详细原因** 两个业务字段，过程本身不入库）
- **落地方式**：分析**草稿**在前端展示；**默认不写** `pipeline_failure_reason`；用户点击「一键设置到失败原因」后由 dt-report 写入（规则见 §1.4）

### 1.3 与既有"一键分析"的关系
| 维度 | 既有一键分析 | AIFA |
|---|---|---|
| 粒度 | 整批 | 单条（一期）；批量排队（二期 §9.6） |
| 智能程度 | 0（纯规则） | LLM + 多数据源 |
| 写库 | 写 `pfr` + `ph.analyzed` | **分析过程与 AI 全文默认不入库**；用户确认后写 `pipeline_failure_reason`（`failed_type` + `reason` 等，§1.4） |
| 部署 | dt-report 内嵌 | **独立服务** |
| 目标 | 快速打标、让数据流转起来 | 辅助归因、缩短人工调查时间 |

两者**互补、不替代**。一键分析解决"怎么让整批失败进入流转"，AIFA 解决"某一条失败到底是为什么"。

### 1.4 输入、输出、失败归类与一键入库（产品口径）

#### 1.4.1 输入（由 dt-report 拼入 payload，AIFA 不查 MySQL）

前端发起分析时携带 **`history_id`**（及会话字段等）。**dt-report** 的 `ai_context_builder` 根据 `history_id` 读取 `pipeline_history` 等，至少拼出（字段名与表结构以实际实现为准，此处为业务语义）：

- **用例维度**：`batch`、`platform`、`module`（及业务需要的 `subtask` 等）、`case_name`、`code_branch`（供 Mongo 日志查询与业务展示；**不向 AIFA 传日志 HTML URL**）
- **资源入口（无日志 URL）**：`screenshot_index_url`（**截图目录/索引 URL**，见 §8.3）、`reports_url`（**测试报告 HTML 页面 URL**）等 —— **原样写入 payload**，由 **AIFA 经 httpx 拉取**；**日志内容**仅通过 AIFA 侧 **Mongo** 按 `case_name` + `batch` + `platform` 查询（§8.2），**dt-report 不传 `log_url`**
- **历史执行**：同 `(case_name, platform)` 近 N 次执行摘要（`recent_executions`）
- **最近一次成功批次**：由 dt-report 查询得到 `last_success_batch`；在团队约定下 **「同用例同形态 URL 仅 batch 段不同」**，对失败记录上的各资源 URL **仅替换 batch** 得到成功侧 **`success_screenshot_index_url`、成功侧 `reports_url`（若有）** 等（**不含日志 URL**）；**以 URL 写入 payload**，由 **AIFA 直接拉取**（§8.3）。可选预填 `success_screenshot_urls[]` 非必选。

#### 1.4.2 输出（四层语义）

1. **详细分析过程**（**不落库**）：以 **结构化 `evidence[]`**（类型、来源、片段、引用）+ **阶段时间线**（Plan / 各 Skill / Synthesize 或等价阶段名 + 耗时）为主；可选 **短「论证摘要」**（与 evidence 编号互链，**字数上限**在实现中配置），**不默认**输出完整模型 CoT。
2. **结论**：**详细失败原因**（长文本，展示用；**默认不落库**）。
3. **失败归类**（枚举，**默认不落库**）：
   - **a. `bug`**：含崩溃、闪退等产品缺陷（与「环境问题」边界由测试用例约定，§1.4.3）
   - **b. `spec_change`（规格变更）**：需 **对比** 当前失败截图（集）与 **历史成功**截图（集）；若对比证据不足，**禁止强判**此类（见 §8.3 降级）
   - **c. `flaky`（用例不稳定）**：需 **对比** 失败与 **历史成功**截图（集）；证据不足时同上
   - **d. `env`（环境问题）**
4. **一键设置到失败原因**：用户确认后，dt-report 写入 **`pipeline_failure_reason`**（表名以 ORM 为准），**仅同步业务结论**：
   - **`reason`**（或等价字段）：采用 AI 返回的 **结论（详细失败原因）**
   - **`failed_type`**（或等价字段）：采用 AI 返回的 **失败归类**（需与库内既有枚举 **映射表** 对齐；无法映射时走默认或阻断并提示，实现阶段定表）
   - **跟踪人 `owner`**（与现网「分析处理」「一键分析」一致）：
     - 若 AI 归类为 **`bug`**：`failed_type` 置为 bug 语义对应值；**跟踪人按模块**解析/落库（与现有一键分析链路对齐）
     - 若为 **其他归类**：按 **分析处理** 中预设的「失败类型 → 跟踪人」关系设置
   - **覆盖策略**：若该 `(case_name, failed_batch, platform)` 已存在记录，是 **upsert** 还是 **二次确认**，产品需在实现前定稿（建议二次确认以防覆盖人工结论）

**说明**：`pipeline_failure_reason` 为既有业务表；任何**新增列**须按项目规范走 `database/` SQL 迁移与 ORM 对齐；若仅写入已有列则不改表结构。

#### 1.4.3 失败归类边界（测试验收口径）

- **`bug` 与 `env`**：例如仅客户端进程崩溃可归 `bug`；设备离线、测试桩不可达等可归 `env`——**细表由测试在验收用例中列举**，开发按同一表实现映射。

### 1.5 「用 history_id 后端拼 payload」的含义（给前端/测试）

- 浏览器**不需要**自行拼凑截图目录 URL、近 N 次历史、成功批次等（**日志不通过 URL 传递**，见 §1.4.1）。
- 前端只需在 Drawer 内发起 **`history_id`**（及 `session_id`、`mode` 等），**dt-report** 根据 `history_id` **只读**数据库与配置，组装 **AIFA 契约 JSON**，再带内部 token 转发 AIFA。
- 好处：敏感拼装、与 `dt_infra` 的耦合集中在 dt-report；AIFA **零 MySQL**、不绑定表结构演进细节。

---

## 2. 核心设计原则

本架构的所有取舍都围绕以下原则展开，遇到冲突时优先级由上至下：

1. **与 dt_infra 数据库零耦合** —— AIFA 不连 MySQL，不知道表结构。
2. **与 dt-report 业务低耦合** —— AIFA 调用通过 HTTP + 独立契约；dt-report 侧以 **独立模块** 增加代理、payload 构造、（可选）一键入库与异步任务 API，**避免修改现有 service 核心逻辑**（见 §3.3）。
3. **降级优先于失败** —— 任何单一数据源故障返回 `partial` 报告，绝不整单崩。
4. **生产级但足够简单** —— 一个 Agent、五个 Skill、**五个 Tool**（Mongo 日志 + 截图 + **测试报告 HTML** + CodeHub×2）、一个内存 Session Store；避免过度工程。
5. **Token 成本硬约束** —— 结构化摘要在 Skill 之间流转，原始数据不透传到最终合成。
6. **未来可替换** —— LLM 厂商、代码仓库实现、Session 后端、Mongo schema 都走抽象或配置，切换不改代码。
7. **规格/不稳定类结论可证伪** —— 无成功截图对比证据时 **不输出强结论** 为 `spec_change` / `flaky`；写入 `data_gaps` 并降级（§1.4、§8.3）。

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
│    ├─► 结构化日志 (motor → MongoDB，按 case_name+batch+platform)  │
│    ├─► 截图/报告 (httpx → 契约 URL，HTML/图片；见 §8.3)         │
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

**一期目标**：尽量不改动现有 service 的核心逻辑；允许在评审后**增加**独立路由/服务模块（如「一键写入失败原因」「异步任务」）时**调用既有** `failure_process_service` / `one_click_analyze_service` 等中的**可复用片段**（以代码评审为准），避免复制粘贴业务规则。

**一期最少新增**（命名可微调）：

1. **`backend/api/v1/ai_proxy.py`** —— `POST /api/v1/ai/analyze`（及追问同路径或子路径）
   - 复用 `get_current_user` 做 JWT 校验
   - **限流**：同一 **`history_id`** 在滑动/固定 **1 分钟窗口内最多 10 次**分析请求（§12.4）；超限返回 **429** 与中文说明
   - 调用 `ai_context_builder.build_payload(history_id)` 构造 payload
   - `httpx.AsyncClient` 转发到 AIFA，**单次调用读超时与 SSE 总时长上限 180s（3 分钟）**（与 §9.6 一致；实现可用分段超时）
   - 透明转发 AIFA 的 SSE 响应流
   - 写一条 `sys_audit_log`（见 §12.5）
   - 请求体：`{ history_id: int, follow_up_message?: str, session_id?: str, mode: "initial"|"follow_up" }`（二期可加 `task_id` 等，§9.6）

2. **`backend/services/ai_context_builder.py`** —— 构造 AIFA 的请求 payload（**纯数据读取**，不做 AI/Prompt）
   - 按 `history_id` 读 `pipeline_history` 主记录，取出 **batch、platform、module、subtask、case_name、code_branch** 及 **截图目录、report** 等 URL 字段（**不向 AIFA 传日志 URL**；日志由 AIFA 用 payload 中的 `case_name`/`batch`/`platform` 查 Mongo）
   - 复用 `history_service` 的 helper 查近 N 次相同 `(case_name, platform)` 的执行记录（默认 N=20）→ `recent_executions`
   - **最近一次成功批次**：仅 dt-report 查库得到 `last_success_batch`；对失败 URL **仅替换 batch** 生成成功侧 **`success_screenshot_index_url`、成功侧报告 URL 等**写入 payload（**不含日志 URL**）；**不在此步强制枚举子链**（可选优化见 §4.1）
   - 读 `module_repo_mapping`（配置文件）得到 `repo_hint`
   - 组装为 AIFA 契约 JSON

3. **（与用户确认动作配套）** `POST /api/v1/ai/apply-failure-reason`（命名待定）——将 AI 返回的 **失败归类 + 结论** 经映射后写入 `pipeline_failure_reason`，规则见 §1.4；须 **JWT + 权限 + 审计**；**禁止**在未登录或无权时写入。

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

**约定**：**不向 AIFA 传递日志 HTML URL**（无 `log_url`字段）；结构化日志由 AIFA 通过 **`query_mongo_logs`** 使用 payload 中的 `case_name`、`batch`、`platform` 等查询 Mongo（§8.2）。

`screenshot_index_url` 为**截图目录或索引页 URL**（或单张 `image/*` 直链，由实现识别）。**默认由 AIFA** 使用 **httpx** 拉取；若为 HTML 索引页，在 **AIFA 内**解析出图片子链后再逐张拉取（`selectolax` 等，见技术选型 §6）。**dt-report 可选**预填 `screenshot_urls[]` / `success_screenshot_urls[]` 作为优化，**非必选**。`reports_url` 为测试报告 HTML，**由 AIFA** 调用 **`fetch_report_html`**（§6.2）拉取并截断。成功侧：`last_success_batch` + `success_screenshot_index_url`（及可选 `success_reports_url` / 与失败同字段名约定由实现固定）。

```json
{
  "session_id": "uuid-generated-by-frontend",
  "mode": "initial",
  "follow_up_message": "仅 mode=follow_up 时存在",
  "case_context": {
    "history_id": 123456,
    "batch": "202604071200",
    "case_name": "test_login_with_invalid_password",
    "platform": "Android",
    "main_module": "auth",
    "module": "auth",
    "subtask": "可选",
    "start_time": "202604071930",
    "case_result": "failed",
    "code_branch": "master",
    "screenshot_index_url": "http://.../batch_失败/screenshots/",
    "screenshot_urls": ["http://.../a.png", "http://.../b.png"],
    "pipeline_url": "http://jenkins/.../123",
    "reports_url": "http://.../batch_失败/report/",
    "case_level": "P0",
    "last_success_batch": "202604061200",
    "success_screenshot_index_url": "http://.../batch_成功/screenshots/",
    "success_screenshot_urls": ["http://.../ok1.png"]
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

- `recent_executions`：由 dt-report 按 `(case_name, platform)` 查近 N 条，AIFA 据此判断「首次失败 / 回归 / flaky」等；**与 `spec_change` / `flaky` 的视觉对比互补**（后者依赖成功截图集，§1.4）。
- `repo_hint`：**由 dt-report 侧维护**的 `main_module → 仓库` 映射（初期为 YAML 配置，后期可升级为字典表）。AIFA 不理解业务模块与仓库的对应关系。
- **字段兼容**：若一期实现中暂不传 `module`/`subtask`/`last_success_batch` 等，以 `nullable`/缺省处理；**不得**要求 AIFA 访问 MySQL 补数据。

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

**与 §1.4 对齐**：`failure_category` 为产品枚举（`bug` | `spec_change` | `flaky` | `env`）；`verdict` 可与之一致或作为对外的粗粒度兼容字段（实现阶段二选一或并存，须在 schema 中固定）。**详细分析过程**以 `evidence[]` + `stage_timeline[]` 为主；`rationale_summary` 为可选短摘要（**字数上限**）。

**`spec_change` / `flaky` 硬规则**：当 `success_screenshot_urls` 为空或对比证据不足时，模型**不得**将 `failure_category` 强判为 `spec_change` / `flaky`；应判为 `unknown` 或依赖日志/历史的次优结论，并在 `data_gaps` 写明原因。

```json
{
  "session_id": "uuid",
  "status": "ok | partial | error",
  "report": {
    "failure_category": "bug | spec_change | flaky | env | unknown",
    "verdict": "product_bug | env_issue | test_flaky | infra | unknown",
    "confidence": 0.0,
    "summary": "一句话结论",
    "detailed_reason": "详细失败原因（长文本，供展示与一键入库 reason）",
    "rationale_summary": "短论证摘要，与 evidence id 互链；可空",
    "stage_timeline": [
      { "stage": "plan", "message": "规划分析路径", "elapsed_ms": 1200 },
      { "stage": "log_analysis", "message": "分析日志", "elapsed_ms": 8000 }
    ],
    "evidence": [
      {
        "id": "e1",
        "type": "log_excerpt | report_excerpt | screenshot_observation | screenshot_compare | commit | history_pattern",
        "source": "mongo_log | report_html | screenshot | codehub | recent_executions",
        "snippet": "...",
        "reference": "具体指向（日志行号/commit sha/历史批次/截图序号）"
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
    "data_gaps": ["成功侧截图索引解析失败，未做规格/不稳定对比", "..."]
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
| `log_analysis_skill` | 定位根因行、堆栈、异常关键字：Mongo 结构化日志 + **测试报告 HTML**（契约 `reports_url`，AIFA 拉取） | `query_mongo_logs`, `fetch_report_html` | `error_lines[]`, `stack_summary`, `keywords[]`, `report_excerpt`（结构化） |
| `screenshot_skill` | 从 **`screenshot_index_url` / `success_screenshot_index_url`**（及可选预填直链表）拉取图片；识别 UI；有成功集时 **LLM 多图对比**（§4.3 硬规则） | `fetch_screenshot_b64`（**支持直链或索引页 URL**，内部可解析 HTML 后再多次 GET） | `ui_state`, `visible_error_text`, `description`, `compare_notes[]` |
| `code_blame_skill` | 反推可能引入问题的 patch | `codehub_list_commits`, `codehub_get_commit_diff` | `suspect_patches[]`（sha/author/why_suspect） |
| `synthesis_skill` | 汇总成最终报告 | _（无 tool，输入各 skill 摘要）_ | 完整 `report` 对象 |

### 6.2 Tool 清单（5 个）

所有 Tool 都是 `async` Python 函数，通过 OpenAI function-calling 协议暴露给 LLM。**不提供**「按 **日志** HTML URL 抓取」Tool（契约不传 `log_url`）；结构化日志仅 **Mongo**。**截图、测试报告** 通过契约中的 **URL 由 AIFA 拉取**。

```python
# 1. MongoDB 结构化日志查询（参数与 case_context 中 case_name/batch/platform 对齐）
async def query_mongo_logs(
    case_name: str, batch: str, platform: str,
    levels: list[str] = ["ERROR", "WARN"], limit: int = 200
) -> dict:
    """motor 只读查询，按 level 过滤，按 timestamp 倒序"""
    # returns: {records: [...], total}

# 2. 测试报告 HTML（契约 reports_url）
async def fetch_report_html(reports_url: str, max_chars: int = 20000) -> dict:
    """httpx GET → selectolax 提正文或关键区域 → 截断；非 HTML 或失败返回结构化 error"""
    # returns: {text, truncated, content_length} 或 {error, detail}

# 3. 截图：直链 image/* 或索引页 URL（索引页需解析后再逐张拉取）
async def fetch_screenshot_b64(
    screenshot_url: str, max_bytes: int = 2_000_000
) -> dict:
    """httpx GET；单张图 base64。若 URL 为目录索引 HTML，由 skill 内先解析出子 URL 再循环调用本 tool"""
    # returns: {base64, mime, size_bytes, truncated} 或 {error, detail}

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

### 8.1 日志来源（无 HTML URL）

**本期不向 AIFA 传入日志 HTML URL**，**不**通过 HTTP 抓取整页 HTML 日志。失败用例的文本日志证据 **仅** 来自 **§8.2 MongoDB 结构化日志**（`query_mongo_logs`）。若 Mongo 无数据或不可用，`log_analysis_skill` 产出空摘要并在 `data_gaps` 说明；**不**以 HTML URL 作为兜底。

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
- Mongo 连不上 → `log_analysis_skill` 跳过日志分支，`error_lines` 为空，`data_gaps` 记「Mongo 不可用」
- Mongo 查空 → 不是错误，正常返回（可能仅依赖截图/CodeHub/历史）
- Mongo 超时 → 同上，记 `data_gaps`，**无 HTML 日志兜底**

### 8.3 截图与测试报告 HTML（契约 URL，AIFA 直连）

**业务语义**：`pipeline_history` 侧存的是 **截图目录/索引页 URL** 或 **单张直链**；`reports_url` 为 **测试报告 HTML 页面 URL**。二者均经 **payload 传给 AIFA**，由 **AIFA 使用 httpx 拉取**（与「不传日志 URL」不矛盾：日志走 Mongo，见 §8.1）。

| 维度 | 细节 |
|---|---|
| **拉取责任** | **默认在 AIFA**：对 `screenshot_index_url` / `success_screenshot_index_url` 先 **GET**；若响应为 **`image/*`** 则按单张处理；若为 **`text/html`** 则在 **AIFA 内**用 `selectolax`（或等价）解析出图片直链列表，再逐张 `GET`（**解析规则与现网索引页结构绑定**，单测覆盖）。**dt-report** 若已预填 `screenshot_urls[]` / `success_screenshot_urls[]`，AIFA **可优先使用**以省一次索引请求。 |
| **测试报告** | `reports_url` 由 **`fetch_report_html`**（§6.2）拉取 HTML → 提正文或关键片段 → **截断**后进入 `log_analysis_skill` 摘要或独立证据字段（实现阶段固定 schema）。 |
| 客户端 | AIFA 共用 `httpx.AsyncClient` |
| 超时 | 索引页 / 单图 connect 3s / read 8s（可配置）；报告 HTML read 10s（可配置） |
| 大小硬上限 | **单张图 2MB**；**报告 HTML** `max_chars`（如 20000）超限截断 + `data_gaps` |
| content-type | 图片必须以 `image/` 开头；报告为 `text/html` 或容错 |
| **张数上限** | 解析出的图片各自最多 **N 张**（建议 ≤10，可 env）；超出则取「前 N-1 + 最后 1 张」等策略 |
| 编码 | 图片 base64 送视觉模型；多图时分段受模型限制 |

**视觉模型调用**（由 `screenshot_skill` 发起，示意多图）：

```python
content = [{"type": "text", "text": "以下为失败执行截图（按执行顺序）..."}]
for i, b64 in enumerate(failure_images):
    content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
if success_images:
    content.append({"type": "text", "text": "以下为最近一次成功批次截图，请对比 UI 差异..."})
    for b64 in success_images:
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
messages = [{"role": "system", "content": prompt}, {"role": "user", "content": content}]
```

**规格变更 / 用例不稳定 对比策略（推荐一期）**：

- **主路径**：**LLM 多图视觉对比** + **§4.3 硬规则**（无成功集则不强判 `spec_change`/`flaky`）。
- **可选演进**：在对比前增加轻量确定性预处理（缩略图、简单差异分），作为 gate 或辅助输入——**非一期必选**。

**降级**：

- 索引页无法解析、无子链或全空 → `data_gaps` 记录；**不整单失败**
- 单张拉取失败 → 跳过该张，继续其他张
- `reports_url` 拉取失败或解析为空 → `data_gaps`；其余 skill 继续
- **成功侧**全部不可用 → **禁止**输出 `spec_change`/`flaky` 强结论（§4.3），其余 skill 仍可按日志/历史输出 `bug`/`env`/`unknown`
- 视觉模型调用失败（配额/网络）→ skill 降级 + WARNING + `data_gaps`

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

### 9.4 报告渲染与一键入库

`ReportView.tsx` 按结构化 schema 渲染（非裸 markdown）：

- **顶部大卡片**：`failure_category`（或 `verdict`）+ `confidence` + `summary`
- **结论区**：`detailed_reason`（可折叠长文）
- **详细分析过程（不落库）**：
  - **阶段时间线** `stage_timeline[]`（步骤名 + 文案 + 耗时）
  - **`evidence[]`**：按 `source` / `type` 分组，**`snippet` 默认折叠**，支持展开；若有 `id` 可与 `rationale_summary` 互链
- **中部**：`suspect_patches`（表格）、`suggested_next_steps`（列表）
- **底部警示条**：`data_gaps`（灰色提示）
- **角标**：`trace.tool_calls / elapsed_ms`（成本与调试）
- **主操作**：**「一键设置到失败原因」**按钮 —— 调用 dt-report 接口 **POST /api/v1/ai/apply-failure-reason**（命名待定），请求体携带 `history_id`、`failure_category`、`detailed_reason`（及防重放/版本戳等实现自定）；服务端按 §1.4 映射写入 **`pipeline_failure_reason`**，成功后 Toast；失败返回明确中文原因

**刷新与关闭 Drawer**：未入库前，分析结果仍为**会话级**；关闭 Drawer 后是否保留前端 state 由产品决定（默认不保留，与旧 §9.3 session 约定一致）。**入库后**以列表/详情读 `pipeline_failure_reason` 为准。

### 9.5 Tab 懒加载

- 组件只在用户切到 "AI 归因" Tab 时 mount
- 首次 mount 不自动发请求；必须用户点"开始分析"按钮才发
- 这让"好奇点开 Drawer 但不想分析"的用户不产生任何 LLM 成本

### 9.6 批量勾选、后台排队与进度（二期 / 优化项）

**目标**：用户在列表中**勾选多条**失败用例，触发 **后台分析队列**；前端展示**排队位置 / 进行中 / 已完成**，每条有**独立入口**查看报告（与单条 Drawer 内体验对齐）。

**任务模型（概念 schema）**：

| 字段 | 说明 |
|---|---|
| `task_id` | UUID，全局唯一 |
| `history_id` | 对应一条失败执行 |
| `status` | `queued` \| `running` \| `succeeded` \| `failed` \| `cancelled` \| `partial`（与报告 status 可区分命名，实现自定） |
| `progress` | 0–100 或阶段枚举 + 文案 |
| `attempt` | 重试次数 |
| `error_code` / `message` | 失败时 |
| `created_at` / `started_at` / `finished_at` | 时间戳 |

**能力**：

- **重试**：用户对 `failed` 任务手动重试（**是否计入** `history_id` 的 10 次/分钟 额度，建议 **计入**，防刷）
- **取消**：**至少**允许取消 `queued`；`running` 是否支持协作取消依赖 AIFA 是否实现中断信号（二期评审）
- **超时**：**单次** dt-report → AIFA 的 HTTP/SSE 客户端 **总等待 3 分钟**；超时将该任务标为 `failed` 或 `partial`（若中途已有部分 SSE 数据，由实现定义），**不**默认无限挂起
- **并发**：仍受 AIFA `AIFA_MAX_CONCURRENT_ANALYSES` 与 dt-report 队列 worker 数约束

**持久化**：队列状态若需跨进程/刷新可恢复，须 **独立存储**（Redis 或 DB 任务表）；**新建表**须按项目规范提交 SQL 迁移。若一期不做持久化，则队列仅 **单进程内存**、刷新即失，须在 UI 明示。

**与一期关系**：一期可仅实现单条 Drawer + SSE；二期再挂接同一 AIFA 契约与同一报告 schema。

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

- **dt-report 侧（硬指标，与产品对齐）**：**同一 `history_id` 在 1 分钟内最多触发 10 次**「发起分析」请求（含用户快速重试；**自动重试是否计入**须在实现中固定并写入运维说明）。超限返回 **429**，body 中文说明。
- **补充（可选全局护栏）**：同一用户每分钟 / 每小时总次数上限（如原 10/min、50/h）可作为**额外**防护，**不得**弱于单 `history_id` 限制。
- **AIFA 侧**：全局并发 semaphore，默认 `AIFA_MAX_CONCURRENT_ANALYSES=8`；超过直接返回 503（不排队，避免 SSE 超时体验变差）

### 12.5 审计与业务写库边界

- **AIFA**：不连接 MySQL；仅写自身 `trace.log` / 应用日志。
- **dt-report `ai_proxy`**：每次调用 AIFA（含追问）写 **`sys_audit_log`**（若该表已落地），建议字段：`user_employee_id / history_id / session_id / mode / result_status`（`result_status` 取报告 `status` 或 HTTP 摘要）。
- **dt-report `apply-failure-reason`（一键入库）**：用户显式确认后，写入 **`pipeline_failure_reason`**（`failed_type`、`reason`、`owner`、`analyzer` 等按 §1.4 映射），**必须**同时写审计（同上或独立 action 类型），且 **JWT + 权限校验**。
- **红线重申**：**禁止** `pipeline_overview` / `pipeline_history` **DELETE**；**禁止** ORM 自动建表；其它表的 **INSERT/UPDATE** 须符合项目迁移与业务红线。一键入库**不得**在未经用户点击时静默写入。

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
| ADR-03 | 单 Agent + 5 Skill + **5 Tool**（Mongo + 报告 HTML + 截图 + CodeHub×2） | 不传**日志** URL；截图/报告 URL 由 AIFA 拉取 |
| ADR-04 | Agent 三阶段 Plan → Act → Synthesize，Skill 之间只传结构化摘要 | 防 token 爆炸；可预测可观测 |
| ADR-05 | 前端 SSE 流式而非轮询 | 用户体验更好，代码增量很小 |
| ADR-06 | 交互 = 一次性为主 + 轻量追问 | 用户明确选择；追问复用 session 摘要，不重跑 tool |
| ADR-07 | **分析草稿**（过程 + 完整结论）**默认不落业务库**；用户**一键确认**后仅将 **失败归类 + 详细原因** 写入 `pipeline_failure_reason`，并与「分析处理」「一键分析」owner 规则对齐（§1.4） | 兼顾可审计与人工确认；避免静默覆盖 |
| ADR-08 | 仅 **5** 个 Tool，严格 async/timeout/截断/结构化错误/幂等/审计；**无日志 URL 抓取**；**报告/截图走契约 URL** | 生产级最小集合 |
| ADR-09 | LLM 走 OpenAI 兼容协议，初期 GLM | 切换厂商零代码改动；初期最小配置 |
| ADR-10 | Mongo 字段名全部走 env 配置 | AIFA 不控制 Mongo schema；换源只改 env |
| ADR-11 | CodeHub 初期唯一实现，同时保留 `CodeRepoClient` Protocol | 生产级与简单的平衡；抽象成本可忽略 |
| ADR-12 | Session 存内存 LRU；抽象为 Protocol 便于未来换 Redis | 初期单实例够用，无需 Redis 依赖 |
| ADR-13 | 内部 service token 而非转发 JWT | 避免跨系统 token 语义污染 |
| ADR-14 | AIFA 只绑内网，浏览器不直连 | 鉴权/限流/审计集中在 dt-report 一处 |
| ADR-15 | dt-report 侧以 **独立模块** 增加 `ai_proxy`、`ai_context_builder`、**一键入库 API**；**避免修改现有 service 核心逻辑**，可复用其函数 | 降低回归面；入库与分析与现网规则一致 |
| ADR-16 | 单请求 token 硬上限 + 按天成本聚合 | 防止单 bug 烧光一天配额 |
| ADR-17 | Partial 优先于整单失败 | 降级优于失败，提高整体可用性 |
| ADR-18 | Prompt 作为代码走 git，不做运行时热更新 | 便于 review 和回滚 |
| ADR-19 | 前端 AI 组件独立目录，不污染 HistoryPage.tsx | HistoryPage.tsx 已 2010 行，继续塞会拖慢编辑和渲染 |
| ADR-20 | Tab 懒加载，首次 mount 不自动发请求 | 避免好奇用户产生无意义 LLM 成本 |
| ADR-21 | **截图/报告 URL** 由契约传入，**默认 AIFA httpx 拉取**；索引页在 **AIFA 内**解析；dt-report **可**预填直链作优化；张数/大小硬上限 | 与「AIFA 直连资源」一致；可选预展开减负 |
| ADR-22 | **最近一次成功批次** 仅 dt-report 查询；URL **仅替换 batch**；失败降级见 §8.3 | AIFA 零 MySQL；与现网 URL 约定绑定 |
| ADR-23 | **`spec_change`/`flaky` 证据不足不强判** | 防止无成功截图时模型胡判 |
| ADR-24 | **单 `history_id` 10 次/分钟** 限流在 dt-report | 成本与防滥用 |
| ADR-25 | **详细过程 = evidence + 阶段时间线**，短 `rationale_summary` 可选；不默认暴露完整 CoT | 可验收、可脱敏 |
| ADR-26 | **二期** 批量后台队列 + 每任务 3min 超时 + 重试/取消（§9.6） | 与一期单条解耦交付 |
| ADR-27 | **附加文件上传** 二期再做 | 降低一期范围 |

---

## 16. 未来演进方向

列为**未纳入一期**或**可持续优化**的方向（部分已在 §9.6、§1.4 有雏形）：

1. **批量队列 UI 与持久化**：多选、后台 worker、跨刷新恢复（可能引入 Redis 或任务表 + 迁移）
2. **多厂商灰度**：通过 A/B 路由在 GLM/Kimi/MiniMax 之间对比质量
3. **Redis session**：多副本部署时替换 `SessionStore` 实现
4. **Prometheus 指标**：接统一监控平台
5. **离线评估集**：收集人工标注的失败样本作为 AIFA 质量回归测试
6. **Fine-tune / RAG**：将项目特有的错误模式沉淀为知识库
7. **截图对比增强**：轻量图像相似度/关键区域裁剪后再送视觉模型（非一期必选）
8. **附加文件上传**：分析请求附加用户文件（安全扫描、大小类型限制、独立存储设计）

---

## 17. 验收清单（供实现阶段 self-check）

- [ ] AIFA 进程完全独立，不 import 任何 `backend.*` 模块
- [ ] AIFA 所有 env 以 `AIFA_` 开头
- [ ] AIFA 不建立任何 MySQL 连接
- [ ] 所有 **5** 个 tool 都是 async，都有 timeout 和截断
- [ ] 所有 **5** 个 tool 返回结构化错误而非 raise
- [ ] 契约 **无 `log_url`**；日志仅 `query_mongo_logs`
- [ ] Plan 阶段输出严格受 JSON schema 约束
- [ ] Skill 之间只传结构化摘要，不传原始 tool output
- [ ] Synthesize 阶段 prompt 输入长度有硬上限
- [ ] 单请求累计 tokens 超过 `AIFA_MAX_TOKENS_PER_REQUEST` 自动熔断为 partial
- [ ] 外部数据源故障返回 partial 而非 500（**配置类** fail-loud 除外）
- [ ] CodeHub 401 是 fail-loud（返回 500）
- [ ] LLM API key 无效是 fail-loud
- [ ] dt-report：`ai_proxy`、`ai_context_builder`、**一键入库 API** 职责清晰；**尽量不修改**现有 service 核心逻辑
- [ ] **单 `history_id` 10 次/分钟** 限流生效，返回 429
- [ ] **截图/报告 URL**：AIFA 拉取、索引页解析、张数/大小上限有文档与单测；可选 dt-report 预填直链
- [ ] **`spec_change`/`flaky`** 在成功截图证据不足时**不强判**（契约或后处理校验）
- [ ] 报告含 `stage_timeline`、`evidence`（可选 `id`）、`detailed_reason`、`failure_category`
- [ ] 一键入库仅写 **`pipeline_failure_reason`** 约定字段，**须用户点击**，写审计
- [ ] `HistoryPage.tsx` 零改动或仅改一行挂 Tab
- [ ] 所有 AI 前端组件在独立目录 `ai_analysis/`
- [ ] Tab 懒加载
- [ ] 前端 session_id 由浏览器生成，Drawer 关闭即作废（与入库后读库展示区分）
- [ ] 内部 service token 校验中间件存在且生效
- [ ] AIFA 只绑内网
- [ ] `sys_audit_log`（或等价）在 **ai_proxy** 与 **一键入库** 有写入点
- [ ] 日志脱敏：不落原始日志/diff/截图
- [ ] Trace 每次请求生成完整记录
- [ ] `/healthz` 和 `/metrics` 端点可用
- [ ] 独立 Dockerfile，不装 Playwright
- [ ] docker-compose 示例可直接拉起
- [ ] （二期）§9.6 任务状态机、3min 超时、重试/取消、逐条结果入口（若本期承诺则本期验收）
