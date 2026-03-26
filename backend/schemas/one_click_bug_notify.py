# ============================================================
# 一键通知（Bug 跟踪人 · WeLink）— 请求/响应 Schema
# 规约：spec/13_one_click_bug_notify_spec.md
# ============================================================

from typing import List, Optional

from pydantic import BaseModel, Field


class OneClickBugNotifyRequest(BaseModel):
    """POST /api/v1/history/one-click-bug-notify 请求体"""

    anchor_history_id: int = Field(..., ge=1, description="锚点 pipeline_history.id")
    selected_history_ids: Optional[List[int]] = Field(
        None, description="勾选行 id 列表，用于同批次校验"
    )


class BugNotifyFailedOwnerItem(BaseModel):
    owner: str = ""
    reason: str = ""


class OneClickBugNotifyDetails(BaseModel):
    """管理员排查用，条数截断"""

    skipped_owners: List[str] = Field(default_factory=list)
    failed_owners: List[BugNotifyFailedOwnerItem] = Field(default_factory=list)


class OneClickBugNotifyResponse(BaseModel):
    success: bool = True
    message: str = ""
    batch: str = ""
    notified_count: int = 0
    skipped_no_domain_count: int = 0
    skipped_parse_owner_count: int = 0
    failed_delivery_count: int = 0
    details: Optional[OneClickBugNotifyDetails] = None
