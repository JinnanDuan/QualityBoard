"""B2 三阶段分析：Plan / Act / Synthesize、session 复用、SSE 事件生成。"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from openai import APIError, AsyncOpenAI, AuthenticationError
from pydantic import BaseModel, ValidationError

from ai_failure_analyzer.api.v1.schemas.report import (
    AnalyzeReportEnvelope,
    EvidenceItem,
    ReportInner,
    StageTimelineItem,
    TracePayload,
)
from ai_failure_analyzer.api.v1.schemas.request import AnalyzeRequest, CaseContext
from ai_failure_analyzer.core.config import Settings
from ai_failure_analyzer.services.evidence_tools import (
    fetch_report_html,
    fetch_screenshot_b64,
    resolve_evidence_urls,
)
from ai_failure_analyzer.services.sse import format_sse

logger = logging.getLogger(__name__)

MAX_PROMPT_JSON_CHARS = 120_000
MAX_PLAN_JSON_CHARS = 8_000
MAX_SYNTHESIS_INPUT_CHARS = 30_000
SESSION_TTL_SECONDS = 30 * 60
SESSION_MAX_SIZE = 500
CATEGORY_BUG = "bug"
CATEGORY_ENV = "环境问题"
CATEGORY_SPEC_CHANGE = "规格变更，用例需适配"
CATEGORY_FLAKY = "用例不稳定，需加固"
CATEGORY_UNKNOWN = "unknown"
ALLOWED_FAILURE_CATEGORIES = (
    CATEGORY_BUG,
    CATEGORY_ENV,
    CATEGORY_SPEC_CHANGE,
    CATEGORY_FLAKY,
    CATEGORY_UNKNOWN,
)
SKILL_HISTORY = "history_skill"
SKILL_REPORT = "report_analysis_skill"
SKILL_SCREENSHOT = "screenshot_skill"
SKILL_CODE_BLAME = "code_blame_skill"
SKILL_SYNTHESIS = "synthesis_skill"
ALLOWED_SKILLS = (SKILL_HISTORY, SKILL_REPORT, SKILL_SCREENSHOT, SKILL_CODE_BLAME)

_SESSION_STORE: Dict[str, Dict[str, Any]] = {}

SYSTEM_PROMPT = """你是测试失败归因助手。只根据用户给出的 JSON 上下文做推断，不要编造未出现的堆栈或日志。
必须只输出一个 JSON 对象（不要 markdown），字段严格如下：
{
  "failure_category": "bug|环境问题|规格变更，用例需适配|用例不稳定，需加固|unknown",
  "summary": "一句话结论（中文）",
  "detailed_reason": "详细失败原因（中文）",
  "confidence": 0.0 到 1.0 的小数,
  "data_gaps": ["可选，列举信息不足点，中文"]
}
failure_category 含义：bug=产品缺陷；环境问题=环境异常；规格变更，用例需适配=需求或界面已变化；用例不稳定，需加固=偶发抖动或竞态；unknown=证据不足。
若缺少成功侧截图对比证据，请不要输出「规格变更，用例需适配」或「用例不稳定，需加固」，应使用 unknown 并在 data_gaps 说明。"""

PLAN_SYSTEM_PROMPT = """你是失败分析任务规划器。你必须只输出一个 JSON 对象，格式如下：
{
  "skills": ["history_skill", "report_analysis_skill", "screenshot_skill", "code_blame_skill"],
  "reason": "简短中文说明"
}
规则：
1) skills 只能从 history_skill/report_analysis_skill/screenshot_skill/code_blame_skill 中选择；
2) skills 最少 1 个，最多 4 个；
3) 不要输出 markdown，不要输出额外字段。"""


class PlanPayload(BaseModel):
    skills: List[str]
    reason: Optional[str] = None


class SessionPayload(BaseModel):
    session_id: str
    mode: str
    plan: List[str]
    skill_summaries: Dict[str, Dict[str, object]]
    stage_timeline: List[StageTimelineItem]
    data_gaps: List[str]
    updated_at: int

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
    """无成功侧截图证据时禁止规格变更/用例不稳定。"""
    if has_evidence:
        return
    if inner.failure_category in (CATEGORY_SPEC_CHANGE, CATEGORY_FLAKY):
        msg = "缺少成功侧截图对比证据，已将失败归类降级为 unknown"
        inner.failure_category = CATEGORY_UNKNOWN
        if msg not in inner.data_gaps:
            inner.data_gaps = list(inner.data_gaps) + [msg]


def _truncate_payload_for_prompt(payload: AnalyzeRequest) -> str:
    raw = payload.model_dump_json(exclude_none=True)
    if len(raw) > MAX_PROMPT_JSON_CHARS:
        raw = raw[:MAX_PROMPT_JSON_CHARS] + "\n…(已截断)"
    return raw


def _now_ts() -> int:
    return int(time.time())


def _cleanup_sessions() -> None:
    now_ts = _now_ts()
    expired_ids: List[str] = []
    for sid, item in _SESSION_STORE.items():
        updated_at = int(item.get("updated_at", 0))
        if now_ts - updated_at > SESSION_TTL_SECONDS:
            expired_ids.append(sid)
    for sid in expired_ids:
        _SESSION_STORE.pop(sid, None)
    if len(_SESSION_STORE) <= SESSION_MAX_SIZE:
        return
    survivors: List[Tuple[str, int]] = []
    for sid, item in _SESSION_STORE.items():
        survivors.append((sid, int(item.get("updated_at", 0))))
    survivors.sort(key=lambda x: x[1], reverse=True)
    keep = set(sid for sid, _ in survivors[:SESSION_MAX_SIZE])
    stale = [sid for sid in _SESSION_STORE.keys() if sid not in keep]
    for sid in stale:
        _SESSION_STORE.pop(sid, None)


def _save_session(
    session_id: str,
    mode: str,
    plan: List[str],
    skill_summaries: Dict[str, Dict[str, object]],
    stage_timeline: List[StageTimelineItem],
    data_gaps: List[str],
) -> None:
    _cleanup_sessions()
    payload = SessionPayload(
        session_id=session_id,
        mode=mode,
        plan=plan,
        skill_summaries=skill_summaries,
        stage_timeline=stage_timeline,
        data_gaps=data_gaps,
        updated_at=_now_ts(),
    )
    _SESSION_STORE[session_id] = payload.model_dump(mode="json")


def _load_session(session_id: str) -> Optional[SessionPayload]:
    _cleanup_sessions()
    raw = _SESSION_STORE.get(session_id)
    if raw is None:
        return None
    try:
        payload = SessionPayload.model_validate(raw)
    except ValidationError:
        _SESSION_STORE.pop(session_id, None)
        return None
    if _now_ts() - payload.updated_at > SESSION_TTL_SECONDS:
        _SESSION_STORE.pop(session_id, None)
        return None
    return payload


def _inner_from_llm_dict(data: Dict[str, object]) -> ReportInner:
    raw_cat = str(data.get("failure_category", CATEGORY_UNKNOWN)).strip()
    category_alias = {
        "bug": CATEGORY_BUG,
        "env": CATEGORY_ENV,
        "环境问题": CATEGORY_ENV,
        "spec_change": CATEGORY_SPEC_CHANGE,
        "规格变更": CATEGORY_SPEC_CHANGE,
        "规格变更，用例需适配": CATEGORY_SPEC_CHANGE,
        "flaky": CATEGORY_FLAKY,
        "用例不稳定": CATEGORY_FLAKY,
        "用例不稳定，需加固": CATEGORY_FLAKY,
        "unknown": CATEGORY_UNKNOWN,
    }
    cat = category_alias.get(raw_cat.lower(), category_alias.get(raw_cat, CATEGORY_UNKNOWN))
    if cat not in ALLOWED_FAILURE_CATEGORIES:
        cat = CATEGORY_UNKNOWN
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
    summary = str(data.get("summary", "")).strip()[:2000]
    if not summary:
        summary = "暂未形成明确结论"
    detailed_reason = str(data.get("detailed_reason", "")).strip()[:20000]
    if not detailed_reason:
        detailed_reason = "当前证据不足，建议结合日志、截图和历史执行进一步人工复核。"
    return ReportInner(
        failure_category=cat,  # type: ignore[arg-type]
        summary=summary,
        detailed_reason=detailed_reason,
        confidence=conf,
        data_gaps=gap_list,
        evidence=[],
        stage_timeline=[],
    )


def _safe_summary_limit(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n…(已截断)"


def _build_history_summary(payload: AnalyzeRequest) -> Dict[str, object]:
    recent = payload.recent_executions or []
    total = len(recent)
    fail_count = 0
    pass_count = 0
    last_pass_batch = payload.case_context.last_success_batch if payload.case_context else None
    for item in recent:
        result = (item.case_result or "").strip().lower()
        if result in ("pass", "success", "通过"):
            pass_count += 1
        elif result:
            fail_count += 1
    pattern = "new"
    if total == 0:
        pattern = "unknown"
    elif fail_count == 0 and pass_count > 0:
        pattern = "stable"
    elif pass_count > 0 and fail_count > 0:
        pattern = "flaky"
    elif fail_count > 0 and pass_count == 0:
        pattern = "regression"
    return {
        "pattern": pattern,
        "last_pass_batch": last_pass_batch,
        "recent_total": total,
        "recent_pass": pass_count,
        "recent_fail": fail_count,
    }


def _derive_plan_from_payload(payload: AnalyzeRequest) -> List[str]:
    plan: List[str] = [SKILL_HISTORY]
    ctx = payload.case_context
    if ctx is not None and (ctx.reports_url or "").strip():
        plan.append(SKILL_REPORT)
    has_any_screenshot = False
    if ctx is not None:
        if len(ctx.screenshot_urls or []) > 0:
            has_any_screenshot = True
        elif (ctx.screenshot_index_url or "").strip():
            has_any_screenshot = True
    if has_any_screenshot:
        plan.append(SKILL_SCREENSHOT)
    if payload.repo_hint is not None and (payload.repo_hint.repo_url or "").strip():
        plan.append(SKILL_CODE_BLAME)
    dedup: List[str] = []
    for skill in plan:
        if skill in ALLOWED_SKILLS and skill not in dedup:
            dedup.append(skill)
    if not dedup:
        dedup = [SKILL_HISTORY]
    return dedup


def _normalize_plan(raw_skills: List[str]) -> List[str]:
    result: List[str] = []
    for item in raw_skills:
        skill = str(item).strip()
        if skill in ALLOWED_SKILLS and skill not in result:
            result.append(skill)
    if not result:
        return [SKILL_HISTORY]
    return result


async def _run_plan_stage(
    payload: AnalyzeRequest,
    settings: Settings,
    trace: TracePayload,
) -> Tuple[List[str], List[str]]:
    data_gaps: List[str] = []
    derived = _derive_plan_from_payload(payload)
    if settings.aifa_llm_mock:
        return derived, data_gaps
    if not settings.aifa_llm_base_url or not settings.aifa_llm_api_key:
        data_gaps.append("LLM 未配置，Plan 阶段使用兜底策略")
        return derived, data_gaps
    client = AsyncOpenAI(
        api_key=settings.aifa_llm_api_key,
        base_url=settings.aifa_llm_base_url,
        timeout=60.0,
    )
    plan_input = {
        "mode": payload.mode,
        "case_context": payload.case_context.model_dump(exclude_none=True) if payload.case_context else {},
        "recent_executions_count": len(payload.recent_executions or []),
        "repo_hint": payload.repo_hint.model_dump(exclude_none=True) if payload.repo_hint else {},
    }
    user_content = _safe_summary_limit(
        json.dumps(plan_input, ensure_ascii=False),
        MAX_PLAN_JSON_CHARS,
    )
    try:
        completion = await client.chat.completions.create(
            model=settings.aifa_llm_model,
            messages=[
                {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        msg = completion.choices[0].message.content or "{}"
        parsed = json.loads(msg)
        if not isinstance(parsed, dict):
            raise ValueError("plan_not_object")
        plan_payload = PlanPayload.model_validate(parsed)
        plan = _normalize_plan(plan_payload.skills)
        usage = completion.usage
        if usage:
            trace.llm_input_tokens += usage.prompt_tokens or 0
            trace.llm_output_tokens += usage.completion_tokens or 0
        return plan, data_gaps
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Plan 阶段失败，使用兜底计划 request_id=%s session_id=%s error=%s",
            "-",  # request_id 仅用于日志弱依赖，避免修改函数签名复杂度
            payload.session_id,
            type(exc).__name__,
        )
        data_gaps.append("Plan 输出无效，已使用兜底计划")
        return derived, data_gaps


def _extract_report_skill_summary(report_result: Dict[str, object]) -> Dict[str, object]:
    if "error" in report_result:
        return {
            "error_lines": [],
            "stack_summary": "",
            "keywords": [],
            "report_excerpt": "",
            "error": report_result.get("error"),
        }
    text = str(report_result.get("text", ""))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    error_lines = [line for line in lines if "error" in line.lower()][:5]
    keywords: List[str] = []
    for token in ("exception", "error", "timeout", "assert"):
        if token in text.lower():
            keywords.append(token)
    return {
        "error_lines": error_lines,
        "stack_summary": lines[0] if lines else "",
        "keywords": keywords,
        "report_excerpt": _safe_summary_limit(text, 800),
    }


def _extract_screenshot_skill_summary(result: Dict[str, object]) -> Dict[str, object]:
    if "error" in result:
        return {
            "ui_state": "unknown",
            "visible_error_text": "",
            "description": "",
            "compare_notes": [],
            "error": result.get("error"),
        }
    if "images" in result:
        count = int(result.get("image_count", 0) or 0)
        notes: List[str] = []
        if bool(result.get("truncated_by_max_images")):
            notes.append("截图数量超限，已截断采样")
        skipped = result.get("skipped_errors")
        if isinstance(skipped, list) and skipped:
            notes.append("部分截图拉取失败")
        return {
            "ui_state": "captured",
            "visible_error_text": "",
            "description": "共获取截图 %s 张" % count,
            "compare_notes": notes,
        }
    return {
        "ui_state": "captured",
        "visible_error_text": "",
        "description": "获取到单张截图",
        "compare_notes": [],
    }


def _build_synthesis_input(
    payload: AnalyzeRequest,
    plan: List[str],
    skill_summaries: Dict[str, Dict[str, object]],
    data_gaps: List[str],
    follow_up_message: Optional[str],
) -> str:
    base = {
        "mode": payload.mode,
        "session_id": payload.session_id,
        "follow_up_message": follow_up_message,
        "plan": plan,
        "case_context": payload.case_context.model_dump(exclude_none=True) if payload.case_context else {},
        "skill_summaries": skill_summaries,
        "data_gaps": data_gaps,
    }
    raw = json.dumps(base, ensure_ascii=False)
    return _safe_summary_limit(raw, MAX_SYNTHESIS_INPUT_CHARS)


def _build_mock_inner_from_summaries(
    has_evidence: bool,
    data_gaps: List[str],
) -> ReportInner:
    category = CATEGORY_SPEC_CHANGE if has_evidence else CATEGORY_UNKNOWN
    summary = "Mock：已按三阶段流程生成结论"
    detailed = "该结果由 Mock 模式生成，用于验证 Plan/Act/Synthesize 主循环。"
    return ReportInner(
        failure_category=category,  # type: ignore[arg-type]
        summary=summary,
        detailed_reason=detailed,
        confidence=0.5,
        data_gaps=data_gaps,
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
    timeline: List[StageTimelineItem] = []
    stage_start = time.perf_counter()
    trace = TracePayload(skills_invoked=[])
    all_data_gaps: List[str] = []
    has_evidence = has_success_screenshot_evidence(payload.case_context)

    plan: List[str] = []
    skill_summaries: Dict[str, Dict[str, object]] = {}
    if payload.mode == "follow_up":
        yield format_sse("progress", {"stage": "synthesize_started", "message": "正在加载历史会话并生成追问结论..."})
        session = _load_session(payload.session_id)
        if session is None:
            yield format_sse(
                "error",
                {
                    "error_code": "session_not_found",
                    "message": "未找到可复用会话，请先发起 initial 分析",
                },
            )
            return
        plan = list(session.plan)
        skill_summaries = dict(session.skill_summaries)
        all_data_gaps = list(session.data_gaps)
        timeline = list(session.stage_timeline)
        trace.skills_invoked = [SKILL_SYNTHESIS]
    else:
        yield format_sse("progress", {"stage": "plan_started", "message": "正在规划分析路径..."})
        plan, plan_gaps = await _run_plan_stage(payload, settings, trace)
        all_data_gaps.extend(plan_gaps)
        timeline.append(
            StageTimelineItem(
                stage="plan",
                message="规划技能执行顺序",
                elapsed_ms=int((time.perf_counter() - stage_start) * 1000),
            )
        )
        yield format_sse("progress", {"stage": "plan_done", "message": "规划完成"})

        yield format_sse("progress", {"stage": "act_started", "message": "正在执行证据提取与分析..."})
        act_start = time.perf_counter()
        resolved_urls: Dict[str, object] = {}
        if payload.case_context is not None:
            resolved_urls = await resolve_evidence_urls(
                settings=settings,
                reports_url=payload.case_context.reports_url,
                screenshot_urls=payload.case_context.screenshot_urls,
                screenshot_index_url=payload.case_context.screenshot_index_url,
            )
            resolution_errors = resolved_urls.get("errors")
            if isinstance(resolution_errors, list):
                for item in resolution_errors:
                    if not isinstance(item, dict):
                        continue
                    code = str(item.get("code", "unknown"))
                    field = str(item.get("field", "unknown"))
                    label = "截图" if "screenshot" in field else "报告"
                    gap = "%s URL 解析失败（%s:%s）" % (label, field, code)
                    if gap not in all_data_gaps:
                        all_data_gaps.append(gap)
            resolution_meta = resolved_urls.get("url_resolution_meta")
            if isinstance(resolution_meta, dict):
                warning_items = resolution_meta.get("warnings")
                if isinstance(warning_items, list):
                    for warning in warning_items:
                        text = "URL 解析提示：%s" % str(warning)
                        if text not in all_data_gaps:
                            all_data_gaps.append(text)
        for skill in plan:
            trace.skills_invoked.append(skill)
            if skill == SKILL_HISTORY:
                skill_summaries[skill] = _build_history_summary(payload)
                continue
            if skill == SKILL_REPORT:
                report_url = str(resolved_urls.get("report_url", "")).strip()
                if not report_url:
                    all_data_gaps.append("缺少 reports_url，跳过报告分析")
                    skill_summaries[skill] = {
                        "error_lines": [],
                        "stack_summary": "",
                        "keywords": [],
                        "report_excerpt": "",
                        "error": "reports_url_missing",
                    }
                    continue
                report_result = await fetch_report_html(report_url, settings=settings)
                trace.tool_calls += 1
                if "error" in report_result:
                    all_data_gaps.append("报告抓取失败：%s" % str(report_result.get("error")))
                skill_summaries[skill] = _extract_report_skill_summary(report_result)
                continue
            if skill == SKILL_SCREENSHOT:
                screenshot_candidates_raw = resolved_urls.get("screenshot_urls", [])
                screenshot_candidates: List[str] = []
                if isinstance(screenshot_candidates_raw, list):
                    for item in screenshot_candidates_raw:
                        if isinstance(item, str) and item.strip():
                            screenshot_candidates.append(item.strip())
                if not screenshot_candidates:
                    all_data_gaps.append("缺少截图 URL，跳过截图分析")
                    skill_summaries[skill] = {
                        "ui_state": "unknown",
                        "visible_error_text": "",
                        "description": "",
                        "compare_notes": [],
                        "error": "screenshot_url_missing",
                    }
                    continue
                screenshot_result = await fetch_screenshot_b64(screenshot_candidates[0], settings=settings)
                trace.tool_calls += 1
                if "error" in screenshot_result:
                    all_data_gaps.append("截图抓取失败：%s" % str(screenshot_result.get("error")))
                screenshot_summary = _extract_screenshot_skill_summary(screenshot_result)
                meta = resolved_urls.get("url_resolution_meta")
                if isinstance(meta, dict):
                    screenshot_summary["url_resolution_meta"] = meta
                skill_summaries[skill] = screenshot_summary
                continue
            if skill == SKILL_CODE_BLAME:
                all_data_gaps.append("CodeHub 工具尚未启用，已跳过代码归因")
                skill_summaries[skill] = {"suspect_patches": [], "error": "tool_not_implemented"}
                continue
            all_data_gaps.append("未知 skill：%s" % skill)
        timeline.append(
            StageTimelineItem(
                stage="act",
                message="执行技能分析",
                elapsed_ms=int((time.perf_counter() - act_start) * 1000),
            )
        )
        yield format_sse("progress", {"stage": "act_done", "message": "执行完成"})

    yield format_sse("progress", {"stage": "synthesize_started", "message": "正在生成归因结论..."})
    synth_start = time.perf_counter()
    inner: ReportInner

    if settings.aifa_llm_mock:
        inner = _build_mock_inner_from_summaries(has_evidence, list(all_data_gaps))
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
        user_content = _build_synthesis_input(
            payload=payload,
            plan=plan,
            skill_summaries=skill_summaries,
            data_gaps=all_data_gaps,
            follow_up_message=payload.follow_up_message,
        )
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
                trace.llm_input_tokens += usage.prompt_tokens or 0
                trace.llm_output_tokens += usage.completion_tokens or 0
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
                    "message": "模型调用或解析失败：%s" % type(e).__name__,
                },
            )
            return

    apply_category_guard(inner, has_evidence)
    if all_data_gaps:
        combined = list(inner.data_gaps)
        for gap in all_data_gaps:
            if gap not in combined:
                combined.append(gap)
        inner.data_gaps = combined

    evidence: List[EvidenceItem] = []
    for skill_name in trace.skills_invoked[:6]:
        summary = skill_summaries.get(skill_name, {})
        snippet = _safe_summary_limit(json.dumps(summary, ensure_ascii=False), 300)
        evidence.append(
            EvidenceItem(
                id="e_%s" % skill_name.replace("_skill", ""),
                type=skill_name,
                source="skill_summary",
                snippet=snippet,
                reference=skill_name,
            )
        )
    inner.evidence = evidence
    timeline.append(
        StageTimelineItem(
            stage="synthesis",
            message="生成归因结论",
            elapsed_ms=int((time.perf_counter() - synth_start) * 1000),
        )
    )
    inner.stage_timeline = timeline
    trace.skills_invoked = trace.skills_invoked or [SKILL_SYNTHESIS]

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    trace.elapsed_ms = elapsed_ms
    status = "ok"
    if len(inner.data_gaps) > 0:
        status = "partial"
    if payload.mode == "initial":
        _save_session(
            session_id=payload.session_id,
            mode=payload.mode,
            plan=plan,
            skill_summaries=skill_summaries,
            stage_timeline=timeline,
            data_gaps=inner.data_gaps,
        )
    yield format_sse("progress", {"stage": "synthesize_done", "message": "结论生成完成"})

    envelope = AnalyzeReportEnvelope(
        session_id=payload.session_id,
        status=status,  # type: ignore[arg-type]
        report=inner,
        trace=trace,
    )

    logger.info(
        "分析完成 request_id=%s session_id=%s elapsed_ms=%s in_tokens=%s out_tokens=%s category=%s status=%s",
        request_id,
        payload.session_id,
        elapsed_ms,
        trace.llm_input_tokens,
        trace.llm_output_tokens,
        inner.failure_category,
        status,
    )

    yield format_sse("report", envelope.model_dump(mode="json"))
