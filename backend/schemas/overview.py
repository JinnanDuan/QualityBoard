from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator

from backend.schemas.common import PageRequest

OVERVIEW_RESULT_ALLOWED = frozenset({"passed", "failed"})


class OverviewItem(BaseModel):
    id: int
    batch: Optional[str] = None
    subtask: Optional[str] = None
    result: Optional[str] = None
    case_num: Optional[str] = None
    batch_start: Optional[datetime] = None
    batch_end: Optional[datetime] = None
    reports_url: Optional[str] = None
    log_url: Optional[str] = None
    screenshot_url: Optional[str] = None
    pipeline_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    passed_num: Optional[int] = None
    failed_num: Optional[int] = None
    platform: Optional[str] = None
    code_branch: Optional[str] = None

    model_config = {"from_attributes": True}


class OverviewQuery(PageRequest):
    batch: Optional[List[str]] = None
    subtask: Optional[List[str]] = None
    platform: Optional[List[str]] = None
    code_branch: Optional[List[str]] = None
    result: Optional[List[str]] = None
    sort_field: Optional[str] = None
    sort_order: Optional[str] = None
    all_batches: bool = False

    @field_validator("result", mode="before")
    @classmethod
    def validate_result_values(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if not v:
            return v
        for item in v:
            if item is not None and str(item) not in OVERVIEW_RESULT_ALLOWED:
                raise ValueError("result 仅允许 passed、failed")
        return v


class OverviewFilterOptions(BaseModel):
    batch: List[str] = []
    subtask: List[str] = []
    platform: List[str] = []
    code_branch: List[str] = []
    result: List[str] = ["passed", "failed"]
