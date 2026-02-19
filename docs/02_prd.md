# 项目 PRD 与系统契约 (System Context)

> **⚠️ 致 AI 开发助手的全局指令 (Global Prompt for AI):**
> 本文档是当前项目的最高需求指导准则。在生成任何前端页面、后端路由、数据库查询逻辑时，必须严格遵循本文档中定义的权限边界、技术栈约束（特别是不可修改数据库结构的红线）以及数据字典映射。如果用户指令与本文档冲突，请以本文档为准并提醒用户。

---

## 1. 项目概述与业务目标 (Project Overview)

### 1.1 项目名称
团队内部测试用例批量执行结果看板与管理系统（以下简称"本系统"）

### 1.2 业务背景与痛点
本系统服务于团队内部的自动化测试流程。当前，测试用例通过 Jenkins 流水线进行批量执行，执行结果数据已经落盘到一套固定的 MySQL 数据库库表中。但存在以下核心痛点：

| # | 痛点 | 影响 |
|---|------|------|
| P1 | 测试用例执行结果分散，缺乏集中展示的可视化看板 | 团队无法快速了解整体测试健康度 |
| P2 | 失败用例的归因分析、流转指派依赖线下沟通，效率低 | 问题响应周期长，容易遗漏 |
| P3 | 缺乏总结报告能力 | 测试进度不透明，决策缺乏数据支撑 |
| P4 | 通知流转靠人工手动跟进，缺少系统级的自动提醒机制 | 催办成本高、容易遗漏 |

### 1.3 核心目标 (MVP)
构建一个 Web 应用，实现以下目标：
1. **集中展示**：以可视化看板形式集中展示测试用例的批量执行结果和趋势。
2. **高效处理**：提供失败用例的在线归因分析、流转指派、状态管理能力。
3. **自动通知**：通过 WeLink 等渠道实现自动化的催办与事件通知。
4. **报告总结**：一键生成批次执行总结报告，支持分享和深度链接。

### 1.4 成功指标
- 提升测试用例执行记录的管理（包括总结、通知、流转等）与处理（包括分析、定位、标注等）效率。
- **量化目标：** 从用例执行结束到所有失败执行记录处理结束，在半天内完成。

### 1.5 核心业务术语

| 术语 | 含义 | 对应数据库概念 |
|------|------|--------------|
| 批次 (Batch) | 一轮完整的测试执行，由 Jenkins 流水线触发 | `pipeline_history.start_time` / `pipeline_overview.batch` |
| 分组 (Subtask) | 批次下按机器/任务划分的执行单元 | `pipeline_overview.subtask` / `pipeline_history.subtask` |
| 用例 (Case) | 一个具体的自动化测试用例 | `pipeline_cases.case_name` |
| 执行记录 | 某个用例在某个批次中的一次执行结果 | `pipeline_history` 表中一行记录 |
| 主模块 (Main Module) | 用例所属的主业务模块，用于关联责任人 | `pipeline_history.main_module` → `ums_module_owner.module` |
| 失败原因记录 | 对某条失败用例的归因分析记录 | `pipeline_failure_reason` 表中一行记录 |
| 平台 (Platform) | 执行用例的平台环境 | 各表中的 `platform` 字段 |

---

## 2. 用户角色与权限边界 (Roles & Permissions)

系统采用严格的基于角色的访问控制 (RBAC)。

### 2.1 角色定义

#### 角色 A：普通用户（团队内所有开发人员）

| 维度 | 说明 |
|------|------|
| **权限定义** | 拥有**只读、导出、标注、移交**权限 |
| **允许的操作** | ① 查看所有测试批次的执行大盘及趋势图 <br> ② 按"错误类型/执行批次/模块/平台/用例名"等条件筛选特定的测试用例 <br> ③ 查看报错日志详情（跳转外部链接） <br> ④ 对自己负责的失败用例进行归因标注（选择失败类型、填写原因、关联 DTS 单号） <br> ⑤ 将失败用例流转/指派给其他开发人员 <br> ⑥ 导出筛选后的执行记录数据 |
| **禁止的操作** | ① 修改用例上下线状态 <br> ② 管理用户账号 <br> ③ 管理失败类型/下线类型字典 <br> ④ 管理模块-责任人映射关系 <br> ⑤ 生成和分享总结报告 <br> ⑥ 配置系统定时通知 <br> ⑦ 执行人工催办操作 |

#### 角色 B：系统管理员 (System Admin)

| 维度 | 说明 |
|------|------|
| **权限定义** | 拥有**最高读写与管理**权限 |
| **允许的操作** | 包含普通用户的所有权限，额外拥有： <br> ① 管理测试用例上下线状态（`pipeline_cases.is_online`等字段） <br> ② 管理用户账号（`ums_email` 表的增删改） <br> ③ 管理模块-责任人映射（`ums_module_owner` 表的增删改） <br> ④ 管理失败类型字典（`case_failed_type` 表的增删改） <br> ⑤ 管理下线类型字典（`case_offline_type` 表的增删改） <br> ⑥ 生成、分享批次总结报告 <br> ⑦ 配置定时催办通知规则 <br> ⑧ 手动触发紧急催办 |

### 2.2 认证方式
- 系统需实现统一账号登录功能，但是对接内部域账号认证的具体实现可以先以空实现替代，先配置为简单写死的管理员账号和普通用户账号认证实现。
- 登录后系统需识别用户角色，动态展示/隐藏对应功能入口。

---

## 3. 核心功能模块与 User Stories (Core Features)

### Epic 1: 测试结果多维数据看板

#### Story 1.1: 批次执行概览趋势图
- **描述：** 作为开发人员，希望能够通过以"批次"为横轴的折线图查看测试执行趋势，以便直观比对不同批次间的用例失败情况及执行耗时的变化。
- **AC（验收标准）：**
  - **Given** 开发人员进入系统首页，**When** 图表组件加载完成，**Then** 以"批次"为 X 轴（按自增顺序自左向右排列）。
  - **Given** 图表进行数据渲染，**When** 绘制趋势线，**Then** 提供多条折线（或双 Y 轴折线+柱状图组合），明确展示关键指标的走势：失败用例数（折线A）、总用例数（折线B）、执行耗时/执行时间（折线C）。
  - **Given** 用户想要查看某个具体批次的详细数据，**When** 将鼠标悬停在 X 轴的某个"批次"节点上（触发 Hover），**Then** 出现提示框（Tooltip），完整展示该批次的所有次要数据，包含：具体的执行发生时间（Timestamp）、成功数、未处理数、以及具体的执行耗时。
  - **Given** 底层 MySQL 中存在海量的历史批次数据，**When** 渲染折线图时，**Then** 系统默认仅查询并展示最近 N 个（如最近 30 个）批次的数据点，以避免 X 轴刻度过于拥挤，并保证图表渲染性能。
- **数据来源：** 以 `pipeline_overview` 为主表，按 `batch` 聚合：`SUM(case_num)` 总用例数、`SUM(failed_num)` 失败数、`SUM(passed_num)` 通过数；执行耗时通过 `MAX(batch_end) - MIN(batch_start)` 计算。

#### Story 1.2: 多层级失败明细下钻
- **描述：** 作为开发人员，希望能够在选中某个批次后，层层下钻（批次 → 分组 → 具体用例）查看失败明细，以便精准定位需要关注的错误。
- **AC：**
  - **Given** 用户在批次列表中点击某一批次，**When** 进入详情页，**Then** 支持按"业务模块（`main_module`）"、"平台（`platform`）"、"执行结果（`case_result`）"等字段进行筛选展示。
  - **Given** 用户查看具体用例，**When** 展开详情，**Then** 展示底层 MySQL 中错误日志（`log_url`）、截图（`screenshot_url`）、测试报告（`reports_url`）、流水线（`pipeline_url`）等的跳转链接。
- **数据来源：** 批次级 → `pipeline_overview`（按 `batch` 过滤）；分组级 → `pipeline_overview`（按 `batch` + `subtask` 过滤）；用例级 → `pipeline_history`（按 `start_time` + `subtask` 过滤）。

#### Story 1.3: 多条件筛选与搜索
- **描述：** 作为开发人员，希望能够通过用例名称（`case_name`）、模块名称（`main_module` / `module`）、执行状态（`case_result`）、平台（`platform`）、批次（`start_time`）、是否已分析（`analyzed`）等字段对结果进行组合筛选，以便从海量数据中过滤出想要观测分析的数据。
- **数据来源：** 主要查询 `pipeline_history` 表，可 JOIN `pipeline_failure_reason` 获取归因信息。

---

### Epic 2: 失败用例的分析与流转

#### Story 2.1: 失败原因标注
- **描述：** 作为开发人员，我希望能够对某条失败的测试用例打上原因标签（如：环境问题、用例需适配、Bug 等）并填写备注，以便对失败进行归因。
- **AC：**
  - **Given** 一条状态为"未处理"（`analyzed = 0`）的失败用例，**When** 用户提交了归因标签（选择 `case_failed_type.failed_reason_type`）和备注（`pipeline_failure_reason.reason`），**Then** 系统在 `pipeline_failure_reason` 表中创建/更新一条记录，同时将 `pipeline_history.analyzed` 设为 `1`，并记录操作人（`analyzer`）。
- **写操作涉及的表：** `pipeline_failure_reason`（INSERT/UPDATE）、`pipeline_history`（UPDATE `analyzed` 字段）。
- **可选字段：** 失败类型（`failed_type`，从 `case_failed_type` 字典表中选择）、详细原因（`reason`）、DTS 单号（`dts_num`）、恢复批次（`recover_batch`）。

#### Story 2.2: 失败用例流转/指派
- **描述：** 作为开发人员，我希望能够将不属于我负责的失败用例指派给其他开发人员，以便确保问题由正确的人跟进。
- **AC：**
  - **Given** 用户正在查看某条失败用例，**When** 选择系统内另一位开发人员（从 `ums_email` 表中获取人员列表）并点击"指派"，**Then** 该用例的负责人变更（更新 `pipeline_failure_reason.owner`），同时更新 `pipeline_history.owner` 和 `pipeline_history.owner_history`（追加流转记录）。
- **写操作涉及的表：** `pipeline_failure_reason`（UPDATE `owner`）、`pipeline_history`（UPDATE `owner`、`owner_history`）。

#### Story 2.3: 用例处理状态机流转
- **描述：** 作为系统，我希望能够在后台维护一套清晰的测试用例处理状态机，以便在开发人员进行标注或指派操作时，系统能自动且正确地推进状态流转。
- **状态定义：**

```
待处理(analyzed=0) ──标注归因──▶ 已分析(analyzed=1)
      │                              │
      └──────指派流转──────▶ 已流转(owner变更, analyzed=0仍可保持)
                                     │
                                     └──标注归因──▶ 已分析(analyzed=1)
```

- **AC：**
  - **Given** 用例处于"待处理"状态（`analyzed = 0`），**When** 开发人员开始指派或标注，**Then** 状态严格按照定义的节点推进，系统自动拦截任何不合规的状态越级跳变请求。
- **说明：** 由于数据库中 `analyzed` 为 `tinyint(1)` 仅表示二态（已分析/未分析），更细粒度的状态流转（如区分"已流转但未分析"）需要通过后端业务逻辑，结合 `pipeline_failure_reason` 中是否有记录、`owner` 是否变更等条件综合判断。

#### Story 2.4: 业务操作留痕与时间线
- **描述：** 作为团队开发人员，我希望在查看某条具体的失败用例时，能够看到一条按时间排序的操作历史记录，以便我能清楚追溯协作过程中谁在什么时间修改了什么状态。
- **AC：**
  - **Given** 用户打开一条经历过多轮流转的失败用例，**When** 查看操作日志面板，**Then** 按时间倒序展示历次状态变更、指派动作的操作人和准确时间戳。
- **数据来源：** `pipeline_history.owner_history`（历史记录字段）以及后端审计日志（参见 Story 5.3）。

---

### Epic 3: 批次执行总结报告

#### Story 3.1: 自动化数据汇总与进度报告
- **描述：** 作为系统管理员，我希望能够随时基于某个批次的当前标注情况，一键生成总结报告，以便向团队同步本批次测试的健康度以及当前的问题分析进度。
- **AC（验收标准）：**
  - **Given** 某批次的失败用例处于任意状态（可能部分甚至全部都是"未处理"），**When** 管理员点击"生成报告"，**Then** 系统不仅聚合已标注各类标签的数量，还要将剩余未标注的用例归入"未处理/待分析"分类计算占比（如饼图显示：Bug 占 20%，环境问题占 50%，未处理占 30%），并生成可视化图表。
  - **Given** 报告成功生成，**When** 报告展示给用户时，**Then** 在报告头部显著位置，系统需计算并展示当前的"分析完成度"（计算公式：已分析用例数 / 总失败用例数 × 100%），避免阅读报告的人误以为最终结果已经落定。
- **数据来源：** 以 `pipeline_history`（按 `start_time` 过滤 + `case_result = 'failed'`）为基础，LEFT JOIN `pipeline_failure_reason`（按 `failed_batch` + `case_name` 关联）获取归因信息，聚合统计各 `failed_type` 的数量分布。

#### Story 3.2: 报告分享与直达操作页面的深度链接
- **描述：** 作为系统管理员，我希望能够将生成的报告生成专属分享链接，且报告内的关键数据项支持点击跳转，以便发送到团队群聊后，开发人员能通过报告一键直达系统对应的页面进行分析和标注。
- **AC（验收标准）：**
  - **Given** 报告生成完毕，**When** 管理员点击"分享"，**Then** 系统生成该批次报告的唯一 URL 链接（需附带必要的访问权限校验），供管理员复制到外部通讯工具中。
  - **Given** 开发人员通过分享链接在浏览器中打开报告，**When** 点击报告图表中的特定分类（例如饼图中的"未处理 30 条"），**Then** 系统在新标签页中打开系统的概览或明细列表页，并自动在 URL 中带上筛选参数（如 `?batchId=xxx&status=unprocessed`），页面加载后直接过滤出这些待处理的用例。

#### Story 3.3: 报告数据快照保存
- **描述：** 作为系统，我希望在管理员生成批次总结报告的那一刻，能够对当前的汇总数据生成一份不可篡改的快照，以便防止后续底层基础数据发生变更而导致历史报告内容失真。
- **AC：**
  - **Given** 一份总结报告已经生成完毕，**When** 后续该批次中的某条失败用例被再次修改了归因标签，**Then** 已生成的报告内容和图表统计依然保持生成时的状态，不受影响。

---

### Epic 4: 消息提醒与通知网络

#### Story 4.1: 定时催办通知
- **描述：** 作为系统，我希望能够在设定的时间节点，自动筛选出"未处理"状态的失败记录，并向其当前负责人发送汇总通知，以便防止问题遗漏。
- **AC：**
  - **Given** 到达管理员设置的每日提醒时间（如每日上午 10 点），**When** 存在归属人为开发 A 的未处理用例（`analyzed = 0` 且 `case_result = 'failed'`），**Then** 系统向 A 发送一条合并通知："您有 X 条未处理的失败用例待分析"。
- **通知渠道：** 通过 WeLink 发送，使用 `ums_email.domain_account` 作为消息接收人标识。

#### Story 4.2: 人工一键紧急催办
- **描述：** 作为系统管理员，我希望能够在系统面板上选择特定批次或特定人员，手动触发提醒并可附加自定义消息，以便应对紧急的发布流程，加速问题闭环。
- **AC（验收标准）：**
  - **Given** 管理员进入系统的"催办管理"面板或在"批次详情页"操作，**When** 切换"按特定批次"或"按特定人员"维度进行查找，**Then** 系统需提供支持多选的列表或下拉框，并实时显示所选项名下当前处于"待处理"的用例数量。
  - **Given** 管理员勾选了目标对象（批次或人员），**When** 点击"发送提醒"唤起弹窗，并输入可选的"紧急自定义附言"（例如："今晚急需发版，请速看"），**Then** 系统在提交前需进行校验拦截：若所选对象名下实际已无待处理用例，则阻断发送并报错提示"该对象当前无待处理任务，无需催办"。
  - **Given** 催办请求合法并成功提交给后端，**When** 后端执行通知分发逻辑，**Then** 系统立刻通过 WeLink 发送带有【紧急催办】标识的高优消息。消息体必须包含：管理员的自定义附言、具体的待处理数量摘要，以及能够一键直达对应处理页面的深度链接（Deep Link）。

#### Story 4.3: 事件触发的实时通知
- **描述：** 作为开发人员，我希望在被其他人指派了失败用例时，能立即收到通知，以便我及时介入处理。
- **AC：**
  - **Given** 开发 A 将用例指派给开发 B，**When** 指派动作成功后，**Then** 系统立即通过 WeLink 触发通知给开发 B（通过 `ums_email.domain_account` 查找接收人），并附带用例详情链接。

#### Story 4.4: 消息通知渠道配置
- **描述：** 作为系统管理员，我希望能够在后台配置消息通知的下发渠道（主要是 WeLink），以便通知能够通过团队最习惯的媒介触达开发人员。
- **AC（验收标准）：**
  - **Given** 业务流（如定时催办、人工催办、流转指派）触发了提醒，**When** 执行通知下发逻辑，**Then** 系统无需进行渠道路由判断，直接将消息组装为 WeLink 支持的格式（如卡片消息或纯文本），并根据开发人员在 `ums_email` 表中的 `domain_account`（域账号）推送到其 WeLink 账号。

#### Story 4.5: 通知防打扰与合并机制
- **描述：** 作为开发人员，我希望系统能提供防打扰机制，以便我不会在短时间内被高频的系统通知（如连续的单独指派）轰炸。
- **AC：**
  - **Given** 系统在极短时间（如 5 分钟）内连续触发了多条针对同一开发人员的指派提醒，**When** 执行发送逻辑，**Then** 系统触发防打扰策略，将这些提醒合并为 1 条摘要通知发送。

---

### Epic 5: 基础支撑系统

#### Story 5.1: 身份认证与权限隔离
- **描述：** 作为团队成员（开发或管理员），我希望能够通过统一账号体系登录系统，且系统能够识别我的角色，以便我只能看到和操作我有权限的功能。
- **AC：**
  - **Given** 登录用户角色为"开发人员"，**When** 访问系统，**Then** 隐藏"生成总结报告"、"设置定时通知"、"催办管理"等管理员专属入口。
  - **Given** 普通用户尝试通过 API 直接调用管理员接口，**When** 后端验证角色，**Then** 返回 403 Forbidden 并拒绝执行。

#### Story 5.2: 管理员后台管理
- **描述：** 作为系统管理员，我希望能够在管理后台维护以下基础数据，以便系统正常运转。
- **管理范围：**
  - **用户管理：** 对 `ums_email` 表的增删改查（员工工号、姓名、邮箱、域账号）。
  - **模块-责任人映射管理：** 对 `ums_module_owner` 表的增删改查（哪个主模块对应哪个责任人）。
  - **失败类型字典管理：** 对 `case_failed_type` 表的增删改查（维护可选的失败原因分类）。
  - **下线类型字典管理：** 对 `case_offline_type` 表的增删改查（维护可选的用例下线原因分类）。
  - **用例上下线管理：** 对 `pipeline_cases` 表中用例的在线/下线状态、下线原因等字段的更新。

#### Story 5.3: 全局系统审计日志 (System Audit Log)
- **描述：** 作为系统管理员，我希望系统能在底层静默记录所有用户的关键数据变更操作（如状态流转、指派、配置修改等），以便在出现数据异常或安全审查时，拥有不可篡改的底层追踪依据。
- **AC（验收标准）：**
  - **Given** 任何用户通过系统触发了核心数据的写操作（如修改用例状态），**When** 请求到达后端，**Then** 系统底层（例如通过 AOP 切面或全局中间件）自动拦截，并提取：操作人 ID、操作时间、行为类型及修改前后的关键参数，异步写入审计日志。
  - **Given** 这是一个底层基建能力，**When** 系统 MVP 版本上线，**Then** 即使前端暂时没有开发"全局日志查询"的管理页面，后端也必须保证这部分数据的稳定落盘。

---

## 4. 技术栈与硬性约束 (Constraints & Tech Stack)

### 4.1 技术栈

| 层级 | 技术选型 |
|------|---------|
| **前端** | React（推荐搭配 Ant Design 组件库 + ECharts/Recharts 图表库） |
| **后端** | FastAPI + SQLAlchemy + Pydantic |
| **数据库** | MySQL 5.7（已存在，使用 `utf8mb4_unicode_ci` 字符集） |
| **通知渠道** | WeLink API |

### 4.2 🚨 数据库与底层架构红线 (Absolute Constraints)

> **以下红线不可逾越，任何 AI 辅助编码过程中生成的代码均必须遵守：**

1. **本系统底层使用已存在的 MySQL 数据库 `dt_infra`**，其中部分核心表结构已完全固定。
2. **严禁修改已有表结构：** 绝对不允许对已有的 8 张表执行 `ALTER TABLE`、`DROP TABLE` 语句，其 DDL 定义不可更改。
3. **允许新建表：** 对于系统自身新增的持久化需求（如报告快照、审计日志等），允许创建新表。**新建表时必须在 `database/` 目录下创建对应的 SQL 迁移文件**，文件命名严格遵循 `V<主版本号>.<次版本号>.<修订号>__<全英文下划线描述>.sql` 格式（详见 `database/README.md`）。
4. **严禁 DML 删除操作：** 不允许对核心执行数据（`pipeline_history`、`pipeline_overview`）执行 `DELETE` 操作。
5. **逻辑实现原则：** 所有复杂的业务聚合需求，必须基于现有的表结构通过高效的 SQL `SELECT` 查询，或者在后端服务的内存中进行处理。

### 4.3 性能与安全约束

| 约束 | 说明 |
|------|------|
| **分页** | 所有列表查询接口必须支持分页，默认 Page Size ≤ 50 |
| **图表数据量** | 趋势图默认展示最近 30 个批次，避免前端渲染海量数据点 |
| **权限校验** | 所有写操作 API 必须在后端进行角色校验，不可仅依赖前端隐藏 |
| **SQL 防注入** | 使用 SQLAlchemy ORM / 参数化查询，禁止拼接 SQL 字符串 |

---

## 5. 页面流转与视图布局 (Page Flow & Views)

### 5.1 全局导航 (Sidebar)

采用左侧固定导航栏，包含以下菜单项：

| 菜单项 | 说明 | 可见角色 |
|--------|------|---------|
| 首页大盘 | 执行趋势概览 + 核心统计卡片 | 所有用户 |
| 分组执行历史 | 按 `pipeline_overview` 展示批次-分组级汇总 | 所有用户 |
| 详细执行历史 | 按 `pipeline_history` 展示用例级明细列表 | 所有用户 |
| 用例管理 | 管理 `pipeline_cases` 表中的用例上下线状态 | 管理员 |
| 管理员设置 | 用户管理、模块映射、字典管理、通知配置 | 管理员 |

### 5.2 首页大盘 (Dashboard View)

**上半部分 — 核心统计数据卡片：**
- 最新批次名称及执行时间
- 总用例数 / 通过数 / 失败数 / 通过率
- 未处理失败用例数 / 分析完成度

**下半部分 — 趋势图：**
- 以"批次"为 X 轴的多指标折线图（参见 Story 1.1）
- 默认展示最近 30 个批次
- 支持 Hover Tooltip 展示详细数据

### 5.3 分组执行历史列表

- **数据源：** `pipeline_overview`
- **列字段：** 批次、分组名、执行结果、总用例数、通过数、失败数、开始时间、结束时间、平台、代码分支
- **筛选条件：** 批次、分组名、执行结果、平台
- **操作：** 点击行跳转到该分组下的详细用例执行列表

### 5.4 详细执行历史列表

- **数据源：** `pipeline_history`，可 LEFT JOIN `pipeline_failure_reason`
- **列字段：** 批次、分组、用例名、主模块、执行结果、用例级别、负责人、是否已分析、平台、代码分支、创建时间
- **筛选条件：** 批次、分组、用例名（模糊搜索）、主模块、执行结果、是否已分析、平台
- **操作：** 点击行展开详情

### 5.5 用例详情交互 (Detail Interaction)

在列表中点击某条执行记录时，通过**右侧滑出抽屉 (Drawer)** 展示以下信息：

| 区域 | 内容 |
|------|------|
| **基本信息** | 用例名、批次、分组、主模块、用例级别、平台、代码分支 |
| **外部链接** | 日志URL、截图URL、测试报告URL、流水线URL（均以可点击链接形式展示） |
| **归因分析区** | 失败类型下拉选择（来源 `case_failed_type`）、详细原因文本框、DTS 单号输入框、恢复批次输入框 |
| **流转操作区** | 当前负责人展示、指派给其他人（下拉选择来源 `ums_email`） |
| **操作时间线** | 按时间倒序展示历次操作记录（来源 `owner_history` 及审计日志） |

### 5.6 页面流转关系

```
首页大盘 ─── 点击批次 ──▶ 分组执行历史（自动带入批次筛选）
                              │
                              └── 点击分组 ──▶ 详细执行历史（自动带入批次+分组筛选）
                                                    │
                                                    └── 点击用例 ──▶ 用例详情 Drawer
                                                                      ├── 归因标注
                                                                      ├── 流转指派
                                                                      └── 查看外部链接

管理员设置 ──▶ 用户管理 / 模块映射管理 / 失败类型字典 / 下线类型字典 / 通知配置
```

---

## 6. 数据字典与业务映射 (Data Dictionary & Mapping)

### 6.1 数据库表总览

本系统共涉及以下 **8 张已存在的数据库表**（均位于 `dt_infra` 库中）：

| 表名 | 业务含义 | 读写属性 |
|------|---------|---------|
| `pipeline_overview` | 批次-分组级执行概览 | **只读**（数据由 CI 流水线写入） |
| `pipeline_history` | 用例级执行明细记录 | **部分可写**（仅 `analyzed`、`owner`、`owner_history` 可更新） |
| `pipeline_failure_reason` | 失败用例归因分析记录 | **可读写**（用户创建/更新归因记录） |
| `pipeline_cases` | 用例主数据（状态、上下线等） | **部分可写**（管理员可更新用例状态与下线信息） |
| `ums_email` | 员工信息表（工号、姓名、邮箱、域账号） | **可读写**（管理员管理） |
| `ums_module_owner` | 主模块-责任人映射 | **可读写**（管理员管理） |
| `case_failed_type` | 失败原因类型字典 | **可读写**（管理员管理） |
| `case_offline_type` | 下线原因类型字典 | **可读写**（管理员管理） |

### 6.2 各表字段详细说明

#### 6.2.1 `pipeline_overview` — 批次-分组执行概览（只读）

| 字段名 | 类型 | 说明 | 读/写 |
|--------|------|------|-------|
| `id` | int(11) PK | 自增主键 | 只读 |
| `batch` | varchar(100) | 轮次/批次标识 | 只读 |
| `subtask` | varchar(100) | 分组名（一个机器一个组，也是 Jenkins 任务名） | 只读 |
| `result` | varchar(25) | 本轮该组执行结果：`passed`（全部通过）/ `failed`（未全部通过） | 只读 |
| `case_num` | varchar(25) | 本轮该组执行的所有用例数量 | 只读 |
| `passed_num` | int(11) | 本轮该组通过的用例数量 | 只读 |
| `failed_num` | int(11) | 本轮该组未通过的用例数量 | 只读 |
| `batch_start` | datetime | 本轮该组开始执行时间 | 只读 |
| `batch_end` | datetime | 本轮该组执行结束时间 | 只读 |
| `reports_url` | varchar(150) | 测试报告 URL | 只读 |
| `log_url` | varchar(150) | 日志 URL | 只读 |
| `screenshot_url` | varchar(150) | 截图 URL | 只读 |
| `pipeline_url` | varchar(150) | Jenkins 流水线 URL | 只读 |
| `platform` | varchar(255) | 平台名称 | 只读 |
| `code_branch` | varchar(255) | 执行时使用的 IDE 代码分支 | 只读 |
| `created_at` | datetime | 创建时间 | 只读 |
| `updated_at` | datetime | 更新时间 | 只读 |

**索引：** `idx_batch_subtask(batch, subtask)` / `idx_subtask(subtask)`

#### 6.2.2 `pipeline_history` — 用例级执行明细（部分可写）

| 字段名 | 类型 | 说明 | 读/写 |
|--------|------|------|-------|
| `id` | int(11) PK | 自增主键 | 只读 |
| `start_time` | varchar(50) | 轮次/批次标识（等同于 `pipeline_overview.batch`） | 只读 |
| `subtask` | varchar(100) | 分组名 | 只读 |
| `case_name` | varchar(255) | 用例名称 | 只读 |
| `case_result` | varchar(50) | 本轮执行结果（如 `passed` / `failed`） | 只读 |
| `case_level` | varchar(100) | 用例级别（如 P0/P1/P2） | 只读 |
| `module` | varchar(40) | 测试用例代码中标记的模块名 | 只读 |
| `main_module` | varchar(100) | 测试用例主模块（用于关联 `ums_module_owner`） | 只读 |
| `platform` | varchar(255) | 平台名称 | 只读 |
| `code_branch` | varchar(255) | 执行时使用的 IDE 代码分支 | 只读 |
| `reports_url` | varchar(255) | 测试报告 URL | 只读 |
| `log_url` | varchar(250) | 日志 URL | 只读 |
| `screenshot_url` | varchar(250) | 截图 URL | 只读 |
| `pipeline_url` | varchar(200) | Jenkins 流水线 URL | 只读 |
| `owner` | varchar(255) | 用例责任人（开发），可流转更新 | **可写** |
| `owner_history` | varchar(255) | 用例责任人变更记录 | **可写** |
| `analyzed` | tinyint(1) | 是否已分析失败原因：`0`=未分析，`1`=已分析 | **可写** |
| `created_at` | datetime | 创建时间 | 只读 |
| `updated_at` | datetime | 更新时间（自动更新） | 自动 |

**索引：** `idx_timentask(start_time, subtask)` / `idx_main_module(main_module)` / `idx_start_time_case(start_time, case_name)` / `idx_casename_platform_batch(case_name, platform, start_time)` / `idx_created_at_desc(created_at)`

#### 6.2.3 `pipeline_failure_reason` — 失败归因记录（可读写）

| 字段名 | 类型 | 说明 | 读/写 |
|--------|------|------|-------|
| `id` | int(11) PK | 自增主键 | 自动 |
| `case_name` | varchar(255) | 用例名称（关联 `pipeline_history.case_name`） | **创建时写入** |
| `failed_batch` | varchar(200) | 失败轮次（关联 `pipeline_history.start_time`） | **创建时写入** |
| `platform` | varchar(255) | 用例平台 | **创建时写入** |
| `owner` | varchar(100) | 失败用例跟踪人（可流转） | **可写** |
| `failed_type` | varchar(100) | 失败原因分类（来源 `case_failed_type.failed_reason_type`） | **可写** |
| `reason` | text | 详细失败原因 | **可写** |
| `analyzer` | varchar(255) | 失败原因分析人 | **可写** |
| `dts_num` | varchar(255) | 关联 DTS 单号 | **可写** |
| `recover_batch` | varchar(200) | 恢复轮次 | **可写** |
| `created_at` | datetime | 创建时间 | 自动 |
| `updated_at` | datetime | 更新时间 | 自动 |

**索引：** `idx_pfr_failedbatch_case(failed_batch, case_name)`

#### 6.2.4 `pipeline_cases` — 用例主数据（部分可写）

| 字段名 | 类型 | 说明 | 读/写 |
|--------|------|------|-------|
| `id` | int(11) PK | 自增主键 | 只读 |
| `case_name` | varchar(255) | 用例名称 | 只读 |
| `case_level` | varchar(255) | 用例级别（如 P0/P1/P2） | 只读 |
| `case_type` | varchar(25) | 用例类型 | 只读 |
| `test_type` | varchar(25) | 测试类型（如 API/UI） | 只读 |
| `platform` | varchar(50) | 平台名称 | 只读 |
| `pkg_type` | varchar(255) | 包类型 | 只读 |
| `is_online` | varchar(25) | 是否在线运行 | **可写（管理员）** |
| `state` | varchar(30) | 用例当前状态 | **可写（管理员）** |
| `state_detail` | varchar(255) | 状态详情/备注 | **可写（管理员）** |
| `change_history` | varchar(500) | 变更历史记录 | **可写（管理员）** |
| `recover_batch` | varchar(50) | 恢复轮次 | **可写（管理员）** |
| `offline_reason_type` | varchar(500) | 下线原因分类（来源 `case_offline_type`） | **可写（管理员）** |
| `offline_reason_detail` | varchar(500) | 下线原因详细说明 | **可写（管理员）** |
| `offline_case_owner` | varchar(255) | 下线用例责任人 | **可写（管理员）** |
| `created_at` | datetime | 创建时间 | 自动 |
| `updated_at` | datetime | 更新时间 | 自动 |

**索引：** `idx_case_name(case_name)` / `idx_state(state)`

#### 6.2.5 `ums_email` — 员工信息表（管理员可读写）

| 字段名 | 类型 | 说明 | 读/写 |
|--------|------|------|-------|
| `employee_id` | varchar(20) PK | 工号 | **可写（管理员）** |
| `name` | varchar(50) | 姓名 | **可写（管理员）** |
| `email` | varchar(100) UNIQUE | 邮箱 | **可写（管理员）** |
| `domain_account` | varchar(255) | 域账号（WeLink 消息接收人标识） | **可写（管理员）** |
| `created_at` | datetime | 创建时间 | 自动 |
| `updated_at` | datetime | 更新时间 | 自动 |

**索引：** `email(UNIQUE)` / `idx_name(name)`

#### 6.2.6 `ums_module_owner` — 模块-责任人映射（管理员可读写）

| 字段名 | 类型 | 说明 | 读/写 |
|--------|------|------|-------|
| `module` | varchar(40) PK | 测试用例主模块名 | **可写（管理员）** |
| `owner` | varchar(20) FK | 负责人工号（外键 → `ums_email.employee_id`） | **可写（管理员）** |
| `for_reference` | varchar(255) | 负责人姓名（辅助展示用） | **可写（管理员）** |
| `created_at` | datetime | 创建时间 | 自动 |
| `updated_at` | datetime | 更新时间 | 自动 |

**外键约束：** `owner` → `ums_email.employee_id`（ON UPDATE CASCADE）

#### 6.2.7 `case_failed_type` — 失败原因类型字典（管理员可读写）

| 字段名 | 类型 | 说明 | 读/写 |
|--------|------|------|-------|
| `id` | int(11) PK | 自增主键 | 自动 |
| `failed_reason_type` | varchar(255) UNIQUE | 失败原因分类名称 | **可写（管理员）** |
| `owner` | varchar(255) | 该失败类型的默认跟踪人 | **可写（管理员）** |
| `creator` | varchar(255) | 创建者 | **可写（管理员）** |
| `updater` | varchar(255) | 更新者 | **可写（管理员）** |
| `created_time` | datetime | 创建时间 | 自动 |
| `updated_time` | datetime | 更新时间 | 自动 |

> **注意：** 本表的时间字段命名为 `created_time` / `updated_time`，与其他表的 `created_at` / `updated_at` 不同，后端 ORM 映射时需特别注意。

#### 6.2.8 `case_offline_type` — 下线原因类型字典（管理员可读写）

| 字段名 | 类型 | 说明 | 读/写 |
|--------|------|------|-------|
| `id` | int(11) PK | 自增主键 | 自动 |
| `offline_reason_type` | varchar(500) UNIQUE | 用例下线原因分类 | **可写（管理员）** |

### 6.3 核心表关联关系

```
ums_email (员工信息)
    │
    ├─── PK: employee_id
    │         │
    │         └──FK──▶ ums_module_owner.owner (模块-责任人映射)
    │                       │
    │                       └── PK: module ◀── pipeline_history.main_module (主模块关联)
    │
    └─── domain_account ──▶ WeLink 消息推送标识


pipeline_overview (批次-分组概览)
    │
    └── batch + subtask ──关联──▶ pipeline_history.start_time + subtask (用例明细)
                                        │
                                        ├── case_name + start_time ──关联──▶ pipeline_failure_reason.case_name + failed_batch (归因记录)
                                        │
                                        └── case_name ──关联──▶ pipeline_cases.case_name (用例主数据)


case_failed_type.failed_reason_type ──被引用──▶ pipeline_failure_reason.failed_type (失败归因选择)
case_offline_type.offline_reason_type ──被引用──▶ pipeline_cases.offline_reason_type (下线原因选择)
```

> **重要说明：** 以上关联关系中，除 `ums_module_owner.owner → ums_email.employee_id` 有数据库级外键约束外，其余均为**逻辑关联**（通过业务字段值匹配），无数据库级外键。后端查询时需通过 JOIN 条件或应用层逻辑保证数据一致性。

### 6.4 核心状态枚举 (Status Enums)

| 所属表 | 字段 | 枚举值 | 业务含义 |
|--------|------|--------|---------|
| `pipeline_overview` | `result` | `passed` | 本轮该分组全部用例通过 |
| | | `failed` | 本轮该分组存在未通过用例 |
| `pipeline_history` | `case_result` | `passed` | 本条用例执行通过 |
| | | `failed` | 本条用例执行失败 |
| `pipeline_history` | `analyzed` | `0` | 未分析（未给失败用例分配失败原因） |
| | | `1` | 已分析（已分配失败原因） |

> **待确认枚举：** `pipeline_cases.is_online` 和 `pipeline_cases.state` 的实际枚举值需从生产数据中确认后补充。建议在开发启动前通过 `SELECT DISTINCT is_online FROM pipeline_cases` 和 `SELECT DISTINCT state FROM pipeline_cases` 查询确认。

### 6.5 字段读写边界总结

| 操作类型 | 可操作的表与字段 | 操作角色 |
|---------|----------------|---------|
| **普通用户写操作** | `pipeline_history`: `analyzed`, `owner`, `owner_history` <br> `pipeline_failure_reason`: 全字段（INSERT/UPDATE） | 普通用户 + 管理员 |
| **管理员专属写操作** | `pipeline_cases`: `is_online`, `state`, `state_detail`, `change_history`, `recover_batch`, `offline_reason_type`, `offline_reason_detail`, `offline_case_owner` <br> `ums_email`: 全字段 <br> `ums_module_owner`: 全字段 <br> `case_failed_type`: 全字段 <br> `case_offline_type`: 全字段 | 仅管理员 |
| **完全只读** | `pipeline_overview`: 全字段 <br> `pipeline_history`: 除上述 3 个可写字段外的所有字段 <br> `pipeline_cases`: 除上述可写字段外的所有字段 | 系统自动（CI 流水线写入） |

---

> **文档版本：** v1.0 — 最终版
> **生成日期：** 2026-02-17
> **后续步骤：** 基于本 PRD 文档进行技术架构文档的生成（API 设计、数据模型映射、组件拆分等）。
