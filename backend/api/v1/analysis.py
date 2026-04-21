# ============================================================
# API — AI 失败分析（A4 接受/拒绝写库）
# ============================================================

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import require_apply_failure_reason_permission
from backend.schemas.analysis import (
    ApplyFailureReasonRequest,
    ApplyFailureReasonResponse,
    RejectFailureReasonRequest,
    RejectFailureReasonResponse,
)
from backend.services.analysis_service import apply_ai_failure_reason, reject_ai_failure_reason

router = APIRouter(prefix="/ai", tags=["AI失败分析"])


@router.post("/apply-failure-reason", response_model=ApplyFailureReasonResponse)
async def post_apply_failure_reason(
    req: ApplyFailureReasonRequest,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(require_apply_failure_reason_permission),
):
    """用户确认后将 AI 结论写入 pipeline_failure_reason，并同步 pipeline_history.analyzed。"""
    analyzer_employee_id = str(payload.get("sub", "")).strip()
    return await apply_ai_failure_reason(db, req, analyzer_employee_id)


@router.post("/reject-failure-reason", response_model=RejectFailureReasonResponse)
async def post_reject_failure_reason(
    req: RejectFailureReasonRequest,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(require_apply_failure_reason_permission),
):
    """拒绝 AI 草稿：不写业务表，仅记录审计。"""
    operator_employee_id = str(payload.get("sub", "")).strip()
    return await reject_ai_failure_reason(db, req, operator_employee_id)
