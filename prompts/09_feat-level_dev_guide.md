# 09 - 特性级的AI辅助开发方法论（以登录认证特性AI辅助开发为例）

## 开发方法论

采用 **SDG（规约驱动生成）+ TDG（测试驱动生成）** 模式，分三步执行：
1. **第一步**：生成 API 规约（Spec），锁定接口契约，人工确认后进入第二步
2. **第二步**：严格按照规约生成后端和前端代码
3. **第三步**：按照规约生成测试用例，验证代码正确性

---

## 第一步：生成登录认证 API 规约（Spec）

### 角色设定
你是本项目的后端架构师，精通 FastAPI + SQLAlchemy + Pydantic v2 技术栈。

### 任务
请先输出一份 Markdown 格式的 **登录认证模块 API 规约**，不要写任何代码，把规约（spec）先输出给我review。

### 项目上下文

**认证方案（PRD 原文）：** "系统需实现统一账号登录功能，但是对接内部域账号认证的具体实现可以先以空实现替代，先配置为简单写死的管理员账号和普通用户账号认证实现。"

**用户表 `ums_email` 现有结构（不可修改）：**
```
employee_id  varchar(20)   PK    工号
name         varchar(50)         姓名
email        varchar(100)  UQ    邮箱
domain_account varchar(255)      域账号
created_at   datetime            创建时间
updated_at   datetime            更新时间
```
> 注意：该表**没有密码字段**。MVP 阶段采用统一的简单密码策略，后续对接域账号认证时替换。

**角色模型：**
- 管理员：工号在环境变量 `ADMIN_EMPLOYEE_IDS`（List[str]）中的用户
- 普通用户：`ums_email` 表中存在、但不在 `ADMIN_EMPLOYEE_IDS` 中的用户

**已有基础设施（已实现，Spec 需与之对齐）：**
- `backend/core/config.py`：`Settings` 类，含 `SECRET_KEY`、`ACCESS_TOKEN_EXPIRE_MINUTES`（默认480分钟=8小时）、`ADMIN_EMPLOYEE_IDS`
- `backend/core/security.py`：`create_access_token(subject)`、`verify_token(token)`、`require_admin` 依赖项，算法 HS256
- `backend/core/dependencies.py`：`get_current_user` 依赖项（从 Bearer token 解析 payload 返回 dict）
- `frontend/src/services/request.ts`：Axios 实例，请求拦截器自动从 `localStorage.getItem("token")` 注入 `Authorization: Bearer <token>`

### 规约必须明确界定的内容

1. **MVP 认证策略：** 登录时如何验证身份（工号 + 密码的具体规则，密码如何比对）
2. **JWT Payload 结构：** `sub` 字段含义、是否包含 `role`/`name` 等附加信息、`exp` 过期时间
3. **`POST /api/v1/auth/login` 接口规约：**
   - 请求体（Pydantic Schema 字段定义）
   - 成功响应体（含 token 和用户信息）
   - 失败响应（401 账号不存在、401 密码错误）
4. **`GET /api/v1/auth/me` 接口规约：**
   - 需要携带 Bearer token
   - 响应体（当前用户的完整信息 + 角色）
5. **`POST /api/v1/auth/logout` 接口规约：** JWT 无状态方案下的登出处理方式
6. **角色判定逻辑：** 后端如何区分管理员与普通用户

### 格式要求
请以如下结构输出 Spec：
```
## 1. 认证策略
## 2. JWT Payload 定义
## 3. POST /api/v1/auth/login
   ### 请求体
   ### 成功响应 (200)
   ### 失败响应 (401)
## 4. GET /api/v1/auth/me
   ### 请求头
   ### 成功响应 (200)
   ### 失败响应 (401)
## 5. POST /api/v1/auth/logout
## 6. 角色与权限判定
```

---

## 第二步：按规约生成后端 + 前端代码

> **前置条件：** 第一步生成的 Spec 已经过人工确认。

### 角色设定
你是本项目的全栈开发工程师。请严格遵照第一步确认的 API 规约，生成后端和前端代码。

### 2.1 后端代码生成

按照项目分层架构 **Schema → Service → API** 的顺序实现（Model 层 `ums_email` 已存在，无需新建）。

#### 2.1.1 Schema 层 — `backend/schemas/auth.py`

当前状态（空壳占位）：
```python
from pydantic import BaseModel

class LoginRequest(BaseModel):
    pass

class LoginResponse(BaseModel):
    pass

class CurrentUserResponse(BaseModel):
    pass
```

**要求：**
- 按照 Spec 中定义的请求体/响应体，填充完整的字段定义
- 响应模型设置 `model_config = {"from_attributes": True}`
- 字段类型标注使用 `Optional[X]` 语法（Python 3.8 兼容，禁止 `X | None`）

#### 2.1.2 Service 层 — `backend/services/auth_service.py`

当前状态（空壳占位）：
```python
class AuthService:
    pass
```

**要求：**
- 改为纯 `async def` 函数风格（不是类），与项目约定一致
- 参考已实现的 `backend/services/history_service.py` 的函数签名风格
- 实现登录验证逻辑：查询 `ums_email` 表校验用户是否存在 → 校验密码 → 生成 JWT token
- 实现获取当前用户信息逻辑：根据 token 中的 `sub`（工号）查询用户详情 + 判定角色
- 使用 `backend/core/security.py` 中已有的 `create_access_token` 函数
- 使用 `backend/core/config.py` 中已有的 `settings.ADMIN_EMPLOYEE_IDS` 判定角色
- 数据库操作使用 `select()` 构建查询（SQLAlchemy 2.0 async 风格）

#### 2.1.3 API 层 — `backend/api/v1/auth.py`

当前状态（占位路由）：
```python
from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["认证"])

@router.post("/login")
async def login():
    return {"message": "TODO"}

@router.post("/logout")
async def logout():
    return {"message": "TODO"}

@router.get("/me")
async def get_current_user_info():
    return {"message": "TODO"}
```

**要求：**
- 数据库会话通过 `db: AsyncSession = Depends(get_db)` 注入
- `/login` 端点：设置 `response_model`，调用 service 层函数
- `/me` 端点：通过 `Depends(get_current_user)` 获取当前用户 payload，再查询完整用户信息
- `/logout` 端点：按 Spec 中的方案处理

#### 2.1.4 security.py / dependencies.py 补充

根据 Spec 的需要，检查并补充 `backend/core/security.py` 和 `backend/core/dependencies.py`：
- 如果 Spec 中的 JWT Payload 需要额外字段（如 role、name），需修改 `create_access_token` 的参数和编码逻辑
- 确保 `get_current_user` 依赖项返回的信息与 Spec 一致

### 2.2 前端代码生成

#### 2.2.1 TypeScript 类型与 API 方法

在 `frontend/src/services/` 或 `frontend/src/types/` 中，按照 Spec 定义：
- `LoginRequest` 接口（字段名与后端 Schema **完全一致**，保持 snake_case）
- `LoginResponse` 接口
- `CurrentUser` 接口（含角色字段）
- `authApi` 对象，包含 `login()`、`logout()`、`me()` 方法
- 使用 `request.post()` / `request.get()` 调用（request 实例来自 `./request.ts`）

#### 2.2.2 登录页面 — `frontend/src/pages/auth/LoginPage.tsx`

当前状态（空壳占位）：
```tsx
export default function LoginPage() {
  return <div>登录页</div>;
}
```

**要求：**
- 使用 Ant Design 组件（`Form`、`Input`、`Button`、`Card`、`message`）构建居中的登录表单
- 表单字段：工号（employee_id）、密码（password）、提交按钮
- 包含表单验证、提交 loading 状态、错误提示
- 登录成功后：将 token 存储到 `localStorage`（key 为 `token`，与 `request.ts` 中的拦截器对齐），跳转到首页 `/`
- 已登录用户访问 `/login` 应自动跳转到首页
- 页面美观、居中显示，体现系统名称 "dt-report"

#### 2.2.3 路由守卫

当前路由配置（`frontend/src/routes/index.tsx`）没有鉴权保护，任何人都可以直接访问所有页面。

**要求：**
- 创建 `RequireAuth` 路由守卫组件：检查 `localStorage` 中是否有 token，无则重定向到 `/login`
- 将 `MainLayout` 包裹在 `RequireAuth` 中，使所有业务页面都受保护
- `/login` 路由不受保护

#### 2.2.4 响应拦截器增强 — `frontend/src/services/request.ts`

当前 Axios 响应拦截器只做了 `response.data` 提取，没有处理 401 场景。

**要求：**
- 在响应错误拦截器中：如果后端返回 `401`，清除 `localStorage` 中的 token，跳转到 `/login`
- 注意：登录接口本身的 401 不应触发跳转（由页面自行处理错误提示）

#### 2.2.5 侧边栏权限控制 — `frontend/src/layouts/MainLayout.tsx`

当前侧边栏对所有用户展示完全相同的菜单，包括管理员专属的菜单项。

**要求：**
- 页面加载时调用 `GET /api/v1/auth/me` 获取当前用户信息和角色
- 根据角色动态过滤菜单项：普通用户隐藏"管理员后台"整个子菜单和"用例管理"
- Header 区域展示当前登录用户姓名，并提供"退出登录"操作

### 2.3 全局约束提醒

- **Python 类型标注**：使用 `Optional[X]`，禁止 `X | None`
- **数据库红线**：不允许修改 `ums_email` 表结构，不允许调用 `Base.metadata.create_all()`
- **SQL 语法**：仅 MySQL 5.7 兼容语法
- **用户可见文字**：全部使用中文
- 遵守 `.cursorrules` 中定义的所有编码契约

---

## 第三步：TDG 验证闭环

> **前置条件：** 第二步的代码已生成完毕且项目可正常启动。

### 角色设定
你是本项目的测试工程师。请运用 TDG 思路，针对第一步的 Spec 设计测试场景并验证。

### 3.1 后端接口测试

针对 `POST /api/v1/auth/login` 编写以下测试场景：

| # | 场景 | 输入 | 预期结果 |
|---|------|------|---------|
| 1 | 正常登录（普通用户） | ums_email 表中存在的工号 + 正确密码 | 200，返回 token，me 接口返回 role=user |
| 2 | 正常登录（管理员） | ADMIN_EMPLOYEE_IDS 中的工号 + 正确密码 | 200，返回 token，me 接口返回 role=admin |
| 3 | 工号不存在 | 不存在的工号 + 任意密码 | 401，明确提示账号不存在 |
| 4 | 密码错误 | 存在的工号 + 错误密码 | 401，明确提示密码错误 |
| 5 | 空字段 | 工号或密码为空 | 422（Pydantic 校验失败） |

针对 `GET /api/v1/auth/me` 编写以下测试场景：

| # | 场景 | 输入 | 预期结果 |
|---|------|------|---------|
| 1 | 携带有效 token | Authorization: Bearer <valid_token> | 200，返回完整用户信息 + 角色 |
| 2 | 不携带 token | 无 Authorization 头 | 401 |
| 3 | 携带过期/无效 token | Authorization: Bearer <invalid> | 401 |

### 3.2 前后端联调验证清单

请逐项在浏览器中手动验证：

- [ ] 访问首页 `/` 未登录状态下，自动跳转到 `/login`
- [ ] 登录页面渲染正常，表单包含工号输入框、密码输入框、登录按钮
- [ ] 输入正确的工号和密码，点击登录，跳转到首页
- [ ] 登录后刷新页面，仍保持登录状态（token 在 localStorage 中）
- [ ] 以普通用户登录，侧边栏不展示"管理员后台"和"用例管理"
- [ ] 以管理员登录，侧边栏展示完整菜单
- [ ] Header 区域显示当前用户姓名
- [ ] 点击"退出登录"，清除 token，跳转回登录页
- [ ] 退出后直接访问 `/history`，被重定向到 `/login`
- [ ] 已登录状态下访问 `/login`，自动跳转到首页
