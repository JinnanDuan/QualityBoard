from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class PipelineCases(Base):
    __tablename__ = "pipeline_cases"
    __table_args__ = (
        Index("idx_case_name", "case_name"),
        Index("idx_state", "state"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用例名称")
    case_level: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用例级别")
    case_type: Mapped[Optional[str]] = mapped_column(String(25), nullable=True, comment="用例类型")
    test_type: Mapped[Optional[str]] = mapped_column(String(25), nullable=True, comment="测试类型")
    is_online: Mapped[Optional[str]] = mapped_column(String(25), nullable=True, comment="是否在线运行")
    state: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, comment="用例当前状态")
    state_detail: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="状态详情/备注")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="平台名称")
    change_history: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="变更历史记录")
    recover_batch: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="恢复轮次")
    offline_reason_detail: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="下线原因详细说明")
    pkg_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="包类型")
    offline_reason_type: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="下线原因分类")
    offline_case_owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="下线用例责任人")
