# dt-report Phase A2 — `ai_context_builder` 阶段规格说明

- **文档类型**：阶段规格（Phase Spec，仅描述 **A2** 交付范围）
- **关联文档**（单一事实来源优先级）：
  1. `2026-04-08-ai-failure-analysis-architecture.md`（§1.4、§3.3、§4.1 请求契约；冲突时以架构为准）
  2. `2026-04-14-ai-failure-analysis-implementation-plan.md`（分期 **A2** 与依赖关系）
  3. `aifa-phase-a1-service-spec.md`（AIFA 对请求 JSON 的校验形态；A2 产出须可被其消费）
- **对应分期**：实现计划 **A2** — **真实 payload**：在 **dt-report** 侧实现 **`ai_context_builder`**，根据 **`history_id`** 只读拼装发往 AIFA 的 **`POST /v1/analyze` 请求体**（与架构 **§4.1** 对齐）。
- **状态**：Draft
- **日期**：2026-04-18

---

## 0. 文档目的

本文档回答：**A2 合并时必须具备哪些行为、数据范围、配置与验收标准**；不重复架构全文，只固化 **A2 范围内的「必须 / 可选 / 禁止」**。

**A2 不包含**（由其他分期负责）：

| 分期 | 内容 |
|------|------|
| **A3** | AIFA 侧 SSE `progress` 丰富度、`report` 字段与架构 §4.3 的终态对齐 |
| **A4** | 用户「接受 / 拒绝」、写入 `pipeline_failure_reason`、`analyzed` 等 |
| **A5** | 按 `history_id` 限流（架构 §12.4） |
| **Phase B** | 报告/截图 Tool、多阶段 Agent、截图索引解析、CodeHub 等 |
| **Phase C1** | 前端 Drawer、AI 归因 Tab、懒加载（见架构 §9） |

**说明**：架构 §3.3 将 **`ai_proxy.py`**（JWT、转发 AIFA、SSE、审计等）与 **`ai_context_builder`** 并列列出；**实现计划将「限流 / 接受拒绝」记在 A4/A5**。本文档 **A2 仅覆盖 `ai_context_builder` 与由其组装的 payload**。与 **「最小 `POST /api/v1/ai/analyze` 代理」** 是否同批合入，由排期决定：代理 **不属于** A2 编号条目，但 **端到端联调** 常与之同批。

---

## 1. 职责边界

### 1.1 必须满足

- **输入**：至少支持按 **`history_id`**（`pipeline_history.id`）定位当前失败行。
- **输出**：一份 **JSON 对象**，语义对齐架构 **§4.1**，可被当前 **`ai-failure-analyzer`** 的 `POST /v1/analyze` 请求体验证逻辑接受（字段 **大部分可选**，未实现的键可 **缺省** 或 **`null`**，**不得**要求 AIFA 访问 MySQL 补数据，与架构 §4.1 末段一致）。
- **数据来源**：**仅 dt-report 已具备的数据库只读访问与配置**（如 `module_repo_mapping`）；**不做** LLM 调用、**不做** Prompt 拼装（架构 §3.3：纯数据读取）。
- **历史执行**：提供 **`recent_executions`**：与架构一致，按 **`(case_name, platform)`** 查询近 **N** 条执行摘要（默认 **N=20**，可配置；实现阶段固定常量即可）。
- **仓库提示**：提供 **`repo_hint`**：来自 **dt-report 维护** 的 **`main_module` → 仓库** 映射（**初期为 YAML 配置文件**，与架构 §4.1 一致；后续若升级为字典表，不在 A2 强制要求）。

### 1.2 明确禁止

- **禁止**在发往 AIFA 的 payload 中包含 **日志 HTML URL**（架构 **§1.4.1**、**§4.1**）。
  - 说明：MySQL `pipeline_history.log_url` 仅可在 **dt-report 内部**用于其他用途；**写入 AIFA 请求 JSON 的字段集合中不得出现** 与「整页日志 HTML」等价的对外传递（改版后 Phase B 以 `reports_url` 与 `screenshot_url` 为主要证据来源）。
- **禁止**在 `ai_context_builder` 内调用 AIFA 或任何 LLM。
- **禁止**违反项目数据库红线：对既有表的 **ALTER / DROP**、对 `pipeline_history` / `pipeline_overview` 的 **DELETE**、**ORM 自动建表** 等（见仓库 `.cursor/rules/project.mdc`）。

### 1.3 可选（A2 允许分步）

实现计划 **A2** 说明：**截图可先直链或空**。下列字段在架构 §4.1 与 §1.4.1 中有定义，**A2 第一期允许**：

- **`screenshot_index_url` / `screenshot_urls[]`**：若库中已有 **截图 URL**（如 `pipeline_history.screenshot_url` 或后续字段），可 **原样或规范化** 填入；若无或不可靠，**可省略或为空**。
- **`reports_url`**：若存在 `pipeline_history.reports_url`，可填入；否则可空。
- **`last_success_batch`、`success_screenshot_index_url`、`success_screenshot_urls[]`**：架构要求由 dt-report 计算 **最近一次成功批次** 并 **仅替换 batch 段** 生成成功侧 URL（§1.4.1）。**A2 允许**在首版 **暂不实现** 或 **部分实现**，但须在 **`data_gaps` 或文档验收**中可说明；**不得**伪造不存在的成功侧证据。

---

## 2. 与 `pipeline_history` 的字段映射（语义）

表结构以 **`database/*.sql` 与 `backend/models/pipeline_history.py`** 为准。架构 §4.1 使用 **`batch`** 等命名；当前表以 **`start_time`** 表示轮次（注释：**等同于 batch**）。**A2 在 `case_context` 中应同时满足产品语义**：

- 将 **`start_time`** 映射为契约中的 **`batch`**（或与架构示例一致的字段名），并在实现与测试中写清对应关系，避免 AIFA 分析维度不一致。

其他常见映射（示例，以实现阶段 ORM 字段为准）：

| 架构 `case_context` 语义 | 数据来源（示例） |
|--------------------------|------------------|
| `history_id` | 请求入参或 `pipeline_history.id` |
| `case_name`, `platform`, `case_result`, `code_branch` | 同行字段 |
| `main_module`, `module`, `subtask` | `main_module`, `module`, `subtask` |
| `pipeline_url`, `case_level` | `pipeline_url`, `case_level` |
| 截图 / 报告 URL | `screenshot_url`, `reports_url` 等（**不传 `log_url` 至 AIFA**） |

---

## 3. `recent_executions` 条目形状（建议）

每条至少包含架构 §4.1 示例中出现的维度，便于 AIFA 单轮或后续 **history_skill** 使用：

- `start_time`（轮次标识）
- `case_result`
- `code_branch`（若有）

**查询策略**：遵循项目 **Service 层约定**（默认 **禁止无必要的 JOIN**；优先单表条件查询 + 分页/限制条数），复用或抽取 **`history_service`** 中与「同 case、同 platform」相关的查询逻辑（架构 §3.3）。

---

## 4. `repo_hint`（YAML 配置）

### 4.1 最小结构（与架构 §4.1 示例对齐）

```yaml
# 示例结构；键名与映射规则以实现为准，须可映射到 §4.1 的 repo_hint
mappings:
  - main_module: "auth"
    repo_url: "https://codehub.internal/group/project"
    default_branch: "master"
    path_hints:
      - "src/auth/"
      - "tests/auth/"
```

### 4.2 行为

- 按当前失败行的 **`main_module`** 查找配置；**未命中**时：`repo_hint` 可为 **空对象** 或 **字段为 null**，**不得**因缺映射而抛未捕获异常导致分析入口 500（与「降级优先」精神一致；具体 HTTP 行为由 **调用方 / A4** 定义）。

### 4.3 实现约定（与代码同步）

- **Service**：`backend/services/ai_context_builder.py`，入口 **`build_analyze_payload(db, history_id)`**，返回 **`case_context` + `recent_executions` + `repo_hint`**（**不含** `session_id` / `mode`，由后续 `ai_proxy` 合并）。
- **环境变量**：**`AI_MODULE_REPO_MAPPING_PATH`** — 指向 UTF-8 YAML 文件的绝对或相对路径；**空** 表示不加载，`repo_hint` 为空对象。模板见仓库根目录 **`config/module_repo_mapping.yaml.example`**。
- **历史执行查询**：`backend/services/history_service.py` 中的 **`list_recent_executions_by_case_platform`**（单表、同 `case_name`+`platform`、默认最多 20 条）。

---

## 5. 体积与安全

- 对 **`case_context` 内字符串字段**、**`recent_executions` 列表长度与单条字段** 实施 **上限与截断**（与架构「Token 成本」及 A1「安全截断」方向一致；具体字节数可在实现中常量配置）。
- **不在日志中打印**完整 URL 或密钥；若需调试，使用 **脱敏** 或 **DEBUG 且受控**（见 `docs/06_logging_guide.md`）。

---

## 6. 错误与降级

| 场景 | 期望行为 |
|------|----------|
| `history_id` 不存在 | 由 **调用方**（如未来的 `ai_proxy`）返回 **404** 或业务错误码；builder 可抛 **明确异常** 或返回 **Result 类型**，由 API 层统一转换为中文错误信息 |
| `case_name` / `platform` 为空导致无法查历史 | `recent_executions` 可为 **空数组**；不阻塞 payload 生成（若业务要求必须拒绝，由评审决定） |
| 配置缺失 | `repo_hint` 降级为空；**不打 ERROR**（除非文件损坏且无法解析） |

---

## 7. 分层与代码位置（建议）

与仓库 **Model → Schema → Service → API** 契约一致（见 `.cursor/rules/project.mdc`）：

- **Service**：`backend/services/ai_context_builder.py`（或等价路径），**纯 async 函数**，例如 `async def build_analyze_payload(db: AsyncSession, history_id: int) -> dict`（返回体形状与架构 §4.1 一致；具体是否使用 Pydantic **内部** 模型由实现定）。
- **API**：**不属于 A2 必交付**；若仅有单元测试调用 Service，仍视为 A2 可合并。

---

## 8. 自动化测试（DoD）

以下满足可视为 **A2 完成**：

1. **单测或集成测试**：给定 **fixture / 测试库** 中的一条 `pipeline_history`，`build_analyze_payload` 产出的 dict **可被序列化为 JSON**，且：
   - **不包含** 键名或语义等价于「日志页 HTML URL」的对外字段（即不与架构 **禁止传日志 URL** 冲突）；
   - 包含 **`case_context`**，且其中 **`case_name`、`batch`（或映射自 `start_time`）、`platform`** 与源行一致；
   - **`recent_executions`** 为列表，条数 **≤ N**；
   - **`repo_hint`** 在配置存在时非空、配置不存在时可空。
2. **回归**：不破坏现有 **pipeline_history** 只读路径；**无** 违规 DDL/DML。

---

## 9. 与相邻切片的衔接

- **A1**：AIFA 已能校验并处理 §4.1 **子集**；A2 保证 dt-report **真实填数**。
- **（可选同批）`ai_proxy`**：接收前端 **`history_id`**，调用 `build_analyze_payload`，再 **httpx 转发** AIFA SSE；JWT、审计、超时见架构 §3.3、§12。
- **A5**：在 **代理层** 对 **`history_id`** 限流，**不在** `ai_context_builder` 内实现。

---

## 10. 维护约定

- 若架构 **§4.1** 字段变更，**先改架构 SSOT**，再同步本文档与实现。
- 本文档仅描述 **A2**；**五 Skill / Tool** 见架构 §6 与 **Phase B** 实现计划。
