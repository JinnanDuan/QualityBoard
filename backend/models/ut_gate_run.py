from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class UtGateRun(Base):
    """Jenkins UT 门禁上报记录，与 database/V1.1.2__create_ut_gate_run.sql 一致。"""

    __tablename__ = "ut_gate_run"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uk_idempotency"),
        Index("idx_created_at", "created_at"),
        Index("idx_mr_url_created", "mr_url", "created_at", mysql_length={"mr_url": 191}),
        Index("idx_is_intercepted_created", "is_intercepted", "created_at"),
        Index("idx_job_build", "job_name", "build_number"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="主键")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment="记录创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
        comment="更新时间",
    )
    reported_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment="门禁结束上报时间"
    )
    jenkins_base_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="Jenkins 根 URL")
    job_name: Mapped[str] = mapped_column(String(256), nullable=False, comment="Job 名称")
    build_number: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, comment="构建号")
    build_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True, comment="本次构建页 URL")
    mr_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True, comment="MR 页面完整 URL")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="幂等键")
    is_intercepted: Mapped[bool] = mapped_column(Boolean, nullable=False, comment="是否拦截到失败用例")
    ut_exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="cargo make test 退出码")
