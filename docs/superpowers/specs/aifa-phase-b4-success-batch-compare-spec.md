# AIFA Phase B4 — 成功批次 URL 替换与多图对比规格说明

- **文档类型**：阶段规格（Phase Spec，仅描述 **B4** 交付范围）
- **关联文档**（单一事实来源优先级）：
  1. `2026-04-08-ai-failure-analysis-architecture.md`（§1.4、§4.3、§8.3 对比与降级规则；冲突时以架构为准）
  2. `2026-04-14-ai-failure-analysis-implementation-plan.md`（分期 **B4** 与依赖关系）
  3. `aifa-phase-b3-url-resolution-spec.md`（B3 URL 归一化与解析产物）
  4. `aifa-phase-b2-agent-three-stage-spec.md`（B2 三阶段编排与 `data_gaps` 语义）
  5. `dt-report-phase-a2-ai-context-builder-spec.md`（`last_success_batch` 与成功侧 URL 字段来源）
- **对应分期**：实现计划 **B4** — **成功批次 + URL 替换 + 多图对比**：在 B3 URL 能力基础上引入失败/成功截图集对比，并将结果纳入 `spec_change` / `flaky` 判定与降级。
- **状态**：Draft
- **日期**：2026-04-22

---

## 0. 文档目的

本文档回答：**B4 合并时“成功侧证据对比”必须具备哪些输入约束、URL 替换策略、对比产物、归类硬规则与验收标准**。  
核心目标是把「是否可以判定 `spec_change` / `flaky`」从“模型自由发挥”收敛为“有证据可追溯的工程规则”。

**B4 不包含**（由其他分期负责）：

| 分期 | 内容 |
|------|------|
| **B1** | 报告/截图拉取原子 Tool（fetch）实现 |
| **B2** | 三阶段主循环、session 与 follow_up 基础语义 |
| **B3** | URL 基础解析与归一化（失败侧） |
| **B5** | CodeHub commits/diff 证据增强 |

---

## 1. 职责边界

### 1.1 必须满足

- **成功侧证据输入**：消费 `last_success_batch`、`success_screenshot_index_url`、`success_screenshot_urls[]`（以及需要时的成功侧报告 URL 字段），不直接查库。
- **URL 替换路径可落地**：当上游未提供成功侧直链列表时，支持按约定对失败侧 URL 做“仅 batch 段替换”得到成功侧候选 URL（替换规则见 §3）。
- **双集合对比**：`screenshot_skill`（或等价模块）能够基于“失败截图集 vs 成功截图集”生成结构化对比摘要。
- **硬规则落地**：当成功侧截图证据缺失或对比证据不足时，系统**禁止强判** `spec_change` / `flaky`，必须降级并写 `data_gaps`。
- **可解释输出**：对比结果至少包含匹配数量、差异摘要、证据不足原因，供 Synthesize 阶段消费。
- **部分失败可降级**：成功侧某些图片拉取失败不应导致整单 500；允许 `partial` 返回。

### 1.2 明确禁止

- **禁止**在无成功侧可用截图证据时输出 `spec_change` / `flaky` 最终分类。
- **禁止**在 URL 替换逻辑中引入宽松“猜测替换”（例如多段模糊替换导致跨环境误命中）。
- **禁止**将原始大图 base64、完整 HTML 写入日志。
- **禁止**把“是否为 bug/env”完全依赖视觉对比；B4 仅增强 `spec_change/flaky` 判定可靠性。

### 1.3 可选（B4 允许分步）

- 初版可采用“LLM 视觉对比 + 规则后处理”的混合策略；更复杂图像相似度算法可后续迭代。
- 失败/成功多图匹配可先按索引顺序或简单规则配对，后续再引入更稳健匹配策略。

---

## 2. 输入字段与优先级

| 字段 | 来源 | B4 用途 |
|------|------|---------|
| `batch` | 失败记录上下文 | URL 替换中的“失败批次”基准 |
| `last_success_batch` | dt-report 计算 | URL 替换目标批次 |
| `screenshot_urls[]` / `screenshot_index_url` | 失败侧证据入口 | 构建失败截图集合 |
| `success_screenshot_urls[]` / `success_screenshot_index_url` | 成功侧证据入口 | 构建成功截图集合 |

**成功侧获取优先级（必须固定）**：

1. 若 `success_screenshot_urls[]` 非空，直接使用；
2. 否则使用 `success_screenshot_index_url` 解析；
3. 若仍缺失，且 `last_success_batch` 与失败侧 URL 可用，尝试 batch 替换生成成功侧入口；
4. 仍不可得则标记 `success_evidence_missing` 并触发强判降级。

---

## 3. 成功批次 URL 替换规则（B4 核心）

## 3.1 触发条件

- 上游未给出可用 `success_screenshot_urls[]` / `success_screenshot_index_url`；
- 同时具备 `last_success_batch` 与失败侧截图入口 URL。

## 3.2 替换约束

- 仅允许替换 URL 中明确标识为“批次段”的子串（例如路径中的 `batch_xxx` 段）。
- 替换前后必须保持：
  - scheme / host / 端口不变；
  - 路径结构不变（仅批次段变化）；
  - query 参数仅在必要时保留，不新增敏感参数。
- 替换后 URL 仍需通过 B3 白名单与合法性校验。

## 3.3 失败处理

- 无法定位批次段：记录 `batch_replace_not_applicable`；
- 替换后 URL 非法或不可访问：记录 `batch_replace_invalid_target`；
- 以上均不应抛未处理异常，统一进入 `data_gaps` 与 `partial` 语义。

---

## 4. 多图对比产物契约（B4 最小）

对比阶段至少输出（字段名可调整）：

- `compare_summary: str`（一段简要对比结论）
- `compare_notes: list[str]`（差异点列表）
- `failed_image_count: int`
- `success_image_count: int`
- `paired_count: int`
- `unpaired_failed_count: int`
- `unpaired_success_count: int`
- `evidence_sufficiency: "enough" | "insufficient" | "missing"`

其中：

- `evidence_sufficiency` 由规则层判定，不完全依赖 LLM 文本。
- `insufficient/missing` 必须附带可读原因（例如“成功侧仅 1 张且不可配对”）。

---

## 5. 分类硬规则与降级

与架构 §4.3/§8.3 对齐，B4 必须实现以下后处理约束：

1. **无成功侧证据**（`evidence_sufficiency=missing`）：
   - 最终 `failure_category` 不得为 `spec_change` / `flaky`；
   - 若模型输出上述分类，强制降级为 `unknown`（或实现约定的次优类别）；
   - `data_gaps` 追加“缺少成功侧截图对比证据”说明。
2. **证据不足**（`insufficient`）：
   - 同样禁止强判 `spec_change` / `flaky`；
   - 可保留 `bug` / `env` / `unknown` 候选。
3. **证据充分**（`enough`）：
   - 才允许 `spec_change` / `flaky` 进入最终候选；
   - 仍需在 `evidence[]` 中保留可追溯对比摘要。

---

## 6. 与 B2/B3 的集成要求

- **对 B3**：复用 B3 URL 解析与校验能力；B4 不重复实现 URL 基础逻辑。
- **对 B2 Act**：在 `screenshot_skill` 增加“成功侧集合构建 + 对比摘要”子阶段。
- **对 B2 Synthesize**：输入新增对比结构化摘要，而不是原始图片内容。
- **对 follow_up**：默认复用已缓存的对比摘要；仅在用户明确要求重比对时才重拉取（可后续增强）。

---

## 7. 安全与可观测性

### 7.1 安全要求

- 成功侧替换生成的 URL 必须再次执行 allowlist 校验。
- 对比流程中的图片拉取沿用大小上限与超时，不得无限扩张。

### 7.2 日志要求

- 记录摘要：`session_id`、`failed_image_count`、`success_image_count`、`paired_count`、`evidence_sufficiency`、`elapsed_ms`。
- 记录 URL 时仅保留脱敏信息（host + 截断 path）。
- 不记录原始图像 base64、不记录完整敏感 query。

---

## 8. 验收标准（B4 DoD）

以下全部满足，视为 **B4 完成**：

1. 成功侧 URL 获取遵循优先级：直链 > 索引页 > batch 替换。
2. batch 替换逻辑具备明确约束与错误码，异常场景可测试。
3. `screenshot_skill` 可输出失败/成功双集合的结构化对比摘要。
4. 当成功侧证据 `missing/insufficient` 时，`spec_change` / `flaky` 被规则层阻断。
5. 成功侧证据充分时，允许输出 `spec_change` / `flaky`，且 evidence 可追溯。
6. 任意单路拉取或对比失败不会导致整单未处理 500，系统可返回 `partial`。
7. 自动化测试覆盖至少：优先级分支、batch 替换成功/失败、证据不足降级、证据充分放行。

---

## 9. 推荐测试清单

| 用例 | 输入场景 | 期望 |
|------|----------|------|
| 成功直链优先 | `success_screenshot_urls[]` 非空 | 不执行 batch 替换，直接对比 |
| 索引页回退 | 无成功直链，有 `success_screenshot_index_url` | 能解析成功侧图片并参与对比 |
| batch 替换成功 | 无成功侧字段，`last_success_batch` 可替换 | 生成可用成功侧 URL 并完成对比 |
| batch 替换不可用 | URL 无批次段或替换后非法 | 写 `data_gaps`，不崩溃 |
| 证据缺失降级 | 成功侧完全不可用 | 禁止 `spec_change/flaky`，分类降级 |
| 证据不足降级 | 成功侧仅少量且无法配对 | 禁止 `spec_change/flaky`，返回 `partial` |
| 证据充分放行 | 双侧多图可配对且差异明确 | 允许 `spec_change` 或 `flaky` 候选 |

---

## 10. 与相邻分期衔接

- **对 B3**：B3 负责“把 URL 变干净”；B4 负责“用成功侧 URL 生成可判定对比证据”。
- **对 B5**：B5 的代码变更证据可与 B4 对比证据互补，但不替代 B4 的硬规则门槛。
- **对 C2**：追问时可直接复用 B4 对比摘要，减少重复拉图成本。

---

## 11. 维护约定

- 若架构更新 `spec_change/flaky` 判定门槛，先改架构，再同步本文件与实现。
- 若线上截图索引结构变化导致对比质量下降，先补 fixture 回归，再调整解析与配对策略。

### 修订记录

| 日期 | 变更 |
|------|------|
| 2026-04-22 | 初稿：B4 成功批次 URL 替换、多图对比、分类硬规则与 DoD |
