# ============================================================
# History Service — 执行明细的业务逻辑层
# ============================================================
# 在分层架构中，Service 层负责"业务逻辑"：
#   API 层(接收请求) → Service 层(处理逻辑) → Model 层(操作数据库)
# Service 层不关心 HTTP 请求/响应的细节，只关心"查什么数据、怎么查"。
# 这样做的好处是：同一个 Service 函数可以被多个 API 端点复用。
# ============================================================

# List: Python 列表类型；Tuple: 元组类型（用于返回 (items, total) 两个值）
from typing import List, Optional, Tuple

# func: SQLAlchemy 的 SQL 函数工具，如 func.count() 生成 COUNT(*) SQL
# select: SQLAlchemy 的查询构建器，相当于 SQL 的 SELECT 语句
# and_: 用于组合多个条件
from sqlalchemy import and_, func, select
# AsyncSession: 异步数据库会话，通过它来执行 SQL 查询
from sqlalchemy.ext.asyncio import AsyncSession

# 导入 ORM 模型
from backend.models.pipeline_failure_reason import PipelineFailureReason
from backend.models.pipeline_history import PipelineHistory
# 导入请求 Schema — 包含分页参数和筛选条件
from backend.schemas.history import HistoryFilterOptions, HistoryQuery

# 关联条件：ph.case_name = pfr.case_name AND ph.start_time = pfr.failed_batch AND ph.platform = pfr.platform
ph = PipelineHistory
pfr = PipelineFailureReason
JOIN_COND = and_(
    ph.case_name == pfr.case_name,
    ph.start_time == pfr.failed_batch,
    ph.platform == pfr.platform,
)


# 这是一个异步函数（async def），因为数据库操作是异步的（不阻塞其他请求）
# 参数:
#   db:    数据库会话（由 API 层通过依赖注入传入）
#   query: 查询参数（包含 page, page_size 及筛选条件）
# 返回值: 元组 (items, total)
#   items: 当前页的 (PipelineHistory, failure_owner, failed_type) 元组列表
#   total: 符合筛选条件的总记录数
async def list_history(
    db: AsyncSession, query: HistoryQuery
) -> Tuple[List[Tuple[PipelineHistory, Optional[str], Optional[str]]], int]:
    # ===== 第一步：构建基础查询（LEFT JOIN pipeline_failure_reason）=====
    stmt = (
        select(ph, pfr.owner.label("failure_owner"), pfr.failed_type)
        .select_from(ph)
        .outerjoin(pfr, JOIN_COND)
    )

    # ===== 第二步：动态添加筛选条件（WHERE 子句）=====
    if query.start_time:
        stmt = stmt.where(ph.start_time.in_(query.start_time))
    if query.subtask:
        stmt = stmt.where(ph.subtask.in_(query.subtask))
    if query.case_name:
        stmt = stmt.where(ph.case_name.in_(query.case_name))
    if query.main_module:
        stmt = stmt.where(ph.main_module.in_(query.main_module))
    if query.case_result:
        stmt = stmt.where(ph.case_result.in_(query.case_result))
    if query.case_level:
        stmt = stmt.where(ph.case_level.in_(query.case_level))
    if query.analyzed:
        stmt = stmt.where(ph.analyzed.in_(query.analyzed))
    if query.platform:
        stmt = stmt.where(ph.platform.in_(query.platform))
    if query.code_branch:
        stmt = stmt.where(ph.code_branch.in_(query.code_branch))
    if query.failure_owner:
        stmt = stmt.where(pfr.owner.in_(query.failure_owner))
    if query.failed_type:
        stmt = stmt.where(pfr.failed_type.in_(query.failed_type))

    # ===== 第三步：查询总记录数 =====
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # ===== 第四步：排序 + 分页 =====
    ALLOWED_SORT_FIELDS = {
        "start_time", "subtask", "case_name", "main_module", "case_result",
        "case_level", "analyzed", "platform", "code_branch", "created_at",
    }
    sort_col = getattr(ph, query.sort_field, None) if query.sort_field else None
    if sort_col and query.sort_field in ALLOWED_SORT_FIELDS and query.sort_order:
        if query.sort_order.lower() == "asc":
            stmt = stmt.order_by(sort_col.asc())
        else:
            stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(ph.created_at.desc())
    stmt = stmt.offset((query.page - 1) * query.page_size).limit(query.page_size)

    # ===== 第五步：执行查询并提取结果 =====
    result = await db.execute(stmt)
    rows = result.all()
    items = [(row[0], row[1], row[2]) for row in rows]

    return items, total


# 获取筛选选项 — 从 pipeline_history 与 pipeline_failure_reason 各列去重，供前端 Select 使用
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

    start_time = await _distinct(ph.start_time)
    subtask = await _distinct(ph.subtask)
    case_name = await _distinct(ph.case_name)
    main_module = await _distinct(ph.main_module)
    case_level = await _distinct(ph.case_level)
    platform = await _distinct(ph.platform)
    code_branch = await _distinct(ph.code_branch)
    failure_owner = await _distinct(pfr.owner)
    failed_type = await _distinct(pfr.failed_type)

    return HistoryFilterOptions(
        start_time=start_time,
        subtask=subtask,
        case_name=case_name,
        main_module=main_module,
        case_result=["passed", "failed"],
        case_level=case_level,
        platform=platform,
        code_branch=code_branch,
        failure_owner=failure_owner,
        failed_type=failed_type,
    )
