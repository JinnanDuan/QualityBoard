# dt-report 全景图（AI 助手沉淀）

> 本文由 AI 助手探索项目后生成，用于后续会话/协作快速复原上下文。
> 如与 `docs/` 下的权威文档冲突，以 `docs/` 为准。

---

## 总览

```
┌────────────────────────────────────────────────────────────────┐
│  dt-report — 团队内部测试用例批量执行结果看板与管理系统         │
│  单服务形态：uvicorn 同时托管 FastAPI API + React SPA 静态     │
└────────────────────────────────────────────────────────────────┘

  数据来源（上游）          本系统职责                       下游
  ┌──────────────┐         ┌──────────────────┐          ┌──────────┐
  │  Jenkins     │─写入 →  │ 集中看板          │ → 人     │  浏览器  │
  │  流水线      │         │ 归因/标注/流转    │          │ (团队)   │
  └──────────────┘         │ 一键分析/通知     │          └──────────┘
          │                │ 总结报告          │          ┌──────────┐
          ▼                │ WeLink 卡片       │ → 通知   │  WeLink  │
    MySQL dt_infra ────────│ 审计日志          │          └──────────┘
    (10 张表, 其中         │                   │
     8 张只读/部分可写,    │                   │
     2 张本系统新增)       └──────────────────┘
```

## 定位与红线

- **不是从零设计的系统**，而是在 Jenkins 已有数据库之上叠加的运营工具。`pipeline_overview/history` 是上游只读产物，**严禁 DELETE、严禁改前 8 张表结构**。
- 业务目标用一句话概括：**"从用例执行结束到所有失败执行记录处理结束，半天内完成"**。

## 技术栈

- 后端 FastAPI + SQLAlchemy 2.0 async + Pydantic v2 + aiomysql
- 前端 React 18 + Ant Design 5 + ECharts + Vite + pnpm
- JWT (HS256, 8h) 认证；管理员通过 `ADMIN_EMPLOYEE_IDS` 工号鉴权
- WeLink 通知通过 Playwright 取 cookie + httpx 发卡片 + INI 配置

## 分层（严格遵守）

```
api/v1/     → services/     → schemas/     → models/
(路由+校验)   (业务+SQL)       (Pydantic)      (ORM)
```

## 实现成熟度地图

- **已非常成熟**：`history` 模块（HistoryPage.tsx ≈2010 行，含所有一键功能的 Drawer/弹窗）、失败标注、失败原因继承、一键分析、一键通知 WeLink、首页大盘、登录认证、DB schema 校验、容器部署。
- **仍是占位**：分组概览、用例管理、**总结报告（report_snapshot 表已建未用）**、**通知中心（定时催办、防打扰）**、管理员后台（用户/模块/字典 CRUD 前后端）、**sys_audit_log 审计写入**。

## 规约（spec 文件位置）

- 真正的功能规约在根目录 `spec/`（14 份编号文件，`01` 到 `13`）——**不是** `openspec/specs/`（空的）。
- 关键规约：
  - `spec/07_history_filter_query`、`spec/08_history_filter_performance`：history 列表**禁止 JOIN**，必须 EXISTS + 批量补齐 + 默认最近 30 批。
  - `spec/11_one_click_batch_analyze`、`spec/13_one_click_bug_notify`：一键功能的契约。
  - `spec/04_failure_process`：失败标注 + 跟踪人流转 + WeLink 通知联动。

## 几个只有看代码才能看出来的约定

1. `**pfr.owner` 存储格式是「姓名 工号」**（半角空格），所有一键操作都依赖这个约定。
2. **"用例开发责任人"展示串**不直接读 `ph.owner`，而是 `main_module` → `ums_module_owner` → `ums_email` 小写等价匹配拼接。
3. **跨表关联键**统一为 `pfr.failed_batch == ph.start_time`（唯一批次键），不按 subtask 切。
4. **前端字段严格 snake_case**，与后端 Pydantic 一一对齐。

---

## AI 助手持久化记忆（跨会话复用）

位于 `~/.claude/projects/-Users-djn-code-dt-report/memory/`：

- `MEMORY.md`（索引）
- `project_overview.md` · `project_architecture.md` · `project_data_model.md`
- `project_implementation_status.md` · `project_workflows.md`
- `project_spec_registry.md` · `reference_canonical_docs.md`

**下次会话的第一入口**：`docs/04_project_structure.md` + `docs/05_technical_architecture.md`，加上上面这些记忆就能快速复原全貌，不用再大面积扫代码。