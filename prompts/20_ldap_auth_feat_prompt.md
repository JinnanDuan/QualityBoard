# 20 - LDAP 域登录认证功能需求描述

## 背景与现状

### 当前登录鉴权实现

- **用户来源**：`ums_email` 表。仅当 `employee_id` 在表中存在时才允许登录。
- **密码校验**：密码与 `.env` 中的 `MVP_LOGIN_PASSWORD` 明文比对，所有用户共用同一密码。
- **核心逻辑位置**：`backend/services/auth_service.py` 的 `authenticate_user()` 函数。
- **配置**：`backend/core/config.py` 中的 `Settings.MVP_LOGIN_PASSWORD`。

### 用户表 `ums_email` 结构（不可修改）

| 字段 | 类型 | 说明 |
|------|------|------|
| employee_id | varchar(20) | 工号，主键 |
| name | varchar(50) | 姓名 |
| email | varchar(100) | 邮箱 |
| domain_account | varchar(255) | 域账号（可为空） |
| created_at / updated_at | datetime | 时间戳 |

> 注意：该表无密码字段，且禁止 ALTER 表结构。

---

## 需求目标

将当前「工号 + 统一密码」的 MVP 认证方式，替换为 **LDAP 域账号认证**。

### 核心要求

1. **LDAP 认证**：用户使用域账号 + 域密码登录，由 LDAP 服务器校验密码。**只要 LDAP 校验通过即可登录，不做用户白名单限制**（不依赖 `ums_email` 表做准入校验）。
2. **配置预留**：在 `.env` 和 `backend/core/config.py` 中预留 LDAP 相关配置项，由运维/开发者自行填写，代码中不硬编码任何 LDAP 连接信息。
3. **兼容与降级**：可考虑保留 MVP 模式作为降级开关（如 LDAP 未配置或连接失败时的 fallback），具体策略由实现时决定。

---

## LDAP 配置项（预留，供自行填写）

参考原 DT 看板实现，仅需两个配置项。使用 `ldap3` 库时，连接方式示例：

```python
from ldap3 import Server, SCHEMA
s = Server(LDAP_HOST, LDAP_PORT, use_ssl=False, get_info=SCHEMA)
```

| 配置项 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| LDAP_HOST | str | LDAP 服务器地址（主机名或 IP） | ldap.example.com |
| LDAP_PORT | int | LDAP 端口（389 明文 / 636 LDAPS） | 389 |

> 实现时需支持配置为空时跳过 LDAP、回退 MVP。

---

## 登录流程变更（目标）

### 当前流程（MVP）

1. 接收 `employee_id` + `password`
2. 查询 `ums_email` 表，不存在 → 401「账号不存在」
3. 校验 `password == MVP_LOGIN_PASSWORD`，不匹配 → 401「密码错误」
4. 签发 JWT，返回用户信息

### 目标流程（LDAP 启用时）

1. 接收 **域账号**（`domain_account`）+ `password`
2. 使用 `LDAP_HOST`、`LDAP_PORT` 连接 LDAP 服务器，校验域账号与密码。
3. LDAP 校验失败 → 401「账号或密码错误」（不区分具体原因，避免信息泄露）。
4. LDAP 校验成功 → 签发 JWT，返回用户信息（与现有 `LoginResponse` 一致）。用户信息可从 LDAP 响应中解析，或按需从 `ums_email` 补充（仅用于展示，不做准入校验）。

### 登录输入约定

- **登录时必须输入域账号**（`domain_account`），即比工号多一个首字母的格式（例如工号 `W00001` 对应域账号 `wW00001`）。
- 前端/接口字段名可沿用 `employee_id` 或改为 `username`，但语义上表示的是域账号。

---

## 技术约束（必须遵守）

1. **项目规则**：遵循 `.cursor/rules/project.mdc`，禁止 ALTER `ums_email` 等已有表。
2. **技术栈**：Python 3.8、FastAPI、SQLAlchemy async、Pydantic v2；类型标注使用 `Optional[X]`。
3. **依赖**：新增 Python 依赖写入 `backend/requirements.txt` 并锁定版本；使用 `ldap3` 库（与原 DT 看板一致）。
4. **日志**：按 `docs/06_logging_guide.md`，登录成功/失败打日志，禁止在日志中输出密码。
5. **文档**：代码变更后同步更新 `spec/01_feat_login-auth_spec.md` 及相关文档。

---

## 交付物期望

1. **配置层**：`.env.example` 或 `.env` 中新增 LDAP 配置项及注释；`backend/core/config.py` 中 `Settings` 增加对应字段。
2. **认证层**：`backend/services/auth_service.py` 中实现 LDAP 校验逻辑，替换或包装现有密码校验；支持 LDAP 未配置时回退 MVP。
3. **可选**：独立的 `backend/core/ldap_client.py` 或 `backend/services/ldap_service.py` 封装 LDAP 连接与 bind 逻辑，便于测试与维护。
4. **规约更新**：`spec/01_feat_login-auth_spec.md` 更新认证策略说明，明确 LDAP 与 MVP 的切换规则。
