# AIFA Phase B3 — 报告/截图 URL 解析与归一化规格说明

- **文档类型**：阶段规格（Phase Spec，仅描述 **B3** 交付范围）
- **关联文档**（单一事实来源优先级）：
  1. `2026-04-08-ai-failure-analysis-architecture.md`（§4.1 case_context、§8.3 URL 与证据拉取约束；冲突时以架构为准）
  2. `2026-04-14-ai-failure-analysis-implementation-plan.md`（分期 **B3** 与依赖关系）
  3. `aifa-phase-b1-report-screenshot-tools-spec.md`（B1 Tool 能力与最小解析基线）
  4. `aifa-phase-b2-agent-three-stage-spec.md`（B2 编排与 follow_up 语义）
- **对应分期**：实现计划 **B3** — **报告/截图 URL 解析与归一化**：将 `case_context` 中的 URL 字段转化为稳定、可拉取、可审计的候选列表，作为 B1 Tool 的上游输入。
- **状态**：Draft
- **日期**：2026-04-22

---

## 0. 文档目的

本文档回答：**B3 合并时 URL 相关能力必须达到什么“稳定可用”标准**，包括字段优先级、索引页链接解析、相对路径归一化、去重排序、白名单过滤、错误语义与验收标准。

**B3 不包含**（由其他分期负责）：

| 分期 | 内容 |
|------|------|
| **B1** | 报告 HTML 与图片二进制拉取的原子 Tool 实现（`fetch_report_html` / `fetch_screenshot_b64`） |
| **B2** | Plan -> Act -> Synthesize 编排与 session follow_up 主循环 |
| **B4** | 成功 batch URL 替换、多图对比业务规则 |
| **B5** | CodeHub 证据能力 |

---

## 1. 职责边界

### 1.1 必须满足

- **输入仅来自契约字段**：`reports_url`、`screenshot_index_url`、`screenshot_urls[]`（及后续 success 侧同构字段），不读取数据库、不推测外部隐式配置。
- **统一 URL 解析层**：新增（或固化）URL 归一化函数层，输出 `normalized_report_url` 与 `normalized_screenshot_urls[]`（字段名可调整，但语义必须稳定）。
- **明确优先级**：
  1. 若 `screenshot_urls[]` 非空，优先视为已解析直链集合；
  2. 否则使用 `screenshot_index_url` 进入索引页解析；
  3. 两者都缺失则返回结构化缺失信息，由上层填充 `data_gaps`。
- **索引页解析结果可控**：支持相对路径转绝对 URL、过滤非图片链接、去重、上限裁剪、稳定排序。
- **全部 async + 可测试**：URL 解析流程可通过 fixture 做自动化回归，不依赖线上真实地址。
- **错误可降级**：某一路 URL 解析失败不应导致整单未处理 500；应返回结构化错误并允许其他证据继续。

### 1.2 明确禁止

- **禁止**在 B3 引入“按日志 HTML URL 抓取”能力（契约仍不传 `log_url`）。
- **禁止**无白名单约束地接受任意 host 并发起请求。
- **禁止**将完整敏感 query 参数写入日志。
- **禁止**在 URL 解析层耦合业务判责逻辑（如 flaky/spec_change 判定）；该类规则属于 B4。

### 1.3 可选（B3 允许分步）

- 初版可先实现“常见索引页结构”选择器，不要求一次覆盖所有历史 DOM 变体，但必须有失败可解释输出。
- 可先对截图 URL 应用归一化；报告 URL 的强化校验（如 content-type 预检）可在同阶段后续小迭代补齐。

---

## 2. 输入字段与解析优先级

| 字段 | 含义 | B3 行为 |
|------|------|---------|
| `reports_url` | 失败用例报告页 URL | 做合法性校验与归一化，输出单一可拉取 URL |
| `screenshot_urls[]` | 预填截图直链列表 | 逐条归一化 + 去重 + 白名单过滤，产出候选列表 |
| `screenshot_index_url` | 截图目录页/索引页 URL | 当直链列表为空时，解析 HTML 提取图片链接 |

**优先级规则（必须一致）**：

1. 先消费 `screenshot_urls[]`（若非空）。
2. 若为空且有 `screenshot_index_url`，进入索引页提链。
3. 两者都不可用时返回空列表与 `missing_screenshot_urls` 类错误标签。

---

## 3. URL 归一化规则

## 3.1 基础校验

- 仅允许 `http` / `https` scheme。
- URL 长度有上限（默认值可配置，例如 2048）。
- 非法 URL（无主机、非法字符、空白）直接结构化拒绝。

## 3.2 相对路径转绝对路径

针对索引页提取出的链接，按以下顺序归一化：

1. 绝对 URL（`http(s)://...`）直接保留；
2. 协议相对 URL（`//host/path`）继承索引页 scheme；
3. 根相对路径（`/a/b.png`）拼接索引页 `scheme://host`；
4. 相对路径（`../img/x.png`、`./x.png`）使用标准 URL join 归一化。

## 3.3 过滤与去重

- 只保留图片候选（后缀匹配或后续 HEAD/GET content-type 校验，策略固定一种即可）。
- 统一去掉片段（`#...`）后去重，保持首次出现顺序。
- 白名单过滤应在最终请求前再次执行（双保险）。

## 3.4 截断策略

- 候选链接数量必须受 `max_screenshot_candidates` 限制。
- 超限时使用固定策略（建议“前 N-1 + 最后 1”），并在返回元信息中标记 `truncated=true`。

---

## 4. 解析产物契约（B3 最小）

URL 解析层至少输出以下结构（命名可调整）：

- `report_url: Optional[str]`
- `screenshot_urls: list[str]`
- `url_resolution_meta: { source, input_count, output_count, truncated, warnings[] }`
- `errors: list[{ code, message, field }]`

其中：

- `source` 取值建议：`prefilled_urls` / `index_page` / `none`
- `warnings[]` 用于非致命问题（例如“3 条 URL 非白名单已跳过”）
- `errors[]` 用于致命缺失或非法输入（例如 `invalid_reports_url`）

---

## 5. 安全与可观测性

### 5.1 安全要求

- URL 请求前必须进行 host allowlist 校验。
- 若允许重定向，必须限制次数，并对跳转目标再次做 allowlist 校验。
- 禁止访问本地环回、链路本地与保留网段（按运行环境策略实现）。

### 5.2 日志要求

- 记录摘要字段：`request_id`、`session_id`、`resolver_stage`、`input_count`、`output_count`、`elapsed_ms`。
- URL 仅记录 `host + path` 或脱敏后形式，不记录完整敏感 query。
- 解析失败需有可检索错误码，便于定位 fixture 漏覆盖与线上 DOM 变更。

---

## 6. 验收标准（B3 DoD）

以下全部满足，视为 **B3 完成**：

1. 当 `screenshot_urls[]` 非空时，系统可稳定输出去重、过滤后的截图 URL 列表，并跳过索引页解析。
2. 当仅有 `screenshot_index_url` 时，系统可从 fixture 索引页中提取图片 URL，并正确处理绝对/相对路径。
3. URL 归一化具备白名单与合法性校验；非法 URL 不触发未处理异常。
4. 候选列表超限时，裁剪策略稳定且可被单测断言。
5. 解析结果包含来源标记与 warning/error 元信息，供 B2 `data_gaps` 与 `stage_timeline` 使用。
6. 自动化测试至少覆盖：预填直链、索引页相对路径、非图片链接过滤、重复链接去重、白名单拒绝、超限截断。

---

## 7. 推荐测试清单

| 用例 | 输入场景 | 期望 |
|------|----------|------|
| 预填直链优先 | `screenshot_urls` 有值，`screenshot_index_url` 也存在 | 使用直链列表，不触发索引页解析 |
| 索引页相对路径 | HTML 含 `../`, `./`, `/` 三类链接 | 全部归一化为绝对 URL |
| 非图片链接混入 | 索引页包含 `.html`、`.js`、空链接 | 非图片被过滤，流程不崩溃 |
| 重复链接 | 同一图片多次出现（含 hash 差异） | 去重后数量正确 |
| 白名单拒绝 | 链接 host 不在 allowlist | 结构化错误/警告，且不发起实际拉取 |
| 超限裁剪 | 解析得到数量 > `max_screenshot_candidates` | 按固定策略裁剪并标记 `truncated` |
| 报告 URL 非法 | `reports_url` 格式错误 | 返回 `invalid_reports_url` 类错误 |

---

## 8. 与相邻分期衔接

- **对 B1**：B3 向 B1 Tool 提供“更干净”的 URL 输入，减少 Tool 内分支复杂度。
- **对 B2**：B2 无需感知解析细节，仅消费 `url_resolution_meta` 与结构化错误。
- **对 B4**：B4 在 B3 归一化能力之上实现成功侧 URL 替换与多图对比规则。

---

## 9. 维护约定

- 若架构中 URL 字段命名或安全约束调整：先更新架构，再同步本文件与实现。
- 每次新增索引页解析规则，必须同步补 fixture 与回归测试，避免线上静默退化。

### 修订记录

| 日期 | 变更 |
|------|------|
| 2026-04-22 | 初稿：B3 URL 解析与归一化边界、规则、DoD 与测试清单 |
