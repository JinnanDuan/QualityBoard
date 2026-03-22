# ============================================================
# 用例开发责任人 — main_module → ums_module_owner / ums_email
# 供 list_history、一键分析等复用。
# ============================================================

from typing import Dict, Optional, Set

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.pipeline_history import PipelineHistory
from backend.models.ums_email import UmsEmail
from backend.models.ums_module_owner import UmsModuleOwner


def format_case_dev_owner_display(
    name: Optional[str],
    employee_id: Optional[str],
) -> Optional[str]:
    """用例开发责任人展示：姓名 + 空格 + 工号（姓名优先用 for_reference，可来自 ums_email.name）。"""
    n = (name or "").strip()
    eid = (employee_id or "").strip()
    if n and eid:
        return f"{n} {eid}"
    if eid:
        return eid
    if n:
        return n
    return None


async def build_module_to_case_dev_owner_display(
    db: AsyncSession, modules: Set[str]
) -> Dict[str, Optional[str]]:
    """
    批量解析 main_module（与 ums_module_owner.module 对应）→ 展示串。
    匹配规则：**按小写比较**（`LOWER(main_module)` = `LOWER(ums_module_owner.module)`），避免流水线写入大小写不一致导致查不到负责人。
    无匹配或无法解析时该 module 对应值为 None。
    """
    if not modules:
        return {}

    modules_lower = {m.lower() for m in modules if m}
    if not modules_lower:
        return {}

    umo_stmt = select(UmsModuleOwner).where(
        func.lower(UmsModuleOwner.module).in_(modules_lower)
    )
    umo_result = await db.execute(umo_stmt)
    # 小写 module → ORM（若库中仅一行 LOG，则仅 'log' 一条键）
    umo_by_lower: Dict[str, UmsModuleOwner] = {}
    for umo in umo_result.scalars().all():
        key = (umo.module or "").lower()
        if key and key not in umo_by_lower:
            umo_by_lower[key] = umo

    need_email_ids: list = []
    for m in modules:
        umo = umo_by_lower.get(m.lower()) if m else None
        if not umo:
            continue
        ref = (umo.for_reference or "").strip()
        if not ref:
            oid = (umo.owner or "").strip()
            if oid:
                need_email_ids.append(oid)

    email_name_by_id: Dict[str, str] = {}
    if need_email_ids:
        uniq_ids = list(dict.fromkeys(need_email_ids))
        em_stmt = select(UmsEmail.employee_id, UmsEmail.name).where(
            UmsEmail.employee_id.in_(uniq_ids)
        )
        em_result = await db.execute(em_stmt)
        for eid, ename in em_result.all():
            if eid:
                email_name_by_id[str(eid)] = (ename or "").strip()

    out: Dict[str, Optional[str]] = {}
    for m in modules:
        umo = umo_by_lower.get(m.lower()) if m else None
        if not umo:
            out[m] = None
            continue
        name = (umo.for_reference or "").strip()
        if not name:
            oid = (umo.owner or "").strip()
            name = email_name_by_id.get(oid, "") if oid else ""
        out[m] = format_case_dev_owner_display(name or None, umo.owner)
    return out


def case_dev_owner_display_for_row(
    row: PipelineHistory,
    module_to_display: Dict[str, Optional[str]],
) -> Optional[str]:
    """根据 pipeline_history 行与 module→展示串映射，返回该行用例开发责任人展示串。"""
    mm = (row.main_module or "").strip()
    if not mm:
        return None
    return module_to_display.get(mm)
