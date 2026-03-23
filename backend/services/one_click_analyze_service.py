# ============================================================
# 一键分析（整批 Bug）— Service
# 规约：spec/11_one_click_batch_analyze_spec.md
# ============================================================

import logging
from typing import List, Optional, Set

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.case_failed_type import CaseFailedType
from backend.models.pipeline_failure_reason import PipelineFailureReason
from backend.models.pipeline_history import PipelineHistory
from backend.schemas.one_click_analyze import (
    OneClickAnalyzeRequest,
    OneClickAnalyzeResponse,
)
from backend.services.case_dev_owner_helpers import (
    build_module_to_case_dev_owner_display,
    case_dev_owner_display_for_row,
)
from backend.services.inherit_failure_reason_service import (
    _mysql_get_lock,
    _mysql_release_lock,
)

logger = logging.getLogger(__name__)

ph = PipelineHistory
pfr = PipelineFailureReason
ALLOWED_RESULTS = ("failed", "error")  # 一键分析仅处理失败/异常；skip、passed 等不参与
PFR_OWNER_MAX_LEN = 100
_HISTORY_UPDATE_CHUNK = 500
_LOCK_MAX_LEN = 64


def _lock_name_one_click(batch: str) -> str:
    n = f"one_click_tb_{batch}"
    return n[:_LOCK_MAX_LEN]


async def _get_bug_failed_type_value(db: AsyncSession) -> Optional[str]:
    """返回 case_failed_type 中代表 bug 的 failed_reason_type 原值。"""
    stmt = (
        select(CaseFailedType.failed_reason_type)
        .where(func.lower(func.trim(CaseFailedType.failed_reason_type)) == "bug")
        .limit(1)
    )
    r = await db.execute(stmt)
    return r.scalars().first()


async def _bulk_set_analyzed(db: AsyncSession, history_ids: List[int]) -> None:
    if not history_ids:
        return
    for i in range(0, len(history_ids), _HISTORY_UPDATE_CHUNK):
        chunk = history_ids[i : i + _HISTORY_UPDATE_CHUNK]
        await db.execute(update(ph).where(ph.id.in_(chunk)).values(analyzed=1))


async def one_click_analyze(
    db: AsyncSession,
    req: OneClickAnalyzeRequest,
    analyzer_employee_id: str,
) -> OneClickAnalyzeResponse:
    """
    以锚点解析批次，对该批次下所有未分析的 failed/error 用例一键写入 bug 及用例开发责任人（姓名+工号）。
    """
    stmt_anchor = select(ph).where(ph.id == req.anchor_history_id)
    res_anchor = await db.execute(stmt_anchor)
    anchor = res_anchor.scalars().first()

    if not anchor:
        logger.warning("一键分析：锚点不存在 anchor_history_id=%s", req.anchor_history_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="锚点记录不存在")

    if anchor.case_result not in ALLOWED_RESULTS:
        logger.warning(
            "一键分析：锚点非失败/异常 id=%s case_result=%s",
            req.anchor_history_id,
            anchor.case_result,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="锚点须为失败或异常用例",
        )

    if anchor.analyzed == 1:
        logger.warning("一键分析：锚点已分析 id=%s", req.anchor_history_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择未分析的失败记录作为锚点",
        )

    batch = anchor.start_time
    if not batch or not str(batch).strip():
        logger.warning("一键分析：锚点批次为空 id=%s", req.anchor_history_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="锚点批次无效")

    batch = str(batch).strip()
    lock_name = _lock_name_one_click(batch)

    if not await _mysql_get_lock(db, lock_name):
        logger.warning(
            "一键分析：批次锁获取失败 lock=%s 操作人=%s",
            lock_name,
            analyzer_employee_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="当前目标批次正在其他任务中处理，请稍后重试",
        )

    try:
        bug_failed_type = await _get_bug_failed_type_value(db)
        if not bug_failed_type:
            logger.error("一键分析：case_failed_type 未配置 bug")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="系统未配置失败类型 bug，请联系管理员",
            )

        target_stmt = select(ph).where(
            ph.start_time == batch,
            ph.case_result.in_(ALLOWED_RESULTS),
            or_(ph.analyzed == 0, ph.analyzed.is_(None)),
        )
        target_result = await db.execute(target_stmt)
        targets: List[PipelineHistory] = list(target_result.scalars().all())

        if not targets:
            await db.commit()
            return OneClickAnalyzeResponse(
                success=True,
                message="本批次没有待一键分析的失败/异常记录（未分析）",
                batch=batch,
                applied_count=0,
                skipped_no_owner_count=0,
                skipped_not_eligible_count=0,
            )

        modules: Set[str] = {
            r.main_module.strip() for r in targets if r.main_module and r.main_module.strip()
        }
        module_to_display = await build_module_to_case_dev_owner_display(db, modules)

        reason_text = f"在{batch}轮次新增失败"
        applied_ids: List[int] = []
        skipped_no_owner = 0
        skipped_ineligible = 0

        for h in targets:
            case_name = h.case_name
            failed_batch = h.start_time
            platform = h.platform

            if not case_name or failed_batch is None or platform is None:
                skipped_ineligible += 1
                continue

            owner_str = case_dev_owner_display_for_row(h, module_to_display)
            if not owner_str:
                skipped_no_owner += 1
                logger.info(
                    "一键分析跳过：无模块负责人 case_name=%r platform=%r",
                    case_name,
                    platform,
                )
                continue

            if len(owner_str) > PFR_OWNER_MAX_LEN:
                logger.warning(
                    "一键分析：跟踪人超长已截断 case_name=%r len=%d",
                    case_name,
                    len(owner_str),
                )
                owner_str = owner_str[:PFR_OWNER_MAX_LEN]

            pfr_stmt = select(pfr).where(
                and_(
                    pfr.case_name == case_name,
                    pfr.failed_batch == failed_batch,
                    pfr.platform == platform,
                )
            )
            pfr_result = await db.execute(pfr_stmt)
            existing = pfr_result.scalars().first()

            if existing:
                existing.owner = owner_str
                existing.reason = reason_text
                existing.failed_type = bug_failed_type
                existing.analyzer = analyzer_employee_id
            else:
                db.add(
                    PipelineFailureReason(
                        case_name=case_name,
                        failed_batch=failed_batch,
                        platform=platform,
                        owner=owner_str,
                        reason=reason_text,
                        failed_type=bug_failed_type,
                        analyzer=analyzer_employee_id,
                    )
                )

            applied_ids.append(h.id)

        await _bulk_set_analyzed(db, applied_ids)
        await db.commit()

        logger.info(
            "一键分析成功 batch=%s applied=%d skipped_no_owner=%d skipped_ineligible=%d analyzer=%s",
            batch,
            len(applied_ids),
            skipped_no_owner,
            skipped_ineligible,
            analyzer_employee_id,
        )

        msg_parts = [f"一键分析完成，成功 {len(applied_ids)} 条"]
        if skipped_no_owner:
            msg_parts.append(f"因无模块负责人跳过 {skipped_no_owner} 条")
        if skipped_ineligible:
            msg_parts.append(f"因关键字段缺失跳过 {skipped_ineligible} 条")

        return OneClickAnalyzeResponse(
            success=True,
            message="，".join(msg_parts),
            batch=batch,
            applied_count=len(applied_ids),
            skipped_no_owner_count=skipped_no_owner,
            skipped_not_eligible_count=skipped_ineligible,
        )

    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        logger.exception("一键分析失败 batch=%s", batch)
        await db.rollback()
        raise
    finally:
        await _mysql_release_lock(db, lock_name)
