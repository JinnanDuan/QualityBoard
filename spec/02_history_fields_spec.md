# 详细执行历史页面字段规约（Spec）

本文档为 `pipeline_history` 表业务字段的展示与筛选规约，作为后续 AI 编程的契约。**本次不考虑** `pipeline_failure_reason` 关联、归因分析区、流转操作区、操作时间线、`owner_history`。

---

## 1. 直接展示字段（表格列）

| 字段名 | 列标题 | dataIndex | 列宽 | 渲染方式 |
|--------|--------|-----------|------|----------|
| start_time | 批次 | start_time | 180 | 纯文本 |
| subtask | 分组 | subtask | 100 | 纯文本 |
| case_name | 用例名 | case_name | 200 | 纯文本，ellipsis 省略 |
| main_module | 主模块 | main_module | 100 | 纯文本 |
| case_result | 执行结果 | case_result | 100 | Tag 着色：passed=绿色，failed=红色，error=橙色，其他=default |
| case_level | 用例级别 | case_level | 90 | 纯文本（P0/P1/P2） |
| analyzed | 是否已分析 | analyzed | 100 | Tag：1=已分析（蓝色），0=未分析（灰色） |
| platform | 平台 | platform | 90 | 纯文本 |
| code_branch | 代码分支 | code_branch | 120 | 纯文本，ellipsis 省略 |
| screenshot_url | 截图 | screenshot_url | 120 | 可点击链接（新窗口打开），无值则显示「暂无」 |
| reports_url | 测试报告 | reports_url | 120 | 可点击链接（新窗口打开），无值则显示「暂无」 |

**说明：** `main_module` 仅有一个值，直接展示；`module` 有多个值，不在表格中展示，仅在 Drawer 中展示。`created_at`、`updated_at` 暂不展示。`id`、`owner_history` 及 `log_url`、`pipeline_url` 不在表格中直接展示。

---

## 2. 点击弹窗展示字段（Drawer 分区）

### 2.1 基本信息区

| 字段名 | 展示形式 |
|--------|----------|
| case_name | 纯文本 |
| start_time | 纯文本（批次） |
| subtask | 纯文本（分组） |
| main_module | 纯文本 |
| module | 纯文本（模块名，可有多值） |
| case_level | 纯文本 |
| owner | 纯文本（用例开发责任人） |
| platform | 纯文本 |
| code_branch | 纯文本 |
| screenshot_url | 可点击链接（新窗口打开），无值则显示「暂无」 |
| reports_url | 可点击链接（新窗口打开），无值则显示「暂无」 |

### 2.2 外部链接区

| 字段名 | 展示形式 |
|--------|----------|
| log_url | 可点击链接（新窗口打开），无值则显示「暂无」 |
| pipeline_url | 可点击链接（新窗口打开），无值则显示「暂无」 |

**说明：** `owner` 在 Drawer 基本信息区展示，名称为「用例开发责任人」。`owner_history` 本次实现不考虑。

---

## 3. 筛选字段清单

| 字段名 | 筛选控件类型 | 是否必选 | 默认值策略 | 备注 |
|--------|--------------|----------|------------|------|
| start_time | 下拉单选 | 否 | 空（查全部） | 选项从接口或现有数据去重获取 |
| subtask | 下拉单选 | 否 | 空 | 选项从数据去重或字典接口获取 |
| case_name | 输入框模糊搜索 | 否 | 空 | 后端需支持 `LIKE %keyword%` |
| main_module | 下拉单选 | 否 | 空 | 选项从数据去重或 `ums_module_owner` 获取 |
| case_result | 下拉单选 | 否 | 空 | 选项：passed、failed、error |
| case_level | 下拉单选 | 否 | 空 | 选项：P0、P1、P2 等 |
| analyzed | 下拉单选 | 否 | 空 | 选项：全部、已分析、未分析（对应 空/1/0） |
| platform | 下拉单选 | 否 | 空 | 选项从数据去重（如 Android、iOS、Web） |
| code_branch | 下拉单选 | 否 | 空 | 选项从数据去重获取 |

**说明：** 除 URL 类字段（`log_url`、`screenshot_url`、`reports_url`、`pipeline_url`）、`owner_history` 及 `module` 外，其余业务字段均需支持筛选。筛选条件需同步到 URL 查询参数，支持 deeplink 一键跳转。

---

## 4. 字段复用说明

| 字段 | 表格列 | Drawer | 筛选 |
|------|--------|--------|------|
| start_time | ✓ | ✓ 基本信息 | ✓ |
| subtask | ✓ | ✓ 基本信息 | ✓ |
| case_name | ✓ | ✓ 基本信息 | ✓ |
| main_module | ✓ | ✓ 基本信息 | ✓ |
| module | — | ✓ 基本信息 | — |
| case_result | ✓ | — | ✓ |
| case_level | ✓ | ✓ 基本信息 | ✓ |
| owner | — | ✓ 基本信息 | — |
| analyzed | ✓ | — | ✓ |
| platform | ✓ | ✓ 基本信息 | ✓ |
| code_branch | ✓ | ✓ 基本信息 | ✓ |
| screenshot_url | ✓ | ✓ 基本信息（链接） | — |
| reports_url | ✓ | ✓ 基本信息（链接） | — |
| log_url | — | ✓ 外部链接 | — |
| pipeline_url | — | ✓ 外部链接 | — |
| owner_history | — | — | — |
| id / created_at / updated_at | — | — | — |
