# ============================================================
# Dashboard Service — 首页看板业务逻辑层
# ============================================================
# 提供最新批次状态、批次趋势数据的聚合查询。
# ============================================================

import logging
import re
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import dashboard_defaults as dash_defaults
from backend.schemas.dashboard import BatchTrendItem, LatestBatchItem

logger = logging.getLogger(__name__)

_PREFIX_OK = re.compile(r"^[0-9A-Za-z._-]{1,64}$")


def _sanitized_batch_prefixes() -> Tuple[str, ...]:
    """从代码内配置解析出有效批次前缀；无效项打 WARNING。"""
    if not dash_defaults.DASHBOARD_BATCH_PREFIX_FILTER_ENABLED:
        return tuple()
    out: List[str] = []
    for p in dash_defaults.DASHBOARD_BATCH_PREFIXES:
        s = p.strip()
        if s and _PREFIX_OK.match(s):
            out.append(s)
        elif s:
            logger.warning(
                "忽略非法批次前缀（仅允许 1～64 位数字、字母与 ._-）: %s",
                s[:80],
            )
    if (
        dash_defaults.DASHBOARD_BATCH_PREFIX_FILTER_ENABLED
        and not out
        and dash_defaults.DASHBOARD_BATCH_PREFIXES
    ):
        logger.warning(
            "批次前缀过滤已开启但无有效前缀，本请求将不附加批次前缀条件",
        )
    return tuple(out)


def _batch_prefix_sql_and_params(table_prefix: str) -> Tuple[str, Dict[str, str]]:
    """
    生成 AND (batch LIKE ...) 片段与绑定参数。
    table_prefix 为 'po.' 或 ''（子查询无别名时用 ''）。
    """
    prefixes = _sanitized_batch_prefixes()
    if not prefixes:
        return "", {}
    col = f"TRIM(COALESCE({table_prefix}batch, ''))"
    parts = []
    params: Dict[str, str] = {}
    for i, p in enumerate(prefixes):
        key = f"dash_bp_{i}"
        parts.append(f"{col} LIKE :{key}")
        params[key] = f"{p}%"
    return " AND (" + " OR ".join(parts) + ")", params


async def get_latest_batch(db: AsyncSession) -> Optional[LatestBatchItem]:
    """
    查询最新已执行完批次的聚合数据。
    仅查 batch_end IS NOT NULL，按 MAX(batch_end) 降序取最新批次。
    若启用批次前缀过滤（见 dashboard_defaults），仅在前缀匹配的轮次中取最新。
    """
    b_outer, bp_params = _batch_prefix_sql_and_params("po.")
    b_inner, _ = _batch_prefix_sql_and_params("")
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
          {b_outer}
          AND po.batch = (
            SELECT batch FROM (
                SELECT batch, MAX(batch_end) AS max_end
                FROM pipeline_overview
                WHERE batch_end IS NOT NULL
                  {b_inner}
                GROUP BY batch
                ORDER BY max_end DESC
                LIMIT 1
            ) t
          )
        GROUP BY po.batch
    """)
    db_result = await db.execute(stmt, bp_params)
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
    若启用批次前缀过滤（见 dashboard_defaults），仅统计 pipeline_overview.batch 匹配前缀的轮次。
    """
    limit = max(1, min(50, limit))
    is_master = code_branch == "master"
    cb_po = _code_branch_condition("po.", is_master)
    cb_sub = _code_branch_condition("", is_master)
    b_po, bp_params = _batch_prefix_sql_and_params("po.")
    b_sub, _ = _batch_prefix_sql_and_params("")

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
          {b_po}
          AND po.batch IN (
            SELECT batch FROM (
                SELECT batch, MAX(batch_start) AS ms
                FROM pipeline_overview
                WHERE batch_end IS NOT NULL AND {cb_sub}
                  {b_sub}
                GROUP BY batch
                ORDER BY ms DESC
                LIMIT :limit
            ) t
          )
        GROUP BY po.batch
        ORDER BY MIN(po.batch_start) ASC
    """)
    params = {"limit": limit}
    params.update(bp_params)
    db_result = await db.execute(stmt, params)
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
