# dt-report 部署指南（Ubuntu 20.04）

本文档描述如何在 **Ubuntu 20.04.6 LTS** 上从零部署 dt-report 项目。

---

## 1. 环境要求

| 组件       | 版本要求                    |
| ---------- | --------------------------- |
| 操作系统   | Ubuntu 20.04.6 LTS (Focal) |
| Python     | 3.8+（系统自带）            |
| Node.js    | 18 LTS                     |
| pnpm       | 10+                        |
| MySQL      | 5.7.x                      |
| Nginx      | 1.18+（系统仓库）          |

---

## 2. 系统基础依赖安装

```bash
sudo apt update && sudo apt upgrade -y

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

## 3. MySQL 5.7 安装与数据库初始化

### 3.1 安装 MySQL 5.7

Ubuntu 20.04 默认仓库中为 MySQL 8.0，安装 5.7 需要手动添加 MySQL APT 源：

```bash
# 下载 MySQL APT 源配置包
wget https://dev.mysql.com/get/mysql-apt-config_0.8.29-1_all.deb

# 安装配置包（弹出界面时选择 MySQL 5.7，然后选 Ok）
sudo dpkg -i mysql-apt-config_0.8.29-1_all.deb
```

在弹出的配置界面中：
1. 选择 `MySQL Server & Cluster`，按回车
2. 选择 `mysql-5.7`，按回车
3. 选择 `Ok`，按回车确认

```bash
# 导入 MySQL GPG 密钥（如遇 GPG 错误）
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys B7B3B788A8D3785C

# 更新包索引并安装
sudo apt update
sudo apt install -y mysql-server=5.7* mysql-client=5.7*

# 启动并设置开机自启
sudo systemctl start mysql
sudo systemctl enable mysql

# 验证版本
mysql --version   # 应输出 Ver 5.7.x
```

### 3.2 安全初始化

```bash
sudo mysql_secure_installation
```

按提示操作：
- 设置 root 密码（记录此密码，后续配置需要）
- 移除匿名用户：Yes
- 禁止 root 远程登录：Yes（推荐）
- 删除 test 数据库：Yes
- 重新加载权限表：Yes

### 3.3 创建数据库用户

```bash
sudo mysql -u root -p
```

在 MySQL 命令行中执行：

```sql
-- 创建项目专用数据库用户（请替换 your_password 为实际密码）
CREATE USER 'dt_report'@'localhost' IDENTIFIED BY 'your_password';

-- 授权
GRANT ALL PRIVILEGES ON dt_infra.* TO 'dt_report'@'localhost';
FLUSH PRIVILEGES;

EXIT;
```

### 3.4 执行数据库迁移脚本

按版本号升序依次执行 `database/` 目录下的全部 SQL 迁移脚本：

```bash
cd /opt/dt-report   # 项目根目录（见第 4 步）

mysql -u dt_report -p < database/V1.0.0__init_dt_infra_database.sql
mysql -u dt_report -p dt_infra < database/V1.0.1__create_pipeline_history.sql
mysql -u dt_report -p dt_infra < database/V1.0.2__create_pipeline_overview.sql
mysql -u dt_report -p dt_infra < database/V1.0.3__create_pipeline_failure_reason.sql
mysql -u dt_report -p dt_infra < database/V1.0.4__create_pipeline_cases.sql
mysql -u dt_report -p dt_infra < database/V1.0.5__create_ums_email.sql
mysql -u dt_report -p dt_infra < database/V1.0.6__create_ums_module_owner.sql
mysql -u dt_report -p dt_infra < database/V1.0.7__create_case_failed_type.sql
mysql -u dt_report -p dt_infra < database/V1.0.8__create_case_offline_type.sql
mysql -u dt_report -p dt_infra < database/V1.0.9__create_sys_audit_log.sql
mysql -u dt_report -p dt_infra < database/V1.1.0__create_report_snapshot.sql
```

> **注意**：V1.0.0 为建库脚本，无需指定数据库名；V1.0.1 ~ V1.1.0 均需指定 `dt_infra`。V1.0.6 依赖 V1.0.5 的 `ums_email` 表外键，务必按顺序执行。

验证：

```bash
mysql -u dt_report -p -e "USE dt_infra; SHOW TABLES;"
```

应看到 10 张表：`case_failed_type`、`case_offline_type`、`pipeline_cases`、`pipeline_failure_reason`、`pipeline_history`、`pipeline_overview`、`report_snapshot`、`sys_audit_log`、`ums_email`、`ums_module_owner`。

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

```bash
cp .env.example .env
```

编辑 `.env` 文件，填写实际的生产配置：

```bash
# 数据库连接（替换用户名、密码、地址）
DATABASE_URL=mysql+aiomysql://dt_report:your_password@127.0.0.1:3306/dt_infra

# JWT 密钥（务必替换为高强度随机字符串）
# 可通过以下命令生成：python3 -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=<替换为随机字符串>

# JWT token 过期时间（分钟），默认 8 小时
ACCESS_TOKEN_EXPIRE_MINUTES=480

# 管理员工号列表
ADMIN_EMPLOYEE_IDS=["W00001","W00002"]

# CORS 允许源（生产环境请限定具体域名）
CORS_ORIGINS=["http://your-domain.com"]

# WeLink 通知配置（按需填写）
WELINK_API_URL=
WELINK_APP_ID=
WELINK_APP_SECRET=
```

### 4.4 启动后端

```bash
cd /opt/dt-report
source .venv/bin/activate

uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

如需后台运行：

```bash
nohup /opt/dt-report/.venv/bin/uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  > /opt/dt-report/backend.log 2>&1 &
```

停止后端：

```bash
# 查找进程
ps aux | grep uvicorn

# 终止进程
kill <PID>
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

构建产物位于 `frontend/dist/` 目录，后续由 Nginx 托管。

---

## 6. Nginx 配置

### 6.1 安装 Nginx

```bash
sudo apt install -y nginx
sudo systemctl start nginx
sudo systemctl enable nginx
```

### 6.2 创建站点配置

```bash
sudo vim /etc/nginx/sites-available/dt-report
```

写入以下内容（请将 `your-domain.com` 替换为实际域名或服务器 IP）：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态资源
    root /opt/dt-report/frontend/dist;
    index index.html;

    # 静态资源缓存
    location /assets/ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # Swagger 文档代理（可选，开发/调试时使用）
    location /docs {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    # SPA history fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 日志
    access_log /var/log/nginx/dt-report-access.log;
    error_log  /var/log/nginx/dt-report-error.log;
}
```

### 6.3 启用站点并重载 Nginx

```bash
# 创建软链接启用站点
sudo ln -s /etc/nginx/sites-available/dt-report /etc/nginx/sites-enabled/

# 如不需要默认站点，可移除
sudo rm -f /etc/nginx/sites-enabled/default

# 测试配置语法
sudo nginx -t

# 重载配置
sudo systemctl reload nginx
```

---

## 7. 验证清单

部署完成后，按以下清单逐项验证：

| 序号 | 验证项                   | 方法                                                   | 预期结果                                     |
| ---- | ------------------------ | ------------------------------------------------------ | -------------------------------------------- |
| 1    | MySQL 服务运行           | `sudo systemctl status mysql`                          | active (running)                             |
| 2    | 数据库表创建完毕         | `mysql -u dt_report -p -e "USE dt_infra; SHOW TABLES;"` | 显示 10 张表                                 |
| 3    | 后端进程运行             | `curl http://localhost:8000/docs`                      | 返回 Swagger UI HTML                         |
| 4    | 后端 API 路由注册        | `curl -s http://localhost:8000/openapi.json \| python3 -m json.tool \| grep path` | 列出全部 `/api/v1/...` 路由                  |
| 5    | Nginx 服务运行           | `sudo systemctl status nginx`                          | active (running)                             |
| 6    | 前端页面可访问           | 浏览器访问 `http://your-domain.com/`                   | 显示左侧导航菜单 + "首页大盘"占位内容       |
| 7    | SPA 路由正常             | 浏览器访问 `http://your-domain.com/overview`           | 显示"分组执行历史"页面，无 404              |
| 8    | API 代理正常             | 浏览器访问 `http://your-domain.com/api/v1/dashboard/trend` | 返回 `{"message": "TODO"}`                   |
| 9    | Swagger 文档可访问       | 浏览器访问 `http://your-domain.com/docs`               | 显示 Swagger UI，含 9 个路由分组             |

---

## 8. 常见问题

### Q1: pip install 报错 `No matching distribution found`

原因：Ubuntu 20.04 自带 Python 3.8，部分较新版本的依赖包可能不支持。当前 `requirements.txt` 中的版本已兼容 Python 3.8，请确保使用项目自带的版本锁定。

### Q2: MySQL 5.7 APT 源安装失败

如果 MySQL 官方 APT 源不可用，可改用 `.tar.gz` 二进制包方式安装。也可使用已有的 MySQL 5.7 实例，跳过安装步骤，直接从 3.3 步开始。

### Q3: 前端 `pnpm build` 报 TypeScript 错误

确认 Node.js 版本为 18.x（`node --version`），且 pnpm 版本为 10.x（`pnpm --version`）。如仍有问题，尝试删除 `node_modules` 后重新安装：

```bash
cd /opt/dt-report/frontend
rm -rf node_modules
pnpm install
pnpm build
```

### Q4: Nginx 返回 502 Bad Gateway

检查后端是否正在运行：

```bash
ps aux | grep uvicorn
curl http://localhost:8000/docs
```

如后端未运行，参照第 4.4 步重新启动。

### Q5: 后端启动时连接数据库失败

确认 `.env` 中 `DATABASE_URL` 的用户名、密码、地址、端口、库名是否正确：

```bash
# 手动测试数据库连接
mysql -u dt_report -p -h 127.0.0.1 -P 3306 dt_infra -e "SELECT 1;"
```

---

## 9. 目录结构参考

部署完成后，`/opt/dt-report` 目录结构如下：

```
/opt/dt-report/
├── .env                    # 环境变量（从 .env.example 复制并修改）
├── .venv/                  # Python 虚拟环境
├── backend/                # 后端源码
│   ├── main.py             # FastAPI 入口
│   ├── requirements.txt    # Python 依赖
│   ├── core/               # 配置、数据库、安全
│   ├── models/             # ORM 模型
│   ├── schemas/            # Pydantic schema
│   ├── api/                # API 路由
│   ├── services/           # 业务逻辑
│   └── utils/              # 工具函数
├── frontend/
│   ├── dist/               # 构建产物（Nginx 托管此目录）
│   ├── src/                # 前端源码
│   └── package.json
├── database/               # SQL 迁移脚本
│   ├── V1.0.0 ~ V1.0.8    # 已有表（8 张）
│   ├── V1.0.9              # 新增 sys_audit_log 表
│   └── V1.1.0              # 新增 report_snapshot 表
└── docs/                   # 项目文档
```
