# ============================================================
# OH 平台日报数据导出 — Schema
# ============================================================

from typing import List

from pydantic import BaseModel, Field


class OhDailyExportResponse(BaseModel):
    """GET /history/oh-daily-export 响应；export_text 布局见 `backend.constants.oh_daily_export_table`。"""

    model_config = {"from_attributes": True}

    start_time: str = Field(..., description="轮次（批次）")
    platform_filter: List[str] = Field(
        ...,
        description="参与统计的 pipeline_history.platform 取值（白名单）",
    )
    export_text: str = Field(..., description="制表符分隔文本，可直接粘贴到 Excel")
