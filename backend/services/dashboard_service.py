# ============================================================
# Dashboard Service — 首页看板业务逻辑层
# ============================================================
# 提供最新批次状态、批次趋势数据的聚合查询。
# ============================================================

import logging
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.schemas.dashboard import BatchTrendItem, LatestBatchItem

logger = logging.getLogger(__name__)


async def get_latest_batch(db: AsyncSession) -> Optional[LatestBatchItem]:
    """
    查询最新已执行完批次的聚合数据。
    仅查 batch_end IS NOT NULL，按 MAX(batch_end) 降序取最新批次。
    """
    stmt = text("""
        SELECT
            po.batch,
            SUM(CAST(COALESCE(po.case_num, '0') AS SIGNED)) AS total_case_num,
            SUM(COALESCE(po.passed_num, 0)) AS passed_num,
            SUM(COALESCE(po.failed_num, 0)) AS failed_num,
            MIN(po.batch_start) AS batch_start,
            MAX(po.batch_end) AS batch_end
        FROM pipeline_overview po
        WHERE po.batch_end IS NOT NULL
          AND po.batch = (
            SELECT batch FROM (
                SELECT batch, MAX(batch_end) AS max_end
                FROM pipeline_overview
                WHERE batch_end IS NOT NULL
                GROUP BY batch
                ORDER BY max_end DESC
                LIMIT 1
            ) t
          )
        GROUP BY po.batch
    """)
    db_result = await db.execute(stmt)
    row = db_result.fetchone()
    if not row:
        return None

    batch, total_case_num, passed_num, failed_num, batch_start, batch_end = row
    total_case_num = total_case_num or 0
    passed_num = passed_num or 0
    failed_num = failed_num or 0

    pass_rate = (passed_num / total_case_num * 100) if total_case_num > 0 else 0.0
    result_status = "failed" if failed_num > 0 else "passed"

    return LatestBatchItem(
        batch=batch or "",
        total_case_num=total_case_num,
        passed_num=passed_num,
        failed_num=failed_num,
        pass_rate=round(pass_rate, 2),
        batch_start=batch_start.isoformat() if batch_start else None,
        batch_end=batch_end.isoformat() if batch_end else None,
        result=result_status,
    )


def _code_branch_condition(prefix: str, is_master: bool) -> str:
    """返回 code_branch 过滤条件，prefix 为表别名如 'po.' 或 ''。"""
    col = f"TRIM(COALESCE({prefix}code_branch, ''))"
    return f"{col} = 'master'" if is_master else f"{col} != 'master'"


async def get_batch_trend(
    db: AsyncSession, limit: int = 30, code_branch: str = "master"
) -> List[BatchTrendItem]:
    """
    查询最近 N 个已执行完批次的聚合数据，按 code_branch 过滤，按 batch_start 升序返回。
    code_branch: master 或 bugfix。
    """
    limit = max(1, min(50, limit))
    is_master = code_branch == "master"
    cb_po = _code_branch_condition("po.", is_master)
    cb_sub = _code_branch_condition("", is_master)

    stmt = text(f"""
        SELECT
            po.batch,
            SUM(CAST(COALESCE(po.case_num, '0') AS SIGNED)) AS total_case_num,
            SUM(COALESCE(po.passed_num, 0)) AS passed_num,
            SUM(COALESCE(po.failed_num, 0)) AS failed_num,
            MIN(po.batch_start) AS batch_start,
            MAX(po.batch_end) AS batch_end
        FROM pipeline_overview po
        WHERE po.batch_end IS NOT NULL
          AND {cb_po}
          AND po.batch IN (
            SELECT batch FROM (
                SELECT batch, MAX(batch_start) AS ms
                FROM pipeline_overview
                WHERE batch_end IS NOT NULL AND {cb_sub}
                GROUP BY batch
                ORDER BY ms DESC
                LIMIT :limit
            ) t
          )
        GROUP BY po.batch
        ORDER BY MIN(po.batch_start) ASC
    """)
    db_result = await db.execute(stmt, {"limit": limit})
    rows = db_result.fetchall()

    items = []
    for row in rows:
        batch, total_case_num, passed_num, failed_num, batch_start, batch_end = row
        total_case_num = total_case_num or 0
        passed_num = passed_num or 0
        failed_num = failed_num or 0
        pass_rate = (passed_num / total_case_num * 100) if total_case_num > 0 else 0.0

        items.append(
            BatchTrendItem(
                batch=batch or "",
                total_case_num=total_case_num,
                passed_num=passed_num,
                failed_num=failed_num,
                pass_rate=round(pass_rate, 2),
                batch_start=batch_start.isoformat() if batch_start else None,
            )
        )

    return items
