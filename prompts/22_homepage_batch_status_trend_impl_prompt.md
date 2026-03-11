# 首页最新批次状态 + 趋势折线图 — 实现 Prompt

请严格按照 `spec/09_homepage_batch_status_trend_spec.md` 实现首页 Dashboard 的「最新批次状态卡片」与「趋势折线图」功能。

---

## 一、必读文档

1. **功能规约**：`spec/09_homepage_batch_status_trend_spec.md`（全文精读，所有实现必须符合该 spec）
2. **项目规则**：`.cursor/rules/project.mdc`（技术栈、数据库红线、分层契约）
3. **日志规范**：`docs/06_logging_guide.md`

---

## 二、实现清单

### 1. 后端：Schema 层

修改 `backend/schemas/dashboard.py`，定义响应模型（字段名与 spec 5.2 完全一致，使用 snake_case）：

| 模型 | 说明 |
|------|------|
| `LatestBatchItem` | 最新批次单条响应：batch, total_case_num, passed_num, failed_num, pass_rate, batch_start, batch_end, result |
| `BatchTrendItem` | 趋势数据单条：batch, total_case_num, passed_num, failed_num, pass_rate, batch_start |
| `BatchTrendResponse` | 趋势接口响应：`{ items: List[BatchTrendItem] }` |

- `pass_rate` 为 float（如 95.83）
- `batch_start`、`batch_end` 为 `Optional[str]`（ISO 格式）
- 无数据时 `latest-batch` 返回 `null`，前端需处理

### 2. 后端：Service 层

修改 `backend/services/dashboard_service.py`，实现**纯 async 函数**（非类）：

| 函数 | 签名 | 说明 |
|------|------|------|
| `get_latest_batch` | `async def get_latest_batch(db: AsyncSession) -> Optional[LatestBatchItem]` | 查询最新批次聚合数据，无数据返回 None |
| `get_batch_trend` | `async def get_batch_trend(db: AsyncSession, limit: int = 30) -> List[BatchTrendItem]` | 查询最近 N 个批次聚合数据，按 batch_start 升序 |

**聚合逻辑**：严格按 spec 5.3 的 SQL 伪代码实现。使用 `text()` 执行原生 SQL 或 SQLAlchemy 的 `select()` + `func`。

**关键点**：
- `case_num` 为 varchar，需 `CAST(COALESCE(case_num, '0') AS SIGNED)` 或等价方式
- 最新批次：子查询 `ORDER BY batch_start DESC LIMIT 1` 取 batch，再按 batch 聚合
- 趋势数据：子查询取最近 N 个 batch，再按 batch 聚合，`ORDER BY MIN(batch_start) ASC`
- `pass_rate`：`passed_num / total_case_num * 100`，total_case_num 为 0 时可为 None 或 0
- `result`：`"failed"` 若 `failed_num > 0`，否则 `"passed"`

**SQL 策略**：项目规则默认禁止联表，此处为单表 `pipeline_overview` 聚合，无需 JOIN。使用子查询取 batch 列表后再聚合。

### 3. 后端：API 层

修改 `backend/api/v1/dashboard.py`：

| 端点 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 最新批次 | GET | `/latest-batch` | 调用 `get_latest_batch`，返回 `LatestBatchItem \| null` |
| 批次趋势 | GET | `/batch-trend` | 查询参数 `limit`（可选，默认 30，最大 50），调用 `get_batch_trend` |

- 注入 `db: AsyncSession = Depends(get_db)`
- 需登录：`Depends(get_current_user)`（与 history 等接口一致）
- 设置 `response_model`，ORM/字典转 Schema 时使用 `LatestBatchItem.model_validate()` 或手动构造

**注意**：删除现有的 `/trend`、`/stats` 占位路由，替换为上述两个端点。

### 4. 前端：Service 层

在 `frontend/src/services/index.ts`（或新建 `dashboardApi.ts` 并导出）中新增：

| 接口 | 类型 | 说明 |
|------|------|------|
| `LatestBatchItem` | 与后端 Schema 字段一致（snake_case） | batch, total_case_num, passed_num, failed_num, pass_rate, batch_start, batch_end, result |
| `BatchTrendItem` | 同上 | batch, total_case_num, passed_num, failed_num, pass_rate, batch_start |
| `dashboardApi.latestBatch()` | `Promise<LatestBatchItem \| null>` | `GET /dashboard/latest-batch` |
| `dashboardApi.batchTrend(limit?: number)` | `Promise<{ items: BatchTrendItem[] }>` | `GET /dashboard/batch-trend?limit=30` |

### 5. 前端：Dashboard 页面

修改 `frontend/src/pages/dashboard/DashboardPage.tsx`：

**5.1 最新批次状态卡片**

- 使用 `useState` + `useEffect` 调用 `dashboardApi.latestBatch()`
- 布局：Ant Design `Row` + `Col` 或 `Card`，单行横向排列
- 展示指标：批次、总用例数、通过数（绿色）、失败数（红色）、通过率、执行时间范围、整体状态 Tag（passed=绿色，failed=红色）
- 空数据：显示「暂无批次数据」，数字类显示「—」
- 点击卡片：跳转 `/history?start_time=批次值`（使用 `useNavigate` + `navigate`）

**5.2 趋势折线图**

- 使用 `useState` + `useEffect` 调用 `dashboardApi.batchTrend(30)`
- 使用 `echarts-for-react` 或 `echarts` 渲染折线图
- X 轴：`items` 的 `batch` 字段
- Y 轴：失败用例数（红色 #ff4d4f）、总用例数（蓝色 #1890ff）两条折线
- Tooltip：批次、执行时间（batch_start 格式化）、总用例数、通过数、失败数、通过率
- 图例：可点击切换显示/隐藏
- 点击数据点：跳转 `/history?start_time=批次值`

**5.3 时间格式化**

- `batch_start`、`batch_end` 使用 `dayjs` 格式化为 `YYYY-MM-DD HH:mm`，范围展示为 `开始 ~ 结束`

### 6. 日志

- Service 层：无数据时可不打日志；查询异常时 `logger.exception`
- API 层：按项目规则，不在每个入口打「请求开始」

---

## 三、实现约束

1. **Python 3.8**：类型标注使用 `Optional[X]`，禁止 `X | None`
2. **前端**：TypeScript 接口字段与后端 Schema **完全一致**（snake_case）
3. **数据库**：仅查询 `pipeline_overview`，不修改表结构，不新增迁移
4. **技术栈**：React 18、Ant Design 5、ECharts、echarts-for-react（已安装）
5. **路由**：History 页路径为 `/history`，筛选参数 `start_time` 与现有 History 筛选兼容

---

## 四、实现顺序建议

1. Schema 定义
2. Service 层（含 SQL 聚合逻辑）
3. API 层
4. 前端 Service（dashboardApi）
5. Dashboard 页面（卡片 + 折线图）

---

## 五、验证方式

1. 有数据时：首页展示最新批次卡片 + 趋势折线图
2. 无数据时：展示「暂无批次数据」，图表区域可显示空状态
3. 点击卡片/数据点：跳转到 History 页并带 `start_time` 参数
4. API：`/docs` 中可调试 `GET /api/v1/dashboard/latest-batch`、`GET /api/v1/dashboard/batch-trend`
