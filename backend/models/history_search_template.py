from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class HistorySearchTemplate(Base):
    __tablename__ = "history_search_template"
    __table_args__ = (
        UniqueConstraint("employee_id", "name", name="uk_hst_employee_name"),
        Index("idx_hst_employee_id", "employee_id"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("ums_email.employee_id", name="fk_hst_employee"),
        nullable=False,
        comment="工号",
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="模板名称")
    query_json: Mapped[str] = mapped_column(Text, nullable=False, comment="筛选条件 JSON")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="创建时间",
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
        comment="更新时间",
    )
