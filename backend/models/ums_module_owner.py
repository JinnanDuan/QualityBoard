from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class UmsModuleOwner(Base):
    __tablename__ = "ums_module_owner"
    __table_args__ = (
        Index("owner", "owner"),
        {"extend_existing": True},
    )

    module: Mapped[str] = mapped_column(String(40), primary_key=True, comment="测试用例主模块")
    owner: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("ums_email.employee_id", onupdate="CASCADE"),
        nullable=False,
        comment="负责人工号",
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    for_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="负责人姓名（辅助）")
