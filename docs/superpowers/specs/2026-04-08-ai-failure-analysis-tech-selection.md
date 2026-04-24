# AI 辅助失败原因分析 — 技术选型

- **文档类型**：技术选型（Tech Selection）
- **关联文档**：
  - `2026-04-08-ai-failure-analysis-architecture.md`（架构设计）
  - `2026-04-14-ai-failure-analysis-implementation-plan.md`（实现计划与分期）
- **状态**：Draft（待评审，2026-04-14 与架构同步修订）
- **作者**：AI 助手 × djn
- **日期**：2026-04-08（初稿）；**修订**：2026-04-14

---

## 0. 文档目的与边界

架构设计文档回答**"系统怎么组织、组件怎么交互"**，本文档回答**"每一处具体用哪个库、哪个模型、哪个协议"**以及**"为什么不用它的竞品"**。

两份文档严格分离：
- **架构文档**里凡是涉及具体技术名的地方，本文档都要给出**选型理由**和**备选**。
- 本文档不重复架构细节；看到"为什么 Agent 要分三阶段"之类问题请回查架构文档。

**2026-04-14 同步说明**：**不向 AIFA 传日志 URL**；Phase B 主证据来源为 **`reports_url`（测试报告 HTML）+ `screenshot_url`（截图目录/索引）**，由 **AIFA 使用 `httpx` 直连拉取**；索引页/HTML 解析使用 **`selectolax` + `httpx`**（见 §6）。dt-report **可选**预填直链数组。**不**引入 Playwright。

---

## 1. 总原则

所有选型决策遵循以下优先级（从高到低）：

1. **与 dt-report 现有栈尽量一致** —— 降低团队认知负担
2. **OpenAI 兼容协议优先** —— 让 LLM 厂商切换零代码改动
3. **官方异步驱动** —— AIFA 全栈 async，不允许同步阻塞
4. **最小依赖原则** —— 能不装的库不装；尤其避免引入重量级运行时
5. **可替换性** —— 所有外部依赖走抽象层（Protocol/Client），换实现只改 env 不改代码

---

## 2. 后端语言与框架

### 2.1 Python 版本
**选择：Python 3.11**

| 候选 | 决策 | 理由 |
|---|---|---|
| Python 3.8 | ✘ | dt-report 当前用 3.8，但 AIFA 是独立进程，不必与 dt-report 版本绑死 |
| **Python 3.11** | ✓ | async 性能大幅改进、PEP 657 错误定位更好、`typing` 支持更完整（`Self`、`TypeGuard`、`Protocol` 默认更稳定） |
| Python 3.12 | ✘ | 过新，第三方库（尤其 motor / openai sdk）兼容窗口更窄 |

**备注**：AIFA 独立进程决策（架构 ADR-01）让我们可以自由选版本。Dockerfile 里锁死 `python:3.11-slim`。

### 2.2 Web 框架
**选择：FastAPI + Uvicorn**

| 候选 | 决策 | 理由 |
|---|---|---|
| **FastAPI** | ✓ | 与 dt-report 完全一致；原生 async；pydantic v2 校验；SSE 支持简洁 |
| Starlette 裸用 | ✘ | 省掉的价值小，失去 pydantic schema 校验 |
| Flask | ✘ | 非 async，不符合原则 3 |
| Quart | ✘ | 非主流，团队不熟 |

### 2.3 pydantic 版本
**选择：pydantic v2**（与 dt-report 一致，避免团队同时维护两个版本）

---

## 3. LLM 接入协议

### 3.1 协议选择
**选择：OpenAI 兼容协议（Chat Completions API + Function Calling）**

| 候选 | 决策 | 理由 |
|---|---|---|
| **OpenAI 兼容协议** | ✓ | GLM / Kimi / MiniMax / DeepSeek 全部原生支持；切换只改 `base_url` + `api_key` + 模型名，代码零改动；function-calling 是行业事实标准 |
| ZhipuAI 官方 SDK | ✘ | 绑定单厂商；未来换模型要重写 agent 层 |
| LangChain | ✘ | 过度抽象、版本不稳定、依赖膨胀严重、对 function-calling 的封装反而制造麻烦 |
| LiteLLM | △ | 思路正确（多厂商代理），但增加一层依赖；我们自己抽 `LLMClient` Protocol 就够了，没必要引入 |
| 自研 HTTP 直写 | ✘ | function-calling 的消息结构、tool_choice、JSON mode 等细节容易写错 |

### 3.2 LLM 客户端库
**选择：`openai` 官方 Python SDK**

```python
from openai import AsyncOpenAI
client = AsyncOpenAI(
    api_key=settings.AIFA_LLM_API_KEY,
    base_url=settings.AIFA_LLM_BASE_URL,  # 指向 ZhipuAI 的兼容端点
)
```

**理由**：
- 官方库维护活跃，function-calling / JSON mode / streaming 支持完整
- `AsyncOpenAI` 是 async
- 大多数国产厂商都保证"调 openai sdk + 自家 base_url 即可跑通"
- 将来想换自写 `httpx` 调用也容易（只有一个文件依赖它）

### 3.3 版本锁定
在 `requirements.txt` 里明确锁死小版本（例如 `openai==1.54.0`），防止 breaking change 悄然引入。

---

## 4. 模型选择

### 4.1 起步策略
**选择：只用一家厂商的现役旗舰 + 视觉模型。**

按用户选择 "一开始只用一家（比如只用 GLM）"，默认配置为 ZhipuAI GLM 系列：

| 用途 | 当前推荐（2026-04） | env key |
|---|---|---|
| 文本推理（Plan / Skill / Synthesize） | GLM 系列文本旗舰模型 | `AIFA_LLM_TEXT_MODEL` |
| 视觉分析（screenshot_skill） | GLM 系列视觉模型 | `AIFA_LLM_VISION_MODEL` |

**具体模型名写在 env 而不是代码里**，便于随厂商迭代切换（GLM-4-Plus → GLM-4.5 → GLM-5 等）。

### 4.2 关键模型能力要求
AIFA 依赖以下模型能力，**任何候选模型都必须同时满足**：

| 能力 | 是否必需 | 说明 |
|---|---|---|
| Function Calling | **必需** | Tool 调用的基础；没有此能力整个 Agent 设计无法运行 |
| JSON Mode / Structured Output | **必需** | Plan 阶段约束输出；Synthesize 阶段约束 report schema |
| 长上下文（≥ 32K tokens） | **必需** | Skill 的日志/diff 摘要合并可能超过 8K |
| 视觉理解（多模态） | **必需**（视觉模型） | 截图理解；若厂商无视觉模型则降级：screenshot_skill 返回 unknown |
| Streaming | **推荐** | SSE 体验更好，但不强求 |

### 4.3 备选厂商（未来替换路径）

| 厂商 | OpenAI 兼容 | 备注 |
|---|---|---|
| ZhipuAI / GLM | ✓ | 初期默认 |
| Moonshot / Kimi | ✓ | 长上下文优势；function-calling 支持完整 |
| MiniMax | ✓ | 多模态表现不错 |
| DeepSeek | ✓ | 推理强、价格低，但视觉覆盖相对滞后 |
| 阿里通义千问 | ✓ | 稳定性好，可作 fallback |
| 字节豆包 | ✓ | 备选 |

**切换成本**：只改以下 env（零代码改动）：
```
AIFA_LLM_API_KEY
AIFA_LLM_BASE_URL
AIFA_LLM_TEXT_MODEL
AIFA_LLM_VISION_MODEL
```

### 4.4 模型能力回归

- 所有 prompt 放 git 管理
- 后续若发现某个模型上 prompt 表现退化，走 A/B 对比：保留上线的 prompt + 候选 prompt，对同一份输入跑两遍，人工打分
- **不做运行时热更新 prompt**（架构 ADR-18）

---

## 5. HTTP 客户端

**选择：`httpx`**

| 候选 | 决策 | 理由 |
|---|---|---|
| **httpx** | ✓ | 与 dt-report 一致（WeLink 集成用的就是它）；原生 async；支持 HTTP/2；连接池管理成熟 |
| aiohttp | ✘ | 非 dt-report 栈；团队要额外学习 |
| requests + anyio 桥接 | ✘ | 同步库强转 async 是反模式 |

**复用策略**：
- AIFA 启动时建立**单例** `httpx.AsyncClient`，供 **`fetch_report_html` / `fetch_screenshot_b64` / `codehub_*`** 等 tool 共享（**无**按**日志** URL 的 HTML 抓取）
- 针对外部调用打 timeout（架构 §8 定义）
- 不复用 dt-report 的 httpx client 实例（跨进程，无意义）

---

## 6. HTML 解析（AIFA：`selectolax`）

**架构约定**：AIFA **不**按**日志** HTML URL 抓取；对 **`reports_url`（测试报告 HTML）** 与 **截图目录索引页（HTML）** 的解析，**AIFA** 使用 **`selectolax`**（与架构 §6.2 `fetch_report_html` / `fetch_screenshot_b64` 行为一致）。

**dt-report** 若**可选**预解析索引页，可选用同一技术栈；**非必选**。

| 候选 | 决策 | 理由 |
|---|---|---|
| **selectolax**（**AIFA 推荐必选**，兼 dt-report 可选） | ✓ | 解析报告 HTML、截图索引页 |
| BeautifulSoup4 | △ | 功能更全但慢 |
| lxml | △ | API 较啰嗦 |
| Playwright/Headless browser | ✘ | 过度；不引入 |

**典型用法**（索引页解析示意）：
```python
from selectolax.parser import HTMLParser
tree = HTMLParser(html)
# 按现网 DOM 抽取图片直链，选择器实现阶段确定
```

---

## 7. 证据拉取策略

**选择：统一 `httpx` 拉取 + `selectolax` 解析**

| 候选 | 决策 | 理由 |
|---|---|---|
| **httpx + selectolax** | ✓ | 统一覆盖报告 HTML 与截图索引页，且与现有代码风格一致 |
| Playwright/Headless browser | ✘ | 运行时重、维护复杂，不符合最小依赖原则 |
| requests + bs4 | ✘ | 同步调用不满足 async 约束 |

**使用约束**：
- 报告抓取统一走 `fetch_report_html(reports_url)`，并做 `max_chars` 截断。
- 截图抓取统一走 `fetch_screenshot_b64(screenshot_url)`，支持 `image/*` 直链或索引页解析。
- 索引页解析出的图片数量、单图大小都必须有硬上限。

---

## 8. 代码仓库客户端

### 8.1 初期实现
**选择：自写 `httpx` 客户端 + `CodeRepoClient` Protocol 抽象**

| 候选 | 决策 | 理由 |
|---|---|---|
| **自写 httpx 客户端** | ✓ | CodeHub 是非主流服务，无现成 SDK；逻辑简单（只用 2 个 API：list_commits、get_diff） |
| `python-gitlab` | ✘ | CodeHub 不兼容 GitLab API schema（用户备注"类似 GitLab 但不是"） |
| `PyGithub` | ✘ | 同上 |
| 本地 `git clone` + `git log/show` | ✘ | 初期评估已否决：clone 慢、磁盘占用大、分支管理复杂 |

### 8.2 抽象层设计
```python
# clients/code_repo/__init__.py
class CodeRepoClient(Protocol):
    async def list_commits(
        self, repo_url: str, branch: str,
        since: str, until: str,
        path_filters: list[str] | None = None,
        limit: int = 30
    ) -> dict: ...

    async def get_commit_diff(
        self, repo_url: str, sha: str, max_lines: int = 500
    ) -> dict: ...

# clients/code_repo/codehub.py
class CodeHubClient(CodeRepoClient):
    # 初期唯一实现
    ...
```

**未来扩展**：新增 `gitlab.py` / `gitea.py` 等实现；通过 env `AIFA_CODE_REPO_PROVIDER` 注入。

**注意**：具体的 CodeHub API 细节（endpoint 路径、认证 header 名、响应 schema）在实现阶段对照其文档确认后补入。本选型只保证"用 httpx + Protocol 抽象"的基础决策不会被推翻。

---

## 9. 配置管理

**选择：`pydantic-settings`（与 dt-report 一致）**

| 候选 | 决策 | 理由 |
|---|---|---|
| **pydantic-settings** | ✓ | dt-report `backend/core/config.py` 已用；团队熟；类型安全 |
| python-dotenv 裸用 | ✘ | 无类型、无校验 |
| dynaconf | ✘ | 功能过剩，引入新学习成本 |

**约定**：所有 env 以 `AIFA_` 为前缀（架构 §12.1），严格与 dt-report 的 env 隔离。

---

## 10. 日志与观测

### 10.1 日志框架
**选择：Python 标准库 `logging` + `dictConfig`（与 dt-report 一致）**

| 候选 | 决策 | 理由 |
|---|---|---|
| **stdlib logging + dictConfig** | ✓ | dt-report 已用（`backend/logging_config.py`）；零额外依赖；双文件滚动 `app.log` + `access.log` 形态可复制 |
| structlog | △ | 功能更强但增加学习成本；我们只要"文件 + 结构化字段"用 stdlib 就够 |
| loguru | ✘ | 非主流，与 dt-report 不一致 |

### 10.2 Trace/指标
**选择：自写 JSONL trace 文件 + `/metrics` JSON 端点**

| 候选 | 决策 | 理由 |
|---|---|---|
| **自写 JSONL trace** | ✓ | 轻；未来接 ELK/ClickHouse 只需改 sink |
| prometheus-client | ✘ | 引入新依赖；当前无 Prometheus 基础设施 |
| OpenTelemetry | ✘ | 过度方案 |

未来接 Prometheus：加一个 `/metrics/prom` adapter，不改主接口（架构 §11.5）。

---

## 11. Session 存储

**选择：内存 LRU（`cachetools.TTLCache` 或自写）+ `SessionStore` Protocol**

| 候选 | 决策 | 理由 |
|---|---|---|
| **内存 TTLCache** | ✓ | 单副本部署够用；无外部依赖 |
| Redis | ✘ | 初期无必要；未来扩副本时替换 Protocol 实现 |
| SQLite / 本地文件 | ✘ | 持久化价值低（session 30 分钟就过期） |

**实现库**：`cachetools`（单文件轻量，社区稳定）。如果想零依赖，也可以 20 行手写一个 LRU+TTL。实现阶段决定即可。

---

## 12. 错误 / 异常处理

**选择：FastAPI exception handler + 结构化错误 schema（沿用 dt-report 风格）**

- Tool 层返回 `{error, detail}` 而非 raise（架构 §6.3）
- FastAPI 顶层异常 handler 转成 SSE `event: error`
- 用 `traceback.format_exc()` 仅落 `aifa_app.log`，不返回给前端

---

## 13. 测试依赖

| 用途 | 选择 | 理由 |
|---|---|---|
| 测试框架 | **pytest + pytest-asyncio** | 与 dt-report 一致 |
| HTTP mock | **pytest-httpx** | httpx 官方配套 |
| Report/Screenshot mock | **pytest-httpx** | 通过 httpx mock 覆盖 HTML 与图片拉取路径 |
| LLM mock | 自写 fake client（实现 `LLMClient` Protocol） | 真实 LLM 调用不可用于单元测试 |
| 覆盖率 | **pytest-cov** | 标配 |

**集成测试**：额外提供 docker-compose.test.yml，拉起 mock 报告/截图源 + mock CodeHub + mock LLM gateway 做端到端。

---

## 14. 前端依赖增量

dt-report 前端已有 React 18 / TypeScript / Ant Design 5 / Axios。本特性**不引入任何新依赖**。

| 需求 | 实现方式 | 说明 |
|---|---|---|
| SSE 客户端 | 浏览器原生 `EventSource` | 零依赖；所有现代浏览器支持 |
| UUID 生成 | 浏览器原生 `crypto.randomUUID()` | 零依赖 |
| Markdown 渲染（如果需要） | **不需要** —— 报告是结构化 schema，不是 markdown | 见架构 §9.4 |
| 代码高亮（如 diff 片段） | Ant Design 已内置 `Typography` + 自定义 CSS | 如果真要做 diff 高亮再引入 `react-syntax-highlighter` |

**原则**：结构化数据 > 自由文本 + markdown 渲染。前端严格按 schema 字段排版。

---

## 15. 完整依赖清单

### 15.1 `ai-failure-analyzer/requirements.txt`

```
# Web 框架
fastapi==0.115.0
uvicorn[standard]==0.32.0
pydantic==2.9.0
pydantic-settings==2.5.0

# HTTP
httpx==0.27.0

# HTML 解析（AIFA：reports_url + 截图索引页；与架构 §6.2 一致）
selectolax==0.3.21

# LLM
openai==1.54.0

# Session
cachetools==5.5.0

# 测试
pytest==8.3.0
pytest-asyncio==0.24.0
pytest-httpx==0.32.0
pytest-cov==5.0.0
```

**版本策略**：
- 所有库**锁死小版本**（`==`），避免 breaking change 悄然引入
- 每季度做一次主动升级并跑完整测试
- 升级 `openai` 时特别关注 function-calling / JSON mode 的 API 变动

### 15.2 dt-report 侧需要新增的依赖

**无**。dt-report 侧的 `ai_proxy` 使用现有 `httpx`，没有新依赖。

---

## 16. 未选型但已预留抽象的部分

这些部分当前版本**不做决策**，但架构已经留好接口，未来需要时只改 env 或加一个实现文件：

| 点 | 预留抽象 | 未来选项 |
|---|---|---|
| 代码仓库 | `CodeRepoClient` Protocol | CodeHub（初期）/ GitLab / Gitea / 本地 git |
| Session 存储 | `SessionStore` Protocol | 内存（初期）/ Redis / Memcached |
| 成本告警 | `CostAlertSink` Protocol | 无（初期）/ WeLink / 邮件 |
| 指标端点格式 | `/metrics` JSON（初期） | 未来加 `/metrics/prom` adapter |
| LLM 厂商 | OpenAI 兼容协议 | GLM（初期）/ Kimi / MiniMax / DeepSeek / 自建网关 |

---

## 17. 选型影响评估

### 17.1 对 dt-report 的影响
**可控增量**（相对初版「仅两文件」已扩展，见架构 §3.3、§1.4）：
- 后端：新增 **`ai_proxy.py`**、**`ai_context_builder.py`**、**一键入库 API**（文件名以实现为准）；**尽量不修改**现有 service 核心逻辑，可复用 `failure_process_service` 等与「分析处理」一致的写入规则
- 前端：新增独立目录 `ai_analysis/`（含报告、时间线、一键入库按钮），`HistoryPage.tsx` 仍建议仅加一行挂 Tab
- 依赖：**Python 侧仍可无新增**（目录解析若复用 `selectolax`，与 AIFA 对齐时需在 dt-report `requirements.txt` 评估是否已存在；若 dt-report 已含则不加）
- 部署：docker-compose 新增一个 service（AIFA）
- 数据库：**一键入库**写入既有 **`pipeline_failure_reason`** 列时**可无表结构变更**；若新增列必须走项目 SQL 迁移与 ORM 对齐

### 17.2 对运维的影响
- 需要运维额外维护：
  - 一个 Docker 镜像的构建/发布
  - 一套 `AIFA_*` env 的管理（尤其 API key 与 token）
  - 一个内网地址与防火墙规则
  - 报告/截图源的访问连通性确认
  - CodeHub service token 的申请

### 17.3 对成本的影响
- **新增现金成本**：LLM 调用费（按 SLO 目标 ≤ 0.5 元/请求估算，按日请求量乘积预估月开销）
- **硬上限熔断**：`AIFA_MAX_TOKENS_PER_REQUEST` 防单次失控
- **并发上限熔断**：`AIFA_MAX_CONCURRENT_ANALYSES` 防瞬时爆发
- **用户侧速率限制（以架构 §12.4 为准）**：**同一 `history_id` 1 分钟内最多 10 次**发起分析；可选叠加「同一用户」全局限流（如每分钟 / 每小时上限）
- **转发超时**：dt-report → AIFA 的 `httpx` 客户端建议 **SSE 总读超时 180s（3 分钟）**（与架构 §3.3、§9.6 一致）

---

## 18. 选型验收清单

实现阶段对照核对：

- [ ] Python 3.11-slim 镜像
- [ ] FastAPI + Uvicorn + pydantic v2
- [ ] 所有 env 经 `pydantic-settings` 加载，前缀 `AIFA_`
- [ ] httpx 单例 AsyncClient 全局共享
- [ ] **无日志 URL 抓取**；证据主路径为 `reports_url` + `screenshot_url`
- [ ] **AIFA** 对 `reports_url`、截图索引 HTML 使用 **selectolax**（与 `fetch_report_html` 等 tool 一致）
- [ ] `openai` SDK（`AsyncOpenAI`）+ `base_url` 指向 ZhipuAI
- [ ] 文本/视觉模型名完全从 env 读取
- [ ] `CodeRepoClient` Protocol 存在；初期仅实现 `CodeHubClient`
- [ ] `SessionStore` Protocol 存在；初期仅实现内存 LRU
- [ ] `LLMClient` Protocol 存在（隔离 openai sdk，便于 mock 和未来替换）
- [ ] Stdlib logging + dictConfig 双文件配置
- [ ] Trace JSONL 文件 + `/metrics` JSON 端点
- [ ] 所有依赖在 `requirements.txt` 锁死 `==` 小版本
- [ ] 前端零新增依赖（只用原生 EventSource + crypto.randomUUID）
- [ ] `HistoryPage.tsx` 改动 ≤ 1 行
- [ ] dt-report 转发 AIFA 的 httpx 客户端配置 **180s** 级读超时（或与架构一致的可调值）
- [ ] docker-compose 可拉起 dt-report + AIFA 两个 service
- [ ] docker-compose.test.yml 可跑端到端测试（含 mock 报告/截图源 + CodeHub/LLM）
