from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class PipelineOverview(Base):
    __tablename__ = "pipeline_overview"
    __table_args__ = (
        Index("idx_batch_subtask", "batch", "subtask"),
        Index("idx_subtask", "subtask"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="轮次")
    subtask: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="组别")
    result: Mapped[Optional[str]] = mapped_column(String(25), nullable=True, comment="本轮该组执行结果")
    case_num: Mapped[Optional[str]] = mapped_column(String(25), nullable=True, comment="本轮该组执行的所有用例数量")
    batch_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="本轮该组开始执行时间")
    batch_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="本轮该组执行结束时间")
    reports_url: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, comment="测试报告URL")
    log_url: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, comment="日志URL")
    screenshot_url: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, comment="截图URL")
    pipeline_url: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, comment="Jenkins流水线URL")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    passed_num: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="本轮该组所有执行通过的用例数量")
    failed_num: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="本轮该组所有未执行通过的用例数量")
    platform: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="平台名称")
    code_branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="本轮执行时使用的IDE代码分支")
