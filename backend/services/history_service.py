# ============================================================
# History Service — 执行明细的业务逻辑层
# ============================================================
# 在分层架构中，Service 层负责"业务逻辑"：
#   API 层(接收请求) → Service 层(处理逻辑) → Model 层(操作数据库)
# Service 层不关心 HTTP 请求/响应的细节，只关心"查什么数据、怎么查"。
# 这样做的好处是：同一个 Service 函数可以被多个 API 端点复用。
# ============================================================

from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select, tuple_
# AsyncSession: 异步数据库会话，通过它来执行 SQL 查询
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.pipeline_failure_reason import PipelineFailureReason
from backend.models.pipeline_history import PipelineHistory
from backend.schemas.history import HistoryFilterOptions, HistoryQuery

ph = PipelineHistory
pfr = PipelineFailureReason

ALLOWED_SORT_FIELDS = {
    "start_time", "subtask", "case_name", "main_module", "case_result",
    "case_level", "analyzed", "platform", "code_branch", "created_at",
}


async def list_history(
    db: AsyncSession, query: HistoryQuery
) -> Tuple[List[Tuple[PipelineHistory, Optional[str], Optional[str]]], int]:
    """
    分步查询，禁止 JOIN：
    1. 仅查 pipeline_history 主表，按分页和基础筛选获取当前页数据
    2. 根据结果中的 (case_name, start_time, platform) 再查 pipeline_failure_reason
    3. 在服务层拼装 failure_owner、failed_type
    """
    # ===== 第一步：若有 failure_owner / failed_type 筛选，先查 pfr 获取匹配的 (case_name, failed_batch, platform) =====
    pfr_keys_list: Optional[List[Tuple[Optional[str], Optional[str], Optional[str]]]] = None
    if query.failure_owner or query.failed_type:
        pfr_stmt = select(pfr.case_name, pfr.failed_batch, pfr.platform).distinct()
        if query.failure_owner:
            pfr_stmt = pfr_stmt.where(pfr.owner.in_(query.failure_owner))
        if query.failed_type:
            pfr_stmt = pfr_stmt.where(pfr.failed_type.in_(query.failed_type))
        pfr_result = await db.execute(pfr_stmt)
        pfr_keys_list = list({tuple(r) for r in pfr_result.all()})
        if not pfr_keys_list:
            return [], 0

    # ===== 第二步：仅查 pipeline_history 主表（无 JOIN）=====
    stmt = select(ph)
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
    if pfr_keys_list is not None:
        stmt = stmt.where(
            tuple_(ph.case_name, ph.start_time, ph.platform).in_(pfr_keys_list)
        )

    # ===== 第三步：总记录数 =====
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # ===== 第四步：排序 + 分页 =====
    sort_col = getattr(ph, query.sort_field, None) if query.sort_field else None
    if sort_col and query.sort_field in ALLOWED_SORT_FIELDS and query.sort_order:
        if query.sort_order.lower() == "asc":
            stmt = stmt.order_by(sort_col.asc())
        else:
            stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(ph.created_at.desc())
    stmt = stmt.offset((query.page - 1) * query.page_size).limit(query.page_size)

    # ===== 第五步：执行主表查询 =====
    result = await db.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        return [], total

    # ===== 第六步：根据当前页结果批量查 pipeline_failure_reason，拼装 failure_owner、failed_type =====
    keys = list({(r.case_name, r.start_time, r.platform) for r in rows})
    pfr_lookup: Dict[Tuple[Optional[str], Optional[str], Optional[str]], Tuple[Optional[str], Optional[str]]] = {
        k: (None, None) for k in keys
    }

    pfr_stmt = select(pfr.case_name, pfr.failed_batch, pfr.platform, pfr.owner, pfr.failed_type).where(
        tuple_(pfr.case_name, pfr.failed_batch, pfr.platform).in_(keys)
    )
    pfr_result = await db.execute(pfr_stmt)
    for r in pfr_result.all():
        k = (r[0], r[1], r[2])
        if k in pfr_lookup and pfr_lookup[k] == (None, None):
            pfr_lookup[k] = (r[3], r[4])

    items = [
        (row, pfr_lookup[(row.case_name, row.start_time, row.platform)][0],
         pfr_lookup[(row.case_name, row.start_time, row.platform)][1])
        for row in rows
    ]
    return items, total


# 获取筛选选项 — 与 list_history 完全解耦，独立执行单表去重查询。
# 即使 history 列表查询超时或失败，筛选项接口仍可正常返回。
async def get_history_options(db: AsyncSession) -> HistoryFilterOptions:
    async def _distinct(column, desc=False):
        stmt = (
            select(column)
            .where(column.is_not(None))
            .where(column != "")
            .distinct()
        )
        stmt = stmt.order_by(column.desc() if desc else column)
        result = await db.execute(stmt)
        return [r[0] for r in result.all() if r[0]]

    # start_time 按降序，利用 idx_timentask/idx_start_time_case 索引避免全表扫描
    start_time = await _distinct(ph.start_time, desc=True)
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
