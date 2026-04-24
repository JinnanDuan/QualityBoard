from typing import Literal, Optional

from pydantic import BaseModel, Field


class ApplyFailureReasonRequest(BaseModel):
    history_id: int = Field(..., ge=1, description="执行历史 ID")
    failure_category: str = Field(..., min_length=1, max_length=255, description="A3 输出的失败分类")
    detailed_reason: str = Field(..., min_length=1, max_length=2000, description="A3 输出的详细原因")
    session_id: Optional[str] = Field(None, max_length=100, description="AIFA 会话 ID")
    analysis_draft_id: Optional[str] = Field(None, max_length=100, description="分析草稿 ID，用于幂等防重放")
    version: Optional[str] = Field(None, max_length=100, description="版本戳")
    nonce: Optional[str] = Field(None, max_length=100, description="随机串")


class ApplyFailureReasonResponse(BaseModel):
    success: bool = True
    history_id: int
    applied: bool
    analyzed_updated: bool
    message: str


class RejectFailureReasonRequest(BaseModel):
    history_id: int = Field(..., ge=1, description="执行历史 ID")
    session_id: Optional[str] = Field(None, max_length=100, description="AIFA 会话 ID")
    analysis_draft_id: Optional[str] = Field(None, max_length=100, description="分析草稿 ID")
    reason: Optional[str] = Field(None, max_length=500, description="拒绝原因（可选）")


class RejectFailureReasonResponse(BaseModel):
    success: bool = True
    history_id: int
    rejected: bool = True
    message: str = "已拒绝本次分析结果"


class AnalyzeRequest(BaseModel):
    history_id: int = Field(..., ge=1, description="执行历史 ID")
    mode: Literal["initial", "follow_up"] = Field("initial", description="分析模式")
    session_id: Optional[str] = Field(None, max_length=100, description="AIFA 会话 ID")
    follow_up_message: Optional[str] = Field(None, max_length=2000, description="追问内容")
