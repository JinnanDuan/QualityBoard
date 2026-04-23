# AIFA Phase B5 — CodeHub 提交与 Diff 证据规格说明

- **文档类型**：阶段规格（Phase Spec，仅描述 **B5** 交付范围）
- **关联文档**（单一事实来源优先级）：
  1. `2026-04-08-ai-failure-analysis-architecture.md`（§6.2 Tool、§8.4 CodeHub、§10 失败语义；冲突时以架构为准）
  2. `2026-04-14-ai-failure-analysis-implementation-plan.md`（分期 **B5** 与依赖关系）
  3. `aifa-phase-b2-agent-three-stage-spec.md`（B2 三阶段编排与摘要隔离）
  4. `dt-report-phase-a2-ai-context-builder-spec.md`（`repo_hint` 来源与映射约定）
  5. `2026-04-08-ai-failure-analysis-tech-selection.md`（CodeRepoClient 抽象、httpx 选型）
- **对应分期**：实现计划 **B5** — **CodeHub 证据链**：交付 `codehub_list_commits` 与 `codehub_get_commit_diff`，为 `code_blame_skill` 产出可追溯 `suspect_patches[]`。
- **状态**：Draft
- **日期**：2026-04-23

---

## 0. 文档目的

本文档回答：**B5 合并时 CodeHub 能力必须具备哪些输入前提、Tool 行为、筛选与截断策略、失败降级、安全与验收标准**。  
核心目标是让“可疑代码变更”从主观猜测变成可审计证据，不破坏 B2 的摘要隔离与可控成本。

**B5 不包含**（由其他分期负责）：

| 分期 | 内容 |
|------|------|
| **A2** | `repo_hint` 生产与映射维护（dt-report 侧） |
| **B1/B3** | 报告/截图 URL 拉取与解析 |
| **B2** | Plan -> Act -> Synthesize 主循环与 session 语义 |
| **B4** | 成功批次替换与多图对比判定规则 |
| **C2** | 追问 UI 与交互体验完善 |

---

## 1. 职责边界

### 1.1 必须满足

- **输入来源固定**：仓库信息来自请求体 `repo_hint`（`repo_url`、`default_branch`、`path_hints`）；AIFA 不推断“模块到仓库”映射。
- **两个 Tool 交付**：
  - `codehub_list_commits(repo_url, branch, since, until, path_filters, limit)`
  - `codehub_get_commit_diff(repo_url, sha, max_lines)`
- **技能产物可追溯**：`code_blame_skill` 输出 `suspect_patches[]`，每条至少含 `sha`、`author`、`commit_time`、`why_suspect`（字段名可调整，语义必须稳定）。
- **成本可控**：
  - 提交列表有条数上限（默认 `limit=30`）
  - diff 有行数上限（默认 `max_lines=500`）
  - 仅对 Top 3-5 条可疑 commit 拉取 diff
- **失败语义明确**：
  - 网络故障/超时/5xx：可降级，返回 `partial + data_gaps`
  - 时间窗无提交：业务正常结果，不作为错误
  - **401 token 无效：fail-loud（返回 500）**

### 1.2 明确禁止

- **禁止**在 `repo_hint` 缺失时强行猜测仓库地址或跨仓扫描。
- **禁止**将原始完整 diff 直接透传到 Synthesize 阶段（必须先摘要化）。
- **禁止**无上限抓取大 diff 或对全部 commit 拉 diff。
- **禁止**在日志中记录完整 token、完整 diff 原文、完整敏感 URL query。

### 1.3 可选（B5 允许分步）

- 初版可先按时间窗 + path filter 做基础筛选；更复杂“语义相关性排序”可后续迭代。
- 初版可串行拉 TopN diff；并发优化可后续补充，但需保留全局超时与限并发。

---

## 2. 输入与默认策略

| 输入字段 | 来源 | B5 用途 |
|----------|------|---------|
| `repo_hint.repo_url` | dt-report `module_repo_mapping` | CodeHub 仓库定位 |
| `repo_hint.default_branch` | 同上 | branch 默认值 |
| `repo_hint.path_hints[]` | 同上 | 提交列表路径过滤 |
| `case_context.start_time` / `batch` | 当前失败记录 | `until` 基准时间 |
| `case_context.last_success_batch` | dt-report 计算最近成功批次 | `since` 优先基准时间 |

**时间窗优先级（必须）**：

- `branch`: `repo_hint.default_branch`，若为空则回退 `"master"`（或服务配置默认分支）
- `until`: 当前失败批次/开始时间
- 当 `last_success_batch` 可用时：`since = last_success_batch`（即“最近成功批次 -> 当前失败批次”窗口）
- 当 `last_success_batch` 缺失/非法时：`since = until - 7d`（兜底窗口）
- `path_filters`: `repo_hint.path_hints`（为空时允许无路径过滤）
- `list_limit`: 30
- `diff_max_lines`: 500
- `diff_top_n`: 3-5

**说明**：

- 对“长期连续成功后首次失败”的主流场景，优先窗口可显著降低噪声提交数量，提高可疑变更定位精度。
- 兜底 7 天窗口仅用于成功批次不可得场景，避免因数据缺失导致 CodeHub 完全不可用。

---

## 3. Tool 契约与行为细则

## 3.1 `codehub_list_commits`

| 项 | 要求 |
|----|------|
| 方法 | `GET`（由 CodeHub API 文档确定 endpoint） |
| 认证 | `AIFA_CODEHUB_TOKEN`（header 名在实现时按网关规范固定） |
| 入参 | `repo_url`, `branch`, `since`, `until`, `path_filters[]`, `limit` |
| 成功返回最小 | `{commits:[{sha, author, time, message, files[]}]}` |
| 失败返回 | 结构化 `{error, detail, status_code?}`（401 见 §5） |
| 排序 | 默认按提交时间倒序（若上游 API 不保证，需本地规范化） |

**行为要求**：

- 需要对时间窗参数做合法性校验（`since <= until`）。
- 当输入包含 `last_success_batch` 且可解析时，必须优先使用“成功 -> 失败”窗口，不得静默改为固定 7 天。
- `path_filters` 为空时允许全仓时间窗查询，但仍受 `limit` 限制。
- 返回条目必须可被后续评分逻辑消费，缺失关键字段时要有兜底值或结构化告警。

## 3.2 `codehub_get_commit_diff`

| 项 | 要求 |
|----|------|
| 方法 | `GET`（按 CodeHub API endpoint） |
| 入参 | `repo_url`, `sha`, `max_lines` |
| 成功返回最小 | `{diff, truncated, files_changed}` |
| 截断 | 超过 `max_lines` 必须裁剪并标记 `truncated=true` |
| 失败返回 | 结构化 `{error, detail, status_code?}` |

**行为要求**：

- 仅对 `list_commits` 筛出的 TopN 执行，不允许对全量 commit 拉 diff。
- diff 截断策略固定（例如按行裁剪，保留头部上下文），并可测试断言。

---

## 4. `code_blame_skill` 产物约束（B5 最小）

`code_blame_skill` 至少输出：

- `suspect_patches[]`：
  - `sha: str`
  - `author: str`
  - `commit_time: str`
  - `summary: str`（提交信息与关键文件变更摘要）
  - `why_suspect: str`（怀疑理由，需引用规则或证据）
  - `files_touched: list[str]`
  - `diff_excerpt: str`（可选，必须受截断）
  - `truncated: bool`
- `codehub_meta`：
  - `time_window`
  - `list_count`
  - `diff_fetched_count`
  - `skipped_reason[]`（如“超限未拉取”“diff 拉取失败”）

**关键约束**：

- Skill 可读取 raw diff，但输出到 Synthesize 的只能是摘要字段。
- `why_suspect` 必须可解释，避免仅输出“模型认为可疑”。

---

## 5. 错误语义与降级

| 场景 | 期望行为 |
|------|----------|
| `repo_hint` 缺失或 `repo_url` 为空 | 跳过 code blame，`data_gaps` 记“仓库映射缺失”，可返回 `partial` |
| `last_success_batch` 缺失/非法 | 回退 `since=until-7d`，并在 `codehub_meta` 或 `data_gaps` 标注“已使用兜底时间窗” |
| CodeHub 网络失败/超时/5xx | 跳过该 skill 或部分结果，写 `data_gaps`，不中断整单 |
| 时间窗无提交 | 正常返回空 `suspect_patches[]`，附“该时间窗无新增提交” |
| commit diff 单条失败 | 跳过该条，继续其他 commit，写 `skipped_reason` |
| **CodeHub 401（token 无效）** | **fail-loud**：整单返回 500，提示联系管理员 |

---

## 6. 安全与可观测性

### 6.1 安全要求

- `repo_url` 在请求前需校验域名白名单（必须匹配 `AIFA_CODEHUB_BASE_URL` 域）。
- 禁止拼接任意用户输入形成未校验 CodeHub API URL。
- Token 仅从环境变量读取，不落盘不回显。

### 6.2 日志要求

- INFO 摘要日志建议字段：`request_id`、`session_id`、`skill=code_blame`、`elapsed_ms`、`list_count`、`diff_fetched_count`、`status`。
- 仅记录 `diff_hash` + `lines`，不记录 raw diff。
- 401 需有可检索错误码，便于告警与运维排查。

---

## 7. 验收标准（B5 DoD）

以下全部满足，视为 **B5 完成**：

1. `codehub_list_commits` 与 `codehub_get_commit_diff` 可稳定返回结构化成功/失败结果。
2. `code_blame_skill` 能按“成功批次 -> 失败批次优先，缺失再回退 7 天”的时间窗 + path filter 产出可追溯 `suspect_patches[]`。
3. diff 抓取严格受 TopN 与 `max_lines` 双上限约束，且有单测覆盖。
4. `repo_hint` 缺失、网络失败、无提交三类场景均可降级为 `partial`（或空证据）而非未处理 500。
5. CodeHub 401 明确触发 fail-loud（HTTP 500），并有中文可读提示。
6. Synthesize 输入不包含 raw diff，仅包含 B5 摘要产物。
7. 日志满足脱敏要求：不记录 token 与 raw diff。

---

## 8. 推荐测试清单

| 用例 | 输入场景 | 期望 |
|------|----------|------|
| 主路径（成功->失败窗口） | `repo_hint` 完整 + `last_success_batch` 可用 + 时间窗有提交 | `since=last_success_batch` 且返回非空 `suspect_patches[]` |
| 兜底时间窗 | `last_success_batch` 缺失或非法 | 回退 `since=until-7d` 并有可观察标记 |
| 无仓库映射 | `repo_hint` 空 | 跳过 code blame，`data_gaps` 可解释 |
| 时间窗无提交 | list 返回空 | `suspect_patches=[]` 且状态正常 |
| path 过滤生效 | 提供 `path_hints` | 结果集中仅出现相关路径提交（或显著减少） |
| TopN 限制 | list 返回 >30，TopN=3 | 仅对 3 条拉 diff |
| diff 截断 | 单条 diff 超 `max_lines` | `truncated=true` 且行数受控 |
| 单条 diff 失败 | 某 sha 返回 5xx | 跳过该条，其他条继续 |
| 401 fail-loud | token 无效 | 返回 500，不走 `partial` |

---

## 9. 与相邻分期衔接

- **对 A2**：强依赖 `repo_hint` 的正确映射；B5 不负责映射生产。
- **对 B2**：B5 作为 `code_blame_skill` 的能力增强，不改变三阶段主框架。
- **对 B4**：B4 提供视觉证据，B5 提供代码变更证据，两者在 Synthesize 互补。
- **对 C2**：追问阶段默认复用缓存 `suspect_patches`，减少重复调用 CodeHub。

---

## 10. 维护约定

- 若 CodeHub API endpoint/认证格式变化：先更新架构或接入 ADR，再同步本文件与实现。
- 若未来新增 `gitlab/gitea` provider：更新 `CodeRepoClient` 兼容矩阵与 B5 测试清单。
- 任何对 fail-loud 条件（尤其 401）的调整，必须同步更新架构与本阶段 DoD。

### 修订记录

| 日期 | 变更 |
|------|------|
| 2026-04-23 | 初稿：B5 范围、Tool 契约、降级/401 语义、DoD 与测试清单 |
| 2026-04-23 | 调整时间窗策略：优先 `last_success_batch -> failed_batch`，缺失时回退 `-7d` |
