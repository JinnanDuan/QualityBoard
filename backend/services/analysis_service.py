# ============================================================
# AI 失败分析 — A4 接受/拒绝写库（apply / reject）
# 规约：docs/superpowers/specs/aifa-phase-a4-apply-failure-reason-spec.md
# ============================================================

import logging
import time
from typing import Optional, Set

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.case_failed_type import CaseFailedType
from backend.models.pipeline_failure_reason import PipelineFailureReason
from backend.models.pipeline_history import PipelineHistory
from backend.models.ums_email import UmsEmail
from backend.schemas.analysis import (
    ApplyFailureReasonRequest,
    ApplyFailureReasonResponse,
    RejectFailureReasonRequest,
    RejectFailureReasonResponse,
)
from backend.services.case_dev_owner_helpers import (
    build_module_to_case_dev_owner_display,
    case_dev_owner_display_for_row,
    format_case_dev_owner_display,
)
from backend.services.failed_type_helpers import get_bug_failed_type_value
from backend.utils.audit import build_audit_detail, write_audit_log

logger = logging.getLogger(__name__)

ph = PipelineHistory
pfr = PipelineFailureReason

PFR_OWNER_MAX_LEN = 100
DETAILED_REASON_MAX_LEN = 2000

# 与 A3 `report.failure_category` 对齐（不含 unknown；unknown 禁止一键入库）
AIFA_REPORT_FAILURE_CATEGORIES = frozenset(
    {
        "bug",
        "环境问题",
        "规格变更，用例需适配",
        "用例不稳定，需加固",
        "unknown",
    }
)


def _strip_or_empty(val: Optional[str]) -> str:
    return (val or "").strip()


def _anti_replay_present(req: ApplyFailureReasonRequest) -> bool:
    return any(
        [
            _strip_or_empty(req.session_id),
            _strip_or_empty(req.analysis_draft_id),
            _strip_or_empty(req.version),
            _strip_or_empty(req.nonce),
        ]
    )


async def _audit(
    db: AsyncSession,
    *,
    operator: str,
    action: str,
    history_id: int,
    result_status: str,
    elapsed_ms: float,
    failure_category: Optional[str] = None,
    session_id: Optional[str] = None,
    analysis_draft_id: Optional[str] = None,
    version: Optional[str] = None,
    nonce: Optional[str] = None,
    message: Optional[str] = None,
    extra: Optional[dict] = None,
) -> None:
    detail_obj = {
        "user_employee_id": operator,
        "history_id": history_id,
        "session_id": session_id,
        "action": action,
        "result_status": result_status,
        "failure_category": failure_category,
        "analysis_draft_id": analysis_draft_id,
        "version": version,
        "nonce": nonce,
        "elapsed_ms": int(elapsed_ms),
        "message": message,
    }
    if extra:
        detail_obj.update(extra)
    await write_audit_log(
        db,
        operator=operator,
        action=action,
        target_type="pipeline_history",
        target_id=str(history_id),
        detail=build_audit_detail(detail_obj),
    )


async def _canonical_failed_type_value(db: AsyncSession, failure_category: str) -> str:
    """
    将 A3 的 failure_category 解析为 case_failed_type.failed_reason_type 的库内原值（同值优先，其次大小写不敏感匹配）。
    """
    raw = failure_category.strip()
    if raw.lower() == "unknown":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="failure_category 为 unknown 时不允许一键入库，请先人工复核",
        )
    if raw not in AIFA_REPORT_FAILURE_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="failure_category 不在 AIFA 允许子集内",
        )

    stmt = select(CaseFailedType.failed_reason_type)
    res = await db.execute(stmt)
    db_types = [r[0] for r in res.all() if r[0]]
    if raw in db_types:
        return raw
    lowered = {t.lower(): t for t in db_types}
    key = raw.lower()
    if key in lowered:
        return lowered[key]
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="failure_category 在库内未配置对应失败类型，请联系管理员",
    )


async def _owner_for_non_bug(db: AsyncSession, mapped_failed_type: str) -> str:
    stmt = select(CaseFailedType).where(
        func.lower(func.trim(CaseFailedType.failed_reason_type)) == mapped_failed_type.strip().lower()
    )
    res = await db.execute(stmt)
    row = res.scalars().first()
    if not row:
        logger.error("case_failed_type 缺失记录 mapped_failed_type=%s", mapped_failed_type)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统未配置失败类型映射，请联系管理员",
        )
    eid = _strip_or_empty(row.owner)
    if not eid:
        logger.error("case_failed_type.owner 未配置 mapped_failed_type=%s", mapped_failed_type)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统未为该失败类型配置默认跟踪人，请联系管理员",
        )
    em_res = await db.execute(select(UmsEmail).where(UmsEmail.employee_id == eid))
    em = em_res.scalars().first()
    name = (em.name or "").strip() if em else ""
    display = format_case_dev_owner_display(name or None, eid) or eid
    if len(display) > PFR_OWNER_MAX_LEN:
        logger.warning("AI 一键入库：跟踪人超长已截断 len=%d", len(display))
        display = display[:PFR_OWNER_MAX_LEN]
    return display


async def _owner_for_bug(db: AsyncSession, history_row: PipelineHistory) -> str:
    mm = _strip_or_empty(history_row.main_module)
    if not mm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="主模块为空，无法解析 bug 跟踪人",
        )
    modules: Set[str] = {mm}
    module_to_display = await build_module_to_case_dev_owner_display(db, modules)
    owner_str = case_dev_owner_display_for_row(history_row, module_to_display)
    if not owner_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法解析 bug 跟踪人：请确认主模块是否配置模块负责人",
        )
    if len(owner_str) > PFR_OWNER_MAX_LEN:
        logger.warning("AI 一键入库：跟踪人超长已截断 case_name=%r", history_row.case_name)
        owner_str = owner_str[:PFR_OWNER_MAX_LEN]
    return owner_str


def _normalize_detailed_reason(text: str) -> str:
    s = (text or "").strip()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="detailed_reason 不能为空",
        )
    if len(s) > DETAILED_REASON_MAX_LEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"detailed_reason 长度超过上限（{DETAILED_REASON_MAX_LEN}）",
        )
    return s


def _pfr_matches(
    existing: PipelineFailureReason,
    *,
    failed_type: str,
    reason: str,
    owner: str,
    analyzer: str,
) -> bool:
    same_type = (existing.failed_type or "").strip().lower() == (failed_type or "").strip().lower()
    same_reason = (existing.reason or "").strip() == reason.strip()
    same_owner = (existing.owner or "").strip() == owner.strip()
    same_analyzer = (existing.analyzer or "").strip() == (analyzer or "").strip()
    return same_type and same_reason and same_owner and same_analyzer


async def apply_ai_failure_reason(
    db: AsyncSession,
    req: ApplyFailureReasonRequest,
    analyzer_employee_id: str,
) -> ApplyFailureReasonResponse:
    t0 = time.perf_counter()
    action = "apply_failure_reason"
    hid = req.history_id

    if not _anti_replay_present(req):
        elapsed = (time.perf_counter() - t0) * 1000
        await _audit(
            db,
            operator=analyzer_employee_id,
            action=action,
            history_id=hid,
            result_status="denied",
            elapsed_ms=elapsed,
            failure_category=req.failure_category,
            session_id=_strip_or_empty(req.session_id) or None,
            analysis_draft_id=_strip_or_empty(req.analysis_draft_id) or None,
            version=_strip_or_empty(req.version) or None,
            nonce=_strip_or_empty(req.nonce) or None,
            message="缺少防伪参数",
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少防伪参数：请提供 session_id、analysis_draft_id、version、nonce 至少一项",
        )

    try:
        try:
            mapped_failed_type = await _canonical_failed_type_value(db, req.failure_category)
            reason_text = _normalize_detailed_reason(req.detailed_reason)
        except HTTPException as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            detail = exc.detail
            msg = detail if isinstance(detail, str) else "参数校验失败"
            await _audit(
                db,
                operator=analyzer_employee_id,
                action=action,
                history_id=hid,
                result_status="denied",
                elapsed_ms=elapsed,
                failure_category=req.failure_category,
                session_id=_strip_or_empty(req.session_id) or None,
                analysis_draft_id=_strip_or_empty(req.analysis_draft_id) or None,
                version=_strip_or_empty(req.version) or None,
                nonce=_strip_or_empty(req.nonce) or None,
                message=msg,
            )
            await db.commit()
            raise exc

        bug_val = await get_bug_failed_type_value(db)
        if not bug_val:
            logger.error("case_failed_type 未配置 bug")
            elapsed = (time.perf_counter() - t0) * 1000
            await _audit(
                db,
                operator=analyzer_employee_id,
                action=action,
                history_id=hid,
                result_status="failed",
                elapsed_ms=elapsed,
                failure_category=req.failure_category,
                session_id=_strip_or_empty(req.session_id) or None,
                analysis_draft_id=_strip_or_empty(req.analysis_draft_id) or None,
                version=_strip_or_empty(req.version) or None,
                nonce=_strip_or_empty(req.nonce) or None,
                message="系统未配置 bug 失败类型",
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="系统未配置失败类型 bug，请联系管理员",
            )

        stmt = select(ph).where(ph.id == hid).with_for_update()
        res = await db.execute(stmt)
        history_row = res.scalars().first()
        if not history_row:
            elapsed = (time.perf_counter() - t0) * 1000
            await _audit(
                db,
                operator=analyzer_employee_id,
                action=action,
                history_id=hid,
                result_status="failed",
                elapsed_ms=elapsed,
                failure_category=req.failure_category,
                session_id=_strip_or_empty(req.session_id) or None,
                analysis_draft_id=_strip_or_empty(req.analysis_draft_id) or None,
                version=_strip_or_empty(req.version) or None,
                nonce=_strip_or_empty(req.nonce) or None,
                message="history 不存在",
            )
            await db.commit()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="执行记录不存在")

        if history_row.case_result not in ("failed", "error"):
            elapsed = (time.perf_counter() - t0) * 1000
            await _audit(
                db,
                operator=analyzer_employee_id,
                action=action,
                history_id=hid,
                result_status="denied",
                elapsed_ms=elapsed,
                failure_category=req.failure_category,
                session_id=_strip_or_empty(req.session_id) or None,
                analysis_draft_id=_strip_or_empty(req.analysis_draft_id) or None,
                version=_strip_or_empty(req.version) or None,
                nonce=_strip_or_empty(req.nonce) or None,
                message="非失败/异常记录",
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="仅失败或异常记录允许一键入库",
            )

        case_name = history_row.case_name
        failed_batch = history_row.start_time
        platform = history_row.platform
        if not case_name or failed_batch is None or platform is None:
            elapsed = (time.perf_counter() - t0) * 1000
            await _audit(
                db,
                operator=analyzer_employee_id,
                action=action,
                history_id=hid,
                result_status="failed",
                elapsed_ms=elapsed,
                failure_category=req.failure_category,
                session_id=_strip_or_empty(req.session_id) or None,
                analysis_draft_id=_strip_or_empty(req.analysis_draft_id) or None,
                version=_strip_or_empty(req.version) or None,
                nonce=_strip_or_empty(req.nonce) or None,
                message="关键字段缺失",
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用例名/批次/平台缺失，无法写入失败原因",
            )

        prev_analyzed = history_row.analyzed or 0

        is_bug = mapped_failed_type.strip().lower() == (bug_val or "").strip().lower()
        try:
            if is_bug:
                owner_str = await _owner_for_bug(db, history_row)
            else:
                owner_str = await _owner_for_non_bug(db, mapped_failed_type)
        except HTTPException as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            detail = exc.detail
            msg = detail if isinstance(detail, str) else "跟踪人解析失败"
            rs = "denied" if exc.status_code < 500 else "failed"
            await _audit(
                db,
                operator=analyzer_employee_id,
                action=action,
                history_id=hid,
                result_status=rs,
                elapsed_ms=elapsed,
                failure_category=req.failure_category,
                session_id=_strip_or_empty(req.session_id) or None,
                analysis_draft_id=_strip_or_empty(req.analysis_draft_id) or None,
                version=_strip_or_empty(req.version) or None,
                nonce=_strip_or_empty(req.nonce) or None,
                message=msg,
            )
            await db.commit()
            raise exc

        pfr_stmt = (
            select(pfr)
            .where(
                pfr.case_name == case_name,
                pfr.failed_batch == failed_batch,
                pfr.platform == platform,
            )
            .with_for_update()
        )
        pfr_res = await db.execute(pfr_stmt)
        existing = pfr_res.scalars().first()

        if existing:
            if _pfr_matches(
                existing,
                failed_type=mapped_failed_type,
                reason=reason_text,
                owner=owner_str,
                analyzer=analyzer_employee_id,
            ):
                history_row.analyzed = 1
                analyzed_updated = prev_analyzed != 1
                elapsed = (time.perf_counter() - t0) * 1000
                await _audit(
                    db,
                    operator=analyzer_employee_id,
                    action=action,
                    history_id=hid,
                    result_status="success",
                    elapsed_ms=elapsed,
                    failure_category=req.failure_category,
                    session_id=_strip_or_empty(req.session_id) or None,
                    analysis_draft_id=_strip_or_empty(req.analysis_draft_id) or None,
                    version=_strip_or_empty(req.version) or None,
                    nonce=_strip_or_empty(req.nonce) or None,
                    message="幂等：结论已一致，无需重复写入",
                    extra={"idempotent": True},
                )
                await db.commit()
                return ApplyFailureReasonResponse(
                    history_id=hid,
                    applied=False,
                    analyzed_updated=analyzed_updated,
                    message="结论已一致，未重复写入",
                )
            elapsed = (time.perf_counter() - t0) * 1000
            await _audit(
                db,
                operator=analyzer_employee_id,
                action=action,
                history_id=hid,
                result_status="conflict",
                elapsed_ms=elapsed,
                failure_category=req.failure_category,
                session_id=_strip_or_empty(req.session_id) or None,
                analysis_draft_id=_strip_or_empty(req.analysis_draft_id) or None,
                version=_strip_or_empty(req.version) or None,
                nonce=_strip_or_empty(req.nonce) or None,
                message="已存在人工/其他来源归因，拒绝覆盖",
                extra={
                    "existing_failed_type": existing.failed_type,
                    "existing_owner": existing.owner,
                },
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="已存在失败归因记录；如需覆盖请使用「分析处理」人工确认",
            )

        db.add(
            PipelineFailureReason(
                case_name=case_name,
                failed_batch=failed_batch,
                platform=platform,
                owner=owner_str,
                reason=reason_text,
                failed_type=mapped_failed_type,
                analyzer=analyzer_employee_id,
            )
        )
        history_row.analyzed = 1
        analyzed_updated = prev_analyzed != 1

        elapsed = (time.perf_counter() - t0) * 1000
        await _audit(
            db,
            operator=analyzer_employee_id,
            action=action,
            history_id=hid,
            result_status="success",
            elapsed_ms=elapsed,
            failure_category=req.failure_category,
            session_id=_strip_or_empty(req.session_id) or None,
            analysis_draft_id=_strip_or_empty(req.analysis_draft_id) or None,
            version=_strip_or_empty(req.version) or None,
            nonce=_strip_or_empty(req.nonce) or None,
            message="写入成功",
        )
        await db.commit()
        logger.info(
            "AI 一键入库成功 history_id=%s failed_type=%s analyzer=%s",
            hid,
            mapped_failed_type,
            analyzer_employee_id,
        )
        return ApplyFailureReasonResponse(
            history_id=hid,
            applied=True,
            analyzed_updated=analyzed_updated,
            message="已写入失败原因并标记为已分析",
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("AI 一键入库失败 history_id=%s", hid)
        try:
            await db.rollback()
        except Exception:
            logger.exception("回滚失败 history_id=%s", hid)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="写入失败，请稍后重试",
        )


async def reject_ai_failure_reason(
    db: AsyncSession,
    req: RejectFailureReasonRequest,
    operator_employee_id: str,
) -> RejectFailureReasonResponse:
    t0 = time.perf_counter()
    action = "reject_failure_reason"
    hid = req.history_id
    elapsed = (time.perf_counter() - t0) * 1000
    await _audit(
        db,
        operator=operator_employee_id,
        action=action,
        history_id=hid,
        result_status="success",
        elapsed_ms=elapsed,
        session_id=_strip_or_empty(req.session_id) or None,
        analysis_draft_id=_strip_or_empty(req.analysis_draft_id) or None,
        message=_strip_or_empty(req.reason) or "用户拒绝 AI 草稿",
    )
    await db.commit()
    return RejectFailureReasonResponse(history_id=hid, rejected=True, message="已拒绝本次分析草稿")
