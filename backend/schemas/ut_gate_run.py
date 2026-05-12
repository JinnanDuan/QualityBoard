from datetime import datetime, time, timezone
import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.schemas.common import PageRequest


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


_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_date_only_string(s: str) -> bool:
    return bool(_DATE_ONLY_RE.match(s.strip()))


class UtGateRunQuery(PageRequest):
    """GET /api/v1/ut-gate-runs 查询参数（spec/17）。"""

    model_config = ConfigDict(extra="ignore")

    page_size: int = Field(20, ge=1, le=100, description="每页条数，最大 100")
    start_time: Optional[str] = Field(
        None,
        description="reported_at 下限（闭区间）；YYYY-MM-DD 或 ISO8601，须与 end_time 同为日期或同为带时间格式",
    )
    end_time: Optional[str] = Field(
        None,
        description="reported_at 上限（闭区间）；YYYY-MM-DD 或 ISO8601",
    )
    is_intercepted: Optional[bool] = Field(None, description="是否拦截到（true/false）；省略则不过滤")
    mr_url: Optional[str] = Field(None, max_length=1024, description="mr_url 精确匹配（与 mr_url_contains 互斥）")
    mr_url_contains: Optional[str] = Field(None, max_length=200, description="mr_url 子串匹配（LIKE 转义）")
    job_name_contains: Optional[str] = Field(None, max_length=200, description="job_name 子串匹配（LIKE 转义）")
    sort_field: Optional[str] = Field(
        None,
        description="排序列：reported_at（默认）、created_at、id",
    )
    sort_order: Optional[str] = Field(None, description="asc / desc，默认 desc")

    parsed_reported_at_start: Optional[datetime] = Field(default=None, exclude=True)
    parsed_reported_at_end: Optional[datetime] = Field(default=None, exclude=True)

    @field_validator("mr_url", "mr_url_contains", "job_name_contains", mode="before")
    @classmethod
    def strip_optional_query_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str):
            return v
        s = v.strip()
        return s if s else None

    @model_validator(mode="after")
    def validate_mr_mutual_and_times_and_sort(self) -> "UtGateRunQuery":
        mu = self.mr_url
        mc = self.mr_url_contains
        if (mu or "").strip() and (mc or "").strip():
            raise ValueError("mr_url 与 mr_url_contains 互斥，不能同时指定")

        st_raw = self.start_time
        en_raw = self.end_time
        if (st_raw or "").strip() and (en_raw or "").strip():
            if _is_date_only_string(st_raw) != _is_date_only_string(en_raw):
                raise ValueError("start_time 与 end_time 须同为 YYYY-MM-DD 日期或同为带时间的 ISO8601")

        def _parse_one(raw: Optional[str], *, is_end: bool) -> Optional[datetime]:
            if raw is None or not str(raw).strip():
                return None
            s = str(raw).strip()
            if _is_date_only_string(s):
                d = datetime.strptime(s, "%Y-%m-%d").date()
                if is_end:
                    return datetime.combine(d, time(23, 59, 59))
                return datetime.combine(d, time.min)
            iso = s.replace("Z", "+00:00") if s.endswith("Z") else s
            try:
                dt = datetime.fromisoformat(iso)
            except ValueError as e:
                raise ValueError("时间格式无效，请使用 YYYY-MM-DD 或 ISO8601") from e
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt

        ps = _parse_one(st_raw, is_end=False)
        pe = _parse_one(en_raw, is_end=True)
        if ps is not None and pe is not None and ps > pe:
            raise ValueError("start_time 不能晚于 end_time")

        sf = (self.sort_field or "").strip() or None
        if sf is not None and sf not in ("reported_at", "created_at", "id"):
            raise ValueError("sort_field 仅支持 reported_at、created_at、id")
        so = (self.sort_order or "").strip().lower() or "desc"
        if so not in ("asc", "desc"):
            raise ValueError("sort_order 仅支持 asc 或 desc")

        object.__setattr__(self, "parsed_reported_at_start", ps)
        object.__setattr__(self, "parsed_reported_at_end", pe)
        return self
