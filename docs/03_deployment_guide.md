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

# WeLink 卡片（一键通知等）：复制 config/welink_card.ini.example 为服务器上的私密文件并填写真实值，
# 再设置本变量为绝对路径；勿将含密码的 INI 提交到代码仓
WELINK_CARD_INI_PATH=

# 一键通知 WeLink 卡片中的「详细执行历史」链接：填写用户浏览器可访问的根地址（无尾部 /）
PUBLIC_APP_URL=https://your-report-host.example.com
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

此脚本会依次：安装后端依赖（`pip install -r backend/requirements.txt`，含 **playwright** Python 包）-> 构建前端 -> 启动后端。**不在此脚本中下载 Chromium**，避免无外网/需代理时 deploy 失败；一键通知所需的浏览器见下节 **手动安装**。

**WeLink 一键通知：Playwright Chromium（手动，首次部署做一次即可）**

1. 在能访问外网或已配置 **`HTTPS_PROXY` / `HTTP_PROXY`** 的 shell 中执行：
   ```bash
   cd /opt/dt-report   # 项目根目录
   .venv/bin/python -m playwright install chromium
   ```
2. 若提示缺系统库：执行 `playwright install-deps chromium`（内部会调 `apt-get` 装系统包）。**注意**：很多企业网里 **`install chromium` 需配 HTTPS 代理访问公网 CDN**，而 **`install-deps` 走 apt 内网源**，若仍带着同一代理会导致 apt 失败。建议：**先配代理装好 Chromium 后，在新 shell 里 `unset HTTPS_PROXY HTTP_PROXY ALL_PROXY` 再执行** `sudo .venv/bin/python -m playwright install-deps chromium`（或按终端提示逐条 `apt-get install`）。
3. 完全离线环境：在有外网的同架构机器安装后，将 `~/.cache/ms-playwright` 拷至运行后端的用户目录下相同路径。

未安装 Chromium 时，**一键通知**在调用 WeLink 时会失败；其余功能不受影响。

若通过 **Xshell** 等开启 **X11 转发** 的会话启动后端，一键通知可能弹出需 **Xmanager** 的提示：属 Chromium 误连图形环境。代码已对 Playwright **去掉 DISPLAY**；仍出现时可在 **`start.sh` / systemd** 中确保 `DISPLAY` 未注入，或关闭会话的 X11 转发后重启后端。

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

- 后端通过 `python -m backend.run` 启动（内部使用 uvicorn），运行在 **端口 8000**，同时提供 API 和前端页面
- PID 文件为项目根目录的 `.pid`
- 日志由 Python logging 写入项目根目录：`app.log`（应用层）、`access.log`（访问日志），支持按大小轮转（单文件 10MB，app.log 保留 5 份，access.log 保留 3 份）
- 查看实时日志：`tail -f /opt/dt-report/app.log` 或 `tail -f /opt/dt-report/access.log`

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

### Q5: 启动时提示 DB Schema Check 失败

系统启动时会校验数据库表结构与 `database/` 下 DDL 文件是否一致。若不一致，会输出差异报告并可能拒绝启动。

**处理方式**：按差异报告执行对应迁移脚本，或联系 DBA 同步表结构。例如报告 `[表缺失] sys_audit_log` 时，执行 `mysql ... dt_infra < database/V1.0.9__create_sys_audit_log.sql`。

**临时跳过**：在 `.env` 中设置 `DB_SCHEMA_CHECK_ENABLED=false` 可跳过校验；设置 `DB_SCHEMA_CHECK_FAIL_FAST=false` 可仅告警不退出。

---

## 9. Docker 镜像构建与运行（可选）

仓库根目录提供 `Dockerfile`：基于 **Ubuntu 20.04**，在镜像内通过**离线 Node 包** + **离线 pnpm 可执行文件**构建前端，**Python 3.8**（系统 `python3`）虚拟环境安装后端依赖，启动命令与脚本部署一致（`python -m backend.run`，端口 **8000**）。

**Ubuntu apt 源**：与同事实体部署方式一致，使用仓库内 **`docker/sources.list`**，构建时复制为镜像内的 `/etc/apt/sources.list`。默认内容为 **Ubuntu 20.04（focal）** 在内网镜像上的常见写法（示例主机为 `his-mirrors.huawei.com`）；若你司使用其他镜像地址，**直接修改该文件**即可，无需改 Dockerfile。注意官方发行版名为 **`focal-updates`**（带字母 **s**），不要写成 `focal-update`。

**Node（离线包）**：镜像构建**不在容器内下载 Node**。构建前请**自行**下载官方 **`node-v*-linux-x64.tar.xz`**（如从 [Node 发行页](https://nodejs.org/dist/) 或公司内网镜像），放到项目 **`docker/nodejs-offline.tar.xz`**（仅改文件名即可，内容保持原包；勿提交 Git，已写入 `.gitignore`）。`Dockerfile` 通过 `COPY` 装入并解压到 `/usr/local`。

**pnpm（离线可执行文件）**：**不在容器内使用 corepack / registry 安装 pnpm**。请从 [pnpm Releases](https://github.com/pnpm/pnpm/releases) 下载 **`pnpm-linuxstatic-x64`**（静态链接，适用于 Ubuntu 容器；建议选 **10.x** 与当前 `pnpm-lock.yaml` 大版本一致），保存为项目 **`docker/pnpm-offline`**（无扩展名即可，构建时复制为 `/usr/local/bin/pnpm` 并 `chmod +x`；勿提交 Git）。

**npm 源（默认写入 Dockerfile）**：解压 Node 后执行 **`npm config set registry https://mirrors.tools.huawei.com/npm/`** 与 **`npm config set strict-ssl false`**，便于 **`pnpm install`** 走华为 npm 镜像。若需改用其它地址，可传 **`NPM_REGISTRY`**（见下表），或在本地修改 Dockerfile 中上述两行。

**pip（Python 依赖）**：构建时在容器内执行 **`pip install -r backend/requirements.txt`**。不能访问公网 PyPI 时，请传入 **`PIP_INDEX_URL`**（内网 simple 地址，如 `https://mirrors.tools.huawei.com/pypi/simple`）；需要时加 **`PIP_TRUSTED_HOST`**（主机名）。能直连公网则可不传 `PIP_INDEX_URL`。

**代理与 `NO_PROXY`（重要）**：`Dockerfile` 中**仅在安装 Playwright Chromium** 的那一步写了 `export http_proxy=...`。但使用 **`docker build --build-arg HTTP_PROXY=...`** 时，构建环境里仍可能让 **pip / pnpm 等进程读到代理变量**，从而经代理访问**内网** PyPI/npm，表现为 **pip 步骤极慢或卡住**。若同时使用**内网镜像**与**代理下载 Chromium**，请把内网 PyPI、npm 等域名写入 **`NO_PROXY`**（例如 `mirrors.tools.huawei.com,.tools.huawei.com`），**勿**只写 `localhost,127.0.0.1`。代理地址仅通过 build-arg 传入，**勿**写入 Dockerfile 提交到 Git。

**构建前须已有** `docker/nodejs-offline.tar.xz`、`docker/pnpm-offline`。示例（华为内网源 + 需代理拉 Chromium 时）：

```bash
docker build \
  --build-arg PIP_INDEX_URL=https://mirrors.tools.huawei.com/pypi/simple \
  --build-arg PIP_TRUSTED_HOST=mirrors.tools.huawei.com \
  --build-arg HTTP_PROXY=http://代理主机:端口 \
  --build-arg HTTPS_PROXY=http://代理主机:端口 \
  --build-arg NO_PROXY=localhost,127.0.0.1,mirrors.tools.huawei.com,.tools.huawei.com \
  -t dt-report:local .
```

**其他内网源（可选 build-arg）**：向运维索取地址后，可与内网 apt、`sources.list` 组合使用。

| build-arg | 含义 |
|-----------|------|
| `PIP_INDEX_URL` | 内网 PyPI 的 simple 地址。不传则使用默认 PyPI（需构建环境能访问公网）。 |
| `PIP_TRUSTED_HOST` | 内网 PyPI 主机名（不含 `https://`），对应 pip `--trusted-host`；华为示例：`mirrors.tools.huawei.com`。 |
| `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` | 主要用于 **Playwright 下载 Chromium**；若传入，**须**将内网 PyPI/npm 域名列入 `NO_PROXY`，见上文。 |
| `NPM_REGISTRY` | 可选。`Dockerfile` 已默认配置华为 npm；若传入，仅在对应 `RUN` 中设置 `npm_config_registry` 覆盖，用于拉取前端依赖。 |

若**不需要**代理下载 Chromium，可省略上表中 **`HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY`**，仅保留 `PIP_INDEX_URL`、`PIP_TRUSTED_HOST` 即可。

运行时用环境变量注入 `DATABASE_URL`（须含 `charset=utf8mb4`）、`SECRET_KEY` 等，与 `.env` 约定一致；不要将含密码的 `.env` 复制进镜像上下文（`.dockerignore` 已排除 `.env`）。

```bash
docker run --rm -p 8000:8000 \
  -e DATABASE_URL='mysql+aiomysql://用户:密码@主机:3306/dt_infra?charset=utf8mb4' \
  -e SECRET_KEY='请替换' \
  dt-report:local
```

**说明**：WeLink 一键通知依赖 **Playwright Chromium**。`Dockerfile` 已在构建阶段执行 **`python -m playwright install-deps chromium`** 与 **`python -m playwright install chromium`**，镜像体积会明显增大。下载浏览器通常需访问 **Playwright 官方 CDN（公网）**；无直连时需 **`HTTP_PROXY`/`HTTPS_PROXY`**，且 **`NO_PROXY`** 中除内网镜像域名外，需保留代理能访问的公网主机规则（按你们网络策略配置）。若 pip 在代理开启时卡住，优先检查 **`NO_PROXY` 是否包含内网 PyPI 主机名**。

---

## 10. 目录结构参考

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
