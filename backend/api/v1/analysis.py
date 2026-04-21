# ============================================================
# API — AI 失败分析（A4 接受/拒绝 + A5 分析入口限流）
# ============================================================

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import require_apply_failure_reason_permission
from backend.schemas.analysis import (
    AnalyzeRequest,
    ApplyFailureReasonRequest,
    ApplyFailureReasonResponse,
    RejectFailureReasonRequest,
    RejectFailureReasonResponse,
)
from backend.services.ai_context_builder import AIContextHistoryNotFoundError, build_analyze_payload
from backend.services.ai_rate_limit_service import HistoryAnalyzeRateLimiter, log_rate_limit_hit
from backend.services.analysis_service import apply_ai_failure_reason, reject_ai_failure_reason

router = APIRouter(prefix="/ai", tags=["AI失败分析"])
_analyze_rate_limiter = HistoryAnalyzeRateLimiter(
    window_seconds=settings.AI_ANALYZE_RATE_LIMIT_WINDOW_SECONDS,
    max_requests=settings.AI_ANALYZE_RATE_LIMIT_MAX_REQUESTS,
)


@router.post("/analyze")
async def post_analyze(
    req: AnalyzeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(require_apply_failure_reason_permission),
):
    user_employee_id = str(payload.get("sub", "")).strip()
    allow, current_count = _analyze_rate_limiter.try_acquire(req.history_id)
    if not allow:
        log_rate_limit_hit(
            history_id=req.history_id,
            user_employee_id=user_employee_id,
            session_id=req.session_id,
            mode=req.mode,
            window_seconds=settings.AI_ANALYZE_RATE_LIMIT_WINDOW_SECONDS,
            threshold=settings.AI_ANALYZE_RATE_LIMIT_MAX_REQUESTS,
            current_count=current_count,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "AI_ANALYZE_RATE_LIMITED",
                "message": "同一失败记录在 1 分钟内最多发起 10 次分析，请稍后重试",
                "history_id": req.history_id,
            },
        )

    try:
        payload_built = await build_analyze_payload(db, req.history_id)
    except AIContextHistoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"执行记录不存在: history_id={req.history_id}",
        )

    if req.mode == "follow_up" and not (req.follow_up_message or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="follow_up 模式必须提供 follow_up_message")

    session_id = (req.session_id or "").strip() or str(uuid.uuid4())
    forward_payload = {
        "session_id": session_id,
        "mode": req.mode,
        "follow_up_message": req.follow_up_message,
        **payload_built,
    }
    if not (settings.AIFA_INTERNAL_TOKEN or "").strip():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AIFA_INTERNAL_TOKEN 未配置")
    aifa_url = settings.AIFA_BASE_URL.rstrip("/") + "/v1/analyze"
    request_id = getattr(request.state, "request_id", "") or str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {settings.AIFA_INTERNAL_TOKEN}",
        "X-Request-ID": request_id,
    }
    timeout = httpx.Timeout(settings.AI_ANALYZE_TIMEOUT_SECONDS)
    client = httpx.AsyncClient(timeout=timeout)
    try:
        request_obj = client.build_request("POST", aifa_url, json=forward_payload, headers=headers)
        upstream = await client.send(request_obj, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AIFA 调用失败: {str(exc)}")

    if upstream.status_code != status.HTTP_200_OK:
        try:
            detail_bytes = await upstream.aread()
            msg = detail_bytes.decode("utf-8", errors="ignore")
        except Exception:
            msg = ""
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AIFA 返回异常状态({upstream.status_code}){': ' + msg if msg else ''}",
        )

    async def stream_body():
        try:
            async for chunk in upstream.aiter_bytes():
                if chunk:
                    yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_body(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-ID": request_id,
        },
    )


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
