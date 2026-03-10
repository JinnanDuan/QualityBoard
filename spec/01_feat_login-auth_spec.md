# 登录认证模块 API 规约 (Auth Module Spec)

## 1. 认证策略

### 模式切换规则

- **LDAP 模式**：当 `LDAP_HOST` 非空时启用。使用域账号 + 域密码登录，LDAP 校验通过即登录，无用户白名单。
- **MVP 模式**：当 `LDAP_HOST` 为空时启用。使用工号 + 统一密码，`ums_email` 表白名单。

### LDAP 模式

| 项目 | 说明 |
|------|------|
| **认证方式** | 域账号（比工号多首字母，如 `wW00001`）+ 域密码 |
| **用户来源** | 无白名单，LDAP 校验通过即可登录 |
| **密码校验** | 通过 `ldap3` 连接 LDAP 服务器，bind 校验域账号与密码 |
| **配置** | `LDAP_HOST`、`LDAP_PORT`（必填），`LDAP_DOMAIN`（可选，用于拼接 `domain_account@LDAP_DOMAIN`） |
| **降级** | LDAP 未配置或连接失败时回退 MVP 模式 |

### MVP 模式

| 项目 | 说明 |
|------|------|
| **认证方式** | 工号（`employee_id`）+ 统一密码 |
| **用户来源** | `ums_email` 表。只有表中存在的 `employee_id` 才允许登录 |
| **密码策略** | 环境变量统一密码 `MVP_LOGIN_PASSWORD`，所有用户共用 |
| **密码校验逻辑** | `request.password == settings.MVP_LOGIN_PASSWORD`（明文比对） |

### 通用

| 项目 | 说明 |
|------|------|
| **会话方案** | 无状态 JWT（HS256），Token 通过 HTTP Header `Authorization: Bearer <token>` 传递 |
| **Token 存储** | 前端登录成功后存入 `localStorage`，key 为 `"token"` |
| **Token 有效期** | `ACCESS_TOKEN_EXPIRE_MINUTES`，默认 480 分钟（8 小时） |

---

## 2. JWT Payload 定义

```json
{
  "sub": "W00001",
  "exp": 1740000000
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `sub` | `str` | Subject，值为用户工号 `employee_id`，是 Token 的唯一身份标识 |
| `exp` | `int` | 过期时间戳（UTC），由 `create_access_token` 自动计算 |

**设计决策 — 不在 Payload 中存储 `role` 和 `name`：**
- `role` 由 `settings.ADMIN_EMPLOYEE_IDS` 实时判定，确保管理员列表变更后立即生效，无需用户重新登录
- `name` 通过 `GET /me` 接口获取，避免 JWT 体积膨胀和数据过期问题
- 此方案与 `security.py` 中现有的 `create_access_token(subject)` 签名完全对齐，**无需修改该函数**

---

## 3. POST /api/v1/auth/login

用户登录接口，验证身份后签发 JWT Token。

### 请求体

`Content-Type: application/json`

```python
class LoginRequest(BaseModel):
    employee_id: str   # 工号或域账号，必填，非空。LDAP 模式下为域账号（比工号多首字母）
    password: str      # 密码，必填，非空
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `employee_id` | `str` | 是 | MVP 模式：员工工号；LDAP 模式：域账号（如 `wW00001`） |
| `password` | `str` | 是 | MVP 模式：统一密码；LDAP 模式：域密码 |

### 成功响应 (200)

```python
class UserInfo(BaseModel):
    employee_id: str
    name: str
    email: str
    role: str                          # "admin" | "user"
    
    model_config = {"from_attributes": True}

class LoginResponse(BaseModel):
    access_token: str                  # JWT Token
    token_type: str = "bearer"         # 固定值 "bearer"
    user: UserInfo                     # 当前登录用户信息
```

响应示例：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "employee_id": "W00001",
    "name": "张三",
    "email": "zhangsan@example.com",
    "role": "admin"
  }
}
```

### 失败响应 (401)

| 场景 | HTTP Status | detail |
|------|-------------|--------|
| MVP：工号不存在 | 401 Unauthorized | `"账号不存在"` |
| MVP：密码错误 | 401 Unauthorized | `"密码错误"` |
| LDAP：校验失败 | 401 Unauthorized | `"账号或密码错误"` |

响应格式（FastAPI `HTTPException` 标准格式）：

```json
{
  "detail": "账号不存在"
}
```

### 处理流程

**LDAP 模式**（`LDAP_HOST` 非空时）：

1. 接收 LoginRequest（employee_id 语义为域账号，password）
2. 使用 ldap3 连接 LDAP 服务器，bind 校验域账号与密码
3. 若校验失败 → 401 "账号或密码错误"
4. 解析 employee_id = 域账号去掉首字母（如 `wW00001` → `W00001`）
5. 优先从 `ums_email` 获取 name/email，查不到则用默认值
6. 调用 create_access_token(subject=employee_id) 生成 JWT
7. 返回 LoginResponse

**MVP 模式**（`LDAP_HOST` 为空时）：

1. 接收 LoginRequest（employee_id, password）
2. SELECT * FROM ums_email WHERE employee_id = :employee_id
3. 若记录不存在 → 401 "账号不存在"
4. 校验 password == settings.MVP_LOGIN_PASSWORD
5. 若不匹配 → 401 "密码错误"
6. 调用 create_access_token(subject=employee_id) 生成 JWT
7. 返回 LoginResponse

---

## 4. GET /api/v1/auth/me

获取当前登录用户的完整信息与角色。前端用于页面加载时确认登录状态、获取用户名和角色以控制菜单展示。

### 请求头

| Header | 值 | 必填 |
|--------|-----|------|
| `Authorization` | `Bearer <access_token>` | 是 |

无请求体、无查询参数。

### 成功响应 (200)

```python
class CurrentUserResponse(BaseModel):
    employee_id: str
    name: str
    email: str
    domain_account: Optional[str] = None
    role: str                          # "admin" | "user"
    
    model_config = {"from_attributes": True}
```

响应示例：

```json
{
  "employee_id": "W00001",
  "name": "张三",
  "email": "zhangsan@example.com",
  "domain_account": "zhangsan",
  "role": "admin"
}
```

### 失败响应 (401)

| 场景 | HTTP Status | detail |
|------|-------------|--------|
| 未携带 Token | 401 Unauthorized | `"Not authenticated"` |
| Token 无效或过期 | 401 Unauthorized | `"Invalid token"` |

### 处理流程

```
1. 通过 Depends(get_current_user) 解析 Bearer token，获取 payload（含 sub，即 employee_id）
2. SELECT * FROM ums_email WHERE employee_id = payload["sub"]
3. 若记录存在 → 使用 ums_email 中的 name、email、domain_account；若不存在 → 返回基础信息（employee_id、name=employee_id、email=""）
4. 判定角色：employee_id in settings.ADMIN_EMPLOYEE_IDS → "admin"，否则 → "user"
5. 返回 CurrentUserResponse
```

---

## 5. POST /api/v1/auth/logout

### 方案说明

本系统采用**无状态 JWT 方案**，服务端不维护 Token 黑名单或 Session 存储。因此：

- 后端 **不做任何状态清理**，直接返回成功
- 实际的"登出"行为由**前端完成**：清除 `localStorage` 中的 `"token"`，跳转到 `/login`
- 此接口存在的意义：保持 RESTful 语义完整，前端调用后执行清理逻辑，后续如需引入 Token 黑名单也有扩展点

### 请求头

| Header | 值 | 必填 |
|--------|-----|------|
| `Authorization` | `Bearer <access_token>` | 是 |

无请求体。

### 成功响应 (200)

```json
{
  "message": "退出成功"
}
```

### 处理流程

```
1. 通过 Depends(get_current_user) 验证 Token 有效性（确保只有已登录用户能调用）
2. 返回 {"message": "退出成功"}
3. 前端收到 200 后：localStorage.removeItem("token") → 跳转 /login
```

---

## 6. 角色与权限判定

### 角色定义

| 角色 | 标识值 | 判定规则 |
|------|--------|---------|
| 管理员 | `"admin"` | `employee_id in settings.ADMIN_EMPLOYEE_IDS` |
| 普通用户 | `"user"` | `employee_id not in settings.ADMIN_EMPLOYEE_IDS` |

### 角色判定函数（伪代码）

```python
def get_user_role(employee_id: str) -> str:
    if employee_id in settings.ADMIN_EMPLOYEE_IDS:
        return "admin"
    return "user"
```

### 权限校验机制

| 层级 | 实现方式 | 已有代码 |
|------|---------|---------|
| **认证（所有接口）** | `Depends(get_current_user)` — 校验 Token 有效性，返回 payload | `dependencies.py` 已实现 |
| **管理员接口** | `Depends(require_admin)` — 在认证基础上额外校验 `sub in ADMIN_EMPLOYEE_IDS`，失败返回 403 | `security.py` 已实现 |
| **前端菜单** | 登录后调用 `GET /me` 获取 `role`，据此动态显隐管理员菜单 | 待实现 |

### config.py 需新增的配置项

```python
MVP_LOGIN_PASSWORD: str = "dt_report_2026"  # MVP 模式统一密码

# LDAP 域登录（LDAP_HOST 留空则使用 MVP 模式）
LDAP_HOST: str = ""
LDAP_PORT: int = 389
LDAP_DOMAIN: str = ""  # 可选，用于拼接 domain_account@LDAP_DOMAIN
```

> `.env` 中预留 LDAP 配置，由运维/开发者自行填写。

---

## 附：接口总览

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `POST` | `/api/v1/auth/login` | 无需 | 用户登录，获取 Token |
| `GET` | `/api/v1/auth/me` | Bearer Token | 获取当前用户信息与角色 |
| `POST` | `/api/v1/auth/logout` | Bearer Token | 用户退出（语义接口） |
