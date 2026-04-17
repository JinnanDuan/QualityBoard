"""分析入口（SSE）。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing_extensions import Annotated
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from ai_failure_analyzer.api.v1.schemas.request import AnalyzeRequest
from ai_failure_analyzer.core.config import Settings, get_settings
from ai_failure_analyzer.core.security import verify_bearer
from ai_failure_analyzer.services.analyze_service import stream_analyze

router = APIRouter(tags=["分析"])

MAX_BODY_BYTES = 512 * 1024


@router.post("/analyze")
async def analyze(
    request: Request,
    _authorized: Annotated[None, Depends(verify_bearer)],
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请求体超过允许大小",
        )
    try:
        payload = AnalyzeRequest.model_validate_json(body)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors(),
        ) from e

    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

    async def event_stream():
        async for chunk in stream_analyze(payload, request_id, settings):
            yield chunk

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Request-ID": request_id,
    }
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream; charset=utf-8",
        headers=headers,
    )
