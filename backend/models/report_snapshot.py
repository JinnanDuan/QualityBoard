from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class ReportSnapshot(Base):
    __tablename__ = "report_snapshot"
    __table_args__ = (
        Index("idx_rs_batch", "batch"),
        Index("idx_rs_created_at", "created_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch: Mapped[str] = mapped_column(String(100), nullable=False, comment="轮次")
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="报告标题")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="报告内容（JSON快照）")
    creator: Mapped[str] = mapped_column(String(50), nullable=False, comment="创建人工号")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
