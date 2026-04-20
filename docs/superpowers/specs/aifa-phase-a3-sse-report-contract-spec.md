# AIFA Phase A3 — SSE 进度与报告契约阶段规格说明

- **文档类型**：阶段规格（Phase Spec，仅描述 **A3** 交付范围）
- **关联文档**（单一事实来源优先级）：
  1. `2026-04-08-ai-failure-analysis-architecture.md`（§4.2 SSE 事件、§4.3 report 契约；冲突时以架构为准）
  2. `2026-04-14-ai-failure-analysis-implementation-plan.md`（分期 **A3** 与依赖关系）
  3. `aifa-phase-a1-service-spec.md`（A1 已交付最小 SSE/最小 report；A3 在其基础上收紧）
  4. `dt-report-phase-a2-ai-context-builder-spec.md`（A2 请求 payload 来源与字段可空策略）
- **对应分期**：实现计划 **A3** — **SSE 进度 + 报告契约**：在不改变传输协议（仍为 `text/event-stream`）前提下，补齐并收紧 `progress` 事件语义与 `report` 字段契约。
- **状态**：Draft
- **日期**：2026-04-20

---

## 0. 文档目的

本文档回答：**A3 合并时必须具备哪些事件行为、字段约束、错误语义与验收标准**；不重复架构全文，只固化 **A3 范围内的「必须 / 可选 / 禁止」**。

**A3 不包含**（由其他分期负责）：

| 分期 | 内容 |
|------|------|
| **A1** | 服务骨架、`/v1/analyze` 入口、内部 token、最小 SSE |
| **A2** | dt-report 侧 `ai_context_builder` 拼装真实请求 payload |
| **A4** | 接受/拒绝写库（`pipeline_failure_reason`、`analyzed`） |
| **A5** | 按 `history_id` 限流与风控策略 |
| **Phase B** | Mongo/截图索引解析/CodeHub Tool、多阶段 Agent 质量优化 |

---

## 1. 职责边界

### 1.1 必须满足

- **传输层不变**：`POST /v1/analyze` 继续返回 **SSE**（`text/event-stream`），A3 不得回退为整包 JSON 一次性返回。
- **事件语义收紧**：`event: progress` 的 `stage` 与 `message` 必须可稳定被前端消费；不得再使用无语义、不可枚举或随机化阶段名。
- **报告契约收紧**：`event: report` 的 `data` 必须符合架构 §4.3 的对象形状，至少满足本文件 §3 的必填集与类型约束。
- **错误路径明确**：可恢复/不可恢复异常应通过 `event: error` 或 `report.status=partial|error` 表达，行为固定并可测试。
- **兼容 A2 缺省字段**：当请求体中某些上下文字段为空或缺省时，A3 必须按降级规则输出 `data_gaps`，而非抛未捕获异常。

### 1.2 明确禁止

- **禁止**新增或要求 dt-report 改协议（如改成 WebSocket、轮询、HTTP JSON 整包）。
- **禁止**输出与架构冲突的 `failure_category`（例如新增未定义枚举）或字段命名漂移。
- **禁止**在无成功侧截图对比证据时强判「规格变更，用例需适配」或「用例不稳定，需加固」（见 §4 硬规则）。
- **禁止**在 SSE 过程中输出不可解析 JSON（包括单引号 JSON、尾逗号、截断对象）。

---

## 2. SSE 事件契约（A3）

### 2.1 事件类型与顺序

A3 至少支持下列事件类型：

| `event` | 说明 | A3 要求 |
|---------|------|---------|
| `progress` | 阶段进度事件 | 至少 2 条；建议覆盖「开始分析」与「合成结论前」关键节点 |
| `report` | 最终报告事件 | 成功路径必须发送且仅发送 1 条 |
| `error` | 失败事件 | 不可恢复错误可直接发送并结束流 |

**顺序约束（规范）**：

1. 正常路径：`progress*` → `report`（结束）。
2. 失败路径：`progress*` → `error`（结束），或直接 `error`（结束）。
3. 同一请求内，`report` 与 `error` **二选一终态**，不得同时作为最终事件重复发送。

### 2.2 `progress.data` 结构

`progress` 的 `data` 必须是 JSON 对象：

```json
{
  "stage": "plan | log_analysis | screenshot_analysis | code_blame | synthesis | finalize",
  "message": "中文进度文案"
}
```

- `stage`：字符串枚举，允许实现阶段缺省部分值，但必须来自**固定集合**。
- `message`：用户可读中文文案，禁止空字符串。
- 可选扩展字段（不影响兼容）：`elapsed_ms`、`percent`、`detail`。

---

## 3. `report` 契约（A3 最小终态）

`event: report` 的 `data` 为完整 JSON 对象，至少包含以下结构：

| 字段 | 类型 | A3 要求 |
|------|------|---------|
| `session_id` | string | 必填；与请求同一会话一致 |
| `status` | `"ok" \| "partial" \| "error"` | 必填；语义稳定 |
| `report` | object | 必填；见下表 |
| `trace` | object | 必填；至少有 `skills_invoked`、`llm_input_tokens`、`llm_output_tokens`、`elapsed_ms` |

`report` 子对象最小必填：

| 字段 | 类型 | A3 要求 |
|------|------|---------|
| `failure_category` | enum | 固定为：`bug`、`环境问题`、`规格变更，用例需适配`、`用例不稳定，需加固`、`unknown` |
| `verdict` | enum/string | `product_bug \| env_issue \| test_flaky \| infra \| unknown`（或与产品约定等价枚举） |
| `confidence` | number | 0～1 浮点，超界需裁剪或降级 |
| `summary` | string | 一句话结论，非空 |
| `detailed_reason` | string | 详细原因，非空 |
| `stage_timeline` | array | 元素含 `stage`、`message`、`elapsed_ms`；允许空数组但字段必须存在 |
| `evidence` | array | 元素至少含 `id`、`type`、`source`、`snippet`、`reference` |
| `data_gaps` | array[string] | 缺失证据与降级原因；无缺失时可空数组 |

可选字段（建议有）：

- `rationale_summary`
- `suspect_patches`
- `suggested_next_steps`

其中 `failure_category = unknown` 时，表示当前证据不足以形成可直接应用的失败归因；下游（如 A4 接受写库）应提示人工复核，避免直接应用该结论。

---

## 4. 业务硬规则（A3 必须固化）

### 4.1 `spec_change` / `flaky` 证据约束

当 `success_screenshot_urls` 为空、不可访问，或对比证据不足时：

- **不得**将 `failure_category` 强判为「规格变更，用例需适配」或「用例不稳定，需加固」；
- 应降级为 `unknown`（或日志/历史支持的次优结论）；
- 必须在 `data_gaps` 写明「成功侧截图证据不足」等原因。

### 4.2 降级一致性

- 若核心字段可生成但证据不完整：`status=partial`，同时返回可展示 `report`。
- 若完全不可生成报告：发送 `event:error` 并结束（或 `status=error` 的 `report`，二选一并固定）。
- 以上策略在实现、测试、README 中保持一致，避免前后端对终态判断分歧。

---

## 5. 验收标准（A3 DoD）

以下全部满足，视为 **A3 完成**：

1. **协议一致性**：`POST /v1/analyze` 仍为 SSE，Content-Type 正确，前端可流式消费。
2. **进度可观测**：在正常分析路径下，至少出现 2 条 `progress`，`stage` 与 `message` 可稳定解析。
3. **报告可校验**：最终 `report` 事件可通过 Pydantic/JSON Schema 校验（按 §3 必填集）。
4. **硬规则生效**：构造无成功截图样例时，不会输出「规格变更，用例需适配」或「用例不稳定，需加固」，且 `data_gaps` 有解释。
5. **异常可消费**：上游 LLM 失败、外部依赖失败时，客户端可收到可解析 `error` 事件或 `status=error|partial` 的 `report`。
6. **回归通过**：A1/A2 相关已有测试不被破坏。

---

## 6. 推荐测试清单

| 用例 | 输入场景 | 期望 |
|------|----------|------|
| 正常成功流 | 请求体完整、Mock LLM 正常 | `progress>=2` 且最终 `report` 满足 §3 |
| 缺少成功截图 | `success_screenshot_urls=[]` | `failure_category` 不能是「规格变更，用例需适配」或「用例不稳定，需加固」，`data_gaps` 说明原因 |
| 依赖失败 | 模拟 LLM 401/超时 | 收到 `error` 或 `status=error|partial`，客户端可解析 |
| 字段缺省 | A2 只传最小上下文 | 不崩溃，`report` 仍可输出，缺口进入 `data_gaps` |
| 事件顺序 | 正常/异常路径 | `report` 与 `error` 不同时作为终态重复发送 |

---

## 7. 与相邻分期衔接

- **对 A2**：A2 负责「输入真实化」；A3 负责「输出契约化」。A3 不新增 MySQL 读取职责。
- **对 A4**：A4 的接受/拒绝写库依赖 A3 的 `report.summary`、`detailed_reason`、`failure_category` 稳定输出。
- **对 B 阶段**：B1/B3/B5 提升证据质量；A3 先固定输出结构，后续仅增强字段内容质量。

---

## 8. 维护约定

- 若架构 §4.2 / §4.3 更新：先改架构 SSOT，再同步本文件与实现。
- 若 `report` 字段新增且影响前端解析：必须在本文件追加兼容策略（向后兼容/灰度字段）。

### 修订记录

| 日期 | 变更 |
|------|------|
| 2026-04-20 | 初稿：A3 范围、SSE 事件顺序、report 最小终态字段、硬规则与 DoD |
