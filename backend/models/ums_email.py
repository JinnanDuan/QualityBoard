from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class UmsEmail(Base):
    __tablename__ = "ums_email"
    __table_args__ = (
        Index("idx_name", "name"),
        {"extend_existing": True},
    )

    employee_id: Mapped[str] = mapped_column(String(20), primary_key=True, comment="工号")
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="姓名")
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, comment="邮箱")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    domain_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default="", comment="域账号")
