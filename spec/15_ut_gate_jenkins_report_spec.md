# UT 门禁结果自动上报至看板系统（Spec）

本文档描述将 CodeHub MR 触发的 Jenkins UT 门禁执行结果**采集、持久化、查询与展示**的方案设计，供 Jenkins 侧脚本改造与 QualityBoard（dt-report）后端/前端实现时对照。本文档**不**包含 `build/.cloudbuild/gate/root.sh` 的具体实现（该文件不在本仓），仅约定对接契约与集成点。

**关联约束**（实现本需求时需遵守项目规则）：新建表须先有 `database/Vx.y.z__*.sql` 迁移；MySQL 5.7 语法；禁止改动既有 8 张保护表；上报接口认证方式与日志规范见本文档与 `docs/06_logging_guide.md`。

---

## 1. 背景与业务目标

### 1.1 背景

- CodeHub 上 MR 在合入前触发 Jenkins UT 门禁任务。
- 任务核心步骤：拉取代码 → 执行 `cargo make test` → 在 Console Output 中出现汇总行，例如：  
  `Summary [ 3.178s] 83 tests run: 83 passed, 3 skipped`  
- **UT 拦截到问题**：以**合法 Summary** 为准——若存在 **失败用例**（例如日志中 **`failed` 且失败数大于 0** 或等价表达），则 **`is_intercepted=true`**。  
- **其余一切情况**（含：**合法 Summary 且无失败**、**无合法 Summary**、**前置失败**、**解析失败** 等）均 **`is_intercepted=false`**。**注意**：`false` **不**等价于「未检出问题的健康构建」——仅表示「未满足『可判定且存在失败用例』」；细分语义须结合 Jenkins 日志或后续扩展字段（见 §8.1、§8.4）。

### 1.2 业务目标

- 记录**哪次 MR / 哪次构建**触发了 UT 门禁。
- 用单一布尔字段 **`is_intercepted`** 表示 **UT 是否拦截到**：**仅当** Summary **可判定**且**存在失败用例**时为 **`true`**；**其它所有情况**均为 **`false`**（见 §3.3、§5.2）。
- 通过 **「UT门禁历史」列表页**（见 §8.3）展示上报记录与 **拦截效果**（**`is_intercepted`** 等列）；**`false` 为混合集合**（含未拦截、不可判定等）。**本期不做**首页图表、**不做** ECharts 趋势/饼柱图（见 §8.2）；若需按「无 Summary / 前置失败」单独出图或趋势分析，**二期**加字段或扩展页面。**本期库表不存** MR 源/目标分支、MR 编号、**Git 仓库 URL、commit**；若要看代码分支或提交维度，须 **二期扩展字段** 或仅从 **`mr_url` 路径** 做展示层解析（非库表字段）。

### 1.3 非目标（本期可不做）

- 替换或重写 Jenkins 门禁判定逻辑（仍以现有脚本/退出码为准）。
- 存储完整 Console Output 或单条用例级明细（除非后续单独立项）。
- 在 Jenkins 内嵌 QualityBoard 页面（本期以 API + Web 看板为主）。

---

## 2. 需求与约束

| 编号 | 需求/约束 | 说明 |
|------|-----------|------|
| R1 | 不破坏现有 UT 门禁 | 上报为**旁路**；不得改变 `cargo make test` 的调用方式与失败判定主路径。 |
| R2 | 上报失败不阻断任务 | 上报须包在「忽略非零退出」或独立子 shell 中；失败仅打日志，**不得** `exit 1`。 |
| R3 | 网络 | Jenkins 执行节点到 QualityBoard 后端需可达；若不通须走代理或内网 DNS，**在部署文档中明确**。 |
| R4 | 敏感信息 | 禁止在脚本中硬编码密码、长期 Token；使用 Jenkins Credentials / 环境变量注入。 |
| R5 | **不依赖未定义环境变量** | Jenkins 侧上报逻辑**仅允许**使用 §5.2.1 所列 **A / B 类**与**脚本可计算值**；**禁止**裸引用未列入 §5.2.1、未判空的变量；可选字段在无法可靠得到时 **省略 JSON 键或传 `null`**（见 §5.2.1）。 |

---

## 3. 问题 1：如何获取 UT 执行结果？

### 3.1 方案对比与本期结论

**本期规约：仅采用方案 B**——在 **root.sh**（或门禁脚本最外层）用 **`tee`** 捕获 `cargo make test` 输出并在**同一次构建**内解析 Summary；**不**采用任务结束后依赖 **Jenkins API（或插件）拉取 Console Output** 再解析的方案 A，也**不**并行部署 QualityBoard 侧「拉日志对账」类同步任务。

| 方案 | 做法 | 优点 | 缺点 | 本期 |
|------|------|------|------|------|
| **A. 任务结束后解析 Console Output** | 用 Jenkins API（或插件）拉取构建日志，服务端/独立 Job 解析 Summary | 不改门禁脚本；集中解析 | 依赖 Jenkins API 与权限；有延迟；日志量大时需截断策略 | **不采用** |
| **B. root.sh 内捕获测试输出** | 将 `cargo make test` 输出经管道 **`tee`** 写入工作区文件，同脚本内解析 Summary | 实时、不依赖事后拉日志；易与构建号、MR 元数据对齐 | 需改脚本（仍可为旁路）；需约定输出编码与文件路径；日志极大时注意磁盘空间 | **采用** |
| **C. 测试框架/JUnit 报告** | 若 `cargo make test` 可生成 JUnit XML，解析 XML 上报 | 结构化、可扩展用例级统计 | 依赖工具链是否产出报告；改造面可能大于解析一行 Summary | **不采用**（后续若要用例级统计再评估） |

### 3.2 本期实现要点（方案 B）

- 在 **root.sh**（或门禁脚本最外层）对测试命令使用 **`tee`**，将 stdout/stderr 写入**构建工作目录下**固定相对路径文件（如 `.ci/ut_console.log`），在同一脚本末尾解析 **`Summary ...`** 行（**本期业务约定**：日志中**不出现多行** Summary，见 §3.3、§7.2）。  
- 构建节点须具备常见 Linux 自带的 **`tee`**（属 coreutils）；极简无 `tee` 的镜像需在流水线镜像或脚本中另行保证可用性。

### 3.3 Summary 行解析规约（逻辑）

- **模式（建议，待与真实日志对齐）**：  
  `Summary [<duration>] <N> tests run: <P> passed, <S> skipped`  
  若存在 **`, <F> failed`** 或 **`0 failed` 以外的 failed 片段**，且 **failed > 0**，则 **`is_intercepted=true`**。  
  **其它任意情况**（含：合法 Summary 且无失败、无合法 Summary、仅凭退出码非 0、解析失败等）一律 **`is_intercepted=false`**。  
- **本期业务约定**：UT 门禁日志中 **Summary 仅一行**（**不出现**多 crate / 多模块导致的**多行** Summary；若将来工具链变化出现多行，须修订 §7.2 解析策略）。  
- **本期解析目标**：产出 **`is_intercepted`（布尔）** 即可；**不得**仅凭「`cargo make test` 退出码非 0」置 **`true`**（须以 Summary 可判定且存在失败用例为准）。  
- **`ut_exit_code`**（见 §5.2）建议随请求上报并落库，便于在 **`is_intercepted=false`** 时结合 Jenkins 排查。

---

## 4. 问题 2：如何持久化存储结果？

| 方案 | 说明 | 推荐 |
|------|------|------|
| **A. 调用后端 API 写入数据库** | Jenkins 脚本 `curl` POST JSON；服务端校验后 INSERT | **推荐**；与现有 dt-report 架构一致，查询简单 |
| **B. 写文件由外部同步** | 写 NDJSON/SQLite，由 Filebeat/定时任务导入 | 适合强隔离网络；增加同步组件与延迟 |
| **C. 消息队列** | 推 Kafka/RabbitMQ，消费者落库 | 适合极大规模；本期通常过重 |

**本期规约**：采用 **A**；若网络不可靠，可在 B 中 **仅作本地落盘备份**（同一路径 append 一行 JSON），不替代 API 成功路径的定义。

---

## 5. 问题 3：数据表结构设计

### 5.1 表名（建议）

`ut_gate_run`（新建表；DDL 单独迁移文件，与 ORM 字段一致）。

### 5.2 字段（建议）

**本期持久化**：Jenkins 构建维度 + **`mr_url`**（**唯一 MR 相关字段**）+ **`idempotency_key`** + **`is_intercepted`** + **`ut_exit_code`**；**不存** `git_remote_url`、`git_commit_sha`、`mr_id`、`source_branch`、`target_branch`、`mr_title`、`summary_line`、各 `tests_*`、`duration_sec`、`reporter_version` 等。

| 字段名 | 类型（MySQL 5.7） | 可空 | 说明 |
|--------|-------------------|------|------|
| `id` | BIGINT UNSIGNED AI PK | 否 | 主键 |
| `created_at` | DATETIME | 否 | 记录创建时间（默认 CURRENT_TIMESTAMP） |
| `updated_at` | DATETIME | 否 | 更新时间 ON UPDATE CURRENT_TIMESTAMP |
| `reported_at` | DATETIME | 否 | 门禁结束上报时间（可由服务端写 `NOW()`，或与客户端 `finished_at` 二选一） |
| `jenkins_base_url` | VARCHAR(512) | 是 | Jenkins 根 URL；**由 `BUILD_URL` 解析**，不依赖 `JENKINS_URL`（见 §5.2.1） |
| `job_name` | VARCHAR(256) | 否 | Job 名称（或 fullName，约定一种） |
| `build_number` | INT UNSIGNED | 否 | 构建号 |
| `build_url` | VARCHAR(1024) | 是 | 本次构建页 URL |
| `mr_url` | VARCHAR(1024) | 是 | **MR 页面完整 URL**（如 CodeHub `.../merge_requests/4647`）；作为**逻辑 MR 唯一标识**用于去重与列表跳转；**无 MR 场景**（非 MR 触发）可空 |
| `idempotency_key` | VARCHAR(128) | 否 | **幂等键**：标识「同一次 Jenkins 构建」的唯一键，防止网络重试或脚本重复执行导致**同一次构建写入多行**（详见下文 **idempotency_key 说明**） |
| `is_intercepted` | TINYINT(1) | 否 | **`1`（true）**：Summary **可判定**且**存在失败用例**；**`0`（false）**：其它**所有**情况（含未拦截、无 Summary、前置失败等） |
| `ut_exit_code` | INT | 是 | `cargo make test` 退出码，便于排查；与 `is_intercepted` 无简单一一对应 |

**为何表内没有 `WORKSPACE`？**  
**§5.2 仅列落库字段**。**`WORKSPACE`** 在 **§5.2.1 A 类**中出现，是因为上报脚本需要用它（或 **`${WORKSPACE:-.}`**）拼 **`tee` 日志路径**（见 §7），属于**运行时路径**，随 Agent/任务变化，对看板无稳定业务语义；**`build_url` 已能唯一定位本次构建**，故**不**把 `WORKSPACE` 设计成表字段。若二期要做「工作区审计」再单独加列。

**唯一约束**：`UNIQUE KEY uk_idempotency (idempotency_key)`，避免同一构建重复 INSERT。

**`idempotency_key` 说明（做什么用）**

- Jenkins 上报可能因 **超时重试、网络抖动、脚本重复调用** 而多次 `POST` **同一构建**；若无幂等设计，库内会出现多条「同一 `job_name` + `build_number`」的记录，统计会被放大。  
- 客户端为**每一次构建**生成一个稳定字符串：**优先**使用 Jenkins **`BUILD_TAG`**（通常为 `job_name-build_number`，在单控制器内可唯一标识一次构建）；或使用 `sha256(job_name + "\0" + str(build_number))` 的 hex（**不**依赖 commit，与本期表结构一致）。  
- 服务端以 **`idempotency_key`** 做 **UNIQUE**：第二次相同 key 的请求返回 **200** 且返回已有记录（或 **409**，见 §6.1），**不**再插入新行。

**`is_intercepted` 与业务用语**

| `is_intercepted` | 含义 |
|------------------|------|
| **true**（1） | **拦截到**：合法 Summary，且存在失败用例 |
| **false**（0） | **非拦截**（混合）：含「未拦截」、无 Summary、前置失败、解析失败等，**库内不区分** |

### 5.2.1 数据来源规约：100% 不依赖「未定义 / 未约定」环境变量（本期）

**目标**：上报脚本在任何 Agent 上不因「变量未注入」而报错或写入脏数据；**拿不到就不传或可空**，**绝不**假设 `VAR` 一定存在。

**A 类——Jenkins 核心变量（视为默认可用；若极端环境缺失须有降级）**

| 变量 | 用途 | 缺失时 |
|------|------|--------|
| `JOB_NAME` | `job_name` | 视为异常，不应继续上报（或记录错误日志） |
| `BUILD_NUMBER` | `build_number` | 同上 |
| `BUILD_URL` | `build_url`；并可**解析**出 `jenkins_base_url`（见下） | 同上 |
| `BUILD_TAG` | **`idempotency_key` 首选** | 改用 `sha256(JOB_NAME + "\0" + BUILD_NUMBER)` 等**纯 A 类变量**计算 |
| `WORKSPACE` | `tee` 日志路径（如 `"$WORKSPACE/.ci/ut_console.log"`） | 降级为 `"${WORKSPACE:-.}/.ci/..."` 或当前目录（须在试点验证） |

**禁止**将下列变量当作「一定存在」写入上报逻辑（除非落入 B 类且已判空）：`JENKINS_URL`、`GIT_*`、`CI_*` 等未列入本节的通用名。

**B 类——CodeHub 插件变量（本期已固化，仅此一项）**

| Jenkins 变量名 | 映射到请求体 / 表字段 | 使用前 |
|----------------|----------------------|--------|
| **`codehubMergeRequestUrl`** | **`mr_url`** | **`[ -n "${codehubMergeRequestUrl:-}" ]`** 为真则赋值；否则 **省略 `mr_url` 键** 或 **`null`**（非 MR 触发等） |

- **本期**：**仅**允许通过 **`codehubMergeRequestUrl`** 填充 **`mr_url`**；**不采用** `.ci/mr_url.txt`、**不采用**从 Console / `consoleText` 解析 MR 链接作为默认路径（二期若变更须改本节）。  
- **禁止**在脚本中再引用其它未列入 **A / B 类**的变量名填充 `mr_url`。

**`jenkins_base_url`（可空）**

- **不得**依赖 `JENKINS_URL`。  
- **推荐**：从 **`BUILD_URL`** 用 shell 解析出 **scheme + host（+ 固定 port）**（例如 `https://jenkins.example.com`），解析失败则 **JSON 中省略 `jenkins_base_url`** 或显式 `null`。

**`mr_url`（可空）**

- **本期**：**仅**来自 **`codehubMergeRequestUrl`**（见上表），与 Webhook **`object_attributes.url`** 语义一致，由 CodeHub 插件注入。  
- **非 MR / 变量为空**：不传 `mr_url` 或 `null`。

**`is_intercepted` / `ut_exit_code`**

- **仅**依赖 **`tee` 落盘日志**与 **`PIPESTATUS[0]`**（或等价），**不**依赖任何 MR/Git 环境变量。

**API / 后端**

- `id`、`created_at`、`updated_at`、`reported_at` 由服务端或数据库生成，**不要求**客户端从环境变量推导。

### 5.3 索引（支持看板查询）

| 索引 | 字段 | 用途 |
|------|------|------|
| `idx_created_at` | `created_at` | 时间范围筛选、列表排序；**二期**若做趋势统计可复用 |
| `idx_mr_url_created` | `mr_url`(191), `created_at` | 按 MR 链接聚合、列表筛选；**`mr_url` 为前缀索引**（MySQL 5.7 utf8mb4 单索引字节上限 3072，全列 `VARCHAR(1024)` 会报 ERROR 1071） |
| `idx_is_intercepted_created` | `is_intercepted`, `created_at` | 列表按拦截状态筛选；**二期**若做分布/趋势可复用 |
| `idx_job_build` | `job_name`, `build_number` | 对账、去重辅助 |

### 5.4 MR 标识（规约）

- **本期仅使用 `mr_url`**：完整 MR 页面 URL 一般已包含 **项目路径 + `merge_requests/<id>`**，**全局可区分不同 MR**，无需再存 `mr_id`、源/目标分支。
- **多仓（已确认）**：不同仓库、不同 MR 的 URL **路径不同**，**仅凭 `mr_url` 即可区分多仓与多 MR**，**不需要**再增加仓库键、`job_name` 等与「仓」绑定的额外字段作区分；每个仓库各自 MR → **各自一条 `mr_url`**，多条构建多行上报；看板按 **`mr_url` 去重** 即按「单仓 MR」统计；若需把多个 MR URL 合成「同一需求」，属 **二期或平台侧关联**，本期不存额外字段。
- **取值来源**：**仅** §5.2.1 **B 类** **`codehubMergeRequestUrl`**（判非空后写入 `mr_url`）。
- **`mr_url` 为空**：非 MR 触发的构建可不报；看板「按 MR」统计时 **排除** `mr_url` 为空的记录，或单独展示「无 MR 关联」。

---

## 6. 问题 4：API 接口设计

### 6.1 写入：上报单次门禁结果

**POST 实现细则**（请求/响应字段、幂等 200/409、鉴权配置、日志）见 **`spec/16_ut_gate_report_post_api_spec.md`**。

| 项目 | 规约 |
|------|------|
| 路径 | `POST /api/v1/ut-gate-runs` |
| Content-Type | `application/json` |
| 认证 | **必须**；**本期仅采用** **固定集成 Token**：HTTP 头 **`Authorization: Bearer <token>`**。**`token`** 由 QualityBoard 配置（如环境变量），Jenkins 经 **Credentials** 注入为环境变量后写入请求头；**禁止**硬编码进仓库脚本。**本期不采用** HMAC + 时间戳、OAuth 用户态；**禁止**将 UT 门禁写入接口与用户登录 Cookie 混用。 |
| 幂等 | 请求体带 `idempotency_key`（**含义与生成**见 §5.2）；**实现口径**见 **`spec/16_ut_gate_report_post_api_spec.md` §5**（重复且一致 → **200**；同键不同内容 → **409**）。 |

**`idempotency_key` 生成建议**：**首选** Jenkins **`BUILD_TAG`**；否则使用 `sha256(job_name + "\0" + str(build_number))` 的 hex（同一 Job 下 **`build_number` 单调递增**，与 `job_name` 组合可区分每次构建）。

**请求体（JSON）示例字段**（与表字段对应，蛇形命名，与前端/后端 Schema 一致）：

- 必填：`idempotency_key`, `job_name`, `build_number`, `is_intercepted`（布尔：`true` / `false`）  
- **建议**：`mr_url`（**仅当** **`codehubMergeRequestUrl`** 非空时**等于该变量值**）、`ut_exit_code`（整数，可空）、`build_url`（来自 `BUILD_URL`）、`jenkins_base_url`（来自 **`BUILD_URL` 解析**，失败则省略）；**须满足 R5 / §5.2.1**  

**响应**：`201 Created` 返回写入记录 ID 与主要字段；幂等命中返回 `200 OK`。

### 6.2 查询：列表与聚合（看板）

**列表 GET 实现细则**（查询参数、时间语义、`reported_at` 筛选、`mr_url`/`job_name` 匹配、分页、权限）见 **`spec/17_ut_gate_runs_get_api_spec.md`**。

**认证（分场景）**：**Jenkins → `POST`** 使用 **`Authorization: Bearer <固定集成Token>`**（见 §6.1、**`spec/16`**）。**浏览器 → `GET` 列表** 使用 **用户登录态（JWT）**，**不得**在浏览器持有集成 Token；细则见 **`spec/17` §3**。**本期不采用** HMAC。  
**看板前端**：列表数据经 **`GET /api/v1/ut-gate-runs`** 由已登录前端调用后端，后端直读库；与主 spec 原「服务端代调」表述等价（**不**经浏览器携带集成 Token）。  
**「UT门禁历史」权限（已确认）**：**全员可见**——凡**已登录**本系统的用户均可访问该菜单及列表数据（不因角色隐藏）；仍依赖应用整体登录与内网部署。

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/ut-gate-runs` | GET | 分页列表；筛选与排序见 **`spec/17_ut_gate_runs_get_api_spec.md` §4～§5**（`start_time`/`end_time` 绑定 **`reported_at`**；`is_intercepted`；`mr_url` 精确与 `mr_url_contains` 子串互斥；`job_name_contains`） |
| `/api/v1/ut-gate-runs/stats` | GET | 聚合：按日/周 **`is_intercepted=true` 次数**、**`false` 次数**（`false` 为混合口径）；可选 **按 `job_name`** 分布（参数：`granularity`, `start_time`, `end_time`）；**本期不按仓库 URL / commit / MR 分支** 维度存库（无 `git_remote_url`、`git_commit_sha`、`source_branch`/`target_branch`）；**stats 首期可不实现**，见 **`spec/17` §11** 与 §8.2 |

### 6.3 异常与错误码

| HTTP | 场景 |
|------|------|
| 400 | JSON 非法、缺少必填字段、枚举非法 |
| 401/403 | 认证失败 |
| 409 | 幂等键冲突且载荷不一致（若采用严格策略） |
| 422 | 业务校验失败（如字段类型非法、与服务端约定规则冲突等；**本期**对 `is_intercepted` 的真假以 **Jenkins 脚本解析结果为准**，服务端可不做强校验） |
| 500 | 服务端/数据库异常（须 `logger.exception`，不落敏感信息） |

**Jenkins 侧**：任意 4xx/5xx **仅记录日志**，不改变门禁退出码。

---

## 7. 问题 5：root.sh 改造要点

### 7.1 插入位置（逻辑顺序）

1. 在调用 `cargo make test` **之前**：确保目录存在，准备日志文件路径。  
2. **执行测试**：`cargo make test 2>&1 | tee "${WORKSPACE:-.}/.ci/ut_console.log"`（路径须与 §5.2.1 **`WORKSPACE` 降级**一致）；**同时**保存 **`PIPESTATUS[0]`**（或等价）为 `UT_EXIT_CODE`。  
3. **在现有成功/失败判定与 `exit` 之前或之后**（须在**同一 shell** 可拿到退出码处）：调用上报函数 `report_ut_gate`（内部 `curl`，`|| true`）。  
4. **保持原有** `exit` 逻辑**不变**（仍以门禁规则为准）。

### 7.2 Summary 解析

- 从 **`${WORKSPACE:-.}/.ci/ut_console.log`**（与 §7.1 路径一致）读取匹配 **`Summary [`** 的行（**本期约定**：日志中**仅一行** Summary，直接取该行即可；实现上亦可保留「取最后一行匹配」以防御偶然重复输出）。  
- 根据该行：**存在失败用例** → 上报 **`is_intercepted: true`**；**否则**（含合法 Summary 无失败）→ **`is_intercepted: false`**。  
- 若**无合法 Summary** 或无法解析：**一律** **`is_intercepted: false`**；**不得**仅凭退出码非 0 置 **`true`**。同时上报 **`ut_exit_code`**（`PIPESTATUS[0]`）便于排查。

### 7.3 失败时是否上报

**是**。只要门禁流程走到「测试已执行完毕」，均应上报 **`is_intercepted`**（及 **`idempotency_key`**、**`job_name`**、**`build_number`** 等必填项）与建议的 **`ut_exit_code`**；**`mr_url`** 仅当 **`codehubMergeRequestUrl`** 非空时填写。  
**未执行测试就中断**（如克隆失败）：是否仍 `POST` 由 **Jenkins 侧策略**自定（**不影响**门禁结论）；**本期不提供** **`error_message`** 上报字段，亦**不在** `ut_gate_run` 表扩展该列。

---

## 8. 问题 6：看板展示维度

### 8.1 维度（本期以列表呈现为主）

| 维度 | 本期在「UT门禁历史」页的用法 |
|------|------------------------------|
| 时间 | 表格列 **`created_at` / `reported_at`**（与 §5.2 一致），支持时间范围 **筛选**、分页排序；**不做**按日/周聚合图表 |
| MR | 列 **`mr_url`**（可外链 CodeHub）、列 **`is_intercepted`**；同一 MR 多行构建以多行展示，**不做** MR 维度合并小计图表 |
| Job | 列 **`job_name`**、**`build_number`** 等；**不做** Job 占比饼图 |

### 8.2 图表（本期不做）

- **本期**：**不实现** ECharts（**无**趋势图、柱状图、饼图等）；**不在系统首页**展示 UT 门禁相关图表或汇总卡片。  
- **二期（可选）**：可恢复趋势/分布类图表（例如按日拦截次数、`job_name` 占比等），与 §6.2 `stats` 接口能力配套后再做。

### 8.3 与现有系统关系：菜单与路由

- **菜单位置**：与 **「详细执行历史」**（现有 `/history` 所在主导航层级）**同级**，新增一项，菜单文案：**「UT门禁历史」**。  
- **路由**：建议 **`/ut-gate-history`**（与 **`/history`** 并列顶层路径；实现时若需微调须保持「与详细执行历史同级」语义，并在路由表中登记）。  
- **页面内容**：**仅** Ant Design **`<Table>`** + 筛选条件 + 分页，对接 **`GET /api/v1/ut-gate-runs`**；行内可链 **`build_url`** / **`mr_url`** 跳转 Jenkins / CodeHub。**本期页面不引入 ECharts**。**前端实现级规约**见 **`spec/18_ut_gate_history_frontend_spec.md`**。  
- **首页**：**不**增加 UT 门禁图表或专用卡片；用户经 **「UT门禁历史」** 菜单进入列表即可。

### 8.4 核心指标：按 MR 去重（不依赖是否合入）

- **指标语义（推荐）**：时间窗内，**至少出现过一次 `is_intercepted=true`** 的 MR 占比——**分子** = 曾 **`true`** 的 **不同 `mr_url`** 数（**须** `mr_url` 非空）；**分母** = 时间窗内 **`mr_url` 非空** 且至少有一条上报记录的 **不同 `mr_url`** 数。  
- **局限**：因 **`is_intercepted=false` 混合多种语义**，分母**包含**「从未 Summary 可判定仅 false」的 MR 时，比例解读偏「宽」；若业务要求分母仅限「Summary 可判定」的 MR，须**二期**增加「可判定」标志字段，或**约定**仅在测试跑完且可解析时上报。  
- **逻辑 MR 键**：**仅** **`mr_url`**（建议服务端或上报端做 **URL 规范化**：去 fragment、统一 host 大小写规则等，**待实现约定**）。  
- **比例**：分子 ÷ 分母。同一 **`mr_url`** 多次构建仅影响「是否曾 **`true`**」，**每个 `mr_url` 在分母中最多计一次**。  
- **`mr_url` 为空** 的构建：不参与本 MR 指标分子/分母，或单独统计「无 MR 关联构建」。

---

## 9. 安全与运维

- **鉴权方式**：**固定集成 Token** + **`Authorization: Bearer`**（见 §6.1、§6.2）；**本期不采用** HMAC。  
- **「UT门禁历史」**：**全员可见**（见 §6.2）；应用仍须登录、内网访问。  
- Token 存放在 **Jenkins Credentials**，注入为环境变量（如 `QUALITYBOARD_UT_REPORT_TOKEN`）。  
- 服务端对 Token **轮换**友好：支持双 Token 过渡期（**可选实现**）。  
- 限流：按 IP 或 Token **QPS 限制**，防止误配置死循环打满服务。  
- 审计：上报成功打 **INFO**（含 `idempotency_key`、`job_name`、`build_number`，不含 Token）。

---

## 10. 已确认决策（原开放问题关闭）

| 原编号 | 决策 |
|--------|------|
| 1（B 类 / `mr_url`） | **`mr_url` 仅由 `codehubMergeRequestUrl` 赋值**（判非空），已写入 **§5.2.1**、§5.4、§6.1、§7.3。 |
| 2（`mr_url` 备选） | **不采用** `.ci/mr_url.txt` 等文件备选；**仅用 B 类变量**。 |
| 3（多仓） | **仅凭 `mr_url` 区分多仓 / 多 MR**即可，**不增加**其它区分字段（见 §5.4）。 |
| 4（Summary） | **约定仅一行 Summary**，**不出现多行**；解析见 §3.3、§7.2。 |
| 5（权限） | **「UT门禁历史」全员可见**（已登录用户均可访问菜单与数据）；见 §6.2、§9。 |
| 6（`error_message`） | **不需要**；**本期不提供**该上报字段，**不扩展**表字段（见 §7.3）。 |

**本期无未决开放项**；若工具链或 CodeHub 插件行为变更，须修订 §3.3、§5.2.1、§7.2 并更新本表。

---

## 11. 文档与实现检查清单（后续迭代用）

**推荐实现顺序**见 **§12**（分阶段计划与 PR 切分）。

- [ ] 新增 `database/V*.*.*__create_ut_gate_run.sql` 与 ORM/Schema/Service/API  
- [x] **`GET /api/v1/ut-gate-runs`** 分页列表：见 **`spec/17_ut_gate_runs_get_api_spec.md`**  
- [ ] Jenkins 侧：Credentials、`curl` 示例、`tee` + `PIPESTATUS` 试点；**`codehubMergeRequestUrl` → `mr_url`**（§5.2.1 **B 类**）按规约接入  
- [ ] 联调：幂等、超时（`curl --max-time`）、DNS  
- [x] 前端：**「UT门禁历史」**菜单（与详细执行历史同级）+ 路由 **`/ut-gate-history`** + 列表页（**无图表**）；**全员可见**（已登录用户）；`utGateApi` 服务封装（**细则见 `spec/18_ut_gate_history_frontend_spec.md`**，**§10 已实现**）  
- [ ] 更新 `docs/` 中架构/接口说明（若有对外部署）

---

## 12. 分阶段实现计划（推荐）

本节约定 **QualityBoard 与 Jenkins 侧** 的落地顺序，与项目分层 **Model → Schema → Service → API** 一致；**不必**引入新的顶层工程子项目，在现有 `backend/models`、`schemas`、`services`、`api/v1` 下为本需求新增一组文件并注册路由即可。

### 12.1 为何分阶段

- **依赖链固定**：须先有迁移 SQL 与 ORM，再写 Service/API；前端依赖稳定接口。
- **验收清晰**：每阶段有可独立验证的交付物（库表、POST 幂等、GET 分页、页面、端到端联调）。
- **与检查清单对应**：§11 勾选项可按 §12 阶段逐项完成。

### 12.2 阶段与验收标准

| 阶段 | 内容 | 验收标准（建议） |
|------|------|------------------|
| **1. 数据层** | `database/V*.*.*__create_ut_gate_run.sql`；`UtGateRun`（或等价命名）ORM；字段与本文 **§5** 一致；**禁止** `create_all` | 迁移在目标环境执行成功 |
| **2. 上报 API** | 请求 Schema、Service（含 **`idempotency_key` 幂等**）、`POST` 路由；**集成 Bearer** 校验；日志符合 `docs/06_logging_guide.md` | 同 key 重复上报不产生重复行；未授权/参数错误返回 4xx |
| **3. 查询 API** | 列表 Query Schema、`select` 分页与计数、`GET` + `PageResponse` | 与项目内其它列表接口行为一致 |
| **4. 前端** | `frontend/src/services` 下 **`utGateApi`**（字段 **snake_case** 与后端一致）；路由 **`/ut-gate-history`**；**「UT门禁历史」**菜单（全员可见，见 §6.2、§9）；列表页，**本期无图表** | 已登录用户可访问列表与分页；**实现见 `spec/18_ut_gate_history_frontend_spec.md` §10（v1.1）** |
| **5. Jenkins 侧** | Credentials、**`curl --max-time`**、**`tee` + `PIPESTATUS`**（或等价）；**`codehubMergeRequestUrl` → `mr_url`**（§5.2.1 **B 类**） | 试点 Job 端到端产生一条符合预期的库记录 |

**文档**：`docs/` 中架构/接口说明在**功能对外可用**的版本与代码同步更新即可，无需每个小改动都改文档。

### 12.3 PR 切分建议（可压缩）

| PR | 范围 |
|----|------|
| **PR1** | 迁移 SQL + ORM（+ 若需 Pydantic 仅用于内部校验可随 PR2，避免空转） |
| **PR2** | POST 上报（认证、幂等、日志） |
| **PR3** | GET 分页列表 |
| **PR4** | 前端 + `pnpm build` / 部署流程按仓库脚本执行 |

单人开发时可合并为 **「数据库 + 后端」** 与 **「前端」** 两个 PR，但**不建议**省略迁移或把迁移与大量无关逻辑混在同一提交。

### 12.4 不必单独成「模块」的部分

- **Summary 解析**：放在 **Service** 层（或同目录下小工具函数文件），无需单独 Python 包。
- **Jenkins 流水线脚本**：若不在本仓，以本文 **§7** 与运维侧仓库/片段为准，QualityBoard 仓内不强制新建脚本目录。

---

## 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-05-07 | 初稿：采集、存储、API、表结构、看板与 root.sh 集成要点 |
| v0.2 | 2026-05-07 | §1.1：无合法 Summary 且退出码非 0 不等同于 UT 未通过；同步 §1.2、§3.3、§5.2、§6.3、§7.2、§8 口径 |
| v0.3 | 2026-05-07 | 新增 §5.4（多仓与 MR ID 作用域）、§8.4（按逻辑 MR 去重指标）；`mr_id` 字段说明与 §10 引用更新 |
| v0.4 | 2026-05-07 | §1.2/§1.3：业务以「是否出现失败用例」为主，用例计数改为可选；同步 §3.3、§5.2、§6.1、§6.3、§7 |
| v0.5 | 2026-05-07 | 业务语义改为「拦截/未拦截」：`ut_status` 枚举 **`intercepted`** / **`not_intercepted`** 替代 passed/failed；全文与 §8.4 指标语义对齐 |
| v0.6 | 2026-05-07 | §3：本期**仅采用方案 B**，取消与方案 A 的配合及对账同步；§3.1 增「本期」列、§3.2 改为实现要点 |
| v0.7 | 2026-05-07 | §5.2：`mr_title` 及 `ut_exit_code` 之后字段删除；`ut_status` 改为布尔 **`is_intercepted`**（仅 Summary 可判定且存在失败为 true，其余 false）；**`idempotency_key`** 前移并专段说明；全文与 §8 统计局限同步 |
| v0.8 | 2026-05-07 | MR 维度**仅保留 `mr_url`**；删除 `mr_id`、`source_branch`、`target_branch`；§5.3/§5.4、§6、§8、§10 同步 |
| v0.9 | 2026-05-07 | 删除 **`git_remote_url`**、**`git_commit_sha`**；**`idempotency_key`** 改为依赖 **`BUILD_TAG`** 或 **`job_name`+`build_number`**；§1.2、§6、§8 与幂等说明同步 |
| v1.0 | 2026-05-07 | 新增 **R5**、**§5.2.1**：**100% 不依赖未定义环境变量**；`jenkins_base_url` 从 **`BUILD_URL` 解析**；**B 类**契约白名单；§5.4、§6.1、§7、§10、§11 同步 |
| v1.0.1 | 2026-05-07 | §5.2：补充说明 **`WORKSPACE` 仅 §5.2.1 / §7 使用、不入库** |
| v1.1 | 2026-05-07 | **认证定稿**：**固定集成 Token** + **`Authorization: Bearer`**；写入/查询一致；**不采用** HMAC；§6.1、§6.2、§9 同步 |
| v1.2 | 2026-05-07 | §8：**本期不做图表**、**首页不展示** UT 图表；菜单 **「UT门禁历史」** 与详细执行历史**同级**，路由建议 **`/ut-gate-history`**；§8.1–§8.3 重写；§1.2、§5.3 索引说明、§11 同步 |
| v1.3 | 2026-05-07 | **B 类**固化为 **`codehubMergeRequestUrl`→`mr_url`**；多仓仅 **`mr_url`**；Summary **单行**；**全员可见**；**无 `error_message`**；§10 改为已确认表；§3.2–§3.3、§5.2.1、§5.4、§6–§9、§11 同步 |
| v1.3.1 | 2026-05-07 | **R5**、表字段 `jenkins_base_url` 与 §5.2.1 对齐（不引用外部「CI 契约」）；§11 前端项补充 **全员可见** |
| v1.4 | 2026-05-07 | 新增 **§12 分阶段实现计划**（阶段表、验收、PR 切分、非单独模块说明）；§11 增加对 §12 的引用 |
| v1.5 | 2026-05-07 | §6.1：POST 细则引用 **`spec/16_ut_gate_report_post_api_spec.md`**；幂等行为与 §16 对齐 |
| v1.6 | 2026-05-07 | 新增 **`spec/17_ut_gate_runs_get_api_spec.md`**（GET 列表）；§6.2 认证分场景（POST 集成 Token / GET 用户 JWT）、筛选与 stats 说明对齐 §17 |
| v1.7 | 2026-05-07 | §11：`GET` 列表检查项已落地；与 **`spec/17` v1.1** 同步 |
| v1.8 | 2026-05-07 | §8.3、§11、§12.2：**前端**细则引用 **`spec/18_ut_gate_history_frontend_spec.md`** |
| v1.9 | 2026-05-07 | §11：前端项注明 **`spec/18` §10** 已落地代码；部署侧仍需 `pnpm build` |
| v1.10 | 2026-05-12 | §5.3、`V1.1.2` DDL：**`idx_mr_url_created`** 改为 **`mr_url`(191)** 前缀索引，避免 MySQL 5.7 utf8mb4 **ERROR 1071** |
