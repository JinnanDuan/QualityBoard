from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class CaseOfflineType(Base):
    __tablename__ = "case_offline_type"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    offline_reason_type: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, comment="用例下线原因分类")
