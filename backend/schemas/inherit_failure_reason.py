# ============================================================
# Inherit Failure Reason Schema — 失败原因继承的请求/响应数据模型
# ============================================================

from typing import List, Literal, Optional

from pydantic import BaseModel, model_validator


class InheritFailureReasonRequest(BaseModel):
    """失败原因继承请求模型，POST /inherit-failure-reason 请求体"""

    inherit_mode: Literal["batch", "case"]
    source_batch: Optional[str] = None  # 批次维度时必填
    target_batch: Optional[str] = None  # 批次维度时必填
    source_pfr_id: Optional[int] = None  # 用例维度时必填，用户从筛选结果中选择的 pfr.id
    history_ids: Optional[List[int]] = None  # 用例维度时必填

    @model_validator(mode="after")
    def validate_mode(self) -> "InheritFailureReasonRequest":
        """根据 inherit_mode 校验必填字段"""
        if self.inherit_mode == "batch":
            if not self.source_batch or not str(self.source_batch).strip():
                raise ValueError("批次维度时源批次必填")
            if not self.target_batch or not str(self.target_batch).strip():
                raise ValueError("批次维度时目标批次必填")
            if self.source_batch == self.target_batch:
                raise ValueError("源批次不能与目标批次相同")
        elif self.inherit_mode == "case":
            if self.source_pfr_id is None:
                raise ValueError("用例维度时请先筛选并选择一条源记录")
            if not self.history_ids:
                raise ValueError("用例维度时勾选记录必填")
        return self


class InheritFailureReasonResponse(BaseModel):
    """失败原因继承响应模型"""

    success: bool = True
    inherited_count: int = 0
    skipped_count: int = 0
    message: str = ""


class InheritBatchOptionsResponse(BaseModel):
    """继承弹窗批次选项响应"""

    batches: List[str] = []


class InheritSourceOptionsResponse(BaseModel):
    """用例维度源选择三字段选项响应"""

    case_names: List[str] = []
    platforms: List[str] = []
    batches: List[str] = []


class InheritSourceRecordItem(BaseModel):
    """用例维度筛选后的单条源记录，供用户选择"""

    id: int  # pipeline_failure_reason.id
    case_name: Optional[str] = None
    platform: Optional[str] = None
    failed_batch: Optional[str] = None
    failed_type: Optional[str] = None
    owner: Optional[str] = None
    reason: Optional[str] = None

    model_config = {"from_attributes": True}


class InheritSourceRecordsResponse(BaseModel):
    """用例维度筛选后的源记录列表响应"""

    records: List[InheritSourceRecordItem] = []
