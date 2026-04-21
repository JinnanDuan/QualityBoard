import json
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.sys_audit_log import SysAuditLog


async def write_audit_log(
    db: AsyncSession,
    *,
    operator: str,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    """写入审计日志到 sys_audit_log 表。"""
    row = SysAuditLog(
        operator=(operator or "").strip() or "unknown",
        action=(action or "").strip() or "unknown",
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        ip_address=ip_address,
    )
    db.add(row)
    await db.flush()


def build_audit_detail(payload: Dict[str, Any]) -> str:
    """将审计详情序列化为 JSON 字符串。"""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
