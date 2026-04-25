from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from backend.schemas.history import HistoryQuery


class HistorySearchTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    query_params: HistoryQuery = Field(..., description="与列表筛选一致的查询参数快照")


class HistorySearchTemplateItem(BaseModel):
    id: int
    name: str
    query_params: HistoryQuery
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
