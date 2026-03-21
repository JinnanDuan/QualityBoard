# ============================================================
# 一键分析（整批 Bug）— 请求/响应 Schema
# 规约：spec/11_one_click_batch_analyze_spec.md
# ============================================================

from typing import Optional

from pydantic import BaseModel, Field


class OneClickAnalyzeRequest(BaseModel):
    """POST /api/v1/history/one-click-analyze 请求体"""

    anchor_history_id: int = Field(..., ge=1, description="锚点 pipeline_history.id")


class OneClickAnalyzeResponse(BaseModel):
    """一键分析响应"""

    success: bool = True
    message: str = ""
    batch: str = ""
    applied_count: int = 0
    skipped_no_owner_count: int = 0
    skipped_not_eligible_count: int = 0
