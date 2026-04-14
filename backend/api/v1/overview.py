from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.schemas.common import PageResponse
from backend.schemas.overview import OverviewFilterOptions, OverviewItem, OverviewQuery
from backend.services.overview_service import get_overview_options, list_overview

router = APIRouter(prefix="/overview", tags=["分组执行历史"])


def _nonempty_subtask(subtask: Optional[List[str]]) -> bool:
    if not subtask:
        return False
    for s in subtask:
        if s is not None and str(s).strip():
            return True
    return False


@router.get("/options", response_model=OverviewFilterOptions)
async def get_overview_options_endpoint(db: AsyncSession = Depends(get_db)):
    """分组执行历史筛选项（单表去重）。"""
    return await get_overview_options(db)


@router.get("", response_model=PageResponse[OverviewItem])
async def get_overview_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    batch: Optional[List[str]] = Query(None),
    subtask: Optional[List[str]] = Query(None),
    platform: Optional[List[str]] = Query(None),
    code_branch: Optional[List[str]] = Query(None),
    result: Optional[List[str]] = Query(None),
    sort_field: Optional[str] = Query(None),
    sort_order: Optional[str] = Query(None),
    all_batches: bool = Query(False, description="为 true 时不注入默认最近30批；须配合 subtask"),
    db: AsyncSession = Depends(get_db),
):
    if all_batches and not _nonempty_subtask(subtask):
        raise HTTPException(
            status_code=422,
            detail="全部分组跨轮次查询时必须指定分组（subtask）",
        )
    try:
        query = OverviewQuery(
            page=page,
            page_size=page_size,
            batch=batch,
            subtask=subtask,
            platform=platform,
            code_branch=code_branch,
            result=result,
            sort_field=sort_field,
            sort_order=sort_order,
            all_batches=all_batches,
        )
    except ValidationError as e:
        parts = [str(err.get("msg", "")) for err in e.errors()]
        raise HTTPException(
            status_code=422,
            detail="; ".join(p for p in parts if p) or "参数校验失败",
        ) from e

    rows, total = await list_overview(db, query)
    items = [OverviewItem.model_validate(r) for r in rows]
    return PageResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
