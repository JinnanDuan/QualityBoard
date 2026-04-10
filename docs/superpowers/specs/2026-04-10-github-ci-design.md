# GitHub CI 与分支门禁设计（QualityBoard）

**日期**：2026-04-10  
**状态**：已定稿（实施前以本文为准）  
**约束**：不在本仓库使用 `gh` CLI 配置远端规则；GitHub 上操作由维护者在网页完成。

---

## 1. 目标

- 在合并到默认分支前，自动执行：**前端可构建**、**后端可安装与语法编译**、**pytest 样例通过**、**ruff 仅检查测试目录**。
- 为后续扩展（全量 ruff、更多 pytest、集成测试等）预留目录与依赖，避免第一版因历史代码风格问题阻塞合并。
- 通过 GitHub **分支规则 / Rulesets** 将上述 CI 设为**必填检查**。

---

## 2. `push` 与 `pull_request` 是否都要跑 CI？

| 触发方式 | 作用 |
|---------|------|
| `pull_request` | 在 PR 更新时验证**即将合并的提交**，是门禁的核心。 |
| `push`（仅 `master`） | 在合并写入 `master` 后**再跑一遍**，可发现「合并提交本身 / 与目标分支合并后」的偶发问题；直接推 `master`（若未禁止）也会跑。 |

**推荐（默认采用）**：同时配置 **`pull_request`** 与 **`push: branches: [master]`**。

- 理由：合并常产生新的 merge commit，仅依赖 PR 上最后一次 push 有时与 `master` 上最终 SHA 不一致；多一次 `master` 上的 run 成本通常可接受，主分支更稳。
- **若希望节省 Actions 分钟数**：可只保留 **`pull_request`**，并确保分支规则**禁止绕过 PR 直推 `master`**，接受「以 PR 头指针通过为准」的策略。

**本文档中的 workflow 默认写法**：`pull_request` + `push` → `master`；若团队选择仅 PR，删除或注释 `push` 段即可，无需改其它逻辑。

---

## 3. CI 结构（GitHub Actions）

- **文件**：`.github/workflows/ci.yml`（单文件）。
- **并行 Job**（推荐，与前期讨论一致）：
  1. **`frontend-build`**：`pnpm install --frozen-lockfile`、`pnpm build`（工作目录 `frontend/`）。
  2. **`backend`**：Python **3.8**；`pip install -r backend/requirements.txt -r backend/requirements-dev.txt`；`python -m compileall backend -q`；`ruff check backend/tests`；`pytest`（见第 4 节）。
- **Runner**：`ubuntu-latest`。
- **缓存**：可选 `actions/cache` 加速 pnpm/npm 与 pip（实施阶段按需添加，非必须）。

---

## 4. 测试与静态检查

### 4.1 依赖

- **`backend/requirements-dev.txt`**（新建）：`pytest`、`pytest-asyncio`、`ruff` 等（版本在实施时锁定）。
- 生产依赖仍仅 **`backend/requirements.txt`**；CI 中同时安装两份。

### 4.2 配置

- 仓库根 **`pytest.ini`**（或等价）：`pythonpath = .`、`asyncio_mode = auto`、`testpaths = backend/tests`（路径以实施为准，与现有 `python -m backend.run` 从项目根启动一致）。

### 4.3 ruff 范围

- 第一版：**仅** `ruff check backend/tests`，保证新测试代码风格一致；全仓库 `backend` 的 ruff 留待后续迭代开启。

### 4.4 样例用例（无 MySQL）

- 使用 **`httpx.AsyncClient` + `ASGITransport`** 对 `backend.main:app` 发请求（如 **`GET /openapi.json` → 200**）。
- 对 **`backend/core/config.py`** 中与布尔/列表相关的解析做 **1～2 条** 单元测试（`monkeypatch` / 环境变量），不连接数据库。
- **说明**：数据库 schema 检查在 **`backend/run.py`**，不在 `main` 的 lifespan 中；因此 ASGI 级 smoke 测试在 CI 中可不起数据库。

---

## 5. GitHub 网页端门禁配置（无 `gh`）

以下在首次 **workflow 已出现在默认分支且至少成功跑过一次** 之后操作（否则「必填检查」下拉框里没有对应 check）。

### 5.1 确认 Check 名称

1. 打开仓库 **Actions**，进入最近一次 **CI** workflow 运行。
2. 记录两个 Job 在 PR「检查」里显示的**完整名称**（常见形式类似：`CI / frontend-build`、`CI / backend`，以实际为准）。

### 5.2 使用 Branch rulesets（推荐，新界面）

1. **Settings** → **Rules** → **Rulesets** → **New ruleset** → **New branch ruleset**。
2. **Ruleset name**：例如 `protect-master`。
3. **Enforcement status**：**Active**。
4. **Target branches**：**Add target** → **Include default branch** 或 **Branch name pattern** `master`（与仓库默认分支一致）。
5. 勾选建议规则：
   - **Require a pull request before merging**（可按需要求审批人数）。
   - **Require status checks to pass** → **Add checks**，勾选上一节记录的两个 Job。
   - （建议）**Block force pushes**。
   - （按需）**Require branches to be up to date before merging**。

### 5.3 经典 Branch protection（备选）

**Settings** → **Branches** → **Add branch protection rule** → Branch name pattern：`master`  
勾选：**Require a pull request before merging**、**Require status checks to pass** 并选择相同 checks；按需勾选 **Include administrators** 等。

### 5.4 私有仓库说明

若部分选项不可用，以 GitHub 当前套餐与文档为准；核心目标仍是：**合并前必须通过上述两个 CI Job**。

---

## 6. 实施范围（代码侧，供后续实现计划引用）

| 项 | 说明 |
|----|------|
| 新建 | `.github/workflows/ci.yml` |
| 新建 | `backend/requirements-dev.txt` |
| 新建 | `pytest.ini`（根目录） |
| 新建 | `backend/pyproject.toml` 或 `ruff.toml`（最小 ruff 配置，可选与 pytest 同文件拆分） |
| 新建 | `backend/tests/` 下若干 `test_*.py` 样例 |
| 不修改 | 既有 8 张表相关红线；不执行 `ALTER`/`DROP` 等 |

---

## 7. 自检摘要

- 与项目约定一致：Python 3.8、pnpm 前端构建、单端口架构不因本设计改变。
- `push` 策略在文档中**可选**，默认双触发；可按分钟数改为仅 `pull_request`。
- 远端规则**仅文档描述**，由维护者在网页完成；不使用 `gh` 自动化。

---

## 8. 下一步

实施阶段：按本文档添加文件并本地/CI 验证通过后，由维护者将改动合并至 `master`，再按 **§5** 在 GitHub 上勾选必填检查。
