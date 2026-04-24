# AIFA Phase B2 — Agent 三阶段编排（Plan / Act / Synthesize）规格说明

- **文档类型**：阶段规格（Phase Spec，仅描述 **B2** 交付范围）
- **关联文档**（单一事实来源优先级）：
  1. `2026-04-08-ai-failure-analysis-architecture.md`（§5 Agent 状态机、§6 Skill×Tool、§10 失败语义；冲突时以架构为准）
  2. `2026-04-14-ai-failure-analysis-implementation-plan.md`（分期 **B2** 与依赖关系）
  3. `aifa-phase-b1-report-screenshot-tools-spec.md`（B1 Tool 能力与错误契约）
  4. `aifa-phase-a3-sse-report-contract-spec.md`（SSE 进度与 report 契约基线）
- **对应分期**：实现计划 **B2** — **Agent 三阶段主循环**：`Plan -> Act -> Synthesize`，并支持 `follow_up` 的 session 复用。
- **状态**：Draft
- **日期**：2026-04-22

---

## 0. 文档目的

本文档回答：**B2 合并时 Agent 必须具备哪些编排行为、阶段边界、输入输出约束、失败降级与验收标准**；不重复架构全文，只固化 **B2 范围内的「必须 / 可选 / 禁止」**。

**B2 不包含**（由其他分期负责）：

| 分期 | 内容 |
|------|------|
| **B1** | `fetch_report_html` / `fetch_screenshot_b64` 具体拉取与索引页解析细节 |
| **B3** | 截图/报告 URL 解析策略的进一步强化与现网 DOM 大规模迭代 |
| **B4** | 成功 batch URL 替换、多图对比业务规则细化 |
| **B5** | CodeHub 调用能力完整接入与质量打磨 |
| **C2** | 追问 UI 与 dt-report 侧会话体验完善（B2 仅定义 AIFA 语义） |

---

## 1. 职责边界

### 1.1 必须满足

- **固定三阶段状态机**：一次 `mode=initial` 请求必须按 `Plan -> Act -> Synthesize` 执行，阶段顺序不可交换。
- **Plan 受限选择**：Plan 阶段只能从预定义 skill 集合中选取与排序（如 `history_skill`、`report_analysis_skill`、`screenshot_skill`、`code_blame_skill`），输出必须是可校验 JSON。
- **Act 顺序执行**：Act 按 `skill_plan` 顺序执行各 skill；每个 skill 只能调用自身白名单 tool。
- **Skill 隔离**：skill 间仅传递结构化摘要，不传 raw tool output。
- **Synthesize 只看摘要**：最终报告合成输入仅为阶段摘要与必要元信息，不直接拼接原始 HTML、原始 diff、原始 base64。
- **follow_up 语义**：`mode=follow_up` 默认跳过 Plan/Act，直接用 session 中缓存的中间结果执行 Synthesize 变体。
- **可观测**：SSE `progress` 至少覆盖三阶段开始/结束（或等价状态），并写入 `stage_timeline`。
- **失败可降级**：单个 skill 或 tool 失败不应导致整单 500；若仍有可用证据，返回 `status="partial"` 并填充 `data_gaps`。

### 1.2 明确禁止

- **禁止**让 Plan 返回未注册 skill 名称并被执行。
- **禁止**在 Synthesize 阶段绕过摘要隔离，直接读取 raw tool 大文本或大图。
- **禁止**在 `follow_up` 默认路径中无条件再次触发全部 tool 调用。
- **禁止**未做上限控制地拼接各 skill 输出到最终 prompt（必须有硬上限或截断策略）。
- **禁止**因单一外部依赖短时失败而直接将 HTTP 200 流式请求升级为未处理 500（配置错误 fail-loud 场景除外）。

### 1.3 可选（B2 允许分步）

- Plan 的输出可先以最小字段实现（如仅 `skills` + `reason`），后续再扩展权重、优先级解释。
- 可先串行执行 skill；并发调度留待后续性能迭代。
- `follow_up` 下“必须补查时重走 Plan”可先保守实现为“仅提示 data_gaps，不自动补查”。

---

## 2. 状态机与阶段出口条件

## 2.1 `mode=initial`

1. **Plan**
   - 输入：请求上下文（`case_context`、`recent_executions`、`repo_hint`、可选 `follow_up_message` 为空）。
   - 输出：`skill_plan`（有序数组）+ 可选解释字段。
   - 出口条件：JSON 校验通过；否则走兜底计划（见 §5）。

2. **Act**
   - 输入：`skill_plan` + 请求上下文。
   - 执行：逐个 skill，产出 `skill_summaries[skill_name]`。
   - 出口条件：全部 skill 完成，或达到可合成最小证据门槛（其余记 `data_gaps`）。

3. **Synthesize**
   - 输入：`skill_summaries` + 关键元信息（`session_id`、时间线、data_gaps）。
   - 输出：最终 `report`。
   - 出口条件：`report` 结构校验通过，推送 `event: report` 结束。

## 2.2 `mode=follow_up`

- 默认路径：跳过 Plan 与 Act，直接读取 `session_id` 对应的 `skill_summaries` 执行 Synthesize 变体。
- 若 session 缺失或过期：返回结构化错误（建议 `event: error` + 可读 message），不隐式退化为全量重跑。
- 是否允许“必须补查后重走 Plan”：B2 可选；若暂不支持，必须在 `data_gaps`/错误信息中明确说明。

---

## 3. Skill 与 Tool 编排约束

### 3.1 Skill 清单（B2 生效范围）

| Skill | 允许 Tool | 产出摘要最小字段 |
|------|-----------|------------------|
| `history_skill` | 无 | `pattern`, `last_pass_batch` |
| `report_analysis_skill` | `fetch_report_html` | `error_lines[]`, `stack_summary`, `keywords[]` |
| `screenshot_skill` | `fetch_screenshot_b64` | `ui_state`, `visible_error_text`, `compare_notes[]` |
| `code_blame_skill` | `codehub_list_commits`, `codehub_get_commit_diff` | `suspect_patches[]` |
| `synthesis_skill` | 无 | 最终 `report` |

> 注：B2 允许在实现初期按能力开关临时禁用某些 skill，但需保证 Plan 不会选中被禁用项，或在 Act 中可预期降级并写入 `data_gaps`。

### 3.2 编排规则

- Plan 只决定“执行哪些 skill、顺序如何”，不执行 tool。
- Act 仅负责执行 skill 与收集摘要，不生成最终面向用户的完整长报告。
- Synthesize 不调用 tool，不访问外部数据源。

---

## 4. Session 与数据模型（B2 最小）

为支撑 follow_up，AIFA 侧需有最小会话缓存（内存或可替换存储，B2 不强制持久化引擎）：

- `session_id: str`
- `mode: "initial" | "follow_up"`
- `plan: list[str]`
- `skill_summaries: dict[str, dict]`
- `stage_timeline: list[dict]`
- `data_gaps: list[str]`
- `updated_at: int`（unix ts）

**TTL 建议**：30 分钟（实现可配置）。  
**容量策略**：超限按 LRU 或最旧淘汰（实现固定一种即可）。

---

## 5. 错误语义与降级

### 5.1 分级原则

- **Partial（推荐默认）**：某个 skill 失败、某个 tool 超时、某路证据缺失；仍可给出报告。
- **Error（业务可恢复失败）**：完全缺少可用于合成的摘要，或会话缺失导致 follow_up 无法执行。
- **Fail-loud（配置类）**：核心配置错误（如内部 token/关键密钥错误）可按架构策略直接失败。

### 5.2 阶段级处理建议

- Plan JSON 非法：记录 warning，使用兜底 `skill_plan`（如 `["history_skill", "report_analysis_skill", "screenshot_skill"]`，按可用能力裁剪）。
- Act 单 skill 失败：写 `data_gaps`，继续后续 skill。
- Synthesize 结构校验失败：尝试一次修复性重试；仍失败则返回 `status="error"` 的结构化结果而非未处理异常。

---

## 6. SSE 与可观测性（B2 补充要求）

- `progress` 事件至少包含阶段粒度：`plan_started/plan_done`、`act_started/act_done`、`synthesize_started/synthesize_done`（命名可调整，但语义必须稳定）。
- `report.stage_timeline` 需记录阶段名与耗时（毫秒）。
- 日志最小字段：`request_id`、`session_id`、`stage`、`skill`（若适用）、`elapsed_ms`、`status`。
- 禁止记录 raw HTML、raw base64、完整敏感 URL query。

---

## 7. 验收标准（B2 DoD）

以下全部满足，视为 **B2 完成**：

1. `mode=initial` 可稳定跑通三阶段，并返回包含 `stage_timeline` 的 `report`。
2. Plan 输出严格受 JSON schema 校验；非法输出有可测试兜底策略。
3. Act 期间 skill 间仅传结构化摘要；代码路径可证明未拼接 raw tool output 到跨 skill 上下文。
4. Synthesize 输入有长度上限（截断或硬限制），避免 prompt 失控。
5. `mode=follow_up` 能复用 session 中间结果生成追问回答；session 不存在时返回结构化错误。
6. 任一 skill/tool 失败时，若仍可合成，返回 `status="partial"` + `data_gaps`，不抛未处理 500。
7. 自动化测试覆盖至少：Plan 非法 JSON、单 skill 失败降级、follow_up 命中/未命中 session、Synthesize 输入上限策略。

---

## 8. 推荐测试清单

| 用例 | 输入场景 | 期望 |
|------|----------|------|
| 初始请求主路径 | `mode=initial` + 正常 payload | 阶段顺序正确，最终 `report.status in {ok, partial}` |
| Plan 非法输出 | mock LLM 返回非 JSON | 触发兜底计划，流程继续 |
| Skill 局部失败 | `fetch_report_html` 超时 | 仍返回 `partial`，`data_gaps` 含报告缺失 |
| Skill 隔离校验 | 构造大 raw 输出 | Synthesize 输入仅摘要，长度受控 |
| follow_up 命中 | 有 `session_id` 且缓存可用 | 跳过 Plan/Act，直接生成追问结果 |
| follow_up 未命中 | 过期或不存在 session | 结构化错误，不 silent full rerun |
| timeline 完整性 | 全流程 | `stage_timeline` 至少含三阶段条目 |

---

## 9. 与相邻分期衔接

- **对 B1**：B2 直接消费 B1 的 tool 契约与结构化错误。
- **对 B3/B4**：截图索引解析与对比规则增强后，不改 B2 三阶段主框架，仅新增 skill 内部能力。
- **对 C2**：前端追问体验、会话展示可复用 B2 的 `session_id` 与 follow_up 语义。

---

## 10. 维护约定

- 若架构 §5/§6 对阶段边界、skill 清单、follow_up 规则有变更：先更新架构，再同步本文件与实现。
- 若实现引入新 skill：必须同步更新「Plan 可选集合」「Skill×Tool 矩阵」「DoD 与测试清单」。

### 修订记录

| 日期 | 变更 |
|------|------|
| 2026-04-22 | 初稿：B2 三阶段状态机、skill 编排约束、follow_up 语义、错误降级与 DoD |
