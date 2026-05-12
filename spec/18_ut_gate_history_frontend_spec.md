# 「UT门禁历史」前端实现规约

本文档对应 **`spec/15_ut_gate_jenkins_report_spec.md` §12.2 阶段 4（前端）** 的实现级说明，与 **§8.3** 菜单/路由/页面形态、**§6.2**（全员可见）、**`spec/17_ut_gate_runs_get_api_spec.md`**（列表 GET）对齐。**不包含** Jenkins 脚本、后端 POST、**`stats`** 图表。

---

## 1. 文档范围与关联

| 关联 | 说明 |
|------|------|
| 上位需求 | **`spec/15_ut_gate_jenkins_report_spec.md`** §8.1～§8.3、§9、§11 前端勾选项 |
| 列表 API | **`GET /api/v1/ut-gate-runs`**，见 **`spec/17_ut_gate_runs_get_api_spec.md`** |
| 项目前端契约 | `.cursor/rules/project.mdc`：`frontend/src/services/`、`frontend/src/pages/`、`request.ts`、`pnpm build` |

**非目标（本期）**：ECharts、首页 UT 卡片、`GET /api/v1/ut-gate-runs/stats`、在浏览器中持有 **`UT_GATE_INTEGRATION_TOKEN`**（仅 Jenkins 使用 POST）。

---

## 2. 路由与导航

### 2.1 路由

| 项 | 规约 |
|----|------|
| **浏览器路径** | **`/ut-gate-history`**（与 **`/history`** 同级顶层路径，见 §15 §8.3） |
| **注册位置** | `frontend/src/routes/index.tsx`：在 **`RequireAuth`** 包裹的 `MainLayout` 子路由中新增一条 **`{ path: "ut-gate-history", element: <UtGateHistoryPage /> }`** |
| **鉴权** | **仅** `RequireAuth`（与「详细执行历史」一致）；**不得**使用 `RequireAdmin`（全员可见） |

### 2.2 侧栏菜单

| 项 | 规约 |
|----|------|
| **文案** | **「UT门禁历史」** |
| **位置** | 与 **「详细执行历史」**（`/history`）**同级**：紧挨在 **`/history`** 项之后（或之前，二选一固定即可） |
| **`key`** | **`/ut-gate-history`**（与路由 path 一致，便于 `navigate`） |
| **图标** | 选用 Ant Design Icons 中与「门禁/检查」语义接近且与 `HistoryOutlined` 可区分的图标（如 **`SafetyCertificateOutlined`** 或 **`AuditOutlined`**，实现时选定一种） |
| **全员可见** | **`getMenuItemsByRole`**（`MainLayout.tsx`）中：**`user` 与 `admin` 均须包含本菜单项**；**不得**随「用例管理 / 管理员后台」等非管理员隐藏逻辑一并过滤掉 |

---

## 3. 页面与组件

### 3.1 文件与导出

| 项 | 规约 |
|----|------|
| **页面文件** | `frontend/src/pages/ut-gate-history/UtGateHistoryPage.tsx`（目录名 **kebab-case** 与路由语义一致） |
| **组件形式** | **默认导出**函数组件：`export default function UtGateHistoryPage()` |
| **数据加载** | `useState` + `useEffect` + 异步函数调用 `utGateApi.list`（与项目其它列表页习惯一致） |

### 3.2 页面结构（本期）

- **仅** Ant Design **`<Table>`** + **筛选区** + **分页**；**不**引入 ECharts、**不**做首页嵌入。
- **表格 `rowKey`**：**`"id"`**（与项目规则一致）。
- **分页**：对接后端 **`PageResponse`**：`pagination.current`、`pagination.pageSize`、`pagination.total`，与 **`spec/17`** 的 `page` / `page_size` / `total` 一致；翻页时重新请求列表。

### 3.3 建议列（与 §15 §5 / §8.1 对齐）

以下列名均为 **中文表头**；数据字段 **snake_case** 与后端一致。

| 列（建议顺序） | 字段 | 说明 |
|----------------|------|------|
| ID | `id` | 大整数；若担心 JS 精度，**可**格式化为 **字符串** 展示（见 §6.2） |
| 上报时间 | `reported_at` | 可格式化为本地可读时间字符串 |
| 创建时间 | `created_at` | 可选列 |
| Job | `job_name` | — |
| 构建号 | `build_number` | — |
| 是否拦截 | `is_intercepted` | **`Tag`** 等：`true` → 建议文案 **「已拦截」**（或「是」）；`false` → **「未拦截」**（或「否」），并在列说明或 Tooltip 中注明 **false 为混合语义**（见 §15 §1.2 / §8.4，简短即可） |
| MR 链接 | `mr_url` | 可空；非空时 **`Link`/`Typography.Link`** `target="_blank"` `rel="noopener noreferrer"` |
| 构建链接 | `build_url` | 可空；非空时同上外链 Jenkins |
| 退出码 | `ut_exit_code` | 可空，展示 `-` 或 `—` |
| 幂等键 | `idempotency_key` | 可选列；过长可 `ellipsis` + `Tooltip` |

**不要求**本期展示：`jenkins_base_url`、`updated_at`（除非产品希望对齐 DBA 排障，可列为可选隐藏列二期再做）。

---

## 4. 筛选与查询参数

筛选条件映射 **`spec/17` §4** Query 参数；请求时 **snake_case** 与后端一致。

| UI 建议 | 对应 Query 参数 | 说明 |
|---------|------------------|------|
| **上报时间**范围（`RangePicker` 或两个日期选择） | `start_time`、`end_time` | 绑定 **`reported_at`**；推荐传 **`YYYY-MM-DD`**（与 §17 日期模式一致）；**须在页面旁用中文提示**：「时间筛选对应上报时间 `reported_at`，与详细执行历史的批次时间不同」 |
| **是否拦截**下拉（全部 / 是 / 否） | `is_intercepted` | 选「全部」则**不传**该参数 |
| **MR 精确**输入框 | `mr_url` | 与 **MR 子串**互斥（见下） |
| **MR 子串**输入框 | `mr_url_contains` | 与 **MR 精确**互斥；若两者均有非空值，**提交前校验**并 **`message.warning`** 或表单错误提示，**不**发请求 |
| **Job 子串**输入框 | `job_name_contains` | 可选 |
| **排序**（可选简化） | `sort_field`、`sort_order` | 默认 **`reported_at` + `desc`**；可提供简单下拉或固定不写死由后端默认 |

**查询按钮**：点击后 `setState` 页码为 **1** 再请求，避免筛选后仍停留在超大页码无数据。

**重置按钮**：清空筛选、`page=1`、重新拉取。

---

## 5. Service 层（`utGateApi`）

### 5.1 文件位置

- **推荐**：新建 **`frontend/src/services/utGate.ts`**，导出 **`utGateApi`** 对象；在 **`frontend/src/services/index.ts`** 增加 **`export { utGateApi } from "./utGate"`**（或等价聚合导出），便于其它模块按需引用。
- **禁止**：在页面内手写完整 `axios` URL 字符串散落多处；**须**通过 **`request`**（`./request.ts`）实例调用。

### 5.2 `request` 与鉴权

- 使用 **`import request from "./request"`**（或与 `historyApi` 相同的 project's request 路径）。
- **JWT**：依赖现有 **`request` 拦截器**从 `localStorage` 注入 **`Authorization: Bearer`**；**禁止**把 **`UT_GATE_INTEGRATION_TOKEN`** 写入前端代码或 `localStorage`。

### 5.3 TypeScript 类型（与后端一致 **snake_case**）

在 **`utGate.ts`**（或紧邻的 `types` 片段）中定义，字段与 **`UtGateRunItem`** / **`UtGateRunQuery`** 对齐，例如：

- **`UtGateRunItem`**：`id`, `created_at`, `updated_at`, `reported_at`, `jenkins_base_url`, `job_name`, `build_number`, `build_url`, `mr_url`, `idempotency_key`, `is_intercepted`, `ut_exit_code`（日期时间字段类型为 **`string | null`** 等与 `HistoryItem` 风格一致即可）。
- **`UtGateRunListParams`**（可选命名）：`page`, `page_size`, `start_time`, `end_time`, `is_intercepted`, `mr_url`, `mr_url_contains`, `job_name_contains`, `sort_field`, `sort_order`；全部为 **可选**除分页默认值由页面传入。

### 5.4 API 方法

```ts
utGateApi.list(params?: UtGateRunListParams): Promise<PageResponse<UtGateRunItem>>
```

- **HTTP**：`request.get("/ut-gate-runs", { params })`。
- **Query 序列化**：与 `historyApi` 类似，**仅附加非 `undefined` / 非空字符串** 的键；`boolean` 的 `is_intercepted` 需能序列化为后端可解析形式（与 FastAPI 行为一致，一般为 `true`/`false` 字符串）。

---

## 6. 大整数 `id` 与日期

- **`id`**：`BIGINT` 可能超过 **`Number.MAX_SAFE_INTEGER`**。表格展示推荐 **`String(row.id)`** 或使用 **`BigInt`** 再转字符串；**避免**对大 `id` 做依赖精度的数值运算。
- **日期时间**：后端返回 ISO 字符串；展示层可用 **`dayjs`**（若项目已用）或 **`toLocaleString`** 格式化，**不**强制与时区策略改动后端。

---

## 7. 错误与空态

- **401**：由 **`request` 响应拦截器**统一跳转登录（现有行为），页面无需重复实现跳转逻辑。
- **列表为空**：`<Empty description="暂无数据" />` 或表格 `locale.emptyText`。
- **非 401 错误**：`message.error` 展示简短中文（可从 `error.response?.data?.detail` 读取数组或字符串）。

---

## 8. 构建与部署

- 修改前端后须执行 **`pnpm build`**（或通过 **`scripts/deploy.sh`**），并**重启**后端以托管新静态资源（见项目规则 §五）。
- **不**新增 `npm`/`yarn` 依赖除非产品必须；若新增须 **`pnpm add`** 并说明用途。

---

## 9. 文档与 Epic 表

- 功能对用户可用后，同步 **`docs/05_technical_architecture.md`** 中 Epic 表「UT 门禁」一行：前端路由 **`/ut-gate-history`** 与页面组件名（与 §15 §11「更新 docs」一致）。

---

## 10. 实现检查清单

- [x] `frontend/src/services/utGate.ts`：`utGateApi` + **`UtGateRunItem`** / 列表请求参数类型  
- [x] `frontend/src/pages/ut-gate-history/UtGateHistoryPage.tsx`：表格 + 筛选 + 分页 + 外链  
- [x] `routes/index.tsx`：注册 **`/ut-gate-history`**，**仅** `RequireAuth`  
- [x] `MainLayout.tsx`：菜单项 **「UT门禁历史」**，**`user`/`admin` 均可见**  
- [ ] 部署环境执行 **`pnpm build`** 并重启后端（见项目规则）  

---

## 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-05-07 | 初稿：对应 §15 §12.2 阶段 4；路由、菜单全员可见、`utGateApi`、表格与筛选、非目标范围 |
| v1.1 | 2026-05-07 | 仓库已按 §10 落地前端实现；构建请在本地执行 `pnpm build` |
