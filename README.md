# dt-report

团队内部测试用例批量执行结果看板与管理系统。

## 技术栈

| 层级   | 技术选型                                                  |
| ------ | --------------------------------------------------------- |
| 前端   | React 18 + TypeScript + Ant Design 5 + ECharts + React Router v6 |
| 后端   | Python 3.11+ / FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2    |
| 数据库 | MySQL 5.7（库名 `dt_infra`）                              |

## 快速启动

### 前端

```bash
cd frontend
pnpm install
pnpm dev
```

前端开发服务器默认运行在 `http://localhost:3000`，API 请求自动代理到后端 `http://localhost:8000`。

### 后端

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r backend/requirements.txt

# 复制环境变量模板并按需修改
cp .env.example .env

# 启动
uvicorn backend.main:app --reload
```

后端默认运行在 `http://localhost:8000`，访问 `/docs` 可查看 Swagger API 文档。

## 数据库迁移

SQL 迁移文件位于 `database/` 目录，按版本号升序手动执行。详见 `database/README.md`。
