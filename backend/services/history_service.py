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
from backend.schemas.history import HistoryFilterOptions, HistoryQuery


# 这是一个异步函数（async def），因为数据库操作是异步的（不阻塞其他请求）
# 参数:
#   db:    数据库会话（由 API 层通过依赖注入传入）
#   query: 查询参数（包含 page, page_size 及 10 个可选筛选条件）
# 返回值: 元组 (items, total)
#   items: 当前页的 PipelineHistory 对象列表
#   total: 符合筛选条件的总记录数
async def list_history(db: AsyncSession, query: HistoryQuery) -> Tuple[List[PipelineHistory], int]:
    # ===== 第一步：构建基础查询 =====
    stmt = select(PipelineHistory)

    # ===== 第二步：动态添加筛选条件（WHERE 子句）=====
    if query.start_time:
        stmt = stmt.where(PipelineHistory.start_time.in_(query.start_time))
    if query.subtask:
        stmt = stmt.where(PipelineHistory.subtask.in_(query.subtask))
    if query.case_name:
        stmt = stmt.where(PipelineHistory.case_name.in_(query.case_name))
    if query.main_module:
        stmt = stmt.where(PipelineHistory.main_module.in_(query.main_module))
    if query.case_result:
        stmt = stmt.where(PipelineHistory.case_result.in_(query.case_result))
    if query.case_level:
        stmt = stmt.where(PipelineHistory.case_level.in_(query.case_level))
    if query.owner:
        stmt = stmt.where(PipelineHistory.owner.in_(query.owner))
    if query.analyzed:
        stmt = stmt.where(PipelineHistory.analyzed.in_(query.analyzed))
    if query.platform:
        stmt = stmt.where(PipelineHistory.platform.in_(query.platform))
    if query.code_branch:
        stmt = stmt.where(PipelineHistory.code_branch.in_(query.code_branch))

    # ===== 第三步：查询总记录数 =====
    # 为什么要单独查总数？因为分页只返回当前页的数据，但前端需要知道"一共有多少条"来计算页数
    # stmt.subquery() 把当前带筛选条件的查询变成子查询
    # select(func.count()).select_from(...) 相当于: SELECT COUNT(*) FROM (子查询)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    # await db.execute(...) 异步执行 SQL，.scalar() 取结果的第一个值（即 COUNT 的数字）
    # "or 0" 是防御性编程：如果结果为 None，则默认返回 0
    total = (await db.execute(count_stmt)).scalar() or 0

    # ===== 第四步：排序 + 分页 =====
    # 支持按指定列排序，默认 created_at DESC
    ALLOWED_SORT_FIELDS = {
        "start_time", "subtask", "case_name", "main_module", "case_result",
        "case_level", "owner", "analyzed", "platform", "code_branch", "created_at",
    }
    sort_col = getattr(PipelineHistory, query.sort_field, None) if query.sort_field else None
    if sort_col and query.sort_field in ALLOWED_SORT_FIELDS and query.sort_order:
        if query.sort_order.lower() == "asc":
            stmt = stmt.order_by(sort_col.asc())
        else:
            stmt = stmt.order_by(sort_col.desc())
    else:
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


# 获取筛选选项 — 从 pipeline_history 各列去重，供前端 Select 使用
async def get_history_options(db: AsyncSession) -> HistoryFilterOptions:
    async def _distinct(column):
        stmt = (
            select(column)
            .where(column.is_not(None))
            .where(column != "")
            .distinct()
            .order_by(column)
        )
        result = await db.execute(stmt)
        return [r[0] for r in result.all() if r[0]]

    start_time = await _distinct(PipelineHistory.start_time)
    subtask = await _distinct(PipelineHistory.subtask)
    case_name = await _distinct(PipelineHistory.case_name)
    main_module = await _distinct(PipelineHistory.main_module)
    case_level = await _distinct(PipelineHistory.case_level)
    owner = await _distinct(PipelineHistory.owner)
    platform = await _distinct(PipelineHistory.platform)
    code_branch = await _distinct(PipelineHistory.code_branch)

    return HistoryFilterOptions(
        start_time=start_time,
        subtask=subtask,
        case_name=case_name,
        main_module=main_module,
        case_result=["passed", "failed"],
        case_level=case_level,
        owner=owner,
        platform=platform,
        code_branch=code_branch,
    )
