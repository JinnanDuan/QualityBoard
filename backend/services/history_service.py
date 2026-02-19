# ============================================================
# History Service — 执行明细的业务逻辑层
# ============================================================
# 在分层架构中，Service 层负责"业务逻辑"：
#   API 层(接收请求) → Service 层(处理逻辑) → Model 层(操作数据库)
# Service 层不关心 HTTP 请求/响应的细节，只关心"查什么数据、怎么查"。
# 这样做的好处是：同一个 Service 函数可以被多个 API 端点复用。
# ============================================================

# List: Python 列表类型；Tuple: 元组类型（用于返回 (items, total) 两个值）
from typing import List, Tuple

# func: SQLAlchemy 的 SQL 函数工具，如 func.count() 生成 COUNT(*) SQL
# select: SQLAlchemy 的查询构建器，相当于 SQL 的 SELECT 语句
from sqlalchemy import func, select
# AsyncSession: 异步数据库会话，通过它来执行 SQL 查询
from sqlalchemy.ext.asyncio import AsyncSession

# 导入 ORM 模型 — 代表 pipeline_history 表
from backend.models.pipeline_history import PipelineHistory
# 导入请求 Schema — 包含分页参数和筛选条件
from backend.schemas.history import HistoryQuery


# 这是一个异步函数（async def），因为数据库操作是异步的（不阻塞其他请求）
# 参数:
#   db:    数据库会话（由 API 层通过依赖注入传入）
#   query: 查询参数（包含 page, page_size, start_time, case_result, platform）
# 返回值: 元组 (items, total)
#   items: 当前页的 PipelineHistory 对象列表
#   total: 符合筛选条件的总记录数
async def list_history(db: AsyncSession, query: HistoryQuery) -> Tuple[List[PipelineHistory], int]:
    # ===== 第一步：构建基础查询 =====
    # select(PipelineHistory) 相当于 SQL: SELECT * FROM pipeline_history
    stmt = select(PipelineHistory)

    # ===== 第二步：动态添加筛选条件（WHERE 子句）=====
    # 只有前端传了这些参数时才加 WHERE 条件，没传就不过滤（查全部）
    # 这叫"动态查询"或"条件查询"

    # 如果前端传了 start_time 参数，添加 WHERE start_time = '...'
    if query.start_time:
        stmt = stmt.where(PipelineHistory.start_time == query.start_time)
    # 如果前端传了 case_result 参数（如 "failed"），添加 WHERE case_result = 'failed'
    if query.case_result:
        stmt = stmt.where(PipelineHistory.case_result == query.case_result)
    # 如果前端传了 platform 参数（如 "iOS"），添加 WHERE platform = 'iOS'
    if query.platform:
        stmt = stmt.where(PipelineHistory.platform == query.platform)

    # ===== 第三步：查询总记录数 =====
    # 为什么要单独查总数？因为分页只返回当前页的数据，但前端需要知道"一共有多少条"来计算页数
    # stmt.subquery() 把当前带筛选条件的查询变成子查询
    # select(func.count()).select_from(...) 相当于: SELECT COUNT(*) FROM (子查询)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    # await db.execute(...) 异步执行 SQL，.scalar() 取结果的第一个值（即 COUNT 的数字）
    # "or 0" 是防御性编程：如果结果为 None，则默认返回 0
    total = (await db.execute(count_stmt)).scalar() or 0

    # ===== 第四步：排序 + 分页 =====
    # ORDER BY created_at DESC — 按创建时间倒序（最新的排在前面）
    stmt = stmt.order_by(PipelineHistory.created_at.desc())
    # offset + limit 实现分页:
    #   offset = (page - 1) * page_size — 跳过前面的记录
    #   limit = page_size — 只取 page_size 条记录
    # 例如: page=2, page_size=10 → offset=10, limit=10 → 取第 11~20 条
    stmt = stmt.offset((query.page - 1) * query.page_size).limit(query.page_size)

    # ===== 第五步：执行查询并提取结果 =====
    # await db.execute(stmt) 异步执行最终的 SELECT SQL
    result = await db.execute(stmt)
    # result.scalars() 把原始行结果转为 ORM 对象（PipelineHistory 实例）
    # .all() 获取所有结果行，list(...) 转成普通 Python 列表
    items = list(result.scalars().all())

    # 返回 (数据列表, 总数) 给 API 层
    return items, total
