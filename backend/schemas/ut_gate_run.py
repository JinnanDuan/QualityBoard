from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UtGateRunCreate(BaseModel):
    """POST /api/v1/ut-gate-runs 请求体；未知字段忽略（spec/16 §4.1）。"""

    model_config = ConfigDict(extra="ignore")

    idempotency_key: str = Field(..., min_length=1, max_length=128)
    job_name: str = Field(..., min_length=1, max_length=256)
    build_number: int = Field(...)
    is_intercepted: bool
    ut_exit_code: Optional[int] = None
    build_url: Optional[str] = Field(None, max_length=1024)
    jenkins_base_url: Optional[str] = Field(None, max_length=512)
    mr_url: Optional[str] = Field(None, max_length=1024)

    @field_validator("idempotency_key", "job_name")
    @classmethod
    def strip_required_strings(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("不能为空或仅空白")
        return s

    @field_validator("build_url", "jenkins_base_url", "mr_url", mode="before")
    @classmethod
    def strip_optional_urls(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str):
            return v
        s = v.strip()
        return s if s else None

    @field_validator("build_number")
    @classmethod
    def build_number_unsigned_int(cls, v: int) -> int:
        if v < 0 or v > 4294967295:
            raise ValueError("build_number 须在 0～4294967295（INT UNSIGNED）范围内")
        return v


class UtGateRunItem(BaseModel):
    """单条 ut_gate_run 响应，与表字段一致（spec/16 §6）。"""

    id: int
    created_at: datetime
    updated_at: datetime
    reported_at: datetime
    jenkins_base_url: Optional[str] = None
    job_name: str
    build_number: int
    build_url: Optional[str] = None
    mr_url: Optional[str] = None
    idempotency_key: str
    is_intercepted: bool
    ut_exit_code: Optional[int] = None

    model_config = {"from_attributes": True}
