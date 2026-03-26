# ============================================================
# 失败类型字典辅助 — 与 case_failed_type 表一致
# ============================================================

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.case_failed_type import CaseFailedType


async def get_bug_failed_type_value(db: AsyncSession) -> Optional[str]:
    """返回 case_failed_type 中代表 bug 的 failed_reason_type 原值（库内大小写保留）。"""
    stmt = (
        select(CaseFailedType.failed_reason_type)
        .where(func.lower(func.trim(CaseFailedType.failed_reason_type)) == "bug")
        .limit(1)
    )
    r = await db.execute(stmt)
    return r.scalars().first()
