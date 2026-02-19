from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class PipelineFailureReason(Base):
    __tablename__ = "pipeline_failure_reason"
    __table_args__ = (
        Index("idx_pfr_failedbatch_case", "failed_batch", "case_name"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用例名称")
    failed_batch: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="失败轮次")
    owner: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="失败用例跟踪人")
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="详细失败原因")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    failed_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="失败原因分类")
    recover_batch: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="恢复轮次")
    platform: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用例平台")
    analyzer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="失败原因分析人")
    dts_num: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="dts单号")
