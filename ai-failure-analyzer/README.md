# ai-failure-analyzer（AIFA）Phase A1

独立服务：失败用例 AI 辅助归因（当前已支持 **Plan / Act / Synthesize 三阶段主循环**，并具备 B1 报告/截图工具调用能力）。

规格说明：
- [docs/superpowers/specs/aifa-phase-a1-service-spec.md](../docs/superpowers/specs/aifa-phase-a1-service-spec.md)
- [docs/superpowers/specs/aifa-phase-b1-report-screenshot-tools-spec.md](../docs/superpowers/specs/aifa-phase-b1-report-screenshot-tools-spec.md)
- [docs/superpowers/specs/aifa-phase-b2-agent-three-stage-spec.md](../docs/superpowers/specs/aifa-phase-b2-agent-three-stage-spec.md)

## 环境要求

- **Python 3.8+**（与 `pyproject.toml` 中 `requires-python` 一致；便于与 dt-report 容器同为 3.8 或本地 3.10/3.11）。
- 技术选型文档仍推荐独立服务使用 **3.11**；若环境与镜像暂为 **3.8**，代码层面已兼容，行为与接口不变。

## 安装

```bash
cd ai-failure-analyzer
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade 'setuptools>=68' pip wheel
pip install -e ".[dev]"
```

若本机 `pip install -e` 报 PEP 660 相关错误，可改用**非 editable**：

```bash
pip install -r requirements-dev.txt
PYTHONPATH=. pytest -q
```

或仅生产依赖：

```bash
pip install -r requirements.txt
pip install .
```

## 环境变量

复制 `.env.example` 为 `.env` 并按需填写。键名说明见 `.env.example`。

- **必须（生产）**：`AIFA_INTERNAL_TOKEN`
- **真实 LLM**：`AIFA_LLM_BASE_URL`、`AIFA_LLM_API_KEY`、`AIFA_LLM_MODEL`（Mock 模式下可不填）
- **CI / 无密钥**：`AIFA_LLM_MOCK=1`
- **CodeHub（B5）**：`AIFA_CODEHUB_BASE_URL`、`AIFA_CODEHUB_TOKEN`（未配置时自动降级跳过 code_blame）

## 启动

```bash
cd ai-failure-analyzer
source .venv/bin/activate
export AIFA_INTERNAL_TOKEN="dev-only-change-me"
export AIFA_LLM_MOCK=1
uvicorn ai_failure_analyzer.main:app --host 0.0.0.0 --port 8080
```

## 健康检查

```bash
curl -sS http://127.0.0.1:8080/healthz | jq .
```

## 分析（SSE）

请求体校验失败时返回 **422**（FastAPI 默认，字段为 `detail`）。请求体过大返回 **400**。

```bash
curl -sS -N \
  -H "Authorization: Bearer dev-only-change-me" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"550e8400-e29b-41d4-a716-446655440000","mode":"initial","case_context":{"case_name":"demo_case","batch":"b1","platform":"Android"}}' \
  http://127.0.0.1:8080/v1/analyze
```

无 `Authorization` 或 token 错误时返回 **401**（JSON，非 SSE）。

## LLM 说明

使用 OpenAI 兼容 `AsyncOpenAI`，默认请求 `response_format={"type":"json_object"}`。若你的兼容网关不支持该参数，可能报错；此时可仅用 Mock 跑通 CI，或联系管理员调整网关。

## 测试

```bash
cd ai-failure-analyzer
pip install -e ".[dev]"
pytest -q
```

## Docker（可选）

镜像与 **dt-report 根目录 Dockerfile** 对齐：`FROM ubuntu:20.04`、`COPY docker/sources.list`，`apt` 安装 **`python3` / `python3-pip` / `python3-venv`**（focal 上为 **Python 3.8.x**），`python3 -m venv /opt/venv`，**不**使用 deadsnakes / Launchpad PPA。应用代码兼容 **3.8+**（见 `pyproject.toml`）。

**构建必须在仓库根目录执行**（否则无法 `COPY docker/sources.list`）：

```bash
cd /path/to/QualityBoard   # 仓库根目录
docker build -f ai-failure-analyzer/Dockerfile -t aifa:a1 .
docker run --rm -e AIFA_INTERNAL_TOKEN=test -e AIFA_LLM_MOCK=1 -p 8080:8080 aifa:a1
```

内网 PyPI 与 dt-report 相同方式传入即可，例如：

`--build-arg PIP_INDEX_URL=... --build-arg PIP_TRUSTED_HOST=...`

若需 **Python 3.10/3.11** 独立镜像，可自行使用 `FROM python:3.11-slim` 等单独维护一条构建线；本仓库默认与 dt-report 同一 Ubuntu + apt Python 路径。
