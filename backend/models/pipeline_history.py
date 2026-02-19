from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class PipelineHistory(Base):
    __tablename__ = "pipeline_history"
    __table_args__ = (
        Index("idx_timentask", "start_time", "subtask"),
        Index("idx_main_module", "main_module"),
        Index("idx_start_time_case", "start_time", "case_name"),
        Index("idx_casename_platform_batch", "case_name", "platform", "start_time"),
        Index("idx_created_at_desc", "created_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    start_time: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="轮次（等同于batch）")
    subtask: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="组别")
    reports_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="测试报告的URL")
    log_url: Mapped[str] = mapped_column(String(250), nullable=False, comment="日志URL")
    screenshot_url: Mapped[str] = mapped_column(String(250), nullable=False, comment="截图URL")
    module: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, comment="测试用例代码中标记的模块名")
    case_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用例名称")
    case_result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="本轮执行结果")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    pipeline_url: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="Jenkins流水线URL")
    case_level: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="用例级别")
    main_module: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="测试用例主模块")
    owner_history: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用例责任人变更记录")
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用例责任人（开发）")
    platform: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="平台名称")
    code_branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="本轮执行时使用的IDE代码分支")
    analyzed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0, comment="是否给失败用例分配了失败原因（1=是，0=否）")
