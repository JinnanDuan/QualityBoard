# AI 辅助失败原因分析 — 实现计划与分期

- **文档类型**：实现计划（Implementation / Roadmap）
- **关联文档**：
  - `2026-04-08-ai-failure-analysis-architecture.md`（架构与契约）
  - `2026-04-08-ai-failure-analysis-tech-selection.md`（技术选型）
  - `aifa-phase-a1-service-spec.md`（**A1** 阶段规格：服务骨架、端点、DoD）
  - `dt-report-phase-a2-ai-context-builder-spec.md`（**A2** 阶段规格：`ai_context_builder`、payload、DoD）
  - `aifa-phase-a3-sse-report-contract-spec.md`（**A3** 阶段规格：SSE 进度与 report 契约收紧）
- **状态**：Draft（随排期滚动更新）
- **日期**：2026-04-14

---

## 0. 文档目的

本文档描述**如何把整体能力拆成可交付特性**、**推荐实现顺序**与**穿刺（POC）范围**，不与架构文档抢职责：

| 文档 | 回答的问题 |
|------|------------|
| 架构设计 | 系统边界、契约、降级、安全、终态行为 |
| 技术选型 | 库、协议、版本 |
| **本文档** | **先做哪块、后做哪块、穿刺做到哪一步算完成** |

架构与技术选型以各自文件为准；分期冲突时**以架构为准**，并回写本文档。

---

## 1. 穿刺（P0 / POC）— 最高优先级

**目标**：勾选**任意一条**失败用例 → 触发 AI 分析 → 展示结果 → 用户 **接受** 或 **拒绝**。

| 动作 | 行为 |
|------|------|
| **接受** | 将当前分析结果写入 **`pipeline_failure_reason`**（至少 `failed_type` / `reason` 等与产品一致）；将该条执行 **`pipeline_history.analyzed` 置为已分析**（与现网「分析处理」语义对齐，实现前对照 `failure_process_service` / `one_click_analyze_service` 确认字段组合） |
| **拒绝** | **不写库**、不更新 `analyzed`；丢弃本次草稿（前端清 state；若服务端有分析草稿 session，一并作废） |

**建议技术形态（竖切最小）**：

1. **入口**：列表勾选一条失败记录 +「AI 分析」按钮（穿刺可用简化入口；终态见架构 Drawer Tab）。
2. **分析请求**：前端传 `history_id` → dt-report **只读**拼最小 payload（**不含日志 URL**；包含 `case_name`/`batch`/`platform` + `reports_url` + `screenshot_url`）→ 调 AIFA（或穿刺期 **Mock AIFA** 返回固定 JSON）。
3. **结果展示**：结构化展示「结论 + 失败归类 + 简要依据」（可与终态 schema 子集对齐）。
4. **接受 / 拒绝**：两个独立 API 或同一资源两种 action；**接受**必须带防误写策略（例如服务端保存 `analysis_draft_id` / 短期 token，避免前端伪造结论）。

**穿刺刻意不做**（避免阻塞 POC）：AIFA 内完整索引页解析与多图拉取、成功 batch 多图对比、完整五 Skill、追问、批量队列、完整限流与审计、独立容器部署（可按团队情况二选一：先同进程 mock，再拆 AIFA）。

**完成标准（DoD）**：演示路径可走通 **分析 → 接受写库+已分析 → 拒绝不写库**；测试可按此写 3～5 条用例。

---

## 2. 分期总览（特性切片）

以下为推荐顺序；每条可单独立项、单独合并。

### Phase A — 单条闭环（承接穿刺）

| ID | 特性 | 说明 |
|----|------|------|
| A1 | 正式 **AIFA 服务骨架**（**已完成**：仓库根目录 `ai-failure-analyzer/`） | FastAPI、`/v1/analyze`、内部 token、健康检查；可先单轮 LLM 无 Tool；**详见 `aifa-phase-a1-service-spec.md`** |
| A2 | **真实 payload** | `ai_context_builder`：`case_name`/`batch`/`platform` + `reports_url` + `screenshot_url`、`recent_executions`、`repo_hint`；**不传日志 URL**；截图可先直链或空；**详见 `dt-report-phase-a2-ai-context-builder-spec.md`** |
| A3 | **SSE 进度 + 报告契约** | 与架构 §4 对齐的最小 `report` 字段 |
| A4 | **接受 / 拒绝 API 终态** | 与架构 §1.4、§9.4、§12.5 一致；审计、权限 |
| A5 | **限流** | 单 `history_id` 10 次/分钟（架构 §12.4） |

### Phase B — 分析质量与证据链

| ID | 特性 | 说明 |
|----|------|------|
| B1 | **Tool：报告/截图证据拉取** | `fetch_report_html` + `fetch_screenshot_b64`（含索引页解析、截断/条数上限；**无**日志 HTML URL） |
| B2 | **Agent 三阶段** | Plan → Act → Synthesize（架构 §5） |
| B3 | **截图/报告 URL 拉取** | AIFA：`fetch_report_html` + `fetch_screenshot_b64`（索引页解析，架构 §8.3）；可选 dt-report 预填直链 |
| B4 | **成功 batch + URL 替换 + 多图对比** | `spec_change` / `flaky` 规则与降级（架构 §4.3、§8.3） |
| B5 | **CodeHub** | list_commits / diff |

### Phase C — 体验与运维

| ID | 特性 | 说明 |
|----|------|------|
| C1 | **Drawer Tab + 懒加载** | 与架构 §9 一致；`HistoryPage` 最小改动 |
| C2 | **追问 + Session** | 架构 §7、§5 追问分支 |
| C3 | **一键入库与「分析处理」owner 全规则** | bug 按模块 / 非 bug 按预设映射（架构 §1.4） |
| C4 | **观测与成本** | trace、metrics、token 熔断 |

### Phase D — 二期（架构 §9.6）

| ID | 特性 | 说明 |
|----|------|------|
| D1 | 批量勾选、后台队列、进度、重试、取消、3min 超时 | 可能引入任务存储与迁移 |

---

## 3. 依赖关系（简图）

```
穿刺(P0) ──► Phase A（硬化服务与契约）
                │
                ├──► Phase B（Tool 与证据链）
                │
                └──► Phase C（Tab、追问、规则对齐）
                          │
                          └──► Phase D（批量队列）
```

---

## 4. 与「整体文档」的关系

- **整体能力**：仍以 **架构 + 选型** 为单一事实来源（SSOT）。
- **本文档**：仅跟踪 **落地顺序与穿刺 DoD**；排期变更时改本文档即可，不必反复改架构大段文字。

---

## 5. 维护约定

- 每完成一个 Phase，在本文档对应行打勾或更新「状态」列（可选）。
- 若产品决定砍掉某期，在本文档标注 **已取消** 并简述原因，避免与架构正文打架。
