# 用例执行历史钻取（专用路径）规约（Spec）

本文档定义从「详细执行历史」列表**点击用例名**进入**专用页面**，查看该用例在**全时间范围**内（在分页与接口约束下）的执行明细。与 [spec/02_history_fields_spec.md](02_history_fields_spec.md)、[spec/07_history_filter_query_spec.md](07_history_filter_query_spec.md)、[spec/08_history_filter_performance_spec.md](08_history_filter_performance_spec.md) 配合使用。

---

## 1. 背景与目标

### 1.1 问题

默认列表在未选批次时会注入「最近 30 批」（见 Spec 08），用户无法在同一列表心智下直接查看**单条用例的完整历史**。

### 1.2 目标

- 提供**专用路径**，默认带入**用例名**及可选 **platform、code_branch**，**不带批次**，以利用 Spec 08 **例外规则**做全量时间范围查询（仍分页）。
- 与大盘「详细执行历史」列表区分路由，便于标题、说明与后续扩展。

---

## 2. 后端依赖（Spec 08 例外）

当请求 **`GET /api/v1/history`** 满足：**已传非空 `case_name`（多选中至少一项有效）**且**未传 `start_time`** 时，**不**注入默认「最近 N 批」，按其它条件 + 分页查询 `pipeline_history` 全时间范围。

详细算法与边界以 [spec/08_history_filter_performance_spec.md](08_history_filter_performance_spec.md) **§3.1.1** 为准。

---

## 3. 路由与 URL

### 3.1 路径

| 项目 | 规约 |
|------|------|
| 前端路径 | **`/history/case-executions`**（与 `/history` 并列，挂在同一应用布局下） |
| 参数方式 | **Query String**，便于分享与书签 |

### 3.2 Query 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `case_name` | **是** | 用例名，与 `pipeline_history.case_name` 一致；**须 URL 编码**（RFC 3986） |
| `platform` | 否 | 平台；来自被点击行；若为空则**不传**该参数（表示不按平台筛选） |
| `code_branch` | 否 | 代码分支；来自被点击行；若为空则**不传** |

**不传 `start_time`**：钻取页初始化请求**不得**默认带批次，以触发 Spec 08 例外。

其它筛选（`subtask`、`main_module`、`case_result` 等）钻取页**默认不带**；用户可在页面上再选。

### 3.3 URL 示例

```
/history/case-executions?case_name=test_login_success&platform=Android&code_branch=master
```

用例名含中文或特殊字符时，使用 `encodeURIComponent` 编码。

---

## 4. 入口交互（列表页）

### 4.1 触发位置

- **详细执行历史**表格中「用例名」列（或等价展示 `case_name` 的单元格）。

### 4.2 行为

| 项目 | 规约 |
|------|------|
| 打开方式 | **新浏览器标签页**打开钻取页（`target=_blank` + `rel="noopener noreferrer"`），避免用户丢失当前列表筛选上下文 |
| 链接目标 | 拼出 **§3** 所述完整 URL（含编码后的 `case_name`） |
| 带入字段 | 来自**被点击行**：`case_name`、`platform`、`code_branch`（空则省略 query 键） |

### 4.3 无障碍与样式

- 用例名呈现为可识别链接（颜色/下划线与表格内其它链接一致）。
- 可选：`title` 提示「在新标签页中查看该用例的全历史执行记录」。

---

## 5. 钻取页（`/history/case-executions`）

### 5.1 页面职责

- 展示与「详细执行历史」**同一套表格能力**（列、分页、排序、Drawer 等），**复用** `HistoryPage` 表格与 `GET /api/v1/history` 请求逻辑，或抽取公共组件，避免两套业务分叉。
- 页面**顶部标题区**建议展示：**「用例执行历史」** + 当前用例名（脱敏规则与全局一致）。
- **布局**：与 `/history` 一致——在主布局内容区内占满视口剩余高度，筛选区与表头、分页区域不随数据行数撑高整页，**仅表体区域内部纵向滚动**。

### 5.2 初始化

1. 挂载时从 URL 解析 `case_name`（必填）、`platform`、`code_branch`。
2. 若缺少 `case_name` 或解析后为空：展示友好错误（如「链接无效」），不发起列表请求。
3. 将解析结果写入筛选表单初始值，**批次留空**，立即按当前页码请求列表。

### 5.3 与 URL 同步

- 若钻取页继续沿用 History 的「筛选与 URL 同步」机制，用户变更筛选后更新 query；**不得**在无用户操作时自动写入 `start_time` unless 用户主动选批次。

### 5.4 性能与提示

- 数据量大时可能较慢；沿用 Spec 08 前端超时与错误提示规约。
- 可选（非必须首版）：页面副文案提示「未选批次时，在已选用例名下查询全部时间范围」。

---

## 6. 路由注册（前端）

在应用路由表（如 `frontend/src/routes/index.tsx`）中增加：

- `path: "history/case-executions"` → 与 `history` 共用同一页面组件或薄包装组件（由实现选定，须满足 §5）。

---

## 7. 验收要点

- [ ] 列表点击用例名，新标签打开 `/history/case-executions?...`，且默认请求**无** `start_time`、**有** `case_name`（及可选 platform/code_branch）。
- [ ] 后端对应该请求**不**注入 30 批（见 Spec 08 §3.1.1）。
- [ ] 缺省 `case_name` 的 URL 有错误处理。
- [ ] 分页、排序、Drawer 与大盘列表行为一致（字段以现有 History 为准）。

---

## 8. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-03-23 | 初稿：专用路径、query 约定、新标签钻取、依赖 Spec 08 例外 |
