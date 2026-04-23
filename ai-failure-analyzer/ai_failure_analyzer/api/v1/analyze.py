"""分析入口（SSE）。"""

import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing_extensions import Annotated
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from ai_failure_analyzer.api.v1.schemas.request import AnalyzeRequest
from ai_failure_analyzer.core.config import Settings, get_settings
from ai_failure_analyzer.core.security import verify_bearer
from ai_failure_analyzer.services.analyze_service import stream_analyze
from ai_failure_analyzer.services.observability import (
    append_trace_line,
    build_trace_payload,
    record_analyze_outcome,
)

router = APIRouter(tags=["分析"])

MAX_BODY_BYTES = 512 * 1024


def _parse_sse_chunk(chunk: str) -> tuple:
    event_name = ""
    data_payload = {}
    lines = chunk.splitlines()
    data_raw = ""
    for line in lines:
        if line.startswith("event:"):
            event_name = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_raw = line[len("data:") :].strip()
    if data_raw:
        try:
            parsed = json.loads(data_raw)
            if isinstance(parsed, dict):
                data_payload = parsed
        except Exception:  # noqa: BLE001
            data_payload = {}
    return event_name, data_payload


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
    stream_started_at = time.perf_counter()

    async def event_stream():
        final_status = "error"
        final_trace = {}
        final_data_gaps = []
        error_code = ""
        error_message = ""
        try:
            async for chunk in stream_analyze(payload, request_id, settings):
                event_name, data_payload = _parse_sse_chunk(chunk)
                if event_name == "report":
                    final_status = str(data_payload.get("status", "error"))
                    trace_obj = data_payload.get("trace", {})
                    if isinstance(trace_obj, dict):
                        final_trace = trace_obj
                    report_obj = data_payload.get("report", {})
                    if isinstance(report_obj, dict):
                        gaps = report_obj.get("data_gaps", [])
                        if isinstance(gaps, list):
                            final_data_gaps = [str(x) for x in gaps]
                elif event_name == "error":
                    final_status = "error"
                    error_code = str(data_payload.get("error_code", "")).strip()
                    error_message = str(data_payload.get("message", "")).strip()
                yield chunk
        except Exception as exc:  # noqa: BLE001
            error_message = str(exc)
            raise
        finally:
            elapsed_ms = int((time.perf_counter() - stream_started_at) * 1000)
            llm_input_tokens = int(final_trace.get("llm_input_tokens", 0) or 0)
            llm_output_tokens = int(final_trace.get("llm_output_tokens", 0) or 0)
            estimated_cost = float(final_trace.get("estimated_cost", 0.0) or 0.0)
            token_budget_triggered = bool(final_trace.get("token_budget_triggered", False))
            external_dependency_error = False
            if final_status == "partial":
                joined = " ".join(final_data_gaps)
                external_dependency_error = (
                    "失败" in joined or "超时" in joined or "异常" in joined or "error" in joined.lower()
                )
            record_analyze_outcome(
                status=final_status,
                elapsed_ms=elapsed_ms,
                llm_input_tokens=llm_input_tokens,
                llm_output_tokens=llm_output_tokens,
                estimated_cost=estimated_cost,
                circuit_breaker_triggered=token_budget_triggered,
                external_dependency_error=external_dependency_error,
            )
            trace_line = build_trace_payload(
                request_id=request_id,
                session_id=payload.session_id,
                history_id=payload.case_context.history_id if payload.case_context else 0,
                status=final_status,
                elapsed_ms=elapsed_ms,
                trace_obj=final_trace,
                error_code=error_code,
                error_message=error_message,
                data_gaps=final_data_gaps,
            )
            append_trace_line(settings.aifa_trace_log_path, trace_line)

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
