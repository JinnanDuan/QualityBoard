# 技术架构说明

> 本文档从逻辑视图角度描述 dt-report 系统的整体技术架构，包括系统上下文、分层结构、核心数据流、模块划分和部署模型。

---

## 1. 系统上下文

```
                              ┌──────────────────────────┐
                              │      dt-report 系统       │
                              │  (FastAPI + React SPA)    │
                              └────────┬─────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
  ┌───────────┐              ┌──────────────────┐           ┌──────────────┐
  │  浏览器    │              │  MySQL 5.7       │           │  WeLink API  │
  │ (团队成员) │              │  dt_infra 库     │           │ (消息通知)   │
  └───────────┘              │  10 张表          │           └──────────────┘
                              └──────────────────┘
```

| 外部实体 | 交互方式 | 说明 |
|----------|---------|------|
| 浏览器（团队成员） | HTTP/HTTPS | 普通用户和管理员通过浏览器访问系统 |
| MySQL 5.7（dt_infra） | aiomysql 异步连接 | 已有 8 张表（只读/部分可写）+ 2 张新增表 |
| Jenkins 流水线 | 无直接交互 | Jenkins 将执行结果写入 MySQL，本系统只读消费 |
| WeLink API | HTTP 外呼 | 催办通知、指派通知、定时提醒（待实现） |

---

## 2. 技术栈总览

```
┌─────────────────────────────────────────────────────────┐
│                     前端 (frontend/)                      │
│  React 18 · TypeScript · Ant Design 5 · ECharts         │
│  React Router v6 · Axios · Vite · pnpm                  │
├─────────────────────────────────────────────────────────┤
│                     后端 (backend/)                       │
│  Python 3.8 · FastAPI · SQLAlchemy 2.0 (async)          │
│  Pydantic v2 · aiomysql · uvicorn                       │
├─────────────────────────────────────────────────────────┤
│                     数据库                                │
│  MySQL 5.7 · 字符集 utf8mb4 · 排序 utf8mb4_unicode_ci   │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 后端分层架构

后端采用严格的四层架构，每一层职责单一、依赖方向自上而下：

```
  HTTP 请求
      │
      ▼
┌──────────────────────────────────────────────┐
│  API 层 (backend/api/v1/)                     │
│  职责：路由定义、参数校验、依赖注入、响应封装  │
│  关键机制：APIRouter / Query / Depends(get_db) │
├──────────────────────────────────────────────┤
│  Service 层 (backend/services/)               │
│  职责：业务逻辑、查询构建、数据聚合            │
│  关键机制：async 函数，返回 (items, total)     │
├──────────────────────────────────────────────┤
│  Schema 层 (backend/schemas/)                 │
│  职责：数据校验、序列化、API 契约定义          │
│  关键机制：Pydantic BaseModel / from_attributes│
├──────────────────────────────────────────────┤
│  Model 层 (backend/models/)                   │
│  职责：ORM 映射，严格对齐数据库 DDL            │
│  关键机制：Mapped[] / mapped_column()          │
└──────────────────────────────────────────────┘
      │
      ▼
   MySQL 5.7
```

### 3.1 核心基础设施

| 模块 | 文件 | 职责 |
|------|------|------|
| 配置中心 | `core/config.py` | Pydantic BaseSettings，从 `.env` 读取 DATABASE_URL、SECRET_KEY、ADMIN_EMPLOYEE_IDS 等 |
| 数据库连接 | `core/database.py` | 创建异步引擎（连接池）和会话工厂，提供 `get_db()` 依赖注入 |
| 认证鉴权 | `core/security.py` | JWT 生成/验证、管理员角色校验 |
| 审计日志 | `utils/audit.py` | 写入 sys_audit_log 表（占位） |

### 3.2 请求处理流程

以 `GET /api/v1/history?page=1&case_result=failed` 为例：

```
浏览器
  │ GET /api/v1/history?page=1&case_result=failed
  ▼
FastAPI 路由匹配
  │ → api/v1/history.py :: get_history_list()
  │ → Depends(get_db) 自动创建 AsyncSession
  │ → Query() 参数校验（page >= 1, page_size <= 100）
  ▼
Service 层
  │ → history_service.list_history(db, query)
  │ → select(PipelineHistory).where(...).order_by(...).offset(...).limit(...)
  │ → 并行查询 COUNT 获取总数
  ▼
MySQL 执行 SQL
  │
  ▼ (返回 ORM 对象列表)
Service → API 层
  │ → HistoryItem.model_validate(orm_obj)  # ORM → Pydantic
  │ → PageResponse(items=[...], total=20, page=1, page_size=20)
  ▼
JSON 响应 → 浏览器
```

---

## 4. 前端架构

```
┌───────────────────────────────────────────────────────┐
│  App.tsx                                               │
│  ├── BrowserRouter + ConfigProvider (Ant Design 中文)  │
│  └── AppRoutes (routes/index.tsx)                      │
│       ├── /login → LoginPage                           │
│       └── / → MainLayout (Sider + Content)             │
│            ├── / → DashboardPage                       │
│            ├── /overview → OverviewPage                 │
│            ├── /history → HistoryPage ←─── 已实现      │
│            ├── /cases → CasesPage                      │
│            ├── /report/:id? → ReportPage               │
│            └── /admin/* → 管理员页面群                  │
└───────────────────────────────────────────────────────┘
```

### 4.1 数据流

```
Page 组件 (useState / useEffect)
    │ 调用
    ▼
services/index.ts (xxxApi.list)
    │ 调用
    ▼
services/request.ts (Axios 实例, baseURL=/api/v1)
    │ HTTP GET/POST
    ▼
后端 API → JSON 响应
    │
    ▼
Page 组件 setState → Ant Design Table 渲染
```

### 4.2 关键约定

- 前端 TypeScript 接口与后端 Pydantic Schema 字段名严格一致（snake_case）
- 分页统一使用 `PageResponse<T>` 泛型接口 `{ items, total, page, page_size }`
- Axios 响应拦截器直接提取 `response.data`，API 方法返回业务数据

---

## 5. 数据库架构

### 5.1 ER 关系概览

```
pipeline_overview (只读)          pipeline_history (部分可写)
┌─────────────────────┐          ┌─────────────────────────┐
│ batch               │◄────────►│ start_time (=batch)      │
│ subtask             │          │ subtask                  │
│ case_num            │          │ case_name                │
│ passed_num          │          │ case_result              │
│ failed_num          │          │ main_module ─────────┐   │
│ platform            │          │ owner ──────────┐    │   │
└─────────────────────┘          │ analyzed        │    │   │
                                  └────────┬───────┘────┘───┘
                                           │       │    │
                           pipeline_failure_reason  │    │
                           ┌───────────────────┐   │    │
                           │ case_name ────────┼───┘    │
                           │ failed_batch      │        │
                           │ owner ────────────┼──►ums_email
                           │ failed_type ──────┼──►case_failed_type
                           │ analyzer          │   ┌────────────────┐
                           └───────────────────┘   │ employee_id    │
                                                    │ name / email   │
                                                    └────────────────┘
                           ums_module_owner
                           ┌───────────────────┐
                           │ module ◄──────────┼─── pipeline_history.main_module
                           │ owner             │
                           └───────────────────┘

pipeline_cases             case_offline_type        sys_audit_log (新增)
┌─────────────────────┐    ┌──────────────────┐     ┌──────────────────────┐
│ case_name            │    │ offline_reason    │     │ operator / action    │
│ is_online            │    │ _type             │     │ target_type / id     │
│ offline_reason_type──┼──► └──────────────────┘     │ detail / ip          │
└─────────────────────┘                              └──────────────────────┘

                           report_snapshot (新增)
                           ┌──────────────────────┐
                           │ batch / snapshot_data │
                           │ generated_by / at     │
                           └──────────────────────┘
```

### 5.2 表的读写属性

| 表 | 读 | 写 | 约束 |
|----|----|----|------|
| pipeline_overview | 全表 | 禁止 | 只读，禁止 DELETE |
| pipeline_history | 全表 | analyzed, owner, owner_history | 禁止 DELETE |
| pipeline_failure_reason | 全表 | 全字段 CRUD | — |
| pipeline_cases | 全表 | is_online, state 等 | 管理员操作 |
| ums_email | 全表 | 全字段 CRUD | 管理员操作 |
| ums_module_owner | 全表 | 全字段 CRUD | 管理员操作 |
| case_failed_type | 全表 | 全字段 CRUD | 管理员操作 |
| case_offline_type | 全表 | 全字段 CRUD | 管理员操作 |
| sys_audit_log | 全表 | INSERT only | 系统自动写入 |
| report_snapshot | 全表 | INSERT / SELECT | 管理员生成报告时写入 |

---

## 6. 业务模块划分

系统按 5 个 Epic 划分业务模块，每个模块对应后端和前端的一组文件：

| Epic | 模块 | 后端路由 | 前端页面 | 核心数据表 |
|------|------|---------|---------|-----------|
| Epic 1 | 数据看板 | `/api/v1/dashboard` | DashboardPage | pipeline_overview |
| Epic 1 | 分组概览 | `/api/v1/overview` | OverviewPage | pipeline_overview |
| Epic 1 | 执行明细 | `/api/v1/history` | HistoryPage | pipeline_history |
| Epic 2 | 失败分析 | `/api/v1/analysis` | (HistoryPage 内交互) | pipeline_failure_reason |
| Epic 3 | 总结报告 | `/api/v1/report` | ReportPage | report_snapshot |
| Epic 4 | 消息通知 | `/api/v1/notification` | NotificationPage | WeLink API |
| Epic 5 | 认证 | `/api/v1/auth` | LoginPage | ums_email |
| Epic 5 | 用例管理 | `/api/v1/cases` | CasesPage | pipeline_cases |
| Epic 5 | 管理员后台 | `/api/v1/admin/*` | Admin 页面群 | ums_*, case_*_type |

---

## 7. 认证与权限模型

```
                     ┌─────────────┐
                     │  浏览器登录   │
                     └──────┬──────┘
                            │ POST /api/v1/auth/login
                            ▼
                     ┌─────────────┐
                     │ 验证账号密码  │
                     │ 签发 JWT     │
                     └──────┬──────┘
                            │ Authorization: Bearer <token>
                            ▼
              ┌─────────────────────────────┐
              │         角色判定              │
              │  token.sub in ADMIN_IDS?     │
              ├──────────────┬──────────────┤
              │  是 → 管理员  │  否 → 普通用户│
              └──────────────┴──────────────┘
                     │                │
                     ▼                ▼
              全部功能可用        只读 + 标注 + 指派
              (含管理后台)        (禁止管理操作)
```

- 认证方式：JWT (HS256)，token 有效期 8 小时
- 角色判定：token 中的 `sub`（员工工号）是否在 `ADMIN_EMPLOYEE_IDS` 列表中
- 权限校验：后端 `Depends(require_admin)` 拦截管理员接口

---

## 8. 部署架构

```
┌─────────────────────────────────────────────────────┐
│  Ubuntu 20.04 LTS 服务器                             │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  uvicorn（默认端口 8000，环境变量 PORT 可覆盖）   │  │
│  │  ┌──────────────────────────────────────────┐  │  │
│  │  │  FastAPI 应用                             │  │  │
│  │  │  ├── /api/v1/*  → API 路由               │  │  │
│  │  │  ├── /assets/*  → 前端静态资源            │  │  │
│  │  │  └── /*         → SPA fallback (index.html)│ │  │
│  │  └──────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────┘  │
│         │                                             │
│         │ aiomysql (异步连接池)                        │
│         ▼                                             │
│  ┌──────────────┐                                    │
│  │ MySQL 5.7    │ ← 可以在同机或远程服务器             │
│  │ dt_infra 库  │                                     │
│  └──────────────┘                                    │
└─────────────────────────────────────────────────────┘
```

| 组件 | 说明 |
|------|------|
| uvicorn | ASGI 服务器，后台运行，PID 写入 `.pid`，日志输出到 `app.log` |
| FastAPI | 同时提供 API 接口和前端静态文件托管（无需 Nginx） |
| 前端构建产物 | `frontend/dist/` 由 Vite 构建，通过 FastAPI StaticFiles 挂载 |
| 运维脚本 | `scripts/` 下 5 个脚本管理启停部署 |
| 环境配置 | `.env` 文件存放数据库连接、JWT 密钥等敏感信息 |

---

## 9. 关键设计决策记录

| 决策 | 选项 | 结论 | 理由 |
|------|------|------|------|
| 前端托管方式 | Nginx 反向代理 vs FastAPI 直接托管 | FastAPI 直接托管 | 内部工具，简化部署，减少组件 |
| 数据库驱动 | pymysql (同步) vs aiomysql (异步) | aiomysql | 配合 FastAPI 异步架构，提升并发 |
| ORM 风格 | SQLAlchemy 1.x 传统式 vs 2.0 声明式 | 2.0 声明式 (Mapped[]) | 类型安全，现代风格 |
| Schema 库 | Pydantic v1 vs v2 | Pydantic v2 | model_config 替代 class Config，性能更优 |
| 包管理 | npm vs pnpm | pnpm | 更快、更省磁盘、严格依赖隔离 |
| 认证方案 | Session vs JWT | JWT (HS256) | 无状态，适合 SPA 架构 |
