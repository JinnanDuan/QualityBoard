# Prompt
我现在想要将前端、后端、数据库全部打通验证一遍；大致思路想要这么做：
1、先生成一份样例数据，导入到pipeline_history
2、实现好后端的查询逻辑，并提供接口，对接数据库要使用model 和  schema方式
3、将查询出来的数据以表格形式展示在“详细执行历史页面”

# LLM ANSWERS：
```markdown
1. 样例数据 — 创建了 database/seed_pipeline_history.sql，INSERT 20 条记录（2 个轮次 × 3 个组别，混合 passed/failed），已成功导入数据库。
2. 后端实现 — 3 个新文件：
backend/schemas/history.py — HistoryItem（ORM → Pydantic 转换）+ HistoryQuery（分页 + 可选筛选）
backend/services/history_service.py — 异步分页查询，支持按 start_time、case_result、platform 筛选
backend/api/v1/history.py — GET /api/v1/history 端点，注入 DB session，返回 PageResponse[HistoryItem]
3. 前端实现 — 2 个文件：
frontend/src/services/index.ts — 添加 historyApi.list() 方法及 TypeScript 类型定义
frontend/src/pages/history/HistoryPage.tsx — Ant Design Table 展示数据，支持分页，用例结果以 Tag 颜色区分（绿色 passed / 红色 failed）
4. 验证结果：
项目	状态
API 总数	20 条 ✓
分页 (page=2, size=10)	返回 10 条 ✓
筛选 case_result=failed	返回 5 条 ✓
筛选 platform=iOS	返回 6 条 ✓
前端页面 /history	200 OK ✓
你现在可以在浏览器中访问 http://localhost:8000/history 查看完整的表格数据。
```