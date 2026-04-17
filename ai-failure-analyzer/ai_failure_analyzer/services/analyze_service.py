"""单轮分析：Mock / 真实 LLM、类别守卫、SSE 片段生成。"""

from __future__ import annotations

import json
import logging
import time
from typing import AsyncIterator, Dict, List, Optional

from openai import APIError, AsyncOpenAI, AuthenticationError

from ai_failure_analyzer.api.v1.schemas.report import AnalyzeReportEnvelope, ReportInner, TracePayload
from ai_failure_analyzer.api.v1.schemas.request import AnalyzeRequest, CaseContext
from ai_failure_analyzer.core.config import Settings
from ai_failure_analyzer.services.sse import format_sse

logger = logging.getLogger(__name__)

MAX_PROMPT_JSON_CHARS = 120_000

SYSTEM_PROMPT = """你是测试失败归因助手。只根据用户给出的 JSON 上下文做推断，不要编造未出现的堆栈或日志。
必须只输出一个 JSON 对象（不要 markdown），字段严格如下：
{
  "failure_category": "bug|spec_change|flaky|env|unknown",
  "summary": "一句话结论（中文）",
  "detailed_reason": "详细失败原因（中文）",
  "confidence": 0.0 到 1.0 的小数,
  "data_gaps": ["可选，列举信息不足点，中文"]
}
failure_category 含义：bug=产品缺陷；spec_change=规格变更；flaky=用例不稳定；env=环境问题；unknown=不确定。
若缺少成功侧截图对比证据，请不要输出 spec_change 或 flaky，应使用 unknown 并在 data_gaps 说明。"""


def has_success_screenshot_evidence(ctx: Optional[CaseContext]) -> bool:
    """成功侧截图对比证据：成功侧直链非空，或成功侧索引 URL 非空字符串。"""
    if ctx is None:
        return False
    urls = ctx.success_screenshot_urls or []
    if len(urls) > 0:
        return True
    idx = (ctx.success_screenshot_index_url or "").strip()
    return bool(idx)


def apply_category_guard(inner: ReportInner, has_evidence: bool) -> None:
    """无成功侧截图证据时禁止 spec_change / flaky。"""
    if has_evidence:
        return
    if inner.failure_category in ("spec_change", "flaky"):
        msg = "缺少成功侧截图对比证据，已将失败归类降级为 unknown"
        inner.failure_category = "unknown"
        if msg not in inner.data_gaps:
            inner.data_gaps = list(inner.data_gaps) + [msg]


def _truncate_payload_for_prompt(payload: AnalyzeRequest) -> str:
    raw = payload.model_dump_json(exclude_none=True)
    if len(raw) > MAX_PROMPT_JSON_CHARS:
        raw = raw[:MAX_PROMPT_JSON_CHARS] + "\n…(已截断)"
    return raw


def _mock_inner_deliberate_spec_change() -> ReportInner:
    """用于测试类别守卫：故意返回 spec_change 且无证据时应被降级。"""
    return ReportInner(
        failure_category="spec_change",
        summary="Mock：疑似规格变更",
        detailed_reason="Mock 占位结论。",
        confidence=0.5,
        data_gaps=[],
        evidence=[],
        stage_timeline=[],
    )


def _inner_from_llm_dict(data: Dict[str, object]) -> ReportInner:
    cat = str(data.get("failure_category", "unknown")).lower()
    if cat not in ("bug", "spec_change", "flaky", "env", "unknown"):
        cat = "unknown"
    conf_raw = data.get("confidence", 0.0)
    try:
        conf = float(conf_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    gaps = data.get("data_gaps")
    gap_list: List[str] = []
    if isinstance(gaps, list):
        gap_list = [str(x) for x in gaps]
    elif gaps is not None:
        gap_list = [str(gaps)]
    return ReportInner(
        failure_category=cat,  # type: ignore[arg-type]
        summary=str(data.get("summary", ""))[:2000],
        detailed_reason=str(data.get("detailed_reason", ""))[:20000],
        confidence=conf,
        data_gaps=gap_list,
        evidence=[],
        stage_timeline=[],
    )


async def stream_analyze(
    payload: AnalyzeRequest,
    request_id: str,
    settings: Settings,
) -> AsyncIterator[str]:
    """产生 SSE 文本块（含 progress / report 或 error）。"""
    t0 = time.perf_counter()
    yield format_sse(
        "progress",
        {"stage": "llm_single", "message": "正在执行单轮归因分析…"},
    )

    has_evidence = has_success_screenshot_evidence(payload.case_context)

    inner: ReportInner
    trace = TracePayload()

    if settings.aifa_llm_mock:
        inner = _mock_inner_deliberate_spec_change()
        trace.llm_input_tokens = 0
        trace.llm_output_tokens = 0
    elif not settings.aifa_llm_base_url or not settings.aifa_llm_api_key:
        yield format_sse(
            "error",
            {
                "error_code": "llm_not_configured",
                "message": "未配置 LLM：请设置 AIFA_LLM_BASE_URL 与 AIFA_LLM_API_KEY，或启用 AIFA_LLM_MOCK",
            },
        )
        return
    else:
        client = AsyncOpenAI(
            api_key=settings.aifa_llm_api_key,
            base_url=settings.aifa_llm_base_url,
            timeout=120.0,
        )
        user_content = _truncate_payload_for_prompt(payload)
        try:
            completion = await client.chat.completions.create(
                model=settings.aifa_llm_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            msg = completion.choices[0].message.content or "{}"
            data = json.loads(msg)
            if not isinstance(data, dict):
                raise ValueError("LLM 返回非 JSON 对象")
            inner = _inner_from_llm_dict(data)
            usage = completion.usage
            if usage:
                trace.llm_input_tokens = usage.prompt_tokens or 0
                trace.llm_output_tokens = usage.completion_tokens or 0
        except (AuthenticationError, APIError, json.JSONDecodeError, ValueError, IndexError) as e:
            logger.warning(
                "LLM 调用失败 request_id=%s session_id=%s: %s",
                request_id,
                payload.session_id,
                type(e).__name__,
            )
            yield format_sse(
                "error",
                {
                    "error_code": "llm_error",
                    "message": f"模型调用或解析失败：{type(e).__name__}",
                },
            )
            return

    apply_category_guard(inner, has_evidence)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    trace.elapsed_ms = elapsed_ms

    envelope = AnalyzeReportEnvelope(
        session_id=payload.session_id,
        status="ok",
        report=inner,
        trace=trace,
    )

    logger.info(
        "分析完成 request_id=%s session_id=%s elapsed_ms=%s in_tokens=%s out_tokens=%s category=%s",
        request_id,
        payload.session_id,
        elapsed_ms,
        trace.llm_input_tokens,
        trace.llm_output_tokens,
        inner.failure_category,
    )

    yield format_sse("report", envelope.model_dump(mode="json"))
