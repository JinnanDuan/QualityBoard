# ============================================================
# 轮次通报（一键生成报告）— Service
# ============================================================

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.pipeline_failure_reason import PipelineFailureReason as Pfr
from backend.models.pipeline_history import PipelineHistory as Ph
from backend.models.ums_email import UmsEmail
from backend.schemas.batch_report import (
    BatchReportModuleCount,
    BatchReportOwnerGroup,
    BatchReportPlatformGroup,
    BatchReportResponse,
)

logger = logging.getLogger(__name__)


async def get_batch_report(db: AsyncSession, start_time: str) -> BatchReportResponse:
    """
    按单一批次汇总：
    - 用例总数 / passed / failed+error / skip（pipeline_history）
    - 「怀疑修改引入」：pipeline_failure_reason.failed_type 大小写不敏感为 bug，
      与 pipeline_history 按 (case_name, start_time, platform) 关联，主模块取执行历史 main_module。
    """
    batch = (start_time or "").strip()
    if not batch:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_time 不能为空")

    # ----- 1) 结果分布（单表）-----
    sum_passed = func.sum(case((Ph.case_result == "passed", 1), else_=0))
    sum_failed = func.sum(
        case((Ph.case_result.in_(["failed", "error"]), 1), else_=0)
    )
    sum_skip = func.sum(case((Ph.case_result == "skip", 1), else_=0))

    agg_stmt = (
        select(
            func.count(Ph.id).label("total"),
            sum_passed.label("passed"),
            sum_failed.label("failed"),
            sum_skip.label("skip"),
        )
        .where(Ph.start_time == batch)
    )
    agg_row = (await db.execute(agg_stmt)).one()
    total = int(agg_row.total or 0)
    passed = int(agg_row.passed or 0)
    failed = int(agg_row.failed or 0)
    skip = int(agg_row.skip or 0)

    # ----- 2) bug 归因 × 主模块（单批次内数据量可控，使用 JOIN）-----
    bug_type = func.lower(func.trim(Pfr.failed_type))
    main_mod = func.coalesce(func.nullif(func.trim(Ph.main_module), ""), "")

    join_stmt = (
        select(
            Pfr.platform.label("platform"),
            Pfr.owner.label("owner"),
            main_mod.label("main_module"),
            func.count().label("cnt"),
        )
        .select_from(Pfr)
        .join(
            Ph,
            and_(
                Ph.case_name == Pfr.case_name,
                Ph.start_time == Pfr.failed_batch,
                Ph.platform == Pfr.platform,
            ),
        )
        .where(Pfr.failed_batch == batch)
        .where(bug_type == "bug")
        .group_by(Pfr.platform, Pfr.owner, main_mod)
    )

    join_result = await db.execute(join_stmt)
    raw_rows: List[Tuple[Optional[str], Optional[str], str, int]] = []
    for row in join_result.all():
        plat = row.platform
        owner_id = row.owner
        mm = row.main_module if row.main_module is not None else ""
        cnt = int(row.cnt or 0)
        raw_rows.append((plat, owner_id, mm, cnt))

    # 平台 → 工号 → 主模块 → 计数
    plat_owner_modules: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    employee_ids: set = set()
    for plat, owner_id, mm, cnt in raw_rows:
        if not plat or not str(plat).strip():
            continue
        pkey = str(plat).strip()
        eid = (owner_id or "").strip()
        if eid:
            employee_ids.add(eid)
        mkey = mm if mm else ""
        plat_owner_modules[pkey][eid][mkey] += cnt

    names_map: Dict[str, str] = {}
    if employee_ids:
        ums_stmt = select(UmsEmail.employee_id, UmsEmail.name).where(
            UmsEmail.employee_id.in_(list(employee_ids))
        )
        ums_res = await db.execute(ums_stmt)
        for eid, name in ums_res.all():
            if eid:
                names_map[str(eid)] = str(name) if name else ""

    platforms_out: List[BatchReportPlatformGroup] = []
    for platform in sorted(plat_owner_modules.keys()):
        owners_map = plat_owner_modules[platform]
        owner_groups: List[BatchReportOwnerGroup] = []
        for employee_id in sorted(owners_map.keys(), key=lambda x: x or ""):
            mod_map = owners_map[employee_id]
            modules_list: List[BatchReportModuleCount] = []
            total_cases = 0
            for mod_name in sorted(mod_map.keys()):
                c = mod_map[mod_name]
                if c <= 0:
                    continue
                total_cases += c
                display_mod = mod_name if mod_name else "（未填写）"
                modules_list.append(BatchReportModuleCount(main_module=display_mod, count=c))
            if total_cases <= 0:
                continue
            disp_name: Optional[str] = None
            if employee_id:
                disp_name = names_map.get(employee_id) or None
            owner_groups.append(
                BatchReportOwnerGroup(
                    employee_id=employee_id if employee_id else "（无）",
                    employee_name=disp_name,
                    case_count=total_cases,
                    modules=modules_list,
                )
            )
        if owner_groups:
            platforms_out.append(BatchReportPlatformGroup(platform=platform, owners=owner_groups))

    logger.info("轮次通报汇总成功 batch=%s total=%d platforms=%d", batch, total, len(platforms_out))

    return BatchReportResponse(
        start_time=batch,
        total=total,
        passed=passed,
        failed=failed,
        skip=skip,
        platforms=platforms_out,
    )
