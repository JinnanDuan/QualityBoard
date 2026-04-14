from typing import List, Optional, Tuple

from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Integer

from backend.models.pipeline_overview import PipelineOverview
from backend.schemas.overview import OverviewFilterOptions, OverviewQuery

po = PipelineOverview

DEFAULT_OVERVIEW_BATCH_LIMIT = 30

ALLOWED_SORT_FIELDS = {
    "batch",
    "subtask",
    "result",
    "case_num",
    "batch_start",
    "batch_end",
    "passed_num",
    "failed_num",
    "platform",
    "code_branch",
    "created_at",
}


async def list_overview(
    db: AsyncSession, query: OverviewQuery
) -> Tuple[List[PipelineOverview], int]:
    """
    分组执行历史列表：单表 pipeline_overview。
    未选 batch 且非 all_batches 模式时注入最近 30 个不重复 batch（spec/14，与 History 批次数一致）。
    """
    eff = query
    if not query.all_batches and not query.batch:
        default_batches_stmt = (
            select(po.batch)
            .where(po.batch.is_not(None))
            .where(po.batch.like("20%"))
            .distinct()
            .order_by(po.batch.desc())
            .limit(DEFAULT_OVERVIEW_BATCH_LIMIT)
        )
        default_result = await db.execute(default_batches_stmt)
        default_batches = [r[0] for r in default_result.all() if r[0]]
        if default_batches:
            eff = query.model_copy(update={"batch": default_batches})
        else:
            return [], 0

    stmt = select(po)
    if eff.batch:
        stmt = stmt.where(po.batch.in_(eff.batch))
    if eff.subtask:
        stmt = stmt.where(po.subtask.in_(eff.subtask))
    if eff.platform:
        stmt = stmt.where(po.platform.in_(eff.platform))
    if eff.code_branch:
        stmt = stmt.where(po.code_branch.in_(eff.code_branch))
    if eff.result:
        stmt = stmt.where(po.result.in_(eff.result))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    sort_field = eff.sort_field
    sort_order = (eff.sort_order or "").lower()
    if (
        sort_field
        and sort_field in ALLOWED_SORT_FIELDS
        and sort_order in ("asc", "desc")
    ):
        if sort_field == "case_num":
            sort_col = cast(po.case_num, Integer)
        else:
            sort_col = getattr(po, sort_field)
        if sort_order == "asc":
            stmt = stmt.order_by(sort_col.asc())
        else:
            stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(po.batch.desc(), po.subtask.asc())

    stmt = stmt.offset((eff.page - 1) * eff.page_size).limit(eff.page_size)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return rows, total


async def get_overview_options(db: AsyncSession) -> OverviewFilterOptions:
    async def _distinct(column, desc: bool = False, prefix: Optional[str] = None) -> List[str]:
        s = (
            select(column)
            .where(column.is_not(None))
            .where(column != "")
        )
        if prefix is not None:
            s = s.where(column.like(prefix + "%"))
        s = s.distinct().order_by(column.desc() if desc else column.asc())
        r = await db.execute(s)
        return [row[0] for row in r.all() if row[0]]

    batch = await _distinct(po.batch, desc=True, prefix="20")
    subtask = await _distinct(po.subtask)
    platform = await _distinct(po.platform)
    code_branch = await _distinct(po.code_branch)

    return OverviewFilterOptions(
        batch=batch,
        subtask=subtask,
        platform=platform,
        code_branch=code_branch,
        result=["passed", "failed"],
    )
