# AIFA Phase C4 — 观测与成本（trace / metrics / token 熔断）规格说明

- **文档类型**：阶段规格（Phase Spec，仅描述 **C4** 交付范围）
- **关联文档**（单一事实来源优先级）：
  1. `2026-04-08-ai-failure-analysis-architecture.md`（§10 错误分级、§11 健康检查与观测、§12 安全与成本边界；冲突时以架构为准）
  2. `2026-04-08-ai-failure-analysis-tech-selection.md`（JSONL trace、`/metrics` JSON、熔断与超时建议）
  3. `2026-04-14-ai-failure-analysis-implementation-plan.md`（分期 **C4** 与依赖关系）
  4. `aifa-phase-a3-sse-report-contract-spec.md`（`status=ok|partial|error` 与 SSE 终态语义）
  5. `aifa-phase-a5-rate-limit-spec.md`（dt-report 侧限流边界，C4 仅观测不改 A5 规则）
- **对应分期**：实现计划 **C4** — **观测与成本**：建立可追踪链路、可聚合指标、单请求 token 成本护栏（熔断），并固化错误分级与降级可解释性。
- **状态**：Draft
- **日期**：2026-04-23

---

## 0. 文档目的

本文档回答：**C4 合并时系统必须具备哪些观测字段、指标口径、成本计算与熔断行为，以及怎样验收**。  
目标是让 AI 分析从“能跑”升级到“可运维、可控成本、可审计”。

**C4 不包含**（由其他分期负责）：

| 分期 | 内容 |
|------|------|
| **A5** | 限流策略本身（单 `history_id` 10 次/分钟） |
| **C1/C2/C3** | 前端 Tab、追问体验、入库 owner 规则 |
| **D1** | 批量队列任务状态机与队列持久化 |
| **平台化告警系统接入** | Prometheus/ELK/ClickHouse 正式接入（C4 先提供可接入输出） |

---

## 1. 职责边界

### 1.1 必须满足

- **trace 完整**：每次分析请求必须有一条可检索 trace，至少覆盖请求上下文、阶段耗时、skill/tool 调用摘要、token 消耗、最终状态。
- **metrics 可读**：提供统一指标端点（初期 JSON），支持请求量、成功率、partial/error 比例、耗时、token 与成本聚合。
- **token 熔断生效**：单请求 token 累计达到上限时，必须触发熔断，终态为 `partial`（配置类致命错误除外）。
- **错误分级统一**：`ok/partial/error` 与 SSE/前端语义一致，日志、trace、指标口径一致。
- **脱敏合规**：日志与 trace 禁止泄露 token、完整敏感 URL query、原始大段证据正文。

### 1.2 明确禁止

- **禁止**只打“文本日志”而无结构化 trace。
- **禁止**在 token 超限后继续深度调用 LLM（导致成本失控）。
- **禁止**把暂时性外部依赖故障全部升级成 HTTP 500（应优先 partial）。
- **禁止**让 metrics 口径与 trace 字段定义不一致。

### 1.3 可选（C4 允许分步）

- 初版可仅输出 `/metrics` JSON，不强制 Prometheus 文本格式。
- 初版成本可按“token * 单价”估算，不要求精确对账到供应商账单。

---

## 2. Trace 规格（必须）

## 2.1 记录范围

每次 `/ai/analyze` 请求生成一条 trace 记录（建议 JSONL 一行一条），覆盖：

- 请求标识：`request_id`、`session_id`、`history_id`
- 时序：`started_at`、`finished_at`、`elapsed_ms`
- 结果：`status`（`ok|partial|error`）、`error_code?`、`error_message?`
- 调用摘要：`skills_invoked[]`、`tool_calls[]`（仅摘要）
- token：`llm_input_tokens`、`llm_output_tokens`、`total_tokens`
- 成本：`estimated_cost`（含计价参数版本）
- 降级：`data_gaps[]`、`degrade_reasons[]`

## 2.2 最小结构（示意）

```json
{
  "request_id": "uuid",
  "session_id": "uuid",
  "history_id": 123456,
  "status": "ok",
  "elapsed_ms": 18740,
  "skills_invoked": ["report_analysis", "screenshot", "synthesis"],
  "tool_calls": [{"name": "fetch_report_html", "ok": true, "elapsed_ms": 230}],
  "llm_input_tokens": 12034,
  "llm_output_tokens": 1820,
  "total_tokens": 13854,
  "estimated_cost": 0.31,
  "data_gaps": [],
  "degrade_reasons": []
}
```

## 2.3 脱敏规则（必须）

- 禁止落：API key、service token、完整 Authorization Header。
- 禁止落：完整 raw diff、完整 HTML、完整 base64 图片。
- URL 仅保留 `host + path` 或经过脱敏处理的片段。

---

## 3. Metrics 规格（必须）

## 3.1 指标端点

- 端点：`GET /metrics`
- 初期返回 JSON（后续可加 `/metrics/prom` 适配层）
- 指标按进程内聚合，重启清零可接受（需在文档注明）

## 3.2 最小指标集

| 指标名 | 类型 | 说明 |
|------|------|------|
| `requests_total` | counter | 总请求数 |
| `requests_ok` | counter | 成功请求数 |
| `requests_partial` | counter | 降级完成请求数 |
| `requests_error` | counter | 失败请求数 |
| `request_latency_p50_ms` | gauge | 请求耗时 P50 |
| `request_latency_p95_ms` | gauge | 请求耗时 P95 |
| `tokens_input_total` | counter | 输入 token 总量 |
| `tokens_output_total` | counter | 输出 token 总量 |
| `tokens_total` | counter | 总 token |
| `estimated_cost_total` | counter | 估算总成本 |
| `circuit_breaker_triggered_total` | counter | token 熔断触发次数 |
| `external_dependency_error_total` | counter | 外部依赖错误次数（可按来源分桶） |

## 3.3 口径一致性（必须）

- `requests_ok + requests_partial + requests_error == requests_total`
- token 与成本统计口径必须与 trace 字段一致
- 熔断触发必须同时体现在：
  - trace：`degrade_reasons` 包含 token 超限
  - metrics：`circuit_breaker_triggered_total` 增加

---

## 4. Token 成本与熔断规则（必须）

## 4.1 配置项

| 配置 | 说明 |
|------|------|
| `AIFA_MAX_TOKENS_PER_REQUEST` | 单请求 token 硬上限 |
| `AIFA_PRICE_PER_1K_INPUT` | 输入 token 单价（估算） |
| `AIFA_PRICE_PER_1K_OUTPUT` | 输出 token 单价（估算） |
| `AIFA_MAX_CONCURRENT_ANALYSES` | 并发上限（与 C4 指标联动观测） |

## 4.2 熔断触发条件

- 当 `累计输入+输出 token >= AIFA_MAX_TOKENS_PER_REQUEST` 时触发
- 触发后行为：
  1. 停止后续高成本 LLM 调用；
  2. 保留已获得证据并合成最小可解释结果；
  3. 返回 `status=partial`；
  4. `data_gaps` 写明“因 token 上限触发熔断”。

## 4.3 成本计算（估算）

- `estimated_cost = input_tokens / 1000 * input_price + output_tokens / 1000 * output_price`
- 每请求写入 trace；metrics 聚合写入 `estimated_cost_total`

---

## 5. 错误分级与降级语义（C4 固化）

| 场景 | 等级 | 期望行为 |
|------|------|----------|
| 外部数据源超时/5xx（非配置） | partial | 返回可用报告 + `data_gaps` |
| 单 skill/tool 失败但主流程可继续 | partial | 不中断整单 |
| token 触顶熔断 | partial | 立即停止扩展调用并返回可解释降级 |
| 配置错误（如 token 无效/缺失） | error/fatal | fail-loud，返回 500 |
| 参数不合法 | user error | 返回 400，中文可读 |

**核心原则**：有可用结论就优先 `partial`，无可用结果再 `error`。

---

## 6. 验收标准（C4 DoD）

以下全部满足，视为 **C4 完成**：

1. 每次分析请求都能产出结构化 trace，包含最小必填字段。
2. `/metrics` 可稳定返回，且关键计数关系成立（见 §3.3）。
3. 单请求 token 超限会触发熔断并返回 `partial`，不会继续高成本调用。
4. trace、metrics、前端终态的 `ok/partial/error` 语义一致。
5. 错误分级可复现：外部依赖故障走 partial，配置类故障 fail-loud。
6. 日志与 trace 通过脱敏检查，不含明文 token 与大段敏感正文。
7. 有每日成本汇总输出（日志或报告），至少含请求数、总成本、p95。

---

## 7. 推荐测试清单

| 用例 | 输入场景 | 期望 |
|------|----------|------|
| 正常请求 | 依赖全部可用 | `status=ok`，trace+metrics 计数增长 |
| 单依赖超时 | 报告或截图源超时 | `status=partial`，`data_gaps` 可解释 |
| token 熔断 | 人工降低 `AIFA_MAX_TOKENS_PER_REQUEST` | 触发 partial，熔断计数+1 |
| 配置错误 | CodeHub token 无效 | fail-loud（500），error 计数增长 |
| 指标一致性 | 连续发送 N 次混合请求 | 三类状态计数求和等于总请求 |
| 脱敏检查 | 注入敏感 URL/token 场景 | trace/log 不出现明文敏感信息 |
| 成本聚合 | 多请求后读取 metrics | `estimated_cost_total` 与 trace 聚合同量级 |

---

## 8. 与相邻分期衔接

- **对 A5**：C4 观测 A5 限流命中，不改 A5 阈值语义。
- **对 C1/C2/C3**：前端展示可消费 `status` 与 trace 摘要，但 C4 不定义 UI 细节。
- **对 D1**：批量队列上线后复用同一 trace/metrics 口径，按 `task_id` 扩展维度。

---

## 9. 维护约定

- 新增/调整任何关键指标字段时，必须同步更新本文件与运维说明。
- 若错误分级规则调整（特别是 partial 与 fail-loud 边界），需同步更新架构与本文件。
- 未来接 Prometheus/ELK 时，应通过适配层扩展，尽量保持既有字段语义不破坏。

### 修订记录

| 日期 | 变更 |
|------|------|
| 2026-04-23 | 初稿：C4 范围、trace 结构、metrics 口径、token 熔断、DoD 与测试清单 |
