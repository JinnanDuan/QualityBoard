# ============================================================
# 跟踪人 owner 展示串解析（与 pipeline_failure_reason.owner 约定一致）
# ============================================================

from typing import Optional


def parse_employee_id_from_owner(owner: str) -> Optional[str]:
    """取 owner 最后一个半角空格之后的子串作为工号；无半角空格则无法解析。"""
    if not owner or not str(owner).strip():
        return None
    s = str(owner).strip()
    if " " not in s:
        return None
    part = s.rsplit(" ", 1)[-1].strip()
    return part if part else None
