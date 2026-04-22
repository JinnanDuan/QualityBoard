# AIFA Phase B1 — 报告与截图证据拉取（Tool）阶段规格说明

- **文档类型**：阶段规格（Phase Spec，仅描述 **B1** 交付范围）
- **关联文档**（单一事实来源优先级）：
  1. `2026-04-08-ai-failure-analysis-architecture.md`（§6.2 Tool、§8.1/§8.3 证据与降级；冲突时以架构为准）
  2. `2026-04-14-ai-failure-analysis-implementation-plan.md`（分期 **B1** 与依赖关系）
  3. `dt-report-phase-a2-ai-context-builder-spec.md`（`case_context` 中 `reports_url`、截图字段来源与**禁止传 `log_url`**）
  4. `2026-04-08-ai-failure-analysis-tech-selection.md`（`httpx`、`selectolax` 选型）
- **对应分期**：实现计划 **B1** — **`fetch_report_html` + `fetch_screenshot_b64`**：从契约中的 URL 拉取测试报告 HTML 与截图（含索引页解析），截断与条数上限可配置，**不提供**按日志 HTML URL 抓取的能力。
- **状态**：Draft
- **日期**：2026-04-22

---

## 0. 文档目的

本文档回答：**B1 合并时 AIFA 必须具备哪些证据拉取行为、返回结构、上限、错误语义与验收标准**；不重复架构全文，只固化 **B1 范围内的「必须 / 可选 / 禁止」**。

**B1 不包含**（由其他分期负责）：

| 分期 | 内容 |
|------|------|
| **A1–A5** | 服务骨架、payload、SSE、写库、限流（已交付或独立 spec） |
| **B2** | Plan → Act → Synthesize 主循环与 skill 编排 |
| **B3** | 与 B1 重叠的「索引页解析细节」若需按现网 DOM 大量迭代，可在 B3 细化；B1 须先交付**可测试的最小可用**解析与降级 |
| **B4** | 成功 batch、URL 替换、多图对比业务规则 |
| **B5** | CodeHub list_commits / diff |

---

## 1. 职责边界

### 1.1 必须满足

- **输入来源**：证据 URL 仅来自请求体中的 `case_context`（及可选预填的 `screenshot_urls` / `success_screenshot_urls` 等），与 **dt-report `ai_context_builder`** 输出一致；**不得**要求 AIFA 读 MySQL。
- **两个 Tool（函数级契约）**：
  - `fetch_report_html(reports_url, max_chars=...)`：拉取测试报告 HTML，抽取可用文本或结构化片段，**截断**后返回。
  - `fetch_screenshot_b64(screenshot_url, max_bytes=...)`：拉取单张 `image/*`，或配合上层对**同一 URL** 先识别为 HTML 索引页再解析子链（见 §3.2）。
- **全部 async**：对外暴露为 `async def`，内部使用共享 `httpx.AsyncClient`（与架构、技术选型一致）。
- **全部可配置上限**：`max_chars`、`max_bytes`、索引页解析出的**最大图片张数**、各类 **HTTP 超时**须在实现中固定为常量或 env，并文档化默认值。
- **结构化错误**：网络错误、非预期内容类型、解析失败等**不抛未捕获异常**致整单 500；返回包含 `error` / `detail`（或等价）的 dict，供后续 skill 写入 `data_gaps`。
- **不提供日志 HTML 抓取**：契约**不传 `log_url`**；本阶段**不**实现「按整页日志 HTML URL 抓取」的 Tool。

### 1.2 明确禁止

- **禁止**在 Tool 内隐式拼接或猜测 `log_url`、或从 dt-report 以外的配置「补」日志 URL。
- **禁止**将完整 HTML 原文、完整 base64 图片写入**应用日志**（仅允许长度、hash、状态码等摘要，见 §6）。
- **禁止**无超时、无大小上限的 GET；禁止跟随重定向到任意外网（见 §5）。

### 1.3 可选（B1 允许分步）

- **DOM/选择器**：具体 `selectolax` 选择器与现网报告/索引页结构绑定，可在初版用**保守策略**（例如先提 `body` 文本再截断），再在 B3 收紧为「只提错误区域」。
- **dt-report 预填直链**：若 `screenshot_urls[]` 已非空，AIFA **可优先**使用该列表，减少对索引页的一次请求（与架构 §4.1 一致）。

---

## 2. 与 `case_context` 的字段关系（语义）

表字段以 `backend/models/pipeline_history.py` 为准；契约命名以架构 §4.1 为准。

| 契约字段 | 典型来源 | B1 使用方式 |
|----------|----------|-------------|
| `reports_url` | `pipeline_history.reports_url` | `fetch_report_html` 唯一报告入口 |
| `screenshot_index_url` | `pipeline_history.screenshot_url` 映射 | 单张直链 **或** 目录/索引页 URL |
| `screenshot_urls` | 可选预填 | 若存在且非空，**优先**用于多图拉取 |
| `success_*` | B4 范围 | B1 工具实现应**可复用**同一套 fetch/parse 逻辑；是否在本期接 `follow_up` 由 B2 决定 |

---

## 3. Tool 行为细则

### 3.1 `fetch_report_html`

| 项 | 要求 |
|----|------|
| 方法 | `GET`，`httpx` |
| 期望 `Content-Type` | `text/html` 为主；非 HTML 可返回结构化 `error`，不崩溃 |
| 解析 | 使用 `selectolax`（或技术选型锁定方案）提取正文或关键区域；**必须**在 `max_chars` 处截断并标记 `truncated` |
| 返回（成功示意） | 至少包含：`text`（或等价）、`truncated`、`content_length`；字段名以实现为准，须稳定 |
| 返回（失败） | `error`、`detail`，**不 raise** |

### 3.2 `fetch_screenshot_b64`

| 项 | 要求 |
|----|------|
| 单 URL 首次 GET | 若 `Content-Type` 为 `image/*`：读 body，校验 `max_bytes`，返回 base64（或等价）与 `mime` |
| 若为 `text/html` | 视为**索引页**：解析出图片 URL 列表（规则在实现中固定并配**单测 fixture**），再对子 URL 循环拉取；循环须受 **最大张数 N** 约束 |
| 张数策略 | 超出 N 时策略须固定（例如「前 N-1 + 最后 1 张」），并在返回或 `data_gaps` 可解释 |
| 返回（成功） | 单张：`base64` / `mime` / `size_bytes` 等；多张时由上层聚合或返回列表，**必须**有统一 schema 文档 |
| 返回（失败） | 结构化 `error`，单张失败可跳过该张并继续（由调用方 skill 策略决定，B1 提供原子能力即可） |

### 3.3 超时与大小（建议默认值，可在实现中覆盖）

与架构 §8.3 方向一致，建议在 B1 中**写死初值**并在 env 中可选覆盖：

- 报告 HTML：connect / read 超时（例如 connect 3s、read 10s 量级）
- 单图：connect / read 超时 + `max_bytes`（例如 2MB 量级）
- `max_chars`：例如 20000（与架构示例同量级）

---

## 4. 安全（SSRF 与 URL 约束）

- 对即将请求的 URL 做**允许规则**：例如仅允许特定 host 前缀、或内网域名清单（与运维/网络环境一致），**禁止**任意公网 SSRF。
- **禁止**默认 `follow_redirects=True` 且无白名单；若开启重定向，须限制次数与目标 host。
- URL 长度上限，防止异常输入。

---

## 5. 可观测性与日志

- 每次 Tool 调用建议打 **INFO** 级摘要日志：`request_id` / `session_id`（若可传）/ `tool_name` / `elapsed_ms` / `input_url` 的**脱敏或 host+path 截断** / 输出大小。
- **禁止**在日志中输出：完整 HTML、完整 base64、完整 URL 中的敏感 query（若存在）。

---

## 6. 验收标准（B1 DoD）

以下全部满足，视为 **B1 完成**：

1. **两个 Tool** 均以 `async` 实现，返回结构可被单元测试断言（成功 / 失败路径）。
2. **`fetch_report_html`**：对合法小 HTML 能返回非空 `text`；超大内容在 `max_chars` 处截断且 `truncated=true`。
3. **`fetch_screenshot_b64`**：对 `image/*` 直链能返回合理 payload；对索引页 HTML 能解析出至少 0 条图片 URL 且不崩（有 fixture）。
4. **错误语义**：4xx/5xx/超时返回结构化错误，不导致 `/v1/analyze` 未处理异常 500（除非上层另有约定）。
5. **无 `log_url` Tool**，且代码路径中不引入日志 HTML 抓取。
6. **单测覆盖**：关键路径（含截断、索引页、失败）有自动化测试；可选 pytest-httpx mock。

---

## 7. 推荐测试清单

| 用例 | 输入场景 | 期望 |
|------|----------|------|
| 报告小页 | 短 HTML | 有 `text`，未截断或 `truncated` 为 false |
| 报告巨大 | 超过 `max_chars` | 截断 + `truncated` |
| 报告 404/5xx | mock | 结构化 `error` |
| 截图直链 | `image/png` | 有 base64 或等价字段，≤ `max_bytes` |
| 截图索引 | 含多张 `img` 的 HTML | 解析出 ≤N 张；超出策略符合 §3.2 |
| 非预期类型 | `application/json` | 不崩溃，结构化错误 |
| URL 非白名单 | 恶意 host | 拒绝请求或结构化错误（依 §4 实现） |

---

## 8. 与相邻分期衔接

- **对 A2**：仅消费已存在的 `reports_url` / 截图相关字段；**不**改 dt-report 表结构。
- **对 B2**：B2 的 Plan/Act 将调用本阶段 Tool，不在 B1 实现完整 Agent。
- **对 B4/B5**：成功侧 URL 与 CodeHub 仍按实现计划与架构各自分期交付。

---

## 9. 维护约定

- 若架构 §6.2 / §8.3 调整上限或 Tool 数量：先改架构 SSOT，再同步本文件与实现。
- 索引页 DOM 与现网变更时：优先补**回归 fixture** 再改选择器，避免线上静默质量下降。

### 修订记录

| 日期 | 变更 |
|------|------|
| 2026-04-22 | 初稿：B1 范围、`fetch_report_html` / `fetch_screenshot_b64`、边界、安全、DoD 与测试清单 |
