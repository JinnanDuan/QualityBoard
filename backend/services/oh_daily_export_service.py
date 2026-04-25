# ============================================================
# OH 平台日报数据导出 — Service
# ============================================================

import logging
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.constants.oh_daily_export_table import (
    OH_DAILY_EXPORT_HEADER_ROW,
    OH_DAILY_EXPORT_ROWS,
)
from backend.models.pipeline_history import PipelineHistory as Ph
from backend.schemas.oh_daily_export import OhDailyExportResponse

logger = logging.getLogger(__name__)

# 与线上一致时可扩展；精确匹配禁止模糊 LIKE，以免误计其它平台
OH_PLATFORMS: Tuple[str, ...] = ("oh",)


def _non_empty_case_name_condition():
    """排除 NULL 与仅空白用例名。"""
    return and_(Ph.case_name.isnot(None), func.length(func.trim(Ph.case_name)) > 0)


def _inner_category_case_flags(batch: str, modules: Tuple[str, ...]):
    """
    单分类、单批次、OH 平台下按 case_name 聚合后的子查询列：
    has_fail=1 表示该用例在本批次任一条 failed/error；has_pass=1 表示任一条 passed。
    """
    has_fail = func.max(
        case((Ph.case_result.in_(["failed", "error"]), 1), else_=0)
    ).label("has_fail")
    has_pass = func.max(case((Ph.case_result == "passed", 1), else_=0)).label("has_pass")
    return (
        select(Ph.case_name.label("case_name"), has_fail, has_pass)
        .where(
            Ph.start_time == batch,
            Ph.platform.in_(list(OH_PLATFORMS)),
            Ph.main_module.in_(list(modules)),
            _non_empty_case_name_condition(),
        )
        .group_by(Ph.case_name)
        .subquery()
    )


def _outcome_from_flags(has_fail: int, has_pass: int) -> str:
    if int(has_fail or 0) == 1:
        return "fail"
    if int(has_fail or 0) == 0 and int(has_pass or 0) == 1:
        return "success"
    return "other"


async def _aggregate_category(
    db: AsyncSession,
    batch: str,
    modules: Tuple[str, ...],
) -> Tuple[int, int, int]:
    """
    单分类、单批次、OH 白名单平台下：
    按 case_name 聚合：任一条 failed/error 则该用例计为 fail；否则若存在 passed 则计 success；其余计 other。
    返回 (total, success, fail)。
    """
    inner = _inner_category_case_flags(batch, modules)

    n_total = func.count().label("n_total")
    n_success = func.coalesce(
        func.sum(
            case(
                (and_(inner.c.has_fail == 0, inner.c.has_pass == 1), 1),
                else_=0,
            )
        ),
        0,
    ).label("n_success")
    n_fail = func.coalesce(
        func.sum(case((inner.c.has_fail == 1, 1), else_=0)),
        0,
    ).label("n_fail")

    stmt = select(n_total, n_success, n_fail).select_from(inner)
    row = (await db.execute(stmt)).one()
    return int(row.n_total or 0), int(row.n_success or 0), int(row.n_fail or 0)


async def _case_outcomes_for_category(
    db: AsyncSession,
    batch: str,
    modules: Tuple[str, ...],
) -> Dict[str, str]:
    """case_name -> 'success' | 'fail' | 'other'，与 _aggregate_category 口径一致。"""
    inner = _inner_category_case_flags(batch, modules)
    stmt = select(inner.c.case_name, inner.c.has_fail, inner.c.has_pass).select_from(inner)
    result = await db.execute(stmt)
    out: Dict[str, str] = {}
    for cn, hf, hp in result.all():
        if cn is None:
            continue
        key = str(cn).strip()
        if not key:
            continue
        out[key] = _outcome_from_flags(int(hf or 0), int(hp or 0))
    return out


async def _previous_batch_strictly_before(
    db: AsyncSession,
    batch_a: str,
) -> Optional[str]:
    """
    在 pipeline_history 中出现过的批次里，取严格小于 batch_a 的最大 start_time 作为上一批 B。
    与字符串/字典序一致；若不存在更小的批次则返回 None。
    """
    stmt = (
        select(func.max(Ph.start_time))
        .where(
            Ph.start_time.isnot(None),
            func.length(func.trim(Ph.start_time)) > 0,
            Ph.start_time < batch_a,
        )
    )
    val = (await db.execute(stmt)).scalar_one_or_none()
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


async def _new_fail_for_category(
    db: AsyncSession,
    batch_a: str,
    batch_b: Optional[str],
    modules: Tuple[str, ...],
) -> int:
    """
    NewFail：批次 B 中 success，批次 A 中 fail 的用例数（同一 case_name，同一分类与 OH 平台口径）。
    无上一批 B 时为 0。
    """
    if not batch_b:
        return 0
    out_a = await _case_outcomes_for_category(db, batch_a, modules)
    out_b = await _case_outcomes_for_category(db, batch_b, modules)
    n = 0
    for cn, st_a in out_a.items():
        if st_a != "fail":
            continue
        if out_b.get(cn) == "success":
            n += 1
    return n


def _build_tsv_lines(rows_data: List[Tuple[str, int, int, int, int, str]]) -> str:
    """
    rows_data: (label, total, success, fail, new_fail, pass_rate_display)
    表头与行序见 backend.constants.oh_daily_export_table。
    """
    lines: List[str] = []
    lines.append("\t".join(OH_DAILY_EXPORT_HEADER_ROW))
    for label, total, success, fail, new_fail, rate_str in rows_data:
        lines.append(
            f"{label}\t{total}\t{success}\t{fail}\t{new_fail}\t{rate_str}"
        )
    return "\n".join(lines)


async def get_oh_daily_export(db: AsyncSession, start_time: str) -> OhDailyExportResponse:
    batch = (start_time or "").strip()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time 不能为空",
        )

    batch_prev = await _previous_batch_strictly_before(db, batch)

    rows_for_tsv: List[Tuple[str, int, int, int, int, str]] = []
    summary_log: List[str] = []

    for label, modules in OH_DAILY_EXPORT_ROWS:
        total, success, fail = await _aggregate_category(db, batch, modules)
        new_fail = await _new_fail_for_category(db, batch, batch_prev, modules)
        if total > 0:
            rate_str = f"{(success / total * 100):.2f}%"
        else:
            rate_str = "0%"
        rows_for_tsv.append((label, total, success, fail, new_fail, rate_str))
        summary_log.append(f"{label}={total}/{success}/{fail}/nf={new_fail}")

    export_text = _build_tsv_lines(rows_for_tsv)

    logger.info(
        "OH 日报导出成功 batch=%s prev_batch=%s platforms=%s %s",
        batch,
        batch_prev or "",
        ",".join(OH_PLATFORMS),
        " ".join(summary_log),
    )

    return OhDailyExportResponse(
        start_time=batch,
        platform_filter=list(OH_PLATFORMS),
        export_text=export_text,
    )
