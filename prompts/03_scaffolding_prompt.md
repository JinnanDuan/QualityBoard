# 03 - 初始化物理目录与脚手架搭建 Prompt

## 角色设定

你是一位拥有丰富全栈工程经验的高级软件架构师，精通 React + Ant Design 前端工程体系，以及 Python FastAPI + SQLAlchemy 后端工程体系。你擅长从零搭建工程化、模块化、可维护的项目脚手架。

## 任务目标

基于下方提供的【项目 PRD 摘要】和【数据库表结构】，为本项目搭建完整的**物理目录结构和工程脚手架**。

**重要约束：本次任务仅搭建骨架，不编写任何具体业务逻辑代码。** 每个文件只需包含最基本的占位内容（如空组件导出、空路由注册、空模型类定义等），确保项目能正常启动即可。

## 项目上下文

### 项目名称
团队内部测试用例批量执行结果看板与管理系统（dt-report）

### 技术栈（不可更改）

| 层级 | 技术选型 |
|------|---------|
| **前端** | React 18 + TypeScript + Ant Design 5 + ECharts（图表） + React Router v6 |
| **后端** | Python 3.11+ / FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 |
| **数据库** | MySQL 5.7（已存在，库名 `dt_infra`，**严禁任何 DDL/表结构修改**） |
| **包管理** | 前端 pnpm / 后端 pip (requirements.txt) |
| **通知渠道** | WeLink API（后续实现） |

### 🚨 数据库红线
- 已有的 8 张表结构不可修改，严禁对其执行 `ALTER TABLE`、`DROP TABLE`。ORM 模型必须与 `database/*.sql` 中的 DDL **完全一致**地反向映射。
- 允许新建表（如 `sys_audit_log`、`report_snapshot`），新建表须在 `database/` 目录下创建 SQL 迁移文件，命名格式：`V<主版本号>.<次版本号>.<修订号>__<全英文下划线描述>.sql`。
- 严禁对 `pipeline_overview`、`pipeline_history` 执行 `DELETE`。

### 数据库 10 张表总览

**已有表（8 张，结构不可修改）：**

| 表名 | 业务含义 | 读写属性 |
|------|---------|---------|
| `pipeline_overview` | 批次-分组级执行概览 | **只读** |
| `pipeline_history` | 用例级执行明细 | **部分可写**（`analyzed`、`owner`、`owner_history`） |
| `pipeline_failure_reason` | 失败归因记录 | **可读写** |
| `pipeline_cases` | 用例主数据 | **部分可写**（管理员操作上下线等） |
| `ums_email` | 员工信息 | **可读写**（管理员） |
| `ums_module_owner` | 模块-责任人映射 | **可读写**（管理员） |
| `case_failed_type` | 失败原因类型字典 | **可读写**（管理员） |
| `case_offline_type` | 下线原因类型字典 | **可读写**（管理员） |

**新增表（2 张，由本系统创建）：**

| 表名 | 业务含义 | 读写属性 | SQL 迁移文件 |
|------|---------|---------|-------------|
| `sys_audit_log` | 全局系统审计日志 | **可写**（系统自动写入） | `V1.0.9__create_sys_audit_log.sql` |
| `report_snapshot` | 批次总结报告快照 | **可读写**（管理员生成报告时写入） | `V1.1.0__create_report_snapshot.sql` |

### 业务功能模块总览（仅用于目录规划，本次不实现）

| Epic | 模块 | 简述 |
|------|------|------|
| Epic 1 | 数据看板 (Dashboard) | 批次趋势图、统计卡片、多层级下钻、多条件筛选 |
| Epic 2 | 失败分析与流转 (Analysis) | 失败归因标注、用例指派/流转、状态机、操作时间线 |
| Epic 3 | 总结报告 (Report) | 一键生成报告、分享链接、数据快照 |
| Epic 4 | 消息通知 (Notification) | 定时催办、人工催办、事件通知、WeLink 推送、防打扰 |
| Epic 5 | 基础支撑 (System) | 身份认证/RBAC、管理员后台（用户/模块/字典管理）、审计日志 |

### 页面与路由规划

| 路由 | 页面 | 可见角色 |
|------|------|---------|
| `/` | 首页大盘（趋势图 + 统计卡片） | 所有用户 |
| `/overview` | 分组执行历史列表（pipeline_overview） | 所有用户 |
| `/history` | 详细执行历史列表（pipeline_history） | 所有用户 |
| `/cases` | 用例管理（pipeline_cases 上下线） | 管理员 |
| `/report/:id?` | 批次总结报告 | 管理员生成，所有用户可查看 |
| `/admin/users` | 用户管理（ums_email） | 管理员 |
| `/admin/modules` | 模块-责任人映射管理 | 管理员 |
| `/admin/dict/failed-types` | 失败类型字典管理 | 管理员 |
| `/admin/dict/offline-types` | 下线类型字典管理 | 管理员 |
| `/admin/notification` | 通知配置与催办管理 | 管理员 |

### 后端 API 路由分组规划

| 路由前缀 | 模块 | 说明 |
|----------|------|------|
| `/api/v1/auth` | 认证 | 登录/登出/当前用户信息 |
| `/api/v1/dashboard` | 看板 | 批次趋势数据、统计卡片数据 |
| `/api/v1/overview` | 分组概览 | pipeline_overview 的分页查询 |
| `/api/v1/history` | 执行明细 | pipeline_history 的分页查询、筛选 |
| `/api/v1/analysis` | 失败分析 | 归因标注、流转指派、操作日志 |
| `/api/v1/cases` | 用例管理 | pipeline_cases 的查询与状态更新 |
| `/api/v1/report` | 总结报告 | 报告生成、查看、分享 |
| `/api/v1/notification` | 通知 | 催办、通知配置 |
| `/api/v1/admin/users` | 用户管理 | ums_email CRUD |
| `/api/v1/admin/modules` | 模块映射 | ums_module_owner CRUD |
| `/api/v1/admin/dict` | 字典管理 | case_failed_type / case_offline_type CRUD |

---

## 输出要求

### 一、目录结构

请生成以下物理目录结构（已标注每个目录/文件的职责）：

```
dt-report/
├── frontend/                          # 前端工程根目录
│   ├── package.json                   # 依赖声明（React 18, antd 5, echarts, react-router-dom v6, axios 等）
│   ├── tsconfig.json                  # TypeScript 配置
│   ├── vite.config.ts                 # Vite 构建配置（含 API 代理到后端）
│   ├── index.html                     # HTML 入口
│   ├── public/
│   └── src/
│       ├── main.tsx                   # 应用入口
│       ├── App.tsx                    # 根组件（路由出口 + 全局 Layout）
│       ├── routes/
│       │   └── index.tsx              # 集中式路由配置（基于 react-router-dom v6）
│       ├── layouts/
│       │   └── MainLayout.tsx         # 主布局（左侧 Sider 导航 + 右侧内容区）
│       ├── pages/                     # 页面组件（按业务模块划分）
│       │   ├── dashboard/
│       │   │   └── DashboardPage.tsx  # 首页大盘
│       │   ├── overview/
│       │   │   └── OverviewPage.tsx   # 分组执行历史
│       │   ├── history/
│       │   │   └── HistoryPage.tsx    # 详细执行历史
│       │   ├── cases/
│       │   │   └── CasesPage.tsx      # 用例管理（管理员）
│       │   ├── report/
│       │   │   └── ReportPage.tsx     # 总结报告
│       │   ├── admin/
│       │   │   ├── UsersPage.tsx      # 用户管理
│       │   │   ├── ModulesPage.tsx    # 模块映射管理
│       │   │   ├── FailedTypesPage.tsx    # 失败类型字典
│       │   │   ├── OfflineTypesPage.tsx   # 下线类型字典
│       │   │   └── NotificationPage.tsx   # 通知配置
│       │   └── auth/
│       │       └── LoginPage.tsx      # 登录页
│       ├── components/                # 全局通用组件
│       │   └── .gitkeep
│       ├── hooks/                     # 自定义 Hooks
│       │   └── .gitkeep
│       ├── services/                  # API 请求层（axios 封装 + 各模块 API）
│       │   ├── request.ts             # axios 实例（baseURL、拦截器、错误处理）
│       │   └── index.ts              # 各模块 API 方法的集中导出
│       ├── stores/                    # 状态管理（如需要，可用 zustand 或 React Context）
│       │   └── .gitkeep
│       ├── types/                     # TypeScript 类型定义
│       │   └── index.ts              # 与后端 Pydantic schema 对齐的前端类型
│       ├── utils/                     # 通用工具函数
│       │   └── index.ts
│       └── styles/                    # 全局样式
│           └── global.css
│
├── backend/                           # 后端工程根目录
│   ├── requirements.txt               # Python 依赖（fastapi, uvicorn, sqlalchemy, pymysql, pydantic 等）
│   ├── main.py                        # FastAPI 应用入口（app 实例创建、路由注册、中间件、CORS）
│   ├── core/                          # 核心配置与基础设施
│   │   ├── __init__.py
│   │   ├── config.py                  # 全局配置（数据库连接、管理员工号列表、JWT密钥等，读取环境变量）
│   │   ├── database.py                # SQLAlchemy async engine / session 工厂
│   │   ├── security.py                # 认证与鉴权工具（JWT 生成/验证、角色校验依赖项）
│   │   └── dependencies.py            # FastAPI 公共依赖项（get_db_session、get_current_user 等）
│   ├── models/                        # SQLAlchemy ORM 模型（严格映射已有表结构 + 新增表）
│   │   ├── __init__.py
│   │   ├── base.py                    # declarative_base 与公共 mixin（如 TimestampMixin）
│   │   ├── pipeline_overview.py       # pipeline_overview 表映射（已有表）
│   │   ├── pipeline_history.py        # pipeline_history 表映射（已有表）
│   │   ├── pipeline_failure_reason.py # pipeline_failure_reason 表映射（已有表）
│   │   ├── pipeline_cases.py          # pipeline_cases 表映射（已有表）
│   │   ├── ums_email.py               # ums_email 表映射（已有表）
│   │   ├── ums_module_owner.py        # ums_module_owner 表映射（已有表）
│   │   ├── case_failed_type.py        # case_failed_type 表映射（已有表）
│   │   ├── case_offline_type.py       # case_offline_type 表映射（已有表）
│   │   ├── sys_audit_log.py           # sys_audit_log 表映射（新增表）
│   │   └── report_snapshot.py         # report_snapshot 表映射（新增表）
│   ├── schemas/                       # Pydantic v2 数据校验模型
│   │   ├── __init__.py
│   │   ├── auth.py                    # 登录请求/响应 schema
│   │   ├── dashboard.py               # 看板数据 schema
│   │   ├── overview.py                # 分组概览 schema
│   │   ├── history.py                 # 执行明细 schema
│   │   ├── analysis.py                # 失败分析/归因 schema
│   │   ├── cases.py                   # 用例管理 schema
│   │   ├── report.py                  # 总结报告 schema
│   │   ├── notification.py            # 通知 schema
│   │   └── common.py                  # 公共 schema（分页、通用响应包装等）
│   ├── api/                           # API 路由层
│   │   ├── __init__.py
│   │   ├── router.py                  # 总路由注册（将各子模块 router include 到 /api/v1 前缀下）
│   │   └── v1/                        # v1 版本 API
│   │       ├── __init__.py
│   │       ├── auth.py                # /api/v1/auth
│   │       ├── dashboard.py           # /api/v1/dashboard
│   │       ├── overview.py            # /api/v1/overview
│   │       ├── history.py             # /api/v1/history
│   │       ├── analysis.py            # /api/v1/analysis
│   │       ├── cases.py               # /api/v1/cases
│   │       ├── report.py              # /api/v1/report
│   │       ├── notification.py        # /api/v1/notification
│   │       └── admin.py               # /api/v1/admin（用户管理、模块映射、字典管理合并）
│   ├── services/                      # 业务逻辑层（被 API 层调用）
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── dashboard_service.py
│   │   ├── overview_service.py
│   │   ├── history_service.py
│   │   ├── analysis_service.py
│   │   ├── cases_service.py
│   │   ├── report_service.py
│   │   ├── notification_service.py
│   │   └── admin_service.py
│   ├── utils/                         # 通用工具
│   │   ├── __init__.py
│   │   └── audit.py                   # 审计日志工具（写入 JSON Lines 文件）
│   └── data/                          # 文件系统持久化目录（用于临时文件等）
│       └── .gitkeep
│
├── database/                          # 数据库 DDL（已有表不可修改，可新增表）
│   ├── README.md
│   ├── V1.0.0~V1.0.8__*.sql          # 已有的 9 个 SQL 文件（不可修改）
│   ├── V1.0.9__create_sys_audit_log.sql       # 新增：审计日志表
│   └── V1.1.0__create_report_snapshot.sql     # 新增：报告快照表
│
├── docs/                              # 项目文档（已存在）
│   ├── 01_user_story_map.md
│   └── 02_prd.md
│
├── prompts/                           # AI prompt 记录（已存在）
│
├── .env.example                       # 环境变量模板
├── .gitignore                         # Git 忽略规则
└── README.md                          # 项目说明
```

### 二、各文件生成规则

#### 前端

1. **`package.json`**：声明所有核心依赖及版本，包含 `dev`（启动 Vite dev server）和 `build` 脚本。
2. **`vite.config.ts`**：配置 `server.proxy` 将 `/api` 代理到 `http://localhost:8000`。
3. **`src/main.tsx`**：标准 React 入口，挂载 `<App />`。
4. **`src/App.tsx`**：使用 `<BrowserRouter>` 包裹路由出口。
5. **`src/routes/index.tsx`**：集中定义所有页面路由（使用 `useRoutes` 或 `<Routes>`），路由路径严格遵循上方【页面与路由规划】。
6. **`src/layouts/MainLayout.tsx`**：使用 Ant Design `Layout` + `Sider` + `Menu`，左侧导航包含所有菜单项，内容区渲染 `<Outlet />`。
7. **所有 Page 组件**：每个页面仅导出一个空壳函数组件，返回页面标题占位文字（如 `<div>首页大盘</div>`）。
8. **`src/services/request.ts`**：创建 axios 实例，baseURL 为 `/api/v1`，配置请求/响应拦截器骨架。
9. **`src/types/index.ts`**：定义与后端 8 张表对应的 TypeScript interface 占位。

#### 后端

1. **`requirements.txt`**：列出所有依赖及版本。
2. **`main.py`**：创建 FastAPI app，注册 CORS 中间件、include 总路由。启动命令为 `uvicorn backend.main:app --reload`。
3. **`core/config.py`**：使用 Pydantic `BaseSettings` 从环境变量读取配置（`DATABASE_URL`、`SECRET_KEY`、`ADMIN_EMPLOYEE_IDS` 等）。
4. **`core/database.py`**：创建 async SQLAlchemy engine 和 async session factory，提供 `get_db` async generator。
5. **`core/security.py`**：预留 JWT 生成/验证函数签名和角色校验依赖项签名。
6. **`models/*.py`**：每张表一个 ORM 模型文件。**已有表必须严格按照 `database/*.sql` 中的 DDL 反向映射**，包括：表名（`__tablename__`）、所有字段名、字段类型、主键、索引、外键约束、默认值、注释。新增表（`sys_audit_log`、`report_snapshot`）同样需严格按照对应 SQL 文件映射。特别注意 `case_failed_type` 表的时间字段是 `created_time/updated_time`（与其他表不同）。所有模型使用 `__table_args__ = {'extend_existing': True}` 以避免冲突。
7. **`schemas/*.py`**：每个业务模块一个 schema 文件，仅定义类名和 `pass` 占位（如 `class HistoryListResponse(BaseModel): pass`）。`common.py` 中定义分页请求/响应基类。
8. **`api/router.py`**：将各 v1 子路由通过 `include_router` 注册到统一前缀 `/api/v1` 下。
9. **`api/v1/*.py`**：每个路由模块创建 `APIRouter`，仅声明路由前缀和 tags，不编写具体端点实现。
10. **`services/*.py`**：每个 service 文件仅定义类名和 `pass` 占位。
11. **`utils/audit.py`**：预留审计日志写入函数签名（写入 `sys_audit_log` 表）。

#### 根目录

1. **`.env.example`**：列出所有需要的环境变量 key 及注释说明（`DATABASE_URL`、`SECRET_KEY`、`ADMIN_EMPLOYEE_IDS`、`WELINK_API_URL`、`WELINK_APP_ID` 等）。
2. **`.gitignore`**：涵盖 Python（`__pycache__`、`.venv`、`*.pyc`）、Node.js（`node_modules`、`dist`）、IDE（`.idea`、`.vscode`）、环境变量（`.env`）、数据文件等。
3. **`README.md`**：简要项目介绍、技术栈、快速启动说明（前后端分别如何启动）。

### 三、红线提醒（生成代码时必须遵守）

1. **ORM 模型只做映射，不做迁移**：已有表的 model 绝不调用 `metadata.create_all()`；新增表通过 `database/` 目录下的 SQL 迁移文件手动执行建表。
2. **不编写任何具体业务逻辑**：API 端点函数体为空或仅返回 `{"message": "TODO"}`，service 方法仅 `pass`。
3. **前端组件不编写具体 UI 实现**：每个 Page 仅返回一行占位文本。
4. **确保脚手架可启动**：前端 `pnpm dev` 能正常打开页面看到导航菜单和占位内容；后端 `uvicorn` 能正常启动并访问 `/docs` 看到 Swagger UI 及所有路由分组。
