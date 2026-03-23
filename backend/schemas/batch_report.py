# ============================================================
# 轮次通报（一键生成报告）— Schema
# ============================================================

from typing import List, Optional

from pydantic import BaseModel, Field


class BatchReportModuleCount(BaseModel):
    """某跟踪人在某平台下，按主模块统计的 bug 失败用例数。"""

    main_module: str = Field(..., description="执行历史主模块，空时前端展示为（未填写）")
    count: int = Field(..., ge=0)


class BatchReportOwnerGroup(BaseModel):
    """某平台下一名失败跟踪人的模块分布。"""

    employee_id: str = Field(..., description="跟踪人工号，对应 pipeline_failure_reason.owner")
    employee_name: Optional[str] = Field(None, description="姓名，来自 ums_email；未登记则为 None")
    case_count: int = Field(..., ge=0, description="该平台下该跟踪人 bug 用例总数（【N条】）")
    modules: List[BatchReportModuleCount] = Field(default_factory=list)


class BatchReportPlatformGroup(BaseModel):
    """某平台下「怀疑修改引入」汇总（仅 failed_type 为 bug 的记录）。"""

    platform: str = Field(..., description="平台原始值")
    owners: List[BatchReportOwnerGroup] = Field(default_factory=list)


class BatchReportResponse(BaseModel):
    """GET /history/batch-report 响应。"""

    model_config = {"from_attributes": True}

    start_time: str = Field(..., description="轮次（批次）")
    total: int = Field(..., ge=0)
    passed: int = Field(..., ge=0)
    failed: int = Field(..., ge=0, description="failed + error")
    skip: int = Field(..., ge=0)
    platforms: List[BatchReportPlatformGroup] = Field(
        default_factory=list,
        description="仅包含存在 bug 类失败原因的平台；无则空列表",
    )
