# 一键通知（Bug 失败跟踪人 · WeLink）功能规约（Spec）

本文档在 `spec/02_history_fields_spec.md`、`spec/03_history_failure_reason_spec.md`、`spec/07_history_filter_query_spec.md`、`spec/11_one_click_batch_analyze_spec.md` 基础上，定义「一键通知」的交互、数据范围、WeLink 消息内容与 API 规约。

**文档位置说明**：与「一键分析」同属详细执行历史上的批量能力，触发方式对齐 `spec/11`，编号顺延为 `13`。

---

## 1. 功能概述

### 1.1 功能目标

在某一**轮次（批次）内，针对失败类型为 bug** 且已落库失败归因的用例，按 `**pipeline_failure_reason.owner`（失败跟踪人）** 聚合人数与条数，通过 **WeLink 卡片消息**通知各跟踪人：该轮次下其名下有多少条 bug 失败用例待跟进；消息中附带**直达详细执行历史**的链接，链接上预置筛选条件（批次、跟踪人、失败原因 = bug）。

**业务背景**：轮次执行结束且失败用例已分析完成后，需要主动提醒「失败原因为 bug」的跟踪人处理名下失败。

### 1.2 与「一键分析」的关系


| 维度         | 一键分析（`spec/11`）                            | 一键通知（本文档）                                                                                  |
| ---------- | ------------------------------------------ | ------------------------------------------------------------------------------------------ |
| 触发         | 勾选 ≥1 条失败/异常行 → 点「一键分析」                    | **相同**：勾选 ≥1 条失败/异常行 → 点「一键通知」                                                             |
| 锚点         | `anchor_history_id` → 解析 `start_time`      | **相同**                                                                                     |
| 作用范围       | 该 `start_time` 下未分析的 failed/error 整批写入 bug | **不同**：该 `start_time` 下**已关联** `pfr` 且 `**failed_type` = bug** 的记录，**按 owner 聚合后发 WeLink** |
| 数据写入       | 写入/更新 `pipeline_failure_reason`、`analyzed` | **不写**业务表；仅调用外部 WeLink（及日志）                                                                |
| 锚点是否须「未分析」 | **须** `analyzed` 为 0/NULL                  | **否**（场景为分析完成之后；锚点可为已分析记录）                                                                 |


### 1.3 适用页面

- **详细执行历史**页面（与「一键分析」「分析处理」「继承失败原因」一致）。

---

## 2. 批次界定（与 spec/11 一致）

- **不按 `subtask` 切分**。
- 以锚点记录的 `**pipeline_history.start_time`** 作为**唯一批次键**。
- 后续统计与发信均只包含 `**start_time` 等于该批次键** 的数据。

---

## 3. 统计与通知对象（候选集）

### 3.1 纳入聚合的记录需同时满足


| 条件                           | 说明                                                                                                        |
| ---------------------------- | --------------------------------------------------------------------------------------------------------- |
| `ph.start_time`              | 等于锚点批次 `start_time`                                                                                       |
| `ph.case_result`             | `'failed'` 或 `'error'`（与失败归因语义一致）                                                                         |
| 存在 `pipeline_failure_reason` | 与 `(ph.case_name, ph.platform, ph.start_time)` 按执行键关联，`pfr.failed_batch = ph.start_time`                  |
| `pfr.failed_type`            | 与 `**case_failed_type`** 表中代表 **bug** 的字典 `**failed_reason_type` 实际存储值**一致（大小写与库一致，与 `spec/11` §5.2 相同原则） |
| `pfr.owner`                  | **非空**（失败跟踪人；存储格式一般为 `**{姓名} {工号}`**，半角空格，与 `spec/11` §5.1 写入格式一致）                                        |


### 3.2 可选加强（与产品确认后写入实现）

- `**ph.analyzed = 1**`：若业务上要求「仅通知已完成分析的轮次数据」，可增加此条件，与「分析完成后再通知」一致。

### 3.3 聚合规则

- 按 `**pfr.owner` 原文字符串**分组（**不做** trim 归一化；历史数据若同一人工号多种写法，会拆成多组，需数据治理侧处理）。
- 每组统计 **用例条数** `count`，作为消息正文中的 **x**。

### 3.4 去重发送

- 每个 `**pfr.owner` 分组**至多发送 **1 条** WeLink 消息（该组条数为聚合后的 `count`）。

---

## 4. 失败跟踪人 → 域账号（`ums_email`）

### 4.1 字段语义（与现网表一致）


| 来源                        | 字段               | 说明                                               |
| ------------------------- | ---------------- | ------------------------------------------------ |
| `pipeline_failure_reason` | `owner`          | 失败跟踪人展示串，一般为 **姓名+工号**，如 `小红 00123456`           |
| `ums_email`               | `employee_id`    | **工号**，如 `00123456`                              |
| `ums_email`               | `domain_account` | **域账号**，WeLink 发送所需，一般为 **首字母+工号**，如 `x00123456` |


### 4.2 工号解析规约

- 从 `pfr.owner` 解析 `**employee_id`**，与 `**ums_email.employee_id**` 匹配。
- **默认策略**（与 `spec/11` 展示格式一致）：`owner` 为 `**{姓名} {工号}`** 时，取 **最后一个半角空格之后**的子串作为工号；若无法解析出非空工号，该分组 **不发送**，计入 **「解析失败」**清单。

### 4.3 发送条件

- 存在 `ums_email` 行且 `**domain_account` 非空**（非 `NULL`、非仅空白）：使用该值作为 WeLink 的 `**user`**。
- **否则**：该分组 **不发送**，计入 **「未配置域账号」清单，响应中给出明确中文说明，提示管理员在数据库 `ums_email` 中补全该员工的 `domain_account`**（表为人工维护，未配置则无法发消息）。

---

## 5. WeLink 消息内容

调用封装方法（见第 8 节占位说明）：

`rolling_welink_share(user, content, remark, url)`


| 参数        | 取值                                     |
| --------- | -------------------------------------- |
| `user`    | `ums_email.domain_account`（须已配置）       |
| `content` | 固定标题：`**rolling线防护通知**`                |
| `remark`  | `**您好，在{轮次}轮次，您名下共有{n}条用例失败，请及时分析处理**` |
| `url`     | 见 §5.1                                 |


其中：

- `**{轮次}**`：与 `**spec/11` §5.3** 一致，使用锚点批次 `**start_time` 字符串原样代入**（示例：`在202601201730轮次…`）。
- `**{n}`**：该 `owner` 分组在 §3 规则下的 **用例条数**。

### 5.1 链接 `url` 规约

- **路径**：前端详细执行历史为 `**/history`**（与现网路由一致；完整 URL 需带站点根地址）。**后端发卡片**时使用环境变量 `**PUBLIC_APP_URL**`（无尾部 `/`）与 `urllib.parse.urlencode` 拼接绝对链接；部署时须在 `.env` 中配置，未配置则接口 **400** 提示无法生成链接。
- **Query**（与列表筛选、URL 同步参数一致，见 `HistoryPage` / `spec/07`）：


| 参数              | 值                           | 说明                                                                                   |
| --------------- | --------------------------- | ------------------------------------------------------------------------------------ |
| `start_time`    | 锚点 `start_time`（单次批次，一个值）   | 与列表「批次」筛选一致                                                                          |
| `failure_owner` | 当前收件人对应的 `**pfr.owner` 全文** | 与 API/前端字段名 `**failure_owner`** 一致（**不是** `failed_case_owner`）；值须 **URL 编码**（含中文、空格） |
| `failed_type`   | 与 §3.1 相同的 **bug 字典值**      | 与列表「失败原因」筛选一致                                                                        |


示例（仅说明结构，实际须编码）：

`https://{host}/history?start_time={batch}&failure_owner={encoded_owner}&failed_type={bug}`

多值筛选在列表中为数组；此处每人一条链接，**单值**即可。

---

## 6. 入口与交互

### 6.1 操作路径

1. 用户勾选 **至少 1 条** `case_result` 为 `failed` 或 `error` 的记录（与「一键分析」可选行范围一致，规约建议与 `spec/11` §3.2 相同）。
2. 点击 **「一键通知」**（文案以 UI 为准）。
3. 前端提交 `**anchor_history_id`**（与 `spec/11` §7.1 相同字段语义），后端解析批次并执行 §3～§5。

### 6.2 多选锚点

- 若勾选多条：前端任选 **一条** 的 `id` 作为 `anchor_history_id`（**建议取勾选集合中的第一条**，与 `spec/11` §3.3 一致）。
- **跨批次校验**：若勾选多条且 `**start_time` 不一致**，前端应 **禁止提交** 并提示 **「请选择同一轮次的用例」**（避免误用错误批次）；后端亦应校验锚点与（若上传）勾选列表批次一致性，**不一致则 400**。

### 6.3 按钮可用条件（建议）


| 状态  | 条件                        |
| --- | ------------------------- |
| 可用  | 至少勾选 1 条 `failed`/`error` |
| 禁用  | 未勾选或勾选行均为非失败/异常           |


权限：与一键分析一致，**需登录**；是否仅管理员可点由权限模型决定（实现阶段与现网 `one-click-analyze` 权限对齐）。

---

## 7. 锚点校验

后端对 `anchor_history_id` 校验如下，不通过返回 **400** 及明确中文 `detail`：


| 校验项                                | 失败提示（示例）      |
| ---------------------------------- | ------------- |
| 记录存在                               | 「锚点记录不存在」     |
| `case_result` 为 `failed` 或 `error` | 「锚点须为失败或异常用例」 |


**说明**：**不要求** `analyzed = 0`（与 `spec/11` §4 刻意不同）。

可选：若前端传入 `selected_history_ids` 用于批次一致性校验，则所有 id 对应行的 `start_time` 须与锚点相同，否则 **400**：「所选记录须属于同一轮次」。

---

## 8. WeLink 集成（`rolling_welink_share`）

- 业务代码中 **统一调用** `**backend.integrations.welink_card.rolling_welink_share(user, content, remark, url)`**，返回 **`(bool, str)`**（是否成功、中文说明）。兼容别名 `**rolling_welink_alert**`（黄区旧名）。
- **配置**：与黄区 `testvigil/tuil/welink_card` 相同，使用 **独立 INI**（`login_*` / `share_*` 等 section）。仓库内仅保留模板 `**config/welink_card.ini.example**`；部署时将真实文件放在服务器（如 `/etc/dt-report/welink_card.ini`），并通过环境变量 `**WELINK_CARD_INI_PATH**` 指向该文件（见 `backend/core/config.py`、`.env.example`）。
- **禁止**在代码中硬编码登录口令、URL、`resourceId` 等敏感项；未设置 `WELINK_CARD_INI_PATH` 或文件不可读时，函数返回失败说明，由上层计入发送失败。
- **实现说明**：黄区原 `share.py` 中 `resp.share_data != 200` 为笔误，已纠正为 `**resp.status_code**`；HTTP 使用项目已有 `**httpx**`，不新增 `requests` 依赖。
- 调用失败时打 **`logger.exception`**（或 WARNING，视场景）；日志中 **禁止**打印密码与完整 Cookie。

---

## 9. API 设计

### 9.1 请求


| 属性  | 规约                                                                                   |
| --- | ------------------------------------------------------------------------------------ |
| 方法  | `POST`                                                                               |
| 路径  | 建议 `**/api/v1/history/one-click-bug-notify`**（与 `one-click-analyze` 并列；实现时可微调，须独立路径） |
| 认证  | 需登录                                                                                  |


**请求体（JSON）**


| 字段                     | 类型      | 必填  | 说明                                                 |
| ---------------------- | ------- | --- | -------------------------------------------------- |
| `anchor_history_id`    | `int`   | 是   | 锚点 `pipeline_history.id`，用于解析 `start_time` 及 §7 校验 |
| `selected_history_ids` | `int[]` | 否   | 若传则用于 **同批次校验**（§6.2）；不传则仅校验锚点                     |


### 9.2 响应（建议）


| 字段                          | 类型       | 说明                                                                                             |
| --------------------------- | -------- | ---------------------------------------------------------------------------------------------- |
| `success`                   | `bool`   | 是否整体完成（无未捕获异常）                                                                                 |
| `message`                   | `string` | 中文总体说明                                                                                         |
| `batch`                     | `string` | 本批 `start_time`                                                                                |
| `notified_count`            | `int`    | **成功发出** WeLink 的跟踪人人数（分组数）                                                                    |
| `skipped_no_domain_count`   | `int`    | **未配置或非空 `domain_account`** 无法发送的分组数                                                           |
| `skipped_parse_owner_count` | `int`    | **无法从 `owner` 解析工号** 的分组数                                                                      |
| `failed_delivery_count`     | `int`    | 可选：调用 WeLink 接口失败的分组数                                                                          |
| `details`                   | `object` | 可选：管理员排查用，如 `skipped_owners: string[]`、`failed_owners: { owner, reason }[]`（注意脱敏与体积，可仅返回前 N 条） |


当候选集中 **无任何 bug 分组** 时：返回 **200**，`message` 说明「本批次无失败类型为 bug 的跟踪记录」等，`notified_count = 0`。

### 9.3 错误码


| HTTP  | 场景             |
| ----- | -------------- |
| `400` | 锚点校验失败、跨批次校验失败 |
| `401` | 未登录            |
| `500` | 未预期异常          |


---

## 10. 前端行为

- **成功**：提示 **已通知人数**；若有跳过/失败，展示 **简要数量** 与引导（如「部分跟踪人未配置域账号，请联系管理员维护 ums_email」）。
- **失败**：展示后端 `detail` / `message`。
- **刷新表格**：与一键分析成功后一致，可刷新当前列表（数据通常无变更，可选；若需与统计一致可刷新）。

---

## 11. 非功能与日志

- **日志**：整单结束 **INFO**（批次、`notified_count`、各类跳过/失败计数、操作者工号）；单条 WeLink 失败 **WARNING**；未预期异常 **ERROR** + `logger.exception`。
- **事务**：本功能 **不修改** `pipeline_history` / `pipeline_failure_reason`，无数据库写事务要求。
- **速率**：若收件人较多，可在实现中对 `rolling_welink_share` **短间隔串行**调用，避免触发对方限流（具体间隔与产品/运维确认）。

---

## 12. 实现检查清单（供开发自测）

- 锚点解析 `start_time`，统计范围 **不按 subtask** 过滤批次。
- 仅统计 `failed`/`error` + 存在 pfr + `failed_type` = 字典 bug + `owner` 非空。
- 按 `owner` 分组计数；每人最多一条 WeLink。
- 工号解析与 `ums_email.employee_id` 匹配；`domain_account` 非空方可发送。
- 消息标题、正文模板与 §5 一致；`url` 使用 `**failure_owner`** + `start_time` + `failed_type`，且正确 **URL 编码**。
- `rolling_welink_share` 置于独立模块，占位可替换。
- 跨批次勾选：前端拦截 + 后端校验（若传 `selected_history_ids`）。

---

## 13. 修订记录


| 版本  | 日期         | 说明                                                         |
| --- | ---------- | ---------------------------------------------------------- |
| 1.0 | 2026-03-25 | 初稿：与一键分析对齐的触发方式、批次键、WeLink 四参数、ums_email 与链接 query 规约、占位说明 |
| 1.1 | 2026-03-25 | §8：迁入 `welink_card` 实现、`WELINK_CARD_INI_PATH`、`config/welink_card.ini.example` |
| 1.2 | 2026-03-25 | §5.1：补充 `PUBLIC_APP_URL` 与后端拼接规则 |


