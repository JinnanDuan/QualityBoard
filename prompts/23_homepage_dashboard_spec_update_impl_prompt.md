# 首页 Dashboard 按最新 Spec 更新实现 — Prompt

请严格按照 `spec/09_homepage_batch_status_trend_spec.md` 更新现有代码实现。

---

## 变更要点

### 1. 最新批次：改为「已执行完」逻辑

- **旧**：按 `MAX(batch_start)` 取最新批次
- **新**：仅查 `batch_end IS NOT NULL`，按 `MAX(batch_end)` 降序取最新批次
- **修改**：`backend/services/dashboard_service.py` 中 `get_latest_batch` 的 SQL

### 2. 趋势接口：新增 code_branch 参数

- **新**：`GET /dashboard/batch-trend?code_branch=master` 或 `?code_branch=bugfix`，`code_branch` 必填
- **过滤**：master = `TRIM(COALESCE(code_branch,'')) = 'master'`；bugfix = `!= 'master'`（含 NULL）
- **已执行完**：趋势数据也仅查 `batch_end IS NOT NULL`
- **修改**：`dashboard_service.get_batch_trend(db, limit, code_branch)`、`dashboard.py` API 增加 `code_branch` 参数

### 3. 前端：双图表 + 点标签

- **布局**：两张折线图上下排列
- **图表 1**：标题「master 分支最近 batch 执行情况」，调用 `batchTrend(30, 'master')`
- **图表 2**：标题「bugfix 分支最近 batch 执行情况」，调用 `batchTrend(30, 'bugfix')`
- **点标签**：ECharts series 增加 `label: { show: true, position: 'top' }`，每个点上方显示数量
- **修改**：`DashboardPage.tsx`、`dashboardApi.batchTrend(limit, codeBranch)`

---

## 必读

- `spec/09_homepage_batch_status_trend_spec.md` 全文，尤其 2.3、3.1、3.4、5.2、5.3
- `.cursor/rules/project.mdc`
