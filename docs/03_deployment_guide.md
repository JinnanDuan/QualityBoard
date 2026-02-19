# dt-report 部署指南（Ubuntu 20.04）

本文档描述如何在 **Ubuntu 20.04.6 LTS** 上从零部署 dt-report 项目。

---

## 1. 环境要求

| 组件       | 版本要求                              |
| ---------- | ------------------------------------- |
| 操作系统   | Ubuntu 20.04.6 LTS (Focal)           |
| Python     | 3.8+（系统自带）                      |
| Node.js    | 18 LTS                               |
| pnpm       | 10+                                  |
| MySQL      | 5.7.x（对接已有实例，无需本地安装）   |

---

## 2. 系统基础依赖安装

```bash
sudo apt update

sudo apt install -y \
  build-essential \
  python3 python3-venv python3-pip python3-dev \
  libffi-dev libssl-dev \
  curl wget git
```

### 2.1 安装 Node.js 18 与 pnpm

通过 nvm 安装 Node.js 18 LTS：

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash

# 使 nvm 立即生效
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

nvm install 18
nvm use 18
nvm alias default 18

# 验证
node --version   # 应输出 v18.x.x
npm --version    # 应输出 10.x.x
```

安装 pnpm：

```bash
npm install -g pnpm

# 验证
pnpm --version   # 应输出 10.x.x
```

---

## 3. 对接已有 MySQL 数据库

本项目对接已有的 MySQL 5.7 数据库实例（库名 `dt_infra`），**不需要在部署机上安装 MySQL**。

### 3.1 前提条件

确保已有数据库满足以下条件：

| 条件               | 要求                                      |
| ------------------ | ----------------------------------------- |
| MySQL 版本         | 5.7.x                                    |
| 数据库名           | `dt_infra`                                |
| 字符集             | `utf8mb4`，排序规则 `utf8mb4_unicode_ci`  |
| 已有基础表（8 张） | `pipeline_overview`、`pipeline_history`、`pipeline_failure_reason`、`pipeline_cases`、`ums_email`、`ums_module_owner`、`case_failed_type`、`case_offline_type` |
| 网络连通性         | 部署机能访问数据库 IP + 端口              |

### 3.2 验证数据库连通性

在部署机上安装 MySQL 客户端工具（仅用于手动验证，非必须）：

```bash
sudo apt install -y mysql-client
```

测试连接（替换为实际的 IP、端口、用户名）：

```bash
mysql -u <用户名> -p -h <数据库IP> -P <端口> dt_infra -e "SHOW TABLES;"
```

应看到 8 张已有基础表。

### 3.3 执行新增表迁移脚本

本系统需要额外创建 2 张新表（`sys_audit_log`、`report_snapshot`）。在确认连通后执行：

```bash
cd /opt/dt-report   # 项目根目录（见第 4 步）

mysql -u <用户名> -p -h <数据库IP> -P <端口> dt_infra < database/V1.0.9__create_sys_audit_log.sql
mysql -u <用户名> -p -h <数据库IP> -P <端口> dt_infra < database/V1.1.0__create_report_snapshot.sql
```

验证：

```bash
mysql -u <用户名> -p -h <数据库IP> -P <端口> dt_infra -e "SHOW TABLES;"
```

应看到 10 张表（8 张已有 + 2 张新增）。

### 3.4 配置数据库连接

数据库连接信息通过项目根目录的 `.env` 文件配置。部署时只需修改此文件即可对接不同的数据库实例：

```bash
cp .env.example .env
```

编辑 `.env`，修改 `DATABASE_URL` 一行（格式说明见下方注释）：

```bash
# 格式：mysql+aiomysql://<用户名>:<密码>@<IP地址>:<端口>/<库名>
DATABASE_URL=mysql+aiomysql://root:your_password@192.168.1.100:3306/dt_infra
```

> **切换数据库实例**：后续如需对接其他数据库，只需修改 `.env` 中的 `DATABASE_URL` 并重启后端即可，无需改动任何代码。

---

## 4. 后端部署

### 4.1 获取项目代码

```bash
# 建议部署到 /opt 目录
sudo mkdir -p /opt/dt-report
sudo chown $USER:$USER /opt/dt-report

# 方式一：从 Git 仓库克隆
git clone <仓库地址> /opt/dt-report

# 方式二：手动拷贝项目文件到 /opt/dt-report
```

### 4.2 创建 Python 虚拟环境并安装依赖

```bash
cd /opt/dt-report

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r backend/requirements.txt
```

### 4.3 配置环境变量

如果在第 3.4 步中已完成 `.env` 的数据库配置，此处继续补充其余配置项：

```bash
# 如尚未创建，先复制模板
cp .env.example .env
```

编辑 `.env` 文件，完整配置项说明如下：

```bash
# ===== 数据库连接（第 3.4 步已配置） =====
# 格式：mysql+aiomysql://<用户名>:<密码>@<IP地址>:<端口>/<库名>
DATABASE_URL=mysql+aiomysql://root:your_password@192.168.1.100:3306/dt_infra

# ===== JWT 认证 =====
# 密钥（务必替换为高强度随机字符串）
# 生成方式：python3 -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=<替换为随机字符串>

# token 过期时间（分钟），默认 8 小时
ACCESS_TOKEN_EXPIRE_MINUTES=480

# ===== 权限控制 =====
# 管理员工号列表（JSON 数组格式）
ADMIN_EMPLOYEE_IDS=["W00001","W00002"]

# CORS 允许源（生产环境请限定具体域名）
CORS_ORIGINS=["http://your-domain.com"]

# ===== WeLink 通知（按需填写） =====
WELINK_API_URL=
WELINK_APP_ID=
WELINK_APP_SECRET=
```

### 4.4 启动后端

推荐使用项目自带脚本（详见第 6 节）：

```bash
cd /opt/dt-report
./scripts/start.sh
```

也可手动启动（前台模式，适合调试）：

```bash
cd /opt/dt-report
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 4.5 验证后端

```bash
curl http://localhost:8000/docs
```

应返回 Swagger UI 的 HTML 页面，且页面中包含所有 API 路由分组（认证、看板、分组概览、执行明细、失败分析、用例管理、总结报告、通知、管理员后台）。

---

## 5. 前端构建

```bash
cd /opt/dt-report/frontend

# 确保使用 Node.js 18
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm use 18

# 安装依赖
pnpm install

# 构建生产包
pnpm build
```

构建产物位于 `frontend/dist/` 目录，由 FastAPI 直接托管（无需 Nginx）。

---

## 6. 快速启停

项目提供了一组脚本（位于 `scripts/` 目录），封装了所有启停操作。

### 6.1 首次部署 / 代码更新

```bash
cd /opt/dt-report
./scripts/deploy.sh
```

此脚本会依次：安装后端依赖 -> 构建前端 -> 启动后端。

### 6.2 日常启停

```bash
# 启动
./scripts/start.sh

# 停止
./scripts/stop.sh

# 重启
./scripts/restart.sh

# 查看状态
./scripts/status.sh
```

### 6.3 说明

- 后端通过 uvicorn 运行在 **端口 8000**，同时提供 API 和前端页面
- PID 文件为项目根目录的 `.pid`，日志文件为 `app.log`
- 查看实时日志：`tail -f /opt/dt-report/app.log`

---

## 7. 验证清单

部署完成后，按以下清单逐项验证：

| 序号 | 验证项                   | 方法                                                   | 预期结果                                     |
| ---- | ------------------------ | ------------------------------------------------------ | -------------------------------------------- |
| 1    | 数据库连通性             | `mysql -u <用户名> -p -h <IP> -P <端口> dt_infra -e "SELECT 1;"` | 返回结果无报错                               |
| 2    | 数据库表齐全             | `mysql -u <用户名> -p -h <IP> -P <端口> dt_infra -e "SHOW TABLES;"` | 显示 10 张表                                 |
| 3    | 后端进程运行             | `./scripts/status.sh`                                  | 后端进程运行中，端口 8000 已监听             |
| 4    | Swagger 文档可访问       | 浏览器访问 `http://<服务器IP>:8000/docs`               | 显示 Swagger UI，含 9 个路由分组             |
| 5    | API 路由正常             | 浏览器访问 `http://<服务器IP>:8000/api/v1/dashboard/trend` | 返回 `{"message": "TODO"}`                   |
| 6    | 前端页面可访问           | 浏览器访问 `http://<服务器IP>:8000/`                   | 显示左侧导航菜单 + "首页大盘"占位内容       |
| 7    | SPA 路由正常             | 浏览器访问 `http://<服务器IP>:8000/overview`           | 显示"分组执行历史"页面，无 404               |

---

## 8. 常见问题

### Q1: pip install 报错 `No matching distribution found`

原因：Ubuntu 20.04 自带 Python 3.8，部分较新版本的依赖包可能不支持。当前 `requirements.txt` 中的版本已兼容 Python 3.8，请确保使用项目自带的版本锁定。

### Q2: 无法连接远程 MySQL 数据库

检查以下几项：
- 部署机到数据库服务器的网络是否连通：`telnet <IP> <端口>`
- 数据库用户是否允许远程连接（MySQL `user` 表的 `host` 字段是否包含部署机 IP 或 `%`）
- 防火墙/安全组是否放行了数据库端口

### Q3: 前端 `pnpm build` 报 TypeScript 错误

确认 Node.js 版本为 18.x（`node --version`），且 pnpm 版本为 10.x（`pnpm --version`）。如仍有问题，尝试删除 `node_modules` 后重新安装：

```bash
cd /opt/dt-report/frontend
rm -rf node_modules
pnpm install
pnpm build
```

### Q4: 后端启动时连接数据库失败

确认 `.env` 中 `DATABASE_URL` 的用户名、密码、地址、端口、库名是否正确：

```bash
# 手动测试数据库连接（替换为实际信息）
mysql -u <用户名> -p -h <数据库IP> -P <端口> dt_infra -e "SELECT 1;"
```

如连接正常但后端仍报错，检查 `DATABASE_URL` 中密码是否含有特殊字符（如 `@`、`#`），需要进行 URL 编码。

---

## 9. 目录结构参考

部署完成后，`/opt/dt-report` 目录结构如下：

```
/opt/dt-report/
├── .env                    # 环境变量（从 .env.example 复制并修改）
├── .venv/                  # Python 虚拟环境
├── scripts/                # 启停脚本
│   ├── deploy.sh           # 首次部署 / 代码更新
│   ├── start.sh            # 启动后端
│   ├── stop.sh             # 停止后端
│   ├── restart.sh          # 重启后端
│   └── status.sh           # 查看运行状态
├── backend/                # 后端源码（同时托管前端静态文件）
│   ├── main.py             # FastAPI 入口
│   ├── requirements.txt    # Python 依赖
│   ├── core/               # 配置、数据库、安全
│   ├── models/             # ORM 模型
│   ├── schemas/            # Pydantic schema
│   ├── api/                # API 路由
│   ├── services/           # 业务逻辑
│   └── utils/              # 工具函数
├── frontend/
│   ├── dist/               # 构建产物（由 FastAPI 直接托管）
│   ├── src/                # 前端源码
│   └── package.json
├── database/               # SQL 迁移脚本
│   ├── V1.0.0 ~ V1.0.8    # 已有表（8 张）
│   ├── V1.0.9              # 新增 sys_audit_log 表
│   └── V1.1.0              # 新增 report_snapshot 表
└── docs/                   # 项目文档
```
