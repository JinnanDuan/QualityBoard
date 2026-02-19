from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class CaseFailedType(Base):
    """注意：此表时间字段为 created_time/updated_time，与其他表不同。"""

    __tablename__ = "case_failed_type"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    failed_reason_type: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, comment="失败原因分类")
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="该失败类型的默认跟踪人")
    creator: Mapped[str] = mapped_column(String(255), nullable=False, comment="创建者")
    updater: Mapped[str] = mapped_column(String(255), nullable=False, comment="更新者")
    created_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    updated_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
