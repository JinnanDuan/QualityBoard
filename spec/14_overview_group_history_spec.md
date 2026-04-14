# 分组执行历史（Overview）规格说明

> 本文档定义「分组执行历史」页（`pipeline_overview` 只读列表）的前后端契约，与 [spec/08_history_filter_performance_spec.md](08_history_filter_performance_spec.md)（默认批次注入思路）、[spec/12_history_case_drilldown_spec.md](12_history_case_drilldown_spec.md)（外链与安全属性）对齐。

---

## 一、范围与数据源

| 项 | 说明 |
|----|------|
| 主表 | `pipeline_overview`（只读，禁止 ALTER/DROP，见项目红线） |
| 页面路由 | 主列表：`/overview`；分组跨轮次专用页：`/overview/subtask-executions` |
| API | `GET /api/v1/overview`（分页列表）、`GET /api/v1/overview/options`（筛选项） |

---

## 二、与首页、详细执行历史的关系

1. **首页大盘**：点击批次**仍直达**「详细执行历史」`/history?start_time=...`（**不**强制经过 `/overview`）。本页为独立菜单入口。
2. **筛选对齐**：与「详细执行历史」可对齐的字段尽量一致：**批次**（对应 History 的 `start_time`）、**分组**（`subtask`）、**平台**（`platform`）、**代码分支**（`code_branch`）、**执行结果**（Overview 为 `result`，主要为 `passed` / `failed`）。**不出现**用例级、归因类筛选（如 `case_name`、`failed_type`、`failure_owner`、`analyzed` 等）。

---

## 三、默认批次注入（列表型，性能规约）

**适用接口**：`GET /api/v1/overview`（主列表模式，见 §6.3 例外）。

**触发条件**：请求中 **`batch` 未传或为空列表**时注入。

**逻辑**（与 spec/08 §3.1 **思路相同**，主表与字段不同）：

1. 从 `pipeline_overview` 取 **`batch`** 的最近 **N** 个不重复值；
2. `batch IS NOT NULL`，`batch LIKE '20%'`，`DISTINCT`，`ORDER BY batch DESC`，`LIMIT N`；
3. **N = 20**（History 为 30，字段为 `start_time`）；
4. 将结果注入为 `batch IN (...)`，与用户其它条件 AND 组合。

**不触发**：用户已选 `batch`（非空列表）时，不注入。

**专用分组页例外**：见 §6.3，**禁止**套用上述注入。

---

## 四、排序

| 场景 | 规则 |
|------|------|
| 默认（未传 `sort_field`） | `batch` **降序**，`subtask` **升序**（字符串） |
| 用户指定列 | `sort_field` + `sort_order`（`asc` / `desc`），允许字段见 §5.2 |
| `case_num` | 列类型为 `varchar`，**按数值排序**时使用 `CAST(case_num AS SIGNED)`（与团队脏数据约定一致；无法转换时 MySQL 按 0 处理） |

---

## 五、API 契约

### 5.1 `GET /api/v1/overview/options`

返回各字段去重选项（单表 `pipeline_overview`），供 Select 使用：

- `batch`：`batch` 非空，优先 `LIKE '20%'` 且降序（与列表注入口径一致，便于选最近轮次）
- `subtask`、`platform`、`code_branch`：非空去重，升序
- `result`：**固定枚举** `["passed", "failed"]`（不依赖库内脏值枚举）

### 5.2 `GET /api/v1/overview` 查询参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `page` | int | 默认 1 |
| `page_size` | int | 默认 20，上限 100 |
| `batch` | string[] | 多选批次，与 History `start_time` 同口径字符串 |
| `subtask` | string[] | 多选分组 |
| `platform` | string[] | 多选 |
| `code_branch` | string[] | 多选 |
| `result` | string[] | 多选，仅允许 `passed`、`failed` |
| `sort_field` | string | 可选；允许：`batch`,`subtask`,`result`,`case_num`,`batch_start`,`batch_end`,`passed_num`,`failed_num`,`platform`,`code_branch`,`created_at` |
| `sort_order` | string | `asc` / `desc` |
| `all_batches` | bool | 默认 `false`；为 `true` 时见 §6.3 |

**响应**：`PageResponse[OverviewItem]`，`OverviewItem` 字段与 ORM `PipelineOverview` 一致（snake_case）。

---

## 六、前端交互

### 6.1 表格列（PRD §5.3 + 外链）

除 PRD 所列：批次、分组、执行结果、总用例数、通过数、失败数、开始/结束时间、平台、代码分支外，须**展示**外链列：

- `reports_url`、`log_url`、`screenshot_url`、`pipeline_url`
- 有 URL：新窗口打开，`target="_blank"`，`rel="noopener noreferrer"`（对齐 spec/12）
- 无 URL：文案「暂无」
- **仅单元格内链接/可点击文字**触发跳转；**整行不承担**钻取（与 History 用例名列一致）

### 6.2 批次列点击

新标签页打开：

`/history?start_time=<encodeURIComponent(batch)>`

（该批次**全部用例**，与 History 多选批次参数形式一致时可使用多个 `start_time` 同名参数；单批次时传一个即可。）

### 6.3 分组列点击 — Modal 二选一

点击当前行的 **`subtask`** 时弹出 **Modal**，用户选择：

- **A**：新标签页打开 **`/overview/subtask-executions?subtask=<encodeURIComponent(subtask)>`**  
  - 仅展示该 **分组** 在 **所有轮次** 的 `pipeline_overview` 行。  
  - 对应列表请求：`GET /api/v1/overview?all_batches=true&subtask=...`（及分页等），**不得**注入 §3 的「最近 20 批」。
- **B**：新标签页打开 **`/history?start_time=<encodeURIComponent(当前行 batch)>&subtask=<encodeURIComponent(subtask)>`**  
  - 同批同组的用例明细。

**校验**：`all_batches=true` 时，服务端须要求 **`subtask` 至少包含一个非空**；否则返回 **422** 并附中文说明。

### 6.4 URL 与 placeholder

- 主列表筛选条件与分页、排序与 **URL Query** 同步（对齐 `HistoryPage` 模式：`replace`、省略默认值）。
- 批次 Select **placeholder**：「不选则默认最近20批」（与 spec/08 前端规约对称）。

### 6.5 错误处理

列表请求：`try/catch`，超时 / 5xx / 4xx 提示与 spec/08 §3.3 一致；失败不清空表格数据。

---

## 七、实现分层（项目契约）

- **Model**：已有 `PipelineOverview`
- **Schema**：`backend/schemas/overview.py` — `OverviewItem`、`OverviewQuery`、`OverviewFilterOptions`
- **Service**：`backend/services/overview_service.py` — `list_overview`、`get_overview_options`（纯 async 函数）
- **API**：`backend/api/v1/overview.py` — `response_model=PageResponse[OverviewItem]` / `OverviewFilterOptions`

Python 3.8：`Optional[]` 标注；日志遵守 `docs/06_logging_guide.md`（关键异常 WARNING/ERROR，避免冗余 INFO）。

---

## 八、版本与变更

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-04-11 | 初版：默认 20 批注入、排序、筛选、外链、batch/subtask 链与 Modal、subtask 专用页与 `all_batches` |
