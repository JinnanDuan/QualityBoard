from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.schemas.dashboard import BatchTrendResponse, LatestBatchItem
from backend.services.dashboard_service import get_batch_trend, get_latest_batch

router = APIRouter(prefix="/dashboard", tags=["看板"])


@router.get("/latest-batch", response_model=Optional[LatestBatchItem])
async def get_latest_batch_endpoint(
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
):
    """获取最新批次聚合数据。"""
    return await get_latest_batch(db)


@router.get("/batch-trend", response_model=BatchTrendResponse)
async def get_batch_trend_endpoint(
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
    limit: int = Query(30, ge=1, le=50),
    code_branch: str = Query(..., description="master 或 bugfix"),
):
    """获取最近 N 个批次的趋势数据，按 code_branch 过滤。"""
    items = await get_batch_trend(db, limit=limit, code_branch=code_branch)
    return BatchTrendResponse(items=items)
