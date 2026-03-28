# ============================================================
# 一键通知（Bug 失败跟踪人 · WeLink）— Service
# 规约：spec/13_one_click_bug_notify_spec.md
# ============================================================

import asyncio
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlencode

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.integrations.welink_card import rolling_welink_share
from backend.models.pipeline_failure_reason import PipelineFailureReason
from backend.models.pipeline_history import PipelineHistory
from backend.models.ums_email import UmsEmail
from backend.schemas.one_click_bug_notify import (
    BugNotifyFailedOwnerItem,
    OneClickBugNotifyDetails,
    OneClickBugNotifyRequest,
    OneClickBugNotifyResponse,
)
from backend.services.failed_type_helpers import get_bug_failed_type_value
from backend.services.owner_parsing import parse_employee_id_from_owner

logger = logging.getLogger(__name__)

ph = PipelineHistory
pfr = PipelineFailureReason
ALLOWED_RESULTS = ("failed", "error")
DETAIL_CAP = 20
WELINK_GAP_SEC = 0.3
TITLE = "rolling线防护通知"


def _build_history_url(base: str, batch: str, owner_full: str, failed_type: str) -> str:
    base = base.rstrip("/")
    q = urlencode(
        {
            "start_time": batch,
            "failure_owner": owner_full,
            "failed_type": failed_type,
        }
    )
    return f"{base}/history?{q}"


async def one_click_bug_notify(
    db: AsyncSession,
    req: OneClickBugNotifyRequest,
    operator_employee_id: str,
) -> OneClickBugNotifyResponse:
    stmt_anchor = select(ph).where(ph.id == req.anchor_history_id)
    res_anchor = await db.execute(stmt_anchor)
    anchor = res_anchor.scalars().first()

    if not anchor:
        logger.warning("一键通知：锚点不存在 anchor_history_id=%s", req.anchor_history_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="锚点记录不存在")

    if anchor.case_result not in ALLOWED_RESULTS:
        logger.warning(
            "一键通知：锚点非失败/异常 id=%s case_result=%s",
            req.anchor_history_id,
            anchor.case_result,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="锚点须为失败或异常用例",
        )

    batch = anchor.start_time
    if not batch or not str(batch).strip():
        logger.warning("一键通知：锚点批次为空 id=%s", req.anchor_history_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="锚点批次无效")
    batch = str(batch).strip()

    if req.selected_history_ids:
        raw_ids = [i for i in req.selected_history_ids if i is not None and i >= 1]
        uniq_ids = list(set(raw_ids))
        if uniq_ids:
            stmt_sel = select(ph).where(ph.id.in_(uniq_ids))
            rsel = await db.execute(stmt_sel)
            rows_sel = list(rsel.scalars().all())
            if len(rows_sel) != len(uniq_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="所选记录不存在",
                )
            for row in rows_sel:
                st = row.start_time
                st_norm = str(st).strip() if st is not None else ""
                if st_norm != batch:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="所选记录须属于同一轮次",
                    )

    public_base = (settings.PUBLIC_APP_URL or "").strip()
    if not public_base:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未配置 PUBLIC_APP_URL，无法生成消息中的访问链接",
        )

    bug_type = await get_bug_failed_type_value(db)
    if not bug_type:
        logger.error("一键通知：case_failed_type 未配置 bug")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统未配置失败类型 bug，请联系管理员",
        )

    stmt_ph = select(ph.case_name, ph.platform).where(
        ph.start_time == batch,
        ph.case_result.in_(ALLOWED_RESULTS),
    )
    rph = await db.execute(stmt_ph)
    ph_keys: Set[Tuple[Optional[str], Optional[str]]] = set()
    for cn, pl in rph.all():
        ph_keys.add((cn, pl))

    stmt_pfr = select(pfr.case_name, pfr.platform, pfr.owner).where(
        and_(
            pfr.failed_batch == batch,
            pfr.failed_type == bug_type,
            pfr.owner.isnot(None),
            pfr.owner != "",
        )
    )
    rpfr = await db.execute(stmt_pfr)
    counts: Dict[str, int] = defaultdict(int)
    for cn, pl, ow in rpfr.all():
        if not ow or not str(ow).strip():
            continue
        if (cn, pl) not in ph_keys:
            continue
        counts[str(ow).strip()] += 1

    if not counts:
        return OneClickBugNotifyResponse(
            success=True,
            message="本批次无失败类型为 bug 的跟踪记录",
            batch=batch,
            notified_count=0,
        )

    parse_failed: List[str] = []
    owner_to_eid: Dict[str, str] = {}
    for owner_str in counts:
        eid = parse_employee_id_from_owner(owner_str)
        if not eid:
            parse_failed.append(owner_str)
        else:
            owner_to_eid[owner_str] = eid

    skipped_parse = len(parse_failed)
    unique_eids = list({e for e in owner_to_eid.values()})
    domain_by_eid: Dict[str, str] = {}
    if unique_eids:
        stmt_um = select(UmsEmail.employee_id, UmsEmail.domain_account).where(
            UmsEmail.employee_id.in_(unique_eids)
        )
        rum = await db.execute(stmt_um)
        for eid_row, dom in rum.all():
            if dom is not None and str(dom).strip():
                domain_by_eid[str(eid_row)] = str(dom).strip()

    loop = asyncio.get_event_loop()
    notified = 0
    skipped_no_domain = 0
    failed_delivery = 0
    skipped_list: List[str] = []
    failed_list: List[BugNotifyFailedOwnerItem] = []

    for pf in parse_failed:
        if len(skipped_list) < DETAIL_CAP:
            skipped_list.append(pf)

    for owner_str, cnt in sorted(counts.items(), key=lambda x: x[0]):
        if owner_str in parse_failed:
            continue
        eid = owner_to_eid[owner_str]
        dom = domain_by_eid.get(eid)
        if not dom:
            skipped_no_domain += 1
            if len(skipped_list) < DETAIL_CAP:
                skipped_list.append(owner_str)
            continue

        remark = f"您好，在{batch}轮次，您名下共有{cnt}条用例失败，请及时分析处理"
        url = _build_history_url(public_base, batch, owner_str, bug_type)

        def _send(u: str = dom, c: str = TITLE, r: str = remark, lk: str = url):
            return rolling_welink_share(u, c, r, lk)

        ok, send_msg = await loop.run_in_executor(None, _send)
        if ok:
            notified += 1
        else:
            failed_delivery += 1
            logger.warning(
                "一键通知 WeLink 失败 owner=%s detail=%s",
                owner_str[:80],
                (send_msg or "")[:200],
            )
            if len(failed_list) < DETAIL_CAP:
                failed_list.append(
                    BugNotifyFailedOwnerItem(owner=owner_str, reason=send_msg or "发送失败")
                )

        await asyncio.sleep(WELINK_GAP_SEC)

    details: Optional[OneClickBugNotifyDetails] = None
    if skipped_list or failed_list:
        details = OneClickBugNotifyDetails(
            skipped_owners=skipped_list,
            failed_owners=failed_list,
        )

    msg_parts = [f"一键通知完成，成功通知 {notified} 人"]
    if skipped_parse:
        msg_parts.append(f"工号解析失败 {skipped_parse} 组")
    if skipped_no_domain:
        msg_parts.append(
            f"未配置域账号 {skipped_no_domain} 组（请在 ums_email 补全 domain_account）"
        )
    if failed_delivery:
        msg_parts.append(f"WeLink 发送失败 {failed_delivery} 组")

    logger.info(
        "一键通知结束 batch=%s notified=%s skipped_parse=%s skipped_no_domain=%s failed_delivery=%s operator=%s",
        batch,
        notified,
        skipped_parse,
        skipped_no_domain,
        failed_delivery,
        operator_employee_id,
    )

    return OneClickBugNotifyResponse(
        success=True,
        message="，".join(msg_parts),
        batch=batch,
        notified_count=notified,
        skipped_no_domain_count=skipped_no_domain,
        skipped_parse_owner_count=skipped_parse,
        failed_delivery_count=failed_delivery,
        details=details,
    )
