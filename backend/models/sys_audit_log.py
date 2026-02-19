from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class SysAuditLog(Base):
    __tablename__ = "sys_audit_log"
    __table_args__ = (
        Index("idx_sal_operator", "operator"),
        Index("idx_sal_action", "action"),
        Index("idx_sal_created_at", "created_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operator: Mapped[str] = mapped_column(String(50), nullable=False, comment="操作人工号")
    action: Mapped[str] = mapped_column(String(100), nullable=False, comment="操作类型")
    target_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="操作对象类型")
    target_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="操作对象ID")
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="操作详情（JSON）")
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="操作人IP")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
