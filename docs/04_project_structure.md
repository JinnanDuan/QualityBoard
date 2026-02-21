# 项目结构说明

> 本文档对 dt-report 项目根目录下的每个一级目录和文件逐一说明，帮助团队成员快速了解项目全貌，便于后续开发。

## 目录总览

```
dt-report/
├── backend/          后端工程（Python FastAPI）
├── frontend/         前端工程（React + Ant Design）
├── database/         数据库 DDL 与种子数据
├── docs/             项目文档
├── prompts/          AI Prompt 记录
├── scripts/          运维脚本（启停/部署）
├── .venv/            Python 虚拟环境（自动生成，不提交）
├── .env.example      环境变量模板
├── .env              实际环境变量（不提交到 Git）
├── .gitignore        Git 忽略规则
├── README.md         项目入口说明
├── app.log           运行日志（自动生成，不提交）
└── .pid              进程 PID 文件（自动生成，不提交）
```

---

## 一、`backend/` — 后端工程

基于 **FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2** 构建。采用分层架构：API 层 → Service 层 → Model 层。

### 入口与依赖

| 文件 | 说明 |
|------|------|
| `main.py` | FastAPI 应用入口。创建 `app` 实例，注册 CORS 中间件，挂载 API 路由，托管前端静态文件（SPA fallback）。启动命令：`uvicorn backend.main:app` |
| `requirements.txt` | Python 依赖清单。核心：fastapi、uvicorn、sqlalchemy[asyncio]、aiomysql、pydantic、pydantic-settings、python-jose（JWT）、passlib（密码哈希）、httpx（HTTP 客户端） |

### `core/` — 核心配置与基础设施

| 文件 | 说明 |
|------|------|
| `config.py` | 全局配置。使用 Pydantic `BaseSettings` 从 `.env` 文件读取 `DATABASE_URL`、`SECRET_KEY`、`ADMIN_EMPLOYEE_IDS`、WeLink API 配置等 |
| `database.py` | 数据库连接层。创建 SQLAlchemy 异步引擎（`create_async_engine`）和会话工厂（`async_sessionmaker`），提供 `get_db()` 异步生成器用于 FastAPI 依赖注入 |
| `security.py` | 认证鉴权工具。JWT Token 的生成（`create_access_token`）与验证（`verify_token`），管理员权限校验依赖项（`require_admin`） |
| `dependencies.py` | 公共依赖项。`get_current_user` 从请求头提取并验证 JWT 获取当前用户信息 |

### `models/` — ORM 模型（数据库表映射）

每张数据库表对应一个 Python 类，字段定义严格与 `database/*.sql` 中的 DDL 保持一致。

| 文件 | 对应表 | 业务含义 | 状态 |
|------|--------|---------|------|
| `base.py` | — | 所有模型的公共基类（`DeclarativeBase`） | 基础设施 |
| `pipeline_overview.py` | `pipeline_overview` | 批次-分组级执行概览 | 只读映射 |
| `pipeline_history.py` | `pipeline_history` | 用例级执行明细 | 部分字段可写 |
| `pipeline_failure_reason.py` | `pipeline_failure_reason` | 失败归因记录 | 可读写 |
| `pipeline_cases.py` | `pipeline_cases` | 用例主数据 | 部分字段可写 |
| `ums_email.py` | `ums_email` | 员工信息 | 可读写（管理员） |
| `ums_module_owner.py` | `ums_module_owner` | 模块-责任人映射 | 可读写（管理员） |
| `case_failed_type.py` | `case_failed_type` | 失败原因类型字典 | 可读写（管理员） |
| `case_offline_type.py` | `case_offline_type` | 下线原因类型字典 | 可读写（管理员） |
| `sys_audit_log.py` | `sys_audit_log` | 系统审计日志（新增表） | 系统写入 |
| `report_snapshot.py` | `report_snapshot` | 报告快照（新增表） | 可读写 |

### `schemas/` — Pydantic 数据校验模型

Schema 定义 API 的请求参数格式和响应 JSON 格式，由 FastAPI 自动校验和序列化。

| 文件 | 说明 | 实现状态 |
|------|------|---------|
| `common.py` | 通用模型：`PageRequest`（分页请求基类）、`PageResponse`（分页响应泛型）、`ApiResponse`（通用响应包装） | ✅ 已实现 |
| `history.py` | 执行明细：`HistoryItem`（含 failure_owner、failed_type 关联字段）、`HistoryQuery`（支持按轮次/结果/平台/跟踪人/失败原因筛选）、`HistoryFilterOptions` | ✅ 已实现 |
| `auth.py` | 认证模块 Schema | 🔲 占位 |
| `dashboard.py` | 数据看板 Schema | 🔲 占位 |
| `overview.py` | 分组概览 Schema | 🔲 占位 |
| `analysis.py` | 失败分析 Schema | 🔲 占位 |
| `cases.py` | 用例管理 Schema | 🔲 占位 |
| `report.py` | 总结报告 Schema | 🔲 占位 |
| `notification.py` | 通知配置 Schema | 🔲 占位 |

### `api/` — API 路由层

接收 HTTP 请求，调用 Service 层，返回 JSON 响应。

| 文件 | 路由前缀 | 说明 | 实现状态 |
|------|---------|------|---------|
| `router.py` | `/api/v1` | 总路由注册，将所有子模块路由挂载到 `/api/v1` 下 | ✅ 已实现 |
| `v1/history.py` | `/api/v1/history` | 执行明细接口：`GET /api/v1/history` 分页查询 + 筛选 | ✅ 已实现 |
| `v1/auth.py` | `/api/v1/auth` | 认证接口（登录/登出） | 🔲 占位 |
| `v1/dashboard.py` | `/api/v1/dashboard` | 数据看板接口 | 🔲 占位 |
| `v1/overview.py` | `/api/v1/overview` | 分组概览接口 | 🔲 占位 |
| `v1/analysis.py` | `/api/v1/analysis` | 失败分析接口 | 🔲 占位 |
| `v1/cases.py` | `/api/v1/cases` | 用例管理接口 | 🔲 占位 |
| `v1/report.py` | `/api/v1/report` | 总结报告接口 | 🔲 占位 |
| `v1/notification.py` | `/api/v1/notification` | 通知配置接口 | 🔲 占位 |
| `v1/admin.py` | `/api/v1/admin` | 管理员后台接口（用户/模块/字典 CRUD） | 🔲 占位 |

### `services/` — 业务逻辑层

封装具体的业务逻辑，被 API 层调用。与数据库的交互通过 ORM Model 完成。

| 文件 | 说明 | 实现状态 |
|------|------|---------|
| `history_service.py` | `list_history(db, query)` — LEFT JOIN pipeline_failure_reason 分页查询，支持动态筛选（轮次/结果/平台/跟踪人/失败原因等）+ 排序 + 分页；`get_history_options()` 返回各筛选字段去重选项 | ✅ 已实现 |
| `auth_service.py` | 认证业务逻辑 | 🔲 占位 |
| `dashboard_service.py` | 看板数据聚合 | 🔲 占位 |
| `overview_service.py` | 分组概览查询 | 🔲 占位 |
| `analysis_service.py` | 失败分析与归因 | 🔲 占位 |
| `cases_service.py` | 用例管理 | 🔲 占位 |
| `report_service.py` | 报告生成 | 🔲 占位 |
| `notification_service.py` | 通知与催办 | 🔲 占位 |
| `admin_service.py` | 管理员后台 | 🔲 占位 |

### `utils/` — 通用工具

| 文件 | 说明 |
|------|------|
| `audit.py` | `write_audit_log()` — 审计日志写入工具（占位实现，后续写入 `sys_audit_log` 表） |

### `data/` — 文件持久化目录

存放运行时产生的临时文件，通过 `.gitkeep` 保证空目录被 Git 跟踪，实际文件通过 `.gitignore` 排除。

---

## 二、`frontend/` — 前端工程

基于 **React 18 + TypeScript + Ant Design 5 + Vite** 构建，使用 **pnpm** 管理依赖。

### 根目录文件

| 文件 | 说明 |
|------|------|
| `package.json` | 依赖声明与脚本。`pnpm dev` 启动开发服务器（端口 3000），`pnpm build` 构建生产包到 `dist/` |
| `vite.config.ts` | Vite 构建配置。开发模式下将 `/api` 请求代理到 `http://localhost:8000`（后端），配置路径别名 `@` → `src/` |
| `tsconfig.json` | TypeScript 编译配置 |
| `index.html` | HTML 入口，Vite 从这里启动打包 |
| `pnpm-lock.yaml` | pnpm 锁定文件，确保团队成员安装相同版本的依赖 |

### `src/` — 源码目录

#### 应用入口

| 文件 | 说明 |
|------|------|
| `main.tsx` | React 应用入口，挂载 `<App />` 到 `#root` DOM 节点 |
| `App.tsx` | 根组件。使用 `<BrowserRouter>` 包裹路由，`<ConfigProvider>` 配置 Ant Design 中文语言包 |

#### `routes/` — 路由配置

| 文件 | 说明 |
|------|------|
| `index.tsx` | 集中式路由表。使用 `useRoutes` 定义所有页面路由，根路径 `/` 使用 `MainLayout` 布局 |

路由与页面的对应关系：

| 路由 | 页面组件 | 说明 |
|------|---------|------|
| `/` | `DashboardPage` | 首页大盘 |
| `/overview` | `OverviewPage` | 分组执行历史 |
| `/history` | `HistoryPage` | 详细执行历史 |
| `/cases` | `CasesPage` | 用例管理 |
| `/report/:id?` | `ReportPage` | 总结报告 |
| `/admin/users` | `UsersPage` | 用户管理 |
| `/admin/modules` | `ModulesPage` | 模块映射管理 |
| `/admin/dict/failed-types` | `FailedTypesPage` | 失败类型字典 |
| `/admin/dict/offline-types` | `OfflineTypesPage` | 下线类型字典 |
| `/admin/notification` | `NotificationPage` | 通知配置 |
| `/login` | `LoginPage` | 登录页 |

#### `layouts/` — 布局组件

| 文件 | 说明 |
|------|------|
| `MainLayout.tsx` | 主布局。Ant Design `Layout` + 可折叠侧边栏（`Sider`）+ 导航菜单（`Menu`）+ 内容区（`<Outlet />`）。点击菜单项通过 `useNavigate` 实现路由跳转 |

#### `pages/` — 页面组件

按业务模块分目录，每个页面一个 `.tsx` 文件：

| 文件 | 说明 | 实现状态 |
|------|------|---------|
| `history/HistoryPage.tsx` | 详细执行历史页面。Table 展示 pipeline_history 数据（含跟踪人、失败原因列），支持分页与多维度筛选，Drawer 含基本信息区、失败归因区（仅 failed 时展示）、外部链接区 | ✅ 已实现 |
| `dashboard/DashboardPage.tsx` | 首页大盘 | 🔲 占位 |
| `overview/OverviewPage.tsx` | 分组执行历史 | 🔲 占位 |
| `cases/CasesPage.tsx` | 用例管理 | 🔲 占位 |
| `report/ReportPage.tsx` | 总结报告 | 🔲 占位 |
| `admin/UsersPage.tsx` | 用户管理 | 🔲 占位 |
| `admin/ModulesPage.tsx` | 模块映射管理 | 🔲 占位 |
| `admin/FailedTypesPage.tsx` | 失败类型字典 | 🔲 占位 |
| `admin/OfflineTypesPage.tsx` | 下线类型字典 | 🔲 占位 |
| `admin/NotificationPage.tsx` | 通知配置 | 🔲 占位 |
| `auth/LoginPage.tsx` | 登录页 | 🔲 占位 |

#### `services/` — API 请求层

| 文件 | 说明 |
|------|------|
| `request.ts` | Axios 实例封装。`baseURL` 为 `/api/v1`，请求拦截器自动附加 JWT Token（从 `localStorage` 读取），响应拦截器提取 `response.data` |
| `index.ts` | API 方法集中导出。定义 `PageResponse`、`HistoryItem` 等 TypeScript 接口，提供 `historyApi.list(params)` 方法调用后端接口 |

#### `types/` — TypeScript 类型定义

| 文件 | 说明 |
|------|------|
| `index.ts` | 与后端 10 张数据库表对应的前端 TypeScript 接口（`PipelineHistory`、`PipelineOverview`、`PipelineFailureReason` 等），以及通用的 `PageResponse`、`ApiResponse` 泛型接口 |

#### 其他目录

| 目录 | 说明 |
|------|------|
| `components/` | 全局通用组件（当前为空，后续开发时存放跨页面复用的组件） |
| `hooks/` | 自定义 React Hooks（当前为空） |
| `stores/` | 状态管理（当前为空，后续可用 zustand 或 React Context） |
| `utils/` | 通用工具函数（当前为空） |
| `styles/` | 全局样式。`global.css` 包含基础样式重置 |

---

## 三、`database/` — 数据库 DDL 与种子数据

存放所有数据库表结构定义（SQL 迁移文件）。文件名遵循版本号命名规则：`V<主>.<次>.<修>__<描述>.sql`。

| 文件 | 说明 |
|------|------|
| `README.md` | 数据库目录说明与迁移执行指引 |
| `V1.0.0__init_dt_infra_database.sql` | 初始化 dt_infra 数据库 |
| `V1.0.1__create_pipeline_history.sql` | 创建 pipeline_history 表（用例级执行明细） |
| `V1.0.2__create_pipeline_overview.sql` | 创建 pipeline_overview 表（批次-分组概览） |
| `V1.0.3__create_pipeline_failure_reason.sql` | 创建 pipeline_failure_reason 表（失败归因） |
| `V1.0.4__create_pipeline_cases.sql` | 创建 pipeline_cases 表（用例主数据） |
| `V1.0.5__create_ums_email.sql` | 创建 ums_email 表（员工信息） |
| `V1.0.6__create_ums_module_owner.sql` | 创建 ums_module_owner 表（模块-责任人映射） |
| `V1.0.7__create_case_failed_type.sql` | 创建 case_failed_type 表（失败原因类型字典） |
| `V1.0.8__create_case_offline_type.sql` | 创建 case_offline_type 表（下线原因类型字典） |
| `V1.0.9__create_sys_audit_log.sql` | 创建 sys_audit_log 表（系统审计日志，**新增表**） |
| `V1.1.0__create_report_snapshot.sql` | 创建 report_snapshot 表（报告快照，**新增表**） |
| `seed_pipeline_history.sql` | 样例数据：20 条 pipeline_history 测试记录，用于端到端验证 |

**注意事项：**
- V1.0.0 ~ V1.0.8 为已有表结构，**严禁修改**
- V1.0.9、V1.1.0 为本系统新增的表
- 严禁对 `pipeline_overview`、`pipeline_history` 执行 `DELETE`

---

## 四、`docs/` — 项目文档

| 文件 | 说明 |
|------|------| 
| `01_user_story_map.md` | 用户故事地图 — 按 Epic 组织的功能需求与用户故事 |
| `02_prd.md` | 产品需求文档（PRD）— 详细的功能规格说明 |
| `03_deployment_guide.md` | 部署指南 — 基于 Ubuntu 20.04 LTS 的完整部署流程（依赖安装、环境配置、启停操作） |
| `04_project_structure.md` | 项目结构说明（本文档） |
| `05_technical_architecture.md` | 技术架构说明 — 系统上下文、分层架构、数据流、ER 关系、部署模型、设计决策 |

---

## 五、`prompts/` — AI Prompt 记录

保存项目开发过程中使用的 AI Prompt，可追溯每个阶段的输入指令。

| 文件 | 说明 |
|------|------|
| `01_user_story_map_prompt.md` | 生成用户故事地图的 Prompt |
| `02_prd_prompts.md` | 生成 PRD 的 Prompt |
| `03_scaffolding_prompt.md` | 生成项目脚手架的 Prompt（包含完整的目录结构、技术栈、数据库约束、文件生成规则等） |
| `04_depoly_guide_and_scripts_prompt.md` | 生成部署指南与运维脚本的 Prompt |
| `05_e2e_test_prompt.md` | 端到端验证打通的 Prompt |

---

## 六、`scripts/` — 运维脚本

自动化部署和运行时管理脚本，简化日常操作。

| 文件 | 用法 | 说明 |
|------|------|------|
| `deploy.sh` | `bash scripts/deploy.sh` | 一键部署：安装后端依赖 → 构建前端 → 启动后端 |
| `start.sh` | `bash scripts/start.sh` | 启动后端（后台运行），写入 PID 到 `.pid`，日志输出到 `app.log` |
| `stop.sh` | `bash scripts/stop.sh` | 停止后端（读取 `.pid` 文件终止进程） |
| `restart.sh` | `bash scripts/restart.sh` | 重启后端（先 stop 再 start） |
| `status.sh` | `bash scripts/status.sh` | 检查运行状态（进程、端口、API、前端页面） |

---

## 七、根目录文件

| 文件 | 说明 |
|------|------|
| `README.md` | 项目入口说明 — 技术栈、快速启动命令、数据库迁移说明 |
| `.env.example` | 环境变量模板。包含 `DATABASE_URL`（数据库连接）、`SECRET_KEY`（JWT 密钥）、`ADMIN_EMPLOYEE_IDS`（管理员工号）、`CORS_ORIGINS`（跨域白名单）、WeLink API 配置等 |
| `.env` | 实际环境变量（基于 `.env.example` 创建，包含真实的数据库密码等敏感信息，**不提交到 Git**） |
| `.gitignore` | Git 忽略规则。排除 `__pycache__`、`.venv`、`node_modules`、`frontend/dist`、`.env`、`.pid`、`*.log` 等 |
| `app.log` | 后端运行日志（由 `start.sh` 自动生成，不提交） |
| `.pid` | 后端进程 PID 文件（由 `start.sh` 自动生成，不提交） |
| `.venv/` | Python 虚拟环境目录（由 `python3 -m venv .venv` 创建，不提交） |

---

## 八、当前开发进度

### 已完成

| 模块 | 内容 |
|------|------|
| 项目脚手架 | 完整的前后端目录结构、路由配置、ORM 模型映射、所有占位文件 |
| 部署体系 | 部署指南文档、5 个运维脚本、FastAPI 静态文件托管（无需 Nginx） |
| 端到端验证 | pipeline_history 的完整数据链路：样例数据 → ORM Model → Service → Schema → API → 前端 Table 展示 |

### 待开发

| 模块 | 涉及文件 | 说明 |
|------|---------|------|
| 身份认证 | `auth_service`、`auth.py`、`LoginPage.tsx` | JWT 登录/登出、角色校验 |
| 数据看板 | `dashboard_service`、`dashboard.py`、`DashboardPage.tsx` | 趋势图、统计卡片、ECharts |
| 分组概览 | `overview_service`、`overview.py`、`OverviewPage.tsx` | pipeline_overview 分页查询 |
| 失败分析 | `analysis_service`、`analysis.py` | 归因标注、流转指派 |
| 用例管理 | `cases_service`、`cases.py`、`CasesPage.tsx` | 用例上下线管理 |
| 总结报告 | `report_service`、`report.py`、`ReportPage.tsx` | 报告生成、快照保存 |
| 通知催办 | `notification_service`、`notification.py`、`NotificationPage.tsx` | WeLink 推送、定时催办 |
| 管理员后台 | `admin_service`、`admin.py`、各 Admin Page | 用户/模块/字典 CRUD |

---

## 九、数据流参考（已实现的 History 模块）

```
前端浏览器
    │  GET /api/v1/history?page=1&page_size=20
    ▼
FastAPI API 层 (api/v1/history.py)
    │  参数校验 → 依赖注入 get_db
    ▼
Service 层 (services/history_service.py)
    │  构建 SQL 查询 → 动态筛选 → 分页
    ▼
ORM Model (models/pipeline_history.py)
    │  SQLAlchemy → SQL → MySQL
    ▼
MySQL pipeline_history 表
    │
    ▼ (返回)
Service 层 → API 层 (Schema 转换) → JSON 响应 → 前端 Table 渲染
```

后续开发其他模块时，遵循相同的分层模式：**Model → Schema → Service → API → 前端页面**。

---

## 十、开发快速上手

### 前提条件

- Python 3.8+（Ubuntu 20.04 系统自带）
- Node.js 18 LTS（通过 nvm 安装）
- pnpm 10+
- 可访问的 MySQL 5.7 数据库（库名 `dt_infra`，含 10 张表）

### 首次部署

```bash
cd /home/djn/code/dt-report

# 1. 配置数据库连接
cp .env.example .env
# 编辑 .env，修改 DATABASE_URL 为实际数据库地址

# 2. 一键部署（安装后端依赖 → 构建前端 → 启动后端）
bash scripts/deploy.sh
```

部署完成后访问 `http://localhost:8000` 即可看到前端页面，`http://localhost:8000/docs` 可查看 Swagger API 文档。

### 日常启停

```bash
bash scripts/start.sh      # 启动
bash scripts/stop.sh       # 停止
bash scripts/restart.sh    # 重启
bash scripts/status.sh     # 查看运行状态
```

### 修改代码后

- **仅改后端**：`bash scripts/restart.sh` 即可
- **改了前端**：需要先重新构建前端再重启后端

```bash
cd frontend && pnpm build && cd ..
bash scripts/restart.sh
```

### 前端热更新开发（可选）

如果需要前端代码修改后实时刷新（无需每次手动 build），可以单独启动 Vite 开发服务器：

```bash
cd frontend
pnpm dev
```

此模式下前端运行在 `http://localhost:3000`，API 请求自动代理到后端 `http://localhost:8000`（由 `vite.config.ts` 中的 proxy 配置）。后端仍需在另一个终端中运行。

### 完整部署文档

详见 [部署指南](03_deployment_guide.md)。
