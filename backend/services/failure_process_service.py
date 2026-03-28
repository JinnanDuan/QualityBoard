# ============================================================
# Failure Process Service — 失败记录标注的业务逻辑层
# ============================================================

import asyncio
import logging
from collections import defaultdict
from functools import partial
from typing import Dict, List, Optional

from fastapi import HTTPException, status  # HTTP 异常与状态码
from sqlalchemy import and_, select  # 组合条件、构建查询
from sqlalchemy.ext.asyncio import AsyncSession  # 异步数据库会话

from backend.core.config import settings
from backend.integrations.welink_card import rolling_welink_share
from backend.models.case_failed_type import CaseFailedType  # 失败类型表
from backend.models.pipeline_failure_reason import PipelineFailureReason  # 失败原因表
from backend.models.pipeline_history import PipelineHistory  # 执行历史表
from backend.models.ums_email import UmsEmail  # 员工表
from backend.models.ums_module_owner import UmsModuleOwner  # 模块负责人表
from backend.schemas.failure_process import (
    FailureProcessOptions,
    CaseFailedTypeItem,
    OwnerItem,
    ModuleItem,
    FailureProcessRequest,
)
from backend.services.failed_type_helpers import get_bug_failed_type_value
from backend.services.owner_parsing import parse_employee_id_from_owner

logger = logging.getLogger(__name__)

HANDOFF_CARD_TITLE = "rolling线问题流转通知"
WELINK_GAP_SEC = 0.3


def _failed_type_same(a: Optional[str], b: Optional[str]) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower()


def _operator_display_for_welink(
    analyzer_employee_id: str,
    name: Optional[str],
    domain_account: Optional[str],
) -> str:
    """查得到 ums_email 时用「姓名 域账号」；查不到则只打工号。"""
    eid = (analyzer_employee_id or "").strip()
    if not name and not domain_account:
        return eid
    nm = (name or "").strip()
    dom = (domain_account or "").strip()
    if nm and dom:
        return f"{nm} {dom}"
    if nm:
        return f"{nm} {eid}"
    return eid


async def _send_bug_tracker_handoff_welink(
    db: AsyncSession,
    analyzer_employee_id: str,
    counts_by_new_employee_id: Dict[str, int],
) -> None:
    """
    仍为 bug 且跟踪人变更时，向新跟踪人发送 WeLink（按新工号合并条数，每人至多一条）。
    """
    if not counts_by_new_employee_id:
        return

    op_stmt = select(UmsEmail).where(UmsEmail.employee_id == analyzer_employee_id)
    op_res = await db.execute(op_stmt)
    op_row = op_res.scalars().first()
    if op_row:
        op_display = _operator_display_for_welink(
            analyzer_employee_id,
            op_row.name,
            op_row.domain_account,
        )
    else:
        op_display = (analyzer_employee_id or "").strip() or "未知"

    public_base = (settings.PUBLIC_APP_URL or "").strip()
    link_url = f"{public_base.rstrip('/')}/history" if public_base else ""

    new_eids = list(counts_by_new_employee_id.keys())
    dom_stmt = select(UmsEmail.employee_id, UmsEmail.domain_account).where(
        UmsEmail.employee_id.in_(new_eids)
    )
    dom_res = await db.execute(dom_stmt)
    domain_by_eid: Dict[str, str] = {}
    for eid_row, dom in dom_res.all():
        if dom is not None and str(dom).strip():
            domain_by_eid[str(eid_row)] = str(dom).strip()

    loop = asyncio.get_event_loop()
    for eid, cnt in sorted(counts_by_new_employee_id.items(), key=lambda x: x[0]):
        dom = domain_by_eid.get(eid)
        if not dom:
            logger.warning(
                "失败标注流转通知跳过：新跟踪人工号 %s 无 domain_account，无法发 WeLink",
                eid,
            )
            continue
        remark = (
            f"您好，{op_display} 交接了{cnt}条失败用例给您，请及时分析处理"
        )
        send_fn = partial(
            rolling_welink_share,
            dom,
            HANDOFF_CARD_TITLE,
            remark,
            link_url,
        )
        ok, msg = await loop.run_in_executor(None, send_fn)
        if ok:
            logger.info(
                "失败标注流转通知已发送 收件人=%s 条数=%s",
                dom[:80],
                cnt,
            )
        else:
            logger.warning(
                "失败标注流转通知发送失败 domain=%s detail=%s",
                dom[:80],
                (msg or "")[:200],
            )
        await asyncio.sleep(WELINK_GAP_SEC)


async def get_failure_process_options(db: AsyncSession) -> FailureProcessOptions:
    """获取标注弹窗所需的选项数据（失败类型、跟踪人、模块）。"""
    # 1. 查询 case_failed_type，按 id 排序
    cft_stmt = select(CaseFailedType).order_by(CaseFailedType.id)
    cft_result = await db.execute(cft_stmt)
    case_failed_types = [
        CaseFailedTypeItem(
            id=row.id,
            failed_reason_type=row.failed_reason_type,
            owner=row.owner,
        )
        for row in cft_result.scalars().all()
    ]

    # 2. 查询 ums_email，按 employee_id 排序
    ums_stmt = select(UmsEmail).order_by(UmsEmail.employee_id)
    ums_result = await db.execute(ums_stmt)
    owners = [
        OwnerItem(employee_id=row.employee_id, name=row.name)
        for row in ums_result.scalars().all()
    ]

    # 3. 查询 ums_module_owner，按 module 排序
    umo_stmt = select(UmsModuleOwner).order_by(UmsModuleOwner.module)
    umo_result = await db.execute(umo_stmt)
    modules = [
        ModuleItem(module=row.module, owner=row.owner)
        for row in umo_result.scalars().all()
    ]

    return FailureProcessOptions(
        case_failed_types=case_failed_types,
        owners=owners,
        modules=modules,
    )


async def process_failure(
    db: AsyncSession,
    req: FailureProcessRequest,
    analyzer_employee_id: str,  # 当前登录用户工号，写入 pipeline_failure_reason.analyzer
) -> None:
    """
    处理失败记录标注：更新 pipeline_history.analyzed，插入或更新 pipeline_failure_reason。
    """
    if not req.history_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="history_ids 不能为空")

    # 1. 校验并获取所有 history 记录，确保存在且 case_result 为 failed 或 error（不含 passed/skip）
    ALLOWED_RESULTS = ("failed", "error")
    stmt = select(PipelineHistory).where(PipelineHistory.id.in_(req.history_ids))
    result = await db.execute(stmt)
    histories = list(result.scalars().all())

    if len(histories) != len(req.history_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="部分记录不存在",
        )

    for h in histories:
        if h.case_result not in ALLOWED_RESULTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"记录 id={h.id} 不是失败/异常记录，无法标注",
            )

    bug_type = await get_bug_failed_type_value(db)
    handoff_counts: Dict[str, int] = defaultdict(int)

    # 2. 更新 pipeline_history.analyzed = 1
    for h in histories:
        h.analyzed = 1

    # 3. 对每条记录，按 (case_name, start_time, platform) 判断 INSERT 或 UPDATE
    for h in histories:
        case_name = h.case_name
        failed_batch = h.start_time
        platform = h.platform

        if not case_name or failed_batch is None or platform is None:
            continue  # 关键字段缺失则跳过

        # 按 (case_name, failed_batch, platform) 查询是否已有 pipeline_failure_reason
        pfr_stmt = select(PipelineFailureReason).where(
            and_(
                PipelineFailureReason.case_name == case_name,
                PipelineFailureReason.failed_batch == failed_batch,
                PipelineFailureReason.platform == platform,
            )
        )
        pfr_result = await db.execute(pfr_stmt)
        existing = pfr_result.scalars().first()

        if (
            bug_type
            and existing
            and _failed_type_same(existing.failed_type, bug_type)
            and _failed_type_same(req.failed_type, bug_type)
        ):
            old_eid = parse_employee_id_from_owner(existing.owner or "")
            new_eid = parse_employee_id_from_owner(req.owner)
            if old_eid and new_eid and old_eid != new_eid:
                handoff_counts[new_eid] += 1

        if existing:
            # 已存在则 UPDATE
            existing.owner = req.owner
            existing.reason = req.reason
            existing.failed_type = req.failed_type
            existing.analyzer = analyzer_employee_id
        else:
            # 不存在则 INSERT
            new_pfr = PipelineFailureReason(
                case_name=case_name,
                failed_batch=failed_batch,
                platform=platform,
                owner=req.owner,
                reason=req.reason,
                failed_type=req.failed_type,
                analyzer=analyzer_employee_id,
            )
            db.add(new_pfr)

    try:
        await db.commit()
        owner_masked = f"{req.owner[:2]}***" if req.owner and len(req.owner) > 2 else "***"
        logger.info(
            "失败标注提交成功 记录数=%d failed_type=%s owner=%s analyzer=%s",
            len(histories),
            req.failed_type,
            owner_masked,
            analyzer_employee_id,
        )
        try:
            await _send_bug_tracker_handoff_welink(
                db, analyzer_employee_id, dict(handoff_counts)
            )
        except Exception:
            logger.exception(
                "失败标注流转通知发送过程异常 analyzer=%s",
                analyzer_employee_id,
            )
    except Exception as e:
        logger.exception("失败标注提交失败: %s", e)
        raise
